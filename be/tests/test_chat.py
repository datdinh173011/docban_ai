import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.schemas import ChatRequest

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"


@pytest.fixture
def app():
    return create_app(
        Settings(llm_api_key="", llm_model="", session_ttl_seconds=1800, database_url=TEST_DATABASE_URL),
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
        Settings(llm_api_key="", llm_model="", session_cookie_secure=True, database_url=TEST_DATABASE_URL),
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
            state["form_draft"] = {"BIRTH_REGISTRATION_FORM": {}}
            await app.state.store.save(session_id, state)

            response = await client.post("/api/v1/chat/stream", json={"message": "thủ tục 5.003859 cần hồ sơ gì", "language_code": "vi"})
    payload = _complete_payload(response.text)
    assert payload["intent"] == "form_guidance"
    assert payload["citations"] == []
