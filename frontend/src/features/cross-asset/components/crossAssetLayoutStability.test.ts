import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function readFrontendCss(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("cross-asset layout stability", () => {
  it("reserves first-screen geometry while async data settles", () => {
    const heroCss = readFrontendCss(
      "src/features/cross-asset/components/CrossAssetHeroPanel.css",
    );
    const statusCss = readFrontendCss(
      "src/features/cross-asset/components/CrossAssetStatusStrip.css",
    );
    const kpiCss = readFrontendCss(
      "src/features/cross-asset/components/CrossAssetKpiBand.css",
    );

    expect(heroCss).toMatch(
      /\.cross-asset-hero-panel__conclusion \{[\s\S]*?min-height: 3\.1em;[\s\S]*?\}/,
    );
    expect(heroCss).toMatch(
      /@media \(max-width: 1200px\) \{[\s\S]*?\.cross-asset-hero-panel__conclusion \{[\s\S]*?min-height: 4\.65em;/,
    );
    expect(heroCss).toMatch(
      /@media \(max-width: 520px\) \{[\s\S]*?\.cross-asset-hero-panel__conclusion \{[\s\S]*?min-height: 6\.2em;/,
    );
    expect(heroCss).toMatch(
      /@media \(max-width: 400px\) \{[\s\S]*?\.cross-asset-hero-panel__conclusion \{[\s\S]*?min-height: 12\.4em;/,
    );

    expect(statusCss).toMatch(
      /\.cross-asset-status-strip \{[\s\S]*?min-height: 42px;[\s\S]*?\}/,
    );
    expect(statusCss).toMatch(
      /@media \(max-width: 400px\) \{[\s\S]*?\.cross-asset-status-strip \{[\s\S]*?min-height: 72px;/,
    );
    expect(kpiCss).toMatch(
      /\.cross-asset-kpi-band__foot \{[\s\S]*?min-height: 24px;[\s\S]*?\}/,
    );
  });

  it("keeps heavy async placeholders close to their settled panel heights", () => {
    const pageCss = readFrontendCss(
      "src/features/cross-asset/pages/CrossAssetDriversPage.css",
    );
    const transmissionCss = readFrontendCss(
      "src/features/cross-asset/components/TransmissionChainGraph.css",
    );
    const yieldCurveCss = readFrontendCss(
      "src/features/cross-asset/components/YieldCurvePanel.css",
    );

    expect(pageCss).toMatch(
      /\.cross-asset-zone-linkage\s+\.moss-page-v2-state-surface\[data-state-variant="loading"\] \{[\s\S]*?min-height: 520px;/,
    );
    expect(pageCss).toMatch(
      /@media \(max-width: 1200px\) \{[\s\S]*?\.cross-asset-zone-linkage\s+\.moss-page-v2-state-surface\[data-state-variant="loading"\] \{[\s\S]*?min-height: 605px;/,
    );
    expect(pageCss).toMatch(
      /@media \(max-width: 900px\) \{[\s\S]*?\.cross-asset-zone-linkage\s+\.moss-page-v2-state-surface\[data-state-variant="loading"\] \{[\s\S]*?min-height: 960px;/,
    );
    expect(pageCss).toMatch(
      /@media \(max-width: 400px\) \{[\s\S]*?\.cross-asset-zone-linkage\s+\.moss-page-v2-state-surface\[data-state-variant="loading"\] \{[\s\S]*?min-height: 1065px;/,
    );
    expect(pageCss).toMatch(
      /\.cross-asset-reference-depth \.cross-asset-trend-panel__loading,[\s\S]*?\.cross-asset-reference-depth \.cross-asset-trend-chart__canvas \{[\s\S]*?height: 300px;/,
    );
    expect(pageCss).toMatch(
      /@media \(max-width: 520px\) \{[\s\S]*?\.cross-asset-reference-toolbar \{[\s\S]*?flex-direction: column;/,
    );

    expect(transmissionCss).toMatch(
      /\.tcg__state \{[\s\S]*?min-width: 0;[\s\S]*?aspect-ratio: 3 \/ 1;[\s\S]*?box-sizing: border-box;/,
    );
    expect(transmissionCss).not.toContain("min-height: 120px");
    expect(transmissionCss).not.toContain("33.333vw");

    expect(yieldCurveCss).toMatch(
      /\.yield-curve-panel__chart \{[\s\S]*?min-height: 360px;/,
    );
    expect(yieldCurveCss).toMatch(
      /\.yield-curve-panel__loading \{[\s\S]*?min-height: 360px;/,
    );
    expect(yieldCurveCss).toMatch(
      /\.yield-curve-panel__empty \{[\s\S]*?min-height: 120px;/,
    );
  });
});
