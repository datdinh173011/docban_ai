from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Citation:
    citation_id: str
    knowledge_chunk_id: str
    source_code: str
    source_title: str
    document_number: str | None
    section_reference: str | None
    source_url: str | None
    effective_from: date | None
    jurisdiction_scope: str
    administrative_area_code: str | None
    quote_preview: str
    source_type: str = "government"
    source_status: str = "reviewed"
    crawled_at: str | None = None
    procedure_code: str | None = None
    snapshot_path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "citation_id": self.citation_id,
            "knowledge_chunk_id": self.knowledge_chunk_id,
            "source_code": self.source_code,
            "source_title": self.source_title,
            "document_number": self.document_number,
            "section_reference": self.section_reference,
            "source_url": self.source_url,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "jurisdiction_scope": self.jurisdiction_scope,
            "administrative_area_code": self.administrative_area_code,
            "quote_preview": self.quote_preview,
            "source_type": self.source_type,
            "source_status": self.source_status,
            "crawled_at": self.crawled_at,
            "procedure_code": self.procedure_code,
            "snapshot_path": self.snapshot_path,
        }


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    content: str
    title: str | None
    hierarchy_path: list[dict[str, str]]
    citation: Citation
    source_type: str = "government"
    retrieval_score: float | None = None
    rerank_score: float | None = None
    claim_ids: tuple[str, ...] = ()
