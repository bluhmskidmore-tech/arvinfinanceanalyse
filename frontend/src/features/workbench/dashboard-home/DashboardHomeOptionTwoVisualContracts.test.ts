import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const featureRoot = resolve(
  process.cwd(),
  "src/features/workbench/dashboard-home",
);
const optionTwoCss = readFileSync(
  resolve(featureRoot, "dashboardHomeOptionTwo.module.css"),
  "utf8",
);
const pageSource = readFileSync(
  resolve(featureRoot, "DashboardHomePage.tsx"),
  "utf8",
);
const holdingDrawerSource = readFileSync(
  resolve(featureRoot, "DashboardHomeHoldingDrawer.tsx"),
  "utf8",
);
const bondNewsSource = readFileSync(
  resolve(featureRoot, "sections/BondNewsSection.tsx"),
  "utf8",
);
const researchCalendarSource = readFileSync(
  resolve(featureRoot, "sections/ResearchCalendarSection.tsx"),
  "utf8",
);
const deferredEvidenceCssPath = resolve(
  featureRoot,
  "dashboardHomeOptionTwoDeferred.module.css",
);
const deferredEvidenceCss = readFileSync(deferredEvidenceCssPath, "utf8");
const holdingDrawerCssPath = resolve(
  featureRoot,
  "dashboardHomeHoldingDrawer.module.css",
);

