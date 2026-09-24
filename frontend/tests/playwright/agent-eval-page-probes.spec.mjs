import { expect, test } from "@playwright/test";

const routes = [
  {
    slug: "dashboard-home",
    path: "/",
    readyTestId: "dashboard-home-page",
    businessTestId: "dashboard-home-hero",
  },
  {
    slug: "balance-analysis",
    path: "/balance-analysis",
    readyTestId: "balance-analysis-page",
    businessTestId: "balance-analysis-cockpit-kpis",
  },
  {
    slug: "bond-analysis",
    path: "/bond-analysis",
    readyTestId: "bond-analysis-overview",
    businessTestId: "bond-analysis-top-cockpit",
  },
  {
    slug: "pnl-attribution",
    path: "/pnl-attribution",
    readyTestId: "pnl-attribution-page-title",
    businessTestId: "pnl-attribution-decision-strip",
  },
  {
    slug: "product-category-pnl",
    path: "/product-category-pnl",
    readyTestId: "product-category-page",
    businessTestId: "product-category-summary",
  },
  {
    slug: "risk-tensor",
    path: "/risk-tensor",
    readyTestId: "risk-tensor-page",
    businessTestId: "risk-tensor-brief",
  },
];

async function awaitMockReadSettled(page, slug) {
  switch (slug) {
    case "dashboard-home":
      await expect(page.getByTestId("dashboard-home-mock-banner")).toBeVisible();
      await expect(page.getByTestId("dashboard-home-kpi-aum")).toHaveAttribute("data-state", "ready");
      break;
    case "balance-analysis":
      await expect(page.getByRole("combobox", { name: "balance-report-date" })).not.toHaveValue("");
      await expect(
        page.getByTestId("balance-analysis-cockpit-kpis").locator(".balance-analysis-kpi-cell__value").first(),
      ).toHaveText(/[0-9]/);
      break;
    case "bond-analysis":
      await expect(page.getByTestId("bond-analysis-daily-judgment")).toContainText(
        /核心读面 已返回.*核心读面可用/,
      );
      break;
    case "pnl-attribution":
      await expect(page.getByTestId("pnl-attribution-current-view-meta")).toBeVisible();
      await expect(page.getByTestId("pnl-attribution-decision-strip").locator("[data-quality]")).not.toHaveAttribute(
        "data-quality",
        "pending",
      );
      break;
    case "product-category-pnl":
      await expect(page.getByTestId("product-category-data-health")).toHaveAttribute(
        "data-health-state",
        "ready",
      );
      break;
    case "risk-tensor":
      // The brief is rendered only after a risk tensor result is available.
      await expect(page.getByTestId("risk-tensor-brief")).toContainText("风险判读");
      break;
    default:
      throw new Error(`Missing mock read assertion for ${slug}`);
  }
}

for (const route of routes) {
  test(`agent-eval-page:${route.slug} loads the mock business view without runtime errors`, async ({
    page,
  }) => {
    const runtimeErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        runtimeErrors.push(`console: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => {
      runtimeErrors.push(`pageerror: ${error.message}`);
    });

    const response = await page.goto(route.path, { waitUntil: "domcontentloaded" });
    expect(response?.ok(), `${route.path} should return a successful response`).toBe(true);
    const mockRibbon = page.locator("#data-mode-ribbon");
    await expect(mockRibbon).toBeVisible({ timeout: 60_000 });
    await expect(mockRibbon).toContainText("MOCK 模式");
    await expect(page.getByTestId(route.readyTestId)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(route.businessTestId)).toBeVisible({ timeout: 60_000 });
    await awaitMockReadSettled(page, route.slug);
    // Keep collecting errors briefly after the route-specific business read settles.
    await page.waitForTimeout(500);
    expect(runtimeErrors, `${route.path} emitted browser runtime errors`).toEqual([]);
  });
}
