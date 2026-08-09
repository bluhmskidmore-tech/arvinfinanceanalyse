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

    const deferredEvidenceCss = readFileSync(deferredEvidenceCssPath, "utf8");
    const styleAccesses = new Set(
      [bondNewsSource, researchCalendarSource].flatMap((source) =>
        [...source.matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(
          (match) => match[1],
        ),
      ),
    );

    expect(styleAccesses.size).toBe(71);
    for (const className of styleAccesses) {
      expect(deferredEvidenceCss).toContain(`.${className}`);
    }
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
      /\[data-role="dashboard-home-date-control"\]\s*\{[^}]*width:\s*92px\s*!important;/s,
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
      /\.extendedEvidence\s*\{[^}]*grid-template-columns:\s*minmax\(0, 42fr\) minmax\(0, 58fr\);/s,
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

  it("reserves breathing room for the desktop evidence rows without clipping their content", () => {
    expect(optionTwoCss).toMatch(
      /\.riskTasks\s*\{[^}]*height:\s*186px;[^}]*min-height:\s*186px;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.marketResearchPanel\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;[^}]*height:\s*220px;[^}]*min-height:\s*220px;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.trustFooter\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;/s,
    );
    expect(optionTwoCss).toMatch(
      /\.extendedEvidence\s*>\s*section\s*\{[^}]*height:\s*358px;[^}]*min-height:\s*358px;/s,
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
    expect(optionTwoCss).toMatch(
      /\[data-layout-role="bond-news-body"\]\s*>\s*strong\)\s*\{[^}]*font-family:\s*var\(--option-two-font-ui\)\s*!important;[^}]*font-weight:\s*500\s*!important;[^}]*line-height:\s*17px\s*!important;/s,
    );
    expect(optionTwoCss).toMatch(
      /\[data-layout-role="bond-news-internal-header"\]\s*>\s*time\)[^{]*\{[^}]*font-family:\s*var\(--option-two-font-data\)\s*!important;/s,
    );
  });
});
