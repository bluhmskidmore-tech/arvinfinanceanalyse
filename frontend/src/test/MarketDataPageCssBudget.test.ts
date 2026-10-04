import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// CSS ratchet, same pattern as StockAnalysisPageSizeGuard.test.ts: the 2026-08-12 governance
// pass pruned MarketDataPage.css from 13618 lines / 996 `!important` down to 6404 / 670 by
// removing selector arms that referenced classes and data-testids from superseded layout
// generations (the pre "2026-07-01-redesign" ledger/tape-cockpit/reference/morning/overview
// shells - none of those class names or testids exist in any current .tsx anymore). The
// 2026-08-13 zombie pass removed the DOM-less overview-board/api-surface/external-map__rows
// island plus dead analyst-split/coverage-command/rate-trend-empty arms (5988 / 659). The
// 2026-08-27 dead-code pass deleted 102 zero-reference market-data-* classes (terminal-rail/
// desk-bridge/evidence-section/pill-tag/news-calendar plus classes orphaned by removing the dead
// MarketDataHeroSection/MarketTerminalTicker components) and the duplicated --imd-* variable
// block of the "Data cards + charts" pass (4534 / 429 after that pass; the same-day budget also
// absorbs the series-compact right-rail collapse styles landed in parallel). The 2026-08-27 IA
// stage-2 retirement pass (macro depth tabs / Livermore collapse / linkage collapse deleted)
// dropped 47 zero-reference class selectors plus the retired `[data-testid=...]` arms and their
// emptied @media blocks (4652 / 424 -> 4195 / 409), then added the ~79-line shell for the two
// replacement summary/nav cards (4274 / 409). One dead island is left for a later pass:
// `[data-testid="market-data-surface-preview-band"]` has no render site and still holds
// 26 `!important`. Budgets
// may be lowered freely; raising one must be a deliberate, reviewed decision. Prefer editing or
// deleting existing rules over appending a new override pass.
describe("MarketDataPage stylesheet budget", () => {
  it("keeps the page stylesheet from regrowing override layers", () => {
    const cssPath = resolve(
      process.cwd(),
      "src/features/market-data/pages/MarketDataPage.css",
    );
    const css = readFileSync(cssPath, "utf8");
    const lineCount = css.replace(/\r\n/g, "\n").trimEnd().split("\n").length;
    const importantCount = (css.match(/!important/g) ?? []).length;

    expect(lineCount).toBeLessThanOrEqual(4284);
    expect(importantCount).toBeLessThanOrEqual(414);
  });
});
