from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.config.choice_runtime import _get_em_c
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.choice_stock_adapter import (
    ChoiceStockRequestPlanItem,
    choice_stock_history_start_date,
    load_choice_stock_request_plan,
)
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"

REQUIRED_CHOICE_STOCK_REQUEST_ITEMS: tuple[tuple[str, str], ...] = (
    ("stock_universe", "a_share_universe_sector_001004"),
    ("sector_membership", "sw2021_industry_membership"),
    ("sector_strength", "daily_return_turnover_amplitude"),
    ("stock_ohlcv", "daily_ohlcv_amount"),
    ("stock_status", "daily_trade_status"),
    ("limit_up_quality", "daily_limit_flags"),
    ("limit_up_quality", "point_in_time_limit_streaks"),
)
CHOICE_STOCK_CSD_CODE_CHUNK_SIZE = 300
CHOICE_CSD_PERMISSION_DENIED_ERROR_CODE = 10001012
TUSHARE_FALLBACK_AUDIT_STATUS = "completed_tushare_fallback"


@dataclass(frozen=True)
class ChoiceStockMaterializationCoverage:
    as_of_date: str
    full_coverage: bool
    status: str
    completed_request_items: list[str]
    missing_request_items: list[str]
    message: str


class ChoiceStockRequestError(RuntimeError):
    def __init__(self, error_code: int, error_msg: str) -> None:
        super().__init__(error_msg)
        self.error_code = error_code
        self.error_msg = error_msg


class _DefaultChoiceStockClient:
    def __init__(self, choice_client: ChoiceClient | None = None) -> None:
        self._choice_client = choice_client or ChoiceClient()

    def css(self, *args: object, options: str = "") -> object:
        return self._choice_client.css(*args, options=options)

    def csd(self, *args: object, options: str = "") -> object:
        return self._choice_client.csd(*args, options=options)

    def sector(self, *args: object, options: str = "") -> object:
        self._choice_client.start()
        cmod = _get_em_c()
        if cmod is None:
            raise ImportError("EmQuantAPI.c is unavailable. Configure CHOICE_EMQUANT_PARENT or config/settings.yaml first.")
        merged = _merge_choice_request_options(
            self._choice_client.settings.choice_request_options,
            options,
        )
        return cmod.sector(*args, merged)


class _DefaultTushareStockClient:
    def __init__(self) -> None:
        self._pro: object | None = None

    def trade_cal(self, **kwargs: object) -> object:
        return self._api().trade_cal(**kwargs)

    def daily(self, **kwargs: object) -> object:
        return self._api().daily(**kwargs)

    def daily_basic(self, **kwargs: object) -> object:
        return self._api().daily_basic(**kwargs)

    def stk_limit(self, **kwargs: object) -> object:
        return self._api().stk_limit(**kwargs)

    def _api(self) -> Any:
        if self._pro is None:
            token = resolve_tushare_token_with_settings_fallback(get_settings())
            if not token:
                raise RuntimeError("MOSS_TUSHARE_TOKEN or settings.tushare_token is required for Tushare stock fallback.")
            ts = import_tushare_pro()
            self._pro = ts.pro_api(token)
        return self._pro


