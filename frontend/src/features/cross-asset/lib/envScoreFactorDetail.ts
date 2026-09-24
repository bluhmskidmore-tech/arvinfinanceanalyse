import type { MacroBondLinkageEnvironmentScore } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

/**
 * 环境评分贡献因子明细行（GET /api/macro-bond-linkage/analysis
 * result.environment_score.contributing_factors[] 的展示模型）。
 */
export type EnvFactorTone = "pos" | "neg" | "neu";

export type EnvFactorDetailRow = {
  category: string;
  categoryLabel: string;
  seriesName: string;
  windowLabel: string;
  delta: number | null;
  deltaLabel: string;
  score: number | null;
  scoreLabel: string;
  weight: number | null;
  observationCount: number | null;
  tone: EnvFactorTone;
};

export type EnvFactorDetailScoreInput = Partial<Pick<MacroBondLinkageEnvironmentScore, "contributing_factors">>;

const CATEGORY_LABELS: Record<string, string> = {
  rate: "利率",
  liquidity: "流动性",
  growth: "增长",
  inflation: "通胀",
};

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function signedFixed(value: number, digits: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

/** Δ 展示：常规值带符号保留 4 位小数；|delta|>=1e4 用万紧凑、>=1e8 用亿紧凑。 */
function formatDeltaLabel(delta: number | null): string {
  if (delta == null) {
    return EM_DASH;
  }
  const abs = Math.abs(delta);
  if (abs >= 1e8) {
    const sign = delta > 0 ? "+" : "-";
    return `${sign}${(abs / 1e8).toFixed(1)}亿`;
  }
  if (abs >= 1e4) {
    const sign = delta > 0 ? "+" : "-";
    return `${sign}${(abs / 1e4).toFixed(1)}万`;
  }
  return signedFixed(delta, 4);
}

function formatScoreLabel(score: number | null): string {
  if (score == null) {
    return EM_DASH;
  }
  return signedFixed(score, 3);
}

function scoreTone(score: number | null): EnvFactorTone {
  if (score == null || score === 0) {
    return "neu";
  }
  return score > 0 ? "pos" : "neg";
}

function monthDay(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const matched = value.match(/^\d{4}-(\d{2})-(\d{2})/);
  return matched ? `${matched[1]}-${matched[2]}` : null;
}

function formatWindowLabel(start: unknown, end: unknown): string {
  const startLabel = monthDay(start);
  const endLabel = monthDay(end);
  if (!startLabel || !endLabel) {
    return "~";
  }
  return `${startLabel}~${endLabel}`;
}

export function buildEnvFactorDetailRows(
  environmentScore: EnvFactorDetailScoreInput | null | undefined,
): EnvFactorDetailRow[] {
  const factors = environmentScore?.contributing_factors;
  if (!Array.isArray(factors) || factors.length === 0) {
    return [];
  }

  return factors.map((factor) => {
    const category = String(factor.category ?? "").trim().toLowerCase();
    const seriesName = String(factor.series_name ?? "").trim() || EM_DASH;
    const delta = toFiniteNumber(factor.delta);
    const score = toFiniteNumber(factor.score);

    return {
      category,
      categoryLabel: CATEGORY_LABELS[category] ?? "其他",
      seriesName,
      windowLabel: formatWindowLabel(factor.window_start, factor.window_end),
      delta,
      deltaLabel: formatDeltaLabel(delta),
      score,
      scoreLabel: formatScoreLabel(score),
      weight: toFiniteNumber(factor.weight),
      observationCount: toFiniteNumber(factor.observation_count),
      tone: scoreTone(score),
    };
  });
}
