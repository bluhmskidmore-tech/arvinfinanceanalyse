from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.app.core_finance.fixed_income_version_set import (
    CONFIGURED_CURRENT_VERSION_STATE,
    FIXED_INCOME_VERSION_SET,
)
from backend.app.schemas.release_control import ReleaseScope

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fixed_income_versions_preserve_existing_descriptor_metadata() -> None:
    versions = FIXED_INCOME_VERSION_SET
    bond = versions.bond_analytics
    risk = versions.risk_tensor

    assert versions.engine_rule_version == "rv_bond_analytics_engine_v3"

    assert bond.job_name == "bond_analytics_materialize"
    assert bond.rule_version == "rv_bond_analytics_formal_materialize_v6"
    assert bond.cache_key == "bond_analytics:materialize:formal"
    assert bond.cache_version == (
        "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v6"
    )
    assert bond.running_source_version == "sv_bond_analytics_running"
    assert bond.stable_output_version == bond.cache_version
    assert bond.vendor_version == "vv_none"
    assert bond.lock_key == "lock:duckdb:formal:bond-analytics:materialize"
    assert bond.input_sources == ("zqtz_bond_daily_snapshot",)
    assert bond.fact_tables == ("fact_formal_bond_analytics_daily",)

    assert risk.job_name == "risk_tensor_materialize"
    assert risk.rule_version == "rv_risk_tensor_formal_materialize_v12"
    assert risk.cache_key == "risk_tensor:materialize:formal"
    assert risk.cache_version == (
        "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v12"
    )
    assert risk.running_source_version == "sv_risk_tensor_running"
    assert risk.stable_output_version == risk.cache_version
    assert risk.vendor_version == "vv_none"
    assert risk.lock_key == "lock:duckdb:formal:risk-tensor:materialize"
    assert risk.input_sources == (
        "fact_formal_bond_analytics_daily",
        "fact_formal_tyw_balance_daily",
    )
    assert risk.fact_tables == ("fact_formal_risk_tensor_daily",)


def test_version_objects_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        FIXED_INCOME_VERSION_SET.engine_rule_version = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        FIXED_INCOME_VERSION_SET.bond_analytics.job_name = "changed"  # type: ignore[misc]


