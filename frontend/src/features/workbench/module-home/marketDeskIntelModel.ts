import type { MacroToolkitAnalysisPayload } from "../../../api/macroToolkitClient";

export type ModuleHomeTone = "ok" | "watch" | "error" | "muted";

export type MarketCrisisExplainComponent = {
  key: string;
  label: string;
  zScore: number | null;
  weight: number | null;
  rawValue: number | null;
};

export type MarketCrisisHistoryPoint = {
  date: string;
  crisisScore: number;
  percentile: number | null;
};

export type MarketDeskIndicatorHighlight = {
  key: string;
  label: string;
  value: string;
  group: string;
  tone: ModuleHomeTone;
};

export type MarketDeskIntelView = {
  curveShape: string | null;
  curveShapeLabel: string | null;
  curveInterpretation: string | null;
  spread10y1yBp: number | null;
  curvePercentile1y: number | null;
  indicators: MarketDeskIndicatorHighlight[];
};

export type MarketCrisisExplainView = {
  crisisScore: number | null;
  regime: string | null;
  percentile: number | null;
  headline: string | null;
  recommendation: string | null;
  dataStatus: string | null;
  availableComponentCount: number | null;
  componentCount: number | null;
  scoreDelta: number | null;
  percentileDelta: number | null;
  components: MarketCrisisExplainComponent[];
  scoreHistory: MarketCrisisHistoryPoint[];
  warnings: string[];
  tone: ModuleHomeTone;
};

const MARKET_CURVE_SHAPE_LABELS: Record<string, string> = {
  Inverted: "倒挂",
  Flat: "平坦",
  Hump: "驼峰",
  ModerateSteep: "中度陡峭",
  NormalSteep: "偏陡",
  Unavailable: "不可用",
};

const MARKET_DESK_INTEL_INDICATOR_LIMIT = 6;

export function macroToolkitModuleTone(tone: string): ModuleHomeTone {
  if (tone === "positive" || tone === "complete") {
    return "ok";
  }
  if (tone === "negative" || tone === "unavailable") {
    return "error";
  }
  if (tone === "degraded" || tone === "neutral") {
    return "watch";
  }
  return "muted";
}

function crisisHistoryDelta(history: MarketCrisisHistoryPoint[]): {
  scoreDelta: number | null;
  percentileDelta: number | null;
} {
  if (history.length < 2) {
    return { scoreDelta: null, percentileDelta: null };
  }
  const first = history[0];
  const last = history[history.length - 1];
  const scoreDelta =
    first && last && Number.isFinite(first.crisisScore) && Number.isFinite(last.crisisScore)
      ? Number((last.crisisScore - first.crisisScore).toFixed(4))
      : null;
  const percentileDelta =
    first?.percentile !== null &&
    first?.percentile !== undefined &&
    last?.percentile !== null &&
    last?.percentile !== undefined
      ? Number((last.percentile - first.percentile).toFixed(2))
      : null;
  return { scoreDelta, percentileDelta };
}

function readCrisisResultNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readCrisisResultString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function buildMarketDeskIntel(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MarketDeskIntelView | null {
  if (!analysis) {
    return null;
  }

  const curveCapability = analysis.capability_results.find((item) => item.key === "yield_curve_shape");
  const curveResult = curveCapability?.result ?? {};
  const curveShape = readCrisisResultString(curveResult.shape);
  const spreads =
    curveResult.spreads && typeof curveResult.spreads === "object"
      ? (curveResult.spreads as Record<string, unknown>)
      : {};
  const spread10y1yRaw = spreads["10Y-1Y"];
  const spread10y1yBp =
    typeof spread10y1yRaw === "number"
      ? spread10y1yRaw
      : typeof spread10y1yRaw === "string"
        ? readCrisisResultNumber(Number.parseFloat(spread10y1yRaw))
        : readCrisisResultNumber(spread10y1yRaw);

  const indicators = analysis.indicators
    .filter((indicator) => indicator.latest_value !== null && indicator.latest_value !== undefined)
    .slice(0, MARKET_DESK_INTEL_INDICATOR_LIMIT)
    .map((indicator) => {
      const changeText =
        indicator.change_pct !== null && indicator.change_pct !== undefined
          ? ` · ${indicator.change_pct >= 0 ? "+" : ""}${indicator.change_pct.toFixed(2)}%`
          : "";
      return {
        key: indicator.key,
        label: indicator.label,
        value: `${indicator.latest_value}${indicator.unit ?? ""}${changeText}`,
        group: indicator.group,
        tone: (indicator.quality === "ok" ? "ok" : "watch") as ModuleHomeTone,
      };
    });

  if (!curveShape && indicators.length === 0) {
    return null;
  }

  return {
    curveShape,
    curveShapeLabel: curveShape ? MARKET_CURVE_SHAPE_LABELS[curveShape] ?? curveShape : null,
    curveInterpretation: readCrisisResultString(curveResult.interpretation),
    spread10y1yBp,
    curvePercentile1y: readCrisisResultNumber(curveResult.percentile_1y),
    indicators,
  };
}

function readMarketCrisisScoreHistory(raw: unknown): MarketCrisisHistoryPoint[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const point = item as Record<string, unknown>;
      const crisisScore = readCrisisResultNumber(point.crisis_score);
      const date = readCrisisResultString(point.date);
      if (crisisScore === null || !date) {
        return null;
      }
      return {
        date,
        crisisScore,
        percentile: readCrisisResultNumber(point.percentile),
      };
    })
    .filter((item): item is MarketCrisisHistoryPoint => Boolean(item));
}

export function buildMarketCrisisExplain(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MarketCrisisExplainView | null {
  if (!analysis) {
    return null;
  }
  const capability = analysis.capability_results.find((item) => item.key === "crisis_score_cn");
  if (!capability) {
    return null;
  }
  const result = capability.result ?? {};
  const rawComponents = Array.isArray(result.components) ? result.components : [];
  const components: MarketCrisisExplainComponent[] = rawComponents
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const component = item as Record<string, unknown>;
      const key = readCrisisResultString(component.key) ?? "";
      if (!key) {
        return null;
      }
      return {
        key,
        label: readCrisisResultString(component.label) ?? key,
        zScore: readCrisisResultNumber(component.z_score),
        weight: readCrisisResultNumber(component.weight),
        rawValue: readCrisisResultNumber(component.raw_value),
      };
    })
    .filter((item): item is MarketCrisisExplainComponent => Boolean(item));
  const warnings = Array.isArray(result.warnings)
    ? result.warnings.map((item) => String(item).trim()).filter(Boolean)
    : capability.warnings ?? [];
  const scoreHistory = readMarketCrisisScoreHistory(result.score_history);
  const { scoreDelta, percentileDelta } = crisisHistoryDelta(scoreHistory);

  return {
    crisisScore: readCrisisResultNumber(result.crisis_score) ?? capability.score,
    regime: readCrisisResultString(result.regime),
    percentile: readCrisisResultNumber(result.percentile),
    headline: readCrisisResultString(result.headline) ?? capability.headline ?? null,
    recommendation: readCrisisResultString(result.recommendation),
    dataStatus: readCrisisResultString(result.data_status) ?? capability.status,
    availableComponentCount: readCrisisResultNumber(result.available_component_count),
    componentCount: readCrisisResultNumber(result.component_count),
    scoreDelta,
    percentileDelta,
    components,
    scoreHistory,
    warnings,
    tone: macroToolkitModuleTone(capability.status),
  };
}
