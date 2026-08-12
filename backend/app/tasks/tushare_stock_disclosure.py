from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.stock_official_disclosure_repo import (
    EVIDENCE_COVERAGE_LOOKBACK_DAYS,
    get_stock_official_disclosure_sync_status,
    upsert_stock_official_disclosure_sync_status,
    upsert_stock_official_disclosures,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.tushare_adapter import (
    TUSHARE_TOKEN_ENV,
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.tasks.broker import register_actor_once

SOURCE_LABEL = "\u4e0a\u5e02\u516c\u53f8\u516c\u544a\u539f\u6587\uff08Tushare\uff09"
ANNOUNCEMENT_TYPE = "official_announcement"
FINANCIAL_REPORT_TYPE = "financial_report"
DEFAULT_LOOKBACK_DAYS = EVIDENCE_COVERAGE_LOOKBACK_DAYS
# Tushare's anns_d endpoint truncates a response at 2,000 rows. Keep this
# mutable for deterministic low-limit pagination tests without live calls.
ANNS_D_PAGE_LIMIT = 2000

_REPORT_SUFFIX = r"(?:\u6458\u8981)?(?:[\uff08(](?:\u4fee\u8ba2\u7248|\u4fee\u8ba2\u7a3f|\u4fee\u8ba2\u540e|\u66f4\u6b63\u540e|\u66f4\u65b0\u540e)[)\uff09])?"
_ANNUAL_RE = re.compile(rf"^(?P<year>\d{{4}})\u5e74\u5e74\u5ea6\u62a5\u544a{_REPORT_SUFFIX}$")
_HALF_RE = re.compile(rf"^(?P<year>\d{{4}})\u5e74\u534a\u5e74\u5ea6\u62a5\u544a{_REPORT_SUFFIX}$")
_Q1_RE = re.compile(rf"^(?P<year>\d{{4}})\u5e74(?:\u4e00\u5b63\u5ea6|\u7b2c\u4e00\u5b63\u5ea6)\u62a5\u544a{_REPORT_SUFFIX}$")
_Q3_RE = re.compile(rf"^(?P<year>\d{{4}})\u5e74(?:\u4e09\u5b63\u5ea6|\u7b2c\u4e09\u5b63\u5ea6)\u62a5\u544a{_REPORT_SUFFIX}$")
_DOCUMENT_URL_KEYS = (
    "url",
    "ann_url",
    "ann_pdf_url",
    "pdf_url",
    "report_url",
    "doc_url",
    "document_url",
    "source_url",
)
_SOURCE_ID_KEYS = ("source_id", "ann_id", "announcement_id", "id", "art_code")
_CORPORATE_SUFFIXES = (
    "\u80a1\u4efd\u6709\u9650\u516c\u53f8",
    "\u6709\u9650\u516c\u53f8",
    "\u96c6\u56e2\u80a1\u4efd\u6709\u9650\u516c\u53f8",
    "\u96c6\u56e2\u6709\u9650\u516c\u53f8",
)
_GENERIC_ISSUER_PREFIX_RE = re.compile(
    r"^(?:(?!\u5173\u4e8e|\u4e8b\u52a1\u6240|\u6838\u67e5|\u610f\u89c1|\u56de\u590d|\u95ee\u8be2).)+?"
    r"(?:\u96c6\u56e2\u80a1\u4efd\u6709\u9650\u516c\u53f8|\u80a1\u4efd\u6709\u9650\u516c\u53f8|\u96c6\u56e2\u6709\u9650\u516c\u53f8|\u6709\u9650\u516c\u53f8)"
    r"(?=[:\uff1a]?\d{4}\u5e74)"
)


def sync_stock_official_disclosures(
    *,
    duckdb_path: str,
    stock_codes: list[str],
    from_date: date | str,
    to_date: date | str | None = None,
    tushare_client: object,
    run_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    normalized_codes = _normalize_stock_codes(stock_codes)
    if not normalized_codes:
        raise ValueError("stock_codes must contain at least one valid stock code.")

    now_dt = _normalize_now(now)
    requested_from = _coerce_date(from_date)
    requested_to = _coerce_date(to_date) if to_date is not None else now_dt.date()
    effective_to = min(requested_to, now_dt.date())
    if requested_from > effective_to:
        raise ValueError("from_date must be on or before to_date after future-date capping.")

    resolved_run_id = run_id or _build_run_id(now_dt)
    conn = duckdb.connect(str(Path(duckdb_path)), read_only=False)
    results: list[dict[str, object]] = []
    total_fetched = 0
    total_upserted = 0
    failures = 0
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope(__name__):
            for stock_code in normalized_codes:
                # Keep the attempted interval available for failure provenance;
                # successful syncs may widen it when an existing interval
                # overlaps or directly adjoins the requested window.
                attempt_source_version = _source_version(
                    stock_code=stock_code,
                    from_date=requested_from,
                    to_date=effective_to,
                )
                vendor_version = _vendor_version(stock_code=stock_code, from_date=requested_from, to_date=effective_to)
                attempt_at = now_dt
                prior = get_stock_official_disclosure_sync_status(conn, stock_code=stock_code)
                prior_success = _coerce_timestamp(prior.get("last_success_at")) if prior else None
                prior_covered = str(prior.get("covered_through_date") or "").strip() if prior else None
                prior_coverage_start = (
                    str(prior.get("coverage_start_date") or prior.get("requested_from_date") or "").strip()
                    if prior and prior_covered
                    else ""
                )
                try:
                    records = _fetch_anns_d_window(
                        tushare_client,
                        stock_code=stock_code,
                        start_date=requested_from,
                        end_date=effective_to,
                    )
                    fetched_count = len(records)
                    coverage_start, coverage_end = _merge_coverage_window(
                        prior_start=_parse_date(prior_coverage_start),
                        prior_end=_parse_date(prior_covered),
                        requested_start=requested_from,
                        requested_end=effective_to,
                    )
                    coverage_source_version = _source_version(
                        stock_code=stock_code,
                        from_date=coverage_start,
                        to_date=coverage_end,
                    )
                    rows = _build_rows(
                        records,
                        stock_code=stock_code,
                        source_version=attempt_source_version,
                        vendor_version=vendor_version,
                        run_id=resolved_run_id,
                        ingested_at=attempt_at,
                    )
                    conn.execute("begin transaction")
                    upserted_count = upsert_stock_official_disclosures(conn, rows=rows)
                    upsert_stock_official_disclosure_sync_status(
                        conn,
                        stock_code=stock_code,
                        requested_from_date=coverage_start.isoformat(),
                        covered_through_date=coverage_end.isoformat(),
                        last_attempt_at=attempt_at,
                        last_success_at=attempt_at,
                        status="empty" if upserted_count == 0 else "success",
                        fetched_count=fetched_count,
                        upserted_count=upserted_count,
                        error_message=None,
                        run_id=resolved_run_id,
                        source_version=coverage_source_version,
                    )
                    conn.execute("commit")
                    total_fetched += fetched_count
                    total_upserted += upserted_count
                    results.append(
                        {
                            "stock_code": stock_code,
                            "status": "empty" if upserted_count == 0 else "success",
                            "fetched_count": fetched_count,
                            "upserted_count": upserted_count,
                            "source_version": coverage_source_version,
                            "vendor_version": vendor_version,
                        }
                    )
                except Exception as exc:
                    _rollback_quietly(conn)
                    failures += 1
                    error_message = _safe_error_message(exc)
                    conn.execute("begin transaction")
                    upsert_stock_official_disclosure_sync_status(
                        conn,
                        stock_code=stock_code,
                        requested_from_date=prior_coverage_start or requested_from.isoformat(),
                        covered_through_date=prior_covered or None,
                        last_attempt_at=attempt_at,
                        last_success_at=prior_success,
                        status="failed",
                        fetched_count=0,
                        upserted_count=0,
                        error_message=error_message,
                        run_id=resolved_run_id,
                        source_version=attempt_source_version,
                    )
                    conn.execute("commit")
                    results.append(
                        {
                            "stock_code": stock_code,
                            "status": "failed",
                            "error_message": error_message,
                            "source_version": attempt_source_version,
                            "vendor_version": vendor_version,
                        }
                    )
    finally:
        conn.close()

    return {
        "status": "completed" if failures == 0 else "completed_with_errors",
        "run_id": resolved_run_id,
        "requested_from_date": requested_from.isoformat(),
        "requested_to_date": requested_to.isoformat(),
        "effective_to_date": effective_to.isoformat(),
        "stock_code_count": len(normalized_codes),
        "failed_stock_count": failures,
        "fetched_count": total_fetched,
        "upserted_count": total_upserted,
        "results": results,
    }


def _refresh_stock_official_disclosures(
    *,
    duckdb_path: str | None = None,
    stock_codes: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError(
            f"{TUSHARE_TOKEN_ENV} is not set; add it to config/.env or export it before calling Tushare pro API."
        )
    pro = import_tushare_pro().pro_api(token)
    resolved_from = from_date or (date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()
    return sync_stock_official_disclosures(
        duckdb_path=str(duckdb_path or settings.duckdb_path),
        stock_codes=list(stock_codes or ()),
        from_date=resolved_from,
        to_date=to_date,
        tushare_client=pro,
    )


refresh_stock_official_disclosures = register_actor_once(
    "refresh_stock_official_disclosures",
    _refresh_stock_official_disclosures,
)


def classify_disclosure_title(
    title: str,
    *,
    stock_name: str = "",
    stock_code: str = "",
) -> tuple[str, date | None]:
    normalized = _normalize_title(title, stock_name=stock_name, stock_code=stock_code)
    for matcher, month_day in ((_ANNUAL_RE, (12, 31)), (_HALF_RE, (6, 30)), (_Q1_RE, (3, 31)), (_Q3_RE, (9, 30))):
        match = matcher.fullmatch(normalized)
        if match is None:
            continue
        year = int(match.group("year"))
        return FINANCIAL_REPORT_TYPE, date(year, month_day[0], month_day[1])
    return ANNOUNCEMENT_TYPE, None


def _build_rows(
    records: list[dict[str, object]],
    *,
    stock_code: str,
    source_version: str,
    vendor_version: str,
    run_id: str,
    ingested_at: datetime,
) -> list[dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    rejected_count = 0
    for record in records:
        publish_date = _extract_publish_date(record)
        title = _text(record.get("title"))
        document_url = _extract_document_url(record)
        if publish_date is None or not title or not document_url:
            rejected_count += 1
            continue
        stock_name = _text(record.get("name")) or stock_code
        source_id = _extract_source_id(record, stock_code=stock_code, publish_date=publish_date, title=title, document_url=document_url)
        evidence_type, report_period = classify_disclosure_title(title, stock_name=stock_name, stock_code=stock_code)
        disclosure_key = _disclosure_key(stock_code=stock_code, publish_date=publish_date, source_id=source_id, title=title, document_url=document_url)
        rows[disclosure_key] = {
            "disclosure_key": disclosure_key,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "evidence_type": evidence_type,
            "publish_date": publish_date.isoformat(),
            "report_period": report_period.isoformat() if report_period is not None else None,
            "title": title,
            "document_url": document_url,
            "source_id": source_id,
            "source_label": SOURCE_LABEL,
            "source_version": source_version,
            "vendor_version": vendor_version,
            "received_at": _extract_received_at(record),
            "ingested_at": ingested_at,
            "run_id": run_id,
            "raw_json": json.dumps(record, ensure_ascii=False, sort_keys=True, default=str),
        }
    if rejected_count:
        raise RuntimeError(f"Rejected {rejected_count} anns_d rows with missing required title/date/url.")
    return list(rows.values())


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        records = frame.to_dict(orient="records")
        return [{str(key): value for key, value in dict(record).items()} for record in records]
    if isinstance(frame, list):
        return [{str(key): value for key, value in dict(record).items()} for record in frame]
    raise RuntimeError("Unsupported anns_d response; expected DataFrame-like object.")


def _fetch_anns_d_window(
    tushare_client: object,
    *,
    stock_code: str,
    start_date: date,
    end_date: date,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Fetch an anns_d date window without accepting a truncated page as complete.

    ``anns_d`` has no pagination cursor and caps each response at 2,000 rows.
    A full-window result at the cap is recursively split into adjacent,
    non-overlapping date windows. A one-day result at the cap fails closed so
    sync status cannot claim coverage that may still be truncated.
    """
    if start_date > end_date:
        return []
    page_limit = max(1, int(limit if limit is not None else ANNS_D_PAGE_LIMIT))
    frame = tushare_client.anns_d(
        ts_code=stock_code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    records = _records_from_frame(frame)
    if len(records) < page_limit:
        return records
    if start_date == end_date:
        raise RuntimeError(
            f"anns_d response reached the {page_limit}-row limit for {stock_code} on "
            f"{start_date.isoformat()}; refusing to mark coverage complete."
        )
    span_days = (end_date - start_date).days
    left_end = start_date + timedelta(days=span_days // 2)
    right_start = left_end + timedelta(days=1)
    return _fetch_anns_d_window(
        tushare_client,
        stock_code=stock_code,
        start_date=start_date,
        end_date=left_end,
        limit=page_limit,
    ) + _fetch_anns_d_window(
        tushare_client,
        stock_code=stock_code,
        start_date=right_start,
        end_date=end_date,
        limit=page_limit,
    )


def _extract_publish_date(record: dict[str, object]) -> date | None:
    for key in ("ann_date", "publish_date", "date", "trade_date"):
        parsed = _parse_date(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _extract_document_url(record: dict[str, object]) -> str:
    for key in _DOCUMENT_URL_KEYS:
        text = _text(record.get(key))
        if text.startswith(("http://", "https://")):
            return text
    return ""


def _extract_source_id(
    record: dict[str, object],
    *,
    stock_code: str,
    publish_date: date,
    title: str,
    document_url: str,
) -> str:
    # anns_d document URLs are the stable official-document identity. Preserve
    # a vendor-provided id as row metadata; _disclosure_key intentionally does
    # not use it when a URL is present, so a later id revision cannot create a
    # second row for the same document.
    for key in _SOURCE_ID_KEYS:
        text = _text(record.get(key))
        if text:
            return text
    # Tushare may omit ann_id/art_code, but the document URL remains the
    # stable vendor identity when a title is corrected in place. Keep the
    # publish date only as a fallback for malformed records with no URL.
    seed_parts = ["tushare", stock_code, document_url]
    if not document_url:
        seed_parts.append(publish_date.isoformat())
    seed = "|".join(seed_parts)
    return "derived_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _extract_received_at(record: dict[str, object]) -> datetime | None:
    for key in ("received_at", "rec_time", "datetime", "created_at"):
        parsed = _parse_timestamp(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _disclosure_key(
    *,
    stock_code: str,
    publish_date: date,
    source_id: str,
    title: str,
    document_url: str,
) -> str:
    # URL is part of the stable document identity so a revised URL is a new
    # evidence row, while title/date/source-id edits at the same URL upsert in
    # place. The source id is intentionally omitted when a URL is present.
    seed = "|".join(["tushare", stock_code, document_url or source_id])
    return "sod_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _merge_coverage_window(
    *,
    prior_start: date | None,
    prior_end: date | None,
    requested_start: date,
    requested_end: date,
) -> tuple[date, date]:
    """Merge only one continuous coverage interval; retain gaps fail-closed."""
    if prior_start is None or prior_end is None or prior_start > prior_end:
        return requested_start, requested_end
    if requested_start <= prior_end + timedelta(days=1) and prior_start <= requested_end + timedelta(days=1):
        return min(prior_start, requested_start), max(prior_end, requested_end)
    return requested_start, requested_end


def _source_version(*, stock_code: str, from_date: date, to_date: date) -> str:
    digest = hashlib.sha256(stock_code.encode("utf-8")).hexdigest()[:8]
    return f"sv_tushare_stock_official_disclosure_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}_{digest}"


def _vendor_version(*, stock_code: str, from_date: date, to_date: date) -> str:
    digest = hashlib.sha256(stock_code.encode("utf-8")).hexdigest()[:8]
    return f"vv_tushare_anns_d_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}_{digest}"


def _normalize_title(title: str, *, stock_name: str, stock_code: str) -> str:
    normalized = re.sub(r"\s+", "", str(title or "").strip())
    prefixes: list[str] = []
    clean_name = stock_name.strip()
    if clean_name:
        prefixes.append(clean_name)
        prefixes.extend(f"{clean_name}{suffix}" for suffix in _CORPORATE_SUFFIXES)
    code = stock_code.strip()
    if code:
        prefixes.append(code)
        prefixes.append(code.split(".", 1)[0])
    for prefix in prefixes:
        if not prefix:
            continue
        if normalized.startswith(prefix) and len(normalized) > len(prefix) and normalized[len(prefix)].isdigit():
            return normalized[len(prefix):]
        for separator in ("\uff1a", ":"):
            token = f"{prefix}{separator}"
            if normalized.startswith(token):
                return normalized[len(token):]
    generic_prefix = _GENERIC_ISSUER_PREFIX_RE.match(normalized)
    if generic_prefix is not None:
        return normalized[generic_prefix.end():].lstrip(":\uff1a")
    return normalized


def _normalize_stock_codes(stock_codes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in stock_codes:
        code = _normalize_stock_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def _normalize_stock_code(raw: object) -> str:
    text = _text(raw).upper()
    if not text:
        return ""
    if "." in text:
        base, suffix = text.split(".", 1)
        if len(base) == 6 and suffix in {"SH", "SZ", "BJ"}:
            return f"{base}.{suffix}"
        return ""
    if len(text) == 6 and text.isdigit():
        if text.startswith(("600", "601", "603", "605", "688", "689", "900")):
            return f"{text}.SH"
        if text.startswith(("000", "001", "002", "003", "300", "301")):
            return f"{text}.SZ"
        if text.startswith(("430", "431", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879")):
            return f"{text}.BJ"
    return ""


def _parse_date(value: object) -> date | None:
    text = _text(value)
    if not text:
        return None
    compact = re.sub(r"[^0-9-]", "", text)
    if len(compact) == 8 and compact.isdigit():
        return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
    if len(text) >= 10:
        return date.fromisoformat(text[:10].replace("/", "-"))
    raise ValueError(f"Unsupported date value: {value!r}")


def _parse_timestamp(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    candidate = text.replace(" ", "T")
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        # Tushare documents rec_time as a publication time but does not
        # declare a timezone. Keep raw_json and omit an ambiguous timestamp.
        return None
    return parsed.astimezone(UTC)


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError(f"Expected non-empty date value, got {value!r}.")
    return parsed


def _coerce_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    text = _text(value)
    if not text:
        return None
    candidate = text.replace(" ", "T")
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return _parse_timestamp(value)
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _normalize_now(now: datetime | None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_run_id(now: datetime) -> str:
    return f"stock_official_disclosure:{now.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"


def _safe_error_message(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    tokens = {os.getenv(TUSHARE_TOKEN_ENV, "").strip()}
    try:
        tokens.add(str(getattr(get_settings(), "tushare_token", "") or "").strip())
    except Exception:  # noqa: S110  # 脱敏辅助不得因 settings 读取失败中断错误上报；env token 兜底已覆盖
        pass
    for token in tokens:
        if token:
            message = message.replace(token, "***")
    return message


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        return


def _text(value: object) -> str:
    return str(value or "").strip()
