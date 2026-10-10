"""Fail-closed preflight for the external homepage macro refresh timer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "docs/templates/home_macro_release_refresh_go_live_checklist.md"
DEFAULT_PACKET = ROOT / "docs/templates/home_macro_release_refresh_timer_enablement_packet.md"
DEFAULT_EVIDENCE = ROOT / "docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md"

_FIELDS = {
    "owner": ("checklist", "Owner:"),
    "rollback": ("checklist", "Rollback:"),
    "timer_host": ("packet", "Timer host:"),
    "write_window": ("packet", "Write window:"),
    "log_path": ("packet", "Log path:"),
    "first_scheduled_run_evidence": ("evidence", "First scheduled run evidence:"),
}


def _value(text: str, label: str) -> str | None:
    for line in text.splitlines():
        if line.strip().lower().startswith(label.lower()):
            value = line.split(":", 1)[1].strip()
            if value and "<" not in value and ">" not in value and value.lower() not in {"tbd", "pending"}:
                return value
    return None


def run_preflight(*, checklist_path: Path, packet_path: Path, evidence_path: Path) -> dict[str, object]:
    paths = {"checklist": checklist_path, "packet": packet_path, "evidence": evidence_path}
    missing_files = [name for name, path in paths.items() if not path.is_file()]
    texts = {name: path.read_text(encoding="utf-8") if path.is_file() else "" for name, path in paths.items()}
    packet_lower = texts["packet"].lower()
    packet_safe = "schtasks /create" not in packet_lower and "crontab " not in packet_lower
    repo_status = "repo-complete" if not missing_files and packet_safe else "repo-incomplete"
    missing_fields = [field for field, (document, label) in _FIELDS.items() if _value(texts[document], label) is None]
    ops_status = "ready" if repo_status == "repo-complete" and not missing_fields else "blocked"
    return {
        "repo_status": repo_status,
        "ops_status": ops_status,
        "missing_files": missing_files,
        "missing_fields": missing_fields,
        "packet_safe": packet_safe,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args(argv)
    result = run_preflight(checklist_path=args.checklist, packet_path=args.packet, evidence_path=args.evidence)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ops_status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
