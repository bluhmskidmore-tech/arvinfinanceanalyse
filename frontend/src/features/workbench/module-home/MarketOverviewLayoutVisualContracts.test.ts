import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const featureRoot = resolve(process.cwd(), "src/features/workbench/module-home");
const shellCss = readFileSync(
  resolve(featureRoot, "marketHomeNocturne.module.css"),
  "utf8",
);
const firstScreenCss = readFileSync(
  resolve(featureRoot, "marketOverviewDenseFirstScreen.module.css"),
  "utf8",
);

describe("market overview layout visual contracts", () => {
  it("bounds the desktop scan width with a single page chapter navigation", () => {
    expect(shellCss).not.toMatch(/\.subpageNav\s*\{/s);
    expect(shellCss).toMatch(
      /\.topbar\s*\{[^}]*max-width:\s*2180px;[^}]*margin-inline:\s*auto;/s,
    );
    expect(shellCss).toMatch(
      /\.chapterNav\s*\{[^}]*max-width:\s*2180px;[^}]*height:\s*36px;/s,
    );
    expect(shellCss).toMatch(
      /\.main\s*\{[^}]*max-width:\s*2180px;[^}]*margin-inline:\s*auto;/s,
    );
  });

  it("keeps the rates observation dominant with a compact impact aside and collapsible evidence", () => {
    expect(firstScreenCss).toMatch(
      /\.primaryObservation\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\) 320px;/s,
    );
    expect(firstScreenCss).toMatch(
      /\.impactPanel\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*gap:\s*16px;/s,
    );
    expect(firstScreenCss).toMatch(
      /\.verificationDetails\s*>\s*summary\s*\{[^}]*cursor:\s*pointer;/s,
    );
  });

  it("keeps the active desktop market subpage legible on its Nocturne background", () => {
    expect(shellCss).toMatch(
      /:global\([^\n]*data-moss-theme-scope="market-overview"[^\n]*\.workbench-section-subnav__link\[data-active="true"\]\)\s*\{[^}]*background:\s*color-mix\(in srgb, var\(--nct-accent\) 14%, transparent\) !important;[^}]*border-color:\s*var\(--nct-accent\) !important;[^}]*color:\s*var\(--nct-ink\) !important;/s,
    );
  });

  it("keeps four desktop quotes readable and uses a two-column mobile tape", () => {
    expect(firstScreenCss).toMatch(
      /\/\* Figma v1\.4:[^*]*\*\/\s*\.marketTape\s*\{[^}]*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\);/s,
    );
    expect(firstScreenCss).toMatch(
      /\.tapeCell:nth-child\(n\)\s*\{[^}]*min-height:\s*104px;[^}]*padding:\s*12px 16px;/s,
    );
    expect(firstScreenCss).toMatch(/\.tapeCell\s*>\s*strong\s*\{\s*font-size:\s*20px;/s);
    const mobileCss = firstScreenCss.slice(
      firstScreenCss.lastIndexOf("@media (max-width: 767px)"),
    );
    expect(mobileCss).toMatch(
      /\.marketTape\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);[^}]*grid-auto-flow:\s*row;/s,
    );
    expect(mobileCss).toMatch(
      /\.tapeCell:nth-child\(2n\)\s*\{\s*border-right:\s*0;/s,
    );
  });

  it("keeps the mobile shell compact within this page and scrolls all ticker items horizontally", () => {
    const mobileShell = shellCss.slice(shellCss.lastIndexOf("@media (max-width: 720px)"));
    expect(mobileShell).toMatch(
      /:global\([^\n]*data-moss-theme-scope="market-overview"[^\n]*\.workbench-page-context-shell\)\s*\{[^}]*display:\s*flex\s*!important;[^}]*flex-wrap:\s*nowrap;/s,
    );
    expect(mobileShell).toMatch(
      /:global\([^\n]*data-moss-theme-scope="market-overview"[^\n]*\.workbench-market-ticker-shell\)\s*\{[^}]*flex-wrap:\s*nowrap\s*!important;[^}]*overflow-x:\s*auto;/s,
    );
    expect(mobileShell).not.toMatch(/display:\s*none|font-size:/);
  });
});
