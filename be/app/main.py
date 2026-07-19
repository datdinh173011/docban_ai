import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.db import create_database_engine
from app.form_ai_review import ai_review_form, merge_ai_issues
from app.form_conversation import maybe_fill_form
from app.form_export import ExportError, ensure_vietnamese_font, render_export
from app.form_validation import canonical_input_hash, validate_form
from app.logging_config import configure_logging
from app.procedure_catalog import load_catalog
from app.procedure_pipeline import ProcedurePipeline, ReviewRegistry
from app.procedure_embeddings import ProcedureEmbeddingClient
from app.procedure_rag import ProcedureRagService
from app.procedure_settings import get_procedure_settings
from app.schemas import (
    AssistantReply,
    ChatRequest,
    FormDraftResponse,
    FormDraftUpdateRequest,
    FormExportRequest,
    FormFieldSchema,
    FormGroupSchema,
    FormSchemaResponse,
    ValidationResult,
    VoiceStatusResponse,
    VoiceTranscriptResponse,
)
from app.session_store import SessionStore
from app.translation import TranslationError, TranslationService, VIETNAMESE
from voice_ai.speech_to_text import SpeechToTextProcessor

logger = logging.getLogger(__name__)

MAX_VOICE_UPLOAD_BYTES = 10 * 1024 * 1024
VOICE_CLIENT_ERRORS = {
    "audio_decode_failed",
    "audio_decode_timeout",
    "audio_empty",
    "audio_too_long",
    "transcript_empty",
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:10]


