import { EM_DASH } from "../../../utils/format";
import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import { selectStockCandidateThemeEvidence } from "../lib/stockAnalysisWorkbenchQueueModel";
import "./StockAnalysisCandidateComparison.css";

type StockAnalysisCandidateComparisonProps = {
  candidates: StockCandidateReviewQueueItem[];
  usesHybridFusion: boolean;
  asOfLabel?: string | null;
  canReviewCandidates?: boolean;
  visibleCount?: number;
  onReviewCandidate: (card: StockCandidateReviewQueueItem) => void;
};

type CandidateDecision = {
  label: "优先复核" | "等待确认" | "降级观察" | "阻断";
  tone: "positive" | "warning" | "neutral";
  reason: "首位候选" | "边界待核实" | "证据不足" | "融合待确认" | "排队复核";
};

type CandidateCardMeta = {
  boundaries: string[];
  boundaryCount: number;
  boundaryLabel: string;
  boundaryDetail: string;
  decision: CandidateDecision;
  evidenceCount: number;
  priorityReason: string;
  scoreSummary: string | null;
};

const DEFAULT_VISIBLE_CANDIDATE_COUNT = 10;

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function compactText(value: string | null | undefined, max = 28, fallback = "待补"): string {
  const normalized = normalizeText(value);
  if (!normalized) return fallback;
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
}

function fullText(value: string | null | undefined, fallback = "待补"): string {
  return normalizeText(value) || fallback;
}

const STRUCTURAL_PLACEHOLDERS = new Set(["接口未提供", "待补", "待确认", "待复核", "-", EM_DASH]);

/**
 * DESIGN §6: when a whole column is structurally absent for the active source,
 * rows show a quiet dash and the raw disclosure stays in the cell tooltip
 * instead of repeating "缺 XXX" on every line.
 */
function denseCellText(value: string | null | undefined): string {
  const normalized = normalizeText(value);
  return !normalized || STRUCTURAL_PLACEHOLDERS.has(normalized) ? EM_DASH : normalized;
}

function isGeneratedBoundaryFallback(value: string | undefined): boolean {
  const normalized = normalizeText(value);
  return (
    normalized.startsWith("基本面因子已纳入候选排序") ||
    normalized.startsWith("基本面与估值证据未接入") ||
    normalized.startsWith("生命法庭层仍是观察线索") ||
    normalized.startsWith("代理信号仅作来源线索") ||
    normalized.startsWith("仅作观察与复核") ||
    normalized.startsWith("来源命中：") ||
    normalized.startsWith("过热门控下仅作观察补充")
  );
}

function meaningfulBoundaryEvidence(card: StockCandidateReviewQueueItem): string[] {
  return card.boundaryEvidence.filter((item) => !isGeneratedBoundaryFallback(item));
}

function candidateEvidenceCount(card: StockCandidateReviewQueueItem): number {
  return card.primaryEvidence.length + card.supportingEvidence.length;
}

function candidateThemeEvidenceSummary(card: StockCandidateReviewQueueItem): string | null {
  const evidence = selectStockCandidateThemeEvidence(card);
  return evidence.length > 0 ? evidence.map((item) => item.value).join(" / ") : null;
}

function rawFieldValue(card: StockCandidateReviewQueueItem, key: string): string | null {
  const value = card.rawFields.find((field) => field.key === key)?.value;
  return value?.trim() ? value : null;
}

function candidateScoreSummary(card: StockCandidateReviewQueueItem): string | null {
  const scores = [
    ["Fusion", rawFieldValue(card, "fusion_score")],
    ["Cycle", rawFieldValue(card, "cycle_score")],
    ["Life", rawFieldValue(card, "lifecourt_proxy_score")],
  ]
    .filter(([, value]) => value != null)
    .map(([label, value]) => `${label} ${value}`);

  return scores.length > 0 ? scores.join(" / ") : null;
}

function candidateEvidenceReason(
  bullet: StockCandidateReviewQueueItem["primaryEvidence"][number],
): string | null {
  const label = normalizeText(bullet.label);
  const value = normalizeText(bullet.value);
  if (!label && !value) return null;
  if (!label) return compactText(value, 24, "");
  if (!value) return compactText(label, 14, "");
  if (value.includes(label)) return compactText(value, 24, "");
  return `${compactText(label, 8, "")} ${compactText(value, 20, "")}`.trim();
}

