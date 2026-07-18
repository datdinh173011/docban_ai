import httpx
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.schemas import ChatRequest


class FakeTranslationService:
    def __init__(self) -> None:
        self.to_vietnamese_calls: list[tuple[str, str]] = []
        self.from_vietnamese_calls: list[tuple[str, str]] = []

    async def to_vietnamese(self, text: str, locale: str) -> str:
        self.to_vietnamese_calls.append((text, locale))
        return "thủ tục 5.003859 cần hồ sơ gì"

    async def from_vietnamese(self, text: str, locale: str) -> str:
        self.from_vietnamese_calls.append((text, locale))
        return f"[{locale}] {text}"

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"


@pytest.fixture
def app():
    return create_app(
        Settings(
            llm_api_key="",
            llm_model="",
            llm_debug_logging=False,
            environment="LOCAL",
            session_ttl_seconds=1800,
            database_url=TEST_DATABASE_URL,
        ),
        FakeRedis(decode_responses=True),
    )


@pytest.mark.asyncio
async def test_session_cookie_is_http_only(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/sessions")
    assert response.status_code == 204
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "icivi_session" not in response.text


@pytest.mark.asyncio
async def test_session_cookie_is_secure_when_enabled() -> None:
    app = create_app(
        Settings(llm_api_key="", llm_model="", environment="LOCAL", session_cookie_secure=True, database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            response = await client.post("/api/v1/sessions")
    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_chat_streams_mock_response_and_keeps_session_server_side(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/chat/stream", json={"message": "Tôi cần hỗ trợ", "language_code": "vi"})
    assert response.status_code == 200
    assert "event: message.delta" in response.text
    assert "event: message.complete" in response.text
    assert "httponly" in response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_non_vietnamese_chat_requires_translation_consent(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/chat/stream", json={"message": "Help me", "language_code": "en"})
    assert response.status_code == 200
    assert "event: translation.consent_required" in response.text


@pytest.mark.asyncio
async def test_non_vietnamese_chat_translates_before_rag_and_after_reply(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None
        translator = FakeTranslationService()
        app.state.translation_service = translator
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/chat/stream", json={
                "message": "What documents do I need?",
                "language_code": "en",
                "translation_consent": True,
            })
    assert translator.to_vietnamese_calls == [("What documents do I need?", "en")]
    assert translator.from_vietnamese_calls
    assert "[en]" in response.text


@pytest.mark.asyncio
async def test_delete_session_clears_cookie(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            response = await client.delete("/api/v1/sessions/current")
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_chat_request_no_longer_exposes_external_llm_consent() -> None:
    assert "external_llm_consent" not in ChatRequest.model_fields


def _complete_payload(sse_text: str) -> dict:
    import json

    for line in sse_text.splitlines():
        if line.startswith("data:") and '"form_code"' in line:
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError(f"no message.complete payload found in: {sse_text!r}")


@pytest.mark.asyncio
async def test_citations_included_for_a_genuine_procedure_guidance_reply(app) -> None:
    """5.003859 is a real, national-scope (no locality gate) catalog record with retrievable
    sections, so this message deterministically produces a procedure_guidance reply with
    non-empty citations — the baseline the suppression test below is contrasted against."""
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None  # avoid the unreachable test database
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/chat/stream", json={"message": "thủ tục 5.003859 cần hồ sơ gì", "language_code": "vi"})
    payload = _complete_payload(response.text)
    assert payload["intent"] == "procedure_guidance"
    assert len(payload["citations"]) > 0


@pytest.mark.asyncio
async def test_citations_are_suppressed_when_form_guidance_overrides_the_reply(app) -> None:
    """Regression test: a session already stuck on a form (active_scenario_code set) that
    receives a message which would deterministically resolve to a real, citation-bearing
    procedure_guidance reply must not leak those citations once maybe_fill_form overrides
    the reply to form_guidance."""
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["active_scenario_code"] = "BIRTH_REGISTRATION_FORM"
            state["active_procedure_code"] = "5.003859"
            state["form_draft"] = {"BIRTH_REGISTRATION_FORM": {}}
            await app.state.store.save(session_id, state)

            response = await client.post("/api/v1/chat/stream", json={"message": "Cần hồ sơ gì?", "language_code": "vi"})
    payload = _complete_payload(response.text)
    assert payload["intent"] == "form_guidance"
    assert payload["citations"] == []


@pytest.mark.asyncio
async def test_review_request_opens_active_form_and_skips_procedure_rag(app, monkeypatch) -> None:
    async with app.router.lifespan_context(app):
        async def fail_if_called(_state):
            raise AssertionError("procedure pipeline must not run for a form review route")

        monkeypatch.setattr(app.state.procedure_pipeline, "ainvoke", fail_if_called)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["active_scenario_code"] = "BIRTH_REGISTRATION_FORM"
            state["conversation_context"]["active_form_code"] = "BIRTH_REGISTRATION_FORM"
            state["form_draft"] = {"BIRTH_REGISTRATION_FORM": {"child_full_name": "Nguyễn Văn A"}}
            await app.state.store.save(session_id, state)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Tôi điền xong rồi, kiểm tra đơn giúp tôi", "language_code": "vi"},
            )

    payload = _complete_payload(response.text)
    assert payload["form_code"] == "BIRTH_REGISTRATION_FORM"
    assert payload["citations"] == []
    assert payload["ui_action"]["type"] == "open_form_review"
    assert payload["ui_action"]["auto_validate"] is True
    assert payload["ui_action"]["request_id"]


@pytest.mark.asyncio
async def test_explicit_finish_opens_incomplete_active_form_for_review(app, monkeypatch) -> None:
    async with app.router.lifespan_context(app):
        async def fail_if_called(*args, **kwargs):
            raise AssertionError("finish route must skip procedure and form LLM pipelines")

        from app import main as main_module

        monkeypatch.setattr(app.state.procedure_pipeline, "ainvoke", fail_if_called)
        monkeypatch.setattr(main_module, "maybe_fill_form", fail_if_called)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["active_scenario_code"] = "CONSTRUCTION_PERMIT_REQUEST_FORM"
            state["conversation_context"]["active_form_code"] = "CONSTRUCTION_PERMIT_REQUEST_FORM"
            state["form_draft"] = {
                "CONSTRUCTION_PERMIT_REQUEST_FORM": {"owner_name": "Nguyễn Văn A"},
            }
            await app.state.store.save(session_id, state)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Không, kết thúc", "language_code": "vi"},
            )
            validation = await client.post("/api/v1/forms/CONSTRUCTION_PERMIT_REQUEST_FORM/validate")

    payload = _complete_payload(response.text)
    assert payload["form_code"] == "CONSTRUCTION_PERMIT_REQUEST_FORM"
    assert payload["ui_action"]["type"] == "open_form_review"
    assert payload["ui_action"]["auto_validate"] is True
    assert validation.json()["status"] == "invalid"
    assert any(
        issue["issue_code"] == "FIELD_REQUIRED" and issue["field_code"] == "owner_citizen_id"
        for issue in validation.json()["issues"]
    )


@pytest.mark.asyncio
async def test_finish_without_active_form_does_not_open_review(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Kết thúc", "language_code": "vi"},
            )

    payload = _complete_payload(response.text)
    assert payload["form_code"] is None
    assert payload["ui_action"] is None


@pytest.mark.asyncio
async def test_plain_no_keeps_incomplete_active_form_in_filling_flow(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["active_scenario_code"] = "CONSTRUCTION_PERMIT_REQUEST_FORM"
            state["conversation_context"]["active_form_code"] = "CONSTRUCTION_PERMIT_REQUEST_FORM"
            state["form_draft"] = {
                "CONSTRUCTION_PERMIT_REQUEST_FORM": {"owner_name": "Nguyễn Văn A"},
            }
            await app.state.store.save(session_id, state)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Không", "language_code": "vi"},
            )

    payload = _complete_payload(response.text)
    assert payload["form_code"] == "CONSTRUCTION_PERMIT_REQUEST_FORM"
    assert payload["ui_action"] is None


@pytest.mark.asyncio
async def test_completed_required_fields_trigger_automatic_review(app) -> None:
    async with app.router.lifespan_context(app):
        candidate = app.state.procedure_pipeline.procedure_settings.form_candidates["BIRTH_REGISTRATION_FORM"]
        complete_values = {field.field_code: "value" for field in candidate.fields if field.required}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["active_scenario_code"] = "BIRTH_REGISTRATION_FORM"
            state["conversation_context"]["active_form_code"] = "BIRTH_REGISTRATION_FORM"
            state["form_draft"] = {"BIRTH_REGISTRATION_FORM": complete_values}
            await app.state.store.save(session_id, state)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Thông tin cuối cùng của tôi là như vậy", "language_code": "vi"},
            )

    payload = _complete_payload(response.text)
    assert payload["form_code"] == "BIRTH_REGISTRATION_FORM"
    assert payload["ui_action"]["type"] == "open_form_review"
    assert payload["ui_action"]["auto_validate"] is True


@pytest.mark.asyncio
async def test_plain_approval_only_starts_form_when_confirmation_is_pending(app) -> None:
    async with app.router.lifespan_context(app):
        base_state = {
            "messages": [{"role": "user", "content": "Đồng ý điền đơn"}],
            "conversation_context": {},
            "active_scenario_code": None,
            "active_procedure_code": None,
        }
        without_pending = await app.state.conversation_agent.ainvoke(base_state)
        with_pending = await app.state.conversation_agent.ainvoke({
            **base_state,
            "conversation_context": {"pending_action": "confirm_form_filling"},
        })

    assert without_pending.user_action == "none"
    assert with_pending.user_action == "start_form"
    assert with_pending.route == "form_flow"


@pytest.mark.asyncio
async def test_residential_building_on_agricultural_land_requires_disambiguation(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Tôi muốn xây nhà cấp 3 trên đất nông nghiệp", "language_code": "vi"},
            )
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)

    payload = _complete_payload(response.text)
    assert "nhà để ở hay công trình phục vụ sản xuất nông nghiệp" in state["conversation_context"]["pending_question"]
    assert payload["quick_replies"] == [
        "Nhà để ở",
        "Phục vụ sản xuất nông nghiệp",
        "Mục đích khác/chưa rõ",
    ]
    assert state["active_procedure_code"] is None
    assert state["conversation_context"]["pending_action"] == (
        "scenario_disambiguation:agricultural_land_residential_conflict"
    )


@pytest.mark.asyncio
async def test_residential_choice_does_not_select_agricultural_structure_procedures(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/chat/stream",
                json={"message": "Tôi muốn xây nhà trên đất nông nghiệp", "language_code": "vi"},
            )
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Nhà để ở", "language_code": "vi"},
            )
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)

    assert "đã được chuyển mục đích sử dụng sang đất ở chưa" in state["conversation_context"]["pending_question"]
    assert not {"1.115242", "1.115243", "1.115244"} & set(state["candidate_codes"])
    assert "scenario" not in state["conversation_context"]["slots"]


