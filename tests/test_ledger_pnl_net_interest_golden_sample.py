from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.core_finance.finance_metric_xlsx import (
    FinanceMetricLedgerOnlySourceData,
    LedgerObservation,
    PeriodEvidence,
)
from backend.app.services import (
    candidate_financial_indicator_period_comparison_service as service,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ID = "GS-LEDGER-PNL-NET-INTEREST-202606-A"
SAMPLE_DIR = ROOT / "tests" / "golden_samples" / SAMPLE_ID
SOURCE_DIR = ROOT / "data_input" / "pnl_总账对账-日均"
SYNTHETIC_REPLAY_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "ledger_pnl"
    / "net_interest_202606_normalized_replay.json"
)
SYNTHETIC_REPLAY_FIXTURE_SHA256 = (
    "8290c7cb48399a422e7dcd5b3e183652651d06d88622fddcc28d994745665b10"
)
REAL_LEDGER_WORKBOOKS = tuple(
    SOURCE_DIR / f"总账对账{month}.xlsx"
    for month in ("202604", "202605", "202606")
)
COMPONENT_IDS = (
    "income.interest.loan.total",
    "expense.interest.deposit.total",
    "income.interest.investment",
    "income.interest.interbank_net",
)


def _load_json(name: str) -> dict[str, object]:
    return json.loads((SAMPLE_DIR / name).read_text(encoding="utf-8"))


def _load_synthetic_replay_fixture() -> dict[str, Any]:
    fixture_bytes = SYNTHETIC_REPLAY_FIXTURE.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == SYNTHETIC_REPLAY_FIXTURE_SHA256
    return json.loads(fixture_bytes.decode("utf-8"))


def _synthetic_replay_sources(
    fixture: dict[str, Any],
) -> dict[str, FinanceMetricLedgerOnlySourceData]:
    account_specs: dict[str, dict[str, Any]] = {}
    yi_divisor = Decimal("100000000")

    def add_component_account(
        *,
        account_code: str,
        contribution_yi: str,
        component_weight: str,
        formula_weight: int,
        current_row: int,
    ) -> None:
        ending_202606 = (
            Decimal(contribution_yi)
            * yi_divisor
            / (Decimal(component_weight) * Decimal(formula_weight))
        )
        assert account_code not in account_specs
        account_specs[account_code] = {
            "current_row": current_row,
            "ending_by_month": {
                "202604": Decimal(0),
                "202605": Decimal(0),
                "202606": ending_202606,
            },
        }

    for component in fixture["components"]:
        component_weight = str(component["effective_component_weight"])
        formula_weight = int(component["formula_weight"])
        add_component_account(
            account_code=str(component["top_account_code"]),
            contribution_yi=str(component["top_contribution_yi"]),
            component_weight=component_weight,
            formula_weight=formula_weight,
            current_row=int(component["top_current_row"]),
        )
        prefix = str(component["filler_code_prefix"])
        row_start = int(component["filler_current_row_start"])
        regular_count = int(component["regular_filler_count"])
        for index in range(1, regular_count + 1):
            add_component_account(
                account_code=f"{prefix}{index:07d}",
                contribution_yi=str(component["regular_filler_contribution_yi"]),
                component_weight=component_weight,
                formula_weight=formula_weight,
                current_row=row_start + index - 1,
            )
        add_component_account(
            account_code=f"{prefix}{regular_count + 1:07d}",
            contribution_yi=str(component["remainder_filler_contribution_yi"]),
            component_weight=component_weight,
            formula_weight=formula_weight,
            current_row=row_start + regular_count,
        )
        shared_offset = component.get("shared_offset_account_code")
        if shared_offset is not None and str(shared_offset) not in account_specs:
            offset_endings = component["shared_offset_ending_yuan_by_month"]
            account_specs[str(shared_offset)] = {
                "current_row": int(component["shared_offset_current_row"]),
                "ending_by_month": {
                    month: Decimal(str(ending))
                    for month, ending in offset_endings.items()
                },
            }

    for item in fixture["supporting_point_accounts"]:
        account_code = str(item["account_code"])
        assert account_code not in account_specs
        ending = Decimal(str(item["ending_yuan"]))
        account_specs[account_code] = {
            "current_row": int(item["current_row"]),
            "ending_by_month": {
                "202604": ending,
                "202605": ending,
                "202606": ending,
            },
        }

    row_offsets = {"202604": 200, "202605": 100, "202606": 0}
    sources: dict[str, FinanceMetricLedgerOnlySourceData] = {}
    for period in fixture["source_periods"]:
        report_month = str(period["month"])
        report_date = date.fromisoformat(str(period["report_date"]))
        observations = tuple(
            LedgerObservation(
                source="main",
                sheet="综本",
                row=int(spec["current_row"]) + row_offsets[report_month],
                account_code=account_code,
                account_name=f"Synthetic fixture account {account_code}",
                currency="CNX",
                opening=Decimal(0),
                debit=Decimal(0),
                credit=Decimal(0),
                ending=spec["ending_by_month"][report_month],
                cell_refs=(
                    (
                        service.LEDGER_HEADERS[0],
                        f"A{int(spec['current_row']) + row_offsets[report_month]}",
                    ),
                    (
                        service.LEDGER_HEADERS[-1],
                        f"G{int(spec['current_row']) + row_offsets[report_month]}",
                    ),
                ),
            )
            for account_code, spec in sorted(account_specs.items())
        )
        sources[report_month] = FinanceMetricLedgerOnlySourceData(
            report_month=report_month,
            report_date=report_date,
            ledger_sha256=str(period["ledger_sha256"]),
            ledger=observations,
            period=PeriodEvidence(
                evidence_id=f"synthetic-{report_month}",
                sheet="综本",
                cell_ref="A1",
                raw_text=f"synthetic {report_month}",
                start=report_date.replace(day=1),
                end=report_date,
            ),
            issues=(),
        )
    return sources


