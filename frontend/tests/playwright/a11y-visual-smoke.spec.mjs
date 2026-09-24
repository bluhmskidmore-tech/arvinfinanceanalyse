import { AxeBuilder } from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

async function probeServer(baseURL) {
  if (!baseURL) {
    return { ok: false, reason: "Playwright baseURL is not configured." };
  }

  try {
    const response = await fetch(baseURL, { method: "GET" });
    if (response.ok) {
      return { ok: true, reason: "" };
    }
    return { ok: false, reason: `Smoke server probe failed with ${response.status}.` };
  } catch (error) {
    return {
      ok: false,
      reason: `Smoke server probe failed: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

const smokePages = [
  {
    slug: "dashboard",
    path: "/",
    readySelector: '[data-testid="dashboard-home-page"]',
  },
  {
    slug: "bond-dashboard",
    path: "/bond-dashboard",
    readySelector: '[data-testid="bond-dashboard-page"]',
  },
  {
    slug: "balance-analysis",
    path: "/balance-analysis",
    readySelector: '[data-testid="balance-analysis-page"]',
    excludeSelectors: [".ag-theme-alpine", ".ag-root"],
  },
  {
    slug: "balance-movement-analysis",
    path: "/balance-movement-analysis",
    readySelector: '[data-testid="balance-movement-analysis-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "cross-asset",
    path: "/cross-asset",
    readySelector: '[data-testid="cross-asset-drivers-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "product-category-pnl",
    path: "/product-category-pnl",
    readySelector: '[data-testid="product-category-page"]',
    blockedAxeImpacts: ["critical", "serious"],
    minimumControlTargetSize: 24,
  },
  {
    slug: "pnl",
    path: "/pnl",
    readySelector: '[data-testid="formal-pnl-v1-page"]',
    excludeSelectors: [".ag-theme-alpine", ".ag-root"],
  },
  {
    slug: "pnl-bridge",
    path: "/pnl-bridge",
    readySelector: '[data-testid="pnl-bridge-page"]',
    excludeSelectors: [".ag-theme-alpine", ".ag-root"],
  },
  {
    slug: "risk-tensor",
    path: "/risk-tensor",
    readySelector: '[data-testid="risk-tensor-brief"]',
  },
  {
    slug: "ledger-pnl",
    path: "/ledger-pnl",
    readySelector: '[data-testid="ledger-pnl-page"]',
    axeSelector: '[data-testid="ledger-pnl-page-title"], [data-testid="ledger-pnl-monthly-analysis-overview"]',
    screenshotFullPage: false,
  },
  {
    slug: "positions",
    path: "/positions",
    readySelector: '[data-testid="positions-page"]',
    excludeSelectors: [".ant-table"],
    screenshotFullPage: false,
  },
  {
    slug: "operations-analysis",
    path: "/operations-analysis",
    readySelector: '[data-testid="operations-layout-preview"]',
    axeSelector: '[data-testid="operations-layout-preview"]',
    screenshotFullPage: false,
  },
  {
    slug: "liability-analytics",
    path: "/liability-analytics",
    readySelector: '[data-testid="liability-analytics-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "market-data",
    path: "/market-data",
    readySelector: '[data-testid="market-data-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "market-finance",
    path: "/market-finance",
    readySelector: '[data-testid="market-finance-workbench"]',
    blockedAxeImpacts: ["critical", "serious"],
    minimumControlTargetSize: 24,
    screenshotFullPage: false,
  },
  {
    slug: "macro-toolkit",
    path: "/macro-toolkit",
    readySelector: '[data-testid="macro-toolkit-tailwind-cockpit"]',
    screenshotFullPage: false,
  },
  {
    slug: "cashflow-projection",
    path: "/cashflow-projection",
    readySelector: '[data-testid="cashflow-projection-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "concentration-monitor",
    path: "/concentration-monitor",
    readySelector: '[data-testid="concentration-monitor-kpi-grid"]',
    screenshotFullPage: false,
  },
  {
    slug: "stock-analysis",
    path: "/stock-analysis",
    readySelector: '[data-testid="stock-analysis-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "average-balance",
    path: "/average-balance",
    readySelector: '[data-testid="average-balance-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "bond-analysis",
    path: "/bond-analysis",
    readySelector: '[data-testid="bond-analysis-overview"]',
    screenshotFullPage: false,
  },
  {
    slug: "pnl-attribution",
    path: "/pnl-attribution",
    readySelector: '[data-testid="pnl-attribution-page-title"]',
    screenshotFullPage: false,
  },
  {
    slug: "team-performance",
    path: "/team-performance",
    readySelector: '[data-testid="team-performance-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "decision-items",
    path: "/decision-items",
    readySelector: '[data-testid="decision-items-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "kpi-performance",
    path: "/kpi",
    readySelector: '[data-testid="kpi-performance-page"]',
    screenshotFullPage: false,
  },
  {
    slug: "news-events",
    path: "/news-events",
    readySelector: '[data-testid="news-events-page-title"]',
    screenshotFullPage: false,
  },
  {
    slug: "platform-config",
    path: "/platform-config",
    readySelector: '[data-testid="platform-config-page-title"]',
    screenshotFullPage: false,
  },
];

const flagshipKeyboardPages = [
  {
    slug: "cross-asset",
    path: "/cross-asset",
    readySelector: '[data-testid="cross-asset-drivers-page"]',
    businessFocusSelector: '[data-testid="cross-asset-evidence-details"] summary',
  },
  {
    slug: "ledger-pnl",
    path: "/ledger-pnl",
    readySelector: '[data-testid="ledger-pnl-page"]',
    businessFocusSelector:
      '[data-testid="ledger-pnl-report-date-control"], [data-testid="ledger-pnl-currency-control"], [aria-label="总账损益报告日"], [aria-label="总账损益币种"]',
  },
  {
    slug: "macro-toolkit",
    path: "/macro-toolkit",
    readySelector: '[data-testid="macro-toolkit-tailwind-cockpit"]',
    // 913db8d0/63ccb747 信息架构重构后 cockpit 是只读结论卡；
    // 业务控件（刷新动作、治理与证据入口）现位于路由工具栏与治理证据栏。
    businessFocusSelector:
      '[data-testid="macro-toolkit-toolbar"] button, [data-testid="macro-toolkit-meta-rail"] button, [data-testid="macro-toolkit-meta-rail"] a',
  },
  {
    slug: "stock-analysis",
    path: "/stock-analysis",
    readySelector: '[data-testid="stock-analysis-page"]',
    businessFocusSelector:
      '[data-testid="stock-analysis-agent-open"], [data-testid="stock-analysis-refresh"], [data-testid="stock-analysis-supply-details-toggle"]',
  },
  {
    slug: "product-category-pnl",
    path: "/product-category-pnl",
    readySelector: '[data-testid="product-category-page"]',
    businessFocusSelector:
      '[data-testid="product-category-branch-product-category-pnl"], [data-testid="product-category-manual-button"], [data-testid="product-category-refresh-button"]',
  },
  {
    slug: "pnl-attribution",
    path: "/pnl-attribution",
    readySelector: '[data-testid="pnl-attribution-page-title"]',
    businessFocusSelector: '[data-testid="pnl-attribution-tab-product-category"]',
  },
  {
    slug: "bond-analysis",
    path: "/bond-analysis",
    readySelector: '[data-testid="bond-analysis-overview"]',
    businessFocusSelector:
      '[data-testid="bond-analysis-overview"] select, [data-testid="bond-analysis-overview"] button, [data-testid="bond-analysis-detail-drilldown"] summary',
  },
];

const gateHControlContextPages = [
  {
    slug: "cross-asset",
    path: "/cross-asset",
    readySelector: '[data-testid="cross-asset-drivers-page"]',
    controls: [
      {
        label: "evidence details disclosure",
        selector: '[data-testid="cross-asset-evidence-details"] summary',
      },
    ],
    stateCueSelector:
      '[data-testid="cross-asset-trust-panel"], [data-testid="cross-asset-action-rail"], [data-testid="cross-asset-data-status-strip"]',
  },
  {
    slug: "ledger-pnl",
    path: "/ledger-pnl",
    readySelector: '[data-testid="ledger-pnl-page"]',
    controls: [
      {
        label: "report date selector",
        selector: '[data-testid="ledger-pnl-report-date-control"], [aria-label="总账损益报告日"]',
      },
      {
        label: "currency selector",
        selector: '[data-testid="ledger-pnl-currency-control"], [aria-label="总账损益币种"]',
      },
    ],
    stateCueSelector:
      '[data-testid="ledger-pnl-functional-audit-strip"], [data-testid="ledger-pnl-monthly-analysis-panel"]',
  },
  {
    slug: "macro-toolkit",
    path: "/macro-toolkit",
    readySelector: '[data-testid="macro-toolkit-tailwind-cockpit"]',
    controls: [
      {
        label: "toolbar refresh action",
        selector: '[data-testid="macro-toolkit-toolbar"] button',
      },
      {
        label: "governance evidence rail entry",
        selector:
          '[data-testid="macro-toolkit-meta-rail"] button, [data-testid="macro-toolkit-meta-rail"] a',
      },
    ],
    stateCueSelector: '[data-testid="macro-toolkit-meta-rail"]',
  },
  {
    slug: "stock-analysis",
    path: "/stock-analysis",
    readySelector: '[data-testid="stock-analysis-page"]',
    controls: [
      {
        label: "queue search",
        selector: '[data-testid="stock-analysis-queue-search"]',
      },
      {
        label: "refresh action",
        selector: '[data-testid="stock-analysis-refresh"]',
      },
    ],
    stateCueSelector: '[data-testid="stock-analysis-page"]',
  },
  {
    slug: "product-category-pnl",
    path: "/product-category-pnl",
    readySelector: '[data-testid="product-category-page"]',
    controls: [
      {
        label: "branch switch",
        selector: '[data-testid="product-category-branch-product-category-pnl"]',
      },
      {
        label: "manual control",
        selector: '[data-testid="product-category-manual-button"]',
      },
      {
        label: "refresh control",
        selector: '[data-testid="product-category-refresh-button"]',
      },
    ],
    stateCueSelector:
      '[data-testid="product-category-decision-focus"], [data-testid="product-category-page"]',
  },
  {
    slug: "pnl-attribution",
    path: "/pnl-attribution",
    readySelector: '[data-testid="pnl-attribution-page-title"]',
    controls: [
      {
        label: "product category tab",
        selector: '[data-testid="pnl-attribution-tab-product-category"]',
      },
    ],
    stateCueSelector:
      '[data-testid="pnl-attribution-product-category-lens-card"], [data-testid="pnl-attribution-formal-lens-card"]',
  },
  {
    slug: "bond-analysis",
    path: "/bond-analysis",
    readySelector: '[data-testid="bond-analysis-overview"]',
    controls: [
      {
        label: "report date selector",
        selector: '[data-testid="bond-analysis-overview"] [role="combobox"][aria-label="报告日"]',
      },
      {
        label: "decision next action",
        selector: '[data-testid="bond-analysis-decision-next-action"]',
      },
      {
        label: "detail disclosure",
        selector: '[data-testid="bond-analysis-detail-drilldown"] summary',
      },
    ],
    focusTarget: {
      label: "decision next action",
      selector: '[data-testid="bond-analysis-decision-next-action"]',
    },
    stateCueSelector: '[data-testid="bond-analysis-daily-judgment"]',
  },
];

const stateCueTextPattern =
  /就绪|匹配|已返回|可用|待|暂无|缺失|降级|陈旧|受限|阻断|失败|错误|告警|风险|预警|兜底|可信|证据|复核|条件|ready|warning|stale|fallback|blocked|no data/i;
const internalSlugNamePattern = /^[a-z0-9]+(?:[-_][a-z0-9]+)+$/i;

async function gotoVisiblePage(page, smokePage) {
  await page.goto(smokePage.path, { waitUntil: "domcontentloaded" });
  const pageRoot = page.locator(smokePage.readySelector);
  await expect(pageRoot).toBeVisible({ timeout: smokePage.readyTimeout ?? 60_000 });
  await page.waitForLoadState("load", { timeout: 15_000 }).catch(() => undefined);
  return pageRoot;
}

async function describeActiveElement(page, targetSelector) {
  return page.evaluate((selector) => {
    const activeElement = document.activeElement;
    const targetElements = [...document.querySelectorAll(selector)];
    const matchedTarget = targetElements.find(
      (target) => target === activeElement || target.contains(activeElement),
    );

    if (!(activeElement instanceof HTMLElement)) {
      return {
        tagName: activeElement?.tagName?.toLowerCase() ?? null,
        testId: null,
        ariaLabel: null,
        text: "",
        targetMatched: false,
      };
    }

    return {
      tagName: activeElement.tagName.toLowerCase(),
      testId: activeElement.getAttribute("data-testid"),
      ariaLabel: activeElement.getAttribute("aria-label"),
      text: (activeElement.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 120),
      targetMatched: Boolean(matchedTarget),
      targetTestId: matchedTarget?.getAttribute("data-testid") ?? null,
      targetTagName: matchedTarget?.tagName.toLowerCase() ?? null,
    };
  }, targetSelector);
}

async function firstVisibleLocator(page, selector, timeout = 60_000) {
  const locator = page.locator(selector);
  const deadline = Date.now() + timeout;

  while (Date.now() <= deadline) {
    const count = await locator.count();
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index);
      if (await candidate.isVisible().catch(() => false)) {
        return candidate;
      }
    }
    await page.waitForTimeout(100);
  }

  await expect(locator.first()).toBeVisible({ timeout: 1 });
  return locator.first();
}

async function readAccessibleControlContext(locator) {
  return locator.evaluate((element) => {
    const text = (element.textContent ?? "").replace(/\s+/g, " ").trim();
    const labelledBy = element
      .getAttribute("aria-labelledby")
      ?.split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent?.replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join(" ");
    const formLabels =
      "labels" in element
        ? Array.from(element.labels ?? [])
            .map((label) => label.textContent?.replace(/\s+/g, " ").trim())
            .filter(Boolean)
            .join(" ")
        : "";
    const accessibleName =
      element.getAttribute("aria-label") ||
      labelledBy ||
      formLabels ||
      element.getAttribute("title") ||
      element.getAttribute("placeholder") ||
      element.getAttribute("value") ||
      text;

    return {
      tagName: element.tagName.toLowerCase(),
      testId: element.getAttribute("data-testid"),
      accessibleName: (accessibleName ?? "").replace(/\s+/g, " ").trim(),
      text,
    };
  });
}

async function focusMainWithSkipLink(page) {
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  const mainContent = page.locator("#workbench-main-content");

  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });
  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(mainContent).toBeFocused();
}

async function focusTargetFromMain(page, targetSelector, maxSteps = 100) {
  await focusMainWithSkipLink(page);

  const focusSequence = [];
  for (let step = 1; step <= maxSteps; step += 1) {
    await page.keyboard.press("Tab");
    const active = await describeActiveElement(page, targetSelector);
    const focusPresentation = await page.evaluate(() => {
      const activeElement = document.activeElement;
      if (!(activeElement instanceof HTMLElement)) {
        return {
          hasVisibleFocus: false,
          outlineStyle: null,
          outlineWidth: null,
          boxShadow: null,
        };
      }

      const style = window.getComputedStyle(activeElement);
      const outlineWidth = Number.parseFloat(style.outlineWidth || "0");
      const hasOutline = style.outlineStyle !== "none" && outlineWidth > 0;
      const hasShadow = Boolean(style.boxShadow && style.boxShadow !== "none");
      return {
        hasVisibleFocus: hasOutline || hasShadow,
        outlineStyle: style.outlineStyle,
        outlineWidth: style.outlineWidth,
        boxShadow: style.boxShadow,
      };
    });
    focusSequence.push({ step, ...active, ...focusPresentation });

    if (active.targetMatched) {
      return { matchedStep: step, active, focusPresentation, focusSequence };
    }
  }

  return { matchedStep: null, active: null, focusPresentation: null, focusSequence };
}

test.describe("frontend accessibility + visual smoke", () => {
  for (const smokePage of smokePages) {
    const blockedAxeImpacts = smokePage.blockedAxeImpacts ?? ["critical"];
    test(`${smokePage.slug} has no ${blockedAxeImpacts.join(" or ")} axe violations @${smokePage.slug}`, async ({ page }, testInfo) => {
      const serverCheck = await probeServer(testInfo.project.use.baseURL);
      expect(serverCheck.ok, serverCheck.reason).toBe(true);

      await gotoVisiblePage(page, smokePage);

      let axeBuilder = new AxeBuilder({ page }).include(smokePage.axeSelector ?? smokePage.readySelector);
      for (const selector of smokePage.excludeSelectors ?? []) {
        axeBuilder = axeBuilder.exclude(selector);
      }
      const { violations } = await axeBuilder.analyze();
      const blockedViolations = violations.filter((violation) =>
        blockedAxeImpacts.includes(violation.impact),
      );
      const undersizedControls = smokePage.minimumControlTargetSize
        ? await page.locator(
            `${smokePage.readySelector} button, ${smokePage.readySelector} a[href], ${smokePage.readySelector} select, ${smokePage.readySelector} input, ${smokePage.readySelector} textarea, ${smokePage.readySelector} summary`,
          ).evaluateAll((controls, minimumSize) =>
            controls.flatMap((control) => {
              const box = control.getBoundingClientRect();
              const style = window.getComputedStyle(control);
              const visible =
                box.width > 0 &&
                box.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden";
              if (!visible || (box.width >= minimumSize && box.height >= minimumSize)) {
                return [];
              }
              return [
                {
                  name: (
                    control.getAttribute("aria-label") ||
                    control.textContent ||
                    control.getAttribute("title") ||
                    ""
                  )
                    .replace(/\s+/g, " ")
                    .trim()
                    .slice(0, 120),
                  width: Math.round(box.width),
                  height: Math.round(box.height),
                },
              ];
            }),
          smokePage.minimumControlTargetSize)
        : [];

      await page.screenshot({
        path: testInfo.outputPath(`${smokePage.slug}.png`),
        fullPage: smokePage.screenshotFullPage ?? true,
      });

      expect.soft(
        blockedViolations,
        blockedViolations
          .map((violation) => `${violation.id}: ${violation.help}`)
          .join("\n"),
      ).toEqual([]);
      expect(
        undersizedControls,
        `Controls smaller than ${smokePage.minimumControlTargetSize}px: ${JSON.stringify(undersizedControls)}`,
      ).toEqual([]);
    });
  }

  for (const keyboardPage of flagshipKeyboardPages) {
    test(`${keyboardPage.slug} exposes a keyboard skip path to the decision surface @gate-h-keyboard`, async ({
      page,
    }, testInfo) => {
      const serverCheck = await probeServer(testInfo.project.use.baseURL);
      expect(serverCheck.ok, serverCheck.reason).toBe(true);

      await gotoVisiblePage(page, keyboardPage);

      const skipLink = page.getByRole("link", { name: "Skip to main content" });
      const mainContent = page.locator("#workbench-main-content");

      await expect(mainContent).toHaveAttribute("aria-label", "Main content");
      await expect(mainContent).toHaveAttribute("tabindex", "-1");

      await page.evaluate(() => {
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
      });
      await page.keyboard.press("Tab");
      await expect(skipLink).toBeFocused();

      await page.keyboard.press("Enter");
      await expect(mainContent).toBeFocused();

      await testInfo.attach(`${keyboardPage.slug}-keyboard-entry.json`, {
        body: JSON.stringify(
          {
            path: keyboardPage.path,
            firstTabTarget: "Skip to main content",
            focusedMainId: await mainContent.evaluate((element) => element.id),
            readySelector: keyboardPage.readySelector,
          },
          null,
          2,
        ),
        contentType: "application/json",
      });
    });
  }

  for (const keyboardPage of flagshipKeyboardPages) {
    test(`${keyboardPage.slug} moves keyboard focus from main into route business controls @gate-h-route-focus`, async ({
      page,
    }, testInfo) => {
      const serverCheck = await probeServer(testInfo.project.use.baseURL);
      expect(serverCheck.ok, serverCheck.reason).toBe(true);

      await gotoVisiblePage(page, keyboardPage);

      const skipLink = page.getByRole("link", { name: "Skip to main content" });
      const mainContent = page.locator("#workbench-main-content");
      const businessTargets = page.locator(keyboardPage.businessFocusSelector);

      await expect(businessTargets.first()).toBeVisible({ timeout: 60_000 });

      await page.evaluate(() => {
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
      });
      await page.keyboard.press("Tab");
      await expect(skipLink).toBeFocused();

      await page.keyboard.press("Enter");
      await expect(mainContent).toBeFocused();

      const focusSequence = [];
      let matchedStep = null;
      for (let step = 1; step <= 80; step += 1) {
        await page.keyboard.press("Tab");
        const active = await describeActiveElement(page, keyboardPage.businessFocusSelector);
        focusSequence.push({ step, ...active });

        if (active.targetMatched) {
          matchedStep = step;
          break;
        }
      }

      await testInfo.attach(`${keyboardPage.slug}-route-focus-sequence.json`, {
        body: JSON.stringify(
          {
            path: keyboardPage.path,
            readySelector: keyboardPage.readySelector,
            businessFocusSelector: keyboardPage.businessFocusSelector,
            matchedStep,
            focusSequence,
          },
          null,
          2,
        ),
        contentType: "application/json",
      });

      expect(
        matchedStep,
        [
          `Expected keyboard focus to reach a route-owned business control for ${keyboardPage.path}.`,
          `Selector: ${keyboardPage.businessFocusSelector}`,
          `Sequence: ${JSON.stringify(focusSequence, null, 2)}`,
        ].join("\n"),
      ).not.toBeNull();
    });
  }

  for (const controlPage of gateHControlContextPages) {
    test(`${controlPage.slug} exposes named controls, visible focus, and non-color state cues @gate-h-control-context`, async ({
      page,
    }, testInfo) => {
      const serverCheck = await probeServer(testInfo.project.use.baseURL);
      expect(serverCheck.ok, serverCheck.reason).toBe(true);

      await gotoVisiblePage(page, controlPage);

      const controlContexts = [];
      for (const control of controlPage.controls) {
        const controlLocator = await firstVisibleLocator(page, control.selector);
        const context = await readAccessibleControlContext(controlLocator);
        controlContexts.push({ ...control, ...context });

        expect(context.accessibleName, `${controlPage.slug} ${control.label} needs a screen-reader name`).not.toBe("");
        expect(
          context.accessibleName,
          `${controlPage.slug} ${control.label} should expose a human-readable name, not an internal slug`,
        ).not.toMatch(internalSlugNamePattern);
      }

      const focusTarget = controlPage.focusTarget ?? controlPage.controls[0];
      const focusEvidence = await focusTargetFromMain(page, focusTarget.selector);
      expect(
        focusEvidence.matchedStep,
        `${controlPage.slug} keyboard focus did not reach ${focusTarget.label}`,
      ).not.toBeNull();
      expect(
        focusEvidence.focusPresentation?.hasVisibleFocus,
        `${controlPage.slug} ${focusTarget.label} needs a visible focus indicator`,
      ).toBe(true);

      const stateCue = await firstVisibleLocator(page, controlPage.stateCueSelector);
      const stateCueText = await stateCue.evaluate((element) =>
        (element.textContent ?? "").replace(/\s+/g, " ").trim(),
      );
      expect(stateCueText, `${controlPage.slug} needs visible non-color state text`).toMatch(stateCueTextPattern);

      await testInfo.attach(`${controlPage.slug}-gate-h-control-context.json`, {
        body: JSON.stringify(
          {
            path: controlPage.path,
            controlContexts,
            focusEvidence,
            stateCueText: stateCueText.slice(0, 500),
          },
          null,
          2,
        ),
        contentType: "application/json",
      });
    });
  }
});
