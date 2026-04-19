from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace

from tests.helpers import load_module


def test_product_category_adapter_returns_unified_analysis_envelope(tmp_path, monkeypatch):
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

    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter(str(duckdb_path))
    result = adapter.execute(
        schema_module.AnalysisQuery(
            consumer="analysis_service",
            analysis_key="product_category_pnl",
            report_date="2026-02-28",
            basis="formal",
            view="monthly",
        )
    )

    assert result.result_meta.result_kind == "analysis.product_category_pnl"
    assert result.result.basis == "formal"
    assert result.result.rows
    assert result.result.summary["asset_total"]["category_id"] == "asset_total"
    assert result.result.attribution


def test_product_category_adapter_scenario_basis_reads_formal_once_and_overlays_rate(
    tmp_path, monkeypatch
):
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

    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter(str(duckdb_path))
    fetch_calls: list[tuple[object, ...]] = []
    real_fetch = adapter._repo.fetch_rows

    def capture_fetch(*args: object) -> list[dict[str, object]]:
        fetch_calls.append(args)
        return real_fetch(*args)

    adapter._repo.fetch_rows = capture_fetch  # type: ignore[method-assign]

    scenario_result = adapter.execute(
        schema_module.AnalysisQuery(
            consumer="analysis_service",
            analysis_key="product_category_pnl",
            report_date="2026-02-28",
            basis="scenario",
            view="monthly",
            scenario_rate_pct=2.5,
        )
    )
    assert len(fetch_calls) == 1
    assert fetch_calls[0] == ("2026-02-28", "monthly")
    assert scenario_result.result_meta.scenario_flag is True
    assert scenario_result.result_meta.basis == "scenario"
    formal_only = adapter_module.ProductCategoryPnlAnalysisAdapter(str(duckdb_path)).execute(
        schema_module.AnalysisQuery(
            consumer="analysis_service",
            analysis_key="product_category_pnl",
            report_date="2026-02-28",
            basis="formal",
            view="monthly",
        )
    )
    def _asset_total_ftp(rows: list[dict[str, object]]) -> str:
        for row in rows:
            if row["category_id"] == "asset_total":
                return str(row["cny_ftp"])
        raise AssertionError("missing asset_total")

    assert _asset_total_ftp(formal_only.result.rows) != _asset_total_ftp(scenario_result.result.rows)


def test_bond_action_placeholder_envelope_shape():
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    adapter_module = load_module(
        "backend.app.services.analysis_adapters",
        "backend/app/services/analysis_adapters.py",
    )

    result = adapter_module.build_bond_action_attribution_placeholder_envelope(
        schema_module.AnalysisQuery(
            consumer="analysis_service",
            analysis_key="bond_action_attribution",
            report_date="2026-03-31",
            basis="formal",
            view="MoM",
        )
    )

    assert result.result_meta.result_kind == "analysis.bond_action_attribution"
    assert result.result_meta.source_surface == "bond_analytics"
    assert result.result_meta.quality_flag == "warning"
    assert result.result.summary["period_type"] == "MoM"
    assert result.result.summary["total_actions"] == 0
    assert result.result.summary["status"] == "unavailable"
    assert result.result.summary["missing_inputs"] == [
        "trade_level_action_facts",
        "trade_execution_metadata",
    ]
    assert result.result.summary["blocked_components"] == [
        "realized_trading",
        "action_attribution",
    ]
    assert result.result.facets["action_details"] == []
    assert result.result.warnings
    assert "unavailable" in result.result.warnings[0].message.lower()


def test_product_category_adapter_rejects_formal_basis_with_scenario_rate_pct():
    """Adapter must reject formal+rate even if a caller bypasses AnalysisQuery validation."""
    adapter_module = load_module(
        "backend.app.services.analysis_adapters",
        "backend/app/services/analysis_adapters.py",
    )

    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter("placeholder.duckdb")

    import pytest

    bad_query = SimpleNamespace(
        consumer="analysis_service",
        analysis_key="product_category_pnl",
        report_date="2026-02-28",
        basis="formal",
        view="monthly",
        scenario_rate_pct=2.5,
    )

    with pytest.raises(ValueError, match="scenario_rate_pct is only allowed when basis"):
        adapter.execute(bad_query)  # type: ignore[arg-type]


