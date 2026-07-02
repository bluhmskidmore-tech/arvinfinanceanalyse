import type { KeyboardEvent, SyntheticEvent } from "react";
import type { StockStrategyLensItem } from "../lib/stockAnalysisPageModel";

type StockAnalysisStrategyLensSectionProps = {
  items: StockStrategyLensItem[];
  onScrollToSection: (targetId: string) => void;
};

const STRATEGY_LENS_DEFAULT_CARD_COUNT = 1;
const STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT = 1;

export function StockAnalysisStrategyLensSection({
  items,
  onScrollToSection,
}: StockAnalysisStrategyLensSectionProps) {
  if (items.length === 0) return null;

  const readyCount = items.filter((item) => item.state === "ready").length;
  const blockedCount = items.filter((item) => item.state === "blocked").length;
  const pausedCount = items.filter((item) => item.state === "paused").length;
  const totalCandidates = items.reduce((sum, item) => {
    const count = Number(item.value);
    return Number.isFinite(count) ? sum + count : sum;
  }, 0);
  const candidateItems = items.filter((item) => item.candidates.length > 0);
  const emptyCandidateItems = items.filter((item) => item.candidates.length === 0);
  const visibleItems = candidateItems.length > 0 ? candidateItems.slice(0, STRATEGY_LENS_DEFAULT_CARD_COUNT) : items;
  const deferredCandidateItems =
    candidateItems.length > STRATEGY_LENS_DEFAULT_CARD_COUNT
      ? candidateItems.slice(STRATEGY_LENS_DEFAULT_CARD_COUNT)
      : [];
  const backgroundItems = candidateItems.length > 0 ? emptyCandidateItems : [];
  const deferredStrategyItems = [...deferredCandidateItems, ...backgroundItems];

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>, targetId: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onScrollToSection(targetId);
    }
  };

  const stopCardNavigation = (event: SyntheticEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  const renderStrategyCard = (item: StockStrategyLensItem) => (
    <article
      key={item.key}
      className="stock-analysis-page__strategy-lens-card"
      data-has-candidates={item.candidates.length > 0 ? "true" : "false"}
      data-tone={item.tone}
      data-state={item.state}
      data-testid={`stock-analysis-strategy-lens-${item.key}`}
      role="button"
      tabIndex={0}
      aria-label={`${item.label}, ${item.value} ${item.unitLabel}, ${item.statusLabel}`}
      onClick={() => onScrollToSection(item.scrollTarget)}
      onKeyDown={(event) => handleKeyDown(event, item.scrollTarget)}
    >
      <div className="stock-analysis-page__strategy-lens-card-head">
        <div>
          <span className="stock-analysis-page__strategy-lens-label">{item.label}</span>
          <small className="stock-analysis-page__strategy-lens-subtitle">{item.subtitle}</small>
        </div>
        <span className="stock-analysis-page__strategy-lens-status">{item.statusLabel}</span>
      </div>
      <div className="stock-analysis-page__strategy-lens-main">
        <strong className="stock-analysis-page__strategy-lens-value">{item.value}</strong>
        <span>{item.unitLabel}</span>
      </div>
      <small className="stock-analysis-page__strategy-lens-detail" title={item.detail}>
        {item.detail}
      </small>
      <details
        className="stock-analysis-page__strategy-lens-meta"
        data-testid={`stock-analysis-strategy-lens-${item.key}-meta`}
        onClick={stopCardNavigation}
        onKeyDown={stopCardNavigation}
      >
        <summary className="stock-analysis-page__strategy-lens-meta-summary">
          <span>证据口径</span>
          <small title={item.focusLabel}>{item.focusLabel}</small>
        </summary>
        <dl className="stock-analysis-page__strategy-lens-ledger" aria-label={`${item.label}复核台账`}>
          <div>
            <dt>候选</dt>
            <dd>{item.candidateCountLabel}</dd>
          </div>
          <div>
            <dt>阻断</dt>
            <dd title={item.blockerLabel}>{item.blockerLabel}</dd>
          </div>
          <div>
            <dt>关注</dt>
            <dd title={item.focusLabel}>{item.focusLabel}</dd>
          </div>
          <div>
            <dt>入口</dt>
            <dd>{item.actionLabel}</dd>
          </div>
        </dl>
        <span className="stock-analysis-page__strategy-lens-version" title={`${item.dateLabel} · ${item.formulaLabel}`}>
          <strong>{item.dateLabel}</strong>
          <em>{item.formulaLabel}</em>
        </span>
        <div className="stock-analysis-page__strategy-lens-evidence" aria-label={`${item.label}证据`}>
          {item.evidence.map((row) => (
            <span key={row.key} title={`${row.label} ${row.value}`}>
              {row.label} <strong>{row.value}</strong>
            </span>
          ))}
        </div>
      </details>
      {item.candidates.length > 0 ? (
        <>
          <ol className="stock-analysis-page__strategy-lens-candidates" aria-label={`${item.label}候选预览`}>
            {item.candidates.slice(0, STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT).map((candidate) => (
              <li key={candidate.key}>
                <span className="stock-analysis-page__strategy-lens-rank">{candidate.rankLabel}</span>
                <strong>
                  {candidate.stockName}
                  <small className="stock-analysis-page__tabular"> {candidate.stockCode}</small>
                </strong>
                <span>{candidate.sectorName || "-"}</span>
                <em>{candidate.metricLabel}</em>
              </li>
            ))}
          </ol>
          {item.candidates.length > STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT ? (
            <details
              className="stock-analysis-page__strategy-lens-candidates-more"
              data-testid={`stock-analysis-strategy-lens-${item.key}-more-candidates`}
              onClick={stopCardNavigation}
              onKeyDown={stopCardNavigation}
            >
              <summary className="stock-analysis-page__strategy-lens-candidates-more-summary">
                <span>更多候选</span>
                <small>余 {item.candidates.length - STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT} 只</small>
              </summary>
              <ol className="stock-analysis-page__strategy-lens-candidates stock-analysis-page__strategy-lens-candidates--extra">
                {item.candidates.slice(STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT).map((candidate) => (
                  <li key={candidate.key}>
                    <span className="stock-analysis-page__strategy-lens-rank">{candidate.rankLabel}</span>
                    <strong>
                      {candidate.stockName}
                      <small className="stock-analysis-page__tabular"> {candidate.stockCode}</small>
                    </strong>
                    <span>{candidate.sectorName || "-"}</span>
                    <em>{candidate.metricLabel}</em>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
        </>
      ) : (
        <p className="stock-analysis-page__strategy-lens-empty" title={item.statusDetail}>
          {item.statusDetail}
        </p>
      )}
      {item.progress != null ? (
        <progress
          className="stock-analysis-page__strategy-lens-meter"
          max={100}
          value={Math.max(4, item.progress * 100)}
          aria-label={`${item.label}进度`}
        />
      ) : null}
    </article>
  );

  return (
    <section
      className="stock-analysis-page__strategy-lens"
      aria-label="策略选股概览"
      data-testid="stock-analysis-strategy-lens"
    >
      <header className="stock-analysis-page__strategy-lens-header">
        <div>
          <p className="stock-analysis-page__strategy-lens-eyebrow">核心选股策略</p>
          <h2>4 策略台账</h2>
        </div>
        <div className="stock-analysis-page__strategy-lens-summary" aria-label="策略台账摘要">
          <span>可用 {readyCount}/{items.length}</span>
          <span>候选 {totalCandidates}</span>
          <span>阻断 {blockedCount}</span>
          {pausedCount > 0 ? <span>暂停 {pausedCount}</span> : null}
        </div>
      </header>
      <div className="stock-analysis-page__strategy-lens-grid">{visibleItems.map(renderStrategyCard)}</div>
      {deferredStrategyItems.length > 0 ? (
        <details
          className="stock-analysis-page__strategy-lens-more-strategies"
          data-testid="stock-analysis-strategy-lens-more-strategies"
        >
          <summary className="stock-analysis-page__strategy-lens-more-strategies-summary">
            <span>更多候选策略</span>
            <small>余 {deferredStrategyItems.length} 个策略，含观察/阻断原因</small>
          </summary>
          <div className="stock-analysis-page__strategy-lens-more-strategies-grid">
            {deferredCandidateItems.map(renderStrategyCard)}
            {backgroundItems.map(renderStrategyCard)}
          </div>
        </details>
      ) : null}
      {deferredStrategyItems.length === 0 && backgroundItems.length > 0 ? (
        <details
          className="stock-analysis-page__strategy-lens-empty-strategies"
          data-testid="stock-analysis-strategy-lens-empty-strategies"
        >
          <summary className="stock-analysis-page__strategy-lens-empty-strategies-summary">
            <span>暂无候选策略</span>
            <small>{backgroundItems.length} 个策略，仅保留阻断原因</small>
          </summary>
          <div className="stock-analysis-page__strategy-lens-empty-strategies-grid">
            {backgroundItems.map(renderStrategyCard)}
          </div>
        </details>
      ) : null}
    </section>
  );
}
