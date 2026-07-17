import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.db import create_database_engine
from app.embeddings import EmbeddingClient
from app.external_search import DisabledExternalSearchAdapter
from app.graph import build_graph
from app.llm import OpenAICompatibleClient
from app.rag import RagService
from app.structured_query import StructuredQueryService
from app.logging_config import configure_logging
from app.schemas import ChatRequest
from app.session_store import SessionStore

logger = logging.getLogger(__name__)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:10]


def create_app(settings: Settings | None = None, redis_client: Redis | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        app.state.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.store = SessionStore(app.state.redis, settings.session_ttl_seconds)
        app.state.database = create_database_engine(settings)
        app.state.graph = build_graph(
            OpenAICompatibleClient(settings),
            RagService(app.state.database, EmbeddingClient(settings), settings.retrieval_limit),
            StructuredQueryService(app.state.database),
            DisabledExternalSearchAdapter(),
            settings.external_search_enabled,
            settings.llm_debug_logging,
        )
        yield
        await app.state.database.dispose()
        if redis_client is None:
            await app.state.redis.aclose()

    app = FastAPI(title="ICIVI MVP", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def set_session_cookie(response: Response, session_id: str) -> None:
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
            max_age=settings.session_ttl_seconds,
            path="/",
        )

    async def ensure_session(session_id: str | None) -> tuple[str, dict, bool]:
        state = await app.state.store.get(session_id) if session_id else None
        if state is not None and session_id is not None:
            return session_id, state, False
        new_session_id = await app.state.store.create()
        return new_session_id, await app.state.store.get(new_session_id) or {}, True

    @app.get("/health")
    async def health() -> dict[str, str]:
        await app.state.redis.ping()
        return {"status": "ok"}

    @app.post("/api/v1/sessions", status_code=204)
    async def create_session(session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> Response:
        response = Response(status_code=204)
        current_session_id, _, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(response, current_session_id)
        return response

    @app.delete("/api/v1/sessions/current", status_code=204)
    async def delete_session(session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> Response:
        response = Response(status_code=204)
        if session_id:
            await app.state.store.delete(session_id)
        response.delete_cookie(settings.session_cookie_name, path="/")
        return response

    @app.post("/api/v1/chat/stream")
    async def chat_stream(chat_request: ChatRequest, http_request: Request, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
        if len(chat_request.message) > settings.max_message_length:
            raise HTTPException(status_code=422, detail="Message exceeds configured length")
        current_session_id, state, is_new = await ensure_session(session_id)
        request_id = http_request.headers.get("x-request-id", "local")

        async def events() -> AsyncIterator[str]:
            started = time.perf_counter()
            try:
                messages = [*state.get("messages", []), {"role": "user", "content": chat_request.message}]
                external_search_consent = state.get("external_search_consent", False)
                if chat_request.external_search_consent is not None:
                    external_search_consent = chat_request.external_search_consent
                result = await app.state.graph.ainvoke({
                    "messages": messages,
                    "request_id": request_id,
                    "language_code": chat_request.language_code,
                    "intent": state.get("intent", "general"),
                    "external_search_consent": external_search_consent,
                    "administrative_area_code": state.get("administrative_area_code"),
                    "retrieved_chunks": [],
                    "citations": [],
                })
                reply = result["reply"]
                for word in reply.answer.split(" "):
                    yield sse("message.delta", {"text": f"{word} "})
                    await asyncio.sleep(0)
                new_state = {
                    "messages": [*messages, {"role": "assistant", "content": reply.answer}][-12:],
                    "language_code": chat_request.language_code,
                    "intent": reply.intent,
                    "external_search_consent": external_search_consent,
                }
                await app.state.store.save(current_session_id, new_state)
                yield sse("message.complete", {
                    "intent": reply.intent,
                    "quick_replies": reply.quick_replies,
                    "citations": result.get("citations", []),
                    "answer_strategy": reply.answer_strategy,
                    "confidence_score": reply.confidence_score,
                    "confidence_band": reply.confidence_band,
                    "confidence_reasons": reply.confidence_reasons,
                    "external_search_used": reply.external_search_used,
                    "external_search_consent_required": reply.external_search_consent_required,
                })
                logger.info("chat_complete request_id=%s session=%s latency_ms=%d", request_id, session_hash(current_session_id), (time.perf_counter() - started) * 1000)
            except Exception as exc:  # Keep the SSE connection protocol stable for clients.
                logger.exception("chat_error request_id=%s session=%s error=%s", request_id, session_hash(current_session_id), type(exc).__name__)
                yield sse("error", {"code": "chat_unavailable", "message": "Không thể xử lý yêu cầu lúc này."})

        stream_response = StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        if is_new:
            set_session_cookie(stream_response, current_session_id)
        return stream_response

    return app


app = create_app()