@pytest.mark.asyncio
async def test_explicit_new_agricultural_structure_request_can_advance_to_locality(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "Tôi xin cấp mới công trình phục vụ sản xuất trên đất nông nghiệp",
                    "language_code": "vi",
                },
            )

    payload = _complete_payload(response.text)
    assert payload["intent"] == "procedure_guidance"
    assert "Hà Nội" in payload["quick_replies"]


@pytest.mark.asyncio
async def test_debug_trace_logs_each_layer_and_never_logs_api_key(capsys) -> None:
    class FailingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("provider unavailable")

    secret = "secret-key-that-must-not-be-logged"
    traced_app = create_app(
        Settings(
            llm_api_key=secret,
            llm_model="trace-model",
            llm_debug_logging=True,
            environment="LOCAL",
            session_ttl_seconds=1800,
            database_url=TEST_DATABASE_URL,
        ),
        FakeRedis(decode_responses=True),
    )
    async with traced_app.router.lifespan_context(traced_app):
        from app import conversation_agent

        original_client = conversation_agent.httpx.AsyncClient
        conversation_agent.httpx.AsyncClient = FailingClient
        try:
            async with AsyncClient(transport=ASGITransport(app=traced_app), base_url="http://test") as client:
                await client.post(
                    "/api/v1/chat/stream",
                    headers={"x-request-id": "trace-request-1"},
                    json={"message": "Tôi muốn xây nhà cấp 3 trên đất nông nghiệp", "language_code": "vi"},
                )
                await client.delete("/api/v1/sessions/current")
                await client.post(
                    "/api/v1/chat/stream",
                    headers={"x-request-id": "trace-request-2"},
                    json={
                        "message": "Tôi xin cấp mới công trình phục vụ sản xuất trên đất nông nghiệp",
                        "language_code": "vi",
                    },
                )
                session_id = client.cookies.get("icivi_session")
                state = await traced_app.state.store.get(session_id)
                state["conversation_context"].update({
                    "user_goal": "Tôi cần xử lý thủ tục đất đai",
                    "slots": {"group": "Đất đai"},
                    "slot_sources": {"group": "session_context"},
                    "pending_question": "Bạn cần xử lý trường hợp đất đai nào?",
                    "pending_options": [
                        "Cấp giấy chứng nhận trong dự án BĐS",
                        "Chuyển nhượng/thừa kế/tặng cho/góp vốn",
                    ],
                    "pending_slot": "scenario",
                    "pending_question_id": "trace-land-question",
                    "pending_action": None,
                })
                await traced_app.state.store.save(session_id, state)
                await client.post(
                    "/api/v1/chat/stream",
                    headers={"x-request-id": "trace-request-3"},
                    json={
                        "message": "Chuyển nhượng/thừa kế/tặng cho/góp vốn",
                        "language_code": "vi",
                    },
                )
        finally:
            conversation_agent.httpx.AsyncClient = original_client

    logs = capsys.readouterr().out
    for event in (
        "conversation_input",
        "conversation_fallback",
        "conversation_llm_request",
        "conversation_llm_fallback",
        "scenario_resolution",
            "conversation_analysis",
            "pending_answer_consumed",
            "candidate_filter",
            "procedure_ranking",
            "routing_decision",
    ):
        assert event in logs
    assert "trace-request-1" in logs
    assert "Tôi muốn xây" in logs
    assert "nhà cấp 3 trên đất nông nghiệp" in logs
    assert "mandatory_disambiguation" in logs
    assert secret not in logs


