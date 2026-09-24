from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date as Date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.adjusted_returns import net_return_after_costs  # noqa: E402
from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date  # noqa: E402
from backend.app.core_finance.portfolio_backtest import (  # noqa: E402
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MAX_POSITIONS,
    PORTFOLIO_ENGINE_VERSION,
    PortfolioBacktestResult,
    run_portfolio_backtest,
    summarize_equity_curve,
    write_equity_curve_csv,
)
from backend.app.core_finance.portfolio_paths import (  # noqa: E402
    calculate_path_horizon_exit,
    load_position_price_paths,
    path_entry_price,
    path_mark_price,
    position_path_key,
)
from backend.app.core_finance.strategy_policy import POLICY  # noqa: E402
from backend.app.core_finance.vol_target_overlay import build_vol_target_index_comparison  # noqa: E402
from scripts.run_portfolio_backtest import (  # noqa: E402
    _load_benchmark_rows,
    _load_daily_exposure_rows,
    _load_execution_rows,
    _market_state_rows_from_execution,
    _price_path_missing_adj_factor_rows,
    _table_names,
)

TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_POSITION_SNAPSHOT = "livermore_position_snapshot"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"

DEFAULT_OUTPUT_DIR = Path("docs/pnl")
DEFAULT_DATA_READINESS_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-data-readiness-report.md"
DEFAULT_RISK_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-risk-budget-robustness-report.md"
DEFAULT_EXIT_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-hold-progress-exit-simulation-report.md"
DEFAULT_ENTRY_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-entry-premium-interaction-report.md"
DEFAULT_SUMMARY_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-summary.md"
DEFAULT_GATE_REPAIR_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-gate-exposure-repair-report.md"
DEFAULT_LIQUIDITY_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-liquidity-unit-capacity-report.md"
DEFAULT_ADJ_GAP_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-adjustment-factor-gap-report.md"
DEFAULT_EXIT_PATH_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-hold-progress-exit-path-mode-report.md"
DEFAULT_RISK_V2_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-risk-budget-robustness-v2-report.md"
DEFAULT_GATE_REPAIR_V2_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-gate-exposure-repair-v2-report.md"
DEFAULT_GATE_REPAIR_V3_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-gate-exposure-repair-v3-report.md"
DEFAULT_LIQUIDITY_V2_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-liquidity-unit-capacity-v2-report.md"
DEFAULT_ADJ_GAP_V2_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-adjustment-factor-gap-v2-report.md"
DEFAULT_PATH_TIEOUT_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-path-engine-tieout-report.md"
DEFAULT_RISK_POST_FIX_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-risk-budget-003-005-post-data-fix-report.md"
DEFAULT_DATA_BLOCKER_RESOLUTION_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-data-blocker-resolution-report.md"
DEFAULT_POST_DATA_FIX_RISK_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-post-data-fix-risk-budget-report.md"
DEFAULT_POST_DATA_FIX_HOLD_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-post-data-fix-hold-progress-report.md"
DEFAULT_GATE_FALLBACK_SPLIT_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-gate-fallback-split-report.md"
DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-liquidity-canonical-rmb-report.md"
DEFAULT_ADJ_REPAIR_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-adjustment-factor-repair-report.md"
DEFAULT_CANONICAL_RESEARCH_DIR = Path("data/research/2026-07-batch3")
DEFAULT_RISK_OPTIMIZATION_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-risk-budget-optimization-report.md"
DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-underwater-exit-overlay-optimization-report.md"
DEFAULT_A_SHARE_CONSTRAINT_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-a-share-trading-constraint-report.md"
DEFAULT_A_SHARE_OPT_SUMMARY_REPORT = DEFAULT_OUTPUT_DIR / "2026-07-batch3-a-share-optimization-summary.md"

