from app.form_validation import validate_form
from app.procedure_settings import load_procedure_settings

SETTINGS = load_procedure_settings()
BIRTH_FORM = SETTINGS.form_candidates["BIRTH_REGISTRATION_FORM"]
CT01_FORM = SETTINGS.form_candidates["PERMANENT_RESIDENCE_CT01_FORM"]


def test_all_required_missing_is_invalid() -> None:
    result = validate_form(BIRTH_FORM, {})
    assert result.status == "invalid"
    assert result.summary.blocking_error > 0
    assert any(issue.issue_code == "FIELD_REQUIRED" for issue in result.issues)


def test_all_valid_required_fields_is_valid() -> None:
    values = {
        "applicant_full_name": "Nguyễn Văn A",
        "relationship_to_child": "Cha",
        "child_full_name": "Nguyễn Văn B",
        "child_birth_date": "2026-01-01",
        "child_gender": "Nam",
        "child_ethnicity": "Kinh",
        "child_nationality": "Việt Nam",
        "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
        "mother_full_name": "Trần Thị C",
        "copy_request_needed": "Không",
    }
    result = validate_form(BIRTH_FORM, values)
    assert result.status == "valid", result.issues
    assert result.summary.blocking_error == 0


def test_warning_only_is_valid_with_warnings() -> None:
    values = {
        "applicant_full_name": "Nguyễn Văn A",
        "relationship_to_child": "Cha",
        "child_full_name": "Nguyễn Văn B",
        "child_birth_date": "2026-01-01",
        "child_gender": "Nam",
        "child_ethnicity": "Kinh",
        "child_nationality": "Việt Nam",
        "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
        "mother_full_name": "Trần Thị C",
        "copy_request_needed": "Không",
        "applicant_id_document": "not-a-valid-id",
    }
    result = validate_form(BIRTH_FORM, values)
    assert result.status == "valid_with_warnings"
    assert result.summary.blocking_error == 0
    assert result.summary.warning >= 1


def test_future_birth_date_is_blocking_error() -> None:
    values = {
        "applicant_full_name": "Nguyễn Văn A",
        "relationship_to_child": "Cha",
        "child_full_name": "Nguyễn Văn B",
        "child_birth_date": "2099-01-01",
        "child_gender": "Nam",
        "child_ethnicity": "Kinh",
        "child_nationality": "Việt Nam",
        "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
        "mother_full_name": "Trần Thị C",
        "copy_request_needed": "Không",
    }
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
