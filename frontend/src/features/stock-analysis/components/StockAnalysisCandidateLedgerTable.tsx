import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";

type ReviewTone = "positive" | "neutral" | "warning";

type StockAnalysisCandidateLedgerTableProps = {
  candidates: StockCandidateReviewQueueItem[];
  usesHybridFusion: boolean;
  selectedSectorCode: string | null;
  visibleCount?: number;
  onReviewCandidate: (card: StockCandidateReviewQueueItem) => void;
};

type NarrativeDetail = {
  preview: string;
  title: string;
};

type FusionActionDisplayLabel = "观察" | "重点复核" | "降权观察" | "卫星观察" | "待复核" | "待确认" | "待补";

const CANDIDATE_LEDGER_DETAIL_CLASS =
  "stock-analysis-page__candidate-ledger-detail text-default-500 text-[10px] truncate max-w-[150px] inline-block";

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function compactText(value: string | null | undefined, max = 38, fallback = "待补"): string {
  const normalized = normalizeText(value);
  if (!normalized) return fallback;
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
}

function fullText(value: string | null | undefined, fallback = "待补"): string {
  const normalized = normalizeText(value);
  return normalized || fallback;
}

function displaySectorCode(value: string): string | null {
  const normalized = normalizeText(value);
  if (!normalized) return null;
  if (/^tushare:[a-z0-9_-]+$/i.test(normalized)) return null;
  return normalized;
}

function candidateEvidenceValue(card: StockCandidateReviewQueueItem, key: string, fallback = "待补"): string {
  const value =
    card.rawFields.find((field) => field.key === key)?.value ??
    [...card.primaryEvidence, ...card.supportingEvidence].find((field) => field.key === key)?.value;
  return value?.trim() ? value : fallback;
}

function candidateEvidenceNumber(card: StockCandidateReviewQueueItem, key: string): number | null {
  const value = Number(candidateEvidenceValue(card, key, "NaN"));
  return Number.isFinite(value) ? value : null;
}

function confidenceTone(label: string): ReviewTone {
  const normalized = normalizeText(label).toLowerCase();
  if (normalized === "高" || normalized === "high") return "positive";
  if (normalized === "低" || normalized === "low") return "warning";
  return "neutral";
}

function confidenceDisplayLabel(label: string): string {
  const normalized = normalizeText(label).toLowerCase();
  if (normalized === "低" || normalized === "low") return "低";
  if (normalized === "中" || normalized === "medium") return "中";
  if (normalized === "高" || normalized === "high") return "高";
  if (!normalized) return "待补";
  if (/^[a-z0-9_\- ]+$/i.test(normalized)) return "待确认";
  return compactText(label, 12);
}

