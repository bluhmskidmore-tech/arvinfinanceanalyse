from tests.helpers import load_module


def test_build_preflight_report_marks_missing_prerequisites_as_blocked(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    responses = {
        "http://api/health": module.ProbeResult(
            name="",
            url="http://api/health",
            status=200,
            outcome="pass",
        ),
        "http://frontend/": module.ProbeResult(
            name="",
            url="http://frontend/",
            status=200,
            outcome="pass",
        ),
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

    monkeypatch.setattr(module, "_fetch_json", lambda url, timeout_seconds=20: responses[url])

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert report["summary"] == {"pass": 5, "blocked": 3, "skipped": 3}
    assert report["required_failures"] == [
        "risk_tensor",
        "balance_dates",
        "balance_overview",
        "pnl_dates",
        "pnl_overview",
        "pnl_bridge",
    ]
    probe_names = {probe["name"]: probe for probe in report["probes"]}
    assert probe_names["balance_overview"]["outcome"] == "skipped"
    assert probe_names["pnl_overview"]["outcome"] == "skipped"
    assert probe_names["pnl_bridge"]["outcome"] == "skipped"
    assert probe_names["risk_tensor"]["outcome"] == "blocked"


def test_build_preflight_report_passes_when_all_required_probes_succeed(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    urls = [
        "http://api/health",
        "http://frontend/",
        "http://api/api/bond-analytics/dates",
        "http://api/api/bond-analytics/return-decomposition?report_date=2025-12-31&period_type=MoM&asset_class=all&accounting_class=all",
        "http://api/api/risk/tensor/dates",
        "http://api/api/risk/tensor?report_date=2025-12-31",
        "http://api/ui/balance-analysis/dates",
        "http://api/ui/balance-analysis/overview?report_date=2025-12-31&position_scope=all&currency_basis=CNY",
        "http://api/api/pnl/dates",
        "http://api/api/pnl/overview?report_date=2025-12-31",
        "http://api/api/pnl/bridge?report_date=2025-12-31",
    ]

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda url, timeout_seconds=20: module.ProbeResult(
            name="",
            url=url,
            status=200,
            outcome="pass",
            result_kind="demo.kind",
            basis="formal",
            report_dates=["2025-12-31"] if url.endswith("/dates") else None,
        ),
    )

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "pass"
    assert report["summary"] == {"pass": len(urls), "blocked": 0, "skipped": 0}
    assert report["required_failures"] == []


def test_build_preflight_report_treats_skipped_required_probe_as_blocking(monkeypatch):
    module = load_module(
        "scripts.governed_phase2_preflight",
        "scripts/governed_phase2_preflight.py",
    )

    responses = {
        "http://api/health": module.ProbeResult(name="", url="http://api/health", status=200, outcome="pass"),
        "http://frontend/": module.ProbeResult(name="", url="http://frontend/", status=200, outcome="pass"),
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

    monkeypatch.setattr(module, "_fetch_json", lambda url, timeout_seconds=20: responses[url])

    report = module.build_preflight_report(api_base="http://api", frontend_base="http://frontend")

    assert report["verdict"] == "blocked"
    assert "bond_return_decomposition" in report["required_failures"]
