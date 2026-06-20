import type {
  StockThemeBreakoutCard,
  StockThemeBreakoutReviewItem,
  StockThemeEvidenceStateRow,
} from "../lib/stockAnalysisPageModel";
import {
  SA_PILL,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";

type StockAnalysisThemeBreakoutPanelProps = {
  cards: StockThemeBreakoutCard[];
  evidenceRows: StockThemeEvidenceStateRow[];
  reviewItems: StockThemeBreakoutReviewItem[];
  emptyMessage: string;
};

export function StockAnalysisThemeBreakoutPanel({
  cards,
  evidenceRows,
  reviewItems,
  emptyMessage,
}: StockAnalysisThemeBreakoutPanelProps) {
  return (
    <>
      {cards.length > 0 ? (
        <div className="stock-analysis-page__candidate-grid" data-testid="stock-analysis-theme-breakout-cards">
          {cards.map((card) => (
            <ThemeBreakoutCard card={card} key={card.themeKey} />
          ))}
        </div>
      ) : (
        <p className="stock-analysis-page__empty">{emptyMessage}</p>
      )}

      {evidenceRows.length > 0 ? (
        <div data-testid="stock-analysis-theme-evidence-state">
          <div className={SA_SECTION_HEAD}>
            <strong>题材证据就绪</strong>
            <span className={SA_PILL}>{evidenceRows.length} 项证据</span>
          </div>
          <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
            {evidenceRows.map((row) => (
              <li key={row.key}>
                <span>
                  <strong>{row.label}</strong>
                  <small>
                    {row.statusLabel} / {row.rowCountLabel}
                  </small>
                </span>
                <em>{row.detail}</em>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {reviewItems.length > 0 ? (
        <div data-testid="stock-analysis-theme-review-items">
          <div className={SA_SECTION_HEAD}>
            <strong>题材未入选复核</strong>
            <span className={SA_PILL}>待排查 {reviewItems.length} 项</span>
          </div>
          <div className="stock-analysis-page__candidate-grid">
            {reviewItems.map((item) => (
              <ThemeReviewItem item={item} key={item.themeKey} />
            ))}
          </div>
        </div>
      ) : null}
    </>
  );
}

function ThemeBreakoutCard({ card }: { card: StockThemeBreakoutCard }) {
  return (
    <article className="stock-analysis-page__candidate">
      <div className="stock-analysis-page__candidate-head">
        <div>
          <h3>
            #{card.rank} {card.themeName}
          </h3>
          <p>{card.parentSectorLabel}</p>
          <div className="stock-analysis-page__pattern-tag">{card.summary}</div>
        </div>
        <span>观察</span>
      </div>
      <div className="stock-analysis-page__decision-meta">
        <span>{card.strongCountLabel}</span>
        <span>{card.limitCountLabel}</span>
        <span>{card.advanceRatioLabel}</span>
        <span>{card.avgPctChangeLabel}</span>
        <span>{card.movementLabel}</span>
      </div>
      <p className="stock-analysis-page__review-focus">{card.reason}</p>
      <p className="stock-analysis-page__review-focus">{card.latestEventLabel}</p>
      <p className="stock-analysis-page__notice">{card.boundaryLabel}</p>
      <ThemeLeaderList leaders={card.leaders} fallbackTag="观察" />
    </article>
  );
}

function ThemeReviewItem({ item }: { item: StockThemeBreakoutReviewItem }) {
  return (
    <article className="stock-analysis-page__candidate">
      <div className="stock-analysis-page__candidate-head">
        <div>
          <h3>
            复核 #{item.rank} {item.themeName}
          </h3>
          <p>{item.parentSectorLabel}</p>
          <div className="stock-analysis-page__pattern-tag">{item.summary}</div>
        </div>
        <span>{item.sourceKindLabel}</span>
      </div>
      <div className="stock-analysis-page__decision-meta">
        <span>{item.failedGateLabel}</span>
      </div>
      <p className="stock-analysis-page__review-focus">{item.reason}</p>
      {item.leaders.length > 0 ? <ThemeLeaderList leaders={item.leaders} fallbackTag="复核" /> : null}
    </article>
  );
}

function ThemeLeaderList({
  leaders,
  fallbackTag,
}: {
  leaders: StockThemeBreakoutCard["leaders"];
  fallbackTag: string;
}) {
  return (
    <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
      {leaders.map((leader) => (
        <li key={leader.stockCode}>
          <span>
            <strong>{leader.stockName}</strong>
            <small>
              {leader.stockCode} / {leader.pctChange} / 换手 {leader.turn} / 收盘强度{" "}
              {leader.closeStrength}
            </small>
          </span>
          <em>{leader.tags.join(" / ") || fallbackTag}</em>
        </li>
      ))}
    </ul>
  );
}
