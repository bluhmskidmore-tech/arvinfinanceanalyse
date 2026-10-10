from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.app.governance.exact_numeric_policy import (
    DEFAULT_REGISTRY_PATH,
    build_exact_numeric_policy,
    build_exact_numeric_policy_binding,
    exact_numeric_compat_registry_sha256,
    load_exact_numeric_compat_registry,
)
from backend.app.schemas.release_control import canonical_sha256


def test_exact_numeric_policy_registry_loads_with_pending_baseline_and_closed_release_gate() -> None:
    registry = load_exact_numeric_compat_registry()

    assert registry["policy_version"] == "exact-numeric-v1"
    assert registry["release_eligible"] is False
    assert registry["controlled_pages"] == [
        "cashflow-projection",
        "bond-dashboard",
        "risk-home",
        "pnl-attribution",
        "risk-tensor",
        "decision-items",
        "balance-analysis",
        "dashboard-home",
    ]
    assert registry["active_exceptions"] == []
    assert registry["pending_migrations"] == [
        {
            "path": "frontend/src/features/cashflow-projection/pages/cashflowProjectionPageModel.ts",
            "page": "cashflow-projection",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "The cashflow page model keeps one raw-only yuan-to-yi fallback for legacy responses while governed raw_text uses Decimal scaling.",
        },
        {
            "path": "frontend/src/features/bond-dashboard/utils/format.ts",
            "page": "bond-dashboard",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "Bond-dashboard exact text formatting is already in place, and this baseline now covers only the remaining raw-only legacy yuan-to-yi fallback in the shared formatter and delta helper.",
        },
        {
            "path": "frontend/src/features/bond-dashboard/components/YieldDistributionBar.tsx",
            "page": "bond-dashboard",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "Bond-dashboard exact text and tooltip formatting are already in place, and this baseline now covers only the remaining raw-only chart-series fallback inside the yield distribution component.",
        },
        {
            "path": "frontend/src/features/bond-dashboard/components/MaturityStructureChart.tsx",
            "page": "bond-dashboard",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Bond-dashboard exact text and tooltip formatting are already in place, and this baseline now covers only the remaining raw-only chart fallback in the maturity structure coordinates.",
        },
        {
            "path": "frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx",
            "page": "pnl-attribution",
            "rule": "decimal_like",
            "count": 4,
            "reason": "Production ProductCategory Decimal JSON strings already render through Decimal-based exact text on this page, but the DTO still permits legacy numbers that have already lost precision and cannot be recovered, so the compatibility debt remains pending.",
        },
        {
            "path": "frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx",
            "page": "pnl-attribution",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "Card and product-category text are exact when Decimal JSON strings are available, but the page still keeps two explicit compatibility boundaries: one raw-only chart coordinate scaling path and one ProductCategory legacy-number text fallback that preserves the old (value / 100_000_000).toFixed(2) behavior.",
        },
        {
            "path": "frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx",
            "page": "pnl-attribution",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "Campisi four-effects still consumes compatibility raw values and converts plain-number amounts to yi in the chart and table; the PnL Bridge raw_text wire is not yet carried through the Campisi DTO, while exact display and formal selection/closure require separate API and finance-owner decisions.",
        },
        {
            "path": "frontend/src/features/pnl-attribution/components/CampisiEnhancedPanel.tsx",
            "page": "pnl-attribution",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Campisi enhanced amount cards still scale plain-number totals locally; the PnL Bridge raw_text wire is not yet carried through the Campisi DTO and the model fallback remains float-based, so the display layer alone cannot restore exact values.",
        },
        {
            "path": "frontend/src/features/pnl-attribution/components/CampisiMaturityBucketPanel.tsx",
            "page": "pnl-attribution",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Campisi maturity-bucket table still scales plain-number bucket amounts locally; the lossless PnL Bridge value is discarded at the Campisi reader/DTO boundary and the model fallback remains float-based, so a versioned producer migration is required.",
        },
        {
            "path": "frontend/src/features/workbench/dashboard-home/adapters/buildHomeMarketContextModel.ts",
            "page": "dashboard-home",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Dashboard Home still formats Campisi plain-number amounts locally and also uses those values for contribution/drag conclusions; producer precision plus business-ranking semantics require owner-approved migration.",
        },
        {
            "path": "frontend/src/features/workbench/dashboard-home/dashboardHomeFirstScreenView.ts",
            "page": "dashboard-home",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Dashboard Home first-screen view still divides plain-number yuan values by 1e8 inside the view formatter, so the display path remains on the local compatibility boundary.",
        },
        {
            "path": "frontend/src/features/workbench/dashboard-home/dashboardHomeBodyView.ts",
            "page": "dashboard-home",
            "rule": "literal_div_1e8",
            "count": 1,
            "reason": "Dashboard Home body view still divides plain-number yuan values by 1e8 inside the view formatter, so the display path remains on the local compatibility boundary.",
        },
        {
            "path": "frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts",
            "page": "balance-analysis",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "The balance-analysis model keeps a raw-number yuan-to-yi fallback plus the owner-blocked reconciliation tolerance disclosure; the formal residual, ratio, status, and ranking paths remain outside this display-only migration.",
        },
    ]


