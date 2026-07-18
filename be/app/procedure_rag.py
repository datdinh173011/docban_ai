"""Filtered hybrid retrieval for published DVC procedure snapshots."""

from sqlalchemy import Integer, String, bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.procedure_embeddings import ProcedureEmbeddingClient
from app.rag import vector_literal
from app.rag_types import Citation, RetrievedChunk


class ProcedureRagService:
    def __init__(self, engine: AsyncEngine, embeddings: ProcedureEmbeddingClient, limit: int = 6) -> None:
        self.engine = engine
        self.embeddings = embeddings
        self.limit = limit

    async def retrieve(self, query: str, procedure_code: str, locality: str | None) -> list[RetrievedChunk]:
        embedding = await self.embeddings.embed(query)
        statement = text("""
            WITH eligible AS (
                SELECT pc.id AS procedure_id, pc.procedure_code, pc.title AS procedure_title, pc.locality, pc.scope,
                    pc.decision_number, pc.pdf_path, ps.crawled_at, pch.id, pch.content, pch.section_title,
                    pch.section_type, pch.review_status, pch.embedding
                FROM procedure_chunk pch
                JOIN procedure_catalog pc ON pc.id = pch.procedure_id
                JOIN procedure_snapshot ps ON ps.id = pc.snapshot_id
                WHERE ps.status = 'published' AND pc.procedure_code = :procedure_code
                  AND (pc.scope = 'Trung ương' OR CAST(:locality AS TEXT) IS NOT NULL AND (
                        pc.locality ILIKE '%' || CAST(:locality AS TEXT) || '%' OR pc.locality ILIKE '%không nêu tỉnh%'))
            ), semantic AS (
                SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank FROM eligible
            ), keyword AS (
                SELECT id, row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('simple', content), websearch_to_tsquery('simple', :query)) DESC) AS rank
                FROM eligible WHERE to_tsvector('simple', content) @@ websearch_to_tsquery('simple', :query)
            ), scores AS (
                SELECT id, sum(score) AS score FROM (
                    SELECT id, 1.0 / (60 + rank) AS score FROM semantic
                    UNION ALL SELECT id, 1.0 / (60 + rank) AS score FROM keyword
                ) ranked GROUP BY id
            )
            SELECT eligible.*, scores.score FROM scores JOIN eligible USING (id)
            ORDER BY scores.score DESC, CASE section_type WHEN 'required_document' THEN 0 WHEN 'processing_time' THEN 1 ELSE 2 END
            LIMIT :limit
        """).bindparams(
            bindparam("procedure_code", type_=String()),
            bindparam("locality", type_=String()),
            bindparam("query", type_=String()),
            bindparam("embedding", type_=String()),
            bindparam("limit", type_=Integer()),
        )
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement, {"procedure_code": procedure_code, "locality": locality,
                "query": query, "embedding": vector_literal(embedding), "limit": self.limit})).mappings().all()
        chunks: list[RetrievedChunk] = []
        for position, row in enumerate(rows, start=1):
            citation = Citation(
                citation_id=f"CIT-{position}", knowledge_chunk_id=str(row["id"]), source_code=f"DVC-{row['procedure_code']}",
                source_title=row["procedure_title"], document_number=row["decision_number"], section_reference=row["section_title"],
                source_url=f"/api/v1/sources/{row['procedure_code']}", effective_from=None,
                jurisdiction_scope="province" if row["scope"] == "Địa phương" else "national",
                administrative_area_code=row["locality"] if row["scope"] == "Địa phương" else None,
                quote_preview=" ".join(row["content"].split())[:280], source_status=row["review_status"],
                crawled_at=row["crawled_at"].isoformat(), procedure_code=row["procedure_code"], snapshot_path=row["pdf_path"],
            )
            chunks.append(RetrievedChunk(str(row["id"]), row["content"], row["section_title"], [{"label": row["section_title"]}], citation, retrieval_score=float(row["score"])))
        return chunks
