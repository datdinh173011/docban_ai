import sys
from types import SimpleNamespace

from app.procedure_ingestion import split_for_embedding
from app.config import Settings
from app.procedure_embeddings import ProcedureEmbeddingClient


def test_embedding_splitter_bounds_chunks_and_preserves_overlap() -> None:
    content = "A" * 1200 + "\n" + "B" * 1200

    chunks = split_for_embedding(content, max_chars=1200, overlap_chars=200)

    assert len(chunks) == 3
    assert all(len(chunk) <= 1200 for chunk in chunks)
    assert chunks[0].endswith("A" * 200)
    assert chunks[1].startswith("A" * 200)


def test_embedding_splitter_rejects_invalid_overlap() -> None:
    try:
        split_for_embedding("text", max_chars=200, overlap_chars=200)
    except ValueError as exc:
        assert str(exc) == "procedure_chunk_size_must_exceed_overlap"
    else:
        raise AssertionError("invalid overlap must fail")


async def test_local_embedding_client_validates_minilm_dimensions(monkeypatch) -> None:
    class FakeModel:
        def encode(self, texts, **kwargs):
            return [[0.0] * 384 for _ in texts]

    monkeypatch.setattr(ProcedureEmbeddingClient, "_model", staticmethod(lambda *args: FakeModel()))
    vectors = await ProcedureEmbeddingClient(Settings(_env_file=None)).embed_many(["khai sinh"])

    assert len(vectors[0]) == 384


def test_local_embedding_model_never_uses_hugging_face_network(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    ProcedureEmbeddingClient._model.cache_clear()
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeSentenceTransformer))
    try:
        ProcedureEmbeddingClient._model("sentence-transformers/all-MiniLM-L6-v2", "cpu")
    finally:
        ProcedureEmbeddingClient._model.cache_clear()

    assert captured["kwargs"] == {"device": "cpu", "local_files_only": True}