def create_app(settings: Settings | None = None, redis_client: Redis | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        if settings.environment == "PRODUCTION":
            ensure_vietnamese_font()
        app.state.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.store = SessionStore(app.state.redis, settings.session_ttl_seconds)
        app.state.translation_service = TranslationService(settings)
        app.state.speech_to_text = SpeechToTextProcessor()
        if not app.state.speech_to_text.preflight():
            logger.warning(
                "voice_stt_unavailable reason=%s",
                app.state.speech_to_text.unavailable_reason,
            )
        app.state.database = create_database_engine(settings)
        procedure_settings = get_procedure_settings()
        catalog = load_catalog(str(settings.procedure_snapshot_dir), str(settings.procedure_catalog_path) if settings.procedure_catalog_path else None)
        app.state.procedure_pipeline = ProcedurePipeline(
            catalog,
            settings.retrieval_limit,
            ReviewRegistry.load(settings.procedure_review_registry_path),
            ProcedureRagService(app.state.database, ProcedureEmbeddingClient(settings), settings.retrieval_limit),
            procedure_settings,
        )
        logger.info("procedure_snapshot_loaded procedure_count=%d crawled_at=%s", len(catalog.records), catalog.crawled_at)
        yield
        await app.state.database.dispose()
        if redis_client is None:
            await app.state.redis.aclose()

    app = FastAPI(title="ICIVI MVP", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
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

    @app.get("/api/v1/voice/status", response_model=VoiceStatusResponse)
    async def voice_status() -> VoiceStatusResponse:
        return VoiceStatusResponse(available=app.state.speech_to_text.preflight())

    @app.post("/api/v1/voice/transcribe", response_model=VoiceTranscriptResponse)
    async def transcribe_voice(file: UploadFile = File(...)) -> VoiceTranscriptResponse:
        processor = app.state.speech_to_text
        if not processor.preflight():
            raise HTTPException(status_code=503, detail="voice_unavailable")

        started = time.perf_counter()
        raw_audio = await file.read(MAX_VOICE_UPLOAD_BYTES + 1)
        await file.close()
        if len(raw_audio) > MAX_VOICE_UPLOAD_BYTES:
            logger.warning(
                "voice_transcription_rejected error_code=audio_too_large bytes=%d",
                len(raw_audio),
            )
            raise HTTPException(status_code=413, detail="audio_too_large")

        try:
            transcript = await run_in_threadpool(processor.transcribe, raw_audio)
        except RuntimeError as exc:
            error_code = str(exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "voice_transcription_failed error_code=%s bytes=%d latency_ms=%d",
                error_code,
                len(raw_audio),
                latency_ms,
            )
            if error_code in {"ffmpeg_unavailable", "stt_unavailable"}:
                raise HTTPException(status_code=503, detail="voice_unavailable") from exc
            if error_code in VOICE_CLIENT_ERRORS:
                raise HTTPException(status_code=422, detail=error_code) from exc
            raise

        logger.info(
            "voice_transcription_complete bytes=%d transcript_chars=%d latency_ms=%d",
            len(raw_audio),
            len(transcript),
            int((time.perf_counter() - started) * 1000),
        )
        return VoiceTranscriptResponse(text=transcript)

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
                needs_translation = chat_request.language_code != VIETNAMESE
                translation_consent = chat_request.translation_consent or state.get("translation_consent", False)
                if needs_translation and not translation_consent:
                    yield sse("translation.consent_required", {"provider": settings.translation_provider_name})
                    return
                canonical_message = await app.state.translation_service.to_vietnamese(
                    chat_request.message, chat_request.language_code,
                )
                messages = [*state.get("messages", []), {"role": "user", "content": canonical_message}]
                result = await app.state.procedure_pipeline.ainvoke({
                    "messages": messages,
                    "request_id": request_id,
                    "language_code": chat_request.language_code,
                    "active_procedure_code": state.get("active_procedure_code"),
                    "administrative_area_code": state.get("administrative_area_code"),
                    "candidate_codes": state.get("candidate_codes", []),
                    "selection_filters": state.get("selection_filters", {}),
                    "pending_filter": state.get("pending_filter"),
                    "locality_required": state.get("locality_required", False),
                })
                reply, form_patch = await maybe_fill_form(
                    {**state, "language_code": VIETNAMESE}, result, settings, app.state.procedure_pipeline.procedure_settings, messages,
                )
                canonical_answer = reply.answer
                if needs_translation:
                    reply.answer = await app.state.translation_service.from_vietnamese(reply.answer, chat_request.language_code)
                    reply.quick_replies = [
                        await app.state.translation_service.from_vietnamese(value, chat_request.language_code)
                        for value in reply.quick_replies
                    ]
                for word in reply.answer.split(" "):
                    yield sse("message.delta", {"text": f"{word} "})
                    await asyncio.sleep(0)
                form_code = form_patch["form_code"] if form_patch else None
                new_state = {
                    "messages": [*messages, {"role": "assistant", "content": canonical_answer}][-12:],
                    "language_code": chat_request.language_code,
                    "translation_consent": bool(translation_consent),
                    "intent": reply.intent,
                    "active_procedure_code": result.get("active_procedure_code"),
                    "active_scenario_code": form_code if form_code else state.get("active_scenario_code"),
                    "candidate_codes": result.get("candidate_codes", []),
                    "selection_filters": result.get("selection_filters", {}),
                    "pending_filter": result.get("pending_filter"),
                    "locality_required": result.get("locality_required", False),
                    "administrative_area_code": result.get("administrative_area_code"),
                    "form_draft": {**state.get("form_draft", {}), form_code: form_patch["fields"]} if form_patch else state.get("form_draft", {}),
                    "last_validation": state.get("last_validation", {}),
                }
                await app.state.store.save(current_session_id, new_state)
                yield sse("message.complete", {
                    "intent": reply.intent,
                    "quick_replies": reply.quick_replies,
                    # Citations belong to the deterministic pipeline's own reply; when
                    # maybe_fill_form overrides `reply` (form_guidance), those citations
                    # are stale/unrelated and must not be shown alongside a different answer.
                    "citations": result.get("citations", []) if reply.intent == "procedure_guidance" else [],
                    "answer_strategy": reply.answer_strategy,
                    "confidence_score": reply.confidence_score,
                    "confidence_band": reply.confidence_band,
                    "confidence_reasons": reply.confidence_reasons,
                    "external_search_used": reply.external_search_used,
                    "external_search_consent_required": reply.external_search_consent_required,
                    "form_code": form_code,
                    "translation_used": needs_translation,
                })
            except TranslationError as exc:
                logger.warning("translation_unavailable request_id=%s session=%s reason=%s", request_id, session_hash(current_session_id), str(exc))
                yield sse("error", {"code": "translation_unavailable", "message": "Không thể dịch yêu cầu lúc này."})
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

    @app.get("/api/v1/sources/{procedure_code}")
    async def source_pdf(procedure_code: str) -> FileResponse:
        """Serve only a published procedure PDF selected by its catalog code."""
        async with app.state.database.connect() as connection:
            pdf_path = await connection.scalar(text("""
                SELECT pc.pdf_path FROM procedure_catalog pc JOIN procedure_snapshot ps ON ps.id = pc.snapshot_id
                WHERE pc.procedure_code = :code AND ps.status = 'published' ORDER BY ps.crawled_at DESC LIMIT 1
            """), {"code": procedure_code})
        if not pdf_path:
            raise HTTPException(status_code=404, detail="Published source not found")
        root = settings.procedure_snapshot_dir.resolve()
        target = (root / pdf_path).resolve()
        if root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        return FileResponse(target, media_type="application/pdf", filename=target.name)

    def _form_candidate_or_404(form_code: str):
        candidate = app.state.procedure_pipeline.procedure_settings.form_candidates.get(form_code)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Unknown form_code")
        return candidate

    @app.get("/api/v1/forms/{form_code}/schema")
    async def form_schema(form_code: str) -> FormSchemaResponse:
        candidate = _form_candidate_or_404(form_code)
        return FormSchemaResponse(
            form_code=candidate.form_code,
            title_vi=candidate.title_vi,
            groups=[
                FormGroupSchema(group_code=group.group_code, label_vi=group.label_vi, display_order=group.display_order)
                for group in candidate.groups
            ],
            fields=[
                FormFieldSchema(
                    field_code=field.field_code,
                    label_vi=field.label_vi,
                    group_code=field.group_code,
                    data_type=field.data_type,
                    required=field.required,
                    enum_values=list(field.validation.enum_values) if field.validation.enum_values else None,
                )
                for field in candidate.fields
            ],
        )

    @app.get("/api/v1/forms/{form_code}/draft")
    async def get_form_draft(
        form_code: str, http_response: Response, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> FormDraftResponse:
        _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        return FormDraftResponse(form_code=form_code, fields=state.get("form_draft", {}).get(form_code, {}), updated_at=state.get("updated_at"))

    @app.put("/api/v1/forms/{form_code}/draft")
    async def update_form_draft(
        form_code: str,
        payload: FormDraftUpdateRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> FormDraftResponse:
        _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        merged = {**state.get("form_draft", {}).get(form_code, {}), **payload.fields}
        new_state = {**state, "form_draft": {**state.get("form_draft", {}), form_code: merged}}
        await app.state.store.save(current_session_id, new_state)
        return FormDraftResponse(form_code=form_code, fields=merged, updated_at=new_state.get("updated_at"))

    @app.post("/api/v1/forms/{form_code}/validate")
    async def validate_form_draft(
        form_code: str, http_response: Response, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> ValidationResult:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        draft = state.get("form_draft", {}).get(form_code, {})
        base_result = validate_form(candidate, draft)
        ai_issues = await ai_review_form(settings, candidate, draft, base_result.issues)
        result = merge_ai_issues(base_result, ai_issues)
        new_state = {**state, "last_validation": {**state.get("last_validation", {}), form_code: result.model_dump()}}
        await app.state.store.save(current_session_id, new_state)
        return result

    @app.post("/api/v1/forms/{form_code}/exports/pdf")
    async def export_form_pdf(
        form_code: str,
        payload: FormExportRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> Response:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        stored = state.get("last_validation", {}).get(form_code)
        if not stored or stored.get("validation_id") != payload.validation_id:
            raise HTTPException(status_code=409, detail="Unknown or mismatched validation_id; validate the form again")
        draft = state.get("form_draft", {}).get(form_code, {})
        if canonical_input_hash(draft) != stored.get("input_hash"):
            raise HTTPException(status_code=409, detail="Form data changed since validation; validate again before exporting")
        if stored.get("summary", {}).get("blocking_error", 0) > 0:
            raise HTTPException(status_code=422, detail="Form still has blocking errors; fix them before exporting")
        try:
            pdf_bytes = render_export(candidate, draft)
        except ExportError as exc:
            raise HTTPException(status_code=422, detail=f"export_failed:{exc.reason}:{exc.field_code}") from exc
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{form_code.lower()}.pdf"'},
        )

    return app


app = create_app()
