from __future__ import annotations

from tests.helpers import load_module


def test_research_run_manifest_is_stable_and_traceable(tmp_path):
    governance_module = load_module(
        "backend.app.governance.research_runs",
        "backend/app/governance/research_runs.py",
    )
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    manifest = governance_module.build_research_run_manifest(
        run_kind="analysis",
        source_version="sv_market_20260331",
        vendor_version="vv_choice_20260331",
        rule_version="rv_macro_signal_v1",
        parameters={"window": 20, "threshold": "0.50"},
        window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "as_of_date": "2026-03-31",
        },
        universe={"portfolio": "all", "desk": "rates"},
        code_version="git:unknown",
    )
    manifest_same_params = governance_module.build_research_run_manifest(
        run_kind="analysis",
        source_version="sv_market_20260331",
        vendor_version="vv_choice_20260331",
        rule_version="rv_macro_signal_v1",
        parameters={"threshold": "0.50", "window": 20},
        window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "as_of_date": "2026-03-31",
        },
        universe={"portfolio": "all", "desk": "rates"},
        code_version="git:unknown",
    )

    assert manifest.parameter_hash == manifest_same_params.parameter_hash
    assert manifest.source_version == "sv_market_20260331"
    assert manifest.vendor_version == "vv_choice_20260331"
    assert manifest.rule_version == "rv_macro_signal_v1"
    assert manifest.temporal_policy == "fail_closed"
    assert manifest.window.start_date == "2026-01-01"
    assert manifest.window.end_date == "2026-03-31"
    assert manifest.window.as_of_date == "2026-03-31"
    assert manifest.universe == {"portfolio": "all", "desk": "rates"}
    assert manifest.code_version == "git:unknown"

    repo = repo_module.GovernanceRepository(base_dir=tmp_path / "governance")
    governance_module.record_research_run(repo=repo, manifest=manifest)

    rows = repo.read_all(governance_module.RESEARCH_RUN_MANIFEST_STREAM)
    assert len(rows) == 1
    assert rows[0]["parameter_hash"] == manifest.parameter_hash
    assert rows[0]["window"]["start_date"] == "2026-01-01"
    assert rows[0]["window"]["end_date"] == "2026-03-31"
    assert rows[0]["window"]["as_of_date"] == "2026-03-31"
    assert rows[0]["universe"] == {"portfolio": "all", "desk": "rates"}
    assert rows[0]["code_version"] == "git:unknown"