@pytest.mark.asyncio
async def test_debug_trace_is_silent_when_flag_is_disabled(app, capsys) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/chat/stream",
                json={"message": "Tôi muốn xây nhà cấp 3 trên đất nông nghiệp", "language_code": "vi"},
            )

    logs = capsys.readouterr().out
    assert "conversation_input" not in logs
    assert "conversation_llm_request" not in logs
    assert "routing_decision_detail" not in logs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    ["Chuyển nhượng/thừa kế/tặng cho/góp vốn", "CHUYỂN NHƯỢNG/THỪA KẾ/TẶNG CHO/GÓP VỐN", "2"],
)
async def test_pending_land_option_is_consumed_before_llm(app, monkeypatch, answer: str) -> None:
    async with app.router.lifespan_context(app):
        agent = app.state.conversation_agent
        agent.settings.llm_api_key = "must-not-be-used"
        agent.settings.llm_model = "must-not-be-used"

        class ForbiddenClient:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("LLM must not run for an exact pending option")

        monkeypatch.setattr("app.conversation_agent.httpx.AsyncClient", ForbiddenClient)
        analysis = await agent.ainvoke({
            "messages": [{"role": "user", "content": answer}],
            "conversation_context": {
                "user_goal": "Tôi cần xử lý thủ tục đất đai",
                "slots": {"group": "Đất đai"},
                "slot_sources": {"group": "session_context"},
                "pending_question": "Bạn cần xử lý trường hợp đất đai nào?",
                "pending_options": [
                    "Cấp giấy chứng nhận trong dự án BĐS",
                    "Chuyển nhượng/thừa kế/tặng cho/góp vốn",
                    "Khác/chưa rõ",
                ],
                "pending_slot": None,
                "pending_question_id": "land-question-1",
                "pending_action": None,
            },
            "active_scenario_code": None,
            "active_procedure_code": None,
        })

    assert analysis.route == "procedure_lookup"
    assert analysis.consumed_pending_question_id == "land-question-1"
    assert analysis.slot_updates["group"] == "Đất đai"
    assert analysis.slot_updates["scenario"] == "Chuyển nhượng/thừa kế/tặng cho/góp vốn đất"
    assert analysis.slot_sources["scenario"] == "pending_answer"
    assert "Lựa chọn: Chuyển nhượng/thừa kế/tặng cho/góp vốn" in analysis.normalized_query


