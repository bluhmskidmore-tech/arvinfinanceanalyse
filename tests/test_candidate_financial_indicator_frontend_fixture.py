from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules
from backend.app.schemas.candidate_financial_indicators import (
    CandidateFinancialIndicatorPayload,
)
from scripts.capture_candidate_financial_indicator_frontend_fixture import (
    _sanitize_capture,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "src"
    / "mocks"
    / "fixtures"
    / "ledgerPnlCandidateFinancialIndicators202606.json"
)


def _expected_ids(rules: dict[str, object]) -> list[str]:
    scale_rules = rules["scale_rules"]
    assert isinstance(scale_rules, list)
    metric_ids = [
        f"{rule['id']}::{basis}"
        for rule in scale_rules
        for basis in rule["available_bases"]
    ]
    for section in ("direct_rules", "manual_metrics", "derived_rules"):
        section_rules = rules[section]
        assert isinstance(section_rules, list)
        metric_ids.extend(rule["id"] for rule in section_rules)
    return metric_ids


def test_frontend_candidate_fixture_keeps_the_rule_catalog_without_real_values() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rules = load_finance_metric_rules()
    expected_ids = _expected_ids(rules)
    result = fixture["result"]

    assert fixture["fixture_kind"] == "synthetic_candidate_financial_indicator_demo"
    assert fixture["capture_status"] == "candidate_non_formal"
    assert fixture["result_meta"]["amount_currency_basis"] == "CNX"
    assert fixture["result_meta"]["evidence_rows"] == 186
    assert fixture["rule_hash"] == result["rule_hash"]
    assert fixture["rule_hash"] != rules["rule_hash"]
    assert result["basis"] == "ledger"
    assert result["metric_status"] == "candidate"
    assert result["formal_use_allowed"] is False
    assert result["currency"] == "CNX"
    assert result["calculation_status"] == "warning"
    assert result["source_alignment"] == "not_applicable"
    assert result["summary"]["metric_evaluated"] == 186
    assert [item["metric_id"] for item in result["metrics"]] == expected_ids
    assert set(fixture["lineage_by_metric"]) == set(expected_ids)
    assert not any(item["metric_id"].startswith("candidate.metric.") for item in result["metrics"])
    assert all(item["lineage"] == [] for item in result["metrics"])
    assert fixture["source_hashes"] == {
        item["source_kind"]: item["sha256"] for item in result["sources"]
    }
    assert all(item["locked_sha256"] is None for item in result["sources"])


def test_frontend_candidate_fixture_reconstructs_a_strict_full_lineage_payload() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload = fixture["result"]
    payload["include_lineage"] = True
    payload["idempotency_key"] = fixture["lineage_idempotency_key"]
    payload["promotion_readiness"]["candidate_idempotency_key"] = fixture[
        "lineage_idempotency_key"
    ]
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
        build_promotion_readiness_evidence_key,
    )

    readiness = payload["promotion_readiness"]
    readiness["readiness_evidence_key"] = build_promotion_readiness_evidence_key(
        candidate_idempotency_key=readiness["candidate_idempotency_key"],
        formal_contract_status=readiness["formal_contract_status"],
        checks=[
            {
                "check_id": check["check_id"],
                "status": check["status"],
                "evidence_refs": check["evidence_refs"],
            }
            for check in readiness["checks"]
        ],
    )
    pack = readiness["evidence_pack"]
    pack["candidate_idempotency_key"] = readiness["candidate_idempotency_key"]
    pack["readiness_evidence_key"] = readiness["readiness_evidence_key"]
    pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=pack,
    )
    for metric in payload["metrics"]:
        metric["lineage"] = fixture["lineage_by_metric"][metric["metric_id"]]

    validated = CandidateFinancialIndicatorPayload.model_validate(payload)
    metrics = {item.metric_id: item for item in validated.metrics}

    assert len(validated.metrics) == 186
    assert metrics["income.interest.net"].lineage
    assert metrics["income.noninterest.total"].lineage
    assert metrics["balance.deposit.corporate.total::point"].lineage
    assert validated.summary.manual_default_count == 19


def test_frontend_candidate_fixture_is_synthetic_and_contains_no_captured_finance_data() -> None:
    raw_fixture = FIXTURE_PATH.read_text(encoding="utf-8")
    fixture = json.loads(raw_fixture)

    for sensitive_marker in (
        "ledger_pnl_candidate_financial_indicators_frontend_demo_capture",
        "297175",
        "0ba128f1dca4084cfdf4aff410576f1945c11240a88778e00175cbc977e7493d",
        "49e9a5b06c30656aaa07ef583d459dfff514ddd478640b0fb6f0b355d9758498",
        "-93537785277.75",
        "57.3617558215",
        "综本!G314",
    ):
        assert sensitive_marker not in raw_fixture

    assert fixture["fixture_kind"] == "synthetic_candidate_financial_indicator_demo"
    assert set(fixture["source_hashes"]) == {"ledger", "daily"}
    assert all(len(value) == 64 for value in fixture["source_hashes"].values())
    account_lineage = [
        row
        for rows in fixture["lineage_by_metric"].values()
        for row in rows
        if row["lineage_type"] == "account"
    ]
    assert account_lineage
    assert all(row["code"].startswith("99") for row in account_lineage)
    assert all(
        evidence_ref.startswith("DEMO:")
        for row in account_lineage
        for evidence_ref in row["evidence_refs"]
    )


