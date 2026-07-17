import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.schemas import ChatRequest


@pytest.fixture
def app():
    return create_app(
        Settings(llm_api_key="", llm_model="", session_ttl_seconds=1800),
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
        Settings(llm_api_key="", llm_model="", session_cookie_secure=True),
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
