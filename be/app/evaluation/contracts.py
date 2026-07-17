from typing import Literal

from pydantic import BaseModel, Field, model_validator

Band = Literal["high", "medium", "low", "unable_to_verify"]


class EvaluationCase(BaseModel):
    case_id: str = Field(pattern=r"^BIRTH-EVAL-[0-9]{3}$")
    question: str = Field(min_length=1)
    procedure_code: Literal["BIRTH_REGISTRATION"]
    scenario_code: str = "STANDARD"
    jurisdiction_code: str | None = None
    expected_paths: list[Literal["structured_query", "hybrid_rag"]] = Field(min_length=1)
    expected_band: Band
    required_evidence_ids: list[str] = Field(default_factory=list)
    required_citation_ids: list[str] = Field(default_factory=list)
    required_fact_ids: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    external_search_expected: bool = False
    required_warning: str | None = None
    critical: bool = True
    expected_correct: bool
    reviewed: bool = False

    @model_validator(mode="after")
    def validate_legal_case(self) -> "EvaluationCase":
        if self.critical and self.expected_band == "high" and not self.required_citation_ids:
            raise ValueError("critical_high_case_requires_citation")
        if self.expected_band in {"low", "unable_to_verify"} and not self.required_warning:
            raise ValueError("low_case_requires_warning")
        return self


class EvaluationObservation(BaseModel):
    case_id: str
    retrieved_evidence_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    external_citation_ids: list[str] = Field(default_factory=list)
    answer_fact_ids: list[str] = Field(default_factory=list)
    answer_text: str = ""
    answer_strategy: Band
    confidence_score: float = Field(ge=0, le=1)
    warning: str | None = None


class EvaluationFailure(BaseModel):
    case_id: str
    category: Literal["data", "retrieval", "citation", "confidence", "groundedness", "warning", "external_authority"]
    detail: str


class EvaluationReport(BaseModel):
    package_code: str
    case_count: int
    metrics: dict[str, float]
    failures: list[EvaluationFailure]
    passed: bool
