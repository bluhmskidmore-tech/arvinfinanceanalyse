from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text  # noqa: E402
from backend.app.tasks.choice_stock_materialize import (  # noqa: E402
    REQUIRED_CHOICE_STOCK_REQUEST_ITEMS,
    assert_choice_stock_vendor_era,
    assert_known_choice_stock_daily_vendor_version,
    ensure_choice_stock_schema,
)


RULE_VERSION = "rv_livermore_after_close_supplement_v1"
REQUIRED_MACRO_SERIES = ("CA.CSI300", "CA.CSI300_PCT_CHG", "CA.CSI300_PE")


def supplement_livermore_after_close_inputs(
    *,
    duckdb_path: str | Path,
    target_date: str | date,
    source_as_of_date: str | date | None = None,
    dry_run: bool = False,
    allow_cross_era_backfill: bool = False,
) -> dict[str, object]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    resolved_date = _normalize_date(target_date)
    compact_date = resolved_date.replace("-", "")
    run_id = f"livermore_after_close_supplement:{resolved_date}:{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(UTC).isoformat()

    token = resolve_tushare_token_with_settings_fallback(get_settings())
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN or settings.tushare_token is required.")
    pro = import_tushare_pro().pro_api(token)

    trade_calendar = _records(pro.trade_cal(exchange="SSE", start_date=compact_date, end_date=compact_date))
    if not any(int(row.get("is_open") or 0) == 1 for row in trade_calendar):
        raise RuntimeError(f"{resolved_date} is not an open SSE trading day.")

    daily_records = _records(pro.daily(trade_date=compact_date))
    if not daily_records:
        raise RuntimeError(f"Tushare daily returned no A-share rows for {resolved_date}.")
    limit_records = _records(pro.stk_limit(trade_date=compact_date))
    if not limit_records:
        raise RuntimeError(f"Tushare stk_limit returned no rows for {resolved_date}.")

    csi300_snapshot = _fetch_sina_csi300_snapshot()

    conn = duckdb.connect(str(resolved_path), read_only=bool(dry_run))
    try:
        if not dry_run:
            _ensure_schemas(conn)
        source_date = _normalize_date(source_as_of_date) if source_as_of_date else _latest_choice_stock_source_date(conn, resolved_date)
        if not source_date:
            raise RuntimeError(f"No prior Choice stock source date is available before {resolved_date}.")
        pe_value, pe_source_date = _latest_macro_value(
            conn,
            series_id="CA.CSI300_PE",
            as_of_date=resolved_date,
        )
        if pe_value is None or not pe_source_date:
            raise RuntimeError("No prior CA.CSI300_PE row is available for supplemental valuation.")

        source_version = _build_source_version(
            {
                "target_date": resolved_date,
                "source_as_of_date": source_date,
                "daily_count": len(daily_records),
                "limit_count": len(limit_records),
                "csi300": csi300_snapshot,
                "pe_source_date": pe_source_date,
                "pe_value": pe_value,
            }
        )
        vendor_version = f"vv_livermore_supplement_tushare_sina_{compact_date}_{source_version[-12:]}"

        plan = {
            "target_date": resolved_date,
            "source_as_of_date": source_date,
            "daily_count": len(daily_records),
            "limit_count": len(limit_records),
            "csi300_close": csi300_snapshot["close"],
            "csi300_pct_chg": csi300_snapshot["pct_chg"],
            "csi300_pe": pe_value,
            "csi300_pe_source_date": pe_source_date,
            "source_version": source_version,
            "vendor_version": vendor_version,
        }
        if dry_run:
            return {"status": "dry_run", "duckdb_path": str(resolved_path), "run_id": run_id, "plan": plan}

        # 写入守卫(与主物化任务共享):vendor 必须命中已知代际白名单;本脚本 OHLCV 来自
        # Tushare pro.daily(千元/手口径,vendor 含 tushare 子串),在 choice_native 代际日期
        # (>= 2026-01-05)补写属于跨代际写入,默认 fail-loud,须显式 --allow-cross-era-backfill
        # 知情放行(消费端仍按 tushare 子串正确定标单位)。
        assert_known_choice_stock_daily_vendor_version(vendor_version)
        assert_choice_stock_vendor_era(
            [resolved_date],
            vendor_version=vendor_version,
            allow_cross_era_backfill=allow_cross_era_backfill,
        )

        conn.execute("begin transaction")
        try:
            stock_counts = _write_stock_inputs(
                conn,
                target_date=resolved_date,
                source_date=source_date,
                daily_records=daily_records,
                limit_records=limit_records,
                source_version=source_version,
                vendor_version=vendor_version,
                run_id=run_id,
            )
            factor_count = _write_factor_snapshot(
                conn,
                target_date=resolved_date,
                source_date=source_date,
                source_version=source_version,
                vendor_version=vendor_version,
                run_id=run_id,
            )
            macro_count = _write_macro_rows(
                conn,
                target_date=resolved_date,
                csi300_snapshot=csi300_snapshot,
                pe_value=pe_value,
                pe_source_date=pe_source_date,
                source_version=source_version,
                vendor_version=vendor_version,
                run_id=run_id,
            )
            _write_materialize_run(
                conn,
                target_date=resolved_date,
                source_date=source_date,
                source_version=source_version,
                vendor_version=vendor_version,
                run_id=run_id,
                row_count=sum(stock_counts.values()) + factor_count + macro_count,
                started_at=started_at,
            )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
    finally:
        conn.close()

    return {
        "status": "completed",
        "duckdb_path": str(resolved_path),
        "run_id": run_id,
        "target_date": resolved_date,
        "source_as_of_date": source_date,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "stock_counts": stock_counts,
        "factor_snapshot_rows": factor_count,
        "macro_rows": macro_count,
        "csi300": {
            "close": csi300_snapshot["close"],
            "pct_chg": csi300_snapshot["pct_chg"],
            "pe": pe_value,
            "pe_source_date": pe_source_date,
        },
    }