def ensure_choice_stock_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "21_choice_stock.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def materialize_choice_stock_inputs(
    *,
    as_of_date: str | date,
    duckdb_path: str | None = None,
    catalog_path: str | None = None,
    client: object | None = None,
    tushare_client: object | None = None,
) -> dict[str, object]:
    settings = get_settings()
    resolved_date = _normalize_date(as_of_date)
    resolved_duckdb_path = str(duckdb_path or settings.duckdb_path)
    resolved_catalog_path = str(catalog_path or settings.choice_stock_catalog_file)
    plan = load_choice_stock_request_plan(resolved_catalog_path, as_of_date=resolved_date)
    if not plan.ready:
        raise ValueError(plan.message)
    missing_request_items = _missing_required_request_items(plan.requests)
    if missing_request_items:
        formatted = ", ".join(missing_request_items)
        raise ValueError(f"Choice stock request plan is missing required Choice stock request items: {formatted}.")

    choice_client = client or _DefaultChoiceStockClient()
    tushare_cache: _TushareStockFallbackCache | None = None
    run_id = f"choice_stock_materialize:{resolved_date}:{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(UTC).isoformat()

    universe_request = _find_request(plan.requests, "stock_universe")
    request_audits: list[dict[str, object]] = []
    stock_codes: list[str] = []
    current_request: ChoiceStockRequestPlanItem | None = None
    universe_rows: list[dict[str, object]] = []
    sector_rows: list[dict[str, object]] = []
    limit_rows: list[dict[str, object]] = []
    daily_by_key: dict[tuple[str, str], dict[str, object]] = {}

    try:
        current_request = universe_request
        universe_result = _call_choice(choice_client, universe_request, stock_codes=[], as_of_date=resolved_date)
        universe_rows = _normalize_sector_universe(universe_result, universe_request)
        stock_codes = sorted({_text(row.get("stock_code")) for row in universe_rows if _text(row.get("stock_code"))})
        if not stock_codes:
            raise RuntimeError("Choice stock universe returned no stock codes.")

        request_audits.append(
            _build_request_audit(
                run_id=run_id,
                as_of_date=resolved_date,
                request=universe_request,
                row_count=len(universe_rows),
                stock_codes=[],
            )
        )

        for request in plan.requests:
            if request.field_key == universe_request.field_key:
                continue
            current_request = request
            audit_status = "completed"
            audit_error_code = 0
            audit_error_msg = ""
            if request.call == "css":
                result = _call_choice(choice_client, request, stock_codes=stock_codes, as_of_date=resolved_date)
                css_rows = _normalize_css_rows(result, request)
                if request.input_family == "sector_membership":
                    sector_rows.extend(_normalize_sector_membership_rows(css_rows, request))
                elif request.input_family == "limit_up_quality":
                    limit_rows.extend(_normalize_limit_quality_rows(css_rows, request, as_of_date=resolved_date))
                row_count = len(css_rows)
            elif request.call == "csd":
                try:
                    csd_rows = []
                    for result in _call_choice_in_stock_code_chunks(
                        choice_client,
                        request,
                        stock_codes=stock_codes,
                        as_of_date=resolved_date,
                    ):
                        csd_rows.extend(_normalize_csd_rows(result, request, default_date=resolved_date))
                except ChoiceStockRequestError as exc:
                    if exc.error_code != CHOICE_CSD_PERMISSION_DENIED_ERROR_CODE:
                        raise
                    start_date, end_date = _request_date_range(request, as_of_date=resolved_date)
                    if (
                        tushare_cache is None
                        or tushare_cache.start_date != start_date
                        or tushare_cache.end_date != end_date
                    ):
                        tushare_cache = _TushareStockFallbackCache(
                            client=tushare_client or _DefaultTushareStockClient(),
                            stock_codes=stock_codes,
                            start_date=start_date,
                            end_date=end_date,
                        )
                    csd_rows = tushare_cache.rows_for_request(request)
                    audit_status = TUSHARE_FALLBACK_AUDIT_STATUS
                    audit_error_code = exc.error_code
                    audit_error_msg = f"Choice csd unavailable; filled from Tushare stock fallback: {exc.error_msg}"
                _merge_daily_rows(daily_by_key, csd_rows, request)
                row_count = len(csd_rows)
            else:
                _call_choice(choice_client, request, stock_codes=stock_codes, as_of_date=resolved_date)
                row_count = 0
            request_audits.append(
                _build_request_audit(
                    run_id=run_id,
                    as_of_date=resolved_date,
                    request=request,
                    row_count=row_count,
                    stock_codes=stock_codes,
                    status=audit_status,
                    error_code=audit_error_code,
                    error_msg=audit_error_msg,
                )
            )
        current_request = None
    except Exception as exc:
        _persist_failed_materialization(
            duckdb_path=resolved_duckdb_path,
            run_id=run_id,
            as_of_date=resolved_date,
            catalog_path=resolved_catalog_path,
            request_audits=request_audits,
            failed_request=current_request,
            stock_codes=stock_codes,
            started_at=started_at,
            error=exc,
        )
        raise

    daily_rows = list(daily_by_key.values())
    source_version = _build_source_version(
        {
            "as_of_date": resolved_date,
            "universe": universe_rows,
            "sector_membership": sector_rows,
            "daily": _daily_rows_for_source_version(daily_rows),
            "limit_quality": limit_rows,
            "request_audits": request_audits,
        }
    )
    vendor_prefix = "vv_choice_tushare_stock" if _used_tushare_fallback(request_audits) else "vv_choice_stock"
    vendor_version = f"{vendor_prefix}_{resolved_date.replace('-', '')}_{source_version.removeprefix('sv_choice_stock_')}"
    completed_at = datetime.now(UTC).isoformat()
    row_count = len(universe_rows) + len(sector_rows) + len(daily_rows) + len(limit_rows)

    duckdb_file = Path(resolved_duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        ensure_choice_stock_schema(conn)
        conn.execute("begin transaction")
        _delete_as_of_rows(
            conn,
            resolved_date,
            history_start_date=choice_stock_history_start_date(resolved_date),
        )
        _insert_run(
            conn,
            run_id=run_id,
            as_of_date=resolved_date,
            status="completed",
            catalog_path=resolved_catalog_path,
            source_version=source_version,
            vendor_version=vendor_version,
            request_count=len(request_audits),
            row_count=row_count,
            started_at=started_at,
            completed_at=completed_at,
            error_message="",
        )
        _insert_request_audits(
            conn,
            request_audits=request_audits,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        _insert_universe(conn, rows=universe_rows, run_id=run_id, source_version=source_version, vendor_version=vendor_version)
        _insert_sector_membership(
            conn,
            rows=sector_rows,
            run_id=run_id,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        _insert_daily_observations(
            conn,
            rows=daily_rows,
            run_id=run_id,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        _insert_limit_quality(
            conn,
            rows=limit_rows,
            run_id=run_id,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()

    return {
        "status": "completed",
        "run_id": run_id,
        "as_of_date": resolved_date,
        "stock_code_count": len(stock_codes),
        "request_count": len(request_audits),
        "row_count": row_count,
        "source_version": source_version,
        "vendor_version": vendor_version,
    }


def load_choice_stock_materialization_coverage(
    *,
    duckdb_path: str,
    as_of_date: str | date,
    required_items: tuple[tuple[str, str], ...] = REQUIRED_CHOICE_STOCK_REQUEST_ITEMS,
) -> ChoiceStockMaterializationCoverage:
    resolved_date = _normalize_date(as_of_date)
    path = Path(duckdb_path)
    if not path.exists():
        return _coverage(
            as_of_date=resolved_date,
            status="not_materialized",
            completed=[],
            missing=_format_required_items(required_items),
        )

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _coverage(
            as_of_date=resolved_date,
            status="not_materialized",
            completed=[],
            missing=_format_required_items(required_items),
        )
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_request_audit",
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
            "choice_stock_limit_quality",
        }
        if not required_tables.issubset(tables):
            return _coverage(
                as_of_date=resolved_date,
                status="not_materialized",
                completed=[],
                missing=_format_required_items(required_items),
            )
        audited = _completed_request_items(conn, resolved_date)
        landed = _landed_request_items(conn, resolved_date, required_items=required_items)
    except duckdb.Error:
        return _coverage(
            as_of_date=resolved_date,
            status="not_materialized",
            completed=[],
            missing=_format_required_items(required_items),
        )
    finally:
        conn.close()

    completed = audited & landed
    missing = [item for item in _format_required_items(required_items) if item not in completed]
    if missing:
        return _coverage(
            as_of_date=resolved_date,
            status="partial",
            completed=sorted(completed),
            missing=missing,
        )
    return ChoiceStockMaterializationCoverage(
        as_of_date=resolved_date,
        full_coverage=True,
        status="ready",
        completed_request_items=sorted(completed),
        missing_request_items=[],
        message=f"Choice stock inputs are materialized for {resolved_date}.",
    )


def _find_request(
    requests: list[ChoiceStockRequestPlanItem],
    input_family: str,
) -> ChoiceStockRequestPlanItem:
    for request in requests:
        if request.input_family == input_family:
            return request
    raise ValueError(f"Choice stock request plan is missing {input_family}.")


def _missing_required_request_items(
    requests: list[ChoiceStockRequestPlanItem],
    required_items: tuple[tuple[str, str], ...] = REQUIRED_CHOICE_STOCK_REQUEST_ITEMS,
) -> list[str]:
    present = {f"{request.input_family}:{request.field_key}" for request in requests}
    return [item for item in _format_required_items(required_items) if item not in present]


def _call_choice(
    client: object,
    request: ChoiceStockRequestPlanItem,
    *,
    stock_codes: list[str],
    as_of_date: str,
) -> object:
    args = [
        ",".join(stock_codes) if value == "__STOCK_CODES__" else as_of_date if value == "__START_DATE__" else value
        for value in request.request_arguments
    ]
    method = getattr(client, request.call)
    result = method(*args, options=request.request_options_text)
    error_code = int(getattr(result, "ErrorCode", 0))
    if error_code != 0:
        error_msg = getattr(result, "ErrorMsg", f"Choice {request.call} failed: {error_code}")
        raise ChoiceStockRequestError(error_code, str(error_msg))
    return result


def _call_choice_in_stock_code_chunks(
    client: object,
    request: ChoiceStockRequestPlanItem,
    *,
    stock_codes: list[str],
    as_of_date: str,
) -> list[object]:
    if request.call != "csd":
        return [_call_choice(client, request, stock_codes=stock_codes, as_of_date=as_of_date)]
    return [
        _call_choice(client, request, stock_codes=chunk, as_of_date=as_of_date)
        for chunk in _stock_code_chunks(stock_codes, CHOICE_STOCK_CSD_CODE_CHUNK_SIZE)
    ]


def _stock_code_chunks(stock_codes: list[str], chunk_size: int) -> list[list[str]]:
    normalized_chunk_size = max(1, chunk_size)
    return [
        stock_codes[index : index + normalized_chunk_size]
        for index in range(0, len(stock_codes), normalized_chunk_size)
    ]


class _TushareStockFallbackCache:
    def __init__(
        self,
        *,
        client: object,
        stock_codes: list[str],
        start_date: str,
        end_date: str,
    ) -> None:
        self.client = client
        self.stock_codes = set(stock_codes)
        self.start_date = start_date
        self.end_date = end_date
        self._trade_dates: list[str] | None = None
        self._daily_rows: dict[tuple[str, str], dict[str, object]] | None = None
        self._daily_basic_rows: dict[tuple[str, str], dict[str, object]] | None = None
        self._limit_rows: dict[tuple[str, str], dict[str, object]] | None = None

    def rows_for_request(self, request: ChoiceStockRequestPlanItem) -> list[dict[str, object]]:
        if request.field_key == "daily_return_turnover_amplitude":
            return self._sector_strength_rows()
        if request.field_key == "daily_ohlcv_amount":
            return self._ohlcv_rows()
        if request.field_key == "daily_trade_status":
            return self._trade_status_rows()
        if request.field_key == "daily_limit_flags":
            return self._limit_rows_for_as_of_date()
        raise RuntimeError(f"No Tushare stock fallback mapping is defined for {request.field_key}.")

    def _sector_strength_rows(self) -> list[dict[str, object]]:
        daily_rows = self._daily_by_key()
        daily_basic_rows = self._daily_basic_by_key()
        rows: list[dict[str, object]] = []
        for (trade_date, stock_code), daily_row in daily_rows.items():
            daily_basic_row = daily_basic_rows.get((trade_date, stock_code), {})
            high_value = _record_float(daily_row, "high")
            low_value = _record_float(daily_row, "low")
            pre_close = _record_float(daily_row, "pre_close")
            amplitude = None
            if high_value is not None and low_value is not None and pre_close is not None and pre_close > 0:
                amplitude = ((high_value - low_value) / pre_close) * 100
            rows.append(
                {
                    "trade_date": trade_date,
                    "stock_code": stock_code,
                    "PCTCHANGE": _record_float(daily_row, "pct_chg"),
                    "TURN": _record_float(daily_basic_row, "turnover_rate_f")
                    or _record_float(daily_basic_row, "turnover_rate"),
                    "AMPLITUDE": amplitude,
                }
            )
        return rows

    def _ohlcv_rows(self) -> list[dict[str, object]]:
        return [
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                "OPEN": _record_float(row, "open"),
                "HIGH": _record_float(row, "high"),
                "LOW": _record_float(row, "low"),
                "CLOSE": _record_float(row, "close"),
                "VOLUME": _record_float(row, "vol"),
                "AMOUNT": _record_float(row, "amount"),
            }
            for (trade_date, stock_code), row in self._daily_by_key().items()
        ]

    def _trade_status_rows(self) -> list[dict[str, object]]:
        return [
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                "TRADESTATUS": "Trading",
            }
            for trade_date, stock_code in self._daily_by_key()
        ]

    def _limit_rows_for_as_of_date(self) -> list[dict[str, object]]:
        return [
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                "HIGHLIMIT": _record_float(row, "up_limit"),
                "LOWLIMIT": _record_float(row, "down_limit"),
            }
            for (trade_date, stock_code), row in self._limit_by_key().items()
        ]

    def _trade_date_values(self) -> list[str]:
        if self._trade_dates is None:
            frame = cast(Any, self.client).trade_cal(
                exchange="SSE",
                is_open="1",
                start_date=_compact_date(self.start_date),
                end_date=_compact_date(self.end_date),
                fields="cal_date,is_open",
            )
            dates = {
                _compact_date(record.get("cal_date"))
                for record in _records_from_tabular_payload(frame)
                if _text(record.get("cal_date"))
            }
            self._trade_dates = sorted(dates)
        return self._trade_dates

    def _daily_by_key(self) -> dict[tuple[str, str], dict[str, object]]:
        if self._daily_rows is None:
            rows: dict[tuple[str, str], dict[str, object]] = {}
            for trade_date in self._trade_date_values():
                frame = cast(Any, self.client).daily(
                    trade_date=trade_date,
                    fields="ts_code,trade_date,open,high,low,close,pre_close,vol,amount,pct_chg",
                )
                for record in _records_from_tabular_payload(frame):
                    stock_code = _record_text(record, "ts_code")
                    if stock_code not in self.stock_codes:
                        continue
                    key = (_normalize_date(_record_text(record, "trade_date")), stock_code)
                    rows[key] = record
            self._daily_rows = dict(sorted(rows.items()))
        return self._daily_rows

    def _daily_basic_by_key(self) -> dict[tuple[str, str], dict[str, object]]:
        if self._daily_basic_rows is None:
            rows: dict[tuple[str, str], dict[str, object]] = {}
            for trade_date in self._trade_date_values():
                frame = cast(Any, self.client).daily_basic(
                    trade_date=trade_date,
                    fields="ts_code,trade_date,turnover_rate,turnover_rate_f",
                )
                for record in _records_from_tabular_payload(frame):
                    stock_code = _record_text(record, "ts_code")
                    if stock_code not in self.stock_codes:
                        continue
                    key = (_normalize_date(_record_text(record, "trade_date")), stock_code)
                    rows[key] = record
            self._daily_basic_rows = rows
        return self._daily_basic_rows

    def _limit_by_key(self) -> dict[tuple[str, str], dict[str, object]]:
        if self._limit_rows is None:
            rows: dict[tuple[str, str], dict[str, object]] = {}
            frame = cast(Any, self.client).stk_limit(
                trade_date=_compact_date(self.end_date),
                fields="ts_code,trade_date,up_limit,down_limit",
            )
            for record in _records_from_tabular_payload(frame):
                stock_code = _record_text(record, "ts_code")
                if stock_code not in self.stock_codes:
                    continue
                key = (_normalize_date(_record_text(record, "trade_date")), stock_code)
                rows[key] = record
            self._limit_rows = rows
        return self._limit_rows


def _records_from_tabular_payload(payload: object) -> list[dict[str, object]]:
    if payload is None:
        return []
    try:
        records = cast(Any, payload).to_dict(orient="records")
    except (AttributeError, TypeError, ValueError):
        return []
    return [
        {str(key).lower(): value for key, value in record.items()}
        for record in records
        if isinstance(record, dict)
    ]


def _record_text(record: dict[str, object], key: str) -> str:
    return _text(record.get(key.lower()) or record.get(key.upper()) or record.get(key))


def _record_float(record: dict[str, object], key: str) -> float | None:
    return _float_or_none_safe(record.get(key.lower()) or record.get(key.upper()) or record.get(key))


def _float_or_none_safe(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _request_date_range(request: ChoiceStockRequestPlanItem, *, as_of_date: str) -> tuple[str, str]:
    if len(request.request_arguments) >= 4:
        return _normalize_date(request.request_arguments[2]), _normalize_date(request.request_arguments[3])
    return choice_stock_history_start_date(as_of_date), as_of_date


def _compact_date(value: object) -> str:
    return _normalize_date(value).replace("-", "")


def _used_tushare_fallback(request_audits: list[dict[str, object]]) -> bool:
    return any(audit.get("status") == TUSHARE_FALLBACK_AUDIT_STATUS for audit in request_audits)


def _build_request_audit(
    *,
    run_id: str,
    as_of_date: str,
    request: ChoiceStockRequestPlanItem,
    row_count: int,
    stock_codes: list[str],
    status: str = "completed",
    error_code: int = 0,
    error_msg: str = "",
) -> dict[str, object]:
    request_arguments = [
        ",".join(stock_codes) if value == "__STOCK_CODES__" else as_of_date if value == "__START_DATE__" else value
        for value in request.request_arguments
    ]
    return {
        "run_id": run_id,
        "as_of_date": as_of_date,
        "input_family": request.input_family,
        "field_key": request.field_key,
        "call": request.call,
        "vendor_indicator": request.vendor_indicator,
        "request_arguments_json": json.dumps(request_arguments, ensure_ascii=False, separators=(",", ":")),
        "request_options_json": json.dumps(request.request_options, ensure_ascii=False, separators=(",", ":")),
        "status": status,
        "row_count": row_count,
        "error_code": error_code,
        "error_msg": error_msg,
    }


def _persist_failed_materialization(
    *,
    duckdb_path: str,
    run_id: str,
    as_of_date: str,
    catalog_path: str,
    request_audits: list[dict[str, object]],
    failed_request: ChoiceStockRequestPlanItem | None,
    stock_codes: list[str],
    started_at: str,
    error: Exception,
) -> None:
    error_code, error_msg = _choice_error_details(error)
    audits = list(request_audits)
    if failed_request is not None:
        audits.append(
            _build_request_audit(
                run_id=run_id,
                as_of_date=as_of_date,
                request=failed_request,
                row_count=0,
                stock_codes=stock_codes,
                status="failed",
                error_code=error_code,
                error_msg=error_msg,
            )
        )
    source_version = _build_source_version(
        {
            "as_of_date": as_of_date,
            "status": "failed",
            "request_audits": audits,
            "error": error_msg,
        }
    )
    vendor_version = f"vv_choice_stock_failed_{as_of_date.replace('-', '')}"
    completed_at = datetime.now(UTC).isoformat()
    duckdb_file = Path(duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    conn: duckdb.DuckDBPyConnection | None = None
    try:
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        ensure_choice_stock_schema(conn)
        conn.execute("begin transaction")
        _insert_run(
            conn,
            run_id=run_id,
            as_of_date=as_of_date,
            status="failed",
            catalog_path=catalog_path,
            source_version=source_version,
            vendor_version=vendor_version,
            request_count=len(audits),
            row_count=0,
            started_at=started_at,
            completed_at=completed_at,
            error_message=error_msg,
        )
        _insert_request_audits(
            conn,
            request_audits=audits,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        conn.execute("commit")
    except Exception:
        if conn is not None:
            _rollback_quietly(conn)
    finally:
        if conn is not None:
            conn.close()


def _choice_error_details(error: Exception) -> tuple[int, str]:
    if isinstance(error, ChoiceStockRequestError):
        return error.error_code, _truncate_error_message(error.error_msg)
    return 0, _truncate_error_message(str(error) or error.__class__.__name__)


def _truncate_error_message(message: str, limit: int = 1000) -> str:
    return message[:limit]


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        return


def _normalize_sector_universe(
    result: object,
    request: ChoiceStockRequestPlanItem,
) -> list[dict[str, object]]:
    rows = _extract_result_rows(result, default_code=request.vendor_indicator)
    normalized: dict[str, dict[str, object]] = {}
    for row in rows:
        stock_code = _text(row.get("SECUCODE") or row.get("SECURITYCODE") or row.get("CODE") or row.get("code"))
        if not stock_code:
            continue
        normalized[stock_code] = {
            "as_of_date": request.request_arguments[-1],
            "stock_code": stock_code,
            "stock_name": _text(row.get("SECURITYSHORTNAME") or row.get("SECURITYNAME") or row.get("NAME")),
            "field_key": request.field_key,
        }
    return [normalized[key] for key in sorted(normalized)]


def _normalize_css_rows(
    result: object,
    request: ChoiceStockRequestPlanItem,
) -> list[dict[str, object]]:
    del request
    return _extract_result_rows(result)


def _normalize_sector_membership_rows(
    rows: list[dict[str, object]],
    request: ChoiceStockRequestPlanItem,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    as_of_date = _normalize_option_date(request.request_options.get("EndDate"))
    for row in rows:
        stock_code = _text(row.get("stock_code") or row.get("CODE"))
        if not stock_code:
            continue
        normalized.append(
            {
                "as_of_date": as_of_date,
                "stock_code": stock_code,
                "sw2021": _text(row.get("SW2021")),
                "sw2021code": _text(row.get("SW2021CODE")),
                "field_key": request.field_key,
            }
        )
    return normalized


def _normalize_limit_quality_rows(
    rows: list[dict[str, object]],
    request: ChoiceStockRequestPlanItem,
    *,
    as_of_date: str,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        stock_code = _text(row.get("stock_code") or row.get("CODE"))
        if not stock_code:
            continue
        normalized.append(
            {
                "as_of_date": as_of_date,
                "stock_code": stock_code,
                "issurgedlimit": _text(row.get("ISSURGEDLIMIT")),
                "isdeclinelimit": _text(row.get("ISDECLINELIMIT")),
                "hlimitedays": _int_or_none(row.get("HLIMITEDAYS")),
                "llimiteddays": _int_or_none(row.get("LLIMITEDDAYS")),
                "field_key": request.field_key,
            }
        )
    return normalized


def _normalize_csd_rows(
    result: object,
    request: ChoiceStockRequestPlanItem,
    *,
    default_date: str,
) -> list[dict[str, object]]:
    del request
    rows = _extract_result_rows(result, default_date=default_date)
    for row in rows:
        if not row.get("trade_date"):
            row["trade_date"] = default_date
    return rows


def _merge_daily_rows(
    daily_by_key: dict[tuple[str, str], dict[str, object]],
    rows: list[dict[str, object]],
    request: ChoiceStockRequestPlanItem,
) -> None:
    for row in rows:
        trade_date = _normalize_date(row.get("trade_date") or row.get("DATES") or row.get("DATE"))
        stock_code = _text(row.get("stock_code") or row.get("CODE"))
        if not stock_code:
            continue
        key = (trade_date, stock_code)
        target = daily_by_key.setdefault(
            key,
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                "field_keys": set(),
            },
        )
        field_keys = cast(set[str], target["field_keys"])
        field_keys.add(request.field_key)
        for source, target_key in (
            ("OPEN", "open_value"),
            ("HIGH", "high_value"),
            ("LOW", "low_value"),
            ("CLOSE", "close_value"),
            ("VOLUME", "volume"),
            ("AMOUNT", "amount"),
            ("PCTCHANGE", "pctchange"),
            ("TURN", "turn"),
            ("AMPLITUDE", "amplitude"),
        ):
            if source in row:
                target[target_key] = _float_or_none(row.get(source))
        for source, target_key in (
            ("TRADESTATUS", "tradestatus"),
            ("HIGHLIMIT", "highlimit"),
            ("LOWLIMIT", "lowlimit"),
        ):
            if source in row:
                target[target_key] = _text(row.get(source))


def _extract_result_rows(
    result: object,
    *,
    default_code: str | None = None,
    default_date: str | None = None,
) -> list[dict[str, object]]:
    if _is_pandas_dataframe(result):
        return _rows_from_dataframe_payload(result, default_date=default_date)

    indicators = [str(item).upper() for item in (getattr(result, "Indicators", None) or [])]
    data = getattr(result, "Data", {}) or {}
    dates = [_normalize_date(item) for item in (getattr(result, "Dates", None) or [])]
    if not dates and default_date is not None:
        dates = [default_date]
    if _is_pandas_dataframe(data):
        return _rows_from_dataframe_payload(data, default_date=default_date)
    if isinstance(data, list):
        codes = [str(item) for item in (getattr(result, "Codes", None) or [])]
        if codes and indicators and len(data) == len(codes) * len(indicators):
            return _rows_from_flat_code_payload(
                data,
                codes=codes,
                indicators=indicators,
                default_date=default_date,
            )
        return [_coerce_row(indicators, item, default_code=default_code, default_date=default_date) for item in data]
    if not isinstance(data, dict):
        return []

    if _looks_like_columnar_payload(data):
        return _rows_from_columnar_payload(data, default_date=default_date)

    rows: list[dict[str, object]] = []
    for code, payload in data.items():
        rows.extend(_rows_from_code_payload(str(code), payload, indicators=indicators, dates=dates))
    return rows


def _is_pandas_dataframe(value: object) -> bool:
    return value.__class__.__name__ == "DataFrame"


def _rows_from_dataframe_payload(
    frame: object,
    *,
    default_date: str | None,
) -> list[dict[str, object]]:
    frame_any = cast(Any, frame)
    try:
        source = frame_any.reset_index() if hasattr(frame_any, "reset_index") else frame_any
        records = source.to_dict(orient="records")
    except (AttributeError, TypeError, ValueError):
        return []

    rows: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        row = {str(key).upper(): value for key, value in record.items()}
        stock_code = row.get("CODES") or row.get("CODE") or row.get("SECUCODE") or row.get("SECURITYCODE")
        if stock_code not in (None, ""):
            row.setdefault("stock_code", stock_code)
        if default_date is not None:
            row.setdefault("trade_date", default_date)
        rows.append(row)
    return rows


def _rows_from_flat_code_payload(
    data: list[object],
    *,
    codes: list[str],
    indicators: list[str],
    default_date: str | None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    width = len(indicators)
    for index, code in enumerate(codes):
        offset = index * width
        values = data[offset : offset + width]
        row: dict[str, object] = {"stock_code": code}
        if default_date is not None:
            row["trade_date"] = default_date
        for indicator, value in zip(indicators, values, strict=True):
            row[indicator] = value
        rows.append(row)
    return rows


def _looks_like_columnar_payload(data: dict[object, object]) -> bool:
    keys = {str(key).upper() for key in data}
    return bool(keys & {"SECUCODE", "SECURITYSHORTNAME", "CODE"})


def _rows_from_columnar_payload(
    data: dict[object, object],
    *,
    default_date: str | None,
) -> list[dict[str, object]]:
    normalized = {str(key).upper(): value for key, value in data.items()}
    lengths = [len(value) for value in normalized.values() if isinstance(value, list)]
    row_count = max(lengths or [0])
    rows = []
    for index in range(row_count):
        row = {}
        for key, values in normalized.items():
            row[key] = values[index] if isinstance(values, list) and index < len(values) else values
        if default_date is not None:
            row["trade_date"] = default_date
        rows.append(row)
    return rows


def _rows_from_code_payload(
    code: str,
    payload: object,
    *,
    indicators: list[str],
    dates: list[str],
) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        row = {str(key).upper(): value for key, value in payload.items()}
        row.setdefault("stock_code", code)
        return [row]
    if not isinstance(payload, list):
        return [{"stock_code": code, "VALUE": payload}]
    if payload and all(isinstance(item, dict) for item in payload):
        rows = []
        for item in payload:
            row = {str(key).upper(): value for key, value in item.items()}
            row.setdefault("stock_code", code)
            rows.append(row)
        return rows
    if indicators and len(payload) == len(indicators) and all(isinstance(item, list) for item in payload):
        row_count = max([len(item) for item in payload] or [0])
        rows = []
        for index in range(row_count):
            row = {"stock_code": code}
            if dates and index < len(dates):
                row["trade_date"] = dates[index]
            for indicator, values in zip(indicators, payload, strict=True):
                row[indicator] = values[index] if index < len(values) else None
            rows.append(row)
        return rows
    if indicators and len(payload) == len(indicators):
        row = {"stock_code": code}
        for indicator, value in zip(indicators, payload, strict=True):
            row[indicator] = value
        return [row]
    if payload and all(isinstance(item, (list, tuple)) for item in payload):
        return [_coerce_row(indicators, item, default_code=code, default_date=dates[0] if dates else None) for item in payload]
    return [{"stock_code": code, "VALUE": payload}]


def _coerce_row(
    indicators: list[str],
    item: object,
    *,
    default_code: str | None,
    default_date: str | None,
) -> dict[str, object]:
    if isinstance(item, dict):
        row = {str(key).upper(): value for key, value in item.items()}
    elif isinstance(item, (list, tuple)):
        row = {
            indicators[index] if index < len(indicators) else f"FIELD_{index}": value
            for index, value in enumerate(item)
        }
    else:
        row = {"VALUE": item}
    if default_code is not None:
        row.setdefault("stock_code", default_code)
    if default_date is not None:
        row.setdefault("trade_date", default_date)
    return row


def _delete_as_of_rows(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    *,
    history_start_date: str,
) -> None:
    for table, column in (
        ("choice_stock_universe", "as_of_date"),
        ("choice_stock_sector_membership", "as_of_date"),
        ("choice_stock_limit_quality", "as_of_date"),
    ):
        conn.execute(f"delete from {table} where {column} = ?", [as_of_date])
    conn.execute(
        """
        delete from choice_stock_daily_observation
        where cast(trade_date as date) between cast(? as date) and cast(? as date)
        """,
        [history_start_date, as_of_date],
    )


def _insert_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    as_of_date: str,
    status: str,
    catalog_path: str,
    source_version: str,
    vendor_version: str,
    request_count: int,
    row_count: int,
    started_at: str,
    completed_at: str,
    error_message: str,
) -> None:
    conn.execute(
        "insert into choice_stock_materialize_run values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            run_id,
            as_of_date,
            status,
            catalog_path,
            source_version,
            vendor_version,
            RULE_VERSION,
            request_count,
            row_count,
            started_at,
            completed_at,
            error_message,
        ],
    )


def _insert_request_audits(
    conn: duckdb.DuckDBPyConnection,
    *,
    request_audits: list[dict[str, object]],
    source_version: str,
    vendor_version: str,
) -> None:
    rows = [
        (
            audit["run_id"],
            audit["as_of_date"],
            audit["input_family"],
            audit["field_key"],
            audit["call"],
            audit["vendor_indicator"],
            audit["request_arguments_json"],
            audit["request_options_json"],
            audit["status"],
            audit["row_count"],
            audit["error_code"],
            audit["error_msg"],
            source_version,
            vendor_version,
            RULE_VERSION,
        )
        for audit in request_audits
    ]
    if not rows:
        return
    conn.executemany("insert into choice_stock_request_audit values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def _insert_universe(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
    run_id: str,
    source_version: str,
    vendor_version: str,
) -> None:
    conn.executemany(
        "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["as_of_date"],
                row["stock_code"],
                row["stock_name"],
                row["field_key"],
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for row in rows
        ],
    )


def _insert_sector_membership(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
    run_id: str,
    source_version: str,
    vendor_version: str,
) -> None:
    if not rows:
        return
    conn.executemany(
        "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["as_of_date"],
                row["stock_code"],
                row["sw2021"],
                row["sw2021code"],
                row["field_key"],
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for row in rows
        ],
    )


def _insert_daily_observations(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
    run_id: str,
    source_version: str,
    vendor_version: str,
) -> None:
    if not rows:
        return
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["trade_date"],
                row["stock_code"],
                row.get("open_value"),
                row.get("high_value"),
                row.get("low_value"),
                row.get("close_value"),
                row.get("volume"),
                row.get("amount"),
                row.get("pctchange"),
                row.get("turn"),
                row.get("amplitude"),
                row.get("tradestatus"),
                row.get("highlimit"),
                row.get("lowlimit"),
                json.dumps(_daily_field_keys(row), ensure_ascii=False, separators=(",", ":")),
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for row in rows
        ],
    )


