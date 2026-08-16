from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.gate_exposure_series import (  # noqa: E402
    load_gate_exposure_by_date,
)
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402

DEFAULT_DB_PATH = ROOT / "data/moss.duckdb"
DEFAULT_CONTRACT_PATH = ROOT / "docs/stock_analysis_fable_extension_study_contract.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data/research/fable-extension-study/runs"
EXTENSION_BIN_ORDER = ("lt_0", "0_5", "5_10", "10_15", "15_plus")
EXTENSION_BIN_BOUNDARIES = {
    "lt_0": "x < 0",
    "0_5": "0 <= x <= 0.05",
    "5_10": "0.05 < x <= 0.10",
    "10_15": "0.10 < x <= 0.15",
    "15_plus": "x > 0.15",
}
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
WINDOWS_RESERVED_RUN_ID_STEMS = {
    "AUX",
    "CON",
    "NUL",
    "PRN",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
LOCAL_SOURCE_METADATA_FIELDS = {"db_path", "contract_path"}
REQUIRED_PROHIBITED_OUTPUTS = {
    "allocation_advice",
    "position_change_command",
    "trade_instruction",
    "execution_approval",
}
CONTRACT_EVIDENCE_TO_RUNTIME_GATE = {
    "primary_adjusted_coverage_gate_passes": "primary_adjusted_coverage",
    "overall_sample_gate_passes": "overall_sample_adequacy",
    "chronological_holdout_direction_is_consistent": (
        "chronological_holdout_direction_consistency"
    ),
    "bin_relation_is_not_inconclusive": "extension_bin_relation_not_inconclusive",
    "cost_basis_remains_comparable": "cost_basis_comparable",
    "candidate_retention_floor_passes": "fixed_15_plus_candidate_retention",
}
PRIMARY_BASIS_ADJUSTMENT_MODE_ALLOWLIST = {
    "net_next_open_adjusted": frozenset({"adj_factor_ratio"}),
}
PANEL_FIELDS = (
    "signal_date",
    "stock_code",
    "stock_name",
    "signal_kind",
    "candidate_rank",
    "entry_date",
    "entry_price_kind",
    "source_entry_executable",
    "entry_block_reason",
    "buy_cost_bps",
    "sell_cost_bps",
    "slippage_bps",
    "price_adjustment_mode",
    "signal_close_value",
    "signal_sma20_value",
    "signal_feature_status",
    "extension",
    "extension_bin",
    "stored_signal_state",
    "replayed_signal_state",
    "replayed_gate_source",
    "replayed_gate_state_missing",
    "state_lineage_conflict",
    "gate_state_as_of_date",
    "return_5d_net",
    "return_5d_net_adj",
    "maturity_5d",
    "return_10d_net",
    "return_10d_net_adj",
    "maturity_10d",
    "return_20d_net",
    "return_20d_net_adj",
    "maturity_20d",
    "data_status",
    "formula_version",
    "source_run_id",
)


def load_study_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path)
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("study contract must be a JSON object")
    if payload.get("schema_version") != "fable_extension_study_contract_v1":
        raise ValueError("schema_version is frozen")
    if payload.get("research_only") is not True:
        raise ValueError("research_only must remain true")
    if payload.get("formal_use_allowed") is not False:
        raise ValueError("formal_use_allowed must remain false")
    if payload.get("actionable") is not False:
        raise ValueError("actionable must remain false")
    if not str(payload.get("study_version") or "").strip():
        raise ValueError("study_version is required")

    universe = _required_mapping(payload, "primary_universe")
    if universe.get("signal_kind") != "stock_candidate":
        raise ValueError("primary_universe signal_kind must be stock_candidate")
    if universe.get("entry_executable") is not True:
        raise ValueError("primary_universe must require entry_executable")
    if universe.get("logical_key") != ["signal_date", "stock_code"]:
        raise ValueError("primary_universe logical_key is frozen")
    if universe.get("blocked_source_rows_retained_for_accountability") is not True:
        raise ValueError("blocked source rows must remain accountable")

    feature = _required_mapping(payload, "primary_feature")
    if feature.get("name") != "ma20_extension":
        raise ValueError("primary_feature name is frozen")
    if feature.get("formula") != "signal_close_value / signal_sma20_value - 1":
        raise ValueError("primary_feature formula is frozen")
    if feature.get("as_of") != "signal_date_close":
        raise ValueError("primary_feature must be as-of signal_date_close")
    if feature.get("unit") != "decimal_ratio":
        raise ValueError("primary_feature unit is frozen")
    if feature.get("lookahead_safe") is not True:
        raise ValueError("primary_feature must remain lookahead safe")
    if feature.get("threshold_search_allowed") is not False:
        raise ValueError("threshold_search_allowed must remain false")

    primary_endpoint = _required_mapping(payload, "primary_endpoint")
    if primary_endpoint.get("field") != "return_20d_net_adj":
        raise ValueError("primary endpoint must remain return_20d_net_adj")
    if _mapping_int(primary_endpoint, "horizon") != 20:
        raise ValueError("primary endpoint horizon must remain 20")
    if primary_endpoint.get("basis") != "net_next_open_adjusted":
        raise ValueError("primary endpoint basis is frozen")
    if primary_endpoint.get("unit") != "decimal_return":
        raise ValueError("primary endpoint unit is frozen")
    if primary_endpoint.get("missing_fallback_allowed") is not False:
        raise ValueError("primary endpoint fallback must remain prohibited")
    sensitivity_endpoint = _required_mapping(payload, "sensitivity_endpoint")
    if sensitivity_endpoint.get("field") != "return_20d_net":
        raise ValueError("sensitivity endpoint must remain return_20d_net")
    if _mapping_int(sensitivity_endpoint, "horizon") != 20:
        raise ValueError("sensitivity endpoint horizon must remain 20")
    if sensitivity_endpoint.get("basis") != "net_next_open_unadjusted":
        raise ValueError("sensitivity endpoint basis is frozen")
    if sensitivity_endpoint.get("unit") != "decimal_return":
        raise ValueError("sensitivity endpoint unit is frozen")
    if sensitivity_endpoint.get("may_replace_primary") is not False:
        raise ValueError("sensitivity endpoint may not replace primary")
    if payload.get("secondary_horizons") != [5, 10]:
        raise ValueError("secondary_horizons are frozen")

    bins = payload.get("extension_bins")
    if list(bins or ()) != list(EXTENSION_BIN_ORDER):
        raise ValueError("extension_bins must remain frozen")
    if payload.get("extension_bin_boundaries") != EXTENSION_BIN_BOUNDARIES:
        raise ValueError("extension_bin_boundaries must remain frozen")
    state_contract = _required_mapping(payload, "gate_state")
    if state_contract.get("as_of") != "signal_date_close":
        raise ValueError("gate state must be as-of signal_date_close")
    if state_contract.get("entry_effective") != "next_tradable_open":
        raise ValueError("gate state entry effect must begin next_tradable_open")
    if state_contract.get("taxonomy") != "livermore_market_gate_not_hason_macro_cycle":
        raise ValueError("gate state taxonomy is frozen")
    stored_lineage = _required_mapping(state_contract, "stored_lineage")
    if (
        stored_lineage.get("field")
        != "livermore_candidate_execution_history.market_state"
    ):
        raise ValueError("stored gate lineage field is frozen")
    if stored_lineage.get("label") != "stored_signal_state":
        raise ValueError("stored gate lineage label is frozen")
    replayed_lineage = _required_mapping(state_contract, "replayed_lineage")
    if replayed_lineage.get("source") != (
        "backend.app.core_finance.gate_exposure_series.load_gate_exposure_by_date"
    ):
        raise ValueError("replayed gate lineage source is frozen")
    if replayed_lineage.get("source_field_must_be_reported") is not True:
        raise ValueError("replayed gate source must remain reportable")
    if replayed_lineage.get("label") != "replayed_signal_state":
        raise ValueError("replayed gate lineage label is frozen")
    if state_contract.get("lineage_conflicts_must_be_reported") is not True:
        raise ValueError("gate lineage conflicts must remain reportable")
    if state_contract.get("lineages_must_not_be_silently_merged") is not True:
        raise ValueError("gate lineages must not be silently merged")

    maturity = _required_mapping(payload, "maturity")
    if maturity.get("calendar_table") != "choice_stock_daily_observation":
        raise ValueError("maturity calendar table is frozen")
    if (
        maturity.get("session_rule")
        != "distinct_valid_trading_dates_strictly_after_signal_date"
    ):
        raise ValueError("maturity session rule is frozen")
    if maturity.get("valid_close_rule") != "finite close_value > 0":
        raise ValueError("maturity valid_close_rule is frozen")
    if maturity.get("valid_status_rule") != (
        "tradestatus must explicitly denote trading when the column exists"
    ):
        raise ValueError("maturity valid_status_rule is frozen")
    if maturity.get("evaluation_clock") != "latest_valid_market_date_not_system_date":
        raise ValueError("maturity evaluation_clock is frozen")
    if maturity.get("categories") != [
        "complete_adjusted",
        "matured_adjustment_missing",
        "matured_missing_bar",
        "natural_pending",
    ]:
        raise ValueError("maturity categories are frozen")

    inference = _required_mapping(payload, "inference")
    if inference.get("bootstrap_unit") != "signal_date":
        raise ValueError("bootstrap_unit must remain signal_date")
    if _mapping_int(inference, "bootstrap_iterations") <= 0:
        raise ValueError("bootstrap_iterations must be positive")
    _mapping_int(inference, "bootstrap_seed")
    if _finite_float(inference.get("confidence_interval")) != 0.95:
        raise ValueError("confidence_interval must remain 0.95")
    if inference.get("continuous_effect_scale") != (
        "return_change_per_10_percentage_point_extension"
    ):
        raise ValueError("continuous_effect_scale is frozen")
    if inference.get("holdout_method") != "chronological_date_split":
        raise ValueError("holdout_method must remain chronological_date_split")
    train_fraction = _finite_float(inference.get("holdout_train_fraction"))
    if train_fraction is None or not 0.0 < train_fraction < 1.0:
        raise ValueError("holdout_train_fraction must be between zero and one")
    gates = _required_mapping(payload, "sample_gates")
    required_gates = {
        "minimum_primary_coverage",
        "minimum_overall_rows",
        "minimum_overall_dates",
        "minimum_bin_rows",
        "minimum_bin_dates",
        "minimum_cell_rows",
        "minimum_cell_dates",
    }
    missing_gates = sorted(required_gates - set(gates))
    if missing_gates:
        raise ValueError(f"sample_gates missing fields: {', '.join(missing_gates)}")
    coverage_gate = _finite_float(gates.get("minimum_primary_coverage"))
    if coverage_gate is None or not 0.0 <= coverage_gate <= 1.0:
        raise ValueError("minimum_primary_coverage must be between zero and one")
    for field in required_gates - {"minimum_primary_coverage"}:
        value = _mapping_int(gates, field)
        if value <= 0:
            raise ValueError(f"{field} must be a positive integer")

    promotion = _required_mapping(payload, "promotion")
    if promotion.get("hard_rule_allowed") is not False:
        raise ValueError("hard_rule_allowed must remain false")
    required_evidence = promotion.get("required_evidence")
    if not isinstance(required_evidence, list) or not required_evidence:
        raise ValueError("promotion required_evidence must be a non-empty list")
    unsupported_evidence = sorted(
        {str(value) for value in required_evidence}
        - set(CONTRACT_EVIDENCE_TO_RUNTIME_GATE)
    )
    if unsupported_evidence:
        raise ValueError(
            "unsupported promotion required_evidence: "
            + ", ".join(unsupported_evidence)
        )
    if required_evidence != list(CONTRACT_EVIDENCE_TO_RUNTIME_GATE):
        raise ValueError(
            "promotion required_evidence must match the frozen runtime gates"
        )
    floor = _finite_float(promotion.get("candidate_retention_floor"))
    if floor is None or not 0.0 <= floor <= 1.0:
        raise ValueError("candidate_retention_floor must be between zero and one")
    if promotion.get("separate_governed_review_required") is not True:
        raise ValueError("separate_governed_review_required must remain true")
    prohibited = set(payload.get("prohibited_outputs") or ())
    if not REQUIRED_PROHIBITED_OUTPUTS.issubset(prohibited):
        raise ValueError("study contract must retain every prohibited output")
    return payload


