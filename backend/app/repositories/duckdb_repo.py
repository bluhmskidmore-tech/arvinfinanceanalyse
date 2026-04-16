from dataclasses import dataclass


@dataclass
class DuckDBRepository:
    """DuckDB is read-only from the API/service path in Phase 1."""

    path: str
    read_only: bool = True

    def healthcheck(self) -> dict[str, object]:
        return {"ok": True, "mode": "read_only", "path": self.path}
