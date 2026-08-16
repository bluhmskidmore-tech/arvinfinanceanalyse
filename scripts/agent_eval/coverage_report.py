"""Gate-probe coverage and archived pass-rate reporting for the agent eval harness.

The north-star number this tool tracks is gate probe coverage: the share of
declared ``business_gates`` / ``page_gates`` that have an executable probe
command in ``gate_probes``. Unprobed gates fail closed during scoring, so the
uncovered list *is* the harness backlog; the report groups every uncovered
gate by its registered ``gate_probe_gaps`` reason to keep that backlog
actionable, and summarizes the probe command mix (pytest / vitest filters).

When ``--archives-root`` is provided the report also aggregates evaluation
archives (``replay.py`` / ``pr_replay.py`` output) into per-task pass rates.
A run directory is any directory containing ``scorecard.json`` or
``result.json``; a run whose ``result.json`` exists but whose scorecard is
missing or unreadable counts as ``void`` (the measurement rejected itself by
design, e.g. the change touched the scoring harness).

This is a reporting tool, not a gate: malformed task or archive files are
recorded as warnings and never abort the report (fail-open), and the process
always exits 0.

Usage:

    python scripts/agent_eval/coverage_report.py
    python scripts/agent_eval/coverage_report.py --archives-root .codex-tmp/agent-eval --format json --out report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_TASKS_DIR = Path("scripts") / "agent_eval" / "tasks"

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)
_UNREGISTERED_GAP_LABEL = "（未登记缺口原因）"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report(
        tasks_dir=Path(args.tasks_dir),
        archives_root=Path(args.archives_root) if args.archives_root else None,
    )
    if args.format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = render_markdown(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"coverage report written: {out_path}", file=sys.stderr)
    else:
        _emit(rendered)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report gate-probe coverage for agent eval tasks and, optionally, "
            "pass rates aggregated from evaluation archives."
        )
    )
    parser.add_argument(
        "--tasks-dir",
        default=str(DEFAULT_TASKS_DIR),
        help=f"Task definitions directory (default: {DEFAULT_TASKS_DIR.as_posix()}).",
    )
    parser.add_argument(
        "--archives-root",
        help=(
            "Optional root scanned recursively for scorecard.json/result.json "
            "archives (e.g. .codex-tmp/agent-eval); enables the pass-rate section."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="Output format: md for a paste-ready Markdown report, json for trend collection (default: md).",
    )
    parser.add_argument(
        "--out",
        help="Optional output file path (default: print to stdout).",
    )
    return parser.parse_args(argv)


def build_report(*, tasks_dir: Path, archives_root: Path | None = None) -> dict[str, Any]:
    """Assemble the full report payload; shared by the md and json renderers."""

    warnings: list[str] = []
    coverage = _build_coverage(tasks_dir, warnings)
    pass_rate = _build_pass_rate(archives_root, warnings)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks_dir": tasks_dir.as_posix(),
        "archives_root": archives_root.as_posix() if archives_root is not None else None,
        "coverage": coverage,
        "pass_rate": pass_rate,
        "warnings": warnings,
    }


# --- coverage -------------------------------------------------------------


def _build_coverage(tasks_dir: Path, warnings: list[str]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    gap_entries: list[dict[str, Any]] = []
    kind_buckets: dict[str, dict[str, Any]] = {}

    for path, payload in _load_task_files(tasks_dir, warnings):
        task_id = payload.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = path.stem
            warnings.append(f"任务 {path.name} 缺少字符串 id，改用文件名 '{task_id}'")

        declared = _declared_gates(payload, path.name, warnings)
        probes = _string_map(payload, "gate_probes", path.name, warnings)
        gaps = _string_map(payload, "gate_probe_gaps", path.name, warnings)

        undeclared = sorted(set(probes) - set(declared))
        if undeclared:
            warnings.append(
                f"任务 {path.name} 的 gate_probes 引用了未声明的 gate（不计入覆盖率）："
                + ", ".join(undeclared)
            )

        probed = [gate for gate in declared if gate in probes]
        unprobed = [gate for gate in declared if gate not in probes]

        for gate in unprobed:
            gap_entries.append({"task_id": task_id, "gate": gate, "reason": gaps.get(gate)})
        for gate in probed:
            kind, target = classify_probe_command(probes[gate])
            bucket = kind_buckets.setdefault(kind, {"count": 0, "targets": set()})
            bucket["count"] += 1
            if target:
                bucket["targets"].add(target)

        tasks.append(
            {
                "task_id": task_id,
                "declared_gates": len(declared),
                "probed_gates": len(probed),
                "unprobed_gates": len(unprobed),
                "coverage_pct": _pct(len(probed), len(declared)),
                "unprobed": [{"gate": gate, "reason": gaps.get(gate)} for gate in unprobed],
            }
        )

    tasks.sort(key=lambda item: item["task_id"])
    declared_total = sum(item["declared_gates"] for item in tasks)
    probed_total = sum(item["probed_gates"] for item in tasks)

    probe_kinds = [
        {"kind": kind, "count": bucket["count"], "targets": sorted(bucket["targets"])}
        for kind, bucket in kind_buckets.items()
    ]
    probe_kinds.sort(key=lambda item: (-item["count"], item["kind"]))

    return {
        "task_count": len(tasks),
        "tasks": tasks,
        "totals": {
            "declared_gates": declared_total,
            "probed_gates": probed_total,
            "unprobed_gates": declared_total - probed_total,
            "coverage_pct": _pct(probed_total, declared_total),
        },
        "gap_groups": _group_gaps(gap_entries),
        "probe_kinds": probe_kinds,
    }


def _load_task_files(tasks_dir: Path, warnings: list[str]) -> list[tuple[Path, dict[str, Any]]]:
    if not tasks_dir.is_dir():
        warnings.append(f"任务目录不存在：{tasks_dir.as_posix()}")
        return []
    entries: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            warnings.append(f"任务文件解析失败，已跳过：{path.name}（{error}）")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"任务文件不是 JSON 对象，已跳过：{path.name}")
            continue
        entries.append((path, payload))
    return entries


def _declared_gates(task: dict[str, Any], file_name: str, warnings: list[str]) -> list[str]:
    gates: list[str] = []
    for field in ("business_gates", "page_gates"):
        for gate in _string_items(task.get(field), field, file_name, warnings):
            if gate not in gates:
                gates.append(gate)
    return gates


def _string_items(value: Any, field: str, file_name: str, warnings: list[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append(f"任务 {file_name} 字段 {field} 不是列表，按空处理")
        return []
    items = [item for item in value if isinstance(item, str)]
    if len(items) != len(value):
        warnings.append(f"任务 {file_name} 字段 {field} 含非字符串项，已忽略")
    return items


def _string_map(task: dict[str, Any], field: str, file_name: str, warnings: list[str]) -> dict[str, str]:
    value = task.get(field)
    if value is None:
        return {}
    if not isinstance(value, dict):
        warnings.append(f"任务 {file_name} 字段 {field} 不是对象，按空处理")
        return {}
    items = {
        key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, str)
    }
    if len(items) != len(value):
        warnings.append(f"任务 {file_name} 字段 {field} 含非字符串键值，已忽略")
    return items


def _group_gaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str | None, list[dict[str, str]]] = {}
    for entry in entries:
        groups.setdefault(entry["reason"], []).append(
            {"task_id": entry["task_id"], "gate": entry["gate"]}
        )
    ordered = []
    for reason, members in groups.items():
        members.sort(key=lambda item: (item["task_id"], item["gate"]))
        ordered.append({"reason": reason, "count": len(members), "entries": members})
    ordered.sort(key=lambda group: (-group["count"], group["reason"] is None, group["reason"] or ""))
    return ordered


def classify_probe_command(command: str) -> tuple[str, str | None]:
    """Classify a gate probe command into (kind, filter/target).

    Kinds: ``pytest``, ``vitest`` (``npm --prefix frontend run test``),
    ``npm:<script>`` for other frontend npm scripts, ``other`` for anything
    outside the trusted-runner whitelist.
    """

    tokens = command.strip().split()
    if len(tokens) >= 3 and tokens[:3] == ["python", "-m", "pytest"]:
        targets = [token for token in tokens[3:] if not token.startswith("-")]
        return "pytest", " ".join(targets) or None
    if len(tokens) >= 5 and tokens[:4] == ["npm", "--prefix", "frontend", "run"]:
        script = tokens[4]
        args = tokens[5:]
        if args and args[0] == "--":
            args = args[1:]
        filters = [token for token in args if not token.startswith("-")]
        kind = "vitest" if script == "test" else f"npm:{script}"
        return kind, " ".join(filters) or None
    return "other", None


# --- pass rate ------------------------------------------------------------


def _build_pass_rate(archives_root: Path | None, warnings: list[str]) -> dict[str, Any]:
    base = {
        "available": archives_root is not None,
        "runs_found": 0,
        "tasks": [],
        "totals": {"runs": 0, "pass": 0, "fail": 0, "void": 0},
    }
    if archives_root is None:
        return base
    if not archives_root.is_dir():
        warnings.append(f"归档目录不存在：{archives_root.as_posix()}")
        return base

    run_dirs: dict[Path, dict[str, Path]] = {}
    for file_name in ("scorecard.json", "result.json"):
        for path in archives_root.rglob(file_name):
            run_dirs.setdefault(path.parent, {})[file_name] = path

    stats: dict[str, dict[str, Any]] = {}
    runs_found = 0
    for run_dir in sorted(run_dirs):
        files = run_dirs[run_dir]
        scorecard = _read_json_object(files.get("scorecard.json"), archives_root, warnings)
        result = _read_json_object(files.get("result.json"), archives_root, warnings)
        if scorecard is None and result is None:
            warnings.append(
                f"归档 {_relative_to(run_dir, archives_root)} 无可读的 scorecard/result，已跳过"
            )
            continue

        if scorecard is not None:
            status = str(scorecard.get("status", "")).strip().lower()
            verdict = "pass" if status == "pass" else "fail"
        else:
            verdict = "void"

        task_id = _archive_task_id(scorecard, result)
        display_ts, sort_key = _archive_timestamp(result, files)

        entry = stats.setdefault(
            task_id,
            {
                "task_id": task_id,
                "runs": 0,
                "pass": 0,
                "fail": 0,
                "void": 0,
                "latest_timestamp": None,
                "latest_status": None,
                "_latest_key": _EPOCH,
            },
        )
        entry["runs"] += 1
        entry[verdict] += 1
        if sort_key >= entry["_latest_key"]:
            entry["_latest_key"] = sort_key
            entry["latest_timestamp"] = display_ts
            entry["latest_status"] = verdict
        runs_found += 1

    tasks = []
    for task_id in sorted(stats):
        entry = dict(stats[task_id])
        entry.pop("_latest_key")
        tasks.append(entry)

    base["runs_found"] = runs_found
    base["tasks"] = tasks
    base["totals"] = {
        "runs": sum(item["runs"] for item in tasks),
        "pass": sum(item["pass"] for item in tasks),
        "fail": sum(item["fail"] for item in tasks),
        "void": sum(item["void"] for item in tasks),
    }
    return base


def _read_json_object(
    path: Path | None, root: Path, warnings: list[str]
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        warnings.append(f"归档文件解析失败，按缺失处理：{_relative_to(path, root)}（{error}）")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"归档文件不是 JSON 对象，按缺失处理：{_relative_to(path, root)}")
        return None
    return payload


def _archive_task_id(scorecard: dict[str, Any] | None, result: dict[str, Any] | None) -> str:
    if scorecard is not None:
        value = scorecard.get("task_id")
        if isinstance(value, str) and value.strip():
            return value
    if result is not None:
        measurement = result.get("measurement")
        if isinstance(measurement, dict):
            integrity = measurement.get("integrity")
            if isinstance(integrity, dict):
                value = integrity.get("task_id")
                if isinstance(value, str) and value.strip():
                    return value
    return "(unknown)"


def _archive_timestamp(
    result: dict[str, Any] | None, files: dict[str, Path]
) -> tuple[str | None, datetime]:
    if result is not None:
        measurement = result.get("measurement")
        if isinstance(measurement, dict):
            raw = measurement.get("collected_at")
            if isinstance(raw, str):
                parsed = _parse_timestamp(raw)
                if parsed is not None:
                    return raw, parsed
    mtimes = [path.stat().st_mtime for path in files.values() if path.is_file()]
    if mtimes:
        stamp = datetime.fromtimestamp(max(mtimes), timezone.utc)
        return stamp.isoformat(timespec="seconds"), stamp
    return None, _EPOCH


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# --- rendering ------------------------------------------------------------


def render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    pass_rate = report["pass_rate"]
    totals = coverage["totals"]

    lines: list[str] = []
    lines.append("# Agent 评测 gate 探针覆盖率报告")
    lines.append("")
    lines.append(f"- 生成时间（UTC）：{report['generated_at']}")
    lines.append(f"- 任务目录：`{report['tasks_dir']}`（{coverage['task_count']} 个任务）")
    if report["archives_root"] is not None:
        lines.append(f"- 评测归档：`{report['archives_root']}`（{pass_rate['runs_found']} 次运行）")
    else:
        lines.append("- 评测归档：未提供 `--archives-root`，跳过通过率统计")
    lines.append("")

    lines.append("## Gate 探针覆盖率（北极星指标）")
    lines.append("")
    lines.append(
        "覆盖率 = 声明的 business/page gate 中已在 `gate_probes` 配置探针命令的比例；"
        "未覆盖 gate 在评分中按 fail-closed 计失败。"
    )
    lines.append("")
    lines.append("| 任务 | 声明 gate | 有探针 | 未覆盖 | 覆盖率 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for task in coverage["tasks"]:
        lines.append(
            f"| `{task['task_id']}` | {task['declared_gates']} | {task['probed_gates']} "
            f"| {task['unprobed_gates']} | {_format_pct(task['coverage_pct'])} |"
        )
    lines.append(
        f"| **合计** | **{totals['declared_gates']}** | **{totals['probed_gates']}** "
        f"| **{totals['unprobed_gates']}** | **{_format_pct(totals['coverage_pct'])}** |"
    )
    lines.append("")

    lines.append("## 未覆盖 gate backlog（按缺口原因分组）")
    lines.append("")
    if coverage["gap_groups"]:
        for group in coverage["gap_groups"]:
            reason = group["reason"] if group["reason"] is not None else _UNREGISTERED_GAP_LABEL
            lines.append(f"- **{reason}**（{group['count']} 个 gate）")
            for entry in group["entries"]:
                lines.append(f"  - `{entry['task_id']}` / `{entry['gate']}`")
    else:
        lines.append("所有声明 gate 均已配置探针，无缺口。")
    lines.append("")

    lines.append("## 探针命令类型分布")
    lines.append("")
    if coverage["probe_kinds"]:
        lines.append("| 类型 | 数量 | 过滤词 / 目标 |")
        lines.append("| --- | ---: | --- |")
        for kind in coverage["probe_kinds"]:
            targets = ", ".join(f"`{target}`" for target in kind["targets"]) or "—"
            lines.append(f"| {kind['kind']} | {kind['count']} | {targets} |")
    else:
        lines.append("暂无已配置的探针命令。")
    lines.append("")

    lines.append("## 评测通过率（按任务聚合）")
    lines.append("")
    if not pass_rate["available"]:
        lines.append("未提供 `--archives-root`，本节未统计。")
    elif pass_rate["runs_found"] == 0:
        lines.append("暂无评测归档。")
    else:
        lines.append(
            "void = scorecard 缺失但 result 存在：测量按防篡改设计作废，是对评测的陈述，不代表变更质量。"
        )
        lines.append("")
        lines.append("| 任务 | 运行 | pass | fail | void | 最近一次 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
        for task in pass_rate["tasks"]:
            if task["latest_timestamp"]:
                latest = f"{task['latest_timestamp']} · {task['latest_status']}"
            else:
                latest = task["latest_status"] or "—"
            lines.append(
                f"| `{task['task_id']}` | {task['runs']} | {task['pass']} "
                f"| {task['fail']} | {task['void']} | {latest} |"
            )
        pr_totals = pass_rate["totals"]
        lines.append(
            f"| **合计** | **{pr_totals['runs']}** | **{pr_totals['pass']}** "
            f"| **{pr_totals['fail']}** | **{pr_totals['void']}** | — |"
        )
    lines.append("")

    if report["warnings"]:
        lines.append("## 警告")
        lines.append("")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def _format_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _relative_to(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _emit(text: str) -> None:
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        # Windows consoles may use a non-UTF-8 code page; a report tool should
        # degrade characters rather than crash.
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding))


if __name__ == "__main__":
    raise SystemExit(main())
