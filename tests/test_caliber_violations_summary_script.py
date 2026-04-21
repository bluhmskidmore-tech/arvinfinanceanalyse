"""Tests for caliber_violations_summary script."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def _load_summary_mod():
    return load_module(
        "backend.scripts.caliber_violations_summary",
        "backend/scripts/caliber_violations_summary.py",
    )


def test_build_summary_has_all_5_rules() -> None:
    mod = _load_summary_mod()
    s = mod.build_summary(project_root=ROOT)
    assert len(s["rules"]) == 5
    assert set(s["rules"].keys()) == set(mod.KNOWN_RULES)


def test_summary_schema_version_is_1() -> None:
    mod = _load_summary_mod()
    s = mod.build_summary(project_root=ROOT)
    assert s["schema_version"] == 1
    assert "generated_at_utc" in s


def test_compare_against_baseline_detects_high_regression() -> None:
    mod = _load_summary_mod()
    baseline = {
        "schema_version": 1,
        "generated_at_utc": "x",
        "rules": {
            "formal_scenario_gate": {
                "rule_id": "formal_scenario_gate",
                "totals": {"high": 4, "medium": 0, "low": 0, "all": 4},
            }
        },
    }
    current = {
        "schema_version": 1,
        "generated_at_utc": "y",
        "rules": {
            "formal_scenario_gate": {
                "rule_id": "formal_scenario_gate",
                "totals": {"high": 5, "medium": 0, "low": 0, "all": 5},
            }
        },
    }
    r = mod.compare_against_baseline(current, baseline)
    assert r["drift_detected"] is True
    assert "formal_scenario_gate" in r["regressions"]


def test_compare_against_baseline_ignores_medium_and_low_changes() -> None:
    mod = _load_summary_mod()
    baseline = {
        "rules": {
            "formal_scenario_gate": {
                "totals": {"high": 4, "medium": 1, "low": 0, "all": 5},
            }
        }
    }
    current = {
        "rules": {
            "formal_scenario_gate": {
                "totals": {"high": 4, "medium": 99, "low": 99, "all": 102},
            }
        }
    }
    r = mod.compare_against_baseline(current, baseline)
    assert r["drift_detected"] is False
    assert r["regressions"] == []


def test_main_default_writes_summary_file_to_target_dir(tmp_path: Path) -> None:
    mod = _load_summary_mod()
    dest = tmp_path / mod.SUMMARY_FILENAME
    try:
        code = mod.main([f"--output-dir={tmp_path.as_posix()}"])
        assert code == 0
        assert dest.is_file()
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert data["schema_version"] == 1
        assert len(data["rules"]) == 5
    finally:
        if dest.is_file():
            dest.unlink()


def test_main_ci_mode_returns_zero_when_no_drift(tmp_path: Path) -> None:
    mod = _load_summary_mod()
    dest = tmp_path / mod.SUMMARY_FILENAME
    summary = mod.build_summary(project_root=ROOT)
    mod.write_summary(summary, dest)
    try:
        code = mod.main(
            [
                "--ci",
                f"--output-dir={tmp_path.as_posix()}",
            ]
        )
        assert code == 0
    finally:
        if dest.is_file():
            dest.unlink()


def test_main_ci_mode_returns_one_when_high_count_regressed(tmp_path: Path) -> None:
    mod = _load_summary_mod()
    dest = tmp_path / mod.SUMMARY_FILENAME
    summary = mod.build_summary(project_root=ROOT)
    # Artificially lower subject-rule high count so live scan shows a high-severity increase
    rid = "subject_514_516_517_merge"
    summary["rules"][rid]["totals"]["high"] = 0
    mod.write_summary(summary, dest)
    try:
        code = mod.main(
            [
                "--ci",
                f"--output-dir={tmp_path.as_posix()}",
            ]
        )
        assert code == 1
    finally:
        if dest.is_file():
            dest.unlink()
