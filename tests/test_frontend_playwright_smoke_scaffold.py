import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_playwright_smoke_scaffold_uses_safe_server_probe_and_artifacts():
    config_path = ROOT / "frontend" / "playwright.config.mjs"
    spec_path = ROOT / "frontend" / "tests" / "playwright" / "a11y-visual-smoke.spec.mjs"
    insights_spec_path = (
        ROOT
        / "frontend"
        / "tests"
        / "playwright"
        / "pnl-by-business-insights-smoke.spec.mjs"
    )
    monthly_spec_path = (
        ROOT
        / "frontend"
        / "tests"
        / "playwright"
        / "monthly-operating-analysis-audit-smoke.spec.mjs"
    )

    assert config_path.exists(), f"Missing Playwright config: {config_path}"
    assert spec_path.exists(), f"Missing Playwright smoke spec: {spec_path}"
    assert insights_spec_path.exists(), f"Missing Insights smoke spec: {insights_spec_path}"
    assert monthly_spec_path.exists(), f"Missing monthly operating analysis smoke spec: {monthly_spec_path}"

    config_text = config_path.read_text(encoding="utf-8")
    assert "../.codex-tmp/playwright-results" in config_text
    assert "MOSS_PLAYWRIGHT_OUTPUT_DIR" in config_text
    assert "outputDir: playwrightOutputDir" in config_text
    assert 'const playwrightPort = process.env.MOSS_PLAYWRIGHT_PORT ?? "5888"' in config_text
    assert 'process.env.MOSS_PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${playwrightPort}`' in config_text
    assert "baseURL: playwrightBaseURL" in config_text
    assert 'process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"' in config_text
    assert "npm run dev -- --host 127.0.0.1 --port ${playwrightPort}" in config_text
    assert 'VITE_DATA_SOURCE: process.env.VITE_DATA_SOURCE ?? "mock"' in config_text
    assert 'const playwrightStatePort = process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"' in config_text
    assert "npm run dev -- --host 127.0.0.1 --port ${playwrightStatePort}" in config_text
    assert 'VITE_DATA_SOURCE: "real"' in config_text

    spec_text = spec_path.read_text(encoding="utf-8")
    assert "@axe-core/playwright" in spec_text
    assert "expect(serverCheck.ok, serverCheck.reason).toBe(true);" in spec_text
    assert "test.skip(!serverCheck.ok" not in spec_text
    assert 'waitUntil: "domcontentloaded"' in spec_text
    assert 'toBeVisible({ timeout: smokePage.readyTimeout ?? 60_000 })' in spec_text
    assert "page.screenshot({" in spec_text
    assert "fullPage: smokePage.screenshotFullPage ?? true" in spec_text
    assert 'smokePage.blockedAxeImpacts ?? ["critical"]' in spec_text
    assert "blockedAxeImpacts.includes(violation.impact)" in spec_text
    assert "excludeSelectors" in spec_text
    assert "axeSelector" in spec_text
    assert "screenshotFullPage" in spec_text
    assert ".ag-theme-alpine" in spec_text
    assert "bond-dashboard-page" in spec_text
    assert "balance-analysis-page" in spec_text
    assert "balance-movement-analysis-page" in spec_text
    assert "product-category-page" in spec_text
    assert "ledger-pnl-page" in spec_text
    assert "positions-page" in spec_text
    assert "operations-layout-preview" in spec_text
    assert "liability-analytics-page" in spec_text
    assert "market-data-page" in spec_text
    assert "macro-toolkit-tailwind-cockpit" in spec_text
    assert "stock-analysis-page" in spec_text
    assert "pnl-attribution-page-title" in spec_text

    insights_spec_text = insights_spec_path.read_text(encoding="utf-8")
    assert "MOSS_PLAYWRIGHT_STATE_BASE_URL" in insights_spec_text
    assert "GS-PNL-BUSINESS-INSIGHTS-A" in insights_spec_text
    assert "pnl-by-business-insights-page" in insights_spec_text
    assert "pnl-by-business-insights-contract-status" in insights_spec_text
    assert "pnl-by-business-insights-contract-review" in insights_spec_text
    assert "pnl-by-business-insights-reconciliation-section" in insights_spec_text
    assert 'violation.impact === "critical"' in insights_spec_text

    monthly_spec_text = monthly_spec_path.read_text(encoding="utf-8")
    assert "MOSS_PLAYWRIGHT_STATE_BASE_URL" in monthly_spec_text
    assert "MOSS_PLAYWRIGHT_STATE_PORT" in monthly_spec_text
    assert "expect(serverCheck.ok, serverCheck.reason).toBe(true);" in monthly_spec_text
    assert "test.skip(!serverCheck.ok" not in monthly_spec_text


def test_frontend_playwright_smoke_covers_high_risk_business_display_routes():
    coverage_report_path = ROOT / "docs" / "audits" / "business-display-coverage-report.json"
    spec_path = ROOT / "frontend" / "tests" / "playwright" / "a11y-visual-smoke.spec.mjs"

    coverage_report = json.loads(coverage_report_path.read_text(encoding="utf-8"))
    spec_text = spec_path.read_text(encoding="utf-8")
    smoke_pages_match = re.search(
        r"const smokePages = \[(?P<body>.*?)\];\s*const flagshipKeyboardPages",
        spec_text,
        re.DOTALL,
    )

    assert smoke_pages_match, "Could not find the smokePages array in the Playwright smoke spec"
    smoke_pages_text = smoke_pages_match.group("body")

    for route in [entry["route"] for entry in coverage_report["routes"]]:
        assert f'path: "{route}"' in smoke_pages_text, f"Missing high-risk smoke route: {route}"

    expected_ready_selectors = {
        "/cashflow-projection": '[data-testid="cashflow-projection-page"]',
        "/concentration-monitor": '[data-testid="concentration-monitor-kpi-grid"]',
        "/team-performance": '[data-testid="team-performance-page"]',
        "/decision-items": '[data-testid="decision-items-page"]',
        "/kpi": '[data-testid="kpi-performance-page"]',
        "/news-events": '[data-testid="news-events-page-title"]',
        "/platform-config": '[data-testid="platform-config-page-title"]',
    }
    for route, ready_selector in expected_ready_selectors.items():
        route_block_match = re.search(
            rf'path: "{re.escape(route)}",(?P<body>.*?)(?:\n  \}},|\n\];)',
            smoke_pages_text,
            re.DOTALL,
        )
        assert route_block_match, f"Missing smoke page block for {route}"
        assert ready_selector in route_block_match.group("body"), f"Missing ready selector for {route}"


def test_frontend_package_exposes_playwright_smoke_scripts():
    package_text = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    assert '"test:a11y-smoke": "playwright test -c playwright.config.mjs"' in package_text
    assert '"test:a11y-smoke:headed": "playwright test -c playwright.config.mjs --headed"' in package_text
    assert '"@playwright/test":' in package_text
    assert '"@axe-core/playwright":' in package_text


def test_ci_runs_frontend_accessibility_smoke_with_local_server():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "VITE_DATA_SOURCE=real npm run build" in workflow
    assert "MOSS_PLAYWRIGHT_USE_WEB_SERVER: \"1\"" in workflow
    assert "npm run test:a11y-smoke" in workflow
