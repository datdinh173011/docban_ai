import logging
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.external_search import ExternalSearchAdapter
from app.llm import LlmTrace, OpenAICompatibleClient
from app.rag import RagService, citations_for, remove_unknown_citation_tokens
from app.rag_types import RetrievedChunk
from app.rag_types import Citation
from app.schemas import AssistantReply
from app.structured_query import ALLOWED_FACT_TYPES, StructuredQueryService, StructuredQuerySpec

logger = logging.getLogger(__name__)


class ConversationState(TypedDict, total=False):
    request_id: str
    messages: list[dict[str, str]]
    language_code: str
    intent: str
    reply: AssistantReply
    external_search_consent: bool
    administrative_area_code: str | None
    retrieved_chunks: list[RetrievedChunk]
    citations: list[dict]
    retrieval_plan: dict[str, Any]
    confidence_score: float
    confidence_band: Literal["high", "medium", "low"]
    confidence_reasons: list[str]
    external_search_used: bool
    structured_fact_count: int
    hybrid_chunk_count: int


def resolve_birth_registration(message: str) -> dict[str, Any] | None:
    lowered = message.lower()
    if not any(term in lowered for term in ("khai sinh", "hộ tịch", "birth registration")):
        return None
    fact_types: list[str] = []
    terms = {
        "required_document": ("giấy tờ", "hồ sơ", "giấy chứng sinh"),
        "processing_time": ("bao lâu", "thời hạn", "ngày"),
        "fee": ("lệ phí", "phí", "chi phí"),
        "receiving_authority": ("nộp ở đâu", "cơ quan", "ủy ban"),
        "legal_basis": ("căn cứ", "nghị định", "luật", "quy định"),
    }
    for fact_type, keywords in terms.items():
        if any(keyword in lowered for keyword in keywords):
            fact_types.append(fact_type)
    return {
        "procedure_code": "BIRTH_REGISTRATION",
        "scenario_code": "STANDARD",
        "claim_types": fact_types or ["legal_basis"],
        "retrieval_paths": ["structured_query", "hybrid_rag"],
    }


def score_evidence(chunks: list[RetrievedChunk], claim_count: int) -> tuple[float, str, list[str]]:
    if not chunks:
        return 0.0, "low", ["no_government_evidence"]
    covered_claims = {claim for chunk in chunks for claim in chunk.claim_ids}
    coverage = min(1.0, len(covered_claims) / max(claim_count, 1))
    jurisdiction = 1.0 if any(chunk.citation.jurisdiction_scope != "national" for chunk in chunks) else 0.75
    quality = min(1.0, 0.6 + (0.1 * min(len(chunks), 4)))
    score = round((0.35 * coverage) + 0.20 + (0.15 * quality) + (0.15 * jurisdiction) + 0.10 + 0.05, 2)
    if score >= 0.8:
        return score, "high", []
    return score, "medium", ["partial_claim_coverage"]


