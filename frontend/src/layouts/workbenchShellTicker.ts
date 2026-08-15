import type { ChoiceMacroLatestPoint } from "../api/contracts";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
  formatChoiceMacroValueParts,
} from "../utils/choiceMacroFormat";

type ShellTickerTone = "up" | "down" | "neutral";

export type ShellTickerItem = {
  key: string;
  label: string;
  value: string;
  delta: string;
  /** delta 省略的完整变动串（含文本单位，如 CNY/USD）收进 title，不在正文重复。 */
  deltaTitle?: string;
  tone: ShellTickerTone;
};

export type ShellTickerModel = {
  items: ShellTickerItem[];
  /** true 表示行情接口未返回可用序列，items 是演示兜底行情，UI 必须加「演示」标识。 */
  isFallback: boolean;
};

const fallbackShellTickerItems: ShellTickerItem[] = [
  { key: "cgb10y", label: "10年国债", value: "1.94%", delta: "+2bp", tone: "up" },
  { key: "dr007", label: "DR007", value: "1.82%", delta: "-6bp", tone: "down" },
  { key: "omo7d", label: "7天逆回购", value: "1.75%", delta: "+1bp", tone: "up" },
  { key: "usd-cny", label: "美元/人民币", value: "7.21", delta: "+0.02", tone: "up" },
];

const shellTickerSeriesSpecs = [
  {
    key: "cgb10y",
    label: "10年国债",
    matchers: [
      "\u4e2d\u503a\u56fd\u503a\u5230\u671f\u6536\u76ca\u7387:10\u5e74",
      "10\u5e74\u671f\u56fd\u503a\u5230\u671f\u6536\u76ca\u7387",
    ],
  },
  {
    key: "policyBank10y",
    label: "10年国开",
    matchers: ["\u4e2d\u503a\u653f\u7b56\u6027\u91d1\u878d\u503a\u5230\u671f\u6536\u76ca\u7387(\u56fd\u5f00\u884c)10\u5e74"],
  },
  {
    key: "us10y",
    label: "10年美债",
    matchers: [
      "\u7f8e\u56fd10\u5e74\u671f\u56fd\u503a\u6536\u76ca\u7387",
      "\u7f8e\u56fd:\u56fd\u503a\u6536\u76ca\u7387:10\u5e74",
    ],
  },
  {
    key: "cnUs10ySpread",
    label: "中美10年利差",
    matchers: [
      "\u4e2d\u7f8e\u56fd\u503a\u5229\u5dee(10Y)",
      "10Y\u4e2d\u56fd\u56fd\u503a-10Y\u7f8e\u56fd\u56fd\u503a",
    ],
  },
  {
    key: "dr007",
    label: "DR007",
    matchers: ["DR007"],
  },
  {
    key: "omo7d",
    label: "7天逆回购",
    matchers: ["\u516c\u5f00\u5e02\u573a7\u5929\u9006\u56de\u8d2d\u5229\u7387"],
  },
  {
    key: "usd-cny",
    label: "美元/人民币",
    matchers: ["\u5373\u671f\u6c47\u7387:\u7f8e\u5143\u5151\u4eba\u6c11\u5e01", "USD/CNY"],
  },
] as const;

export type ShellTickerKey = (typeof shellTickerSeriesSpecs)[number]["key"];

const shellTickerDisplayKeys: ShellTickerKey[] = [
  "cgb10y",
  "policyBank10y",
  "us10y",
  "cnUs10ySpread",
  "dr007",
  "omo7d",
  "usd-cny",
];

const shellTickerSeriesIdsByKey: Record<ShellTickerKey, string[]> = {
  cgb10y: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
  policyBank10y: ["EMM00166502"],
  us10y: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"],
  cnUs10ySpread: ["CA.CN_US_SPREAD", "EM1"],
  dr007: ["CA.DR007", "M002", "EMM00167613"],
  omo7d: ["M001"],
  "usd-cny": ["CA.USDCNY", "EMM00058124"],
};

const FLAT_DELTA_DISPLAY = "持平";

function formatShellTickerValue(point: ChoiceMacroLatestPoint) {
  return formatChoiceMacroValue(point, { spaceBeforeUnit: false });
}

function isZeroDeltaDisplay(delta: string) {
  const numeric = delta.match(/-?\d+(?:\.\d+)?/);
  return numeric != null && Number.parseFloat(numeric[0]) === 0;
}

function buildShellTickerDelta(
  point: ChoiceMacroLatestPoint,
): Pick<ShellTickerItem, "delta" | "deltaTitle" | "tone"> {
  if (point.latest_change == null) {
    // 无变动信息时显示占位符，不再套用涨跌语义色。
    return { delta: formatChoiceMacroDelta(point, { spaceBeforeUnit: false }), tone: "neutral" };
  }

  // formatChoiceMacroValueParts 仅对文本单位（非 % / bp）返回非空 unit；
  // 该单位已完整出现在数值列，变动值不再重复单位串，完整串收进 title。
  const { unit } = formatChoiceMacroValueParts(point, { spaceBeforeUnit: false });
  const fullDelta = formatChoiceMacroDelta(point, { spaceBeforeUnit: false });
  const delta = unit
    ? formatChoiceMacroDelta({ ...point, unit: "" }, { spaceBeforeUnit: false })
    : fullDelta;

  if (isZeroDeltaDisplay(delta)) {
    // 格式化后为 ±0 的变动归中性，显示「持平」而不是 +0/-0。
    return { delta: FLAT_DELTA_DISPLAY, deltaTitle: fullDelta, tone: "neutral" };
  }

  return {
    delta,
    deltaTitle: unit ? fullDelta : undefined,
    tone: point.latest_change < 0 ? "down" : "up",
  };
}

export function buildShellTickerItems(
  series: ChoiceMacroLatestPoint[],
  keys: ShellTickerKey[] = shellTickerDisplayKeys,
): ShellTickerModel {
  const resolved: ShellTickerItem[] = [];

  for (const spec of shellTickerSeriesSpecs.filter((item) => keys.includes(item.key))) {
    const stableSeriesIds = shellTickerSeriesIdsByKey[spec.key] ?? [];
    const point =
      series.find((candidate) => stableSeriesIds.includes(candidate.series_id)) ??
      series.find((candidate) =>
        spec.matchers.some((matcher) => candidate.series_name.includes(matcher)),
      );

    if (!point) {
      continue;
    }

    resolved.push({
      key: spec.key,
      label: spec.label,
      value: formatShellTickerValue(point),
      ...buildShellTickerDelta(point),
    });
  }

  return resolved.length > 0
    ? { items: resolved, isFallback: false }
    : { items: fallbackShellTickerItems, isFallback: true };
}
