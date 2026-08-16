import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// CSS ratchet for the macro toolkit page stylesheet. The sheet had accreted whole
// layout generations as stacked overrides, leaving dead rule islands (the removed
// cockpit header / title-block / meta, the decision-slab, the command-brief, and
// the two-col shell) whose selectors no longer matched any rendered element. A
// static dead-code prune removed 21 fully-dead rules plus 6 dead selector arms
// with zero rendering change, verified by a 1920/1280 Playwright geometry A/B at
// 0px delta and the existing MacroToolkitPage source-text pins staying green.
// Budgets may be lowered freely; raising one must be a deliberate, reviewed
// decision. Prefer editing or deleting existing rules over appending a new
// override pass, and cover layout with Playwright geometry checks rather than new
// CSS source-text pins.
describe("MacroToolkitPage stylesheet budget guard", () => {
  it("keeps the page stylesheet from regrowing dead override layers", () => {
    const cssPath = resolve(
      process.cwd(),
      "src/features/macro-toolkit/pages/MacroToolkitPage.css",
    );
    const css = readFileSync(cssPath, "utf8");
    const lineCount = css
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trimEnd()
      .split("\n").length;
    const importantCount = (css.match(/!important/g) ?? []).length;

    // Post-governance baseline (2026-08-12): 5741 lines / 1 `!important`.
    // Rebased 2026-08-12 later the same day: the decision-chain feature commits
    // (157bd93e trend charts / signal history / scheduler health and follow-ups)
    // added ~103 lines of live panel styles after the baseline was cut, bringing
    // the sheet to 5844 lines. Deliberate raise to 5844 + 50 headroom; lowering
    // is still always welcome.
    // Lowered 2026-08-12 again: the PageSectionLead `!important` inversion块被
    // 根治（PagePrimitives 内联色改为 --moss-page-ink* 变量 + 原值兜底，根块
    // 变量接管），sheet 回到 5792 lines / 1 `!important`（仅历史遗留的
    // .macro-toolkit-row--selected）。Budget: 5792 + 50 headroom / 1.
    expect(lineCount).toBeLessThanOrEqual(5842);
    expect(importantCount).toBeLessThanOrEqual(1);
  });
});