def test_product_category_adapter_rejects_analytical_basis():
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    adapter_module = load_module(
        "backend.app.services.analysis_adapters",
        "backend/app/services/analysis_adapters.py",
    )

    adapter = adapter_module.ProductCategoryPnlAnalysisAdapter("placeholder.duckdb")

    import pytest

    with pytest.raises(ValueError):
        adapter.execute(
            schema_module.AnalysisQuery(
                consumer="analysis_service",
                analysis_key="product_category_pnl",
                report_date="2026-02-28",
                basis="analytical",
                view="monthly",
            )
        )


def test_bond_action_placeholder_rejects_scenario_basis():
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    adapter_module = load_module(
        "backend.app.services.analysis_adapters",
        "backend/app/services/analysis_adapters.py",
    )

    import pytest

    with pytest.raises(ValueError):
        adapter_module.build_bond_action_attribution_placeholder_envelope(
            schema_module.AnalysisQuery(
                consumer="analysis_service",
                analysis_key="bond_action_attribution",
                report_date="2026-03-31",
                basis="scenario",
                view="MoM",
                scenario_rate_pct=2.5,
            )
        )


def test_product_category_service_delegates_to_unified_analysis_service(monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    result_meta_module = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )
    service_module = load_module(
        "backend.app.services.product_category_pnl_service",
        "backend/app/services/product_category_pnl_service.py",
    )

    captured: dict[str, object] = {}

    class FakeAnalysisService:
        def execute(self, query):
            captured["query"] = query
            return schema_module.AnalysisResultEnvelope(
                result_meta=result_meta_module.ResultMeta(
                    trace_id="tr_product_category_analysis",
                    basis="formal",
                    result_kind="product_category_pnl.detail",
                    formal_use_allowed=True,
                    source_version="sv_analysis",
                    vendor_version="vv_none",
                    rule_version="rv_analysis",
                    cache_version="cv_analysis",
                    quality_flag="ok",
                    scenario_flag=False,
                ),
                result=schema_module.AnalysisResultPayload(
                    report_date="2026-02-28",
                    analysis_key="product_category_pnl",
                    basis="formal",
                    view="monthly",
                    rows=[
                        {
                            "category_id": "asset_total",
                            "category_name": "资产合计",
                            "side": "asset",
                            "level": 0,
                            "view": "monthly",
                            "report_date": "2026-02-28",
                            "baseline_ftp_rate_pct": "1.50",
                            "cnx_scale": "100",
                            "cny_scale": "80",
                            "foreign_scale": "20",
                            "cnx_cash": "10",
                            "cny_cash": "8",
                            "foreign_cash": "2",
                            "cny_ftp": "1",
                            "foreign_ftp": "0.2",
                            "cny_net": "9",
                            "foreign_net": "1.8",
                            "business_net_income": "10.8",
                            "weighted_yield": "1.6",
                            "is_total": True,
                            "children": [],
                            "scenario_rate_pct": None,
                        },
                        {
                            "category_id": "liability_total",
                            "category_name": "负债合计",
                            "side": "liability",
                            "level": 0,
                            "view": "monthly",
                            "report_date": "2026-02-28",
                            "baseline_ftp_rate_pct": "1.50",
                            "cnx_scale": "50",
                            "cny_scale": "40",
                            "foreign_scale": "10",
                            "cnx_cash": "3",
                            "cny_cash": "2",
                            "foreign_cash": "1",
                            "cny_ftp": "0.5",
                            "foreign_ftp": "0.1",
                            "cny_net": "2.5",
                            "foreign_net": "0.9",
                            "business_net_income": "3.4",
                            "weighted_yield": "1.2",
                            "is_total": True,
                            "children": [],
                            "scenario_rate_pct": None,
                        },
                        {
                            "category_id": "grand_total",
                            "category_name": "总计",
                            "side": "all",
                            "level": 0,
                            "view": "monthly",
                            "report_date": "2026-02-28",
                            "baseline_ftp_rate_pct": "1.50",
                            "cnx_scale": "150",
                            "cny_scale": "120",
                            "foreign_scale": "30",
                            "cnx_cash": "13",
                            "cny_cash": "10",
                            "foreign_cash": "3",
                            "cny_ftp": "1.5",
                            "foreign_ftp": "0.3",
                            "cny_net": "11.5",
                            "foreign_net": "2.7",
                            "business_net_income": "14.2",
                            "weighted_yield": "1.4",
                            "is_total": True,
                            "children": [],
                            "scenario_rate_pct": None,
                        },
                    ],
                    summary={
                        "available_views": ["monthly", "qtd"],
                        "asset_total": {"category_id": "asset_total"},
                        "liability_total": {"category_id": "liability_total"},
                        "grand_total": {"category_id": "grand_total"},
                    },
                ),
            )

    monkeypatch.setattr(
        service_module,
        "build_analysis_service",
        lambda duckdb_path: FakeAnalysisService(),
    )

    payload = service_module.product_category_pnl_envelope(
        duckdb_path="ignored.duckdb",
        report_date="2026-02-28",
        view="monthly",
    )

    assert captured["query"].analysis_key == "product_category_pnl"
    assert payload["result"]["view"] == "monthly"
    assert payload["result_meta"]["result_kind"] == "product_category_pnl.detail"