def _insert_limit_quality(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
    run_id: str,
    source_version: str,
    vendor_version: str,
) -> None:
    if not rows:
        return
    conn.executemany(
        "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["as_of_date"],
                row["stock_code"],
                row["issurgedlimit"],
                row["isdeclinelimit"],
                row["hlimitedays"],
                row["llimiteddays"],
                row["field_key"],
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for row in rows
        ],
    )


def _count_rows(conn: duckdb.DuckDBPyConnection, table: str, column: str, value: str) -> int:
    row = conn.execute(f"select count(*) from {table} where {column} = ?", [value]).fetchone()
    return int(row[0]) if row is not None else 0


def _completed_request_items(conn: duckdb.DuckDBPyConnection, as_of_date: str) -> set[str]:
    rows = conn.execute(
        """
        select distinct input_family, field_key
        from choice_stock_request_audit
        where as_of_date = ?
          and status in ('completed', 'completed_tushare_fallback')
          and coalesce(row_count, 0) > 0
        """,
        [as_of_date],
    ).fetchall()
    return {f"{row[0]}:{row[1]}" for row in rows}


def _landed_request_items(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    *,
    required_items: tuple[tuple[str, str], ...],
) -> set[str]:
    required = set(_format_required_items(required_items))
    landed: set[str] = set()
    if (
        "stock_universe:a_share_universe_sector_001004" in required
        and _count_rows_by_field(
            conn,
            table="choice_stock_universe",
            date_column="as_of_date",
            date_value=as_of_date,
            field_key="a_share_universe_sector_001004",
        )
        > 0
    ):
        landed.add("stock_universe:a_share_universe_sector_001004")
    if (
        "sector_membership:sw2021_industry_membership" in required
        and _count_rows_by_field(
            conn,
            table="choice_stock_sector_membership",
            date_column="as_of_date",
            date_value=as_of_date,
            field_key="sw2021_industry_membership",
        )
        > 0
    ):
        landed.add("sector_membership:sw2021_industry_membership")
    if (
        "limit_up_quality:point_in_time_limit_streaks" in required
        and _count_rows_by_field(
            conn,
            table="choice_stock_limit_quality",
            date_column="as_of_date",
            date_value=as_of_date,
            field_key="point_in_time_limit_streaks",
        )
        > 0
    ):
        landed.add("limit_up_quality:point_in_time_limit_streaks")
    landed.update(_landed_daily_request_items(conn, as_of_date) & required)
    return landed