describe("dashboard home option two visual contracts", () => {
  it("keeps the shell as the only main landmark", () => {
    expect(pageSource).not.toContain("<main");
    expect(pageSource).toContain('aria-label="组合经营日报内容"');
  });

  it("keeps the holding drawer in a component-owned, viewport-bounded dark layer", () => {
    expect(holdingDrawerSource).toContain(
      'import styles from "./dashboardHomeHoldingDrawer.module.css";',
    );
    expect(holdingDrawerSource).not.toContain(
      'from "./dashboardHomeWorkMatrix.module.css"',
    );
    expect(existsSync(holdingDrawerCssPath)).toBe(true);
    if (!existsSync(holdingDrawerCssPath)) {
      return;
    }

    const drawerCss = readFileSync(holdingDrawerCssPath, "utf8");
    for (const selector of [
      ".drawerLayer",
      ".drawerScrim",
      ".holdingDrawer",
      ".drawerHeader",
      ".drawerMetrics",
      ".drawerAuditList",
      ".drawerLinks",
    ]) {
      expect(drawerCss).toContain(selector);
    }
    expect(drawerCss).toMatch(
      /\.drawerLayer\s*\{[^}]*position:\s*fixed;[^}]*inset:\s*0;/s,
    );
    expect(drawerCss).toMatch(
      /\.holdingDrawer\s*\{[^}]*max-height:\s*100dvh;[^}]*overflow-y:\s*auto;/s,
    );
    expect(drawerCss).toContain("var(--dh-api-panel)");
  });

  it("keeps live deferred evidence styles out of the legacy homepage stylesheet", () => {
    const expectedImport =
      'import styles from "../dashboardHomeOptionTwoDeferred.module.css";';

    for (const source of [bondNewsSource, researchCalendarSource]) {
      expect(source).toContain(expectedImport);
      expect(source).not.toContain("dashboardHome.module.css");
      expect(source).not.toContain("institutionalDashboardSurface.module.css");
      expect(source).not.toContain(
        "institutionalDashboardSurface.foundation.module.css",
      );
    }

    expect(existsSync(deferredEvidenceCssPath)).toBe(true);
    if (!existsSync(deferredEvidenceCssPath)) {
      return;
    }

    expect(optionTwoCss).not.toMatch(/\.extendedEvidence\s*:\s*global/);
    expect(deferredEvidenceCss).not.toContain(".extendedEvidence");
    const styleAccesses = new Set(
      [bondNewsSource, researchCalendarSource].flatMap((source) =>
        [...source.matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(
          (match) => match[1],
        ),
      ),
    );

    // 72 = 原 71 + 卡头 stale 琥珀点（dhBondNewsStaleDot，§6 状态去重收敛）。
    expect(styleAccesses.size).toBe(72);
    for (const className of styleAccesses) {
      expect(deferredEvidenceCss).toContain(`.${className}`);
    }
  });

  it("keeps the opening decision band action-first without decorative card noise", () => {
    expect(optionTwoCss).toMatch(
      /\.overviewSectionHeader\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\) auto;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.overviewSectionHeader\s*>\s*span\s*\{[^}]*display:\s*none;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.decisionStrip\s*\{[^}]*minmax\(160px, 0\.72fr\)[^}]*minmax\(0, 1\.8fr\)[^}]*minmax\(220px, 0\.88fr\);/s,
    );
    expect(optionTwoCss).toMatch(
      /\.overviewAttention\s*\{[^}]*border-left:\s*2px solid var\(--option-two-blue\);[^}]*background:\s*var\(--option-two-panel-2\);/s,
    );
    expect(optionTwoCss).toMatch(
      /\.portfolioSummaryBody\s*\{[^}]*grid-template-columns:\s*200px minmax\(0, 1fr\);/s,
    );
    expect(optionTwoCss).toMatch(
      /\.overviewNarrative\s*\{[^}]*border-radius:\s*0;[^}]*background:\s*transparent;/s,
    );
  });

  it("fits KPI values and removes stretched empty cards at the 1280px breakpoint", () => {
    const compactStart = optionTwoCss.indexOf("@media (max-width: 1280px)");
    const compactEnd = optionTwoCss.indexOf(
      "@media (max-width: 1024px)",
      compactStart,
    );
    const compactCss = optionTwoCss.slice(compactStart, compactEnd);

    expect(compactStart).toBeGreaterThanOrEqual(0);
    expect(compactEnd).toBeGreaterThan(compactStart);
    expect(compactCss).toMatch(
      /\.kpiItem\s*>\s*strong\s*\{[^}]*font-size:\s*clamp\(/s,
    );
    expect(compactCss).toMatch(
      /\.riskTasks,\s*\.analyticsPanel,\s*\.marketResearchPanel\s*\{[^}]*min-height:\s*(?:0|auto);/s,
    );
    expect(compactCss).not.toContain("min-height: 330px;");
  });

  it("intentionally removes secondary toolbar controls before narrow layouts can clip", () => {
    const tabletStart = optionTwoCss.indexOf("@media (max-width: 1024px)");
    const tabletEnd = optionTwoCss.indexOf(
      "@media (max-width: 720px)",
      tabletStart,
    );
    const tabletCss = optionTwoCss.slice(tabletStart, tabletEnd);
    const mobileCss = optionTwoCss.slice(tabletEnd);

    expect(tabletStart).toBeGreaterThanOrEqual(0);
    expect(tabletEnd).toBeGreaterThan(tabletStart);
    expect(tabletCss).toMatch(
      /\[data-role="dashboard-home-status-row"\],\s*\.page[^}]*\[data-role="dashboard-home-partial-toggle"\]\s*\{[^}]*display:\s*none;/s,
    );
    expect(tabletCss).toMatch(
      /\[data-testid="dashboard-home-search-box"\]\s*\{[^}]*width:\s*28px;[^}]*min-width:\s*28px;/s,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="dashboard-home-agent-open"\]\s*\{[^}]*display:\s*none;/s,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="dashboard-home-search-box"\]:focus-within\s*\{[^}]*position:\s*absolute;[^}]*width:\s*min\(/s,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="dashboard-home-toolbar"\]\s*\{[^}]*flex-direction:\s*row\s*!important;/s,
    );
    expect(mobileCss).toMatch(
      /\[data-role="dashboard-home-date-control"\]\s*\{[^}]*width:\s*auto\s*!important;[^}]*gap:\s*8px;/s,
    );
    expect(tabletCss).toMatch(
      /\[data-role="dashboard-home-toolbar-left"\]\s*\{[^}]*flex-wrap:\s*wrap;/s,
    );
  });

  it("moves toolbar controls into separate rows on narrow desktop widths", () => {
    const narrowDesktopStart = optionTwoCss.indexOf(
      "@media (min-width: 1025px) and (max-width: 1399px)",
    );
    const narrowDesktopEnd = optionTwoCss.indexOf(
      "@media (max-width: 1280px)",
      narrowDesktopStart,
    );
    const narrowDesktopCss = optionTwoCss.slice(
      narrowDesktopStart,
      narrowDesktopEnd,
    );

    expect(narrowDesktopStart).toBeGreaterThanOrEqual(0);
    expect(narrowDesktopEnd).toBeGreaterThan(narrowDesktopStart);
    expect(narrowDesktopCss).toMatch(
      /\[data-testid="dashboard-home-toolbar"\]\s*\{[^}]*height:\s*auto;[^}]*min-height:\s*54px;/s,
    );
    expect(narrowDesktopCss).toMatch(
      /\[data-role="dashboard-home-toolbar-left"\]\s*\{[^}]*width:\s*100%;[^}]*flex:\s*1 1 100%;/s,
    );
    expect(narrowDesktopCss).toMatch(
      /\[data-role="dashboard-home-toolbar-right"\]\s*\{[^}]*width:\s*100%;[^}]*margin-left:\s*0;/s,
    );
  });

  it("keeps a dense two-band layout and removes vertical table scrolling at the intermediate breakpoint", () => {
    const intermediateStart = optionTwoCss.indexOf(
      "@media (min-width: 900px) and (max-width: 1024px)",
    );
    const intermediateEnd = optionTwoCss.indexOf(
      "@media (max-width: 899px)",
      intermediateStart,
    );
    const intermediateCss = optionTwoCss.slice(
      intermediateStart,
      intermediateEnd,
    );

    expect(intermediateStart).toBeGreaterThanOrEqual(0);
    expect(intermediateEnd).toBeGreaterThan(intermediateStart);
    expect(intermediateCss).toMatch(
      /\.bodyGrid\s*\{[^}]*grid-template-columns:\s*minmax\(0, 38fr\) minmax\(0, 24fr\) minmax\(0, 38fr\);/s,
    );
    expect(intermediateCss).toMatch(
      /\.holdingsChangesBody\s*\{[^}]*grid-template-columns:\s*minmax\(0, 62fr\) minmax\(280px, 38fr\);/s,
    );
    expect(intermediateCss).toMatch(
      /\.extendedEvidence\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\);/s,
    );
    expect(intermediateCss).toMatch(
      /\.tableScroller\s*\{[^}]*height:\s*auto;[^}]*overflow:\s*visible;/s,
    );
    expect(intermediateCss).toMatch(
      /\.positionMatrix th:nth-child\(2\)\s*\{[^}]*width:\s*20%;/s,
    );
    expect(intermediateCss).toMatch(
      /\.holdingsTablePanel th:nth-child\(2\)\s*\{[^}]*width:\s*96px;/s,
    );
  });

  it("uses natural card height instead of nested vertical scrolling below the intermediate breakpoint", () => {
    const narrowStart = optionTwoCss.indexOf("@media (max-width: 899px)");
    const narrowEnd = optionTwoCss.indexOf(
      "@media (max-width: 720px)",
      narrowStart,
    );
    const narrowCss = optionTwoCss.slice(narrowStart, narrowEnd);

    expect(narrowStart).toBeGreaterThanOrEqual(0);
    expect(narrowEnd).toBeGreaterThan(narrowStart);
    expect(narrowCss).toMatch(
      /\.holdingsChanges\s*\{[^}]*height:\s*auto;[^}]*max-height:\s*none;/s,
    );
    expect(narrowCss).toMatch(
      /\.tableScroller\s*\{[^}]*overflow-x:\s*auto;[^}]*overflow-y:\s*visible;/s,
    );
  });

  it("uses natural height for desktop evidence rows without clipping their content", () => {
    const riskPanel = optionTwoCss.match(/\.riskTasks\s*\{(?=[^}]*grid-column:)([^}]+)\}/s)?.[1];
    expect(riskPanel).toContain("min-height: 0;");
    expect(riskPanel).not.toMatch(/(?:^|;)\s*(?:height|max-height):\s*\d+px/s);
    expect(optionTwoCss).toMatch(
      /\.marketResearchPanel\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;[^}]*height:\s*220px;[^}]*min-height:\s*220px;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.trustFooter\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.extendedEvidence\s*>\s*section\s*\{[^}]*display:\s*flex;[^}]*height:\s*auto;[^}]*min-height:\s*0;[^}]*flex-direction:\s*column;[^}]*align-self:\s*start;[^}]*overflow:\s*visible;/s,
    );
    expect(deferredEvidenceCss).toMatch(
      /\.(?:dhCalendarSection|dhBondNewsSection)\s*:\s*global\(\[data-layout-role="research-calendar-card"\]\),\s*\.(?:dhCalendarSection|dhBondNewsSection)\s*:\s*global\(\[data-layout-role="bond-news-card"\]\)\s*\{[^}]*height:\s*auto\s*!important;[^}]*min-height:\s*0\s*!important;[^}]*max-height:\s*none\s*!important;[^}]*flex:\s*1\s+1\s+auto;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.extendedEvidence\s*\{[^}]*align-items:\s*start;[^}]*grid-template-columns:\s*minmax\(0, 1fr\);/s,
    );
    expect(deferredEvidenceCss).toMatch(
      /\.dhCalendarSection\s+\.dhMacroBriefingGrid\s*\{[^}]*grid-template-columns:\s*minmax\(520px, 0\.9fr\) minmax\(700px, 1\.1fr\)\s*!important;/s,
    );
    expect(deferredEvidenceCss).toMatch(
      /\.(?:dhCalendarSection|dhBondNewsSection)\s*:\s*global\(\[data-layout-role="bond-news-grid"\]\)\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1\.7fr\) minmax\(340px, 0\.7fr\)\s*!important;/s,
    );
    expect(deferredEvidenceCss).not.toContain(
      '[data-layout-role="bond-news-item"]:nth-child(n + 2)',
    );
    expect(deferredEvidenceCss).toMatch(
      /@media \(max-width:\s*1600px\)\s*\{[^}]*\.dhMacroBriefingGrid[^}]*\[data-layout-role="bond-news-grid"\][^}]*grid-template-columns:\s*minmax\(0, 1fr\)\s*!important;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.extendedEvidenceHeader\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;/s,
    );
  });

  it("keeps a page-scoped CJK reading face and a distinct tabular data face", () => {
    expect(optionTwoCss).toMatch(
      /\.page\s*\{[^}]*--option-two-font-ui:\s*var\(--moss-font-sans\);[^}]*--option-two-font-data:[^;]*"Bahnschrift"[^;]*var\(--moss-font-mono\);[^}]*--font-tabular:\s*var\(--option-two-font-data\);/s,
    );
    expect(optionTwoCss).toMatch(
      /\.page\s*\{[^}]*font-family:\s*var\(--option-two-font-ui\);[^}]*font-synthesis:\s*none;[^}]*font-variant-numeric:\s*tabular-nums lining-nums;/s,
    );
    expect(deferredEvidenceCss).toMatch(
      /\[data-layout-role="bond-news-body"\]\s*>\s*strong\)\s*\{[^}]*font-family:\s*var\(--option-two-font-ui\)\s*!important;[^}]*font-weight:\s*500\s*!important;[^}]*line-height:\s*17px\s*!important;/s,
    );
    expect(deferredEvidenceCss).toMatch(
      /\[data-layout-role="bond-news-internal-header"\]\s*>\s*time\)[^{]*\{[^}]*font-family:\s*var\(--option-two-font-data\)\s*!important;/s,
    );
  });
});