function candidatePriorityReason(card: StockCandidateReviewQueueItem, boundaryCount: number): string {
  const evidencePieces: string[] = [];

  for (const bullet of [...card.primaryEvidence, ...card.supportingEvidence]) {
    const piece = candidateEvidenceReason(bullet);
    if (!piece || evidencePieces.includes(piece)) continue;
    evidencePieces.push(piece);
    if (evidencePieces.length >= 2) break;
  }

  if (evidencePieces.length === 0) {
    return boundaryCount > 0 ? `待核边界 ${boundaryCount} 条` : "等待证据补齐";
  }

  const pieces = evidencePieces.slice(0, 2);
  const distanceToBreakout = normalizeText(card.distanceToBreakoutPct);
  if (pieces.length < 2 && distanceToBreakout && !["-", EM_DASH].includes(distanceToBreakout)) {
    pieces.push(`观察位 ${compactText(distanceToBreakout, 14, "")}`);
  }

  return pieces.slice(0, 2).join(" · ");
}

function confidenceDisplayLabel(value: string | null): string {
  const normalized = normalizeText(value).toLowerCase();
  if (normalized === "高" || normalized === "high") return "高";
  if (normalized === "中" || normalized === "medium") return "中";
  if (normalized === "低" || normalized === "low") return "低";
  if (!normalized || /^[a-z0-9_\- ]+$/i.test(normalized)) return "待补";
  return compactText(value, 10);
}

function fusionActionDisplayLabel(value: string | null): string {
  const normalized = normalizeText(value).toLowerCase().replace(/[\s-]+/g, "_");
  if (
    normalized === "观察" ||
    normalized === "仅观察" ||
    normalized === "observe" ||
    normalized === "observe_only" ||
    normalized === "monitor" ||
    normalized === "monitor_only" ||
    normalized === "observation_only"
  ) {
    return "仅观察";
  }
  if (normalized === "重点复核" || normalized === "core_plus_trading") {
    return "重点复核";
  }
  if (normalized === "降权观察" || normalized === "core_reduce_trading") {
    return "降权观察";
  }
  if (normalized === "卫星观察" || normalized === "satellite_trial") {
    return "卫星观察";
  }
  if (
    normalized === "复核" ||
    normalized === "待复核" ||
    normalized === "review" ||
    normalized === "review_only" ||
    normalized === "manual_review" ||
    normalized === "pending_review"
  ) {
    return "待复核";
  }
  if (normalized === "裁决待确认" || normalized === "decision_pending" || normalized === "pending") {
    return "待确认";
  }
  if (!normalized || normalized === "待补" || /^[a-z0-9_]+$/i.test(normalized)) return "待补";
  return "待确认";
}

function supportedOutputLabel(key: string): string {
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块强弱",
    stock_candidates: "趋势候选",
    uptrend_momentum_candidates: "上升趋势",
    fresh_trend_watchlist: "新趋势观察",
    mean_reversion_candidates: "均值回归",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材突破",
    hybrid_fusion: "融合观察",
    hybrid_fusion_candidates: "融合观察",
    risk_exit: "风险退出",
  };
  return labels[key] ?? "输出待确认";
}

function candidateSourceLabel(card: StockCandidateReviewQueueItem): string {
  const canonicalSource = rawFieldValue(card, "source_module_key");
  if (canonicalSource) return supportedOutputLabel(canonicalSource.trim());
  const rawSource =
    card.rawFields.find((field) => ["source", "source_kind", "strategy", "module"].includes(field.key))?.value ??
    card.rawFields.find((field) => /source|strategy|module/i.test(`${field.key} ${field.label}`))?.value;
  if (rawSource?.trim()) {
    const localizedSource = supportedOutputLabel(rawSource.trim());
    return localizedSource === "输出待确认" ? compactText(rawSource, 18) : localizedSource;
  }
  return "来源待确认";
}

function candidateSourceSignal(sourceLabel: string): { label: string; tone: "positive" | "warning" } {
  const normalized = sourceLabel.toLowerCase();
  if (normalized.includes("hybrid") || normalized.includes("融合")) {
    return { label: "融合池", tone: "warning" };
  }
  if (normalized.includes("factor") || normalized.includes("多因子")) {
    return { label: "因子池", tone: "warning" };
  }
  if (
    normalized.includes("stock_candidates") ||
    normalized.includes("趋势候选") ||
    normalized.includes("fresh_trend") ||
    normalized.includes("新趋势观察") ||
    normalized.includes("uptrend") ||
    normalized.includes("上升趋势")
  ) {
    return { label: "主快照", tone: "positive" };
  }
  return { label: "来源待确认", tone: "warning" };
}