RISK_PER_TRADE_GRID = (0.003, 0.005, 0.0075, 0.010)
RISK_PER_TRADE_OPTIMIZATION_GRID = (0.002, 0.003, 0.004, 0.005, 0.006, 0.0075, 0.010)
SINGLE_NAME_CAP_GRID = (0.10, 0.15, 0.20, 1.0)
SINGLE_NAME_CAP_OPTIMIZATION_GRID = (0.10, 0.125, 0.15, 0.20, 1.0)
PORTFOLIO_EXPOSURE_CAP_GRID = ("existing_gate", 0.50, 0.75, 1.00)
LIQUIDITY_THRESHOLDS = (20_000_000.0, 50_000_000.0, 100_000_000.0, 200_000_000.0)
LIQUIDITY_CANONICAL_THRESHOLDS = (5_000_000.0, 10_000_000.0, 20_000_000.0, 50_000_000.0, 100_000_000.0, 200_000_000.0)
LIQUIDITY_UNIT_MULTIPLIERS = (
    ("raw", 1.0),
    ("x10", 10.0),
    ("x100", 100.0),
    ("x1000", 1000.0),
    ("x10000", 10000.0),
    ("x100000", 100000.0),
    ("x1000000", 1000000.0),
)
ENTRY_PREMIUM_BUCKETS = ("<0", "[0,1%)", "[1%,2%)", "[2%,3%)", "[3%,5%)", ">=5%")
RANDOM_SEED = 20260704
GATE_PERSISTED_TABLES = ("livermore_monitor_append", "livermore_gate_history", "livermore_gate_supplement")
_BATCH3_INPUT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def run_batch3_research(
    *,
    db_path: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data_payload = run_data_readiness_report(
        db_path=db_path,
        report_path=out / DEFAULT_DATA_READINESS_REPORT.name,
        signal_kind=signal_kind,
    )
    risk_payload = run_risk_budget_robustness_report(
        db_path=db_path,
        report_path=out / DEFAULT_RISK_REPORT.name,
        output_dir=out,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    exit_payload = run_hold_progress_exit_simulation_report(
        db_path=db_path,
        report_path=out / DEFAULT_EXIT_REPORT.name,
        output_dir=out,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    entry_payload = run_entry_premium_interaction_report(
        db_path=db_path,
        report_path=out / DEFAULT_ENTRY_REPORT.name,
        signal_kind=None,
    )
    gate_payload = run_gate_exposure_repair_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_REPAIR_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    liquidity_payload = run_liquidity_unit_capacity_report(
        db_path=db_path,
        report_path=out / DEFAULT_LIQUIDITY_REPORT.name,
        signal_kind=signal_kind,
    )
    adjustment_payload = run_adjustment_factor_gap_report(
        db_path=db_path,
        report_path=out / DEFAULT_ADJ_GAP_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    exit_path_payload = run_hold_progress_exit_path_mode_report(
        db_path=db_path,
        report_path=out / DEFAULT_EXIT_PATH_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk_v2_payload = run_risk_budget_robustness_v2_report(
        db_path=db_path,
        report_path=out / DEFAULT_RISK_V2_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    gate_v2_payload = run_gate_exposure_repair_v2_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_REPAIR_V2_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    gate_v3_payload = run_gate_exposure_repair_v3_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_REPAIR_V3_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    gate_split_payload = run_gate_fallback_split_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_FALLBACK_SPLIT_REPORT.name,
        gate_payload=gate_v3_payload,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    liquidity_v2_payload = run_liquidity_unit_capacity_v2_report(
        db_path=db_path,
        report_path=out / DEFAULT_LIQUIDITY_V2_REPORT.name,
        signal_kind=signal_kind,
    )
    liquidity_canonical_payload = run_liquidity_canonical_rmb_report(
        db_path=db_path,
        report_path=out / DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT.name,
        signal_kind=signal_kind,
    )
    adjustment_v2_payload = run_adjustment_factor_gap_v2_report(
        db_path=db_path,
        report_path=out / DEFAULT_ADJ_GAP_V2_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    adjustment_repair_payload = run_adjustment_factor_repair_report(
        db_path=db_path,
        report_path=out / DEFAULT_ADJ_REPAIR_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    path_tieout_payload = run_path_engine_tieout_report(
        db_path=db_path,
        report_path=out / DEFAULT_PATH_TIEOUT_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    canonical_payload = build_canonical_research_dataset(
        db_path=db_path,
        output_dir=DEFAULT_CANONICAL_RESEARCH_DIR,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_canonical_payload,
        adjustment_payload=adjustment_repair_payload,
    )
    adjustment_repair_payload = _sync_adjustment_repair_report_with_canonical_denominators(
        adjustment_repair_payload,
        canonical_payload,
    )
    risk_optimization_payload = run_risk_budget_optimization_report(
        db_path=db_path,
        report_path=out / DEFAULT_RISK_OPTIMIZATION_REPORT.name,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_canonical_payload,
        adjustment_payload=adjustment_repair_payload,
        canonical_payload=canonical_payload,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    underwater_overlay_payload = run_underwater_exit_overlay_optimization_report(
        db_path=db_path,
        report_path=out / DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT.name,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_canonical_payload,
        adjustment_payload=adjustment_repair_payload,
        canonical_payload=canonical_payload,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    a_share_constraint_payload = run_a_share_trading_constraint_report(
        db_path=db_path,
        report_path=out / DEFAULT_A_SHARE_CONSTRAINT_REPORT.name,
        signal_kind=signal_kind,
        liquidity_payload=liquidity_canonical_payload,
        canonical_payload=canonical_payload,
    )
    risk_post_fix_payload = run_risk_budget_post_data_fix_report(
        db_path=db_path,
        report_path=out / DEFAULT_RISK_POST_FIX_REPORT.name,
        gate_payload=gate_v3_payload,
        liquidity_payload=liquidity_v2_payload,
        adjustment_payload=adjustment_v2_payload,
    )
    data_blocker_payload = run_data_blocker_resolution_report(
        report_path=out / DEFAULT_DATA_BLOCKER_RESOLUTION_REPORT.name,
        gate_payload=gate_v3_payload,
        liquidity_payload=liquidity_v2_payload,
        adjustment_payload=adjustment_v2_payload,
    )
    post_data_fix_risk_payload = run_post_data_fix_risk_budget_report(
        db_path=db_path,
        report_path=out / DEFAULT_POST_DATA_FIX_RISK_REPORT.name,
        gate_payload=gate_v3_payload,
        liquidity_payload=liquidity_v2_payload,
        adjustment_payload=adjustment_v2_payload,
    )
    post_data_fix_hold_payload = run_post_data_fix_hold_progress_report(
        db_path=db_path,
        report_path=out / DEFAULT_POST_DATA_FIX_HOLD_REPORT.name,
        exit_path_payload=exit_path_payload,
        gate_payload=gate_v3_payload,
        liquidity_payload=liquidity_v2_payload,
        adjustment_payload=adjustment_v2_payload,
    )
    summary_payload = write_batch3_summary(
        report_path=out / DEFAULT_SUMMARY_REPORT.name,
        data_payload=data_payload,
        risk_payload=risk_payload,
        exit_payload=exit_payload,
        entry_payload=entry_payload,
        extra_payloads={
            "gate_exposure_repair": gate_payload,
            "liquidity_unit_capacity": liquidity_payload,
            "adjustment_factor_gap": adjustment_payload,
            "hold_progress_exit_path_mode": exit_path_payload,
            "risk_budget_robustness_v2": risk_v2_payload,
            "gate_exposure_repair_v2": gate_v2_payload,
            "gate_exposure_repair_v3": gate_v3_payload,
            "gate_fallback_split": gate_split_payload,
            "liquidity_unit_capacity_v2": liquidity_v2_payload,
            "liquidity_canonical_rmb": liquidity_canonical_payload,
            "adjustment_factor_gap_v2": adjustment_v2_payload,
            "adjustment_factor_repair": adjustment_repair_payload,
            "path_engine_tieout": path_tieout_payload,
            "canonical_research_dataset": canonical_payload,
            "risk_budget_optimization": risk_optimization_payload,
            "underwater_exit_overlay_optimization": underwater_overlay_payload,
            "a_share_trading_constraint": a_share_constraint_payload,
            "risk_budget_003_005_post_data_fix": risk_post_fix_payload,
            "data_blocker_resolution": data_blocker_payload,
            "post_data_fix_risk_budget": post_data_fix_risk_payload,
            "post_data_fix_hold_progress": post_data_fix_hold_payload,
        },
    )
    a_share_summary_payload = write_a_share_optimization_summary(
        report_path=out / DEFAULT_A_SHARE_OPT_SUMMARY_REPORT.name,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_canonical_payload,
        adjustment_payload=adjustment_repair_payload,
        canonical_payload=canonical_payload,
        risk_payload=risk_optimization_payload,
        underwater_payload=underwater_overlay_payload,
        a_share_constraint_payload=a_share_constraint_payload,
        legacy_summary_payload=summary_payload,
    )
    return {
        "status": summary_payload["status"],
        "reports": {
            "data_readiness": str(out / DEFAULT_DATA_READINESS_REPORT.name),
            "risk_budget_robustness": str(out / DEFAULT_RISK_REPORT.name),
            "hold_progress_exit": str(out / DEFAULT_EXIT_REPORT.name),
            "entry_premium_interaction": str(out / DEFAULT_ENTRY_REPORT.name),
            "summary": str(out / DEFAULT_SUMMARY_REPORT.name),
            "gate_exposure_repair": str(out / DEFAULT_GATE_REPAIR_REPORT.name),
            "liquidity_unit_capacity": str(out / DEFAULT_LIQUIDITY_REPORT.name),
            "adjustment_factor_gap": str(out / DEFAULT_ADJ_GAP_REPORT.name),
            "hold_progress_exit_path_mode": str(out / DEFAULT_EXIT_PATH_REPORT.name),
            "risk_budget_robustness_v2": str(out / DEFAULT_RISK_V2_REPORT.name),
            "gate_exposure_repair_v2": str(out / DEFAULT_GATE_REPAIR_V2_REPORT.name),
            "gate_exposure_repair_v3": str(out / DEFAULT_GATE_REPAIR_V3_REPORT.name),
            "gate_fallback_split": str(out / DEFAULT_GATE_FALLBACK_SPLIT_REPORT.name),
            "liquidity_unit_capacity_v2": str(out / DEFAULT_LIQUIDITY_V2_REPORT.name),
            "liquidity_canonical_rmb": str(out / DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT.name),
            "adjustment_factor_gap_v2": str(out / DEFAULT_ADJ_GAP_V2_REPORT.name),
            "adjustment_factor_repair": str(out / DEFAULT_ADJ_REPAIR_REPORT.name),
            "path_engine_tieout": str(out / DEFAULT_PATH_TIEOUT_REPORT.name),
            "canonical_strategy_paths": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_strategy_paths.parquet"),
            "canonical_strategy_trades": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_strategy_trades.parquet"),
            "canonical_data_quality_summary": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_data_quality_summary.csv"),
            "risk_budget_optimization": str(out / DEFAULT_RISK_OPTIMIZATION_REPORT.name),
            "underwater_exit_overlay_optimization": str(out / DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT.name),
            "a_share_trading_constraint": str(out / DEFAULT_A_SHARE_CONSTRAINT_REPORT.name),
            "a_share_optimization_summary": str(out / DEFAULT_A_SHARE_OPT_SUMMARY_REPORT.name),
            "risk_budget_003_005_post_data_fix": str(out / DEFAULT_RISK_POST_FIX_REPORT.name),
            "data_blocker_resolution": str(out / DEFAULT_DATA_BLOCKER_RESOLUTION_REPORT.name),
            "post_data_fix_risk_budget": str(out / DEFAULT_POST_DATA_FIX_RISK_REPORT.name),
            "post_data_fix_hold_progress": str(out / DEFAULT_POST_DATA_FIX_HOLD_REPORT.name),
        },
        "data_readiness": data_payload,
        "risk_budget": risk_payload,
        "hold_progress_exit": exit_payload,
        "entry_premium": entry_payload,
        "summary": summary_payload,
        "gate_exposure_repair": gate_payload,
        "liquidity_unit_capacity": liquidity_payload,
        "adjustment_factor_gap": adjustment_payload,
        "hold_progress_exit_path_mode": exit_path_payload,
        "risk_budget_robustness_v2": risk_v2_payload,
        "gate_exposure_repair_v2": gate_v2_payload,
        "gate_exposure_repair_v3": gate_v3_payload,
        "gate_fallback_split": gate_split_payload,
        "liquidity_unit_capacity_v2": liquidity_v2_payload,
        "liquidity_canonical_rmb": liquidity_canonical_payload,
        "adjustment_factor_gap_v2": adjustment_v2_payload,
        "adjustment_factor_repair": adjustment_repair_payload,
        "path_engine_tieout": path_tieout_payload,
        "canonical_research_dataset": canonical_payload,
        "risk_budget_optimization": risk_optimization_payload,
        "underwater_exit_overlay_optimization": underwater_overlay_payload,
        "a_share_trading_constraint": a_share_constraint_payload,
        "a_share_optimization_summary": a_share_summary_payload,
        "risk_budget_003_005_post_data_fix": risk_post_fix_payload,
        "data_blocker_resolution": data_blocker_payload,
        "post_data_fix_risk_budget": post_data_fix_risk_payload,
        "post_data_fix_hold_progress": post_data_fix_hold_payload,
    }


def run_batch3_followup_returnwork(
    *,
    db_path: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    gate_v3_payload = run_gate_exposure_repair_v3_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_REPAIR_V3_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    gate_split_payload = run_gate_fallback_split_report(
        db_path=db_path,
        report_path=out / DEFAULT_GATE_FALLBACK_SPLIT_REPORT.name,
        gate_payload=gate_v3_payload,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    liquidity_payload = run_liquidity_canonical_rmb_report(
        db_path=db_path,
        report_path=out / DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT.name,
        signal_kind=signal_kind,
    )
    adjustment_payload = run_adjustment_factor_repair_report(
        db_path=db_path,
        report_path=out / DEFAULT_ADJ_REPAIR_REPORT.name,
        signal_kind=signal_kind,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    canonical_payload = build_canonical_research_dataset(
        db_path=db_path,
        output_dir=DEFAULT_CANONICAL_RESEARCH_DIR,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
    )
    adjustment_payload = _sync_adjustment_repair_report_with_canonical_denominators(
        adjustment_payload,
        canonical_payload,
    )
    risk_payload = run_risk_budget_optimization_report(
        db_path=db_path,
        report_path=out / DEFAULT_RISK_OPTIMIZATION_REPORT.name,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
        canonical_payload=canonical_payload,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    underwater_payload = run_underwater_exit_overlay_optimization_report(
        db_path=db_path,
        report_path=out / DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT.name,
        signal_kind=signal_kind,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
        canonical_payload=canonical_payload,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    a_share_constraint_payload = run_a_share_trading_constraint_report(
        db_path=db_path,
        report_path=out / DEFAULT_A_SHARE_CONSTRAINT_REPORT.name,
        signal_kind=signal_kind,
        liquidity_payload=liquidity_payload,
        canonical_payload=canonical_payload,
    )
    summary_payload = write_a_share_optimization_summary(
        report_path=out / DEFAULT_A_SHARE_OPT_SUMMARY_REPORT.name,
        gate_payload=gate_split_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
        canonical_payload=canonical_payload,
        risk_payload=risk_payload,
        underwater_payload=underwater_payload,
        a_share_constraint_payload=a_share_constraint_payload,
        legacy_summary_payload={"status": "not_run_in_followup_only_mode"},
    )
    return {
        "status": summary_payload["status"],
        "gate_fallback_split": gate_split_payload,
        "liquidity_canonical_rmb": liquidity_payload,
        "adjustment_factor_repair": adjustment_payload,
        "canonical_research_dataset": canonical_payload,
        "risk_budget_optimization": risk_payload,
        "underwater_exit_overlay_optimization": underwater_payload,
        "a_share_trading_constraint": a_share_constraint_payload,
        "a_share_optimization_summary": summary_payload,
        "reports": {
            "gate_fallback_split": str(out / DEFAULT_GATE_FALLBACK_SPLIT_REPORT.name),
            "liquidity_canonical_rmb": str(out / DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT.name),
            "adjustment_factor_repair": str(out / DEFAULT_ADJ_REPAIR_REPORT.name),
            "canonical_strategy_paths": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_strategy_paths.parquet"),
            "canonical_strategy_trades": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_strategy_trades.parquet"),
            "canonical_data_quality_summary": str(DEFAULT_CANONICAL_RESEARCH_DIR / "canonical_data_quality_summary.csv"),
            "risk_budget_optimization": str(out / DEFAULT_RISK_OPTIMIZATION_REPORT.name),
            "underwater_exit_overlay_optimization": str(out / DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT.name),
            "a_share_trading_constraint": str(out / DEFAULT_A_SHARE_CONSTRAINT_REPORT.name),
            "a_share_optimization_summary": str(out / DEFAULT_A_SHARE_OPT_SUMMARY_REPORT.name),
        },
    }


def run_data_readiness_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_DATA_READINESS_REPORT,
    signal_kind: str = "stock_candidate",
) -> dict[str, Any]:
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    db_file = Path(db_path)
    if not db_file.exists():
        payload = _blocked_payload(f"DuckDB file not found: {db_file}")
        _write_data_readiness_report(report, payload)
        return payload

    conn = duckdb.connect(str(db_file), read_only=True)
    try:
        tables = _table_names(conn)
        if TABLE_EXECUTION_HIST not in tables:
            payload = _blocked_payload(f"Required table {TABLE_EXECUTION_HIST} is missing.")
            _write_data_readiness_report(report, payload)
            return payload
        execution_rows, execution_issues = _load_execution_rows(
            conn,
            tables=tables,
            signal_kind=signal_kind,
            start_date=None,
            end_date=None,
        )
        if not execution_rows:
            payload = _blocked_payload("No execution rows available for data-readiness checks.")
            _write_data_readiness_report(report, payload)
            return payload

        start_date, end_date = _execution_date_window(execution_rows)
        exposure = _gate_exposure_readiness(conn, start_date=start_date, end_date=end_date)
        macro = _macro_history_readiness(conn, tables)
        positions = _position_history_readiness(conn, tables)
        price_paths = load_position_price_paths(conn, execution_rows, max_horizon_days=25)
        price_path = _price_path_readiness(price_paths)
        liquidity = _liquidity_readiness(execution_rows)
    finally:
        conn.close()

    decision = _classify_data_readiness(
        exposure=exposure,
        macro=macro,
        positions=positions,
        price_path=price_path,
        liquidity=liquidity,
    )
    payload = {
        "status": decision["status"],
        "db_path": str(db_file),
        "report_path": str(report),
        "signal_kind": signal_kind,
        "execution_row_count": len(execution_rows),
        "date_window": {"start": start_date, "end": end_date},
        "gate_exposure": exposure,
        "macro_history": macro,
        "position_history": positions,
        "price_path_adjustment": price_path,
        "liquidity": liquidity,
        "execution_issues": execution_issues,
        "blockers": decision["blockers"],
        "research_flags": decision["research_flags"],
    }
    _write_data_readiness_report(report, payload)
    return payload


def _classify_data_readiness(
    *,
    exposure: Mapping[str, object],
    macro: Mapping[str, object],
    positions: Mapping[str, object],
    price_path: Mapping[str, object],
    liquidity: Mapping[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    research_flags: list[str] = []
    fallback_ratio = _first_float(exposure.get("fallback_ratio")) or 0.0
    if fallback_ratio > 0.10:
        blockers.append(f"gate exposure fallback ratio {fallback_ratio:.2%} is above 10%")
    if macro.get("status") != "ready":
        blockers.append("macro composite history is missing or lacks required fields")
    if (_first_float(positions.get("sample_count")) or 0.0) < 30:
        research_flags.append("position holding history is sparse")
    if (_first_float(price_path.get("missing_adjustment_factor_ratio")) or 0.0) > 0:
        research_flags.append("some path rows use raw fallback because adjustment factors are missing")
    threshold_rows = list(liquidity.get("thresholds") or [])
    if liquidity.get("status") == "blocked":
        blockers.append("liquidity thresholds have no passing known rows")
    elif any(row["pass_count"] == 0 and row["missing_count"] == 0 for row in threshold_rows):
        research_flags.append("at least one liquidity threshold eliminates all known rows")
    if not (_first_float(liquidity.get("daily_amount_coverage_ratio")) or 0.0):
        blockers.append("daily_amount is unavailable for all loaded execution rows")
    status = "blocked" if blockers else "research_only" if research_flags else "ready"
    return {"status": status, "blockers": blockers, "research_flags": research_flags}


def run_risk_budget_robustness_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_RISK_REPORT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    output = Path(output_dir)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_risk_report(report, payload)
        return payload

    execution_rows = loaded["execution_rows"]
    market_state_rows = loaded["market_state_rows"]
    exposure_rows = loaded["exposure_rows"]
    benchmark_rows = loaded["benchmark_rows"]
    price_paths = loaded["price_paths"]
    variants = _run_risk_variant_set(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        price_paths=price_paths,
        benchmark_rows=benchmark_rows,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    csv_paths: dict[str, str] = {}
    for name, result in variants.items():
        csv_path = output / f"batch3_equity_{name}.csv"
        write_equity_curve_csv(csv_path, result.equity_curve)
        csv_paths[name] = str(csv_path)

    variant_rows = [
        _variant_summary_row(
            name,
            result,
            liquidity=_liquidity_readiness(execution_rows),
            missing_adjustment_factor_ratio=loaded["price_path_adjustment"]["missing_adjustment_factor_ratio"],
        )
        for name, result in variants.items()
    ]
    primary_names = ["fixed_20d_equal", "risk_budget_rpt_0p005", "risk_budget_rpt_0p01"]
    slices = _risk_slices(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        price_paths=price_paths,
        benchmark_rows=benchmark_rows,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    bootstrap = _bootstrap_by_date(
        variants["fixed_20d_equal"],
        variants["risk_budget_rpt_0p005"],
    )
    walk_forward = _risk_walk_forward(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        price_paths=price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    cap_sensitivity = _single_name_cap_sensitivity(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        price_paths=price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    recommendation = _risk_budget_recommendation(variant_rows, bootstrap, walk_forward)
    payload = {
        "status": "research_only" if recommendation["status"] != "ready" else "ready",
        "db_path": str(db_path),
        "report_path": str(report),
        "signal_kind": signal_kind,
        "portfolio_engine_version": PORTFOLIO_ENGINE_VERSION,
        "execution_row_count": len(execution_rows),
        "csv_paths": csv_paths,
        "variant_rows": variant_rows,
        "slices": slices,
        "bootstrap_by_date": bootstrap,
        "walk_forward": walk_forward,
        "single_name_cap_sensitivity": cap_sensitivity,
        "top_contributions": {
            name: _top_contributions(variants[name])
            for name in primary_names
            if name in variants
        },
        "recommendation": recommendation,
        "data_warnings": loaded["issues"],
    }
    _write_risk_report(report, payload)
    return payload


def run_hold_progress_exit_simulation_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_EXIT_REPORT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    output = Path(output_dir)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_exit_report(report, payload)
        return payload

    simulations = simulate_hold_progress_exits(
        loaded["execution_rows"],
        loaded["price_paths"],
    )
    if not simulations:
        payload = _blocked_payload("No path rows could be evaluated for no-progress exit simulation.")
        _write_exit_report(report, payload)
        return payload
    position_csv = output / "batch3_hold_progress_exit_positions.csv"
    _write_csv(position_csv, simulations)
    portfolio_rows = _hold_exit_portfolio_comparison(
        loaded["execution_rows"],
        simulations,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    portfolio_csv = output / "batch3_hold_progress_exit_portfolio.csv"
    _write_csv(portfolio_csv, portfolio_rows)
    residual_rows = _residual_summary(simulations)
    rule_rows = _exit_rule_summary(simulations, portfolio_rows)
    portfolio_engine_mode = "horizon_diagnostic"
    recommendation = _hold_exit_recommendation(
        rule_rows,
        portfolio_rows,
        portfolio_engine_mode=portfolio_engine_mode,
    )
    payload = {
        "status": "research_only",
        "db_path": str(db_path),
        "report_path": str(report),
        "signal_kind": signal_kind,
        "portfolio_engine_mode": portfolio_engine_mode,
        "portfolio_comparison_scope": "diagnostic_only_not_comparable_to_path_mode_risk_report",
        "position_level_csv": str(position_csv),
        "portfolio_level_csv": str(portfolio_csv),
        "evaluated_position_rule_rows": len(simulations),
        "residual_rows": residual_rows,
        "rule_rows": rule_rows,
        "portfolio_rows": portfolio_rows,
        "recommendation": recommendation,
        "data_warnings": loaded["issues"],
    }
    _write_exit_report(report, payload)
    return payload


def run_entry_premium_interaction_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_ENTRY_REPORT,
    signal_kind: str | None = None,
) -> dict[str, Any]:
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind or "")
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_entry_report(report, payload)
        return payload

    benchmark_regime = _volatility_regime_by_date(loaded["benchmark_rows"])
    rows: list[dict[str, object]] = []
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in loaded["execution_rows"]:
        premium = _entry_premium(row)
        return_20d = _first_float(row.get("return_20d_net_adj"), row.get("return_20d_net"))
        if premium is None or return_20d is None:
            continue
        bucket = _entry_premium_bucket(premium)
        interactions = {
            "signal_kind": str(row.get("signal_kind") or "UNKNOWN"),
            "market_state": str(row.get("market_state") or "UNKNOWN"),
            "liquidity_bucket": _liquidity_bucket(_first_float(row.get("daily_amount"))),
            "volatility_regime": benchmark_regime.get(str(row.get("signal_date") or row.get("entry_date"))[:10], "UNKNOWN"),
        }
        for group_type, group_value in interactions.items():
            grouped[(group_type, group_value, bucket)].append(return_20d)
    for (group_type, group_value, bucket), returns in sorted(grouped.items()):
        rows.append(_return_summary_row(group_type, group_value, bucket, returns))
    payload = {
        "status": "research_only",
        "db_path": str(db_path),
        "report_path": str(report),
        "row_count": len(rows),
        "interaction_rows": rows,
        "conclusion": "diagnostic_only_no_hard_cap",
    }
    _write_entry_report(report, payload)
    return payload


def run_gate_exposure_repair_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_GATE_REPAIR_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_gate_repair_report(report, payload)
        return payload
    execution_rows = loaded["execution_rows"]
    start_date, end_date = _execution_date_window(execution_rows)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        calendar = _gate_exposure_readiness(conn, start_date=start_date, end_date=end_date)
    finally:
        conn.close()
    fixed = run_portfolio_backtest(
        execution_rows,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk_005 = run_portfolio_backtest(
        execution_rows,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        sizing="risk_budget",
        risk_per_trade=0.005,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk_010 = run_portfolio_backtest(
        execution_rows,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        sizing="risk_budget",
        risk_per_trade=0.010,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    trading_day_rows = [
        _equity_exposure_coverage("fixed_20d_equal", fixed.equity_curve),
        _equity_exposure_coverage("risk_budget_rpt_0p005", risk_005.equity_curve),
        _equity_exposure_coverage("risk_budget_rpt_0p01", risk_010.equity_curve),
    ]
    max_trading_day_fallback = max(
        (_float_or_default(row.get("fallback_ratio"), 1.0) for row in trading_day_rows),
        default=1.0,
    )
    blockers = []
    if _float_or_default(calendar.get("fallback_ratio"), 1.0) > 0.10:
        blockers.append(f"calendar-day gate exposure fallback ratio {_fmt(calendar.get('fallback_ratio'))} remains above 10%")
    if max_trading_day_fallback > 0.10:
        blockers.append(f"trading-day gate exposure fallback ratio {_fmt(max_trading_day_fallback)} remains above 10%")
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "calendar_day_exposure": calendar,
        "trading_day_exposure": trading_day_rows,
        "explanation": "Calendar-day readiness includes every date in the execution window; trading-day ratios are measured on portfolio equity-curve dates.",
        "target": "fallback ratio < 10%, ideally 0; current data remains blocked.",
        "blockers": blockers,
    }
    _write_gate_repair_report(report, payload)
    return payload


def run_liquidity_unit_capacity_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_LIQUIDITY_REPORT,
    signal_kind: str = "stock_candidate",
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_liquidity_unit_report(report, payload)
        return payload
    liquidity = _liquidity_readiness(loaded["execution_rows"])
    thresholds_all_fail = all(row["pass_count"] == 0 for row in liquidity["thresholds"])
    payload = {
        "status": "blocked",
        "report_path": str(report),
        "signal_kind": signal_kind,
        "liquidity": liquidity,
        "unit_status": "unverified",
        "interpretation": "If daily_amount is RMB, the candidate pool is below executable capacity. If it is not RMB, upstream unit mapping must be fixed before readiness can improve.",
        "thresholds_all_fail": thresholds_all_fail,
        "blockers": [
            "daily_amount upstream unit remains unverified",
            "liquidity thresholds have no passing known rows",
        ],
    }
    _write_liquidity_unit_report(report, payload)
    return payload


def run_adjustment_factor_gap_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_ADJ_GAP_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_adjustment_gap_report(report, payload)
        return payload
    price_paths = loaded["price_paths"]
    clean_keys = {
        key
        for key, rows in price_paths.items()
        if rows and not any(bool(row.get("adj_factor_missing")) for row in rows)
    }
    clean_rows = [
        row
        for row in loaded["execution_rows"]
        if position_path_key(row.get("stock_code"), row.get("entry_date")) in clean_keys
    ]
    clean_price_paths = {key: price_paths[key] for key in clean_keys}
    sensitivity = _adjustment_gap_sensitivity(
        clean_rows,
        loaded["market_state_rows"],
        loaded["exposure_rows"],
        clean_price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    payload = {
        "status": "research_only",
        "report_path": str(report),
        "price_path_adjustment": loaded["price_path_adjustment"],
        "clean_path_count": len(clean_price_paths),
        "clean_execution_row_count": len(clean_rows),
        "sensitivity_excluding_missing_adj_factor_paths": sensitivity,
    }
    _write_adjustment_gap_report(report, payload)
    return payload


def run_risk_budget_robustness_v2_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_RISK_V2_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_risk_v2_report(report, payload)
        return payload
    variants = _run_risk_variant_set(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        price_paths=loaded["price_paths"],
        benchmark_rows=loaded["benchmark_rows"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    daily_bootstrap = _bootstrap_by_date(variants["fixed_20d_equal"], variants["risk_budget_rpt_0p005"])
    month_bootstrap = _cluster_bootstrap_by_period(
        variants["fixed_20d_equal"],
        variants["risk_budget_rpt_0p005"],
        period="month",
    )
    slices = _risk_slices(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        price_paths=loaded["price_paths"],
        benchmark_rows=loaded["benchmark_rows"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    underperforming = [
        row
        for row in slices
        if row.get("slice_type") in {"calendar_year", "market_state", "volatility_regime"}
        and (_first_float(row.get("increment")) or 0.0) < 0
    ]
    walk_forward = _risk_walk_forward(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    payload = {
        "status": "research_only",
        "report_path": str(report),
        "daily_bootstrap": daily_bootstrap,
        "month_cluster_bootstrap": month_bootstrap,
        "walk_forward": walk_forward,
        "underperforming_independent_slices": underperforming,
        "risk_budget_0p005": "research_only",
        "risk_budget_0p010": "rejected_too_concentrated",
        "reason": "Data blockers remain and robustness is not stable across bootstrap, walk-forward return, and independent slices.",
    }
    _write_risk_v2_report(report, payload)
    return payload


def run_hold_progress_exit_path_mode_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_EXIT_PATH_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_exit_path_mode_report(report, payload)
        return payload
    simulations = simulate_hold_progress_exits(loaded["execution_rows"], loaded["price_paths"])
    path_position_csv = report.parent / "batch3_hold_progress_exit_path_mode_positions.csv"
    path_portfolio_csv = report.parent / "batch3_hold_progress_exit_path_mode_portfolio.csv"
    sim_by_rule = _simulations_by_rule(simulations)
    base_specs = [
        ("fixed_20d", "equal_weight", None),
        ("risk_budget_0p005", "risk_budget", 0.005),
        ("risk_budget_0p010", "risk_budget", 0.010),
    ]
    rules = sorted(
        {
            str(row.get("rule"))
            for row in simulations
            if row.get("portfolio_applicable") and "diagnostic" not in str(row.get("rule"))
        }
    )
    portfolio_rows: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []
    for base_name, sizing, risk in base_specs:
        baseline = _run_path_exit_portfolio_variant(
            loaded["execution_rows"],
            loaded["market_state_rows"],
            loaded["exposure_rows"],
            loaded["price_paths"],
            sim_by_rule,
            rule=None,
            sizing=sizing,
            risk_per_trade=risk,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        portfolio_rows.append(_path_exit_comparison_row(base_name, "baseline", baseline, baseline))
        position_rows.extend(baseline["position_rows"])
        for rule in rules:
            result = _run_path_exit_portfolio_variant(
                loaded["execution_rows"],
                loaded["market_state_rows"],
                loaded["exposure_rows"],
                loaded["price_paths"],
                sim_by_rule,
                rule=rule,
                sizing=sizing,
                risk_per_trade=risk,
                initial_capital=initial_capital,
                max_positions=max_positions,
            )
            portfolio_rows.append(_path_exit_comparison_row(base_name, rule, result, baseline))
            position_rows.extend(result["position_rows"])
    _write_csv(path_position_csv, position_rows)
    _write_csv(path_portfolio_csv, portfolio_rows)
    rule_rows = _path_exit_rule_summary(portfolio_rows)
    candidate_rules = _path_exit_candidate_rules(rule_rows)
    data_gate_blockers = _path_exit_data_gate_blockers(
        loaded["execution_rows"],
        loaded["price_path_adjustment"],
        portfolio_rows,
    )
    payload = {
        "status": "research_only",
        "report_path": str(report),
        "engine_mode": "path_mode_report_layer_v1",
        "position_level_csv": str(path_position_csv),
        "portfolio_level_csv": str(path_portfolio_csv),
        "portfolio_rows": portfolio_rows,
        "rule_rows": rule_rows,
        "recommendation": {
            "no_progress_exit": "research_only",
            "candidate_rules": [],
            "research_leads": candidate_rules,
            "blocked_by_data_quality": bool(data_gate_blockers),
            "data_gate_blockers": data_gate_blockers,
            "reason": "Path-mode relative leads require non-worse fixed and risk-budget return/drawdown, but paper-trading candidates stay blocked while data gates fail.",
        },
    }
    _write_exit_path_mode_report(report, payload)
    return payload


def run_gate_exposure_repair_v2_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_GATE_REPAIR_V2_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_gate_repair_v2_report(report, payload)
        return payload
    execution_rows = loaded["execution_rows"]
    start_date, end_date = _execution_date_window(execution_rows)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        calendar = _gate_exposure_readiness(conn, start_date=start_date, end_date=end_date)
        diagnostics = _gate_exposure_source_diagnostics(conn, start_date=start_date, end_date=end_date)
    finally:
        conn.close()
    fixed = run_portfolio_backtest(
        execution_rows,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    trading_day = _equity_exposure_coverage("fixed_20d_equal", fixed.equity_curve)
    calendar_fallback_ratio = _float_or_default(calendar.get("fallback_ratio"), 1.0)
    trading_fallback_ratio = _float_or_default(trading_day.get("fallback_ratio"), 1.0)
    blockers = []
    if calendar_fallback_ratio > 0.10:
        blockers.append("calendar-day gate exposure fallback ratio remains above 10%")
    if trading_fallback_ratio > 0.10:
        blockers.append("trading-day gate exposure fallback ratio remains above 10%")
    if trading_fallback_ratio <= 0.10 and calendar_fallback_ratio > 0.10:
        repair_result = "partially_repaired; trading-day exposure fallback is below 10%, calendar-day coverage still misses non-trading days"
    elif not blockers:
        repair_result = "repaired"
    else:
        repair_result = "not_repaired; source tables or replay coverage remain insufficient"
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "date_window": {"start": start_date, "end": end_date},
        "calendar_day_exposure": calendar,
        "trading_day_exposure": trading_day,
        "source_diagnostics": diagnostics,
        "blockers": blockers,
        "repair_result": repair_result,
    }
    _write_gate_repair_v2_report(report, payload)
    return payload


def run_gate_exposure_repair_v3_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_GATE_REPAIR_V3_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_gate_repair_v3_report(report, payload)
        return payload
    execution_rows = loaded["execution_rows"]
    start_date, end_date = _execution_date_window(execution_rows)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        calendar = _gate_exposure_readiness(conn, start_date=start_date, end_date=end_date)
        diagnostics = _gate_exposure_source_diagnostics(conn, start_date=start_date, end_date=end_date)
        trading_calendar = _gate_trading_calendar_validation(
            conn,
            calendar,
            start_date=start_date,
            end_date=end_date,
        )
    finally:
        conn.close()
    fixed = run_portfolio_backtest(
        execution_rows,
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    trading_day = _equity_exposure_coverage("fixed_20d_equal", fixed.equity_curve)
    calendar_fallback_ratio = _float_or_default(calendar.get("fallback_ratio"), 1.0)
    trading_fallback_ratio = _float_or_default(trading_day.get("fallback_ratio"), 1.0)
    true_missing = _first_float(trading_calendar.get("true_trading_day_missing_count"))
    blockers = []
    warnings = []
    if trading_fallback_ratio > 0.10:
        blockers.append("trading-day gate exposure fallback ratio remains above 10%")
    if trading_calendar.get("status") != "ready":
        blockers.append("calendar missing dates are not validated against a trading-day source")
    elif true_missing is None or true_missing > 0:
        blockers.append("calendar missing dates include true trading days")
    elif calendar_fallback_ratio > 0.10:
        warnings.append("calendar-day fallback remains a pipeline coverage warning, not a strategy hard blocker")

    if not blockers and warnings:
        repair_result = "trading_day_repaired_calendar_pipeline_warning"
    elif not blockers:
        repair_result = "repaired"
    else:
        repair_result = "blocked_pending_gate_coverage_repair"
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "date_window": {"start": start_date, "end": end_date},
        "calendar_day_exposure": calendar,
        "trading_day_exposure": trading_day,
        "trading_calendar_validation": trading_calendar,
        "source_diagnostics": diagnostics,
        "blockers": blockers,
        "warnings": warnings,
        "repair_result": repair_result,
    }
    _write_gate_repair_v3_report(report, payload)
    return payload


def run_liquidity_unit_capacity_v2_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_LIQUIDITY_V2_REPORT,
    signal_kind: str = "stock_candidate",
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_liquidity_v2_report(report, payload)
        return payload
    liquidity = _liquidity_readiness(loaded["execution_rows"])
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = _table_names(conn)
        columns = _columns(conn, TABLE_OBS) if TABLE_OBS in tables else set()
        implied = _liquidity_implied_unit_diagnostics(conn, loaded["execution_rows"], columns)
        lineage = _liquidity_source_lineage_diagnostics(conn, loaded["execution_rows"], columns)
    finally:
        conn.close()
    scaled_thresholds = _liquidity_scaled_thresholds(loaded["execution_rows"])
    blockers = ["daily_amount upstream unit remains unverified"]
    if all(row["pass_count"] == 0 for row in liquidity["thresholds"]):
        blockers.append("liquidity thresholds have no passing known rows under raw unit")
    payload = {
        "status": "blocked",
        "report_path": str(report),
        "source_table": TABLE_OBS,
        "source_field": "amount",
        "source_columns": sorted(columns),
        "unit_status": "unverified",
        "liquidity": liquidity,
        "source_lineage": lineage,
        "implied_unit_diagnostics": implied,
        "scaled_threshold_hypotheses": scaled_thresholds,
        "blockers": blockers,
    }
    _write_liquidity_v2_report(report, payload)
    return payload


def run_adjustment_factor_gap_v2_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_ADJ_GAP_V2_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_adjustment_gap_v2_report(report, payload)
        return payload
    price_paths = loaded["price_paths"]
    clean_keys = {
        key
        for key, rows in price_paths.items()
        if rows and not any(bool(row.get("adj_factor_missing")) for row in rows)
    }
    clean_rows = [
        row
        for row in loaded["execution_rows"]
        if position_path_key(row.get("stock_code"), row.get("entry_date")) in clean_keys
    ]
    clean_price_paths = {key: price_paths[key] for key in clean_keys}
    sensitivity = _adjustment_gap_sensitivity(
        clean_rows,
        loaded["market_state_rows"],
        loaded["exposure_rows"],
        clean_price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        table_diagnostics = _adjustment_factor_table_diagnostics(conn, price_paths)
    finally:
        conn.close()
    missing_rows = loaded["price_path_adjustment"].get("missing_adjustment_factor_rows", 0)
    clean_subset_share = _round(len(clean_rows) / len(loaded["execution_rows"]) if loaded["execution_rows"] else 0.0)
    blockers = []
    if _float_or_default(missing_rows, 0.0) > 0:
        blockers.append("adjustment factor gaps remain in price paths")
    if clean_subset_share < 0.80:
        blockers.append("clean adjustment subset share is below 80%; promotion conclusions would be sample-biased")
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "price_path_adjustment": loaded["price_path_adjustment"],
        "missing_by_month": _adjustment_gap_by_month(price_paths),
        "missing_by_board": _adjustment_gap_by_board(price_paths),
        "adj_factor_table_diagnostics": table_diagnostics,
        "clean_path_count": len(clean_price_paths),
        "clean_execution_row_count": len(clean_rows),
        "clean_subset_share": clean_subset_share,
        "sample_selection_warning": "clean subset may be biased because only paths with complete adjustment factors remain",
        "sensitivity_excluding_missing_adj_factor_paths": sensitivity,
        "blockers": blockers,
    }
    _write_adjustment_gap_v2_report(report, payload)
    return payload


def run_gate_fallback_split_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_GATE_FALLBACK_SPLIT_REPORT,
    gate_payload: Mapping[str, Any] | None = None,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    payload = dict(gate_payload or {})
    if not payload:
        payload = run_gate_exposure_repair_v3_report(
            db_path=db_path,
            report_path=report.with_name(DEFAULT_GATE_REPAIR_V3_REPORT.name),
            signal_kind=signal_kind,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
    if payload.get("status") == "blocked" and "calendar_day_exposure" not in payload:
        split_payload = _blocked_payload(str(payload.get("reason") or "gate payload unavailable"))
        _write_gate_fallback_split_report(report, split_payload)
        return split_payload
    calendar = payload.get("calendar_day_exposure", {})
    trading = payload.get("trading_day_exposure", {})
    validation = payload.get("trading_calendar_validation", {})
    backfill = _read_csi300_backfill_report_summary(report.parent / "2026-07-batch3-csi300-benchmark-backfill-report.md")
    decision = _gate_fallback_split_decision(calendar, trading, validation)
    split_payload = {
        "status": decision["path_simulation_status"],
        "report_path": str(report),
        "db_path": db_path,
        "date_window": payload.get("date_window"),
        "calendar_day_exposure": calendar,
        "trading_day_exposure": trading,
        "trading_calendar_validation": validation,
        "backfill_summary": backfill,
        "path_simulation_gate": decision,
        "calendar_pipeline_gate": {
            "status": "research_only" if _float_or_default(calendar.get("fallback_ratio"), 1.0) > 0.10 else "ready",
            "reason": "natural-date calendar fallback is a pipeline coverage diagnostic, not the path simulation fallback metric",
        },
        "by_date_fallback": {
            "calendar_missing_dates": calendar.get("missing_dates", []),
            "calendar_missing_date_ranges": calendar.get("missing_date_ranges", []),
            "trading_day_fallback_date_ranges": trading.get("fallback_date_ranges", []),
        },
        "blockers": decision["blockers"],
        "warnings": decision["warnings"],
        "live_strategy_changes": "none",
    }
    _write_gate_fallback_split_report(report, split_payload)
    return split_payload


def run_liquidity_canonical_rmb_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_LIQUIDITY_CANONICAL_RMB_REPORT,
    signal_kind: str = "stock_candidate",
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_liquidity_canonical_rmb_report(report, payload)
        return payload
    execution_rows = loaded["execution_rows"]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = _table_names(conn)
        columns = _columns(conn, TABLE_OBS) if TABLE_OBS in tables else set()
        lineage = _liquidity_source_lineage_diagnostics(conn, execution_rows, columns)
        implied = _liquidity_implied_unit_diagnostics(conn, execution_rows, columns)
        amount_like_sources = _amount_like_source_columns(conn)
    finally:
        conn.close()
    raw_liquidity = _liquidity_readiness(execution_rows)
    scale_hypotheses = _liquidity_canonical_scale_hypotheses(execution_rows)
    coverage = _liquidity_trade_coverage(execution_rows, canonical_multiplier=None)
    canonical = _canonical_liquidity_status(lineage, implied)
    blockers = []
    if canonical["status"] != "ready":
        blockers.append("daily_amount_rmb_canonical is not verified by vendor/unit lineage")
    if all(row["pass_count"] == 0 for row in raw_liquidity["thresholds"]):
        blockers.append("raw daily_amount thresholds have zero passing rows; unit investigation remains required")
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "db_path": db_path,
        "canonical_field": "daily_amount_rmb_canonical",
        "canonical_status": canonical["status"],
        "canonical_multiplier": canonical.get("multiplier"),
        "canonical_evidence": canonical,
        "source_lineage": lineage,
        "implied_unit_diagnostics": implied,
        "amount_like_sources": amount_like_sources,
        "raw_liquidity": raw_liquidity,
        "scale_hypotheses": scale_hypotheses,
        "trade_coverage": coverage,
        "liquidity_blocked": bool(blockers),
        "blockers": blockers,
        "live_strategy_changes": "none",
    }
    _write_liquidity_canonical_rmb_report(report, payload)
    return payload


def run_adjustment_factor_repair_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_ADJ_REPAIR_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_adjustment_factor_repair_report(report, payload)
        return payload
    price_paths = loaded["price_paths"]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sources = _adjustment_factor_source_inventory(conn)
        table_diagnostics = _adjustment_factor_table_diagnostics(conn, price_paths)
    finally:
        conn.close()
    clean_keys = {
        key
        for key, rows in price_paths.items()
        if rows and not any(bool(row.get("adj_factor_missing")) for row in rows)
    }
    clean_rows = [
        row
        for row in loaded["execution_rows"]
        if position_path_key(row.get("stock_code"), row.get("entry_date")) in clean_keys
    ]
    clean_price_paths = {key: price_paths[key] for key in clean_keys}
    price_quality = loaded["price_path_adjustment"]
    missing_ratio = _float_or_default(price_quality.get("missing_adjustment_factor_ratio"), 1.0)
    clean_subset_share = _round(len(clean_rows) / len(loaded["execution_rows"]) if loaded["execution_rows"] else 0.0)
    blockers = _adjustment_factor_blockers(missing_ratio, clean_subset_share)
    if blockers:
        full_sample = {"status": "skipped_until_adjustment_factor_blocker_clears"}
        clean_sample = {"status": "skipped_until_adjustment_factor_blocker_clears"}
    else:
        full_sample = _sample_variant_metrics(
            loaded["execution_rows"],
            loaded["market_state_rows"],
            loaded["exposure_rows"],
            price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        clean_sample = _sample_variant_metrics(
            clean_rows,
            loaded["market_state_rows"],
            loaded["exposure_rows"],
            clean_price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "db_path": db_path,
        "price_path_adjustment": price_quality,
        "source_inventory": sources,
        "adj_factor_table_diagnostics": table_diagnostics,
        "coverage": _adjustment_repair_coverage(price_paths, loaded["execution_rows"]),
        "denominator_scopes": _adjustment_denominator_scopes(loaded, canonical_path_rows=None),
        "full_sample_current": full_sample,
        "clean_adjustment_subset": clean_sample,
        "repaired_factor_sample": {
            "status": "blocked",
            "reason": "No explicit additional factor source with the missing path dates was found; no forward-fill or future-value reconstruction was applied.",
        },
        "clean_subset_share": clean_subset_share,
        "sample_selection_warning": "clean subset is sample-biased when share is below 70%",
        "instability": _sample_instability(full_sample, clean_sample) if not blockers else {"status": "skipped_until_repair"},
        "blockers": blockers,
        "live_strategy_changes": "none",
    }
    _write_adjustment_factor_repair_report(report, payload)
    return payload


def build_canonical_research_dataset(
    *,
    db_path: str,
    output_dir: str | Path = DEFAULT_CANONICAL_RESEARCH_DIR,
    signal_kind: str = "stock_candidate",
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths_path = out / "canonical_strategy_paths.parquet"
    trades_path = out / "canonical_strategy_trades.parquet"
    quality_path = out / "canonical_data_quality_summary.csv"
    manifest_path = out / "canonical_dataset_manifest.json"
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        payload.update(
            {
                "schema_status": "schema_blocked",
                "data_quality_status": "data_quality_blocked",
                "promotion_status": "promotion_blocked",
                "paths_path": str(paths_path),
                "trades_path": str(trades_path),
                "quality_summary_path": str(quality_path),
                "manifest_path": str(manifest_path),
            }
        )
        _write_canonical_dataset_manifest(manifest_path, payload)
        return payload
    path_rows = _canonical_path_rows(loaded, gate_payload, liquidity_payload)
    trade_rows = _canonical_trade_rows(loaded, gate_payload, liquidity_payload, adjustment_payload)
    _write_parquet(paths_path, path_rows)
    _write_parquet(trades_path, trade_rows)
    quality_rows = _canonical_quality_summary_rows(
        loaded,
        path_rows,
        trade_rows,
        gate_payload,
        liquidity_payload,
        adjustment_payload,
    )
    _write_csv(quality_path, quality_rows)
    adjustment_denominator_scopes = _adjustment_denominator_scopes(loaded, canonical_path_rows=path_rows)
    data_quality_flags = _canonical_dataset_quality_flags(
        gate_payload,
        liquidity_payload,
        adjustment_payload,
        path_rows=path_rows,
        trade_rows=trade_rows,
    )
    data_quality_status = "data_quality_blocked" if data_quality_flags else "data_quality_ready"
    promotion_status = "promotion_blocked" if data_quality_flags else "promotion_ready"
    payload = {
        "status": "schema_ready",
        "schema_status": "schema_ready",
        "data_quality_status": data_quality_status,
        "promotion_status": promotion_status,
        "dataset_id": "2026-07-batch3",
        "db_path": db_path,
        "paths_path": str(paths_path),
        "trades_path": str(trades_path),
        "quality_summary_path": str(quality_path),
        "manifest_path": str(manifest_path),
        "path_row_count": len(path_rows),
        "trade_row_count": len(trade_rows),
        "quality_row_count": len(quality_rows),
        "date_range": _execution_date_window(loaded["execution_rows"]),
        "source_tables": [TABLE_EXECUTION_HIST, TABLE_OBS, TABLE_ADJ_FACTOR, "fact_choice_macro_daily"],
        "paths_sha256": _file_sha256(paths_path),
        "trades_sha256": _file_sha256(trades_path),
        "quality_sha256": _file_sha256(quality_path),
        "adjustment_denominator_scopes": adjustment_denominator_scopes,
        "data_quality_flags": data_quality_flags,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "live_strategy_changes": "none",
    }
    _write_canonical_dataset_manifest(manifest_path, payload)
    return payload


def _sync_adjustment_repair_report_with_canonical_denominators(
    adjustment_payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
) -> dict[str, Any]:
    scopes = canonical_payload.get("adjustment_denominator_scopes")
    if not isinstance(scopes, Mapping) or "price_path_adjustment" not in adjustment_payload:
        return dict(adjustment_payload)
    updated = dict(adjustment_payload)
    updated["denominator_scopes"] = dict(scopes)
    updated["denominator_scope_source"] = "canonical_research_dataset"
    report_path = updated.get("report_path")
    if report_path:
        _write_adjustment_factor_repair_report(Path(str(report_path)), updated)
    return updated


def run_risk_budget_optimization_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_RISK_OPTIMIZATION_REPORT,
    signal_kind: str = "stock_candidate",
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_risk_budget_optimization_report(report, payload)
        return payload
    preliminary_blockers = _data_quality_go_blockers(gate_payload, liquidity_payload, adjustment_payload)
    if preliminary_blockers:
        decision = {
            "recommendation": "blocked",
            "candidate_list": [],
            "best_research_candidate": {"risk_per_trade": 0.005, "status": "research_only"},
            "best_conservative_candidate": {"risk_per_trade": 0.003, "status": "research_only"},
            "selected_walk_forward_risk_per_trade": None,
            "blockers": sorted(set(preliminary_blockers)),
            "risk_0p010_candidate_allowed": False,
        }
        payload = {
            "status": "blocked",
            "report_path": str(report),
            "db_path": db_path,
            "canonical_dataset": canonical_payload,
            "optimization_rows": [],
            "grid_execution_status": "skipped_until_data_blockers_clear",
            "grid_skip_reason": "full risk_per_trade x single_name_cap x downside_portfolio_exposure_cap grid is not executed while data blockers remain",
            "portfolio_exposure_cap_semantics": "numeric cells are downside clamps on the existing gate exposure series; they do not lever exposure above the gate",
            "required_grid_cell_count": (
                len(RISK_PER_TRADE_OPTIMIZATION_GRID)
                * len(SINGLE_NAME_CAP_OPTIMIZATION_GRID)
                * len(PORTFOLIO_EXPOSURE_CAP_GRID)
            ),
            "required_risk_per_trade_grid": list(RISK_PER_TRADE_OPTIMIZATION_GRID),
            "required_single_name_cap_grid": list(SINGLE_NAME_CAP_OPTIMIZATION_GRID),
            "required_portfolio_exposure_cap_grid": list(PORTFOLIO_EXPOSURE_CAP_GRID),
            "full_sample_metrics": {},
            "walk_forward": {"status": "skipped_until_data_blockers_clear"},
            "daily_bootstrap": {"status": "skipped_until_data_blockers_clear"},
            "month_cluster_bootstrap": {"status": "skipped_until_data_blockers_clear"},
            "slices": [],
            "slice_status": "skipped_until_data_blockers_clear",
            "top_contributions": {},
            "decision": decision,
            "live_strategy_changes": "none",
        }
        _write_risk_budget_optimization_report(report, payload)
        return payload
    optimization_rows = _risk_budget_optimization_rows(
        loaded,
        gate_payload=gate_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    fixed = run_portfolio_backtest(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk_003 = run_portfolio_backtest(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        sizing="risk_budget",
        risk_per_trade=0.003,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk_005 = run_portfolio_backtest(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        variant="fixed_20d",
        mode="path",
        price_paths=loaded["price_paths"],
        sizing="risk_budget",
        risk_per_trade=0.005,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    daily_bootstrap = _bootstrap_by_date(fixed, risk_005)
    month_bootstrap = _cluster_bootstrap_by_period(fixed, risk_005, period="month")
    walk_forward = _risk_walk_forward(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        exposure_rows=loaded["exposure_rows"],
        price_paths=loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    decision = _risk_budget_optimization_decision(
        optimization_rows,
        gate_payload=gate_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
        daily_bootstrap=daily_bootstrap,
        month_bootstrap=month_bootstrap,
        walk_forward=walk_forward,
    )
    payload = {
        "status": decision["recommendation"],
        "report_path": str(report),
        "db_path": db_path,
        "canonical_dataset": canonical_payload,
        "optimization_rows": optimization_rows,
        "grid_execution_status": "executed_full_grid",
        "grid_skip_reason": None,
        "portfolio_exposure_cap_semantics": "numeric cells are downside clamps on the existing gate exposure series; they do not lever exposure above the gate",
        "required_grid_cell_count": (
            len(RISK_PER_TRADE_OPTIMIZATION_GRID)
            * len(SINGLE_NAME_CAP_OPTIMIZATION_GRID)
            * len(PORTFOLIO_EXPOSURE_CAP_GRID)
        ),
        "required_risk_per_trade_grid": list(RISK_PER_TRADE_OPTIMIZATION_GRID),
        "required_single_name_cap_grid": list(SINGLE_NAME_CAP_OPTIMIZATION_GRID),
        "required_portfolio_exposure_cap_grid": list(PORTFOLIO_EXPOSURE_CAP_GRID),
        "full_sample_metrics": {
            "fixed_20d": fixed.metrics,
            "risk_budget_0p003": risk_003.metrics,
            "risk_budget_0p005": risk_005.metrics,
        },
        "walk_forward": walk_forward,
        "daily_bootstrap": daily_bootstrap,
        "month_cluster_bootstrap": month_bootstrap,
        "slices": []
        if decision["blockers"]
        else _risk_slices(
            loaded["execution_rows"],
            loaded["market_state_rows"],
            exposure_rows=loaded["exposure_rows"],
            price_paths=loaded["price_paths"],
            benchmark_rows=loaded["benchmark_rows"],
            initial_capital=initial_capital,
            max_positions=max_positions,
        ),
        "slice_status": "skipped_until_data_blockers_clear" if decision["blockers"] else "ready",
        "top_contributions": {
            "risk_budget_0p003": _top_contributions(risk_003),
            "risk_budget_0p005": _top_contributions(risk_005),
        },
        "decision": decision,
        "live_strategy_changes": "none",
    }
    _write_risk_budget_optimization_report(report, payload)
    return payload


def run_underwater_exit_overlay_optimization_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_UNDERWATER_OVERLAY_OPT_REPORT,
    signal_kind: str = "stock_candidate",
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_underwater_overlay_optimization_report(report, payload)
        return payload
    blockers = _data_quality_go_blockers(gate_payload, liquidity_payload, adjustment_payload)
    if blockers:
        payload = {
            "status": "blocked",
            "report_path": str(report),
            "db_path": db_path,
            "canonical_dataset": canonical_payload,
            "rule_effect_rows": [],
            "portfolio_comparison_rows": [],
            "priority_research_leads": ["day5_underwater_exit", "day3_underwater_reduce_half"],
            "frozen_prior_diagnostic_reference": _frozen_underwater_prior_diagnostics(),
            "blockers": blockers,
            "reason": "Underwater exit overlay promotion is skipped until data blockers clear; existing path-mode diagnostics remain research-only.",
            "live_strategy_changes": "none",
        }
        _write_underwater_overlay_optimization_report(report, payload)
        return payload
    simulations = simulate_hold_progress_exits(loaded["execution_rows"], loaded["price_paths"])
    comparison_rows = _underwater_overlay_comparison_rows(
        loaded,
        simulations,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    effect_rows = _underwater_rule_effect_rows(simulations, comparison_rows)
    research_leads = [
        row["rule"]
        for row in effect_rows
        if row.get("candidate_status") in {"research_lead", "research_only"}
        and row.get("rule") in {"day5_underwater_exit", "day3_underwater_reduce_half"}
    ]
    payload = {
        "status": "blocked" if blockers else "research_only",
        "report_path": str(report),
        "db_path": db_path,
        "canonical_dataset": canonical_payload,
        "rule_effect_rows": effect_rows,
        "portfolio_comparison_rows": comparison_rows,
        "priority_research_leads": research_leads,
        "frozen_prior_diagnostic_reference": _frozen_underwater_prior_diagnostics(),
        "blockers": blockers,
        "reason": "Underwater exit overlays are research leads only while liquidity and adjustment data blockers remain.",
        "live_strategy_changes": "none",
    }
    _write_underwater_overlay_optimization_report(report, payload)
    return payload


def run_a_share_trading_constraint_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_A_SHARE_CONSTRAINT_REPORT,
    signal_kind: str = "stock_candidate",
    liquidity_payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_a_share_trading_constraint_report(report, payload)
        return payload
    diagnostics = _a_share_constraint_diagnostics(loaded["execution_rows"], loaded["price_paths"], liquidity_payload)
    blockers = []
    if diagnostics["execution_constraint_status"] != "ready":
        blockers.append("A-share execution constraints are research_only/incomplete: board lot, ST, limit-down delay, or capacity gates are not fully integrated")
    if liquidity_payload.get("canonical_status") != "ready":
        blockers.append("capacity estimate blocked until canonical RMB liquidity amount is verified")
    payload = {
        "status": "blocked" if blockers else "research_only",
        "report_path": str(report),
        "db_path": db_path,
        "canonical_dataset": canonical_payload,
        "diagnostics": diagnostics,
        "blockers": blockers,
        "live_strategy_changes": "none",
    }
    _write_a_share_trading_constraint_report(report, payload)
    return payload


def run_path_engine_tieout_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_PATH_TIEOUT_REPORT,
    signal_kind: str = "stock_candidate",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    report = Path(report_path)
    loaded = _load_batch3_inputs(db_path=db_path, signal_kind=signal_kind)
    if loaded["status"] != "ready":
        payload = _blocked_payload(loaded["reason"])
        _write_path_tieout_report(report, payload)
        return payload
    rows = _path_engine_tieout_rows(
        loaded["execution_rows"],
        loaded["market_state_rows"],
        loaded["exposure_rows"],
        loaded["price_paths"],
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    max_abs_delta = max(
        abs(_first_float(row.get("cumulative_return_delta")) or 0.0)
        for row in rows
    ) if rows else 1.0
    payload = {
        "status": "ready" if max_abs_delta <= 0.000001 else "blocked",
        "report_path": str(report),
        "tieout_rows": rows,
        "max_abs_cumulative_return_delta": _round(max_abs_delta),
        "explanation": "Report-layer path baseline now uses the same buy-before-path-sell ordering as run_portfolio_backtest(mode='path').",
        "blockers": [] if max_abs_delta <= 0.000001 else ["path-mode report baseline does not tie out to risk-budget robustness baseline"],
    }
    _write_path_tieout_report(report, payload)
    return payload


def run_risk_budget_post_data_fix_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_RISK_POST_FIX_REPORT,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = Path(report_path)
    blockers = []
    blockers.extend(str(item) for item in gate_payload.get("blockers", []))
    blockers.extend(str(item) for item in liquidity_payload.get("blockers", []))
    blockers.extend(str(item) for item in adjustment_payload.get("blockers", []))
    payload = {
        "status": "blocked",
        "db_path": db_path,
        "report_path": str(report),
        "risk_budget_candidates": ["0.003", "0.005"],
        "reason": "Post-data-fix robustness cannot be run as a promotion study until gate, liquidity, and adjustment data blockers are resolved.",
        "blockers": sorted(set(blockers)),
    }
    _write_risk_post_fix_report(report, payload)
    return payload


def run_data_blocker_resolution_report(
    *,
    report_path: str | Path = DEFAULT_DATA_BLOCKER_RESOLUTION_REPORT,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = Path(report_path)
    blockers = _post_data_fix_blockers(
        gate_payload=gate_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
    )
    gate_diag = gate_payload.get("source_diagnostics", {})
    replay_sources = gate_diag.get("replay_sources", {})
    supplement = replay_sources.get("fact_livermore_gate_supplement_daily", {})
    trading_validation = gate_payload.get("trading_calendar_validation", {})
    payload = {
        "status": "blocked" if blockers else "ready",
        "report_path": str(report),
        "blockers": blockers,
        "gate": {
            "calendar_fallback_ratio": gate_payload.get("calendar_day_exposure", {}).get("fallback_ratio"),
            "trading_day_fallback_ratio": gate_payload.get("trading_day_exposure", {}).get("fallback_ratio"),
            "true_trading_day_missing_count": trading_validation.get("true_trading_day_missing_count"),
            "true_trading_day_missing_ratio": trading_validation.get("true_trading_day_missing_ratio"),
            "calendar_missing_classification": trading_validation.get("classification"),
            "calendar_missing_not_trading_day_count": trading_validation.get("calendar_missing_not_trading_day_count"),
            "trading_day_sources": trading_validation.get("trading_day_sources", []),
            "supplement_rows": supplement.get("window_rows"),
            "supplement_mapping_assessment": supplement.get("mapping_assessment"),
            "replay_sources": replay_sources,
        },
        "liquidity": {
            "unit_status": liquidity_payload.get("unit_status"),
            "raw_thresholds": liquidity_payload.get("liquidity", {}).get("thresholds", []),
            "unit_diagnostics": liquidity_payload.get("implied_unit_diagnostics", {}),
            "source_lineage": liquidity_payload.get("source_lineage", {}),
            "scale_hypotheses": liquidity_payload.get("scaled_threshold_hypotheses", []),
        },
        "adjustment": {
            "missing_adjustment_factor_rows": adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_rows"),
            "missing_adjustment_factor_ratio": adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio"),
            "clean_subset_share": adjustment_payload.get("clean_subset_share"),
            "sample_selection_warning": adjustment_payload.get("sample_selection_warning"),
        },
    }
    _write_data_blocker_resolution_report(report, payload)
    return payload


def run_post_data_fix_risk_budget_report(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_POST_DATA_FIX_RISK_REPORT,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = Path(report_path)
    blockers = _post_data_fix_blockers(
        gate_payload=gate_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
    )
    payload = {
        "status": "blocked" if blockers else "ready",
        "db_path": db_path,
        "report_path": str(report),
        "risk_budget_candidates": ["0.003", "0.005"],
        "required_comparisons": [
            "fixed_20d",
            "risk_budget_0.003",
            "risk_budget_0.005",
            "exposure_matched_fixed_control",
        ],
        "required_checks": [
            "daily bootstrap",
            "month-cluster bootstrap",
            "walk-forward",
            "year/market-state/volatility/liquidity slices",
        ],
        "blockers": blockers,
        "reason": "Formal post-data-fix risk-budget study is blocked until gate, liquidity, and adjustment blockers are all resolved.",
    }
    _write_post_data_fix_risk_report(report, payload)
    return payload


def run_post_data_fix_hold_progress_report(
    *,
    exit_path_payload: Mapping[str, Any],
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    db_path: str | None = None,
    report_path: str | Path = DEFAULT_POST_DATA_FIX_HOLD_REPORT,
) -> dict[str, Any]:
    report = Path(report_path)
    blockers = _post_data_fix_blockers(
        gate_payload=gate_payload,
        liquidity_payload=liquidity_payload,
        adjustment_payload=adjustment_payload,
    )
    research_leads = exit_path_payload.get("recommendation", {}).get("research_leads", [])
    preferred_retest_order = ["day5_underwater_exit", "day3_underwater_exit", "day3_underwater_reduce_half"]
    priority_retest_rules = [rule for rule in preferred_retest_order if rule in research_leads]
    if not priority_retest_rules:
        priority_retest_rules = list(research_leads)
    payload = {
        "status": "blocked" if blockers else "research_only",
        "db_path": db_path,
        "report_path": str(report),
        "research_leads": research_leads,
        "priority_retest_rule": priority_retest_rules[0] if priority_retest_rules else None,
        "priority_retest_rules": priority_retest_rules,
        "required_rule_gates": [
            "fixed_20d return non-worse",
            "fixed_20d maxDD non-worse",
            "risk_0.005 return non-worse",
            "risk_0.005 maxDD non-worse",
            "p5/p10 left tail improves",
            "winner damage controlled",
            "at least two independent subsamples",
        ],
        "blockers": blockers,
        "reason": "Hold-progress retest is blocked until data gates pass; current path-mode result is a research lead only.",
    }
    _write_post_data_fix_hold_report(report, payload)
    return payload


def write_a_share_optimization_summary(
    *,
    report_path: str | Path = DEFAULT_A_SHARE_OPT_SUMMARY_REPORT,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
    risk_payload: Mapping[str, Any],
    underwater_payload: Mapping[str, Any],
    a_share_constraint_payload: Mapping[str, Any],
    legacy_summary_payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = Path(report_path)
    hard_blockers = sorted(
        set(
            _data_quality_go_blockers(gate_payload, liquidity_payload, adjustment_payload)
            + [str(item) for item in a_share_constraint_payload.get("blockers", [])]
            + [str(item) for item in risk_payload.get("decision", {}).get("blockers", [])]
        )
    )
    paper_trading = "NO" if hard_blockers else "YES"
    decision = risk_payload.get("decision", {})
    best = decision.get("best_research_candidate") or {}
    conservative = decision.get("best_conservative_candidate") or {}
    exit_leads = underwater_payload.get("priority_research_leads", [])
    payload = {
        "status": "blocked" if hard_blockers else "research_only",
        "report_path": str(report),
        "paper_trading": paper_trading,
        "live_strategy_change": "NO",
        "best_research_candidate": _variant_name_from_optimization_row(best) or "risk_budget_0.005",
        "best_conservative_candidate": _variant_name_from_optimization_row(conservative) or "risk_budget_0.003",
        "best_exit_overlay_lead": exit_leads[0] if exit_leads else "day5_underwater_exit",
        "data_readiness": {
            "trading_day_gate_fallback": gate_payload.get("path_simulation_gate", {}).get("trading_day_exposure_fallback_ratio"),
            "calendar_gate_fallback": gate_payload.get("path_simulation_gate", {}).get("calendar_gate_fallback_ratio"),
            "liquidity_canonical_status": liquidity_payload.get("canonical_status"),
            "adjustment_factor_status": adjustment_payload.get("status"),
            "adjustment_factor_missing_ratio": adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio"),
            "macro_status": "blocked_until_macro_composite_history_exists",
            "position_history_status": "blocked_until_position_history_expands",
            "canonical_dataset_status": canonical_payload.get("status"),
            "canonical_schema_status": canonical_payload.get("schema_status"),
            "canonical_data_quality_status": canonical_payload.get("data_quality_status"),
            "canonical_promotion_status": canonical_payload.get("promotion_status"),
            "canonical_data_quality_flags": canonical_payload.get("data_quality_flags"),
            "a_share_execution_constraint_status": a_share_constraint_payload.get("diagnostics", {}).get("execution_constraint_status"),
        },
        "strategy_ranking": [
            {"variant": "risk_budget_0.003", "status": "research_only", "reason": "conservative research candidate; blocked by data gates"},
            {"variant": "risk_budget_0.005", "status": "research_only", "reason": "balanced research candidate; blocked by data gates"},
            {"variant": "risk_budget_0.0075", "status": "diagnostic_only", "reason": "higher concentration risk"},
            {"variant": "risk_budget_0.010", "status": "rejected_diagnostic_only", "reason": "too concentrated and not allowed as candidate"},
            {"variant": "fixed_20d", "status": "baseline", "reason": "comparison baseline"},
        ],
        "hard_blockers": hard_blockers,
        "legacy_summary_status": legacy_summary_payload.get("status"),
        "next_action": "Verify vendor RMB liquidity unit and backfill missing adjustment-factor dates before rerunning promotion tests.",
    }
    _write_a_share_optimization_summary(report, payload)
    return payload


def write_batch3_summary(
    *,
    report_path: str | Path = DEFAULT_SUMMARY_REPORT,
    data_payload: Mapping[str, Any],
    risk_payload: Mapping[str, Any],
    exit_payload: Mapping[str, Any],
    entry_payload: Mapping[str, Any],
    extra_payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    extra_payloads = extra_payloads or {}
    data_ready = data_payload.get("status") == "ready"
    risk_go = "no-go"
    if data_ready and risk_payload.get("recommendation", {}).get("risk_budget_0p005") == "candidate_for_further_paper_trading":
        risk_go = "go"
    exit_go = "no-go"
    if data_ready and exit_payload.get("recommendation", {}).get("no_progress_exit") == "candidate_for_further_paper_trading":
        exit_go = "go"
    gate_summary_payload = (
        extra_payloads.get("gate_exposure_repair_v3")
        or extra_payloads.get("gate_exposure_repair_v2")
        or {}
    )
    gate_validation = gate_summary_payload.get("trading_calendar_validation", {})
    calendar_gate_ratio = gate_summary_payload.get("calendar_day_exposure", {}).get("fallback_ratio")
    if calendar_gate_ratio is None:
        calendar_gate_ratio = data_payload.get("gate_exposure", {}).get("fallback_ratio")
    payload = {
        "status": "research_only",
        "report_path": str(report),
        "risk_budget_0p005_go_no_go": risk_go,
        "no_progress_exit_go_no_go": exit_go,
        "risk_budget_recommendation": risk_payload.get("recommendation", {}),
        "hold_exit_recommendation": exit_payload.get("recommendation", {}),
        "data_status": data_payload.get("status"),
        "fallback_exposure_ratio": data_payload.get("gate_exposure", {}).get("fallback_ratio"),
        "calendar_gate_fallback_ratio": calendar_gate_ratio,
        "trading_day_gate_fallback_ratio": gate_summary_payload.get("trading_day_exposure", {}).get("fallback_ratio"),
        "true_trading_day_missing_count": gate_validation.get("true_trading_day_missing_count"),
        "calendar_missing_classification": gate_validation.get("classification"),
        "liquidity_thresholds": data_payload.get("liquidity", {}).get("thresholds", []),
        "remaining_blockers": _summary_blockers(data_payload, risk_payload, exit_payload, *extra_payloads.values()),
        "extra_report_statuses": {
            name: payload.get("status")
            for name, payload in extra_payloads.items()
        },
        "deferred_or_rejected": {
            "current_probe_pyramid": "defer/rework",
            "max_entry_premium_2_3pct_hard_cap": "rejected",
            "simple_gate_downgrade_delay": "rejected",
            "vol_target": "control_only",
            "macro_multiplier": "blocked_until_macro_composite_history_exists",
            "overheat_live_exit": "blocked_until_position_history_is_much_richer",
        },
        "tests": "Run focused pytest plus ruff after generation; do not use this summary as a live rule.",
    }
    _write_summary_report(report, payload, data_payload, risk_payload, exit_payload, entry_payload)
    return payload


def simulate_hold_progress_exits(
    execution_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    rules = _hold_exit_rules()
    rows: list[dict[str, object]] = []
    for source in execution_rows:
        stock_code = str(source.get("stock_code") or "").strip()
        entry_date = str(source.get("entry_date") or "")[:10]
        if not stock_code or not entry_date:
            continue
        path = tuple(price_paths.get(position_path_key(stock_code, entry_date)) or ())
        if not path:
            continue
        entry_price = path_entry_price(path[0], fallback=_first_float(source.get("entry_price")))
        if entry_price is None or entry_price <= 0:
            continue
        scheduled = calculate_path_horizon_exit(
            path,
            horizon_days=20,
            entry_price=entry_price,
            buy_cost_rate=POLICY.buy_cost_rate,
            sell_cost_rate=POLICY.sell_cost_rate,
            slippage_rate=POLICY.slippage_rate,
        )
        if scheduled is None:
            continue
        scheduled_return = float(scheduled["return_net"])
        for rule in rules:
            rule_row = _simulate_hold_exit_rule(source, path, entry_price, scheduled_return, rule)
            rows.append(rule_row)
    return rows


def _simulate_hold_exit_rule(
    source: Mapping[str, object],
    path: Sequence[Mapping[str, object]],
    entry_price: float,
    scheduled_return: float,
    rule: Mapping[str, object],
) -> dict[str, object]:
    day = int(rule["day"])
    rule_name = str(rule["name"])
    action = str(rule["action"])
    trigger_index = day - 1
    base = {
        "rule": rule_name,
        "action": action,
        "portfolio_applicable": action in {"exit", "reduce_half"},
        "day": day,
        "stock_code": str(source.get("stock_code") or ""),
        "signal_date": str(source.get("signal_date") or "")[:10],
        "entry_date": str(source.get("entry_date") or "")[:10],
        "signal_kind": str(source.get("signal_kind") or ""),
        "market_state": str(source.get("market_state") or ""),
        "baseline_return_net": _round(scheduled_return),
        "triggered": False,
        "overlay_applied": False,
        "missing_exit": False,
        "rule_return_net": _round(scheduled_return),
        "residual_return_after_trigger": None,
        "missed_rebound_cost": 0.0,
        "winner_damage": 0.0,
        "planned_exit_date": str(source.get("exit_date_20d") or "")[:10],
        "exit_date": str(source.get("exit_date_20d") or "")[:10],
    }
    if len(path) <= trigger_index:
        return {**base, "missing_exit": True, "missing_reason": "missing_trigger_day"}
    trigger_mark = path_mark_price(path[trigger_index])
    if trigger_mark is None or trigger_mark <= 0:
        return {**base, "missing_exit": True, "missing_reason": "missing_trigger_mark"}
    floating_return = trigger_mark / entry_price - 1.0
    base["floating_return"] = _round(floating_return)
    if not bool(rule["predicate"](floating_return)):
        return base
    if action == "diagnostic":
        return {
            **base,
            "triggered": True,
            "overlay_applied": False,
            "diagnostic_continuation_return": _round(scheduled_return - floating_return),
            "missing_reason": "",
        }
    exit_row = _next_tradable_open(path, trigger_index + 1)
    if exit_row is None:
        return {**base, "triggered": True, "missing_exit": True, "missing_reason": "missing_next_tradable_open"}
    exit_price = path_entry_price(exit_row, fallback=None)
    if exit_price is None or exit_price <= 0:
        return {**base, "triggered": True, "missing_exit": True, "missing_reason": "missing_next_open_price"}
    trigger_return = _net_return(entry_price, exit_price)
    if action == "reduce_half":
        rule_return = 0.5 * trigger_return + 0.5 * scheduled_return
    else:
        rule_return = trigger_return
    residual = scheduled_return - trigger_return
    missed_rebound = max(scheduled_return - rule_return, 0.0)
    if scheduled_return > 0 and rule_return < scheduled_return:
        winner_damage = scheduled_return - rule_return
    else:
        winner_damage = 0.0
    return {
        **base,
        "triggered": True,
        "overlay_applied": True,
        "rule_return_net": _round(rule_return),
        "trigger_exit_return_net": _round(trigger_return),
        "residual_return_after_trigger": _round(residual),
        "missed_rebound_cost": _round(abs(missed_rebound)),
        "winner_damage": _round(winner_damage),
        "exit_date": str(exit_row.get("trade_date") or "")[:10],
        "exit_price": _round(exit_price),
        "missing_reason": "",
    }


def _load_batch3_inputs(*, db_path: str, signal_kind: str) -> dict[str, Any]:
    db_file = Path(db_path)
    cache_key = (str(db_file.resolve()) if db_file.exists() else str(db_file), signal_kind)
    if cache_key in _BATCH3_INPUT_CACHE:
        return _BATCH3_INPUT_CACHE[cache_key]
    if not db_file.exists():
        return {"status": "blocked", "reason": f"DuckDB file not found: {db_file}"}
    conn = duckdb.connect(str(db_file), read_only=True)
    try:
        tables = _table_names(conn)
        if TABLE_EXECUTION_HIST not in tables:
            return {"status": "blocked", "reason": f"Required table {TABLE_EXECUTION_HIST} is missing."}
        execution_rows, issues = _load_execution_rows(
            conn,
            tables=tables,
            signal_kind=signal_kind,
            start_date=None,
            end_date=None,
        )
        if not execution_rows:
            return {"status": "blocked", "reason": "No execution rows matched the requested filters."}
        start_date, end_date = _execution_date_window(execution_rows)
        exposure_rows, exposure_issues = _load_daily_exposure_rows(
            conn,
            tables=tables,
            start_date=start_date,
            end_date=end_date,
        )
        issues.extend(exposure_issues)
        benchmark_rows, benchmark_tables = _load_benchmark_rows(
            conn,
            tables=tables,
            start_date=start_date,
            end_date=end_date,
        )
        market_state_rows = _market_state_rows_from_execution(execution_rows)
        price_paths = load_position_price_paths(conn, execution_rows, max_horizon_days=25)
        price_path_adjustment = _price_path_readiness(price_paths)
    finally:
        conn.close()
    payload = {
        "status": "ready",
        "execution_rows": execution_rows,
        "market_state_rows": market_state_rows,
        "exposure_rows": exposure_rows,
        "benchmark_rows": benchmark_rows,
        "benchmark_tables": benchmark_tables,
        "price_paths": price_paths,
        "price_path_adjustment": price_path_adjustment,
        "issues": issues,
    }
    _BATCH3_INPUT_CACHE[cache_key] = payload
    return payload


def _run_risk_variant_set(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    benchmark_rows: Sequence[Mapping[str, object]],
    initial_capital: float,
    max_positions: int,
) -> dict[str, PortfolioBacktestResult]:
    results: dict[str, PortfolioBacktestResult] = {
        "fixed_20d_equal": run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        ),
        "fixed_5d_equal": run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_5d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        ),
    }
    for risk_per_trade in RISK_PER_TRADE_GRID:
        results[f"risk_budget_rpt_{_label(risk_per_trade)}"] = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=risk_per_trade,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
    vol_payload = {
        target: build_vol_target_index_comparison(
            benchmark_rows,
            exposure_rows=exposure_rows,
            market_state_rows=market_state_rows,
            exposure_by_market_state=POLICY.exposure_by_market_state,
            target_vol=target,
            window=POLICY.backtest_variants.vol_target_window,
            initial_capital=initial_capital,
        )
        for target in POLICY.backtest_variants.vol_target_grid
    }
    for target, comparison in vol_payload.items():
        exposure_by_date = {
            str(date_key): float(exposure)
            for date_key, exposure in comparison.get("vol_target_exposure_by_date", {}).items()
        }
        if not exposure_by_date:
            continue
        results[f"vol_target_{_label(target)}_control"] = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            exposure_by_date=exposure_by_date,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
            vol_target=target,
        )
    risk_primary = results.get("risk_budget_rpt_0p005")
    if risk_primary is not None:
        matched_exposure = _average_exposure(risk_primary.equity_curve)
        exposure_by_date = {str(row["date"]): matched_exposure for row in risk_primary.equity_curve}
        results["fixed_20d_exposure_matched_to_risk_0p005"] = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            exposure_by_date=exposure_by_date,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
    return results


def _variant_summary_row(
    name: str,
    result: PortfolioBacktestResult,
    *,
    liquidity: Mapping[str, Any],
    missing_adjustment_factor_ratio: float,
) -> dict[str, object]:
    daily_returns = _daily_returns(result.equity_curve)
    sell_returns = [float(row["return_net"]) for row in result.trades if row.get("action") == "sell" and row.get("return_net") is not None]
    winners = [value for value in sell_returns if value > 0]
    losers = [value for value in sell_returns if value < 0]
    metrics = result.metrics
    return {
        "variant": name,
        "cumulative_return": metrics.get("cumulative_return"),
        "cagr": metrics.get("cagr"),
        "max_drawdown": metrics.get("max_drawdown"),
        "daily_sharpe": metrics.get("daily_sharpe"),
        "sortino": _sortino(daily_returns),
        "calmar": _calmar(metrics.get("cagr"), metrics.get("max_drawdown")),
        "annual_turnover": metrics.get("annual_turnover"),
        "average_exposure": _average_exposure(result.equity_curve),
        "max_single_name_weight": metrics.get("max_single_name_weight"),
        "average_position_count": _average_position_count(result.equity_curve),
        "win_rate": _ratio(len(winners), len(sell_returns)),
        "average_winner": _round(statistics.fmean(winners)) if winners else None,
        "average_loser": _round(statistics.fmean(losers)) if losers else None,
        "fallback_exposure_ratio": metrics.get("exposure_fallback_day_ratio"),
        "missing_adjusted_path_ratio": missing_adjustment_factor_ratio,
        "liquidity_200m_pass_count": _threshold_row(liquidity, 200_000_000.0).get("pass_count"),
        "liquidity_200m_fail_count": _threshold_row(liquidity, 200_000_000.0).get("fail_count"),
        "trade_count": len([row for row in result.trades if row.get("action") == "sell"]),
    }


def _risk_slices(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    benchmark_rows: Sequence[Mapping[str, object]],
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    slice_specs = []
    slice_specs.extend(("calendar_year", key, rows) for key, rows in _calendar_year_slices(execution_rows).items())
    slice_specs.extend(("calendar_half", key, rows) for key, rows in _calendar_half_slices(execution_rows).items())
    slice_specs.extend(("market_state", key, rows) for key, rows in _group_slices(execution_rows, "market_state").items())
    slice_specs.extend(("signal_kind", key, rows) for key, rows in _group_slices(execution_rows, "signal_kind").items())
    slice_specs.extend(("liquidity_bucket", key, rows) for key, rows in _liquidity_slices(execution_rows).items())
    slice_specs.extend(("entry_premium_bucket", key, rows) for key, rows in _entry_premium_slices(execution_rows).items())
    slice_specs.extend(
        ("volatility_regime", key, rows)
        for key, rows in _volatility_regime_slices(execution_rows, benchmark_rows).items()
    )
    out: list[dict[str, object]] = []
    for slice_type, slice_value, rows in slice_specs:
        if len(rows) < 10:
            continue
        fixed = run_portfolio_backtest(
            rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        risk = run_portfolio_backtest(
            rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=0.005,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        out.append(
            {
                "slice_type": slice_type,
                "slice_value": slice_value,
                "row_count": len(rows),
                "fixed_20d_return": fixed.metrics.get("cumulative_return"),
                "risk_0p005_return": risk.metrics.get("cumulative_return"),
                "increment": _round(
                    _first_float(risk.metrics.get("cumulative_return"))
                    - _first_float(fixed.metrics.get("cumulative_return"))
                )
                if fixed.metrics.get("cumulative_return") is not None and risk.metrics.get("cumulative_return") is not None
                else None,
                "risk_0p005_max_drawdown": risk.metrics.get("max_drawdown"),
                "risk_0p005_sharpe": risk.metrics.get("daily_sharpe"),
            }
        )
    return out


def _bootstrap_by_date(
    fixed_result: PortfolioBacktestResult,
    risk_result: PortfolioBacktestResult,
    *,
    iterations: int = 300,
) -> dict[str, object]:
    fixed_returns = _returns_by_date(fixed_result.equity_curve)
    risk_returns = _returns_by_date(risk_result.equity_curve)
    dates = sorted(set(fixed_returns) & set(risk_returns))
    if not dates:
        return {"status": "blocked", "reason": "No paired daily returns."}
    paired = [risk_returns[date] - fixed_returns[date] for date in dates]
    rng = random.Random(RANDOM_SEED)
    samples = []
    for _ in range(iterations):
        compounded = 1.0
        for _date in dates:
            compounded *= 1.0 + rng.choice(paired)
        samples.append(compounded - 1.0)
    return {
        "status": "ready",
        "iterations": iterations,
        "date_count": len(dates),
        "mean_increment": _round(statistics.fmean(samples)),
        "p10_increment": _round(_percentile(samples, 0.10)),
        "p50_increment": _round(_percentile(samples, 0.50)),
        "p90_increment": _round(_percentile(samples, 0.90)),
    }


def _risk_walk_forward(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    initial_capital: float,
    max_positions: int,
) -> dict[str, object]:
    dates = sorted({str(row.get("signal_date") or row.get("entry_date"))[:10] for row in execution_rows if row.get("entry_date")})
    if len(dates) < 20:
        return {"status": "blocked", "reason": "Not enough dates for train/test split."}
    split_date = dates[int(len(dates) * 0.60)]
    train_rows = [row for row in execution_rows if str(row.get("signal_date") or row.get("entry_date"))[:10] < split_date]
    test_rows = [row for row in execution_rows if str(row.get("signal_date") or row.get("entry_date"))[:10] >= split_date]
    train_results = {}
    for risk in RISK_PER_TRADE_GRID:
        result = run_portfolio_backtest(
            train_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=risk,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        train_results[risk] = result
    selected = max(
        RISK_PER_TRADE_GRID,
        key=lambda risk: (
            _first_float(train_results[risk].metrics.get("daily_sharpe")) or -999.0,
            -risk,
        ),
    )
    test_selected = run_portfolio_backtest(
        test_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        variant="fixed_20d",
        mode="path",
        price_paths=price_paths,
        sizing="risk_budget",
        risk_per_trade=selected,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    test_fixed = run_portfolio_backtest(
        test_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        variant="fixed_20d",
        mode="path",
        price_paths=price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    return {
        "status": "ready",
        "split_date": split_date,
        "selected_risk_per_trade": selected,
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "train_metrics_by_risk": {
            str(risk): train_results[risk].metrics for risk in RISK_PER_TRADE_GRID
        },
        "test_selected_metrics": test_selected.metrics,
        "test_fixed_20d_metrics": test_fixed.metrics,
    }


def _single_name_cap_sensitivity(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cap in SINGLE_NAME_CAP_GRID:
        result = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=0.005,
            single_name_cap=cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        rows.append(
            {
                "single_name_cap": None if cap >= 1.0 else cap,
                "diagnostic_no_cap": cap >= 1.0,
                "cumulative_return": result.metrics.get("cumulative_return"),
                "max_drawdown": result.metrics.get("max_drawdown"),
                "daily_sharpe": result.metrics.get("daily_sharpe"),
                "max_single_name_weight": result.metrics.get("max_single_name_weight"),
            }
        )
    return rows


def _hold_exit_portfolio_comparison(
    execution_rows: Sequence[Mapping[str, object]],
    simulations: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    sim_by_key = {
        (
            str(row.get("stock_code")),
            str(row.get("entry_date"))[:10],
            str(row.get("rule")),
        ): row
        for row in simulations
        if row.get("portfolio_applicable") and row.get("triggered") and not row.get("missing_exit")
    }
    out: list[dict[str, object]] = []
    base_specs = [
        ("fixed_20d", "equal_weight", None),
        ("risk_budget_0p005", "risk_budget", 0.005),
        ("risk_budget_0p010", "risk_budget", 0.010),
    ]
    rules = sorted({str(row.get("rule")) for row in simulations if row.get("portfolio_applicable")})
    for base_name, sizing, risk in base_specs:
        baseline = _run_exit_portfolio_variant(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            sizing=sizing,
            risk_per_trade=risk,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        out.append(_portfolio_comparison_row(base_name, "baseline", baseline, baseline))
        for rule in rules:
            modified = []
            for row in execution_rows:
                key = (str(row.get("stock_code")), str(row.get("entry_date"))[:10], rule)
                sim = sim_by_key.get(key)
                if sim is None:
                    modified.append(dict(row))
                    continue
                next_row = dict(row)
                next_row["return_20d_net_adj"] = sim.get("rule_return_net")
                next_row["exit_date_20d"] = sim.get("exit_date")
                modified.append(next_row)
            result = _run_exit_portfolio_variant(
                modified,
                market_state_rows,
                exposure_rows=exposure_rows,
                sizing=sizing,
                risk_per_trade=risk,
                initial_capital=initial_capital,
                max_positions=max_positions,
            )
            out.append(_portfolio_comparison_row(base_name, rule, result, baseline))
    return out


def _run_exit_portfolio_variant(
    rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    sizing: str,
    risk_per_trade: float | None,
    initial_capital: float,
    max_positions: int,
) -> PortfolioBacktestResult:
    kwargs: dict[str, object] = {
        "variant": "fixed_20d",
        "mode": "horizon",
        "exposure_rows": exposure_rows,
        "initial_capital": initial_capital,
        "max_positions": max_positions,
    }
    if sizing == "risk_budget":
        kwargs.update(
            {
                "sizing": "risk_budget",
                "risk_per_trade": risk_per_trade,
                "single_name_cap": POLICY.backtest_variants.risk_budget_single_name_cap,
                "fallback_stop_distance_pct": POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            }
        )
    return run_portfolio_backtest(rows, market_state_rows, **kwargs)


def _portfolio_comparison_row(
    base_name: str,
    rule: str,
    result: PortfolioBacktestResult,
    baseline: PortfolioBacktestResult,
) -> dict[str, object]:
    return {
        "base_variant": base_name,
        "rule": rule,
        "cumulative_return": result.metrics.get("cumulative_return"),
        "cagr": result.metrics.get("cagr"),
        "max_drawdown": result.metrics.get("max_drawdown"),
        "daily_sharpe": result.metrics.get("daily_sharpe"),
        "return_delta_vs_baseline": _round(
            (_first_float(result.metrics.get("cumulative_return")) or 0.0)
            - (_first_float(baseline.metrics.get("cumulative_return")) or 0.0)
        ),
        "max_drawdown_delta_vs_baseline": _round(
            (_first_float(result.metrics.get("max_drawdown")) or 0.0)
            - (_first_float(baseline.metrics.get("max_drawdown")) or 0.0)
        ),
    }


def _residual_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, str], list[float]] = defaultdict(list)
    for row in rows:
        residual = _first_float(row.get("residual_return_after_trigger"))
        if residual is not None and row.get("triggered"):
            grouped[(int(row["day"]), str(row["rule"]))].append(residual)
    return [
        {
            "day": day,
            "rule": rule,
            "sample_count": len(values),
            "avg_residual_return": _round(statistics.fmean(values)),
            "p10_residual_return": _round(_percentile(values, 0.10)),
        }
        for (day, rule), values in sorted(grouped.items())
    ]


def _exit_rule_summary(
    rows: Sequence[Mapping[str, object]],
    portfolio_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("rule"))].append(row)
    portfolio_by_rule = {
        (str(row.get("base_variant")), str(row.get("rule"))): row
        for row in portfolio_rows
    }
    out: list[dict[str, object]] = []
    for rule, rule_rows in sorted(grouped.items()):
        triggered = [row for row in rule_rows if row.get("triggered")]
        usable = [row for row in triggered if not row.get("missing_exit")]
        baseline_returns = [_first_float(row.get("baseline_return_net")) for row in usable]
        rule_returns = [_first_float(row.get("rule_return_net")) for row in usable]
        baseline_values = [value for value in baseline_returns if value is not None]
        rule_values = [value for value in rule_returns if value is not None]
        out.append(
            {
                "rule": rule,
                "sample_count": len(rule_rows),
                "trigger_count": len(triggered),
                "usable_trigger_count": len(usable),
                "missing_exit_count": len(triggered) - len(usable),
                "baseline_p5": _round(_percentile(baseline_values, 0.05)) if baseline_values else None,
                "rule_p5": _round(_percentile(rule_values, 0.05)) if rule_values else None,
                "baseline_p10": _round(_percentile(baseline_values, 0.10)) if baseline_values else None,
                "rule_p10": _round(_percentile(rule_values, 0.10)) if rule_values else None,
                "missed_rebound_cost": _round(
                    statistics.fmean(
                        _first_float(row.get("missed_rebound_cost")) or 0.0
                        for row in usable
                    )
                )
                if usable
                else None,
                "winner_damage": _round(
                    statistics.fmean(
                        _first_float(row.get("winner_damage")) or 0.0
                        for row in usable
                    )
                )
                if usable
                else None,
                "fixed_20d_return_delta": portfolio_by_rule.get(("fixed_20d", rule), {}).get("return_delta_vs_baseline"),
                "fixed_20d_mdd_delta": portfolio_by_rule.get(("fixed_20d", rule), {}).get("max_drawdown_delta_vs_baseline"),
                "risk_0p005_return_delta": portfolio_by_rule.get(("risk_budget_0p005", rule), {}).get("return_delta_vs_baseline"),
                "risk_0p005_mdd_delta": portfolio_by_rule.get(("risk_budget_0p005", rule), {}).get("max_drawdown_delta_vs_baseline"),
            }
        )
    return out


def _equity_exposure_coverage(
    variant: str,
    equity_curve: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    counts: dict[str, int] = defaultdict(int)
    missing_dates = []
    for row in equity_curve:
        basis = str(row.get("exposure_basis") or "unknown")
        counts[basis] += 1
        if basis != "per_date_actual":
            missing_dates.append(str(row.get("date") or "")[:10])
    total = len(equity_curve)
    fallback = total - counts.get("per_date_actual", 0)
    fallback_ratio = fallback / total if total else 1.0
    return {
        "variant": variant,
        "status": "ready" if total and fallback_ratio <= 0.10 else "blocked",
        "equity_curve_days": total,
        "per_date_actual_days": counts.get("per_date_actual", 0),
        "state_max_fallback_days": counts.get("state_max_fallback", 0),
        "other_fallback_days": fallback - counts.get("state_max_fallback", 0),
        "fallback_ratio": _round(fallback_ratio),
        "basis_counts": dict(sorted(counts.items())),
        "fallback_date_ranges": _date_ranges(missing_dates),
    }


def _adjustment_gap_sensitivity(
    clean_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    clean_price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    initial_capital: float,
    max_positions: int,
) -> dict[str, object]:
    if not clean_rows or not clean_price_paths:
        return {
            "status": "blocked",
            "reason": "No execution rows remain after excluding paths with missing adjustment factors.",
            "clean_execution_row_count": len(clean_rows),
            "clean_path_count": len(clean_price_paths),
        }
    fixed = run_portfolio_backtest(
        clean_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        variant="fixed_20d",
        mode="path",
        price_paths=clean_price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    risk = run_portfolio_backtest(
        clean_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        variant="fixed_20d",
        mode="path",
        price_paths=clean_price_paths,
        sizing="risk_budget",
        risk_per_trade=0.005,
        single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
        fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    fixed_return = _first_float(fixed.metrics.get("cumulative_return"))
    risk_return = _first_float(risk.metrics.get("cumulative_return"))
    fixed_mdd = _first_float(fixed.metrics.get("max_drawdown"))
    risk_mdd = _first_float(risk.metrics.get("max_drawdown"))
    return {
        "status": "ready",
        "clean_execution_row_count": len(clean_rows),
        "clean_path_count": len(clean_price_paths),
        "fixed_20d": fixed.metrics,
        "risk_budget_0p005": risk.metrics,
        "risk_0p005_return_delta": _round(risk_return - fixed_return)
        if fixed_return is not None and risk_return is not None
        else None,
        "risk_0p005_mdd_delta": _round(risk_mdd - fixed_mdd)
        if fixed_mdd is not None and risk_mdd is not None
        else None,
        "risk_0p005_still_beats_fixed_20d": bool(
            fixed_return is not None and risk_return is not None and risk_return > fixed_return
        ),
    }


def _cluster_bootstrap_by_period(
    fixed_result: PortfolioBacktestResult,
    risk_result: PortfolioBacktestResult,
    *,
    period: str,
    iterations: int = 300,
) -> dict[str, object]:
    fixed_returns = _returns_by_date(fixed_result.equity_curve)
    risk_returns = _returns_by_date(risk_result.equity_curve)
    dates = sorted(set(fixed_returns) & set(risk_returns))
    if not dates:
        return {"status": "blocked", "reason": "No paired daily returns."}
    grouped: dict[str, list[float]] = defaultdict(list)
    for date_key in dates:
        if period == "month":
            period_key = date_key[:7]
        elif period == "year":
            period_key = date_key[:4]
        else:
            return {"status": "blocked", "reason": f"Unsupported cluster period: {period}"}
        grouped[period_key].append(risk_returns[date_key] - fixed_returns[date_key])
    period_keys = sorted(grouped)
    if not period_keys:
        return {"status": "blocked", "reason": "No bootstrap clusters."}
    rng = random.Random(RANDOM_SEED + len(period_keys))
    samples = []
    for _ in range(iterations):
        compounded = 1.0
        for period_key in (rng.choice(period_keys) for _item in period_keys):
            for daily_increment in grouped[period_key]:
                compounded *= 1.0 + daily_increment
        samples.append(compounded - 1.0)
    return {
        "status": "ready",
        "period": period,
        "iterations": iterations,
        "date_count": len(dates),
        "cluster_count": len(period_keys),
        "mean_increment": _round(statistics.fmean(samples)),
        "p10_increment": _round(_percentile(samples, 0.10)),
        "p50_increment": _round(_percentile(samples, 0.50)),
        "p90_increment": _round(_percentile(samples, 0.90)),
    }


def _simulations_by_rule(
    simulations: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str, str], Mapping[str, object]]:
    out: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for row in simulations:
        if not row.get("portfolio_applicable") or not row.get("triggered") or row.get("missing_exit"):
            continue
        rule = str(row.get("rule") or "")
        stock_code = str(row.get("stock_code") or "").strip()
        entry_date = str(row.get("entry_date") or "")[:10]
        if rule and stock_code and entry_date:
            out[(rule, stock_code, entry_date)] = row
    return out


def _run_path_exit_portfolio_variant(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    sim_by_rule: Mapping[tuple[str, str, str], Mapping[str, object]],
    *,
    rule: str | None,
    sizing: str,
    risk_per_trade: float | None,
    initial_capital: float,
    max_positions: int,
) -> dict[str, object]:
    market_state_by_date = _market_state_by_date_simple(market_state_rows)
    exposure_by_date = _exposure_by_date_simple(exposure_rows)
    path_rows_by_key = {
        str(key): tuple(sorted(rows, key=lambda row: str(row.get("trade_date") or row.get("date") or "")[:10]))
        for key, rows in price_paths.items()
    }
    candidates_by_entry_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    trade_dates: set[str] = set(market_state_by_date)
    skip_counts: dict[str, int] = defaultdict(int)
    for row in execution_rows:
        stock_code = str(row.get("stock_code") or "").strip()
        entry_date = str(row.get("entry_date") or "")[:10]
        if not stock_code or not entry_date:
            skip_counts["missing_entry_key"] += 1
            continue
        key = position_path_key(stock_code, entry_date)
        path = path_rows_by_key.get(key, ())
        plan = _path_exit_plan(row, path, sim_by_rule, rule)
        if plan is None:
            skip_counts["missing_path_exit"] += 1
            continue
        candidate = dict(row)
        candidate["_path_key"] = key
        candidate["_path_rows"] = path
        candidate["_exit_plan"] = plan
        candidates_by_entry_date[entry_date].append(candidate)
        market_state_by_date.setdefault(entry_date, str(row.get("market_state") or "OFF"))
        trade_dates.add(entry_date)
        last_exit = max(str(leg["exit_date"])[:10] for leg in plan["legs"])
        trade_dates.add(last_exit)
        for path_row in path:
            date_key = str(path_row.get("trade_date") or path_row.get("date") or "")[:10]
            if entry_date <= date_key <= last_exit:
                trade_dates.add(date_key)
    for rows in candidates_by_entry_date.values():
        rows.sort(key=lambda item: (int(item.get("candidate_rank") or 999999), str(item.get("stock_code") or "")))

    cash = float(initial_capital)
    positions: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []
    exposure_actual_days = 0
    exposure_fallback_days = 0
    single_name_cap = POLICY.backtest_variants.risk_budget_single_name_cap
    fallback_stop = POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct
    risk_per_trade_value = risk_per_trade or POLICY.backtest_variants.risk_budget_risk_per_trade_grid[0]

    for trade_date in sorted(date for date in trade_dates if date):
        has_actual_exposure = trade_date in exposure_by_date
        if has_actual_exposure:
            exposure_actual_days += 1
        else:
            exposure_fallback_days += 1
        realized_pnl = 0.0

        day_start_equity = cash + _path_exit_invested_value(positions, trade_date)
        day_buy_notional = 0.0
        for candidate in candidates_by_entry_date.get(trade_date, []):
            if candidate.get("entry_executable") is False:
                skip_counts["entry_blocked"] += 1
                continue
            stock_code = str(candidate.get("stock_code") or "").strip()
            if _unique_open_stock_count(positions) >= max_positions:
                skip_counts["no_slot"] += 1
                continue
            if any(str(position.get("stock_code")) == stock_code for position in positions):
                skip_counts["duplicate_stock"] += 1
                continue
            state = str(candidate.get("market_state") or market_state_by_date.get(trade_date, "OFF"))
            exposure = _policy_exposure_for_date(
                trade_date,
                state=state,
                exposure_by_date=exposure_by_date,
            )
            if exposure <= 0:
                skip_counts["no_exposure"] += 1
                continue
            plan = candidate["_exit_plan"]
            entry_price = _first_float(plan.get("entry_price"))
            if entry_price is None or entry_price <= 0:
                skip_counts["missing_path_exit"] += 1
                continue
            stop_distance = None
            stop_ref_fallback = False
            exposure_cap_clipped = False
            if sizing == "risk_budget":
                stop_distance, stop_ref_fallback = _risk_stop_distance_for_row(
                    candidate,
                    entry_price=entry_price,
                    fallback_stop_distance_pct=fallback_stop,
                )
                raw_target_weight = min(risk_per_trade_value / stop_distance, single_name_cap)
                raw_target_amount = day_start_equity * raw_target_weight
                remaining_budget = max(day_start_equity * exposure - day_buy_notional, 0.0)
                if remaining_budget <= 1e-9:
                    skip_counts["exposure_cap_skip"] += 1
                    continue
                target_amount = min(raw_target_amount, remaining_budget)
                exposure_cap_clipped = target_amount + 1e-9 < raw_target_amount
            else:
                target_amount = day_start_equity * exposure / max_positions
            if target_amount <= 0:
                skip_counts["no_exposure"] += 1
                continue
            if cash + 1e-9 < target_amount:
                skip_counts["insufficient_cash"] += 1
                continue

            cash -= target_amount
            day_buy_notional += target_amount
            target_weight = target_amount / day_start_equity if day_start_equity > 0 else 0.0
            weighted_return = sum(
                float(leg["fraction"]) * float(leg["return_net"])
                for leg in plan["legs"]
            )
            trades.append(
                {
                    "date": trade_date,
                    "action": "buy",
                    "stock_code": stock_code,
                    "stock_name": candidate.get("stock_name"),
                    "signal_kind": candidate.get("signal_kind"),
                    "candidate_rank": candidate.get("candidate_rank"),
                    "market_state": state,
                    "amount": round(target_amount, 6),
                    "target_weight": round(target_weight, 6),
                    "exit_date": max(str(leg["exit_date"])[:10] for leg in plan["legs"]),
                    "expected_return_net": _round(weighted_return),
                    "daily_amount": candidate.get("daily_amount"),
                    "sizing": sizing,
                    "risk_per_trade": risk_per_trade_value if sizing == "risk_budget" else None,
                    "risk_budget_planned": _round(target_weight * stop_distance)
                    if stop_distance is not None
                    else None,
                    "stop_distance_pct": _round(stop_distance),
                    "exposure_cap_clipped": exposure_cap_clipped if sizing == "risk_budget" else None,
                    "stop_ref_fallback": stop_ref_fallback if sizing == "risk_budget" else None,
                }
            )
            for leg in plan["legs"]:
                leg_amount = target_amount * float(leg["fraction"])
                positions.append(
                    {
                        "base_rule": rule or "baseline",
                        "exit_stage": leg["exit_stage"],
                        "stock_code": stock_code,
                        "stock_name": candidate.get("stock_name"),
                        "signal_kind": candidate.get("signal_kind"),
                        "candidate_rank": candidate.get("candidate_rank"),
                        "market_state": state,
                        "entry_date": trade_date,
                        "planned_exit_date": plan["scheduled_exit_date"],
                        "exit_date": str(leg["exit_date"])[:10],
                        "entry_price": entry_price,
                        "exit_price": leg.get("exit_price"),
                        "return_net": float(leg["return_net"]),
                        "amount": leg_amount,
                        "target_weight": target_weight * float(leg["fraction"]),
                        "path_rows": candidate["_path_rows"],
                        "sizing": sizing,
                        "risk_per_trade": risk_per_trade_value if sizing == "risk_budget" else None,
                        "stop_distance_pct": stop_distance,
                        "rule": rule or "baseline",
                    }
                )

        remaining_positions = []
        for position in positions:
            if str(position["exit_date"])[:10] <= trade_date:
                proceeds = _path_exit_sell_proceeds(position)
                cash += proceeds
                realized_pnl += proceeds - float(position["amount"])
                sell_row = _path_exit_sell_trade(position, trade_date=trade_date, proceeds=proceeds)
                trades.append(sell_row)
                position_rows.append(sell_row)
            else:
                remaining_positions.append(position)
        positions = remaining_positions

        invested = _path_exit_invested_value(positions, trade_date)
        equity = cash + invested
        stock_values = _path_stock_values(positions, trade_date)
        max_single_name_weight = max((value / equity for value in stock_values.values()), default=0.0) if equity > 0 else 0.0
        date_state = market_state_by_date.get(trade_date, "OFF")
        equity_curve.append(
            {
                "date": trade_date,
                "net_value": round(equity, 6),
                "cash": round(cash, 6),
                "invested": round(invested, 6),
                "open_positions": _unique_open_stock_count(positions),
                "slot_utilization": round(_unique_open_stock_count(positions) / max_positions, 6),
                "market_state": date_state,
                "exposure": _round(
                    _policy_exposure_for_date(
                        trade_date,
                        state=date_state,
                        exposure_by_date=exposure_by_date,
                    )
                ),
                "exposure_basis": "per_date_actual" if has_actual_exposure else "state_max_fallback",
                "max_single_name_weight": round(max_single_name_weight, 6),
                "buy_notional": round(day_buy_notional, 6),
                "realized_pnl": round(realized_pnl, 6),
            }
        )

    metrics = summarize_equity_curve(
        equity_curve,
        initial_capital=initial_capital,
        max_positions=max_positions,
        trades=trades,
    )
    exposure_days = exposure_actual_days + exposure_fallback_days
    metrics.update(
        {
            "portfolio_engine_version": f"{PORTFOLIO_ENGINE_VERSION}+batch3_path_exit_report_v1",
            "mode": "path",
            "sizing": sizing,
            "risk_per_trade": risk_per_trade_value if sizing == "risk_budget" else None,
            "single_name_cap": single_name_cap if sizing == "risk_budget" else None,
            "rule": rule or "baseline",
            "exposure_actual_days": exposure_actual_days,
            "exposure_fallback_days": exposure_fallback_days,
            "exposure_fallback_day_ratio": _round(exposure_fallback_days / exposure_days)
            if exposure_days
            else 0.0,
        }
    )
    return {
        "metrics": metrics,
        "equity_curve": equity_curve,
        "trades": trades,
        "position_rows": position_rows,
        "skip_counts": dict(sorted(skip_counts.items())),
    }


def _path_exit_plan(
    source: Mapping[str, object],
    path: Sequence[Mapping[str, object]],
    sim_by_rule: Mapping[tuple[str, str, str], Mapping[str, object]],
    rule: str | None,
) -> dict[str, object] | None:
    if not path:
        return None
    stock_code = str(source.get("stock_code") or "").strip()
    entry_date = str(source.get("entry_date") or "")[:10]
    entry_price = path_entry_price(path[0], fallback=_first_float(source.get("entry_price")))
    if entry_price is None or entry_price <= 0:
        return None
    scheduled = calculate_path_horizon_exit(
        path,
        horizon_days=20,
        entry_price=entry_price,
        buy_cost_rate=POLICY.buy_cost_rate,
        sell_cost_rate=POLICY.sell_cost_rate,
        slippage_rate=POLICY.slippage_rate,
    )
    if scheduled is None:
        return None
    scheduled_leg = {
        "fraction": 1.0,
        "exit_stage": "scheduled_exit",
        "exit_date": str(scheduled["exit_date"])[:10],
        "exit_price": scheduled.get("exit_price"),
        "return_net": float(scheduled["return_net"]),
    }
    legs = [scheduled_leg]
    sim = sim_by_rule.get((str(rule), stock_code, entry_date)) if rule else None
    if sim is not None:
        action = str(sim.get("action") or "")
        trigger_return = _first_float(sim.get("trigger_exit_return_net"), sim.get("rule_return_net"))
        exit_date = str(sim.get("exit_date") or "")[:10]
        if action in {"exit", "reduce_half"} and trigger_return is not None and exit_date:
            trigger_leg = {
                "fraction": 0.5 if action == "reduce_half" else 1.0,
                "exit_stage": f"rule_{action}",
                "exit_date": exit_date,
                "exit_price": sim.get("exit_price"),
                "return_net": trigger_return,
            }
            if action == "reduce_half":
                legs = [trigger_leg, {**scheduled_leg, "fraction": 0.5}]
            else:
                legs = [trigger_leg]
    return {
        "entry_price": entry_price,
        "scheduled_exit_date": scheduled_leg["exit_date"],
        "scheduled_return_net": scheduled_leg["return_net"],
        "legs": legs,
    }


def _path_exit_comparison_row(
    base_name: str,
    rule: str,
    result: Mapping[str, object],
    baseline: Mapping[str, object],
) -> dict[str, object]:
    metrics = result.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    return {
        "base_variant": base_name,
        "rule": rule,
        "cumulative_return": metrics.get("cumulative_return"),
        "cagr": metrics.get("cagr"),
        "max_drawdown": metrics.get("max_drawdown"),
        "daily_sharpe": metrics.get("daily_sharpe"),
        "return_delta_vs_baseline": _round(
            (_first_float(metrics.get("cumulative_return")) or 0.0)
            - (_first_float(baseline_metrics.get("cumulative_return")) or 0.0)
        ),
        "max_drawdown_delta_vs_baseline": _round(
            (_first_float(metrics.get("max_drawdown")) or 0.0)
            - (_first_float(baseline_metrics.get("max_drawdown")) or 0.0)
        ),
        "exposure_fallback_day_ratio": metrics.get("exposure_fallback_day_ratio"),
    }


def _path_exit_rule_summary(
    portfolio_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_key = {
        (str(row.get("base_variant")), str(row.get("rule"))): row
        for row in portfolio_rows
    }
    rules = sorted(
        {
            str(row.get("rule"))
            for row in portfolio_rows
            if row.get("rule") and row.get("rule") != "baseline"
        }
    )
    out = []
    for rule in rules:
        fixed = by_key.get(("fixed_20d", rule), {})
        risk_005 = by_key.get(("risk_budget_0p005", rule), {})
        risk_010 = by_key.get(("risk_budget_0p010", rule), {})
        out.append(
            {
                "rule": rule,
                "fixed_20d_return_delta": fixed.get("return_delta_vs_baseline"),
                "fixed_20d_mdd_delta": fixed.get("max_drawdown_delta_vs_baseline"),
                "risk_0p005_return_delta": risk_005.get("return_delta_vs_baseline"),
                "risk_0p005_mdd_delta": risk_005.get("max_drawdown_delta_vs_baseline"),
                "risk_0p010_return_delta": risk_010.get("return_delta_vs_baseline"),
                "risk_0p010_mdd_delta": risk_010.get("max_drawdown_delta_vs_baseline"),
                "candidate_status": "research_only",
            }
        )
    return out


def _path_exit_candidate_rules(rule_rows: Sequence[Mapping[str, object]]) -> list[object]:
    return [
        row["rule"]
        for row in rule_rows
        if row.get("risk_0p005_return_delta") is not None
        and _gte(row.get("risk_0p005_return_delta"), 0)
        and _lte(row.get("risk_0p005_mdd_delta"), 0)
        and _gte(row.get("fixed_20d_return_delta"), 0)
        and _lte(row.get("fixed_20d_mdd_delta"), 0)
    ]


def _path_exit_data_gate_blockers(
    execution_rows: Sequence[Mapping[str, object]],
    price_path_adjustment: Mapping[str, object],
    portfolio_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    blockers = []
    baseline_fallback = [
        _first_float(row.get("exposure_fallback_day_ratio"))
        for row in portfolio_rows
        if row.get("rule") == "baseline"
    ]
    fallback_values = [value for value in baseline_fallback if value is not None]
    if fallback_values and max(fallback_values) > 0.10:
        blockers.append("path-mode baseline exposure fallback ratio remains above 10%")
    liquidity = _liquidity_readiness(execution_rows)
    if all(row["pass_count"] == 0 for row in liquidity["thresholds"]):
        blockers.append("liquidity thresholds have no passing known rows")
    missing_adj_ratio = _float_or_default(price_path_adjustment.get("missing_adjustment_factor_ratio"), 0.0)
    if missing_adj_ratio > 0:
        blockers.append("price paths still contain missing adjustment factors")
    return blockers


def _market_state_by_date_simple(rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        date_key = str(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date") or "")[:10]
        state = str(row.get("market_state") or row.get("state") or "").strip()
        if date_key and state:
            out[date_key] = state
    return out


def _exposure_by_date_simple(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows:
        date_key = str(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date") or "")[:10]
        exposure = _first_float(row.get("exposure"), row.get("market_gate_exposure"), row.get("value"))
        if date_key and exposure is not None:
            out[date_key] = min(max(exposure, 0.0), 1.0)
    return out


def _policy_exposure_for_date(
    date_key: str,
    *,
    state: str,
    exposure_by_date: Mapping[str, float],
) -> float:
    if date_key in exposure_by_date:
        return exposure_by_date[date_key]
    raw = POLICY.exposure_by_market_state.get(state or "OFF", 0.0)
    if isinstance(raw, (tuple, list)):
        values = [_first_float(value) for value in raw]
        exposure = max((value for value in values if value is not None), default=0.0)
    else:
        exposure = _first_float(raw) or 0.0
    return min(max(exposure, 0.0), 1.0)


def _risk_stop_distance_for_row(
    row: Mapping[str, object],
    *,
    entry_price: float,
    fallback_stop_distance_pct: float,
) -> tuple[float, bool]:
    ema10 = _first_float(row.get("ema10_signal"), row.get("ema10"))
    if entry_price <= 0 or ema10 is None:
        return fallback_stop_distance_pct, True
    stop_distance = (entry_price - ema10) / entry_price
    if stop_distance <= 0 or not math.isfinite(stop_distance):
        return fallback_stop_distance_pct, True
    return stop_distance, False


def _unique_open_stock_count(positions: Sequence[Mapping[str, object]]) -> int:
    return len({str(position.get("stock_code") or "") for position in positions if position.get("stock_code")})


def _path_exit_invested_value(
    positions: Sequence[Mapping[str, object]],
    trade_date: str,
) -> float:
    return sum(_path_exit_position_value(position, trade_date) for position in positions)


def _path_stock_values(
    positions: Sequence[Mapping[str, object]],
    trade_date: str,
) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for position in positions:
        out[str(position.get("stock_code") or "")] += _path_exit_position_value(position, trade_date)
    return dict(out)


def _path_exit_position_value(position: Mapping[str, object], trade_date: str) -> float:
    amount = _first_float(position.get("amount")) or 0.0
    entry_price = _first_float(position.get("entry_price"))
    path_rows = position.get("path_rows")
    if not isinstance(path_rows, Sequence) or entry_price is None or entry_price <= 0:
        return amount
    mark = _path_mark_on_or_before(path_rows, trade_date)
    if mark is None or mark <= 0:
        return amount
    return amount * mark / entry_price


def _path_mark_on_or_before(
    path: Sequence[Mapping[str, object]],
    trade_date: str,
) -> float | None:
    mark: float | None = None
    for row in path:
        date_key = str(row.get("trade_date") or row.get("date") or "")[:10]
        if not date_key or date_key > trade_date:
            break
        candidate = path_mark_price(row)
        if candidate is not None:
            mark = candidate
    return mark


def _path_exit_sell_proceeds(position: Mapping[str, object]) -> float:
    amount = _first_float(position.get("amount")) or 0.0
    entry_price = _first_float(position.get("entry_price"))
    exit_price = _first_float(position.get("exit_price"))
    if entry_price is not None and entry_price > 0 and exit_price is not None and exit_price > 0:
        return amount * (1.0 + _net_return(entry_price, exit_price))
    return amount * (1.0 + (_first_float(position.get("return_net")) or 0.0))


def _path_exit_sell_trade(
    position: Mapping[str, object],
    *,
    trade_date: str,
    proceeds: float,
) -> dict[str, object]:
    amount = _first_float(position.get("amount")) or 0.0
    return_net = proceeds / amount - 1.0 if amount > 0 else _first_float(position.get("return_net"))
    return {
        "date": trade_date,
        "action": "sell",
        "rule": position.get("rule"),
        "exit_stage": position.get("exit_stage"),
        "stock_code": position.get("stock_code"),
        "stock_name": position.get("stock_name"),
        "signal_kind": position.get("signal_kind"),
        "candidate_rank": position.get("candidate_rank"),
        "market_state": position.get("market_state"),
        "entry_date": position.get("entry_date"),
        "planned_exit_date": position.get("planned_exit_date"),
        "exit_date": position.get("exit_date"),
        "entry_price": _round(_first_float(position.get("entry_price"))),
        "exit_price": _round(_first_float(position.get("exit_price"))),
        "amount": round(proceeds, 6),
        "entry_amount": round(amount, 6),
        "target_weight": _round(_first_float(position.get("target_weight"))),
        "return_net": _round(return_net),
        "sizing": position.get("sizing"),
        "risk_per_trade": position.get("risk_per_trade"),
        "stop_distance_pct": _round(_first_float(position.get("stop_distance_pct"))),
    }


def _gate_exposure_source_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    tables = _table_names(conn)
    persisted = []
    for table in GATE_PERSISTED_TABLES:
        if table not in tables:
            persisted.append({"table": table, "exists": False, "status": "missing"})
            continue
        columns = _columns(conn, table)
        date_col = _first_present(columns, ("trade_date", "date", "snapshot_as_of_date", "as_of_date"))
        exposure_col = _first_present(columns, ("exposure", "market_gate_exposure", "value"))
        total_rows = conn.execute(f"select count(*) from {table}").fetchone()[0]
        if not date_col or not exposure_col:
            persisted.append(
                {
                    "table": table,
                    "exists": True,
                    "status": "missing_date_or_exposure_column",
                    "columns": sorted(columns),
                    "row_count": total_rows,
                }
            )
            continue
        row = conn.execute(
            f"""
            select count(*), min(cast({date_col} as date)), max(cast({date_col} as date))
            from {table}
            where cast({date_col} as date) >= cast(? as date)
              and cast({date_col} as date) <= cast(? as date)
              and {exposure_col} is not null
            """,
            [start_date, end_date],
        ).fetchone()
        persisted.append(
            {
                "table": table,
                "exists": True,
                "status": "usable_schema",
                "date_col": date_col,
                "exposure_col": exposure_col,
                "row_count": total_rows,
                "window_non_null_exposure_rows": row[0],
                "window_first_date": str(row[1])[:10] if row[1] else None,
                "window_last_date": str(row[2])[:10] if row[2] else None,
            }
        )
    candidate_history = _candidate_history_gate_evidence_diagnostics(
        conn,
        tables=tables,
        start_date=start_date,
        end_date=end_date,
    )
    replay = _gate_replay_source_diagnostics(
        conn,
        tables=tables,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "persisted_exposure_tables": persisted,
        "candidate_history_gate_evidence": candidate_history,
        "replay_sources": replay,
    }


def _candidate_history_gate_evidence_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    if "livermore_candidate_history" not in tables:
        return {"table": "livermore_candidate_history", "exists": False}
    columns = _columns(conn, "livermore_candidate_history")
    if not {"snapshot_as_of_date", "signal_evidence_json"}.issubset(columns):
        return {
            "table": "livermore_candidate_history",
            "exists": True,
            "status": "missing_required_columns",
            "columns": sorted(columns),
        }
    rows = conn.execute(
        """
        select snapshot_as_of_date, signal_evidence_json
        from livermore_candidate_history
        where signal_evidence_json is not null
          and cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        """,
        [start_date, end_date],
    ).fetchall()
    by_date: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for raw_date, raw_evidence in rows:
        evidence = _json_object(raw_evidence)
        exposure = _first_float(
            _nested(evidence, ("market_gate", "exposure")),
            evidence.get("market_gate_exposure"),
            evidence.get("exposure"),
        )
        if exposure is None:
            continue
        state = str(
            _nested(evidence, ("market_gate", "state"))
            or evidence.get("market_state")
            or evidence.get("state")
            or "UNKNOWN"
        )
        by_date[str(raw_date)[:10]].append((round(exposure, 10), state))
    consistent_dates = 0
    inconsistent_dates = []
    for date_key, values in sorted(by_date.items()):
        exposures = {item[0] for item in values}
        states = {item[1] for item in values}
        if len(exposures) == 1 and len(states) == 1:
            consistent_dates += 1
        else:
            inconsistent_dates.append(date_key)
    return {
        "table": "livermore_candidate_history",
        "exists": True,
        "raw_evidence_rows": len(rows),
        "dates_with_gate_evidence": len(by_date),
        "consistent_gate_dates": consistent_dates,
        "inconsistent_gate_dates": len(inconsistent_dates),
        "inconsistent_dates_sample": inconsistent_dates[:20],
    }


def _gate_replay_source_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    out = {}
    for table in ("choice_market_snapshot", "fact_choice_macro_daily", "fact_livermore_gate_supplement_daily"):
        if table not in tables:
            out[table] = {"exists": False}
            continue
        columns = _columns(conn, table)
        date_col = _first_present(columns, ("trade_date", "date"))
        if not date_col:
            out[table] = {"exists": True, "status": "missing_date_column", "columns": sorted(columns)}
            continue
        series_clause = "and series_id = 'CA.CSI300'" if "series_id" in columns else ""
        row = conn.execute(
            f"""
            select count(*), min(cast({date_col} as date)), max(cast({date_col} as date))
            from {table}
            where cast({date_col} as date) >= cast(? as date)
              and cast({date_col} as date) <= cast(? as date)
              {series_clause}
            """,
            [start_date, end_date],
        ).fetchone()
        out[table] = {
            "exists": True,
            "date_col": date_col,
            "columns": sorted(columns),
            "window_rows": row[0],
            "window_first_date": str(row[1])[:10] if row[1] else None,
            "window_last_date": str(row[2])[:10] if row[2] else None,
        }
        if table == "fact_livermore_gate_supplement_daily":
            out[table]["mapping_assessment"] = _gate_supplement_mapping_assessment(columns)
    return out


def _gate_trading_calendar_validation(
    conn: duckdb.DuckDBPyConnection,
    calendar: Mapping[str, object],
    *,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    missing_dates = sorted(
        {
            str(value)[:10]
            for value in calendar.get("missing_dates", [])
            if str(value or "").strip()
        }
    )
    if not missing_dates:
        missing_dates = _expand_date_ranges(calendar.get("missing_date_ranges", []))
    trading_days, sources = _benchmark_trading_day_sources(conn, start_date=start_date, end_date=end_date)
    if not trading_days:
        return {
            "status": "blocked",
            "calendar_source": "none",
            "reason": "No local benchmark trading-day source was available for validation.",
            "true_trading_day_missing_count": None,
            "true_trading_day_missing_ratio": None,
            "calendar_missing_not_trading_day_count": len(missing_dates),
            "trading_day_sources": sources,
        }
    true_missing = sorted(set(missing_dates) & trading_days)
    not_trading = sorted(set(missing_dates) - trading_days)
    weekend_count = sum(1 for value in not_trading if _is_weekend(value))
    weekday_non_trading_count = len(not_trading) - weekend_count
    classification = (
        "non_trading_dates_only"
        if not true_missing
        else "contains_true_trading_day_missing_dates"
    )
    return {
        "status": "ready",
        "calendar_source": "benchmark_derived_trading_days",
        "calendar_source_warning": (
            "Uses local CA.CSI300 benchmark observations as the A-share trading-day set; "
            "this validates strategy gate coverage but is not an independent exchange calendar."
        ),
        "classification": classification,
        "true_trading_day_total": len(trading_days),
        "true_trading_day_missing_count": len(true_missing),
        "true_trading_day_missing_ratio": _round(len(true_missing) / len(trading_days) if trading_days else None),
        "true_trading_day_missing_sample": true_missing[:25],
        "true_trading_day_missing_ranges": _date_ranges(true_missing),
        "calendar_missing_total": len(missing_dates),
        "calendar_missing_not_trading_day_count": len(not_trading),
        "calendar_missing_weekend_count": weekend_count,
        "calendar_missing_weekday_non_trading_count": weekday_non_trading_count,
        "calendar_missing_not_trading_day_ranges": _date_ranges(not_trading),
        "trading_day_sources": sources,
        "replayed_exposure_lineage": {
            "benchmark_series_id": "CA.CSI300",
            "gate_formula": "backend.app.core_finance.livermore_strategy.evaluate_market_gate",
            "exposure_formula": "passed_conditions / 4",
            "supplement_table": "fact_livermore_gate_supplement_daily",
            "source_tables": [source["table"] for source in sources if source.get("row_count")],
        },
    }


def _benchmark_trading_day_sources(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
) -> tuple[set[str], list[dict[str, object]]]:
    tables = _table_names(conn)
    trading_days: set[str] = set()
    sources: list[dict[str, object]] = []
    for table in ("fact_choice_macro_daily", "choice_market_snapshot"):
        if table not in tables:
            sources.append({"table": table, "exists": False})
            continue
        columns = _columns(conn, table)
        date_col = _first_present(columns, ("trade_date", "date"))
        value_col = _first_present(columns, ("value_numeric", "value", "close"))
        if not date_col or not value_col or "series_id" not in columns:
            sources.append(
                {
                    "table": table,
                    "exists": True,
                    "status": "missing_required_columns",
                    "columns": sorted(columns),
                }
            )
            continue
        optional_cols = [column for column in ("source_version", "vendor_version", "rule_version") if column in columns]
        select_cols = ", ".join([date_col, *optional_cols])
        rows = conn.execute(
            f"""
            select {select_cols}
            from {table}
            where series_id = 'CA.CSI300'
              and {value_col} is not null
              and cast({date_col} as date) >= cast(? as date)
              and cast({date_col} as date) <= cast(? as date)
            order by cast({date_col} as date)
            """,
            [start_date, end_date],
        ).fetchall()
        dates: list[str] = []
        version_counts: dict[str, dict[str, int]] = {column: defaultdict(int) for column in optional_cols}
        for raw in rows:
            date_key = str(raw[0])[:10]
            if not date_key:
                continue
            dates.append(date_key)
            trading_days.add(date_key)
            for index, column in enumerate(optional_cols, start=1):
                version_counts[column][str(raw[index] or "")] += 1
        sources.append(
            {
                "table": table,
                "exists": True,
                "status": "ready" if dates else "empty",
                "series_id": "CA.CSI300",
                "row_count": len(dates),
                "first_date": min(dates) if dates else None,
                "last_date": max(dates) if dates else None,
                "source_versions": _top_count_rows(version_counts.get("source_version", {})),
                "vendor_versions": _top_count_rows(version_counts.get("vendor_version", {})),
                "rule_versions": _top_count_rows(version_counts.get("rule_version", {})),
            }
        )
    return trading_days, sources


def _top_count_rows(counts: Mapping[str, int], *, limit: int = 5) -> list[dict[str, object]]:
    return [
        {"value": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _expand_date_ranges(ranges: object) -> list[str]:
    expanded: list[str] = []
    if not isinstance(ranges, Sequence) or isinstance(ranges, (str, bytes)):
        return expanded
    for item in ranges:
        if not isinstance(item, Mapping):
            continue
        start = _parse_date_key(item.get("start"))
        end = _parse_date_key(item.get("end"))
        if start is None or end is None or end < start:
            continue
        current = start
        while current <= end:
            expanded.append(current.isoformat())
            current += timedelta(days=1)
    return sorted(set(expanded))


def _parse_date_key(value: object) -> Date | None:
    try:
        return Date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _is_weekend(value: str) -> bool:
    parsed = _parse_date_key(value)
    return bool(parsed and parsed.weekday() >= 5)


def _gate_supplement_mapping_assessment(columns: set[str]) -> dict[str, object]:
    exposure_fields = _present_columns(
        columns,
        (
            "exposure",
            "market_gate_exposure",
            "gate_exposure",
            "target_exposure",
            "max_exposure",
            "position_exposure",
            "value",
        ),
    )
    state_fields = _present_columns(columns, ("market_state", "gate_state", "market_gate_state", "state", "risk_tier"))
    supplement_only_fields = _present_columns(
        columns,
        ("breadth_5d", "limit_up_quality_ok", "limit_up_count", "up_down_ratio", "risk_on_score"),
    )
    usable = bool(exposure_fields)
    if not usable:
        reason = (
            "supplement table has rows but lacks an explicit exposure field; it cannot be treated as "
            "persisted market_gate.exposure without replaying the benchmark/gate calculation"
        )
    elif not state_fields:
        reason = "explicit exposure field exists, but no gate state/risk tier field was found for state tie-out"
    else:
        reason = "explicit exposure and state-like fields are present; validate formula lineage before use"
    return {
        "usable_as_exposure_history": usable,
        "exposure_fields": exposure_fields,
        "state_fields": state_fields,
        "supplement_only_fields": supplement_only_fields,
        "reason": reason,
    }


def _present_columns(columns: set[str], names: Sequence[str]) -> list[str]:
    return [name for name in names if name in columns]


def _liquidity_implied_unit_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    execution_rows: Sequence[Mapping[str, object]],
    columns: set[str],
) -> dict[str, object]:
    if not {"trade_date", "stock_code", "amount", "volume", "close_value"}.issubset(columns):
        return {"status": "blocked", "reason": "choice observation table lacks amount/volume/close fields"}
    start_date, end_date = _execution_date_window(execution_rows)
    rows = conn.execute(
        f"""
        select amount, volume, close_value
        from {TABLE_OBS}
        where cast(trade_date as date) >= cast(? as date)
          and cast(trade_date as date) <= cast(? as date)
          and amount is not null
          and volume is not null
          and close_value is not null
        limit 20000
        """,
        [start_date, end_date],
    ).fetchall()
    ratios = []
    for amount, volume, close_value in rows:
        amount_value = _first_float(amount)
        volume_value = _first_float(volume)
        close = _first_float(close_value)
        if amount_value is not None and volume_value and close:
            ratios.append(amount_value / (volume_value * close))
    median_ratio = statistics.median(ratios) if ratios else None
    return {
        "status": "ready" if ratios else "blocked",
        "sample_count": len(ratios),
        "amount_over_volume_x_close_median": _round(median_ratio) if median_ratio is not None else None,
        "amount_over_volume_x_close_p10": _round(_percentile(ratios, 0.10)) if ratios else None,
        "amount_over_volume_x_close_p90": _round(_percentile(ratios, 0.90)) if ratios else None,
        "unit_hypothesis": _liquidity_unit_hypothesis(median_ratio),
        "interpretation": "Near 1 suggests amount in currency with volume in shares; near 100 suggests amount in currency with volume in lots; near 0.1 suggests a scaled amount field with lot-based volume. Vendor confirmation is still required.",
    }


def _liquidity_source_lineage_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    execution_rows: Sequence[Mapping[str, object]],
    columns: set[str],
) -> dict[str, object]:
    required = {"trade_date", "stock_code", "amount", "volume", "close_value"}
    if not required.issubset(columns):
        return {"status": "blocked", "reason": "choice observation table lacks daily OHLCV amount fields"}
    start_date, end_date = _execution_date_window(execution_rows)
    optional = [column for column in ("field_keys_json", "source_version", "vendor_version", "rule_version") if column in columns]
    if optional:
        select_cols = ", ".join(optional)
        rows = conn.execute(
            f"""
            select {select_cols}, count(*) as row_count
            from {TABLE_OBS}
            where cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
              and amount is not null
            group by {select_cols}
            order by row_count desc
            limit 20
            """,
            [start_date, end_date],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            select count(*) as row_count
            from {TABLE_OBS}
            where cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
              and amount is not null
            """,
            [start_date, end_date],
        ).fetchall()
    distributions: dict[str, dict[str, int]] = {column: defaultdict(int) for column in optional}
    row_count = 0
    for raw in rows:
        values = raw[:-1] if optional else ()
        count = int(raw[-1])
        row_count += count
        for column, value in zip(optional, values):
            distributions[column][str(value or "")] += count
    lineage = {
        "status": "ready" if row_count else "blocked",
        "source_table": TABLE_OBS,
        "field_mapping": "choice_stock_materialize maps upstream AMOUNT/VOLUME/CLOSE directly to amount/volume/close_value; Batch3 consumes amount as daily_amount.",
        "canonical_field_status": "daily_amount_rmb_unconfirmed",
        "row_count_with_amount": row_count,
        "source_versions": _top_count_rows(distributions.get("source_version", {})),
        "vendor_versions": _top_count_rows(distributions.get("vendor_version", {})),
        "rule_versions": _top_count_rows(distributions.get("rule_version", {})),
        "field_keys_json": _top_count_rows(distributions.get("field_keys_json", {})),
        "local_evidence_conclusion": (
            "Local lineage confirms pass-through storage, not the vendor unit. "
            "daily_amount_rmb must stay unconfirmed until vendor documentation or upstream metadata proves the conversion."
        ),
    }
    return lineage


def _liquidity_unit_hypothesis(ratio: float | None) -> str:
    if ratio is None:
        return "unclassified"
    if 0.05 <= ratio <= 0.20:
        return "consistent_with_scaled_amount_and_lot_volume"
    if 0.80 <= ratio <= 1.20:
        return "consistent_with_amount_rmb_and_share_volume"
    if 80.0 <= ratio <= 120.0:
        return "consistent_with_amount_rmb_and_lot_volume"
    return "unclassified"


def _liquidity_scaled_thresholds(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    values = [_first_float(row.get("daily_amount")) for row in rows]
    known_values = [value for value in values if value is not None]
    out = []
    for scale_name, multiplier in (("raw", 1.0), ("x1000", 1000.0), ("x10000", 10000.0)):
        scaled = [value * multiplier for value in known_values]
        for threshold in LIQUIDITY_THRESHOLDS:
            out.append(
                {
                    "scale": scale_name,
                    "multiplier": multiplier,
                    "threshold": threshold,
                    "pass_count": sum(1 for value in scaled if value >= threshold),
                    "fail_count": sum(1 for value in scaled if value < threshold),
                    "missing_count": len(rows) - len(known_values),
                }
            )
    return out


def _adjustment_gap_by_month(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    limit: int = 24,
) -> list[dict[str, object]]:
    counts: dict[str, int] = defaultdict(int)
    for rows in price_paths.values():
        for row in rows:
            if bool(row.get("adj_factor_missing")):
                date_key = str(row.get("trade_date") or "")[:10]
                if len(date_key) >= 7:
                    counts[date_key[:7]] += 1
    return [
        {"month": month, "missing_rows": count}
        for month, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _adjustment_gap_by_board(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    counts: dict[str, int] = defaultdict(int)
    for key, rows in price_paths.items():
        board = _board_for_stock_code(key.split("|", 1)[0])
        for row in rows:
            if bool(row.get("adj_factor_missing")):
                counts[board] += 1
    return [
        {"board": board, "missing_rows": count}
        for board, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _board_for_stock_code(stock_code: str) -> str:
    code = str(stock_code).split(".", 1)[0]
    suffix = str(stock_code).split(".")[-1] if "." in str(stock_code) else ""
    if code.startswith("688"):
        return "STAR"
    if code.startswith("300"):
        return "ChiNext"
    if code.startswith(("8", "4")) or suffix == "BJ":
        return "Beijing"
    if suffix == "SH":
        return "Shanghai_main"
    if suffix == "SZ":
        return "Shenzhen_main"
    return "UNKNOWN"


def _path_engine_tieout_rows(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    specs = [
        ("fixed_20d", "equal_weight", None, {}),
        (
            "risk_0p005",
            "risk_budget",
            0.005,
            {
                "sizing": "risk_budget",
                "risk_per_trade": 0.005,
                "single_name_cap": POLICY.backtest_variants.risk_budget_single_name_cap,
                "fallback_stop_distance_pct": POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            },
        ),
        (
            "risk_0p010",
            "risk_budget",
            0.010,
            {
                "sizing": "risk_budget",
                "risk_per_trade": 0.010,
                "single_name_cap": POLICY.backtest_variants.risk_budget_single_name_cap,
                "fallback_stop_distance_pct": POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            },
        ),
    ]
    rows = []
    for variant, sizing, risk_per_trade, engine_kwargs in specs:
        engine = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            initial_capital=initial_capital,
            max_positions=max_positions,
            **engine_kwargs,
        )
        report = _run_path_exit_portfolio_variant(
            execution_rows,
            market_state_rows,
            exposure_rows,
            price_paths,
            {},
            rule=None,
            sizing=sizing,
            risk_per_trade=risk_per_trade,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        report_metrics = report["metrics"]
        rows.append(
            {
                "variant": variant,
                "engine_cumulative_return": engine.metrics.get("cumulative_return"),
                "report_cumulative_return": report_metrics.get("cumulative_return"),
                "cumulative_return_delta": _round(
                    (_first_float(report_metrics.get("cumulative_return")) or 0.0)
                    - (_first_float(engine.metrics.get("cumulative_return")) or 0.0)
                ),
                "engine_max_drawdown": engine.metrics.get("max_drawdown"),
                "report_max_drawdown": report_metrics.get("max_drawdown"),
                "max_drawdown_delta": _round(
                    (_first_float(report_metrics.get("max_drawdown")) or 0.0)
                    - (_first_float(engine.metrics.get("max_drawdown")) or 0.0)
                ),
                "engine_daily_sharpe": engine.metrics.get("daily_sharpe"),
                "report_daily_sharpe": report_metrics.get("daily_sharpe"),
                "daily_sharpe_delta": _round(
                    (_first_float(report_metrics.get("daily_sharpe")) or 0.0)
                    - (_first_float(engine.metrics.get("daily_sharpe")) or 0.0)
                ),
            }
        )
    return rows


def _gate_fallback_split_decision(
    calendar: Mapping[str, object],
    trading: Mapping[str, object],
    validation: Mapping[str, object],
) -> dict[str, object]:
    trading_ratio = _float_or_default(trading.get("fallback_ratio"), 1.0)
    calendar_ratio = _float_or_default(calendar.get("fallback_ratio"), 1.0)
    true_missing = _first_float(validation.get("true_trading_day_missing_count"))
    blockers = []
    warnings = []
    if trading_ratio > 0:
        blockers.append("trading-day exposure fallback ratio is above 0")
    if validation.get("status") != "ready":
        blockers.append("trading-day calendar validation source is unavailable")
    elif true_missing is None or true_missing > 0:
        blockers.append("calendar fallback includes true trading days")
    if calendar_ratio > 0.10:
        warnings.append("calendar gate fallback remains high and is a data-pipeline coverage warning")
    return {
        "path_simulation_status": "blocked" if blockers else "ready",
        "calendar_pipeline_status": "research_only" if warnings else "ready",
        "calendar_gate_fallback_ratio": _round(calendar_ratio),
        "trading_day_exposure_fallback_ratio": _round(trading_ratio),
        "true_trading_day_missing_count": true_missing,
        "blockers": blockers,
        "warnings": warnings,
    }


def _read_csi300_backfill_report_summary(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "missing", "report_path": str(path)}
    text = path.read_text(encoding="utf-8")
    out: dict[str, object] = {"status": "present", "report_path": str(path)}
    for key in (
        "inserted_count",
        "conflict_count",
        "inserted_min_date",
        "inserted_max_date",
        "source_backup_duckdb_path",
        "source_table",
        "series_id",
    ):
        marker = f"- {key}:"
        for line in text.splitlines():
            if line.startswith(marker):
                out[key] = line.split(":", 1)[1].strip()
                break
    out["skipped_count"] = "not_reported; identical existing rows are skipped by insert-only-missing logic"
    return out


def _amount_like_source_columns(conn: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    patterns = ("amount", "turnover", "money", "成交额")
    rows = conn.execute(
        """
        select table_name, column_name
        from information_schema.columns
        where table_schema not in ('information_schema', 'pg_catalog')
        order by table_name, column_name
        """
    ).fetchall()
    out = []
    for table, column in rows:
        col_lower = str(column).lower()
        if not any(pattern in col_lower or pattern in str(column) for pattern in patterns):
            continue
        table_name = str(table)
        column_name = str(column)
        row_count: int | None = None
        non_null_count: int | None = None
        scan_status = "scanned"
        try:
            row_count = int(conn.execute(f"select count(*) from {_sql_ident(table_name)}").fetchone()[0])
            non_null_count = int(
                conn.execute(
                    f"select count(*) from {_sql_ident(table_name)} where {_sql_ident(column_name)} is not null"
                ).fetchone()[0]
            )
        except Exception as exc:  # pragma: no cover - defensive for views with unsupported scans.
            scan_status = f"scan_failed: {exc.__class__.__name__}"
        out.append(
            {
                "table": table_name,
                "column": column_name,
                "row_count": row_count,
                "non_null_count": non_null_count,
                "scan_status": scan_status,
                "priority": _amount_like_source_priority(table_name, column_name),
            }
        )
    return sorted(out, key=lambda row: (int(row["priority"]), str(row["table"]), str(row["column"])))


def _sql_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _amount_like_source_priority(table: str, column: str) -> int:
    table_lower = table.lower()
    column_lower = column.lower()
    if table_lower == TABLE_OBS and column_lower == "amount":
        return 0
    if table_lower == TABLE_OBS and column_lower in {"volume", "turnover"}:
        return 1
    if table_lower == TABLE_EXECUTION_HIST and column_lower in {"daily_amount", "amount"}:
        return 2
    if "stock" in table_lower or "choice" in table_lower or "livermore" in table_lower:
        return 10
    return 100


def _liquidity_canonical_scale_hypotheses(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    values = [_first_float(row.get("daily_amount")) for row in rows]
    known_values = [value for value in values if value is not None]
    out = []
    for scale_name, multiplier in LIQUIDITY_UNIT_MULTIPLIERS:
        scaled = [value * multiplier for value in known_values]
        if scaled:
            distribution = {
                "min": _round(min(scaled)),
                "median": _round(statistics.median(scaled)),
                "p90": _round(_percentile(scaled, 0.90)),
                "max": _round(max(scaled)),
            }
        else:
            distribution = {"min": None, "median": None, "p90": None, "max": None}
        for threshold in LIQUIDITY_CANONICAL_THRESHOLDS:
            out.append(
                {
                    "scale": scale_name,
                    "multiplier": multiplier,
                    "threshold_rmb": threshold,
                    "pass_count": sum(1 for value in scaled if value >= threshold),
                    "fail_count": sum(1 for value in scaled if value < threshold),
                    "unknown_count": len(rows) - len(known_values),
                    **distribution,
                }
            )
    return out


def _liquidity_trade_coverage(
    rows: Sequence[Mapping[str, object]],
    *,
    canonical_multiplier: float | None,
) -> dict[str, object]:
    values = [_first_float(row.get("daily_amount")) for row in rows]
    known = [value for value in values if value is not None]
    unknown_count = len(rows) - len(known)
    multiplier = canonical_multiplier or 1.0
    scaled = [value * multiplier for value in known]
    by_symbol: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0, "unknown": 0})
    by_date: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0, "unknown": 0})
    for row in rows:
        stock_code = str(row.get("stock_code") or "")
        date_key = str(row.get("entry_date") or row.get("signal_date") or "")[:10]
        amount = _first_float(row.get("daily_amount"))
        bucket = "unknown"
        if amount is not None:
            bucket = "pass" if amount * multiplier >= 20_000_000 else "fail"
        by_symbol[stock_code][bucket] += 1
        by_date[date_key][bucket] += 1
    top_illiquid = [
        {"stock_code": key, **counts}
        for key, counts in sorted(by_symbol.items(), key=lambda item: (-item[1]["fail"], item[0]))[:10]
    ]
    return {
        "total_trade_rows": len(rows),
        "pass_count_20m": sum(1 for value in scaled if value >= 20_000_000),
        "fail_count_20m": sum(1 for value in scaled if value < 20_000_000),
        "unknown_count": unknown_count,
        "unknown_ratio": _round(unknown_count / len(rows) if rows else 1.0),
        "by_symbol_top_illiquid": top_illiquid,
        "by_date_sample": [
            {"date": key, **counts}
            for key, counts in sorted(by_date.items())[:20]
        ],
    }


def _canonical_liquidity_status(
    lineage: Mapping[str, object],
    implied: Mapping[str, object],
) -> dict[str, object]:
    if lineage.get("canonical_field_status") != "daily_amount_rmb_confirmed":
        return {
            "status": "blocked",
            "reason": "lineage confirms pass-through only; vendor unit contract is missing",
            "multiplier": None,
            "unit_hypothesis": implied.get("unit_hypothesis"),
        }
    return {
        "status": "ready",
        "reason": "canonical field confirmed by lineage",
        "multiplier": 1.0,
        "unit_hypothesis": implied.get("unit_hypothesis"),
    }


def _adjustment_factor_source_inventory(conn: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        select table_name, column_name
        from information_schema.columns
        where table_schema not in ('information_schema', 'pg_catalog')
        order by table_name, column_name
        """
    ).fetchall()
    keywords = ("adj", "adjust", "factor", "复权")
    grouped: dict[str, list[str]] = defaultdict(list)
    for table, column in rows:
        haystack = f"{table}.{column}".lower()
        if any(keyword in haystack for keyword in keywords):
            grouped[str(table)].append(str(column))
    out = []
    for table, columns in sorted(grouped.items()):
        count = None
        try:
            count = conn.execute(f"select count(*) from {table}").fetchone()[0]
        except Exception:
            count = None
        out.append({"table": table, "columns": columns, "row_count": count})
    return out


def _sample_variant_metrics(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    initial_capital: float,
    max_positions: int,
) -> dict[str, object]:
    if not execution_rows:
        return {"status": "blocked", "reason": "no execution rows"}
    fixed = run_portfolio_backtest(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        variant="fixed_20d",
        mode="path",
        price_paths=price_paths,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    out = {"status": "ready", "fixed_20d": fixed.metrics}
    for risk in (0.003, 0.005, 0.0075, 0.010):
        result = run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variant="fixed_20d",
            mode="path",
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=risk,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        out[f"risk_budget_{_label(risk)}"] = result.metrics
    return out


def _adjustment_factor_blockers(missing_ratio: float, clean_subset_share: float | None) -> list[str]:
    blockers = []
    if missing_ratio > 0.02:
        blockers.append("adjustment factor missing ratio is above 2%")
    if clean_subset_share is None or clean_subset_share < 0.70:
        blockers.append("clean adjustment subset share is below 70%; promotion evidence would be sample-biased")
    return blockers


def _adjustment_repair_coverage(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    execution_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    missing_rows = [
        {"stock_code": key.split("|", 1)[0], "trade_date": str(row.get("trade_date") or "")[:10]}
        for key, rows in price_paths.items()
        for row in rows
        if bool(row.get("adj_factor_missing"))
    ]
    affected_symbols = sorted({row["stock_code"] for row in missing_rows})
    affected_dates = sorted({row["trade_date"] for row in missing_rows if row["trade_date"]})
    affected_trade_keys = {
        key
        for key, rows in price_paths.items()
        if any(bool(row.get("adj_factor_missing")) for row in rows)
    }
    total_path_rows = sum(len(rows) for rows in price_paths.values())
    return {
        "total_path_rows": total_path_rows,
        "missing_factor_rows": len(missing_rows),
        "missing_ratio": _round(len(missing_rows) / total_path_rows) if total_path_rows else 1.0,
        "affected_symbol_count": len(affected_symbols),
        "affected_symbols_sample": affected_symbols[:25],
        "affected_date_count": len(affected_dates),
        "affected_dates_sample": affected_dates[:25],
        "affected_trade_count": sum(
            1
            for row in execution_rows
            if position_path_key(row.get("stock_code"), row.get("entry_date")) in affected_trade_keys
        ),
    }


def _sample_instability(full_sample: Mapping[str, object], clean_sample: Mapping[str, object]) -> dict[str, object]:
    fixed_full = _nested(full_sample, ("fixed_20d", "cumulative_return"))
    fixed_clean = _nested(clean_sample, ("fixed_20d", "cumulative_return"))
    risk_full = _nested(full_sample, ("risk_budget_0p005", "cumulative_return"))
    risk_clean = _nested(clean_sample, ("risk_budget_0p005", "cumulative_return"))
    deltas = {
        "fixed_20d_cumulative_return_delta_clean_minus_full": _round(
            (_first_float(fixed_clean) or 0.0) - (_first_float(fixed_full) or 0.0)
        ),
        "risk_0p005_cumulative_return_delta_clean_minus_full": _round(
            (_first_float(risk_clean) or 0.0) - (_first_float(risk_full) or 0.0)
        ),
    }
    max_abs = max(abs(value or 0.0) for value in deltas.values())
    return {**deltas, "status": "unstable" if max_abs > 0.10 else "diagnostic"}


def _canonical_date(value: object) -> str:
    text = str(value or "")[:10]
    return text if text and text.lower() != "none" else ""


def _canonical_horizon_flags(trade_date: str, planned_exit_date: str) -> tuple[bool | None, bool]:
    if not trade_date or not planned_exit_date:
        return None, False
    beyond = trade_date > planned_exit_date
    return not beyond, beyond


def _canonical_amount_fields(
    *,
    raw_amount: object,
    raw_volume: object,
    raw_close: object,
    liquidity_payload: Mapping[str, Any],
) -> dict[str, object]:
    amount = _first_float(raw_amount)
    volume = _first_float(raw_volume)
    close = _first_float(raw_close)
    ratio = amount / (volume * close) if amount is not None and volume and close else None
    multiplier = _first_float(liquidity_payload.get("canonical_multiplier"))
    canonical_amount = None
    if liquidity_payload.get("canonical_status") == "ready" and amount is not None and multiplier is not None:
        canonical_amount = amount * multiplier
    return {
        "daily_amount_rmb_canonical": _round(canonical_amount),
        "raw_daily_amount": amount,
        "raw_volume": volume,
        "raw_close": close,
        "amount_volume_close_ratio": _round(ratio) if ratio is not None else None,
        "implied_amount_multiplier_diagnostic": (
            _liquidity_unit_hypothesis(ratio) if ratio is not None else "insufficient_raw_amount_volume_close"
        ),
    }


def _canonical_weight_fields(
    source: Mapping[str, object],
    *,
    gate_exposure: float | None,
    entry_price: float | None,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, object]:
    stop_distance = None
    stop_ref_fallback = None
    if entry_price is not None and entry_price > 0:
        stop_distance, stop_ref_fallback = _risk_stop_distance_for_row(
            source,
            entry_price=entry_price,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        )
    baseline_weight = None
    if gate_exposure is not None and max_positions > 0:
        baseline_weight = min(max(gate_exposure, 0.0), 1.0) / max_positions
    risk_weight_003 = _canonical_risk_weight(stop_distance, 0.003, gate_exposure)
    risk_weight_005 = _canonical_risk_weight(stop_distance, 0.005, gate_exposure)
    return {
        "stop_distance": _round(stop_distance),
        "stop_ref_fallback": stop_ref_fallback,
        "position_weight": _round(baseline_weight),
        "position_weight_basis": "fixed_20d_equal_weight_gate_exposure_estimate"
        if baseline_weight is not None
        else "missing_gate_exposure",
        "risk_budget_position_weight_0p003": _round(risk_weight_003),
        "risk_budget_position_weight_0p005": _round(risk_weight_005),
        "risk_budget_weight_basis": "risk_per_trade_over_stop_distance_capped_by_single_name_and_gate"
        if stop_distance is not None and gate_exposure is not None
        else "missing_stop_or_gate_exposure",
    }


def _canonical_risk_weight(stop_distance: float | None, risk_per_trade: float, gate_exposure: float | None) -> float | None:
    if stop_distance is None or stop_distance <= 0 or gate_exposure is None:
        return None
    raw_weight = risk_per_trade / stop_distance
    return min(raw_weight, POLICY.backtest_variants.risk_budget_single_name_cap, max(gate_exposure, 0.0))


def _append_flag(flags: list[str], name: str, condition: bool) -> None:
    if condition:
        flags.append(name)


def _canonical_path_rows(
    loaded: Mapping[str, Any],
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
) -> list[dict[str, object]]:
    exposure_by_date = _exposure_by_date_simple(loaded["exposure_rows"])
    market_state_by_date = _market_state_by_date_simple(loaded["market_state_rows"])
    canonical_status = str(liquidity_payload.get("canonical_status") or "blocked")
    rows = []
    for source in loaded["execution_rows"]:
        stock_code = str(source.get("stock_code") or "")
        entry_date = _canonical_date(source.get("entry_date"))
        planned_exit_date = _canonical_date(source.get("exit_date_20d"))
        key = position_path_key(stock_code, entry_date)
        for index, path_row in enumerate(loaded["price_paths"].get(key, [])):
            trade_date = _canonical_date(path_row.get("trade_date"))
            within_planned_horizon, beyond_planned_exit = _canonical_horizon_flags(trade_date, planned_exit_date)
            raw_close = path_row.get("close")
            amount_fields = _canonical_amount_fields(
                raw_amount=path_row.get("amount"),
                raw_volume=path_row.get("volume"),
                raw_close=raw_close,
                liquidity_payload=liquidity_payload,
            )
            gate_exposure = exposure_by_date.get(trade_date)
            entry_price = _first_float(source.get("entry_price"), path_entry_price(path_row, fallback=None))
            weight_fields = _canonical_weight_fields(source, gate_exposure=gate_exposure, entry_price=entry_price)
            incomplete_horizon = not planned_exit_date or source.get("return_20d_net_adj") is None
            flags = []
            _append_flag(flags, "adjustment_factor_missing", bool(path_row.get("adj_factor_missing")))
            _append_flag(flags, "liquidity_unit_unverified", canonical_status != "ready")
            _append_flag(flags, "gate_exposure_missing", gate_exposure is None)
            _append_flag(flags, "exposure_window_missing", gate_exposure is None)
            _append_flag(flags, "incomplete_horizon", incomplete_horizon)
            _append_flag(flags, "beyond_planned_exit", beyond_planned_exit)
            rows.append(
                {
                    "symbol": stock_code,
                    "trade_date": trade_date,
                    "entry_date": entry_date,
                    "planned_exit_date": planned_exit_date,
                    "actual_exit_date": planned_exit_date,
                    "within_planned_horizon": within_planned_horizon,
                    "beyond_planned_exit": beyond_planned_exit,
                    "exposure_window_missing": gate_exposure is None,
                    "incomplete_horizon": incomplete_horizon,
                    "path_day": index + 1,
                    "entry_price_adjusted": entry_price,
                    "next_tradable_open_adjusted": path_entry_price(path_row, fallback=None),
                    "close_adjusted_by_day_k": path_mark_price(path_row),
                    "raw_open": path_row.get("open"),
                    **amount_fields,
                    "adjustment_factor": path_row.get("adj_factor"),
                    "adjustment_factor_missing": bool(path_row.get("adj_factor_missing")),
                    "liquidity_status": canonical_status,
                    "gate_state": market_state_by_date.get(trade_date, source.get("market_state")),
                    "gate_exposure": gate_exposure,
                    "signal_kind": source.get("signal_kind"),
                    "volatility_regime": None,
                    "entry_premium": _entry_premium(source),
                    **weight_fields,
                    "cost_rate": POLICY.buy_cost_rate + POLICY.sell_cost_rate,
                    "slippage_rate": POLICY.slippage_rate,
                    "limit_up_down_availability": _limit_availability(path_row),
                    "data_quality_flags": ";".join(flags) if flags else "ok",
                }
            )
    return rows


def _canonical_trade_rows(
    loaded: Mapping[str, Any],
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> list[dict[str, object]]:
    exposure_by_date = _exposure_by_date_simple(loaded["exposure_rows"])
    canonical_status = str(liquidity_payload.get("canonical_status") or "blocked")
    rows = []
    for source in loaded["execution_rows"]:
        stock_code = str(source.get("stock_code") or "")
        entry_date = _canonical_date(source.get("entry_date"))
        planned_exit_date = _canonical_date(source.get("exit_date_20d"))
        flags = []
        _append_flag(flags, "liquidity_unit_unverified", canonical_status != "ready")
        key = position_path_key(stock_code, entry_date)
        path = loaded["price_paths"].get(key, [])
        _append_flag(flags, "adjustment_factor_missing", any(bool(row.get("adj_factor_missing")) for row in path))
        horizon_exit = calculate_path_horizon_exit(
            path,
            horizon_days=20,
            entry_price=_first_float(source.get("entry_price")),
            buy_cost_rate=POLICY.buy_cost_rate,
            sell_cost_rate=POLICY.sell_cost_rate,
            slippage_rate=POLICY.slippage_rate,
        )
        exit_price = _first_float(source.get("exit_price_20d"))
        exit_lineage = "source_execution_history"
        if exit_price is None and horizon_exit is not None:
            exit_price = _first_float(horizon_exit.get("exit_price"))
            exit_lineage = "computed_from_path_horizon_20d"
        return_net = _first_float(source.get("return_20d_net_adj"))
        return_lineage = "source_execution_history"
        if return_net is None and horizon_exit is not None:
            return_net = _first_float(horizon_exit.get("return_net"))
            return_lineage = "computed_from_path_horizon_20d"
        actual_exit_date = _canonical_date(source.get("exit_date_20d"))
        if horizon_exit is not None:
            actual_exit_date = _canonical_date(horizon_exit.get("exit_date")) or actual_exit_date
        gate_exposure = exposure_by_date.get(entry_date)
        entry_price = _first_float(source.get("entry_price"))
        amount_fields = _canonical_amount_fields(
            raw_amount=source.get("daily_amount"),
            raw_volume=source.get("volume"),
            raw_close=source.get("signal_close") or source.get("close") or source.get("close_value"),
            liquidity_payload=liquidity_payload,
        )
        weight_fields = _canonical_weight_fields(source, gate_exposure=gate_exposure, entry_price=entry_price)
        incomplete_horizon = not planned_exit_date or not actual_exit_date or return_net is None
        _append_flag(flags, "gate_exposure_missing", gate_exposure is None)
        _append_flag(flags, "incomplete_horizon", incomplete_horizon)
        rows.append(
            {
                "symbol": stock_code,
                "trade_date": _canonical_date(source.get("signal_date")) or entry_date,
                "entry_date": entry_date,
                "planned_exit_date": planned_exit_date,
                "actual_exit_date": actual_exit_date,
                "incomplete_horizon": incomplete_horizon,
                "entry_price_adjusted": entry_price,
                "exit_price_adjusted": exit_price,
                "exit_price_adjusted_lineage": exit_lineage if exit_price is not None else "missing",
                "return_20d_net_adj": _round(return_net),
                "return_20d_net_adj_lineage": return_lineage if return_net is not None else "missing",
                **amount_fields,
                "liquidity_status": canonical_status,
                "gate_state": source.get("market_state"),
                "gate_exposure": gate_exposure,
                "signal_kind": source.get("signal_kind"),
                "entry_premium": _entry_premium(source),
                **weight_fields,
                "cost_rate": POLICY.buy_cost_rate + POLICY.sell_cost_rate,
                "slippage_rate": POLICY.slippage_rate,
                "data_quality_flags": ";".join(flags) if flags else "ok",
            }
        )
    return rows


def _canonical_quality_summary_rows(
    loaded: Mapping[str, Any],
    path_rows: Sequence[Mapping[str, object]],
    trade_rows: Sequence[Mapping[str, object]],
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> list[dict[str, object]]:
    denominator_scope = _adjustment_denominator_scopes(loaded, canonical_path_rows=path_rows)
    rows: list[dict[str, object]] = [
        {"metric": "path_row_count", "value": len(path_rows), "status": "info"},
        {"metric": "trade_row_count", "value": len(trade_rows), "status": "info"},
        {
            "metric": "trading_day_exposure_fallback_ratio",
            "value": gate_payload.get("path_simulation_gate", {}).get("trading_day_exposure_fallback_ratio"),
            "status": gate_payload.get("path_simulation_gate", {}).get("path_simulation_status"),
        },
        {"metric": "liquidity_canonical_status", "value": liquidity_payload.get("canonical_status"), "status": liquidity_payload.get("status")},
        {
            "metric": "adjustment_factor_missing_ratio_reported",
            "value": adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio"),
            "status": adjustment_payload.get("status"),
        },
    ]
    for key, value in denominator_scope.items():
        rows.append({"metric": key, "value": value, "status": "info" if "ratio" not in key else adjustment_payload.get("status")})
    rows.extend(
        _canonical_required_field_summary(path_rows, scope="paths")
        + _canonical_required_field_summary(trade_rows, scope="trades")
    )
    return rows


def _canonical_dataset_quality_flags(
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    *,
    path_rows: Sequence[Mapping[str, object]] = (),
    trade_rows: Sequence[Mapping[str, object]] = (),
) -> list[str]:
    flags = []
    if _float_or_default(gate_payload.get("path_simulation_gate", {}).get("trading_day_exposure_fallback_ratio"), 1.0) > 0:
        flags.append("trading_day_gate_fallback")
    if liquidity_payload.get("canonical_status") != "ready":
        flags.append("liquidity_unit_unverified")
    if _float_or_default(adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio"), 1.0) > 0.02:
        flags.append("adjustment_factor_missing_gt_2pct")
    if path_rows and any(row.get("gate_exposure") is None for row in path_rows):
        flags.append("canonical_path_gate_exposure_null")
    if trade_rows and any(row.get("exit_price_adjusted") is None for row in trade_rows):
        flags.append("canonical_trade_exit_price_adjusted_null")
    return flags


def _canonical_required_field_summary(
    rows: Sequence[Mapping[str, object]],
    *,
    scope: str,
) -> list[dict[str, object]]:
    required_by_scope = {
        "paths": (
            "daily_amount_rmb_canonical",
            "gate_exposure",
            "position_weight",
            "stop_distance",
            "volatility_regime",
        ),
        "trades": (
            "daily_amount_rmb_canonical",
            "gate_exposure",
            "position_weight",
            "stop_distance",
            "exit_price_adjusted",
            "return_20d_net_adj",
        ),
    }
    out: list[dict[str, object]] = []
    total = len(rows)
    for field in required_by_scope.get(scope, ()):
        null_count = sum(1 for row in rows if row.get(field) is None or row.get(field) == "")
        null_ratio = null_count / total if total else 1.0
        status = "ready"
        if null_count:
            status = "blocked" if field in {"daily_amount_rmb_canonical", "gate_exposure", "exit_price_adjusted"} else "research_only"
        if field == "volatility_regime" and null_count:
            status = "not_supported"
        out.append(
            {
                "metric": f"{scope}_{field}_null_ratio",
                "value": _round(null_ratio),
                "status": status,
            }
        )
        out.append(
            {
                "metric": f"{scope}_{field}_null_count",
                "value": null_count,
                "status": status,
            }
        )
    return out


def _adjustment_denominator_scopes(
    loaded: Mapping[str, Any],
    *,
    canonical_path_rows: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    price_paths = loaded["price_paths"]
    engine_path_rows = sum(len(rows) for rows in price_paths.values())
    engine_missing_rows = sum(1 for rows in price_paths.values() for row in rows if bool(row.get("adj_factor_missing")))
    canonical_rows = list(canonical_path_rows) if canonical_path_rows is not None else [
        row
        for rows in price_paths.values()
        for row in rows
    ]
    within_rows = [
        row
        for row in canonical_rows
        if row.get("within_planned_horizon") is True
        or (
            canonical_path_rows is None
            and _canonical_date(row.get("trade_date"))
        )
    ]
    if canonical_path_rows is None:
        exit_by_key = {
            position_path_key(row.get("stock_code"), row.get("entry_date")): _canonical_date(row.get("exit_date_20d"))
            for row in loaded["execution_rows"]
        }
        within_rows = []
        for key, path in price_paths.items():
            planned_exit = exit_by_key.get(key, "")
            for row in path:
                trade_date = _canonical_date(row.get("trade_date"))
                within, _ = _canonical_horizon_flags(trade_date, planned_exit)
                if within is True:
                    within_rows.append(row)
    canonical_missing_rows = sum(1 for row in canonical_rows if bool(row.get("adjustment_factor_missing") or row.get("adj_factor_missing")))
    within_missing_rows = sum(1 for row in within_rows if bool(row.get("adjustment_factor_missing") or row.get("adj_factor_missing")))
    return {
        "engine_path_rows": engine_path_rows,
        "engine_missing_adjustment_factor_rows": engine_missing_rows,
        "engine_missing_adjustment_factor_ratio": _round(engine_missing_rows / engine_path_rows) if engine_path_rows else 1.0,
        "canonical_path_rows": len(canonical_rows),
        "canonical_missing_adjustment_factor_rows": canonical_missing_rows,
        "canonical_missing_adjustment_factor_ratio": _round(canonical_missing_rows / len(canonical_rows)) if canonical_rows else 1.0,
        "within_horizon_path_rows": len(within_rows),
        "within_horizon_missing_adjustment_factor_rows": within_missing_rows,
        "within_horizon_missing_adjustment_factor_ratio": _round(within_missing_rows / len(within_rows)) if within_rows else 1.0,
        "denominator_scope_note": (
            "engine_path_rows count raw loaded path rows; canonical_path_rows count emitted canonical path rows; "
            "within_horizon_path_rows excludes path rows beyond planned_exit_date."
        ),
    }


def _limit_availability(row: Mapping[str, object]) -> str:
    if bool(row.get("halted")) or str(row.get("tradestatus") or "").strip().lower() in {"0", "halt", "halted", "suspend", "suspended"}:
        return "halted_or_suspended"
    if bool(row.get("limit_up")):
        return "limit_up"
    if bool(row.get("limit_down")):
        return "limit_down"
    if path_entry_price(row, fallback=None) is None:
        return "missing_open"
    return "tradable"


def _risk_budget_optimization_rows(
    loaded: Mapping[str, Any],
    *,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    rows = []
    for risk in RISK_PER_TRADE_OPTIMIZATION_GRID:
        for cap in SINGLE_NAME_CAP_OPTIMIZATION_GRID:
            for exposure_cap in PORTFOLIO_EXPOSURE_CAP_GRID:
                diagnostic = risk >= 0.010 or cap > 0.20
                exposure_override = _portfolio_exposure_cap_override(loaded["exposure_rows"], exposure_cap)
                result = run_portfolio_backtest(
                    loaded["execution_rows"],
                    loaded["market_state_rows"],
                    exposure_rows=loaded["exposure_rows"],
                    exposure_by_date=exposure_override,
                    variant="fixed_20d",
                    mode="path",
                    price_paths=loaded["price_paths"],
                    sizing="risk_budget",
                    risk_per_trade=risk,
                    single_name_cap=cap,
                    fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
                    initial_capital=initial_capital,
                    max_positions=max_positions,
                )
                metrics = result.metrics
                max_weight = _first_float(metrics.get("max_single_name_weight")) or 0.0
                row = {
                    "risk_per_trade": risk,
                    "single_name_cap": cap,
                    "portfolio_exposure_cap": exposure_cap,
                    "grid_cell": f"risk={risk}|single_cap={cap}|downside_exposure_cap={exposure_cap}",
                    "grid_execution_status": "executed",
                    "portfolio_exposure_cap_semantics": "downside_clamp_existing_gate",
                    "diagnostic_only": diagnostic,
                    "cumulative_return": metrics.get("cumulative_return"),
                    "annualized_return": metrics.get("cagr"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "daily_sharpe": metrics.get("daily_sharpe"),
                    "sortino": _sortino(_daily_returns(result.equity_curve)),
                    "calmar": _calmar(metrics.get("cagr"), metrics.get("max_drawdown")),
                    "max_single_name_weight": metrics.get("max_single_name_weight"),
                    "turnover": metrics.get("annual_turnover"),
                    "robust_utility": _robust_utility(metrics, result.equity_curve, gate_payload, liquidity_payload, adjustment_payload),
                    "hard_fail": max_weight > 0.20,
                }
                rows.append(row)
    return sorted(rows, key=lambda item: (_first_float(item.get("robust_utility")) or -999.0), reverse=True)


def _portfolio_exposure_cap_override(
    exposure_rows: Sequence[Mapping[str, object]],
    exposure_cap: object,
) -> dict[str, float] | None:
    if exposure_cap == "existing_gate":
        return None
    cap = _first_float(exposure_cap)
    if cap is None:
        return None
    capped: dict[str, float] = {}
    for date_key, exposure in _exposure_by_date_simple(exposure_rows).items():
        capped[date_key] = min(max(exposure, 0.0), max(cap, 0.0), 1.0)
    return capped


def _robust_utility(
    metrics: Mapping[str, object],
    equity_curve: Sequence[Mapping[str, object]],
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> float | None:
    annualized = _first_float(metrics.get("cagr")) or 0.0
    max_dd = _first_float(metrics.get("max_drawdown")) or 0.0
    downside_vol = _downside_volatility(_daily_returns(equity_curve))
    max_weight = _first_float(metrics.get("max_single_name_weight")) or 0.0
    turnover = _first_float(metrics.get("annual_turnover")) or 0.0
    data_penalty = 0.0
    if _float_or_default(gate_payload.get("path_simulation_gate", {}).get("trading_day_exposure_fallback_ratio"), 1.0) > 0:
        data_penalty += 1.0
    if liquidity_payload.get("canonical_status") != "ready":
        data_penalty += 1.0
    if _float_or_default(adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio"), 1.0) > 0.02:
        data_penalty += 1.0
    score = (
        annualized
        - 1.5 * max_dd
        - 0.5 * downside_vol
        - 2.0 * max(max_weight - 0.15, 0.0)
        - 1.0 * min(turnover / 10.0, 1.0)
        - data_penalty
    )
    return _round(score)


def _downside_volatility(returns: Sequence[float]) -> float:
    downside = [min(value, 0.0) for value in returns]
    return _round(statistics.stdev(downside) * math.sqrt(252)) if len(downside) > 1 else 0.0


def _risk_budget_optimization_decision(
    rows: Sequence[Mapping[str, object]],
    *,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
    daily_bootstrap: Mapping[str, object],
    month_bootstrap: Mapping[str, object],
    walk_forward: Mapping[str, object],
) -> dict[str, object]:
    blockers = _data_quality_go_blockers(gate_payload, liquidity_payload, adjustment_payload)
    if _lt(daily_bootstrap.get("p10_increment"), 0):
        blockers.append("daily bootstrap p10 increment is below 0")
    if _lt(month_bootstrap.get("p10_increment"), 0):
        blockers.append("month-cluster bootstrap p10 increment is below 0")
    candidates = [
        row
        for row in rows
        if not row.get("diagnostic_only")
        and not row.get("hard_fail")
        and _lte(row.get("max_single_name_weight"), 0.20)
    ]
    best = candidates[0] if candidates else None
    conservative = next((row for row in candidates if _first_float(row.get("risk_per_trade")) == 0.003), None)
    return {
        "recommendation": "blocked" if blockers else "research_only",
        "candidate_list": [] if blockers else [best] if best else [],
        "best_research_candidate": best,
        "best_conservative_candidate": conservative,
        "selected_walk_forward_risk_per_trade": walk_forward.get("selected_risk_per_trade"),
        "blockers": sorted(set(blockers)),
        "risk_0p010_candidate_allowed": False,
    }


def _data_quality_go_blockers(
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> list[str]:
    blockers = []
    trading_ratio = gate_payload.get("path_simulation_gate", {}).get("trading_day_exposure_fallback_ratio")
    if trading_ratio is None:
        trading_ratio = gate_payload.get("trading_day_exposure", {}).get("fallback_ratio")
    if _float_or_default(trading_ratio, 1.0) > 0:
        blockers.append("trading-day gate fallback > 0")
    if liquidity_payload.get("canonical_status") != "ready":
        blockers.append("liquidity canonical RMB amount is not verified")
    missing_ratio = adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_ratio")
    if _float_or_default(missing_ratio, 1.0) > 0.02:
        blockers.append("adjustment factor missing ratio > 2%")
    return blockers


def _underwater_overlay_comparison_rows(
    loaded: Mapping[str, Any],
    simulations: Sequence[Mapping[str, object]],
    *,
    initial_capital: float,
    max_positions: int,
) -> list[dict[str, object]]:
    sim_by_rule = _simulations_by_rule(simulations)
    base_specs = [
        ("fixed_20d", "equal_weight", None, False),
        ("risk_budget_0p003", "risk_budget", 0.003, False),
        ("risk_budget_0p005", "risk_budget", 0.005, False),
        ("risk_budget_0p0075", "risk_budget", 0.0075, True),
        ("risk_budget_0p010", "risk_budget", 0.010, True),
    ]
    rules = [
        "day3_underwater_exit",
        "day3_underwater_reduce_half",
        "day5_underwater_exit",
        "day5_underwater_reduce_half",
        "day8_stagnation_exit",
        "day5_winner_gt5_diagnostic",
    ]
    rows = []
    for base_name, sizing, risk, diagnostic in base_specs:
        baseline = _run_path_exit_portfolio_variant(
            loaded["execution_rows"],
            loaded["market_state_rows"],
            loaded["exposure_rows"],
            loaded["price_paths"],
            sim_by_rule,
            rule=None,
            sizing=sizing,
            risk_per_trade=risk,
            initial_capital=initial_capital,
            max_positions=max_positions,
        )
        rows.append({**_path_exit_comparison_row(base_name, "baseline", baseline, baseline), "diagnostic_only": diagnostic})
        for rule in rules:
            result = _run_path_exit_portfolio_variant(
                loaded["execution_rows"],
                loaded["market_state_rows"],
                loaded["exposure_rows"],
                loaded["price_paths"],
                sim_by_rule,
                rule=rule,
                sizing=sizing,
                risk_per_trade=risk,
                initial_capital=initial_capital,
                max_positions=max_positions,
            )
            rows.append({**_path_exit_comparison_row(base_name, rule, result, baseline), "diagnostic_only": diagnostic or "diagnostic" in rule})
    return rows


def _underwater_rule_effect_rows(
    simulations: Sequence[Mapping[str, object]],
    comparison_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in simulations:
        grouped[str(row.get("rule"))].append(row)
    by_portfolio = {
        (str(row.get("base_variant")), str(row.get("rule"))): row
        for row in comparison_rows
    }
    out = []
    for rule, rows in sorted(grouped.items()):
        triggered = [row for row in rows if row.get("triggered")]
        usable = [row for row in triggered if not row.get("missing_exit")]
        p5_base = [_first_float(row.get("baseline_return_net")) for row in usable]
        p5_rule = [_first_float(row.get("rule_return_net")) for row in usable]
        base_values = [value for value in p5_base if value is not None]
        rule_values = [value for value in p5_rule if value is not None]
        fixed = by_portfolio.get(("fixed_20d", rule), {})
        risk003 = by_portfolio.get(("risk_budget_0p003", rule), {})
        risk005 = by_portfolio.get(("risk_budget_0p005", rule), {})
        improves_mdd = _lte(risk003.get("max_drawdown_delta_vs_baseline"), 0) and _lte(risk005.get("max_drawdown_delta_vs_baseline"), 0)
        nonworse_return = _gte(risk003.get("return_delta_vs_baseline"), 0) and _gte(risk005.get("return_delta_vs_baseline"), 0)
        status = "research_lead" if improves_mdd and nonworse_return else "research_only"
        out.append(
            {
                "rule": rule,
                "sample_count": len(rows),
                "trigger_count": len(triggered),
                "usable_trigger_count": len(usable),
                "missing_next_open_count": sum(1 for row in triggered if row.get("missing_reason") == "missing_next_open_price"),
                "p5_trade_return_improvement": _round(_percentile(rule_values, 0.05) - _percentile(base_values, 0.05)) if base_values and rule_values else None,
                "p10_trade_return_improvement": _round(_percentile(rule_values, 0.10) - _percentile(base_values, 0.10)) if base_values and rule_values else None,
                "missed_rebound_cost": _round(statistics.fmean((_first_float(row.get("missed_rebound_cost")) or 0.0) for row in usable)) if usable else None,
                "winner_damage": _round(statistics.fmean((_first_float(row.get("winner_damage")) or 0.0) for row in usable)) if usable else None,
                "fixed_20d_return_delta": fixed.get("return_delta_vs_baseline"),
                "fixed_20d_maxdd_delta": fixed.get("max_drawdown_delta_vs_baseline"),
                "risk_0p003_return_delta": risk003.get("return_delta_vs_baseline"),
                "risk_0p003_maxdd_delta": risk003.get("max_drawdown_delta_vs_baseline"),
                "risk_0p005_return_delta": risk005.get("return_delta_vs_baseline"),
                "risk_0p005_maxdd_delta": risk005.get("max_drawdown_delta_vs_baseline"),
                "candidate_status": status,
            }
        )
    return out


def _frozen_underwater_prior_diagnostics() -> list[dict[str, object]]:
    return [
        {
            "rule": "day5_underwater_exit",
            "source_report": str(DEFAULT_EXIT_PATH_REPORT),
            "status": "frozen_prior_research_lead",
            "promotion_evidence": False,
            "reason": "prior path-mode diagnostic lead; requires rerun after liquidity, adjustment, and A-share execution blockers clear",
        },
        {
            "rule": "day3_underwater_reduce_half",
            "source_report": str(DEFAULT_EXIT_PATH_REPORT),
            "status": "frozen_prior_research_lead",
            "promotion_evidence": False,
            "reason": "prior path-mode diagnostic lead; requires rerun after liquidity, adjustment, and A-share execution blockers clear",
        },
    ]


def _a_share_constraint_diagnostics(
    execution_rows: Sequence[Mapping[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    liquidity_payload: Mapping[str, Any],
) -> dict[str, object]:
    entry_halted = 0
    entry_missing_open = 0
    path_halted = 0
    path_limit_down = 0
    missing_open_rows = 0
    st_rows = 0
    for source in execution_rows:
        stock_name = str(source.get("stock_name") or "")
        if "ST" in stock_name.upper():
            st_rows += 1
        key = position_path_key(source.get("stock_code"), source.get("entry_date"))
        path = price_paths.get(key, [])
        if path:
            first = path[0]
            if bool(first.get("halted")) or str(first.get("tradestatus") or "").strip().lower() in {"0", "halt", "halted", "suspend", "suspended"}:
                entry_halted += 1
            if path_entry_price(first, fallback=None) is None:
                entry_missing_open += 1
        for row in path:
            if bool(row.get("halted")):
                path_halted += 1
            if bool(row.get("limit_down")):
                path_limit_down += 1
            if path_entry_price(row, fallback=None) is None:
                missing_open_rows += 1
    liquidity_ready = liquidity_payload.get("canonical_status") == "ready"
    incomplete_reasons = ["100-share board-lot sizing is not modeled"]
    if not liquidity_ready:
        incomplete_reasons.append("capacity estimate is blocked until canonical RMB liquidity amount is verified")
    if path_limit_down:
        incomplete_reasons.append("limit-down exit delay is not integrated into underwater overlay retests")
    if path_halted:
        incomplete_reasons.append("halted path rows require delayed execution handling")
    if missing_open_rows:
        incomplete_reasons.append("missing open path rows require delayed execution handling")
    if st_rows:
        incomplete_reasons.append("ST/special treatment constraints are not integrated")
    return {
        "execution_constraint_status": "research_only_incomplete" if incomplete_reasons else "research_only",
        "incomplete_reasons": incomplete_reasons,
        "t_plus_one_assessment": "Day 3/5/8 exits happen after entry date, so T+1 does not block these overlays in the current path logic.",
        "entry_halted_count": entry_halted,
        "entry_missing_open_count": entry_missing_open,
        "path_halted_count": path_halted,
        "path_limit_down_count": path_limit_down,
        "missing_open_path_rows": missing_open_rows,
        "st_or_special_treatment_trade_rows": st_rows,
        "board_lot_rule": "100-share lot sizing not modeled in current research engine; sizing remains notional-level diagnostic.",
        "cost_model": {
            "buy_cost_rate": POLICY.buy_cost_rate,
            "sell_cost_rate": POLICY.sell_cost_rate,
            "slippage_rate": POLICY.slippage_rate,
        },
        "capacity_status": "ready" if liquidity_ready else "blocked",
        "capacity_note": "Capacity estimate requires daily_amount_rmb_canonical; theoretical next-open exits are not guaranteed executions.",
    }


def _gate_exposure_readiness(conn: duckdb.DuckDBPyConnection, *, start_date: str, end_date: str) -> dict[str, object]:
    points = load_gate_exposure_by_date(conn, start_date, end_date)
    source_counts: dict[str, int] = defaultdict(int)
    missing_dates: list[str] = []
    for date_key, point in points.items():
        source_counts[point.source] += 1
        if point.source == "missing":
            missing_dates.append(date_key)
    total = len(points)
    persisted = sum(count for source, count in source_counts.items() if source.startswith("persisted:"))
    replayed = source_counts.get("replayed", 0)
    fallback = source_counts.get("missing", 0)
    return {
        "status": "ready" if total and fallback / total <= 0.10 else "blocked",
        "date_count": total,
        "persisted_rows": persisted,
        "replayed_rows": replayed,
        "fallback_rows": fallback,
        "fallback_ratio": _round(fallback / total if total else 1.0),
        "source_counts": dict(sorted(source_counts.items())),
        "missing_dates": missing_dates,
        "missing_dates_sample": missing_dates[:25],
        "missing_date_ranges": _date_ranges(missing_dates),
        "missing_dates_total": len(missing_dates),
    }


def _macro_history_readiness(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, object]:
    candidates = (
        "livermore_macro_context_history",
        "macro_composite_history",
        "fact_macro_composite_daily",
        "macro_environment_history",
    )
    checked = []
    for table in candidates:
        if table not in tables:
            checked.append({"table": table, "exists": False, "status": "missing"})
            continue
        columns = _columns(conn, table)
        date_col = _first_present(columns, ("trade_date", "date", "as_of_date", "snapshot_as_of_date"))
        status_col = _first_present(columns, ("macro_status", "status", "macro_state", "environment"))
        score_col = _first_present(columns, ("composite_score", "macro_score", "score"))
        row_count = conn.execute(f"select count(*) from {table}").fetchone()[0]
        ok = bool(date_col and (status_col or score_col) and row_count)
        checked.append(
            {
                "table": table,
                "exists": True,
                "status": "ready" if ok else "invalid_schema_or_empty",
                "date_col": date_col,
                "status_col": status_col,
                "score_col": score_col,
                "row_count": row_count,
            }
        )
        if ok:
            return {"status": "ready", "source_table": table, "checked": checked}
    return {"status": "blocked", "source_table": None, "checked": checked}


def _position_history_readiness(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, object]:
    if TABLE_POSITION_SNAPSHOT not in tables:
        return {
            "status": "blocked",
            "reason": f"{TABLE_POSITION_SNAPSHOT} missing",
            "sample_count": 0,
        }
    columns = _columns(conn, TABLE_POSITION_SNAPSHOT)
    date_col = _first_present(columns, ("snapshot_date", "trade_date", "date", "as_of_date"))
    stock_col = _first_present(columns, ("stock_code", "ts_code", "symbol"))
    state_col = _first_present(columns, ("market_state", "state"))
    if not date_col or not stock_col:
        return {"status": "blocked", "reason": "position snapshot lacks date or stock column", "sample_count": 0}
    state_select = state_col if state_col else "'UNKNOWN'"
    rows = conn.execute(
        f"""
        select {date_col}, {stock_col}, {state_select}
        from {TABLE_POSITION_SNAPSHOT}
        """
    ).fetchall()
    states: dict[str, int] = defaultdict(int)
    dates = []
    symbols = set()
    for raw_date, raw_symbol, raw_state in rows:
        dates.append(str(raw_date)[:10])
        symbols.add(str(raw_symbol))
        states[str(raw_state or "UNKNOWN")] += 1
    return {
        "status": "ready" if len(rows) >= 30 else "research_only",
        "sample_count": len(rows),
        "position_count": len(rows),
        "symbol_count": len(symbols),
        "snapshot_start": min(dates) if dates else None,
        "snapshot_end": max(dates) if dates else None,
        "market_state_counts": dict(sorted(states.items())),
        "overheat_sample_count": states.get("OVERHEAT", 0),
    }


def _price_path_readiness(price_paths: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, object]:
    total_rows = sum(len(rows) for rows in price_paths.values())
    missing_rows = _price_path_missing_adj_factor_rows(price_paths)
    affected = {
        f"{row.get('trade_date')}|{key.split('|', 1)[0]}"
        for key, rows in price_paths.items()
        for row in rows
        if bool(row.get("adj_factor_missing"))
    }
    return {
        "status": "ready" if total_rows and missing_rows == 0 else "research_only",
        "path_count": len(price_paths),
        "total_path_rows": total_rows,
        "missing_adjustment_factor_rows": missing_rows,
        "missing_adjustment_factor_ratio": _round(missing_rows / total_rows if total_rows else 1.0),
        "affected_symbol_date_count": len(affected),
        "top_missing_adjustment_factor_symbols": _top_missing_adjustment_factor_symbols(price_paths),
    }


def _liquidity_readiness(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    known = [_first_float(row.get("daily_amount")) for row in rows]
    known_values = [value for value in known if value is not None]
    threshold_rows = []
    for threshold in LIQUIDITY_THRESHOLDS:
        pass_count = sum(1 for value in known_values if value >= threshold)
        fail_count = sum(1 for value in known_values if value < threshold)
        missing_count = len(rows) - len(known_values)
        threshold_rows.append(
            {
                "threshold": threshold,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "missing_count": missing_count,
                "pass_ratio": _round(pass_count / len(rows) if rows else 0.0),
            }
        )
    return {
        "status": "ready" if known_values and any(row["pass_count"] > 0 for row in threshold_rows) else "blocked",
        "row_count": len(rows),
        "daily_amount_known_count": len(known_values),
        "daily_amount_missing_count": len(rows) - len(known_values),
        "daily_amount_coverage_ratio": _round(len(known_values) / len(rows) if rows else 0.0),
        "daily_amount_unit_assumption": "RMB from daily_amount; verify upstream field when all thresholds fail",
        "daily_amount_min": _round(min(known_values)) if known_values else None,
        "daily_amount_median": _round(statistics.median(known_values)) if known_values else None,
        "daily_amount_p90": _round(_percentile(known_values, 0.90)) if known_values else None,
        "daily_amount_max": _round(max(known_values)) if known_values else None,
        "thresholds": threshold_rows,
    }


def _hold_exit_rules() -> list[dict[str, object]]:
    return [
        {"name": "day3_underwater_exit", "day": 3, "action": "exit", "predicate": lambda value: value < -0.03},
        {"name": "day3_underwater_reduce_half", "day": 3, "action": "reduce_half", "predicate": lambda value: value < -0.03},
        {"name": "day5_underwater_exit", "day": 5, "action": "exit", "predicate": lambda value: value < -0.03},
        {"name": "day5_underwater_reduce_half", "day": 5, "action": "reduce_half", "predicate": lambda value: value < -0.03},
        {"name": "day8_stagnation_exit", "day": 8, "action": "exit", "predicate": lambda value: value < 0.0},
        {
            "name": "day5_no_progress_reduce_half",
            "day": 5,
            "action": "reduce_half",
            "predicate": lambda value: -0.03 <= value < 0.02,
        },
        {"name": "day8_stagnation_exit_lt2", "day": 8, "action": "exit", "predicate": lambda value: value < 0.02},
        {"name": "day8_stagnation_exit_lt0", "day": 8, "action": "exit", "predicate": lambda value: value < 0.0},
        {"name": "day5_winner_gt5_diagnostic", "day": 5, "action": "diagnostic", "predicate": lambda value: value > 0.05},
        {"name": "day8_winner_gt5_diagnostic", "day": 8, "action": "diagnostic", "predicate": lambda value: value > 0.05},
    ]


def _next_tradable_open(
    path: Sequence[Mapping[str, object]],
    start_index: int,
) -> Mapping[str, object] | None:
    for row in path[max(start_index, 0) :]:
        if bool(row.get("halted")) or str(row.get("tradestatus") or "").strip().lower() in {"0", "halt", "halted", "suspend", "suspended"}:
            continue
        if bool(row.get("limit_down")):
            continue
        return row
    return None


def _risk_budget_recommendation(
    variant_rows: Sequence[Mapping[str, object]],
    bootstrap: Mapping[str, object],
    walk_forward: Mapping[str, object],
) -> dict[str, object]:
    row_005 = _variant_row(variant_rows, "risk_budget_rpt_0p005")
    row_fixed = _variant_row(variant_rows, "fixed_20d_equal")
    criteria = {
        "fallback_ratio_below_10pct": _lt(row_005.get("fallback_exposure_ratio"), 0.10),
        "beats_fixed_20d": _gt(row_005.get("cumulative_return"), row_fixed.get("cumulative_return")),
        "max_drawdown_below_25pct": _lt(row_005.get("max_drawdown"), 0.25),
        "daily_sharpe_above_0p8": _gt(row_005.get("daily_sharpe"), 0.8),
        "max_single_name_weight_lte_20pct": _lte(row_005.get("max_single_name_weight"), 0.20),
        "liquidity_not_eliminating_all_trades": _gt(row_005.get("liquidity_200m_pass_count"), 0),
        "bootstrap_not_dominated_by_few_dates": _gt(bootstrap.get("p10_increment"), 0),
    }
    decision = "candidate_for_further_paper_trading" if all(criteria.values()) else "research_only"
    row_010 = _variant_row(variant_rows, "risk_budget_rpt_0p01")
    too_concentrated_010 = (
        _gt(row_010.get("max_single_name_weight"), 0.20)
        or _gte(row_010.get("max_drawdown"), 0.25)
    )
    return {
        "status": "ready" if decision == "candidate_for_further_paper_trading" else "research_only",
        "risk_budget_0p005": decision,
        "risk_budget_0p010_too_concentrated": too_concentrated_010,
        "criteria": criteria,
        "selected_walk_forward_risk_per_trade": walk_forward.get("selected_risk_per_trade"),
        "reason": "fallback/liquidity/robustness gates must all pass before paper trading.",
    }


def _hold_exit_recommendation(
    rule_rows: Sequence[Mapping[str, object]],
    portfolio_rows: Sequence[Mapping[str, object]],
    *,
    portfolio_engine_mode: str,
) -> dict[str, object]:
    position_candidates = []
    portfolio_rejections = []
    for row in rule_rows:
        rule = str(row.get("rule"))
        if "diagnostic" in rule:
            continue
        p10_base = _first_float(row.get("baseline_p10"))
        p10_rule = _first_float(row.get("rule_p10"))
        p5_base = _first_float(row.get("baseline_p5"))
        p5_rule = _first_float(row.get("rule_p5"))
        winner_damage = _first_float(row.get("winner_damage")) or 0.0
        if p10_base is None or p10_rule is None or p5_base is None or p5_rule is None:
            continue
        position_ok = p5_rule > p5_base and p10_rule > p10_base and winner_damage < 0.03
        portfolio_ok = (
            _gte(row.get("fixed_20d_return_delta"), 0)
            and _lte(row.get("fixed_20d_mdd_delta"), 0)
            and _gte(row.get("risk_0p005_return_delta"), 0)
            and _lte(row.get("risk_0p005_mdd_delta"), 0)
        )
        if position_ok:
            position_candidates.append(rule)
        if position_ok and not portfolio_ok:
            portfolio_rejections.append(rule)
    mode_consistent = portfolio_engine_mode == "path"
    candidates = position_candidates if mode_consistent and not portfolio_rejections else []
    decision = "candidate_for_further_paper_trading" if candidates else "research_only"
    return {
        "status": "research_only",
        "no_progress_exit": decision,
        "candidate_rules": candidates,
        "position_level_candidate_rules": position_candidates,
        "portfolio_rejected_rules": portfolio_rejections,
        "portfolio_engine_mode": portfolio_engine_mode,
        "mode_consistent_with_risk_report": mode_consistent,
        "reason": "paper-trading candidates require position-level left-tail improvement, controlled winner damage, non-worse portfolio return/drawdown, and path-mode consistency.",
    }


def _summary_blockers(*payloads: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    gate_calendar_validated = any(
        _first_float(payload.get("trading_calendar_validation", {}).get("true_trading_day_missing_count")) == 0
        and _lte(payload.get("trading_day_exposure", {}).get("fallback_ratio"), 0.10)
        for payload in payloads
    )
    for payload in payloads:
        payload_blockers = [str(item) for item in payload.get("blockers", []) if item]
        if gate_calendar_validated:
            payload_blockers = [
                blocker
                for blocker in payload_blockers
                if "gate exposure fallback ratio" not in blocker
                and "calendar-day gate exposure fallback ratio" not in blocker
            ]
        if payload.get("status") == "blocked" and payload.get("reason"):
            blockers.append(str(payload.get("reason") or "blocked report"))
        elif payload.get("status") == "blocked" and not payload_blockers:
            if not (
                gate_calendar_validated
                and (
                    "gate_exposure" in payload
                    or "calendar_day_exposure" in payload
                    or "trading_calendar_validation" in payload
                )
            ):
                blockers.append("blocked report")
        blockers.extend(payload_blockers)
        if (
            not gate_calendar_validated
            and payload.get("gate_exposure", {}).get("fallback_ratio", 0) > 0.10
            and not any(
                "gate exposure fallback ratio" in blocker for blocker in payload_blockers
            )
        ):
            blockers.append("gate exposure fallback ratio remains above 10%")
        if payload.get("macro_history", {}).get("status") == "blocked":
            blockers.append("macro composite history remains missing")
    return sorted(set(blockers))


def _post_data_fix_blockers(
    *,
    gate_payload: Mapping[str, Any],
    liquidity_payload: Mapping[str, Any],
    adjustment_payload: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    for payload in (gate_payload, liquidity_payload, adjustment_payload):
        if payload.get("status") == "blocked" and payload.get("reason"):
            blockers.append(str(payload.get("reason")))

    trading_ratio = _first_float(gate_payload.get("trading_day_exposure", {}).get("fallback_ratio"))
    validation = gate_payload.get("trading_calendar_validation", {})
    true_missing = _first_float(validation.get("true_trading_day_missing_count"))
    if validation:
        if validation.get("status") != "ready":
            blockers.append("gate calendar missing dates require trading-day validation")
        elif true_missing is None or true_missing > 0:
            blockers.append("true trading-day gate exposure missing count must be zero")
    else:
        calendar_ratio = _first_float(gate_payload.get("calendar_day_exposure", {}).get("fallback_ratio"))
        if calendar_ratio is None or calendar_ratio > 0.10:
            blockers.append("calendar-day gate exposure fallback ratio must be below 10% until trading-day validation exists")
    if trading_ratio is None or trading_ratio > 0.10:
        blockers.append("trading-day gate exposure fallback ratio must be below 10%")

    if liquidity_payload.get("unit_status") != "confirmed":
        blockers.append("daily_amount upstream unit remains unconfirmed")
    raw_thresholds = list(liquidity_payload.get("liquidity", {}).get("thresholds") or [])
    if raw_thresholds and all(row.get("pass_count") == 0 for row in raw_thresholds):
        blockers.append("raw liquidity thresholds still have zero passing rows")

    missing_adj_rows = _first_float(
        adjustment_payload.get("price_path_adjustment", {}).get("missing_adjustment_factor_rows")
    )
    if missing_adj_rows is None or missing_adj_rows > 0:
        blockers.append("adjustment factor gaps remain in price paths")
    clean_subset_share = _first_float(adjustment_payload.get("clean_subset_share"))
    if clean_subset_share is None or clean_subset_share < 0.80:
        blockers.append("clean adjustment subset share is below 80%")
    return sorted(set(blockers))


def _write_gate_fallback_split_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "calendar_day_exposure" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Gate Fallback Split Report", payload)
        return
    calendar = payload.get("calendar_day_exposure", {})
    trading = payload.get("trading_day_exposure", {})
    validation = payload.get("trading_calendar_validation", {})
    backfill = payload.get("backfill_summary", {})
    lines = [
        "# 2026-07 Batch 3 Gate Fallback Split Report",
        "",
        f"- status: {payload.get('status')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        f"- calendar_gate_fallback_ratio: {_fmt(calendar.get('fallback_ratio'))}",
        f"- trading_day_exposure_fallback_ratio: {_fmt(trading.get('fallback_ratio'))}",
        f"- true_trading_day_missing_count: {validation.get('true_trading_day_missing_count')}",
        f"- calendar_missing_classification: {validation.get('classification')}",
        "",
        "## Gate Conclusions",
        "",
        f"- path_simulation_gate: {payload.get('path_simulation_gate', {}).get('path_simulation_status')}",
        f"- calendar_pipeline_gate: {payload.get('calendar_pipeline_gate', {}).get('status')}",
        "- calendar fallback is a natural-date pipeline coverage diagnostic and must not be used as portfolio simulation fallback.",
        "- strategy go/no-go uses `trading_day_exposure_fallback_ratio` only.",
        "",
        "## Coverage",
        "",
        "| basis | total | persisted_or_actual | replayed | fallback | fallback_ratio |",
        "|---|---:|---:|---:|---:|---:|",
        f"| calendar natural days | {calendar.get('date_count')} | {calendar.get('persisted_rows')} | {calendar.get('replayed_rows')} | {calendar.get('fallback_rows')} | {_fmt(calendar.get('fallback_ratio'))} |",
        f"| portfolio trading days | {trading.get('equity_curve_days')} | {trading.get('per_date_actual_days')} | 0 | {trading.get('state_max_fallback_days')} | {_fmt(trading.get('fallback_ratio'))} |",
        "",
        "## CSI300 Benchmark Backfill",
        "",
        f"- source_table: {backfill.get('source_table')}",
        f"- series_id: {backfill.get('series_id')}",
        f"- inserted_count: {backfill.get('inserted_count')}",
        f"- skipped_count: {backfill.get('skipped_count')}",
        f"- conflict_count: {backfill.get('conflict_count')}",
        f"- inserted_min_date: {backfill.get('inserted_min_date')}",
        f"- inserted_max_date: {backfill.get('inserted_max_date')}",
        "",
        "## Fallback Dates",
        "",
        f"- calendar_missing_dates_total: {calendar.get('missing_dates_total')}",
        f"- calendar_missing_date_ranges: {json.dumps(calendar.get('missing_date_ranges', []), ensure_ascii=False)}",
        f"- trading_day_fallback_date_ranges: {json.dumps(trading.get('fallback_date_ranges', []), ensure_ascii=False)}",
        "",
        "## Blockers And Warnings",
        "",
    ]
    for blocker in payload.get("blockers", []):
        lines.append(f"- blocker: {blocker}")
    for warning in payload.get("warnings", []):
        lines.append(f"- warning: {warning}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_liquidity_canonical_rmb_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "raw_liquidity" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Liquidity Canonical RMB Report", payload)
        return
    coverage = payload.get("trade_coverage", {})
    lines = [
        "# 2026-07 Batch 3 Liquidity Canonical RMB Report",
        "",
        f"- status: {payload.get('status')}",
        f"- canonical_field: {payload.get('canonical_field')}",
        f"- canonical_status: {payload.get('canonical_status')}",
        f"- liquidity_blocked: {payload.get('liquidity_blocked')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        "",
        "## Canonical Evidence",
        "",
        f"- canonical_evidence: `{json.dumps(payload.get('canonical_evidence', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
        f"- implied_unit_diagnostics: `{json.dumps(payload.get('implied_unit_diagnostics', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
        f"- source_lineage: `{json.dumps(payload.get('source_lineage', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
        "",
        "## Amount-Like Sources",
        "",
        "| table | column | row_count | non_null_count | scan_status |",
        "|---|---|---:|---:|---|",
    ]
    for row in payload.get("amount_like_sources", [])[:80]:
        lines.append(
            f"| {row.get('table')} | {row.get('column')} | {row.get('row_count')} | {row.get('non_null_count')} | {row.get('scan_status')} |"
        )
    lines.extend(
        [
            "",
            "## Threshold Hypotheses",
            "",
            "| scale | multiplier | threshold_rmb | pass | fail | unknown | median | p90 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("scale_hypotheses", []):
        lines.append(
            f"| {row.get('scale')} | {_fmt(row.get('multiplier'))} | {_fmt(row.get('threshold_rmb'))} | {row.get('pass_count')} | {row.get('fail_count')} | {row.get('unknown_count')} | {_fmt(row.get('median'))} | {_fmt(row.get('p90'))} |"
        )
    lines.extend(
        [
            "",
            "## Trade Coverage At 20m RMB",
            "",
            f"- total_trade_rows: {coverage.get('total_trade_rows')}",
            f"- pass_count: {coverage.get('pass_count_20m')}",
            f"- fail_count: {coverage.get('fail_count_20m')}",
            f"- unknown_count: {coverage.get('unknown_count')}",
            f"- unknown_ratio: {_fmt(coverage.get('unknown_ratio'))}",
            "",
            "## Top Illiquid Contributors",
            "",
            "| stock_code | pass | fail | unknown |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in coverage.get("by_symbol_top_illiquid", []):
        lines.append(f"| {row.get('stock_code')} | {row.get('pass')} | {row.get('fail')} | {row.get('unknown')} |")
    lines.extend(["", "## Blockers", ""])
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.append("")
    lines.append("No strategy conclusion may be promoted while `daily_amount_rmb_canonical` is blocked.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_adjustment_factor_repair_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "price_path_adjustment" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Adjustment Factor Repair Report", payload)
        return
    coverage = payload.get("coverage", {})
    lines = [
        "# 2026-07 Batch 3 Adjustment Factor Repair Report",
        "",
        f"- status: {payload.get('status')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        f"- missing_factor_rows: {coverage.get('missing_factor_rows')}",
        f"- missing_ratio: {_fmt(coverage.get('missing_ratio'))}",
        f"- affected_symbol_count: {coverage.get('affected_symbol_count')}",
        f"- affected_date_count: {coverage.get('affected_date_count')}",
        f"- affected_trade_count: {coverage.get('affected_trade_count')}",
        f"- clean_subset_share: {_fmt(payload.get('clean_subset_share'))}",
        "",
        "## Source Inventory",
        "",
        "| table | row_count | columns |",
        "|---|---:|---|",
    ]
    for row in payload.get("source_inventory", []):
        lines.append(f"| {row.get('table')} | {row.get('row_count')} | {', '.join(row.get('columns', []))} |")
    denominator_scopes = payload.get("denominator_scopes", {})
    lines.extend(
        [
            "",
            "## Denominator Scopes",
            "",
            f"- denominator_scope_source: {payload.get('denominator_scope_source')}",
            f"- engine_path_rows: {denominator_scopes.get('engine_path_rows')}",
            f"- engine_missing_adjustment_factor_rows: {denominator_scopes.get('engine_missing_adjustment_factor_rows')}",
            f"- engine_missing_adjustment_factor_ratio: {_fmt(denominator_scopes.get('engine_missing_adjustment_factor_ratio'))}",
            f"- canonical_path_rows: {denominator_scopes.get('canonical_path_rows')}",
            f"- canonical_missing_adjustment_factor_rows: {denominator_scopes.get('canonical_missing_adjustment_factor_rows')}",
            f"- canonical_missing_adjustment_factor_ratio: {_fmt(denominator_scopes.get('canonical_missing_adjustment_factor_ratio'))}",
            f"- within_horizon_path_rows: {denominator_scopes.get('within_horizon_path_rows')}",
            f"- within_horizon_missing_adjustment_factor_rows: {denominator_scopes.get('within_horizon_missing_adjustment_factor_rows')}",
            f"- within_horizon_missing_adjustment_factor_ratio: {_fmt(denominator_scopes.get('within_horizon_missing_adjustment_factor_ratio'))}",
            f"- denominator_scope_note: {denominator_scopes.get('denominator_scope_note')}",
            "",
            "## Coverage Detail",
            "",
            f"- affected_symbols_sample: {json.dumps(coverage.get('affected_symbols_sample', []), ensure_ascii=False)}",
            f"- affected_dates_sample: {json.dumps(coverage.get('affected_dates_sample', []), ensure_ascii=False)}",
            f"- adj_factor_table_diagnostics: `{json.dumps(payload.get('adj_factor_table_diagnostics', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            "",
            "## Backtest Samples",
            "",
            f"- full_sample_current: `{json.dumps(payload.get('full_sample_current', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            f"- clean_adjustment_subset: `{json.dumps(payload.get('clean_adjustment_subset', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            f"- repaired_factor_sample: `{json.dumps(payload.get('repaired_factor_sample', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            f"- instability: `{json.dumps(payload.get('instability', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.append("")
    lines.append("No forward-fill, future adjusted-close reconstruction, or unofficial factor chain repair was applied.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_risk_budget_optimization_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "optimization_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Risk-Budget Optimization Report", payload)
        return
    decision = payload.get("decision", {})
    lines = [
        "# 2026-07 Batch 3 Risk-Budget Optimization Report",
        "",
        f"- status: {payload.get('status')}",
        f"- recommendation: {decision.get('recommendation')}",
        f"- selected_walk_forward_risk_per_trade: {decision.get('selected_walk_forward_risk_per_trade')}",
        f"- risk_0p010_candidate_allowed: {decision.get('risk_0p010_candidate_allowed')}",
        f"- grid_execution_status: {payload.get('grid_execution_status')}",
        f"- grid_skip_reason: {payload.get('grid_skip_reason')}",
        f"- portfolio_exposure_cap_semantics: {payload.get('portfolio_exposure_cap_semantics')}",
        f"- required_grid_cell_count: {payload.get('required_grid_cell_count')}",
        f"- required_risk_per_trade_grid: {payload.get('required_risk_per_trade_grid')}",
        f"- required_single_name_cap_grid: {payload.get('required_single_name_cap_grid')}",
        f"- required_portfolio_exposure_cap_grid: {payload.get('required_portfolio_exposure_cap_grid')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        "",
        "## Blockers",
        "",
    ]
    for blocker in decision.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "## Optimization Table",
            "",
            "| risk_per_trade | single_name_cap | portfolio_exposure_cap | diagnostic_only | cumulative_return | maxDD | Sharpe | max_weight | utility | hard_fail |",
            "|---:|---:|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload.get("optimization_rows", [])[:80]:
        lines.append(
            f"| {_fmt(row.get('risk_per_trade'))} | {_fmt(row.get('single_name_cap'))} | {row.get('portfolio_exposure_cap')} | {row.get('diagnostic_only')} | {_fmt(row.get('cumulative_return'))} | {_fmt(row.get('max_drawdown'))} | {_fmt(row.get('daily_sharpe'))} | {_fmt(row.get('max_single_name_weight'))} | {_fmt(row.get('robust_utility'))} | {row.get('hard_fail')} |"
        )
    lines.extend(
        [
            "",
            "## Bootstrap And Walk-Forward",
            "",
            f"- daily_bootstrap: `{json.dumps(payload.get('daily_bootstrap', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            f"- month_cluster_bootstrap: `{json.dumps(payload.get('month_cluster_bootstrap', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            f"- walk_forward: `{json.dumps(payload.get('walk_forward', {}), ensure_ascii=False, sort_keys=True, default=str)}`",
            "",
            "## Slices",
            "",
            "| slice_type | slice_value | rows | fixed_return | risk_0p005_return | increment |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("slices", [])[:80]:
        lines.append(
            f"| {row.get('slice_type')} | {row.get('slice_value')} | {row.get('row_count')} | {_fmt(row.get('fixed_20d_return'))} | {_fmt(row.get('risk_0p005_return'))} | {_fmt(row.get('increment'))} |"
        )
    lines.append("")
    lines.append("`risk_budget_0.010` is diagnostic only and is not allowed in the candidate list.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_underwater_overlay_optimization_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "rule_effect_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Underwater Exit Overlay Optimization Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Underwater Exit Overlay Optimization Report",
        "",
        f"- status: {payload.get('status')}",
        f"- priority_research_leads: {payload.get('priority_research_leads')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        f"- reason: {payload.get('reason')}",
        "",
        "## Blockers",
        "",
    ]
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "## Frozen Prior Diagnostic Reference",
            "",
            "| rule | source_report | status | promotion_evidence | reason |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload.get("frozen_prior_diagnostic_reference", []):
        lines.append(
            f"| {row.get('rule')} | {row.get('source_report')} | {row.get('status')} | {row.get('promotion_evidence')} | {row.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Rule Effects",
            "",
            "| rule | triggers | usable | missing_open | p5_improvement | p10_improvement | winner_damage | missed_rebound | risk003_ret_delta | risk005_ret_delta | status |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload.get("rule_effect_rows", []):
        lines.append(
            f"| {row.get('rule')} | {row.get('trigger_count')} | {row.get('usable_trigger_count')} | {row.get('missing_next_open_count')} | {_fmt(row.get('p5_trade_return_improvement'))} | {_fmt(row.get('p10_trade_return_improvement'))} | {_fmt(row.get('winner_damage'))} | {_fmt(row.get('missed_rebound_cost'))} | {_fmt(row.get('risk_0p003_return_delta'))} | {_fmt(row.get('risk_0p005_return_delta'))} | {row.get('candidate_status')} |"
        )
    lines.append("")
    lines.append("Missing next open is not replaced with future close; theoretical next-open exits are not guaranteed execution.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_a_share_trading_constraint_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "diagnostics" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 A-Share Trading Constraint Report", payload)
        return
    diagnostics = payload.get("diagnostics", {})
    lines = [
        "# 2026-07 Batch 3 A-Share Trading Constraint Report",
        "",
        f"- status: {payload.get('status')}",
        f"- live_strategy_changes: {payload.get('live_strategy_changes')}",
        f"- execution_constraint_status: {diagnostics.get('execution_constraint_status')}",
        f"- capacity_status: {diagnostics.get('capacity_status')}",
        f"- incomplete_reasons: {json.dumps(diagnostics.get('incomplete_reasons', []), ensure_ascii=False)}",
        "",
        "## Diagnostics",
        "",
        f"- t_plus_one_assessment: {diagnostics.get('t_plus_one_assessment')}",
        f"- entry_halted_count: {diagnostics.get('entry_halted_count')}",
        f"- entry_missing_open_count: {diagnostics.get('entry_missing_open_count')}",
        f"- path_halted_count: {diagnostics.get('path_halted_count')}",
        f"- path_limit_down_count: {diagnostics.get('path_limit_down_count')}",
        f"- missing_open_path_rows: {diagnostics.get('missing_open_path_rows')}",
        f"- st_or_special_treatment_trade_rows: {diagnostics.get('st_or_special_treatment_trade_rows')}",
        f"- board_lot_rule: {diagnostics.get('board_lot_rule')}",
        f"- cost_model: `{json.dumps(diagnostics.get('cost_model', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- capacity_note: {diagnostics.get('capacity_note')}",
        "",
        "## Blockers",
        "",
    ]
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.append("")
    lines.append("Theoretical next-open exits are not treated as guaranteed execution.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_a_share_optimization_summary(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# 2026-07 Batch 3 A-Share Optimization Summary",
        "",
        f"- status: {payload.get('status')}",
        f"- paper_trading: {payload.get('paper_trading')}",
        f"- live_strategy_change: {payload.get('live_strategy_change')}",
        f"- best_research_candidate: {payload.get('best_research_candidate')}",
        f"- best_conservative_candidate: {payload.get('best_conservative_candidate')}",
        f"- best_exit_overlay_lead: {payload.get('best_exit_overlay_lead')}",
        "",
        "## Data Readiness",
        "",
    ]
    for key, value in payload.get("data_readiness", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Strategy Ranking", ""])
    for row in payload.get("strategy_ranking", []):
        lines.append(f"- {row.get('variant')}: {row.get('status')} ({row.get('reason')})")
    lines.extend(["", "## Exact Blockers", ""])
    for blocker in payload.get("hard_blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "## Final recommendation:",
            "",
            f"- Live strategy change: {payload.get('live_strategy_change')}",
            f"- Paper trading: {payload.get('paper_trading')}",
            f"- Best research candidate: {payload.get('best_research_candidate')}",
            f"- Best conservative candidate: {payload.get('best_conservative_candidate')}",
            f"- Best exit overlay lead: {payload.get('best_exit_overlay_lead')}",
            f"- Hard blockers: {', '.join(payload.get('hard_blockers', []))}",
            f"- Next action: {payload.get('next_action')}",
            "",
            "No live candidate generation, live risk-exit trigger, confluence semantics, or live FORMULA_VERSION was changed.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_canonical_dataset_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_data_readiness_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "gate_exposure" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Data Readiness Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Data Readiness Report",
        "",
        f"- status: {payload['status']}",
        f"- db_path: {payload.get('db_path', 'NA')}",
        f"- signal_kind: {payload.get('signal_kind', 'NA')}",
        f"- execution_row_count: {payload.get('execution_row_count', 'NA')}",
        "",
        "## Gate Exposure",
        "",
        "| persisted_rows | replayed_rows | fallback_rows | fallback_ratio | missing_dates_total |",
        "|---:|---:|---:|---:|---:|",
    ]
    gate = payload.get("gate_exposure", {})
    lines.append(
        f"| {gate.get('persisted_rows')} | {gate.get('replayed_rows')} | {gate.get('fallback_rows')} | {_fmt(gate.get('fallback_ratio'))} | {gate.get('missing_dates_total')} |"
    )
    lines.extend(
        [
            "",
            f"- missing_dates_sample: {gate.get('missing_dates_sample', [])}",
            f"- missing_date_ranges: {gate.get('missing_date_ranges', [])}",
            "",
            "## Macro Composite History",
            "",
            f"- status: {payload.get('macro_history', {}).get('status')}",
            f"- source_table: {payload.get('macro_history', {}).get('source_table')}",
            "",
            "## Position Holding History",
            "",
        ]
    )
    pos = payload.get("position_history", {})
    lines.extend(
        [
            f"- status: {pos.get('status')}",
            f"- position_count: {pos.get('position_count', 0)}",
            f"- symbol_count: {pos.get('symbol_count', 0)}",
            f"- snapshot_range: {pos.get('snapshot_start')} to {pos.get('snapshot_end')}",
            f"- market_state_counts: {pos.get('market_state_counts', {})}",
            f"- OVERHEAT sample count: {pos.get('overheat_sample_count', 0)}",
            "",
            "## Price Path Adjustment Coverage",
            "",
        ]
    )
    price = payload.get("price_path_adjustment", {})
    lines.extend(
        [
            f"- total_path_rows: {price.get('total_path_rows')}",
            f"- missing_adjustment_factor_rows: {price.get('missing_adjustment_factor_rows')}",
            f"- missing_adjustment_factor_ratio: {_fmt(price.get('missing_adjustment_factor_ratio'))}",
            f"- affected_symbol_date_count: {price.get('affected_symbol_date_count')}",
            f"- top_missing_adjustment_factor_symbols: {price.get('top_missing_adjustment_factor_symbols', [])}",
            "",
            "## Liquidity Thresholds",
            "",
            f"- daily_amount_unit_assumption: {payload.get('liquidity', {}).get('daily_amount_unit_assumption')}",
            f"- daily_amount_min: {_fmt(payload.get('liquidity', {}).get('daily_amount_min'))}",
            f"- daily_amount_median: {_fmt(payload.get('liquidity', {}).get('daily_amount_median'))}",
            f"- daily_amount_p90: {_fmt(payload.get('liquidity', {}).get('daily_amount_p90'))}",
            f"- daily_amount_max: {_fmt(payload.get('liquidity', {}).get('daily_amount_max'))}",
            "",
            "| threshold_rmb | pass_count | fail_count | missing_count | pass_ratio |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("liquidity", {}).get("thresholds", []):
        lines.append(
            f"| {_fmt(row['threshold'])} | {row['pass_count']} | {row['fail_count']} | {row['missing_count']} | {_fmt(row['pass_ratio'])} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"- blockers: {payload.get('blockers', [])}",
            f"- research_flags: {payload.get('research_flags', [])}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_risk_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "variant_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Risk-Budget Robustness Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Risk-Budget Robustness Report",
        "",
        f"- status: {payload['status']}",
        f"- signal_kind: {payload.get('signal_kind')}",
        f"- execution_row_count: {payload.get('execution_row_count')}",
        f"- recommendation: {payload.get('recommendation', {}).get('risk_budget_0p005')}",
        "",
        "## Variant Metrics",
        "",
        "| variant | cumulative_return | cagr | max_drawdown | daily_sharpe | sortino | calmar | annual_turnover | avg_exposure | max_single_name_weight | avg_position_count | win_rate | avg_winner | avg_loser | fallback_exposure_ratio | missing_adjusted_path_ratio | liq_200m_pass | liq_200m_fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("variant_rows", []):
        lines.append(
            "| {variant} | {cum} | {cagr} | {mdd} | {sharpe} | {sortino} | {calmar} | {turnover} | {avg_exp} | {max_weight} | {avg_pos} | {win} | {winner} | {loser} | {fallback} | {missing_adj} | {pass200} | {fail200} |".format(
                variant=row["variant"],
                cum=_fmt(row.get("cumulative_return")),
                cagr=_fmt(row.get("cagr")),
                mdd=_fmt(row.get("max_drawdown")),
                sharpe=_fmt(row.get("daily_sharpe")),
                sortino=_fmt(row.get("sortino")),
                calmar=_fmt(row.get("calmar")),
                turnover=_fmt(row.get("annual_turnover")),
                avg_exp=_fmt(row.get("average_exposure")),
                max_weight=_fmt(row.get("max_single_name_weight")),
                avg_pos=_fmt(row.get("average_position_count")),
                win=_fmt(row.get("win_rate")),
                winner=_fmt(row.get("average_winner")),
                loser=_fmt(row.get("average_loser")),
                fallback=_fmt(row.get("fallback_exposure_ratio")),
                missing_adj=_fmt(row.get("missing_adjusted_path_ratio")),
                pass200=row.get("liquidity_200m_pass_count"),
                fail200=row.get("liquidity_200m_fail_count"),
            )
        )
    lines.extend(
        [
            "",
            "## Bootstrap By Trade Date",
            "",
            json.dumps(payload.get("bootstrap_by_date", {}), ensure_ascii=False, sort_keys=True),
            "",
            "## Walk Forward",
            "",
            json.dumps(payload.get("walk_forward", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "## Single-Name Cap Sensitivity",
            "",
            "| single_name_cap | diagnostic_no_cap | cumulative_return | max_drawdown | daily_sharpe | max_single_name_weight |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("single_name_cap_sensitivity", []):
        lines.append(
            f"| {_fmt(row.get('single_name_cap'))} | {row.get('diagnostic_no_cap')} | {_fmt(row.get('cumulative_return'))} | {_fmt(row.get('max_drawdown'))} | {_fmt(row.get('daily_sharpe'))} | {_fmt(row.get('max_single_name_weight'))} |"
        )
    lines.extend(
        [
            "",
            "## Slices",
            "",
            "| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | risk_0p005_max_drawdown | risk_0p005_sharpe |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("slices", [])[:200]:
        lines.append(
            f"| {row['slice_type']} | {row['slice_value']} | {row['row_count']} | {_fmt(row.get('fixed_20d_return'))} | {_fmt(row.get('risk_0p005_return'))} | {_fmt(row.get('increment'))} | {_fmt(row.get('risk_0p005_max_drawdown'))} | {_fmt(row.get('risk_0p005_sharpe'))} |"
        )
    lines.extend(
        [
            "",
            "## Top Contributions",
            "",
            json.dumps(payload.get("top_contributions", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "## Recommendation",
            "",
            json.dumps(payload.get("recommendation", {}), ensure_ascii=False, sort_keys=True),
            "",
            "## Output CSV",
            "",
        ]
    )
    for name, csv_path in payload.get("csv_paths", {}).items():
        lines.append(f"- {name}: {csv_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_exit_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "rule_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Hold-Progress Exit Simulation Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Hold-Progress Exit Simulation Report",
        "",
        f"- status: {payload['status']}",
        f"- signal_kind: {payload.get('signal_kind')}",
        f"- evaluated_position_rule_rows: {payload.get('evaluated_position_rule_rows')}",
        f"- recommendation: {payload.get('recommendation', {}).get('no_progress_exit')}",
        f"- portfolio_engine_mode: {payload.get('portfolio_engine_mode')}",
        f"- portfolio_comparison_scope: {payload.get('portfolio_comparison_scope')}",
        f"- position_level_csv: {payload.get('position_level_csv')}",
        f"- portfolio_level_csv: {payload.get('portfolio_level_csv')}",
        "",
        "Portfolio comparison below is diagnostic-only when `portfolio_engine_mode` is `horizon_diagnostic`; it is not comparable to the path-mode risk-budget robustness baseline.",
        "",
        "## Rule Summary",
        "",
        "| rule | sample_count | trigger_count | usable_trigger_count | missing_exit_count | baseline_p5 | rule_p5 | baseline_p10 | rule_p10 | missed_rebound_cost | winner_damage | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("rule_rows", []):
        lines.append(
            "| {rule} | {samples} | {triggers} | {usable} | {missing} | {bp5} | {rp5} | {bp10} | {rp10} | {missed} | {winner} | {fixed_delta} | {fixed_mdd_delta} | {risk_delta} | {risk_mdd_delta} |".format(
                rule=row["rule"],
                samples=row["sample_count"],
                triggers=row["trigger_count"],
                usable=row["usable_trigger_count"],
                missing=row["missing_exit_count"],
                bp5=_fmt(row.get("baseline_p5")),
                rp5=_fmt(row.get("rule_p5")),
                bp10=_fmt(row.get("baseline_p10")),
                rp10=_fmt(row.get("rule_p10")),
                missed=_fmt(row.get("missed_rebound_cost")),
                winner=_fmt(row.get("winner_damage")),
                fixed_delta=_fmt(row.get("fixed_20d_return_delta")),
                fixed_mdd_delta=_fmt(row.get("fixed_20d_mdd_delta")),
                risk_delta=_fmt(row.get("risk_0p005_return_delta")),
                risk_mdd_delta=_fmt(row.get("risk_0p005_mdd_delta")),
            )
        )
    lines.extend(
        [
            "",
            "## Forward Residual Return",
            "",
            "| day | rule | sample_count | avg_residual_return | p10_residual_return |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for row in payload.get("residual_rows", []):
        lines.append(
            f"| {row['day']} | {row['rule']} | {row['sample_count']} | {_fmt(row.get('avg_residual_return'))} | {_fmt(row.get('p10_residual_return'))} |"
        )
    lines.extend(
        [
            "",
            "## Portfolio Comparison",
            "",
            "| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("portfolio_rows", []):
        lines.append(
            f"| {row['base_variant']} | {row['rule']} | {_fmt(row.get('cumulative_return'))} | {_fmt(row.get('cagr'))} | {_fmt(row.get('max_drawdown'))} | {_fmt(row.get('daily_sharpe'))} | {_fmt(row.get('return_delta_vs_baseline'))} | {_fmt(row.get('max_drawdown_delta_vs_baseline'))} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            json.dumps(payload.get("recommendation", {}), ensure_ascii=False, sort_keys=True),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_entry_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "interaction_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Entry Premium Interaction Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Entry Premium Interaction Report",
        "",
        f"- status: {payload['status']}",
        f"- conclusion: {payload.get('conclusion')}",
        "",
        "| group_type | group_value | entry_premium_bucket | sample_count | avg_return_20d | win_rate | p10_return_20d |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload.get("interaction_rows", []):
        lines.append(
            f"| {row['group_type']} | {row['group_value']} | {row['entry_premium_bucket']} | {row['sample_count']} | {_fmt(row.get('avg_return_20d'))} | {_fmt(row.get('win_rate'))} | {_fmt(row.get('p10_return_20d'))} |"
        )
    lines.extend(
        [
            "",
            "This report is diagnostic only. It does not recommend a 2%-3% hard entry-premium cap or any live rule.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_summary_report(
    path: Path,
    payload: Mapping[str, Any],
    data_payload: Mapping[str, Any],
    risk_payload: Mapping[str, Any],
    exit_payload: Mapping[str, Any],
    entry_payload: Mapping[str, Any],
) -> None:
    lines = [
        "# 2026-07 Batch 3 Summary",
        "",
        f"- status: {payload['status']}",
        f"- risk_budget_0p005_go_no_go: {payload['risk_budget_0p005_go_no_go']}",
        f"- no_progress_exit_go_no_go: {payload['no_progress_exit_go_no_go']}",
        f"- calendar_gate_fallback_ratio: {_fmt(payload.get('calendar_gate_fallback_ratio'))}",
        f"- trading_day_gate_fallback_ratio: {_fmt(payload.get('trading_day_gate_fallback_ratio'))}",
        f"- true_trading_day_missing_count: {payload.get('true_trading_day_missing_count')}",
        f"- calendar_missing_classification: {payload.get('calendar_missing_classification')}",
        f"- legacy_calendar_fallback_exposure_ratio: {_fmt(payload.get('fallback_exposure_ratio'))}",
        "",
        "## Go / No-Go",
        "",
        f"- risk_budget_0.005: {payload['risk_budget_0p005_go_no_go']} ({risk_payload.get('recommendation', {}).get('risk_budget_0p005')})",
        f"- risk_budget_0.010 too concentrated: {risk_payload.get('recommendation', {}).get('risk_budget_0p010_too_concentrated')}",
        f"- no-progress exit: {payload['no_progress_exit_go_no_go']} ({exit_payload.get('recommendation', {}).get('no_progress_exit')})",
        "",
        "## Data Blockers",
        "",
    ]
    for blocker in payload.get("remaining_blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "## Liquidity Counts",
            "",
            "| threshold_rmb | pass_count | fail_count | missing_count |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("liquidity_thresholds", []):
        lines.append(
            f"| {_fmt(row['threshold'])} | {row['pass_count']} | {row['fail_count']} | {row['missing_count']} |"
        )
    lines.extend(
        [
            "",
            "## Explicit Reject / Defer",
            "",
        ]
    )
    for name, decision in payload.get("deferred_or_rejected", {}).items():
        lines.append(f"- {name}: {decision}")
    lines.extend(
        [
            "",
            "## Report Status",
            "",
            f"- data readiness: {data_payload.get('status')}",
            f"- risk-budget robustness: {risk_payload.get('status')}",
            f"- hold-progress exit simulation: {exit_payload.get('status')}",
            f"- entry-premium interaction: {entry_payload.get('status')}",
            "",
            "## Additional Batch 3 Blocker Reports",
            "",
        ]
    )
    for name, status in payload.get("extra_report_statuses", {}).items():
        lines.append(f"- {name}: {status}")
    lines.extend(
        [
            "",
            "## Tests",
            "",
            "- Run `python -m pytest -q tests/test_batch3_stock_strategy_research.py ...` plus existing Batch 2 focused tests.",
            "- Run `python -m ruff check` on changed Batch 3 files.",
            "",
            "No Batch 3 result is wired into live strategy behavior.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gate_repair_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "calendar_day_exposure" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Gate Exposure Repair Report", payload)
        return
    calendar = payload.get("calendar_day_exposure", {})
    lines = [
        "# 2026-07 Batch 3 Gate Exposure Repair Report",
        "",
        f"- status: {payload.get('status')}",
        f"- target: {payload.get('target')}",
        f"- explanation: {payload.get('explanation')}",
        "",
        "## Calendar-Day Exposure Readiness",
        "",
        "| date_count | persisted_rows | replayed_rows | fallback_rows | fallback_ratio | missing_dates_total |",
        "|---:|---:|---:|---:|---:|---:|",
        "| {date_count} | {persisted} | {replayed} | {fallback} | {ratio} | {missing} |".format(
            date_count=calendar.get("date_count"),
            persisted=calendar.get("persisted_rows"),
            replayed=calendar.get("replayed_rows"),
            fallback=calendar.get("fallback_rows"),
            ratio=_fmt(calendar.get("fallback_ratio")),
            missing=calendar.get("missing_dates_total"),
        ),
        "",
        f"- source_counts: {calendar.get('source_counts', {})}",
        f"- missing_date_ranges: {calendar.get('missing_date_ranges', [])}",
        "",
        "## Trading-Day Equity-Curve Coverage",
        "",
        "| variant | status | equity_curve_days | per_date_actual_days | state_max_fallback_days | fallback_ratio |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload.get("trading_day_exposure", []):
        lines.append(
            "| {variant} | {status} | {days} | {actual} | {fallback} | {ratio} |".format(
                variant=row.get("variant"),
                status=row.get("status"),
                days=row.get("equity_curve_days"),
                actual=row.get("per_date_actual_days"),
                fallback=row.get("state_max_fallback_days"),
                ratio=_fmt(row.get("fallback_ratio")),
            )
        )
    lines.extend(
        [
            "",
            "The calendar-day ratio answers data-pipeline coverage; the trading-day ratio answers how much of the simulated equity curve still used the max policy exposure fallback.",
            "Synthetic exposure-matched baselines remain controls only and do not prove real gate coverage.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_liquidity_unit_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "liquidity" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Liquidity Unit Capacity Report", payload)
        return
    liquidity = payload.get("liquidity", {})
    lines = [
        "# 2026-07 Batch 3 Liquidity Unit Capacity Report",
        "",
        f"- status: {payload.get('status')}",
        f"- unit_status: {payload.get('unit_status')}",
        f"- source_field: {TABLE_OBS}.amount loaded as daily_amount in execution backtest inputs",
        f"- interpretation: {payload.get('interpretation')}",
        f"- thresholds_all_fail: {payload.get('thresholds_all_fail')}",
        "",
        "## Daily Amount Distribution",
        "",
        f"- row_count: {liquidity.get('row_count')}",
        f"- known_count: {liquidity.get('daily_amount_known_count')}",
        f"- missing_count: {liquidity.get('daily_amount_missing_count')}",
        f"- coverage_ratio: {_fmt(liquidity.get('daily_amount_coverage_ratio'))}",
        f"- min: {_fmt(liquidity.get('daily_amount_min'))}",
        f"- median: {_fmt(liquidity.get('daily_amount_median'))}",
        f"- p90: {_fmt(liquidity.get('daily_amount_p90'))}",
        f"- max: {_fmt(liquidity.get('daily_amount_max'))}",
        "",
        "## Capacity Thresholds",
        "",
        "| threshold_rmb | pass_count | fail_count | missing_count | pass_ratio |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in liquidity.get("thresholds", []):
        lines.append(
            f"| {_fmt(row.get('threshold'))} | {row.get('pass_count')} | {row.get('fail_count')} | {row.get('missing_count')} | {_fmt(row.get('pass_ratio'))} |"
        )
    lines.extend(
        [
            "",
            "Conclusion: keep this report blocked until the upstream unit is explicitly confirmed. If the unit is RMB, current capacity is unusable at the tested thresholds; if the unit is not RMB, convert upstream and rerun.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_adjustment_gap_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "price_path_adjustment" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Adjustment Factor Gap Report", payload)
        return
    price = payload.get("price_path_adjustment", {})
    sensitivity = payload.get("sensitivity_excluding_missing_adj_factor_paths", {})
    lines = [
        "# 2026-07 Batch 3 Adjustment Factor Gap Report",
        "",
        f"- status: {payload.get('status')}",
        f"- clean_path_count: {payload.get('clean_path_count')}",
        f"- clean_execution_row_count: {payload.get('clean_execution_row_count')}",
        "",
        "## Adjustment Factor Coverage",
        "",
        f"- path_count: {price.get('path_count')}",
        f"- total_path_rows: {price.get('total_path_rows')}",
        f"- missing_adjustment_factor_rows: {price.get('missing_adjustment_factor_rows')}",
        f"- missing_adjustment_factor_ratio: {_fmt(price.get('missing_adjustment_factor_ratio'))}",
        f"- affected_symbol_date_count: {price.get('affected_symbol_date_count')}",
        "",
        "## Top Missing Symbols",
        "",
        "| stock_code | missing_rows | first_date | last_date |",
        "|---|---:|---|---|",
    ]
    for row in price.get("top_missing_adjustment_factor_symbols", []):
        lines.append(
            f"| {row.get('stock_code')} | {row.get('missing_rows')} | {row.get('first_date')} | {row.get('last_date')} |"
        )
    lines.extend(
        [
            "",
            "## Sensitivity Excluding Missing Adjustment Paths",
            "",
            f"- status: {sensitivity.get('status')}",
            f"- risk_0p005_return_delta: {_fmt(sensitivity.get('risk_0p005_return_delta'))}",
            f"- risk_0p005_mdd_delta: {_fmt(sensitivity.get('risk_0p005_mdd_delta'))}",
            f"- risk_0p005_still_beats_fixed_20d: {sensitivity.get('risk_0p005_still_beats_fixed_20d')}",
            "",
            "Fixed 20d metrics:",
            json.dumps(sensitivity.get("fixed_20d", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "Risk-budget 0.005 metrics:",
            json.dumps(sensitivity.get("risk_budget_0p005", {}), ensure_ascii=False, sort_keys=True, default=str),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_risk_v2_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "daily_bootstrap" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Risk-Budget Robustness V2 Report", payload)
        return
    walk_forward = payload.get("walk_forward", {})
    selected = walk_forward.get("test_selected_metrics", {})
    fixed = walk_forward.get("test_fixed_20d_metrics", {})
    lines = [
        "# 2026-07 Batch 3 Risk-Budget Robustness V2 Report",
        "",
        f"- status: {payload.get('status')}",
        f"- risk_budget_0p005: {payload.get('risk_budget_0p005')}",
        f"- risk_budget_0p010: {payload.get('risk_budget_0p010')}",
        f"- reason: {payload.get('reason')}",
        "",
        "## Daily IID Bootstrap",
        "",
        json.dumps(payload.get("daily_bootstrap", {}), ensure_ascii=False, sort_keys=True, default=str),
        "",
        "## Month-Cluster Bootstrap",
        "",
        json.dumps(payload.get("month_cluster_bootstrap", {}), ensure_ascii=False, sort_keys=True, default=str),
        "",
        "## Walk Forward",
        "",
        f"- status: {walk_forward.get('status')}",
        f"- split_date: {walk_forward.get('split_date')}",
        f"- selected_risk_per_trade: {walk_forward.get('selected_risk_per_trade')}",
        "",
        "| metric | selected_risk | fixed_20d | delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in ("cumulative_return", "max_drawdown", "daily_sharpe", "cagr"):
        selected_value = _first_float(selected.get(metric))
        fixed_value = _first_float(fixed.get(metric))
        delta = _round(selected_value - fixed_value) if selected_value is not None and fixed_value is not None else None
        lines.append(f"| {metric} | {_fmt(selected_value)} | {_fmt(fixed_value)} | {_fmt(delta)} |")
    selected_calmar = _calmar(selected.get("cagr"), selected.get("max_drawdown"))
    fixed_calmar = _calmar(fixed.get("cagr"), fixed.get("max_drawdown"))
    calmar_delta = _round(selected_calmar - fixed_calmar) if selected_calmar is not None and fixed_calmar is not None else None
    lines.extend(
        [
            f"| calmar | {_fmt(selected_calmar)} | {_fmt(fixed_calmar)} | {_fmt(calmar_delta)} |",
            "",
            "## Underperforming Independent Slices",
            "",
            "| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | max_drawdown | sharpe |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("underperforming_independent_slices", []):
        lines.append(
            f"| {row.get('slice_type')} | {row.get('slice_value')} | {row.get('row_count')} | {_fmt(row.get('fixed_20d_return'))} | {_fmt(row.get('risk_0p005_return'))} | {_fmt(row.get('increment'))} | {_fmt(row.get('risk_0p005_max_drawdown'))} | {_fmt(row.get('risk_0p005_sharpe'))} |"
        )
    lines.extend(
        [
            "",
            "Specific concern required by review: 2026, WARM, and low/mid/high volatility slices must be treated as independent robustness checks; any negative row above blocks live promotion.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_exit_path_mode_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "portfolio_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Hold-Progress Exit Path-Mode Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Hold-Progress Exit Path-Mode Report",
        "",
        f"- status: {payload.get('status')}",
        f"- engine_mode: {payload.get('engine_mode')}",
        f"- position_level_csv: {payload.get('position_level_csv')}",
        f"- portfolio_level_csv: {payload.get('portfolio_level_csv')}",
        f"- recommendation: {payload.get('recommendation', {}).get('no_progress_exit')}",
        "",
        "This simulation exits on the day-k trigger's next tradable open and does not use future path data to decide the trigger. It remains report-layer only.",
        "",
        "## Rule Summary",
        "",
        "| rule | fixed_20d_return_delta | fixed_20d_mdd_delta | risk_0p005_return_delta | risk_0p005_mdd_delta | risk_0p010_return_delta | risk_0p010_mdd_delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("rule_rows", []):
        lines.append(
            f"| {row.get('rule')} | {_fmt(row.get('fixed_20d_return_delta'))} | {_fmt(row.get('fixed_20d_mdd_delta'))} | {_fmt(row.get('risk_0p005_return_delta'))} | {_fmt(row.get('risk_0p005_mdd_delta'))} | {_fmt(row.get('risk_0p010_return_delta'))} | {_fmt(row.get('risk_0p010_mdd_delta'))} |"
        )
    lines.extend(
        [
            "",
            "## Portfolio Comparison",
            "",
            "| base_variant | rule | cumulative_return | cagr | max_drawdown | daily_sharpe | return_delta_vs_baseline | max_drawdown_delta_vs_baseline | exposure_fallback_day_ratio |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("portfolio_rows", []):
        lines.append(
            f"| {row.get('base_variant')} | {row.get('rule')} | {_fmt(row.get('cumulative_return'))} | {_fmt(row.get('cagr'))} | {_fmt(row.get('max_drawdown'))} | {_fmt(row.get('daily_sharpe'))} | {_fmt(row.get('return_delta_vs_baseline'))} | {_fmt(row.get('max_drawdown_delta_vs_baseline'))} | {_fmt(row.get('exposure_fallback_day_ratio'))} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            json.dumps(payload.get("recommendation", {}), ensure_ascii=False, sort_keys=True, default=str),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gate_repair_v2_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "calendar_day_exposure" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Gate Exposure Repair V2 Report", payload)
        return
    calendar = payload.get("calendar_day_exposure", {})
    trading = payload.get("trading_day_exposure", {})
    diagnostics = payload.get("source_diagnostics", {})
    lines = [
        "# 2026-07 Batch 3 Gate Exposure Repair V2 Report",
        "",
        f"- status: {payload.get('status')}",
        f"- repair_result: {payload.get('repair_result')}",
        f"- date_window: {payload.get('date_window')}",
        "",
        "## Coverage",
        "",
        "| basis | date_count | actual_or_replayed | fallback_rows | fallback_ratio |",
        "|---|---:|---:|---:|---:|",
        f"| calendar | {calendar.get('date_count')} | {(_first_float(calendar.get('persisted_rows')) or 0) + (_first_float(calendar.get('replayed_rows')) or 0):.0f} | {calendar.get('fallback_rows')} | {_fmt(calendar.get('fallback_ratio'))} |",
        f"| trading-day equity | {trading.get('equity_curve_days')} | {trading.get('per_date_actual_days')} | {trading.get('state_max_fallback_days')} | {_fmt(trading.get('fallback_ratio'))} |",
        "",
        "## Persisted Exposure Tables",
        "",
        "| table | exists | status | rows | window_non_null_exposure_rows | first | last |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in diagnostics.get("persisted_exposure_tables", []):
        lines.append(
            f"| {row.get('table')} | {row.get('exists')} | {row.get('status')} | {row.get('row_count')} | {row.get('window_non_null_exposure_rows')} | {row.get('window_first_date')} | {row.get('window_last_date')} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Evidence And Replay Sources",
            "",
            json.dumps(diagnostics.get("candidate_history_gate_evidence", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            json.dumps(diagnostics.get("replay_sources", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "Stop condition: this remains no-go until both calendar and trading-day fallback ratios are below 10%.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gate_repair_v3_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "calendar_day_exposure" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Gate Exposure Repair V3 Report", payload)
        return
    calendar = payload.get("calendar_day_exposure", {})
    trading = payload.get("trading_day_exposure", {})
    validation = payload.get("trading_calendar_validation", {})
    diagnostics = payload.get("source_diagnostics", {})
    lines = [
        "# 2026-07 Batch 3 Gate Exposure Repair V3 Report",
        "",
        f"- status: {payload.get('status')}",
        f"- repair_result: {payload.get('repair_result')}",
        f"- date_window: {payload.get('date_window')}",
        f"- calendar_gate_fallback_ratio: {_fmt(calendar.get('fallback_ratio'))}",
        f"- trading_day_gate_fallback_ratio: {_fmt(trading.get('fallback_ratio'))}",
        f"- true_trading_day_missing_count: {validation.get('true_trading_day_missing_count')}",
        f"- true_trading_day_missing_ratio: {_fmt(validation.get('true_trading_day_missing_ratio'))}",
        f"- calendar_missing_classification: {validation.get('classification')}",
        "",
        "## Calendar vs Trading-Day Coverage",
        "",
        "| basis | date_count | actual_or_replayed | fallback_rows | fallback_ratio |",
        "|---|---:|---:|---:|---:|",
        f"| calendar natural days | {calendar.get('date_count')} | {(_first_float(calendar.get('persisted_rows')) or 0) + (_first_float(calendar.get('replayed_rows')) or 0):.0f} | {calendar.get('fallback_rows')} | {_fmt(calendar.get('fallback_ratio'))} |",
        f"| trading-day equity curve | {trading.get('equity_curve_days')} | {trading.get('per_date_actual_days')} | {trading.get('state_max_fallback_days')} | {_fmt(trading.get('fallback_ratio'))} |",
        f"| benchmark trading calendar | {validation.get('true_trading_day_total')} | {validation.get('true_trading_day_total')} | {validation.get('true_trading_day_missing_count')} | {_fmt(validation.get('true_trading_day_missing_ratio'))} |",
        "",
        "## Calendar Missing Classification",
        "",
        f"- calendar_missing_total: {validation.get('calendar_missing_total')}",
        f"- calendar_missing_not_trading_day_count: {validation.get('calendar_missing_not_trading_day_count')}",
        f"- calendar_missing_weekend_count: {validation.get('calendar_missing_weekend_count')}",
        f"- calendar_missing_weekday_non_trading_count: {validation.get('calendar_missing_weekday_non_trading_count')}",
        f"- true_trading_day_missing_ranges: {validation.get('true_trading_day_missing_ranges')}",
        f"- calendar_missing_not_trading_day_ranges: {validation.get('calendar_missing_not_trading_day_ranges')}",
        f"- calendar_source_warning: {validation.get('calendar_source_warning')}",
        "",
        "## Replayed Exposure Lineage",
        "",
        json.dumps(validation.get("replayed_exposure_lineage", {}), ensure_ascii=False, sort_keys=True, default=str),
        "",
        "## Trading-Day Sources",
        "",
        "| table | status | series_id | rows | first | last | source_versions | vendor_versions | rule_versions |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for row in validation.get("trading_day_sources", []):
        lines.append(
            "| {table} | {status} | {series_id} | {rows} | {first} | {last} | {source_versions} | {vendor_versions} | {rule_versions} |".format(
                table=row.get("table"),
                status=row.get("status"),
                series_id=row.get("series_id"),
                rows=row.get("row_count"),
                first=row.get("first_date"),
                last=row.get("last_date"),
                source_versions=json.dumps(row.get("source_versions", []), ensure_ascii=False),
                vendor_versions=json.dumps(row.get("vendor_versions", []), ensure_ascii=False),
                rule_versions=json.dumps(row.get("rule_versions", []), ensure_ascii=False),
            )
        )
    lines.extend(
        [
            "",
            "## Persisted Exposure Tables",
            "",
            "| table | exists | status | rows | window_non_null_exposure_rows | first | last |",
            "|---|---|---|---:|---:|---|---|",
        ]
    )
    for row in diagnostics.get("persisted_exposure_tables", []):
        lines.append(
            f"| {row.get('table')} | {row.get('exists')} | {row.get('status')} | {row.get('row_count')} | {row.get('window_non_null_exposure_rows')} | {row.get('window_first_date')} | {row.get('window_last_date')} |"
        )
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = list(payload.get("warnings", []))
    if not warnings:
        lines.append("- none")
    for warning in warnings:
        lines.append(f"- {warning}")
    lines.extend(["", "## Blockers", ""])
    blockers = list(payload.get("blockers", []))
    if not blockers:
        lines.append("- none")
    for blocker in blockers:
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "Stop condition: strategy gate is blocked only when trading-day fallback exceeds 10%, true trading-day missing dates remain, or no trading-day validation source exists. Natural calendar gaps that validate as non-trading dates are pipeline warnings.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_liquidity_v2_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "liquidity" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Liquidity Unit Capacity V2 Report", payload)
        return
    liquidity = payload.get("liquidity", {})
    lines = [
        "# 2026-07 Batch 3 Liquidity Unit Capacity V2 Report",
        "",
        f"- status: {payload.get('status')}",
        f"- unit_status: {payload.get('unit_status')}",
        f"- source: {payload.get('source_table')}.{payload.get('source_field')}",
        "",
        "## Raw Daily Amount",
        "",
        f"- known_count: {liquidity.get('daily_amount_known_count')}",
        f"- min: {_fmt(liquidity.get('daily_amount_min'))}",
        f"- median: {_fmt(liquidity.get('daily_amount_median'))}",
        f"- p90: {_fmt(liquidity.get('daily_amount_p90'))}",
        f"- max: {_fmt(liquidity.get('daily_amount_max'))}",
        "",
        "## Raw Thresholds",
        "",
        "| threshold | pass_count | fail_count | missing_count |",
        "|---:|---:|---:|---:|",
    ]
    for row in liquidity.get("thresholds", []):
        lines.append(f"| {_fmt(row.get('threshold'))} | {row.get('pass_count')} | {row.get('fail_count')} | {row.get('missing_count')} |")
    lines.extend(
        [
            "",
            "## Source Lineage",
            "",
            json.dumps(payload.get("source_lineage", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "Local lineage confirms pass-through storage from upstream AMOUNT to `choice_stock_daily_observation.amount` and then Batch3 `daily_amount`; it does not confirm a canonical `daily_amount_rmb` conversion.",
            "",
            "## Unit Diagnostics",
            "",
            json.dumps(payload.get("implied_unit_diagnostics", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "## Threshold Sensitivity Under Scale Hypotheses",
            "",
            "| scale | multiplier | threshold | pass_count | fail_count | missing_count |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("scaled_threshold_hypotheses", []):
        lines.append(
            f"| {row.get('scale')} | {_fmt(row.get('multiplier'))} | {_fmt(row.get('threshold'))} | {row.get('pass_count')} | {row.get('fail_count')} | {row.get('missing_count')} |"
        )
    lines.extend(["", "## Blockers", ""])
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.append("")
    lines.append("Stop condition: this remains blocked until the upstream amount unit is confirmed and raw/converted thresholds are explicitly justified.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_adjustment_gap_v2_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "price_path_adjustment" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Adjustment Factor Gap V2 Report", payload)
        return
    price = payload.get("price_path_adjustment", {})
    sensitivity = payload.get("sensitivity_excluding_missing_adj_factor_paths", {})
    table_diagnostics = payload.get("adj_factor_table_diagnostics", {})
    lines = [
        "# 2026-07 Batch 3 Adjustment Factor Gap V2 Report",
        "",
        f"- status: {payload.get('status')}",
        f"- missing_adjustment_factor_rows: {price.get('missing_adjustment_factor_rows')}",
        f"- missing_adjustment_factor_ratio: {_fmt(price.get('missing_adjustment_factor_ratio'))}",
        f"- clean_path_count: {payload.get('clean_path_count')}",
        f"- clean_execution_row_count: {payload.get('clean_execution_row_count')}",
        f"- clean_subset_share: {_fmt(payload.get('clean_subset_share'))}",
        f"- sample_selection_warning: {payload.get('sample_selection_warning')}",
        "",
        "## Adjustment Factor Table Diagnostics",
        "",
        f"- table_status: {table_diagnostics.get('status')}",
        f"- row_count: {table_diagnostics.get('row_count')}",
        f"- date_count: {table_diagnostics.get('date_count')}",
        f"- stock_code_count: {table_diagnostics.get('stock_code_count')}",
        f"- first_date: {table_diagnostics.get('first_date')}",
        f"- last_date: {table_diagnostics.get('last_date')}",
        f"- missing_path_date_count: {table_diagnostics.get('missing_path_date_count')}",
        f"- missing_path_dates_present_in_adj_table: {table_diagnostics.get('missing_path_dates_present_in_adj_table')}",
        f"- missing_path_dates_absent_from_adj_table: {table_diagnostics.get('missing_path_dates_absent_from_adj_table')}",
        f"- diagnosis: {table_diagnostics.get('diagnosis')}",
        "",
        "### Top Missing Path Dates",
        "",
        "| trade_date | missing_rows |",
        "|---|---:|",
    ]
    for row in table_diagnostics.get("top_missing_path_dates", []):
        lines.append(f"| {row.get('trade_date')} | {row.get('missing_rows')} |")
    lines.extend(
        [
            "",
            "## Missing By Month",
            "",
            "| month | missing_rows |",
            "|---|---:|",
        ]
    )
    for row in payload.get("missing_by_month", []):
        lines.append(f"| {row.get('month')} | {row.get('missing_rows')} |")
    lines.extend(
        [
            "",
            "## Missing By Board",
            "",
            "| board | missing_rows |",
            "|---|---:|",
        ]
    )
    for row in payload.get("missing_by_board", []):
        lines.append(f"| {row.get('board')} | {row.get('missing_rows')} |")
    lines.extend(
        [
            "",
            "## Clean-Subset Sensitivity",
            "",
            f"- status: {sensitivity.get('status')}",
            f"- risk_0p005_return_delta: {_fmt(sensitivity.get('risk_0p005_return_delta'))}",
            f"- risk_0p005_mdd_delta: {_fmt(sensitivity.get('risk_0p005_mdd_delta'))}",
            f"- risk_0p005_still_beats_fixed_20d: {sensitivity.get('risk_0p005_still_beats_fixed_20d')}",
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.append("")
    lines.append("Stop condition: this remains no-go until missing adjustment factor paths are filled or excluded with explicit sample-bias disclosure.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_path_tieout_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") == "blocked" and "tieout_rows" not in payload:
        _write_simple_blocked_report(path, "2026-07 Batch 3 Path Engine Tie-Out Report", payload)
        return
    lines = [
        "# 2026-07 Batch 3 Path Engine Tie-Out Report",
        "",
        f"- status: {payload.get('status')}",
        f"- max_abs_cumulative_return_delta: {_fmt(payload.get('max_abs_cumulative_return_delta'))}",
        f"- explanation: {payload.get('explanation')}",
        "",
        "| variant | engine_return | report_return | return_delta | engine_maxDD | report_maxDD | maxDD_delta | engine_sharpe | report_sharpe | sharpe_delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("tieout_rows", []):
        lines.append(
            f"| {row.get('variant')} | {_fmt(row.get('engine_cumulative_return'))} | {_fmt(row.get('report_cumulative_return'))} | {_fmt(row.get('cumulative_return_delta'))} | {_fmt(row.get('engine_max_drawdown'))} | {_fmt(row.get('report_max_drawdown'))} | {_fmt(row.get('max_drawdown_delta'))} | {_fmt(row.get('engine_daily_sharpe'))} | {_fmt(row.get('report_daily_sharpe'))} | {_fmt(row.get('daily_sharpe_delta'))} |"
        )
    lines.extend(["", "## Blockers", ""])
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    if not payload.get("blockers"):
        lines.append("- none")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_risk_post_fix_report(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# 2026-07 Batch 3 Risk-Budget 0.003 / 0.005 Post-Data-Fix Report",
        "",
        f"- status: {payload.get('status')}",
        f"- reason: {payload.get('reason')}",
        f"- risk_budget_candidates: {payload.get('risk_budget_candidates')}",
        "",
        "## Blockers Before Promotion Study",
        "",
    ]
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "This report is intentionally blocked. Run the 0.003/0.005 comparison only after gate exposure, liquidity unit, and adjustment factor blockers are resolved.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_data_blocker_resolution_report(path: Path, payload: Mapping[str, Any]) -> None:
    gate = payload.get("gate", {})
    liquidity = payload.get("liquidity", {})
    adjustment = payload.get("adjustment", {})
    lines = [
        "# 2026-07 Batch 3 Data Blocker Resolution Report",
        "",
        f"- status: {payload.get('status')}",
        f"- calendar_gate_fallback_ratio: {_fmt(gate.get('calendar_fallback_ratio'))}",
        f"- trading_day_gate_fallback_ratio: {_fmt(gate.get('trading_day_fallback_ratio'))}",
        f"- true_trading_day_missing_count: {gate.get('true_trading_day_missing_count')}",
        f"- true_trading_day_missing_ratio: {_fmt(gate.get('true_trading_day_missing_ratio'))}",
        f"- calendar_missing_classification: {gate.get('calendar_missing_classification')}",
        f"- calendar_missing_not_trading_day_count: {gate.get('calendar_missing_not_trading_day_count')}",
        f"- liquidity_unit_status: {liquidity.get('unit_status')}",
        f"- adjustment_missing_ratio: {_fmt(adjustment.get('missing_adjustment_factor_ratio'))}",
        f"- clean_subset_share: {_fmt(adjustment.get('clean_subset_share'))}",
        "",
        "## Gate Exposure",
        "",
        f"- supplement_window_rows: {gate.get('supplement_rows')}",
        "",
        "### Supplement Mapping Assessment",
        "",
        json.dumps(gate.get("supplement_mapping_assessment", {}), ensure_ascii=False, sort_keys=True, default=str),
        "",
        "The supplement table is treated as an input table, not usable exposure history, unless it contains explicit exposure/state fields with formula lineage.",
        "",
        "### Trading-Day Validation Sources",
        "",
        "| table | status | rows | first | last | source_versions | rule_versions |",
        "|---|---|---:|---|---|---|---|",
    ]
    for row in gate.get("trading_day_sources", []):
        lines.append(
            "| {table} | {status} | {rows} | {first} | {last} | {source_versions} | {rule_versions} |".format(
                table=row.get("table"),
                status=row.get("status"),
                rows=row.get("row_count"),
                first=row.get("first_date"),
                last=row.get("last_date"),
                source_versions=json.dumps(row.get("source_versions", []), ensure_ascii=False),
                rule_versions=json.dumps(row.get("rule_versions", []), ensure_ascii=False),
            )
        )
    lines.extend(
        [
            "",
            "### Replay Sources",
            "",
            "| source | exists | rows | first | last | usable_as_exposure_history |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for table, info in sorted((gate.get("replay_sources") or {}).items()):
        assessment = info.get("mapping_assessment", {}) if isinstance(info, Mapping) else {}
        lines.append(
            f"| {table} | {info.get('exists') if isinstance(info, Mapping) else None} | "
            f"{info.get('window_rows') if isinstance(info, Mapping) else None} | "
            f"{info.get('window_first_date') if isinstance(info, Mapping) else None} | "
            f"{info.get('window_last_date') if isinstance(info, Mapping) else None} | "
            f"{assessment.get('usable_as_exposure_history') if isinstance(assessment, Mapping) else None} |"
        )
    lines.extend(
        [
            "",
            "## Liquidity Unit",
            "",
            "### Source Lineage",
            "",
            json.dumps(liquidity.get("source_lineage", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "### Unit Diagnostics",
            "",
            json.dumps(liquidity.get("unit_diagnostics", {}), ensure_ascii=False, sort_keys=True, default=str),
            "",
            "### Raw Thresholds",
            "",
            "| threshold | pass_count | fail_count | missing_count |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in liquidity.get("raw_thresholds", []):
        lines.append(f"| {_fmt(row.get('threshold'))} | {row.get('pass_count')} | {row.get('fail_count')} | {row.get('missing_count')} |")
    lines.extend(
        [
            "",
            "### Scale Hypotheses",
            "",
            "| scale | multiplier | threshold | pass_count | fail_count | missing_count |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in liquidity.get("scale_hypotheses", []):
        lines.append(
            f"| {row.get('scale')} | {_fmt(row.get('multiplier'))} | {_fmt(row.get('threshold'))} | "
            f"{row.get('pass_count')} | {row.get('fail_count')} | {row.get('missing_count')} |"
        )
    lines.extend(
        [
            "",
            "## Adjustment Factors",
            "",
            f"- missing_adjustment_factor_rows: {adjustment.get('missing_adjustment_factor_rows')}",
            f"- missing_adjustment_factor_ratio: {_fmt(adjustment.get('missing_adjustment_factor_ratio'))}",
            f"- clean_subset_share: {_fmt(adjustment.get('clean_subset_share'))}",
            f"- sample_selection_warning: {adjustment.get('sample_selection_warning')}",
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    if not payload.get("blockers"):
        lines.append("- none")
    lines.append("")
    lines.append(
        "Stop condition: promotion studies stay blocked until trading-day gate fallback is validated, liquidity unit is confirmed, and adjustment coverage is adequate. Natural calendar gaps validated as non-trading dates are pipeline warnings."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_post_data_fix_risk_report(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# 2026-07 Batch 3 Post-Data-Fix Risk-Budget Report",
        "",
        f"- status: {payload.get('status')}",
        f"- db_path: {payload.get('db_path')}",
        f"- reason: {payload.get('reason')}",
        f"- risk_budget_candidates: {payload.get('risk_budget_candidates')}",
        "",
        "## Required Comparisons",
        "",
    ]
    for item in payload.get("required_comparisons", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Required Checks", ""])
    for item in payload.get("required_checks", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Current Blockers", ""])
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    if not payload.get("blockers"):
        lines.append("- none")
    lines.append("")
    lines.append("No promotion conclusion is allowed while any blocker remains.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_post_data_fix_hold_report(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# 2026-07 Batch 3 Post-Data-Fix Hold-Progress Report",
        "",
        f"- status: {payload.get('status')}",
        f"- db_path: {payload.get('db_path')}",
        f"- priority_retest_rule: {payload.get('priority_retest_rule')}",
        f"- priority_retest_rules: {payload.get('priority_retest_rules')}",
        f"- reason: {payload.get('reason')}",
        "",
        "## Research Leads",
        "",
    ]
    for item in payload.get("research_leads", []):
        lines.append(f"- {item}")
    if not payload.get("research_leads"):
        lines.append("- none")
    lines.extend(["", "## Required Rule Gates", ""])
    for item in payload.get("required_rule_gates", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Current Blockers", ""])
    for blocker in payload.get("blockers", []):
        lines.append(f"- {blocker}")
    if not payload.get("blockers"):
        lines.append("- none")
    lines.append("")
    lines.append("These rules remain retest leads only; none is a paper-trading rule while liquidity or adjustment blockers remain.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_simple_blocked_report(path: Path, title: str, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                f"- status: {payload.get('status', 'blocked')}",
                f"- reason: {payload.get('reason', 'blocked')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _blocked_payload(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason}


def _execution_date_window(rows: Sequence[Mapping[str, object]]) -> tuple[str, str]:
    starts = [str(row.get("entry_date") or row.get("signal_date"))[:10] for row in rows if row.get("entry_date") or row.get("signal_date")]
    ends = [
        str(row.get("exit_date_20d") or row.get("exit_date_5d") or row.get("entry_date"))[:10]
        for row in rows
        if row.get("exit_date_20d") or row.get("exit_date_5d") or row.get("entry_date")
    ]
    return min(starts), max(ends or starts)


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _first_present(columns: set[str], names: tuple[str, ...]) -> str:
    for name in names:
        if name in columns:
            return name
    return ""


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _nested(data: Mapping[str, Any], keys: tuple[str, ...]) -> object:
    current: object = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _first_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _float_or_default(value: object, default: float) -> float:
    number = _first_float(value)
    return default if number is None else number


def _lt(left: object, right: object) -> bool:
    left_number = _first_float(left)
    right_number = _first_float(right)
    return left_number is not None and right_number is not None and left_number < right_number


def _gt(left: object, right: object) -> bool:
    left_number = _first_float(left)
    right_number = _first_float(right)
    return left_number is not None and right_number is not None and left_number > right_number


def _lte(left: object, right: object) -> bool:
    left_number = _first_float(left)
    right_number = _first_float(right)
    return left_number is not None and right_number is not None and left_number <= right_number


def _gte(left: object, right: object) -> bool:
    left_number = _first_float(left)
    right_number = _first_float(right)
    return left_number is not None and right_number is not None and left_number >= right_number


def _entry_premium(row: Mapping[str, object]) -> float | None:
    entry_price = _first_float(row.get("entry_price"))
    signal_close = _first_float(row.get("signal_close"))
    if entry_price is None or signal_close is None or signal_close <= 0:
        return None
    return entry_price / signal_close - 1.0


def _entry_premium_bucket(value: float) -> str:
    if value < 0:
        return "<0"
    if value < 0.01:
        return "[0,1%)"
    if value < 0.02:
        return "[1%,2%)"
    if value < 0.03:
        return "[2%,3%)"
    if value < 0.05:
        return "[3%,5%)"
    return ">=5%"


def _liquidity_bucket(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 20_000_000:
        return "<20m"
    if value < 50_000_000:
        return "20m_to_50m"
    if value < 100_000_000:
        return "50m_to_100m"
    if value < 200_000_000:
        return "100m_to_200m"
    return ">=200m"


def _return_summary_row(group_type: str, group_value: str, bucket: str, returns: Sequence[float]) -> dict[str, object]:
    return {
        "group_type": group_type,
        "group_value": group_value,
        "entry_premium_bucket": bucket,
        "sample_count": len(returns),
        "avg_return_20d": _round(statistics.fmean(returns)),
        "win_rate": _round(sum(1 for value in returns if value > 0) / len(returns)),
        "p10_return_20d": _round(_percentile(returns, 0.10)),
    }


def _volatility_regime_by_date(benchmark_rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    returns = []
    previous = None
    for row in sorted(benchmark_rows, key=lambda item: str(item.get("trade_date") or item.get("date"))):
        date_key = str(row.get("trade_date") or row.get("date"))[:10]
        value = _first_float(row.get("value"), row.get("value_numeric"), row.get("close"))
        daily_return = _first_float(row.get("daily_return"), row.get("return"))
        if daily_return is None and value is not None and previous is not None and previous > 0:
            daily_return = value / previous - 1.0
        if value is not None:
            previous = value
        if daily_return is None:
            continue
        returns.append((date_key, daily_return))
    vols = []
    for index, (date_key, _ret) in enumerate(returns):
        if index < 19:
            continue
        window = [value for _date, value in returns[index - 19 : index + 1]]
        vol = statistics.stdev(window) * math.sqrt(252) if len(window) > 1 else None
        if vol is not None:
            vols.append((date_key, vol))
    if not vols:
        return {}
    values = [vol for _date, vol in vols]
    p33 = _percentile(values, 0.33)
    p66 = _percentile(values, 0.66)
    out = {}
    for date_key, vol in vols:
        if vol <= p33:
            out[date_key] = "low_vol"
        elif vol <= p66:
            out[date_key] = "mid_vol"
        else:
            out[date_key] = "high_vol"
    return out


def _net_return(entry_price: float, exit_price: float) -> float:
    gross = exit_price / entry_price - 1.0
    return net_return_after_costs(
        gross,
        buy_cost_rate=POLICY.buy_cost_rate,
        sell_cost_rate=POLICY.sell_cost_rate,
        slippage_rate=POLICY.slippage_rate,
    )


def _daily_returns(equity_curve: Sequence[Mapping[str, object]]) -> list[float]:
    values = [float(row["net_value"]) for row in equity_curve if row.get("net_value") is not None]
    return [values[index] / values[index - 1] - 1.0 for index in range(1, len(values)) if values[index - 1] > 0]


def _returns_by_date(equity_curve: Sequence[Mapping[str, object]]) -> dict[str, float]:
    out = {}
    previous = None
    for row in equity_curve:
        value = _first_float(row.get("net_value"))
        date_key = str(row.get("date") or "")[:10]
        if value is None or not date_key:
            continue
        if previous is not None and previous > 0:
            out[date_key] = value / previous - 1.0
        previous = value
    return out


def _sortino(returns: Sequence[float]) -> float | None:
    if not returns:
        return None
    downside = [min(value, 0.0) for value in returns]
    if len(downside) < 2:
        return None
    downside_dev = statistics.stdev(downside)
    if downside_dev <= 0:
        return None
    return _round(statistics.fmean(returns) / downside_dev * math.sqrt(252))


def _calmar(cagr: object, max_drawdown: object) -> float | None:
    cagr_value = _first_float(cagr)
    drawdown = _first_float(max_drawdown)
    if cagr_value is None or drawdown is None or drawdown <= 0:
        return None
    return _round(cagr_value / drawdown)


def _average_exposure(equity_curve: Sequence[Mapping[str, object]]) -> float:
    values = []
    for row in equity_curve:
        net_value = _first_float(row.get("net_value"))
        invested = _first_float(row.get("invested"))
        if net_value and invested is not None:
            values.append(invested / net_value)
    return _round(statistics.fmean(values)) if values else 0.0


def _average_position_count(equity_curve: Sequence[Mapping[str, object]]) -> float:
    values = [_first_float(row.get("open_positions")) for row in equity_curve]
    clean = [value for value in values if value is not None]
    return _round(statistics.fmean(clean)) if clean else 0.0


def _top_contributions(result: PortfolioBacktestResult) -> dict[str, list[dict[str, object]]]:
    by_date: dict[str, float] = defaultdict(float)
    by_symbol: dict[str, float] = defaultdict(float)
    for row in result.trades:
        if row.get("action") != "sell":
            continue
        proceeds = _first_float(row.get("amount"))
        return_net = _first_float(row.get("return_net"))
        if proceeds is None or return_net is None or return_net <= -0.999999:
            continue
        cost = proceeds / (1.0 + return_net)
        pnl = proceeds - cost
        by_date[str(row.get("date") or "")[:10]] += pnl
        by_symbol[str(row.get("stock_code") or "")] += pnl
    return {
        "largest_5_pnl_dates": [
            {"date": key, "pnl": _round(value)}
            for key, value in sorted(by_date.items(), key=lambda item: abs(item[1]), reverse=True)[:5]
        ],
        "top_10_symbols_by_pnl": [
            {"stock_code": key, "pnl": _round(value)}
            for key, value in sorted(by_symbol.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
    }


def _threshold_row(liquidity: Mapping[str, Any], threshold: float) -> Mapping[str, object]:
    for row in liquidity.get("thresholds", []):
        if _first_float(row.get("threshold")) == threshold:
            return row
    return {}


def _date_ranges(date_keys: Sequence[str]) -> list[dict[str, object]]:
    parsed = []
    for date_key in sorted({str(value)[:10] for value in date_keys if value}):
        try:
            parsed.append(datetime.strptime(date_key, "%Y-%m-%d").date())
        except ValueError:
            continue
    if not parsed:
        return []
    ranges: list[dict[str, object]] = []
    start = parsed[0]
    previous = parsed[0]
    for current in parsed[1:]:
        if current == previous + timedelta(days=1):
            previous = current
            continue
        ranges.append({"start": start.isoformat(), "end": previous.isoformat(), "days": (previous - start).days + 1})
        start = current
        previous = current
    ranges.append({"start": start.isoformat(), "end": previous.isoformat(), "days": (previous - start).days + 1})
    return ranges


def _top_missing_adjustment_factor_symbols(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for key, rows in price_paths.items():
        stock_code = key.split("|", 1)[0]
        for row in rows:
            if bool(row.get("adj_factor_missing")):
                grouped[stock_code].append(str(row.get("trade_date") or "")[:10])
    out = []
    for stock_code, dates in grouped.items():
        clean_dates = sorted(date_key for date_key in dates if date_key)
        out.append(
            {
                "stock_code": stock_code,
                "missing_rows": len(clean_dates),
                "first_date": clean_dates[0] if clean_dates else None,
                "last_date": clean_dates[-1] if clean_dates else None,
            }
        )
    return sorted(out, key=lambda row: (-int(row["missing_rows"]), str(row["stock_code"])))[:limit]


def _adjustment_factor_table_diagnostics(
    conn: duckdb.DuckDBPyConnection,
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    missing_pairs = [
        (key.split("|", 1)[0], str(row.get("trade_date") or "")[:10])
        for key, rows in price_paths.items()
        for row in rows
        if bool(row.get("adj_factor_missing")) and str(row.get("trade_date") or "").strip()
    ]
    missing_dates = sorted({trade_date for _stock_code, trade_date in missing_pairs})
    if TABLE_ADJ_FACTOR not in _table_names(conn):
        return {
            "status": "blocked",
            "reason": f"{TABLE_ADJ_FACTOR} table is missing",
            "missing_path_rows": len(missing_pairs),
            "missing_path_date_count": len(missing_dates),
        }
    row = conn.execute(
        f"""
        select count(*), count(distinct trade_date), count(distinct stock_code), min(trade_date), max(trade_date)
        from {TABLE_ADJ_FACTOR}
        """
    ).fetchone()
    present_missing_dates: set[str] = set()
    absent_missing_dates = set(missing_dates)
    if missing_dates:
        placeholders = ", ".join("?" for _ in missing_dates)
        present_missing_dates = {
            str(item[0])[:10]
            for item in conn.execute(
                f"""
                select distinct trade_date
                from {TABLE_ADJ_FACTOR}
                where trade_date in ({placeholders})
                """,
                missing_dates,
            ).fetchall()
        }
        absent_missing_dates = set(missing_dates) - present_missing_dates
    missing_date_counts = _counter_values([trade_date for _stock_code, trade_date in missing_pairs])
    return {
        "status": "ready",
        "table": TABLE_ADJ_FACTOR,
        "row_count": int(row[0] or 0),
        "date_count": int(row[1] or 0),
        "stock_code_count": int(row[2] or 0),
        "first_date": str(row[3])[:10] if row[3] else None,
        "last_date": str(row[4])[:10] if row[4] else None,
        "missing_path_rows": len(missing_pairs),
        "missing_path_date_count": len(missing_dates),
        "missing_path_dates_present_in_adj_table": len(present_missing_dates),
        "missing_path_dates_absent_from_adj_table": len(absent_missing_dates),
        "top_missing_path_dates": [
            {"trade_date": trade_date, "missing_rows": count}
            for trade_date, count in sorted(
                missing_date_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:20]
        ],
        "diagnosis": (
            "Path-level gaps are concentrated on dates absent from the local adj_factor table; "
            "do not forward-fill factors without vendor-backed lineage."
        ),
    }


def _counter_values(values: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for value in values:
        out[value] += 1
    return dict(out)


def _calendar_year_slices(rows: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        date_key = str(row.get("signal_date") or row.get("entry_date"))[:10]
        if len(date_key) >= 4:
            out[date_key[:4]].append(row)
    return dict(out)


def _calendar_half_slices(rows: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        date_key = str(row.get("signal_date") or row.get("entry_date"))[:10]
        if len(date_key) < 7:
            continue
        month = int(date_key[5:7])
        half = "H1" if month <= 6 else "H2"
        out[f"{date_key[:4]}-{half}"].append(row)
    return dict(out)


def _group_slices(rows: Sequence[Mapping[str, object]], key: str) -> dict[str, list[Mapping[str, object]]]:
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        out[str(row.get(key) or "UNKNOWN")].append(row)
    return dict(out)


def _liquidity_slices(rows: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        out[_liquidity_bucket(_first_float(row.get("daily_amount")))].append(row)
    return dict(out)


def _entry_premium_slices(rows: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        premium = _entry_premium(row)
        if premium is None:
            out["missing"].append(row)
        else:
            out[_entry_premium_bucket(premium)].append(row)
    return dict(out)


def _volatility_regime_slices(
    rows: Sequence[Mapping[str, object]],
    benchmark_rows: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    regime_by_date = _volatility_regime_by_date(benchmark_rows)
    out: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        date_key = str(row.get("signal_date") or row.get("entry_date"))[:10]
        out[regime_by_date.get(date_key, "UNKNOWN")].append(row)
    return dict(out)


def _variant_row(rows: Sequence[Mapping[str, object]], variant: str) -> Mapping[str, object]:
    for row in rows:
        if row.get("variant") == variant:
            return row
    return {}


def _percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(math.floor((len(ordered) - 1) * p)), 0), len(ordered) - 1)
    return ordered[index]


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return _round(numerator / denominator)


def _round(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, 6)


def _label(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".").replace(".", "p")


def _fmt(value: object) -> str:
    number = _first_float(value)
    if number is None:
        return "NA" if value is None else str(value)
    return f"{number:.6f}"


def _variant_name_from_optimization_row(row: object) -> str | None:
    if not isinstance(row, Mapping):
        return None
    risk = _first_float(row.get("risk_per_trade"))
    if risk is None:
        return None
    return f"risk_budget_{risk:.4f}".rstrip("0").rstrip(".")


def _write_parquet(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    import pandas as pd  # noqa: PLC0415

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_parquet(path, index=False)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Batch 3 stock-strategy research reports.")
    parser.add_argument("--db-path", default="data/moss.duckdb")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--signal-kind", default="stock_candidate")
    parser.add_argument("--followup-only", action="store_true", help="Generate only the Batch 3 A-share optimization follow-up artifacts.")
    args = parser.parse_args()
    runner = run_batch3_followup_returnwork if args.followup_only else run_batch3_research
    payload = runner(db_path=args.db_path, output_dir=args.output_dir, signal_kind=args.signal_kind)
    print(
        json.dumps(
            {
                name: {
                    "status": section.get("status"),
                    "report_path": section.get("report_path"),
                }
                for name, section in payload.items()
                if isinstance(section, Mapping)
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
