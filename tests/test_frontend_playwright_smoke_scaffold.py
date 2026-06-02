from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_playwright_smoke_scaffold_uses_safe_server_probe_and_artifacts():
    config_path = ROOT / "frontend" / "playwright.config.mjs"
    spec_path = ROOT / "frontend" / "tests" / "playwright" / "a11y-visual-smoke.spec.mjs"

    assert config_path.exists(), f"Missing Playwright config: {config_path}"
    assert spec_path.exists(), f"Missing Playwright smoke spec: {spec_path}"

    config_text = config_path.read_text(encoding="utf-8")
    assert "../.codex-tmp/playwright-results" in config_text
    assert 'baseURL: process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888"' in config_text
    assert 'process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"' in config_text
    assert "npm run dev -- --host 127.0.0.1 --port 5888" in config_text

    spec_text = spec_path.read_text(encoding="utf-8")
    assert "@axe-core/playwright" in spec_text
    assert 'test.skip(!serverCheck.ok, serverCheck.reason);' in spec_text
    assert "page.screenshot({" in spec_text
    assert "fullPage: smokePage.screenshotFullPage ?? true" in spec_text
    assert "violations.filter((violation) => violation.impact === \"critical\")" in spec_text
    assert "excludeSelectors" in spec_text
    assert "axeSelector" in spec_text
    assert "screenshotFullPage" in spec_text
    assert ".ag-theme-alpine" in spec_text
    assert "fixed-income-dashboard-page" in spec_text
    assert "balance-analysis-page" in spec_text
    assert "product-category-page" in spec_text
    assert "ledger-pnl-page" in spec_text


def test_frontend_package_exposes_playwright_smoke_scripts():
    package_text = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    assert '"test:a11y-smoke": "playwright test -c playwright.config.mjs"' in package_text
    assert '"test:a11y-smoke:headed": "playwright test -c playwright.config.mjs --headed"' in package_text
    assert '"@playwright/test":' in package_text
    assert '"@axe-core/playwright":' in package_text


def test_ci_runs_frontend_accessibility_smoke_with_local_server():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "MOSS_PLAYWRIGHT_USE_WEB_SERVER: \"1\"" in workflow
    assert "npm run test:a11y-smoke" in workflow
