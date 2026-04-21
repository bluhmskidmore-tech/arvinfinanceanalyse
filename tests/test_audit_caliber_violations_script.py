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


def _minimal_project_with_services_file(root: Path, rel_services_file: str, content: str) -> Path:
    p = root / "backend" / "app" / "services" / rel_services_file
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return root


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


def test_scan_finds_basis_eq_scenario_in_minimal_services_tree(tmp_path: Path) -> None:
    """Stable repro without depending on analysis_adapters.py drift."""
    mod = _load_audit_module()
    _minimal_project_with_services_file(
        tmp_path,
        "caliber_audit_snippet.py",
        "def _f(basis: str) -> bool:\n    return basis == 'scenario'\n",
    )
    violations, _sup = mod.scan_violations(project_root=tmp_path)
    found = [
        v
        for v in violations
        if v["file"].endswith("services/caliber_audit_snippet.py")
        and v["pattern_id"] == "basis_eq_scenario_str"
    ]
    assert found, "expected basis_eq_scenario_str in minimal services tree"


def test_scan_skips_calibers_subpackage() -> None:
    mod = _load_audit_module()
    violations, _ = mod.scan_violations(project_root=ROOT)
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
        assert isinstance(data["suppressed"], int)
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
        out, sup = mod.scan_violations(rule_id=rid, project_root=ROOT)
        assert isinstance(out, list)
        assert isinstance(sup, int)


def test_scan_skips_canonical_module_file_for_each_rule() -> None:
    mod = _load_audit_module()
    for rid in mod.KNOWN_RULES:
        rule = get_caliber_rule(rid)
        canon_rel = rule.canonical_module.replace(".", "/") + ".py"
        violations, _ = mod.scan_violations(rule_id=rid, project_root=ROOT)
        for v in violations:
            assert v["file"] != canon_rel


def test_subject_merge_suppression_requires_matching_marker(tmp_path: Path) -> None:
    """Real ``pnl.py`` may lack adjacent Human markers; use an isolated snippet."""
    mod = _load_audit_module()
    root = _minimal_project_with_services_file(
        tmp_path,
        "subject_marker.py",
        (
            "# Human: caliber-subject_514_516_517_merge-justified\n"
            'JournalType = Literal["514", "516", "517", "adjustment"]\n'
        ),
    )
    v, sup = mod.scan_violations(rule_id="subject_514_516_517_merge", project_root=root)
    assert not v
    assert sup >= 1


def test_hat_mapping_core_finance_suppressed_when_justified() -> None:
    mod = _load_audit_module()
    v, sup = mod.scan_violations(rule_id="hat_mapping", project_root=ROOT)
    cf = [x for x in v if "/core_finance/" in x["file"]]
    assert not cf
    assert sup >= 1


def test_issuance_exclusion_baseline_is_empty() -> None:
    mod = _load_audit_module()
    v, _ = mod.scan_violations(rule_id="issuance_exclusion", project_root=ROOT)
    assert v == []


def test_fx_mid_conversion_baseline_is_empty() -> None:
    mod = _load_audit_module()
    v, _ = mod.scan_violations(rule_id="fx_mid_conversion", project_root=ROOT)
    assert v == []


def test_justified_comment_above_line_suppresses_matching_rule(tmp_path: Path) -> None:
    mod = _load_audit_module()
    root_baseline = _minimal_project_with_services_file(
        tmp_path / "a",
        "x.py",
        'def f():\n    return "R001", "持有至到期"\n',
    )
    v0, s0 = mod.scan_violations(rule_id="hat_mapping", project_root=root_baseline)
    assert v0
    assert s0 == 0

    root_sup = _minimal_project_with_services_file(
        tmp_path / "b",
        "x.py",
        (
            "def f():\n"
            "    # Human: caliber-hat_mapping-justified\n"
            '    return "R001", "持有至到期"\n'
        ),
    )
    v1, s1 = mod.scan_violations(rule_id="hat_mapping", project_root=root_sup)
    assert len(v1) == len(v0) - 1
    assert s1 >= 1


def test_justified_marker_for_different_rule_does_not_suppress(tmp_path: Path) -> None:
    mod = _load_audit_module()
    content = (
        "# Human: caliber-hat_mapping-justified\n"
        'JournalType = Literal["514", "516", "517", "adjustment"]\n'
    )
    root = _minimal_project_with_services_file(tmp_path, "rule_mismatch.py", content)
    v, sup = mod.scan_violations(rule_id="subject_514_516_517_merge", project_root=root)
    hit = [x for x in v if "rule_mismatch.py" in x["file"]]
    assert hit, "expected subject rule to still flag the Literal line"
    assert sup == 0


def test_justified_comment_too_far_above_does_not_suppress(tmp_path: Path) -> None:
    mod = _load_audit_module()
    lines = ["# Human: caliber-hat_mapping-justified", *([""] * 19), 'x = "持有至到期"']
    content = "\n".join(lines) + "\n"
    root = _minimal_project_with_services_file(tmp_path, "far.py", content)
    v, sup = mod.scan_violations(rule_id="hat_mapping", project_root=root)
    assert v
    assert sup == 0


def test_scan_includes_suppressed_count_for_reporting() -> None:
    mod = _load_audit_module()
    _v, sup = mod.scan_violations(rule_id="hat_mapping", project_root=ROOT)
    assert isinstance(sup, int)
