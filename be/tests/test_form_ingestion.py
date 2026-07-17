from pathlib import Path

import pytest

from app.form_ingestion import (
    TRUST_TIER,
    build_form_draft,
    conditional_document_drafts,
    detached_house_text,
    extract_pdf_text,
    inspect_form_corpus,
    source_specs,
)

FORM_DATA_DIR = Path(__file__).resolve().parents[2] / "docs" / "form_data"


def test_all_supplied_pdfs_pass_technical_inspection() -> None:
    inspections = inspect_form_corpus(FORM_DATA_DIR)

    assert len(inspections) == 9
    assert all(inspection.valid for inspection in inspections)
    assert all(inspection.source_trust_tier == TRUST_TIER for inspection in inspections)
    assert all(len(inspection.sha256) == 64 for inspection in inspections)
    assert all(inspection.rendered_page_count == inspection.page_count for inspection in inspections)


@pytest.mark.parametrize(
    ("form_code", "expected_fields"),
    [
        ("BIRTH_REGISTRATION_FORM", {"child_full_name", "mother_full_name", "father_full_name"}),
        ("PERMANENT_RESIDENCE_CT01_FORM", {"citizen_id", "household_members"}),
        ("CONSTRUCTION_PERMIT_REQUEST_FORM", {"construction_address", "floor_count"}),
    ],
)
def test_primary_form_drafts_keep_field_provenance(form_code: str, expected_fields: set[str]) -> None:
    inspections = {item.source_key: item for item in inspect_form_corpus(FORM_DATA_DIR)}
    spec = next(item for item in source_specs().values() if item.form_code == form_code)

    draft = build_form_draft(spec, inspections[spec.source_key])

    assert draft["source_trust_tier"] == TRUST_TIER
    assert expected_fields <= {field["field_code"] for field in draft["fields"]}
    assert all(field["provenance"]["source_key"] == spec.source_key for field in draft["fields"])


def test_catalog_and_bundle_cannot_be_published_as_forms() -> None:
    inspections = {item.source_key: item for item in inspect_form_corpus(FORM_DATA_DIR)}
    for filename in ("00_danh_muc_bieu_mau_3_thu_tuc_2026.pdf", "bo_bieu_mau_3_thu_tuc_2026.pdf"):
        spec = source_specs()[filename]
        with pytest.raises(ValueError, match="noncanonical_form_source"):
            build_form_draft(spec, inspections[spec.source_key])


def test_detached_house_scope_is_extracted_without_other_construction_variants() -> None:
    spec = source_specs()["03_don_de_nghi_cap_gpxd_nha_o_rieng_le.pdf"]
    _, pdf_text = extract_pdf_text(FORM_DATA_DIR / spec.filename)
    scoped_text = detached_house_text(pdf_text)

    assert "4.4. Đối với công trình nhà ở riêng lẻ" in scoped_text
    assert "4.5. Đối với trường hợp cải tạo" not in scoped_text


def test_support_documents_remain_draft_conditional_documents() -> None:
    drafts = conditional_document_drafts()

    assert len(drafts) == 4
    assert all(draft["status"] == "draft" for draft in drafts)
    assert all("SUPPORT" in draft["support_form_code"] for draft in drafts)
