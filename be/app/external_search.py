"""Feature-flagged external search contract; no provider is enabled in V1."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExternalSearchResult:
    title: str
    source_url: str
    snippet: str
    publisher: str | None = None


class ExternalSearchAdapter(Protocol):
    async def search(self, query: str) -> list[ExternalSearchResult]: ...


class DisabledExternalSearchAdapter:
    """Keeps external retrieval off until a reviewed provider is configured."""

    async def search(self, query: str) -> list[ExternalSearchResult]:
        return []


class FakeExternalSearchAdapter:
    """Deterministic adapter for graph and API tests."""

    def __init__(self, results: list[ExternalSearchResult] | None = None) -> None:
        self.results = results or []
        self.calls: list[str] = []

    async def search(self, query: str) -> list[ExternalSearchResult]:
        self.calls.append(query)
        return self.results
