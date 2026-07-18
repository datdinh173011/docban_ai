from __future__ import annotations

import pytest

from app.procedure_rag import ProcedureRagService


class FakeEmbeddings:
    async def embed(self, query: str) -> list[float]:
        assert query == "Hồ sơ cần chuẩn bị"
        return [0.0] * 384


class FakeResult:
    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    async def execute(self, statement, parameters: dict[str, object]) -> FakeResult:
        self.calls.append((statement, parameters))
        return FakeResult()


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *args) -> None:
        return None


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def connect(self) -> FakeConnectionContext:
        return FakeConnectionContext(self.connection)


@pytest.mark.asyncio
@pytest.mark.parametrize("locality", [None, "Hà Nội"])
async def test_retrieval_binds_nullable_locality_as_postgres_text(locality: str | None) -> None:
    engine = FakeEngine()
    service = ProcedureRagService(engine, FakeEmbeddings())

    result = await service.retrieve("Hồ sơ cần chuẩn bị", "1.013225", locality)

    statement, parameters = engine.connection.calls[0]
    assert result == []
    assert statement._bindparams["locality"].type.python_type is str
    assert "CAST(:locality AS TEXT)" in statement.text
    assert parameters["locality"] == locality
