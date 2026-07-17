from datetime import date

from app.rag import has_valid_evidence, remove_unknown_citation_tokens, vector_literal
from app.rag_types import Citation, RetrievedChunk


def make_chunk() -> RetrievedChunk:
    citation = Citation(
        citation_id="CIT-1",
        knowledge_chunk_id="chunk-1",
        source_code="LAW_CIVIL_STATUS_2014",
        source_title="Luật Hộ tịch",
        document_number="60/2014/QH13",
        section_reference="Điều 16",
        source_url="https://example.test/law",
        effective_from=date(2016, 1, 1),
        jurisdiction_scope="national",
        administrative_area_code=None,
        quote_preview="Nội dung nguồn",
    )
    return RetrievedChunk("chunk-1", "Nội dung nguồn", "Điều 16", [], citation)


def test_vector_literal_is_postgres_vector_syntax() -> None:
    assert vector_literal([0.1, 2.0, -3.25]) == "[0.1,2,-3.25]"


def test_unknown_citation_tokens_are_removed() -> None:
    answer = remove_unknown_citation_tokens("Có căn cứ [CIT-1] và bịa đặt [CIT-99].", [make_chunk().citation])
    assert answer == "Có căn cứ [CIT-1] và bịa đặt ."


def test_evidence_requires_traceable_source() -> None:
    assert has_valid_evidence([make_chunk()])
