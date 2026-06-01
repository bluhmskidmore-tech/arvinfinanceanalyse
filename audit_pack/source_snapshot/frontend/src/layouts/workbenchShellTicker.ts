import type { ChoiceMacroLatestPoint } from "../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../utils/choiceMacroFormat";

type ShellTickerTone = "up" | "down";

export type ShellTickerItem = {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: ShellTickerTone;
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

function formatShellTickerValue(point: ChoiceMacroLatestPoint) {
  return formatChoiceMacroValue(point, { spaceBeforeUnit: false });
}

function formatShellTickerDelta(point: ChoiceMacroLatestPoint) {
  return formatChoiceMacroDelta(point, { spaceBeforeUnit: false });
}

export function buildShellTickerItems(
  series: ChoiceMacroLatestPoint[],
  keys: ShellTickerKey[] = shellTickerDisplayKeys,
): ShellTickerItem[] {
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
      delta: formatShellTickerDelta(point),
      tone: point.latest_change != null && point.latest_change < 0 ? "down" : "up",
    });
  }

  return resolved.length > 0 ? resolved : fallbackShellTickerItems;
}
