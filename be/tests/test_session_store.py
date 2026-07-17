import pytest
from fakeredis.aioredis import FakeRedis

from app.session_store import SessionStore


@pytest.mark.asyncio
async def test_session_is_created_saved_and_deleted() -> None:
    redis = FakeRedis(decode_responses=True)
    store = SessionStore(redis, ttl_seconds=1800)

    session_id = await store.create()
    assert await store.get(session_id) == {
        "messages": [],
        "language_code": "vi",
        "intent": "general",
        "external_search_consent": False,
    }

    await store.save(session_id, {"messages": [{"role": "user", "content": "Xin chào"}], "intent": "general"})
    assert (await store.get(session_id))["messages"][0]["role"] == "user"

    await store.delete(session_id)
    assert await store.get(session_id) is None
