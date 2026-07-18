"""Provider-agnostic translation used at the boundary of the Vietnamese RAG pipeline."""

import json
import logging
import re

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.llm import response_content

logger = logging.getLogger(__name__)

VIETNAMESE = "vi"
SUPPORTED_LOCALES = frozenset({"vi", "en", "mww", "km"})
_CITATION_TOKEN = re.compile(r"\[CIT-\d+\]")


class TranslationError(RuntimeError):
    """Raised when a translation cannot be trusted for retrieval."""


class TranslationPayload(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


def _parse(content: str) -> TranslationPayload:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(\{.*\})\s*```\s*", content, flags=re.DOTALL | re.IGNORECASE)
    return TranslationPayload.model_validate(json.loads(fenced.group(1) if fenced else content))


class TranslationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.translation_enabled
            and self.settings.effective_translation_api_key
            and self.settings.effective_translation_model
        )

    async def to_vietnamese(self, source_text: str, source_locale: str) -> str:
        if source_locale == VIETNAMESE:
            return source_text
        return await self._translate(source_text, source_locale, VIETNAMESE)

    async def from_vietnamese(self, source_text: str, target_locale: str) -> str:
        if target_locale == VIETNAMESE:
            return source_text
        return await self._translate(source_text, VIETNAMESE, target_locale)

    async def _translate(self, source_text: str, source_locale: str, target_locale: str) -> str:
        if source_locale not in SUPPORTED_LOCALES or target_locale not in SUPPORTED_LOCALES:
            raise TranslationError("unsupported_locale")
        if not self.is_configured:
            raise TranslationError("translation_provider_unavailable")

        prompt = (
            "Translate the user-visible text exactly from "
            f"{source_locale} to {target_locale}. Do not answer questions, add facts, summarize, "
            "or omit information. Preserve identifiers, URLs, dates, amounts, quoted text, and "
            "citation tokens such as [CIT-1] unchanged. Return JSON only: {\"text\": \"...\"}."
        )
        payload = {
            "model": self.settings.effective_translation_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": source_text},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.settings.effective_translation_api_key}"}
        url = f"{self.settings.effective_translation_base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.settings.translation_timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            translated = _parse(response_content(response)[0]).text
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.warning("translation_failed provider=%s status=%s reason=%s", self.settings.translation_provider_name, status_code, type(exc).__name__)
            raise TranslationError("translation_failed") from exc
        if _CITATION_TOKEN.findall(translated) != _CITATION_TOKEN.findall(source_text):
            logger.warning("translation_rejected provider=%s reason=citation_tokens_changed", self.settings.translation_provider_name)
            raise TranslationError("citation_tokens_changed")
        return translated
