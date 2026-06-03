"""Read-only preflight before enabling the Tushare news backup timer."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CHECKLIST_PATH = Path("docs/templates/tushare_news_backup_refresh_go_live_checklist.md")
TIMER_PACKET_PATH = Path("docs/templates/tushare_news_backup_timer_enablement_packet.md")
EVIDENCE_PATH = Path("docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md")
PAGE_SCREENSHOT_PATH = Path("frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png")
PAGE_JSON_PATH = Path("frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json")

PLACEHOLDER_MARKERS = ("<", ">")
DISALLOWED_INSTALL_COMMANDS = (
    "schtasks /create",
    "crontab ",
)
PREFLIGHT_STAGES = ("pre-enable", "post-enable")
CLI_STAGES = (*PREFLIGHT_STAGES, "all")


@dataclass(frozen=True)
class GateResult:
    name: str
    outcome: str
    detail: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _line_value(text: str, label: str) -> str:
    prefix = f"- {label}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            return stripped[len(prefix) :].strip()
    return ""


def _has_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or any(marker in stripped for marker in PLACEHOLDER_MARKERS)


def _check_required_lines(text: str, labels: tuple[str, ...]) -> tuple[bool, str]:
    missing = [label for label in labels if _has_placeholder(_line_value(text, label))]
    if missing:
        return False, f"Pending fields: {', '.join(missing)}"
    return True, "All required fields are filled."


def _boundary_rows(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("|")]


def _check_boundary_confirmation(text: str) -> tuple[bool, str]:
    rows = _boundary_rows(text)
    required_fragments = (
        "MOSS_TUSHARE_TOKEN",
        "Job runs from repo root",
        "DuckDB path",
        "Refresh window avoids",
        "/ui/news/tushare-npr/ingest",
        "/api/news/tushare-npr/ingest",
        "Homepage still reads",
    )
    missing_or_pending: list[str] = []
    for fragment in required_fragments:
        row = next((candidate for candidate in rows if fragment in candidate), "")
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        status = cells[1].lower() if len(cells) >= 3 else ""
        evidence = cells[2] if len(cells) >= 3 else ""
        if status != "yes" or _has_placeholder(evidence):
            missing_or_pending.append(fragment)
    if missing_or_pending:
        return False, f"Pending boundary checks: {', '.join(missing_or_pending)}"
    return True, "All boundary checks are yes with evidence."


def _check_evidence_text(text: str) -> tuple[bool, str]:
    required = (
        "status = completed",
        "fetched = 1203",
        "inserted = 1203",
        "purged_expired = 97",
        "tushare.major_news",
        "2026-06-03T19:43:00+00:00",
        "tushare.news.sina",
        "2026-06-03T20:19:24+00:00",
        "error_rows` is `0`",
        "blank_payload_rows` is `0`",
        "Page Evidence",
        "hasReadLandedCopy`: `true",
        "hasAutoUpdateCopy`: `false",
        "hasReservedIngestWriteRequest`: `false",
        "/ui/news/choice-events/latest",
        "POST /ui/news/tushare-npr/ingest",
        "POST /api/news/tushare-npr/ingest",
    )
    missing = [item for item in required if item not in text]
    if missing:
        return False, f"Missing evidence markers: {', '.join(missing)}"
    return True, "Refresh and page evidence markers are present."


def _check_post_enable_evidence_text(text: str) -> tuple[bool, str]:
    enablement = _line_value(text, "External timer enablement").lower()
    if "not enabled" in enablement:
        return False, "Go-live evidence still says not enabled."
    if enablement != "enabled":
        return False, "Go-live evidence does not confirm timer enablement."

    timer_evidence = _line_value(text, "Timer evidence in go-live bundle")
    if _has_placeholder(timer_evidence):
        return False, "Timer evidence in go-live bundle is pending."
    return True, "Go-live evidence confirms timer enablement."


def _check_page_artifacts(repo_root: Path) -> tuple[bool, str]:
    missing = [
        str(path)
        for path in (PAGE_SCREENSHOT_PATH, PAGE_JSON_PATH)
        if not (repo_root / path).exists()
    ]
    if missing:
        return False, f"Missing page artifacts: {', '.join(missing)}"
    return True, "Page screenshot and browser evidence JSON exist."


def _check_page_evidence_json(repo_root: Path) -> tuple[bool, str]:
    path = repo_root / PAGE_JSON_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, f"Page evidence JSON cannot be read: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"Page evidence JSON is invalid: {exc}"

    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, dict):
        return False, "Page evidence JSON is missing checks."

    failures: list[str] = []
    expected_checks = {
        "hasReadLandedCopy": True,
        "hasAutoUpdateCopy": False,
        "hasTushareCopy": True,
        "hasNewsItems": True,
        "hasReservedIngestWriteRequest": False,
    }
    for key, expected in expected_checks.items():
        if checks.get(key) is not expected:
            failures.append(f"{key}={checks.get(key)!r}")

    news_requests = payload.get("newsRequests")
    if not isinstance(news_requests, list) or not news_requests:
        failures.append("newsRequests missing")
    else:
        for request in news_requests:
            if not isinstance(request, dict):
                failures.append("newsRequests contains non-object entry")
                continue
            method = str(request.get("method", "")).upper()
            url = str(request.get("url", ""))
            if "/ui/news/choice-events/latest" not in url:
                failures.append(f"unexpected news request URL: {url}")
            if method != "GET":
                failures.append(f"unexpected news request method: {method or '<missing>'}")

    write_requests = payload.get("writeRequests")
    if not isinstance(write_requests, list):
        failures.append("writeRequests missing")
    elif write_requests:
        failures.append("reserved ingest write request captured")

    if failures:
        return False, "; ".join(failures)
    return True, "Page evidence JSON confirms landed-data read behavior and no reserved write request."


def _contains_disallowed_install_command(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        normalized = " ".join(stripped.lower().split())
        if not normalized or normalized.startswith("no `"):
            continue
        if any(command in normalized for command in DISALLOWED_INSTALL_COMMANDS):
            return True
    return False


def _check_timer_packet(text: str) -> tuple[bool, str]:
    passed, detail = _check_required_lines(
        text,
        (
            "Credential owner",
            "Schedule owner",
            "Page acceptance owner",
            "Rollback owner",
            "Timer host",
            "Repository root",
            "Python executable",
            "DuckDB path",
            "Log path",
            "Refresh window",
            "Write-window exclusion note",
            "Alert/log retention owner",
        ),
    )
    if not passed:
        return False, detail

    required_markers = (
        "Windows Task Scheduler command draft",
        "Cron command draft",
        "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina",
        "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run",
        "scripts/tushare_news_backup_timer_preflight.py",
        "preflight must return `pass` before enablement",
        "No `schtasks /Create` command is provided",
        "No `crontab` install command is provided",
        "POST /ui/news/tushare-npr/ingest",
        "POST /api/news/tushare-npr/ingest",
        "/ui/news/choice-events/latest",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        return False, f"Missing timer packet markers: {', '.join(missing)}"
    if _contains_disallowed_install_command(text):
        return False, "Install commands are not allowed in the timer enablement packet."
    return True, "Timer enablement packet is filled and keeps install commands out."


def _gate(name: str, passed: bool, detail: str) -> GateResult:
    return GateResult(name=name, outcome="pass" if passed else "blocked", detail=detail)


NEXT_ACTIONS: dict[str, dict[str, str]] = {
    "owners_filled": {
        "path": CHECKLIST_PATH.as_posix(),
        "action": "Fill Credential owner, Schedule owner, Page acceptance owner, Rollback owner, and Evidence location.",
    },
    "boundary_confirmation_filled": {
        "path": CHECKLIST_PATH.as_posix(),
        "action": "Mark each boundary row yes and attach evidence without secrets.",
    },
    "timer_enablement_packet_filled": {
        "path": TIMER_PACKET_PATH.as_posix(),
        "action": "Fill timer host, repository root, Python executable, log path, refresh window, write-window note, and packet owners.",
    },
    "refresh_and_page_evidence_attached": {
        "path": EVIDENCE_PATH.as_posix(),
        "action": "Attach refresh result markers and page evidence markers.",
    },
    "page_artifacts_exist": {
        "path": PAGE_JSON_PATH.as_posix(),
        "action": "Attach page screenshot and browser evidence JSON.",
    },
    "page_evidence_json_confirms_read_only_fallback": {
        "path": PAGE_JSON_PATH.as_posix(),
        "action": "Regenerate browser evidence JSON showing landed-data read behavior and no reserved write request.",
    },
    "page_acceptance_signoff_filled": {
        "path": CHECKLIST_PATH.as_posix(),
        "action": "Fill Page evidence owner sign-off.",
    },
    "enable_timer_decision_yes": {
        "path": CHECKLIST_PATH.as_posix(),
        "action": "Set Enable timer to yes only after pre-enable evidence is accepted.",
    },
    "timer_evidence_filled": {
        "path": CHECKLIST_PATH.as_posix(),
        "action": "Fill Enabled by, Enabled at, and Timer evidence after the first scheduled run.",
    },
    "post_enable_evidence_confirms_timer_enabled": {
        "path": EVIDENCE_PATH.as_posix(),
        "action": "Update External timer enablement to enabled and fill Timer evidence in go-live bundle.",
    },
}


def _next_actions(blocking_items: list[str]) -> list[dict[str, str]]:
    return [
        {"gate": name, **NEXT_ACTIONS[name]}
        for name in blocking_items
        if name in NEXT_ACTIONS
    ]


def build_timer_preflight_report(
    *,
    repo_root: str | Path = ROOT,
    stage: str = "post-enable",
) -> dict[str, object]:
    if stage not in PREFLIGHT_STAGES:
        raise ValueError(f"Unsupported preflight stage: {stage}")

    root = Path(repo_root)
    checklist_path = root / CHECKLIST_PATH
    timer_packet_path = root / TIMER_PACKET_PATH
    evidence_path = root / EVIDENCE_PATH
    checklist = _read_text(checklist_path)
    timer_packet = _read_text(timer_packet_path)
    evidence = _read_text(evidence_path)

    gates: list[GateResult] = []
    gates.append(_gate("checklist_exists", checklist_path.exists(), str(checklist_path)))
    gates.append(_gate("timer_enablement_packet_exists", timer_packet_path.exists(), str(timer_packet_path)))
    gates.append(_gate("evidence_exists", evidence_path.exists(), str(evidence_path)))

    passed, detail = _check_required_lines(
        checklist,
        (
            "Credential owner",
            "Schedule owner",
            "Page acceptance owner",
            "Rollback owner",
            "Evidence location",
        ),
    )
    gates.append(_gate("owners_filled", passed, detail))

    passed, detail = _check_boundary_confirmation(checklist)
    gates.append(_gate("boundary_confirmation_filled", passed, detail))

    passed, detail = _check_timer_packet(timer_packet)
    gates.append(_gate("timer_enablement_packet_filled", passed, detail))

    passed, detail = _check_evidence_text(evidence)
    gates.append(_gate("refresh_and_page_evidence_attached", passed, detail))

    passed, detail = _check_page_artifacts(root)
    gates.append(_gate("page_artifacts_exist", passed, detail))

    passed, detail = _check_page_evidence_json(root)
    gates.append(_gate("page_evidence_json_confirms_read_only_fallback", passed, detail))

    signoff = _line_value(checklist, "Page evidence owner sign-off")
    gates.append(
        _gate(
            "page_acceptance_signoff_filled",
            not _has_placeholder(signoff),
            "Page evidence owner sign-off is filled." if not _has_placeholder(signoff) else "Page evidence owner sign-off is pending.",
        )
    )

    enable_timer = _line_value(checklist, "Enable timer").lower()
    gates.append(
        _gate(
            "enable_timer_decision_yes",
            enable_timer == "yes",
            f"Enable timer decision is {enable_timer or 'missing'}.",
        )
    )

    if stage == "post-enable":
        passed, detail = _check_required_lines(
            checklist,
            (
                "Enabled by",
                "Enabled at",
                "Timer evidence",
            ),
        )
        gates.append(_gate("timer_evidence_filled", passed, detail))

        passed, detail = _check_post_enable_evidence_text(evidence)
        gates.append(_gate("post_enable_evidence_confirms_timer_enabled", passed, detail))

    blocking_items = [gate.name for gate in gates if gate.outcome != "pass"]
    summary = {
        "pass": sum(1 for gate in gates if gate.outcome == "pass"),
        "blocked": len(blocking_items),
    }
    return {
        "verdict": "pass" if not blocking_items else "blocked",
        "blocking_items": blocking_items,
        "next_actions": _next_actions(blocking_items),
        "summary": summary,
        "gates": [asdict(gate) for gate in gates],
        "stage": stage,
        "checklist_path": str(CHECKLIST_PATH),
        "timer_packet_path": str(TIMER_PACKET_PATH),
        "evidence_path": str(EVIDENCE_PATH),
    }


def build_timer_preflight_bundle(*, repo_root: str | Path = ROOT) -> dict[str, object]:
    reports = {
        stage: build_timer_preflight_report(repo_root=repo_root, stage=stage)
        for stage in PREFLIGHT_STAGES
    }
    blocking_stages = [
        stage for stage, report in reports.items() if report["verdict"] != "pass"
    ]
    return {
        "stage": "all",
        "verdict": "pass" if not blocking_stages else "blocked",
        "blocking_stages": blocking_stages,
        "reports": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether the Tushare news backup timer can be enabled.",
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--stage",
        choices=CLI_STAGES,
        default="post-enable",
        help="Use pre-enable before creating the external timer; use post-enable after the first scheduled run; use all to print both reports.",
    )
    args = parser.parse_args(argv)

    if args.stage == "all":
        report = build_timer_preflight_bundle(repo_root=args.repo_root)
    else:
        report = build_timer_preflight_report(repo_root=args.repo_root, stage=args.stage)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
