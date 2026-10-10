import { describe, expect, it } from "vitest";

import type { ProductCategoryMetricValue } from "../../../api/contracts";
import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import { EM_DASH } from "../../../utils/format";

import {
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryTrendSnapshot,
} from "./productCategoryPnlPageModel";

function percentMetric(raw: string | null): ProductCategoryMetricValue | null {
  return raw === null
    ? null
    : { raw, display: `${Number(raw).toFixed(2)}%`, unit: "percent" };
}

function spreadSnapshot(
  view: "monthly" | "ytd",
  reportDate: string,
  values: { asset: string | null; liability: string | null; spread: string | null },
) {
  const { result } = buildMockProductCategoryPnlEnvelope({ view, reportDate });
  return buildProductCategoryTrendSnapshot({
    ...result,
    interest_spread: {
      ...result.interest_spread,
      all_currency_asset_yield_pct: percentMetric(values.asset),
      all_currency_liability_yield_pct: percentMetric(values.liability),
      all_currency_spread_pct: percentMetric(values.spread),
    },
  });
}

describe("product category spread movement units", () => {
  it.each(["monthly", "ytd"] as const)(
    "converts current and prior % levels to bp alongside the % change in the %s view",
    (view) => {
      const surface = buildProductCategoryDiagnosticsSurface({
        rows: [],
        trendSnapshots: [
          spreadSnapshot(view, "2026-08-31", {
            asset: "3.22355375",
            liability: "1",
            spread: "2.22355375",
          }),
          spreadSnapshot(view, "2026-07-31", {
            asset: "1.83755375",
            liability: "1.2",
            spread: "0.63755375",
          }),
        ],
      });

      expect(surface.spreadAttribution).toMatchObject({
        state: "ready",
        currentSpreadLabel: "222.4 bp",
        priorSpreadLabel: "63.8 bp",
        spreadDeltaLabel: "+158.6 bp",
        currentAssetYieldLabel: "3.22%",
        currentLiabilityYieldLabel: "1.00%",
        assetYieldDeltaLabel: "+138.6 bp",
        liabilityYieldDeltaLabel: "-20 bp",
      });
    },
  );

  it("preserves negative and zero spread levels when converting to bp", () => {
    const surface = buildProductCategoryDiagnosticsSurface({
      rows: [],
      trendSnapshots: [
        spreadSnapshot("monthly", "2026-08-31", {
          asset: "0.76",
          liability: "1",
          spread: "-0.24",
        }),
        spreadSnapshot("monthly", "2026-07-31", {
          asset: "1",
          liability: "1",
          spread: "0",
        }),
      ],
    });

    expect(surface.spreadAttribution).toMatchObject({
      state: "ready",
      currentSpreadLabel: "-24 bp",
      priorSpreadLabel: "0 bp",
      spreadDeltaLabel: "-24 bp",
    });
  });

  it.each([
    { current: null, prior: "1.05", currentLabel: EM_DASH, priorLabel: "105 bp" },
    { current: "1.05", prior: null, currentLabel: "105 bp", priorLabel: EM_DASH },
    { current: null, prior: null, currentLabel: EM_DASH, priorLabel: EM_DASH },
  ])("keeps missing spread levels distinct from zero: %j", (values) => {
    const surface = buildProductCategoryDiagnosticsSurface({
      rows: [],
      trendSnapshots: [
        spreadSnapshot("monthly", "2026-08-31", {
          asset: "2.68",
          liability: "1.63",
          spread: values.current,
        }),
        spreadSnapshot("monthly", "2026-07-31", {
          asset: "2.68",
          liability: "1.63",
          spread: values.prior,
        }),
      ],
    });

    expect(surface.spreadAttribution).toMatchObject({
      state: "incomplete",
      currentSpreadLabel: values.currentLabel,
      priorSpreadLabel: values.priorLabel,
      spreadDeltaLabel: EM_DASH,
    });
  });

  describe.each(["monthly", "ytd"] as const)("%s prior comparison readiness", (view) => {
    it.each(["asset", "liability", "spread"] as const)(
      "marks a prior snapshot with missing %s as incomplete",
      (missingMetric) => {
        const surface = buildProductCategoryDiagnosticsSurface({
          rows: [],
          trendSnapshots: [
            spreadSnapshot(view, "2026-08-31", {
              asset: "2.68", liability: "1.63", spread: "1.05",
            }),
            spreadSnapshot(view, "2026-07-31", {
              asset: "2.68", liability: "1.63", spread: "1.05",
              [missingMetric]: null,
            }),
          ],
        });

        expect(surface.spreadAttribution).toMatchObject({
          state: "incomplete",
          reason: "缺少可比上期趋势快照，无法完成利差变动归因。",
          currentSpreadLabel: "105 bp",
          driverHint: "缺少完整收益率对比",
        });
      },
    );

    it("keeps complete zero-valued snapshots ready", () => {
      const surface = buildProductCategoryDiagnosticsSurface({
        rows: [],
        trendSnapshots: ["2026-08-31", "2026-07-31"].map((reportDate) =>
          spreadSnapshot(view, reportDate, { asset: "0", liability: "0", spread: "0" }),
        ),
      });

      expect(surface.spreadAttribution).toMatchObject({
        state: "ready",
        currentSpreadLabel: "0 bp",
        priorSpreadLabel: "0 bp",
        assetYieldDeltaLabel: "0 bp",
        liabilityYieldDeltaLabel: "0 bp",
        spreadDeltaLabel: "0 bp",
      });
    });
  });
});