def _count_rows_by_field(
    conn: duckdb.DuckDBPyConnection,
    *,
    table: str,
    date_column: str,
    date_value: str,
    field_key: str,
) -> int:
    row = conn.execute(
        f"select count(*) from {table} where {date_column} = ? and field_key = ?",
        [date_value, field_key],
    ).fetchone()
    return int(row[0]) if row is not None else 0


def _landed_daily_request_items(conn: duckdb.DuckDBPyConnection, as_of_date: str) -> set[str]:
    rows = conn.execute(
        """
        select
          field_keys_json,
          pctchange,
          turn,
          amplitude,
          open_value,
          high_value,
          low_value,
          close_value,
          volume,
          amount,
          tradestatus,
          highlimit,
          lowlimit
        from choice_stock_daily_observation
        where trade_date = ?
        """,
        [as_of_date],
    ).fetchall()
    landed: set[str] = set()
    for row in rows:
        field_keys = set(_parse_field_keys_json(row[0]))
        if "daily_return_turnover_amplitude" in field_keys and _has_any_value(row[1:4]):
            landed.add("sector_strength:daily_return_turnover_amplitude")
        if "daily_ohlcv_amount" in field_keys and _has_any_value(row[4:10]):
            landed.add("stock_ohlcv:daily_ohlcv_amount")
        if "daily_trade_status" in field_keys and _has_any_value(row[10:11]):
            landed.add("stock_status:daily_trade_status")
        if "daily_limit_flags" in field_keys and _has_any_value(row[11:13]):
            landed.add("limit_up_quality:daily_limit_flags")
    return landed