def load_extension_study_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_kind: str = "stock_candidate",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    tables = _table_names(conn)
    required_tables = {
        "livermore_candidate_execution_history",
        "livermore_candidate_history",
    }
    if not required_tables.issubset(tables):
        missing = ", ".join(sorted(required_tables - tables))
        raise ValueError(f"missing required tables: {missing}")

    execution_columns = _columns(conn, "livermore_candidate_execution_history")
    required_execution = {
        "signal_date",
        "stock_code",
        "signal_kind",
        "signal_close",
        "entry_executable",
    }
    if not required_execution.issubset(execution_columns):
        missing = ", ".join(sorted(required_execution - execution_columns))
        raise ValueError(f"execution history missing columns: {missing}")
    history_columns = _columns(conn, "livermore_candidate_history")
    required_history = {"snapshot_as_of_date", "stock_code", "signal_kind", "ma20"}
    if not required_history.issubset(history_columns):
        missing = ", ".join(sorted(required_history - history_columns))
        raise ValueError(f"candidate history missing columns: {missing}")

    raw_count = int(
        conn.execute(
            "select count(*) from livermore_candidate_execution_history where signal_kind = ?",
            [signal_kind],
        ).fetchone()[0]
    )
    optional_specs = (
        ("stock_name", "varchar"),
        ("candidate_rank", "integer"),
        ("market_state", "varchar"),
        ("entry_date", "date"),
        ("entry_price_kind", "varchar"),
        ("entry_block_reason", "varchar"),
        ("exit_date_5d", "date"),
        ("exit_date_10d", "date"),
        ("exit_date_20d", "date"),
        ("return_5d_net", "double"),
        ("return_5d_net_adj", "double"),
        ("return_10d_net", "double"),
        ("return_10d_net_adj", "double"),
        ("return_20d_net", "double"),
        ("return_20d_net_adj", "double"),
        ("buy_cost_bps", "double"),
        ("sell_cost_bps", "double"),
        ("slippage_bps", "double"),
        ("price_adjustment_mode", "varchar"),
        ("data_status", "varchar"),
        ("formula_version", "varchar"),
        ("run_id", "varchar"),
    )
    selected = [
        "signal_date",
        "stock_code",
        "signal_kind",
        "signal_close",
        "entry_executable",
        *[
            name
            if name in execution_columns
            else f"cast(null as {cast_type}) as {name}"
            for name, cast_type in optional_specs
        ],
    ]
    query = f"""
        with execution_rows as (
          select distinct
            {", ".join(selected)}
          from livermore_candidate_execution_history
          where signal_kind = ?
        ),
        history_rows as (
          select
            snapshot_as_of_date,
            stock_code,
            signal_kind,
            min(ma20) as ma20,
            count(*) as history_source_row_count,
            count(distinct ma20) as ma20_value_count
          from livermore_candidate_history
          where signal_kind = ?
          group by snapshot_as_of_date, stock_code, signal_kind
        )
        select
          e.*,
          h.ma20,
          h.history_source_row_count,
          h.ma20_value_count
        from execution_rows e
        left join history_rows h
          on cast(h.snapshot_as_of_date as date) = cast(e.signal_date as date)
         and h.stock_code = e.stock_code
         and h.signal_kind = e.signal_kind
        order by cast(e.signal_date as date), e.candidate_rank nulls last, e.stock_code
    """
    cursor = conn.execute(query, [signal_kind, signal_kind])
    column_names = [description[0] for description in cursor.description]
    source_rows = [
        dict(zip(column_names, values, strict=True)) for values in cursor.fetchall()
    ]
    rows: list[dict[str, object]] = []
    for source in source_rows:
        signal_date = _date_text(source.get("signal_date"))
        signal_close = _finite_float(source.get("signal_close"))
        ma20 = _finite_float(source.get("ma20"))
        history_count = int(source.get("history_source_row_count") or 0)
        ma20_value_count = int(source.get("ma20_value_count") or 0)
        if history_count == 0:
            feature_status = "missing_history"
        elif ma20_value_count != 1:
            feature_status = "ambiguous_ma20"
        elif signal_close is None or ma20 is None or ma20 <= 0.0:
            feature_status = "missing_or_invalid_price_feature"
        else:
            feature_status = "ready"
        rows.append(
            {
                "signal_date": signal_date,
                "stock_code": str(source.get("stock_code") or ""),
                "stock_name": source.get("stock_name"),
                "signal_kind": source.get("signal_kind"),
                "candidate_rank": int(source.get("candidate_rank") or 0),
                "market_state": source.get("market_state"),
                "signal_close_value": signal_close,
                "signal_sma20_value": ma20,
                "signal_feature_as_of_date": signal_date if history_count else None,
                "signal_feature_status": feature_status,
                "signal_history_count": history_count,
                "entry_date": _date_text(source.get("entry_date")) or None,
                "entry_price_kind": source.get("entry_price_kind"),
                "entry_executable": _as_bool(
                    source.get("entry_executable"), default=False
                ),
                "entry_block_reason": source.get("entry_block_reason") or "",
                "exit_date_5d": _date_text(source.get("exit_date_5d")) or None,
                "exit_date_10d": _date_text(source.get("exit_date_10d")) or None,
                "exit_date_20d": _date_text(source.get("exit_date_20d")) or None,
                "return_5d_net": source.get("return_5d_net"),
                "return_5d_net_adj": source.get("return_5d_net_adj"),
                "return_10d_net": source.get("return_10d_net"),
                "return_10d_net_adj": source.get("return_10d_net_adj"),
                "return_20d_net": source.get("return_20d_net"),
                "return_20d_net_adj": source.get("return_20d_net_adj"),
                "buy_cost_bps": source.get("buy_cost_bps"),
                "sell_cost_bps": source.get("sell_cost_bps"),
                "slippage_bps": source.get("slippage_bps"),
                "price_adjustment_mode": source.get("price_adjustment_mode"),
                "data_status": source.get("data_status"),
                "formula_version": source.get("formula_version"),
                "source_run_id": source.get("run_id"),
            }
        )
    executable_rows = [
        row for row in rows if _as_bool(row.get("entry_executable"), default=False)
    ]
    primary_text_fields = {
        "formula_version": "primary_formula_versions",
        "entry_price_kind": "primary_entry_price_kinds",
        "price_adjustment_mode": "primary_price_adjustment_modes",
    }
    primary_numeric_fields = {
        "buy_cost_bps": "primary_buy_cost_bps_values",
        "sell_cost_bps": "primary_sell_cost_bps_values",
        "slippage_bps": "primary_slippage_bps_values",
    }
    primary_cost_metadata: dict[str, object] = {
        metadata_name: sorted(
            {
                text_value
                for row in executable_rows
                if (text_value := str(row.get(field) or "").strip())
            }
        )
        for field, metadata_name in primary_text_fields.items()
    }
    primary_cost_metadata.update(
        {
            metadata_name: sorted(
                {
                    numeric_value
                    for row in executable_rows
                    if (numeric_value := _finite_float(row.get(field))) is not None
                }
            )
            for field, metadata_name in primary_numeric_fields.items()
        }
    )
    primary_cost_metadata["primary_cost_basis_missing_counts"] = {
        field: sum(
            1
            for row in executable_rows
            if (
                not str(row.get(field) or "").strip()
                if field in primary_text_fields
                else _finite_float(row.get(field)) is None
            )
        )
        for field in (*primary_text_fields, *primary_numeric_fields)
    }
    metadata = {
        "raw_execution_row_count": raw_count,
        "deduplicated_execution_row_count": len(rows),
        "exact_duplicate_row_count": raw_count - len(rows),
        "source_entry_blocked_count": sum(
            1
            for row in rows
            if not _as_bool(row.get("entry_executable"), default=False)
        ),
        "feature_status_counts": dict(
            sorted(Counter(str(row["signal_feature_status"]) for row in rows).items())
        ),
        "data_status_counts": dict(
            sorted(
                Counter(
                    str(row.get("data_status") or "missing") for row in rows
                ).items()
            )
        ),
        "formula_versions": sorted(
            {
                str(row.get("formula_version"))
                for row in rows
                if row.get("formula_version")
            }
        ),
        "source_run_ids": sorted(
            {str(row.get("source_run_id")) for row in rows if row.get("source_run_id")}
        ),
        **primary_cost_metadata,
    }
    return rows, metadata


