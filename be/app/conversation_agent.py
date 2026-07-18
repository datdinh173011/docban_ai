"""Conversation understanding and routing before grounded procedure retrieval."""

from __future__ import annotations

import json
import logging
import re
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.llm import response_content
from app.procedure_catalog import ProcedureCatalog, normalize_text, tokens

logger = logging.getLogger(__name__)

Route = Literal[
    "clarify",
    "procedure_lookup",
    "procedure_follow_up",
    "form_flow",
    "form_review",
    "general",
    "out_of_scope",
]
UserAction = Literal["start_form", "continue_form", "review_form", "switch_procedure", "none"]
SlotSource = Literal["explicit_user", "pending_answer", "llm_inferred", "session_context"]

_AFFIRMATIVE = {"co", "dong y", "dong y dien don", "co dien don", "ok", "duoc", "tiep tuc"}
_REVIEW_PHRASES = (
    "ra soat",
    "kiem tra don",
    "kiem tra ho so",
    "tham dinh",
    "xem lai don",
    "mo don",
    "dien xong",
    "da dien xong",
)
_FOLLOW_UP_PHRASES = ("can gi", "giay to", "ho so", "bao lau", "le phi", "nop o dau", "cach lam")
_FORM_FINISH_PHRASES = ("ket thuc", "dung dien", "ngung dien", "ket thuc dien don", "ket thuc va ra soat")
_SCENARIO_DIR = Path(__file__).resolve().parents[1] / "data" / "scenario_groups"
_SLOT_ATTRIBUTES = {"group", "field", "request_type", "scenario", "audience", "locality"}


class ConversationAnalysis(BaseModel):
    route: Route = "procedure_lookup"
    normalized_query: str = Field(min_length=1, max_length=2000)
    slot_updates: dict[str, str] = Field(default_factory=dict)
    explicit_procedure_code: str | None = None
    missing_slot: str | None = None
    clarifying_question: str | None = None
    quick_replies: list[str] = Field(default_factory=list, max_length=7)
    confidence: float = Field(default=0.5, ge=0, le=1)
    user_action: UserAction = "none"
    slot_sources: dict[str, SlotSource] = Field(default_factory=dict)
    rejected_slots: list[dict[str, str]] = Field(default_factory=list)
    scenario_rule_id: str | None = None
    pending_question_id: str | None = None
    consumed_pending_question_id: str | None = None


def _read_list(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"conversation_scenario_invalid:{path.name}") from exc
    if not isinstance(payload, list) or not payload or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"conversation_scenario_list_required:{path.name}")
    return payload


