import type { ReactNode } from "react";
import type {
  StockObservationClosureSummary,
  WorkbenchDataDigest,
  WorkbenchFact,
} from "../lib/stockAnalysisPageModel";

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
  digest?: WorkbenchDataDigest;
  closureSummary?: StockObservationClosureSummary;
  railContent?: ReactNode;
};

function StockWorkbenchFactGrid({
  title,
  facts,
}: {
  title: string;
  facts: WorkbenchFact[];
}) {
  if (facts.length === 0) return null;
  return (
    <section className="stock-analysis-page__workbench-digest-section">
      <h3>{title}</h3>
      <div className="stock-analysis-page__workbench-fact-grid">
        {facts.map((fact) => (
          <article
            className="stock-analysis-page__workbench-fact"
            data-testid={`stock-analysis-workbench-fact-${fact.id}`}
            data-tone={fact.tone}
            data-primary={fact.isPrimary ? "true" : "false"}
            key={fact.id}
          >
            <span>{fact.label}</span>
            <strong>{fact.value}</strong>
            {fact.subValue ? <small>{fact.subValue}</small> : null}
            <em title={fact.sourcePath}>来源：{fact.sourcePath}</em>
          </article>
        ))}
      </div>
    </section>
  );
}

function StockWorkbenchDigest({ digest }: { digest: WorkbenchDataDigest }) {
  return (
    <section
      className="stock-analysis-page__workbench-digest"
      data-testid="stock-analysis-workbench-digest"
      aria-label="首屏供数摘要"
    >
      <StockWorkbenchFactGrid title="核心口径" facts={digest.primaryFacts} />
      <StockWorkbenchFactGrid
        title="候选与证据"
        facts={[...digest.candidateFacts, ...digest.evidenceFacts]}
      />
      <StockWorkbenchFactGrid title="慢接口补证" facts={digest.slowFacts} />
    </section>
  );
}

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
  digest,
  closureSummary,
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

          {digest ? <StockWorkbenchDigest digest={digest} /> : null}

          {closureSummary ? (
            <section
              className="stock-analysis-page__observation-closure"
              data-testid="stock-analysis-observation-closure-panel"
              data-tone={closureSummary.tone}
              aria-label="观测闭环总控"
            >
              <div className="stock-analysis-page__observation-closure-head">
                <div>
                  <span>观测闭环总控</span>
                  <h2>{closureSummary.headline}</h2>
                  <p>{closureSummary.detail}</p>
                </div>
                <strong>正式用途：{closureSummary.formalUseAllowed ? "是" : "否"}</strong>
              </div>
              <dl className="stock-analysis-page__observation-closure-metrics">
                <div>
                  <dt>接口链路</dt>
                  <dd>{`${closureSummary.endpointLoadedCount}/${closureSummary.endpointTotal}`}</dd>
                </div>
                <div>
                  <dt>待复核项</dt>
                  <dd>{closureSummary.unresolvedReasons.length}</dd>
                </div>
                <div>
                  <dt>读取失败</dt>
                  <dd>{closureSummary.endpointErrorCount}</dd>
                </div>
                <div>
                  <dt>元信息缺口</dt>
                  <dd>{closureSummary.metaMissingCount}</dd>
                </div>
              </dl>
              <div className="stock-analysis-page__observation-closure-grid">
                <div>
                  <h3>未闭环原因</h3>
                  <ul data-testid="stock-analysis-observation-closure-reasons">
                    {closureSummary.unresolvedReasons.slice(0, 5).map((reason) => (
                      <li key={reason.key} data-tone={reason.tone}>
                        <span>{reason.endpointLabel}</span>
                        <strong>{reason.displayText}</strong>
                        <small title={reason.fieldPath}>字段来源已记录</small>
                      </li>
                    ))}
                    {closureSummary.unresolvedReasons.length === 0 ? (
                      <li data-tone="neutral">
                        <span>证据项</span>
                        <strong>暂无新增待复核项</strong>
                        <small>仍保留观测边界，不代表正式通过</small>
                      </li>
                    ) : null}
                  </ul>
                </div>
                <div>
                  <h3>下一步证据动作</h3>
                  <ul data-testid="stock-analysis-observation-closure-actions">
                    {closureSummary.nextEvidenceActions.slice(0, 5).map((action) => (
                      <li key={action.key}>
                        <span>{action.source}</span>
                        <strong>{action.actionText}</strong>
                        <small title={action.fieldPath}>证据字段已定位</small>
                      </li>
                    ))}
                    {closureSummary.nextEvidenceActions.length === 0 ? (
                      <li>
                        <span>治理</span>
                        <strong>等待业务 owner 审批与人工复核</strong>
                        <small>{closureSummary.approvalStatus}</small>
                      </li>
                    ) : null}
                  </ul>
                </div>
              </div>
            </section>
          ) : null}

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
