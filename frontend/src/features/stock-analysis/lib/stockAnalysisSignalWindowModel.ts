import type {
  LivermoreCandidateHistoryHorizonStats,
  LivermoreStrategyScorePayload,
  LivermoreStrategyScoreRow,
} from "../../../api/contracts";
import type { StockCandidateSourcePool } from "./stockAnalysisPageModel";

/**
 * 候选卡「信号窗口」披露（strategy-score 透传）。
 *
 * 只做取数与格式化，不重算任何统计；后端未返回该来源池/市场状态的统计行时
 * 整块为 null，页面不渲染。
 *
 * 存在的理由：各池的前瞻形态一致为「T+5 为正、T+20 中位数转负」，
 * 信号本质是短窗口交易信号；页面按"选股"呈现会诱导按选股周期持有，
 * 恰好吃满窗口后的均值回归。这里把有效窗口显式写在候选卡上。
 */
export type StockCandidateSignalWindow = {
  /** strategy-score 里的 signal_kind（用于回查后端统计行）。 */
  signalKind: string;
  /** 统计对应的市场状态；与当前门控状态一致时才有参考意义。 */
  marketState: string;
  /** 主观察窗口标签，恒为 T+5（后端 primary_horizon）。 */
  horizonLabel: string;
  sampleLabel: string;
  winRateLabel: string;
  medianLabel: string;
  /** T+20 中位数标签；后端未返回 T+20 统计时为 null。 */
  longHorizonLabel: string | null;
  /** 固定观察窗口文案，随 T+20 是否转负变化。 */
  guidance: string;
  tone: "positive" | "warning" | "neutral";
};

export type StockCandidateSignalWindowFields = {
  /** 信号窗口披露；后端缺该来源池统计时为 undefined/null，不渲染。 */
  signalWindow?: StockCandidateSignalWindow | null;
};

const PRIMARY_HORIZON = "return_5d";
const LONG_HORIZON = "return_20d";

/** 来源池键 -> strategy-score 的 signal_kind（后端为单数命名，且与池 key 不完全一致）。 */
const SIGNAL_KIND_BY_SOURCE_POOL: Record<StockCandidateSourcePool, string | null> = {
  theme_breakout: "theme_breakout",
  hybrid_fusion: "hybrid_fusion",
  stock_candidates: "stock_candidate",
  fresh_trend_watchlist: "fresh_trend_watchlist",
  factor_screen_candidates: "factor_screen",
  uptrend_momentum_candidates: "uptrend_momentum",
  mean_reversion_candidates: "mean_reversion",
  // 后端首屏队列不区分来源池统计，无法回查对应统计行。
  workbench_review_queue: null,
};

function finiteNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatSignedPercent(value: number | null): string | null {
  if (value == null) return null;
  const pct = value * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatWinRate(value: number | null): string | null {
  return value == null ? null : `${(value * 100).toFixed(1)}%`;
}

function horizonStats(
  row: LivermoreStrategyScoreRow,
  horizon: string,
): LivermoreCandidateHistoryHorizonStats | null {
  const stats = (row.stats as Record<string, LivermoreCandidateHistoryHorizonStats> | undefined)?.[horizon];
  return stats ?? null;
}

/**
 * 取该来源池在当前市场状态下的统计行。
 * 优先 current_market_state_rows（后端已按当前门控筛过），否则回退整表按 market_state 匹配。
 */
function findScoreRow(
  score: LivermoreStrategyScorePayload | null | undefined,
  signalKind: string,
): LivermoreStrategyScoreRow | null {
  if (!score) return null;
  const currentRow = (score.current_market_state_rows ?? []).find((row) => row.signal_kind === signalKind);
  if (currentRow) return currentRow;
  const currentState = score.current_market_state?.trim();
  if (!currentState) return null;
  return (
    (score.rows ?? []).find(
      (row) => row.signal_kind === signalKind && row.market_state === currentState,
    ) ?? null
  );
}

/**
 * 构建单个来源池的信号窗口披露；T+5 统计缺失或无可用样本时返回 null（不渲染半块）。
 */
export function buildCandidateSignalWindow(
  score: LivermoreStrategyScorePayload | null | undefined,
  sourcePool: StockCandidateSourcePool,
): StockCandidateSignalWindow | null {
  const signalKind = SIGNAL_KIND_BY_SOURCE_POOL[sourcePool];
  if (!signalKind) return null;
  const row = findScoreRow(score, signalKind);
  if (!row) return null;

  const primary = horizonStats(row, PRIMARY_HORIZON);
  if (!primary) return null;
  const availableCount = finiteNumber(primary.available_count) ?? 0;
  if (availableCount <= 0) return null;

  const winRate = finiteNumber(primary.win_rate);
  const medianReturn = finiteNumber(primary.median_return);
  const winRateLabel = formatWinRate(winRate);
  const medianLabel = formatSignedPercent(medianReturn);
  if (winRateLabel == null && medianLabel == null) return null;

  const longStats = horizonStats(row, LONG_HORIZON);
  const longMedian = longStats ? finiteNumber(longStats.median_return) : null;
  const longHorizonLabel = longMedian == null ? null : `T+20 中位 ${formatSignedPercent(longMedian)}`;

  // T+20 中位为负 = 拿过窗口反而亏；这是各池共同形态，必须显式说明不作持有依据。
  const longHorizonNegative = longMedian != null && longMedian < 0;
  const guidance = longHorizonNegative
    ? "建议观察窗口 T+5；该池历史 T+20 中位为负，不作持有依据。"
    : "建议观察窗口 T+5；超过该窗口的持有需另行验证。";
  const tone: StockCandidateSignalWindow["tone"] = longHorizonNegative
    ? "warning"
    : winRate != null && winRate >= 0.5
      ? "positive"
      : "neutral";

  return {
    signalKind,
    marketState: row.market_state,
    horizonLabel: "T+5",
    sampleLabel: `样本 ${availableCount}`,
    winRateLabel: winRateLabel == null ? "T+5 胜率待补" : `T+5 胜率 ${winRateLabel}`,
    medianLabel: medianLabel == null ? "T+5 中位待补" : `T+5 中位 ${medianLabel}`,
    longHorizonLabel,
    guidance,
    tone,
  };
}

/**
 * 给候选队列注入信号窗口字段。队列内所有候选同属一个来源池（择池后统一），
 * 因此按条目自身的 sourcePool 回查即可；无统计时保持字段缺失。
 */
export function attachCandidateSignalWindow<
  T extends { sourcePool: StockCandidateSourcePool },
>(queue: T[], score: LivermoreStrategyScorePayload | null | undefined): T[] {
  if (!score || queue.length === 0) return queue;
  const windowByPool = new Map<StockCandidateSourcePool, StockCandidateSignalWindow | null>();
  return queue.map((item) => {
    if (!windowByPool.has(item.sourcePool)) {
      windowByPool.set(item.sourcePool, buildCandidateSignalWindow(score, item.sourcePool));
    }
    const signalWindow = windowByPool.get(item.sourcePool) ?? null;
    return signalWindow ? { ...item, signalWindow } : item;
  });
}
