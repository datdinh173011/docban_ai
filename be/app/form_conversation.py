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
from app.form_validation import canonicalize_field_value, field_value_is_answered
from app.procedure_catalog import normalize_text
from app.procedure_settings import FormCandidate, FormMapping, ProcedureSettings
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


def form_required_fields_complete(candidate: FormCandidate, values: dict[str, Any]) -> bool:
    """Completion is deterministic: every required field must have a non-empty value."""
    return all(not field.required or field_value_is_answered(field, values.get(field.field_code)) for field in candidate.fields)


def _reconcile_incomplete_reply(candidate: FormCandidate, values: dict[str, Any], reply: AssistantReply) -> AssistantReply:
    missing = [
        field for field in candidate.fields
        if field.required and not field_value_is_answered(field, values.get(field.field_code))
    ]
    normalized_answer = normalize_text(reply.answer)
    completion_claims = ("ghi nhan day du", "da day du", "da hoan tat", "hoan thanh bieu mau")
    if not missing or not any(claim in normalized_answer for claim in completion_claims):
        return reply
    return AssistantReply(
        intent="form_guidance",
        answer=(
            f"Đơn vẫn còn thiếu trường bắt buộc: {missing[0].label_vi.lower()}. "
            "Bạn có thể tiếp tục cung cấp thông tin hoặc chọn “Kết thúc và rà soát”."
        ),
        quick_replies=["Tiếp tục điền", "Kết thúc và rà soát"],
    )


async def maybe_fill_form(
    state: dict[str, Any],
    result: dict[str, Any],
    settings: Settings,
    procedure_settings: ProcedureSettings,
    messages: list[dict[str, str]],
) -> tuple[AssistantReply, dict[str, Any] | None]:
    """Returns (reply_to_use, form_patch_or_None). form_patch is {"form_code", "fields"}."""
    message = messages[-1]["content"]
    active_form_code = state.get("active_scenario_code")
    # An explicit keyword match against a *different* form in the new message always wins over
    # a sticky active form — otherwise, once a form is active, later messages naming a different
    # procedure (e.g. "đăng ký khai sinh" while active_scenario_code is still the construction
    # form) get silently ignored and the session stays stuck on the old form forever.
    keyword_match = resolve_form_code(None, message, procedure_settings.form_mappings)
    if keyword_match and keyword_match != active_form_code:
        form_code = keyword_match
    elif active_form_code in procedure_settings.form_candidates:
        form_code = active_form_code
    else:
        form_code = resolve_form_code(result.get("active_procedure_code"), message, procedure_settings.form_mappings)
    if form_code is None:
        return result["reply"], None

    candidate = procedure_settings.form_candidates[form_code]
    known_fields = state.get("form_draft", {}).get(form_code, {})
    form_reply = await fill_form(settings, messages[-6:], state.get("language_code", "vi"), candidate, known_fields)
    newly_extracted = {}
    for field_code, value in form_reply.extracted_fields.items():
        field = candidate.field_by_code(field_code)
        if value and field is not None:
            newly_extracted[field_code] = canonicalize_field_value(field, value)
    merged_fields = {**known_fields, **newly_extracted}
    new_reply = AssistantReply(intent="form_guidance", answer=form_reply.answer, quick_replies=form_reply.quick_replies)
    new_reply = _reconcile_incomplete_reply(candidate, merged_fields, new_reply)
    return new_reply, {
        "form_code": form_code,
        "fields": merged_fields,
        "complete": form_required_fields_complete(candidate, merged_fields),
    }
