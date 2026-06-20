"""Cube query API routes – Phase 3 upgraded.

These routes now delegate to ``AnalyticalBridgeService`` which handles
``formal``, ``analytical``, and ``ledger`` bases.  The previous stub
(``_raise_cube_query_not_promoted``) is replaced by the real service path.

Auth is required via ``AuthContext`` (header X-User-Id / X-User-Role or
env-based fallback).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.governance.settings import Settings, get_settings
from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.analytical_bridge_service import AnalyticalBridgeService
from backend.app.services.cube_query_service import CubeQueryService

router = APIRouter(prefix="/api/cube")


@router.post("/query", response_model=CubeQueryResponse)
def cube_query(
    request: CubeQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CubeQueryResponse:
    bridge = AnalyticalBridgeService()
    try:
        return bridge.execute(request, settings.duckdb_path, auth=auth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dimensions/{fact_table}")
def list_dimensions(fact_table: str) -> dict[str, object]:
    try:
        return CubeQueryService.describe_fact_table(fact_table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