function fusionActionDisplayLabel(label: string): FusionActionDisplayLabel {
  const normalized = normalizeText(label).toLowerCase().replace(/[\s-]+/g, "_");
  if (
    normalized === "观察" ||
    normalized === "仅观察" ||
    normalized === "observe" ||
    normalized === "observe_only" ||
    normalized === "monitor" ||
    normalized === "monitor_only" ||
    normalized === "observation_only"
  ) {
    return "观察";
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
    normalized === "待复核" ||
    normalized === "复核" ||
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
  if (!normalized || normalized === "待补" || /^[a-z0-9_]+$/i.test(normalized)) {
    return "待补";
  }
  return "待确认";
}

function narrativeDetail(label: string, value: string | null | undefined, max = 40, fallback = "待补"): NarrativeDetail {
  return {
    preview: `${label}：${compactText(value, max, fallback)}`,
    title: `${label}：${fullText(value, fallback)}`,
  };
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

function boundaryPreview(card: StockCandidateReviewQueueItem): NarrativeDetail {
  const firstBoundary = meaningfulBoundaryEvidence(card)[0];
  const value = firstBoundary ?? (card.boundaryEvidence.length > 0 ? "观察口径" : "边界清洁");
  return narrativeDetail("边界", value, 32);
}

function reviewFocusPreview(card: StockCandidateReviewQueueItem): NarrativeDetail {
  return narrativeDetail("复核焦点", card.reviewFocus, 40);
}

function invalidationPreview(card: StockCandidateReviewQueueItem): NarrativeDetail {
  return narrativeDetail("失效", card.invalidationFocus, 32);
}

function primaryEvidencePreview(card: StockCandidateReviewQueueItem): NarrativeDetail {
  const evidence = card.primaryEvidence[0] ?? card.supportingEvidence[0];
  const value = evidence ? `${evidence.label}：${evidence.value}` : "证据待补";
  return narrativeDetail("证据", value, 34, "证据待补");
}

function supportingEvidencePreview(card: StockCandidateReviewQueueItem): NarrativeDetail {
  const evidence = card.supportingEvidence[0] ?? card.primaryEvidence[1] ?? card.primaryEvidence[0];
  const fallback = card.distanceToBreakoutPct ? `观察：${card.distanceToBreakoutPct}` : "支持待补";
  const value = evidence ? `${evidence.label}：${evidence.value}` : fallback;
  return narrativeDetail("支持", value, 34, "支持待补");
}

function evidenceReasonValue(
  bullet: StockCandidateReviewQueueItem["primaryEvidence"][number],
): string | null {
  const label = normalizeText(bullet.label);
  const value = normalizeText(bullet.value);
  if (!label && !value) return null;
  if (!label) return compactText(value, 24, "");
  if (!value || value.includes(label)) return compactText(value || label, 24, "");
  return `${compactText(label, 8, "")} ${compactText(value, 20, "")}`.trim();
}

function priorityReasonPreview(card: StockCandidateReviewQueueItem, meaningfulBoundaryCount: number): NarrativeDetail {
  const pieces: string[] = [];

  for (const bullet of [...card.primaryEvidence, ...card.supportingEvidence]) {
    const piece = evidenceReasonValue(bullet);
    if (!piece || pieces.includes(piece)) continue;
    pieces.push(piece);
    if (pieces.length >= 2) break;
  }

  if (pieces.length < 2) {
    const distanceToBreakout = normalizeText(card.distanceToBreakoutPct);
    if (distanceToBreakout && !["-", "—"].includes(distanceToBreakout)) {
      pieces.push(`观察位 ${compactText(distanceToBreakout, 14, "")}`);
    }
  }

  if (meaningfulBoundaryCount > 0) {
    pieces.push(`边界 ${meaningfulBoundaryCount} 待核`);
  } else if (pieces.length > 0) {
    pieces.push("边界清洁");
  }

  return narrativeDetail("优先理由", pieces.join(" · "), 58, "等待证据补齐");
}

function reviewStatusDetail(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  fusionActionLabel: FusionActionDisplayLabel,
  statusLabel: string,
  meaningfulBoundaryCount: number,
): string {
  if (!usesHybridFusion) return statusLabel;
  if (meaningfulBoundaryCount > 0) return `${statusLabel} · 边界 ${meaningfulBoundaryCount}`;
  if (fusionActionLabel !== statusLabel) return `${fusionActionLabel} · ${statusLabel}`;
  return fusionActionLabel;
}

function rowStatus(
  card: StockCandidateReviewQueueItem,
  usesHybridFusion: boolean,
  fusionActionLabel: FusionActionDisplayLabel,
  meaningfulBoundaryCount: number,
): { label: string; tone: ReviewTone } {
  if (meaningfulBoundaryCount > 0) return { label: "待复核", tone: "warning" };
  if (usesHybridFusion) {
    if (fusionActionLabel === "观察") return { label: "观察", tone: "neutral" };
    if (fusionActionLabel === "重点复核") return { label: "待复核", tone: "positive" };
    if (fusionActionLabel === "降权观察") return { label: "降权观察", tone: "warning" };
    if (fusionActionLabel === "卫星观察") return { label: "观察", tone: "neutral" };
    if (fusionActionLabel === "待确认") return { label: "待确认", tone: "warning" };
    if (fusionActionLabel === "待补") return { label: "待补", tone: "warning" };
    return { label: "待复核", tone: "warning" };
  }
  const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
  if (evidenceCount >= 3) return { label: "可复核", tone: "positive" };
  if (evidenceCount > 0) return { label: "证据待补", tone: "warning" };
  return { label: "待补", tone: "neutral" };
}

function ScoreCell({ label, value, max = 0.4 }: { label: string; value: number | null; max?: number }) {
  const pct = value == null ? 0 : Math.max(4, Math.min(100, (value / max) * 100));
  const display = value == null ? "待补" : value.toFixed(6);

  return (
    <span className="flex flex-col gap-0.5 text-xs" data-mobile-label={label}>
      <strong className="tabular-nums font-mono">{display}</strong>
      <span aria-hidden="true">
        <i style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

export function StockAnalysisCandidateLedgerTable({
  candidates,
  usesHybridFusion,
  selectedSectorCode,
  visibleCount = 10,
  onReviewCandidate,
}: StockAnalysisCandidateLedgerTableProps) {
  const visibleCandidates = candidates.slice(0, visibleCount);

  return (
    <div className="overflow-x-auto rounded-lg border border-default-200 mt-4">
      <table
        className="w-full table-auto text-sm text-left whitespace-nowrap [&_th]:px-3 [&_th]:py-2 [&_th]:border-b [&_th]:border-default-200 [&_th]:bg-default-100/50 [&_th]:text-default-600 [&_th]:font-semibold [&_td]:px-3 [&_td]:py-2 [&_td]:border-b [&_td]:border-default-100/50 hover:[&_tbody_tr]:bg-default-50/50 transition-colors"
        data-mode={usesHybridFusion ? "hybrid" : "trend"}
        data-testid="stock-analysis-review-queue-table"
      >
        <thead>
          <tr>
            <th scope="col">排名</th>
            <th scope="col">股票</th>
            <th scope="col">行业</th>
            {usesHybridFusion ? (
              <>
                <th scope="col">Fusion</th>
                <th scope="col">Cycle</th>
                <th scope="col">Lifecourt</th>
                <th scope="col">Confidence</th>
                <th scope="col">Action</th>
              </>
            ) : (
              <>
                <th scope="col">形态</th>
                <th scope="col">距观察</th>
                <th scope="col">证据</th>
                <th scope="col">边界</th>
                <th scope="col">失效</th>
              </>
            )}
            <th scope="col">复核</th>
          </tr>
        </thead>
        <tbody>
          {visibleCandidates.map((card) => {
            const fusionActionLabel = fusionActionDisplayLabel(candidateEvidenceValue(card, "fusion_action"));
            const meaningfulBoundaryCount = meaningfulBoundaryEvidence(card).length;
            const status = rowStatus(card, usesHybridFusion, fusionActionLabel, meaningfulBoundaryCount);
            const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
            const confidenceDisplay = confidenceDisplayLabel(candidateEvidenceValue(card, "confidence"));
            const stockNarrative = reviewFocusPreview(card);
            const sectorNarrative = boundaryPreview(card);
            const evidenceNarrative = primaryEvidencePreview(card);
            const invalidationNarrative = invalidationPreview(card);
            const supportNarrative = supportingEvidencePreview(card);
            const priorityNarrative = priorityReasonPreview(card, meaningfulBoundaryCount);
            const reviewDetail = reviewStatusDetail(
              card,
              usesHybridFusion,
              fusionActionLabel,
              status.label,
              meaningfulBoundaryCount,
            );
            const sectorCodeDisplay = displaySectorCode(card.sectorCode);

            return (
              <tr
                key={card.stockCode}
                className="group"
                data-testid={`stock-candidate-${card.stockCode}`}
                data-selected-sector={
                  selectedSectorCode != null && card.sectorCode === selectedSectorCode ? "true" : undefined
                }
              >
                <td className="text-right">#{card.rank}</td>
                <td>
                  <strong>{card.stockName}</strong>
                  <small className="tabular-nums font-mono">{card.stockCode}</small>
                  <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={stockNarrative.title}>
                    {stockNarrative.preview}
                  </small>
                  <small
                    className={`${CANDIDATE_LEDGER_DETAIL_CLASS} stock-analysis-page__candidate-ledger-priority`}
                    title={priorityNarrative.title}
                  >
                    {priorityNarrative.preview}
                  </small>
                </td>
                <td>
                  <strong>{card.sectorName}</strong>
                  {sectorCodeDisplay ? <small className="tabular-nums font-mono">{sectorCodeDisplay}</small> : null}
                  <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={sectorNarrative.title}>
                    {sectorNarrative.preview}
                  </small>
                </td>
                {usesHybridFusion ? (
                  <>
                    <td data-mobile-label="F">
                      <ScoreCell label="F" value={candidateEvidenceNumber(card, "fusion_score")} />
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={evidenceNarrative.title}>
                        {evidenceNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="C">
                      <ScoreCell label="C" value={candidateEvidenceNumber(card, "cycle_score")} />
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={invalidationNarrative.title}>
                        {invalidationNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="L">
                      <ScoreCell label="L" value={candidateEvidenceNumber(card, "lifecourt_proxy_score")} max={0.2} />
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={supportNarrative.title}>
                        {supportNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="Conf">
                      <span
                        className="px-2 py-0.5 rounded text-[10px] bg-primary/10 text-primary"
                        data-tone={confidenceTone(confidenceDisplay)}
                      >
                        {confidenceDisplay}
                      </span>
                    </td>
                    <td data-mobile-label="Action">
                      <strong>{fusionActionLabel}</strong>
                    </td>
                  </>
                ) : (
                  <>
                    <td data-mobile-label="形态">
                      <strong>{card.pattern}</strong>
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={evidenceNarrative.title}>
                        {evidenceNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="距观察">
                      <strong className="tabular-nums font-mono">{card.distanceToBreakoutPct}</strong>
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={invalidationNarrative.title}>
                        {invalidationNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="证据">
                      <strong>{evidenceCount} 证据</strong>
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={supportNarrative.title}>
                        {supportNarrative.preview}
                      </small>
                    </td>
                    <td data-mobile-label="边界">
                      <span className="font-medium text-xs" data-tone={status.tone}>
                        {meaningfulBoundaryCount > 0 ? `边界 ${meaningfulBoundaryCount}` : "边界清洁"}
                      </span>
                    </td>
                    <td data-mobile-label="失效">
                      <small className={CANDIDATE_LEDGER_DETAIL_CLASS} title={invalidationNarrative.title}>
                        {invalidationNarrative.preview}
                      </small>
                    </td>
                  </>
                )}
                <td>
                  <button
                    type="button"
                    className="text-primary hover:underline cursor-pointer text-sm"
                    data-testid={`stock-candidate-review-chart-${card.stockCode}`}
                    data-tone={status.tone}
                    onClick={() => onReviewCandidate(card)}
                    aria-label={`复核 ${card.stockName} K 线`}
                  >
                    <span className="sr-only">复核 </span>K 线
                  </button>
                  <small title={reviewDetail}>{reviewDetail}</small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
