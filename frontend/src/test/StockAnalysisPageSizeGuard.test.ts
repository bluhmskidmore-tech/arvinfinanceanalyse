import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("StockAnalysisPage extraction guard", () => {
  it("keeps the page container from regrowing beyond the current extraction boundary", () => {
    const pagePath = resolve(
      process.cwd(),
      "src/features/stock-analysis/pages/StockAnalysisPage.tsx",
    );
    const lineCount = readFileSync(pagePath, "utf8")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trimEnd()
      .split("\n").length;

    expect(lineCount).toBeLessThanOrEqual(4000);
  });

  it("keeps stock-analysis behavior split across focused modules", () => {
    const featureRoot = resolve(process.cwd(), "src/features/stock-analysis");
    const moduleCount = [
      ...readdirSync(resolve(featureRoot, "components")),
      ...readdirSync(resolve(featureRoot, "hooks")),
      ...readdirSync(resolve(featureRoot, "lib")),
    ].filter((fileName) => /\.(ts|tsx)$/.test(fileName)).length;

    expect(moduleCount).toBeGreaterThanOrEqual(35);
  });

  // CSS ratchet: the page stylesheet once grew to 21k lines / 2.4k `!important`
  // by stacking whole layout generations as end-of-file overrides, which is how
  // stale `grid-template-areas` shells ended up shredding the redesigned first
  // screen. Budgets may be lowered freely; raising one must be a deliberate,
  // reviewed decision. Prefer editing or deleting existing rules over appending
  // a new override pass, and cover layout with the Playwright geometry spec
  // (tests/playwright/stock-analysis-first-screen-geometry.spec.mjs), not with
  // CSS source-text pins.
  it("keeps the page stylesheet from regrowing override layers", () => {
    const cssPath = resolve(
      process.cwd(),
      "src/features/stock-analysis/pages/StockAnalysisPage.css",
    );
    const css = readFileSync(cssPath, "utf8");
    const lineCount = css.replace(/\r\n/g, "\n").trimEnd().split("\n").length;
    const importantCount = (css.match(/!important/g) ?? []).length;

    expect(lineCount).toBeLessThanOrEqual(10893);
    expect(importantCount).toBeLessThanOrEqual(899);
  });
});