def _ensure_schemas(conn: duckdb.DuckDBPyConnection) -> None:
    for relative_path in ("11_choice_macro.sql", "21_choice_stock.sql", "27_choice_stock_factor_snapshot.sql"):
        text = (REGISTRY_DIR / relative_path).read_text(encoding="utf-8")
        for statement in parse_registry_sql_text(text):
            conn.execute(statement)
    ensure_choice_stock_schema(conn)


def _write_stock_inputs(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    source_date: str,
    daily_records: list[dict[str, object]],
    limit_records: list[dict[str, object]],
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> dict[str, int]:
    source_counts = {
        "choice_stock_universe": _count_rows(conn, "choice_stock_universe", "as_of_date", source_date),
        "choice_stock_sector_membership": _count_rows(conn, "choice_stock_sector_membership", "as_of_date", source_date),
        "choice_stock_limit_quality": _count_rows(conn, "choice_stock_limit_quality", "as_of_date", source_date),
    }
    if source_counts["choice_stock_universe"] <= 0 or source_counts["choice_stock_sector_membership"] <= 0:
        raise RuntimeError(f"Prior stock universe/sector inputs are missing for {source_date}.")

    for table, column in (
        ("choice_stock_request_audit", "as_of_date"),
        ("choice_stock_universe", "as_of_date"),
        ("choice_stock_sector_membership", "as_of_date"),
        ("choice_stock_daily_observation", "trade_date"),
        ("choice_stock_limit_quality", "as_of_date"),
    ):
        conn.execute(f"delete from {table} where {column} = ?", [target_date])

    conn.execute(
        """
        insert into choice_stock_universe
        select ?, stock_code, stock_name, field_key, ?, ?, ?, ?
        from choice_stock_universe
        where as_of_date = ?
        """,
        [target_date, source_version, vendor_version, RULE_VERSION, run_id, source_date],
    )
    conn.execute(
        """
        insert into choice_stock_sector_membership
        select ?, stock_code, sw2021, sw2021code, field_key, ?, ?, ?, ?
        from choice_stock_sector_membership
        where as_of_date = ?
        """,
        [target_date, source_version, vendor_version, RULE_VERSION, run_id, source_date],
    )

    limit_by_code = {_text(row.get("ts_code")): row for row in limit_records if _text(row.get("ts_code"))}
    previous_limit_days = _load_previous_limit_days(conn, source_date)
    previous_turn = _load_previous_turn(conn, source_date)
    daily_rows = []
    limit_quality_rows = []
    daily_field_keys = json.dumps(
        [
            "daily_limit_flags",
            "daily_ohlcv_amount",
            "daily_return_turnover_amplitude",
            "daily_trade_status",
        ],
        separators=(",", ":"),
    )
    for record in daily_records:
        stock_code = _text(record.get("ts_code"))
        if not stock_code:
            continue
        limit_record = limit_by_code.get(stock_code, {})
        open_value = _float_or_none(record.get("open"))
        high_value = _float_or_none(record.get("high"))
        low_value = _float_or_none(record.get("low"))
        close_value = _float_or_none(record.get("close"))
        pre_close = _float_or_none(record.get("pre_close"))
        pct_chg = _float_or_none(record.get("pct_chg"))
        amplitude = None
        if pre_close and high_value is not None and low_value is not None and pre_close > 0:
            amplitude = (high_value - low_value) / pre_close * 100.0
        up_limit = _float_or_none(limit_record.get("up_limit"))
        down_limit = _float_or_none(limit_record.get("down_limit"))
        is_high_limit = close_value is not None and up_limit is not None and close_value >= up_limit * 0.999
        is_low_limit = close_value is not None and down_limit is not None and close_value <= down_limit * 1.001
        prev_high_days, prev_low_days = previous_limit_days.get(stock_code, (0, 0))
        hlimitedays = prev_high_days + 1 if is_high_limit else 0
        llimitedays = prev_low_days + 1 if is_low_limit else 0
        daily_rows.append(
            (
                target_date,
                stock_code,
                open_value,
                high_value,
                low_value,
                close_value,
                _float_or_none(record.get("vol")),
                _float_or_none(record.get("amount")),
                pct_chg,
                previous_turn.get(stock_code),
                amplitude,
                "交易",
                _number_text(up_limit),
                _number_text(down_limit),
                daily_field_keys,
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
        )
        limit_quality_rows.append(
            (
                target_date,
                stock_code,
                "1" if is_high_limit else "0",
                "1" if is_low_limit else "0",
                hlimitedays,
                llimitedays,
                "point_in_time_limit_streaks",
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
        )

    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        daily_rows,
    )
    conn.executemany(
        "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        limit_quality_rows,
    )
    _write_request_audits(
        conn,
        target_date=target_date,
        source_date=source_date,
        daily_count=len(daily_rows),
        limit_count=len(limit_quality_rows),
        source_counts=source_counts,
        source_version=source_version,
        vendor_version=vendor_version,
        run_id=run_id,
    )
    return {
        "universe": source_counts["choice_stock_universe"],
        "sector_membership": source_counts["choice_stock_sector_membership"],
        "daily_observation": len(daily_rows),
        "limit_quality": len(limit_quality_rows),
        "request_audit": len(REQUIRED_CHOICE_STOCK_REQUEST_ITEMS),
        "turn_carry_forward": sum(1 for row in daily_rows if row[9] is not None),
    }


def _write_request_audits(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    source_date: str,
    daily_count: int,
    limit_count: int,
    source_counts: dict[str, int],
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> None:
    row_counts = {
        "stock_universe:a_share_universe_sector_001004": source_counts["choice_stock_universe"],
        "sector_membership:sw2021_industry_membership": source_counts["choice_stock_sector_membership"],
        "sector_strength:daily_return_turnover_amplitude": daily_count,
        "stock_ohlcv:daily_ohlcv_amount": daily_count,
        "stock_status:daily_trade_status": daily_count,
        "limit_up_quality:daily_limit_flags": daily_count,
        "limit_up_quality:point_in_time_limit_streaks": limit_count,
    }
    request_meta = {
        "supplement_kind": "after_close",
        "source_as_of_date": source_date,
        "daily_vendor": "tushare.daily",
        "limit_vendor": "tushare.stk_limit",
        "turn_source": f"previous_choice_stock_daily_observation:{source_date}",
    }
    rows = []
    for input_family, field_key in REQUIRED_CHOICE_STOCK_REQUEST_ITEMS:
        item = f"{input_family}:{field_key}"
        rows.append(
            (
                run_id,
                target_date,
                input_family,
                field_key,
                "supplement",
                item,
                json.dumps(request_meta, ensure_ascii=False, sort_keys=True),
                "",
                "completed_tushare_fallback" if input_family in {"sector_strength", "stock_ohlcv", "stock_status"} else "completed",
                row_counts[item],
                0,
                f"Supplemented after close; slow-moving dimensions and turn carried from {source_date}.",
                source_version,
                vendor_version,
                RULE_VERSION,
            )
        )
    conn.executemany("insert into choice_stock_request_audit values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def _write_factor_snapshot(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    source_date: str,
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> int:
    base_rows = conn.execute(
        """
        select
          stock_code, pe, pb, ps, roe, gross_margin, dividend_yield, industry
        from choice_stock_factor_snapshot
        where as_of_date = ?
        """,
        [source_date],
    ).fetchall()
    if not base_rows:
        raise RuntimeError(f"No prior factor snapshot is available for {source_date}.")
    stock_codes = [str(row[0]) for row in base_rows if str(row[0] or "").strip()]
    price_metrics = _price_metrics(conn, target_date=target_date, stock_codes=stock_codes)
    rows = []
    for stock_code, pe, pb, ps, roe, gross_margin, dividend_yield, industry in base_rows:
        code = str(stock_code)
        metrics = price_metrics.get(code, {})
        rows.append(
            (
                target_date,
                code,
                pe,
                pb,
                ps,
                roe,
                gross_margin,
                metrics.get("three_month_return", 0.0),
                metrics.get("twelve_month_return", 0.0),
                metrics.get("volatility", 0.0),
                dividend_yield,
                industry,
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
        )
    conn.execute("delete from choice_stock_factor_snapshot where as_of_date = ?", [target_date])
    conn.executemany("insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def _write_macro_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    csi300_snapshot: dict[str, float],
    pe_value: float,
    pe_source_date: str,
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> int:
    for table, column in (("fact_choice_macro_daily", "trade_date"), ("choice_market_snapshot", "trade_date")):
        placeholders = ", ".join("?" for _ in REQUIRED_MACRO_SERIES)
        conn.execute(
            f"delete from {table} where {column} = ? and series_id in ({placeholders})",
            [target_date, *REQUIRED_MACRO_SERIES],
        )
    fact_rows = [
        ("CA.CSI300", "CSI300 close", target_date, csi300_snapshot["close"], "daily", "index", "ok"),
        ("CA.CSI300_PCT_CHG", "CSI300 pct_chg", target_date, csi300_snapshot["pct_chg"], "daily", "%", "ok"),
        (
            "CA.CSI300_PE",
            "CSI300 PE",
            target_date,
            pe_value,
            "daily",
            "x",
            f"supplemental_previous:{pe_source_date}",
        ),
    ]
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                series_id,
                series_name,
                trade_date,
                value,
                frequency,
                unit,
                source_version,
                vendor_version,
                RULE_VERSION,
                quality_flag,
                run_id,
            )
            for series_id, series_name, trade_date, value, frequency, unit, quality_flag in fact_rows
        ],
    )
    conn.executemany(
        "insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                series_id,
                series_name,
                "sina.index_spot:sh000300" if series_id != "CA.CSI300_PE" else f"previous_fact_choice_macro_daily:{pe_source_date}",
                "sina" if series_id != "CA.CSI300_PE" else "local_previous_fact",
                trade_date,
                value,
                frequency,
                unit,
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for series_id, series_name, trade_date, value, frequency, unit, _quality_flag in fact_rows
        ],
    )
    return len(fact_rows)


def _write_materialize_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    source_date: str,
    source_version: str,
    vendor_version: str,
    run_id: str,
    row_count: int,
    started_at: str,
) -> None:
    conn.execute("delete from choice_stock_materialize_run where as_of_date = ? and run_id = ?", [target_date, run_id])
    conn.execute(
        "insert into choice_stock_materialize_run values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            run_id,
            target_date,
            "completed",
            f"supplement:carried_from={source_date}",
            source_version,
            vendor_version,
            RULE_VERSION,
            len(REQUIRED_CHOICE_STOCK_REQUEST_ITEMS),
            row_count,
            started_at,
            datetime.now(UTC).isoformat(),
            "",
        ],
    )