def test_version_module_import_does_not_load_tasks_services_or_registry() -> None:
    code = """
import sys
import backend.app.core_finance.fixed_income_version_set
for name in sys.modules:
    if name.startswith(('backend.app.tasks.', 'backend.app.services.')):
        raise SystemExit(f'unexpected side-effect import: {name}')
if 'backend.app.core_finance.module_registry' in sys.modules:
    raise SystemExit('unexpected module_registry import')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_configured_fragment_is_static_and_does_not_claim_approval() -> None:
    fragment = FIXED_INCOME_VERSION_SET.emit_configured_current_fragment()

    assert fragment["version_state"] == CONFIGURED_CURRENT_VERSION_STATE
    assert fragment["engine_rule_version"] == "rv_bond_analytics_engine_v3"
    assert fragment["bond_analytics"] == (
        FIXED_INCOME_VERSION_SET.bond_analytics.emit_descriptor_fragment()
    )
    assert fragment["risk_tensor"] == (
        FIXED_INCOME_VERSION_SET.risk_tensor.emit_descriptor_fragment()
    )
    assert fragment["bond_analytics"]["input_sources"] == [  # type: ignore[index]
        "zqtz_bond_daily_snapshot"
    ]
    assert fragment["risk_tensor"]["fact_tables"] == [  # type: ignore[index]
        "fact_formal_risk_tensor_daily"
    ]

    serialized = json.dumps(fragment, sort_keys=True)
    assert "approved" not in serialized
    assert "frozen" not in serialized
    assert "release_eligible" not in serialized
    assert "lane_key" not in serialized
    assert "artifact_version" not in serialized


def test_runtime_emitters_require_and_preserve_observed_lineage() -> None:
    from backend.app.tasks.formal_compute_runtime import _manifest_min_lineage

    versions = FIXED_INCOME_VERSION_SET
    fragment = versions.emit_runtime_fragment(
        run_id="run-fixed-income-1",
        report_date="2026-08-31",
        bond_source_version="sv_bond_snapshot_42",
        bond_vendor_version="vv_none",
        risk_source_version="sv_risk_tensor__sv_bond_snapshot_42__sv_liability_7",
        risk_vendor_version="vv_none",
        risk_upstream_source_version="sv_bond_snapshot_42",
        risk_upstream_rule_version=versions.bond_analytics.rule_version,
        risk_upstream_cache_version=versions.bond_analytics.cache_version,
        liability_source_version="sv_liability_7",
        liability_rule_version="rv_liability_3",
    )

    bond_runtime = fragment["runtime"]["bond_analytics"]  # type: ignore[index]
    risk_runtime = fragment["runtime"]["risk_tensor"]  # type: ignore[index]
    assert bond_runtime == versions.bond_analytics.emit_runtime_lineage(
        run_id="run-fixed-income-1",
        report_date="2026-08-31",
        source_version="sv_bond_snapshot_42",
        vendor_version="vv_none",
    )
    assert risk_runtime["source_version"] == (
        "sv_risk_tensor__sv_bond_snapshot_42__sv_liability_7"
    )
    assert risk_runtime["upstream_lineage"] == {
        "source_version": "sv_bond_snapshot_42",
        "rule_version": versions.bond_analytics.rule_version,
        "cache_version": versions.bond_analytics.cache_version,
    }
    assert risk_runtime["liability_lineage"] == {
        "source_version": "sv_liability_7",
        "rule_version": "rv_liability_3",
    }

    manifest_lineage = versions.bond_analytics.emit_manifest_min_lineage(
        run_id="run-fixed-income-1",
        report_date="2026-08-31",
        source_version="sv_bond_snapshot_42",
        vendor_version="vv_none",
    )
    assert "cache_key" not in manifest_lineage
    assert "cache_version" not in manifest_lineage
    assert manifest_lineage["source_version"] == "sv_bond_snapshot_42"
    assert manifest_lineage == _manifest_min_lineage(
        descriptor=versions.bond_analytics.descriptor,
        run_id="run-fixed-income-1",
        report_date="2026-08-31",
        source_version="sv_bond_snapshot_42",
        vendor_version="vv_none",
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"bond_source_version": ""}, "bond_analytics.source_version is required"),
        (
            {"risk_upstream_source_version": "sv_other"},
            "upstream source_version must match",
        ),
        (
            {"risk_upstream_rule_version": "rv_other"},
            "upstream rule_version must match",
        ),
        (
            {"risk_upstream_cache_version": "cv_other"},
            "upstream cache_version must match",
        ),
        (
            {"liability_rule_version": ""},
            "liability source_version and rule_version must either both be set or both be empty",
        ),
        (
            {
                "risk_source_version": "sv_risk_tensor__sv_bond_snapshot_42",
            },
            "must exactly encode upstream and liability lineage",
        ),
    ],
)
def test_runtime_fragment_fails_closed_on_invalid_dynamic_lineage(
    override: dict[str, str],
    message: str,
) -> None:
    versions = FIXED_INCOME_VERSION_SET
    kwargs = {
        "run_id": "run-fixed-income-1",
        "report_date": "2026-08-31",
        "bond_source_version": "sv_bond_snapshot_42",
        "bond_vendor_version": "vv_none",
        "risk_source_version": "sv_risk_tensor__sv_bond_snapshot_42__sv_liability_7",
        "risk_vendor_version": "vv_none",
        "risk_upstream_source_version": "sv_bond_snapshot_42",
        "risk_upstream_rule_version": versions.bond_analytics.rule_version,
        "risk_upstream_cache_version": versions.bond_analytics.cache_version,
        "liability_source_version": "sv_liability_7",
        "liability_rule_version": "rv_liability_3",
    }
    kwargs.update(override)

    with pytest.raises(ValueError, match=message):
        versions.emit_runtime_fragment(**kwargs)


def test_runtime_fragment_allows_explicit_absence_of_liability_lineage() -> None:
    versions = FIXED_INCOME_VERSION_SET
    fragment = versions.emit_runtime_fragment(
        run_id="run-fixed-income-1",
        report_date="2026-08-31",
        bond_source_version="sv_bond_snapshot_42",
        bond_vendor_version="vv_none",
        risk_source_version="sv_risk_tensor__sv_bond_snapshot_42",
        risk_vendor_version="vv_none",
        risk_upstream_source_version="sv_bond_snapshot_42",
        risk_upstream_rule_version=versions.bond_analytics.rule_version,
        risk_upstream_cache_version=versions.bond_analytics.cache_version,
        liability_source_version="",
        liability_rule_version="",
    )

    assert fragment["runtime"]["risk_tensor"]["liability_lineage"] == {  # type: ignore[index]
        "source_version": "",
        "rule_version": "",
    }


def test_runtime_lineage_preserves_observed_vendor_version() -> None:
    lineage = FIXED_INCOME_VERSION_SET.bond_analytics.emit_runtime_lineage(
        run_id="run-observed-vendor",
        report_date="2026-08-31",
        source_version="sv_bond_snapshot_42",
        vendor_version="vv_bond_provider_42",
    )

    assert FIXED_INCOME_VERSION_SET.bond_analytics.vendor_version == "vv_none"
    assert lineage["vendor_version"] == "vv_bond_provider_42"


def test_runtime_fragment_round_trips_in_release_manifest_scope_alias_payload() -> None:
    versions = FIXED_INCOME_VERSION_SET
    fragment = versions.emit_runtime_fragment(
        run_id="run-fixed-income-manifest",
        report_date="2026-08-31",
        bond_source_version="sv_bond_snapshot_42",
        bond_vendor_version="vv_none",
        risk_source_version="sv_risk_tensor__sv_bond_snapshot_42__sv_liability_7",
        risk_vendor_version="vv_none",
        risk_upstream_source_version="sv_bond_snapshot_42",
        risk_upstream_rule_version=versions.bond_analytics.rule_version,
        risk_upstream_cache_version=versions.bond_analytics.cache_version,
        liability_source_version="sv_liability_7",
        liability_rule_version="rv_liability_3",
    )

    scope = ReleaseScope(
        scope_kind="logical_lane",
        scope_key="fixed-income-test-only",
        artifact_kind="fixed-income-shadow-evidence",
        artifact_version="configured-current-test-only",
        artifact_sha256="a" * 64,
        evidence_sha256="b" * 64,
        alias_payload={"fixed_income_version_fragment": fragment},
    )

    assert scope.model_dump(mode="json")["alias_payload"] == {
        "fixed_income_version_fragment": fragment
    }


def test_engine_and_tasks_keep_existing_public_constants() -> None:
    from backend.app.core_finance.bond_analytics.engine import ENGINE_RULE_VERSION
    from backend.app.tasks import bond_analytics_materialize as bond_task
    from backend.app.tasks import risk_tensor_materialize as risk_task

    versions = FIXED_INCOME_VERSION_SET
    assert ENGINE_RULE_VERSION == versions.engine_rule_version
    assert bond_task.BOND_ANALYTICS_MODULE == versions.bond_analytics.descriptor
    assert bond_task.RULE_VERSION == "rv_bond_analytics_formal_materialize_v6"
    assert bond_task.CACHE_KEY == versions.bond_analytics.cache_key
    assert bond_task.CACHE_VERSION == versions.bond_analytics.cache_version
    assert risk_task.RISK_TENSOR_MODULE == versions.risk_tensor.descriptor
    assert risk_task.RULE_VERSION == "rv_risk_tensor_formal_materialize_v12"
    assert risk_task.CACHE_KEY == versions.risk_tensor.cache_key
    assert risk_task.CACHE_VERSION == versions.risk_tensor.cache_version
    assert risk_task.BOND_ANALYTICS_CACHE_KEY == versions.bond_analytics.cache_key


def test_read_side_and_governance_exports_keep_existing_public_constants() -> None:
    from backend.app.services import bond_analytics_service, bond_dashboard_service
    from backend.app.services import risk_tensor_service
    from backend.app.repositories import risk_tensor_repo
    from scripts import emit_bond_analysis_governance_record

    versions = FIXED_INCOME_VERSION_SET

    assert bond_analytics_service.JOB_NAME == versions.bond_analytics.job_name
    assert bond_analytics_service.BOND_ANALYTICS_LOCK.key == versions.bond_analytics.lock_key
    assert (
        bond_analytics_service.BOND_ANALYTICS_LOCK.ttl_seconds
        == versions.bond_analytics.lock_ttl_seconds
    )
    assert bond_analytics_service.CACHE_KEY == versions.bond_analytics.cache_key
    assert bond_analytics_service.CACHE_VERSION == versions.bond_analytics.cache_version
    assert bond_analytics_service.RULE_VERSION == versions.bond_analytics.rule_version

    assert (
        bond_dashboard_service.BOND_ANALYTICS_JOB_NAME
        == versions.bond_analytics.job_name
    )
    assert (
        bond_dashboard_service.BOND_ANALYTICS_CACHE_KEY
        == versions.bond_analytics.cache_key
    )
    assert (
        bond_dashboard_service.BOND_ANALYTICS_CACHE_VERSION
        == versions.bond_analytics.cache_version
    )
    assert (
        bond_dashboard_service.BOND_ANALYTICS_RULE_VERSION
        == versions.bond_analytics.rule_version
    )

    assert risk_tensor_service.CACHE_KEY == versions.risk_tensor.cache_key
    assert risk_tensor_service.CACHE_VERSION == versions.risk_tensor.cache_version
    assert risk_tensor_service.RULE_VERSION == versions.risk_tensor.rule_version
    assert risk_tensor_repo.BOND_ANALYTICS_CACHE_KEY == versions.bond_analytics.cache_key

    record = emit_bond_analysis_governance_record.build_record("2026-06-06T00:00:00Z")
    assert record["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert record["rule_version"] == "rv_bond_analytics_formal_materialize_v2"
    assert record["cache_version"] == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2"


def test_version_literals_have_one_source_within_migrated_fixed_income_runtime() -> None:
    production_files = (
        REPO_ROOT / "backend/app/core_finance/fixed_income_version_set.py",
        REPO_ROOT / "backend/app/core_finance/bond_analytics/engine.py",
        REPO_ROOT / "backend/app/tasks/bond_analytics_materialize.py",
        REPO_ROOT / "backend/app/tasks/risk_tensor_materialize.py",
        REPO_ROOT / "backend/app/services/bond_analytics_service.py",
        REPO_ROOT / "backend/app/services/bond_dashboard_service.py",
        REPO_ROOT / "backend/app/services/risk_tensor_service.py",
        REPO_ROOT / "backend/app/repositories/risk_tensor_repo.py",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

    assert combined.count("rv_bond_analytics_engine_v3") == 1
    assert combined.count("rv_bond_analytics_formal_materialize_v6") == 1
    assert combined.count("rv_risk_tensor_formal_materialize_v12") == 1


def test_bond_analysis_governance_record_stays_pinned_to_historical_candidate() -> None:
    record = __import__(
        "scripts.emit_bond_analysis_governance_record",
        fromlist=["build_record"],
    ).build_record("2026-06-06T00:00:00Z")

    assert record["source_version"] == "sv_bond_analysis_action_attr_gs_a"
    assert record["rule_version"] == "rv_bond_analytics_formal_materialize_v2"
    assert record["cache_version"] == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2"
