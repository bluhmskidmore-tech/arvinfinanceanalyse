import { expect, test } from "@playwright/test";

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test("risk overview keeps its desktop content out of the dashboard-home header row", async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP_VIEWPORT);
  await page.goto("/risk-overview", { waitUntil: "domcontentloaded" });

  const riskPage = page.getByTestId("risk-overview-page");
  const hero = page.getByTestId("risk-overview-hero");
  await expect(riskPage).toBeVisible({ timeout: 60_000 });
  await expect(hero).toBeVisible({ timeout: 60_000 });

  const geometry = await riskPage.evaluate((element) => {
    const layout = element.querySelector(":scope > main");
    const heroElement = element.querySelector('[data-testid="risk-overview-hero"]');
    if (!(layout instanceof HTMLElement) || !(heroElement instanceof HTMLElement)) {
      throw new Error("risk overview layout and hero must be rendered");
    }

    const heroBox = heroElement.getBoundingClientRect();
    return {
      layoutClientHeight: layout.clientHeight,
      layoutScrollHeight: layout.scrollHeight,
      heroTop: heroBox.top,
      pageOverflowY: getComputedStyle(element).overflowY,
    };
  });

  expect(geometry.layoutClientHeight).toBeGreaterThan(DESKTOP_VIEWPORT.height / 2);
  // The sticky rail owns an 18px decorative tail; allow that existing paint-only overflow.
  expect(geometry.layoutScrollHeight - geometry.layoutClientHeight).toBeLessThanOrEqual(24);
  expect(geometry.heroTop).toBeLessThan(DESKTOP_VIEWPORT.height);
  expect(geometry.pageOverflowY).not.toBe("hidden");
});

test("dashboard home retains its owner-only desktop shell", async ({ page }) => {
  await page.setViewportSize(DESKTOP_VIEWPORT);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const dashboard = page.getByTestId("dashboard-home-page");
  const scrollRoot = page.getByTestId("dashboard-home-scroll-root");

  await expect(dashboard).toBeVisible({ timeout: 60_000 });
  await expect(scrollRoot).toBeVisible({ timeout: 60_000 });

  const geometry = await dashboard.evaluate((element) => {
    const layout = element.querySelector(
      '[data-testid="dashboard-home-scroll-root"]',
    );
    const pageStyle = getComputedStyle(element);
    const layoutStyle = layout ? getComputedStyle(layout) : null;

    return {
      gridTemplateRows: pageStyle.gridTemplateRows,
      pageOverflowY: pageStyle.overflowY,
      layoutOverflowY: layoutStyle?.overflowY ?? null,
      layoutClientHeight: layout?.clientHeight ?? 0,
    };
  });

  expect(geometry.gridTemplateRows).toMatch(/^42px\s/);
  expect(geometry.pageOverflowY).toBe("hidden");
  expect(geometry.layoutOverflowY).toBe("auto");
  expect(geometry.layoutClientHeight).toBeGreaterThan(
    DESKTOP_VIEWPORT.height / 2,
  );
});
