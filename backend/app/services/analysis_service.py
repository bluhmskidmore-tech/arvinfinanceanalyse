from __future__ import annotations

from typing import Iterable, Protocol

from backend.app.schemas.analysis_service import AnalysisQuery, AnalysisResultEnvelope


class AnalysisAdapter(Protocol):
    analysis_key: str

    def execute(self, query: AnalysisQuery) -> AnalysisResultEnvelope:
        ...


class UnifiedAnalysisService:
    def __init__(self, adapters: Iterable[AnalysisAdapter]):
        self._adapters = {
            adapter.analysis_key: adapter
            for adapter in adapters
        }

    def execute(self, query: AnalysisQuery) -> AnalysisResultEnvelope:
        try:
            adapter = self._adapters[query.analysis_key]
        except KeyError as exc:
            raise ValueError(f"Unsupported analysis_key={query.analysis_key}") from exc
        return adapter.execute(query)

    def supported_analysis_keys(self) -> set[str]:
        return set(self._adapters)


def build_default_analysis_service(
    *,
    duckdb_path: str | None = None,
) -> UnifiedAnalysisService:
    from backend.app.services.analysis_adapters import (
        BondActionAttributionAdapter,
        ProductCategoryPnlAnalysisAdapter,
    )

    adapters: list[AnalysisAdapter] = [BondActionAttributionAdapter()]
    if duckdb_path is not None:
        adapters.append(ProductCategoryPnlAnalysisAdapter(duckdb_path))
    return UnifiedAnalysisService(adapters)
