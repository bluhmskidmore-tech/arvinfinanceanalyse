import { describe, expect, it } from "vitest";

import { createApiClient } from "../../api/client";
import {
  BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
  bondDashboardAssetSectionForGroup,
  selectBondDashboardBundleSection,
} from "./bondDashboardBundleModel";

describe("bondDashboardBundleModel", () => {
  it("maps asset group controls to the matching bundle section ids", () => {
    expect(bondDashboardAssetSectionForGroup("bond_type")).toBe("asset-structure");
    expect(bondDashboardAssetSectionForGroup("rating")).toBe("asset-structure-rating");
    expect(bondDashboardAssetSectionForGroup("portfolio_name")).toBe(
      "asset-structure-portfolio-name",
    );
    expect(bondDashboardAssetSectionForGroup("tenor_bucket")).toBe(
      "asset-structure-tenor-bucket",
    );
  });

  it("selects the same envelopes that the page previously received from single-section calls", async () => {
    const client = createApiClient({ mode: "mock" });
    const reportDate = "2026-03-31";
    const bundle = await client.fetchBondDashboardBundle(
      reportDate,
      BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
      { industryTopN: 10 },
    );

    expect(selectBondDashboardBundleSection(bundle, "headline-kpis")).toEqual(
      await client.getBondDashboardHeadlineKpis(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "risk-indicators")).toEqual(
      await client.getBondDashboardRiskIndicators(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "asset-structure")).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "bond_type"),
    );
    expect(selectBondDashboardBundleSection(bundle, "asset-structure-rating")).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "rating"),
    );
    expect(selectBondDashboardBundleSection(bundle, "asset-structure-portfolio-name")).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "portfolio_name"),
    );
    expect(selectBondDashboardBundleSection(bundle, "asset-structure-tenor-bucket")).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "tenor_bucket"),
    );
    expect(selectBondDashboardBundleSection(bundle, "yield-distribution")).toEqual(
      await client.getBondDashboardYieldDistribution(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "portfolio-comparison")).toEqual(
      await client.getBondDashboardPortfolioComparison(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "spread-analysis")).toEqual(
      await client.getBondDashboardSpreadAnalysis(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "maturity-structure")).toEqual(
      await client.getBondDashboardMaturityStructure(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "industry-distribution")).toEqual(
      await client.getBondDashboardIndustryDistribution(reportDate),
    );
    expect(selectBondDashboardBundleSection(bundle, "business-type-metrics")).toEqual(
      await client.getBondBusinessTypeMetrics({ reportDate }),
    );
  });
});
