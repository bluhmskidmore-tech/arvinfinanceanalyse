from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE  # noqa: E402
from scripts.portfolio_home_closure_scorecard import build_scorecard  # noqa: E402
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)


ARTIFACTS = [
    {
        "name": "evidence_snapshot",
        "path": Path("portfolio") / "portfolio-home-evidence-snapshot.json",
        "kind": "json",
    },
    {
        "name": "business_owner_approval_packet",
        "path": Path("portfolio") / "portfolio-home-business-owner-approval-packet.json",
        "kind": "json",
    },
    {
        "name": "owner_action_packet",
        "path": Path("portfolio") / "portfolio-home-owner-action-packet.json",
        "kind": "json",
    },
    {
        "name": "owner_input_needed_summary",
        "path": Path("portfolio") / "portfolio-home-owner-input-needed-summary.json",
        "kind": "json",
    },
    {
        "name": "owner_handoff_packet",
        "path": Path("portfolio") / "portfolio-home-owner-handoff-packet.md",
        "kind": "current_blockers_markdown",
    },
    {
        "name": "option_b_execution_note",
        "path": Path("portfolio") / "portfolio-home-option-b-execution-note.md",
        "kind": "current_blockers_markdown",
    },
    {
        "name": "full_closure_signoff_packet",
        "path": Path("portfolio") / "portfolio-home-full-closure-sign-off-packet.md",
        "kind": "scorecard_line_markdown",
    },
    {
        "name": "readiness_gate_audit",
        "path": Path("audits") / "2026-06-05-portfolio-readiness-gate-audit.md",
        "kind": "authoritative_blockers_markdown",
    },
]


def _resolved_docs_root(docs_root: Path) -> Path:
    path = Path(docs_root)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _unique_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _json_score_blockers(path: Path) -> list[str] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or "score_blockers" not in payload:
        return None
    return _unique_strings(payload.get("score_blockers"))


def _markdown_section_score_blockers(text: str) -> list[str] | None:
    lines = text.splitlines()
    in_section = False
    blockers: list[str] = []
    for line in lines:
        if line.strip() == "## Current Blockers":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = re.fullmatch(r"- `([^`]+)`", line.strip())
        if match:
            blockers.append(match.group(1))
    return blockers if in_section else None


def _scorecard_line_score_blockers(text: str) -> list[str] | None:
    prefix = "- Closure scorecard blockers: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return re.findall(r"`([^`]+)`", line)
    return None


def _authoritative_blockers_score_blockers(text: str) -> list[str] | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "Authoritative score blockers from the scorecard:":
            continue
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                return re.findall(r"`([^`]+)`", stripped)
            break
    return None


def _markdown_score_blockers(path: Path, kind: str) -> list[str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    if kind == "current_blockers_markdown":
        return _markdown_section_score_blockers(text)
    if kind == "scorecard_line_markdown":
        return _scorecard_line_score_blockers(text)
    if kind == "authoritative_blockers_markdown":
        return _authoritative_blockers_score_blockers(text)
    raise ValueError(f"Unsupported portfolio-home score blocker artifact kind: {kind}")


def _compare_artifact(
    *,
    name: str,
    path: Path,
    kind: str,
    expected: list[str],
) -> dict[str, object]:
    if kind == "json":
        actual = _json_score_blockers(path)
    else:
        actual = _markdown_score_blockers(path, kind)
    if actual is None:
        return {
            "name": name,
            "path": str(path),
            "kind": kind,
            "status": "blocked",
            "blockers": [f"{name}_score_blockers_missing"],
            "score_blockers": [],
            "missing_blockers": expected,
            "unexpected_blockers": [],
        }
    missing = [blocker for blocker in expected if blocker not in actual]
    unexpected = [blocker for blocker in actual if blocker not in expected]
    ordering_mismatch = not missing and not unexpected and actual != expected
    blockers = []
    if missing or unexpected or ordering_mismatch:
        blockers.append(f"{name}_score_blockers_mismatch")
    return {
        "name": name,
        "path": str(path),
        "kind": kind,
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
        "score_blockers": actual,
        "missing_blockers": missing,
        "unexpected_blockers": unexpected,
        "ordering_mismatch": ordering_mismatch,
    }


def build_report(
    *,
    docs_root: Path = ROOT / "docs",
    duckdb_path: Path = DEFAULT_DUCKDB,
    report_date: str = DEFAULT_REPORT_DATE,
    template_path: Path = DEFAULT_TEMPLATE,
    limit: int | None = None,
) -> dict[str, object]:
    if limit is not None:
        limit = validate_non_negative_portfolio_limit(
            limit,
            label="score blocker consistency limit",
        )
    resolved_docs_root = _resolved_docs_root(docs_root)
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=3,
        docs_root=resolved_docs_root,
    )
    expected = _unique_strings(scorecard.get("score_blockers"))
    selected_artifacts = ARTIFACTS[:limit] if limit is not None else ARTIFACTS
    artifacts = [
        _compare_artifact(
            name=str(artifact["name"]),
            path=resolved_docs_root / artifact["path"],
            kind=str(artifact["kind"]),
            expected=expected,
        )
        for artifact in selected_artifacts
    ]
    blockers = [
        blocker
        for artifact in artifacts
        for blocker in artifact.get("blockers", [])
    ]
    return {
        "check_kind": "portfolio_home_score_blocker_consistency",
        "page_id": scorecard.get("page_id"),
        "page_slug": scorecard.get("page_slug"),
        "report_date": scorecard.get("report_date"),
        "docs_root": str(resolved_docs_root),
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
        "scorecard_status": scorecard.get("score_status"),
        "scorecard_full_score_ready": scorecard.get("full_score_ready"),
        "expected_score_blockers": expected,
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home score blocker consistency across evidence packets.",
    )
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="score blocker consistency limit",
        ),
        default=None,
    )
    parser.add_argument(
        "--require-consistent",
        action="store_true",
        help="Return non-zero unless all evidence packets carry the same score blockers.",
    )
    args = parser.parse_args(argv)

    report = build_report(
        docs_root=Path(args.docs_root),
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_consistent and report["status"] != "consistent":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
