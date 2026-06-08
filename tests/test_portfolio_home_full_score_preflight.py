from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_full_score_preflight.py"
REPORT_DATE = "2026-05-31"


def _run_preflight(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _run_preflight_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def test_portfolio_home_full_score_preflight_reports_blocked_owner_matrix() -> None:
    preflight = build_preflight_for_test(limit=3)

    assert preflight["preflight_status"] == "blocked"
    assert preflight["current_score"] == "99.86 / 100"
    assert preflight["remaining_gap"] == "0.14"
    assert preflight["full_score_ready"] is False
    assert preflight["score_blockers"] == [
        "risk_tensor_quality_warning",
        "krd_contract_decision_required",
        "bond_maturity_date_remediation_required",
        "tyw_liability_maturity_date_remediation_required",
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
        "business_owner_approval",
        "owner_decision_intake_blocked",
    ]
    assert preflight["evidence_scope"] == {
        "read_only": True,
        "writes_database": False,
        "fills_owner_decisions": False,
        "captures_approval": False,
        "approves_metric_or_page": False,
        "changes_score": False,
        "certification_effect": "none",
    }

    blockers = {
        str(item["blocker"]): item
        for item in preflight["blocker_matrix"]
    }
    assert set(blockers) == set(preflight["score_blockers"])
    assert blockers["krd_contract_decision_required"]["owner"] == "risk_owner"
    assert blockers["krd_contract_decision_required"]["closure_status"] == "blocked"
    assert blockers["krd_contract_decision_required"]["strict_gate_command"] == (
        "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean"
    )
    assert blockers["bond_maturity_date_remediation_required"]["owner"] == "data_owner"
    assert blockers["bond_maturity_date_remediation_required"]["current_evidence"] == {
        "missing_maturity_rows": 114,
        "missing_maturity_market_value": "37622164239.83000008",
        "candidate_evidence_status": "no_candidates",
    }
    assert blockers["tyw_liability_maturity_date_remediation_required"]["current_evidence"] == {
        "missing_maturity_rows": 1455,
        "missing_maturity_principal": "43822652393.01000002",
        "candidate_evidence_status": "no_candidates",
    }
    assert blockers["business_owner_approval"]["owner"] == "business_owner"
    assert blockers["business_owner_approval"]["closure_status"] == "blocked"
    assert blockers["owner_decision_intake_blocked"]["owner"] == "business_owner"

    assert preflight["owner_routes"] == [
        {
            "owner": "risk_owner",
            "status": "blocked",
            "blockers": [
                "risk_tensor_quality_warning",
                "krd_contract_decision_required",
                "risk_tensor_warning_mismatch",
            ],
        },
        {
            "owner": "data_owner",
            "status": "blocked",
            "blockers": [
                "bond_maturity_date_remediation_required",
                "tyw_liability_maturity_date_remediation_required",
                "duration_exclusion_warning_mismatch",
            ],
        },
        {
            "owner": "business_owner",
            "status": "blocked",
            "blockers": [
                "business_owner_approval",
                "owner_decision_intake_blocked",
            ],
        },
    ]


def test_portfolio_home_full_score_preflight_markdown_summarizes_owner_boundaries() -> None:
    from scripts.portfolio_home_full_score_preflight import render_markdown

    markdown = render_markdown(_minimal_preflight_for_markdown())

    assert "# Portfolio Home Full-Score Preflight" in markdown
    assert "- Page: `PAGE-PORTFOLIO-HOME-001` (`portfolio`)" in markdown
    assert "- Report date: `2026-05-31`" in markdown
    assert "- Preflight status: `blocked`" in markdown
    assert "- Current score: `99.86 / 100`" in markdown
    assert "- Remaining gap: `0.14`" in markdown
    assert "- Full score ready: `false`" in markdown
    assert "This preflight is read-only and is not an approval." in markdown
    assert "- Writes database: `false`" in markdown
    assert "- Captures approval: `false`" in markdown
    assert "- Changes score: `false`" in markdown
    assert "- Candidate boundary status: `no_candidates`" in markdown
    assert "- Candidate strict gate effect: `none`" in markdown
    assert "- Candidate fills maturity date: `false`" in markdown
    assert "## Owner Routes" in markdown
    assert "- `risk_owner`: `blocked` - `risk_tensor_quality_warning`, `krd_contract_decision_required`" in markdown
    assert "- `data_owner`: `blocked` - `bond_maturity_date_remediation_required`" in markdown
    assert "- `business_owner`: `blocked` - `business_owner_approval`" in markdown
    assert "## Blocker Matrix" in markdown
    assert "| risk_tensor_quality_warning | risk_owner | blocked | `python scripts/risk.py --require-clean` | Recompute risk tensor. | Risk tensor quality is ok. |" in markdown
    assert "| bond_maturity_date_remediation_required | data_owner | blocked | `python scripts/maturity.py --require-empty` | Fill source maturity dates. | Queue is empty or signed exclusion exists. |" in markdown
    assert "## Current Evidence" in markdown
    assert "### risk_tensor_quality_warning" in markdown
    assert "- `decision_status`: `blocked`" in markdown
    assert "### bond_maturity_date_remediation_required" in markdown
    assert "- `missing_maturity_rows`: `114`" in markdown
    assert "## Required Final Gate" in markdown
    assert "`python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`" in markdown


def test_portfolio_home_full_score_preflight_markdown_compacts_nested_current_evidence() -> None:
    from scripts.portfolio_home_full_score_preflight import render_markdown

    preflight = _minimal_preflight_for_markdown()
    matrix = preflight["blocker_matrix"]
    assert isinstance(matrix, list)
    first_row = matrix[0]
    assert isinstance(first_row, dict)
    evidence = first_row["current_evidence"]
    assert isinstance(evidence, dict)
    evidence["duration_exclusion_delta_detail"] = {
        "status": "mismatch",
        "delta": {"market_value_sum": "791193600.00000000"},
        "top_recomputed_rows_by_market_value": [
            {"instrument_code": "BOND-1"},
            {"instrument_code": "BOND-2"},
        ],
    }

    markdown = render_markdown(preflight)

    assert "- `duration_exclusion_delta_detail.status`: `mismatch`" in markdown
    assert "- `duration_exclusion_delta_detail.delta.market_value_sum`: `791193600.00000000`" in markdown
    assert "- `duration_exclusion_delta_detail.top_recomputed_rows_by_market_value`: `2 rows`" in markdown
    assert "BOND-1" not in markdown


def test_portfolio_home_full_score_preflight_cli_can_emit_markdown_without_unblocking() -> None:
    completed = _run_preflight_raw("--limit", "3", "--format", "markdown", "--require-full-score-ready")

    assert completed.returncode == 1
    assert "# Portfolio Home Full-Score Preflight" in completed.stdout
    assert "- Preflight status: `blocked`" in completed.stdout
    assert "- Full score ready: `false`" in completed.stdout
    assert "This preflight is read-only and is not an approval." in completed.stdout
    assert "- Candidate boundary status: `no_candidates`" in completed.stdout
    assert "risk_tensor_quality_warning" in completed.stdout
    assert completed.stderr == ""


def test_portfolio_home_full_score_preflight_cli_requires_full_score_when_requested() -> None:
    returncode, payload = _run_preflight("--limit", "3", "--require-full-score-ready")

    assert returncode == 1
    assert payload["preflight_status"] == "blocked"
    assert payload["full_score_ready"] is False
    assert payload["required_next_command"] == (
        "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
    )


def test_portfolio_home_full_score_preflight_summarizes_candidate_rows_without_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "candidate.duckdb"
    _create_candidate_db(duckdb_path)

    import scripts.portfolio_home_full_score_preflight as preflight_mod

    monkeypatch.setattr(
        preflight_mod,
        "build_scorecard",
        lambda **_: _minimal_scorecard(),
    )
    monkeypatch.setattr(
        preflight_mod,
        "build_risk_warning",
        lambda **_: _minimal_risk_warning(),
    )
    monkeypatch.setattr(
        preflight_mod,
        "build_intake_check",
        lambda **_: _minimal_intake_check(),
    )

    preflight = preflight_mod.build_preflight(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        limit=3,
    )

    assert preflight["preflight_status"] == "blocked"
    assert preflight["candidate_boundary"] == {
        "status": "candidate_found",
        "strict_gate_effect": "none",
        "approves_metric_or_page": False,
        "fills_maturity_date": False,
        "writes_database": False,
    }
    blockers = {
        str(item["blocker"]): item
        for item in preflight["blocker_matrix"]
    }
    assert blockers["bond_maturity_date_remediation_required"]["current_evidence"] == {
        "missing_maturity_rows": 1,
        "missing_maturity_market_value": "100.00000000",
        "candidate_evidence_status": "candidate_found",
    }
    assert blockers["tyw_liability_maturity_date_remediation_required"]["current_evidence"] == {
        "missing_maturity_rows": 1,
        "missing_maturity_principal": "30.00000000",
        "candidate_evidence_status": "candidate_found",
    }


def _minimal_scorecard() -> dict[str, object]:
    score_blockers = [
        "risk_tensor_quality_warning",
        "krd_contract_decision_required",
        "bond_maturity_date_remediation_required",
        "tyw_liability_maturity_date_remediation_required",
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
        "business_owner_approval",
        "owner_decision_intake_blocked",
    ]
    return {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "current_score": "99.86 / 100",
        "remaining_gap": "0.14",
        "full_score_ready": False,
        "score_status": "blocked",
        "score_blockers": score_blockers,
        "score_blocker_actions": [
            {
                "blocker": blocker,
                "owner": "test_owner",
                "next_action": f"close {blocker}",
                "evidence_command": f"test command for {blocker}",
                "exit_criteria": f"{blocker} closes",
            }
            for blocker in score_blockers
        ],
        "gates": {
            "krd_contract": {
                "status": "decision_required",
                "blockers": ["krd_contract_decision_required"],
            },
            "business_owner_approval": {
                "status": "pending",
                "blockers": ["business_owner_approval"],
                "approval_action_item_count": 1,
            },
        },
    }


def _minimal_preflight_for_markdown() -> dict[str, object]:
    return {
        "check_kind": "portfolio_home_full_score_preflight",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": REPORT_DATE,
        "duckdb_path": "data/moss.duckdb",
        "preflight_status": "blocked",
        "current_score": "99.86 / 100",
        "remaining_gap": "0.14",
        "full_score_ready": False,
        "score_status": "blocked",
        "score_blockers": [
            "risk_tensor_quality_warning",
            "krd_contract_decision_required",
            "bond_maturity_date_remediation_required",
            "business_owner_approval",
        ],
        "evidence_scope": {
            "read_only": True,
            "writes_database": False,
            "fills_owner_decisions": False,
            "captures_approval": False,
            "approves_metric_or_page": False,
            "changes_score": False,
            "certification_effect": "none",
        },
        "candidate_boundary": {
            "status": "no_candidates",
            "strict_gate_effect": "none",
            "approves_metric_or_page": False,
            "fills_maturity_date": False,
            "writes_database": False,
        },
        "owner_routes": [
            {
                "owner": "risk_owner",
                "status": "blocked",
                "blockers": [
                    "risk_tensor_quality_warning",
                    "krd_contract_decision_required",
                ],
            },
            {
                "owner": "data_owner",
                "status": "blocked",
                "blockers": ["bond_maturity_date_remediation_required"],
            },
            {
                "owner": "business_owner",
                "status": "blocked",
                "blockers": ["business_owner_approval"],
            },
        ],
        "blocker_matrix": [
            {
                "blocker": "risk_tensor_quality_warning",
                "owner": "risk_owner",
                "closure_status": "blocked",
                "strict_gate_command": "python scripts/risk.py --require-clean",
                "next_action": "Recompute risk tensor.",
                "exit_criteria": "Risk tensor quality is ok.",
                "current_evidence": {
                    "decision_status": "blocked",
                    "warning_consistency_status": "mismatch",
                },
            },
            {
                "blocker": "bond_maturity_date_remediation_required",
                "owner": "data_owner",
                "closure_status": "blocked",
                "strict_gate_command": "python scripts/maturity.py --require-empty",
                "next_action": "Fill source maturity dates.",
                "exit_criteria": "Queue is empty or signed exclusion exists.",
                "current_evidence": {
                    "missing_maturity_rows": 114,
                    "candidate_evidence_status": "no_candidates",
                },
            },
        ],
        "required_next_command": (
            "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
        ),
    }


def _minimal_risk_warning() -> dict[str, object]:
    return {
        "decision_status": "blocked",
        "decision_blockers": [
            "risk_tensor_quality_warning",
            "risk_tensor_warning_mismatch",
        ],
        "warning_consistency_status": "mismatch",
        "consistency_blockers": ["duration_exclusion_warning_mismatch"],
        "duration_exclusion_delta_detail": {
            "status": "mismatch",
        },
    }


def _minimal_intake_check() -> dict[str, object]:
    return {
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "owner_decision_statuses": {
            "risk_owner": "pending",
            "data_owner": "pending",
            "business_owner": "pending",
        },
        "decision_gap_counts": {},
        "blockers": ["business_owner_approval_missing"],
    }


def build_preflight_for_test(
    *,
    duckdb_path: Path | None = None,
    limit: int = 3,
) -> dict[str, object]:
    from scripts.portfolio_home_full_score_preflight import build_preflight
    from scripts.portfolio_home_full_closure_evidence import DEFAULT_DUCKDB

    return build_preflight(
        duckdb_path=duckdb_path or DEFAULT_DUCKDB,
        report_date=REPORT_DATE,
        limit=limit,
    )


def _create_candidate_db(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              market_value decimal(24, 8),
              maturity_date varchar,
              dv01 decimal(24, 8),
              tenor_bucket varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table position_snapshot (
              as_of_date varchar,
              bond_code varchar,
              bond_name varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        connection.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, 'BOND-1', 'Bond 1', 'book', 'cc', 100, null, 1, '2Y',
              'sv_bond', 'rv_bond', 'batch-bond', 'trace-bond'
            )
            """,
            [REPORT_DATE],
        )
        connection.execute(
            """
            insert into fact_formal_tyw_balance_daily values (
              ?, 'POS-1', 'deposit', 'liability', 'Counterparty', 'liability',
              'CNY', 30, 0.03, null, 'sv_tyw', 'rv_tyw', 'batch-tyw', 'trace-tyw'
            )
            """,
            [REPORT_DATE],
        )
        connection.execute(
            """
            insert into zqtz_bond_daily_snapshot values (
              ?, 'BOND-1', 'book', 'cc', '2030-05-31',
              'sv_candidate_bond', 'rv_candidate_bond', 'batch-candidate-bond',
              'trace-candidate-bond'
            )
            """,
            [REPORT_DATE],
        )
        connection.execute(
            """
            insert into tyw_interbank_daily_snapshot values (
              ?, 'POS-1', 'deposit', 'liability', 'Counterparty', '2026-08-31',
              'sv_candidate_tyw', 'rv_candidate_tyw', 'batch-candidate-tyw',
              'trace-candidate-tyw'
            )
            """,
            [REPORT_DATE],
        )
    finally:
        connection.close()
