from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
RULE_ASSET = ROOT / "backend" / "app" / "core_finance" / "qdb_finance_2026_v1_0_1.json"
EXPECTED_RULE_HASH = "c67f4c85390992a1929bcff65c2bbdbd5c5c382912af3ebcd49297b1e7ac6a66"
EXPECTED_METADATA = {
    "rule_version": "qdb-finance-2026-v1.0.1",
    "schema_version": "1.0",
    "currency": "CNX",
    "raw_amount_unit": "元",
    "output_amount_unit": "亿元",
    "conversion_divisor": "100000000",
}
EXPECTED_SOURCE_HASHES = {
    "2026年财务指标表-3月最终(2).xlsx": "73d475d77d04a89d9d7eae5b9853ef5b604c413625eb308c1af9fd175aa17aeb",
    "总账对账202606.xlsx": "29717578b92e107cc2fbcd5b66cd7c63191c24e1a7d245c103c94e235331c0b7",
    "日均202606.xlsx": "49e9a5b06c30656aaa07ef583d459dfff514ddd478640b0fb6f0b355d9758498",
}
EXPECTED_VALIDATION_IDS = (
    "period.same_end_date",
    "period.ytd_starts_jan1",
    "period.month_is_calendar_month",
    "currency.cnx_only",
    "ledger.balance_identity",
    "ledger.duplicate_full_code",
    "rules.missing_accounts",
    "recon.company_deposit",
    "recon.retail_deposit",
    "recon.personal_loan",
    "recon.loan_interest",
    "recon.noninterest",
)
EXPECTED_SECTION_COUNTS = {
    "scale_rules": 19,
    "direct_rules": 75,
    "manual_metrics": 19,
    "derived_rules": 35,
}


def _load_rules(path: Path | None = None) -> dict[str, Any]:
    try:
        from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules
    except ModuleNotFoundError:
        pytest.fail("finance metric rule loader is not implemented")
    return load_finance_metric_rules(path)


def _mutable_rules() -> dict[str, Any]:
    return json.loads(RULE_ASSET.read_text(encoding="utf-8"))


def _write_rules(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "metric_rules.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _expanded_output_ids(rules: dict[str, Any]) -> list[str]:
    expanded = [
        f"{rule['id']}::{basis}"
        for rule in rules["scale_rules"]
        for basis in rule["available_bases"]
    ]
    expanded.extend(rule["id"] for rule in rules["direct_rules"])
    expanded.extend(rule["id"] for rule in rules["manual_metrics"])
    expanded.extend(rule["id"] for rule in rules["derived_rules"])
    return expanded


def test_frozen_finance_metric_rules_have_expected_contract_and_hash() -> None:
    assert RULE_ASSET.is_file(), "frozen qdb-finance rule asset is missing"

    rules = _load_rules()

    assert rules["rule_hash"] == EXPECTED_RULE_HASH
    assert {key: rules["metadata"][key] for key in EXPECTED_METADATA} == EXPECTED_METADATA
    assert {
        item["file"]: item["sha256"]
        for item in rules["metadata"]["derived_from"]
    } == EXPECTED_SOURCE_HASHES
    assert tuple(rule["id"] for rule in rules["validation_rules"]) == EXPECTED_VALIDATION_IDS
    assert {section: len(rules[section]) for section in EXPECTED_SECTION_COUNTS} == EXPECTED_SECTION_COUNTS
    expanded_ids = _expanded_output_ids(rules)
    assert len(expanded_ids) == 186
    assert len(expanded_ids) == len(set(expanded_ids))


def test_rule_loader_rejects_structurally_valid_unapproved_rule_bytes(
    tmp_path: Path,
) -> None:
    payload = _mutable_rules()
    payload["scale_rules"][0]["name"] += "-changed"
    changed_asset = _write_rules(tmp_path, payload)
    changed_hash = hashlib.sha256(changed_asset.read_bytes()).hexdigest()

    with pytest.raises(ValueError) as exc_info:
        _load_rules(changed_asset)

    message = str(exc_info.value)
    assert changed_hash in message
    assert EXPECTED_RULE_HASH in message
    assert "upgrade metadata.rule_version" in message


@pytest.mark.parametrize("field", ["code", "weight"])
def test_rule_loader_rejects_non_string_term_fields(tmp_path: Path, field: str) -> None:
    payload = _mutable_rules()
    payload["scale_rules"][0]["terms_by_basis"]["point"][0][field] = 201

    with pytest.raises(ValueError, match=rf"{field} must be a string"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_rejects_wrong_metadata(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["metadata"] = deepcopy(payload["metadata"])
    payload["metadata"]["rule_version"] = "qdb-finance-2026-v9.0.0"

    with pytest.raises(ValueError, match="metadata.rule_version"):
        _load_rules(_write_rules(tmp_path, payload))


@pytest.mark.parametrize("source_file", tuple(EXPECTED_SOURCE_HASHES))
def test_rule_loader_rejects_changed_source_hash(tmp_path: Path, source_file: str) -> None:
    payload = _mutable_rules()
    source = next(item for item in payload["metadata"]["derived_from"] if item["file"] == source_file)
    source["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="metadata.derived_from source records"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_rejects_duplicate_expanded_output_id(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["direct_rules"][1]["id"] = payload["direct_rules"][0]["id"]

    with pytest.raises(ValueError, match="expanded output IDs must be unique"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_requires_twelve_validation_rules(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["validation_rules"].pop()

    with pytest.raises(ValueError, match="validation_rules must contain exactly 12 rules"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_rejects_duplicate_validation_id(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["validation_rules"][1]["id"] = payload["validation_rules"][0]["id"]

    with pytest.raises(ValueError, match="validation rule IDs must match the frozen contract"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_rejects_replaced_validation_id(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["validation_rules"][-1]["id"] = "recon.replaced"

    with pytest.raises(ValueError, match="validation rule IDs must match the frozen contract"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_requires_186_expanded_outputs(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["derived_rules"].pop()

    with pytest.raises(ValueError, match="expanded output count must be 186"):
        _load_rules(_write_rules(tmp_path, payload))


def test_rule_loader_rejects_section_count_drift_with_same_total_outputs(tmp_path: Path) -> None:
    payload = _mutable_rules()
    payload["derived_rules"].append(payload["direct_rules"].pop())

    with pytest.raises(ValueError, match="direct_rules must contain exactly 75 rules"):
        _load_rules(_write_rules(tmp_path, payload))
