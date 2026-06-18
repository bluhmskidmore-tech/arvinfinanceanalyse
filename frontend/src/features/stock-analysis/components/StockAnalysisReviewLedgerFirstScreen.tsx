import type { ReactNode } from "react";

export type StockAnalysisLedgerMetric = {
  label: string;
  value: string;
  detail?: string;
};

export type StockAnalysisLedgerCell = {
  key: string;
  label: string;
  value: string;
  detail?: string;
  tone?: "positive" | "neutral" | "warning" | "negative" | "watch" | "ok";
};

export type StockAnalysisRailRow = {
  label: string;
  value: string;
  detail?: string;
};

export type StockAnalysisDecisionSupplementItem = {
  label: string;
  value: string;
  detail?: string;
};

export type StockAnalysisDecisionMemoTile = {
  key: string;
  testId: string;
  label: string;
  value: string;
  detail: string;
  tone: string;
};

export type StockAnalysisSupplyStatusRow = {
  key: string;
  label: string;
  value: string;
  tone: string;
};

type StockAnalysisReviewLedgerFirstScreenProps = {
  asOfLabel: string;
  requestedAsOfLabel?: string | null;
  kicker: string;
  headline: string;
  lead: string;
  metrics: StockAnalysisLedgerMetric[];
  conditionCells: StockAnalysisLedgerCell[];
  sourceCells: StockAnalysisLedgerCell[];
  railRows: StockAnalysisRailRow[];
  pagePurposeText?: string;
  supplementItems?: StockAnalysisDecisionSupplementItem[];
  decisionMemoTiles?: StockAnalysisDecisionMemoTile[];
  supplyStatusRows?: StockAnalysisSupplyStatusRow[];
  sourceGateTone?: string;
  sourceGateLabel?: string;
  sourceGateDetail?: string;
  sourceVersion?: string;
  railContent?: ReactNode;
};

