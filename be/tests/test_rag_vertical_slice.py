import logging

import pytest
from pydantic import ValidationError

from app.external_search import ExternalSearchResult, FakeExternalSearchAdapter
from app.graph import build_graph, resolve_birth_registration, resolve_procedure, score_evidence
from app.rag_types import Citation, RetrievedChunk
from app.schemas import AssistantReply
from app.structured_query import StructuredQuerySpec


def government_evidence(*claim_ids: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        content="Nội dung nguồn chính thức.",
        title="Điều 16",
        hierarchy_path=[],
        citation=Citation(
            citation_id="CIT-1",
            knowledge_chunk_id="chunk-1",
            source_code="LAW_CIVIL_STATUS_2014",
            source_title="Luật Hộ tịch",
            document_number="60/2014/QH13",
            section_reference="Điều 16",
            source_url="https://example.test/law",
            effective_from=None,
            jurisdiction_scope="national",
            administrative_area_code=None,
            quote_preview="Nội dung nguồn chính thức.",
        ),
        claim_ids=claim_ids,
    )


def test_birth_resolver_returns_structured_retrieval_plan() -> None:
    plan = resolve_birth_registration("Đăng ký khai sinh cần giấy tờ gì?")
    assert plan is not None
    assert plan["procedure_code"] == "BIRTH_REGISTRATION"
    assert "required_document" in plan["claim_types"]


def test_birth_resolver_detects_receiving_authority_question() -> None:
    plan = resolve_birth_registration("Nộp đăng ký khai sinh ở đâu?")

    assert plan is not None
    assert "receiving_authority" in plan["claim_types"]


def test_unknown_request_does_not_resolve_to_birth_registration() -> None:
    assert resolve_birth_registration("Tôi cần đổi giấy phép lái xe") is None


@pytest.mark.parametrize(
    ("message", "procedure_code"),
    [
        ("Tôi cần đăng ký thường trú", "PERMANENT_RESIDENCE"),
        ("Xin cấp giấy phép xây nhà ở riêng lẻ", "CONSTRUCTION_PERMIT_DETACHED_HOUSE"),
    ],
)
def test_procedure_resolver_supports_other_v1_packages(message: str, procedure_code: str) -> None:
    plan = resolve_procedure(message)

    assert plan is not None
    assert plan["procedure_code"] == procedure_code


def test_structured_query_rejects_unknown_fact_type_and_large_limit() -> None:
    with pytest.raises(ValidationError):
        StructuredQuerySpec(procedure_code="BIRTH_REGISTRATION", fact_types=["unknown"], limit=100)


def test_scoring_requires_government_evidence_for_high_confidence() -> None:
    assert score_evidence([], 1) == (0.0, "low", ["no_government_evidence"])
    score, band, reasons = score_evidence([government_evidence("legal_basis")], 1)
    assert score >= 0.8
    assert band == "high"
    assert reasons == []


@pytest.mark.asyncio
async def test_fake_external_search_is_deterministic() -> None:
    adapter = FakeExternalSearchAdapter([ExternalSearchResult("Nguồn", "https://example.test", "Kết quả")])
    results = await adapter.search("khai sinh")
    assert results[0].title == "Nguồn"
    assert adapter.calls == ["khai sinh"]


class FakeRagService:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls: list[str] = []

    async def retrieve(self, *args, **kwargs) -> list[RetrievedChunk]:
        self.calls.append(args[0])
        return self.chunks


class FakeStructuredQuery:
    async def execute(self, *args, **kwargs) -> list[RetrievedChunk]:
        return []


class FakeLlmClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def reply(self, *args, **kwargs) -> AssistantReply:
        self.calls.append(args)
        return AssistantReply(intent="procedure_guidance", answer="Có căn cứ [CIT-1].")


