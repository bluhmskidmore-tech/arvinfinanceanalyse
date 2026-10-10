import { BarChartOutlined, DatabaseOutlined, SafetyCertificateOutlined } from "@ant-design/icons";

import { BaseChart } from "../../../components/charts/BaseChart";
import { EM_DASH } from "../../../utils/format";
import type {
  StockCandidateReviewQueueItem,
  StockSectorRow,
} from "../lib/stockAnalysisPageModel";
import type { StockAnalysisResearchDeskModel } from "../lib/stockAnalysisResearchDeskModel";
import "./StockAnalysisReadOnlyResearchZone.css";
import "../pages/StockAnalysisDeepResearch.css";
import researchDeskStyles from "../pages/StockAnalysisResearchDesk.module.css";

export type StockAnalysisReadOnlyResearchZoneProps = {
  analyticsAsOf: string | null;
  model: StockAnalysisResearchDeskModel;
  sectorRows: StockSectorRow[];
  selectedCandidate: StockCandidateReviewQueueItem | null;
};

export function StockAnalysisReadOnlyResearchZone({
  analyticsAsOf,
  model,
  sectorRows,
  selectedCandidate,
}: StockAnalysisReadOnlyResearchZoneProps) {
  if (!selectedCandidate) {
    return (
      <section
        className="stock-analysis-page__readonly-research"
        data-testid="stock-analysis-readonly-research"
      >
        <strong>只读深研暂不可用</strong>
        <p>当前没有可复核候选，页面不会读取共振、历史回测或风险执行结果。</p>
      </section>
    );
  }

  const selectedSector =
    sectorRows.find((row) => row.sectorCode === selectedCandidate.sectorCode) ?? null;
  const detailSource = model.sourceItems.find((item) => item.key === "selected-stock-detail") ?? null;
  const klineSource = model.sourceItems.find((item) => item.key === "selected-kline") ?? null;
  const currentEvidenceTone =
    detailSource?.tone === "negative" || klineSource?.tone === "negative"
      ? "negative"
      : detailSource?.tone === "positive" && klineSource?.tone === "positive" && selectedSector
        ? "positive"
        : "warning";
  const currentEvidenceStatus = [
    `详情 ${detailSource?.statusLabel ?? "待触发"}`,
    `K线 ${klineSource?.statusLabel ?? "待确认"}`,
    `行业 ${selectedSector ? "已匹配" : "待匹配"}`,
  ].join(" / ");
  const keyFacts = model.summary.keyFacts.slice(0, 6);
  const momentumCards = model.momentumCards.slice(0, 6);

  return (
    <section
      className="stock-analysis-page__readonly-research"
      data-testid="stock-analysis-readonly-research"
    >
      <header className="stock-analysis-page__readonly-research-head">
        <div>
          <p>只读深度研究</p>
          <h2>
            {selectedCandidate.stockName} <small>{selectedCandidate.stockCode}</small>
          </h2>
          <span>
            {selectedCandidate.sectorName} · 数据日 {analyticsAsOf ?? EM_DASH}
          </span>
        </div>
        <div className="stock-analysis-page__readonly-research-quote">
          <strong>{model.summary.quoteValue}</strong>
          <span>涨跌 {model.summary.dailyChangeLabel}</span>
        </div>
      </header>

      <div
        className="stock-analysis-page__readonly-research-boundaries"
        aria-label="只读研究边界"
      >
        <article data-tone={currentEvidenceTone}>
          <DatabaseOutlined aria-hidden="true" />
          <span>当前证据</span>
          <strong>{currentEvidenceStatus}</strong>
        </article>
        <article data-tone="warning">
          <BarChartOutlined aria-hidden="true" />
          <span>正式评分与代理回测</span>
          <strong>盘前资格未闭合，未读取</strong>
        </article>
        <article data-tone="warning">
          <SafetyCertificateOutlined aria-hidden="true" />
          <span>风险与执行</span>
          <strong>保持关闭</strong>
        </article>
      </div>

      <div className="stock-analysis-page__readonly-research-grid">
        <article className="stock-analysis-page__readonly-research-panel">
          <div className="stock-analysis-page__readonly-research-panel-head">
            <div>
              <span>个股详情</span>
              <strong>{model.summary.keyFactsTitle}</strong>
            </div>
            <em data-tone={detailSource?.tone ?? "warning"}>
              {detailSource?.statusLabel ?? "待触发"}
            </em>
          </div>
          <dl className="stock-analysis-page__readonly-research-facts">
            {keyFacts.map((item) => (
              <div key={item.key}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </article>

        <article className="stock-analysis-page__readonly-research-panel">
          <div className="stock-analysis-page__readonly-research-panel-head">
            <div>
              <span>K线观察</span>
              <strong>{model.summary.researchSummary}</strong>
            </div>
            <em data-tone={klineSource?.tone ?? "warning"}>
              {klineSource?.statusLabel ?? "待确认"}
            </em>
          </div>
          {model.summary.chartOption ? (
            <div className="stock-analysis-page__readonly-research-chart">
              <BaseChart option={model.summary.chartOption} height={180} />
            </div>
          ) : (
            <div className="stock-analysis-page__readonly-research-empty">
              <strong>{model.summary.chartMessage?.headline ?? "价格序列待补"}</strong>
              <span>{model.summary.chartMessage?.detail ?? model.summary.chartFootnote}</span>
            </div>
          )}
          <div className={researchDeskStyles.chartFooter}>
            <div className={researchDeskStyles.chartLegend} aria-label="价格图例">
              <span data-series="close">收盘</span>
              <span data-series="ma5">MA5</span>
              <span data-series="ma20">MA20</span>
            </div>
            <small className={researchDeskStyles.footnote}>{model.summary.chartFootnote}</small>
          </div>
          <dl className="stock-analysis-page__readonly-research-facts stock-analysis-page__readonly-research-facts--compact">
            {momentumCards.map((item) => (
              <div key={item.key}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </article>

        <article className="stock-analysis-page__readonly-research-panel">
          <div className="stock-analysis-page__readonly-research-panel-head">
            <div>
              <span>当前行业快照</span>
              <strong>{selectedSector?.sectorName ?? selectedCandidate.sectorName}</strong>
            </div>
            <em data-tone={selectedSector ? "positive" : "warning"}>
              {selectedSector ? `第 ${selectedSector.rank} 名` : "待匹配"}
            </em>
          </div>
          {selectedSector ? (
            <dl className="stock-analysis-page__readonly-research-facts">
              <div>
                <dt>行业评分</dt>
                <dd>{selectedSector.score}</dd>
              </div>
              <div>
                <dt>当日涨跌</dt>
                <dd>{selectedSector.pctChange}</dd>
              </div>
              <div>
                <dt>平均换手（%）</dt>
                <dd>{selectedSector.turnover}</dd>
              </div>
              <div>
                <dt>平均振幅</dt>
                <dd>{selectedSector.amplitude}</dd>
              </div>
              <div>
                <dt>成分数量</dt>
                <dd>{selectedSector.constituentCount.toLocaleString("zh-CN")}</dd>
              </div>
            </dl>
          ) : (
            <div className="stock-analysis-page__readonly-research-empty">
              <strong>行业快照待匹配</strong>
              <span>候选仍可查看个股证据，行业结论保持为空。</span>
            </div>
          )}
        </article>
      </div>

      <p className="stock-analysis-page__readonly-research-disclosure">
        当前区域只展示已返回的观察证据，不生成正式共振、策略评分、代理回测、风险退出或交易执行结论。
      </p>
    </section>
  );
}
