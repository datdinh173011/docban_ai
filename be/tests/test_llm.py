import json
import logging

import httpx
import pytest

from app.config import Settings
from app.llm import LlmTrace, OpenAICompatibleClient
from app.rag_types import Citation, RetrievedChunk


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": json.dumps({"intent": "general", "answer": "Câu trả lời tham khảo.", "quick_replies": []})}}]}


class FakeAsyncClient:
    payload: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
        FakeAsyncClient.payload = json
        return FakeResponse()


def evidence() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        content="PRIVATE EVIDENCE BODY",
        title="Điều 16",
        hierarchy_path=[],
        citation=Citation(
            citation_id="CIT-1",
            knowledge_chunk_id="chunk-1",
            source_code="LAW_CIVIL_STATUS_2014",
            source_title="Luật Hộ tịch",
            document_number="60/2014/QH13",
            section_reference="Điều 16",
            source_url="https://example.test/law",
            effective_from=None,
            jurisdiction_scope="national",
            administrative_area_code=None,
            quote_preview="PRIVATE EVIDENCE BODY",
        ),
    )


def trace() -> LlmTrace:
    return LlmTrace(
        request_id="request-123",
        intent="procedure_guidance",
        retrieval_plan={"procedure_code": "BIRTH_REGISTRATION"},
        confidence_score=0.8,
        confidence_band="high",
        confidence_reasons=[],
        external_search_used=False,
        structured_fact_count=1,
        hybrid_chunk_count=1,
    )


@pytest.mark.asyncio
async def test_llm_without_evidence_receives_unverified_safety_prompt(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", llm_debug_logging=False))

    reply = await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    prompt = FakeAsyncClient.payload["messages"][0]["content"]
    assert reply.answer == "Câu trả lời tham khảo."
    assert "There is no verified evidence" in prompt
    assert "do not give legal requirements" in prompt


@pytest.mark.asyncio
async def test_llm_truncates_only_excess_quick_replies(monkeypatch, caplog) -> None:
    class FourRepliesResponse(FakeResponse):
        def json(self) -> dict:
            return {"choices": [{"message": {"content": json.dumps({
                "intent": "general",
                "answer": "Câu trả lời hợp lệ.",
                "quick_replies": ["Một", "Hai", "Ba", "Bốn"],
            })}}]}

    class FourRepliesClient(FakeAsyncClient):
        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            return FourRepliesResponse()

    caplog.set_level(logging.INFO, logger="app.llm")
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FourRepliesClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", llm_debug_logging=True))

    reply = await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert reply.quick_replies == ["Một", "Hai", "Ba"]
    assert any("quick_replies_received': 4" in message and "quick_replies_normalized': True" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_llm_does_not_repair_invalid_quick_reply_type(monkeypatch) -> None:
    class InvalidRepliesResponse(FakeResponse):
        def json(self) -> dict:
            return {"choices": [{"message": {"content": json.dumps({
                "intent": "general",
                "answer": "Câu trả lời không hợp lệ.",
                "quick_replies": "Không phải danh sách",
            })}}]}

    class InvalidRepliesClient(FakeAsyncClient):
        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            return InvalidRepliesResponse()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", InvalidRepliesClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model"))

    reply = await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert reply.intent == "general"
    assert "chưa có dữ liệu thủ tục" in reply.answer


@pytest.mark.asyncio
async def test_local_transport_requests_non_streaming_json(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", environment="LOCAL"))

    await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert FakeAsyncClient.payload["stream"] is False


@pytest.mark.asyncio
async def test_production_transport_does_not_set_local_stream_flag(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", environment="PRODUCTION"))

    await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert "stream" not in FakeAsyncClient.payload


@pytest.mark.asyncio
async def test_local_transport_accepts_fenced_json_and_sse(monkeypatch) -> None:
    class SseResponse(FakeResponse):
        headers = {"content-type": "text/event-stream"}
        text = "\n".join([
            'data: {"choices":[{"delta":{"content":"```json\\n{\\\"intent\\\":\\\"general\\\","}}]}',
            'data: {"choices":[{"delta":{"content":"\\\"answer\\\":\\\"ok\\\",\\\"quick_replies\\\":[]}\\n```"}}]}',
            "data: [DONE]",
        ])

    class SseAsyncClient(FakeAsyncClient):
        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            return SseResponse()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", SseAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", environment="LOCAL"))

    reply = await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert reply.answer == "ok"


@pytest.mark.asyncio
async def test_debug_log_redacts_user_and_evidence_content(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", llm_debug_logging=True))
    user_message = "Nguyen Van A CCCD 012345678901"

    await client.reply([{"role": "user", "content": user_message}], "vi", [evidence()], trace())

    messages = "\n".join(caplog.messages)
    assert "llm_request" in messages
    assert "llm_response" in messages
    assert "request-123" in messages
    assert "LAW_CIVIL_STATUS_2014" in messages
    assert user_message not in messages
    assert "PRIVATE EVIDENCE BODY" not in messages
    assert "test-key" not in messages


@pytest.mark.asyncio
async def test_debug_log_is_disabled_by_default(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", llm_debug_logging=False))

    await client.reply([{"role": "user", "content": "message"}], "vi", [], trace())

    assert not any("llm_request" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_llm_provider_failure_falls_back_to_safe_mock(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    class ErrorResponse:
        status_code = 429

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("rate limited", request=httpx.Request("POST", "https://example.test"), response=self)

    class FailingAsyncClient(FakeAsyncClient):
        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            return ErrorResponse()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", FailingAsyncClient)
    client = OpenAICompatibleClient(Settings(llm_api_key="test-key", llm_model="test-model", llm_debug_logging=True))

    reply = await client.reply([{"role": "user", "content": "Hỗ trợ tôi"}], "vi", [])

    assert reply.intent == "general"
    assert "chưa có dữ liệu thủ tục" in reply.answer
    assert any("llm_fallback" in message and "429" in message for message in caplog.messages)
