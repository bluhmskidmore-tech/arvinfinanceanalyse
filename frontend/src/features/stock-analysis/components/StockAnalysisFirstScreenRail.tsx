import type { StockCandidateReviewQueueItem, StockReviewQueueEmptyState } from "../lib/stockAnalysisPageModel";
import type { StockDataGapOverview } from "../lib/stockAnalysisFirstScreenModel";

type StockAnalysisFirstScreenRailProps = {
  queueTotalCount: number;
  queueVisibleCount: number;
  canReviewCandidates: boolean;
  emptyState: StockReviewQueueEmptyState | null;
  primaryBlockerLabel: string | null;
  topCandidates: StockCandidateReviewQueueItem[];
  onOpenCandidate: (card: StockCandidateReviewQueueItem) => void;
  onJumpToQueue: () => void;
  gapOverview: StockDataGapOverview;
};

/** First-screen right rail: review-queue status plus a compact data-gap digest. */
export function StockAnalysisFirstScreenRail({
  queueTotalCount,
  queueVisibleCount,
  canReviewCandidates,
  emptyState,
  primaryBlockerLabel,
  topCandidates,
  onOpenCandidate,
  onJumpToQueue,
  gapOverview,
}: StockAnalysisFirstScreenRailProps) {
  const queueEmpty = queueTotalCount === 0;
  return (
    <aside
      className="stock-analysis-page__fs-rail"
      data-testid="stock-analysis-first-screen-rail"
      aria-label="复核队列与数据缺口"
    >
      <section
        className="stock-analysis-page__fs-rail-card"
        data-testid="stock-analysis-review-queue-status"
        data-state={queueEmpty ? "empty" : canReviewCandidates ? "ready" : "blocked"}
      >
        <header className="stock-analysis-page__fs-card-head">
          <h2>复核队列</h2>
          <span
            className="stock-analysis-page__fs-card-pill stock-analysis-page__tabular"
            data-tone={queueEmpty ? "warning" : canReviewCandidates ? "positive" : "negative"}
          >
            {queueEmpty ? "0 条" : `${queueVisibleCount}/${queueTotalCount} 条`}
          </span>
        </header>
        {queueEmpty ? (
          <p
            className="stock-analysis-page__fs-rail-empty"
            role="status"
            data-testid="stock-analysis-review-queue-empty"
            title={emptyState?.detail ?? undefined}
          >
            {emptyState?.headline ?? "今天没有进入复核队列的候选"}
            {primaryBlockerLabel ? `：${primaryBlockerLabel}` : ""}
          </p>
        ) : (
          <>
            <p className="stock-analysis-page__fs-rail-note">
              {canReviewCandidates ? "候选可继续只读复核" : "门禁未放行，候选仅可只读排查"}
            </p>
            <ol className="stock-analysis-page__fs-rail-queue">
              {/* 同一股票可按来源模块各占一行且携带模块内 rank（后端按 (source_module, stock_code) 去重），
                  stockCode+rank 会撞 key，补 index 保证唯一（与候选对比表同口径）。 */}
              {topCandidates.map((card, index) => (
                <li key={`${card.stockCode}-${card.rank}-${index}`}>
                  <button
                    type="button"
                    data-testid={`stock-analysis-rail-queue-${card.stockCode}`}
                    onClick={() => onOpenCandidate(card)}
                  >
                    <span className="stock-analysis-page__tabular">#{card.rank}</span>
                    <strong>{card.stockName}</strong>
                    <small className="stock-analysis-page__tabular">{card.stockCode}</small>
                    <em>{card.sectorName || "—"}</em>
                  </button>
                </li>
              ))}
            </ol>
            <button
              type="button"
              className="stock-analysis-page__fs-rail-jump"
              data-testid="stock-analysis-rail-queue-jump"
              onClick={onJumpToQueue}
            >
              查看完整队列
            </button>
          </>
        )}
      </section>
      <section
        className="stock-analysis-page__fs-rail-card"
        data-testid="stock-analysis-data-gap-summary"
      >
        <header className="stock-analysis-page__fs-card-head">
          <h2>数据缺口</h2>
          <span
            className="stock-analysis-page__fs-card-pill stock-analysis-page__tabular"
            data-tone={gapOverview.blockingGaps.length > 0 ? "negative" : "positive"}
          >
            阻断 {gapOverview.blockingGaps.length}/{gapOverview.activeGaps.length}
          </span>
        </header>
        {gapOverview.activeGaps.length === 0 ? (
          <p className="stock-analysis-page__fs-rail-empty" role="status">
            当前无未闭合缺口。
          </p>
        ) : (
          <ul className="stock-analysis-page__fs-rail-gaps">
            {gapOverview.blockingGaps.slice(0, 3).map((gap, index) => (
              <li
                key={`${gap.input_family}-${index}`}
                title={gap.evidence}
                data-testid={`stock-analysis-gap-summary-${gap.input_family}`}
              >
                <span
                  className="stock-analysis-page__fs-status-dot"
                  data-tone="negative"
                  aria-hidden="true"
                />
                <strong>{gap.shortLabel}</strong>
                <em>{gap.statusLabel}</em>
              </li>
            ))}
          </ul>
        )}
        <p className="stock-analysis-page__fs-rail-foot">补证明细见下方证据与口径。</p>
      </section>
    </aside>
  );
}
