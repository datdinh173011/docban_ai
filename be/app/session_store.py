import json
import secrets
from datetime import UTC, datetime

from redis.asyncio import Redis


class SessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(session_id: str) -> str:
        return f"icivi:session:{session_id}"

    async def create(self) -> str:
        session_id = secrets.token_urlsafe(32)
        state = {
            "messages": [],
            "language_code": "vi",
            "intent": "general",
            "active_procedure_code": None,
            # Repurposed to hold the currently-active form_code once a chat turn
            # resolves into one of the form-fillable procedures (see form_conversation.py).
            "active_scenario_code": None,
            "candidate_codes": [],
            "selection_filters": {},
            "pending_filter": None,
            "locality_required": False,
            "administrative_area_code": None,
            "form_draft": {},
            "last_validation": {},
        }
        await self.redis.set(self.key(session_id), json.dumps(state), ex=self.ttl_seconds)
        return session_id

    async def get(self, session_id: str) -> dict | None:
        raw = await self.redis.get(self.key(session_id))
        if raw is None:
            return None
        await self.redis.expire(self.key(session_id), self.ttl_seconds)
        return json.loads(raw)

    async def save(self, session_id: str, state: dict) -> None:
        state["updated_at"] = datetime.now(UTC).isoformat()
        await self.redis.set(self.key(session_id), json.dumps(state), ex=self.ttl_seconds)

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(self.key(session_id))
