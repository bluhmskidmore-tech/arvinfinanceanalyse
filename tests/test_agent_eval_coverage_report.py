"""Tests for scripts/agent_eval/coverage_report.py.

All fixtures are self-contained temporary task directories and fake archives,
so the tests stay independent from the real scripts/agent_eval/tasks/ content
(which other work streams extend in parallel) and from real replay runs.
"""

import json

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval.coverage_report import (
    build_report,
    classify_probe_command,
    main,
    render_markdown,
)

SHARED_GAP_REASON = "Needs a trade-date basis assertion."

FULL_PROBE_TASK = {
    "id": "full_probe_001",
    "business_gates": ["unit_consistency"],
    "page_gates": ["page_loads"],
    "gate_probes": {
        "unit_consistency": "python -m pytest tests/test_unit_contract.py -q",
        "page_loads": "npm --prefix frontend run test -- LedgerPnlPageLoads",
    },
}

MIXED_PROBE_TASK = {
    "id": "mixed_probe_002",
    "business_gates": ["unit_consistency", "date_semantics"],
    "page_gates": ["page_loads", "no_console_errors"],
    "gate_probes": {
        "unit_consistency": "npm --prefix frontend run test -- MixedUnitContract",
        "no_console_errors": "npm --prefix frontend run test:a11y-smoke",
    },
    "gate_probe_gaps": {"date_semantics": SHARED_GAP_REASON},
}