def _fetch_sina_csi300_snapshot() -> dict[str, float]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required for Sina CSI300 supplement.") from exc
    frame = ak.stock_zh_index_spot_sina()
    records = _records(frame)
    for record in records:
        values = list(record.values())
        if not values:
            continue
        code = str(values[0] or "").strip().lower()
        if code not in {"sh000300", "sz399300"}:
            continue
        close_value = _float_or_none(values[2] if len(values) > 2 else None)
        pct_chg = _float_or_none(values[4] if len(values) > 4 else None)
        if close_value is None or pct_chg is None:
            continue
        return {"close": close_value, "pct_chg": pct_chg}
    raise RuntimeError("Sina index spot did not return sh000300/sz399300.")


def _latest_choice_stock_source_date(conn: duckdb.DuckDBPyConnection, target_date: str) -> str | None:
    row = conn.execute(
        """
        select max(as_of_date)
        from choice_stock_universe
        where cast(as_of_date as date) < cast(? as date)
        """,
        [target_date],
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _latest_macro_value(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_id: str,
    as_of_date: str,
) -> tuple[float | None, str | None]:
    row = conn.execute(
        """
        select value_numeric, trade_date
        from fact_choice_macro_daily
        where series_id = ?
          and cast(trade_date as date) < cast(? as date)
          and value_numeric is not null
        order by cast(trade_date as date) desc
        limit 1
        """,
        [series_id, as_of_date],
    ).fetchone()
    if not row:
        return None, None
    return _float_or_none(row[0]), str(row[1])


def _load_previous_limit_days(conn: duckdb.DuckDBPyConnection, source_date: str) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        """
        select stock_code, coalesce(hlimitedays, 0), coalesce(llimitedays, 0)
        from choice_stock_limit_quality
        where as_of_date = ?
        """,
        [source_date],
    ).fetchall()
    return {str(stock_code): (int(high_days or 0), int(low_days or 0)) for stock_code, high_days, low_days in rows}


