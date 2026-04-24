import type { SeriesOption } from "echarts";
import { describe, expect, it } from "vitest";

import type { Numeric } from "../api/contracts";
import type { AssetClassRiskSummary, KRDBucket } from "../features/bond-analytics/types";
import {
  buildAssetClassMarketValuePieOption,
  buildKrdDv01BarOption,
} from "../features/bond-analytics/utils/echartsRiskCharts";
import { designTokens } from "../theme/designSystem";
import { formatRawAsNumeric } from "../utils/format";

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  signAware = false,
  precision?: number,
): Numeric {
  return formatRawAsNumeric({
    raw,
    unit,
    sign_aware: signAware,
    ...(precision === undefined ? {} : { precision }),
  });
}

const yuan = (raw: number | null) => numeric(raw, "yuan", true);
const pct = (raw: number | null, precision?: number) => numeric(raw, "pct", false, precision);
const ratio = (raw: number | null, precision?: number) => numeric(raw, "ratio", false, precision);
const dv01 = (raw: number | null, precision?: number) => numeric(raw, "dv01", false, precision);

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
          krd: ratio(0),
          dv01: dv01(123_456),
          market_value_weight: ratio(0),
        },
        {
          tenor: "5Y",
          krd: ratio(0),
          dv01: dv01(240_000),
          market_value_weight: ratio(0),
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
          market_value: yuan(10_000_000),
          duration: ratio(1),
          dv01: dv01(1),
          weight: pct(0.4, 0),
        },
        {
          asset_class: "credit",
          market_value: yuan(8_000_000),
          duration: ratio(2),
          dv01: dv01(2),
          weight: pct(0.35, 0),
        },
        {
          asset_class: "other",
          market_value: yuan(5_000_000),
          duration: ratio(3),
          dv01: dv01(3),
          weight: pct(0.25, 0),
        },
        {
          asset_class: "unknown_slice",
          market_value: yuan(1_000_000),
          duration: ratio(0),
          dv01: dv01(0),
          weight: pct(0.05, 0),
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
      expect(series?.data?.[0]?.itemStyle?.color).toBe(designTokens.color.info[500]);
      expect(series?.data?.[1]?.itemStyle?.color).toBe(designTokens.color.warning[400]);
      expect(series?.data?.[2]?.itemStyle?.color).toBe(designTokens.color.neutral[500]);
      expect(series?.data?.[3]?.itemStyle?.color).toBe(designTokens.color.neutral[400]);

      const tooltip = option?.tooltip as {
        formatter?: (p: {
          data?: {
            name: string;
            marketValueRaw: Numeric;
            weight: Numeric;
          };
        }) => string;
      };
      const text = tooltip?.formatter?.({
        data: {
          name: "rate",
          marketValueRaw: yuan(10_000_000),
          weight: pct(0.4, 0),
        },
      });
      expect(text).toContain("市值");
      expect(text).toContain("权重");
      expect(text).toContain("40%");
    });
  });
});
