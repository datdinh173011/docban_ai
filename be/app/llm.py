import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import httpx

from app.config import Settings
from app.rag_types import RetrievedChunk
from app.schemas import AssistantReply

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CIVI, a Vietnamese public-service assistant.
Do not invent citations, decide administrative eligibility, or claim that procedures are
verified outside the supplied evidence. Explain limits when sufficient evidence is absent.
Reply in the user's requested language. Return JSON only with intent, answer, quick_replies.
intent is one of procedure_guidance, form_guidance, general, out_of_scope."""


@dataclass(frozen=True)
class LlmTrace:
    request_id: str
    intent: str
    retrieval_plan: dict[str, Any]
    confidence_score: float | None
    confidence_band: str | None
    confidence_reasons: list[str]
    external_search_used: bool
    structured_fact_count: int = 0
    hybrid_chunk_count: int = 0


def _content_fingerprint(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()[:16]


def mock_reply(language_code: str, evidence: list[RetrievedChunk] | None = None) -> AssistantReply:
    is_vietnamese = language_code.lower().startswith("vi")
    if evidence:
        excerpts = " ".join(f"{chunk.content[:320]} [{chunk.citation.citation_id}]" for chunk in evidence[:2])
        return AssistantReply(intent="procedure_guidance", answer=excerpts, quick_replies=[])
    answer = (
        "Tôi đã ghi nhận yêu cầu của bạn. Phiên bản thử nghiệm này chưa có dữ liệu thủ tục "
        "chính thức để tra cứu, nên tôi chỉ có thể hướng dẫn ở mức chung. Bạn có thể cho biết "
        "bạn muốn thực hiện việc gì hoặc đang ở tỉnh/thành phố nào?"
        if is_vietnamese
        else "I have recorded your request. This early version does not yet have official procedure data, so I can only provide general guidance."
    )
    return AssistantReply(intent="general", answer=answer, quick_replies=[])


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _debug_log(
        self,
        event: str,
        trace: LlmTrace | None,
        messages: list[dict[str, str]],
        evidence: list[RetrievedChunk],
        **extra: object,
    ) -> None:
        if not self.settings.llm_debug_logging:
            return
        message_metadata = [
            {"role": message.get("role", "unknown"), "chars": len(message.get("content", "")), "sha256": _content_fingerprint(message.get("content", ""))}
            for message in messages
        ]
        evidence_metadata = [
            {
                "citation_id": chunk.citation.citation_id,
                "source_code": chunk.citation.source_code,
                "chunk_chars": len(chunk.content),
                "chunk_sha256": _content_fingerprint(chunk.content),
            }
            for chunk in evidence
        ]
        logger.info(
            "%s request_id=%s intent=%s plan=%s confidence_score=%s confidence_band=%s "
            "confidence_reasons=%s external_search_used=%s structured_fact_count=%s "
            "hybrid_chunk_count=%s messages=%s evidence=%s extra=%s",
            event,
            trace.request_id if trace else "unknown",
            trace.intent if trace else "unknown",
            trace.retrieval_plan if trace else {},
            trace.confidence_score if trace else None,
            trace.confidence_band if trace else None,
            trace.confidence_reasons if trace else [],
            trace.external_search_used if trace else False,
            trace.structured_fact_count if trace else 0,
            trace.hybrid_chunk_count if trace else 0,
            message_metadata,
            evidence_metadata,
            extra,
        )

    async def reply(
        self,
        messages: list[dict[str, str]],
        language_code: str,
        evidence: list[RetrievedChunk] | None = None,
        trace: LlmTrace | None = None,
    ) -> AssistantReply:
        evidence = evidence or []
        if not self.settings.llm_api_key or not self.settings.llm_model:
            self._debug_log("llm_skipped", trace, messages, evidence, reason="missing_configuration")
            return mock_reply(language_code, evidence)

        evidence_text = "\n".join(
            f"[{chunk.citation.citation_id}] {chunk.citation.source_title}: {chunk.content}" for chunk in evidence
        )
        grounding = (
            "Use only the supplied evidence for administrative or legal statements. "
            "Cite every such statement with its supplied [CIT-n] token. Do not create any citation token.\n"
            f"EVIDENCE:\n{evidence_text}"
            if evidence
            else "There is no verified evidence. State that official information is insufficient; do not give legal requirements."
        )

        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": f"{SYSTEM_PROMPT}\nRequested language code: {language_code}.\n{grounding}"},
                *messages,
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        try:
            self._debug_log("llm_request", trace, messages, evidence, model=self.settings.llm_model)
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            self._debug_log("llm_response", trace, messages, evidence, provider_status=response.status_code, response_chars=len(content))
            return AssistantReply.model_validate(json.loads(content))
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            self._debug_log("llm_fallback", trace, messages, evidence, reason=type(exc).__name__, provider_status=status_code)
            logger.warning("llm_fallback reason=%s provider_status=%s", type(exc).__name__, status_code)
            return mock_reply(language_code, evidence)
