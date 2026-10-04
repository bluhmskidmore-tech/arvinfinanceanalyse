import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

import { MarketWorkbenchFrame } from "../features/workbench/market-shell";

const STOCK_ANALYSIS_PAGE_SOURCE = readFileSync(
  resolve(process.cwd(), "src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx"),
  "utf8",
);
const STOCK_ANALYSIS_ACTIONS_SOURCE = readFileSync(
  resolve(
    process.cwd(),
    "src/features/stock-analysis/components/StockAnalysisWorkbenchActions.tsx",
  ),
  "utf8",
);
const STOCK_ANALYSIS_EVIDENCE_SOURCE = readFileSync(
  resolve(
    process.cwd(),
    "src/features/stock-analysis/components/StockAnalysisEvidenceDisclosure.tsx",
  ),
  "utf8",
);
const STOCK_ANALYSIS_PAGE_CSS_SOURCE = readFileSync(
  resolve(process.cwd(), "src/features/stock-analysis/pages/StockAnalysisPage.css"),
  "utf8",
);
const STOCK_ANALYSIS_EDITORIAL_CSS_SOURCE = readFileSync(
  resolve(process.cwd(), "src/features/stock-analysis/pages/StockAnalysisEditorialLedger.css"),
  "utf8",
);
const STOCK_ANALYSIS_STAGE_NAV_CSS_SOURCE = readFileSync(
  resolve(
    process.cwd(),
    "src/features/stock-analysis/components/StockAnalysisStageNav.module.css",
  ),
  "utf8",
);

