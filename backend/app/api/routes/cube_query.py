from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.governance.settings import get_settings
from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse
from backend.app.services.cube_query_service import CubeQueryService


router = APIRouter(prefix="/api/cube")
_service = CubeQueryService()


@router.post("/query", response_model=CubeQueryResponse)
def cube_query(request: CubeQueryRequest) -> CubeQueryResponse:
    try:
        return _service.execute(request, str(get_settings().duckdb_path))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/dimensions/{fact_table}")
def list_dimensions(fact_table: str) -> dict[str, object]:
    try:
        return _service.describe_fact_table(fact_table)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
