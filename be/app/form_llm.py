"""Isolated LLM call site for scenario-driven form slot-filling.

This module never touches `app.llm.OpenAICompatibleClient.reply()` or
`AssistantReply` — those stay dedicated to the citation-grounded procedure_guidance
path. `fill_form()` is a parallel, narrowly-scoped call: given a form's field schema
and the conversation so far, it asks for at most one missing required field per turn
and extracts only values the user explicitly stated (never inferred).
"""

import json
import logging
import re

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.llm import response_content
from app.procedure_settings import FormCandidate, get_procedure_settings

logger = logging.getLogger(__name__)


class FormFillingReply(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    quick_replies: list[str] = Field(default_factory=list, max_length=3)
    extracted_fields: dict[str, str] = Field(default_factory=dict)


def parse_form_filling_json(content: str) -> FormFillingReply:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(\{.*\})\s*```\s*", content, flags=re.DOTALL | re.IGNORECASE)
    payload = json.loads(fenced.group(1) if fenced else content)
    return FormFillingReply.model_validate(payload)


def mock_form_reply(language_code: str, candidate: FormCandidate, known_fields: dict) -> FormFillingReply:
    missing = next((field for field in candidate.fields if field.required and not known_fields.get(field.field_code)), None)
    is_vietnamese = language_code.lower().startswith("vi")
    if missing is None:
        answer = (
            "Tôi đã ghi nhận đủ các thông tin bắt buộc cho biểu mẫu này. Bạn có thể sang tab "
            "Rà soát & Kiểm tra đơn để xem lại và chỉnh sửa trước khi thẩm định."
            if is_vietnamese
            else "All required fields for this form are recorded. Check the review tab to confirm."
        )
    else:
        answer = (
            f"Bạn vui lòng cho biết: {missing.label_vi.lower()}?"
            if is_vietnamese
            else f"Could you tell me: {missing.label_vi}?"
        )
    return FormFillingReply(answer=answer, quick_replies=[])


def _field_schema_text(candidate: FormCandidate, known_fields: dict) -> str:
    missing_required = [
        {"field_code": f.field_code, "label_vi": f.label_vi, "data_type": f.data_type, "enum_values": list(f.validation.enum_values) if f.validation.enum_values else None}
        for f in candidate.fields
        if f.required and not known_fields.get(f.field_code)
    ]
    optional_remaining = [
        {"field_code": f.field_code, "label_vi": f.label_vi, "data_type": f.data_type}
        for f in candidate.fields
        if not f.required and not known_fields.get(f.field_code)
    ]
    return json.dumps({"missing_required_fields": missing_required, "optional_remaining_fields": optional_remaining}, ensure_ascii=False)


async def fill_form(
    settings: Settings,
    messages: list[dict[str, str]],
    language_code: str,
    candidate: FormCandidate,
    known_fields: dict,
) -> FormFillingReply:
    if not settings.llm_api_key or not settings.llm_model:
        return mock_form_reply(language_code, candidate, known_fields)

    system_prompt = (
        f"{get_procedure_settings().form_filling_prompt}\n"
        f"Requested language code: {language_code}.\n"
        f"FORM: {candidate.form_code} — {candidate.title_vi}\n"
        f"FIELD_SCHEMA: {_field_schema_text(candidate, known_fields)}\n"
        f"KNOWN_FIELDS: {json.dumps(known_fields, ensure_ascii=False)}\n"
        f"SCENARIO_GUIDE: {candidate.scenario_excerpt}"
    )
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "response_format": {"type": "json_object"},
    }
    if settings.environment == "LOCAL":
        payload["stream"] = False
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        content, _transport = response_content(response)
        return parse_form_filling_json(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning("form_llm_fallback reason=%s provider_status=%s form_code=%s", type(exc).__name__, status_code, candidate.form_code)
        return mock_form_reply(language_code, candidate, known_fields)
