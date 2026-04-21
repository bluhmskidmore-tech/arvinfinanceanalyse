"""
Read-only audit: find inline patterns that may duplicate registered caliber rules.

Scans backend Python sources (per-rule roots) and writes Markdown + JSON reports
per rule. Does not modify source files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from backend.app.core_finance.calibers import get_caliber_rule

# Registration order is not guaranteed; KNOWN_RULES is lexicographically sorted rule_ids
# matching list_caliber_rules().
KNOWN_RULES: tuple[str, ...] = (
    "accounting_basis",
    "formal_scenario_gate",
    "fx_mid_conversion",
    "hat_mapping",
    "issuance_exclusion",
    "subject_514_516_517_merge",
)

# Subset of KNOWN_RULES that the CI gate enforces at zero unjustified violations.
# Informational-only rules stay in KNOWN_RULES (audit + registry) but are excluded here
# until their consumer migration batch lands (e.g. accounting_basis → W-accounting-basis-migration).
_GATE_ENFORCED_RULES: frozenset[str] = frozenset(
    {
        "accounting_basis",
        "formal_scenario_gate",
        "fx_mid_conversion",
        "hat_mapping",
        "issuance_exclusion",
        "subject_514_516_517_merge",
    }
)

_DEFAULT_SCANNED_DIR_RELS: tuple[str, ...] = (
    "backend/app/services",
    "backend/app/tasks",
    "backend/app/schemas",
    "backend/app/api",
)

_CORE_FINANCE_DIR = "backend/app/core_finance"

_SCANNED_DIR_RELS: tuple[str, ...] = _DEFAULT_SCANNED_DIR_RELS

_SNIPPET_MAX = 160

JUSTIFIED_LOOKBACK_LINES = 10
_JUSTIFIED_MARKER_RE = re.compile(
    r"Human:\s*caliber-([a-z0-9_]+)-justified", re.IGNORECASE
)


def _rule_marked_justified_on_line(line: str, rule_id: str) -> bool:
    rid = rule_id.casefold()
    for m in _JUSTIFIED_MARKER_RE.finditer(line):
        if m.group(1).casefold() == rid:
            return True
    return False


def _is_suppressed_by_justified_comment(
    rule_id: str, line_no: int, lines: list[str]
) -> bool:
    """True if this line or up to LOOKBACK physical lines above contain the marker.

    Markers may appear in ``#`` comments, same-line trailing comments, or
    docstrings (e.g. ``Human: caliber-<rule_id>-justified``).
    """
    if line_no < 1 or line_no > len(lines):
        return False
    if _rule_marked_justified_on_line(lines[line_no - 1], rule_id):
        return True
    for offset in range(1, JUSTIFIED_LOOKBACK_LINES + 1):
        idx = line_no - 1 - offset
        if idx < 0:
            break
        if _rule_marked_justified_on_line(lines[idx], rule_id):
            return True
    return False


class PatternDef(TypedDict):
    pattern_id: str
    regex: re.Pattern[str]
    confidence: str
    full_file: NotRequired[bool]


def _formal_scenario_gate_patterns() -> tuple[PatternDef, ...]:
    return (
        {
            "pattern_id": "basis_eq_scenario_str",
            "regex": re.compile(r"\bbasis\s*==\s*['\"]scenario['\"]"),
            "confidence": "high",
        },
        {
            "pattern_id": "basis_eq_formal_str",
            "regex": re.compile(r"\bbasis\s*==\s*['\"]formal['\"]"),
            "confidence": "high",
        },
        {
            "pattern_id": "is_formal_attr",
            "regex": re.compile(r"\bis_formal\b"),
            "confidence": "medium",
        },
        {
            "pattern_id": "formal_only_token",
            "regex": re.compile(r"\bformal_only\b"),
            "confidence": "medium",
        },
        {
            "pattern_id": "scenario_only_token",
            "regex": re.compile(r"\bscenario_only\b"),
            "confidence": "medium",
        },
        {
            "pattern_id": "if_formal_branch",
            "regex": re.compile(r"\bif\s+\w*formal\w*\s*[:=]"),
            "confidence": "low",
        },
    )


def _accounting_basis_patterns() -> tuple[PatternDef, ...]:
    """Flag inline AC/FVOCI/FVTPL comparisons and ``'AC' in x``-style probes.

    Deliberately omits a bare-literal sweep: it duplicates the equality patterns on
    the same physical line (e.g. ``return "AC"`` after ``if basis == "AC"``) and
    floods Literal declarations; migration tracking focuses on branching/filter
    comparisons instead.
    """
    _BASIS = r"(?:AC|FVOCI|FVTPL)"
    return (
        {
            "pattern_id": "accounting_basis_eq_right_literal",
            "regex": re.compile(rf"(?:==|!=)\s*['\"]{_BASIS}['\"]"),
            "confidence": "high",
        },
        {
            "pattern_id": "accounting_basis_eq_left_literal",
            "regex": re.compile(rf"['\"]{_BASIS}['\"]\s*(?:==|!=)"),
            "confidence": "high",
        },
        {
            "pattern_id": "accounting_basis_quoted_in_operand",
            "regex": re.compile(rf"['\"]{_BASIS}['\"]\s+in\b"),
            "confidence": "high",
        },
    )


PATTERNS: dict[str, tuple[PatternDef, ...]] = {
    "accounting_basis": _accounting_basis_patterns(),
    "subject_514_516_517_merge": (
        {
            "pattern_id": "prefix_tuple_inline",
            "regex": re.compile(
                r"['\"](?:514|516|517)['\"]\s*,\s*['\"](?:514|516|517)['\"]"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "account_startswith_pnl_prefix",
            "regex": re.compile(
                r"\.startswith\(\s*\(?\s*['\"](?:514|516|517)['\"]"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "bare_pnl_prefix_literal",
            "regex": re.compile(r"['\"](?:514|516|517)['\"](?!\s*[:=])"),
            "confidence": "medium",
        },
    ),
    "formal_scenario_gate": _formal_scenario_gate_patterns(),
    "issuance_exclusion": (
        {
            "pattern_id": "issuance_substring_zh",
            "regex": re.compile(
                r"['\"]发行类?['\"]\s+in\b|\bin\s+['\"]发行"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "issuance_eq_issued",
            "regex": re.compile(r"[=!]=\s*['\"]ISSUED['\"]"),
            "confidence": "high",
        },
        {
            "pattern_id": "liability_substring_zh",
            "regex": re.compile(r"['\"]负债['\"]\s+in\b"),
            "confidence": "medium",
        },
    ),
    "hat_mapping": (
        {
            "pattern_id": "hat_tuple_membership",
            "regex": re.compile(
                r"\bin\s+\(\s*['\"][HAT]['\"]\s*,\s*['\"][HAT]['\"]\s*,\s*['\"][HAT]['\"]\s*\)"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "accounting_class_substring",
            "regex": re.compile(
                r"['\"](?:AFS|HTM|TRADING)['\"]\s+in\b|['\"]可供出售['\"]|['\"]持有至到期['\"]|['\"]交易['\"]\s+in\b"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "legacy_derive_function_call",
            "regex": re.compile(r"\bderive_invest_type_std_value\s*\("),
            "confidence": "medium",
        },
        {
            "pattern_id": "last_char_hat_extract",
            "regex": re.compile(r"\[-1\]\s+in\s+\(\s*['\"][HAT]"),
            "confidence": "medium",
        },
    ),
    "fx_mid_conversion": (
        {
            "pattern_id": "inline_date_ternary",
            "regex": re.compile(
                r"business_date\s+if\s+.*\s+else\s+as_of_date|as_of_date\s+if\s+.*\s+else\s+business_date"
            ),
            "confidence": "high",
        },
        {
            "pattern_id": "manual_basis_date_branch",
            "regex": re.compile(
                r"if\s+basis\s*==\s*['\"]formal['\"][\s\S]{0,80}business_date",
                re.MULTILINE,
            ),
            "confidence": "medium",
            "full_file": True,
        },
    ),
}

# Backward-compat for W2 tests: formal_scenario_gate patterns only
_PATTERNS: tuple[PatternDef, ...] = PATTERNS["formal_scenario_gate"]

_MD_NAME = "caliber-violations-formal-scenario-gate-baseline.md"
_JSON_NAME = "caliber-violations-formal-scenario-gate-baseline.json"


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_files_to_skip(rule_id: str) -> set[str]:
    rule = get_caliber_rule(rule_id)
    rel = rule.canonical_module.replace(".", "/") + ".py"
    return {rel}


def _scanned_dir_relatives_for_rule(rule_id: str) -> tuple[str, ...]:
    base = _DEFAULT_SCANNED_DIR_RELS
    if rule_id in {
        "accounting_basis",
        "subject_514_516_517_merge",
        "hat_mapping",
        "fx_mid_conversion",
    }:
        return tuple([*base, _CORE_FINANCE_DIR])
    return base


def _should_skip_file(py_path: Path) -> bool:
    parts = py_path.parts
    if "__pycache__" in parts:
        return True
    if "tests" in parts:
        return True
    if "calibers" in parts:
        return True
    return False


def _iter_py_files(project_root: Path, rel_dir: str) -> Iterator[Path]:
    base = project_root / rel_dir
    if not base.is_dir():
        return
    yield from base.rglob("*.py")


def _collect_violations_for_file(
    project_root: Path,
    py_path: Path,
    patterns: tuple[PatternDef, ...],
    rule_id: str,
) -> tuple[list[dict[str, Any]], int]:
    rel = py_path.relative_to(project_root).as_posix()
    text = py_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    line_patterns = [p for p in patterns if not p.get("full_file")]
    file_patterns = [p for p in patterns if p.get("full_file")]
    out: list[dict[str, Any]] = []
    suppressed = 0

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        snippet = stripped[:_SNIPPET_MAX]
        for p in line_patterns:
            if p["regex"].search(line):
                if _is_suppressed_by_justified_comment(rule_id, line_no, lines):
                    suppressed += 1
                    continue
                out.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "snippet": snippet,
                        "pattern_id": p["pattern_id"],
                        "confidence": p["confidence"],
                    }
                )

    for p in file_patterns:
        for m in p["regex"].finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            line_text = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            snippet = line_text.strip()[:_SNIPPET_MAX]
            if _is_suppressed_by_justified_comment(rule_id, line_no, lines):
                suppressed += 1
                continue
            out.append(
                {
                    "file": rel,
                    "line": line_no,
                    "snippet": snippet,
                    "pattern_id": p["pattern_id"],
                    "confidence": p["confidence"],
                }
            )

    return out, suppressed


def count_by_confidence(violations: list[dict[str, Any]]) -> dict[str, int]:
    high = sum(1 for v in violations if v["confidence"] == "high")
    medium = sum(1 for v in violations if v["confidence"] == "medium")
    low = sum(1 for v in violations if v["confidence"] == "low")
    return {"high": high, "medium": medium, "low": low, "all": len(violations)}


_count_by_confidence = count_by_confidence


def scan_violations(
    rule_id: str = "formal_scenario_gate",
    project_root: Path | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Scan configured backend subtrees for inline patterns for one rule.

    Default ``rule_id`` keeps W2 call sites working without changes.

    Returns ``(violations, suppressed)`` where *violations* is sorted by
    (file, line, pattern_id, snippet) and *suppressed* counts regex hits
    skipped due to ``# Human: caliber-<rule_id>-justified`` markers.
    """
    if rule_id not in PATTERNS:
        raise ValueError(f"unknown rule_id: {rule_id!r}; expected one of {KNOWN_RULES!r}")
    root = project_root if project_root is not None else _repo_root_from_script()
    patterns = PATTERNS[rule_id]
    skip_rels = _canonical_files_to_skip(rule_id)
    raw: list[dict[str, Any]] = []
    suppressed_total = 0
    for rel in _scanned_dir_relatives_for_rule(rule_id):
        for py_path in _iter_py_files(root, rel):
            if _should_skip_file(py_path):
                continue
            rel_file = py_path.relative_to(root).as_posix()
            if rel_file in skip_rels:
                continue
            batch, sup = _collect_violations_for_file(root, py_path, patterns, rule_id)
            raw.extend(batch)
            suppressed_total += sup
    raw.sort(key=lambda v: (v["file"], v["line"], v["pattern_id"], v["snippet"]))
    return raw, suppressed_total


