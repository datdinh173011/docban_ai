"""Bridges the deterministic chat pipeline to the isolated form-filling LLM path.

`maybe_fill_form` is the single integration point called from `main.py`'s
`chat_stream` handler, right after `ProcedurePipeline.ainvoke`. It only ever
overrides the deterministic reply when the conversation resolves to one of the
form-mapped procedures (via `resolve_form_code`) — for every other procedure it is
a no-op, so `ProcedurePipeline` itself needs no changes.
"""

from typing import Any

from app.config import Settings
from app.form_llm import fill_form
from app.procedure_catalog import normalize_text
from app.procedure_settings import FormMapping, ProcedureSettings
from app.schemas import AssistantReply


def resolve_form_code(active_procedure_code: str | None, message: str, mappings: tuple[FormMapping, ...]) -> str | None:
    if active_procedure_code:
        for mapping in mappings:
            if active_procedure_code in mapping.match_procedure_codes:
                return mapping.form_code
    normalized_message = normalize_text(message)
    for mapping in mappings:
        if any(normalize_text(keyword) in normalized_message for keyword in mapping.match_keywords):
            return mapping.form_code
    return None


async def maybe_fill_form(
    state: dict[str, Any],
    result: dict[str, Any],
    settings: Settings,
    procedure_settings: ProcedureSettings,
    messages: list[dict[str, str]],
) -> tuple[AssistantReply, dict[str, Any] | None]:
    """Returns (reply_to_use, form_patch_or_None). form_patch is {"form_code", "fields"}."""
    active_form_code = state.get("active_scenario_code")
    form_code = active_form_code if active_form_code in procedure_settings.form_candidates else None
    if form_code is None:
        form_code = resolve_form_code(result.get("active_procedure_code"), messages[-1]["content"], procedure_settings.form_mappings)
    if form_code is None:
        return result["reply"], None

    candidate = procedure_settings.form_candidates[form_code]
    known_fields = state.get("form_draft", {}).get(form_code, {})
    form_reply = await fill_form(settings, messages[-6:], state.get("language_code", "vi"), candidate, known_fields)
    newly_extracted = {
        field_code: value
        for field_code, value in form_reply.extracted_fields.items()
        if value and candidate.field_by_code(field_code) is not None
    }
    merged_fields = {**known_fields, **newly_extracted}
    new_reply = AssistantReply(intent="form_guidance", answer=form_reply.answer, quick_replies=form_reply.quick_replies)
    return new_reply, {"form_code": form_code, "fields": merged_fields}
