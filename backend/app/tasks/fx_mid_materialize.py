from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb
import requests
from backend.app.core_finance.fx_calendar import is_cfets_fx_non_business_day
from backend.app.core_finance.fx_rates import is_valid_fx_mid_rate
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.akshare_adapter import VendorAdapter as AkShareVendorAdapter
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.choice_fx_catalog import (
    FormalFxCandidate,
    discover_formal_fx_candidates,
)
from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_fx_daily_mid_schema_if_missing,
)
from backend.app.tasks.broker import register_actor_once

logger = logging.getLogger(__name__)

CHOICE_SOURCE_NAME = "CFETS"
AKSHARE_SOURCE_NAME = "AKSHARE"
CHOICE_REQUEST_TIMEOUT_SECONDS = 5
CHOICE_FX_LOOKBACK_DAYS = 7
CHINAMONEY_FX_HISTORY_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew"
CHINAMONEY_REQUEST_TIMEOUT_SECONDS = 15
CHINAMONEY_PAIR_BY_BASE_CURRENCY = {
    "USD": "USD/CNY",
    "EUR": "EUR/CNY",
    "AUD": "AUD/CNY",
    "CAD": "CAD/CNY",
    "HKD": "HKD/CNY",
}


def resolve_fx_mid_csv_path(
    *,
    official_csv_path: str = "",
    explicit_csv_path: str,
    data_input_root: Path,
) -> Path | None:
    del data_input_root
    official = Path(official_csv_path).expanduser() if str(official_csv_path).strip() else None
    if official is not None:
        if official.exists():
            return official
        raise FileNotFoundError(f"FX official CSV not found: {official}")

    explicit = Path(explicit_csv_path).expanduser() if str(explicit_csv_path).strip() else None
    if explicit is not None:
        if explicit.exists():
            return explicit
        raise FileNotFoundError(f"FX mid CSV not found: {explicit}")

    return None


def _parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _validate_required_headers(fieldnames: list[str] | None) -> None:
    required_headers = {
        "trade_date",
        "base_currency",
        "quote_currency",
        "mid_rate",
        "source_name",
        "is_business_day",
        "is_carry_forward",
    }
    actual_headers = {str(name).strip() for name in (fieldnames or []) if str(name).strip()}
    missing_headers = sorted(required_headers - actual_headers)
    if missing_headers:
        raise ValueError(
            "FX mid CSV required headers missing: " + ", ".join(missing_headers)
        )


def _build_source_version(csv_path: Path) -> str:
    payload = csv_path.read_bytes()
    return f"sv_fx_{hashlib.sha256(payload).hexdigest()[:12]}"


def _build_choice_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_fx_choice_{digest}"


def _build_akshare_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_fx_akshare_{digest}"


def _ensure_fx_mid_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)
    ensure_fx_daily_mid_schema_if_missing(conn)