function displaySectorCode(value: string): string | null {
  const normalized = normalizeText(value);
  if (!normalized) return null;
  if (/^tushare:[a-z0-9_-]+$/i.test(normalized)) return null;
  return normalized;
}

function candidateDecision(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  index: number,
  boundaryCount: number,
): CandidateDecision {
  const evidenceCount = candidateEvidenceCount(card);
  if (evidenceCount < 3) return { label: "降级观察", tone: "warning", reason: "证据不足" };
  if (boundaryCount > 0) return { label: "等待确认", tone: "warning", reason: "边界待核实" };
  if (index === 0) return { label: "优先复核", tone: "positive", reason: "首位候选" };
  if (usesHybridFusion) return { label: "等待确认", tone: "neutral", reason: "融合待确认" };
  return { label: "等待确认", tone: "neutral", reason: "排队复核" };
}

function buildCandidateCardMeta(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  index: number,
): CandidateCardMeta {
  const boundaries = meaningfulBoundaryEvidence(card);
  const boundaryCount = boundaries.length;

  return {
    boundaries,
    boundaryCount,
    boundaryLabel: boundaryCount > 0 ? `待核 ${boundaryCount} 条` : "清晰",
    boundaryDetail: boundaries[0] ?? "新闻/公告事件仍在详情中复核",
    decision: candidateDecision(card, usesHybridFusion, index, boundaryCount),
    evidenceCount: candidateEvidenceCount(card),
    priorityReason: candidatePriorityReason(card, boundaryCount),
    scoreSummary: usesHybridFusion ? candidateScoreSummary(card) : null,
  };
}

