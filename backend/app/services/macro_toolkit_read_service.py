"""Service-owned read entry points and payload builders for macro toolkit."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from backend.app.core_finance.macro import DEFAULT_CRISIS_SCORE_HISTORY_LIMIT
from backend.app.core_finance.macro.toolkit.runner import MacroToolkitScript
from backend.app.governance.settings import get_settings
from backend.app.services import macro_report_asset_service, macro_toolkit_service
from backend.app.services import macro_toolkit_analysis_service as analysis
from backend.app.services.formal_result_runtime import FallbackMode, QualityFlag, VendorStatus
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    MacroToolkitRefreshReceiptHealth,
)


class MacroToolkitResultMetaOverrides(TypedDict):
    quality_flag: QualityFlag
    vendor_status: VendorStatus
    fallback_mode: FallbackMode
    tables_used: list[str]


@dataclass(frozen=True)
class MacroToolkitScriptsPayloadDependencies:
    """Legacy-compatible collaborators used by the service-owned scripts builder."""

    iter_toolkit_scripts: Callable[[], Iterable[MacroToolkitScript]]
    script_payload: Callable[[MacroToolkitScript], dict[str, object]]
    source_checks: Callable[..., list[dict[str, object]]]
    latest_source_check_date: Callable[[list[dict[str, object]]], object]
    cffex_member_rank_status: Callable[..., dict[str, object]]
    commodity_futures_refresh_permission_payload: Callable[..., dict[str, object]]
    commodity_futures_status: Callable[..., dict[str, object]]
    macro_model_readiness: Callable[..., dict[str, object]]
    output_files: Callable[[], list[dict[str, object]]]
    capability_plan: Callable[..., list[dict[str, object]]]
    owner_scoped_choice_stock_refresh_overview: Callable[..., dict[str, object]]
    script_warnings: Callable[[dict[str, object]], list[str]]
    envelope: Callable[..., dict[str, object]]


@dataclass(frozen=True)
class MacroToolkitAnalysisPayloadDependencies:
    """Collaborators for analysis assembly and isolated payload tests."""

    analysis_indicators: Callable[[str | Path], list[dict[str, object]]]
    output_files: Callable[[], list[dict[str, object]]]
    load_report_bundle: Callable[[Path], dict[str, object]]
    latest_indicator_date: Callable[[list[dict[str, object]]], Any]
    macro_model_readiness: Callable[..., dict[str, object]]
    analysis_signal_cards: Callable[..., list[dict[str, object]]]
    equity_strategy_payload_data_status: Callable[..., dict[str, object]]
    analysis_runtime_status: Callable[[str], dict[str, object]]
    select_primary_signal: Callable[..., dict[str, object]]
    full_analysis_blocks: Callable[..., tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]]
    gate_capability_results_on_refresh_receipt: Callable[..., list[dict[str, object]]]
    source_checks_for_aliases: Callable[..., list[dict[str, object]]]
    source_checks: Callable[..., list[dict[str, object]]]
    capability_plan: Callable[..., list[dict[str, object]]]
    hason_macro_strategy_summary: Callable[..., dict[str, object]]
    analysis_conclusion: Callable[..., dict[str, object]]
    analysis_warnings: Callable[[dict[str, object]], list[str]]
    gate_primary_signal_on_refresh_receipt: Callable[..., dict[str, object]]
    gate_analysis_conclusion_on_refresh_receipt: Callable[..., dict[str, object]]
    analysis_data_health: Callable[..., dict[str, object]]
    cffex_member_rank_status: Callable[..., dict[str, object]]
    choice_stock_refresh_overview: Callable[..., dict[str, object]]
    aggregate_macro_result_meta_overrides: Callable[[dict[str, object]], MacroToolkitResultMetaOverrides]
    envelope: Callable[..., dict[str, object]]
    iter_toolkit_scripts: Callable[[], Sequence[object]]


def build_macro_toolkit_analysis(
    detail: str,
    *,
    history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    refresh_receipt_health: (
        MacroToolkitRefreshReceiptHealth | None
    ) = None,
) -> dict[str, object]:
    from backend.app.services import macro_toolkit_route_support as support

    settings = get_settings()
    return build_macro_toolkit_analysis_payload(
        detail,
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
        output_dir=support.OUTPUT_DIR,
        report_bundle_dirname=macro_report_asset_service.BUNDLE_DIRNAME,
        default_data_sources=support.DEFAULT_DATA_SOURCES,
        source_check_aliases=support._SOURCE_CHECK_ALIASES,
        capability_definitions=support._CAPABILITY_DEFINITIONS,
        history_limit=history_limit,
        refresh_receipt_health=refresh_receipt_health,
        dependencies=_macro_toolkit_analysis_payload_dependencies(),
    )


def build_macro_toolkit_strategy_summaries() -> dict[str, object]:
    from backend.app.services import macro_toolkit_route_support as support

    settings = get_settings()
    strategies, price_context = support._equity_strategy_summaries_with_context(settings.duckdb_path)
    strategy_data_status = support._equity_strategy_payload_data_status(
        strategies,
        price_context_unavailable=price_context is None and not strategies,
    )
    warnings = support._equity_strategy_payload_warnings(strategy_data_status)
    strategy_as_of_date = support._latest_strategy_as_of_date(strategies)
    shadow_portfolio_report = support.compute_equity_shadow_portfolio_report(
        settings.duckdb_path,
        latest_factor_snapshot=support._latest_factor_snapshot_from_price_context(price_context),
    )
    macro_etf_strategy = support._macro_etf_strategy_snapshot_for_toolkit(
        duckdb_path=settings.duckdb_path,
        as_of_date=strategy_as_of_date,
    )
    strategy_result: dict[str, object] = {
        "strategy_summaries": strategies,
        "strategy_data_status": strategy_data_status,
        "shadow_portfolio_report": shadow_portfolio_report,
        "macro_etf_strategy": macro_etf_strategy,
        "choice_stock_refresh": support._choice_stock_refresh_overview(
            settings.duckdb_path,
            settings.governance_path,
            reference_date=strategy_as_of_date,
        ),
        "warnings": warnings,
    }
    result_meta_overrides = support._aggregate_macro_result_meta_overrides(strategy_result)
    return support._envelope(
        "macro_toolkit.analysis.strategy_summaries",
        strategy_result,
        quality_flag=str(result_meta_overrides["quality_flag"]),
        vendor_status=str(result_meta_overrides["vendor_status"]),
        fallback_mode=str(result_meta_overrides["fallback_mode"]),
        tables_used=list(result_meta_overrides["tables_used"]),
        as_of_date=strategy_as_of_date,
    )


def _macro_toolkit_analysis_payload_dependencies(
) -> MacroToolkitAnalysisPayloadDependencies:
    from backend.app.services import macro_toolkit_route_support as support

    return MacroToolkitAnalysisPayloadDependencies(
        analysis_indicators=support._analysis_indicators,
        output_files=support._output_files,
        load_report_bundle=macro_report_asset_service.load_report_bundle,
        latest_indicator_date=support._latest_indicator_date,
        macro_model_readiness=macro_toolkit_service.macro_model_readiness,
        analysis_signal_cards=support._analysis_signal_cards,
        equity_strategy_payload_data_status=support._equity_strategy_payload_data_status,
        analysis_runtime_status=support._analysis_runtime_status,
        select_primary_signal=analysis.select_primary_signal,
        full_analysis_blocks=_build_macro_toolkit_full_analysis_blocks,
        gate_capability_results_on_refresh_receipt=(
            analysis._gate_capability_results_on_refresh_receipt
        ),
        source_checks_for_aliases=support._source_checks_for_aliases,
        source_checks=support._source_checks,
        capability_plan=support._capability_plan,
        hason_macro_strategy_summary=support._hason_macro_strategy_summary,
        analysis_conclusion=support._analysis_conclusion,
        analysis_warnings=support._analysis_warnings,
        gate_primary_signal_on_refresh_receipt=(
            support._gate_primary_signal_on_refresh_receipt
        ),
        gate_analysis_conclusion_on_refresh_receipt=(
            support._gate_analysis_conclusion_on_refresh_receipt
        ),
        analysis_data_health=analysis._analysis_data_health,
        cffex_member_rank_status=support._cffex_member_rank_status,
        choice_stock_refresh_overview=support._choice_stock_refresh_overview,
        aggregate_macro_result_meta_overrides=(
            support._aggregate_macro_result_meta_overrides
        ),
        envelope=support._envelope,
        iter_toolkit_scripts=support.iter_toolkit_scripts,
    )


def _build_macro_toolkit_full_analysis_blocks(
    duckdb_path: str | Path,
    analysis_date: date,
    *,
    history_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    from backend.app.services import macro_toolkit_route_support as support

    return build_macro_toolkit_full_analysis_blocks(
        duckdb_path,
        analysis_date,
        history_limit=history_limit,
        a_share_stampede_risk=support._a_share_stampede_risk,
        macro_capability_results=support._macro_capability_results,
        equity_strategy_summaries=support._equity_strategy_summaries,
    )


def build_macro_toolkit_scripts_payload(
    *,
    auth: object,
    duckdb_path: str | Path,
    governance_path: str | Path,
    output_dir: str | Path,
    toolkit_root: str | Path,
    default_data_sources: Sequence[str],
    omitted_source_scripts: object,
    dependencies: MacroToolkitScriptsPayloadDependencies,
) -> dict[str, object]:
    """Build the scripts/readiness payload after the route authorizes the read."""

    scripts = [dependencies.script_payload(script) for script in dependencies.iter_toolkit_scripts()]
    source_checks = dependencies.source_checks(duckdb_path)
    source_check_cache = {str(check["alias"]): check for check in source_checks}
    cffex_status = dependencies.cffex_member_rank_status(
        duckdb_path,
        reference_date=dependencies.latest_source_check_date(source_checks),
    )
    commodity_permission = dependencies.commodity_futures_refresh_permission_payload(auth)
    commodity_status = dependencies.commodity_futures_status(duckdb_path)
    readiness = dependencies.macro_model_readiness(
        output_dir=output_dir,
        reference_date=dependencies.latest_source_check_date(source_checks),
    )
    return dependencies.envelope(
        "macro_toolkit.scripts",
        {
            "default_data_sources": list(default_data_sources),
            "toolkit_root": str(toolkit_root),
            "output_dir": str(output_dir),
            "scripts": scripts,
            "groups": sorted({str(item["group"]) for item in scripts}),
            "omitted_scripts": omitted_source_scripts,
            "output_files": dependencies.output_files(),
            "source_checks": source_checks,
            "capabilities": dependencies.capability_plan(
                duckdb_path,
                source_check_cache=source_check_cache,
            ),
            "cffex_member_rank": cffex_status,
            "choice_stock_refresh": dependencies.owner_scoped_choice_stock_refresh_overview(
                auth,
                duckdb_path=duckdb_path,
                governance_path=governance_path,
                reference_date=dependencies.latest_source_check_date(source_checks),
            ),
            "commodity_futures_refresh": {
                "permission": commodity_permission,
                "status": commodity_status,
            },
            "model_readiness": readiness["model_readiness"],
            "readiness_summary": readiness["readiness_summary"],
            "warnings": dependencies.script_warnings(cffex_status),
        },
    )


def build_macro_toolkit_analysis_coverage(
    *,
    indicators: Sequence[dict[str, object]],
    output_files: Sequence[dict[str, object]],
    script_count: int,
) -> dict[str, object]:
    """Compute the stable coverage block used by analysis conclusions."""

    hit_count = sum(1 for item in indicators if item["latest_value"] is not None)
    return {
        "indicator_count": len(indicators),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else 0,
        "script_count": script_count,
        "output_file_count": len(output_files),
    }


def build_macro_toolkit_analysis_payload(
    detail: str,
    *,
    duckdb_path: str | Path,
    governance_path: str | Path,
    output_dir: str | Path,
    report_bundle_dirname: str,
    default_data_sources: Sequence[str],
    source_check_aliases: Sequence[str],
    capability_definitions: Sequence[Mapping[str, Sequence[str]]],
    history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    refresh_receipt_health: MacroToolkitRefreshReceiptHealth | None = None,
    dependencies: MacroToolkitAnalysisPayloadDependencies,
) -> dict[str, object]:
    """Read inputs and assemble the complete macro-toolkit analysis envelope."""

    indicators = dependencies.analysis_indicators(duckdb_path)
    indicator_by_key = {str(item["key"]): item for item in indicators}
    output_files = dependencies.output_files()
    report_bundle = dependencies.load_report_bundle(
        Path(output_dir) / report_bundle_dirname
    )
    analysis_date = dependencies.latest_indicator_date(indicators)
    readiness = dependencies.macro_model_readiness(
        output_dir=output_dir,
        reference_date=analysis_date,
    )
    base_signal_cards = dependencies.analysis_signal_cards(
        indicator_by_key,
        output_files,
        [],
        None,
        capabilities_deferred=True,
    )
    if detail == "core":
        a_share_risk = None
        capability_results: list[dict[str, object]] = []
        strategy_summaries: list[dict[str, object]] = []
        strategy_data_status = dependencies.equity_strategy_payload_data_status(
            strategy_summaries,
            deferred=True,
        )
        source_checks: list[dict[str, object]] = []
        capabilities: list[dict[str, object]] = []
        runtime_status = dependencies.analysis_runtime_status("core")
        signal_cards = base_signal_cards
        primary_signal = dependencies.select_primary_signal(
            signal_cards,
            a_share_risk=a_share_risk,
            capability_results=capability_results,
            capabilities_deferred=True,
        )
    else:
        a_share_risk, capability_results, strategy_summaries = (
            dependencies.full_analysis_blocks(
                duckdb_path,
                analysis_date,
                history_limit=history_limit,
            )
        )
        capability_results = dependencies.gate_capability_results_on_refresh_receipt(
            capability_results,
            refresh_receipt_health,
        )
        strategy_data_status = dependencies.equity_strategy_payload_data_status(
            strategy_summaries
        )
        source_check_cache: dict[str, dict[str, object]] = {}
        dependencies.source_checks_for_aliases(
            (
                str(alias)
                for aliases in (
                    source_check_aliases,
                    tuple(
                        str(alias)
                        for definition in capability_definitions
                        for alias in definition["data_aliases"]
                    ),
                )
                for alias in aliases
            ),
            duckdb_path,
            source_check_cache=source_check_cache,
        )
        source_checks = dependencies.source_checks(
            duckdb_path,
            source_check_cache=source_check_cache,
        )
        capabilities = dependencies.capability_plan(
            duckdb_path,
            source_check_cache=source_check_cache,
        )
        runtime_status = dependencies.analysis_runtime_status("full")
        signal_cards = dependencies.analysis_signal_cards(
            indicator_by_key,
            output_files,
            capability_results,
            a_share_risk,
        )
        primary_signal = dependencies.select_primary_signal(
            signal_cards,
            a_share_risk=a_share_risk,
            capability_results=capability_results,
            capabilities_deferred=False,
        )
    hason_strategy = dependencies.hason_macro_strategy_summary(
        output_files,
        analysis_date=analysis_date,
    )
    coverage = build_macro_toolkit_analysis_coverage(
        indicators=indicators,
        output_files=output_files,
        script_count=len(dependencies.iter_toolkit_scripts()),
    )
    conclusion = dependencies.analysis_conclusion(base_signal_cards, coverage)
    warnings = dependencies.analysis_warnings(coverage)
    if refresh_receipt_health is not None:
        primary_signal = dependencies.gate_primary_signal_on_refresh_receipt(
            primary_signal,
            refresh_receipt_health,
        )
        conclusion = dependencies.gate_analysis_conclusion_on_refresh_receipt(
            conclusion,
            warnings,
            refresh_receipt_health,
        )
    data_health = dependencies.analysis_data_health(
        indicators=indicators,
        source_checks=source_checks,
        capability_results=capability_results,
        capabilities=capabilities,
        runtime_status=runtime_status,
        warnings=warnings,
        reference_date=analysis_date,
    )
    if refresh_receipt_health is not None:
        data_health["refresh_receipt"] = refresh_receipt_health.as_payload()
    analysis_result = {
        "default_data_sources": list(default_data_sources),
        "as_of_date": analysis_date,
        "conclusion": conclusion,
        "coverage": coverage,
        "indicators": indicators,
        "signal_cards": signal_cards,
        "primary_signal": primary_signal,
        "hason_strategy": hason_strategy,
        "a_share_risk": a_share_risk,
        "capability_results": capability_results,
        "strategy_summaries": strategy_summaries,
        "strategy_data_status": strategy_data_status,
        "output_files": output_files,
        "report_bundle": report_bundle,
        "source_checks": source_checks,
        "capabilities": capabilities,
        "cffex_member_rank": dependencies.cffex_member_rank_status(
            duckdb_path,
            reference_date=dependencies.latest_indicator_date(indicators),
        ),
        "choice_stock_refresh": dependencies.choice_stock_refresh_overview(
            duckdb_path,
            governance_path,
            reference_date=analysis_date,
        ),
        "runtime_status": runtime_status,
        "data_health": data_health,
        "model_readiness": readiness["model_readiness"],
        "readiness_summary": readiness["readiness_summary"],
        "warnings": warnings,
    }
    result_meta_overrides = dependencies.aggregate_macro_result_meta_overrides(
        analysis_result
    )
    return dependencies.envelope(
        "macro_toolkit.analysis",
        analysis_result,
        quality_flag=str(result_meta_overrides["quality_flag"]),
        vendor_status=str(result_meta_overrides["vendor_status"]),
        fallback_mode=str(result_meta_overrides["fallback_mode"]),
        tables_used=list(result_meta_overrides["tables_used"]),
        as_of_date=analysis_date,
    )


def build_macro_toolkit_full_analysis_blocks(
    duckdb_path: str | Path,
    analysis_date: object,
    *,
    history_limit: int,
    a_share_stampede_risk: Callable[[str | Path], dict[str, object]],
    macro_capability_results: Callable[..., list[dict[str, object]]],
    equity_strategy_summaries: Callable[[str | Path], list[dict[str, object]]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    """Run the three independent full-analysis reads concurrently."""

    with ThreadPoolExecutor(max_workers=3) as executor:
        a_share_risk_future = executor.submit(
            copy_context().run,
            a_share_stampede_risk,
            duckdb_path,
        )
        capability_results_future = executor.submit(
            copy_context().run,
            macro_capability_results,
            duckdb_path,
            report_date=analysis_date,
            history_limit=history_limit,
        )
        strategy_summaries_future = executor.submit(
            copy_context().run,
            equity_strategy_summaries,
            duckdb_path,
        )
        return (
            a_share_risk_future.result(),
            capability_results_future.result(),
            strategy_summaries_future.result(),
        )


