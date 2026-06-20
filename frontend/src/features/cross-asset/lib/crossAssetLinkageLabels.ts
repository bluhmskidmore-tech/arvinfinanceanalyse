const RATE_DIRECTION_LABELS: Record<string, string> = {
  rising: "上行",
  falling: "下行",
  neutral: "中性",
};

export function formatLinkageRateDirection(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (!key) {
    return "不可用";
  }
  return RATE_DIRECTION_LABELS[key] ?? value!.trim();
}

export function formatLinkageEnvironmentScoreDetail(
  label: string,
  score: number | null | undefined,
  missingText = "缺少评分。",
): string {
  if (score == null || Number.isNaN(score)) {
    return missingText;
  }
  return `${label} ${score.toFixed(2)}`;
}

export function formatLinkageCorrelationTarget(
  seriesName: string,
  targetFamily: string,
  targetTenor?: string | null,
): string {
  const target = `${targetFamily}${targetTenor ? ` ${targetTenor}` : ""}`.trim();
  return `${seriesName} → ${target}`;
}

const WATERFALL_FACTOR_CATEGORY_LABEL: Record<string, string> = {
  liquidity: "流动性因子",
  rate: "利率因子",
  growth: "增长因子",
  inflation: "通胀因子",
};

const WATERFALL_FACTOR_NAME_PATTERNS: ReadonlyArray<{ pattern: RegExp; text: string }> = [
  { pattern: /^liquidity proxy$/i, text: "流动性代理" },
  { pattern: /^rate proxy$/i, text: "利率代理" },
  { pattern: /^growth proxy$/i, text: "增长代理" },
  { pattern: /^inflation proxy$/i, text: "通胀代理" },
  { pattern: /^neutral test driver$/i, text: "中性测试驱动" },
];

export function formatWaterfallContributingFactorName(
  seriesName: string | null | undefined,
  category?: string | null,
): string {
  const trimmed = String(seriesName ?? "").trim();
  if (!trimmed) {
    const key = String(category ?? "").trim().toLowerCase();
    return WATERFALL_FACTOR_CATEGORY_LABEL[key] ?? "环境因子";
  }
  const matched = WATERFALL_FACTOR_NAME_PATTERNS.find((entry) => entry.pattern.test(trimmed));
  if (matched) {
    return matched.text;
  }
  const shiborMatch = trimmed.match(/^SHIBOR:(.+)$/i);
  if (shiborMatch) {
    return `Shibor ${shiborMatch[1]}`;
  }
  return trimmed;
}

export function formatWaterfallContributingFactorSummary(
  factors: ReadonlyArray<{ series_name?: string | null; category?: string | null }>,
): string {
  const labels = [
    ...new Set(
      factors
        .map((factor) => formatWaterfallContributingFactorName(factor.series_name, factor.category))
        .filter(Boolean),
    ),
  ];
  return labels.join("、");
}
