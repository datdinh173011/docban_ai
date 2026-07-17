import re
from collections.abc import Sequence
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.embeddings import EmbeddingClient
from app.rag_types import Citation, RetrievedChunk

_DOCUMENT_NUMBER = re.compile(r"\b\d{1,4}/\d{4}/[A-ZĐ-]+\b", re.IGNORECASE)


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.10g}" for value in values) + "]"


class RagService:
    """Retrieves only published, applicable chunks and produces server-owned citations."""

    def __init__(self, engine: AsyncEngine, embeddings: EmbeddingClient, limit: int = 6) -> None:
        self.engine = engine
        self.embeddings = embeddings
        self.limit = limit

    async def retrieve(
        self,
        query: str,
        language_code: str,
        procedure_code: str = "BIRTH_REGISTRATION",
        administrative_area_code: str | None = None,
    ) -> list[RetrievedChunk]:
        embedding = await self.embeddings.embed(query)
        rows = await self._hybrid_rows(query, embedding, language_code, procedure_code, administrative_area_code)
        return [self._to_chunk(row, position) for position, row in enumerate(rows, start=1)]

    async def _hybrid_rows(
        self,
        query: str,
        embedding: list[float],
        language_code: str,
        procedure_code: str,
        administrative_area_code: str | None,
    ) -> list[dict]:
        # RRF gives exact/full-text and semantic matches equal influence without mixing score scales.
        statement = text("""
            WITH RECURSIVE applicable_area AS (
                SELECT id, parent_id FROM administrative_area WHERE area_code = :area_code
                UNION ALL
                SELECT parent.id, parent.parent_id FROM administrative_area parent
                JOIN applicable_area child ON child.parent_id = parent.id
            ), eligible AS (
                SELECT kc.id, kc.content, kc.title, kc.hierarchy_path, kc.embedding,
                    kd.jurisdiction_scope, area.area_code AS administrative_area_code,
                    ls.source_code, ls.title_vi AS source_title, ls.document_number,
                    lsv.source_url, lsv.effective_from
                FROM knowledge_chunk kc
                JOIN knowledge_document kd ON kd.id = kc.knowledge_document_id
                JOIN legal_source_version lsv ON lsv.id = kd.legal_source_version_id
                JOIN legal_source ls ON ls.id = lsv.legal_source_id
                JOIN procedure_version pv ON pv.id = kd.procedure_version_id
                JOIN administrative_procedure ap ON ap.id = pv.procedure_id
                LEFT JOIN administrative_area area ON area.id = kd.administrative_area_id
                WHERE kd.status = 'published' AND lsv.status = 'published' AND pv.status = 'published'
                  AND kd.language_code = :language_code AND ap.procedure_code = :procedure_code
                  AND (lsv.effective_from IS NULL OR lsv.effective_from <= CURRENT_DATE)
                  AND (lsv.effective_to IS NULL OR lsv.effective_to >= CURRENT_DATE)
                  AND (
                    kd.jurisdiction_scope = 'national'
                    OR (:area_code IS NOT NULL AND area.id IN (SELECT id FROM applicable_area))
                  )
            ), semantic AS (
                SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank
                FROM eligible WHERE embedding IS NOT NULL
            ), keyword AS (
                SELECT id, row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('simple', content), websearch_to_tsquery('simple', :query)) DESC) AS rank
                FROM eligible WHERE to_tsvector('simple', content) @@ websearch_to_tsquery('simple', :query)
            ), exact_match AS (
                SELECT id, row_number() OVER (ORDER BY CASE WHEN :document_number <> '' AND document_number ILIKE '%' || :document_number || '%' THEN 0 ELSE 1 END, id) AS rank
                FROM eligible WHERE :document_number <> '' AND document_number ILIKE '%' || :document_number || '%'
            ), ranked AS (
                SELECT id, 1.0 / (60 + rank) AS score FROM semantic
                UNION ALL SELECT id, 1.0 / (60 + rank) FROM keyword
                UNION ALL SELECT id, 2.0 / (60 + rank) FROM exact_match
            ), scores AS (
                SELECT id, sum(score) AS score FROM ranked GROUP BY id
            )
            SELECT eligible.*, scores.score
            FROM scores JOIN eligible ON eligible.id = scores.id
            ORDER BY scores.score DESC, CASE eligible.jurisdiction_scope WHEN 'district' THEN 0 WHEN 'province' THEN 1 ELSE 2 END
            LIMIT :limit
        """)
        document_number = next(iter(_DOCUMENT_NUMBER.findall(query)), "")
        async with self.engine.connect() as connection:
            result = await connection.execute(
                statement,
                {
                    "query": query,
                    "embedding": vector_literal(embedding),
                    "language_code": language_code,
                    "procedure_code": procedure_code,
                    "area_code": administrative_area_code,
                    "document_number": document_number,
                    "limit": self.limit,
                },
            )
            return [dict(row) for row in result.mappings().all()]

    @staticmethod
    def _to_chunk(row: dict, position: int) -> RetrievedChunk:
        hierarchy = row["hierarchy_path"] or []
        section = " > ".join(part.get("label", "") for part in hierarchy if part.get("label")) or row["title"]
        citation = Citation(
            citation_id=f"CIT-{position}",
            knowledge_chunk_id=str(row["id"]),
            source_code=row["source_code"],
            source_title=row["source_title"],
            document_number=row["document_number"],
            section_reference=section,
            source_url=row["source_url"],
            effective_from=row["effective_from"],
            jurisdiction_scope=row["jurisdiction_scope"],
            administrative_area_code=row["administrative_area_code"],
            quote_preview=" ".join(row["content"].split())[:280],
        )
        return RetrievedChunk(
            chunk_id=str(row["id"]), content=row["content"], title=row["title"], hierarchy_path=hierarchy, citation=citation
        )


def citations_for(chunks: Sequence[RetrievedChunk]) -> list[dict[str, str | None]]:
    return [chunk.citation.to_dict() for chunk in chunks]


def remove_unknown_citation_tokens(answer: str, citations: Sequence[Citation]) -> str:
    allowed = {citation.citation_id for citation in citations}
    return re.sub(r"\[(CIT-\d+)\]", lambda match: match.group(0) if match.group(1) in allowed else "", answer)


def has_valid_evidence(chunks: Sequence[RetrievedChunk]) -> bool:
    return bool(chunks and any(chunk.citation.source_url or chunk.citation.document_number for chunk in chunks))
