import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

for (const width of [1440, 1280, 1024, 900, 768, 390]) {
  test(`home styles preserve layout and controls when shell CSS loads last at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("dashboard-home-hero-kpi-strip")).toBeVisible({ timeout: 60_000 });
    await page.evaluate(() => document.fonts.ready);
    // Reduced-motion CSS can still retain a nonzero transition duration.
    // Compare settled cascade values, including focus rings, in the same frame.
    await page.addStyleTag({
      content: "*, *::before, *::after { transition: none !important; animation: none !important; }",
    });

    for (const focusSearch of [false, true]) {
      if (focusSearch) {
        await page.getByTestId("dashboard-home-search-box").locator("input").focus();
      }

      const result = await page.evaluate(() => {
        // This guard runs against the Vite server from playwright.config.mjs.
        // Reorder the real stylesheet rather than copying CSS into a test fixture.
        const shell = [...document.querySelectorAll("style[data-vite-dev-id]")]
          .find((node) => node.dataset.viteDevId.endsWith("/dashboardHomeShell.module.css"));
        if (!shell) throw new Error("The Vite homepage shell stylesheet was not loaded.");
        const parent = shell.parentNode;
        const nextSibling = shell.nextSibling;
        const selectors = [
          '[data-testid="dashboard-home-page"]',
          '[data-testid="dashboard-home-toolbar"]',
          '[data-testid="dashboard-home-toolbar"] [data-role]',
          '[data-testid="dashboard-home-toolbar"] button',
          '[data-testid="dashboard-home-toolbar"] input',
          '[data-testid="dashboard-home-search-box"]',
          '[data-testid="dashboard-home-scroll-root"]',
          '[data-testid="dashboard-home-hero"]',
          '[data-testid="dashboard-home-hero-kpi-strip"]',
        ];
        const elements = [...new Set(selectors.flatMap((selector) => [...document.querySelectorAll(selector)]))];
        const properties = [
          "display", "position", "grid-template-columns", "grid-template-rows",
          "gap", "padding", "align-items", "flex-wrap", "background-color", "color",
          "font-size", "line-height", "visibility", "opacity", "border-radius",
          "border-color", "border-width", "border-style",
          "outline", "outline-offset", "box-shadow",
        ];
        const capture = () => elements.map((element) => {
          const box = element.getBoundingClientRect();
          const css = getComputedStyle(element);
          return {
            element: element.getAttribute("data-testid") || element.getAttribute("data-role") || element.tagName,
            box: Object.fromEntries(["x", "y", "width", "height"].map((key) => [key, box[key]])),
            style: Object.fromEntries(properties.map((key) => [key, css.getPropertyValue(key)])),
          };
        });
        try {
          // Force both orders even if the initial import already loaded shell last.
          // Synchronous captures exclude query completion or clock updates.
          document.head.prepend(shell);
          const before = capture();
          document.head.append(shell);
          return { before, after: capture() };
        } finally {
          parent.insertBefore(shell, nextSibling);
        }
      });

      expect(result.after, focusSearch ? "focused search" : "default toolbar").toEqual(result.before);
    }
  });
}
