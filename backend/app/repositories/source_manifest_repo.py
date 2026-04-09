from dataclasses import dataclass, field


@dataclass
class SourceManifestRepository:
    rows: list[dict[str, object]] = field(default_factory=list)

    def add_many(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        self.rows.extend(rows)
        return rows