@pytest.mark.asyncio
async def test_free_text_does_not_get_forced_into_pending_option(app) -> None:
    async with app.router.lifespan_context(app):
        analysis = await app.state.conversation_agent.ainvoke({
            "messages": [{"role": "user", "content": "Tôi chưa rõ trường hợp của gia đình mình"}],
            "conversation_context": {
                "slots": {"group": "Đất đai"},
                "pending_question": "Bạn cần xử lý trường hợp đất đai nào?",
                "pending_options": [
                    "Cấp giấy chứng nhận trong dự án BĐS",
                    "Chuyển nhượng/thừa kế/tặng cho/góp vốn",
                ],
                "pending_slot": "scenario",
                "pending_question_id": "land-question-2",
                "pending_action": None,
            },
            "active_scenario_code": None,
            "active_procedure_code": None,
        })

    assert analysis.consumed_pending_question_id is None


@pytest.mark.asyncio
async def test_land_branch_selection_keeps_group_and_does_not_repeat_top_level_question(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.procedure_pipeline.rag_service = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/sessions")
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            state["conversation_context"].update({
                "user_goal": "Tôi cần xử lý thủ tục đất đai",
                "slots": {"group": "Đất đai"},
                "slot_sources": {"group": "session_context"},
                "pending_question": "Bạn cần xử lý trường hợp đất đai nào?",
                "pending_options": [
                    "Cấp giấy chứng nhận trong dự án BĐS",
                    "Chuyển nhượng/thừa kế/tặng cho/góp vốn",
                    "Khác/chưa rõ",
                ],
                "pending_slot": "scenario",
                "pending_question_id": "land-question-api",
                "pending_action": None,
            })
            await app.state.store.save(session_id, state)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Chuyển nhượng/thừa kế/tặng cho/góp vốn", "language_code": "vi"},
            )
            updated = await app.state.store.get(session_id)

    payload = _complete_payload(response.text)
    assert updated["conversation_context"]["slots"]["group"] == "Đất đai"
    assert updated["conversation_context"]["slots"]["scenario"] == "Chuyển nhượng/thừa kế/tặng cho/góp vốn đất"
    assert updated["conversation_context"]["slot_sources"]["scenario"] == "pending_answer"
    assert updated["conversation_context"]["pending_question_id"] is None
    assert len(updated["candidate_codes"]) <= 10
    assert "Đất đai" not in payload["quick_replies"]