NO_PROBE_TASK = {
    "id": "no_probe_003",
    "business_gates": ["precision_and_rounding"],
    "page_gates": ["fallback_state_visible"],
    "gate_probe_gaps": {"precision_and_rounding": SHARED_GAP_REASON},
}


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_tasks_dir(tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    _write_json(tasks_dir / "full_probe_001.json", FULL_PROBE_TASK)
    _write_json(tasks_dir / "mixed_probe_002.json", MIXED_PROBE_TASK)
    _write_json(tasks_dir / "no_probe_003.json", NO_PROBE_TASK)
    return tasks_dir


def _result_payload(task_id, collected_at):
    return {
        "evidence": [],
        "checks": {},
        "business_gates": {},
        "page_gates": {},
        "changed_files": [],
        "measurement": {
            "collected_at": collected_at,
            "integrity": {"task_id": task_id, "trusted": False},
        },
    }


def _scorecard_payload(task_id, status):
    return {
        "task_id": task_id,
        "status": status,
        "score": 95.5 if status == "pass" else 40.0,
        "breakdown": {"business": 40, "page": 20, "verification": 20, "diff": 20},
        "hard_failures": [] if status == "pass" else ["Business gate failed: unit_consistency"],
        "warnings": [],
    }


def _make_archives(tmp_path):
    """One task with a pass, a fail, and a void (pr-replay style, no scorecard) run."""

    root = tmp_path / "archives"
    pass_dir = root / "replays" / "full_probe_001-20260812T010101Z"
    _write_json(pass_dir / "scorecard.json", _scorecard_payload("full_probe_001", "pass"))
    _write_json(pass_dir / "result.json", _result_payload("full_probe_001", "2026-08-12T01:01:01+00:00"))

    fail_dir = root / "replays" / "full_probe_001-20260812T020202Z"
    _write_json(fail_dir / "scorecard.json", _scorecard_payload("full_probe_001", "fail"))
    _write_json(fail_dir / "result.json", _result_payload("full_probe_001", "2026-08-12T02:02:02+00:00"))

    void_dir = root / "pr-replay" / "full_probe_001"
    _write_json(void_dir / "result.json", _result_payload("full_probe_001", "2026-08-13T03:03:03+00:00"))
    return root


def _coverage_by_task(report):
    return {task["task_id"]: task for task in report["coverage"]["tasks"]}


# --- coverage -------------------------------------------------------------


def test_coverage_per_task_and_totals(tmp_path):
    report = build_report(tasks_dir=_make_tasks_dir(tmp_path))
    tasks = _coverage_by_task(report)

    assert report["coverage"]["task_count"] == 3
    assert tasks["full_probe_001"]["declared_gates"] == 2
    assert tasks["full_probe_001"]["probed_gates"] == 2
    assert tasks["full_probe_001"]["coverage_pct"] == 100.0
    assert tasks["mixed_probe_002"]["declared_gates"] == 4
    assert tasks["mixed_probe_002"]["probed_gates"] == 2
    assert tasks["mixed_probe_002"]["coverage_pct"] == 50.0
    assert tasks["no_probe_003"]["probed_gates"] == 0
    assert tasks["no_probe_003"]["coverage_pct"] == 0.0

    totals = report["coverage"]["totals"]
    assert totals == {
        "declared_gates": 8,
        "probed_gates": 4,
        "unprobed_gates": 4,
        "coverage_pct": 50.0,
    }
    assert report["warnings"] == []


def test_gap_groups_merge_same_reason_across_tasks(tmp_path):
    report = build_report(tasks_dir=_make_tasks_dir(tmp_path))
    groups = {group["reason"]: group for group in report["coverage"]["gap_groups"]}

    shared = groups[SHARED_GAP_REASON]
    assert shared["count"] == 2
    assert shared["entries"] == [
        {"task_id": "mixed_probe_002", "gate": "date_semantics"},
        {"task_id": "no_probe_003", "gate": "precision_and_rounding"},
    ]

    unregistered = groups[None]
    assert unregistered["count"] == 2
    assert unregistered["entries"] == [
        {"task_id": "mixed_probe_002", "gate": "page_loads"},
        {"task_id": "no_probe_003", "gate": "fallback_state_visible"},
    ]
    # Registered reasons sort ahead of the unregistered bucket at equal counts.
    assert report["coverage"]["gap_groups"][-1]["reason"] is None


def test_probe_kind_distribution(tmp_path):
    report = build_report(tasks_dir=_make_tasks_dir(tmp_path))
    kinds = {kind["kind"]: kind for kind in report["coverage"]["probe_kinds"]}

    assert kinds["pytest"]["count"] == 1
    assert kinds["pytest"]["targets"] == ["tests/test_unit_contract.py"]
    assert kinds["vitest"]["count"] == 2
    assert kinds["vitest"]["targets"] == ["LedgerPnlPageLoads", "MixedUnitContract"]
    assert kinds["npm:test:a11y-smoke"]["count"] == 1
    assert kinds["npm:test:a11y-smoke"]["targets"] == []


def test_classify_probe_command_variants():
    assert classify_probe_command("python -m pytest tests/test_x.py -q") == (
        "pytest",
        "tests/test_x.py",
    )
    assert classify_probe_command("npm --prefix frontend run test -- LedgerPnl") == (
        "vitest",
        "LedgerPnl",
    )
    assert classify_probe_command("npm --prefix frontend run typecheck") == (
        "npm:typecheck",
        None,
    )
    assert classify_probe_command("bash scripts/evil.sh") == ("other", None)


def test_bad_task_json_warns_without_crashing(tmp_path):
    tasks_dir = _make_tasks_dir(tmp_path)
    (tasks_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
    (tasks_dir / "not_object.json").write_text('["a list"]', encoding="utf-8")

    report = build_report(tasks_dir=tasks_dir)

    assert report["coverage"]["task_count"] == 3
    assert "broken.json" not in _coverage_by_task(report)
    assert any("broken.json" in warning for warning in report["warnings"])
    assert any("not_object.json" in warning for warning in report["warnings"])
    # Numbers from the healthy tasks are unaffected by the broken files.
    assert report["coverage"]["totals"]["coverage_pct"] == 50.0

    exit_code = main(["--tasks-dir", str(tasks_dir), "--out", str(tmp_path / "report.md")])
    assert exit_code == 0


# --- pass rate ------------------------------------------------------------


def test_pass_rate_aggregation_with_void(tmp_path):
    report = build_report(
        tasks_dir=_make_tasks_dir(tmp_path),
        archives_root=_make_archives(tmp_path),
    )
    pass_rate = report["pass_rate"]

    assert pass_rate["available"] is True
    assert pass_rate["runs_found"] == 3
    assert len(pass_rate["tasks"]) == 1

    stats = pass_rate["tasks"][0]
    assert stats["task_id"] == "full_probe_001"
    assert stats["runs"] == 3
    assert stats["pass"] == 1
    assert stats["fail"] == 1
    assert stats["void"] == 1
    assert stats["latest_status"] == "void"
    assert stats["latest_timestamp"] == "2026-08-13T03:03:03+00:00"

    assert pass_rate["totals"] == {"runs": 3, "pass": 1, "fail": 1, "void": 1}


def test_unreadable_scorecard_with_result_counts_as_void(tmp_path):
    root = tmp_path / "archives"
    run_dir = root / "replays" / "mixed_probe_002-20260812T040404Z"
    (run_dir).mkdir(parents=True)
    (run_dir / "scorecard.json").write_text("{corrupt", encoding="utf-8")
    _write_json(run_dir / "result.json", _result_payload("mixed_probe_002", "2026-08-12T04:04:04+00:00"))

    report = build_report(tasks_dir=_make_tasks_dir(tmp_path), archives_root=root)
    stats = report["pass_rate"]["tasks"][0]

    assert stats["task_id"] == "mixed_probe_002"
    assert stats == {
        "task_id": "mixed_probe_002",
        "runs": 1,
        "pass": 0,
        "fail": 0,
        "void": 1,
        "latest_timestamp": "2026-08-12T04:04:04+00:00",
        "latest_status": "void",
    }
    assert any("scorecard.json" in warning for warning in report["warnings"])


def test_archive_dir_with_only_corrupt_files_is_skipped(tmp_path):
    root = tmp_path / "archives"
    run_dir = root / "replays" / "junk-20260812T050505Z"
    run_dir.mkdir(parents=True)
    (run_dir / "scorecard.json").write_text("{corrupt", encoding="utf-8")

    report = build_report(tasks_dir=_make_tasks_dir(tmp_path), archives_root=root)

    assert report["pass_rate"]["runs_found"] == 0
    assert report["pass_rate"]["tasks"] == []
    assert any("已跳过" in warning for warning in report["warnings"])


# --- rendering ------------------------------------------------------------


def test_markdown_output_tables_and_sections(tmp_path):
    out_path = tmp_path / "report.md"
    exit_code = main(
        [
            "--tasks-dir",
            str(_make_tasks_dir(tmp_path)),
            "--archives-root",
            str(_make_archives(tmp_path)),
            "--format",
            "md",
            "--out",
            str(out_path),
        ]
    )
    assert exit_code == 0
    text = out_path.read_text(encoding="utf-8")

    assert "## Gate 探针覆盖率（北极星指标）" in text
    assert "| `full_probe_001` | 2 | 2 | 0 | 100.0% |" in text
    assert "| `mixed_probe_002` | 4 | 2 | 2 | 50.0% |" in text
    assert "| `no_probe_003` | 2 | 0 | 2 | 0.0% |" in text
    assert "| **合计** | **8** | **4** | **4** | **50.0%** |" in text

    assert f"- **{SHARED_GAP_REASON}**（2 个 gate）" in text
    assert "- **（未登记缺口原因）**（2 个 gate）" in text
    assert "  - `mixed_probe_002` / `date_semantics`" in text

    assert "## 探针命令类型分布" in text
    assert "| vitest | 2 |" in text

    assert "## 评测通过率（按任务聚合）" in text
    assert "| `full_probe_001` | 3 | 1 | 1 | 1 | 2026-08-13T03:03:03+00:00 · void |" in text
    assert "| **合计** | **3** | **1** | **1** | **1** | — |" in text


def test_markdown_messages_when_archives_missing_or_empty(tmp_path):
    tasks_dir = _make_tasks_dir(tmp_path)

    without_root = render_markdown(build_report(tasks_dir=tasks_dir))
    assert "未提供 `--archives-root`，本节未统计。" in without_root
    assert "暂无评测归档" not in without_root

    empty_root = tmp_path / "empty-archives"
    empty_root.mkdir()
    with_empty_root = render_markdown(build_report(tasks_dir=tasks_dir, archives_root=empty_root))
    assert "暂无评测归档。" in with_empty_root


def test_json_output_schema_is_stable(tmp_path, capsys):
    exit_code = main(
        [
            "--tasks-dir",
            str(_make_tasks_dir(tmp_path)),
            "--archives-root",
            str(_make_archives(tmp_path)),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {
        "schema_version",
        "generated_at",
        "tasks_dir",
        "archives_root",
        "coverage",
        "pass_rate",
        "warnings",
    }
    assert payload["schema_version"] == 1
    assert set(payload["coverage"]) == {
        "task_count",
        "tasks",
        "totals",
        "gap_groups",
        "probe_kinds",
    }
    assert set(payload["pass_rate"]) == {"available", "runs_found", "tasks", "totals"}
    for task in payload["coverage"]["tasks"]:
        assert set(task) == {
            "task_id",
            "declared_gates",
            "probed_gates",
            "unprobed_gates",
            "coverage_pct",
            "unprobed",
        }
    for stats in payload["pass_rate"]["tasks"]:
        assert set(stats) == {
            "task_id",
            "runs",
            "pass",
            "fail",
            "void",
            "latest_timestamp",
            "latest_status",
        }