def _install_synthetic_replay(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    fixture = _load_synthetic_replay_fixture()
    sources = _synthetic_replay_sources(fixture)
    for report_month in sources:
        (tmp_path / f"总账对账{report_month}.xlsx").write_bytes(b"synthetic replay")
    (tmp_path / "日均202605.xlsx").write_bytes(b"synthetic replay")

    def parse_synthetic_source(
        ledger_path: str | Path,
        *,
        requested_month: str,
    ) -> FinanceMetricLedgerOnlySourceData:
        assert Path(ledger_path).parent == tmp_path
        return sources[requested_month]

    monkeypatch.setattr(
        service,
        "parse_finance_metric_ledger_only_source",
        parse_synthetic_source,
    )
    monkeypatch.setattr(
        service,
        "read_xlsx",
        lambda _path: SimpleNamespace(sheets={"年": object(), "月": object()}),
    )
    return fixture


def _rows_digest(rows: list[dict[str, object]]) -> str:
    canonical = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _capture_snapshot(*, source_dir: Path = SOURCE_DIR) -> dict[str, object]:
    parent = service.candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(source_dir),
        report_month="202606",
    )
    bridge = parent["net_interest_component_bridge"]
    components: list[dict[str, object]] = []
    for metric_id in COMPONENT_IDS:
        detail = service.candidate_financial_indicator_component_detail_envelope(
            source_dir=str(source_dir),
            report_month="202606",
            metric_id=metric_id,
            parent_idempotency_key=parent["idempotency_key"],
        )
        contributing = [
            row for row in detail["rows"] if row["row_status"] == "contributing"
        ]
        top = contributing[0]
        component: dict[str, object] = {
            "metric_id": metric_id,
            "formula_weight": detail["formula_weight"],
            "quality_status": detail["quality_status"],
            "foot_status": detail["foot_status"],
            "contributing_account_count": len(contributing),
            "account_contribution_total_yi": detail["account_contribution_total_yi"],
            "contribution_reconciliation_yi": detail["contribution_reconciliation_yi"],
            "rows_sha256": _rows_digest(detail["rows"]),
            "top_contributor": {
                "account_code": top["account_code"],
                "contribution_to_net_delta_yi": top[
                    "contribution_to_net_delta_yi"
                ],
                "current_locator": (
                    f"{top['source_evidence'][0]['sheet']}!"
                    f"{top['source_evidence'][0]['ending_cell']}"
                ),
            },
        }
        if metric_id == "income.interest.interbank_net":
            offset = next(
                row
                for row in detail["rows"]
                if row["account_code"] == "50206000001"
            )
            component["excluded_offset"] = {
                "account_code": offset["account_code"],
                "row_status": offset["row_status"],
                "effective_component_weight": offset["effective_component_weight"],
                "effective_net_weight": offset["effective_net_weight"],
            }
        components.append(component)

    return {
        "sample_contract_version": "ledger-pnl-net-interest-golden-v1",
        "sample_id": SAMPLE_ID,
        "report_month": parent["report_month"],
        "rule_version": parent["rule_version"],
        "source_periods": parent["source_periods"],
        "full_scope_status": parent["full_scope_status"],
        "full_scope_reason_code": parent["full_scope_reason_code"],
        "bridge": {
            "quality_status": bridge["quality_status"],
            "foot_status": bridge["foot_status"],
            "net_delta_yi": bridge["net_delta_yi"],
            "component_contribution_total_yi": bridge[
                "component_contribution_total_yi"
            ],
            "reconciliation_delta_yi": bridge["reconciliation_delta_yi"],
        },
        "components": components,
        "governance": {
            "sample_status": "captured-awaiting-approval",
            "owner": "TBD",
            "approver": "TBD",
            "metric_status": parent["metric_status"],
            "formal_use_allowed": parent["formal_use_allowed"],
            "certification_effect": parent["certification_effect"],
            "driver_status": parent["driver_status"],
        },
    }


