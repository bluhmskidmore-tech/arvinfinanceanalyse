from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.financial_result_publication_repo import (
    FinancialPublicationError,
    invalidate_financial_generation,
    read_publication_pointer,
    resolve_financial_generation,
)

BALANCE_ANALYSIS_PUBLICATION_API_VERSION = "balance-analysis-api/v1"
BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION = "balance-analysis-overview/v1"
BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION = "balance-analysis-portfolio/v2"
BALANCE_ANALYSIS_OVERVIEW_TABLE = "balance_analysis_overview_envelope"
BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY = "balance_analysis_overview"
BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE = "balance_analysis_basis_breakdown_envelope"
BALANCE_ANALYSIS_BASIS_BREAKDOWN_COVERAGE_KEY = "balance_analysis_basis_breakdown"


class BalanceAnalysisPublicationUnavailable(RuntimeError):
    pass


class BalanceAnalysisPublicationNotReady(RuntimeError):
    pass


def configured_balance_analysis_publication_root(settings: Settings) -> Path | None:
    configured = str(settings.balance_analysis_publication_root or "").strip()
    if not configured:
        return None
    root = Path(configured).resolve()
    financial_root = str(getattr(settings, "financial_publication_root", "") or "").strip()
    if financial_root and root == Path(financial_root).resolve():
        raise BalanceAnalysisPublicationUnavailable(
            "Balance-analysis publication root must be separate from the PnL publication root."
        )
    return root


def invalidate_balance_analysis_publications_before_fact_change(
    *,
    source_duckdb_path: Path | str,
    report_dates: tuple[str, ...],
    reason: str,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    active_settings = settings or get_settings()
    normalized_dates = {
        date.fromisoformat(str(value)).isoformat()
        for value in report_dates
        if str(value or "").strip()
    }
    if not normalized_dates:
        return ()
    if Path(source_duckdb_path).resolve() != Path(active_settings.duckdb_path).resolve():
        return ()
    root = configured_balance_analysis_publication_root(active_settings)
    if root is None:
        return ()
    pointer = read_publication_pointer(root, require_valid=False)
    if pointer is None:
        return ()
    retained = pointer.get("retained_generations")
    if not isinstance(retained, list):
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis publication pointer has no retained-generation set."
        )
    current_generation = str(pointer.get("generation") or "")
    affected_generations: list[str] = []
    for item in retained:
        if not isinstance(item, Mapping):
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis retained-generation entry is invalid."
            )
        generation = str(item.get("generation") or "")
        try:
            resolved = resolve_financial_generation(
                root,
                generation=generation,
                reader_api_version=BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
                reader_schema_version=BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
            )
        except FinancialPublicationError as exc:
            invalidation_path = root / "invalidations" / f"{generation}.json"
            if invalidation_path.is_file():
                continue
            raise BalanceAnalysisPublicationNotReady(
                f"Cannot validate committed balance-analysis generation {generation!r} before fact change."
            ) from exc
        if not normalized_dates.intersection(_overview_coverage_dates(resolved.manifest)):
            continue
        affected_generations.append(generation)

    invalidated: list[str] = []
    for generation in sorted(
        affected_generations,
        key=lambda value: value == current_generation,
    ):
        invalidate_financial_generation(
            root,
            generation=generation,
            reason=reason,
        )
        invalidated.append(generation)
    return tuple(invalidated)


def _overview_coverage_dates(manifest: Mapping[str, object]) -> set[str]:
    sealed = manifest.get("sealed_payload")
    if not isinstance(sealed, Mapping):
        raise BalanceAnalysisPublicationNotReady(
            "Committed balance-analysis publication has no sealed payload."
        )
    coverage = sealed.get("coverage_dates")
    if not isinstance(coverage, Mapping):
        raise BalanceAnalysisPublicationNotReady(
            "Committed balance-analysis publication has no coverage declaration."
        )
    raw_dates = coverage.get(BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY)
    if not isinstance(raw_dates, list):
        raise BalanceAnalysisPublicationNotReady(
            "Committed balance-analysis publication has no overview coverage."
        )
    return {str(item) for item in raw_dates}