def load_trading_calendar(conn: duckdb.DuckDBPyConnection) -> list[str]:
    if "choice_stock_daily_observation" not in _table_names(conn):
        raise ValueError("missing required table: choice_stock_daily_observation")
    columns = _columns(conn, "choice_stock_daily_observation")
    required = {"trade_date", "close_value"}
    if not required.issubset(columns):
        missing = ", ".join(sorted(required - columns))
        raise ValueError(f"trading calendar missing columns: {missing}")
    filters = [
        "try_cast(close_value as double) > 0",
        "isfinite(try_cast(close_value as double))",
    ]
    params: list[object] = []
    if "tradestatus" in columns:
        filters.append("lower(trim(cast(tradestatus as varchar))) in (?, ?, ?)")
        params.extend(["trading", "\u4ea4\u6613", "\u6b63\u5e38\u4ea4\u6613"])
    cursor = conn.execute(
        f"""
        select distinct cast(trade_date as date) as trade_date
        from choice_stock_daily_observation
        where {" and ".join(filters)}
        order by trade_date
        """,
        params,
    )
    return [_date_text(row[0]) for row in cursor.fetchall()]


def classify_outcome_maturity(
    *,
    signal_date: str,
    trading_dates: Sequence[str],
    horizon: int,
    adjusted_return: object,
    raw_return: object,
) -> str:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    normalized_dates = sorted(
        {str(value)[:10] for value in trading_dates if str(value).strip()}
    )
    available_forward_dates = len(normalized_dates) - bisect_right(
        normalized_dates,
        str(signal_date)[:10],
    )
    adjusted = _finite_float(adjusted_return)
    raw = _finite_float(raw_return)
    if available_forward_dates < horizon:
        if adjusted is not None or raw is not None:
            raise ValueError("outcome exists before the horizon matures")
        return "natural_pending"
    if adjusted is not None:
        return "complete_adjusted"
    if raw is not None:
        return "matured_adjustment_missing"
    return "matured_missing_bar"


def assign_extension_bin(extension: object) -> str:
    value = _finite_float(extension)
    if value is None:
        return "feature_missing"
    if value < 0.0:
        return "lt_0"
    if value <= 0.05:
        return "0_5"
    if value <= 0.10:
        return "5_10"
    if value <= 0.15:
        return "10_15"
    return "15_plus"


def build_candidate_panel(
    rows: Sequence[Mapping[str, object]],
    *,
    trading_dates: Sequence[str],
    macro_points: Mapping[str, object],
) -> list[dict[str, object]]:
    _assert_unique_candidate_keys(rows)
    panel: list[dict[str, object]] = []
    for source in rows:
        signal_date = str(source.get("signal_date") or source.get("trade_date") or "")[
            :10
        ]
        stock_code = str(source.get("stock_code") or source.get("symbol") or "").strip()
        if not signal_date or not stock_code:
            raise ValueError("signal_date and stock_code are required")
        feature_status = str(source.get("signal_feature_status") or "missing_feature")
        close_value = _finite_float(source.get("signal_close_value"))
        ma20_value = _finite_float(source.get("signal_sma20_value"))
        extension = (
            close_value / ma20_value - 1.0
            if feature_status == "ready"
            and close_value is not None
            and ma20_value is not None
            and ma20_value > 0.0
            else None
        )
        macro_point = macro_points.get(signal_date)
        stored_signal_state = str(source.get("market_state") or "UNKNOWN")
        replayed_signal_state = _point_field(macro_point, "state") or "UNKNOWN"
        replayed_gate_source = _point_field(macro_point, "source") or "missing"
        replayed_gate_state_missing = _replayed_gate_state_is_missing(
            state=replayed_signal_state,
            source=replayed_gate_source,
        )
        source_executable = _as_bool(source.get("entry_executable"), default=False)
        item: dict[str, object] = dict(source)
        item.update(
            {
                "signal_date": signal_date,
                "stock_code": stock_code,
                "source_entry_executable": source_executable,
                "primary_eligible": source_executable,
                "feature_eligible": source_executable and extension is not None,
                "extension": extension,
                "extension_bin": assign_extension_bin(extension),
                "stored_signal_state": stored_signal_state,
                "replayed_signal_state": replayed_signal_state,
                "replayed_gate_source": replayed_gate_source,
                "replayed_gate_state_missing": replayed_gate_state_missing,
                "state_lineage_conflict": bool(
                    not replayed_gate_state_missing
                    and stored_signal_state != "UNKNOWN"
                    and replayed_signal_state != "UNKNOWN"
                    and stored_signal_state != replayed_signal_state
                ),
                "gate_state_as_of_date": signal_date,
            }
        )
        for horizon in (5, 10, 20):
            item[f"maturity_{horizon}d"] = classify_outcome_maturity(
                signal_date=signal_date,
                trading_dates=trading_dates,
                horizon=horizon,
                adjusted_return=source.get(f"return_{horizon}d_net_adj"),
                raw_return=source.get(f"return_{horizon}d_net"),
            )
        panel.append(item)
    return panel


def _summarize_gate_state_cells(
    rows: Sequence[Mapping[str, object]],
    *,
    state_field: str,
    minimum_cell_rows: int,
    minimum_cell_dates: int,
) -> dict[str, dict[str, object]]:
    cells: dict[str, dict[str, object]] = {}
    states = sorted({str(row.get(state_field) or "UNKNOWN") for row in rows})
    for state in states:
        state_payload: dict[str, object] = {}
        for bin_id in EXTENSION_BIN_ORDER:
            cell_rows = [
                row
                for row in rows
                if str(row.get(state_field) or "UNKNOWN") == state
                and row.get("extension_bin") == bin_id
            ]
            matured_rows = [
                row for row in cell_rows if row.get("maturity_20d") != "natural_pending"
            ]
            adjusted_rows = [
                row
                for row in cell_rows
                if row.get("maturity_20d") == "complete_adjusted"
                and _finite_float(row.get("return_20d_net_adj")) is not None
            ]
            stats = _return_stats(
                [
                    value
                    for row in adjusted_rows
                    if (value := _finite_float(row.get("return_20d_net_adj")))
                    is not None
                ]
            )
            candidate_dates = len({str(row.get("signal_date")) for row in cell_rows})
            adjusted_dates = len({str(row.get("signal_date")) for row in adjusted_rows})
            state_payload[bin_id] = {
                "candidate_count": len(cell_rows),
                "candidate_distinct_date_count": candidate_dates,
                "distinct_date_count": adjusted_dates,
                "adjusted_outcome_coverage": _round_optional(
                    len(adjusted_rows) / len(matured_rows) if matured_rows else None
                ),
                "20d_adjusted": stats,
                "interpretation_eligible": bool(
                    _mapping_int(stats, "sample_count") >= minimum_cell_rows
                    and adjusted_dates >= minimum_cell_dates
                ),
            }
        cells[state] = state_payload
    return cells


