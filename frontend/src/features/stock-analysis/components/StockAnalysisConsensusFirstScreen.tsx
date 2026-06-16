import { BarChartOutlined, DatabaseOutlined, LineChartOutlined, ThunderboltOutlined } from "@ant-design/icons";

import { consensusStrategyLabel, type ConsensusCandidateItem, type ConsensusSummary } from "../lib/buildConsensusSummary";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import { CompactStatusTile } from "./StockAnalysisStatusPrimitives";

type StockAnalysisConsensusFirstScreenProps = {
  consensusSummary: ConsensusSummary;
  consensusHitCount: number;
  firstScreenItems: ConsensusCandidateItem[];
  emptyDetail?: string | null;
  onOpenConsensusDetail: (row: ConsensusCandidateItem) => void;
};

export function StockAnalysisConsensusFirstScreen({
  consensusSummary,
  consensusHitCount,
  firstScreenItems,
  emptyDetail,
  onOpenConsensusDetail,
}: StockAnalysisConsensusFirstScreenProps) {
  return (
    <section
      className={SA_FIRST_CARD}
      id="stock-analysis-consensus-first-screen"
      data-testid="stock-analysis-consensus-first-screen"
    >
      <div className={SA_SECTION_HEAD}>
        <div className="stock-analysis-page__min-w-0">
          <p className={SA_SECTION_EYEBROW}>多策略共振</p>
          <h2 className={SA_CARD_TITLE}>策略共振选股</h2>
          <p className={SA_SECTION_DESC}>共振命中 · 三重优先</p>
        </div>
        <span className={SA_PILL}>
          共振 {consensusHitCount} · 去重 {consensusSummary.totalUnion}
        </span>
      </div>

      <div
        className="stock-analysis-page__consensus-workbench-strip"
        data-testid="stock-analysis-consensus-workbench-strip"
        aria-label="策略共振摘要"
      >
        <div data-tone={consensusHitCount > 0 ? "positive" : "neutral"}>
          <ThunderboltOutlined aria-hidden="true" />
          <span>共振</span>
          <strong className="stock-analysis-page__tabular">{consensusHitCount}</strong>
        </div>
        <div>
          <DatabaseOutlined aria-hidden="true" />
          <span>去重</span>
          <strong className="stock-analysis-page__tabular">{consensusSummary.totalUnion}</strong>
        </div>
        <div>
          <LineChartOutlined aria-hidden="true" />
          <span>趋势</span>
          <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.livermore}</strong>
        </div>
        <div>
          <BarChartOutlined aria-hidden="true" />
          <span>多因子</span>
          <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.factor_screen}</strong>
        </div>
      </div>

      {!consensusSummary.hasAnyStrategy ? (
        <p className="stock-analysis-page__empty">{emptyDetail ?? "候选 0"}</p>
      ) : firstScreenItems.length === 0 ? (
        <div
          className="stock-analysis-page__empty-status-grid"
          role="status"
          data-testid="stock-analysis-consensus-empty-scan"
          aria-label="暂无多策略共振"
        >
          <CompactStatusTile icon={<ThunderboltOutlined />} label="共振" value={consensusHitCount} />
          <CompactStatusTile icon={<DatabaseOutlined />} label="去重" value={consensusSummary.totalUnion} />
          <CompactStatusTile
            icon={<LineChartOutlined />}
            label="复核"
            value="队列"
            tone="positive"
            className="stock-analysis-page__compact-status-tile--accent"
          />
        </div>
      ) : (
        <div className="stock-analysis-page__consensus-first-list">
          {firstScreenItems.map((row) => {
            const isTriple = row.consensusCount >= 3;
            return (
              <button
                key={row.stockCode}
                type="button"
                className={`stock-analysis-page__consensus-first-row stock-analysis-page__row--clickable${
                  isTriple ? " stock-analysis-page__consensus-first-row--triple" : ""
                }`}
                data-testid={`consensus-first-row-${row.stockCode}`}
                onClick={() => onOpenConsensusDetail(row)}
              >
                <div className="stock-analysis-page__consensus-first-main">
                  <strong>
                    {row.stockName} <small className="stock-analysis-page__tabular">{row.stockCode}</small>
                  </strong>
                  <span>{row.sectorName}</span>
                </div>
                <div className="stock-analysis-page__consensus-first-badges">
                  <span
                    className={`stock-analysis-page__consensus-badge${
                      isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                    }`}
                  >
                    {row.consensusCount} 策略共振
                  </span>
                  {row.strategies.map((kind) => (
                    <span key={kind} className="stock-analysis-page__consensus-badge">
                      {consensusStrategyLabel(kind)}
                    </span>
                  ))}
                </div>
                <div className="stock-analysis-page__consensus-ranks">
                  {row.hybridFusionRank != null && <span>融合 #{row.hybridFusionRank}</span>}
                  {row.livermoreRank != null && <span>趋势 #{row.livermoreRank}</span>}
                  {row.factorScreenRank != null && <span>多因子 #{row.factorScreenRank}</span>}
                  {row.meanReversionRank != null && <span>超跌 #{row.meanReversionRank}</span>}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
