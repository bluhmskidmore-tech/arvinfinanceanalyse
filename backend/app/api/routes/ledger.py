from __future__ import annotations

import re
from importlib import import_module
from uuid import uuid4

from backend.app.governance.settings import get_settings
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/api")


def _svc():
    return import_module("backend.app.services.ledger_import_service")


def _analytics_svc():
    return import_module("backend.app.services.ledger_analytics_service")


@router.post("/ledger/import")
async def import_ledger(request: Request):
    settings = get_settings()
    service = _svc().LedgerImportService(str(settings.duckdb_path))
    try:
        _reject_unknown_query_params(request, set())
        file_name, content = await _extract_multipart_file(request)
        payload = service.import_file(file_name=file_name, content=content)
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_IMPORT_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )

    if payload.get("error", {}).get("code") == "LEDGER_IMPORT_DUPLICATE":
        return JSONResponse(status_code=409, content=payload)
    return payload


@router.get("/ledger/imports")
def list_ledger_imports(request: Request):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, set())
        return _svc().LedgerImportService(str(settings.duckdb_path)).list_imports()
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_IMPORTS_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )


@router.get("/ledger/dates")
def list_ledger_dates(request: Request):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, set())
        return _analytics_svc().LedgerAnalyticsService(str(settings.duckdb_path)).dates()
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_DATES_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_DATES_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )


@router.get("/ledger/dashboard")
def ledger_dashboard(
    request: Request,
    as_of_date: str | None = Query(None),
):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, {"as_of_date"})
        requested = _analytics_svc().normalize_requested_date(as_of_date=as_of_date)
        return _analytics_svc().LedgerAnalyticsService(str(settings.duckdb_path)).dashboard(
            requested_as_of_date=requested,
        )
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_DASHBOARD_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_DASHBOARD_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )


@router.get("/ledger/positions")
def ledger_positions(
    request: Request,
    as_of_date: str | None = Query(None),
    direction: str | None = Query(None),
    bond_code: str | None = Query(None),
    portfolio: str | None = Query(None),
    account_category_std: str | None = Query(None),
    asset_class_std: str | None = Query(None),
    cost_center: str | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
):
    settings = get_settings()
    try:
        analytics = _analytics_svc()
        _reject_unknown_query_params(
            request,
            {
                "as_of_date",
                "direction",
                "bond_code",
                "portfolio",
                "account_category_std",
                "asset_class_std",
                "cost_center",
                "page",
                "page_size",
            },
        )
        requested = analytics.normalize_requested_date(as_of_date=as_of_date)
        filters = analytics.normalize_filters(
            direction=direction,
            bond_code=bond_code,
            portfolio=portfolio,
            account_category_std=account_category_std,
            asset_class_std=asset_class_std,
            cost_center=cost_center,
        )
        return analytics.LedgerAnalyticsService(str(settings.duckdb_path)).positions(
            requested_as_of_date=requested,
            filters=filters,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_POSITIONS_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_POSITIONS_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )


@router.get("/ledger/export/positions")
def export_ledger_positions(
    request: Request,
    as_of_date: str | None = Query(None),
    direction: str | None = Query(None),
    bond_code: str | None = Query(None),
    portfolio: str | None = Query(None),
    account_category_std: str | None = Query(None),
    asset_class_std: str | None = Query(None),
    cost_center: str | None = Query(None),
    format: str = Query("xlsx"),
):
    settings = get_settings()
    try:
        if format != "xlsx":
            raise ValueError("format must be xlsx.")
        analytics = _analytics_svc()
        _reject_unknown_query_params(
            request,
            {
                "as_of_date",
                "direction",
                "bond_code",
                "portfolio",
                "account_category_std",
                "asset_class_std",
                "cost_center",
                "format",
            },
        )
        requested = analytics.normalize_requested_date(as_of_date=as_of_date)
        filters = analytics.normalize_filters(
            direction=direction,
            bond_code=bond_code,
            portfolio=portfolio,
            account_category_std=account_category_std,
            asset_class_std=asset_class_std,
            cost_center=cost_center,
        )
        filename, content, metadata_headers = analytics.LedgerAnalyticsService(
            str(settings.duckdb_path),
        ).export_positions(
            requested_as_of_date=requested,
            filters=filters,
        )
        return Response(
            content=content,
            media_type=analytics.XLSX_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                **metadata_headers,
            },
        )
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_EXPORT_POSITIONS_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_POSITIONS_LOADING_FAILURE",
            message=str(exc),
            retryable=True,
        )


def _reject_unknown_query_params(request: Request, allowed: set[str]) -> None:
    unknown = sorted(set(request.query_params.keys()) - allowed)
    if unknown:
        raise ValueError(f"Unsupported query parameter(s): {', '.join(unknown)}")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
            },
            "trace": {
                "request_id": f"req_ledger_{uuid4().hex[:12]}",
            },
        },
    )


async def _extract_multipart_file(request: Request) -> tuple[str, bytes]:
    content_type = request.headers.get("content-type", "")
    boundary = _multipart_boundary(content_type)
    if boundary is None:
        raise ValueError("Content-Type must be multipart/form-data with a file field.")

    body = await request.body()
    marker = b"--" + boundary
    for raw_part in body.split(marker):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")
        header_bytes, separator, payload = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_bytes.decode("latin-1", errors="replace").split("\r\n")
        disposition = next(
            (
                header
                for header in headers
                if header.lower().startswith("content-disposition:")
            ),
            "",
        )
        if 'name="file"' not in disposition:
            continue
        filename = _multipart_filename(disposition)
        if not filename:
            raise ValueError("Multipart file field is missing filename.")
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        if not payload:
            raise ValueError("Uploaded ledger file is empty.")
        return filename, payload

    raise ValueError("Missing multipart file field named 'file'.")


def _multipart_boundary(content_type: str) -> bytes | None:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if match is None:
        return None
    boundary = match.group("boundary").strip().strip('"')
    return boundary.encode("latin-1") if boundary else None


def _multipart_filename(disposition: str) -> str:
    match = re.search(r'filename="(?P<filename>[^"]*)"', disposition)
    if match is None:
        return ""
    return match.group("filename").strip()