class ConversationAgent:
    """Extracts conversational state but never supplies administrative facts."""

    def __init__(self, settings: Settings, catalog: ProcedureCatalog) -> None:
        self.settings = settings
        self.catalog = catalog
        self.topic_scenarios = _read_list(_SCENARIO_DIR / "cau_hoi_theo_de_muc.json")
        self.taxonomy = _read_list(_SCENARIO_DIR / "phan_loai_tthc.json")
        topic_names = {item.get("Đề mục") for item in self.topic_scenarios}
        taxonomy_codes = {str(item.get("Mã số", "")) for item in self.taxonomy}
        if len(topic_names) != 7 or None in topic_names:
            raise ValueError("conversation_topic_scenarios_invalid")
        if len(self.taxonomy) != len(catalog.records) or taxonomy_codes != set(catalog.by_code):
            raise ValueError("conversation_taxonomy_codes_mismatch")
        self.disambiguation_rules: dict[str, dict[str, Any]] = {}
        for topic in self.topic_scenarios:
            rules = topic.get("Quy tắc phân biệt", [])
            if not isinstance(rules, list):
                raise ValueError("conversation_disambiguation_rules_invalid")
            for rule in rules:
                rule_id = rule.get("Mã") if isinstance(rule, dict) else None
                keyword_groups = rule.get("Tất cả nhóm từ khóa") if isinstance(rule, dict) else None
                question = rule.get("Câu hỏi") if isinstance(rule, dict) else None
                options = rule.get("Lựa chọn") if isinstance(rule, dict) else None
                outcomes = rule.get("Xử lý lựa chọn") if isinstance(rule, dict) else None
                if (
                    not isinstance(rule_id, str)
                    or not rule_id
                    or rule_id in self.disambiguation_rules
                    or not isinstance(keyword_groups, list)
                    or not keyword_groups
                    or not all(isinstance(group, list) and group and all(isinstance(value, str) for value in group) for group in keyword_groups)
                    or not isinstance(question, str)
                    or not question
                    or not isinstance(options, list)
                    or len(options) < 2
                    or not all(isinstance(option, str) for option in options)
                    or not isinstance(outcomes, dict)
                    or not set(outcomes).issubset(options)
                ):
                    raise ValueError("conversation_disambiguation_rule_invalid")
                self.disambiguation_rules[rule_id] = rule

    def _trace(self, event: str, state: dict[str, Any], **payload: Any) -> None:
        if not self.settings.llm_debug_logging:
            return
        trace = state.get("trace_context") or {}
        logger.info(
            "%s request_id=%s session=%s turn=%s payload=%s",
            event,
            trace.get("request_id", state.get("request_id", "unknown")),
            trace.get("session_hash", "unknown"),
            trace.get("turn_number", len(state.get("messages", []))),
            json.dumps(payload, ensure_ascii=False, default=str),
        )

    def _rule_for_message(self, message: str) -> dict[str, Any] | None:
        normalized = normalize_text(message)
        for rule in self.disambiguation_rules.values():
            keyword_groups = rule.get("Tất cả nhóm từ khóa", [])
            if keyword_groups and all(
                any(normalize_text(keyword) in normalized for keyword in group)
                for group in keyword_groups
            ):
                return rule
        return None

    @staticmethod
    def _question_id(question: str | None, options: list[str]) -> str | None:
        if not question:
            return None
        payload = json.dumps({"question": question, "options": options}, ensure_ascii=False, sort_keys=True)
        return sha256(payload.encode("utf-8")).hexdigest()[:12]

    def _infer_missing_slot(self, question: str | None, options: list[str]) -> str | None:
        if not question:
            return None
        if normalize_text(question) == normalize_text("Bạn đang cần giải quyết vấn đề thuộc nhóm nào?"):
            return "group"
        for topic in self.topic_scenarios:
            if normalize_text(question) == normalize_text(str(topic.get("Câu hỏi nhánh", ""))):
                if topic.get("Đề mục") == "Đất đai":
                    return "scenario"
                break
        best: tuple[float, str] | None = None
        for attribute in _SLOT_ATTRIBUTES:
            values = {getattr(record, attribute) for record in self.catalog.records}
            option_scores: list[float] = []
            for option in options:
                option_tokens = tokens(option)
                score = max(
                    (len(option_tokens & tokens(value)) / max(min(len(option_tokens), len(tokens(value))), 1) for value in values),
                    default=0,
                )
                option_scores.append(score)
            average = sum(option_scores) / max(len(option_scores), 1)
            if best is None or average > best[0]:
                best = (average, attribute)
        return best[1] if best and best[0] >= 0.5 else None

    def _canonical_pending_value(
        self, slot: str, choice: str, context_slots: dict[str, str],
    ) -> str | None:
        if slot not in _SLOT_ATTRIBUTES:
            return None
        records = self.catalog.records
        for attribute, value in context_slots.items():
            if attribute in _SLOT_ATTRIBUTES and attribute != slot:
                records = [record for record in records if getattr(record, attribute) == value]
        values = {getattr(record, slot) for record in records}
        choice_tokens = tokens(choice)
        ranked: list[tuple[float, str]] = []
        for value in values:
            normalized_choice = normalize_text(choice)
            normalized_value = normalize_text(value)
            if normalized_choice == normalized_value or normalized_choice in normalized_value or normalized_value in normalized_choice:
                score = 1
            else:
                value_tokens = tokens(value)
                score = len(choice_tokens & value_tokens) / max(min(len(choice_tokens), len(value_tokens)), 1)
            ranked.append((score, value))
        ranked.sort(reverse=True)
        if not ranked or ranked[0][0] < 0.6 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
            return None
        return ranked[0][1]

    def _pending_option_answer(self, message: str, context: dict[str, Any], state: dict[str, Any]) -> ConversationAnalysis | None:
        if context.get("pending_action"):
            return None
        options = context.get("pending_options") or []
        if not isinstance(options, list) or not options:
            return None
        normalized = normalize_text(message.strip())
        choice = None
        if message.strip().isdigit() and 1 <= int(message.strip()) <= len(options):
            choice = options[int(message.strip()) - 1]
        if choice is None:
            choice = next(
                (option for option in options if normalize_text(str(option)) == normalized),
                None,
            )
        if choice is None:
            return None
        pending_slot = context.get("pending_slot") or self._infer_missing_slot(context.get("pending_question"), options)
        context_slots = dict(context.get("slots") or {})
        slot_updates = self._explicit_slot_updates(str(choice))
        if pending_slot:
            canonical = self._canonical_pending_value(pending_slot, str(choice), context_slots)
            if canonical:
                slot_updates[pending_slot] = canonical
        if context_slots.get("group") and pending_slot != "group":
            slot_updates["group"] = context_slots["group"]
        question_id = context.get("pending_question_id") or self._question_id(context.get("pending_question"), options)
        previous_goal = str(context.get("user_goal") or "").strip()
        normalized_query = f"{previous_goal}. Lựa chọn: {choice}".strip(". ") if previous_goal else str(choice)
        self._trace(
            "pending_answer_consumed",
            state,
            question_id=question_id,
            option=choice,
            pending_slot=pending_slot,
            slot_updates=slot_updates,
        )
        return ConversationAnalysis(
            route="procedure_lookup",
            normalized_query=normalized_query,
            slot_updates=slot_updates,
            slot_sources={key: "pending_answer" for key in slot_updates},
            confidence=1,
            consumed_pending_question_id=question_id,
        )

    def _pending_rule_answer(self, message: str, context: dict[str, Any]) -> ConversationAnalysis | None:
        pending_action = str(context.get("pending_action") or "")
        if not pending_action.startswith("scenario_disambiguation:"):
            return None
        rule = self.disambiguation_rules.get(pending_action.split(":", 1)[1])
        if not rule:
            return None
        normalized = normalize_text(message)
        question_id = context.get("pending_question_id") or self._question_id(
            context.get("pending_question"), context.get("pending_options") or [],
        )
        choice = next(
            (item for item in rule.get("Lựa chọn", []) if normalize_text(item) == normalized or normalize_text(item) in normalized),
            None,
        )
        if not choice:
            return ConversationAnalysis(
                route="clarify",
                normalized_query=message,
                clarifying_question=rule["Câu hỏi"],
                quick_replies=rule.get("Lựa chọn", []),
                confidence=0.95,
                scenario_rule_id=rule["Mã"],
                pending_question_id=question_id,
            )
        outcome = rule.get("Xử lý lựa chọn", {}).get(choice, {})
        slot_updates = dict(outcome.get("Gán slot", {}))
        rejected_slots = [
            {"slot": key, "value": "", "reason": "choice_cleared_slot"}
            for key in outcome.get("Xóa slot", [])
        ]
        if outcome.get("Câu hỏi tiếp theo"):
            return ConversationAnalysis(
                route="clarify",
                normalized_query=message,
                slot_updates=slot_updates,
                slot_sources={key: "pending_answer" for key in slot_updates},
                rejected_slots=rejected_slots,
                clarifying_question=outcome["Câu hỏi tiếp theo"],
                quick_replies=outcome.get("Lựa chọn tiếp theo", []),
                confidence=0.98,
                consumed_pending_question_id=question_id,
            )
        return ConversationAnalysis(
            route="procedure_lookup",
            normalized_query=message,
            slot_updates=slot_updates,
            slot_sources={key: "pending_answer" for key in slot_updates},
            rejected_slots=rejected_slots,
            confidence=0.98,
            consumed_pending_question_id=question_id,
        )

    def _explicit_slot_updates(self, message: str) -> dict[str, str]:
        message_tokens = tokens(message)
        updates: dict[str, str] = {}
        for attribute in _SLOT_ATTRIBUTES - {"group"}:
            scored: list[tuple[float, str]] = []
            for value in {getattr(record, attribute) for record in self.catalog.records}:
                value_tokens = tokens(value)
                if not value_tokens:
                    continue
                overlap = len(value_tokens & message_tokens) / len(value_tokens)
                if normalize_text(value) in normalize_text(message):
                    overlap = 1
                scored.append((overlap, value))
            scored.sort(reverse=True)
            minimum_overlap = 0.5 if attribute == "request_type" else 0.6
            if scored and scored[0][0] >= minimum_overlap and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                updates[attribute] = scored[0][1]
        records = self.catalog.records
        for attribute, value in updates.items():
            if attribute != "locality":
                records = [record for record in records if getattr(record, attribute) == value]
        groups = {record.group for record in records}
        if len(groups) == 1:
            updates["group"] = next(iter(groups))
        return updates

    def _fallback(self, state: dict[str, Any]) -> ConversationAnalysis:
        message = state["messages"][-1]["content"].strip()
        normalized = normalize_text(message)
        context = state.get("conversation_context") or {}
        pending_action = context.get("pending_action")
        active_form = state.get("active_scenario_code") or context.get("active_form_code")
        active_procedure = state.get("active_procedure_code")

        pending_rule = self._pending_rule_answer(message, context)
        if pending_rule:
            return pending_rule

        pending_option = self._pending_option_answer(message, context, state)
        if pending_option:
            return pending_option

        if active_form and any(phrase in normalized for phrase in _FORM_FINISH_PHRASES):
            return ConversationAnalysis(
                route="form_review",
                normalized_query=message,
                confidence=1,
                user_action="review_form",
            )

        if any(phrase in normalized for phrase in _REVIEW_PHRASES):
            return ConversationAnalysis(
                route="form_review",
                normalized_query=message,
                confidence=0.98,
                user_action="review_form",
            )
        if normalized in _AFFIRMATIVE and pending_action == "confirm_form_filling":
            return ConversationAnalysis(
                route="form_flow",
                normalized_query=message,
                confidence=0.98,
                user_action="start_form",
            )
        explicit_code = next((code for code in self.catalog.by_code if code in message), None)
        if explicit_code:
            return ConversationAnalysis(
                route="procedure_lookup",
                normalized_query=message,
                explicit_procedure_code=explicit_code,
                confidence=1,
            )
        if active_form:
            return ConversationAnalysis(
                route="form_flow",
                normalized_query=message,
                confidence=0.9,
                user_action="continue_form",
            )
        if active_procedure and any(phrase in normalized for phrase in _FOLLOW_UP_PHRASES):
            procedure_name = self.catalog.by_code[active_procedure].name if active_procedure in self.catalog.by_code else ""
            return ConversationAnalysis(
                route="procedure_follow_up",
                normalized_query=f"{message} — thủ tục {procedure_name}".strip(" —"),
                confidence=0.9,
            )
        if normalized in {"xin chao", "chao", "toi can ho tro", "ho tro toi"}:
            return self._topic_clarification(message)
        explicit_slots = self._explicit_slot_updates(message)
        return ConversationAnalysis(
            route="procedure_lookup",
            normalized_query=message,
            slot_updates=explicit_slots,
            slot_sources={key: "explicit_user" for key in explicit_slots},
            confidence=0.95 if explicit_slots else 0.55,
        )

    def _topic_clarification(self, message: str) -> ConversationAnalysis:
        topics = [str(item["Đề mục"]) for item in self.topic_scenarios]
        return ConversationAnalysis(
            route="clarify",
            normalized_query=message,
            missing_slot="group",
            clarifying_question="Bạn đang cần giải quyết vấn đề thuộc nhóm nào?",
            quick_replies=topics,
            confidence=0.95,
        )

    def _system_prompt(self, state: dict[str, Any]) -> str:
        topics = [
            {
                "topic": item["Đề mục"],
                "question": item["Câu hỏi nhánh"],
                "options": str(item["Lựa chọn gợi ý cho người dùng"]).splitlines(),
                "next": item["Câu hỏi tiếp theo"],
                "disambiguation_rules": item.get("Quy tắc phân biệt", []),
            }
            for item in self.topic_scenarios
        ]
        context = state.get("conversation_context") or {}
        return (
            "Bạn là tầng hiểu hội thoại của trợ lý thủ tục hành chính. "
            "Chỉ phân loại, viết lại truy vấn và chọn một câu hỏi làm rõ; tuyệt đối không nêu hồ sơ, phí, "
            "thời hạn, điều kiện hay kết luận pháp lý. Trả đúng một JSON object theo schema: "
            '{"route":"clarify|procedure_lookup|procedure_follow_up|form_flow|form_review|general|out_of_scope",'
            '"normalized_query":"string","slot_updates":{},"explicit_procedure_code":null,'
            '"missing_slot":null,"clarifying_question":null,"quick_replies":[],"confidence":0.0,'
            '"user_action":"start_form|continue_form|review_form|switch_procedure|none"}. '
            "Chỉ dùng start_form nếu pending_action là confirm_form_filling. Một câu đồng ý không có pending action "
            "không được tự mở form. Dùng form_review khi người dùng yêu cầu xem, kiểm tra, rà soát, thẩm định "
            "hoặc nói đã điền xong. Mỗi lượt chỉ hỏi một câu. Tối đa 7 quick replies. "
            "slot_updates chỉ được dùng các khóa group, field, request_type, scenario, audience, locality và giá trị "
            "phải giữ đúng nhãn trong dữ liệu kịch bản. "
            f"TOPIC_SCENARIOS={json.dumps(topics, ensure_ascii=False)}\n"
            f"CONVERSATION_CONTEXT={json.dumps(context, ensure_ascii=False)}\n"
            f"ACTIVE_PROCEDURE={state.get('active_procedure_code')}\n"
            f"ACTIVE_FORM={state.get('active_scenario_code')}"
        )

    def _validate_analysis(self, analysis: ConversationAnalysis, state: dict[str, Any]) -> ConversationAnalysis:
        context = state.get("conversation_context") or {}
        if analysis.explicit_procedure_code not in self.catalog.by_code:
            analysis.explicit_procedure_code = None
        if analysis.user_action == "start_form" and context.get("pending_action") != "confirm_form_filling":
            analysis.user_action = "none"
            if analysis.route == "form_flow" and not state.get("active_scenario_code"):
                analysis.route = "procedure_lookup"
        if analysis.route == "clarify" and not analysis.clarifying_question:
            return self._topic_clarification(analysis.normalized_query)
        canonical_slots: dict[str, str] = {}
        message_tokens = tokens(state["messages"][-1]["content"])
        for attribute, raw_value in analysis.slot_updates.items():
            if attribute not in _SLOT_ATTRIBUTES or not isinstance(raw_value, str) or not raw_value.strip():
                analysis.rejected_slots.append({"slot": attribute, "value": str(raw_value), "reason": "invalid_slot"})
                continue
            values = {getattr(record, attribute) for record in self.catalog.records}
            matched = next((value for value in values if normalize_text(value) == normalize_text(raw_value)), None)
            if not matched:
                analysis.rejected_slots.append({"slot": attribute, "value": raw_value, "reason": "unknown_taxonomy_value"})
                continue
            source = analysis.slot_sources.get(attribute, "llm_inferred")
            value_tokens = tokens(matched)
            overlap = len(value_tokens & message_tokens) / max(len(value_tokens), 1)
            explicit_evidence = bool(value_tokens) and overlap >= 0.5
            if source == "llm_inferred" and (analysis.confidence < 0.9 or not explicit_evidence):
                analysis.rejected_slots.append({
                    "slot": attribute,
                    "value": matched,
                    "reason": "insufficient_explicit_evidence",
                })
                continue
            canonical_slots[attribute] = matched
            analysis.slot_sources[attribute] = "explicit_user" if source == "llm_inferred" and explicit_evidence else source
        analysis.slot_updates = canonical_slots
        analysis.slot_sources = {key: value for key, value in analysis.slot_sources.items() if key in canonical_slots}
        analysis.quick_replies = analysis.quick_replies[:7]
        return analysis

    def _apply_disambiguation(self, analysis: ConversationAnalysis, state: dict[str, Any]) -> ConversationAnalysis:
        rule = self._rule_for_message(state["messages"][-1]["content"])
        if not rule:
            return analysis
        rejected = list(analysis.rejected_slots)
        if "scenario" in analysis.slot_updates:
            rejected.append({
                "slot": "scenario",
                "value": analysis.slot_updates["scenario"],
                "reason": "mandatory_disambiguation",
            })
        self._trace(
            "scenario_resolution",
            state,
            matched_rule=rule["Mã"],
            question=rule["Câu hỏi"],
            options=rule.get("Lựa chọn", []),
            reason="mandatory_disambiguation",
        )
        return ConversationAnalysis(
            route="clarify",
            normalized_query=analysis.normalized_query,
            slot_updates={key: value for key, value in analysis.slot_updates.items() if key != "scenario"},
            slot_sources={key: value for key, value in analysis.slot_sources.items() if key != "scenario"},
            rejected_slots=rejected,
            missing_slot="structure_purpose",
            clarifying_question=rule["Câu hỏi"],
            quick_replies=rule.get("Lựa chọn", []),
            confidence=1,
            scenario_rule_id=rule["Mã"],
        )

    def _finalize(self, analysis: ConversationAnalysis, state: dict[str, Any], source: str) -> ConversationAnalysis:
        raw_slots = dict(analysis.slot_updates)
        validated = self._validate_analysis(analysis, state)
        final = self._apply_disambiguation(validated, state)
        if final.route == "clarify":
            if final.missing_slot not in _SLOT_ATTRIBUTES and final.missing_slot != "structure_purpose":
                final.missing_slot = self._infer_missing_slot(final.clarifying_question, final.quick_replies)
            final.pending_question_id = final.pending_question_id or self._question_id(
                final.clarifying_question, final.quick_replies,
            )
        self._trace(
            "conversation_analysis",
            state,
            source=source,
            route=final.route,
            confidence=final.confidence,
            raw_slots=raw_slots,
            accepted_slots=final.slot_updates,
            slot_sources=final.slot_sources,
            rejected_slots=final.rejected_slots,
            question=final.clarifying_question,
        )
        return final

    def pipeline_overrides(
        self,
        slots: dict[str, str],
        explicit_code: str | None = None,
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if explicit_code in self.catalog.by_code:
            return {"candidate_codes": [explicit_code], "selection_filters": {}}
        filters = {key: value for key, value in slots.items() if key in _SLOT_ATTRIBUTES - {"locality"}}
        records = self.catalog.records
        for attribute, value in filters.items():
            records = [record for record in records if getattr(record, attribute) == value]
        result: dict[str, Any] = {}
        if filters:
            result["selection_filters"] = filters
            result["candidate_codes"] = [record.code for record in records]
        if slots.get("locality"):
            result["administrative_area_code"] = slots["locality"]
        if self.settings.llm_debug_logging:
            logger.info(
                "candidate_filter request_id=%s session=%s turn=%s payload=%s",
                (trace_context or {}).get("request_id", "unknown"),
                (trace_context or {}).get("session_hash", "unknown"),
                (trace_context or {}).get("turn_number", "unknown"),
                json.dumps({
                    "initial_count": len(self.catalog.records),
                    "filters": filters,
                    "final_count": len(records),
                    "candidate_codes": [record.code for record in records],
                }, ensure_ascii=False),
            )
        return result

    async def ainvoke(self, state: dict[str, Any]) -> ConversationAnalysis:
        self._trace(
            "conversation_input",
            state,
            messages=state.get("messages", [])[-12:],
            conversation_context=state.get("conversation_context", {}),
            active_procedure=state.get("active_procedure_code"),
            active_form=state.get("active_scenario_code"),
        )
        fallback = self._fallback(state)
        self._trace("conversation_fallback", state, analysis=fallback.model_dump())
        if (
            fallback.route in {"form_review", "form_flow"}
            or fallback.consumed_pending_question_id
            or not self.settings.llm_api_key
            or not self.settings.llm_model
        ):
            reason = (
                "pending_answer"
                if fallback.consumed_pending_question_id
                else "deterministic_route"
                if fallback.route in {"form_review", "form_flow"}
                else "missing_llm_configuration"
            )
            return self._finalize(fallback, state, reason)

        system_prompt = self._system_prompt(state)
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                *state["messages"][-12:],
            ],
            "response_format": {"type": "json_object"},
        }
        if self.settings.environment == "LOCAL":
            payload["stream"] = False
        self._trace("conversation_llm_request", state, model=self.settings.llm_model, payload=payload)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                )
                response.raise_for_status()
            content, _transport = response_content(response)
            self._trace(
                "conversation_llm_response",
                state,
                provider_status=response.status_code,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                raw_output=content,
            )
            fenced = re.fullmatch(r"\s*```(?:json)?\s*(\{.*\})\s*```\s*", content, flags=re.DOTALL | re.IGNORECASE)
            analysis = ConversationAnalysis.model_validate_json(fenced.group(1) if fenced else content)
            return self._finalize(analysis, state, "llm")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.warning("conversation_agent_fallback reason=%s provider_status=%s", type(exc).__name__, status_code)
            self._trace(
                "conversation_llm_fallback",
                state,
                reason=type(exc).__name__,
                provider_status=status_code,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                fallback=fallback.model_dump(),
            )
            return self._finalize(fallback, state, "llm_error_fallback")
