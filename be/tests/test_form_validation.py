import pytest

from app.form_validation import validate_form
from app.procedure_settings import load_procedure_settings

SETTINGS = load_procedure_settings()
BIRTH_FORM = SETTINGS.form_candidates["BIRTH_REGISTRATION_FORM"]
CT01_FORM = SETTINGS.form_candidates["PERMANENT_RESIDENCE_CT01_FORM"]

BASE_REQUIRED_FIELDS = {
    "applicant_full_name": "Nguyễn Văn A",
    "applicant_birth_date": "1990-01-01",
    "applicant_residence": "Hà Nội",
    "applicant_id_document": "012345678901",
    "relationship_to_child": "Cha",
    "child_full_name": "Nguyễn Văn B",
    "child_birth_date": "2026-01-01",
    "child_gender": "Nam",
    "child_ethnicity": "Kinh",
    "child_nationality": "Việt Nam",
    "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
    "child_hometown": "Hà Nội",
    "mother_full_name": "Trần Thị C",
    "mother_birth_year": "1994",
    "mother_ethnicity": "Kinh",
    "mother_nationality": "Việt Nam",
    "mother_residence": "Hà Nội",
    "mother_id_document": "012345678902",
    "copy_request_needed": "Không",
    "copy_count": 0,
}


def test_all_required_missing_is_invalid() -> None:
    result = validate_form(BIRTH_FORM, {})
    assert result.status == "invalid"
    assert result.summary.blocking_error > 0
    assert any(issue.issue_code == "FIELD_REQUIRED" for issue in result.issues)


def test_all_valid_required_fields_is_valid() -> None:
    result = validate_form(BIRTH_FORM, BASE_REQUIRED_FIELDS)
    assert result.status == "valid", result.issues
    assert result.summary.blocking_error == 0


def test_warning_only_is_valid_with_warnings() -> None:
    values = {**BASE_REQUIRED_FIELDS, "father_birth_year": "not-a-valid-year"}
    result = validate_form(BIRTH_FORM, values)
    assert result.status == "valid_with_warnings"
    assert result.summary.blocking_error == 0
    assert result.summary.warning >= 1


def test_future_birth_date_is_blocking_error() -> None:
    values = {**BASE_REQUIRED_FIELDS, "child_birth_date": "2099-01-01"}
    result = validate_form(BIRTH_FORM, values)
    assert result.status == "invalid"
    assert any(issue.issue_code == "FIELD_DATE_IN_FUTURE" for issue in result.issues)


def test_citizen_id_regex_enforced() -> None:
    result = validate_form(CT01_FORM, {"applicant_full_name": "Nguyễn Văn A", "citizen_id": "123", "residence_request": "Đăng ký thường trú"})
    assert result.status == "invalid"
    assert any(issue.field_code == "citizen_id" for issue in result.issues)


def test_input_hash_is_deterministic_regardless_of_key_order() -> None:
    result_a = validate_form(CT01_FORM, {"applicant_full_name": "A", "citizen_id": "123456789012"})
    result_b = validate_form(CT01_FORM, {"citizen_id": "123456789012", "applicant_full_name": "A"})
    assert result_a.input_hash == result_b.input_hash


def test_not_applicable_is_only_accepted_for_conditional_fields() -> None:
    conditional = validate_form(CT01_FORM, {"applicant_email": "Không có"})
    forbidden = validate_form(CT01_FORM, {"applicant_full_name": "Không áp dụng"})
    assert not any(issue.field_code == "applicant_email" for issue in conditional.issues)
    assert any(issue.issue_code == "FIELD_NOT_APPLICABLE_FORBIDDEN" and issue.field_code == "applicant_full_name" for issue in forbidden.issues)


@pytest.mark.parametrize(
    ("copy_request", "copy_count", "valid"),
    [("Không", 0, True), ("Không", 1, False), ("Có", 1, True), ("Có", 0, False)],
)
def test_copy_count_matches_copy_request(copy_request: str, copy_count: int, valid: bool) -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "copy_request_needed": copy_request, "copy_count": copy_count})
    copy_issues = [issue for issue in result.issues if issue.field_code == "copy_count"]
    assert (not copy_issues) is valid


def test_future_mother_birth_year_is_blocking_error() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "2099"})
    assert result.status == "invalid"
    assert any(issue.issue_code == "FIELD_YEAR_IN_FUTURE" and issue.field_code == "mother_birth_year" for issue in result.issues)


def test_mother_born_same_year_as_child_is_blocking_error() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "2026"})
    assert result.status == "invalid"
    assert any(issue.rule_code == "MOTHER_BIRTH_YEAR_BEFORE_CHILD" for issue in result.issues)


def test_mother_born_after_child_is_blocking_error() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "2027"})
    assert result.status == "invalid"
    assert any(issue.rule_code == "MOTHER_BIRTH_YEAR_BEFORE_CHILD" for issue in result.issues)


def test_small_but_valid_age_gap_is_warning_not_blocking() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "2014"})
    assert result.status == "valid_with_warnings"
    assert result.summary.blocking_error == 0
    assert any(issue.rule_code == "MOTHER_MINIMUM_AGE_GAP" and issue.severity == "warning" for issue in result.issues)


def test_age_gap_at_the_minimum_boundary_is_clean() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "2013"})
    assert result.status == "valid"
    assert not any("MOTHER" in issue.rule_code for issue in result.issues)


def test_plausible_age_gap_has_no_cross_field_issues() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "mother_birth_year": "1994"})
    assert result.status == "valid"
    assert result.issues == []


def test_missing_mother_birth_year_is_required() -> None:
    values = dict(BASE_REQUIRED_FIELDS)
    values.pop("mother_birth_year")
    result = validate_form(BIRTH_FORM, values)
    assert result.status == "invalid"
    assert any(issue.issue_code == "FIELD_REQUIRED" and issue.field_code == "mother_birth_year" for issue in result.issues)


def test_father_cross_field_rules_mirror_mother() -> None:
    result = validate_form(BIRTH_FORM, {**BASE_REQUIRED_FIELDS, "father_birth_year": "2026"})
    assert result.status == "invalid"
    assert any(issue.rule_code == "FATHER_BIRTH_YEAR_BEFORE_CHILD" for issue in result.issues)