function countMatches(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

function indexOfOrThrow(source: string, value: string): number {
  const index = source.indexOf(value);
  expect(index, `expected to find ${value}`).toBeGreaterThanOrEqual(0);
  return index;
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

describe("StockAnalysis page chrome contract", () => {
  it("keeps the body-only frame and v2 compact chrome owners in the real page implementation", () => {
    expect(countMatches(STOCK_ANALYSIS_PAGE_SOURCE, /<MarketWorkbenchFrame\b/g)).toBe(1);
    expect(STOCK_ANALYSIS_PAGE_SOURCE).toContain('chrome="body-only"');
    expect(countMatches(STOCK_ANALYSIS_PAGE_SOURCE, /<PageV2Shell\b/g)).toBe(1);
    expect(countMatches(STOCK_ANALYSIS_PAGE_SOURCE, /<PageDecisionHero\b/g)).toBe(1);
    expect(countMatches(STOCK_ANALYSIS_PAGE_SOURCE, /<DataStatusStrip\b/g)).toBe(1);
    expect(STOCK_ANALYSIS_PAGE_SOURCE).toContain('testId="stock-analysis-page-v2-shell"');
    expect(STOCK_ANALYSIS_PAGE_SOURCE).toContain('testId="stock-analysis-page-compact-chrome"');
    expect(STOCK_ANALYSIS_PAGE_SOURCE).toContain('testId="stock-analysis-page-status-strip"');
    expect(STOCK_ANALYSIS_PAGE_SOURCE).toContain('data-testid="stock-analysis-page-toolbar-owner"');
  });

  it("renders no legacy topbar, navigation, or audit footer in body-only mode", () => {
    render(
      createElement(
        MarketWorkbenchFrame,
        {
          pageKey: "stock-analysis",
          chrome: "body-only",
          title: "股票分析",
          question: "测试问题",
          status: { label: "就绪", tone: "ok" },
          metaItems: [],
          children: createElement("div", { "data-testid": "body-only-content" }, "正文"),
        },
      ),
    );

    expect(screen.getByTestId("market-workbench-frame")).toHaveAttribute("data-chrome", "body-only");
    expect(screen.getByTestId("body-only-content")).toBeVisible();
    expect(screen.queryByTestId("market-workbench-topbar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-workbench-nav")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-workbench-audit-footer")).not.toBeInTheDocument();
  });

  it("keeps exactly one evidence disclosure entry point in the page", () => {
    expect(countMatches(STOCK_ANALYSIS_PAGE_SOURCE, /<StockAnalysisEvidenceDisclosure\b/g)).toBe(1);
    expect(
      countMatches(
        STOCK_ANALYSIS_EVIDENCE_SOURCE,
        /data-testid="stock-analysis-evidence-disclosure-summary"/g,
      ),
    ).toBe(1);
  });

  it("keeps the stock-analysis toolbar controls in the intended review order", () => {
    const datePicker = indexOfOrThrow(
      STOCK_ANALYSIS_ACTIONS_SOURCE,
      'data-testid="stock-analysis-as-of-picker"',
    );
    const queueSearch = indexOfOrThrow(
      STOCK_ANALYSIS_ACTIONS_SOURCE,
      'data-testid="stock-analysis-queue-search"',
    );
    const agentButton = indexOfOrThrow(
      STOCK_ANALYSIS_ACTIONS_SOURCE,
      'data-testid="stock-analysis-agent-open"',
    );
    const refreshButton = indexOfOrThrow(
      STOCK_ANALYSIS_ACTIONS_SOURCE,
      'data-testid="stock-analysis-refresh"',
    );

    expect(datePicker).toBeLessThan(queueSearch);
    expect(queueSearch).toBeLessThan(agentButton);
    expect(agentButton).toBeLessThan(refreshButton);
  });

  it("keeps the compact-toolbar controls unique and removes legacy topbar controls", () => {
    expect(
      countMatches(STOCK_ANALYSIS_ACTIONS_SOURCE, /data-testid="stock-analysis-as-of-picker"/g),
    ).toBe(1);
    expect(
      countMatches(STOCK_ANALYSIS_ACTIONS_SOURCE, /data-testid="stock-analysis-queue-search"/g),
    ).toBe(1);
    expect(
      countMatches(STOCK_ANALYSIS_ACTIONS_SOURCE, /data-testid="stock-analysis-agent-open"/g),
    ).toBe(1);
    expect(
      countMatches(STOCK_ANALYSIS_ACTIONS_SOURCE, /data-testid="stock-analysis-refresh"/g),
    ).toBe(1);
    expect(STOCK_ANALYSIS_ACTIONS_SOURCE).not.toContain('data-testid="stock-analysis-toolbar-data-status"');
    expect(STOCK_ANALYSIS_ACTIONS_SOURCE).not.toContain('data-testid="stock-analysis-toolbar-gate-status"');
    expect(STOCK_ANALYSIS_ACTIONS_SOURCE).not.toContain('data-testid="stock-analysis-toolbar-loop-status"');
    expect(STOCK_ANALYSIS_ACTIONS_SOURCE).not.toContain('data-testid="stock-analysis-toolbar-route"');
    expect(STOCK_ANALYSIS_ACTIONS_SOURCE).not.toContain('data-testid="stock-analysis-complete-evidence-toggle"');
  });

  it("keeps the compact chrome and decision-layout owners in the editorial ledger stylesheet only", () => {
    const editorialOwnedSelectors = [
      ".stock-analysis-page__compact-control-row",
      ".stock-analysis-page__decision-first-screen",
      ".stock-analysis-page__evidence-disclosure",
      ".stock-analysis-page__evidence-disclosure-summary",
      ".stock-analysis-page__evidence-disclosure-body",
    ];

    editorialOwnedSelectors.forEach((selector) => {
      expect(
        countMatches(
          STOCK_ANALYSIS_PAGE_CSS_SOURCE,
          new RegExp(`${escapeRegex(selector)}\\s*\\{`, "g"),
        ),
        `${selector} should no longer be duplicated in StockAnalysisPage.css`,
      ).toBe(0);
      expect(
        countMatches(
          STOCK_ANALYSIS_EDITORIAL_CSS_SOURCE,
          new RegExp(`${escapeRegex(selector)}\\s*\\{`, "g"),
        ),
        `${selector} should remain owned by StockAnalysisEditorialLedger.css`,
      ).toBeGreaterThan(0);
    });
  });

  it("keeps the shared stage navigation aligned by page shells instead of local outer margins", () => {
    const rootRule =
      STOCK_ANALYSIS_STAGE_NAV_CSS_SOURCE.match(/\.stageNav\s*\{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(rootRule).toContain("border-radius: var(--dh-api-radius);");
    expect(rootRule).not.toContain("margin:");
  });
});
