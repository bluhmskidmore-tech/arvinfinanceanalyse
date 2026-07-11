from __future__ import annotations

import base64
import logging
import re
from importlib import import_module
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
MAX_LEDGER_MULTIPART_OVERHEAD_BYTES = 64 * 1024


class _LedgerImportTooLargeError(ValueError):
    pass


def _svc():
    return import_module("backend.app.services.ledger_import_service")


def _import_task():
    return import_module("backend.app.tasks.ledger_import")


def _run_svc():
    return import_module("backend.app.services.ledger_import_run_service")


def _analytics_svc():
    return import_module("backend.app.services.ledger_analytics_service")


@router.post("/ledger/import", status_code=202)
async def import_ledger(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
):
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="ledger.data", action="import")
    except PermissionError as exc:
        return _error_response(
            status_code=403,
            code="LEDGER_IMPORT_FORBIDDEN",
            message=str(exc),
            retryable=False,
        )
    try:
        _reject_unknown_query_params(request, set())
        service_module = _svc()
        file_name, content = await _extract_multipart_file(
            request,
            max_file_bytes=service_module.MAX_LEDGER_IMPORT_BYTES,
        )
        file_name = _run_svc().normalize_ledger_import_file_name(file_name)
        suffix = Path(file_name).suffix.lower()
        if suffix not in service_module.SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported ledger import file type: {suffix or '<none>'}")
    except _LedgerImportTooLargeError as exc:
        return _error_response(
            status_code=413,
            code="LEDGER_IMPORT_TOO_LARGE",
            message=str(exc),
            retryable=False,
        )
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_IMPORT_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )

    run_id = f"ledger_import:{uuid4().hex}"
    request_id = f"req_ledger_{uuid4().hex[:12]}"
    run_service = _run_svc()
    transition_args = {
        "governance_dir": settings.governance_path,
        "governance_backend": settings.governance_backend,
        "governance_sql_dsn": settings.governance_sql_dsn,
        "job_state_dsn": settings.job_state_dsn,
        "run_id": run_id,
        "file_name": file_name,
    }
    try:
        run_service.record_ledger_import_transition(status="queued", **transition_args)
    except Exception as exc:
        logger.error(
            "Ledger import queued transition failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        return _error_response(
            status_code=503,
            code="LEDGER_LOADING_FAILURE",
            message="Ledger import status is unavailable.",
            retryable=True,
        )
    try:
        task_module = _import_task()
        task_module.run_ledger_import.send(
            file_name=file_name,
            content_base64=base64.b64encode(content).decode("ascii"),
            duckdb_path=str(settings.duckdb_path),
            run_id=run_id,
            governance_dir=str(settings.governance_path),
        )
    except Exception as exc:
        logger.error(
            "Ledger import queue dispatch failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        try:
            run_service.record_ledger_import_transition(
                status="failed",
                error_category="dispatch_failed",
                error_message="Ledger import queue dispatch failed.",
                **transition_args,
            )
        except Exception as transition_exc:
            logger.error(
                "Ledger import dispatch failure transition failed run_id=%s error_type=%s.",
                run_id,
                type(transition_exc).__name__,
            )
        return _error_response(
            status_code=503,
            code="LEDGER_LOADING_FAILURE",
            message="Ledger import queue dispatch failed.",
            retryable=True,
        )

    return JSONResponse(
        status_code=202,
        content={
            "data": {
                "status": "queued",
                "run_id": run_id,
                "file_name": file_name,
            },
            "trace": {
                "request_id": request_id,
                "run_id": run_id,
            },
        },
    )


@router.get("/ledger/import-status")
def get_ledger_import_status(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str | None = Query(None),
):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, {"run_id"})
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise ValueError("run_id is required.")
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
        run_service = _run_svc()
        try:
            data = run_service.get_ledger_import_run_status(
                governance_dir=settings.governance_path,
                governance_backend=settings.governance_backend,
                governance_sql_dsn=settings.governance_sql_dsn,
                run_id=normalized_run_id,
            )
        except run_service.LedgerImportRunNotFoundError:
            return _error_response(
                status_code=404,
                code="LEDGER_IMPORT_RUN_NOT_FOUND",
                message="Ledger import run was not found.",
                retryable=False,
            )
        return {
            "data": data,
            "trace": {
                "request_id": f"req_ledger_{uuid4().hex[:12]}",
                "run_id": normalized_run_id,
            },
        }
    except ValueError as exc:
        return _error_response(
            status_code=400,
            code="LEDGER_IMPORT_STATUS_INVALID_REQUEST",
            message=str(exc),
            retryable=False,
        )
    except Exception as exc:
        logger.error(
            "Ledger import status read failed run_id=%s error_type=%s.",
            str(run_id or "").strip(),
            type(exc).__name__,
        )
        return _error_response(
            status_code=503,
            code="LEDGER_IMPORT_STATUS_UNAVAILABLE",
            message="Ledger import status is unavailable.",
            retryable=True,
        )


@router.get("/ledger/imports")
def list_ledger_imports(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, set())
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
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
def list_ledger_dates(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, set())
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
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
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    as_of_date: str | None = Query(None),
):
    settings = get_settings()
    try:
        _reject_unknown_query_params(request, {"as_of_date"})
        requested = _analytics_svc().normalize_requested_date(as_of_date=as_of_date)
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
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
    auth: Annotated[AuthContext, Depends(get_auth_context)],
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
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
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
    auth: Annotated[AuthContext, Depends(get_auth_context)],
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
        auth_error = _ledger_read_auth_error(auth, settings)
        if auth_error is not None:
            return auth_error
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


def _ledger_read_auth_error(auth: AuthContext, settings) -> JSONResponse | None:
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="ledger.data", action="read")
    except PermissionError as exc:
        return _error_response(
            status_code=403,
            code="LEDGER_READ_FORBIDDEN",
            message=str(exc),
            retryable=False,
        )
    except RuntimeError as exc:
        return _error_response(
            status_code=503,
            code="LEDGER_AUTH_UNAVAILABLE",
            message=str(exc),
            retryable=True,
        )
    return None


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


async def _extract_multipart_file(
    request: Request,
    *,
    max_file_bytes: int,
) -> tuple[str, bytes]:
    content_type = request.headers.get("content-type", "")
    boundary = _multipart_boundary(content_type)
    if boundary is None:
        raise ValueError("Content-Type must be multipart/form-data with a file field.")

    body = await _read_bounded_request_body(
        request,
        max_body_bytes=max_file_bytes + MAX_LEDGER_MULTIPART_OVERHEAD_BYTES,
    )
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
        if len(payload) > max_file_bytes:
            raise _LedgerImportTooLargeError(
                f"Ledger import file is too large. Maximum size is {max_file_bytes} bytes."
            )
        return filename, payload

    raise ValueError("Missing multipart file field named 'file'.")


async def _read_bounded_request_body(request: Request, *, max_body_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_bytes = int(content_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be a non-negative integer.") from exc
        if declared_bytes < 0:
            raise ValueError("Content-Length must be a non-negative integer.")
        if declared_bytes > max_body_bytes:
            raise _LedgerImportTooLargeError(
                "Ledger import request is too large."
            )

    chunks: list[bytes] = []
    received_bytes = 0
    async for chunk in request.stream():
        received_bytes += len(chunk)
        if received_bytes > max_body_bytes:
            raise _LedgerImportTooLargeError("Ledger import request is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


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
