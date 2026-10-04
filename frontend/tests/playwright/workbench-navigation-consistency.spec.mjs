import { expect, test } from "@playwright/test";

const routes = [
  "/portfolio", "/market-overview", "/risk-overview", "/performance", "/reports",
  "/stock-analysis", "/bond-analysis", "/balance-analysis", "/balance-movement-analysis",
  "/ledger-pnl", "/product-category-pnl", "/pnl-attribution", "/cross-asset",
  "/market-data", "/macro-toolkit", "/platform-config", "/agent", "/not-a-page",
  "/operations-analysis", "/market-finance", "/bond-trading-desk", "/team-performance",
  "/decision-items", "/liability-analytics", "/macro-observation", "/source-preview",
  "/bond-dashboard", "/positions", "/average-balance", "/bank-ledger-dashboard",
  "/risk-tensor", "/concentration-monitor", "/cashflow-projection", "/kpi", "/news-events",
  "/pnl", "/pnl-bridge", "/cube-query", "/pnl-by-business", "/pnl-by-business-insights",
];

async function railAppearance(page) {
  return page.locator("#workbench-primary-navigation").evaluate((rail) => {
    const selectors = [
      ":scope", ".workbench-shell-rail-brand-wrap", ".workbench-shell-rail-mark",
      ".workbench-shell-rail-product-name", ".workbench-shell-nav-section",
      ".workbench-group-nav-shell", '.workbench-shell-group-link[data-active="false"]',
      '.workbench-shell-group-link[data-active="false"] .workbench-shell-group-label',
      ".workbench-shell-agent-nav", ".workbench-shell-agent-nav__link",
      ".workbench-shell-agent-nav__hint", ".workbench-shell-rail-section",
      '.workbench-shell-support-link[data-active="false"]',
    ];
    return selectors.map((selector) => {
      const element = selector === ":scope" ? rail : rail.querySelector(selector);
      if (!element) return null;
      const css = getComputedStyle(element);
      if (css.display === "none") return { display: "none" };
      const properties = [
        "padding", "margin", "gap", "height", "width", "fontFamily", "fontSize",
        "fontWeight", "lineHeight", "letterSpacing", "color", "backgroundColor",
        "borderRadius", "display",
      ];
      // The chat link becomes selected on /agent; compare its geometry here.
      return Object.fromEntries(properties.filter((key) =>
        selector !== ".workbench-shell-agent-nav__link" || !["color", "backgroundColor"].includes(key),
      ).map((key) => [key, css[key]]));
    });
  });
}

test("all shell variants retain the homepage navigation appearance", async ({ page, context, baseURL }) => {
  test.setTimeout(180_000);
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(baseURL).origin || /^\/(api|ui|health)(\/|$)/.test(url.pathname)) return route.abort();
    return route.continue();
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("dashboard-home-page")).toBeVisible();
  await page.waitForTimeout(500);
  const homepage = await railAppearance(page);
  const hrefs = await page.getByTestId("workbench-group-nav").locator("a").evaluateAll(
    (links) => links.map((link) => link.getAttribute("href")),
  );
  for (const path of routes) {
    await page.goto(path);
    await expect(page.locator("#workbench-primary-navigation")).toBeVisible();
    await page.waitForTimeout(700);
    expect.soft(await railAppearance(page), path).toEqual(homepage);
    expect(await page.getByTestId("workbench-group-nav").locator("a").evaluateAll(
      (links) => links.map((link) => link.getAttribute("href")),
    ), path).toEqual(hrefs);
  }
  // Exercise SPA navigation after the lazy route styles have accumulated.
  await page.getByTestId("workbench-group-nav").getByRole("link", { name: "经营日报", exact: true }).click();
  await expect(page.getByTestId("dashboard-home-page")).toBeVisible();
  await page.mouse.move(1000, 20);
  await expect.poll(() => railAppearance(page)).toEqual(homepage);
});
