from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.repositories.choice_data_opportunity_catalog import (
    build_choice_funding_edb_probe_plan,
    choice_api_wrapper_readiness,
    discover_choice_funding_macro_candidates,
    load_choice_funding_confirmed_candidates,
    load_choice_data_opportunity_catalog,
    list_choice_data_opportunities,
)


def test_choice_data_opportunity_catalog_exposes_fixed_income_macro_p0_candidates():
    catalog = load_choice_data_opportunity_catalog()

    p0_items = list_choice_data_opportunities(
        catalog,
        priority="P0",
        domain="fixed_income_macro",
    )

    ids = {item.opportunity_id for item in p0_items}
    assert {
        "choice_yield_curve_full_tenor",
        "choice_funding_conditions",
        "choice_bond_position_market_fields",
        "choice_treasury_futures_positioning",
    }.issubset(ids)
    assert all(item.choice_api_functions for item in p0_items)
    assert all(item.business_surfaces for item in p0_items)
    assert all(item.implementation_state != "avoid" for item in p0_items)


def test_choice_data_opportunity_catalog_filters_avoid_by_default(tmp_path: Path):
    catalog_path = tmp_path / "choice_data_opportunities.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test",
                "vendor_name": "choice",
                "generated_from": "test",
                "opportunities": [
                    {
                        "opportunity_id": "recommended",
                        "priority": "P0",
                        "domain": "fixed_income_macro",
                        "title": "Recommended data",
                        "choice_api_functions": ["edb"],
                        "data_families": ["yield_curve"],
                        "business_surfaces": ["bond_analytics"],
                        "landing_targets": ["fact_choice_macro_daily"],
                        "existing_evidence": ["test"],
                        "implementation_state": "candidate",
                        "next_step": "Probe entitlement.",
                        "caveats": [],
                    },
                    {
                        "opportunity_id": "choice_trade_execution",
                        "priority": "avoid",
                        "domain": "operations_guardrail",
                        "title": "Trade execution APIs",
                        "choice_api_functions": ["porder"],
                        "data_families": ["order_execution"],
                        "business_surfaces": ["none"],
                        "landing_targets": [],
                        "existing_evidence": [
                            "Trading APIs are outside MOSS analytical ingestion."
                        ],
                        "implementation_state": "avoid",
                        "next_step": "Do not connect without explicit trading-system scope.",
                        "caveats": [
                            "Do not mix vendor portfolio operations with governed MOSS books."
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    catalog = load_choice_data_opportunity_catalog(catalog_path)

    default_ids = {item.opportunity_id for item in list_choice_data_opportunities(catalog)}
    assert default_ids == {"recommended"}

    all_ids = {
        item.opportunity_id
        for item in list_choice_data_opportunities(catalog, include_avoid=True)
    }
    assert all_ids == {"recommended", "choice_trade_execution"}


def test_choice_data_opportunity_catalog_rejects_duplicate_ids(tmp_path: Path):
    catalog_path = tmp_path / "choice_data_opportunities.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test",
                "vendor_name": "choice",
                "generated_from": "test",
                "opportunities": [
                    {
                        "opportunity_id": "dup",
                        "priority": "P1",
                        "domain": "equity_strategy",
                        "title": "First",
                        "choice_api_functions": ["css"],
                        "data_families": ["stock_factor"],
                        "business_surfaces": ["stock_analysis"],
                        "landing_targets": ["choice_stock_factor_snapshot"],
                        "existing_evidence": ["test"],
                        "implementation_state": "candidate",
                        "next_step": "Probe entitlement.",
                        "caveats": [],
                    },
                    {
                        "opportunity_id": "dup",
                        "priority": "P1",
                        "domain": "equity_strategy",
                        "title": "Second",
                        "choice_api_functions": ["csd"],
                        "data_families": ["stock_factor"],
                        "business_surfaces": ["stock_analysis"],
                        "landing_targets": ["choice_stock_factor_snapshot"],
                        "existing_evidence": ["test"],
                        "implementation_state": "candidate",
                        "next_step": "Probe entitlement.",
                        "caveats": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate Choice data opportunity ids: dup"):
        load_choice_data_opportunity_catalog(catalog_path)


def test_choice_data_opportunity_catalog_reports_api_wrapper_readiness():
    catalog = load_choice_data_opportunity_catalog()

    funding = choice_api_wrapper_readiness(
        catalog,
        opportunity_id="choice_funding_conditions",
    )
    assert funding == {"edb": "available"}

    metadata = choice_api_wrapper_readiness(
        catalog,
        opportunity_id="choice_market_calendar_metadata",
    )
    assert metadata["tradedates"] == "available"
    assert metadata["edbquery"] == "available"
    assert metadata["cfnquery"] == "available"
    assert metadata["cec"] == "missing_wrapper"
    assert metadata["cfc"] == "missing_wrapper"
    assert metadata["datastatistics"] == "missing_wrapper"


def test_discover_choice_funding_macro_candidates_from_default_catalog():
    candidates = discover_choice_funding_macro_candidates()

    assert candidates
    assert all(candidate.choice_api_function == "edb" for candidate in candidates)
    assert all(
        candidate.landing_targets == ["fact_choice_macro_daily", "choice_market_snapshot"]
        for candidate in candidates
    )
    assert any(candidate.match_reason == "theme:money_liquidity" for candidate in candidates)
    assert {"EMM00166252", "EMM00167613"}.issubset(
        {candidate.series_id for candidate in candidates}
    )


def test_discover_choice_funding_macro_candidates_uses_theme_and_keywords(tmp_path: Path):
    macro_catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_macro_catalog(
        macro_catalog_path,
        [
            {
                "series_id": "DR007",
                "series_name": "DR007",
                "vendor_series_code": "DR007",
                "theme": "money_liquidity",
                "tags": ["choice", "macro", "money"],
            },
            {
                "series_id": "SHIBOR_ON",
                "series_name": "SHIBOR:ON",
                "vendor_series_code": "SHIBOR_ON",
                "theme": "macro_market",
                "tags": ["choice", "macro", "rates"],
            },
            {
                "series_id": "CPI",
                "series_name": "CPI",
                "vendor_series_code": "CPI",
                "theme": "macro_market",
                "tags": ["choice", "macro"],
            },
        ],
    )

    candidates = discover_choice_funding_macro_candidates(macro_catalog_path)

    assert [candidate.series_id for candidate in candidates] == ["DR007", "SHIBOR_ON"]
    assert candidates[0].match_reason == "theme:money_liquidity"
    assert candidates[1].match_reason == "keyword:shibor"


def test_build_choice_funding_edb_probe_plan_batches_candidates(tmp_path: Path):
    macro_catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_macro_catalog(
        macro_catalog_path,
        [
            {
                "series_id": "DR007",
                "series_name": "DR007",
                "vendor_series_code": "DR007",
                "theme": "money_liquidity",
                "tags": ["choice", "macro", "money"],
            },
            {
                "series_id": "SHIBOR_ON",
                "series_name": "SHIBOR:ON",
                "vendor_series_code": "SHIBOR_ON",
                "theme": "macro_market",
                "tags": ["choice", "macro", "rates"],
            },
            {
                "series_id": "R007",
                "series_name": "R007",
                "vendor_series_code": "R007",
                "theme": "money_liquidity",
                "tags": ["choice", "macro", "money"],
            },
        ],
    )

    plan = build_choice_funding_edb_probe_plan(
        macro_catalog_path,
        as_of_date="2026-06-10",
        chunk_size=2,
    )

    assert plan.opportunity_id == "choice_funding_conditions"
    assert plan.choice_api_function == "edb"
    assert plan.wrapper_status == "available"
    assert plan.as_of_date == "2026-06-10"
    assert plan.total_candidates == 3
    assert [batch.codes for batch in plan.batches] == [["DR007", "R007"], ["SHIBOR_ON"]]
    assert all(
        batch.request_options
        == "IsLatest=0,StartDate=2026-06-10,EndDate=2026-06-10,Ispandas=1,RECVtimeout=5"
        for batch in plan.batches
    )
    assert plan.landing_targets == ["fact_choice_macro_daily", "choice_market_snapshot"]


def test_build_choice_funding_edb_probe_plan_can_use_latest_mode(tmp_path: Path):
    macro_catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_macro_catalog(
        macro_catalog_path,
        [
            {
                "series_id": "SHIBOR_ON",
                "series_name": "SHIBOR:ON",
                "vendor_series_code": "SHIBOR_ON",
                "theme": "macro_market",
                "tags": ["choice", "macro", "rates"],
            },
        ],
    )

    plan = build_choice_funding_edb_probe_plan(
        macro_catalog_path,
        as_of_date="2026-06-10",
        chunk_size=10,
        probe_mode="latest",
    )

    assert plan.probe_mode == "latest"
    assert plan.batches[0].probe_mode == "latest"
    assert plan.batches[0].request_options == "IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5"


def test_build_choice_funding_edb_probe_plan_rejects_unknown_mode(tmp_path: Path):
    macro_catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_macro_catalog(
        macro_catalog_path,
        [
            {
                "series_id": "SHIBOR_ON",
                "series_name": "SHIBOR:ON",
                "vendor_series_code": "SHIBOR_ON",
                "theme": "macro_market",
                "tags": ["choice", "macro", "rates"],
            },
        ],
    )

    with pytest.raises(ValueError, match="probe_mode must be one of"):
        build_choice_funding_edb_probe_plan(
            macro_catalog_path,
            as_of_date="2026-06-10",
            probe_mode="bad-mode",  # type: ignore[arg-type]
        )


def test_choice_funding_confirmed_candidates_first_batch_is_shibor_only():
    catalog = load_choice_funding_confirmed_candidates()

    first_batch = catalog.first_batch_series()
    first_batch_ids = {item.series_id for item in first_batch}

    assert catalog.probe_mode == "latest"
    assert catalog.write_performed is False
    assert first_batch_ids == {
        "EMM00166252",
        "EMM00166253",
        "EMM00166254",
        "EMM00167612",
        "EMM00167613",
        "EMM00167614",
        "EMM00167708",
    }
    assert all(item.latest_date == "2026-06-09" for item in first_batch)
    assert all(item.unit == "%" for item in first_batch)
    assert all(item.first_batch_action == "candidate_for_landing" for item in first_batch)
    assert "EMM01089843" not in first_batch_ids
    assert "EMM00087084" not in first_batch_ids


def _write_macro_catalog(path: Path, series: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "catalog_version": "test-macro",
                "vendor_name": "choice",
                "generated_at": "2026-06-10T09:00:00+08:00",
                "generated_from": "test",
                "batches": [
                    {
                        "batch_id": "stable",
                        "fetch_mode": "date_slice",
                        "fetch_granularity": "batch",
                        "refresh_tier": "stable",
                        "policy_note": "test",
                        "request_options": {"IsLatest": 0},
                        "series": [
                            {
                                "frequency": "daily",
                                "unit": "%",
                                "is_core": False,
                                **item,
                            }
                            for item in series
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
