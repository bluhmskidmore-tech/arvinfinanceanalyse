from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse


router = APIRouter(prefix="/api/cube")


def _raise_cube_query_not_promoted() -> None:
    raise HTTPException(
        status_code=503,
        detail="Cube query route is reserved and not backed by the current governed rollout yet.",
    )


@router.post("/query", response_model=CubeQueryResponse)
def cube_query(request: CubeQueryRequest) -> CubeQueryResponse:
    _raise_cube_query_not_promoted()


@router.get("/dimensions/{fact_table}")
def list_dimensions(fact_table: str) -> dict[str, object]:
    _raise_cube_query_not_promoted()
