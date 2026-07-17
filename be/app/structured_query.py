"""Safe, allowlisted structured retrieval for published procedure facts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.rag_types import Citation, RetrievedChunk

FactType = Literal[
    "audience",
    "receiving_authority",
    "process",
    "required_document",
    "processing_time",
    "fee",
    "legal_basis",
]
ALLOWED_FACT_TYPES = {
    "audience",
    "receiving_authority",
    "process",
    "required_document",
    "processing_time",
    "fee",
    "legal_basis",
}


class StructuredQuerySpec(BaseModel):
    resource: Literal["procedure_fact"] = "procedure_fact"
    fact_types: list[FactType] = Field(min_length=1, max_length=4)
    procedure_code: Literal[
        "BIRTH_REGISTRATION",
        "PERMANENT_RESIDENCE",
        "CONSTRUCTION_PERMIT_DETACHED_HOUSE",
    ]
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("fact_types")
    @classmethod
    def no_duplicate_fact_types(cls, value: list[FactType]) -> list[FactType]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_fact_types")
        return value


class StructuredQueryService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def execute(
        self,
        spec: StructuredQuerySpec,
        administrative_area_code: str | None = None,
    ) -> list[RetrievedChunk]:
        statement = text("""
            WITH RECURSIVE applicable_area AS (
                SELECT id, parent_id FROM administrative_area WHERE area_code = :area_code
                UNION ALL
                SELECT parent.id, parent.parent_id
                FROM administrative_area parent
                JOIN applicable_area child ON child.parent_id = parent.id
            )
            SELECT pf.id, pf.fact_type, pf.value, pf.jurisdiction_scope,
                   area.area_code AS administrative_area_code,
                   pf.effective_from, pf.metadata, lsv.source_url, ls.source_code,
                   ls.title_vi AS source_title, ls.document_number
            FROM procedure_fact pf
            JOIN procedure_version pv ON pv.id = pf.procedure_version_id
            JOIN administrative_procedure ap ON ap.id = pv.procedure_id
            LEFT JOIN administrative_area area ON area.id = pf.administrative_area_id
            LEFT JOIN legal_source_version lsv ON lsv.id = pf.legal_source_version_id
            LEFT JOIN legal_source ls ON ls.id = lsv.legal_source_id
            WHERE ap.procedure_code = :procedure_code
              AND pv.status = 'published'
              AND pv.version_no = (
                  SELECT max(current_version.version_no)
                  FROM procedure_version current_version
                  WHERE current_version.procedure_id = pv.procedure_id
                    AND current_version.status = 'published'
              )
              AND pf.status = 'published'
              AND (pf.effective_from IS NULL OR pf.effective_from <= CURRENT_DATE)
              AND (pf.effective_to IS NULL OR pf.effective_to >= CURRENT_DATE)
              AND pf.fact_type = ANY(CAST(:fact_types AS text[]))
              AND (
                  pf.jurisdiction_scope = 'national'
                  OR (:area_code IS NOT NULL AND pf.administrative_area_id IN
                      (SELECT id FROM applicable_area))
              )
            ORDER BY CASE pf.jurisdiction_scope
                WHEN 'district' THEN 0 WHEN 'province' THEN 1 ELSE 2 END,
                pf.updated_at DESC
            LIMIT :limit
        """)
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement, {
                "procedure_code": spec.procedure_code,
                "fact_types": spec.fact_types,
                "area_code": administrative_area_code,
                "limit": spec.limit,
            })).mappings().all()
        return [self._to_evidence(dict(row), position) for position, row in enumerate(rows, start=1)]

    @staticmethod
    def _to_evidence(row: dict, position: int) -> RetrievedChunk:
        value = row["value"]
        content = value.get("text", "") if isinstance(value, dict) else str(value)
        source_title = row["source_title"] or "Dữ liệu thủ tục đã kiểm duyệt"
        citation = Citation(
            citation_id=f"CIT-S{position}",
            knowledge_chunk_id=f"FACT-{row['id']}",
            source_code=row["source_code"] or "PROCEDURE_FACT",
            source_title=source_title,
            document_number=row["document_number"],
            section_reference=row["metadata"].get("section_reference", row["fact_type"]),
            source_url=row["source_url"],
            effective_from=row["effective_from"] if isinstance(row["effective_from"], date) else None,
            jurisdiction_scope=row["jurisdiction_scope"],
            administrative_area_code=row["administrative_area_code"],
            quote_preview=content[:280],
        )
        return RetrievedChunk(
            chunk_id=f"FACT-{row['id']}",
            content=content,
            title=row["fact_type"],
            hierarchy_path=[],
            citation=citation,
            retrieval_score=1.0,
            rerank_score=1.0,
            claim_ids=(row["fact_type"],),
        )
