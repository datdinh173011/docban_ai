import json
from pathlib import Path

import pytest

from app.procedure_settings import load_procedure_settings


SETTINGS_DIR = Path(__file__).parents[1] / "app" / "settings"


def copy_bundle(destination: Path) -> None:
    for source in SETTINGS_DIR.rglob("*"):
        if source.is_file():
            target = destination / source.relative_to(SETTINGS_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())


def test_bundled_procedure_settings_are_valid() -> None:
    settings = load_procedure_settings(SETTINGS_DIR)

    assert settings.max_quick_replies == 7
    assert [item.attribute for item in settings.selection_filters] == [
        "group",
        "field",
        "request_type",
        "scenario",
        "audience",
    ]
    assert "EVIDENCE" in settings.grounded_response_prompt


def test_runtime_override_bundle_is_loaded_from_its_directory(tmp_path: Path) -> None:
    override = tmp_path / "runtime_settings"
    copy_bundle(override)
    selection_path = override / "procedure_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["filters"][0]["question"] = "Câu hỏi override?"
    selection_path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")

    settings = load_procedure_settings(override)

    assert settings.directory == override.resolve()
    assert settings.selection_filters[0].question == "Câu hỏi override?"


def test_invalid_selection_attribute_rejects_startup_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "settings"
    copy_bundle(bundle)
    selection_path = bundle / "procedure_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["filters"][0]["attribute"] = "unknown"
    selection_path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="procedure_selection_filter_attribute_invalid"):
        load_procedure_settings(bundle)


def test_birth_registration_form_has_the_expected_cross_field_rules() -> None:
    settings = load_procedure_settings(SETTINGS_DIR)
    birth = settings.form_candidates["BIRTH_REGISTRATION_FORM"]
    rule_codes = {rule.rule_code for rule in birth.cross_field_rules}
    assert rule_codes == {
        "MOTHER_BIRTH_YEAR_BEFORE_CHILD",
        "MOTHER_MINIMUM_AGE_GAP",
        "FATHER_BIRTH_YEAR_BEFORE_CHILD",
        "FATHER_MINIMUM_AGE_GAP",
    }


def test_required_field_matrix_matches_product_rules() -> None:
    settings = load_procedure_settings(SETTINGS_DIR)
    birth = settings.form_candidates["BIRTH_REGISTRATION_FORM"]
    ct01 = settings.form_candidates["PERMANENT_RESIDENCE_CT01_FORM"]
    construction = settings.form_candidates["CONSTRUCTION_PERMIT_REQUEST_FORM"]

    optional_birth_groups = {"father", "marriage"}
    assert all(field.required == (field.group_code not in optional_birth_groups) for field in birth.fields)
    assert all(field.required for field in ct01.fields)
    assert all(field.required for field in construction.fields)
    assert {field.field_code for field in ct01.fields if field.allow_not_applicable} == {"applicant_email", "household_members"}
    assert {field.field_code for field in construction.fields if field.allow_not_applicable} == {
        "representative_name",
        "representative_title",
        "representative_citizen_id",
        "design_org_name",
        "design_org_license_number",
        "review_org_name",
        "review_org_license_number",
        "setback_distance",
        "attached_documents",
    }


def _birth_form_guidance(bundle: Path) -> Path:
    return bundle / "form_guidance.json"


def test_cross_field_rule_with_unknown_field_code_rejects_startup_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "settings"
    copy_bundle(bundle)
    path = _birth_form_guidance(bundle)
    guidance = json.loads(path.read_text(encoding="utf-8"))
    birth = next(c for c in guidance["candidates"] if c["form_code"] == "BIRTH_REGISTRATION_FORM")
    birth["cross_field_rules"][0]["older_field_code"] = "not_a_real_field"
    path.write_text(json.dumps(guidance, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="cross_field_rule_unknown_field"):
        load_procedure_settings(bundle)


def test_cross_field_rule_with_invalid_severity_rejects_startup_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "settings"
    copy_bundle(bundle)
    path = _birth_form_guidance(bundle)
    guidance = json.loads(path.read_text(encoding="utf-8"))
    birth = next(c for c in guidance["candidates"] if c["form_code"] == "BIRTH_REGISTRATION_FORM")
    birth["cross_field_rules"][0]["severity"] = "not_a_real_severity"
    path.write_text(json.dumps(guidance, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="cross_field_rule_severity_invalid"):
        load_procedure_settings(bundle)
