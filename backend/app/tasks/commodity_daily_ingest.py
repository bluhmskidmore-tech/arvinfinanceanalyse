"""Ingest main-contract commodity futures + Nanhua index daily bars into DuckDB."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import duckdb  # noqa: E402
from backend.app.governance.locks import LockDefinition, acquire_lock  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection  # noqa: E402
from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text  # noqa: E402

logger = logging.getLogger(__name__)

COMMODITY_DAILY_LOCK = LockDefinition(key="lock:duckdb:commodity-daily-ingest", ttl_seconds=900)
DEFAULT_START_DATE = "2024-01-01"
RULE_VERSION = "rv_commodity_daily_v1"
TUSHARE_API_PACE_SECONDS = 1.5


def _fetch_with_retry(fn, *args, max_retries=3, base_delay=2.0, **kwargs):
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning("Retry %s/%s after %ss: %s", attempt + 1, max_retries, delay, e)
            time.sleep(delay)


def _tushare_call(fn, *args, **kwargs):
    time.sleep(TUSHARE_API_PACE_SECONDS)
    return _fetch_with_retry(fn, *args, **kwargs)


def ensure_commodity_futures_daily_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "29_commodity_futures_daily.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


INSERT_SQL = """
insert into fact_commodity_futures_daily (
  trade_date,
  product_code,
  contract_code,
  exchange,
  open_value,
  high_value,
  low_value,
  close_value,
  settle_value,
  volume,
  open_interest,
  source_version,
  vendor_version,
  rule_version
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class CommodityProductSpec:
    product_code: str
    name_zh: str
    kind: Literal["futures", "index"]
    exchange: str
    tushare_ts_code: str
    akshare_symbol: str | None = None


COMMODITY_PRODUCTS: tuple[CommodityProductSpec, ...] = (
    CommodityProductSpec("RB", "螺纹钢", "futures", "SHF", "RB.SHF", "RB0"),
    CommodityProductSpec("HC", "热轧卷板", "futures", "SHF", "HC.SHF", "HC0"),
    CommodityProductSpec("I", "铁矿石", "futures", "DCE", "I.DCE", "I0"),
    CommodityProductSpec("JM", "焦煤", "futures", "DCE", "JM.DCE", "JM0"),
    CommodityProductSpec("J", "焦炭", "futures", "DCE", "J.DCE", "J0"),
    CommodityProductSpec("CU", "铜", "futures", "SHF", "CU.SHF", "CU0"),
    CommodityProductSpec("AL", "铝", "futures", "SHF", "AL.SHF", "AL0"),
    CommodityProductSpec("ZN", "锌", "futures", "SHF", "ZN.SHF", "ZN0"),
    CommodityProductSpec("SC", "原油", "futures", "INE", "SC.INE", "SC0"),
    CommodityProductSpec("TA", "PTA", "futures", "ZCE", "TA.ZCE", "TA0"),
    CommodityProductSpec("MA", "甲醇", "futures", "ZCE", "MA.ZCE", "MA0"),
    CommodityProductSpec("M", "豆粕", "futures", "DCE", "M.DCE", "M0"),
    CommodityProductSpec("P", "棕榈油", "futures", "DCE", "P.DCE", "P0"),
    CommodityProductSpec("AU", "黄金", "futures", "SHF", "AU.SHF", "AU0"),
    CommodityProductSpec("AG", "白银", "futures", "SHF", "AG.SHF", "AG0"),
    CommodityProductSpec("NHCI", "南华商品指数", "index", "NH", "NHCI.NH", None),
    CommodityProductSpec("NHII", "南华工业品指数", "index", "NH", "NHII.NH", None),
)


def _emit_json_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


def _normalize_trade_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    return None


def _compact_date(value: str) -> str:
    return str(value).replace("-", "")


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _source_version(prefix: str, records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256(
        json.dumps(records, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_{prefix}_{digest}"


def _exchange_from_ts_code(ts_code: str, *, fallback: str) -> str:
    if "." in ts_code:
        return ts_code.rsplit(".", 1)[-1].upper()
    return fallback


def _iter_weekday_dates(*, start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date.")
    current = start
    resolved: list[str] = []
    while current <= end:
        if current.weekday() < 5:
            resolved.append(current.isoformat())
        current += timedelta(days=1)
    return resolved


def _estimate_trading_days(*, start_date: str, end_date: str, pro: Any | None) -> list[str]:
    if pro is not None:
        try:
            frame = _tushare_call(
                pro.trade_cal,
                exchange="SSE",
                start_date=_compact_date(start_date),
                end_date=_compact_date(end_date),
                is_open="1",
            )
            dates = [
                normalized
                for normalized in (_normalize_trade_date(item.get("cal_date")) for item in _records_from_frame(frame))
                if normalized
            ]
            if dates:
                return sorted(dates)
        except Exception as exc:  # noqa: BLE001
            logger.warning("trade_cal unavailable, falling back to weekday estimate: %s", exc)
    return _iter_weekday_dates(start_date=start_date, end_date=end_date)


def _row_tuple(row: dict[str, object]) -> tuple[object, ...]:
    return (
        row["trade_date"],
        row["product_code"],
        row.get("contract_code"),
        row.get("exchange"),
        row.get("open_value"),
        row.get("high_value"),
        row.get("low_value"),
        row.get("close_value"),
        row.get("settle_value"),
        row.get("volume"),
        row.get("open_interest"),
        row.get("source_version"),
        row.get("vendor_version"),
        row.get("rule_version") or RULE_VERSION,
    )


def _build_row(
    *,
    spec: CommodityProductSpec,
    trade_date: str,
    contract_code: str | None,
    open_value: float | None,
    high_value: float | None,
    low_value: float | None,
    close_value: float | None,
    settle_value: float | None,
    volume: float | None,
    open_interest: float | None,
    source_version: str,
    vendor_version: str,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "product_code": spec.product_code,
        "contract_code": contract_code,
        "exchange": spec.exchange,
        "open_value": open_value,
        "high_value": high_value,
        "low_value": low_value,
        "close_value": close_value,
        "settle_value": settle_value,
        "volume": volume,
        "open_interest": open_interest,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": RULE_VERSION,
    }


def _fetch_tushare_index_rows(
    *,
    spec: CommodityProductSpec,
    pro: Any,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    records = _records_from_tushare_index(pro, spec=spec, start_date=start_date, end_date=end_date)
    vendor_version = f"vv_tushare_index_daily_{spec.product_code}_{_compact_date(end_date)}"
    source_version = _source_version(f"tushare_index_daily_{spec.product_code.lower()}", records)
    rows: list[dict[str, object]] = []
    for record in records:
        trade_date = _normalize_trade_date(record.get("trade_date"))
        if trade_date is None or trade_date < start_date or trade_date > end_date:
            continue
        rows.append(
            _build_row(
                spec=spec,
                trade_date=trade_date,
                contract_code=spec.tushare_ts_code,
                open_value=_coerce_float(record.get("open")),
                high_value=_coerce_float(record.get("high")),
                low_value=_coerce_float(record.get("low")),
                close_value=_coerce_float(record.get("close")),
                settle_value=None,
                volume=_coerce_float(record.get("vol")),
                open_interest=None,
                source_version=source_version,
                vendor_version=vendor_version,
            )
        )
    return rows


def _records_from_tushare_index(
    pro: Any,
    *,
    spec: CommodityProductSpec,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    return _records_from_frame(
        _tushare_call(
            pro.index_daily,
            ts_code=spec.tushare_ts_code,
            start_date=_compact_date(start_date),
            end_date=_compact_date(end_date),
        )
    )


def _fetch_tushare_futures_rows(
    *,
    spec: CommodityProductSpec,
    pro: Any,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    mapping_records = _records_from_frame(
        _tushare_call(
            pro.fut_mapping,
            ts_code=spec.tushare_ts_code,
            start_date=_compact_date(start_date),
            end_date=_compact_date(end_date),
        )
    )
    if not mapping_records:
        return []

    contract_bounds: dict[str, tuple[str, str]] = {}
    mapping_by_trade_date: dict[str, str] = {}
    for record in mapping_records:
        trade_date = _normalize_trade_date(record.get("trade_date"))
        contract_code = str(record.get("mapping_ts_code") or "").strip()
        if trade_date is None or not contract_code:
            continue
        if trade_date < start_date or trade_date > end_date:
            continue
        mapping_by_trade_date[trade_date] = contract_code
        bounds = contract_bounds.get(contract_code)
        if bounds is None:
            contract_bounds[contract_code] = (trade_date, trade_date)
        else:
            contract_bounds[contract_code] = (min(bounds[0], trade_date), max(bounds[1], trade_date))

    daily_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for contract_code, (contract_start, contract_end) in contract_bounds.items():
        try:
            daily_records = _records_from_frame(
                _tushare_call(
                    pro.fut_daily,
                    ts_code=contract_code,
                    start_date=_compact_date(contract_start),
                    end_date=_compact_date(contract_end),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping fut_daily for %s (%s): %s",
                contract_code,
                spec.product_code,
                exc,
            )
            continue
        for record in daily_records:
            trade_date = _normalize_trade_date(record.get("trade_date"))
            if trade_date is None:
                continue
            daily_by_key[(contract_code, trade_date)] = record

    joined_records: list[dict[str, object]] = []
    for trade_date, contract_code in sorted(mapping_by_trade_date.items()):
        daily = daily_by_key.get((contract_code, trade_date))
        if daily is None:
            continue
        joined_records.append(
            {
                **daily,
                "trade_date": trade_date,
                "mapping_ts_code": contract_code,
            }
        )

    vendor_version = f"vv_tushare_fut_daily_{spec.product_code}_{spec.exchange}_{_compact_date(end_date)}"
    source_version = _source_version(f"tushare_fut_daily_{spec.product_code.lower()}", joined_records)
    rows: list[dict[str, object]] = []
    for record in joined_records:
        trade_date = str(record["trade_date"])
        contract_code = str(record.get("mapping_ts_code") or record.get("ts_code") or "").strip() or None
        rows.append(
            _build_row(
                spec=spec,
                trade_date=trade_date,
                contract_code=contract_code,
                open_value=_coerce_float(record.get("open")),
                high_value=_coerce_float(record.get("high")),
                low_value=_coerce_float(record.get("low")),
                close_value=_coerce_float(record.get("close")),
                settle_value=_coerce_float(record.get("settle")),
                volume=_coerce_float(record.get("vol")),
                open_interest=_coerce_float(record.get("oi")),
                source_version=source_version,
                vendor_version=vendor_version,
            )
        )
    return rows


def _akshare_field(record: dict[str, object], *names: str) -> object | None:
    for name in names:
        if name in record and record[name] is not None:
            return record[name]
    return None


def _fetch_akshare_futures_rows(
    *,
    spec: CommodityProductSpec,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    if not spec.akshare_symbol:
        return []
    import akshare as ak  # noqa: PLC0415

    frame = ak.futures_main_sina(
        symbol=spec.akshare_symbol,
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
    )
    records = _records_from_frame(frame)
    vendor_version = f"vv_akshare_futures_main_sina_{spec.product_code}_{_compact_date(end_date)}"
    source_version = _source_version(f"akshare_futures_main_sina_{spec.product_code.lower()}", records)
    rows: list[dict[str, object]] = []
    for record in records:
        trade_date = _normalize_trade_date(_akshare_field(record, "日期", "date", "trade_date"))
        if trade_date is None or trade_date < start_date or trade_date > end_date:
            continue
        rows.append(
            _build_row(
                spec=spec,
                trade_date=trade_date,
                contract_code=spec.akshare_symbol,
                open_value=_coerce_float(_akshare_field(record, "开盘价", "open")),
                high_value=_coerce_float(_akshare_field(record, "最高价", "high")),
                low_value=_coerce_float(_akshare_field(record, "最低价", "low")),
                close_value=_coerce_float(_akshare_field(record, "收盘价", "close")),
                settle_value=_coerce_float(_akshare_field(record, "动态结算价", "settle")),
                volume=_coerce_float(_akshare_field(record, "成交量", "volume", "vol")),
                open_interest=_coerce_float(_akshare_field(record, "持仓量", "hold", "oi", "open_interest")),
                source_version=source_version,
                vendor_version=vendor_version,
            )
        )
    return rows


def _fetch_product_rows(
    *,
    spec: CommodityProductSpec,
    pro: Any | None,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, object]], str]:
    if pro is not None:
        try:
            if spec.kind == "index":
                rows = _fetch_tushare_index_rows(spec=spec, pro=pro, start_date=start_date, end_date=end_date)
            else:
                rows = _fetch_tushare_futures_rows(spec=spec, pro=pro, start_date=start_date, end_date=end_date)
            if rows:
                return rows, "tushare"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tushare fetch failed for %s: %s", spec.product_code, exc)

    try:
        rows = _fetch_akshare_futures_rows(spec=spec, start_date=start_date, end_date=end_date)
        if rows:
            return rows, "akshare"
    except Exception as exc:  # noqa: BLE001
        logger.warning("AkShare fetch failed for %s: %s", spec.product_code, exc)

    return [], "none"


def _replace_product_rows(conn: duckdb.DuckDBPyConnection, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    product_code = str(rows[0]["product_code"])
    trade_dates = sorted({str(row["trade_date"]) for row in rows})
    conn.execute("begin transaction")
    try:
        conn.execute(
            """
            delete from fact_commodity_futures_daily
            where product_code = ?
              and trade_date between ? and ?
            """,
            [product_code, trade_dates[0], trade_dates[-1]],
        )
        conn.executemany(INSERT_SQL, [_row_tuple(row) for row in rows])
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    return len(rows)


def run_commodity_daily_ingest(
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
    duckdb_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    settings = get_settings()
    resolved_end = end_date or date.today().isoformat()
    token = resolve_tushare_token_with_settings_fallback(settings)
    pro = None
    if token:
        pro = import_tushare_pro().pro_api(token)

    estimated_trade_dates = _estimate_trading_days(start_date=start_date, end_date=resolved_end, pro=pro)
    per_product: list[dict[str, object]] = []
    total_rows = 0
    vendors: set[str] = set()

    if dry_run:
        for spec in COMMODITY_PRODUCTS:
            per_product.append(
                {
                    "product_code": spec.product_code,
                    "name_zh": spec.name_zh,
                    "kind": spec.kind,
                    "tushare_ts_code": spec.tushare_ts_code,
                    "akshare_symbol": spec.akshare_symbol,
                    "estimated_rows": len(estimated_trade_dates),
                    "vendor": "estimate_only",
                }
            )
        total_rows = len(estimated_trade_dates) * len(COMMODITY_PRODUCTS)
        payload: dict[str, object] = {
            "status": "dry_run",
            "dry_run": True,
            "start_date": start_date,
            "end_date": resolved_end,
            "product_count": len(COMMODITY_PRODUCTS),
            "estimated_trading_days": len(estimated_trade_dates),
            "estimated_total_rows": total_rows,
            "tushare_token_configured": bool(token),
            "vendors_observed": sorted(vendors),
            "products": per_product,
            "rule_version": RULE_VERSION,
            "table": "fact_commodity_futures_daily",
        }
        return payload

    db_file = Path(duckdb_path or settings.duckdb_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with acquire_lock(COMMODITY_DAILY_LOCK, base_dir=db_file.parent):
        conn = duckdb.connect(str(db_file), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            for spec in COMMODITY_PRODUCTS:
                rows, vendor = _fetch_product_rows(
                    spec=spec,
                    pro=pro,
                    start_date=start_date,
                    end_date=resolved_end,
                )
                written = _replace_product_rows(conn, rows)
                vendors.add(vendor)
                per_product.append(
                    {
                        "product_code": spec.product_code,
                        "name_zh": spec.name_zh,
                        "row_count": written,
                        "vendor": vendor,
                    }
                )
                total_rows += written
        finally:
            conn.close()

    return {
        "status": "completed",
        "dry_run": False,
        "start_date": start_date,
        "end_date": resolved_end,
        "duckdb_path": str(db_file),
        "product_count": len(COMMODITY_PRODUCTS),
        "row_count": total_rows,
        "tushare_token_configured": bool(token),
        "vendors": sorted(vendors),
        "products": per_product,
        "rule_version": RULE_VERSION,
        "table": "fact_commodity_futures_daily",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest commodity futures main-contract daily bars.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date")
    parser.add_argument("--duckdb-path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = run_commodity_daily_ingest(
        start_date=args.start_date,
        end_date=args.end_date,
        duckdb_path=args.duckdb_path,
        dry_run=args.dry_run,
    )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
