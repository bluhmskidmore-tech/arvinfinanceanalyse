"""Independent, read-only MOSS equity research export; never an execution signal."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_VERSION = 1
DEFAULT_MIN_AMOUNT = 300_000_000.0
FIELDS = {
    "daily_basic": "ts_code,trade_date,turnover_rate,volume_ratio,pe_ttm,pb,total_mv,circ_mv",
    "moneyflow": "ts_code,trade_date,net_mf_amount",
    "fina_indicator": "ts_code,ann_date,end_date,roe,profit_dedt,dt_netprofit_yoy,netprofit_yoy,or_yoy",
    "cashflow": "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,n_cashflow_act,update_flag",
    "income": "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,n_income_attr_p,n_income,minority_gain,update_flag",
}
CONTRACT_URLS = {
    "trade_cal": "https://tushare.pro/document/2?doc_id=26",
    "daily_basic": "https://tushare.pro/document/2?doc_id=32",
    "moneyflow": "https://tushare.pro/document/2?doc_id=170",
    "fina_indicator": "https://tushare.pro/document/2?doc_id=79",
    "cashflow": "https://tushare.pro/document/2?doc_id=44",
    "income": "https://tushare.pro/document/2?doc_id=33",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_date(value: object) -> str:
    text = str(value or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(text).isoformat()


def _date(value: object) -> str | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return validate_date(text)
    except ValueError:
        return None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _scaled(value: object, multiplier: float) -> float | None:
    number = _number(value)
    return number * multiplier if number is not None else None


def _dump(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False, default=str) + "\n").encode("utf-8")


def _write_json(path: Path, value: object) -> str:
    data = _dump(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _financial_business_key(row: dict[str, Any]) -> bytes:
    # Initial/revised flags may differ while every dated business value is identical.
    return _dump({key: value for key, value in row.items() if key != "update_flag"})


def normalize_daily_rows(rows: list[dict[str, Any]], target_date: str,
                         dataset: str) -> dict[str, dict[str, Any]]:
    target = validate_date(target_date)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("ts_code") or row.get("stock_code") or "").strip()
        if not code or _date(row.get("trade_date")) != target:
            raise ValueError(f"{dataset}: missing code or unexpected trade_date")
        if code in result:
            raise ValueError(f"{dataset}: duplicate natural key {code}/{target}")
        result[code] = row
    return result


def latest_report_period(target_date: str) -> str:
    target = date.fromisoformat(validate_date(target_date))
    periods = [date(year, month, day) for year in (target.year - 1, target.year)
               for month, day in ((3, 31), (6, 30), (9, 30), (12, 31))]
    return max(period for period in periods if period <= target).isoformat()


def recent_report_periods(target_date: str) -> list[str]:
    target = date.fromisoformat(validate_date(target_date))
    periods = [date(year, month, day) for year in (target.year - 1, target.year)
               for month, day in ((3, 31), (6, 30), (9, 30), (12, 31))]
    return [period.isoformat() for period in sorted((p for p in periods if p <= target), reverse=True)[:2]]


def validate_market_sessions(snapshot: dict[str, Any], calendar_rows: list[dict[str, Any]],
                             target_date: str) -> dict[str, Any]:
    """Observed dates cannot substitute for an exchange calendar: whole-day holes fail."""
    target = validate_date(target_date)
    sessions = {_date(day) for day in snapshot["sessions"]}
    if None in sessions or target not in sessions:
        raise ValueError("MOSS session dates are invalid or do not include target")
    start = min(sessions)
    calendar: dict[str, int] = {}
    for row in calendar_rows:
        day = _date(row.get("cal_date"))
        if day is None or day < start or day > target or str(row.get("exchange")) != "SSE":
            raise ValueError("trade_cal returned invalid date range or exchange")
        if day in calendar:
            raise ValueError("trade_cal duplicate natural key")
        if str(row.get("is_open")) not in {"0", "1"}:
            raise ValueError("trade_cal returned invalid is_open")
        calendar[day] = int(row["is_open"])
    start_day, target_day = date.fromisoformat(start), date.fromisoformat(target)
    all_days = {(start_day + timedelta(days=offset)).isoformat()
                for offset in range((target_day - start_day).days + 1)}
    if set(calendar) != all_days:
        raise ValueError("trade_cal missing calendar dates; window completeness unverified")
    expected = {day for day, is_open in calendar.items() if is_open}
    if expected != sessions:
        missing = sorted(expected - sessions)
        unexpected = sorted(sessions - expected)
        raise ValueError(f"MOSS whole-market session gaps: missing={missing}; unexpected={unexpected}")
    return {"status": "validated", "exchange": "SSE", "start_date": start,
            "end_date": target, "open_session_count": len(expected), "missing_open_dates": []}


def archive_moss_snapshot(snapshot: dict[str, Any], output_dir: Path,
                          sources: list[dict[str, Any]]) -> dict[str, Any]:
    body = gzip.compress(_dump(snapshot), compresslevel=6, mtime=0)
    relative = "raw/moss_snapshot.json.gz"
    path = output_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    entry = {"endpoint": "moss_readonly_snapshot", "params": {"as_of_date": snapshot["market_gate"]["as_of_date"]},
             "fetched_at": utc_now(), "status": "success", "relative_path": relative,
             "sha256": hashlib.sha256(body).hexdigest(), "encoding": "gzip_json_utf8",
             "row_count": len(snapshot["observations"]), "universe_count": len(snapshot["universe"])}
    sources.append(entry)
    return entry


def load_moss_snapshot(duckdb_path: str | Path, target_date: str) -> dict[str, Any]:
    """Exact-date universe, left joins, and 61 market sessions; no migrations/writes."""
    import duckdb
    from backend.app.core_finance.choice_stock_units import amount_rmb_sql, volume_shares_sql

    target = validate_date(target_date)
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}

        def read(sql: str, params: list[object]) -> list[dict[str, Any]]:
            cursor = conn.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        required = {"choice_stock_universe", "choice_stock_daily_observation"}
        if not required <= tables:
            raise ValueError("MOSS required stock tables are missing")
        universe = read("select * from choice_stock_universe where as_of_date = ?", [target])
        if not universe:
            raise ValueError(f"MOSS has no exact-date universe for {target}")
        codes = [str(row["stock_code"]) for row in universe]
        if len(set(codes)) != len(codes):
            raise ValueError("MOSS universe has duplicate natural keys")
        sectors = read("select stock_code, sw2021, sw2021code from choice_stock_sector_membership "
                       "where as_of_date = ?", [target]) if "choice_stock_sector_membership" in tables else []
        sector_by_code: dict[str, dict[str, Any]] = {}
        for row in sectors:
            code = str(row["stock_code"])
            if code in sector_by_code:
                raise ValueError("MOSS sector membership has duplicate natural keys")
            sector_by_code[code] = row
        for row in universe:
            member = sector_by_code.get(str(row["stock_code"]), {})
            row["sector"] = member.get("sw2021")
            row["sector_code"] = member.get("sw2021code")
        sessions = [row[0] for row in conn.execute(
            "select distinct trade_date from choice_stock_daily_observation "
            "where trade_date <= ? order by trade_date desc limit 61", [target]).fetchall()]
        if not sessions or str(sessions[0]) != target:
            raise ValueError(f"MOSS has no exact-date daily observations for {target}")
        observations = read(
            f"select obs.*, {amount_rmb_sql(table_alias='obs', alias='amount_yuan')}, "
            f"{volume_shares_sql(table_alias='obs', alias='volume_shares')} "
            "from choice_stock_daily_observation obs where trade_date >= ? and trade_date <= ? "
            "and stock_code in (select stock_code from choice_stock_universe where as_of_date = ?)",
            [sessions[-1], target, target])
        adjustments = read("select * from stock_adjustment_factor where trade_date >= ? "
                           "and trade_date <= ? and stock_code in "
                           "(select stock_code from choice_stock_universe where as_of_date = ?)",
                           [sessions[-1], target, target]) if "stock_adjustment_factor" in tables else []
        limits = read("select * from stock_limit_price_daily where trade_date = ?", [target]) \
            if "stock_limit_price_daily" in tables else []
        limit_by_code = normalize_daily_rows(limits, target, "MOSS numeric limits")
        for row in observations:
            if str(row["trade_date"]) == target:
                row["up_limit"] = limit_by_code.get(str(row["stock_code"]), {}).get("up_limit")
                row["down_limit"] = limit_by_code.get(str(row["stock_code"]), {}).get("down_limit")
        gate_rows = read("select * from livermore_gate_history where trade_date = ?", [target]) \
            if "livermore_gate_history" in tables else []
        if len(gate_rows) > 1:
            raise ValueError("MOSS market gate has duplicate target-date records")
        gate = gate_rows[0] if gate_rows else {
            "state": "PENDING_DATA", "exposure": 0.0,
            "reason": "exact_date_persisted_MOSS_gate_missing",
        }
        gate["as_of_date"] = target
        if "conditions_json" in gate:
            gate["conditions"] = json.loads(gate.pop("conditions_json"))
        snapshot = {"universe": universe, "observations": observations,
                    "adjustments": adjustments, "market_gate": gate,
                    "sessions": sessions, "source": str(Path(duckdb_path).resolve())}
        snapshot["snapshot_sha256"] = hashlib.sha256(_dump(snapshot)).hexdigest()
        return snapshot


def technical_stock(universe_row: dict[str, Any], history_rows: list[dict[str, Any]],
                    adjustment_rows: list[dict[str, Any]], target_date: str,
                    min_amount_yuan: float = DEFAULT_MIN_AMOUNT) -> dict[str, Any]:
    from backend.app.core_finance.field_normalization import is_tradestatus_tradable

    target = validate_date(target_date)
    code = str(universe_row.get("stock_code") or universe_row.get("code") or "")
    name = str(universe_row.get("stock_name") or universe_row.get("name") or code)
    failures: list[str] = []
    notes: list[str] = []
    history: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, float | None] = {}
    for row in history_rows:
        day = _date(row.get("trade_date"))
        if not day or day > target:
            raise ValueError("MOSS daily history contains invalid/future dates")
        if day in history:
            raise ValueError(f"MOSS daily history duplicate natural key {code}/{day}")
        history[day] = row
    for row in adjustment_rows:
        day = _date(row.get("trade_date"))
        if not day or day > target:
            raise ValueError("MOSS adjustment history contains invalid/future dates")
        if day in adjustments:
            raise ValueError(f"MOSS adjustment duplicate natural key {code}/{day}")
        adjustments[day] = _number(row.get("adj_factor"))
    current = history.get(target, {})
    close = _number(current.get("close_value"))
    amount = _number(current.get("amount_yuan"))
    if not current or current.get("_missing_observation"):
        failures.append("target_date_observation_missing")
    if close is None or close <= 0:
        failures.append("target_date_close_missing_or_nonpositive")
    if not is_tradestatus_tradable(current.get("tradestatus")):
        failures.append("suspended_or_trade_status_unknown")
    if re.match(r"^\*?ST", name.upper()):
        failures.append("ST_security")
    if amount is None:
        failures.append("amount_missing_or_source_unit_unknown")
    elif amount < min_amount_yuan:
        failures.append("daily_amount_below_research_floor")
    up_limit = _number(current.get("up_limit"))
    if up_limit is None:
        failures.append("numeric_limit_price_missing")
    elif close is not None and close >= up_limit - 0.005:
        failures.append("closed_at_up_limit_not_executable")
    ohlc = [_number(current.get(key)) for key in ("open_value", "high_value", "low_value", "close_value")]
    if all(value is not None and value > 0 for value in ohlc) and max(ohlc) - min(ohlc) < 1e-9:
        failures.append("one_price_bar_not_executable")
    target_adj = adjustments.get(target)
    ordered = sorted(history)
    adjusted: list[float | None] = []
    for day in ordered:
        raw_close = _number(history[day].get("close_value"))
        factor = adjustments.get(day)
        adjusted.append(raw_close * factor / target_adj if raw_close is not None and raw_close > 0
                        and factor is not None and factor > 0 and target_adj is not None and target_adj > 0 else None)
    if target_adj is None or target_adj <= 0:
        failures.append("target_date_adjustment_missing")

    def moving_average(window: int) -> float | None:
        values = adjusted[-window:]
        if len(values) < window or any(value is None for value in values):
            failures.append(f"adjusted_history_insufficient_{window}d")
            return None
        return sum(values) / window

    ma20, ma60 = moving_average(20), moving_average(60)
    window21 = adjusted[-21:]
    return20 = (window21[-1] / window21[0] - 1) if len(window21) == 21 and all(
        value is not None and value > 0 for value in window21) else None
    if return20 is None:
        failures.append("adjusted_history_insufficient_return20")
    if ma20 is not None and ma60 is not None and close is not None and not (close > ma20 > ma60):
        failures.append("price_above_ma20_above_ma60_not_met")
    if return20 is not None and return20 <= 0:
        failures.append("return20_not_positive")
    if not universe_row.get("sector"):
        notes.append("target_date_sector_missing")
    data_gaps: list[str] = []
    for reason in ("target_date_observation_missing", "target_date_close_missing_or_nonpositive",
                   "amount_missing_or_source_unit_unknown", "numeric_limit_price_missing",
                   "target_date_adjustment_missing"):
        if reason in failures:
            data_gaps.append(reason)
    if len(ordered) < 60:
        data_gaps.append("history_observation_count_below_60")
    required_history = ordered[-60:]
    if any(_number(history[day].get("close_value")) is None
           or _number(history[day].get("close_value")) <= 0 for day in required_history):
        data_gaps.append("historical_close_missing_or_nonpositive")
    if any(adjustments.get(day) is None or adjustments[day] <= 0 for day in required_history):
        data_gaps.append("historical_adjustment_missing_or_nonpositive")
    return {"code": code, "name": name, "sector": universe_row.get("sector"),
            "sector_code": universe_row.get("sector_code"), "close": close,
            "pct_change": _scaled(current.get("pctchange"), 0.01), "amount_yuan": amount,
            "ma20": ma20, "ma60": ma60, "return20": return20,
            "technical_pass": not failures, "technical_rank": None,
            "technical_data_gap_reasons": data_gaps,
            "fail_reasons": failures, "notes": notes}


def _financial_record(code: str, rows: list[dict[str, Any]], target: str,
                      period: str, dataset: str, notes: list[str]) -> dict[str, Any]:
    candidates = []
    for row in rows:
        if row.get("ts_code") != code or _date(row.get("end_date")) != period:
            continue
        ann = _date(row.get("ann_date"))
        if ann is None:
            notes.append(f"{dataset}:ann_date_missing_or_invalid")
            continue
        if ann > target:
            notes.append(f"{dataset}:future_ann_date_rejected")
            continue
        actual_raw = row.get("f_ann_date")
        actual = _date(actual_raw) if actual_raw else ann
        if actual is None or actual > target:
            notes.append(f"{dataset}:future_or_invalid_actual_ann_date_rejected")
            continue
        if dataset in {"cashflow", "income"} and str(row.get("report_type")) != "1":
            notes.append(f"{dataset}:report_type_not_consolidated_latest")
            continue
        candidates.append((max(ann, actual), ann, row))
    if not candidates:
        notes.append(f"{dataset}:no_eligible_announced_report")
        return {}
    latest = max((row[0], row[1]) for row in candidates)
    chosen = [row[2] for row in candidates if (row[0], row[1]) == latest]
    if len({_financial_business_key(row) for row in chosen}) > 1:
        # Select a real source row only if it contains every other row's non-null
        # value, including metadata. Never synthesize complementary partial rows.
        dominating = [row for row in chosen if all(
            value is None or row.get(key) == value
            for other in chosen for key, value in other.items())]
        if not dominating:
            notes.append(f"{dataset}:conflicting_report_versions")
            return {}
        notes.append(f"{dataset}:sparse_duplicate_reconciled")
        return max(dominating, key=lambda row: str(row.get("update_flag") or "0"))
    if len(chosen) > 1:
        notes.append(f"{dataset}:identical_business_duplicates_merged")
    return max(chosen, key=lambda row: str(row.get("update_flag") or "0"))


def financial_fields(code: str, indicator_rows: list[dict[str, Any]],
                     cashflow_rows: list[dict[str, Any]], income_rows: list[dict[str, Any]],
                     target_date: str, report_period: str) -> dict[str, Any]:
    target, requested_period = validate_date(target_date), validate_date(report_period)
    notes: list[str] = []
    query_periods = [period for period in recent_report_periods(target) if period <= requested_period]

    def announced_periods(rows: list[dict[str, Any]], statement: bool) -> set[str]:
        result = set()
        for row in rows:
            period, ann = _date(row.get("end_date")), _date(row.get("ann_date"))
            actual = _date(row.get("f_ann_date")) if row.get("f_ann_date") else ann
            if row.get("ts_code") != code or period not in query_periods or ann is None or ann > target:
                continue
            if actual is None or actual > target or statement and str(row.get("report_type")) != "1":
                continue
            result.add(period)
        return result

    available = announced_periods(indicator_rows, False)
    if not available:
        available = announced_periods(cashflow_rows, True) | announced_periods(income_rows, True)
    period = max(available) if available else requested_period
    if available and period != requested_period:
        notes.append("latest_ended_period_not_yet_disclosed;using_latest_announced_period")
    indicator = _financial_record(code, indicator_rows, target, period, "fina_indicator", notes)
    cashflow = _financial_record(code, cashflow_rows, target, period, "cashflow", notes)
    income = _financial_record(code, income_rows, target, period, "income", notes)
    cash, parent = _number(cashflow.get("n_cashflow_act")), _number(income.get("n_income_attr_p"))
    consolidated = _number(income.get("n_income"))
    minority = _number(income.get("minority_gain"))
    if cashflow and income and cashflow.get("comp_type") and income.get("comp_type") and (
        str(cashflow["comp_type"]) != str(income["comp_type"])
    ):
        notes.append("financial_statement_company_type_mismatch")
        cash = parent = consolidated = minority = None
    revenue = _scaled(indicator.get("or_yoy"), 0.01)
    profit = _scaled(indicator.get("netprofit_yoy"), 0.01)
    deducted = _scaled(indicator.get("dt_netprofit_yoy"), 0.01)
    deducted_profit = _number(indicator.get("profit_dedt"))
    ratio = cash / parent if cash is not None and parent is not None and parent > 0 else None
    cashflow_company_type = str(cashflow.get("comp_type") or "").strip()
    income_company_type = str(income.get("comp_type") or "").strip()
    consolidated_ratio = cash / consolidated if cash is not None and consolidated is not None \
        and consolidated > 0 and cashflow_company_type and cashflow_company_type == income_company_type else None
    if cash is not None and consolidated is not None and consolidated > 0 \
            and (not cashflow_company_type or not income_company_type):
        notes.append("consolidated_cash_ratio_company_type_missing")
    if ratio is not None and ratio >= 1 and consolidated_ratio is not None and consolidated_ratio < 1:
        notes.append("ocf_parent_ratio_supported_but_consolidated_ratio_below_one")
    roe = _scaled(indicator.get("roe"), 0.01)
    complete = all(value is not None for value in (revenue, profit, deducted, deducted_profit, cash, parent, roe))
    coverage = "complete" if complete else "partial" if indicator or cashflow or income else "missing"
    supported = complete and revenue > 0 and profit > 0 and deducted > 0 and deducted_profit > 0 \
        and parent > 0 and cash > 0 and ratio >= 1 and roe > 0
    return {"report_period": period if available else None, "queried_report_periods": query_periods,
            "ann_date": _date(indicator.get("ann_date")),
            "cashflow_ann_date": _date(cashflow.get("ann_date")),
            "income_ann_date": _date(income.get("ann_date")),
            "cashflow_f_ann_date": _date(cashflow.get("f_ann_date")),
            "income_f_ann_date": _date(income.get("f_ann_date")),
            "cashflow_update_flag": cashflow.get("update_flag"),
            "income_update_flag": income.get("update_flag"),
            "revenue_yoy": revenue, "profit_yoy": profit, "deducted_profit_yoy": deducted,
            "roe": roe, "deducted_profit_yuan": deducted_profit,
            "ocf_yuan": cash, "parent_profit_yuan": parent, "ocf_to_parent_profit": ratio,
            "consolidated_profit_yuan": consolidated, "minority_profit_yuan": minority,
            "ocf_to_consolidated_profit": consolidated_ratio,
            "financial_coverage": coverage,
            "financial_status": "growth_cash_supported" if supported else "growth_cash_risk" if complete
            else "insufficient_data", "notes": sorted(set(notes))}


def build_result(snapshot: dict[str, Any], vendor_data: dict[str, list[dict[str, Any]]],
                 target_date: str, generated_at: str,
                 min_amount_yuan: float = DEFAULT_MIN_AMOUNT) -> dict[str, Any]:
    target = validate_date(target_date)
    period = latest_report_period(target)
    basic = normalize_daily_rows(vendor_data.get("daily_basic", []), target, "daily_basic")
    flows = normalize_daily_rows(vendor_data.get("moneyflow", []), target, "moneyflow")
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    adjustments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot["observations"]:
        observations[str(row["stock_code"])].append(row)
    for row in snapshot["adjustments"]:
        adjustments[str(row["stock_code"])].append(row)
    financial_by_code: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for name in ("fina_indicator", "cashflow", "income"):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in vendor_data.get(name, []):
            grouped[str(row.get("ts_code"))].append(row)
        financial_by_code[name] = grouped
    universe_codes = [str(row.get("stock_code") or row.get("code")) for row in snapshot["universe"]]
    if len(set(universe_codes)) != len(universe_codes) or not universe_codes:
        raise ValueError("research universe is empty or has duplicate natural keys")
    gate = dict(snapshot["market_gate"])
    gate_date = _date(gate.get("as_of_date") or gate.get("trade_date"))
    if gate_date is not None and gate_date != target:
        raise ValueError("MOSS market gate does not match target date")
    gate["as_of_date"] = target
    stocks = []
    for member, code in zip(snapshot["universe"], universe_codes, strict=True):
        history = list(observations[code])
        present_dates = {_date(row.get("trade_date")) for row in history}
        for session in snapshot.get("sessions", []):
            day = _date(session)
            if day is None or day > target:
                raise ValueError("MOSS expected sessions contain invalid/future dates")
            if day not in present_dates:
                history.append({"stock_code": code, "trade_date": day, "_missing_observation": True})
        item = technical_stock(member, history, adjustments[code], target, min_amount_yuan)
        daily, flow = basic.get(code, {}), flows.get(code, {})
        item.update({"pe_ttm": _number(daily.get("pe_ttm")), "pb": _number(daily.get("pb")),
                     "turnover_rate": _scaled(daily.get("turnover_rate"), 0.01),
                     "volume_ratio": _number(daily.get("volume_ratio")),
                     "total_mv_yuan": _scaled(daily.get("total_mv"), 10_000),
                     "circ_mv_yuan": _scaled(daily.get("circ_mv"), 10_000),
                     "net_mf_amount_yuan": _scaled(flow.get("net_mf_amount"), 10_000)})
        financial = financial_fields(code, financial_by_code["fina_indicator"].get(code, []),
                                     financial_by_code["cashflow"].get(code, []),
                                     financial_by_code["income"].get(code, []), target, period)
        item["notes"].extend(financial.pop("notes"))
        item.update(financial)
        item["research_status"] = "observation_only"
        if not daily:
            item["notes"].append("daily_basic_missing")
        if not flow:
            item["notes"].append("moneyflow_missing_auxiliary_only")
        if item["pe_ttm"] is None or item["pe_ttm"] <= 0:
            item["notes"].append("PE_TTM_missing_or_nonpositive_valuation_not_comparable")
        elif item["pe_ttm"] >= 60:
            item["notes"].append("PE_TTM_at_least_60_research_valuation_risk")
        if gate.get("state") not in {"WARM", "HOT"}:
            item["fail_reasons"].append(f"market_gate_{gate.get('state', 'UNKNOWN')}")
        if item["financial_status"] != "growth_cash_supported":
            item["fail_reasons"].append("financial_" + item["financial_status"])
        stocks.append(item)
    ranked = sorted((item for item in stocks if item["technical_pass"]),
                    key=lambda item: (-item["return20"], -item["amount_yuan"], item["code"]))
    for rank, item in enumerate(ranked, 1):
        item["technical_rank"] = rank
    layer = {"growth_cash_supported": 0, "insufficient_data": 1, "growth_cash_risk": 2}
    shortlist = sorted(ranked[:20], key=lambda item: (layer[item["financial_status"]], item["technical_rank"]))
    financial_supported = [item for item in ranked if item["financial_status"] == "growth_cash_supported"]
    datasets = {}
    universe_set = set(universe_codes)
    for name in FIELDS:
        rows = vendor_data.get(name, [])
        covered = len({str(row.get("ts_code")) for row in rows} & universe_set)
        datasets[name] = {"row_count": len(rows), "covered_stock_count": covered,
                          "coverage_ratio": covered / len(stocks),
                          "status": "complete" if covered == len(stocks) else "partial" if covered else "missing",
                          "scope": "target_date" if name in {"daily_basic", "moneyflow"}
                          else "two_recent_ended_periods;latest_announced_per_stock;not_backtest_PIT"}
        if name in {"fina_indicator", "cashflow", "income"}:
            datasets[name]["queried_report_periods"] = recent_report_periods(target)
    calendar_quality = None
    if "trade_cal" in vendor_data:
        calendar_quality = validate_market_sessions(snapshot, vendor_data["trade_cal"], target)
        datasets["trade_cal"] = {**calendar_quality, "status": "complete",
                                 "row_count": len(vendor_data["trade_cal"])}
    financial_complete = sum(item["financial_coverage"] == "complete" for item in stocks)
    technical_gap_counts: dict[str, int] = defaultdict(int)
    for item in stocks:
        for reason in set(item["technical_data_gap_reasons"]):
            technical_gap_counts[reason] += 1
    technical_gap_stocks = sum(bool(item["technical_data_gap_reasons"]) for item in stocks)
    warnings = ["Observation research only; no orders, position recommendation or gate override.",
                "Financial responses fetched now may contain revisions; this is not historical backtest PIT.",
                "Money flow is auxiliary active-order net flow, not proof of a market theme.",
                "Universe is MOSS exact-date landed coverage; do not assume Beijing Exchange inclusion.",
                "Research rules are unvalidated and do not inherit MOSS strategy out-of-sample support."]
    degraded = any(data["status"] != "complete" for data in datasets.values()) or financial_complete < len(stocks)
    if technical_gap_stocks:
        degraded = True
        warnings.append(f"MOSS technical data gaps affect {technical_gap_stocks} stocks; "
                        "an empty shortlist must not be interpreted as a fully observed universe failing the filters.")
    if gate.get("state") in {"PENDING_DATA", "NO_DATA", "STALE"}:
        degraded = True
        warnings.append("MOSS exact-date gate unavailable or stale; execution remains blocked.")
    return {"schema_version": SCHEMA_VERSION, "formal_use_allowed": False, "target_date": target,
            "generated_at": generated_at, "status": "degraded" if degraded else "ready",
            "universe_count": len(stocks), "universe_scope": "MOSS exact-date landed universe",
            "quality": {"technical_pass_count": len(ranked), "shortlist_count": len(shortlist),
                        "financial_supported_count": len(financial_supported),
                        "technical_data_gap_stock_count": technical_gap_stocks,
                        "technical_data_gap_reason_counts": dict(sorted(technical_gap_counts.items())),
                        "financial_complete_count": financial_complete,
                        "daily_basic_coverage_count": datasets["daily_basic"]["covered_stock_count"],
                        "moneyflow_coverage_count": datasets["moneyflow"]["covered_stock_count"]},
            "market_gate": gate, "datasets": datasets,
            "rules": {"min_amount_yuan": min_amount_yuan, "liquidity_basis": "target_date_turnover_amount",
                      "technical": "close > adjusted_MA20 > adjusted_MA60; adjusted_return20 > 0",
                      "adjustment_basis": "raw_close * historical_adj / target_adj; full 20/60/21 bars required",
                      "shortlist_limit": 20, "technical_order": "return20 desc, amount_yuan desc, code asc",
                      "financial_research_extension_version": 1,
                      "financial_supported_candidates_limit": 20,
                      "financial_supported_candidates_use": "research_discovery_only;all_technical_pass_and_growth_cash_supported;technical_rank_ascending;not_execution_admission",
                      "financial_support": "revenue/profit/deducted_profit growth > 0; ROE and deducted profit > 0; OCF / positive parent profit >= 1",
                      "financial_report_type": "1_consolidated_latest_same_period",
                      "financial_report_periods_queried": recent_report_periods(target),
                      "financial_period_selection": "latest_announced_indicator_period;else_latest_announced_statement_period;no_cross_period_cash_ratio",
                      "valuation_warning_pe_ttm": 60,
                      "financial_use": "current_research_snapshot_not_historical_PIT",
                      "consolidated_cash_quality_use": "same_period_and_matching_nonempty_company_type;consolidated_OCF/positive_consolidated_profit;minority_profit_and_ratio_are_counterevidence_only;no_change_to_financial_support_or_coverage",
                      "market_calendar": calendar_quality or {"status": "not_checked_by_pure_helper"},
                      "return_and_growth_units": "ratio", "money_units": "CNY_yuan",
                      "strategy_oos_support": "not_validated", "execution_allowed": False},
            "stocks": stocks, "shortlist": shortlist,
            "financial_supported_candidates": financial_supported[:20], "warnings": warnings, "raw_files": []}


class VendorArchive:
    """Archive response bodies and credential-free request metadata, including failures."""

    def __init__(self, output_dir: Path, token: str, sources: list[dict[str, Any]]) -> None:
        self.output_dir, self.token, self.sources = output_dir, token, sources

    def fetch(self, endpoint: str, fields: str, params: dict[str, object]) -> list[dict[str, Any]]:
        import requests

        entry: dict[str, Any] = {"endpoint": endpoint, "params": params, "fields": fields,
                                 "fetched_at": utc_now(), "status": "failed", "row_count": 0,
                                 "contract_url": CONTRACT_URLS[endpoint.removesuffix("_vip")]}
        relative = f"raw/{len(self.sources) + 1:03d}_{endpoint}.json"
        payload: object = {}
        try:
            if not self.token:
                raise RuntimeError("configured Tushare token unavailable")
            response = requests.post("https://api.tushare.pro", json={"api_name": endpoint,
                                     "token": self.token, "params": params, "fields": fields}, timeout=45)
            entry["http_status"] = response.status_code
            payload = response.json()
            response.raise_for_status()
            if not isinstance(payload, dict) or payload.get("code") != 0:
                raise RuntimeError(str(payload.get("msg") if isinstance(payload, dict) else "invalid vendor response"))
            data = payload.get("data") or {}
            columns, values = data.get("fields") or [], data.get("items") or []
            if not isinstance(columns, list) or not isinstance(values, list):
                raise ValueError("invalid vendor tabular data")
            rows = [dict(zip(columns, row, strict=True)) for row in values]
            entry.update(status="success" if rows else "empty", row_count=len(rows))
            if endpoint.removesuffix("_vip") in {"fina_indicator", "cashflow", "income"}:
                entry["tabular_sha256"] = hashlib.sha256(_dump({
                    "fields": columns, "items": values})).hexdigest()
                unique: dict[bytes, dict[str, Any]] = {}
                for row in sorted(rows, key=lambda item: str(item.get("update_flag") or "0")):
                    unique[_financial_business_key(row)] = row
                entry["identical_duplicate_row_count"] = len(rows) - len(unique)
                entry["duplicate_basis"] = "all_fields_except_update_flag;raw_response_preserved"
                rows = list(unique.values())
                entry["usable_distinct_row_count"] = len(rows)
            if endpoint in {"daily_basic", "moneyflow"}:
                entry["documented_single_call_limit"] = 6000
                entry["possible_truncation"] = len(rows) >= 6000
            else:
                entry["pagination_contract"] = (
                    "limit_offset_observed_2026-09-09;not_listed_in_official_reference"
                    if endpoint.endswith("_vip") and "offset" in params
                    else "single_call;coverage_checked_against_universe")
            return rows
        except Exception as exc:
            error = str(exc).replace(self.token, "[REDACTED]") if self.token else str(exc)
            entry["error"] = error[:800]
            entry["error_kind"] = "transport" if isinstance(exc, requests.RequestException) else "vendor_or_contract"
            if not payload:
                payload = {"transport_error": error[:800]}
            return []
        finally:
            # Vendor error messages must not echo the configured credential into artifacts.
            serialized = _dump(payload).decode("utf-8")
            if self.token:
                serialized = serialized.replace(self.token, "[REDACTED]")
            body = serialized.encode("utf-8")
            path = self.output_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            entry.update(relative_path=relative, sha256=hashlib.sha256(body).hexdigest(),
                         response_credential_redaction=True)
            self.sources.append(entry)


def fetch_vendor_data(archive: VendorArchive, snapshot: dict[str, Any], target: str,
                      min_amount_yuan: float) -> dict[str, list[dict[str, Any]]]:
    """Page period-wide VIP reads; only remaining top-20 gaps get single-code reads."""
    compact = target.replace("-", "")
    data: dict[str, list[dict[str, Any]]] = {}
    data["trade_cal"] = archive.fetch("trade_cal", "exchange,cal_date,is_open", {
        "exchange": "SSE", "start_date": min(snapshot["sessions"]).replace("-", ""), "end_date": compact})
    validate_market_sessions(snapshot, data["trade_cal"], target)
    for name in ("daily_basic", "moneyflow"):
        rows = archive.fetch(name, FIELDS[name], {"trade_date": compact})
        normalize_daily_rows(rows, target, name)
        data[name] = rows
    preliminary = build_result(snapshot, data, target, utc_now(), min_amount_yuan)
    codes = [item["code"] for item in preliminary["shortlist"]]
    for name in ("fina_indicator", "cashflow", "income"):
        rows = []
        for period in recent_report_periods(target):
            params: dict[str, object] = {"period": period.replace("-", "")}
            if name in {"cashflow", "income"}:
                params["report_type"] = "1"
            offset, page_size = 0, 2000
            seen_pages: set[str] = set()
            page_entries: list[dict[str, Any]] = []
            pagination_complete = False
            # A small limit works across all three VIP endpoints. Advance by raw rows,
            # including duplicates, and require an empty page rather than assuming a cap.
            for _page in range(100):
                page_rows = archive.fetch(name + "_vip", FIELDS[name], {
                    **params, "limit": page_size, "offset": offset})
                entry = archive.sources[-1]
                page_entries.append(entry)
                entry["pagination_complete"] = False
                if entry["status"] == "failed":
                    break
                count = entry["row_count"]
                if count == 0:
                    pagination_complete = True
                    for page_entry in page_entries:
                        page_entry["pagination_complete"] = True
                    break
                signature = entry["tabular_sha256"]
                if count > page_size or signature in seen_pages:
                    entry.update(status="failed", error_kind="vendor_or_contract",
                                 error="financial pagination ignored limit or repeated a page",
                                 possible_truncation=True)
                    break
                seen_pages.add(signature)
                rows.extend(page_rows)
                offset += count
            else:
                archive.sources[-1].update(
                    status="failed", error_kind="vendor_or_contract", possible_truncation=True,
                    error="financial pagination exceeded 100-page safety bound")
            # Transport, permission, or pagination failure stays partial. Do not hide an
            # incomplete universe fetch behind repeated top-20 single-security requests.
            if not pagination_complete or not archive.token:
                continue
            for code in codes:
                if _financial_record(code, rows, target, period, name, []):
                    continue
                rows.extend(archive.fetch(name, FIELDS[name], {**params, "ts_code": code}))
                if archive.sources[-1].get("error_kind") == "transport":
                    break
        data[name] = rows
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vendor-source-ip")
    parser.add_argument("--duckdb-path", type=Path, default=ROOT / "data" / "moss.duckdb")
    parser.add_argument("--min-amount-yuan", type=float, default=DEFAULT_MIN_AMOUNT)
    args = parser.parse_args(argv)
    target = validate_date(args.as_of_date)
    if not math.isfinite(args.min_amount_yuan) or args.min_amount_yuan <= 0:
        parser.error("--min-amount-yuan must be finite and positive")
    output = args.output_dir.resolve()
    # A dated run must not overwrite an older successful result on failure.
    if output.exists() and any(output.iterdir()):
        parser.error("--output-dir must be empty or new; use a distinct run directory")
    output.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    generated = utc_now()
    manifest: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "formal_use_allowed": False,
                                "target_date": target, "generated_at": generated,
                                "sources": sources, "status": "failed", "raw_files": []}
    token = ""
    try:
        snapshot = load_moss_snapshot(args.duckdb_path, target)
        saved_snapshot = archive_moss_snapshot(snapshot, output, sources)
        manifest["moss_snapshot"] = {"database": snapshot["source"],
                                     "sha256": saved_snapshot["sha256"],
                                     "relative_path": saved_snapshot["relative_path"],
                                     "business_content_sha256": snapshot["snapshot_sha256"],
                                     "as_of_date": target, "universe_count": len(snapshot["universe"]),
                                     "history_sessions": snapshot["sessions"]}
        from backend.app.governance.settings import get_settings
        from backend.app.repositories.tushare_adapter import resolve_tushare_token_with_settings_fallback
        token = resolve_tushare_token_with_settings_fallback(get_settings())
        network = nullcontext()
        if args.vendor_source_ip:
            from scripts.choice_stock_daily_refresh import _vendor_source_network
            from backend.app.network.source_bound_socks_proxy import resolve_vendor_source_ip
            network = _vendor_source_network(resolve_vendor_source_ip(args.vendor_source_ip))
        archive = VendorArchive(output, token, sources)
        with network:
            data = fetch_vendor_data(archive, snapshot, target, args.min_amount_yuan)
        generated = utc_now()
        result = build_result(snapshot, data, target, generated, args.min_amount_yuan)
        failures = [source["endpoint"] for source in sources if source["status"] == "failed"]
        if failures:
            result["warnings"].append("Vendor endpoint failures recorded in manifest: " + ", ".join(sorted(set(failures))))
            result["status"] = "degraded"
        exit_code = 0
    except Exception as exc:
        message = str(exc).replace(token, "[REDACTED]") if token else str(exc)
        result = {"schema_version": SCHEMA_VERSION, "formal_use_allowed": False,
                  "target_date": target, "generated_at": generated, "status": "failed",
                  "failure_reason": message[:800], "universe_count": 0,
                  "quality": {}, "market_gate": {}, "datasets": {}, "rules": {"execution_allowed": False},
                  "stocks": [], "shortlist": [], "warnings": [message[:800]]}
        exit_code = 1
    manifest["status"] = result["status"]
    manifest["generated_at"] = result["generated_at"]
    manifest["raw_files"] = [source["relative_path"] for source in sources]
    result["raw_files"] = manifest["raw_files"]
    manifest["result_sha256"] = _write_json(output / "result.json", result)
    _write_json(output / "manifest.json", manifest)
    print(json.dumps({"status": result["status"], "target_date": target,
                      "universe_count": result["universe_count"], "output_dir": str(output)}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
