from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.app.core_finance import finance_metric_engine
from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules
from backend.app.services.candidate_financial_indicator_service import (
    candidate_financial_indicator_envelope,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data_input" / "pnl_总账对账-日均"
CURRENT_RULE_VERSION = "qdb-finance-2026-v1.0.1"
HISTORICAL_RULE_VERSION = "qdb-finance-2026-v1.0.0"


def _source_hashes(rules: dict[str, object]) -> dict[str, str]:
    metadata = rules["metadata"]
    assert isinstance(metadata, dict)
    derived_from = metadata["derived_from"]
    assert isinstance(derived_from, list)
    return {
        str(item["file"]): str(item["sha256"])
        for item in derived_from
        if isinstance(item, dict)
    }


def test_default_rule_version_locks_the_current_202606_source_pair() -> None:
    rules = load_finance_metric_rules()
    source_hashes = _source_hashes(rules)

    assert rules["metadata"]["rule_version"] == CURRENT_RULE_VERSION
    for file_name in ("总账对账202606.xlsx", "日均202606.xlsx"):
        source_path = SOURCE_DIR / file_name
        assert source_hashes[file_name] == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_historical_rule_version_remains_available_for_replay() -> None:
    rules = load_finance_metric_rules(rule_version=HISTORICAL_RULE_VERSION)

    assert rules["metadata"]["rule_version"] == HISTORICAL_RULE_VERSION
    assert rules["rule_hash"] == "7f1b9d47dece2db850ef69cd9ab13b2520ad3bc09d6a2bce3a48ac6017777567"
    assert _source_hashes(rules)["总账对账202606.xlsx"].startswith("0ba128f1")


def test_v101_changes_only_version_provenance_and_the_ledger_source_lock() -> None:
    historical_path = finance_metric_engine.RULE_ASSETS[HISTORICAL_RULE_VERSION]
    current_path = finance_metric_engine.RULE_ASSETS[CURRENT_RULE_VERSION]
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    current = json.loads(current_path.read_text(encoding="utf-8"))

    current["metadata"]["rule_version"] = historical["metadata"]["rule_version"]
    current["metadata"]["generated_on"] = historical["metadata"]["generated_on"]
    current_ledger = next(
        item
        for item in current["metadata"]["derived_from"]
        if item["file"] == "总账对账202606.xlsx"
    )
    historical_ledger = next(
        item
        for item in historical["metadata"]["derived_from"]
        if item["file"] == "总账对账202606.xlsx"
    )
    current_ledger["sha256"] = historical_ledger["sha256"]

    assert current == historical


def test_named_rule_version_rejects_an_asset_with_different_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        finance_metric_engine.RULE_ASSETS,
        CURRENT_RULE_VERSION,
        finance_metric_engine.RULE_ASSETS[HISTORICAL_RULE_VERSION],
    )

    with pytest.raises(ValueError, match="requested rule_version"):
        load_finance_metric_rules(rule_version=CURRENT_RULE_VERSION)


def test_current_sources_pass_source_lock_without_becoming_formal() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    result = envelope["result"]

    assert result["rule_version"] == CURRENT_RULE_VERSION
    assert result["source_alignment"] == "matched"
    assert result["formal_use_allowed"] is False
    assert result["calculation_status"] == "warning"
    assert result["promotion_readiness"]["status"] == "blocked"
    assert result["promotion_readiness"]["blocking_count"] == 4
    assert result["summary"]["validation_warning_failed"] == 1
    assert result["summary"]["manual_default_count"] == 19
