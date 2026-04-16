from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import duckdb


@dataclass
class CubeQueryRepository:
    path: str

    def fetchall(
        self,
        sql: str,
        params: Sequence[object] | None = None,
    ) -> list[tuple]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                return conn.execute(sql, list(params or [])).fetchall()
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Cube query storage is unavailable.") from exc
