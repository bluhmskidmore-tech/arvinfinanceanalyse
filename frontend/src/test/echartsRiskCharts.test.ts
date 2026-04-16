import type { SeriesOption } from "echarts";
import { describe, expect, it } from "vitest";

import type { AssetClassRiskSummary, KRDBucket } from "../features/bond-analytics/types";
import {
  buildAssetClassMarketValuePieOption,
  buildKrdDv01BarOption,
} from "../features/bond-analytics/utils/echartsRiskCharts";

function firstSeriesEntry(series: SeriesOption | SeriesOption[] | undefined): SeriesOption | undefined {
  if (series == null) return undefined;
  return Array.isArray(series) ? series[0] : series;
}

describe("echartsRiskCharts", () => {
  describe("buildKrdDv01BarOption", () => {
    it("returns null for empty buckets", () => {
      expect(buildKrdDv01BarOption([])).toBeNull();
    });

    it("builds category bar option with tenor axis and tooltip contract", () => {
      const buckets: KRDBucket[] = [
        {
          tenor: "1Y",
          krd: "0",
          dv01: "123456",
          market_value_weight: "0",
        },
        {
          tenor: "5Y",
          krd: "0",
          dv01: "240000",
          market_value_weight: "0",
        },
      ];
      const option = buildKrdDv01BarOption(buckets);
      expect(option).not.toBeNull();
      expect(option?.xAxis).toMatchObject({
        type: "category",
        data: ["1Y", "5Y"],
      });
      const series = firstSeriesEntry(option?.series) as { data: unknown[] } | undefined;
      expect(series?.data?.length).toBe(2);

      const tooltip = option?.tooltip as {
        formatter?: (p: unknown) => string;
      };
      const line = tooltip?.formatter?.([{ dataIndex: 0 }]);
      expect(line).toContain("1Y");
      expect(line).toContain("DV01");
      expect(line).toMatch(/万/);
    });
  });

  describe("buildAssetClassMarketValuePieOption", () => {
    it("returns null for empty rows", () => {
      expect(buildAssetClassMarketValuePieOption([])).toBeNull();
    });

    it("builds pie option with slice colors, tooltip, and data length", () => {
      const rows: AssetClassRiskSummary[] = [
        {
          asset_class: "rate",
          market_value: "10000000",
          duration: "1",
          dv01: "1",
          weight: "40%",
        },
        {
          asset_class: "credit",
          market_value: "8000000",
          duration: "2",
          dv01: "2",
          weight: "35%",
        },
        {
          asset_class: "other",
          market_value: "5000000",
          duration: "3",
          dv01: "3",
          weight: "25%",
        },
        {
          asset_class: "unknown_slice",
          market_value: "1000000",
          duration: "0",
          dv01: "0",
          weight: "5%",
        },
      ];
      const option = buildAssetClassMarketValuePieOption(rows);
      expect(option).not.toBeNull();
      const series = firstSeriesEntry(option?.series) as {
        type?: string;
        data: Array<{ itemStyle?: { color?: string } }>;
      };
      expect(series?.type).toBe("pie");
      expect(series?.data?.length).toBe(4);
      expect(series?.data?.[0]?.itemStyle?.color).toBe("#1f5eff");
      expect(series?.data?.[1]?.itemStyle?.color).toBe("#ff7a45");
      expect(series?.data?.[2]?.itemStyle?.color).toBe("#8c8c8c");
      expect(series?.data?.[3]?.itemStyle?.color).toBe("#bfbfbf");

      const tooltip = option?.tooltip as {
        formatter?: (p: {
          data?: {
            name: string;
            marketValueRaw: string;
            weight: string;
          };
        }) => string;
      };
      const text = tooltip?.formatter?.({
        data: {
          name: "rate",
          marketValueRaw: "10000000",
          weight: "40%",
        },
      });
      expect(text).toContain("市值");
      expect(text).toContain("权重");
      expect(text).toContain("40%");
    });
  });
});
