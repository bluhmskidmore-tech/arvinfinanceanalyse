"""Smoke tests for audit_caliber_violations script."""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.app.core_finance.calibers import get_caliber_rule, list_caliber_rules

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def _load_audit_module():
    return load_module(
        "backend.scripts.audit_caliber_violations",
        "backend/scripts/audit_caliber_violations.py",
    )


def test_pattern_constants_are_compiled_regex_objects() -> None:
    mod = _load_audit_module()
    patterns = mod._PATTERNS
    allowed = {"high", "medium", "low"}
    for entry in patterns:
        assert "pattern_id" in entry
        assert "regex" in entry
        assert "confidence" in entry
        assert isinstance(entry["regex"], re.Pattern)
        assert entry["confidence"] in allowed


def test_scan_finds_known_violation_in_analysis_adapters() -> None:
    mod = _load_audit_module()
    violations = mod.scan_violations(project_root=ROOT)
    found = [
        v
        for v in violations
        if str(v["file"]).endswith("services/analysis_adapters.py")
        and v["pattern_id"] == "basis_eq_scenario_str"
    ]
    assert found, "expected at least one basis_eq_scenario_str hit in services/analysis_adapters.py"


def test_scan_skips_calibers_subpackage() -> None:
    mod = _load_audit_module()
    violations = mod.scan_violations(project_root=ROOT)
    for v in violations:
        assert "calibers" not in v["file"].split("/")


def test_scan_returns_sorted_stable_order() -> None:
    mod = _load_audit_module()
    first = mod.scan_violations(project_root=ROOT)
    second = mod.scan_violations(project_root=ROOT)
    assert first == second


def test_main_writes_markdown_and_json_sidecar(tmp_path: Path) -> None:
    mod = _load_audit_module()
    md_path = tmp_path / mod._MD_NAME
    json_path = tmp_path / mod._JSON_NAME
    try:
        mod.main(output_dir=tmp_path, project_root=ROOT)
        assert md_path.is_file()
        assert json_path.is_file()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["rule_id"] == "formal_scenario_gate"
        assert isinstance(data["generated_at_utc"], str)
        assert data["scanned_dirs"] == list(mod._SCANNED_DIR_RELS)
        assert set(data["totals"].keys()) == {"high", "medium", "low", "all"}
        assert isinstance(data["violations"], list)
    finally:
        for p in (md_path, json_path):
            if p.is_file():
                p.unlink()


def test_known_rules_constant_lists_all_5_registered_rule_ids() -> None:
    mod = _load_audit_module()
    registered = sorted(r.rule_id for r in list_caliber_rules())
    assert list(mod.KNOWN_RULES) == registered


def test_patterns_dict_has_entry_per_known_rule() -> None:
    mod = _load_audit_module()
    for rid in mod.KNOWN_RULES:
        assert rid in mod.PATTERNS
        assert len(mod.PATTERNS[rid]) >= 1


def test_scan_violations_per_rule_runs_for_each_known_rule_without_crashing() -> None:
    mod = _load_audit_module()
    for rid in mod.KNOWN_RULES:
        out = mod.scan_violations(rule_id=rid, project_root=ROOT)
        assert isinstance(out, list)


def test_scan_skips_canonical_module_file_for_each_rule() -> None:
    mod = _load_audit_module()
    for rid in mod.KNOWN_RULES:
        rule = get_caliber_rule(rid)
        canon_rel = rule.canonical_module.replace(".", "/") + ".py"
        violations = mod.scan_violations(rule_id=rid, project_root=ROOT)
        for v in violations:
            assert v["file"] != canon_rel


def test_subject_514_516_517_merge_baseline_finds_at_least_one_high_in_pnl_module() -> None:
    mod = _load_audit_module()
    v = mod.scan_violations(rule_id="subject_514_516_517_merge", project_root=ROOT)
    pnl_hits = [
        x
        for x in v
        if x["confidence"] == "high" and x["file"].endswith("core_finance/pnl.py")
    ]
    assert pnl_hits


def test_hat_mapping_baseline_finds_at_least_three_high_in_core_finance() -> None:
    mod = _load_audit_module()
    v = mod.scan_violations(rule_id="hat_mapping", project_root=ROOT)
    cf_high = [x for x in v if x["confidence"] == "high" and "/core_finance/" in x["file"]]
    assert len(cf_high) >= 3


def test_issuance_exclusion_baseline_is_empty() -> None:
    mod = _load_audit_module()
    v = mod.scan_violations(rule_id="issuance_exclusion", project_root=ROOT)
    assert v == []


def test_fx_mid_conversion_baseline_is_empty() -> None:
    mod = _load_audit_module()
    v = mod.scan_violations(rule_id="fx_mid_conversion", project_root=ROOT)
    assert v == []
