import { expect, test } from "@playwright/test";

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

const liveRoutes = [
  { slug: "dashboard-home", path: "/", readySelector: '[data-testid="dashboard-home-page"]' },
  { slug: "operations-analysis", path: "/operations-analysis", readySelector: '[data-testid="operations-layout-preview"]' },
  { slug: "portfolio", path: "/portfolio", readySelector: '[data-testid="module-workbench-home"]' },
  { slug: "bond-analysis", path: "/bond-analysis", readySelector: '[data-testid="bond-analysis-overview"]' },
  { slug: "bond-trading-desk", path: "/bond-trading-desk", readySelector: '[data-testid="bond-trading-desk-page"]' },
  { slug: "cross-asset", path: "/cross-asset", readySelector: '[data-testid="cross-asset-drivers-page"]' },
  { slug: "team-performance", path: "/team-performance", readySelector: '[data-testid="team-performance-page"]' },
  { slug: "decision-items", path: "/decision-items", readySelector: '[data-testid="decision-items-page"]' },
  { slug: "balance-analysis", path: "/balance-analysis", readySelector: '[data-testid="balance-analysis-page"]' },
  { slug: "balance-movement-analysis", path: "/balance-movement-analysis", readySelector: '[data-testid="balance-movement-analysis-page"]' },
  { slug: "liability-analytics", path: "/liability-analytics", readySelector: '[data-testid="liability-analytics-page"]' },
  { slug: "market-overview", path: "/market-overview", readySelector: '[data-testid="module-workbench-home"]' },
  { slug: "market-data", path: "/market-data", readySelector: '[data-testid="market-data-page"]' },
  { slug: "market-finance", path: "/market-finance", readySelector: '[data-testid="market-finance-workbench"]' },
  { slug: "macro-observation", path: "/macro-observation", readySelector: '[data-testid="macro-observation-readonly-boundary"]' },
  { slug: "macro-toolkit", path: "/macro-toolkit", readySelector: '[data-testid="macro-toolkit-page"]' },
  { slug: "stock-analysis", path: "/stock-analysis", readySelector: '[data-testid="stock-analysis-page"]' },
  { slug: "platform-config", path: "/platform-config", readySelector: '[data-testid="platform-config-page-title"]' },
  { slug: "reports", path: "/reports", readySelector: '[data-testid="module-workbench-home"]' },
  { slug: "bond-dashboard", path: "/bond-dashboard", readySelector: '[data-testid="bond-dashboard-page"]' },
  { slug: "positions", path: "/positions", readySelector: '[data-testid="positions-page"]' },
  { slug: "average-balance", path: "/average-balance", readySelector: '[data-testid="average-balance-page"]' },
  { slug: "ledger-pnl", path: "/ledger-pnl", readySelector: '[data-testid="ledger-pnl-page"]' },
  { slug: "bank-ledger-dashboard", path: "/bank-ledger-dashboard", readySelector: '[data-testid="ledger-dashboard-page"]' },
  { slug: "risk-overview", path: "/risk-overview", readySelector: '[data-testid="module-workbench-home"]' },
  { slug: "risk-tensor", path: "/risk-tensor", readySelector: '[data-testid="risk-tensor-brief"]' },
  { slug: "concentration-monitor", path: "/concentration-monitor", readySelector: '[data-testid="concentration-monitor-contract-status"]' },
  { slug: "cashflow-projection", path: "/cashflow-projection", readySelector: '[data-testid="cashflow-projection-page"]' },
  { slug: "performance", path: "/performance", readySelector: '[data-testid="module-workbench-home"]' },
  { slug: "kpi", path: "/kpi", readySelector: '[data-testid="kpi-performance-page"]' },
  { slug: "news-events", path: "/news-events", readySelector: '[data-testid="news-events-page-title"]' },
  { slug: "product-category-pnl", path: "/product-category-pnl", readySelector: '[data-testid="product-category-page"]' },
  { slug: "pnl", path: "/pnl", readySelector: '[data-testid="formal-pnl-v1-page"]' },
  { slug: "pnl-bridge", path: "/pnl-bridge", readySelector: '[data-testid="pnl-bridge-page"]' },
  { slug: "pnl-attribution", path: "/pnl-attribution", readySelector: '[data-testid="pnl-attribution-page-title"]' },
  { slug: "cube-query", path: "/cube-query", readySelector: '[data-testid="cube-query-page"]' },
  { slug: "pnl-by-business", path: "/pnl-by-business", readySelector: '[data-testid="pnl-by-business-page"]' },
  { slug: "pnl-by-business-insights", path: "/pnl-by-business-insights", readySelector: '[data-testid="pnl-by-business-insights-page"]' },
];

