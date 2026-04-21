"""W-formal-gate-2026-04-21 caliber migration: analysis adapters + AnalysisQuery lockstep with formal_scenario_gate."""

from __future__ import annotations

import sys
from typing import get_args

import pytest

from backend.app.core_finance.calibers.enums import Basis
from backend.app.core_finance.calibers.rules.formal_scenario_gate import ForbiddenBasisViewCombination
from backend.app.schemas.analysis_service import AnalysisBasis, AnalysisQuery
from tests.helpers import load_module


def test_analysis_query_accepts_formal_without_scenario_rate() -> None:
    q = AnalysisQuery(
        consumer="c",
        analysis_key="k",
        report_date="2026-02-28",
        basis="formal",
    )
    assert q.basis == "formal"
    assert q.scenario_rate_pct is None


def test_analysis_query_rejects_scenario_without_scenario_rate() -> None:
    with pytest.raises(ValueError, match="scenario_rate_pct is required"):
        AnalysisQuery(
            consumer="c",
            analysis_key="k",
            report_date="2026-02-28",
            basis="scenario",
        )


def test_analysis_basis_literal_lockstep_with_basis_enum() -> None:
    assert set(get_args(AnalysisBasis)) == {b.value for b in Basis}


def _materialize_product_category_fixture(tmp_path, monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    task_module = sys.modules.get("backend.app.tasks.product_category_pnl")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.product_category_pnl",
            "backend/app/tasks/product_category_pnl.py",
        )
    test_module = load_module(
        "tests.test_product_category_pnl_flow",
        "tests/test_product_category_pnl_flow.py",
    )
    adapter_module = load_module(
        "backend.app.services.analysis_adapters",
        "backend/app/services/analysis_adapters.py",
    )

    data_root = tmp_path / "data_input"
    source_dir = data_root / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    test_module._write_month_pair(source_dir, "202602", january=False)

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    task_module.materialize_product_category_pnl.fn(
        duckdb_path=str(duckdb_path),
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
    )

    return schema_module, adapter_module, duckdb_path


@pytest.mark.parametrize("basis", ("formal", "scenario"))
def test_product_category_adapter_execute_include_basis_no_gate_violation(
    tmp_path, monkeypatch, basis: str
) -> None:
    schema_module, adapter_module, duckdb_path = _materialize_product_category_fixture(
        tmp_path, monkeypatch
    )
    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter(str(duckdb_path))
    kwargs: dict = dict(
        consumer="analysis_service",
        analysis_key="product_category_pnl",
        report_date="2026-02-28",
        basis=basis,
        view="monthly",
    )
    if basis == "scenario":
        kwargs["scenario_rate_pct"] = 2.5
    query = schema_module.AnalysisQuery(**kwargs)
    try:
        envelope = adapter.execute(query)
    except ForbiddenBasisViewCombination:  # pragma: no cover - contract guard
        pytest.fail("execute raised ForbiddenBasisViewCombination for allowed basis")
    assert envelope.result.basis == basis


def test_product_category_adapter_analytical_raises_valueerror_not_gate(
    tmp_path, monkeypatch
) -> None:
    schema_module, adapter_module, duckdb_path = _materialize_product_category_fixture(
        tmp_path, monkeypatch
    )
    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter(str(duckdb_path))
    with pytest.raises(ValueError) as excinfo:
        adapter.execute(
            schema_module.AnalysisQuery(
                consumer="analysis_service",
                analysis_key="product_category_pnl",
                report_date="2026-02-28",
                basis="analytical",
                view="monthly",
            )
        )
    assert not isinstance(excinfo.value, ForbiddenBasisViewCombination)
