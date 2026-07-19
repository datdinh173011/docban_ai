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

from app.procedure_settings import CrossFieldRule, FormCandidate, FormField
from app.schemas import ValidationIssue, ValidationResult, ValidationSummary

_EMPTY_VALUES = (None, "", [], {})
NOT_APPLICABLE_VALUE = "Không áp dụng"
_NOT_APPLICABLE_ALIASES = {"không áp dụng", "không có", "khong ap dung", "khong co"}


def canonical_input_hash(values: dict) -> str:
    canonical = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _is_empty(value: object) -> bool:
    return value in _EMPTY_VALUES


def is_not_applicable_value(value: object) -> bool:
    return isinstance(value, str) and " ".join(value.casefold().split()) in _NOT_APPLICABLE_ALIASES


def canonicalize_field_value(field: FormField, value: object) -> object:
    if field.allow_not_applicable and is_not_applicable_value(value):
        return NOT_APPLICABLE_VALUE
    return value


def field_value_is_answered(field: FormField, value: object) -> bool:
    if _is_empty(value):
        return False
    if is_not_applicable_value(value):
        return field.allow_not_applicable
    return True


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
    if is_not_applicable_value(value):
        if field.allow_not_applicable:
            return None
        return _issue(
            field,
            "FIELD_NOT_APPLICABLE_FORBIDDEN",
            severity="blocking_error",
            message_vi=f"{field.label_vi} không được phép chọn Không áp dụng.",
        )
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
    if field.validation.not_future_year and isinstance(value, str) and re.fullmatch(r"\d{4}", value.strip()):
        if int(value.strip()) > date.today().year:
            return _issue(field, "FIELD_YEAR_IN_FUTURE", severity="blocking_error")
    return None


def _extract_year(value: object) -> int | None:
    """A cross-field rule's endpoints may each be a full ISO date or a bare 4-digit year."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    parsed = _parse_date(text)
    if parsed is not None:
        return parsed.year
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    return None


def _check_cross_field_rule(rule: CrossFieldRule, values: dict) -> ValidationIssue | None:
    older_year = _extract_year(values.get(rule.older_field_code))
    younger_year = _extract_year(values.get(rule.younger_field_code))
    if older_year is None or younger_year is None:
        return None
    if older_year > younger_year - rule.min_gap_years:
        return ValidationIssue(
            issue_code="CROSS_FIELD_MIN_AGE_GAP",
            rule_code=rule.rule_code,
            field_code=rule.anchor_field_code,
            severity=rule.severity,
            message_vi=rule.message_vi,
            suggestion_vi=rule.suggestion_vi,
        )
    return None


def summarize_issues(issues: list[ValidationIssue]) -> ValidationSummary:
    summary = ValidationSummary()
    for issue in issues:
        setattr(summary, issue.severity, getattr(summary, issue.severity) + 1)
    return summary


def status_from_summary(summary: ValidationSummary) -> str:
    """Shared status rollup, reused by `validate_form` and by the AI-issue merge
    step in `app.form_ai_review` so both paths roll up the same way."""
    if summary.blocking_error:
        return "invalid"
    if summary.warning:
        return "valid_with_warnings"
    if summary.unable_to_verify:
        return "unable_to_validate"
    return "valid"


def validate_form(candidate: FormCandidate, values: dict) -> ValidationResult:
    issues = [issue for field in candidate.fields if (issue := _check_field(field, values.get(field.field_code))) is not None]
    copy_request = values.get("copy_request_needed")
    copy_count = values.get("copy_count")
    if candidate.form_code == "BIRTH_REGISTRATION_FORM" and copy_count not in _EMPTY_VALUES:
        try:
            parsed_copy_count = int(str(copy_count).strip())
        except ValueError:
            parsed_copy_count = None
        copy_count_field = candidate.field_by_code("copy_count")
        if copy_count_field and copy_request == "Có" and (parsed_copy_count is None or parsed_copy_count < 1):
            issues.append(_issue(copy_count_field, "COPY_COUNT_REQUIRED_WHEN_REQUESTED", severity="blocking_error", message_vi="Số lượng bản sao phải từ 1 trở lên khi có yêu cầu cấp bản sao."))
        if copy_count_field and copy_request == "Không" and parsed_copy_count != 0:
            issues.append(_issue(copy_count_field, "COPY_COUNT_MUST_BE_ZERO", severity="blocking_error", message_vi="Số lượng bản sao phải bằng 0 khi không yêu cầu cấp bản sao."))
    issues += [issue for rule in candidate.cross_field_rules if (issue := _check_cross_field_rule(rule, values)) is not None]
    summary = summarize_issues(issues)
    return ValidationResult(
        validation_id=str(uuid4()),
        form_code=candidate.form_code,
        input_hash=canonical_input_hash(values),
        status=status_from_summary(summary),
        summary=summary,
        issues=issues,
        validated_at=datetime.now(UTC).isoformat(),
    )
