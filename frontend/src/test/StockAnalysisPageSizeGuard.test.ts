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
});
