import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";

type ReviewTone = "positive" | "neutral" | "warning";

type StockAnalysisCandidateLedgerTableProps = {
  candidates: StockCandidateReviewQueueItem[];
  usesHybridFusion: boolean;
  selectedSectorCode: string | null;
  visibleCount?: number;
  onReviewCandidate: (card: StockCandidateReviewQueueItem) => void;
};

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
  const normalized = label.trim().toLowerCase();
  if (normalized === "高" || normalized === "high") return "positive";
  if (normalized === "低" || normalized === "low") return "warning";
  return "neutral";
}

function confidenceDisplayLabel(label: string): string {
  if (label === "低") return "low";
  if (label === "中") return "medium";
  if (label === "高") return "high";
  return label;
}

function rowStatus(card: StockCandidateReviewQueueItem, usesHybridFusion: boolean): { label: string; tone: ReviewTone } {
  if (usesHybridFusion) {
    const action = candidateEvidenceValue(card, "fusion_action").toLowerCase();
    if (action === "monitor_only" || action === "观察") return { label: "观察", tone: "neutral" };
    return { label: "待复核", tone: "warning" };
  }
  const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
  if (card.boundaryEvidence.length > 0) return { label: "待复核", tone: "warning" };
  if (evidenceCount >= 3) return { label: "可复核", tone: "positive" };
  if (evidenceCount > 0) return { label: "证据待补", tone: "warning" };
  return { label: "待补", tone: "neutral" };
}

function ScoreCell({ label, value, max = 0.4 }: { label: string; value: number | null; max?: number }) {
  const pct = value == null ? 0 : Math.max(4, Math.min(100, (value / max) * 100));
  const display = value == null ? "待补" : value.toFixed(6);

  return (
    <span className="stock-analysis-page__candidate-score" data-mobile-label={label}>
      <strong className="stock-analysis-page__tabular">{display}</strong>
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
    <div className="stock-analysis-page__review-table-wrap stock-analysis-page__review-table-wrap--ledger">
      <table
        className="stock-analysis-page__table stock-analysis-page__review-queue-table stock-analysis-page__candidate-ledger-table"
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
            const status = rowStatus(card, usesHybridFusion);
            const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
            const primaryEvidencePreview = card.primaryEvidence[0] ?? card.supportingEvidence[0];
            const confidenceLabel = candidateEvidenceValue(card, "confidence");
            const confidenceDisplay = confidenceDisplayLabel(confidenceLabel);

            return (
              <tr
                key={card.stockCode}
                className="stock-analysis-page__review-candidate-card"
                data-testid={`stock-candidate-${card.stockCode}`}
                data-selected-sector={
                  selectedSectorCode != null && card.sectorCode === selectedSectorCode ? "true" : undefined
                }
              >
                <td className="stock-analysis-page__table-number">#{card.rank}</td>
                <td>
                  <strong>{card.stockName}</strong>
                  <small className="stock-analysis-page__tabular">{card.stockCode}</small>
                </td>
                <td>
                  <strong>{card.sectorName}</strong>
                  <small className="stock-analysis-page__tabular">{card.sectorCode}</small>
                </td>
                {usesHybridFusion ? (
                  <>
                    <td data-mobile-label="F">
                      <ScoreCell label="F" value={candidateEvidenceNumber(card, "fusion_score")} />
                    </td>
                    <td data-mobile-label="C">
                      <ScoreCell label="C" value={candidateEvidenceNumber(card, "cycle_score")} />
                    </td>
                    <td data-mobile-label="L">
                      <ScoreCell label="L" value={candidateEvidenceNumber(card, "lifecourt_proxy_score")} max={0.2} />
                    </td>
                    <td data-mobile-label="Conf">
                      <span
                        className="stock-analysis-page__review-confidence-badge"
                        data-tone={confidenceTone(confidenceLabel)}
                      >
                        {confidenceDisplay}
                      </span>
                    </td>
                    <td data-mobile-label="Action">
                      <strong>{candidateEvidenceValue(card, "fusion_action")}</strong>
                    </td>
                  </>
                ) : (
                  <>
                    <td data-mobile-label="形态">
                      <strong>{card.pattern}</strong>
                    </td>
                    <td data-mobile-label="距观察">
                      <strong className="stock-analysis-page__tabular">{card.distanceToBreakoutPct}</strong>
                    </td>
                    <td data-mobile-label="证据">
                      <strong>{evidenceCount} 证据</strong>
                      <small title={primaryEvidencePreview?.value}>
                        {primaryEvidencePreview
                          ? `${primaryEvidencePreview.label}: ${primaryEvidencePreview.value}`
                          : "证据待补"}
                      </small>
                    </td>
                    <td data-mobile-label="边界">
                      <span className="stock-analysis-page__review-row-status" data-tone={status.tone}>
                        {card.boundaryEvidence.length > 0 ? `边界 ${card.boundaryEvidence.length}` : "边界清洁"}
                      </span>
                    </td>
                    <td data-mobile-label="失效">
                      <small title={card.invalidationFocus}>{card.invalidationFocus}</small>
                    </td>
                  </>
                )}
                <td>
                  <button
                    type="button"
                    className="stock-analysis-page__review-status-button"
                    data-testid={`stock-candidate-review-chart-${card.stockCode}`}
                    data-tone={status.tone}
                    onClick={() => onReviewCandidate(card)}
                    aria-label={`复核 ${card.stockName} K 线`}
                  >
                    <span className="sr-only">复核 </span>K 线
                  </button>
                  <small title={status.label}>{status.label}</small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
