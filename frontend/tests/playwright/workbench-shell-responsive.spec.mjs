import { expect, test } from "@playwright/test";

test.beforeEach(async ({ context, baseURL }) => {
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(baseURL).origin || /^\/(api|ui|health)(\/|$)/.test(url.pathname)) return route.abort();
    return route.continue();
  });
});

const NAV_VIEWPORTS = [
  { width: 390, height: 844, label: "mobile-390" },
  { width: 768, height: 1024, label: "tablet-768" },
  { width: 1024, height: 900, label: "desktop-1024" },
];

const GLOBAL_NAV_TRIGGER_PATTERN = /工作台|导航|菜单|menu|navigation/i;

// Every page uses the same primary navigation as the homepage.
const STOCK_NAVIGATION = [
  { name: "经营日报", href: "/" },
  { name: "组合工作台", href: "/portfolio" },
  { name: "市场工作台", href: "/market-overview" },
  { name: "风险工作台", href: "/risk-overview" },
  { name: "绩效工作台", href: "/performance" },
  { name: "报表与数据", href: "/reports" },
];

async function openStockShell(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("stock-analysis-page")).toBeVisible({ timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
}

async function ensureGlobalNavigationReachable(page) {
  const nav = page.getByTestId("workbench-group-nav");

  if (await nav.isVisible().catch(() => false)) {
    return nav;
  }

  const exactTrigger = page.getByRole("button", { name: "打开主导航" });
  const trigger = (await exactTrigger.count())
    ? exactTrigger.first()
    : page.getByRole("button", { name: GLOBAL_NAV_TRIGGER_PATTERN }).first();
  await expect(
    trigger,
    "Expected either a visible global navigation rail or a visible navigation trigger.",
  ).toBeVisible({ timeout: 5_000 });
  await trigger.click();
  await expect(nav).toBeVisible({ timeout: 10_000 });
  return nav;
}

async function collectLinkBoxes(nav) {
  return nav.getByRole("link").evaluateAll((links) =>
    links.map((link) => {
      const rect = link.getBoundingClientRect();
      return {
        text: (link.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80),
        left: rect.left,
        right: rect.right,
        width: rect.width,
        height: rect.height,
      };
    }),
  );
}

async function collectFocusableSequence(page, selector, maxSteps = 24) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });

  const sequence = [];
  for (let step = 1; step <= maxSteps; step += 1) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate((targetSelector) => {
      const activeElement = document.activeElement;
      const targets = [...document.querySelectorAll(targetSelector)];
      const matchedTarget = targets.find(
        (target) => target === activeElement || target.contains(activeElement),
      );

      if (!(activeElement instanceof HTMLElement)) {
        return { tagName: null, text: "", matched: false };
      }

      return {
        tagName: activeElement.tagName.toLowerCase(),
        text: (activeElement.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80),
        matched: Boolean(matchedTarget),
      };
    }, selector);
    sequence.push({ step, ...active });
    if (active.matched) {
      return { matchedStep: step, sequence };
    }
  }

  return { matchedStep: null, sequence };
}

for (const viewport of NAV_VIEWPORTS) {
  test(`stock-analysis keeps global navigation reachable at ${viewport.label}`, async ({ page }) => {
    await openStockShell(page, viewport);

    const nav = await ensureGlobalNavigationReachable(page);
    const navLinks = nav.getByRole("link");
    await expect(navLinks.first()).toBeVisible();
    await expect(navLinks).toHaveCount(STOCK_NAVIGATION.length);
    for (const item of STOCK_NAVIGATION) {
      const link = nav.getByRole("link", { name: item.name, exact: true });
      await expect(link).toHaveCount(1);
      await expect(link).toHaveAttribute("href", item.href);
    }
    expect(new Set(await navLinks.evaluateAll((links) => links.map((link) => link.getAttribute("href")))).size)
      .toBe(STOCK_NAVIGATION.length);
    await page.waitForTimeout(250);
    const linkBoxes = await collectLinkBoxes(nav);
    for (const link of linkBoxes) {
      expect(link.width, `${link.text} should have a rendered width`).toBeGreaterThan(0);
      expect(link.height, `${link.text} should have a rendered height`).toBeGreaterThan(0);
      expect(link.left, `${link.text} should stay within the left viewport edge`).toBeGreaterThanOrEqual(-1);
      expect(link.right, `${link.text} should stay within the right viewport edge`).toBeLessThanOrEqual(
        viewport.width + 1,
      );
    }

    const activeLink = nav.locator('a[data-active="true"]').first();
    await expect(activeLink).toBeVisible();

    const keyboardEvidence = await collectFocusableSequence(page, '[data-testid="workbench-group-nav"] a');
    expect(
      keyboardEvidence.matchedStep,
      `Expected keyboard focus to reach a global navigation link. Sequence: ${JSON.stringify(keyboardEvidence.sequence, null, 2)}`,
    ).not.toBeNull();
    const focusedHrefs = new Set();
    for (let step = 0; step < STOCK_NAVIGATION.length; step += 1) {
      const href = await page.evaluate(() => document.activeElement?.closest('[data-testid="workbench-group-nav"] a')?.getAttribute("href"));
      expect(href, "Every navigation item should be reachable in one keyboard pass").toBeTruthy();
      expect(focusedHrefs.has(href), "Keyboard order must not repeat a navigation item").toBe(false);
      focusedHrefs.add(href);
      await page.keyboard.press("Tab");
    }
    expect([...focusedHrefs].sort()).toEqual(STOCK_NAVIGATION.map((item) => item.href).sort());

    const noHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 2,
    );
    expect(noHorizontalOverflow).toBe(true);
  });
}