def scan_all_violations(
    project_root: Path | None = None,
) -> dict[str, tuple[list[dict[str, Any]], int]]:
    """Run :func:`scan_violations` for every :data:`KNOWN_RULES` entry."""
    return {
        rid: scan_violations(rule_id=rid, project_root=project_root)
        for rid in KNOWN_RULES
    }


def _markdown_report(
    *,
    rule_id: str,
    generated_at_utc: str,
    totals: dict[str, int],
    violations: list[dict[str, Any]],
    scanned_dirs: tuple[str, ...],
    suppressed: int,
) -> str:
    lines: list[str] = [
        f"# Caliber audit — {rule_id}",
        "",
        f"- Generated (UTC): `{generated_at_utc}`",
        f"- Scanned: `{', '.join(scanned_dirs)}`",
        f"- Totals: high={totals['high']}, medium={totals['medium']}, low={totals['low']}, all={totals['all']}",
        f"- Suppressed (Human justified): {suppressed}",
        "",
    ]
    for tier in ("high", "medium", "low"):
        tier_rows = [v for v in violations if v["confidence"] == tier]
        lines.append(f"## {tier}")
        lines.append("")
        lines.append("| file | line | snippet | pattern_id |")
        lines.append("| --- | ---: | --- | --- |")
        for v in tier_rows:
            esc_snippet = str(v["snippet"]).replace("|", "\\|")
            lines.append(
                f"| {v['file']} | {v['line']} | {esc_snippet} | {v['pattern_id']} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _baseline_paths(rule_id: str) -> tuple[str, str]:
    md = f"caliber-violations-{rule_id}-baseline.md"
    json_name = f"caliber-violations-{rule_id}-baseline.json"
    return md, json_name


def write_rule_baseline_outputs(
    *,
    rule_id: str,
    output_dir: Path,
    violations: list[dict[str, Any]],
    generated_at_utc: str,
    suppressed: int = 0,
) -> tuple[Path, Path]:
    """Write MD + JSON for one rule; used by :func:`main` and CLI."""
    output_dir.mkdir(parents=True, exist_ok=True)
    totals = count_by_confidence(violations)
    scanned_dirs = _scanned_dir_relatives_for_rule(rule_id)
    md_name, json_name = _baseline_paths(rule_id)
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "generated_at_utc": generated_at_utc,
        "scanned_dirs": list(scanned_dirs),
        "suppressed": suppressed,
        "totals": {
            "high": totals["high"],
            "medium": totals["medium"],
            "low": totals["low"],
            "all": totals["all"],
        },
        "violations": [
            {
                "file": v["file"],
                "line": v["line"],
                "snippet": v["snippet"],
                "pattern_id": v["pattern_id"],
                "confidence": v["confidence"],
            }
            for v in violations
        ],
    }
    md_path = output_dir / md_name
    json_path = output_dir / json_name
    md_path.write_text(
        _markdown_report(
            rule_id=rule_id,
            generated_at_utc=generated_at_utc,
            totals=totals,
            violations=violations,
            scanned_dirs=scanned_dirs,
            suppressed=suppressed,
        ),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return md_path, json_path


def main(
    *,
    output_dir: Path | None = None,
    project_root: Path | None = None,
) -> None:
    """
    Backward-compatible entry: scan **formal_scenario_gate** only and write
    legacy-named outputs (``_MD_NAME`` / ``_JSON_NAME``) for W2 tests.
    """
    root = project_root if project_root is not None else _repo_root_from_script()
    out = output_dir if output_dir is not None else Path(".omx/reports")
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()
    generated_at_utc = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    rule_id = "formal_scenario_gate"
    violations, suppressed = scan_violations(rule_id=rule_id, project_root=root)
    totals = count_by_confidence(violations)
    # W2 expects filenames _MD_NAME / _JSON_NAME at output_dir root
    out.mkdir(parents=True, exist_ok=True)
    scanned_dirs = _scanned_dir_relatives_for_rule(rule_id)
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "generated_at_utc": generated_at_utc,
        "scanned_dirs": list(scanned_dirs),
        "suppressed": suppressed,
        "totals": {
            "high": totals["high"],
            "medium": totals["medium"],
            "low": totals["low"],
            "all": totals["all"],
        },
        "violations": [
            {
                "file": v["file"],
                "line": v["line"],
                "snippet": v["snippet"],
                "pattern_id": v["pattern_id"],
                "confidence": v["confidence"],
            }
            for v in violations
        ],
    }
    md_path = out / _MD_NAME
    json_path = out / _JSON_NAME
    md_path.write_text(
        _markdown_report(
            rule_id=rule_id,
            generated_at_utc=generated_at_utc,
            totals=totals,
            violations=violations,
            scanned_dirs=scanned_dirs,
            suppressed=suppressed,
        ),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sup_txt = f" suppressed={suppressed}" if suppressed else ""
    print(
        f"[caliber-audit] {rule_id}: {totals['high']}H + {totals['medium']}M + {totals['low']}L "
        f"all={totals['all']}{sup_txt} -> {md_path.as_posix()}"
    )


def _parse_cli(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit inline caliber policy patterns.")
    p.add_argument(
        "--rule",
        metavar="RULE_ID",
        help=f"Scan only this rule (default: all {len(KNOWN_RULES)} rules).",
    )
    p.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".omx/reports",
        help="Report directory (default: .omx/reports)",
    )
    return p.parse_args(argv)


def cli_main(argv: list[str] | None = None) -> int:
    args = _parse_cli(list(argv or sys.argv[1:]))
    root = _repo_root_from_script()
    out = Path(args.output_dir)
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()
    generated_at_utc = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    rules: tuple[str, ...]
    if args.rule:
        if args.rule not in PATTERNS:
            print(f"Unknown rule: {args.rule!r}", file=sys.stderr)
            return 2
        rules = (args.rule,)
    else:
        rules = KNOWN_RULES

    for rid in rules:
        violations, suppressed = scan_violations(rule_id=rid, project_root=root)
        totals = count_by_confidence(violations)
        md_path, _jp = write_rule_baseline_outputs(
            rule_id=rid,
            output_dir=out,
            violations=violations,
            generated_at_utc=generated_at_utc,
            suppressed=suppressed,
        )
        sup_txt = f" suppressed={suppressed}" if suppressed else ""
        print(
            f"[caliber-audit] {rid}: {totals['high']}H + {totals['medium']}M + {totals['low']}L "
            f"all={totals['all']}{sup_txt} -> {md_path.as_posix()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
