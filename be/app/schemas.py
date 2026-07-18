from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language_code: str = Field(default="vi", min_length=2, max_length=12)
    external_search_consent: bool | None = None


class CitationPayload(BaseModel):
    citation_id: str
    knowledge_chunk_id: str
    source_code: str
    source_title: str
    document_number: str | None = None
    section_reference: str | None = None
    source_url: str | None = None
    effective_from: str | None = None
    jurisdiction_scope: str
    administrative_area_code: str | None = None
    quote_preview: str
    source_type: str = "government"
    source_status: str = "reviewed"
    crawled_at: str | None = None
    procedure_code: str | None = None
    snapshot_path: str | None = None


class AssistantReply(BaseModel):
    intent: Literal["procedure_guidance", "form_guidance", "general", "out_of_scope"]
    answer: str = Field(min_length=1, max_length=4000)
    quick_replies: list[str] = Field(default_factory=list, max_length=7)
    answer_strategy: Literal["high", "medium", "low", "unable_to_verify", "consent_required"] = "unable_to_verify"
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    confidence_band: Literal["high", "medium", "low"] | None = None
    confidence_reasons: list[str] = Field(default_factory=list, max_length=5)
    external_search_used: bool = False
    external_search_consent_required: bool = False
