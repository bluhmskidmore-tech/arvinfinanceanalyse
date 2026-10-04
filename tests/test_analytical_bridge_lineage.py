"""Synthetic lineage regressions for already-landed non-formal Cube reads."""
from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.schemas.cube_query import CubeQueryRequest
from backend.app.security.auth_context import AuthContext
from backend.app.services.analytical_bridge_service import AnalyticalBridgeService

pytestmark = pytest.mark.excluded_surface_regression

REPORT_DATE = "2026-08-31"
AUTH = AuthContext(user_id="synthetic-lineage", role="viewer", identity_source="test")


@pytest.fixture
def bridge_db():
    with duckdb.connect(":memory:") as conn:
        conn.execute(
            "create table fact_formal_bond_analytics_daily "
            "(report_date varchar, portfolio_name varchar, market_value decimal(24,8), "
            "source_version varchar, rule_version varchar)"
        )
        conn.execute(
            "create table fact_formal_pnl_fi "
            "(report_date varchar, portfolio_name varchar, total_pnl decimal(24,8), "
            "source_version varchar, rule_version varchar)"
        )
        conn.execute(
            "create table position_snapshot "
            "(as_of_date varchar, portfolio varchar, fair_value decimal(24,8), "
            "source_version varchar, rule_version varchar)"
        )
        yield conn


def _case(fact: str, basis: str) -> tuple[str, str, str, str]:
    if basis == "ledger":
        return "position_snapshot", "as_of_date", "portfolio", "fair_value"
    if fact == "pnl":
        return "fact_formal_pnl_fi", "report_date", "portfolio_name", "total_pnl"
    return "fact_formal_bond_analytics_daily", "report_date", "portfolio_name", "market_value"


def _execute(conn, fact: str, basis: str, *, filters=None, report_date=REPORT_DATE):
    class Repo:
        def fetchall(self, sql, params=None):
            return conn.execute(sql, list(params or [])).fetchall()

    table, _, _, measure = _case(fact, basis)
    request = CubeQueryRequest(
        report_date=report_date, fact_table=fact, basis=basis,
        measures=[f"sum({measure})"], filters=filters or {},
    )
    response = AnalyticalBridgeService(repo_factory=lambda _: Repo()).execute(
        request, ":memory:", auth=AUTH,
    )
    return response, table


CASES = [("bond_analytics", "analytical"), ("pnl", "analytical"), ("balance", "ledger")]


@pytest.mark.parametrize("fact,basis", CASES)
def test_selected_rows_supply_source_and_rule_and_change_after_replacement(bridge_db, fact, basis):
    table, _, _, measure = _case(fact, basis)
    bridge_db.execute(f"insert into {table} values (?, ?, ?, ?, ?)",
                      [REPORT_DATE, "selected", 125, "sv_synthetic_a", "rv_synthetic_a"])
    first, _ = _execute(bridge_db, fact, basis)
    assert first.result_meta.source_version == "sv_synthetic_a"
    assert first.result_meta.rule_version == "rv_synthetic_a"
    assert first.result_meta.formal_use_allowed is False
    assert first.rows == [{measure: Decimal("125")}]

    bridge_db.execute(f"update {table} set source_version=?, rule_version=?",
                      ["sv_synthetic_b", "rv_synthetic_b"])
    second, _ = _execute(bridge_db, fact, basis)
    assert second.result_meta.source_version == "sv_synthetic_b"
    assert second.result_meta.rule_version == "rv_synthetic_b"
    assert second.rows == first.rows


@pytest.mark.parametrize("fact,basis", CASES)
def test_lineage_uses_same_date_and_filters_as_values(bridge_db, fact, basis):
    table, _, dimension, measure = _case(fact, basis)
    bridge_db.executemany(f"insert into {table} values (?, ?, ?, ?, ?)", [
        (REPORT_DATE, "selected", 125, "sv_selected", "rv_selected"),
        (REPORT_DATE, "other", 250, None, None),
        ("2026-07-31", "selected", 500, None, None),
    ])
    response, _ = _execute(bridge_db, fact, basis, filters={dimension: ["selected"]})
    assert response.rows == [{measure: Decimal("125")}]
    assert response.result_meta.source_version == "sv_selected"
    assert response.result_meta.rule_version == "rv_selected"
    assert response.result_meta.tables_used == [table]
    assert response.result_meta.evidence_rows == 1


@pytest.mark.parametrize("fact,basis", CASES)
def test_multiple_selected_versions_are_preserved_and_stable(bridge_db, fact, basis):
    table, _, _, _ = _case(fact, basis)
    bridge_db.executemany(f"insert into {table} values (?, ?, ?, ?, ?)", [
        (REPORT_DATE, "selected", 125, "sv_b", "rv_b"),
        (REPORT_DATE, "selected", 250, "sv_a", "rv_a"),
        (REPORT_DATE, "selected", 500, "sv_b", "rv_b"),
    ])
    response, _ = _execute(bridge_db, fact, basis)
    assert response.result_meta.source_version == "sv_a__sv_b"
    assert response.result_meta.rule_version == "rv_a__rv_b"
    assert response.result_meta.evidence_rows == 3


@pytest.mark.parametrize("fact,basis", CASES)
@pytest.mark.parametrize("field,value", [
    ("source_version", None), ("source_version", ""), ("source_version", "   "),
    ("source_version", "\t"), ("source_version", "\n"), ("source_version", "\u2003"),
    ("rule_version", None), ("rule_version", ""), ("rule_version", "   "),
    ("rule_version", "\t"), ("rule_version", "\n"), ("rule_version", "\u2003"),
])
def test_partial_missing_lineage_cannot_be_hidden_by_valid_rows(bridge_db, fact, basis, field, value):
    table, _, _, measure = _case(fact, basis)
    bridge_db.executemany(f"insert into {table} values (?, ?, ?, ?, ?)", [
        (REPORT_DATE, "selected", 125, "sv_valid", "rv_valid"),
        (REPORT_DATE, "selected", 250, "sv_valid", "rv_valid"),
    ])
    bridge_db.execute(f"update {table} set {field}=? where {measure}=250", [value])
    with pytest.raises(RuntimeError, match="lineage is incomplete"):
        _execute(bridge_db, fact, basis)


@pytest.mark.parametrize("fact,basis", CASES)
def test_empty_selection_remains_explicitly_empty_nonformal(bridge_db, fact, basis):
    response, table = _execute(bridge_db, fact, basis)
    assert response.rows == []
    assert response.total_rows == 0
    assert response.result_meta.quality_flag == "warning"
    assert response.result_meta.formal_use_allowed is False
    assert response.result_meta.source_version.endswith("_empty")
    assert response.result_meta.tables_used == [table]
    assert response.result_meta.evidence_rows == 0


@pytest.mark.parametrize("fact", ["bond_analytics", "pnl"])
def test_formal_delegation_retains_its_governed_contract(bridge_db, fact):
    table, _, _, measure = _case(fact, "formal")
    bridge_db.execute(f"insert into {table} values (?, ?, ?, ?, ?)",
                      [REPORT_DATE, "selected", 125, "sv_formal", "rv_formal"])
    response, _ = _execute(bridge_db, fact, "formal")
    assert response.rows == [{measure: Decimal("125")}]
    assert response.result_meta.basis == "formal"
    assert response.result_meta.formal_use_allowed is True
    assert response.result_meta.source_version == "sv_formal"
    assert response.result_meta.rule_version == "rv_formal"
