from __future__ import annotations

import json
import os
from pathlib import Path


def resolve_obsidian_vault_path() -> Path | None:
    explicit = str(os.getenv("MOSS_OBSIDIAN_VAULT_PATH", "")).strip()
    if explicit:
        return Path(explicit).expanduser()

    config_candidates: list[Path] = []
    appdata = str(os.getenv("APPDATA", "")).strip()
    if appdata:
        config_candidates.append(Path(appdata) / "Obsidian" / "obsidian.json")
    config_candidates.append(Path.home() / "AppData" / "Roaming" / "Obsidian" / "obsidian.json")
    config_candidates.append(Path.home() / ".config" / "Obsidian" / "obsidian.json")

    for candidate in config_candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        vaults = payload.get("vaults")
        if not isinstance(vaults, dict):
            continue
        ranked: list[tuple[int, int, str]] = []
        for entry in vaults.values():
            if not isinstance(entry, dict):
                continue
            path_value = str(entry.get("path") or "").strip()
            if not path_value:
                continue
            ranked.append(
                (
                    1 if bool(entry.get("open")) else 0,
                    int(entry.get("ts") or 0),
                    path_value,
                )
            )
        if ranked:
            ranked.sort(reverse=True)
            return Path(ranked[0][2]).expanduser()
    return None


def read_note_text(note_path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return note_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return note_path.read_text(encoding="utf-8", errors="ignore")
