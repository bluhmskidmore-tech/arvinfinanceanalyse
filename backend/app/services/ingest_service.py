from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.repositories.source_manifest_repo import SourceManifestRepository


@dataclass
class IngestService:
    data_root: Path
    manifest_repo: SourceManifestRepository | None = None

    def scan(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for path in sorted(self.data_root.rglob("*")):
            if not path.is_file():
                continue

            source_name = path.name.split("-")[0] if "-" in path.name else path.parent.name
            rows.append(
                {
                    "source_name": source_name,
                    "file_name": path.name,
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                }
            )

        if self.manifest_repo is not None:
            self.manifest_repo.add_many(rows)

        return rows
