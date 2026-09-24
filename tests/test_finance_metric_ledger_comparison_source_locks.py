from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from backend.app.core_finance import finance_metric_ledger_comparison_source_locks as source_locks
from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules


EXPECTED_LOCKS = {
    "202604": "6b59d7b41b9b11aa8bff431b9d33e353b20751b024e959327dae619a2b84e977",
    "202605": "dabefcb6b713d0a427bb09d53673940ecd5df8b98051c61592b0c89b3d505224",
    "202606": "29717578b92e107cc2fbcd5b66cd7c63191c24e1a7d245c103c94e235331c0b7",
}


def test_ledger_comparison_source_lock_asset_is_pinned_and_scope_limited() -> None:
    contract = source_locks.load_finance_metric_ledger_comparison_source_locks()

    assert contract["contract_version"] == "ledger-comparison-source-locks-v1"
    assert contract["lock_version"] == "qdb-ledger-comparison-source-locks-2026-v1.0.0"
    assert contract["scope"] == "ledger_only_key_metrics_and_component_detail"
    assert contract["compatible_rule_version"] == "qdb-finance-2026-v1.0.1"
    assert contract["sheet"] == "综本"
    assert contract["currency"] == "CNX"
    assert contract["value_basis"] == "ending_balance"
    assert contract["formal_use_allowed"] is False
    assert contract["certification_effect"] == "none"
    assert contract["asset_sha256"] == source_locks.PINNED_LOCK_ASSET_SHA256
    assert {
        record["report_month"]: record["sha256"]
        for record in contract["records"]
    } == EXPECTED_LOCKS


def test_ledger_comparison_202606_lock_matches_the_active_rule_source_evidence() -> None:
    contract = source_locks.load_finance_metric_ledger_comparison_source_locks()
    rules = load_finance_metric_rules(rule_version="qdb-finance-2026-v1.0.1")
    rule_hash = next(
        item["sha256"]
        for item in rules["metadata"]["derived_from"]
        if item["file"] == "总账对账202606.xlsx"
    )
    manifest_hash = next(
        record["sha256"]
        for record in contract["records"]
        if record["report_month"] == "202606"
    )

    assert manifest_hash == rule_hash == EXPECTED_LOCKS["202606"]


def test_ledger_comparison_source_lock_asset_byte_drift_fails_closed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drifted = tmp_path / "source-locks.json"
    drifted.write_bytes(source_locks.LOCK_ASSET.read_bytes() + b"\n")
    monkeypatch.setattr(source_locks, "LOCK_ASSET", drifted)

    with pytest.raises(ValueError, match="asset SHA-256"):
        source_locks.load_finance_metric_ledger_comparison_source_locks()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda payload: payload["records"].append(deepcopy(payload["records"][0])),
            "unique report months and files",
        ),
        (
            lambda payload: payload["records"][0].update({"sha256": "A" * 64}),
            "lowercase SHA-256",
        ),
        (
            lambda payload: payload["records"][0].update({"file": "总账对账202605.xlsx"}),
            "file/report month/report date",
        ),
        (
            lambda payload: payload["records"][0].update({"report_date": "2026-04-29"}),
            "file/report month/report date",
        ),
        (
            lambda payload: payload["records"][2].update({"sha256": "0" * 64}),
            "active rule source evidence",
        ),
    ],
)
def test_ledger_comparison_source_lock_asset_rejects_invalid_records(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    payload = json.loads(source_locks.LOCK_ASSET.read_text(encoding="utf-8"))
    mutate(payload)
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    invalid = tmp_path / "source-locks.json"
    invalid.write_bytes(raw)
    monkeypatch.setattr(source_locks, "LOCK_ASSET", invalid)
    monkeypatch.setattr(
        source_locks,
        "PINNED_LOCK_ASSET_SHA256",
        hashlib.sha256(raw).hexdigest(),
    )

    with pytest.raises(ValueError, match=message):
        source_locks.load_finance_metric_ledger_comparison_source_locks()
