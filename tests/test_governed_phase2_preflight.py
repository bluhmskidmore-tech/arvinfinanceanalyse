from tests.helpers import load_module


def _default_probe_result(module, url: str):
    reserved_urls = {
        "http://api/ui/risk/overview",
        "http://api/ui/home/alerts",
        "http://api/ui/home/contribution",
        "http://api/api/cube/dimensions/bond_analytics",
        "http://api/api/risk/buckets?report_date=2025-12-31",
        "http://api/api/analysis/yield_metrics?report_date=2025-12-31",
        "http://api/api/analysis/liabilities/counterparty?report_date=2025-12-31&top_n=10",
        "http://api/api/liabilities/monthly?year=2025",
    }
    dated_urls = {
        "http://api/api/bond-analytics/dates",
        "http://api/api/risk/tensor/dates",
        "http://api/ui/balance-analysis/dates",
        "http://api/api/pnl/dates",
        "http://api/ui/pnl/product-category/dates",
    }
    status = 503 if url in reserved_urls else 200
    return module.ProbeResult(
        name="",
        url=url,
        status=status,
        outcome="pass" if status == 200 else "blocked",
        result_kind="demo.kind" if status == 200 else None,
        basis="formal" if status == 200 else None,
        report_dates=["2025-12-31"] if url in dated_urls else None,
        detail="reserved" if status == 503 else None,
    )


def test_build_preflight_report_marks_missing_prerequisites_as_blocked(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    overrides = {
        "http://api/api/bond-analytics/dates": module.ProbeResult(
            name="",
            url="http://api/api/bond-analytics/dates",
            status=200,
            outcome="pass",
            result_kind="bond_analytics.dates",
            basis="formal",
            report_dates=["2025-12-31"],
        ),
        "http://api/api/bond-analytics/return-decomposition?report_date=2025-12-31&period_type=MoM&asset_class=all&accounting_class=all": module.ProbeResult(
            name="",
            url="http://api/api/bond-analytics/return-decomposition?report_date=2025-12-31&period_type=MoM&asset_class=all&accounting_class=all",
            status=200,
            outcome="pass",
            result_kind="bond_analytics.return_decomposition",
            basis="formal",
        ),
        "http://api/api/risk/tensor/dates": module.ProbeResult(
            name="",
            url="http://api/api/risk/tensor/dates",
            status=200,
            outcome="pass",
            result_kind="risk.tensor.dates",
            basis="formal",
            report_dates=["2025-12-31"],
        ),
        "http://api/api/risk/tensor?report_date=2025-12-31": module.ProbeResult(
            name="",
            url="http://api/api/risk/tensor?report_date=2025-12-31",
            status=503,
            outcome="blocked",
            detail="Bond analytics lineage missing.",
        ),
        "http://api/ui/balance-analysis/dates": module.ProbeResult(
            name="",
            url="http://api/ui/balance-analysis/dates",
            status=503,
            outcome="blocked",
            detail="Canonical formal lineage unavailable.",
            report_dates=[],
        ),
        "http://api/api/pnl/dates": module.ProbeResult(
            name="",
            url="http://api/api/pnl/dates",
            status=503,
            outcome="blocked",
            detail="Canonical formal lineage unavailable.",
            report_dates=[],
        ),
    }

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: overrides.get(url) or _default_probe_result(module, url),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert set(report["required_failures"]) == {
        "risk_tensor",
        "balance_dates",
        "balance_overview",
        "pnl_dates",
        "pnl_overview",
        "pnl_bridge",
        "executive_pnl_attribution",
    }


def test_build_preflight_report_passes_when_all_required_probes_succeed(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: _default_probe_result(module, url),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "pass"
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["skipped"] == 0
    assert report["summary"]["pass"] == len(report["probes"])
    assert report["required_failures"] == []


def test_build_preflight_report_treats_skipped_required_probe_as_blocking(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    overrides = {
        "http://api/api/bond-analytics/dates": module.ProbeResult(
            name="",
            url="http://api/api/bond-analytics/dates",
            status=200,
            outcome="pass",
            report_dates=[],
        ),
        "http://api/api/risk/tensor/dates": module.ProbeResult(
            name="",
            url="http://api/api/risk/tensor/dates",
            status=200,
            outcome="pass",
            report_dates=["2025-12-31"],
        ),
        "http://api/api/risk/tensor?report_date=2025-12-31": module.ProbeResult(
            name="",
            url="http://api/api/risk/tensor?report_date=2025-12-31",
            status=200,
            outcome="pass",
        ),
        "http://api/ui/balance-analysis/dates": module.ProbeResult(
            name="",
            url="http://api/ui/balance-analysis/dates",
            status=200,
            outcome="pass",
            report_dates=["2025-12-31"],
        ),
        "http://api/ui/balance-analysis/overview?report_date=2025-12-31&position_scope=all&currency_basis=CNY": module.ProbeResult(
            name="",
            url="http://api/ui/balance-analysis/overview?report_date=2025-12-31&position_scope=all&currency_basis=CNY",
            status=200,
            outcome="pass",
        ),
        "http://api/api/pnl/dates": module.ProbeResult(
            name="",
            url="http://api/api/pnl/dates",
            status=200,
            outcome="pass",
            report_dates=["2025-12-31"],
        ),
        "http://api/api/pnl/overview?report_date=2025-12-31": module.ProbeResult(
            name="",
            url="http://api/api/pnl/overview?report_date=2025-12-31",
            status=200,
            outcome="pass",
        ),
        "http://api/api/pnl/bridge?report_date=2025-12-31": module.ProbeResult(
            name="",
            url="http://api/api/pnl/bridge?report_date=2025-12-31",
            status=200,
            outcome="pass",
        ),
    }

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: overrides.get(url) or _default_probe_result(module, url),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert "bond_return_decomposition" in report["required_failures"]


def test_build_preflight_report_blocks_when_excluded_route_is_live(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: (
            module.ProbeResult(
                name="",
                url=url,
                status=200,
                outcome="pass",
                result_kind="demo.kind",
                basis="formal",
                report_dates=None,
            )
            if url == "http://api/ui/risk/overview"
            else _default_probe_result(module, url)
        ),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert "ui_risk_overview" in report["required_failures"]


def test_build_preflight_report_blocks_when_reserved_route_is_live(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: (
            module.ProbeResult(
                name="",
                url=url,
                status=200,
                outcome="pass",
                result_kind="demo.kind",
                basis="formal",
                report_dates=None,
            )
            if url == "http://api/api/risk/buckets?report_date=2025-12-31"
            else _default_probe_result(module, url)
        ),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert "api_risk_buckets_reserved" in report["required_failures"]
