"""Pure rule-based validation for a form draft — no LLM, no database.

Rules and Vietnamese messages come entirely from the field schema loaded via
`app.procedure_settings.get_procedure_settings().form_candidates`; this module
contains no hardcoded business text.
"""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from uuid import uuid4

from app.procedure_settings import FormCandidate, FormField
from app.schemas import ValidationIssue, ValidationResult, ValidationSummary

_EMPTY_VALUES = (None, "", [], {})


def canonical_input_hash(values: dict) -> str:
    canonical = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _is_empty(value: object) -> bool:
    return value in _EMPTY_VALUES


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _issue(field: FormField, issue_code: str, *, severity: str | None = None, message_vi: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        issue_code=issue_code,
        rule_code=field.validation.rule_code,
        field_code=field.field_code,
        severity=severity or field.validation.severity,
        message_vi=message_vi or field.validation.message_vi,
        suggestion_vi=field.validation.suggestion_vi,
    )


def _check_field(field: FormField, value: object) -> ValidationIssue | None:
    empty = _is_empty(value)
    if field.required and empty:
        return _issue(field, "FIELD_REQUIRED", severity="blocking_error")
    if empty:
        return None
    if field.data_type == "enum" and field.validation.enum_values and value not in field.validation.enum_values:
        return _issue(field, "FIELD_ENUM_INVALID", severity="blocking_error")
    if field.validation.regex and isinstance(value, str) and not re.fullmatch(field.validation.regex, value.strip()):
        return _issue(field, "FIELD_FORMAT_INVALID")
    if field.validation.max_length and isinstance(value, str) and len(value) > field.validation.max_length:
        return _issue(field, "FIELD_TOO_LONG")
    if field.data_type == "date" and field.validation.not_future_date:
        parsed = _parse_date(value)
        if parsed is None:
            return _issue(field, "FIELD_DATE_UNPARSEABLE", severity="blocking_error", message_vi=f"Định dạng ngày của {field.label_vi.lower()} không hợp lệ, cần dạng YYYY-MM-DD.")
        if parsed > date.today():
            return _issue(field, "FIELD_DATE_IN_FUTURE", severity="blocking_error")
    return None


def _summarize(issues: list[ValidationIssue]) -> ValidationSummary:
    summary = ValidationSummary()
    for issue in issues:
        setattr(summary, issue.severity, getattr(summary, issue.severity) + 1)
    return summary


def validate_form(candidate: FormCandidate, values: dict) -> ValidationResult:
    issues = [issue for field in candidate.fields if (issue := _check_field(field, values.get(field.field_code))) is not None]
    summary = _summarize(issues)
    if summary.blocking_error:
        status = "invalid"
    elif summary.warning:
        status = "valid_with_warnings"
    else:
        status = "valid"
    return ValidationResult(
        validation_id=str(uuid4()),
        form_code=candidate.form_code,
        input_hash=canonical_input_hash(values),
        status=status,
        summary=summary,
        issues=issues,
        validated_at=datetime.now(UTC).isoformat(),
    )
