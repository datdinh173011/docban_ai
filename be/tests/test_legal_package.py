import json
from pathlib import Path

import pytest

from app.legal_package import PackageError, parse_review_timestamp, validate_package_manifest, validate_registry_document, verify_source_content


def approved_source(source_code: str) -> dict:
    return {
        "source_code": source_code,
        "canonical_url": f"https://vbpl.example.gov.vn/{source_code}.pdf",
        "fetch_url": f"https://files.example.gov.vn/{source_code}.pdf",
        "allowed_canonical_hostname": "vbpl.example.gov.vn",
        "allowed_fetch_hostname": "files.example.gov.vn",
        "allowed_redirect_hostnames": ["cdn.example.gov.vn"],
        "issuing_authority_vi": "Cơ quan nhà nước",
        "document_number": source_code,
        "title_vi": source_code,
        "source_type": "law",
        "procedure_code": "BIRTH_REGISTRATION",
        "effective_from": "2016-01-01",
        "owner": "legal-review",
        "check_cadence_days": 30,
        "parser_profile": "legal_pdf",
        "approval_status": "approved",
        "legal_status": "active",
        "official_verified_at": "2026-07-18T00:00:00Z",
        "reviewer_id": "legal-reviewer",
    }


def package_manifest() -> dict:
    return {
        "package_code": "BIRTH_REGISTRATION",
        "version_no": 1,
        "procedure_code": "BIRTH_REGISTRATION",
        "documents": [
            {"document_code": "BIRTH_LAW_V1", "source_code": "LAW_CIVIL_STATUS_2014"},
            {"document_code": "BIRTH_DECREE_V1", "source_code": "DECREE_CIVIL_STATUS"},
        ],
        "procedure_facts": [{
            "fact_type": "legal_basis",
            "value": {"text": "Căn cứ pháp lý đã được reviewer xác nhận."},
            "source_code": "LAW_CIVIL_STATUS_2014",
            "section_reference": "Điều 1",
        }],
    }


def test_registry_requires_exact_https_hostname_and_unique_source_code() -> None:
    source = approved_source("LAW_CIVIL_STATUS_2014")
    duplicate = approved_source("LAW_CIVIL_STATUS_2014")
    duplicate["canonical_url"] = "https://unapproved.example.gov.vn/law.pdf"

    errors = validate_registry_document({"sources": [source, duplicate]})

    assert "registry_url_not_exactly_allowed:LAW_CIVIL_STATUS_2014" in errors
    assert "registry_source_duplicate:LAW_CIVIL_STATUS_2014" in errors


def test_draft_source_can_be_a_discovery_record_without_fetch_urls() -> None:
    source = approved_source("LAW_CIVIL_STATUS_2026_DISCOVERY")
    for field in ("canonical_url", "fetch_url", "allowed_canonical_hostname", "allowed_fetch_hostname", "official_verified_at", "reviewer_id"):
        source.pop(field)
    source["approval_status"] = "draft"
    source["legal_status"] = "discovery"

    assert validate_registry_document({"sources": [source]}) == []


def test_approved_source_rejects_third_party_discovery_host() -> None:
    source = approved_source("LAW_CIVIL_STATUS_2014")
    source["canonical_url"] = "https://thuvienphapluat.vn/law"
    source["allowed_canonical_hostname"] = "thuvienphapluat.vn"

    assert "registry_url_not_exactly_allowed:LAW_CIVIL_STATUS_2014" in validate_registry_document({"sources": [source]})


def test_snapshot_content_must_match_document_number_and_title() -> None:
    source = approved_source("LAW_CIVIL_STATUS_2014")
    source["document_number"] = "60/2014/QH13"
    source["title_vi"] = "Luật Hộ tịch"
    source["metadata"] = {"expected_text_markers": ["Điều 1"]}

    verify_source_content(source, "LUẬT HỘ TỊCH số 60/2014/QH13\nĐiều 1. Phạm vi điều chỉnh")
    with pytest.raises(PackageError, match="source_document_metadata_mismatch"):
        verify_source_content(source, "Nội dung của một văn bản khác")


def test_pdf_source_uses_reviewed_marker_when_ocr_title_is_imperfect() -> None:
    source = approved_source("DECREE_123_2015_ND_CP")
    source["document_number"] = "123/2015/NĐ-CP"
    source["title_vi"] = "Quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch"
    source["metadata"] = {"expected_text_markers": ["Luật Hộ tịch"]}

    verify_source_content(source, "Số 123/2015/NĐ-CP. Nghị định thi hành Luật Hộ tịch.")


def test_review_timestamp_is_timezone_aware() -> None:
    timestamp = parse_review_timestamp("2026-07-18T00:00:00Z")

    assert timestamp is not None
    assert timestamp.tzinfo is not None


def test_package_requires_fact_provenance_to_one_package_source() -> None:
    manifest = package_manifest()
    manifest["procedure_facts"][0]["source_code"] = "UNREGISTERED_SOURCE"

    assert validate_package_manifest(manifest) == ["package_fact_provenance_invalid:0"]


def test_package_accepts_supported_procedure() -> None:
    manifest = package_manifest()
    manifest["procedure_code"] = "PERMANENT_RESIDENCE"

    assert validate_package_manifest(manifest) == []


def test_package_rejects_unknown_procedure() -> None:
    manifest = package_manifest()
    manifest["procedure_code"] = "UNSUPPORTED_PROCEDURE"

    assert validate_package_manifest(manifest) == ["package_procedure_not_supported"]


@pytest.mark.parametrize(
    "registry_name",
    [
        "birth_registration_sources.template.json",
        "permanent_residence_sources.template.json",
        "construction_permit_detached_house_sources.template.json",
    ],
)
def test_v1_registry_templates_are_valid(registry_name: str) -> None:
    path = Path(__file__).parents[1] / "data" / "registry" / registry_name

    assert validate_registry_document(json.loads(path.read_text(encoding="utf-8"))) == []
