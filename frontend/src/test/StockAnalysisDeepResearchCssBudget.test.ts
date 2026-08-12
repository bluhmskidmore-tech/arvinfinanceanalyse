import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("StockAnalysisDeepResearch CSS budget", () => {
  // Ratchet baseline: 2,222 lines / 295 `!important`; the review buffer is
  // intentionally limited to 50 lines and 10 priority declarations.
  it("keeps the deep-research stylesheet from regrowing override layers", () => {
    const cssPath = resolve(
      process.cwd(),
      "src/features/stock-analysis/pages/StockAnalysisDeepResearch.css",
    );
    const css = readFileSync(cssPath, "utf8");
    const lineCount = css
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trimEnd()
      .split("\n").length;
    const importantCount = (css.match(/!important/g) ?? []).length;

    expect(lineCount).toBeLessThanOrEqual(2272);
    expect(importantCount).toBeLessThanOrEqual(305);
  });
});
