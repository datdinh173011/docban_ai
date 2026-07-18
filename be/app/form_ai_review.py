"""AI-assisted second pass over a form draft, layered on top of the pure rule
engine in `app.form_validation`. Mirrors `app.form_llm`'s pattern: an isolated
LLM call site with its own request/response models and its own degrade-to-empty
fallback, so a provider hiccup never breaks the deterministic result.

The rule engine's findings are always authoritative and are never dropped or
overridden here — `ai_review_form()` only proposes *additional* issues, and
`merge_ai_issues()` only adds them where the rule engine didn't already flag
the same field.
"""

import json
import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.form_validation import status_from_summary, summarize_issues
from app.llm import response_content
from app.procedure_settings import FormCandidate, get_procedure_settings
from app.schemas import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

_AI_RULE_CODE_PREFIX = "AI_"


class FormReviewIssue(BaseModel):
    field_code: str | None = None
    issue_code: str = Field(min_length=1, max_length=80)
    severity: Literal["blocking_error", "warning", "suggestion", "unable_to_verify"]
    message_vi: str = Field(min_length=1, max_length=500)
    suggestion_vi: str | None = None


class FormReviewReply(BaseModel):
    issues: list[FormReviewIssue] = Field(default_factory=list, max_length=20)


def parse_form_review_json(content: str) -> FormReviewReply:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(\{.*\})\s*```\s*", content, flags=re.DOTALL | re.IGNORECASE)
    payload = json.loads(fenced.group(1) if fenced else content)
    return FormReviewReply.model_validate(payload)


def _field_schema_text(candidate: FormCandidate) -> str:
    fields = [
        {
            "field_code": field.field_code,
            "label_vi": field.label_vi,
            "data_type": field.data_type,
            "required": field.required,
            "enum_values": list(field.validation.enum_values) if field.validation.enum_values else None,
        }
        for field in candidate.fields
    ]
    return json.dumps(fields, ensure_ascii=False)


def _rule_issues_text(rule_issues: list[ValidationIssue]) -> str:
    return json.dumps(
        [{"field_code": issue.field_code, "issue_code": issue.issue_code, "severity": issue.severity} for issue in rule_issues],
        ensure_ascii=False,
    )


async def ai_review_form(settings: Settings, candidate: FormCandidate, values: dict, rule_issues: list[ValidationIssue]) -> list[ValidationIssue]:
    if not settings.llm_api_key or not settings.llm_model:
        return []

    system_prompt = (
        f"{get_procedure_settings().form_review_prompt}\n"
        f"FORM: {candidate.form_code} — {candidate.title_vi}\n"
        f"FIELD_SCHEMA: {_field_schema_text(candidate)}\n"
        f"SUBMITTED_VALUES: {json.dumps(values, ensure_ascii=False)}\n"
        f"RULE_ISSUES_ALREADY_FOUND: {_rule_issues_text(rule_issues)}"
    )
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hãy rà soát biểu mẫu và trả lời đúng định dạng JSON yêu cầu."},
        ],
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
        reply = parse_form_review_json(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning("form_ai_review_fallback reason=%s provider_status=%s form_code=%s", type(exc).__name__, status_code, candidate.form_code)
        return []

    known_field_codes = {field.field_code for field in candidate.fields}
    issues: list[ValidationIssue] = []
    for item in reply.issues:
        if item.field_code is not None and item.field_code not in known_field_codes:
            logger.warning("form_ai_review_unknown_field field_code=%s form_code=%s", item.field_code, candidate.form_code)
            continue
        issues.append(
            ValidationIssue(
                issue_code=item.issue_code,
                rule_code=f"{_AI_RULE_CODE_PREFIX}{item.issue_code}",
                field_code=item.field_code,
                severity=item.severity,
                message_vi=item.message_vi,
                suggestion_vi=item.suggestion_vi,
            )
        )
    return issues


def merge_ai_issues(result: ValidationResult, ai_issues: list[ValidationIssue]) -> ValidationResult:
    """Adds AI-proposed issues that don't collide (by field_code) with an
    existing rule issue; recomputes summary/status from the merged list.
    Rule issues are never removed or replaced. A no-op when `ai_issues` is
    empty or every AI issue targets a field the rule engine already flagged."""
    if not ai_issues:
        return result
    existing_field_codes = {issue.field_code for issue in result.issues if issue.field_code is not None}
    added = [issue for issue in ai_issues if issue.field_code not in existing_field_codes]
    if not added:
        return result
    merged_issues = [*result.issues, *added]
    summary = summarize_issues(merged_issues)
    return result.model_copy(update={"issues": merged_issues, "summary": summary, "status": status_from_summary(summary)})
