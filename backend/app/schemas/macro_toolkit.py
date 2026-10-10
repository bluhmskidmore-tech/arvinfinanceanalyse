from __future__ import annotations

from typing import Any

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict


class _StrictMacroToolkitModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MacroToolkitCoverage(_StrictMacroToolkitModel):
    indicator_count: int
    hit_count: int
    hit_rate: float
    script_count: int
    output_file_count: int


class MacroToolkitScriptsResult(_StrictMacroToolkitModel):
    default_data_sources: list[str]
    toolkit_root: str
    output_dir: str
    scripts: list[dict[str, Any]]
    groups: list[str]
    omitted_scripts: dict[str, str]
    output_files: list[dict[str, Any]]
    source_checks: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    cffex_member_rank: dict[str, Any]
    choice_stock_refresh: dict[str, Any]
    commodity_futures_refresh: dict[str, Any]
    model_readiness: list[dict[str, Any]]
    readiness_summary: dict[str, Any]
    warnings: list[str]


class MacroToolkitAnalysisResult(_StrictMacroToolkitModel):
    """Stable top-level contract; analytical cards remain intentionally dynamic."""

    default_data_sources: list[str]
    as_of_date: str | None
    conclusion: dict[str, Any]
    coverage: MacroToolkitCoverage
    indicators: list[dict[str, Any]]
    signal_cards: list[dict[str, Any]]
    primary_signal: dict[str, Any]
    hason_strategy: dict[str, Any]
    a_share_risk: dict[str, Any] | None
    capability_results: list[dict[str, Any]]
    strategy_summaries: list[dict[str, Any]]
    strategy_data_status: dict[str, Any]
    output_files: list[dict[str, Any]]
    report_bundle: dict[str, Any]
    source_checks: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    cffex_member_rank: dict[str, Any]
    choice_stock_refresh: dict[str, Any]
    runtime_status: dict[str, Any]
    data_health: dict[str, Any]
    model_readiness: list[dict[str, Any]]
    readiness_summary: dict[str, Any]
    warnings: list[str]


class MacroToolkitStrategySummariesResult(_StrictMacroToolkitModel):
    strategy_summaries: list[dict[str, Any]]
    strategy_data_status: dict[str, Any]
    shadow_portfolio_report: dict[str, Any]
    macro_etf_strategy: dict[str, Any]
    choice_stock_refresh: dict[str, Any]
    warnings: list[str]


class MacroToolkitScriptsEnvelope(_StrictMacroToolkitModel):
    result_meta: ResultMeta
    result: MacroToolkitScriptsResult


class MacroToolkitAnalysisEnvelope(_StrictMacroToolkitModel):
    result_meta: ResultMeta
    result: MacroToolkitAnalysisResult


class MacroToolkitStrategySummariesEnvelope(_StrictMacroToolkitModel):
    result_meta: ResultMeta
    result: MacroToolkitStrategySummariesResult


class MacroToolkitDynamicEnvelope(_StrictMacroToolkitModel):
    """Envelope for vendor/script receipts whose nested keys are runtime-defined."""

    result_meta: ResultMeta
    result: dict[str, Any]
