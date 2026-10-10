import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const featureRoot = resolve(process.cwd(), "src/features/workbench/dashboard-home");
const readCss = (name: string) => readFileSync(resolve(featureRoot, name), "utf8");
const pageCss = readCss("dashboardHomeOptionTwo.module.css");
const governanceCss = readCss("dashboardHomeOptionTwoGovernanceSection.module.css");
const researchCss = readCss("dashboardHomeOptionTwoResearchList.module.css");
const supportCss = readCss("dashboardHomeOptionTwoSupportBand.module.css");
const shellCss = readCss("dashboardHomeShell.module.css");

describe("homepage style consistency", () => {
  it("defines shared page-local control, heading and single-line row scales", () => {
    expect(pageCss).toContain("--option-two-control-height: 32px;");
    expect(pageCss).toContain("--option-two-control-font-size: 12px;");
    expect(pageCss).toContain("--option-two-control-line-height: 18px;");
    expect(pageCss).toContain("--option-two-heading-line-height: 22px;");
    expect(pageCss).toContain("--option-two-row-height: 24px;");
  });

  it.each([
    ["portfolio and market", pageCss, /\.tabHeader button\s*\{([^}]+)\}/s],
    ["governance", governanceCss, /\.tabs button\s*\{([^}]+)\}/s],
  ] as const)("uses the same tab geometry and typography for %s", (_, css, pattern) => {
    const body = css.match(pattern)?.[1];
    expect(body).toBeDefined();
    expect(body).toContain("height: var(--option-two-control-height);");
    expect(body).toContain("padding: 0 var(--moss-space-2);");
    expect(body).toContain("font-size: var(--option-two-control-font-size);");
    expect(body).toContain("font-weight: 500;");
    expect(body).toContain("line-height: var(--option-two-control-line-height);");
    expect(body).toContain("var(--moss-motion-duration-fast)");
  });

  it.each([
    ["portfolio and market", pageCss, "tabHeader"],
    ["governance", governanceCss, "tabs"],
  ] as const)("keeps hover, selected and focus states consistent for %s", (_, css, name) => {
    expect(css).toContain(`.${name} button:not([aria-selected="true"]):hover`);
    expect(css).toContain(`.${name} button:focus-visible`);
    const selected = css.match(
      new RegExp(`\\.${name} button\\[aria-selected="true"\\]\\s*\\{([^}]+)\\}`, "s"),
    )?.[1];
    expect(selected).toContain("font-weight: 600;");
    expect(selected).toContain("color: var(--option-two-blue);");
    expect(css).toContain("background: var(--dh-api-blue-soft);");
  });

  it("uses shared heading leading and row density across homepage sections", () => {
    for (const css of [pageCss, governanceCss, researchCss, supportCss]) {
      expect(css).toContain("height: var(--option-two-row-height);");
    }
    for (const css of [pageCss, governanceCss, supportCss]) {
      expect(css).toContain("line-height: var(--option-two-heading-line-height);");
    }
  });

  it("uses the live dark theme for the desktop toolbar title", () => {
    const titles = [...shellCss.matchAll(
      /:global\(\[data-testid="dashboard-home-page"\]\)\[data-testid="dashboard-home-page"\] \.dhTitle\s*\{([^}]+)\}/gs,
    )];
    // The final desktop rule overrides the earlier, roomier shell treatment.
    const title = titles[titles.length - 1]?.[1];
    expect(title).toContain("color: var(--dh-api-ink);");
  });

  it("supports keyboard feedback and a consistent tint on actionable rows", () => {
    expect(pageCss).toContain('.page :is(a[href], button, input, select, [tabindex="0"]):focus-visible');
    expect(pageCss).toContain(".holdingsTablePanel tbody tr:focus-within");
    expect(researchCss).toContain(".table tbody tr:focus-within");
    expect(supportCss).toContain("background: var(--dh-api-blue-soft);");
  });
});