export function StockAnalysisCandidateComparison({
  candidates,
  usesHybridFusion,
  asOfLabel,
  canReviewCandidates = true,
  visibleCount = DEFAULT_VISIBLE_CANDIDATE_COUNT,
  onReviewCandidate,
}: StockAnalysisCandidateComparisonProps) {
  const visibleCandidates = candidates.slice(0, visibleCount);

  if (visibleCandidates.length === 0) return null;

  return (
    <section
      className="stock-analysis-page__candidate-comparison"
      data-testid="stock-analysis-candidate-comparison"
      aria-label="候选横向比较"
    >
      <div
        className="stock-analysis-page__candidate-comparison-basis"
        data-testid="stock-analysis-candidate-comparison-basis"
      >
        <span className="stock-analysis-page__tabular">数据日 {compactText(asOfLabel, 12, "待确认")}</span>
        <span>口径 {usesHybridFusion ? "融合排序" : "候选排序"}</span>
        <span
          className="stock-analysis-page__candidate-comparison-rules"
          data-testid="stock-analysis-candidate-comparison-rules"
        >
          口径：首位优先；边界/事件待核实先等待；证据不足降级观察
        </span>
      </div>
      <div className="stock-analysis-page__candidate-dense-wrap">
        <table
          className="stock-analysis-page__candidate-dense-table"
          data-testid="stock-analysis-candidate-dense-table"
          data-mode={usesHybridFusion ? "hybrid" : "trend"}
        >
          <thead>
            <tr>
              <th scope="col" className="stock-analysis-page__candidate-dense-num">排名</th>
              <th scope="col">标的</th>
              <th scope="col">行业</th>
              <th scope="col">来源策略</th>
              <th scope="col">{usesHybridFusion ? "动作" : "形态"}</th>
              <th scope="col" className="stock-analysis-page__candidate-dense-num">
                {usesHybridFusion ? "置信度" : "观察位"}
              </th>
              <th scope="col" className="stock-analysis-page__candidate-dense-num">证据</th>
              <th scope="col">边界</th>
              <th scope="col">优先理由</th>
              <th scope="col">决策状态</th>
              <th scope="col">复核</th>
            </tr>
          </thead>
          <tbody>
            {visibleCandidates.map((card, index) => {
              const meta = buildCandidateCardMeta(card, usesHybridFusion, index);
              const decision: CandidateDecision = canReviewCandidates
                ? meta.decision
                : { ...meta.decision, label: "阻断", tone: "warning" };
              const sourceLabel = candidateSourceLabel(card);
              const sourceSignal = candidateSourceSignal(sourceLabel);
              const themeEvidenceSummary = candidateThemeEvidenceSummary(card);
              const sectorCodeDisplay = displaySectorCode(card.sectorCode);
              const priorityTitle = themeEvidenceSummary
                ? `优先理由：${meta.priorityReason} · 题材归属：${themeEvidenceSummary}`
                : `优先理由：${meta.priorityReason}`;

              return (
                <tr
                  key={`${card.stockCode}:${card.rank}:${index}`}
                  data-testid={`stock-comparison-candidate-row-${card.stockCode}`}
                  data-tone={decision.tone}
                  data-lead={index === 0 ? "true" : undefined}
                >
                  <td className="stock-analysis-page__candidate-dense-num stock-analysis-page__tabular">
                    #{card.rank}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="stock-analysis-page__candidate-dense-stock"
                      title={`复核焦点：${fullText(card.reviewFocus)}`}
                      onClick={() => onReviewCandidate(card)}
                    >
                      <span>{card.stockName}</span>
                      <small className="stock-analysis-page__tabular">{card.stockCode}</small>
                    </button>
                    {card.liquidityFloorPass === false ? (
                      <small
                        className="stock-analysis-page__candidate-dense-liquidity"
                        title={card.dailyAmountLabel ?? "低于 2 亿元日成交门槛"}
                      >
                        低流动
                      </small>
                    ) : null}
                  </td>
                  <td
                    className="stock-analysis-page__candidate-dense-muted"
                    title={sectorCodeDisplay ? `${card.sectorName}（${sectorCodeDisplay}）` : card.sectorName}
                  >
                    {card.sectorName}
                  </td>
                  <td
                    className="stock-analysis-page__candidate-dense-source"
                    data-tone={sourceSignal.tone}
                    title={`来源信号：${sourceSignal.label}`}
                  >
                    {sourceLabel}
                  </td>
                  <td
                    className="stock-analysis-page__candidate-dense-muted"
                    title={
                      usesHybridFusion
                        ? (meta.scoreSummary ?? undefined)
                        : `形态：${fullText(card.pattern)}｜${fullText(card.patternNote, "")}`.replace(/｜$/, "")
                    }
                  >
                    {usesHybridFusion
                      ? denseCellText(fusionActionDisplayLabel(rawFieldValue(card, "fusion_action")))
                      : denseCellText(card.pattern)}
                  </td>
                  <td className="stock-analysis-page__candidate-dense-num stock-analysis-page__tabular">
                    {usesHybridFusion
                      ? denseCellText(confidenceDisplayLabel(rawFieldValue(card, "confidence")))
                      : denseCellText(card.distanceToBreakoutPct)}
                  </td>
                  <td className="stock-analysis-page__candidate-dense-num stock-analysis-page__tabular">
                    {meta.evidenceCount} 条
                  </td>
                  <td
                    className="stock-analysis-page__candidate-dense-boundary"
                    data-tone={meta.boundaryCount > 0 ? "warning" : "neutral"}
                    title={meta.boundaryDetail}
                  >
                    {meta.boundaryLabel}
                  </td>
                  <td className="stock-analysis-page__candidate-dense-reason" title={priorityTitle}>
                    {meta.priorityReason}
                    {themeEvidenceSummary ? (
                      <small data-testid={`stock-comparison-candidate-theme-${card.stockCode}`}>
                        {" 题材归属："}
                        {themeEvidenceSummary}
                      </small>
                    ) : null}
                  </td>
                  <td
                    className="stock-analysis-page__candidate-dense-decision"
                    title={`失效：${fullText(card.invalidationFocus)}`}
                  >
                    <span
                      className={`stock-analysis-page__candidate-comparison-decision stock-analysis-page__candidate-comparison-decision--${decision.tone}`}
                    >
                      {decision.label}
                    </span>
                    <small>{decision.reason}</small>
                  </td>
                  <td className="stock-analysis-page__candidate-dense-action">
                    <button
                      type="button"
                      className={`stock-analysis-page__candidate-comparison-action stock-analysis-page__candidate-comparison-action--${decision.tone}`}
                      data-testid={`stock-comparison-candidate-review-${card.stockCode}`}
                      data-tone={decision.tone}
                      onClick={() => onReviewCandidate(card)}
                    >
                      {canReviewCandidates ? "复核" : "只读"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