def test_sanitizer_allowlists_fields_instead_of_copying_future_capture_fields() -> None:
    captured = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    secret = "future-captured-finance-field"
    captured["result_meta"]["future_secret"] = secret
    captured["result"]["future_secret"] = secret
    captured["result"]["sources"][0]["future_secret"] = secret
    captured["result"]["metrics"][0]["future_secret"] = secret
    captured["result"]["validations"][0]["future_secret"] = secret
    captured["result"]["gaps"][0]["future_secret"] = secret
    captured["lineage_by_metric"][captured["result"]["metrics"][0]["metric_id"]][0][
        "future_secret"
    ] = secret

    sanitized = _sanitize_capture(captured)

    leaked_future_field = secret in json.dumps(sanitized, ensure_ascii=False)
    assert leaked_future_field is False


def test_synthetic_lineage_amounts_are_internally_consistent() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    metric_values = {
        metric["metric_id"]: metric["value"] for metric in fixture["result"]["metrics"]
    }

    for rows in fixture["lineage_by_metric"].values():
        for row in rows:
            if row["lineage_type"] == "account":
                expected = (
                    Decimal(row["raw_yuan"])
                    / Decimal("100000000")
                    * Decimal(row["weight"])
                )
                assert Decimal(row["contribution_yi"]) == expected
            elif row["lineage_type"] == "metric" and row["metric_value_yi"] is not None:
                assert row["metric_value_yi"] == metric_values[row["metric_id"]]
                expected = Decimal(row["metric_value_yi"]) * Decimal(row["weight"])
                assert Decimal(row["contribution_yi"]) == expected


def test_synthetic_metric_status_propagates_non_ok_dependencies() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    metric_statuses = {
        metric["metric_id"]: metric["status"] for metric in fixture["result"]["metrics"]
    }

    for metric_id, rows in fixture["lineage_by_metric"].items():
        has_non_ok_dependency = any(
            row["lineage_type"] == "metric" and row["dependency_status"] != "ok"
            for row in rows
        )
        if has_non_ok_dependency:
            assert metric_statuses[metric_id] != "ok"


def test_sanitizer_does_not_copy_captured_source_quality_state() -> None:
    captured = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    state_marker = "captured_state_leak"
    captured["result"]["metrics"][0].update(
        {"status": "warning", "reasons": [state_marker]}
    )
    captured["result"]["metrics"][1].update({"status": "error", "value": None})
    captured["result"]["validations"][0].update(
        {
            "validation_id": f"{state_marker}.validation",
            "severity": "warning",
            "passed": False,
            "message": state_marker,
        }
    )
    captured["result"]["gaps"] = [
        {
            "gap_id": f"{state_marker}.gap",
            "severity": "error",
            "kind": "calculation",
            "title": state_marker,
            "detail": state_marker,
            "metric_ids": [captured["result"]["metrics"][0]["metric_id"]],
        }
    ]
    all_lineage = [
        row for rows in captured["lineage_by_metric"].values() for row in rows
    ]
    next(row for row in all_lineage if row["lineage_type"] == "account")[
        "observed"
    ] = False
    next(row for row in all_lineage if row["lineage_type"] == "metric")[
        "dependency_status"
    ] = "error"

    sanitized = _sanitize_capture(captured)
    serialized = json.dumps(sanitized, ensure_ascii=False)

    leaked_source_state = state_marker in serialized
    assert leaked_source_state is False
    sanitized_statuses = {
        metric["metric_id"]: metric["status"]
        for metric in sanitized["result"]["metrics"]
    }
    assert all(
        status == "manual_default"
        for metric_id, status in sanitized_statuses.items()
        if metric_id.startswith("input.adjustment.")
    )
    assert all(
        status in {"ok", "warning"}
        for metric_id, status in sanitized_statuses.items()
        if not metric_id.startswith("input.adjustment.")
    )
    assert "error" not in sanitized_statuses.values()
    assert all(validation["passed"] for validation in sanitized["result"]["validations"])
    assert [gap["gap_id"] for gap in sanitized["result"]["gaps"]] == [
        "synthetic.source_unlocked",
        "synthetic.manual_defaults",
    ]
    sanitized_lineage = [
        row for rows in sanitized["lineage_by_metric"].values() for row in rows
    ]
    assert all(
        row["observed"] is True
        for row in sanitized_lineage
        if row["lineage_type"] == "account"
    )
    assert all(
        row["dependency_status"] == sanitized_statuses[row["metric_id"]]
        for row in sanitized_lineage
        if row["lineage_type"] == "metric"
    )
