"""Data-driven conversation and retrieval for the DVC procedure snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.procedure_catalog import ProcedureCatalog, ProcedureRecord, ProcedureSection, normalize_text, tokens
from app.rag_types import Citation, RetrievedChunk
from app.schemas import AssistantReply
from app.procedure_rag import ProcedureRagService
from app.procedure_settings import ProcedureSettings, get_procedure_settings
SECTION_LABELS = {
    "condition": "Điều kiện/yêu cầu",
    "required_document": "Thành phần hồ sơ",
    "receiving_authority": "Cơ quan thực hiện",
    "submission": "Cách thức thực hiện",
    "processing_time": "Thời hạn giải quyết",
    "fee": "Phí, lệ phí",
    "process": "Trình tự thực hiện",
    "legal_basis": "Căn cứ pháp lý",
    "result": "Kết quả thực hiện",
    "overview": "Thông tin thủ tục",
}
QUESTION_SECTIONS = {
    "hồ sơ": {"required_document"},
    "giấy tờ": {"required_document"},
    "cần gì": {"required_document", "condition"},
    "bao lâu": {"processing_time"},
    "thời hạn": {"processing_time"},
    "lệ phí": {"fee"},
    "phí": {"fee"},
    "nộp ở đâu": {"receiving_authority", "submission"},
    "cơ quan": {"receiving_authority"},
    "quy trình": {"process"},
    "cách làm": {"process", "submission"},
    "điều kiện": {"condition"},
    "căn cứ": {"legal_basis"},
}


@dataclass(frozen=True)
class PipelineResult:
    reply: AssistantReply
    citations: list[dict[str, str | None]]
    state: dict[str, Any]


class ReviewRegistry:
    """Explicit operator approvals; omitted sections remain snapshot-only."""

    def __init__(self, approved: dict[str, set[str]] | None = None) -> None:
        self.approved = approved or {}

    @classmethod
    def load(cls, path: Path | None) -> "ReviewRegistry":
        if path is None:
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        reviewed = payload.get("reviewed_sections")
        if not isinstance(reviewed, list):
            raise ValueError("review_registry_requires_reviewed_sections")
        approved: dict[str, set[str]] = {}
        for item in reviewed:
            code, sections = item.get("procedure_code"), item.get("section_types")
            if not isinstance(code, str) or not isinstance(sections, list) or not all(isinstance(section, str) for section in sections):
                raise ValueError("review_registry_entry_invalid")
            approved.setdefault(code, set()).update(sections)
        return cls(approved)

    def is_reviewed(self, record: ProcedureRecord, section: ProcedureSection) -> bool:
        return record.data_warning == "Không có cảnh báo tự động" and section.section_type in self.approved.get(record.code, set())


def _compact(content: str, limit: int = 950) -> str:
    compacted = " ".join(content.split())
    return compacted if len(compacted) <= limit else f"{compacted[:limit].rsplit(' ', 1)[0]}..."


def _matches_answer(message: str, value: str) -> bool:
    normalized_message = normalize_text(message)
    normalized_value = normalize_text(value)
    return normalized_message == normalized_value or normalized_value in normalized_message or normalized_message in normalized_value


class ProcedurePipeline:
    def __init__(
        self,
        catalog: ProcedureCatalog,
        limit: int = 6,
        reviews: ReviewRegistry | None = None,
        rag_service: ProcedureRagService | None = None,
        procedure_settings: ProcedureSettings | None = None,
    ) -> None:
        self.catalog = catalog
        self.limit = limit
        self.reviews = reviews or ReviewRegistry()
        self.rag_service = rag_service
        self.procedure_settings = procedure_settings or get_procedure_settings()

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        result = self.respond(state)
        procedure_code = result.state.get("active_procedure_code")
        if self.rag_service and procedure_code and result.citations:
            record = self.catalog.by_code[procedure_code]
            chunks = await self.rag_service.retrieve(state["messages"][-1]["content"], procedure_code, result.state.get("administrative_area_code"))
            if chunks:
                reviewed = all(chunk.citation.source_status == "reviewed" for chunk in chunks)
                result = PipelineResult(
                    AssistantReply(intent="procedure_guidance", answer=self._checklist(record, chunks),
                        quick_replies=result.reply.quick_replies, answer_strategy="high" if reviewed else "medium",
                        confidence_score=0.9 if reviewed else 0.65, confidence_band="high" if reviewed else "medium",
                        confidence_reasons=[] if reviewed else ["snapshot_not_reviewed"]),
                    [chunk.citation.to_dict() for chunk in chunks], result.state,
                )
        return {
            "reply": result.reply,
            "citations": result.citations,
            **result.state,
        }

    def respond(self, state: dict[str, Any]) -> PipelineResult:
        message = state["messages"][-1]["content"].strip()
        if state.get("locality_required") and state.get("active_procedure_code"):
            # A locality reply is intentionally interpreted only after a procedure was selected.
            state = {**state, "administrative_area_code": message}
        selected = self._selected_record(state)
        if selected is None:
            candidates, filters = self._resolve_candidates(message, state)
            if len(candidates) == 1:
                selected = candidates[0]
            else:
                return self._clarify(candidates, filters, state)

        locality = state.get("administrative_area_code")
        if selected.is_local and not locality:
            return self._ask_locality(selected, state)
        if selected.is_local and not self._locality_matches(selected, locality):
            return self._locality_mismatch(selected, locality, state)
        return self._answer(selected, message, state)

    def _selected_record(self, state: dict[str, Any]) -> ProcedureRecord | None:
        code = state.get("active_procedure_code")
        return self.catalog.by_code.get(code) if code else None

    def _resolve_candidates(self, message: str, state: dict[str, Any]) -> tuple[list[ProcedureRecord], dict[str, str]]:
        records = self.catalog.records
        saved_codes = state.get("candidate_codes") or []
        if saved_codes:
            records = [self.catalog.by_code[code] for code in saved_codes if code in self.catalog.by_code]
        filters = dict(state.get("selection_filters") or {})
        pending_filter = state.get("pending_filter")
        if pending_filter:
            values = sorted({getattr(record, pending_filter) for record in records})
            choice = None
            if message.isdigit() and 1 <= int(message) <= len(values):
                choice = values[int(message) - 1]
            if choice is None:
                choice = next((value for value in values if _matches_answer(message, value)), None)
            if choice:
                filters[pending_filter] = choice
                records = [record for record in records if getattr(record, pending_filter) == choice]
        exact_code = next((record for record in self.catalog.records if record.code in message), None)
        if exact_code:
            return [exact_code], filters
        for selection_filter in self.procedure_settings.selection_filters:
            attribute = selection_filter.attribute
            values = {getattr(record, attribute) for record in records}
            choice = next((value for value in values if len(value) > 2 and _matches_answer(message, value)), None)
            if choice:
                filters[attribute] = choice
                records = [record for record in records if getattr(record, attribute) == choice]
        for attribute, value in filters.items():
            records = [record for record in records if getattr(record, attribute) == value]
        query_tokens = tokens(message)
        ranked = sorted(
            ((self._procedure_score(record, query_tokens), record) for record in records),
            key=lambda item: item[0],
            reverse=True,
        )
        if ranked and ranked[0][0] >= 0.72 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.20):
            return [ranked[0][1]], filters
        return records, filters

    @staticmethod
    def _procedure_score(record: ProcedureRecord, query_tokens: set[str]) -> float:
        corpus = tokens(" ".join((record.name, record.group, record.field, record.request_type, record.scenario)))
        if not query_tokens or not corpus:
            return 0.0
        overlap = len(query_tokens & corpus) / len(query_tokens)
        name_overlap = len(query_tokens & tokens(record.name)) / max(len(query_tokens), 1)
        return (0.65 * overlap) + (0.35 * name_overlap)

    def _clarify(self, candidates: list[ProcedureRecord], filters: dict[str, str], state: dict[str, Any]) -> PipelineResult:
        if not candidates:
            return self._result(
                "Tôi chưa xác định được thủ tục phù hợp từ dữ liệu snapshot. Bạn hãy mô tả mục đích và tỉnh/thành nơi thực hiện để tôi tra cứu chính xác.",
                [],
                state,
                quick_replies=[],
                confidence="low",
                reasons=["procedure_not_identified"],
            )
        for selection_filter in self.procedure_settings.selection_filters:
            attribute = selection_filter.attribute
            if attribute in filters:
                continue
            values = sorted({getattr(record, attribute) for record in candidates})
            if len(values) == 1:
                filters[attribute] = values[0]
                candidates = [record for record in candidates if getattr(record, attribute) == values[0]]
                continue
            if len(values) <= self.procedure_settings.max_quick_replies:
                return self._result(
                    selection_filter.question,
                    [],
                    state,
                    quick_replies=values[:self.procedure_settings.max_quick_replies],
                    confidence="low",
                    reasons=["procedure_clarification_required"],
                    candidate_codes=[record.code for record in candidates],
                    selection_filters=filters,
                    pending_filter=attribute,
                    selection_label=selection_filter.label,
                )
        names = sorted(candidates, key=lambda record: len(record.name))[:self.procedure_settings.max_quick_replies]
        return self._result(
            "Tôi cần bạn chọn đúng thủ tục trước khi tra cứu chi tiết.",
            [],
            state,
            quick_replies=[f"{record.code} — {record.name[:70]}" for record in names],
            confidence="low",
            reasons=["procedure_clarification_required"],
            candidate_codes=[record.code for record in candidates],
            selection_filters=filters,
            pending_filter=None,
        )

    def _ask_locality(self, record: ProcedureRecord, state: dict[str, Any]) -> PipelineResult:
        return self._result(
            f"Thủ tục “{record.name}” thuộc phạm vi địa phương. {self.procedure_settings.locality_question}",
            [],
            state,
            quick_replies=[record.locality] if "khong neu tinh" not in normalize_text(record.locality) else [],
            confidence="low",
            reasons=["locality_required"],
            active_procedure_code=record.code,
            candidate_codes=[record.code],
            locality_required=True,
        )

    @staticmethod
    def _locality_matches(record: ProcedureRecord, locality: str | None) -> bool:
        if not locality:
            return False
        if "khong neu tinh" in normalize_text(record.locality):
            return True
        return _matches_answer(locality, record.locality)

    def _locality_mismatch(self, record: ProcedureRecord, locality: str | None, state: dict[str, Any]) -> PipelineResult:
        return self._result(
            f"Snapshot chỉ có bản ghi mã {record.code} áp dụng tại {record.locality}; tôi không dùng bản ghi này cho {locality}. Vui lòng chọn thủ tục hoặc nguồn đúng địa bàn.",
            [],
            state,
            quick_replies=[],
            confidence="low",
            reasons=["locality_mismatch"],
            active_procedure_code=None,
            candidate_codes=[],
        )

    def _answer(self, record: ProcedureRecord, query: str, state: dict[str, Any]) -> PipelineResult:
        sections = self._retrieve(record, query)
        if not sections:
            return self._result(
                "Tôi chưa tìm được phần thông tin phù hợp trong PDF snapshot của thủ tục này nên không thể xác minh câu trả lời.",
                [],
                state,
                quick_replies=["Hồ sơ cần chuẩn bị", "Thời hạn giải quyết", "Cách thức thực hiện"],
                confidence="low",
                reasons=["evidence_not_found"],
                active_procedure_code=record.code,
            )
        chunks = [self._chunk(record, section, position) for position, section in enumerate(sections, start=1)]
        answer = self._checklist(record, chunks)
        reviewed = all(chunk.citation.source_status == "reviewed" for chunk in chunks)
        return self._result(
            answer,
            chunks,
            state,
            quick_replies=["Hồ sơ cần chuẩn bị", "Thời hạn giải quyết", "Cách thức thực hiện"],
            confidence="high" if reviewed else "medium",
            reasons=[] if reviewed else ["snapshot_not_reviewed"],
            active_procedure_code=record.code,
            candidate_codes=[record.code],
            locality_required=False,
        )

    def _retrieve(self, record: ProcedureRecord, query: str) -> list[ProcedureSection]:
        query_tokens = tokens(query)
        preferred = {section for phrase, section in QUESTION_SECTIONS.items() if phrase in normalize_text(query)}
        scored: list[tuple[float, ProcedureSection]] = []
        for section in record.sections:
            content_tokens = tokens(f"{section.title} {section.content}")
            lexical = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
            section_bonus = 0.55 if section.section_type in preferred else 0.0
            # Title and metadata provide a stable semantic proxy when embeddings are unavailable.
            metadata_bonus = 0.15 if query_tokens & tokens(record.name + " " + record.scenario) else 0.0
            scored.append((lexical + section_bonus + metadata_bonus, section))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [section for score, section in scored if score > 0][: self.limit]
        return selected or list(record.sections[: min(self.limit, 3)])

    def _chunk(self, record: ProcedureRecord, section: ProcedureSection, position: int) -> RetrievedChunk:
        citation = Citation(
            citation_id=f"CIT-{position}",
            knowledge_chunk_id=f"SNAPSHOT-{record.code}-{section.chunk_no}",
            source_code=f"DVC-{record.code}",
            source_title=f"Snapshot DVC: {record.name}",
            document_number=record.decision_number,
            section_reference=section.title,
            source_url=None,
            effective_from=None,
            jurisdiction_scope="province" if record.is_local else "national",
            administrative_area_code=record.locality if record.is_local else None,
            quote_preview=_compact(section.content, 280),
            source_status="reviewed" if self.reviews.is_reviewed(record, section) else "snapshot",
            crawled_at=self.catalog.crawled_at,
            procedure_code=record.code,
            snapshot_path=record.pdf_file,
        )
        return RetrievedChunk(
            chunk_id=citation.knowledge_chunk_id,
            content=_compact(section.content, 650),
            title=section.title,
            hierarchy_path=[{"label": section.title}],
            citation=citation,
            retrieval_score=None,
        )

    @staticmethod
    def _checklist(record: ProcedureRecord, chunks: list[RetrievedChunk]) -> str:
        lines = [
            f"**Thủ tục:** {record.name} (mã {record.code}).",
            f"**Phạm vi:** {record.locality}; cấp thực hiện: {record.execution_level}.",
            f"Thông tin dưới đây được trích từ bản snapshot crawl ngày {chunks[0].citation.crawled_at}; chưa phải xác nhận pháp lý cuối cùng.",
        ]
        for chunk in chunks:
            lines.append(f"**{chunk.title or 'Thông tin liên quan'}:** {_compact(chunk.content, 480)} [{chunk.citation.citation_id}]")
        return "\n\n".join(lines)

    def _result(
        self,
        answer: str,
        chunks: list[RetrievedChunk],
        state: dict[str, Any],
        *,
        quick_replies: list[str],
        confidence: str,
        reasons: list[str],
        **updates: Any,
    ) -> PipelineResult:
        reply = AssistantReply(
            intent="procedure_guidance" if chunks or updates.get("active_procedure_code") else "general",
            answer=answer,
            quick_replies=quick_replies,
            answer_strategy=confidence,
            confidence_score={"high": 0.9, "medium": 0.65, "low": 0.2}[confidence],
            confidence_band=confidence,
            confidence_reasons=reasons,
        )
        next_state = {
            "active_procedure_code": updates.get("active_procedure_code", state.get("active_procedure_code")),
            "candidate_codes": updates.get("candidate_codes", state.get("candidate_codes", [])),
            "selection_filters": updates.get("selection_filters", state.get("selection_filters", {})),
            "pending_filter": updates.get("pending_filter"),
            "locality_required": updates.get("locality_required", False),
            "administrative_area_code": updates.get("administrative_area_code", state.get("administrative_area_code")),
        }
        return PipelineResult(reply, [chunk.citation.to_dict() for chunk in chunks], next_state)