def test_product_category_service_warns_when_totals_are_incomplete(monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    result_meta_module = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )
    service_module = load_module(
        "backend.app.services.product_category_pnl_service",
        "backend/app/services/product_category_pnl_service.py",
    )

    def row(category_id: str, category_name: str, side: str, business_net_income: str):
        return {
            "category_id": category_id,
            "category_name": category_name,
            "side": side,
            "level": 0,
            "view": "monthly",
            "report_date": "2026-02-28",
            "baseline_ftp_rate_pct": "1.50",
            "cnx_scale": "0",
            "cny_scale": "0",
            "foreign_scale": "0",
            "cnx_cash": "0",
            "cny_cash": "0",
            "foreign_cash": "0",
            "cny_ftp": "0",
            "foreign_ftp": "0",
            "cny_net": "0",
            "foreign_net": "0",
            "business_net_income": business_net_income,
            "weighted_yield": None,
            "is_total": True,
            "children": [],
            "scenario_rate_pct": None,
        }

    class FakeAnalysisService:
        def execute(self, query):
            return schema_module.AnalysisResultEnvelope(
                result_meta=result_meta_module.ResultMeta(
                    trace_id="tr_product_category_analysis",
                    basis="formal",
                    result_kind="product_category_pnl.detail",
                    formal_use_allowed=True,
                    source_version="sv_analysis",
                    vendor_version="vv_none",
                    rule_version="rv_analysis",
                    cache_version="cv_analysis",
                    quality_flag="ok",
                    scenario_flag=False,
                ),
                result=schema_module.AnalysisResultPayload(
                    report_date="2026-02-28",
                    analysis_key="product_category_pnl",
                    basis="formal",
                    view="monthly",
                    rows=[
                        row("asset_total", "资产合计", "asset", "10.00"),
                        row("liability_total", "负债合计", "liability", "3.00"),
                        row("grand_total", "总计", "all", "14.00"),
                    ],
                    summary={
                        "available_views": ["monthly"],
                        "asset_total": {"category_id": "asset_total"},
                        "liability_total": {"category_id": "liability_total"},
                        "grand_total": {"category_id": "grand_total"},
                    },
                ),
            )

    monkeypatch.setattr(
        service_module,
        "build_analysis_service",
        lambda duckdb_path: FakeAnalysisService(),
    )

    payload = service_module.product_category_pnl_envelope(
        duckdb_path="ignored.duckdb",
        report_date="2026-02-28",
        view="monthly",
    )

    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["grand_total"]["business_net_income"] == "14.00"