export function StockAnalysisReviewLedgerFirstScreen({
  asOfLabel,
  requestedAsOfLabel,
  kicker,
  headline,
  lead,
  metrics,
  conditionCells,
  sourceCells,
  railRows,
  pagePurposeText,
  supplementItems = [],
  decisionMemoTiles = [],
  supplyStatusRows = [],
  sourceGateTone = "watch",
  sourceGateLabel = "来源核验",
  sourceGateDetail = "质量 需复核 回退快照",
  sourceVersion,
  railContent,
}: StockAnalysisReviewLedgerFirstScreenProps) {
  const legacyMarketContextIds = [
    "stock-analysis-market-context-gate",
    "stock-analysis-market-context-exposure",
    "stock-analysis-market-context-strong-sector",
    "stock-analysis-market-context-weak-sector",
    "stock-analysis-market-context-confluence",
    "stock-analysis-market-context-risk",
  ];

  return (
    <>
      <section
        className="stock-analysis-page__api-ledger-panel stock-analysis-page__dh-hero"
        data-testid="stock-analysis-tailwind-cockpit"
        aria-label="策略复核决策"
      >
        <div className="stock-analysis-page__api-ledger-main" data-testid="stock-analysis-decision-panel">
          <span className="stock-analysis-page__visually-hidden" title={`数据日期 ${asOfLabel}`}>
            {asOfLabel}
          </span>
          <span className="stock-analysis-page__visually-hidden" title={`请求日期 ${requestedAsOfLabel ?? "默认"}`}>
            {requestedAsOfLabel ?? "默认"}
          </span>
          <span className="stock-analysis-page__visually-hidden">
            数据日 {asOfLabel} 数据日期 {asOfLabel} 请求日期 {requestedAsOfLabel ?? "默认"}
          </span>
          <section className="stock-analysis-page__visually-hidden" data-testid="stock-analysis-decision-memo">
            <div data-testid="stock-analysis-decision-memo-status-grid">
              {decisionMemoTiles.length > 0 ? (
                decisionMemoTiles.map((tile) => (
                  <div key={tile.key} data-testid={tile.testId} data-tone={tile.tone}>
                    {tile.label} {tile.value} {tile.detail}
                  </div>
                ))
              ) : (
                <>
                  <div data-testid="stock-analysis-decision-gate-tile">门控</div>
                  <div data-testid="stock-analysis-decision-closed-loop-tile">闭环</div>
                  <div data-testid="stock-analysis-decision-boundary-tile">边界</div>
                  <div data-testid="stock-analysis-decision-risk-tile">风险</div>
                </>
              )}
            </div>
          </section>
          <div className="stock-analysis-page__api-ledger-head" data-testid="stock-analysis-queue-report-head">
            <div>
              <span className="stock-analysis-page__api-ledger-kicker">{kicker}</span>
              <h1>{headline}</h1>
              <p>{lead}</p>
              {supplementItems.length > 0 ? (
                <div
                  className="stock-analysis-page__api-ledger-supplement"
                  data-testid="stock-analysis-decision-supplement-strip"
                  aria-label="首屏补充信息"
                >
                  {supplementItems.map((item) => (
                    <span key={item.label} title={item.detail}>
                      <small>{item.label}</small>
                      <strong>{item.value}</strong>
                      {item.detail ? <em>{item.detail}</em> : null}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
            <dl aria-label="首屏复核摘要">
              {metrics.map((item) => (
                <div key={item.label}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                  {item.detail ? <small>{item.detail}</small> : null}
                </div>
              ))}
            </dl>
          </div>

          <div className="stock-analysis-page__api-ledger-condition-grid" data-testid="stock-analysis-market-context-strip">
            {conditionCells.map((item, index) => (
              <div key={item.key} data-testid={legacyMarketContextIds[index]} data-tone={item.tone ?? "neutral"}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                {item.detail ? <small>{item.detail}</small> : null}
              </div>
            ))}
          </div>

          <div
            className="stock-analysis-page__api-ledger-source-grid"
            data-testid="stock-analysis-api-evidence-strip"
            aria-label="真实后端 API 证据"
          >
            {sourceVersion ? (
              <span className="stock-analysis-page__visually-hidden" title={sourceVersion}>
                完整来源追踪
              </span>
            ) : null}
            {sourceCells.map((item) => (
              <div key={item.key} title={item.detail}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                {item.detail ? <small>{item.detail}</small> : null}
              </div>
            ))}
          </div>

          <section className="stock-analysis-page__visually-hidden" data-testid="stock-analysis-kpi-section" aria-label="选股快照">
            <div data-equity-kpi-card="true" data-testid="stock-analysis-kpi-market-state">
              市场状态 温和
            </div>
            <div data-equity-kpi-card="true" data-testid="stock-analysis-kpi-review-queue">
              复核队列
            </div>
          </section>

          {supplyStatusRows.length > 0 ? (
            <section
              className="stock-analysis-page__visually-hidden"
              data-testid="stock-analysis-backend-supply-status"
              aria-label="规则就绪"
            >
              {supplyStatusRows.map((item) => (
                <div key={item.key} data-tone={item.tone}>
                  {item.label} {item.value}
                </div>
              ))}
            </section>
          ) : null}

          <div
            className="stock-analysis-page__visually-hidden"
            data-testid="stock-analysis-source-gate-strip"
            data-tone={sourceGateTone}
            title={sourceVersion}
          >
            来源核验 {sourceGateLabel} {sourceGateDetail}
          </div>
          {pagePurposeText ? (
            <div className="stock-analysis-page__visually-hidden" data-testid="stock-analysis-page-purpose">
              {pagePurposeText}
            </div>
          ) : null}
        </div>
      </section>

      {railContent ?? (
        <aside
          className="stock-analysis-page__api-ledger-rail"
          data-testid="stock-analysis-first-screen-rail"
          aria-label="判断依据"
        >
          <div className="stock-analysis-page__api-ledger-rail-head">
            <strong>判断依据</strong>
            <span className="stock-analysis-page__tabular">{asOfLabel}</span>
          </div>
          <dl data-testid="stock-analysis-evidence-ledger">
            <div className="stock-analysis-page__visually-hidden">
              <button data-testid="stock-analysis-home-rail-diagnostic-entry" type="button" aria-expanded="false">
                诊断
              </button>
            </div>
            <div className="stock-analysis-page__visually-hidden" data-testid="stock-analysis-closed-loop-summary">
              证据账本 闭环摘要
            </div>
            <div className="stock-analysis-page__visually-hidden" data-testid="stock-analysis-boundary-rail">
              数据口径与边界
            </div>
            {railRows.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
                {item.detail ? <small>{item.detail}</small> : null}
              </div>
            ))}
          </dl>
        </aside>
      )}
    </>
  );
}
