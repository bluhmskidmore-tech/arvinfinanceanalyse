from __future__ import annotations

from scripts.mcp.moss_project_mcp import (
    LineageEvidenceProvider,
    MetricContractsProvider,
    page_evidence_readiness,
    page_trace_bundle,
    product_page_trace_bundles,
)


WORKBENCH_ENDPOINT = "/ui/market-data/stock-analysis/workbench"
WORKBENCH_RESULT_KIND = "market_data.stock_analysis.workbench"
WORKBENCH_CONTRACT_URI = (
    "moss://metric-contracts/doc/stock_analysis_workbench_api_contract"
)


def test_stock_analysis_trace_bundle_routes_the_implemented_workbench_without_formal_promotion() -> None:
    bundles = product_page_trace_bundles()

    for alias in (
        "stock-analysis",
        "/stock-analysis",
        "GAP-STOCK-ANALYSIS-PAGE",
        WORKBENCH_ENDPOINT,
        WORKBENCH_RESULT_KIND,
    ):
        bundle = page_trace_bundle(bundles, alias)
        assert bundle["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
        assert bundle["primary_api"] == WORKBENCH_ENDPOINT

    stock = page_trace_bundle(bundles, "stock-analysis")
    assert "/ui/market-data/livermore" in stock["supporting_apis"]
    assert "docs/stock_analysis_workbench_api_contract.md" in stock["contract_docs"]
    assert "backend/app/services/stock_analysis_workbench_service.py" in stock["backend_touchpoints"]
    assert "tests/test_stock_analysis_workbench_api.py" in stock["test_touchpoints"]
    assert any("no independent golden sample" in item for item in stock["verification_focus"])

    readiness = page_evidence_readiness(bundles, ["stock-analysis"])["pages"][0]
    assert readiness["approval_status"] == "gap_or_observational"
    assert readiness["formal_use_allowed"] is False
    assert readiness["formal_envelope_allowed"] is False


def test_metric_contract_provider_exposes_the_implemented_observational_contract() -> None:
    provider = MetricContractsProvider()
    resource_uris = {resource["uri"] for resource in provider.resources()}

    assert WORKBENCH_CONTRACT_URI in resource_uris
    resource = provider.read_resource(WORKBENCH_CONTRACT_URI)
    contract_text = resource["text"]
    assert "Status: implemented, observational only; governance closure pending" in contract_text
    assert f"Primary endpoint: `GET {WORKBENCH_ENDPOINT}`" in contract_text
    assert "formal_use_allowed=false" in contract_text


def test_stock_analysis_lineage_queries_expand_to_the_workbench_identity() -> None:
    expected = {
        WORKBENCH_ENDPOINT,
        WORKBENCH_RESULT_KIND,
        "rv_stock_analysis_workbench_v1",
        "cv_stock_analysis_workbench_v1",
    }

    for query in ("gap-stock-analysis-page", "stock-analysis", "/stock-analysis"):
        assert expected <= set(LineageEvidenceProvider._QUERY_EXPANSIONS[query])