def _replace_fx_mid_rows(
    *,
    duckdb_path: str,
    rows: list[tuple[object, ...]],
) -> None:
    for row in rows:
        try:
            mid_rate = Decimal(str(row[3]))
        except (IndexError, InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Invalid formal FX mid_rate in materialize input.") from exc
        if not is_valid_fx_mid_rate(mid_rate):
            raise ValueError(
                "Invalid formal FX mid_rate in materialize input: "
                "value must be finite and greater than zero."
            )

    canonical_keys = {
        (row[0], str(row[1]).upper(), str(row[2]).upper())
        for row in rows
    }
    if len(canonical_keys) != len(rows):
        raise ValueError("Duplicate fx_daily_mid canonical grain in materialize input")

    conn = duckdb.connect(duckdb_path, read_only=False)
    transaction_started = False
    try:
        _ensure_fx_mid_table(conn)
        conn.execute("begin transaction")
        transaction_started = True
        if rows:
            conn.executemany(
                """
                insert or replace into fx_daily_mid (
                  trade_date,
                  base_currency,
                  quote_currency,
                  mid_rate,
                  source_name,
                  is_business_day,
                  is_carry_forward,
                  source_version,
                  vendor_name,
                  vendor_version,
                  vendor_series_code,
                  observed_trade_date
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.execute("commit")
        transaction_started = False
    except Exception:
        if transaction_started:
            conn.execute("rollback")
        raise
    finally:
        conn.close()


def _normalize_choice_trade_date(value: object) -> str:
    return str(value or "").strip().replace("/", "-").split(" ", 1)[0]


def _extract_choice_mid_rate(
    *,
    result: object,
    vendor_code: str,
) -> tuple[str, Decimal] | None:
    if result.__class__.__name__ == "DataFrame":
        rows = result.loc[[vendor_code]] if vendor_code in result.index else None
        if rows is None or len(rows) == 0:
            return None
        latest = rows.iloc[-1]
        value = latest["RESULT"]
        if value in (None, ""):
            return None
        return _normalize_choice_trade_date(latest["DATES"]), Decimal(str(value))

    codes = [str(code) for code in getattr(result, "Codes", [])]
    if vendor_code not in codes:
        return None
    dates = [_normalize_choice_trade_date(item) for item in getattr(result, "Dates", [])]
    if not dates:
        return None
    data = getattr(result, "Data", {})
    values = data.get(vendor_code, [])
    indicator_values = values[0] if values else []
    if not indicator_values:
        return None
    return dates[-1], Decimal(str(indicator_values[-1]))


def _invert_mid_rate(value: Decimal) -> Decimal:
    if not is_valid_fx_mid_rate(value):
        raise ValueError(
            "FX vendor returned an invalid reverse-pair mid_rate; "
            "value must be finite and greater than zero."
        )
    return Decimal("1") / value


def _normalize_vendor_row(
    *,
    requested_report_date: str,
    candidate: FormalFxCandidate,
    observed_trade_date: str,
    raw_mid_rate: Decimal,
    source_name: str,
    source_version: str,
    vendor_name: str,
    vendor_version: str,
    mid_rate_is_normalized: bool = False,
) -> tuple[object, ...]:
    if not is_valid_fx_mid_rate(raw_mid_rate):
        raise ValueError(
            f"FX vendor returned invalid mid_rate for pair={candidate.pair_label}; "
            "value must be finite and greater than zero."
        )

    requested_date = date.fromisoformat(requested_report_date)
    observed_date = date.fromisoformat(observed_trade_date)
    if observed_date > requested_date:
        raise ValueError(
            f"FX vendor returned future observed_trade_date={observed_trade_date} "
            f"for requested_report_date={requested_report_date}."
        )
    if observed_date < requested_date and not is_cfets_fx_non_business_day(
        requested_report_date,
        base_currency=candidate.base_currency,
        quote_currency=candidate.quote_currency,
    ):
        raise ValueError(
            f"Formal FX carry-forward is only allowed for confirmed non-business days; "
            f"requested_report_date={requested_report_date}, observed_trade_date={observed_trade_date}."
        )
    mid_rate = (
        raw_mid_rate
        if mid_rate_is_normalized
        else _invert_mid_rate(raw_mid_rate)
        if candidate.invert_result
        else raw_mid_rate
    )
    if not is_valid_fx_mid_rate(mid_rate):
        raise ValueError(
            f"Normalized formal FX mid_rate is invalid for pair={candidate.pair_label}; "
            "value must be finite and greater than zero."
        )
    is_business_day = observed_trade_date == requested_report_date
    return (
        requested_report_date,
        candidate.base_currency,
        candidate.quote_currency,
        mid_rate,
        source_name,
        is_business_day,
        not is_business_day,
        source_version,
        vendor_name,
        vendor_version,
        candidate.vendor_series_code,
        observed_trade_date,
    )


def _fetch_choice_fx_mid_rows_for_report_date(
    report_date: str,
    *,
    candidates: list[FormalFxCandidate],
) -> list[tuple[object, ...]]:
    requested_date = date.fromisoformat(report_date)
    client = ChoiceClient()
    vendor_codes = [candidate.vendor_series_code for candidate in candidates]

    for offset in range(CHOICE_FX_LOOKBACK_DAYS + 1):
        query_date = (requested_date - timedelta(days=offset)).isoformat()
        request_options = (
            f"IsLatest=0,StartDate={query_date},EndDate={query_date},"
            f"RECVtimeout={CHOICE_REQUEST_TIMEOUT_SECONDS}"
        )
        try:
            result = client.edb(
                vendor_codes,
                options=request_options,
                exclude_option_prefixes=("ispandas=",),
            )
        except TypeError as exc:
            if "exclude_option_prefixes" not in str(exc):
                raise
            result = client.edb(
                vendor_codes,
                options=request_options,
            )
        normalized_rows: list[tuple[object, ...]] = []
        observed_rows: list[dict[str, object]] = []
        for candidate in candidates:
            extracted = _extract_choice_mid_rate(result=result, vendor_code=candidate.vendor_series_code)
            if extracted is None:
                normalized_rows = []
                break
            observed_trade_date, raw_mid_rate = extracted
            observed_rows.append(
                {
                    "vendor_series_code": candidate.vendor_series_code,
                    "pair_label": candidate.pair_label,
                    "observed_trade_date": observed_trade_date,
                    "mid_rate": format(raw_mid_rate, "f"),
                }
            )

        if not normalized_rows and len(observed_rows) != len(candidates):
            continue

        source_version = _build_choice_source_version(
            {
                "requested_report_date": report_date,
                "query_date": query_date,
                "rows": observed_rows,
            }
        )
        vendor_version = f"vv_choice_fx_{query_date.replace('-', '')}_{hashlib.sha256(json.dumps(observed_rows, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:10]}"
        for candidate, observed in zip(candidates, observed_rows, strict=True):
            normalized_rows.append(
                _normalize_vendor_row(
                    requested_report_date=report_date,
                    candidate=candidate,
                    observed_trade_date=str(observed["observed_trade_date"]),
                    raw_mid_rate=Decimal(str(observed["mid_rate"])),
                    source_name=CHOICE_SOURCE_NAME,
                    source_version=source_version,
                    vendor_name="choice",
                    vendor_version=vendor_version,
                )
            )
        return normalized_rows
    return []


def _fetch_chinamoney_fx_mid_rows_for_report_date(
    report_date: str,
    *,
    candidates: list[FormalFxCandidate],
) -> list[tuple[object, ...]]:
    requested_date = date.fromisoformat(report_date)
    requested_pairs: list[str] = []
    for candidate in candidates:
        pair = CHINAMONEY_PAIR_BY_BASE_CURRENCY.get(candidate.base_currency.upper())
        if pair is None:
            return []
        requested_pairs.append(pair)

    start_date = (requested_date - timedelta(days=CHOICE_FX_LOOKBACK_DAYS)).isoformat()
    response = requests.post(
        CHINAMONEY_FX_HISTORY_URL,
        params={
            "startDate": start_date,
            "endDate": report_date,
            "currency": ",".join(requested_pairs),
            "pageNum": 1,
            "pageSize": CHOICE_FX_LOOKBACK_DAYS + 1,
        },
        headers={
            "Accept": "application/json",
            "Referer": "https://www.chinamoney.com.cn/chinese/bkccpr/",
            "User-Agent": "MOSS-V3 formal FX materializer",
        },
        timeout=CHINAMONEY_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []

    data_payload = payload.get("data")
    records = payload.get("records")
    if not isinstance(data_payload, dict) or not isinstance(records, list):
        return []
    response_pairs = data_payload.get("searchlist")
    if not isinstance(response_pairs, list):
        raw_currency = str(data_payload.get("currency") or "")
        response_pairs = [item.strip() for item in raw_currency.split(",") if item.strip()]
    normalized_response_pairs = [str(item).strip().upper() for item in response_pairs]

    eligible_records = [
        record
        for record in records
        if isinstance(record, dict)
        and str(record.get("date") or "") <= report_date
        and str(record.get("date") or "") >= start_date
    ]
    if not eligible_records:
        return []
    selected_record = max(eligible_records, key=lambda item: str(item.get("date") or ""))
    observed_trade_date = str(selected_record.get("date") or "")
    values = selected_record.get("values")
    if not observed_trade_date or not isinstance(values, list) or len(values) != len(normalized_response_pairs):
        return []

    rates_by_pair: dict[str, Decimal] = {}
    for pair, raw_value in zip(normalized_response_pairs, values, strict=True):
        if raw_value in (None, "", "---"):
            continue
        try:
            rates_by_pair[pair] = Decimal(str(raw_value).replace(",", ""))
        except InvalidOperation:
            continue
    if any(pair not in rates_by_pair for pair in requested_pairs):
        return []

    response_head = payload.get("head")
    stable_provider_metadata = {}
    if isinstance(response_head, dict):
        stable_provider_metadata = {
            key: response_head[key]
            for key in ("provider", "version", "rep_code", "repCode")
            if response_head.get(key) not in (None, "")
        }

    lineage_payload = {
        "requested_report_date": report_date,
        "start_date": start_date,
        "provider": stable_provider_metadata,
        "response_pairs": normalized_response_pairs,
        "selected_record": selected_record,
    }
    digest = hashlib.sha256(
        json.dumps(lineage_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    source_version = f"sv_fx_chinamoney_{digest}"
    vendor_version = f"vv_chinamoney_fx_{observed_trade_date.replace('-', '')}_{digest}"

    normalized_rows: list[tuple[object, ...]] = []
    for candidate, pair in zip(candidates, requested_pairs, strict=True):
        normalized_rows.append(
            _normalize_vendor_row(
                requested_report_date=report_date,
                candidate=candidate,
                observed_trade_date=observed_trade_date,
                raw_mid_rate=rates_by_pair[pair],
                source_name=CHOICE_SOURCE_NAME,
                source_version=source_version,
                vendor_name="chinamoney",
                vendor_version=vendor_version,
                mid_rate_is_normalized=True,
            )
        )
    return normalized_rows


def _materialize_fx_mid_rows(
    *,
    csv_path: str,
    duckdb_path: str,
) -> dict[str, object]:
    logger.info("starting materialize_fx_mid_rows for csv_path=%s", csv_path)
    duckdb_file = Path(duckdb_path)
    writer_lock = resolve_duckdb_writer_lock(duckdb_file)
    with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
        payload = _materialize_fx_mid_rows_under_writer_lock(
            csv_path=csv_path,
            duckdb_path=duckdb_path,
        )
    logger.info("completed materialize_fx_mid_rows")
    return payload


def _materialize_fx_mid_rows_under_writer_lock(
    *,
    csv_path: str,
    duckdb_path: str,
) -> dict[str, object]:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"FX mid CSV not found: {csv_file}")

    source_version = _build_source_version(csv_file)
    vendor_version = f"vv_fx_csv_{source_version.removeprefix('sv_')}"
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_required_headers(reader.fieldnames)
        latest_by_key: dict[tuple[str, str, str], tuple[object, ...]] = {}
        for row in reader:
            trade_date = str(row["trade_date"]).strip()
            base_currency = normalize_currency_code(str(row["base_currency"]))
            quote_currency = normalize_currency_code(str(row["quote_currency"]))
            try:
                mid_rate = Decimal(str(row["mid_rate"]).strip())
            except InvalidOperation as exc:
                raise ValueError(f"Invalid mid_rate value in FX CSV: {row['mid_rate']!r}") from exc
            if not is_valid_fx_mid_rate(mid_rate):
                raise ValueError(
                    f"Invalid mid_rate value in FX CSV: {row['mid_rate']!r}; "
                    "value must be finite and greater than zero."
                )
            source_name = str(row.get("source_name") or csv_file.stem).strip()
            normalized_row = (
                trade_date,
                base_currency,
                quote_currency,
                mid_rate,
                source_name,
                _parse_bool(str(row.get("is_business_day") or "")),
                _parse_bool(str(row.get("is_carry_forward") or "")),
                source_version,
                "csv",
                vendor_version,
                str(row.get("vendor_series_code") or "").strip(),
                str(row.get("observed_trade_date") or trade_date).strip(),
            )
            latest_by_key[(trade_date, base_currency, quote_currency)] = normalized_row
        rows = list(latest_by_key.values())

    _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=rows)

    return {
        "status": "completed",
        "row_count": len(rows),
        "source_version": source_version,
        "vendor_version": vendor_version,
        "csv_path": str(csv_file),
    }


def _build_formal_candidate_payload(candidates: list[FormalFxCandidate]) -> list[dict[str, object]]:
    return [asdict(candidate) for candidate in candidates]


def _fetch_akshare_fx_mid_rows_for_report_date(
    report_date: str,
    *,
    candidates: list[FormalFxCandidate],
) -> list[tuple[object, ...]]:
    adapter = AkShareVendorAdapter()
    snapshot = adapter.fetch_fx_mid_snapshot(
        report_date=report_date,
        candidates=_build_formal_candidate_payload(candidates),
    )
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or not rows:
        return []
    by_base_currency = {
        str(item.get("base_currency") or "").upper(): item
        for item in rows
        if str(item.get("base_currency") or "").strip()
    }
    source_version = str(snapshot.get("source_version") or "")
    if not source_version:
        source_version = _build_akshare_source_version(
            {
                "requested_report_date": report_date,
                "rows": rows,
            }
        )
    vendor_version = str(snapshot.get("vendor_version") or "")
    if not vendor_version:
        vendor_version = f"vv_akshare_fx_{report_date.replace('-', '')}_{hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:10]}"
    normalized_rows: list[tuple[object, ...]] = []
    for candidate in candidates:
        vendor_row = by_base_currency.get(candidate.base_currency.upper())
        if vendor_row is None:
            return []
        normalized_rows.append(
            _normalize_vendor_row(
                requested_report_date=report_date,
                candidate=candidate,
                observed_trade_date=str(vendor_row.get("observed_trade_date") or report_date),
                raw_mid_rate=Decimal(str(vendor_row["mid_rate"])),
                source_name=str(vendor_row.get("source_name") or AKSHARE_SOURCE_NAME),
                source_version=source_version,
                vendor_name="akshare",
                vendor_version=vendor_version,
                mid_rate_is_normalized=True,
            )
        )
    return normalized_rows


def _load_formal_fx_candidates() -> list[FormalFxCandidate]:
    settings = get_settings()
    catalog_path = Path(settings.choice_macro_catalog_file)
    candidates = discover_formal_fx_candidates(catalog_path=catalog_path)
    if not candidates:
        raise ValueError(
            f"No formal FX middle-rate candidates were discovered from Choice catalog: {catalog_path}"
        )
    return candidates


def _materialize_fx_mid_for_report_date(
    *,
    report_date: str,
    duckdb_path: str,
    data_input_root: str,
    official_csv_path: str = "",
    explicit_csv_path: str = "",
    writer_lock_already_held: bool = False,
) -> dict[str, object]:
    logger.info("starting materialize_fx_mid_for_report_date for report_date=%s", report_date)
    duckdb_file = Path(duckdb_path)
    writer_lock = resolve_duckdb_writer_lock(duckdb_file)
    csv_path = resolve_fx_mid_csv_path(
        official_csv_path=official_csv_path,
        explicit_csv_path=explicit_csv_path,
        data_input_root=Path(data_input_root),
    )

    if csv_path is not None:
        if writer_lock_already_held:
            payload = _materialize_fx_mid_rows_under_writer_lock(
                csv_path=str(csv_path),
                duckdb_path=duckdb_path,
            )
        else:
            with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
                payload = _materialize_fx_mid_rows_under_writer_lock(
                    csv_path=str(csv_path),
                    duckdb_path=duckdb_path,
                )
        logger.info("completed materialize_fx_mid_for_report_date")
        return {
            **payload,
            "source_kind": "csv_override",
            "report_date": report_date,
        }

    candidates = _load_formal_fx_candidates()

    choice_error: Exception | None = None
    try:
        choice_rows = _fetch_choice_fx_mid_rows_for_report_date(
            report_date,
            candidates=candidates,
        )
    except Exception as exc:
        logger.warning(
            "Choice FX source unavailable; trying ChinaMoney fallback: %s",
            exc,
        )
        choice_error = exc
        choice_rows = []

    if choice_rows:
        if writer_lock_already_held:
            _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=choice_rows)
        else:
            with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
                _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=choice_rows)
        logger.info("completed materialize_fx_mid_for_report_date")
        return {
            "status": "completed",
            "row_count": len(choice_rows),
            "source_version": str(choice_rows[0][7]),
            "vendor_version": str(choice_rows[0][9]),
            "source_kind": "choice",
            "report_date": report_date,
            "candidate_count": len(candidates),
        }

    chinamoney_error: Exception | None = None
    try:
        chinamoney_rows = _fetch_chinamoney_fx_mid_rows_for_report_date(
            report_date,
            candidates=candidates,
        )
    except Exception as exc:
        logger.warning(
            "ChinaMoney FX source unavailable; trying AkShare fallback: %s",
            exc,
        )
        chinamoney_error = exc
        chinamoney_rows = []

    if chinamoney_rows:
        if writer_lock_already_held:
            _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=chinamoney_rows)
        else:
            with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
                _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=chinamoney_rows)
        logger.info("completed materialize_fx_mid_for_report_date")
        return {
            "status": "completed",
            "row_count": len(chinamoney_rows),
            "source_version": str(chinamoney_rows[0][7]),
            "vendor_version": str(chinamoney_rows[0][9]),
            "source_kind": "chinamoney",
            "report_date": report_date,
            "candidate_count": len(candidates),
            "choice_error": str(choice_error) if choice_error is not None else "",
        }

    akshare_error: Exception | None = None
    try:
        akshare_rows = _fetch_akshare_fx_mid_rows_for_report_date(
            report_date,
            candidates=candidates,
        )
    except Exception as exc:
        logger.warning(
            "AkShare FX source unavailable; no live fallback remains: %s",
            exc,
        )
        akshare_error = exc
        akshare_rows = []

    if akshare_rows:
        if writer_lock_already_held:
            _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=akshare_rows)
        else:
            with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
                _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=akshare_rows)
        logger.info("completed materialize_fx_mid_for_report_date")
        return {
            "status": "completed",
            "row_count": len(akshare_rows),
            "source_version": str(akshare_rows[0][7]),
            "vendor_version": str(akshare_rows[0][9]),
            "source_kind": "akshare",
            "report_date": report_date,
            "candidate_count": len(candidates),
            "choice_error": str(choice_error) if choice_error is not None else "",
            "chinamoney_error": str(chinamoney_error) if chinamoney_error is not None else "",
        }

    error_details = []
    if choice_error is not None:
        error_details.append(f"Choice failed: {choice_error}")
    else:
        error_details.append("Choice returned no complete middle-rate candidate set.")
    if chinamoney_error is not None:
        error_details.append(f"ChinaMoney failed: {chinamoney_error}")
    else:
        error_details.append("ChinaMoney returned no complete middle-rate candidate set.")
    if akshare_error is not None:
        error_details.append(f"AkShare failed: {akshare_error}")
    else:
        error_details.append("AkShare returned no complete middle-rate candidate set.")
    raise ValueError(" ".join(error_details))


materialize_fx_mid_rows = register_actor_once(
    "materialize_fx_mid_rows",
    _materialize_fx_mid_rows,
)

materialize_fx_mid_for_report_date = register_actor_once(
    "materialize_fx_mid_for_report_date",
    _materialize_fx_mid_for_report_date,
)
