from pathlib import Path
from datetime import datetime

import pytest

from app.procedure_catalog import ProcedureCatalog, split_sections
from app.procedure_pipeline import ProcedurePipeline, ReviewRegistry
from app.config import Settings


SNAPSHOT_DIR = Path(__file__).parents[1] / "data" / "dichvucong_xaydung"


@pytest.fixture(scope="module")
def catalog() -> ProcedureCatalog:
    return ProcedureCatalog.from_snapshot(SNAPSHOT_DIR)


def test_snapshot_catalog_validates_all_procedures_and_sections(catalog: ProcedureCatalog) -> None:
    assert len(catalog.records) == 207
    assert len(catalog.by_code) == 207
    assert all(record.snapshot_sha256 and record.sections for record in catalog.records)
    assert catalog.by_code["1.013225"].decision_number == "1077/QĐ-BXD"


def test_default_snapshot_is_packaged_with_backend() -> None:
    settings = Settings(_env_file=None)
    assert settings.procedure_snapshot_dir.name == "dichvucong_xaydung"
    assert settings.procedure_snapshot_dir.parent.name == "data"


def test_snapshot_crawl_timestamp_is_accepted_by_asyncpg() -> None:
    assert datetime.fromisoformat("2026-07-17T17:45:53.8293289+07:00").tzinfo is not None


def test_pdf_section_extraction_removes_postgres_unsafe_nul_bytes() -> None:
    sections = split_sections("THÀNH PHẦN HỒ SƠ\nGiấy tờ\x00 cần nộp")
    assert sections[0].content == "THÀNH PHẦN HỒ SƠ\nGiấy tờ cần nộp"


@pytest.mark.asyncio
async def test_catalog_pipeline_requires_locality_then_returns_snapshot_citations(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    selected = await pipeline.ainvoke({"messages": [{"role": "user", "content": "1.013225"}]})

    assert selected["active_procedure_code"] == "1.013225"
    assert selected["locality_required"] is True
    assert selected["reply"].confidence_reasons == ["locality_required"]

    answered = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hà Nội"}],
        "active_procedure_code": selected["active_procedure_code"],
        "locality_required": selected["locality_required"],
    })

    assert answered["reply"].answer_strategy == "medium"
    assert answered["citations"]
    assert all(citation["source_status"] == "snapshot" for citation in answered["citations"])
    assert all(citation["procedure_code"] == "1.013225" for citation in answered["citations"])


@pytest.mark.asyncio
async def test_pipeline_never_uses_a_fixed_locality_for_another_province(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hà Nội"}],
        "active_procedure_code": "1.115729",
        "locality_required": True,
    })

    assert result["active_procedure_code"] is None
    assert result["reply"].confidence_reasons == ["locality_mismatch"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_pipeline_uses_taxonomy_for_a_single_question_with_seven_options(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({"messages": [{"role": "user", "content": "Tôi cần làm thủ tục"}]})

    assert result["pending_filter"] == "group"
    assert len(result["reply"].quick_replies) == 7
    assert result["reply"].confidence_reasons == ["procedure_clarification_required"]


@pytest.mark.asyncio
async def test_pipeline_accepts_a_numeric_taxonomy_reply(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    initial = await pipeline.ainvoke({"messages": [{"role": "user", "content": "Tôi cần làm thủ tục"}]})
    selected_group = initial["reply"].quick_replies[0]

    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "1"}],
        "candidate_codes": initial["candidate_codes"],
        "selection_filters": initial["selection_filters"],
        "pending_filter": initial["pending_filter"],
    })

    assert result["selection_filters"]["group"] == selected_group


@pytest.mark.asyncio
async def test_review_registry_only_marks_explicitly_approved_sections(tmp_path: Path, catalog: ProcedureCatalog) -> None:
    registry_path = tmp_path / "reviews.json"
    registry_path.write_text('{"reviewed_sections":[{"procedure_code":"1.013225","section_types":["required_document"]}]}', encoding="utf-8")
    pipeline = ProcedurePipeline(catalog, reviews=ReviewRegistry.load(registry_path))

    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hồ sơ cần những gì?"}],
        "active_procedure_code": "1.013225",
        "administrative_area_code": "Hà Nội",
    })

    statuses = {citation["section_reference"]: citation["source_status"] for citation in result["citations"]}
    assert statuses["Thành Phần Hồ Sơ"] == "reviewed"
