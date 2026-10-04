from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_basis_bridge import calculate_pnl_basis_bridge
from backend.app.services import pnl_basis_bridge_service


def _meta(source_version: str, rule_version: str, tables: list[str]) -> dict[str, object]:
    return {
        "source_version": source_version,
        "rule_version": rule_version,
        "tables_used": tables,
    }


def _product_envelope(*, view: str, gross: str, ftp: str, net: str) -> dict[str, object]:
    return {
        "result_meta": _meta(
            f"sv_product_{view}",
            "rv_product",
            ["product_category_pnl_formal_read_model"],
        ),
        "result": {
            "report_date": "2026-07-31",
            "view": view,
            "grand_total": {
                "cnx_cash": gross,
                "cny_ftp": ftp,
                "foreign_ftp": "0",
                "business_net_income": net,
            },
        },
    }


def _system_envelope() -> dict[str, object]:
    return {
        "result_meta": _meta(
            "sv_system",
            "rv_system",
            ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
        ),
        "result": {
            "year": 2026,
            "as_of_date": "2026-07-31",
            "months": [
                {
                    "month_key": "2026-01",
                    "period_start_date": "2026-01-01",
                    "period_end_date": "2026-01-31",
                    "source_total_pnl": "80",
                    "unallocated_pnl": "0",
                    "summary": {
                        "total_pnl": "80",
                        "manual_adjustment": "0",
                        "ftp_cost": "40",
                        "ftp_net_pnl": "40",
                    },
                },
                {
                    "month_key": "2026-07",
                    "period_start_date": "2026-07-01",
                    "period_end_date": "2026-07-31",
                    "source_total_pnl": "125",
                    "unallocated_pnl": "5",
                    "summary": {
                        "total_pnl": "120",
                        "manual_adjustment": "20",
                        "ftp_cost": "50",
                        "ftp_net_pnl": "70",
                    },
                },
            ],
        },
    }


def test_basis_bridge_fails_loud_when_an_input_identity_does_not_close() -> None:
    with pytest.raises(ValueError, match="system gross - FTP"):
        calculate_pnl_basis_bridge(
            system_gross_pnl=Decimal("120"),
            system_manual_adjustment=Decimal("20"),
            system_unallocated_pnl=Decimal("5"),
            system_ftp_cost=Decimal("50"),
            system_ftp_net_pnl=Decimal("69"),
            formal_recognized_pnl=Decimal("105"),
            product_gross_cash_income=Decimal("90"),
            product_ftp_cost=Decimal("30"),
            product_ftp_net_income=Decimal("60"),
        )


def test_basis_bridge_fails_loud_when_rounding_alignment_exceeds_tolerance() -> None:
    with pytest.raises(ValueError, match="rounding alignment"):
        calculate_pnl_basis_bridge(
            system_gross_pnl=Decimal("120"),
            system_manual_adjustment=Decimal("20"),
            system_unallocated_pnl=Decimal("10000"),
            system_ftp_cost=Decimal("50"),
            system_ftp_net_pnl=Decimal("70"),
            formal_recognized_pnl=Decimal("105"),
            product_gross_cash_income=Decimal("90"),
            product_ftp_cost=Decimal("30"),
            product_ftp_net_income=Decimal("60"),
        )


def test_pnl_basis_bridge_closes_monthly_and_ytd_without_hiding_mapping_residual(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pnl_basis_bridge_service,
        "product_category_pnl_envelope",
        lambda _path, *, report_date, view: _product_envelope(
            view=view,
            gross="90" if view == "monthly" else "150",
            ftp="30" if view == "monthly" else "50",
            net="60" if view == "monthly" else "100",
        ),
    )
    monkeypatch.setattr(
        pnl_basis_bridge_service,
        "pnl_by_business_monthly_envelope",
        lambda **_kwargs: _system_envelope(),
    )
    monkeypatch.setattr(
        pnl_basis_bridge_service,
        "pnl_overview_envelope",
        lambda **_kwargs: {
            "result_meta": _meta("sv_overview", "rv_overview", ["fact_formal_pnl_fi"]),
            "result": {"report_date": "2026-07-31", "total_pnl": "105"},
        },
    )

    envelope = pnl_basis_bridge_service.pnl_basis_bridge_envelope(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        report_date="2026-07-31",
    )

    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["result_kind"] == "pnl.basis_bridge"
    result = envelope["result"]
    assert result["arithmetic_status"] == "closed"
    assert result["mapping_status"] == "pending_crosswalk"
    monthly, ytd = result["periods"]

    assert monthly["system_to_formal_gross"]["closure_residual"] == "0"
    assert monthly["system_to_product_ftp_net"]["closure_residual"] == "0"
    assert monthly["system_to_product_ftp_net"]["mapping_status"] == "pending_crosswalk"
    monthly_components = {
        item["code"]: item for item in monthly["system_to_product_ftp_net"]["components"]
    }
    assert monthly_components["remove_system_manual_adjustment"]["amount"] == "-20"
    assert monthly_components["restore_unallocated_formal_pnl"]["amount"] == "5"
    assert monthly_components["formal_to_product_gross_scope_mapping_residual"]["amount"] == "-15"
    assert monthly_components["formal_to_product_gross_scope_mapping_residual"][
        "evidence_status"
    ] == "mapping_pending"
    assert monthly_components["ftp_method_and_denominator_difference"]["amount"] == "20"

    assert ytd["inputs"]["system_ftp_net_pnl"] == "110"
    assert ytd["inputs"]["formal_recognized_pnl"] == "185"
    assert ytd["system_to_formal_gross"]["closure_residual"] == "0"
    assert ytd["system_to_product_ftp_net"]["end_value"] == "100"
    assert ytd["system_to_product_ftp_net"]["closure_residual"] == "0"

