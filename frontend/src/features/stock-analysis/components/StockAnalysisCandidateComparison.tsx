import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import "./StockAnalysisCandidateComparison.css";

type StockAnalysisCandidateComparisonProps = {
  candidates: StockCandidateReviewQueueItem[];
  usesHybridFusion: boolean;
  asOfLabel?: string | null;
  visibleCount?: number;
  onReviewCandidate: (card: StockCandidateReviewQueueItem) => void;
};

type CandidateDecision = {
  label: "优先复核" | "等待确认" | "降级观察";
  tone: "positive" | "warning" | "neutral";
  reason: "首位候选" | "边界待核实" | "证据不足" | "融合待确认" | "排队复核";
};

type CandidateCardMeta = {
  boundaries: string[];
  boundaryCount: number;
  boundaryLabel: string;
  boundaryDetail: string;
  criteria: CandidateCriterion[];
  decision: CandidateDecision;
  evidenceCount: number;
  priorityReason: string;
  scoreSummary: string | null;
};

type CandidateCriterion = {
  label: string;
  value: string;
  tone: "positive" | "warning" | "neutral";
};

const DEFAULT_ALTERNATE_PREVIEW_COUNT = 0;

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function compactText(value: string | null | undefined, max = 28, fallback = "待补"): string {
  const normalized = normalizeText(value);
  if (!normalized) return fallback;
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
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
  if (pieces.length < 2 && distanceToBreakout && !["-", "—"].includes(distanceToBreakout)) {
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

function candidateCriterionTone(label: string): CandidateCriterion["tone"] {
  if (label === "高" || label === "重点复核" || label === "待复核") return "positive";
  if (label === "低" || label === "降权观察" || label === "待补" || label === "待确认") return "warning";
  return "neutral";
}

function buildCandidateCriteria({
  card,
  usesHybridFusion,
  asOfLabel,
}: {
  card: StockCandidateReviewQueueItem;
  usesHybridFusion: boolean;
  asOfLabel?: string | null;
}): CandidateCriterion[] {
  const rankingBasis = usesHybridFusion ? "融合排序" : card.pattern ? compactText(card.pattern, 8) : "候选排序";
  const baseCriteria: CandidateCriterion[] = [
    {
      label: "数据日",
      value: compactText(asOfLabel, 12, "待确认"),
      tone: asOfLabel ? "neutral" : "warning",
    },
    {
      label: "口径",
      value: rankingBasis,
      tone: usesHybridFusion || card.pattern ? "neutral" : "warning",
    },
  ];

  if (!usesHybridFusion) {
    return baseCriteria;
  }

  const confidence = confidenceDisplayLabel(rawFieldValue(card, "confidence"));
  const action = fusionActionDisplayLabel(rawFieldValue(card, "fusion_action"));

  return [
    ...baseCriteria,
    {
      label: "置信度",
      value: confidence,
      tone: candidateCriterionTone(confidence),
    },
    {
      label: "动作",
      value: action,
      tone: candidateCriterionTone(action),
    },
  ];
}

function candidateDecision(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  index: number,
  boundaryCount: number,
): CandidateDecision {
  const evidenceCount = candidateEvidenceCount(card);
  if (evidenceCount < 3) return { label: "降级观察", tone: "warning", reason: "证据不足" };
  if (index === 0) return { label: "优先复核", tone: "positive", reason: "首位候选" };
  if (boundaryCount > 0) return { label: "等待确认", tone: "warning", reason: "边界待核实" };
  if (usesHybridFusion) return { label: "等待确认", tone: "neutral", reason: "融合待确认" };
  return { label: "等待确认", tone: "neutral", reason: "排队复核" };
}

function buildCandidateCardMeta(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  index: number,
  asOfLabel?: string | null,
): CandidateCardMeta {
  const boundaries = meaningfulBoundaryEvidence(card);
  const boundaryCount = boundaries.length;
  const evidenceCount = candidateEvidenceCount(card);

  return {
    boundaries,
    boundaryCount,
    boundaryLabel: boundaryCount > 0 ? `待核 ${boundaryCount} 条` : "清晰",
    boundaryDetail: boundaries[0] ?? "新闻/公告事件仍在详情中复核",
    criteria: buildCandidateCriteria({ card, usesHybridFusion, asOfLabel }),
    decision: candidateDecision(card, usesHybridFusion, index, boundaryCount),
    evidenceCount,
    priorityReason: candidatePriorityReason(card, boundaryCount),
    scoreSummary: usesHybridFusion ? candidateScoreSummary(card) : null,
  };
}

export function StockAnalysisCandidateComparison({
  candidates,
  usesHybridFusion,
  asOfLabel,
  visibleCount = 5,
  onReviewCandidate,
}: StockAnalysisCandidateComparisonProps) {
  const visibleCandidates = candidates.slice(0, visibleCount);

  if (visibleCandidates.length === 0) return null;

  const [leadCandidate, ...alternateCandidates] = visibleCandidates;
  const leadMeta = buildCandidateCardMeta(leadCandidate, usesHybridFusion, 0, asOfLabel);
  const visibleAlternateCandidates = alternateCandidates.slice(0, DEFAULT_ALTERNATE_PREVIEW_COUNT);
  const deferredAlternateCandidates = alternateCandidates.slice(DEFAULT_ALTERNATE_PREVIEW_COUNT);

  const renderAlternateCard = (card: StockCandidateReviewQueueItem, index: number) => {
    const meta = buildCandidateCardMeta(card, usesHybridFusion, index + 1, asOfLabel);
    const alternateCriteria = usesHybridFusion ? meta.criteria.slice(1) : [];

    return (
      <article
        key={card.stockCode}
        className="stock-analysis-page__candidate-alternate-card"
        data-testid={`stock-comparison-candidate-row-${card.stockCode}`}
        data-tone={meta.decision.tone}
      >
        <div className="stock-analysis-page__candidate-alternate-head">
          <span
            className={`stock-analysis-page__candidate-comparison-decision stock-analysis-page__candidate-comparison-decision--${meta.decision.tone}`}
          >
            {meta.decision.label}
          </span>
          <small>#{card.rank} · {meta.decision.reason}</small>
        </div>
        <strong>{card.stockName}</strong>
        <small className="stock-analysis-page__tabular">{card.stockCode}</small>
        <dl>
          <div>
            <dt>观察</dt>
            <dd className="stock-analysis-page__tabular">{card.distanceToBreakoutPct}</dd>
          </div>
          <div>
            <dt>证据</dt>
            <dd>{meta.evidenceCount} 条</dd>
          </div>
          <div>
            <dt>边界</dt>
            <dd title={meta.boundaryDetail}>{meta.boundaryLabel}</dd>
          </div>
        </dl>
        <p
          className="stock-analysis-page__candidate-priority-reason"
          title={`优先理由：${meta.priorityReason}`}
        >
          优先理由：{compactText(meta.priorityReason, 44)}
        </p>
        {alternateCriteria.length > 0 ? (
          <dl
            className="stock-analysis-page__candidate-criteria stock-analysis-page__candidate-criteria--compact"
            data-testid={`stock-candidate-criteria-${card.stockCode}`}
            aria-label={`${card.stockName} 选股口径校验`}
          >
            {alternateCriteria.map((criterion) => (
              <div key={criterion.label} data-tone={criterion.tone}>
                <dt>{criterion.label}</dt>
                <dd className="stock-analysis-page__tabular" title={criterion.value}>
                  {criterion.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
        <button
          type="button"
          className={`stock-analysis-page__candidate-comparison-action stock-analysis-page__candidate-comparison-action--${meta.decision.tone}`}
          data-testid={`stock-comparison-candidate-review-${card.stockCode}`}
          data-tone={meta.decision.tone}
          onClick={() => onReviewCandidate(card)}
        >
          复核
        </button>
      </article>
    );
  };

  return (
    <section
      className="stock-analysis-page__candidate-comparison"
      data-testid="stock-analysis-candidate-comparison"
      aria-label="候选横向比较"
    >
      <header className="stock-analysis-page__candidate-comparison-head">
        <div>
          <strong>候选横向比较</strong>
          <span>先做取舍，再看单只详情</span>
        </div>
        <span
          className="stock-analysis-page__candidate-comparison-rules"
          data-testid="stock-analysis-candidate-comparison-rules"
        >
          口径：首位优先；边界/事件待核实先等待；证据不足降级观察
        </span>
      </header>
      <div className="stock-analysis-page__candidate-decision-board">
        <article
          className="stock-analysis-page__candidate-lead-card"
          data-testid={`stock-comparison-candidate-row-${leadCandidate.stockCode}`}
          data-tone={leadMeta.decision.tone}
        >
          <div className="stock-analysis-page__candidate-lead-rank">
            <span>首选</span>
            <strong>#{leadCandidate.rank}</strong>
          </div>
          <div className="stock-analysis-page__candidate-lead-main">
            <span
              className={`stock-analysis-page__candidate-comparison-decision stock-analysis-page__candidate-comparison-decision--${leadMeta.decision.tone}`}
            >
              {leadMeta.decision.label} · {leadMeta.decision.reason}
            </span>
            <h3>
              {leadCandidate.stockName}
              <small className="stock-analysis-page__tabular">{leadCandidate.stockCode}</small>
            </h3>
            <p
              className="stock-analysis-page__candidate-priority-reason"
              title={`优先理由：${leadMeta.priorityReason}`}
            >
              优先理由：{compactText(leadMeta.priorityReason, 70)}
            </p>
            <dl className="stock-analysis-page__candidate-lead-metrics">
              <div>
                <dt>观察位</dt>
                <dd className="stock-analysis-page__tabular">{leadCandidate.distanceToBreakoutPct}</dd>
              </div>
              <div>
                <dt>证据</dt>
                <dd className="stock-analysis-page__tabular">{leadMeta.evidenceCount} 条</dd>
              </div>
              <div>
                <dt>边界</dt>
                <dd>{leadMeta.boundaryLabel}</dd>
              </div>
            </dl>
            <dl
              className="stock-analysis-page__candidate-criteria"
              data-testid={`stock-candidate-criteria-${leadCandidate.stockCode}`}
              aria-label={`${leadCandidate.stockName} 选股口径校验`}
            >
              {leadMeta.criteria.map((criterion) => (
                <div key={criterion.label} data-tone={criterion.tone}>
                  <dt>{criterion.label}</dt>
                  <dd className="stock-analysis-page__tabular" title={criterion.value}>
                    {criterion.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <div
            className="stock-analysis-page__candidate-lead-evidence"
            data-has-score={leadMeta.scoreSummary ? "true" : "false"}
          >
            {leadMeta.scoreSummary ? <span title={leadMeta.scoreSummary}>{leadMeta.scoreSummary}</span> : null}
            <small title={leadCandidate.invalidationFocus}>
              失效：{compactText(leadCandidate.invalidationFocus, 30)}
            </small>
            <button
              type="button"
              className={`stock-analysis-page__candidate-comparison-action stock-analysis-page__candidate-comparison-action--${leadMeta.decision.tone}`}
              data-testid={`stock-comparison-candidate-review-${leadCandidate.stockCode}`}
              data-tone={leadMeta.decision.tone}
              onClick={() => onReviewCandidate(leadCandidate)}
            >
              复核
            </button>
          </div>
        </article>

        {alternateCandidates.length > 0 ? (
          <div className="stock-analysis-page__candidate-alternates" data-testid="stock-analysis-candidate-alternates">
            {visibleAlternateCandidates.map((card, index) => renderAlternateCard(card, index))}
            {deferredAlternateCandidates.length > 0 ? (
              <details
                className="stock-analysis-page__candidate-more-alternates"
                data-testid="stock-analysis-candidate-more-alternates"
              >
                <summary className="stock-analysis-page__candidate-more-alternates-summary">
                  <span>更多备选</span>
                  <small>余 {deferredAlternateCandidates.length} 只</small>
                </summary>
                <div className="stock-analysis-page__candidate-more-alternates-grid">
                  {deferredAlternateCandidates.map((card, index) =>
                    renderAlternateCard(card, index + DEFAULT_ALTERNATE_PREVIEW_COUNT),
                  )}
                </div>
              </details>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