def build_graph(
    llm_client: OpenAICompatibleClient,
    rag_service: RagService,
    structured_query: StructuredQueryService,
    external_search: ExternalSearchAdapter,
    external_search_enabled: bool,
    debug_logging: bool = False,
):
    async def resolve(state: ConversationState) -> dict:
        plan = resolve_birth_registration(state["messages"][-1]["content"])
        if plan is None:
            return {"retrieval_plan": {}, "intent": "out_of_scope"}
        return {"retrieval_plan": plan, "intent": "procedure_guidance"}

    def resolution_route(state: ConversationState) -> str:
        return "retrieve" if state.get("retrieval_plan") else "generate"

    async def retrieve(state: ConversationState) -> dict:
        plan = state["retrieval_plan"]
        message = state["messages"][-1]["content"]
        chunks: list[RetrievedChunk] = []
        structured_fact_count = 0
        hybrid_chunk_count = 0
        try:
            fact_types = [value for value in plan["claim_types"] if value in ALLOWED_FACT_TYPES]
            if fact_types:
                structured_chunks = await structured_query.execute(
                    StructuredQuerySpec(procedure_code="BIRTH_REGISTRATION", fact_types=fact_types),
                    state.get("administrative_area_code"),
                )
                chunks.extend(structured_chunks)
                structured_fact_count = len(structured_chunks)
            hybrid_chunks = await rag_service.retrieve(
                message,
                state["language_code"],
                procedure_code=plan["procedure_code"],
                administrative_area_code=state.get("administrative_area_code"),
            )
            chunks.extend(hybrid_chunks)
            hybrid_chunk_count = len(hybrid_chunks)
        except Exception as exc:
            # A retrieval failure must never make the model improvise legal advice.
            if debug_logging:
                logger.warning("rag_retrieval_failed request_id=%s error=%s", state.get("request_id", "unknown"), type(exc).__name__)
            chunks = []
        score, band, reasons = score_evidence(chunks, len(plan["claim_types"]))
        if debug_logging:
            logger.info(
                "rag_retrieval request_id=%s procedure_code=%s structured_fact_count=%s hybrid_chunk_count=%s "
                "evidence_count=%s confidence_score=%s confidence_band=%s confidence_reasons=%s",
                state.get("request_id", "unknown"),
                plan["procedure_code"],
                structured_fact_count,
                hybrid_chunk_count,
                len(chunks),
                score,
                band,
                reasons,
            )
        return {
            "retrieved_chunks": chunks,
            "citations": citations_for(chunks),
            "confidence_score": score,
            "confidence_band": band,
            "confidence_reasons": reasons,
            "structured_fact_count": structured_fact_count,
            "hybrid_chunk_count": hybrid_chunk_count,
        }

    def evidence_route(state: ConversationState) -> str:
        if state.get("confidence_band") == "high":
            return "generate"
        if external_search_enabled and not state.get("external_search_consent", False):
            return "request_external_consent"
        if external_search_enabled:
            return "external_search"
        return "generate"

    async def external_search_node(state: ConversationState) -> dict:
        results = await external_search.search(state["messages"][-1]["content"])
        if not results:
            return await abstain(state)
        external_chunks = [
            RetrievedChunk(
                chunk_id=f"EXTERNAL-{position}",
                content=result.snippet,
                title=result.title,
                hierarchy_path=[],
                citation=Citation(
                    citation_id=f"EXT-{position}",
                    knowledge_chunk_id=f"EXTERNAL-{position}",
                    source_code="EXTERNAL_SEARCH",
                    source_title=result.title,
                    document_number=None,
                    section_reference=None,
                    source_url=result.source_url,
                    effective_from=None,
                    jurisdiction_scope="external",
                    administrative_area_code=None,
                    quote_preview=result.snippet[:280],
                    source_type="external",
                ),
                source_type="external",
            )
            for position, result in enumerate(results, start=1)
        ]
        government_chunks = [chunk for chunk in state.get("retrieved_chunks", []) if chunk.source_type == "government"]
        if government_chunks:
            return {
                "retrieved_chunks": [*government_chunks, *external_chunks],
                "citations": citations_for([*government_chunks, *external_chunks]),
                "external_search_used": True,
            }
        return {
            "reply": AssistantReply(
                intent="procedure_guidance",
                answer="Tôi chưa thể xác minh nội dung này bằng nguồn chính thức. Các nguồn tham khảo bên ngoài được liệt kê bên dưới; vui lòng kiểm tra lại với cơ quan có thẩm quyền.",
                answer_strategy="low",
                confidence_score=state.get("confidence_score", 0.0),
                confidence_band="low",
                confidence_reasons=["no_government_evidence"],
                external_search_used=True,
            ),
            "retrieved_chunks": external_chunks,
            "citations": citations_for(external_chunks),
            "external_search_used": True,
        }

    def external_result_route(state: ConversationState) -> str:
        return "generate" if state.get("reply") is None else "end"

    async def request_external_consent(state: ConversationState) -> dict:
        return {
            "reply": AssistantReply(
                intent="procedure_guidance",
                answer="Nguồn chính thức hiện chưa đủ để trả lời chính xác. Bạn có đồng ý cho ICIVI dùng tìm kiếm bên ngoài trong phiên này không?",
                answer_strategy="consent_required",
                confidence_score=state.get("confidence_score"),
                confidence_band=state.get("confidence_band"),
                confidence_reasons=state.get("confidence_reasons", []),
                external_search_consent_required=True,
            ),
        }

    async def abstain(state: ConversationState) -> dict:
        return {
            "reply": AssistantReply(
                intent=state.get("intent", "procedure_guidance"),
                answer="Tôi chưa có đủ nguồn chính thức đã được kiểm duyệt để trả lời chính xác. Vui lòng xem Cổng Dịch vụ công hoặc liên hệ cơ quan hộ tịch nơi thực hiện thủ tục.",
                answer_strategy="unable_to_verify",
                confidence_score=state.get("confidence_score", 0.0),
                confidence_band=state.get("confidence_band", "low"),
                confidence_reasons=state.get("confidence_reasons", ["no_government_evidence"]),
            ),
            "citations": [],
        }

    async def generate(state: ConversationState) -> dict:
        chunks = state.get("retrieved_chunks", [])
        government_chunks = [chunk for chunk in chunks if chunk.source_type == "government"]
        trace = LlmTrace(
            request_id=state.get("request_id", "unknown"),
            intent=state.get("intent", "general"),
            retrieval_plan=state.get("retrieval_plan", {}),
            confidence_score=state.get("confidence_score"),
            confidence_band=state.get("confidence_band"),
            confidence_reasons=state.get("confidence_reasons", []),
            external_search_used=state.get("external_search_used", False),
            structured_fact_count=state.get("structured_fact_count", 0),
            hybrid_chunk_count=state.get("hybrid_chunk_count", 0),
        )
        reply = await llm_client.reply(state["messages"], state["language_code"], government_chunks, trace)
        reply.answer = remove_unknown_citation_tokens(reply.answer, [chunk.citation for chunk in government_chunks])
        reply.answer_strategy = state.get("confidence_band", "low")
        reply.confidence_score = state.get("confidence_score", 0.0)
        reply.confidence_band = state.get("confidence_band", "low")
        reply.confidence_reasons = state.get("confidence_reasons", ["no_government_evidence"])
        reply.external_search_used = state.get("external_search_used", False)
        return {"reply": reply, "citations": citations_for(government_chunks)}

    workflow = StateGraph(ConversationState)
    workflow.add_node("resolve", resolve)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)
    workflow.add_node("external_search", external_search_node)
    workflow.add_node("request_external_consent", request_external_consent)
    workflow.add_node("abstain", abstain)
    workflow.add_edge(START, "resolve")
    workflow.add_conditional_edges("resolve", resolution_route, {"retrieve": "retrieve", "generate": "generate"})
    workflow.add_conditional_edges(
        "retrieve",
        evidence_route,
        {
            "generate": "generate",
            "request_external_consent": "request_external_consent",
            "external_search": "external_search",
        },
    )
    workflow.add_conditional_edges("external_search", external_result_route, {"generate": "generate", "end": END})
    workflow.add_edge("generate", END)
    workflow.add_edge("request_external_consent", END)
    workflow.add_edge("abstain", END)
    return workflow.compile()