for (const route of liveRoutes) {
  test(`${route.slug} keeps a dark route owner and avoids large light-surface regressions`, async ({
    page,
  }) => {
    await page.setViewportSize(DESKTOP_VIEWPORT);
    await page.goto(route.path, { waitUntil: "domcontentloaded" });
    await expect(page.locator(route.readySelector)).toBeVisible({ timeout: 60_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForTimeout(250);

    const audit = await page.evaluate(({ readySelector }) => {
      const transparentPattern = /^(transparent|rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\))$/i;
      const darkHexPattern = /^#(?:0[0-9a-f]{5}|1[0-9a-f]{5}|2[0-9a-f]{5}|3[0-9a-f]{5}|4[0-9a-f]{5}|5[0-9a-f]{5}|6[0-9a-f]{5}|7[0-9a-f]{5}|8[0-9a-f]{5}|9[0-9a-f]{5}|a[0-9a-f]{5}|b[0-9a-f]{5}|c[0-9a-f]{5})$/i;
      const popupIgnoreSelector = [
        "[role='tooltip']",
        ".ant-tooltip",
        ".ant-popover",
        ".ant-dropdown",
        ".ant-select-dropdown",
        ".ant-picker-dropdown",
        ".ant-message",
        ".ant-notification",
      ].join(",");

      const parseColor = (value) => {
        if (!value || transparentPattern.test(value)) {
          return null;
        }
        const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
        if (!match) {
          return null;
        }
        return [Number(match[1]), Number(match[2]), Number(match[3])];
      };

      const luminance = (rgb) => {
        const normalized = rgb.map((channel) => {
          const unit = channel / 255;
          return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * normalized[0] + 0.7152 * normalized[1] + 0.0722 * normalized[2];
      };

      const resolveEffectiveBackground = (node) => {
        let current = node;
        while (current) {
          const style = window.getComputedStyle(current);
          const background = style.backgroundColor;
          const rgb = parseColor(background);
          if (rgb) {
            return {
              tagName: current.tagName.toLowerCase(),
              testId: current.getAttribute("data-testid"),
              className: current.className,
              background,
              rgb,
              luminance: luminance(rgb),
            };
          }
          current = current.parentElement;
        }
        const bodyColor = window.getComputedStyle(document.body).backgroundColor;
        const bodyRgb = parseColor(bodyColor);
        return {
          tagName: "body",
          testId: null,
          className: document.body.className,
          background: bodyColor,
          rgb: bodyRgb,
          luminance: bodyRgb ? luminance(bodyRgb) : null,
        };
      };

      const routeReady = document.querySelector(readySelector);
      const themeOwner = document.querySelector('[data-moss-theme="dark"]');
      const ownerBackground = themeOwner ? resolveEffectiveBackground(themeOwner) : null;
      const routeRoot = routeReady instanceof HTMLElement ? routeReady : null;

      const routeRootStyle = routeRoot instanceof HTMLElement ? window.getComputedStyle(routeRoot) : null;
      const routeRootOwnBackground = routeRootStyle ? parseColor(routeRootStyle.backgroundColor) : null;
      const routeRootEffectiveBackground = routeRoot ? resolveEffectiveBackground(routeRoot) : null;
      const routeRootParentOwner =
        routeRoot instanceof HTMLElement ? routeRoot.closest('[data-moss-theme="dark"]') : null;

      const routeRootAudit =
        routeRoot instanceof HTMLElement
          ? {
              tagName: routeRoot.tagName.toLowerCase(),
              testId: routeRoot.getAttribute("data-testid"),
              className: routeRoot.className,
              ownerMatches: routeRootParentOwner === themeOwner,
              ownBackground: routeRootStyle?.backgroundColor ?? null,
              ownBackgroundIsTransparent: !routeRootOwnBackground,
              effectiveBackground: routeRootEffectiveBackground?.background ?? null,
              effectiveLuminance: routeRootEffectiveBackground?.luminance ?? null,
              colorScheme: routeRootStyle?.colorScheme ?? null,
              tokenCanvas: routeRootStyle?.getPropertyValue("--dh-api-bg").trim() ?? "",
              tokenCanvasDark: darkHexPattern.test(
                routeRootStyle?.getPropertyValue("--dh-api-bg").trim() ?? "",
              ),
            }
          : null;

      const viewportArea = window.innerWidth * window.innerHeight;
      const sampleCoverage = (node, rect) => {
        const visibleLeft = Math.max(0, rect.left);
        const visibleTop = Math.max(0, rect.top);
        const visibleRight = Math.min(window.innerWidth, rect.right);
        const visibleBottom = Math.min(window.innerHeight, rect.bottom);
        if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) {
          return { visibleArea: 0, exposedPoints: 0, totalPoints: 0 };
        }
        const midX = (visibleLeft + visibleRight) / 2;
        const midY = (visibleTop + visibleBottom) / 2;
        const quarterX = (visibleRight - visibleLeft) / 4;
        const quarterY = (visibleBottom - visibleTop) / 4;
        const points = [
          [midX, midY],
          [midX - quarterX, midY],
          [midX + quarterX, midY],
          [midX, midY - quarterY],
          [midX, midY + quarterY],
        ];
        let exposedPoints = 0;
        for (const [x, y] of points) {
          const topNode = document.elementFromPoint(x, y);
          if (topNode && (topNode === node || node.contains(topNode))) {
            exposedPoints += 1;
          }
        }
        return {
          visibleArea: (visibleRight - visibleLeft) * (visibleBottom - visibleTop),
          exposedPoints,
          totalPoints: points.length,
        };
      };

      const candidates = Array.from(document.body.querySelectorAll("*"))
        .filter((node) => node instanceof HTMLElement)
        .filter((node) => {
          if (node.matches(popupIgnoreSelector) || node.closest(popupIgnoreSelector)) {
            return false;
          }
          const rect = node.getBoundingClientRect();
          const visibleWidth = Math.min(window.innerWidth, rect.right) - Math.max(0, rect.left);
          const visibleHeight = Math.min(window.innerHeight, rect.bottom) - Math.max(0, rect.top);
          if (visibleWidth <= 0 || visibleHeight <= 0) {
            return false;
          }
          if (visibleWidth < window.innerWidth * 0.6 || visibleHeight < window.innerHeight * 0.25) {
            return false;
          }
          if (visibleWidth * visibleHeight < viewportArea * 0.15) {
            return false;
          }
          const style = window.getComputedStyle(node);
          if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) {
            return false;
          }
          if (!parseColor(style.backgroundColor)) {
            return false;
          }
          const coverage = sampleCoverage(node, rect);
          if (coverage.exposedPoints < Math.ceil(coverage.totalPoints / 2)) {
            return false;
          }
          return true;
        })
        .map((node) => {
          const rect = node.getBoundingClientRect();
          const style = window.getComputedStyle(node);
          const rgb = parseColor(style.backgroundColor);
          const coverage = sampleCoverage(node, rect);
          const visibleWidth = Math.min(window.innerWidth, rect.right) - Math.max(0, rect.left);
          const visibleHeight = Math.min(window.innerHeight, rect.bottom) - Math.max(0, rect.top);
          return {
            tagName: node.tagName.toLowerCase(),
            testId: node.getAttribute("data-testid"),
            className: node.className,
            width: Math.round(visibleWidth),
            height: Math.round(visibleHeight),
            top: Math.round(rect.top),
            left: Math.round(rect.left),
            area: Math.round(coverage.visibleArea),
            exposedPoints: coverage.exposedPoints,
            totalPoints: coverage.totalPoints,
            background: style.backgroundColor,
            luminance: rgb ? luminance(rgb) : null,
          };
        })
        .filter((item) => item.luminance !== null && item.luminance > 0.72)
        .sort((left, right) => right.area - left.area)
        .slice(0, 8);

      return {
        readyFound: Boolean(routeReady),
        ownerFound: Boolean(themeOwner),
        ownerThemeValue: themeOwner?.getAttribute("data-moss-theme") ?? null,
        ownerClassName: themeOwner?.className ?? null,
        ownerBackground,
        routeRootAudit,
        largeLightSurfaces: candidates,
      };
    }, { readySelector: route.readySelector });

    expect(audit.readyFound).toBe(true);
    expect(audit.ownerFound, JSON.stringify(audit, null, 2)).toBe(true);
    expect(audit.ownerThemeValue).toBe("dark");
    expect(audit.ownerClassName ?? "").toContain("theme-dh-api");
    expect(audit.ownerBackground, JSON.stringify(audit, null, 2)).not.toBeNull();
    expect(audit.ownerBackground?.luminance ?? 1, JSON.stringify(audit, null, 2)).toBeLessThan(0.35);
    expect(audit.routeRootAudit, JSON.stringify(audit, null, 2)).not.toBeNull();
    expect(audit.routeRootAudit?.ownerMatches, JSON.stringify(audit, null, 2)).toBe(true);
    expect(audit.routeRootAudit?.effectiveLuminance ?? 1, JSON.stringify(audit, null, 2)).toBeLessThan(0.35);
    expect(audit.routeRootAudit?.colorScheme, JSON.stringify(audit, null, 2)).toBe("dark");
    expect(audit.routeRootAudit?.tokenCanvasDark, JSON.stringify(audit, null, 2)).toBe(true);
    expect(audit.largeLightSurfaces, JSON.stringify(audit, null, 2)).toEqual([]);
  });
}