def test_exact_numeric_policy_digest_binds_controlled_pages_paths_and_registry_sha() -> None:
    registry = load_exact_numeric_compat_registry()
    binding = build_exact_numeric_policy_binding(registry, rehearsal_only=True)
    policy = build_exact_numeric_policy(rehearsal_only=True)

    assert binding == {
        "policy_version": "exact-numeric-v1",
        "controlled_pages": registry["controlled_pages"],
        "controlled_paths": registry["controlled_paths"],
        "compat_registry_sha256": exact_numeric_compat_registry_sha256(registry),
        "release_eligible": False,
        "rehearsal_only": True,
    }
    assert policy["policy_sha256"] == canonical_sha256(binding)
    assert policy["compat_registry_sha256"] == binding["compat_registry_sha256"]
    assert policy["pending_migration_count"] == 13
    assert policy["active_exception_count"] == 0


def test_shared_amount_formatter_migration_keeps_the_path_controlled_and_release_closed() -> None:
    registry = load_exact_numeric_compat_registry()
    shared_path = "frontend/src/utils/format.ts"

    assert shared_path in registry["controlled_paths"]
    assert not any(
        entry["path"] == shared_path
        for entry in [*registry["pending_migrations"], *registry["active_exceptions"]]
    )
    source = (DEFAULT_REGISTRY_PATH.parents[1] / shared_path).read_text(encoding="utf-8")
    # The retired debt was number division in formatYi. The real controlled
    # producer now delegates to Decimal scaling; registry removal alone is not proof.
    assert "formatScaledAmount(raw, 100_000_000, 2)" in source
    assert "formatDecimalZh(amount.div(divisor), precision, grouped)" in source
    assert "if (typeof raw === \"number\") return Number.isFinite(raw) ? new Decimal(raw) : null;" in source
    assert registry["pending_migrations"]
    assert registry["release_eligible"] is False
    assert build_exact_numeric_policy(rehearsal_only=True)["release_eligible"] is False


def test_pending_migrations_require_release_gate_to_stay_closed() -> None:
    payload = deepcopy(load_exact_numeric_compat_registry(DEFAULT_REGISTRY_PATH))
    payload["release_eligible"] = True

    with pytest.raises(ValueError, match="release_eligible must stay false"):
        load_exact_numeric_compat_registry_payload(payload)


def test_active_exception_requires_owner_and_iso_expiry() -> None:
    payload = deepcopy(load_exact_numeric_compat_registry(DEFAULT_REGISTRY_PATH))
    payload["pending_migrations"] = []
    payload["release_eligible"] = True
    payload["active_exceptions"] = [
        {
            "path": "frontend/src/features/bond-dashboard/utils/format.ts",
            "page": "bond-dashboard",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "temporary approved compatibility",
        }
    ]

    with pytest.raises(ValueError, match="active exception owner is required"):
        load_exact_numeric_compat_registry_payload(payload)


def test_active_exception_rejects_placeholder_owner() -> None:
    payload = deepcopy(load_exact_numeric_compat_registry(DEFAULT_REGISTRY_PATH))
    payload["pending_migrations"] = []
    payload["release_eligible"] = True
    payload["active_exceptions"] = [
        {
            "path": "frontend/src/features/bond-dashboard/utils/format.ts",
            "page": "bond-dashboard",
            "rule": "literal_div_1e8",
            "count": 2,
            "reason": "temporary approved compatibility",
            "owner": "PENDING",
            "expires_on": "2999-12-31",
        }
    ]

    with pytest.raises(ValueError, match="owner must not be a placeholder"):
        load_exact_numeric_compat_registry_payload(payload)


def test_registry_rejects_duplicate_path_rule_baselines() -> None:
    payload = deepcopy(load_exact_numeric_compat_registry(DEFAULT_REGISTRY_PATH))
    payload["pending_migrations"].append(
        deepcopy(payload["pending_migrations"][0])
    )

    with pytest.raises(ValueError, match="path/rule entries must be unique"):
        load_exact_numeric_compat_registry_payload(payload)


def load_exact_numeric_compat_registry_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    from backend.app.governance import exact_numeric_policy as policy

    path = DEFAULT_REGISTRY_PATH.parent / "_tmp_exact_numeric_policy_test.json"
    try:
        _write_json(path, payload)
        return policy.load_exact_numeric_compat_registry(path)
    finally:
        path.unlink(missing_ok=True)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
