"""BD-018: actual service, Numeric serialization and strict read-consumer contract.

Repository rows and governance lineage are explicit synthetic boundaries. No
provider, business storage, API server or real-source reconciliation is used.
"""
from __future__ import annotations

import socket
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.bond_analytics import read_models
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, duckdb_read_scope
from backend.app.schemas.home_bond_read_contracts import BondPositionChangesReadEnvelope
from backend.app.services import bond_analytics_service as service

CURRENT = "2026-09-30"
PREVIOUS = "2026-08-31"


def _row(code, amount, *, book="AC", portfolio="synthetic-main", cost_center="synthetic-cc",
         currency="CNY", maturity="2030-01-01", **fields):
    return {"instrument_code": code, "market_value": Decimal(amount),
            "market_value_native": Decimal("999999"), "accounting_class": book,
            "portfolio_name": portfolio, "cost_center": cost_center, "currency_code": currency,
            "maturity_date": maturity, "instrument_name": f"Synthetic {code}",
            "issuer_name": "Synthetic issuer", "rating": "AAA", "asset_class_std": "credit",
            "source_version": "sv_synthetic_only", **fields}


@pytest.fixture
def read_changes(monkeypatch, tmp_path):
    def deny_network(*args, **kwargs):
        raise AssertionError("No network access is allowed in this regression")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    captured = []

    def lineage(report_date, rows):
        captured.append((report_date, deepcopy(rows)))
        return {"source_version": "sv_synthetic_only", "rule_version": service.RULE_VERSION,
                "vendor_version": "vv_synthetic_only"}

    monkeypatch.setattr(service, "_lineage", lineage)

    def run(current, previous, top_n=100, dates=None):
        snapshots = {CURRENT: deepcopy(current), PREVIOUS: deepcopy(previous)}
        repo = SimpleNamespace(
            fetch_bond_analytics_rows=lambda *, report_date: snapshots[report_date],
            list_report_dates=lambda: dates if dates is not None else [CURRENT, PREVIOUS],
        )
        monkeypatch.setattr(service, "_repo", lambda: repo)
        response = service.get_position_changes(date.fromisoformat(CURRENT), top_n=top_n)
        # Actual strict wire consumer used by /api/bond-analytics/position-changes.
        BondPositionChangesReadEnvelope.model_validate(response)
        assert response["result_meta"]["amount_currency_basis"] == "CNY"
        expected_rows = current + (previous if PREVIOUS in repo.list_report_dates() else [])
        assert captured[-1][1] == expected_rows
        return response["result"]

    return run


def _raw(item, field):
    return Decimal(item[field]["raw"])


@pytest.mark.parametrize("reverse_current", [False, True])
@pytest.mark.parametrize("reverse_previous", [False, True])
def test_same_bond_multiple_books_retains_all_legs(read_changes, reverse_current, reverse_previous):
    current = [_row("SYNTH-X", "120"), _row("SYNTH-X", "50", book="OCI")]
    previous = [_row("SYNTH-X", "100"), _row("SYNTH-X", "50", book="OCI")]
    result = read_changes(current[::-1] if reverse_current else current,
                          previous[::-1] if reverse_previous else previous)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert _raw(item, "current_market_value") == Decimal("170")
    assert _raw(item, "previous_market_value") == Decimal("150")
    assert _raw(item, "change_market_value") == Decimal("20")
    assert _raw(item, "current_weight") == 1
    assert item["direction"] == "increase"
    assert item["reason_label"] == "增持"
    assert item["change_market_value"]["unit"] == "yuan"
    assert item["current_weight"]["unit"] == "ratio"


def test_cross_portfolio_currency_maturity_and_partial_book_exits_close_to_totals(read_changes):
    previous = [
        _row("SYNTH-X", "100"),
        _row("SYNTH-X", "50", book="OCI", currency="USD", cost_center="synthetic-alt"),
        _row("SYNTH-X", "30", portfolio="synthetic-other", maturity="2032-01-01"),
        _row("SYNTH-EXIT", "80"), _row("SYNTH-FLAT", "5"),
    ]
    current = [
        _row("SYNTH-X", "120"),
        _row("SYNTH-X", "30", portfolio="synthetic-other", maturity="2032-01-01"),
        _row("SYNTH-X", "10", book="TPL", currency="USD"),
        _row("SYNTH-NEW", "40"), _row("SYNTH-FLAT", "5"),
    ]
    result = read_changes(current, previous)
    items = {item["instrument_code"]: item for item in result["items"]}
    assert set(items) == {"SYNTH-X", "SYNTH-EXIT", "SYNTH-NEW"}
    assert _raw(items["SYNTH-X"], "change_market_value") == -20
    assert items["SYNTH-X"]["reason_label"] == "减持"
    assert items["SYNTH-EXIT"]["reason_label"] == "清仓"
    assert items["SYNTH-NEW"]["reason_label"] == "新增"
    assert sum((_raw(item, "change_market_value") for item in result["items"]), Decimal(0)) == (
        _raw(result, "total_market_value") - _raw(result, "prev_total_market_value"))
    assert any("USD" in warning for warning in result["warnings"])
    assert read_changes(list(reversed(current)), list(reversed(previous)))["items"] == result["items"]


