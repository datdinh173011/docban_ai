from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language_code: Literal["vi", "en", "mww", "km"] = "vi"
    translation_consent: bool | None = None
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


class FormFieldSchema(BaseModel):
    field_code: str
    label_vi: str
    group_code: str
    data_type: Literal["string", "date", "enum", "number", "table"]
    required: bool
    allow_not_applicable: bool = False
    enum_values: list[str] | None = None


class FormGroupSchema(BaseModel):
    group_code: str
    label_vi: str
    display_order: int


class FormSchemaResponse(BaseModel):
    form_code: str
    title_vi: str
    groups: list[FormGroupSchema]
    fields: list[FormFieldSchema]


class FormDraftUpdateRequest(BaseModel):
    fields: dict[str, Any]


class FormDraftResponse(BaseModel):
    form_code: str
    fields: dict[str, Any]
    updated_at: str | None = None


class ValidationIssue(BaseModel):
    issue_code: str
    rule_code: str
    field_code: str | None
    severity: Literal["blocking_error", "warning", "suggestion", "unable_to_verify"]
    message_vi: str
    suggestion_vi: str | None = None


class ValidationSummary(BaseModel):
    blocking_error: int = 0
    warning: int = 0
    suggestion: int = 0
    unable_to_verify: int = 0


class ValidationResult(BaseModel):
    validation_id: str
    form_code: str
    input_hash: str
    status: Literal["valid", "valid_with_warnings", "invalid", "unable_to_validate"]
    summary: ValidationSummary
    issues: list[ValidationIssue]
    validated_at: str


class FormExportRequest(BaseModel):
    validation_id: str
