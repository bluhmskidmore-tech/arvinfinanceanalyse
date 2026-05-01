from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse
from backend.app.security.auth_context import AuthContext, get_auth_context


router = APIRouter(prefix="/api/cube")


def _raise_cube_query_not_promoted() -> None:
    raise HTTPException(
        status_code=503,
        detail="Cube query route is reserved and not backed by the current governed rollout yet.",
    )


@router.post("/query", response_model=CubeQueryResponse)
def cube_query(
    request: CubeQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> CubeQueryResponse:
    _raise_cube_query_not_promoted()


@router.get("/dimensions/{fact_table}")
def list_dimensions(fact_table: str) -> dict[str, object]:
    _raise_cube_query_not_promoted()