def test_book_transfer_keeps_bond_flat_and_top_n_orders_aggregated_deltas(read_changes):
    previous = [_row("SYNTH-X", "100"), _row("SYNTH-Y", "20"), _row("SYNTH-Y", "20", book="OCI")]
    current = [_row("SYNTH-X", "100", book="OCI"), _row("SYNTH-Y", "30"),
               _row("SYNTH-Y", "30", book="OCI"), _row("SYNTH-Z", "15")]
    result = read_changes(current, previous, top_n=1)
    assert [item["instrument_code"] for item in result["items"]] == ["SYNTH-Y"]
    assert _raw(result["items"][0], "change_market_value") == 20
    assert _raw(result, "total_market_value") == 175


def test_conflicting_descriptions_are_unavailable_and_disclosed_order_independently(read_changes):
    previous = [_row("SYNTH-X", "100")]
    current = [_row("SYNTH-X", "120"), _row("SYNTH-X", "50", book="OCI",
                instrument_name="Synthetic conflict", issuer_name="Different synthetic issuer",
                rating="AA", asset_class_std="rate")]
    result = read_changes(current, previous)
    item = result["items"][0]
    assert item["instrument_name"] is None
    assert item["issuer_name"] is None
    assert item["rating"] is None
    assert item["asset_class"] == ""
    assert any("SYNTH-X" in warning and "conflict" in warning.lower() for warning in result["warnings"])
    reordered = read_changes(list(reversed(current)), previous)
    assert reordered["items"] == result["items"]
    assert reordered["warnings"] == result["warnings"]


def test_missing_prior_snapshot_stays_empty_instead_of_inventing_new_positions(read_changes):
    result = read_changes([_row("SYNTH-X", "100")], [], dates=[CURRENT])
    assert result["source_status"] == "empty"
    assert result["items"] == []
    assert result["prev_report_date"] is None


def test_single_leg_and_null_description_contract_stays_unchanged(read_changes):
    result = read_changes([_row("SYNTH-X", "110", issuer_name=None)], [_row("SYNTH-X", "100")])
    item = result["items"][0]
    assert item["issuer_name"] is None
    assert _raw(item, "change_market_value") == 10
    assert result["warnings"] == []


def test_core_aggregation_preserves_decimal_precision_and_input_rows():
    rows = [_row("SYNTH-X", "100000000.12345678"),
            _row("SYNTH-X", ".00000001", book="OCI"),
            _row("SYNTH-X", ".00000001", book="OCI", maturity="2031-01-01")]
    before = deepcopy(rows)
    aggregate = getattr(read_models, "aggregate_bond_position_market_values", None)
    assert callable(aggregate), "Bond-code aggregation must be available"
    aggregated, warnings = aggregate(rows)
    assert aggregated["SYNTH-X"]["market_value"] == Decimal("100000000.12345680")
    assert warnings == []
    assert rows == before


def test_actual_repository_immutable_read_service_and_wire_contract(read_changes, tmp_path, monkeypatch):
    """Exercise the real multi-leg repository without weakening its read guard."""
    path = tmp_path / "synthetic-snapshot.duckdb"
    schema = Path(__file__).resolve().parents[1] / "backend/app/schema_registry/duckdb/02_bond_analytics.sql"
    with duckdb.connect(str(path)) as conn:
        for statement in schema.read_text(encoding="utf-8").split("-- MOSS:STMT"):
            if statement.strip():
                conn.execute(statement)
        for report_date, amount, book, currency in [
            (PREVIOUS, "100", "AC", "CNY"), (PREVIOUS, "50", "OCI", "USD"),
            (CURRENT, "120", "AC", "CNY"), (CURRENT, "50", "OCI", "USD"),
        ]:
            row = {"report_date": report_date, **_row("SYNTH-X", amount, book=book, currency=currency)}
            fields = list(row)
            conn.execute(
                f"insert into fact_formal_bond_analytics_daily ({', '.join(fields)}) "
                f"values ({', '.join('?' for _ in fields)})", list(row.values()),
            )
    active_path = tmp_path / "unopened-active.duckdb"
    repo = BondAnalyticsRepository(str(active_path))
    monkeypatch.setattr(service, "_repo", lambda: repo)
    selection = DuckDBReadSelection(active_path=active_path, snapshot_path=path, generation="synthetic-track4")
    with duckdb_read_scope(selection, required_online=True):
        assert len(repo.fetch_bond_analytics_rows(report_date=CURRENT)) == 2
        response = service.get_position_changes(date.fromisoformat(CURRENT))
    BondPositionChangesReadEnvelope.model_validate(response)
    assert _raw(response["result"]["items"][0], "change_market_value") == 20
    assert _raw(response["result"], "total_market_value") == 170
    assert not active_path.exists()