def test_bond_action_service_uses_placeholder_envelope_builder(monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    result_meta_module = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )
    service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    captured: dict[str, object] = {}

    def fake_placeholder(query):
        captured["query"] = query
        return schema_module.AnalysisResultEnvelope(
            result_meta=result_meta_module.ResultMeta(
                trace_id="tr_bond_action_analysis",
                basis="formal",
                result_kind="bond_analytics.action_attribution",
                formal_use_allowed=True,
                source_version="sv_analysis",
                vendor_version="vv_none",
                rule_version="rv_analysis",
                cache_version="cv_analysis",
                quality_flag="warning",
                scenario_flag=False,
                source_surface="bond_analytics",
            ),
            result=schema_module.AnalysisResultPayload(
                report_date="2026-03-31",
                analysis_key="bond_action_attribution",
                basis="formal",
                summary={
                    "period_type": "MoM",
                    "period_start": "2026-03-01",
                    "period_end": "2026-03-31",
                    "total_actions": 0,
                    "total_pnl_from_actions": "0",
                    "period_start_duration": "0",
                    "period_end_duration": "0",
                    "duration_change_from_actions": "0",
                    "period_start_dv01": "0",
                    "period_end_dv01": "0",
                    "status": "unavailable",
                    "available_components": [],
                    "missing_inputs": ["trade_level_action_facts"],
                    "blocked_components": ["action_attribution"],
                },
                facets={
                    "by_action_type": [],
                    "action_details": [],
                },
                warnings=[
                    schema_module.AnalysisWarning(
                        code="empty",
                        level="warning",
                        message="no attribution rows",
                    )
                ],
            ),
        )

    monkeypatch.setattr(
        service_module,
        "build_bond_action_attribution_placeholder_envelope",
        fake_placeholder,
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert captured["query"].analysis_key == "bond_action_attribution"
    assert payload["result"]["period_type"] == "MoM"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.action_attribution"
    assert payload["result_meta"]["source_surface"] == "bond_analytics"
    assert payload["result"]["status"] == "unavailable"
    assert payload["result"]["missing_inputs"] == ["trade_level_action_facts"]


def test_bond_action_service_uses_schema_default_status_when_summary_omits_it(monkeypatch):
    service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    response_module = load_module(
        "backend.app.schemas.bond_analytics",
        "backend/app/schemas/bond_analytics.py",
    )

    def fake_placeholder(_query):
        return schema_module.AnalysisResultEnvelope(
            result_meta=schema_module.ResultMeta(
                trace_id="tr_analysis",
                basis="formal",
                result_kind="bond_analytics.action_attribution",
                formal_use_allowed=True,
                source_version="sv_analysis",
                vendor_version="vv_none",
                rule_version="rv_analysis",
                cache_version="cv_analysis",
                quality_flag="warning",
                scenario_flag=False,
                source_surface="bond_analytics",
            ),
            result=schema_module.AnalysisResultPayload(
                report_date="2026-03-31",
                analysis_key="bond_action_attribution",
                basis="formal",
                summary={
                    "period_type": "MoM",
                    "period_start": "2026-03-01",
                    "period_end": "2026-03-31",
                    "total_actions": 0,
                    "total_pnl_from_actions": "0",
                    "period_start_duration": "0",
                    "period_end_duration": "0",
                    "duration_change_from_actions": "0",
                    "period_start_dv01": "0",
                    "period_end_dv01": "0",
                },
                facets={
                    "by_action_type": [],
                    "action_details": [],
                },
                warnings=[],
            ),
        )

    monkeypatch.setattr(
        service_module,
        "build_bond_action_attribution_placeholder_envelope",
        fake_placeholder,
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert payload["result"]["status"] == response_module.ActionAttributionResponse.model_fields["status"].default