def _summarize_gate_state_effects(
    rows: Sequence[Mapping[str, object]],
    *,
    state_field: str,
    minimum_cell_rows: int,
    minimum_cell_dates: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
    holdout_train_fraction: float,
) -> dict[str, dict[str, object]]:
    effects: dict[str, dict[str, object]] = {}
    states = sorted({str(row.get(state_field) or "UNKNOWN") for row in rows})
    for state_index, state in enumerate(states):
        state_rows = [
            row for row in rows if str(row.get(state_field) or "UNKNOWN") == state
        ]
        matured_rows = [
            row for row in state_rows if row.get("maturity_20d") != "natural_pending"
        ]
        adjusted_rows = [
            row
            for row in matured_rows
            if _finite_float(row.get("return_20d_net_adj")) is not None
        ]
        raw_rows = [
            row
            for row in matured_rows
            if _finite_float(row.get("return_20d_net")) is not None
        ]
        adjusted_dates = len({str(row.get("signal_date")) for row in adjusted_rows})
        state_seed = bootstrap_seed + state_index * 100
        effects[state] = {
            "candidate_count": len(state_rows),
            "candidate_distinct_date_count": len(
                {str(row.get("signal_date")) for row in state_rows}
            ),
            "adjusted_outcome_coverage": _round_optional(
                len(adjusted_rows) / len(matured_rows) if matured_rows else None
            ),
            "raw_sensitivity_coverage": _round_optional(
                len(raw_rows) / len(matured_rows) if matured_rows else None
            ),
            "interpretation_eligible": bool(
                len(adjusted_rows) >= minimum_cell_rows
                and adjusted_dates >= minimum_cell_dates
            ),
            "20d_adjusted_primary": date_block_bootstrap_effect(
                adjusted_rows,
                outcome_field="return_20d_net_adj",
                iterations=bootstrap_iterations,
                seed=state_seed,
            ),
            "20d_raw_sensitivity": date_block_bootstrap_effect(
                raw_rows,
                outcome_field="return_20d_net",
                iterations=bootstrap_iterations,
                seed=state_seed,
            ),
            "chronological_holdout": chronological_holdout_effect(
                adjusted_rows,
                outcome_field="return_20d_net_adj",
                train_fraction=holdout_train_fraction,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=state_seed,
            ),
            "raw_sensitivity_holdout": chronological_holdout_effect(
                raw_rows,
                outcome_field="return_20d_net",
                train_fraction=holdout_train_fraction,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=state_seed,
            ),
        }
    return effects


def date_block_bootstrap_effect(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_field: str,
    iterations: int,
    seed: int,
) -> dict[str, object]:
    usable: list[tuple[str, float, float]] = []
    for row in rows:
        signal_date = str(row.get("signal_date") or "")[:10]
        extension = _finite_float(row.get("extension"))
        outcome = _finite_float(row.get(outcome_field))
        if signal_date and extension is not None and outcome is not None:
            usable.append((signal_date, extension, outcome))
    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for signal_date, extension, outcome in usable:
        grouped[signal_date].append((extension, outcome))
    dates = sorted(grouped)
    observed = _ols_slope([pair for date_key in dates for pair in grouped[date_key]])
    bootstrap_slopes: list[float] = []
    if observed is not None and iterations > 0 and dates:
        rng = random.Random(seed)
        for _ in range(iterations):
            sampled = [rng.choice(dates) for _ in dates]
            slope = _ols_slope(
                [pair for date_key in sampled for pair in grouped[date_key]]
            )
            if slope is not None:
                bootstrap_slopes.append(slope * 0.10)
    slope_per_10pp = None if observed is None else observed * 0.10
    return {
        "sample_count": len(usable),
        "distinct_date_count": len(dates),
        "slope_per_10pp_extension": _round_optional(slope_per_10pp),
        "bootstrap_ci_95": [
            _round_optional(_percentile(bootstrap_slopes, 0.025)),
            _round_optional(_percentile(bootstrap_slopes, 0.975)),
        ]
        if bootstrap_slopes
        else [None, None],
        "bootstrap_iterations_requested": iterations,
        "bootstrap_iterations_usable": len(bootstrap_slopes),
        "bootstrap_seed": seed,
        "direction": (
            "negative"
            if slope_per_10pp is not None and slope_per_10pp < 0
            else "positive"
            if slope_per_10pp is not None and slope_per_10pp > 0
            else "flat_or_unavailable"
        ),
    }