def _parse_field_keys_json(value: object) -> list[str]:
    try:
        parsed = json.loads(_text(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _has_any_value(values: tuple[object, ...]) -> bool:
    return any(value is not None and _text(value) != "" for value in values)


def _merge_choice_request_options(base_options: str, options: str) -> str:
    return ",".join(
        item.strip()
        for item in [base_options, options]
        if item and item.strip()
    )


def _daily_field_keys(row: dict[str, object]) -> list[str]:
    field_keys = row.get("field_keys", [])
    if isinstance(field_keys, (list, tuple, set)):
        return sorted(str(item) for item in field_keys)
    return []


def _daily_rows_for_source_version(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{**row, "field_keys": _daily_field_keys(row)} for row in rows]


def _coverage(
    *,
    as_of_date: str,
    status: str,
    completed: list[str],
    missing: list[str],
) -> ChoiceStockMaterializationCoverage:
    if status == "not_materialized":
        message = f"Choice stock catalog is confirmed, but DuckDB materialization is not landed for {as_of_date}."
    else:
        message = (
            f"Choice stock materialized input coverage is incomplete for {as_of_date}; "
            f"missing request items: {', '.join(missing)}."
        )
    return ChoiceStockMaterializationCoverage(
        as_of_date=as_of_date,
        full_coverage=False,
        status=status,
        completed_request_items=completed,
        missing_request_items=missing,
        message=message,
    )


def _format_required_items(required_items: tuple[tuple[str, str], ...]) -> list[str]:
    return [f"{family}:{field_key}" for family, field_key in required_items]


def _normalize_date(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    date_text = text.split()[0]
    parts = date_text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat()
    return date.fromisoformat(text[:10]).isoformat()


def _normalize_option_date(value: object) -> str:
    return _normalize_date(value)


def _text(value: object) -> str:
    return str(value or "").strip()


def _float_or_none(value: object) -> float | None:
    text = _text(value)
    return None if not text else float(text)


def _int_or_none(value: object) -> int | None:
    text = _text(value)
    return None if not text else int(float(text))


def _build_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_choice_stock_{digest}"
