"""Import the audited DVC snapshot into PostgreSQL/pgvector."""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.procedure_catalog import ProcedureCatalog
from app.procedure_embeddings import ProcedureEmbeddingClient
from app.procedure_pipeline import ReviewRegistry
from app.rag import vector_literal


class ProcedureImportError(ValueError):
    pass


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_for_embedding(content: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Bound chunks before embedding, favoring paragraph/table line boundaries."""
    if max_chars <= overlap_chars:
        raise ValueError("procedure_chunk_size_must_exceed_overlap")
    if len(content) <= max_chars:
        return [content]
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + max_chars)
        if end < len(content):
            boundary = max(content.rfind("\n", start + max_chars // 2, end), content.rfind(" ", start + max_chars // 2, end))
            if boundary > start:
                end = boundary
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(content):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


async def import_snapshot(engine: AsyncEngine, settings: Settings, snapshot_code: str) -> dict[str, int]:
    """Create one immutable draft snapshot; publish is an explicit operator action."""
    source_dir = settings.procedure_snapshot_dir.resolve()
    catalog = ProcedureCatalog.from_snapshot(source_dir)
    if len(catalog.records) != 207:
        raise ProcedureImportError("snapshot_must_contain_207_procedures")
    embedder = ProcedureEmbeddingClient(settings)
    review_registry = ReviewRegistry.load(settings.procedure_review_registry_path)
    manifest_sha256 = _digest(source_dir / "procedures.json")
    crawled_at = datetime.fromisoformat(catalog.crawled_at)
    chunk_count = 0
    async with engine.begin() as connection:
        exists = await connection.scalar(text("SELECT 1 FROM procedure_snapshot WHERE snapshot_code = :code"), {"code": snapshot_code})
        if exists:
            raise ProcedureImportError("snapshot_code_already_exists")
        snapshot_id = await connection.scalar(text("""
            INSERT INTO procedure_snapshot (snapshot_code, crawled_at, source_path, procedure_count, manifest_sha256)
            VALUES (:code, :crawled_at, :source_path, :count, :digest) RETURNING id
        """), {"code": snapshot_code, "crawled_at": crawled_at, "source_path": str(source_dir), "count": len(catalog.records), "digest": manifest_sha256})
        procedure_ids: dict[str, object] = {}
        for record in catalog.records:
            procedure_id = await connection.scalar(text("""
                INSERT INTO procedure_catalog (snapshot_id, procedure_code, title, group_name, field_name, request_type, scenario,
                    locality, scope, execution_level, issuing_authority, receiving_authority, decision_number, pdf_path, pdf_sha256, data_warning)
                VALUES (:snapshot_id, :code, :title, :group_name, :field_name, :request_type, :scenario, :locality, :scope,
                    :execution_level, :issuing_authority, :receiving_authority, :decision_number, :pdf_path, :pdf_sha256, :data_warning)
                RETURNING id
            """), {"snapshot_id": snapshot_id, "code": record.code, "title": record.name, "group_name": record.group,
                "field_name": record.field, "request_type": record.request_type, "scenario": record.scenario, "locality": record.locality,
                "scope": record.scope, "execution_level": record.execution_level, "issuing_authority": record.issuing_authority,
                "receiving_authority": record.receiving_authority, "decision_number": record.decision_number, "pdf_path": record.pdf_file,
                "pdf_sha256": record.snapshot_sha256, "data_warning": record.data_warning})
            procedure_ids[record.code] = procedure_id
            drafts = [
                (section, part_no, content)
                for section in record.sections
                for part_no, content in enumerate(split_for_embedding(section.content, settings.procedure_chunk_max_chars, settings.procedure_chunk_overlap_chars))
            ]
            embeddings = await embedder.embed_many([content for _, _, content in drafts])
            for (section, part_no, content), embedding in zip(drafts, embeddings, strict=True):
                status = "reviewed" if review_registry.is_reviewed(record, section) else "snapshot"
                await connection.execute(text("""
                    INSERT INTO procedure_chunk (procedure_id, chunk_no, section_type, section_title, content, normalized_content, embedding, review_status)
                    VALUES (:procedure_id, :chunk_no, :section_type, :section_title, :content, :normalized_content, CAST(:embedding AS vector), :status)
                """), {"procedure_id": procedure_id, "chunk_no": (section.chunk_no * 10000) + part_no, "section_type": section.section_type,
                    "section_title": section.title, "content": section.content, "normalized_content": " ".join(section.content.lower().split()),
                    "embedding": vector_literal(embedding), "status": status})
                chunk_count += 1
        forms_path = source_dir / "forms.csv"
        candidates = 0
        for form_path in (source_dir / "mau_don_to_khai").iterdir():
            if form_path.suffix.lower() not in {".doc", ".docx"}:
                continue
            await connection.execute(text("""
                INSERT INTO procedure_form_candidate (snapshot_id, filename, relative_path, sha256)
                VALUES (:snapshot_id, :filename, :relative_path, :sha256)
            """), {"snapshot_id": snapshot_id, "filename": form_path.name,
                "relative_path": str(form_path.relative_to(source_dir)), "sha256": _digest(form_path)})
            candidates += 1
        # Keep raw external references for reviewers; no unreviewed record is mapped to a procedure.
        if forms_path.exists():
            with forms_path.open(encoding="utf-8-sig", newline="") as source:
                list(csv.DictReader(source))
    return {"procedures": len(catalog.records), "chunks": chunk_count, "form_candidates": candidates}


async def publish_snapshot(engine: AsyncEngine, snapshot_code: str) -> None:
    async with engine.begin() as connection:
        updated = await connection.execute(text("""
            UPDATE procedure_snapshot SET status = 'published'
            WHERE snapshot_code = :code AND status = 'draft'
        """), {"code": snapshot_code})
        if not updated.rowcount:
            raise ProcedureImportError("snapshot_not_draft")