def _load_previous_turn(conn: duckdb.DuckDBPyConnection, source_date: str) -> dict[str, float]:
    rows = conn.execute(
        """
        select stock_code, turn
        from choice_stock_daily_observation
        where trade_date = ?
          and turn is not null
        """,
        [source_date],
    ).fetchall()
    values: dict[str, float] = {}
    for stock_code, turn_value in rows:
        value = _float_or_none(turn_value)
        if value is not None:
            values[str(stock_code)] = value
    return values


def _price_metrics(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    stock_codes: list[str],
) -> dict[str, dict[str, float]]:
    stock_code_set = set(stock_codes)
    history_start = (date.fromisoformat(target_date) - timedelta(days=380)).isoformat()
    rows = conn.execute(
        """
        select trade_date, stock_code, close_value
        from choice_stock_daily_observation
        where cast(trade_date as date) >= cast(? as date)
          and cast(trade_date as date) <= cast(? as date)
          and close_value is not null
          and close_value > 0
        order by trade_date, stock_code
        """,
        [history_start, target_date],
    ).fetchall()
    by_stock: dict[str, list[tuple[date, float]]] = {stock_code: [] for stock_code in stock_codes}
    for trade_date_raw, stock_code_raw, close_value_raw in rows:
        stock_code = str(stock_code_raw)
        if stock_code not in stock_code_set:
            continue
        close_value = _float_or_none(close_value_raw)
        if close_value is None or close_value <= 0:
            continue
        by_stock.setdefault(stock_code, []).append((date.fromisoformat(str(trade_date_raw)[:10]), close_value))

    as_of = date.fromisoformat(target_date)
    return {
        stock_code: {
            "three_month_return": _return_since(points, as_of - timedelta(days=90)),
            "twelve_month_return": _return_since(points, as_of - timedelta(days=365)),
            "volatility": _annualized_volatility(points),
        }
        for stock_code, points in by_stock.items()
    }