def _without_rows_digests(snapshot: dict[str, object]) -> dict[str, object]:
    projected = deepcopy(snapshot)
    for component in projected["components"]:  # type: ignore[index]
        component.pop("rows_sha256")
    return projected


def test_net_interest_golden_sample_is_capture_ready_and_reconciled() -> None:
    for name in ("request.json", "response.json", "assertions.md", "approval.md"):
        assert (SAMPLE_DIR / name).is_file()
    request = _load_json("request.json")
    response = _load_json("response.json")
    approval = (SAMPLE_DIR / "approval.md").read_text(encoding="utf-8")

    assert request["report_month"] == response["report_month"] == "202606"
    assert response["bridge"]["quality_status"] == "standard_candidate"
    assert response["bridge"]["foot_status"] == "passed"
    assert Decimal(response["bridge"]["net_delta_yi"]) == Decimal(
        response["bridge"]["component_contribution_total_yi"]
    )
    assert Decimal(response["bridge"]["reconciliation_delta_yi"]) == 0
    assert sum(
        Decimal(component["account_contribution_total_yi"])
        for component in response["components"]
    ) == Decimal(response["bridge"]["net_delta_yi"])
    assert [component["contributing_account_count"] for component in response["components"]] == [
        21,
        14,
        18,
        19,
    ]
    assert [component["metric_id"] for component in response["components"]] == list(
        COMPONENT_IDS
    )
    assert all(period["lock_status"] == "locked_match" for period in response["source_periods"])
    assert {
        period["month"]: period["ledger_sha256"]
        for period in response["source_periods"]
    } == {
        "202606": "29717578b92e107cc2fbcd5b66cd7c63191c24e1a7d245c103c94e235331c0b7",
        "202605": "dabefcb6b713d0a427bb09d53673940ecd5df8b98051c61592b0c89b3d505224",
        "202604": "6b59d7b41b9b11aa8bff431b9d33e353b20751b024e959327dae619a2b84e977",
    }
    assert [
        component["account_contribution_total_yi"]
        for component in response["components"]
    ] == [
        "-0.3473924741",
        "0.0830909629",
        "-1.7260319538",
        "-0.5727880768",
    ]
    assert [component["rows_sha256"] for component in response["components"]] == [
        "e92473871f4768c200eec5fbec674c943512b961a816af74e1028a4c08bafda0",
        "17972a75ffe85500a13bc2b2786eef78c058359f410e4acdbd798efba73e771f",
        "e1938c17c95666c1ff4ccb0581fc5f1bccc42f54150297acb313ed434df2cfa3",
        "4385913de9f039365fd61f833dd4c0ea461bae0c15501462daad9fa5237cdb4b",
    ]
    assert [
        (
            component["top_contributor"]["account_code"],
            component["top_contributor"]["contribution_to_net_delta_yi"],
        )
        for component in response["components"]
    ] == [
        ("50106000001", "-0.1047455527"),
        ("52101000001", "-0.1264796803"),
        ("51402010003", "-1.3160266974"),
        ("52201000001", "-0.7223470174"),
    ]
    assert response["components"][2]["top_contributor"]["current_locator"] == "综本!G1041"
    assert response["components"][3]["excluded_offset"] == {
        "account_code": "50206000001",
        "row_status": "excluded_offset",
        "effective_component_weight": "0",
        "effective_net_weight": "0",
    }
    assert response["full_scope_reason_code"] == "missing_required_sheet"
    assert response["governance"] == {
        "sample_status": "captured-awaiting-approval",
        "owner": "TBD",
        "approver": "TBD",
        "metric_status": "candidate",
        "formal_use_allowed": False,
        "certification_effect": "none",
        "driver_status": "unclear",
    }
    assert "captured-awaiting-approval" in approval
    assert "Owner: `TBD`" in approval
    assert "Approver: `TBD`" in approval


def test_committed_synthetic_fixture_executes_the_production_calculation_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _install_synthetic_replay(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    actual = _capture_snapshot(source_dir=tmp_path)
    expected = _load_json("response.json")

    assert fixture["data_classification"] == "synthetic_aggregate_preserving"
    assert fixture["retained_compact_evidence"] == (
        "previously_disclosed_account_codes_contributions_and_current_locators_only"
    )
    assert fixture["source_hash_role"] == "governed_identity_anchor_only"
    assert fixture["account_name_policy"] == "synthetic_placeholder"
    assert len(fixture["supporting_point_accounts"]) == 25
    assert _without_rows_digests(actual) == _without_rows_digests(expected)
    assert {
        component["metric_id"]: component["rows_sha256"]
        for component in actual["components"]
    } == fixture["expected_synthetic_rows_sha256"]


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_real_net_interest_source_replay_matches_the_capture_ready_snapshot() -> None:
    assert _capture_snapshot() == _load_json("response.json")
