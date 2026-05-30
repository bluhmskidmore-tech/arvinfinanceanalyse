import type { AssetStructurePayload, Numeric } from "../../../../api/contracts";
import { formatYi, nativeToNumber } from "../../../bond-dashboard/utils/format";
import type { HomeAssetBar } from "../dashboardHomeView";

const FILL_CLASSES = ["blue", "redish", "greenish", "grey"] as const;
const DEFAULT_TOP_N = 4;

function pctFromNumeric(value: Numeric | null | undefined): number {
  if (value?.raw == null || !Number.isFinite(value.raw)) {
    return 0;
  }
  const raw = value.raw;
  if (value.unit === "pct" && raw > 1) {
    return raw;
  }
  return raw * 100;
}

function slugId(label: string, index: number): string {
  const slug = label.trim().toLowerCase().replace(/\s+/g, "-") || "item";
  return `asset-${slug}-${index}`;
}

export function mapAssetStructureToHomeAssetBars(
  payload: AssetStructurePayload | null | undefined,
  reportDate: string,
  topN = DEFAULT_TOP_N,
): { bars: readonly HomeAssetBar[]; hasData: boolean } {
  if (!payload || payload.report_date !== reportDate || payload.items.length === 0) {
    return { bars: [], hasData: false };
  }

  const sorted = [...payload.items].sort(
    (left, right) => nativeToNumber(right.total_market_value) - nativeToNumber(left.total_market_value),
  );

  const head = sorted.slice(0, topN);
  const tail = sorted.slice(topN);
  const rows =
    tail.length > 0
      ? [
          ...head,
          {
            category: "其他",
            total_market_value: {
              raw: tail.reduce((sum, item) => sum + nativeToNumber(item.total_market_value), 0),
              unit: "yuan" as const,
              display: "",
              precision: 2,
              sign_aware: false,
            },
            bond_count: tail.reduce((sum, item) => sum + item.bond_count, 0),
            percentage: {
              raw: tail.reduce((sum, item) => sum + pctFromNumeric(item.percentage), 0) / 100,
              unit: "pct" as const,
              display: "",
              precision: 2,
              sign_aware: false,
            },
          },
        ]
      : head;

  const bars: HomeAssetBar[] = rows.map((item, index) => ({
    id: slugId(item.category, index),
    label: item.category?.trim() || "—",
    pct: Number(pctFromNumeric(item.percentage).toFixed(2)),
    value: formatYi(item.total_market_value),
    fillClass: FILL_CLASSES[index % FILL_CLASSES.length]!,
  }));

  return { bars, hasData: bars.length > 0 };
}
