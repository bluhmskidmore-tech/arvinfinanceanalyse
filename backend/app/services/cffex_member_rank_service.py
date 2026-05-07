from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import (
    DEFAULT_CFFEX_CONTRACTS,
    CffexMemberRankRow,
    ensure_cffex_member_rank_schema,
    load_member_rank_frame,
    normalize_cffex_contract,
    normalize_trade_date,
    product_code_from_contract,
    replace_member_rank_rows,
    rows_from_records,
)
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)


@dataclass(frozen=True)
class SourceFetchResult:
    source_vendor: str
    contract: str
    status: str
    row_count: int
    detail: str = ""


def materialize_cffex_member_rank(
    *,
    duckdb_path: str | Path | None = None,
    trade_date: str | None = None,
    contracts: tuple[str, ...] = DEFAULT_CFFEX_CONTRACTS,
    sources: tuple[str, ...] = ("choice", "tushare"),
) -> dict[str, object]:
    settings = get_settings()
    resolved_path = Path(duckdb_path or settings.duckdb_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    ingest_batch_id = _new_ingest_batch_id()
    attempts: list[SourceFetchResult] = []
    conn = duckdb.connect(str(resolved_path), read_only=False)
    try:
        ensure_cffex_member_rank_schema(conn)
        for contract in contracts:
            normalized_contract = normalize_cffex_contract(contract)
            for source in sources:
                source_name = source.strip().lower()
                if source_name == "choice":
                    result, rows = _fetch_choice_rows(
                        trade_date=trade_date,
                        contract=normalized_contract,
                        ingest_batch_id=ingest_batch_id,
                    )
                elif source_name == "tushare":
                    result, rows = _fetch_tushare_rows(
                        trade_date=trade_date,
                        contract=normalized_contract,
                        ingest_batch_id=ingest_batch_id,
                        settings=settings,
                    )
                else:
                    result, rows = (
                        SourceFetchResult(source_name, normalized_contract, "unsupported_source", 0),
                        [],
                    )
                if rows:
                    replace_member_rank_rows(conn, rows)
                    result = SourceFetchResult(result.source_vendor, result.contract, "materialized", len(rows), result.detail)
                attempts.append(result)
    finally:
        conn.close()
    return {
        "ingest_batch_id": ingest_batch_id,
        "trade_date": normalize_trade_date(trade_date) if trade_date else None,
        "contracts": [normalize_cffex_contract(item) for item in contracts],
        "sources": list(sources),
        "attempts": [attempt.__dict__ for attempt in attempts],
        "row_count": sum(attempt.row_count for attempt in attempts if attempt.status == "materialized"),
    }


def ensure_cffex_member_rank_for_request(
    *,
    duckdb_path: str | Path | None = None,
    trade_date: str,
    contract: str,
) -> dict[str, object]:
    settings = get_settings()
    resolved_path = Path(duckdb_path or settings.duckdb_path)
    normalized_contract = normalize_cffex_contract(contract)
    normalized_date = normalize_trade_date(trade_date)
    existing = load_member_rank_frame(resolved_path, trade_date=normalized_date, contract=normalized_contract)
    if not existing.empty:
        return {
            "status": "cached",
            "row_count": int(len(existing)),
            "trade_date": normalized_date,
            "contract": normalized_contract,
        }
    result = materialize_cffex_member_rank(
        duckdb_path=resolved_path,
        trade_date=normalized_date,
        contracts=(normalized_contract,),
    )
    refreshed = load_member_rank_frame(resolved_path, trade_date=normalized_date, contract=normalized_contract)
    return {
        **result,
        "status": "materialized" if not refreshed.empty else "missing",
        "row_count": int(len(refreshed)),
        "trade_date": normalized_date,
        "contract": normalized_contract,
    }


def _fetch_tushare_rows(
    *,
    trade_date: str | None,
    contract: str,
    ingest_batch_id: str,
    settings: Any,
) -> tuple[SourceFetchResult, list[CffexMemberRankRow]]:
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        return SourceFetchResult("tushare", contract, "missing_token", 0), []
    try:
        ts = import_tushare_pro()
        pro = ts.pro_api(token)
    except RuntimeError as exc:
        return SourceFetchResult("tushare", contract, "unavailable", 0, str(exc)), []

    product_code = product_code_from_contract(contract)
    try:
        frame, source_date = _fetch_tushare_product_frame(
            pro=pro,
            product_code=product_code,
            trade_date=trade_date,
        )
    except Exception as exc:  # vendor SDK surface varies
        return SourceFetchResult("tushare", contract, "error", 0, str(exc)), []
    if frame.empty:
        return SourceFetchResult("tushare", contract, "empty", 0, "no rows returned"), []
    records = _records_from_any(frame)
    rows = rows_from_records(
        records,
        source_vendor="tushare",
        requested_contract=contract,
        ingest_batch_id=ingest_batch_id,
        source_version=f"sv_tushare_fut_holding_{_source_date_label(source_date)}",
        vendor_version="vv_tushare_fut_holding",
    )
    if rows:
        return SourceFetchResult("tushare", contract, "fetched", len(rows)), rows
    return SourceFetchResult("tushare", contract, "empty", 0, "no parseable rows returned"), []


def _fetch_choice_rows(
    *,
    trade_date: str | None,
    contract: str,
    ingest_batch_id: str,
) -> tuple[SourceFetchResult, list[CffexMemberRankRow]]:
    try:
        result = ChoiceClient().fut_transaction_rankings(
            _choice_symbol(contract),
            normalize_trade_date(trade_date) if trade_date else "",
            "volume,long,short",
        )
    except (ImportError, RuntimeError, AttributeError) as exc:
        return SourceFetchResult("choice", contract, "unavailable", 0, str(exc)), []
    error_code = int(getattr(result, "ErrorCode", 0) or 0)
    if error_code != 0:
        detail = str(getattr(result, "ErrorMsg", f"Choice returned ErrorCode={error_code}"))
        return SourceFetchResult("choice", contract, "error", 0, detail), []
    records = _records_from_any(result)
    rows = rows_from_records(
        records,
        source_vendor="choice",
        requested_contract=contract,
        ingest_batch_id=ingest_batch_id,
        source_version=f"sv_choice_fut_transaction_rankings_{_source_date_label(trade_date)}",
        vendor_version="vv_choice_fut_transaction_rankings",
    )
    if not rows:
        return SourceFetchResult("choice", contract, "empty", 0, "no parseable rows returned"), []
    return SourceFetchResult("choice", contract, "fetched", len(rows)), rows


def _records_from_any(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, dict):
        return [value]
    for attr in ("Data", "data", "records"):
        data = getattr(value, attr, None)
        if data is not None and data is not value:
            records = _records_from_any(data)
            if records:
                return records
    if isinstance(value, list | tuple):
        records: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                records.append(item)
            elif hasattr(item, "__dict__"):
                records.append(dict(vars(item)))
        return records
    return []


def _fetch_tushare_product_frame(
    *,
    pro: Any,
    product_code: str,
    trade_date: str | None,
) -> tuple[pd.DataFrame, str | None]:
    query_date = _to_tushare_date(trade_date) if trade_date else _latest_tushare_product_date(pro, product_code)
    if not query_date:
        return pd.DataFrame(), None
    for exchange in ("CFFEX", "CFE", ""):
        kwargs: dict[str, str] = {"trade_date": query_date}
        if exchange:
            kwargs["exchange"] = exchange
        frame = pro.fut_holding(**kwargs)
        if frame is None or len(frame) == 0:
            continue
        aggregated = _aggregate_tushare_product_frame(frame, product_code)
        if not aggregated.empty:
            return aggregated, query_date
    return pd.DataFrame(), query_date


def _latest_tushare_product_date(pro: Any, product_code: str) -> str | None:
    for exchange in ("CFFEX", "CFE", ""):
        kwargs: dict[str, str] = {"symbol": product_code}
        if exchange:
            kwargs["exchange"] = exchange
        try:
            frame = pro.fut_holding(**kwargs)
        except Exception:
            continue
        if frame is None or len(frame) == 0 or "trade_date" not in frame.columns:
            continue
        dates = [str(item) for item in frame["trade_date"].dropna().tolist() if str(item).strip()]
        if dates:
            return max(dates)
    return None


def _aggregate_tushare_product_frame(frame: pd.DataFrame, product_code: str) -> pd.DataFrame:
    out = frame.copy()
    if "symbol" not in out.columns or "broker" not in out.columns:
        return pd.DataFrame()
    out["symbol_text"] = out["symbol"].fillna("").astype(str).str.upper()
    out = out[
        (out["symbol_text"].map(_leading_letters) == product_code)
        & out["symbol_text"].str.contains(r"\d", regex=True)
    ].copy()
    if out.empty:
        return pd.DataFrame()
    numeric_columns = ["vol", "vol_chg", "long_hld", "long_chg", "short_hld", "short_chg"]
    for column in numeric_columns:
        if column not in out.columns:
            out[column] = 0.0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    grouped = (
        out.groupby(["trade_date", "broker"], as_index=False)[numeric_columns]
        .sum()
        .sort_values(["vol", "long_hld", "short_hld"], ascending=False)
    )
    grouped["symbol"] = product_code
    return grouped


def _leading_letters(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalpha())


def _choice_symbol(contract: str) -> str:
    product = product_code_from_contract(contract)
    return f"CFFEX.{product}"


def _to_tushare_date(value: str | None) -> str:
    date_value = normalize_trade_date(value or "")
    return date_value.replace("-", "")


def _source_date_label(value: str | None) -> str:
    if not value:
        return "latest"
    return _to_tushare_date(value)


def _new_ingest_batch_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"cffex-member-rank-{stamp}-{uuid.uuid4().hex[:8]}"