def summarize_extension_study(
    panel: Sequence[Mapping[str, object]],
    *,
    study_version: str,
    minimum_primary_coverage: float,
    minimum_overall_rows: int,
    minimum_overall_dates: int,
    minimum_bin_rows: int,
    minimum_bin_dates: int,
    minimum_cell_rows: int,
    minimum_cell_dates: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
    holdout_train_fraction: float = 0.70,
) -> dict[str, object]:
    primary = [
        row for row in panel if _as_bool(row.get("primary_eligible"), default=False)
    ]
    horizon_statuses: dict[str, dict[str, int]] = {}
    maturity_order = (
        "complete_adjusted",
        "matured_adjustment_missing",
        "matured_missing_bar",
        "natural_pending",
    )
    for horizon in (5, 10, 20):
        counts = Counter(str(row.get(f"maturity_{horizon}d") or "") for row in primary)
        horizon_statuses[f"{horizon}d"] = {
            status: int(counts.get(status, 0)) for status in maturity_order
        }

    matured_primary = [
        row for row in primary if row.get("maturity_20d") != "natural_pending"
    ]
    adjusted_ready = [
        row
        for row in matured_primary
        if _finite_float(row.get("return_20d_net_adj")) is not None
    ]
    raw_ready = [
        row
        for row in matured_primary
        if _finite_float(row.get("return_20d_net")) is not None
    ]
    analysis_ready = [
        row for row in adjusted_ready if _finite_float(row.get("extension")) is not None
    ]
    raw_analysis_ready = [
        row for row in raw_ready if _finite_float(row.get("extension")) is not None
    ]
    adjusted_coverage = (
        len(adjusted_ready) / len(matured_primary) if matured_primary else None
    )
    raw_coverage = len(raw_ready) / len(matured_primary) if matured_primary else None
    stored_complete_adjustment_missing = [
        row
        for row in matured_primary
        if str(row.get("data_status") or "").strip().lower() == "complete"
        and row.get("maturity_20d") == "matured_adjustment_missing"
    ]
    stored_pending_after_market_maturity = [
        row
        for row in matured_primary
        if str(row.get("data_status") or "").strip().lower() == "pending"
        and _finite_float(row.get("return_20d_net_adj")) is None
    ]
    accounted_incomplete_ids = {
        id(row)
        for row in (
            *stored_complete_adjustment_missing,
            *stored_pending_after_market_maturity,
        )
    }
    other_matured_incomplete = [
        row
        for row in matured_primary
        if _finite_float(row.get("return_20d_net_adj")) is None
        and id(row) not in accounted_incomplete_ids
    ]

    extension_bins: dict[str, dict[str, object]] = {}
    for bin_id in EXTENSION_BIN_ORDER:
        bin_rows = [row for row in primary if row.get("extension_bin") == bin_id]
        bin_matured_rows = [
            row for row in bin_rows if row.get("maturity_20d") != "natural_pending"
        ]
        bin_adjusted_rows = [
            row
            for row in bin_rows
            if row.get("maturity_20d") == "complete_adjusted"
            and _finite_float(row.get("return_20d_net_adj")) is not None
        ]
        bin_payload: dict[str, object] = {
            "candidate_count": len(bin_rows),
            "candidate_distinct_date_count": len(
                {str(row.get("signal_date")) for row in bin_rows}
            ),
            "distinct_date_count": len(
                {str(row.get("signal_date")) for row in bin_adjusted_rows}
            ),
            "adjusted_outcome_coverage": _round_optional(
                len(bin_adjusted_rows) / len(bin_matured_rows)
                if bin_matured_rows
                else None
            ),
            "candidate_share": _round_optional(len(bin_rows) / len(primary))
            if primary
            else None,
        }
        for horizon in (5, 10, 20):
            adjusted_values = [
                float(value)
                for row in bin_rows
                if row.get(f"maturity_{horizon}d") == "complete_adjusted"
                and (value := _finite_float(row.get(f"return_{horizon}d_net_adj")))
                is not None
            ]
            raw_values = [
                float(value)
                for row in bin_rows
                if row.get(f"maturity_{horizon}d") != "natural_pending"
                and (value := _finite_float(row.get(f"return_{horizon}d_net")))
                is not None
            ]
            bin_payload[f"{horizon}d_adjusted"] = _return_stats(adjusted_values)
            bin_payload[f"{horizon}d_raw_sensitivity"] = _return_stats(raw_values)
        primary_stats = bin_payload.get("20d_adjusted")
        primary_count = (
            int(primary_stats.get("sample_count") or 0)
            if isinstance(primary_stats, Mapping)
            else 0
        )
        bin_payload["interpretation_eligible"] = bool(
            primary_count >= minimum_bin_rows
            and _mapping_int(bin_payload, "distinct_date_count") >= minimum_bin_dates
        )
        extension_bins[bin_id] = bin_payload

    state_fields = (
        ("stored_signal_state", "stored_signal_state"),
        ("replayed_signal_state", "replayed_signal_state"),
    )
    gate_state_cells = {
        state_basis: _summarize_gate_state_cells(
            primary,
            state_field=state_field,
            minimum_cell_rows=minimum_cell_rows,
            minimum_cell_dates=minimum_cell_dates,
        )
        for state_basis, state_field in state_fields
    }
    gate_state_effects = {
        state_basis: _summarize_gate_state_effects(
            primary,
            state_field=state_field,
            minimum_cell_rows=minimum_cell_rows,
            minimum_cell_dates=minimum_cell_dates,
            bootstrap_iterations=bootstrap_iterations,
            bootstrap_seed=bootstrap_seed,
            holdout_train_fraction=holdout_train_fraction,
        )
        for state_basis, state_field in state_fields
    }
    state_conflict_count = sum(
        1
        for row in primary
        if _as_bool(row.get("state_lineage_conflict"), default=False)
    )
    stored_unknown_count = sum(
        1
        for row in primary
        if str(row.get("stored_signal_state") or "UNKNOWN") == "UNKNOWN"
    )
    replayed_unknown_count = sum(
        1
        for row in primary
        if str(row.get("replayed_signal_state") or "UNKNOWN") == "UNKNOWN"
    )
    replayed_no_data_count = sum(
        1
        for row in primary
        if str(row.get("replayed_signal_state") or "UNKNOWN") == "NO_DATA"
    )
    replayed_missing_count = sum(
        1
        for row in primary
        if _replayed_gate_state_is_missing(
            state=row.get("replayed_signal_state"),
            source=row.get("replayed_gate_source"),
        )
    )
    adjusted_effect = date_block_bootstrap_effect(
        analysis_ready,
        outcome_field="return_20d_net_adj",
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    raw_effect = date_block_bootstrap_effect(
        raw_analysis_ready,
        outcome_field="return_20d_net",
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    adjusted_holdout = chronological_holdout_effect(
        analysis_ready,
        outcome_field="return_20d_net_adj",
        train_fraction=holdout_train_fraction,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    raw_holdout = chronological_holdout_effect(
        raw_analysis_ready,
        outcome_field="return_20d_net",
        train_fraction=holdout_train_fraction,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    monotonicity = assess_bin_monotonicity(extension_bins)
    overall_dates = len({str(row.get("signal_date")) for row in analysis_ready})
    quality_blocked = (
        adjusted_coverage is None or adjusted_coverage < minimum_primary_coverage
    )
    sample_adequate = (
        len(analysis_ready) >= minimum_overall_rows
        and overall_dates >= minimum_overall_dates
    )
    blockers: list[str] = []
    if quality_blocked:
        blockers.append("primary_adjusted_coverage_below_gate")
    if not sample_adequate:
        blockers.append("primary_sample_below_gate")
    if replayed_missing_count:
        blockers.append("replayed_gate_state_missing")

    return {
        "status": "research_only_data_quality_blocked"
        if quality_blocked
        else "research_only",
        "research_only": True,
        "formal_use_allowed": False,
        "actionable": False,
        "study_version": study_version,
        "promotion_verdict": "insufficient_evidence"
        if blockers
        else "research_only_review_required",
        "promotion_blockers": blockers,
        "sample_accountability": {
            "source_row_count": len(panel),
            "primary_universe_row_count": len(primary),
            "source_blocked_row_count": len(panel) - len(primary),
            "feature_missing_row_count": sum(
                1 for row in primary if row.get("extension_bin") == "feature_missing"
            ),
            "stored_gate_state_missing_row_count": stored_unknown_count,
            "replayed_gate_state_missing_row_count": replayed_missing_count,
            "distinct_signal_date_count": len(
                {str(row.get("signal_date")) for row in primary}
            ),
            "horizons": horizon_statuses,
            "materialization_20d": {
                "adjusted_outcome_ready": len(adjusted_ready),
                "stored_complete_adjustment_missing": len(
                    stored_complete_adjustment_missing
                ),
                "stored_pending_after_market_maturity": len(
                    stored_pending_after_market_maturity
                ),
                "other_matured_incomplete": len(other_matured_incomplete),
            },
            "primary_adjusted_coverage": _round_optional(adjusted_coverage),
            "raw_sensitivity_coverage": _round_optional(raw_coverage),
        },
        "extension_bins": extension_bins,
        "state_lineage": {
            "conflict_count": state_conflict_count,
            "conflict_rate": _round_optional(
                state_conflict_count / len(primary) if primary else None
            ),
            "stored_unknown_count": stored_unknown_count,
            "replayed_unknown_count": replayed_unknown_count,
            "replayed_no_data_count": replayed_no_data_count,
            "replayed_missing_count": replayed_missing_count,
            "replayed_source_counts": dict(
                sorted(
                    Counter(
                        str(row.get("replayed_gate_source") or "missing")
                        for row in primary
                    ).items()
                )
            ),
        },
        "gate_state_extension_cells": gate_state_cells,
        "gate_state_effects": gate_state_effects,
        "continuous_effect": {
            "20d_adjusted_primary": adjusted_effect,
            "20d_raw_sensitivity": raw_effect,
        },
        "monotonicity": monotonicity,
        "chronological_holdout": {
            "20d_adjusted_primary": adjusted_holdout,
            "20d_raw_sensitivity": raw_holdout,
        },
        "sample_adequacy": {
            "primary_adjusted_row_count": len(adjusted_ready),
            "primary_adjusted_distinct_date_count": len(
                {str(row.get("signal_date")) for row in adjusted_ready}
            ),
            "primary_analysis_ready_row_count": len(analysis_ready),
            "primary_analysis_ready_distinct_date_count": overall_dates,
            "minimum_overall_rows": minimum_overall_rows,
            "minimum_overall_dates": minimum_overall_dates,
            "adequate": sample_adequate,
        },
    }


def evaluate_promotion_gates(
    summary: Mapping[str, object],
    *,
    panel: Sequence[Mapping[str, object]],
    contract: Mapping[str, object],
    source_metadata: Mapping[str, object],
) -> dict[str, object]:
    evaluated = dict(summary)
    primary = [
        row for row in panel if _as_bool(row.get("primary_eligible"), default=False)
    ]
    primary_count = len(primary)
    promotion = _required_mapping(contract, "promotion")
    floor = _finite_float(promotion.get("candidate_retention_floor"))
    if floor is None or not 0.0 <= floor <= 1.0:
        raise ValueError("candidate_retention_floor must be between zero and one")

    fixed_bin_lenses: dict[str, dict[str, object]] = {}
    for bin_id in EXTENSION_BIN_ORDER:
        excluded_count = sum(1 for row in primary if row.get("extension_bin") == bin_id)
        retained_count = primary_count - excluded_count
        retained_share = retained_count / primary_count if primary_count else None
        fixed_bin_lenses[bin_id] = {
            "excluded_candidate_count": excluded_count,
            "retained_candidate_count": retained_count,
            "retained_candidate_share": _round_optional(retained_share),
            "candidate_retention_floor": floor,
            "retention_floor_passed": bool(
                retained_share is not None and retained_share >= floor
            ),
        }

    state_bin_lenses: dict[str, dict[str, object]] = {}
    for state_basis in ("stored_signal_state", "replayed_signal_state"):
        basis_lenses: dict[str, object] = {}
        states = sorted({str(row.get(state_basis) or "UNKNOWN") for row in primary})
        for state in states:
            state_payload: dict[str, object] = {}
            for bin_id in EXTENSION_BIN_ORDER:
                excluded_count = sum(
                    1
                    for row in primary
                    if str(row.get(state_basis) or "UNKNOWN") == state
                    and row.get("extension_bin") == bin_id
                )
                retained_count = primary_count - excluded_count
                retained_share = (
                    retained_count / primary_count if primary_count else None
                )
                state_payload[bin_id] = {
                    "excluded_candidate_count": excluded_count,
                    "retained_candidate_count": retained_count,
                    "retained_candidate_share": _round_optional(retained_share),
                    "candidate_retention_floor": floor,
                    "retention_floor_passed": bool(
                        retained_share is not None and retained_share >= floor
                    ),
                }
            basis_lenses[state] = state_payload
        state_bin_lenses[state_basis] = basis_lenses

    accountability = summary.get("sample_accountability")
    accountability = accountability if isinstance(accountability, Mapping) else {}
    sample_adequacy = summary.get("sample_adequacy")
    sample_adequacy = sample_adequacy if isinstance(sample_adequacy, Mapping) else {}
    effects = summary.get("continuous_effect")
    effects = effects if isinstance(effects, Mapping) else {}
    primary_effect = effects.get("20d_adjusted_primary")
    primary_effect = primary_effect if isinstance(primary_effect, Mapping) else {}
    ci = primary_effect.get("bootstrap_ci_95")
    ci_values = list(ci) if isinstance(ci, Sequence) and not isinstance(ci, str) else []
    ci_low = _finite_float(ci_values[0]) if len(ci_values) == 2 else None
    ci_high = _finite_float(ci_values[1]) if len(ci_values) == 2 else None
    slope = _finite_float(primary_effect.get("slope_per_10pp_extension"))

    holdouts = summary.get("chronological_holdout")
    holdouts = holdouts if isinstance(holdouts, Mapping) else {}
    primary_holdout = holdouts.get("20d_adjusted_primary")
    primary_holdout = primary_holdout if isinstance(primary_holdout, Mapping) else {}
    discovery = primary_holdout.get("discovery")
    discovery = discovery if isinstance(discovery, Mapping) else {}
    discovery_effect = discovery.get("effect")
    discovery_effect = discovery_effect if isinstance(discovery_effect, Mapping) else {}
    holdout = primary_holdout.get("holdout")
    holdout = holdout if isinstance(holdout, Mapping) else {}
    holdout_effect = holdout.get("effect")
    holdout_effect = holdout_effect if isinstance(holdout_effect, Mapping) else {}
    negative_holdout_consistent = bool(
        primary_holdout.get("direction_consistent") is True
        and discovery_effect.get("direction") == "negative"
        and holdout_effect.get("direction") == "negative"
    )

    monotonicity = summary.get("monotonicity")
    monotonicity = monotonicity if isinstance(monotonicity, Mapping) else {}
    lineage = summary.get("state_lineage")
    lineage = lineage if isinstance(lineage, Mapping) else {}
    endpoint = _required_mapping(contract, "primary_endpoint")
    formula_versions = _metadata_text_values(
        source_metadata.get("primary_formula_versions")
    )
    entry_price_kinds = _metadata_text_values(
        source_metadata.get("primary_entry_price_kinds")
    )
    adjustment_modes = _metadata_text_values(
        source_metadata.get("primary_price_adjustment_modes")
    )
    buy_costs = _metadata_number_values(
        source_metadata.get("primary_buy_cost_bps_values")
    )
    sell_costs = _metadata_number_values(
        source_metadata.get("primary_sell_cost_bps_values")
    )
    slippage_costs = _metadata_number_values(
        source_metadata.get("primary_slippage_bps_values")
    )
    missing_cost_fields = source_metadata.get("primary_cost_basis_missing_counts")
    missing_cost_fields = (
        missing_cost_fields if isinstance(missing_cost_fields, Mapping) else {}
    )
    required_cost_fields = {
        "formula_version",
        "entry_price_kind",
        "price_adjustment_mode",
        "buy_cost_bps",
        "sell_cost_bps",
        "slippage_bps",
    }
    cost_fields_complete = bool(
        required_cost_fields.issubset(missing_cost_fields)
        and all(
            int(missing_cost_fields[field] or 0) == 0 for field in required_cost_fields
        )
    )
    endpoint_basis = str(endpoint.get("basis") or "")
    allowed_adjustment_modes = PRIMARY_BASIS_ADJUSTMENT_MODE_ALLOWLIST.get(
        endpoint_basis,
        frozenset(),
    )
    adjustment_mode_compatible = bool(
        len(adjustment_modes) == 1 and adjustment_modes[0] in allowed_adjustment_modes
    )
    cost_basis_comparable = bool(
        endpoint.get("field") == "return_20d_net_adj"
        and endpoint_basis == "net_next_open_adjusted"
        and len(set(formula_versions)) == 1
        and entry_price_kinds == ["next_open"]
        and adjustment_mode_compatible
        and len(set(buy_costs)) == 1
        and len(set(sell_costs)) == 1
        and len(set(slippage_costs)) == 1
        and cost_fields_complete
    )
    coverage = _finite_float(accountability.get("primary_adjusted_coverage"))
    minimum_coverage = _finite_float(
        _required_mapping(contract, "sample_gates").get("minimum_primary_coverage")
    )
    coverage_passed = bool(
        coverage is not None
        and minimum_coverage is not None
        and coverage >= minimum_coverage
    )
    effect_passed = bool(
        slope is not None
        and slope < 0.0
        and ci_low is not None
        and ci_high is not None
        and ci_high < 0.0
    )
    lineage_passed = int(lineage.get("conflict_count") or 0) == 0
    retention_passed = bool(fixed_bin_lenses["15_plus"]["retention_floor_passed"])
    hard_rule_allowed = promotion.get("hard_rule_allowed") is True

    gate_evaluation: dict[str, dict[str, object]] = {
        "primary_adjusted_coverage": {
            "passed": coverage_passed,
            "observed": coverage,
            "minimum": minimum_coverage,
        },
        "overall_sample_adequacy": {
            "passed": sample_adequacy.get("adequate") is True,
        },
        "primary_extension_effect_strictly_negative": {
            "passed": effect_passed,
            "slope_per_10pp_extension": slope,
            "bootstrap_ci_95": [ci_low, ci_high],
        },
        "chronological_holdout_direction_consistency": {
            "passed": primary_holdout.get("direction_consistent") is True,
            "direction_consistent": primary_holdout.get("direction_consistent"),
        },
        "chronological_holdout_negative_consistency": {
            "passed": negative_holdout_consistent,
            "discovery_direction": discovery_effect.get("direction"),
            "holdout_direction": holdout_effect.get("direction"),
        },
        "extension_bin_relation_not_inconclusive": {
            "passed": monotonicity.get("assessment") not in {None, "inconclusive"},
            "assessment": monotonicity.get("assessment"),
        },
        "extension_bin_monotonic_deterioration": {
            "passed": monotonicity.get("assessment") == "deteriorating",
            "assessment": monotonicity.get("assessment"),
        },
        "gate_state_lineage_consistency": {
            "passed": lineage_passed,
            "conflict_count": int(lineage.get("conflict_count") or 0),
            "conflict_rate": lineage.get("conflict_rate"),
        },
        "cost_basis_comparable": {
            "passed": cost_basis_comparable,
            "endpoint_field": endpoint.get("field"),
            "endpoint_basis": endpoint.get("basis"),
            "formula_versions": formula_versions,
            "entry_price_kinds": entry_price_kinds,
            "price_adjustment_modes": adjustment_modes,
            "allowed_price_adjustment_modes": sorted(allowed_adjustment_modes),
            "price_adjustment_mode_compatible": adjustment_mode_compatible,
            "buy_cost_bps_values": buy_costs,
            "sell_cost_bps_values": sell_costs,
            "slippage_bps_values": slippage_costs,
            "missing_counts": dict(missing_cost_fields),
        },
        "fixed_15_plus_candidate_retention": {
            "passed": retention_passed,
            **fixed_bin_lenses["15_plus"],
        },
        "contract_hard_rule_permission": {
            "passed": hard_rule_allowed,
            "hard_rule_allowed": promotion.get("hard_rule_allowed"),
        },
    }
    blocker_by_gate = {
        "primary_adjusted_coverage": "primary_adjusted_coverage_below_gate",
        "overall_sample_adequacy": "primary_sample_below_gate",
        "primary_extension_effect_strictly_negative": (
            "primary_extension_effect_ci_not_strictly_negative"
        ),
        "chronological_holdout_direction_consistency": (
            "chronological_holdout_not_negative_consistent"
        ),
        "chronological_holdout_negative_consistency": (
            "chronological_holdout_not_negative_consistent"
        ),
        "extension_bin_relation_not_inconclusive": (
            "extension_bin_relation_inconclusive"
        ),
        "extension_bin_monotonic_deterioration": (
            "extension_bins_not_monotonic_deteriorating"
        ),
        "gate_state_lineage_consistency": "gate_state_lineage_conflict",
        "cost_basis_comparable": "cost_basis_comparability_not_verified",
        "fixed_15_plus_candidate_retention": "fixed_15_plus_retention_below_floor",
        "contract_hard_rule_permission": "contract_hard_rule_promotion_prohibited",
    }
    required_evidence = promotion.get("required_evidence")
    if not isinstance(required_evidence, list) or not required_evidence:
        raise ValueError("promotion required_evidence must be a non-empty list")
    contract_required_evidence: dict[str, dict[str, object]] = {}
    for evidence_name in (str(value) for value in required_evidence):
        runtime_gate = CONTRACT_EVIDENCE_TO_RUNTIME_GATE.get(evidence_name)
        if runtime_gate is None:
            raise ValueError(
                f"unsupported promotion required_evidence: {evidence_name}"
            )
        contract_required_evidence[evidence_name] = {
            "runtime_gate": runtime_gate,
            "passed": gate_evaluation[runtime_gate].get("passed") is True,
        }

    raw_blockers = summary.get("promotion_blockers")
    raw_blockers = (
        raw_blockers
        if isinstance(raw_blockers, Sequence) and not isinstance(raw_blockers, str)
        else []
    )
    blockers = {str(value) for value in raw_blockers if str(value)}
    for gate_name, payload in gate_evaluation.items():
        if payload.get("passed") is not True:
            blockers.add(blocker_by_gate[gate_name])

    evaluated.update(
        {
            "promotion_verdict": (
                "insufficient_evidence" if blockers else "research_only_review_required"
            ),
            "promotion_blockers": sorted(blockers),
            "promotion_gate_evaluation": gate_evaluation,
            "contract_required_evidence": contract_required_evidence,
            "retention_lenses": {
                "fixed_extension_bin_exclusions": fixed_bin_lenses,
                "gate_state_bin_exclusions": state_bin_lenses,
            },
        }
    )
    if blockers and evaluated.get("status") == "research_only":
        evaluated["status"] = "research_only_evidence_blocked"
    return evaluated


def run_extension_study_from_duckdb(
    *,
    db_path: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT_PATH,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    run_id: str,
    signal_kind: str = "stock_candidate",
) -> dict[str, object]:
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(db_file)
    contract_file = Path(contract_path)
    contract = load_study_contract(contract_file)
    expected_signal_kind = str(
        _required_mapping(contract, "primary_universe").get("signal_kind") or ""
    )
    if signal_kind != expected_signal_kind:
        raise ValueError(
            f"signal_kind {signal_kind!r} does not match frozen contract {expected_signal_kind!r}"
        )

    with read_only_connection(str(db_file)) as conn:
        rows, loader_metadata = load_extension_study_rows(
            conn,
            signal_kind=signal_kind,
        )
        if not rows:
            raise ValueError("no execution rows matched the frozen study universe")
        _assert_unique_candidate_keys(rows)
        trading_dates = load_trading_calendar(conn)
        if not trading_dates:
            raise ValueError("valid trading calendar is empty")
        signal_dates = sorted({str(row.get("signal_date") or "")[:10] for row in rows})
        macro_points = load_gate_exposure_by_date(
            conn,
            signal_dates[0],
            signal_dates[-1],
        )

    point_source_counts = Counter(
        _point_field(point, "source") or "missing" for point in macro_points.values()
    )
    source_metadata = {
        **loader_metadata,
        "db_path": str(db_file.resolve()),
        "db_sha256": _sha256_file(db_file),
        "contract_path": str(contract_file.resolve()),
        "contract_file_sha256": _sha256_file(contract_file),
        "calendar_start_date": trading_dates[0],
        "calendar_end_date": trading_dates[-1],
        "calendar_date_count": len(trading_dates),
        "evaluation_as_of_date": trading_dates[-1],
        "gate_point_source_counts": dict(sorted(point_source_counts.items())),
        "gate_taxonomy": "livermore_market_gate_not_hason_macro_cycle",
        "database_access": "read_only",
    }
    return run_extension_study_from_inputs(
        rows=rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
        contract=contract,
        source_metadata=source_metadata,
        output_root=output_root,
        run_id=run_id,
    )


def run_extension_study_from_inputs(
    *,
    rows: Sequence[Mapping[str, object]],
    trading_dates: Sequence[str],
    macro_points: Mapping[str, object],
    contract: Mapping[str, object],
    source_metadata: Mapping[str, object],
    output_root: str | Path,
    run_id: str,
) -> dict[str, object]:
    normalized_run_id = _validate_run_id(run_id)
    if contract.get("research_only") is not True:
        raise ValueError("research_only must remain true")
    if contract.get("formal_use_allowed") is not False:
        raise ValueError("formal_use_allowed must remain false")
    if contract.get("actionable") is not False:
        raise ValueError("actionable must remain false")
    _assert_unique_candidate_keys(rows)
    panel = build_candidate_panel(
        rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
    )
    panel = sorted(
        panel,
        key=lambda row: (
            str(row.get("signal_date") or ""),
            _mapping_int(row, "candidate_rank", default=0),
            str(row.get("stock_code") or ""),
        ),
    )
    gates = _required_mapping(contract, "sample_gates")
    inference = _required_mapping(contract, "inference")
    summary = summarize_extension_study(
        panel,
        study_version=str(contract.get("study_version") or ""),
        minimum_primary_coverage=_mapping_float(gates, "minimum_primary_coverage"),
        minimum_overall_rows=_mapping_int(gates, "minimum_overall_rows"),
        minimum_overall_dates=_mapping_int(gates, "minimum_overall_dates"),
        minimum_bin_rows=_mapping_int(gates, "minimum_bin_rows"),
        minimum_bin_dates=_mapping_int(gates, "minimum_bin_dates"),
        minimum_cell_rows=_mapping_int(gates, "minimum_cell_rows"),
        minimum_cell_dates=_mapping_int(gates, "minimum_cell_dates"),
        bootstrap_iterations=_mapping_int(inference, "bootstrap_iterations"),
        bootstrap_seed=_mapping_int(inference, "bootstrap_seed"),
        holdout_train_fraction=_mapping_float(inference, "holdout_train_fraction"),
    )
    summary = {
        **summary,
        "source_metadata": dict(source_metadata),
        "contract_boundary": {
            "primary_feature": contract.get("primary_feature"),
            "primary_endpoint": contract.get("primary_endpoint"),
            "sensitivity_endpoint": contract.get("sensitivity_endpoint"),
            "promotion": contract.get("promotion"),
        },
    }
    summary = evaluate_promotion_gates(
        summary,
        panel=panel,
        contract=contract,
        source_metadata=source_metadata,
    )
    stable_source_metadata = {
        key: value
        for key, value in source_metadata.items()
        if key not in LOCAL_SOURCE_METADATA_FIELDS
    }
    stable_summary = dict(summary)
    stable_summary["source_metadata"] = stable_source_metadata
    result_sha256 = _stable_hash(
        {
            "contract": contract,
            "source_metadata": stable_source_metadata,
            "trading_dates": sorted({str(value)[:10] for value in trading_dates}),
            "macro_points": {
                str(key)[:10]: {
                    "state": _point_field(value, "state") or "UNKNOWN",
                    "source": _point_field(value, "source") or "missing",
                }
                for key, value in sorted(macro_points.items())
            },
            "panel": panel,
            "summary": stable_summary,
        }
    )
    manifest = {
        "run_id": normalized_run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "research_only": True,
        "formal_use_allowed": False,
        "actionable": False,
        "analysis_kind": "ma20_extension_gate_state_interaction_study",
        "study_version": contract.get("study_version"),
        "result_sha256": result_sha256,
        "contract_sha256": _stable_hash(contract),
        "script_path": Path(__file__).resolve().relative_to(ROOT.resolve()).as_posix(),
        "script_sha256": _sha256_file(Path(__file__).resolve()),
        "source_row_fingerprint_sha256": _stable_hash(rows),
        "trading_calendar_fingerprint_sha256": _stable_hash(
            sorted({str(value)[:10] for value in trading_dates})
        ),
        "gate_state_fingerprint_sha256": _stable_hash(
            {
                str(key)[:10]: {
                    "state": _point_field(value, "state") or "UNKNOWN",
                    "source": _point_field(value, "source") or "missing",
                }
                for key, value in sorted(macro_points.items())
            }
        ),
        "source_metadata": dict(source_metadata),
    }
    run_dir = _write_extension_artifacts(
        output_root=output_root,
        run_id=normalized_run_id,
        panel=panel,
        summary=summary,
        manifest=manifest,
    )
    return {
        "run_dir": str(run_dir),
        "result_sha256": result_sha256,
        "summary": summary,
    }


def _write_extension_artifacts(
    *,
    output_root: str | Path,
    run_id: str,
    panel: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    manifest: Mapping[str, object],
) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / run_id
    run_dir.mkdir(exist_ok=False)

    _write_json(run_dir / "study_summary.json", summary)
    _write_json(run_dir / "run_manifest.json", manifest)
    _write_csv(
        run_dir / "candidate_panel.csv",
        fieldnames=PANEL_FIELDS,
        rows=[{field: row.get(field) for field in PANEL_FIELDS} for row in panel],
    )

    extension_rows: list[dict[str, object]] = []
    extension_bins = summary.get("extension_bins")
    if isinstance(extension_bins, Mapping):
        for bin_id in EXTENSION_BIN_ORDER:
            payload = extension_bins.get(bin_id)
            if not isinstance(payload, Mapping):
                continue
            record: dict[str, object] = {
                "extension_bin": bin_id,
                "candidate_count": payload.get("candidate_count"),
                "candidate_distinct_date_count": payload.get(
                    "candidate_distinct_date_count"
                ),
                "distinct_date_count": payload.get("distinct_date_count"),
                "adjusted_outcome_coverage": payload.get("adjusted_outcome_coverage"),
                "candidate_share": payload.get("candidate_share"),
                "interpretation_eligible": payload.get("interpretation_eligible"),
            }
            for horizon in (5, 10, 20):
                for basis in ("adjusted", "raw_sensitivity"):
                    stats = payload.get(f"{horizon}d_{basis}")
                    if not isinstance(stats, Mapping):
                        continue
                    for metric in (
                        "sample_count",
                        "mean_return",
                        "median_return",
                        "win_rate",
                    ):
                        record[f"{horizon}d_{basis}_{metric}"] = stats.get(metric)
            extension_rows.append(record)
    extension_fields = (
        tuple(extension_rows[0]) if extension_rows else ("extension_bin",)
    )
    _write_csv(
        run_dir / "extension_bins.csv",
        fieldnames=extension_fields,
        rows=extension_rows,
    )

    state_rows: list[dict[str, object]] = []
    state_tables = summary.get("gate_state_extension_cells")
    if isinstance(state_tables, Mapping):
        for state_basis, table in sorted(state_tables.items()):
            if not isinstance(table, Mapping):
                continue
            for state, bins in sorted(table.items()):
                if not isinstance(bins, Mapping):
                    continue
                for bin_id in EXTENSION_BIN_ORDER:
                    cell = bins.get(bin_id)
                    if not isinstance(cell, Mapping):
                        continue
                    stats = cell.get("20d_adjusted")
                    stats = stats if isinstance(stats, Mapping) else {}
                    state_rows.append(
                        {
                            "state_basis": state_basis,
                            "state": state,
                            "extension_bin": bin_id,
                            "candidate_count": cell.get("candidate_count"),
                            "candidate_distinct_date_count": cell.get(
                                "candidate_distinct_date_count"
                            ),
                            "distinct_date_count": cell.get("distinct_date_count"),
                            "adjusted_outcome_coverage": cell.get(
                                "adjusted_outcome_coverage"
                            ),
                            "adjusted_sample_count": stats.get("sample_count"),
                            "adjusted_mean_return": stats.get("mean_return"),
                            "adjusted_median_return": stats.get("median_return"),
                            "adjusted_win_rate": stats.get("win_rate"),
                            "interpretation_eligible": cell.get(
                                "interpretation_eligible"
                            ),
                        }
                    )
    state_fields = (
        "state_basis",
        "state",
        "extension_bin",
        "candidate_count",
        "candidate_distinct_date_count",
        "distinct_date_count",
        "adjusted_outcome_coverage",
        "adjusted_sample_count",
        "adjusted_mean_return",
        "adjusted_median_return",
        "adjusted_win_rate",
        "interpretation_eligible",
    )
    _write_csv(
        run_dir / "gate_state_extension_cells.csv",
        fieldnames=state_fields,
        rows=state_rows,
    )

    accountability = summary.get("sample_accountability")
    accountability_rows = [
        {"metric": key, "value": value}
        for key, value in _flatten_mapping(accountability).items()
    ]
    _write_csv(
        run_dir / "sample_accountability.csv",
        fieldnames=("metric", "value"),
        rows=accountability_rows,
    )
    (run_dir / "README.md").write_text(
        _render_extension_readme(summary=summary, manifest=manifest),
        encoding="utf-8",
    )
    return run_dir


def _render_extension_readme(
    *,
    summary: Mapping[str, object],
    manifest: Mapping[str, object],
) -> str:
    accountability = summary.get("sample_accountability")
    accountability = accountability if isinstance(accountability, Mapping) else {}
    effects = summary.get("continuous_effect")
    effects = effects if isinstance(effects, Mapping) else {}
    primary_effect = effects.get("20d_adjusted_primary")
    primary_effect = primary_effect if isinstance(primary_effect, Mapping) else {}
    holdouts = summary.get("chronological_holdout")
    holdouts = holdouts if isinstance(holdouts, Mapping) else {}
    primary_holdout = holdouts.get("20d_adjusted_primary")
    primary_holdout = primary_holdout if isinstance(primary_holdout, Mapping) else {}
    lineage = summary.get("state_lineage")
    lineage = lineage if isinstance(lineage, Mapping) else {}
    blockers = summary.get("promotion_blockers")
    blocker_text = (
        ", ".join(str(value) for value in blockers)
        if isinstance(blockers, list)
        else ""
    )
    holdout_consistent = _as_bool(
        primary_holdout.get("direction_consistent"), default=False
    )
    return "\n".join(
        [
            "# Fable MA20 extension research study",
            "",
            f"- status: {summary.get('status')}",
            f"- promotion_verdict: {summary.get('promotion_verdict')}",
            f"- promotion_blockers: {blocker_text or 'none'}",
            f"- study_version: {manifest.get('study_version')}",
            f"- result_sha256: {manifest.get('result_sha256')}",
            "- research_only: true",
            "- formal_use_allowed: false",
            "- actionable: false",
            "",
            "## Decision-relevant findings",
            "",
            f"- primary_universe_row_count: {accountability.get('primary_universe_row_count')}",
            f"- primary_adjusted_coverage: {accountability.get('primary_adjusted_coverage')}",
            f"- slope_per_10pp_extension: {primary_effect.get('slope_per_10pp_extension')}",
            f"- bootstrap_ci_95: {primary_effect.get('bootstrap_ci_95')}",
            f"- holdout_direction_consistent: {str(holdout_consistent).lower()}",
            f"- state_lineage_conflict_count: {lineage.get('conflict_count')}",
            f"- state_lineage_conflict_rate: {lineage.get('conflict_rate')}",
            "",
            "A threshold is not supported when the adjusted-outcome coverage gate fails,",
            "the confidence interval includes zero, or the chronological holdout changes",
            "direction. State interactions remain diagnostic while state lineages conflict.",
            "",
            "## Boundary",
            "",
            "The primary endpoint is 20-session adjusted net return. The unadjusted",
            "20-session net return is sensitivity evidence only and never replaces a",
            "missing adjusted outcome.",
            "",
            "State tables describe the Livermore market gate, not the Hason macro-cycle",
            "taxonomy. Stored signal-date state and current-rule replay are reported",
            "separately because their lineage can conflict.",
            "",
            "This run does not produce allocation, position-change, trading, or execution",
            "instructions. Any strategy promotion requires a separate governed review.",
            "",
        ]
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    *,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _flatten_mapping(value: object, *, prefix: str = "") -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {prefix or "value": value}
    flattened: dict[str, object] = {}
    for key, item in sorted(value.items()):
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            flattened.update(_flatten_mapping(item, prefix=path))
        else:
            flattened[path] = item
    return flattened


def chronological_holdout_effect(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_field: str,
    train_fraction: float,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between zero and one")
    usable = [
        row
        for row in rows
        if str(row.get("signal_date") or "")[:10]
        and _finite_float(row.get("extension")) is not None
        and _finite_float(row.get(outcome_field)) is not None
    ]
    dates = sorted({str(row.get("signal_date"))[:10] for row in usable})
    if len(dates) < 2:
        return {
            "status": "insufficient_dates",
            "train_fraction": train_fraction,
            "discovery": _empty_holdout_segment(),
            "holdout": _empty_holdout_segment(),
            "direction_consistent": False,
        }
    split_index = min(max(int(len(dates) * train_fraction), 1), len(dates) - 1)
    discovery_dates = set(dates[:split_index])
    holdout_dates = set(dates[split_index:])
    discovery_rows = [
        row for row in usable if str(row.get("signal_date"))[:10] in discovery_dates
    ]
    holdout_rows = [
        row for row in usable if str(row.get("signal_date"))[:10] in holdout_dates
    ]
    discovery_effect = date_block_bootstrap_effect(
        discovery_rows,
        outcome_field=outcome_field,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    holdout_effect = date_block_bootstrap_effect(
        holdout_rows,
        outcome_field=outcome_field,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed + 1,
    )
    discovery_direction = str(discovery_effect.get("direction"))
    holdout_direction = str(holdout_effect.get("direction"))
    return {
        "status": "ready",
        "train_fraction": train_fraction,
        "split_date": dates[split_index],
        "discovery": {
            "start_date": dates[0],
            "end_date": dates[split_index - 1],
            "date_count": len(discovery_dates),
            "effect": discovery_effect,
        },
        "holdout": {
            "start_date": dates[split_index],
            "end_date": dates[-1],
            "date_count": len(holdout_dates),
            "effect": holdout_effect,
        },
        "direction_consistent": bool(
            discovery_direction in {"negative", "positive"}
            and discovery_direction == holdout_direction
        ),
    }


def assess_bin_monotonicity(
    extension_bins: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    eligible_bins: list[str] = []
    means: list[float] = []
    for bin_id in EXTENSION_BIN_ORDER:
        payload = extension_bins.get(bin_id)
        if (
            not isinstance(payload, Mapping)
            or payload.get("interpretation_eligible") is not True
        ):
            continue
        stats = payload.get("20d_adjusted")
        mean_return = (
            _finite_float(stats.get("mean_return"))
            if isinstance(stats, Mapping)
            else None
        )
        if mean_return is None:
            continue
        eligible_bins.append(bin_id)
        means.append(mean_return)
    if len(means) < 3:
        assessment = "inconclusive"
    elif all(right <= left for left, right in zip(means, means[1:], strict=False)):
        assessment = (
            "deteriorating"
            if any(right < left for left, right in zip(means, means[1:], strict=False))
            else "flat"
        )
    elif all(right >= left for left, right in zip(means, means[1:], strict=False)):
        assessment = (
            "improving"
            if any(right > left for left, right in zip(means, means[1:], strict=False))
            else "flat"
        )
    else:
        assessment = "non_monotonic"
    return {
        "assessment": assessment,
        "eligible_bin_count": len(eligible_bins),
        "eligible_bins": eligible_bins,
    }


def _empty_holdout_segment() -> dict[str, object]:
    return {
        "start_date": None,
        "end_date": None,
        "date_count": 0,
        "effect": {},
    }


def _assert_unique_candidate_keys(rows: Sequence[Mapping[str, object]]) -> None:
    counts = Counter(
        (
            str(row.get("signal_date") or row.get("trade_date") or "")[:10],
            str(row.get("stock_code") or row.get("symbol") or "").strip(),
        )
        for row in rows
    )
    conflicts = sorted(key for key, count in counts.items() if count > 1)
    if conflicts:
        raise ValueError(
            "conflicting logical candidate duplicates remain after exact dedupe: "
            f"count={len(conflicts)}, preview={conflicts[:10]}"
        )


def _point_field(point: object, field: str) -> str:
    if isinstance(point, Mapping):
        value = point.get(field)
    else:
        value = getattr(point, field, None)
    return str(value or "").strip()


def _replayed_gate_state_is_missing(*, state: object, source: object) -> bool:
    normalized_state = str(state or "").strip().upper()
    normalized_source = str(source or "").strip().lower()
    return normalized_state in {"", "UNKNOWN", "NO_DATA"} or normalized_source in {
        "",
        "missing",
    }


def _metadata_text_values(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _metadata_number_values(value: object) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return sorted(
        {number for item in value if (number := _finite_float(item)) is not None}
    )


def _return_stats(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {
            "sample_count": 0,
            "mean_return": None,
            "median_return": None,
            "win_rate": None,
        }
    return {
        "sample_count": len(values),
        "mean_return": _round_optional(sum(values) / len(values)),
        "median_return": _round_optional(median(values)),
        "win_rate": _round_optional(sum(value > 0 for value in values) / len(values)),
    }


def _ols_slope(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    denominator = sum((x - mean_x) ** 2 for x, _ in pairs)
    if denominator <= 1e-18:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in pairs) / denominator


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = min(max(quantile, 0.0), 1.0) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _as_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    return default


def _finite_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _required_mapping(
    payload: Mapping[str, object], field: str
) -> Mapping[str, object]:
    value = payload.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _mapping_float(
    payload: Mapping[str, object],
    field: str,
    *,
    default: float | None = None,
) -> float:
    value = _finite_float(payload.get(field))
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field} must be a finite number")
    return value


def _mapping_int(
    payload: Mapping[str, object],
    field: str,
    *,
    default: int | None = None,
) -> int:
    value = _finite_float(payload.get(field))
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field} must be an integer")
    if not value.is_integer():
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_run_id(value: object) -> str:
    raw_run_id = str(value or "")
    run_id = raw_run_id.strip()
    reserved_stem = run_id.split(".", 1)[0].upper()
    if (
        raw_run_id != run_id
        or not RUN_ID_PATTERN.fullmatch(run_id)
        or run_id.endswith(".")
        or reserved_stem in WINDOWS_RESERVED_RUN_ID_STEMS
    ):
        raise ValueError(
            "run_id must be 1-128 ASCII letters, digits, dots, underscores, or hyphens "
            "and must begin with a letter or digit"
        )
    return run_id


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _date_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)[:10]


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "select table_name from information_schema.tables where table_schema = 'main'"
        ).fetchall()
    }


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {
        str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the research-only Fable MA20 extension study from DuckDB."
    )
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--contract-path", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--signal-kind", default="stock_candidate")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_extension_study_from_duckdb(
        db_path=args.db_path,
        contract_path=args.contract_path,
        output_root=args.output_root,
        run_id=args.run_id,
        signal_kind=args.signal_kind,
    )
    summary = result.get("summary")
    status = summary.get("status") if isinstance(summary, Mapping) else None
    print(
        json.dumps(
            {
                "run_dir": result.get("run_dir"),
                "result_sha256": result.get("result_sha256"),
                "status": status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