@pytest.mark.asyncio
async def test_graph_returns_high_only_from_government_evidence() -> None:
    llm = FakeLlmClient()
    graph = build_graph(
        llm,
        FakeRagService([government_evidence("legal_basis")]),
        FakeStructuredQuery(),
        FakeExternalSearchAdapter(),
        False,
    )
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Căn cứ luật nào để đăng ký khai sinh?"}],
        "language_code": "vi",
        "external_search_consent": False,
    })
    assert result["reply"].answer_strategy == "high"
    assert result["reply"].confidence_band == "high"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_graph_calls_llm_for_general_request_without_government_evidence() -> None:
    llm = FakeLlmClient()
    graph = build_graph(llm, FakeRagService([]), FakeStructuredQuery(), FakeExternalSearchAdapter(), False)

    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Hôm nay trời thế nào?"}],
        "language_code": "vi",
        "external_search_consent": False,
    })

    assert len(llm.calls) == 1
    assert result["reply"].confidence_band == "low"
    assert result["reply"].confidence_reasons == ["no_government_evidence"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_graph_calls_llm_for_birth_request_without_evidence_when_external_search_is_disabled(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.graph")
    llm = FakeLlmClient()
    graph = build_graph(llm, FakeRagService([]), FakeStructuredQuery(), FakeExternalSearchAdapter(), False, True)

    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Đăng ký khai sinh cần gì?"}],
        "language_code": "vi",
        "external_search_consent": False,
    })

    assert len(llm.calls) == 1
    assert result["reply"].answer_strategy == "low"
    assert any("rag_retrieval" in message and "structured_fact_count=0" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_birth_follow_up_uses_active_procedure_context() -> None:
    llm = FakeLlmClient()
    rag = FakeRagService([])
    graph = build_graph(llm, rag, FakeStructuredQuery(), FakeExternalSearchAdapter(), False)

    first = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Tôi muốn đăng ký khai sinh cho bé"}],
        "language_code": "vi",
        "external_search_consent": False,
    })
    follow_up = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Cần giấy tờ gì?"}],
        "language_code": "vi",
        "active_procedure_code": first["active_procedure_code"],
        "active_scenario_code": first["active_scenario_code"],
        "external_search_consent": False,
    })

    assert first["context_origin"] == "explicit"
    assert follow_up["context_origin"] == "follow_up"
    assert follow_up["intent"] == "procedure_guidance"
    assert len(rag.calls) == 2


@pytest.mark.asyncio
async def test_unrelated_message_does_not_retrieve_or_clear_active_birth_context() -> None:
    rag = FakeRagService([])
    graph = build_graph(FakeLlmClient(), rag, FakeStructuredQuery(), FakeExternalSearchAdapter(), False)

    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Thời tiết hôm nay thế nào?"}],
        "language_code": "vi",
        "active_procedure_code": "BIRTH_REGISTRATION",
        "active_scenario_code": "STANDARD",
        "external_search_consent": False,
    })

    assert result["context_origin"] == "out_of_scope"
    assert result["active_procedure_code"] == "BIRTH_REGISTRATION"
    assert rag.calls == []


@pytest.mark.asyncio
async def test_explicit_supported_procedure_switches_active_birth_context() -> None:
    graph = build_graph(FakeLlmClient(), FakeRagService([]), FakeStructuredQuery(), FakeExternalSearchAdapter(), False)

    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Tôi muốn đăng ký thường trú"}],
        "language_code": "vi",
        "active_procedure_code": "BIRTH_REGISTRATION",
        "active_scenario_code": "STANDARD",
        "external_search_consent": False,
    })

    assert result["context_origin"] == "explicit"
    assert result["active_procedure_code"] == "PERMANENT_RESIDENCE"


@pytest.mark.asyncio
async def test_graph_requests_external_search_consent_before_adapter_call() -> None:
    adapter = FakeExternalSearchAdapter([ExternalSearchResult("Nguồn", "https://example.test", "Kết quả")])
    graph = build_graph(FakeLlmClient(), FakeRagService([]), FakeStructuredQuery(), adapter, True)
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Đăng ký khai sinh cần gì?"}],
        "language_code": "vi",
        "external_search_consent": False,
    })
    assert result["reply"].external_search_consent_required is True
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_graph_labels_external_only_answer_as_low() -> None:
    adapter = FakeExternalSearchAdapter([ExternalSearchResult("Nguồn", "https://example.test", "Kết quả")])
    graph = build_graph(FakeLlmClient(), FakeRagService([]), FakeStructuredQuery(), adapter, True)
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Đăng ký khai sinh cần gì?"}],
        "language_code": "vi",
        "external_search_consent": True,
    })
    assert result["reply"].answer_strategy == "low"
    assert result["citations"][0]["source_type"] == "external"
    assert adapter.calls == ["Đăng ký khai sinh cần gì?"]
