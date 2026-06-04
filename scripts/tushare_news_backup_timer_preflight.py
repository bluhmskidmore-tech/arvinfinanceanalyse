"""Read-only preflight before enabling the Tushare news backup timer."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
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
OUTPUT_FORMATS = ("json", "markdown", "ops-gap")
POST_ENABLE_ONLY_GATES = (
    "timer_evidence_filled",
    "post_enable_evidence_confirms_timer_enabled",
)


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
        "action": "Set Enable timer to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer.",
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


def _filter_next_actions(
    next_actions: list[dict[str, str]],
    *,
    allowed_gates: set[str] | None = None,
) -> list[dict[str, str]]:
    if allowed_gates is None:
        return list(next_actions)
    return [action for action in next_actions if action["gate"] in allowed_gates]


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
        "ops_gap": {
            "immediate_stage": "pre-enable",
            "deferred_stage": "post-enable",
            "deferred_until": "pre-enable pass and first scheduled run finishes",
            "ready_to_create_timer": reports["pre-enable"]["verdict"] == "pass",
            "immediate_next_actions": _filter_next_actions(
                reports["pre-enable"]["next_actions"],
            ),
            "deferred_post_enable_next_actions": _filter_next_actions(
                reports["post-enable"]["next_actions"],
                allowed_gates=set(POST_ENABLE_ONLY_GATES),
            ),
        },
    }


def _format_blocking_stages(stages: list[str]) -> str:
    if not stages:
        return "`none`"
    return ", ".join(f"`{stage}`" for stage in stages)


def _format_summary(report: dict[str, object]) -> str:
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise TypeError("preflight summary must be a dictionary")
    return f"`{summary['pass']} pass / {summary['blocked']} blocked`"


def _passed_gate_names(reports: dict[str, object]) -> list[str]:
    stage_reports = [
        report for report in reports.values() if isinstance(report, dict)
    ]
    if not stage_reports:
        return []
    passed_sets = []
    for report in stage_reports:
        gates = report.get("gates", [])
        if not isinstance(gates, list):
            continue
        passed_sets.append(
            {
                gate["name"]
                for gate in gates
                if isinstance(gate, dict) and gate.get("outcome") == "pass"
            }
        )
    if not passed_sets:
        return []
    common = set.intersection(*passed_sets)
    first_stage_order = [
        gate["name"]
        for gate in stage_reports[0].get("gates", [])
        if isinstance(gate, dict) and gate.get("name") in common
    ]
    return first_stage_order


def _stage_title(stage: str) -> str:
    return stage.replace("-", " ").title().replace(" ", "-")


def _stage_reports_for_ops_gap(report: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    if report.get("stage") == "all":
        reports = report["reports"]
        if not isinstance(reports, dict):
            raise TypeError("all-stage preflight report must contain reports")
        return [
            (stage, reports[stage])
            for stage in PREFLIGHT_STAGES
            if isinstance(reports.get(stage), dict)
        ]
    return [(str(report["stage"]), report)]


def _format_ops_gap_blocking_items(report: dict[str, object]) -> list[str]:
    rows = ["## Current Blocking Items", ""]
    for stage, stage_report in _stage_reports_for_ops_gap(report):
        rows.extend((f"### {_stage_title(stage)}", ""))
        blocking_items = stage_report["blocking_items"]
        if blocking_items:
            rows.extend(f"- `{item}`" for item in blocking_items)
        else:
            rows.append("- `none`")
        rows.append("")
    return rows


def _format_ops_gap_summary(report: dict[str, object]) -> list[str]:
    if report.get("stage") != "all":
        return []
    reports = report["reports"]
    if not isinstance(reports, dict):
        raise TypeError("all-stage preflight report must contain reports")
    pre_enable = reports["pre-enable"]
    post_enable = reports["post-enable"]
    return [
        "Blocking stages: " + _format_blocking_stages(report["blocking_stages"]),
        "",
        "Pre-enable summary: " + _format_summary(pre_enable),
        "",
        "Post-enable summary: " + _format_summary(post_enable),
        "",
    ]


def _format_ops_gap_next_actions(report: dict[str, object]) -> list[str]:
    if report.get("stage") == "all":
        ops_gap = report["ops_gap"]
        if not isinstance(ops_gap, dict):
            raise TypeError("all-stage preflight report must contain ops_gap")
        rows = []
        for title, key in (
            ("## Immediate `next_actions`", "immediate_next_actions"),
            ("## Deferred Post-Enable `next_actions`", "deferred_post_enable_next_actions"),
        ):
            rows.extend((title, "", "| Gate | Path | Action |", "| --- | --- | --- |"))
            next_actions = ops_gap[key]
            if next_actions:
                rows.extend(
                    f"| `{action['gate']}` | `{action['path']}` | {action['action']} |"
                    for action in next_actions
                )
            else:
                rows.append("| `none` | `none` | No action required. |")
            rows.append("")
        return rows

    rows = [
        "## Current `next_actions`",
        "",
        "| Gate | Path | Action |",
        "| --- | --- | --- |",
    ]
    next_actions = report["next_actions"]
    if next_actions:
        rows.extend(
            f"| `{action['gate']}` | `{action['path']}` | {action['action']} |"
            for action in next_actions
        )
    else:
        rows.append("| `none` | `none` | No action required. |")
    rows.append("")
    return rows


def _format_ops_gap_activation_sequence(report: dict[str, object]) -> list[str]:
    rows = [
        "## Activation Sequence",
        "",
        "Immediate stage: `pre-enable`",
        "",
        "Post-enable inputs remain deferred until `pre-enable` returns `pass` and the first scheduled run finishes.",
        "",
    ]
    if report.get("stage") == "all":
        rows.extend(
            (
                "Do not create the external timer while `pre-enable` is blocked.",
                "After `pre-enable` passes, create the external timer outside this packet and collect first-run evidence.",
                "",
            )
        )
    return rows


def render_timer_preflight_markdown(report: dict[str, object]) -> str:
    if report.get("stage") != "all":
        return "\n".join(
            (
                "# Tushare News Backup Timer Preflight Status",
                "",
                f"Current verdict: `{report['verdict']}`",
                "",
                *(
                    (
                        f"Ready to create timer: `{str(report['verdict'] == 'pass').lower()}`",
                        "",
                    )
                    if report.get("stage") == "pre-enable"
                    else ()
                ),
                "Current blocking items:",
                "",
                *[f"- `{item}`" for item in report["blocking_items"]],
                "",
                "Current `next_actions`:",
                "",
                "| Gate | Path | Action |",
                "| --- | --- | --- |",
                *[
                    f"| `{action['gate']}` | `{action['path']}` | {action['action']} |"
                    for action in report["next_actions"]
                ],
                "",
            )
        )

    reports = report["reports"]
    if not isinstance(reports, dict):
        raise TypeError("all-stage preflight report must contain reports")
    pre_enable = reports["pre-enable"]
    post_enable = reports["post-enable"]
    rows = [
        "# Tushare News Backup Timer Preflight Status",
        "",
        f"Status timestamp: {date.today().isoformat()}",
        "",
        "External timer is not enabled. Do not enable the timer until the `pre-enable` preflight returns `pass`.",
        "",
        "Combined verdict: `" + str(report["verdict"]) + "`",
        "",
        "Blocking stages: " + _format_blocking_stages(report["blocking_stages"]),
        "",
        "Pre-enable summary: " + _format_summary(pre_enable),
        "",
        "Post-enable summary: " + _format_summary(post_enable),
        "",
        "Machine-readable JSON `ops_gap`:",
        "",
        "- `ops_gap.ready_to_create_timer` is true only after `pre-enable` passes.",
        "- `ops_gap.immediate_next_actions` contains the current `pre-enable` items.",
        "- `ops_gap.deferred_post_enable_next_actions` contains only first-scheduled-run evidence items.",
        "- `ops_gap.deferred_until` records when deferred items become actionable.",
        "",
        f"Ready to create timer: `{str(report['ops_gap']['ready_to_create_timer']).lower()}`",
        "",
        "## Operator Fill Order",
        "",
        "1. Fill owner fields first in `docs/templates/tushare_news_backup_refresh_go_live_checklist.md`.",
        "2. Confirm boundary rows with evidence, without exposing secrets.",
        "3. Complete the timer enablement packet in `docs/templates/tushare_news_backup_timer_enablement_packet.md`.",
        "4. Record page acceptance sign-off for the attached homepage evidence.",
        "5. Set Enable timer to yes after pre-enable evidence is accepted, then rerun `--stage pre-enable` before creating the external timer.",
        "6. After the first scheduled run, attach timer evidence and rerun `--stage post-enable`.",
        "",
        *_format_ops_gap_activation_sequence(report),
    ]

    for stage in PREFLIGHT_STAGES:
        stage_report = reports[stage]
        rows.extend(
            (
                f"## {stage.title()} Status",
                "",
                f"Current verdict: `{stage_report['verdict']}`",
                "",
                "Current blocking items:",
                "",
            )
        )
        blocking_items = stage_report["blocking_items"]
        if blocking_items:
            rows.extend(f"- `{item}`" for item in blocking_items)
        else:
            rows.append("- `none`")
        if stage == "post-enable":
            action_heading = "Additional post-enable `next_actions`:"
            next_actions = report["ops_gap"]["deferred_post_enable_next_actions"]
        else:
            action_heading = "Current `next_actions`:"
            next_actions = stage_report["next_actions"]
        rows.extend(("", action_heading, "", "| Gate | Path | Action |", "| --- | --- | --- |"))
        if next_actions:
            rows.extend(
                f"| `{action['gate']}` | `{action['path']}` | {action['action']} |"
                for action in next_actions
            )
        else:
            rows.append("| `none` | `none` | No action required. |")
        rows.append("")
    rows.extend(
        (
            "## Already Verified Evidence Gates",
            "",
        )
    )
    passed_gates = _passed_gate_names(reports)
    if passed_gates:
        rows.extend(f"- `{gate}`" for gate in passed_gates)
    else:
        rows.append("- `none`")
    rows.extend(
        (
            "",
            "Reserved routes remain reserved:",
            "",
            "- `POST /ui/news/tushare-npr/ingest`",
            "- `POST /api/news/tushare-npr/ingest`",
            "",
            "Homepage read path remains `/ui/news/choice-events/latest`.",
            "",
        )
    )
    return "\n".join(rows)


def render_timer_ops_gap_markdown(report: dict[str, object]) -> str:
    return "\n".join(
        (
            "# Tushare News Backup Timer Ops Gap Packet",
            "",
            f"Status timestamp: {date.today().isoformat()}",
            "",
            "This packet does not enable the timer. It converts the current blocked preflight gates into external operations inputs to collect before enablement.",
            "",
            "Do not run a real Tushare refresh from this packet.",
            "Do not open reserved ingest routes.",
            "External timer remains disabled.",
            "",
            f"Current verdict: `{report['verdict']}`",
            "",
            *_format_ops_gap_summary(report),
            f"Ready to create timer: `{str(report['ops_gap']['ready_to_create_timer']).lower()}`",
            "",
            *_format_ops_gap_activation_sequence(report),
            *_format_ops_gap_blocking_items(report),
            *_format_ops_gap_next_actions(report),
            "## Required External Inputs",
            "",
            "Fill these before rerunning `pre-enable`:",
            "",
            "| Input | Target document | Evidence to attach |",
            "| --- | --- | --- |",
            "| Credential owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for `MOSS_TUSHARE_TOKEN`; no token value. |",
            "| Schedule owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person responsible for the external timer. |",
            "| Page acceptance owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person accepting homepage fallback evidence. |",
            "| Rollback owner | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who can disable the timer. |",
            "| Timer host | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Hostname or scheduler host identifier. |",
            "| Repository root | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute repo path used as job working directory. |",
            "| Python executable | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute Python path on the timer host. |",
            "| Log path | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Absolute scheduler log path. |",
            "| Refresh window | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Local time and timezone. |",
            "| Write-window exclusion note | `docs/templates/tushare_news_backup_timer_enablement_packet.md` | Evidence that the job avoids other DuckDB writers. |",
            "| Page evidence owner sign-off | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Sign-off for the attached homepage screenshot and browser JSON. |",
            "| Enable timer decision | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Set to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer. |",
            "",
            "Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` after filling pre-enable inputs.",
            "Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable --format markdown` to read the operator go/no-go status.",
            "",
            "## Post-Enable Inputs",
            "",
            "Fill these only after the first scheduled run:",
            "",
            "| Input | Target document | Evidence to attach |",
            "| --- | --- | --- |",
            "| Enabled by | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Team/person who enabled the external timer. |",
            "| Enabled at | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Timestamp with timezone. |",
            "| Timer evidence | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Scheduler screenshot, job config excerpt, or first scheduled-run log without secrets. |",
            "| Timer evidence in go-live bundle | `docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md` | Same timer evidence linked from the go-live bundle. |",
            "",
            "Run `python scripts/tushare_news_backup_timer_preflight.py --stage post-enable` after the first scheduled run.",
            "",
            "## Boundaries",
            "",
            "- Homepage read path remains `/ui/news/choice-events/latest`.",
            "- `POST /ui/news/tushare-npr/ingest` remains reserved.",
            "- `POST /api/news/tushare-npr/ingest` remains reserved.",
            "- Do not add homepage auto-ingest behavior.",
            "- Do not change database schema, auth/permission framework, scheduler base, cache base, or global SDK wrappers.",
            "",
        )
    )


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
    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS,
        default="json",
        help="Output JSON, status Markdown, or operations gap Markdown.",
    )
    args = parser.parse_args(argv)

    if args.stage == "all":
        report = build_timer_preflight_bundle(repo_root=args.repo_root)
    else:
        report = build_timer_preflight_report(repo_root=args.repo_root, stage=args.stage)
    if args.format == "ops-gap":
        print(render_timer_ops_gap_markdown(report))
    elif args.format == "markdown":
        print(render_timer_preflight_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