def _return_since(points: list[tuple[date, float]], since_date: date) -> float:
    if len(points) < 2:
        return 0.0
    ordered = sorted(points, key=lambda item: item[0])
    latest_close = ordered[-1][1]
    start_candidates = [item for item in ordered if item[0] >= since_date]
    start_close = (start_candidates[0] if start_candidates else ordered[0])[1]
    if start_close <= 0:
        return 0.0
    return latest_close / start_close - 1


def _annualized_volatility(points: list[tuple[date, float]]) -> float:
    if len(points) < 3:
        return 0.0
    ordered = sorted(points, key=lambda item: item[0])
    returns = [
        current[1] / previous[1] - 1
        for previous, current in zip(ordered, ordered[1:], strict=False)
        if previous[1] > 0
    ]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return math.sqrt(variance) * math.sqrt(252)


def _count_rows(conn: duckdb.DuckDBPyConnection, table: str, column: str, value: str) -> int:
    row = conn.execute(f"select count(*)::integer from {table} where {column} = ?", [value]).fetchone()
    return int(row[0] or 0) if row else 0


def _build_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"sv_livermore_after_close_supplement_{digest}"


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _normalize_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip().replace("/", "-")[:10]
    return date.fromisoformat(text).isoformat()


def _records(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _text(value: object) -> str:
    return str(value or "").strip()


def _float_or_none(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _number_text(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}".rstrip("0").rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Supplement Livermore after-close inputs for one trading date.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--source-as-of-date", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-cross-era-backfill",
        action="store_true",
        help="知情放行代际守卫:允许 tushare 口径 supplement vendor 补写 choice_native 代际日期。",
    )
    args = parser.parse_args()
    try:
        payload = supplement_livermore_after_close_inputs(
            duckdb_path=args.duckdb_path,
            target_date=args.target_date,
            source_as_of_date=args.source_as_of_date or None,
            dry_run=args.dry_run,
            allow_cross_era_backfill=args.allow_cross_era_backfill,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
