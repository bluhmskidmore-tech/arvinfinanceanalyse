import type { ReactNode } from "react";

export type StockAnalysisWorkbenchContractSummary = {
  question: string;
  answerLabel: string;
  reason: string;
  canReviewCandidates: boolean;
  topReviewStock?: string | null;
  primaryBlocker?: string | null;
  formalUseAllowed: boolean;
  routeLabel: string;
  resultKindLabel: string;
  includeLabel?: string;
};

export type StockAnalysisEvidenceSourceCell = {
  key: string;
  label: string;
  value: string;
  detail?: string;
};

export type StockAnalysisEndpointLedgerItem = {
  key: string;
  label: string;
  status: string;
  tone: string;
  detail: string;
};

export type StockAnalysisGateStateVariantRow = {
  key: string;
  title: string;
  tone: string;
  detail: string;
};

export type StockAnalysisReadinessItem = {
  key: string;
  label: string;
  statusLabel: string;
  status: string;
  metric: string;
  detail: string;
  summary: string;
  inputsLabel: string;
};

export type StockAnalysisGapReleaseCard = {
  key: string;
  label: string;
  statusLabel: string;
  tone: "negative" | "warning" | "neutral";
  releaseLabel: string;
  evidence: string;
};

type StockAnalysisEvidenceDisclosureProps = {
  contract?: StockAnalysisWorkbenchContractSummary;
  onOpenTopReviewStock?: () => void;
  sourceCells: StockAnalysisEvidenceSourceCell[];
  endpointLedgerItems: StockAnalysisEndpointLedgerItem[];
  gateStateVariantRows: StockAnalysisGateStateVariantRow[];
  readinessItems: StockAnalysisReadinessItem[];
  gapReleaseCards: StockAnalysisGapReleaseCard[];
  digestContent?: ReactNode;
  closureContent?: ReactNode;
  railContent?: ReactNode;
};

/**
 * Collapsed evidence layer. Endpoint routes, trace ids, rule versions and gap
 * remediation details are only allowed inside this disclosure, never on the
 * first screen (DESIGN.md section 6, provenance layering).
 */
export function StockAnalysisEvidenceDisclosure({
  contract,
  onOpenTopReviewStock,
  sourceCells,
  endpointLedgerItems,
  gateStateVariantRows,
  readinessItems,
  gapReleaseCards,
  digestContent,
  closureContent,
  railContent,
}: StockAnalysisEvidenceDisclosureProps) {
  return (
    <details
      className="stock-analysis-page__evidence-disclosure"
      data-testid="stock-analysis-evidence-disclosure"
      aria-label="证据与口径"
    >
      <summary
        className="stock-analysis-page__evidence-disclosure-summary"
        data-testid="stock-analysis-evidence-disclosure-summary"
      >
        <span>证据与口径</span>
        <strong>接口契约、供数链路与缺口补证</strong>
        <small>默认收起 · 数据入口与版本信息集中在此</small>
      </summary>
      <div className="stock-analysis-page__evidence-disclosure-body">
        {contract ? (
          <section
            className="stock-analysis-page__evidence-contract"
            data-testid="stock-analysis-workbench-contract"
            aria-label="页面复核业务契约"
          >
            <div className="stock-analysis-page__evidence-contract-head">
              <span>页面核心问题</span>
              <strong>{contract.question}</strong>
              <small>{contract.reason}</small>
            </div>
            <dl className="stock-analysis-page__evidence-contract-grid">
              <div>
                <dt>结论状态</dt>
                <dd>{contract.answerLabel}</dd>
              </div>
              <div>
                <dt>候选复核</dt>
                <dd>{contract.canReviewCandidates ? "可复核" : "只读观察"}</dd>
              </div>
              <div>
                <dt>首要复核标的</dt>
                <dd>
                  {contract.topReviewStock && onOpenTopReviewStock ? (
                    <button
                      type="button"
                      className="stock-analysis-page__top-review-action"
                      aria-label={`打开 ${contract.topReviewStock} 复核详情`}
                      onClick={onOpenTopReviewStock}
                    >
                      {contract.topReviewStock}
                    </button>
                  ) : (
                    contract.topReviewStock ?? "暂无"
                  )}
                </dd>
              </div>
              <div>
                <dt>使用边界</dt>
                <dd>{contract.formalUseAllowed ? "正式口径可用" : "仅供观察"}</dd>
              </div>
            </dl>
            <div className="stock-analysis-page__evidence-contract-meta">
              <span>数据入口 {contract.routeLabel}</span>
              <span>结果口径 {contract.resultKindLabel}</span>
              {contract.includeLabel ? <span>{contract.includeLabel}</span> : null}
              <span>首要阻断 {contract.primaryBlocker ?? "无"}</span>
            </div>
          </section>
        ) : null}

        {sourceCells.length > 0 ? (
          <section
            className="stock-analysis-page__evidence-source-grid"
            data-testid="stock-analysis-api-evidence-strip"
            aria-label="供数与链路"
          >
            {sourceCells.map((item) => (
              <div key={item.key}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                {item.detail ? <small title={item.detail}>{item.detail}</small> : null}
              </div>
            ))}
          </section>
        ) : null}

        {digestContent}
        {closureContent}
        {railContent}

        {gapReleaseCards.length > 0 ? (
          <section
            className="stock-analysis-page__v6-gap-release-panel"
            data-testid="stock-analysis-v6-gap-release-panel"
            aria-label="数据缺口与补证条件"
          >
            <header className="stock-analysis-page__evidence-section-head">
              <h2>数据缺口与补证条件</h2>
              <p>明确缺口影响，以及补齐证据后的复核边界</p>
            </header>
            <div className="stock-analysis-page__v6-gap-release-grid">
              {gapReleaseCards.map((card) => (
                <article
                  key={card.key}
                  className="stock-analysis-page__v6-gap-release-card"
                  data-tone={card.tone}
                  title={card.evidence}
                >
                  <strong>{card.label}</strong>
                  <span>
                    {card.statusLabel}，{card.releaseLabel}
                  </span>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {endpointLedgerItems.length > 0 || gateStateVariantRows.length > 0 ? (
          <section
            className="stock-analysis-page__v6-audit-detail"
            data-testid="stock-analysis-v6-audit-disclosure"
            aria-label="供数链路与门禁状态审计"
          >
            <section
              className="stock-analysis-page__v6-endpoint-ledger-section"
              data-testid="stock-analysis-v6-endpoint-ledger-section"
              aria-label="供数与链路状态"
            >
              <header className="stock-analysis-page__evidence-section-head">
                <h2>供数与链路</h2>
                <p>默认只读主包，重型诊断按需加载；页面不伪造缺失模块</p>
              </header>
              <div className="stock-analysis-page__v6-endpoint-ledger-grid">
                {endpointLedgerItems.map((item) => (
                  <article
                    key={item.key}
                    className="stock-analysis-page__v6-endpoint-ledger-card"
                    data-tone={item.tone}
                  >
                    <div>
                      <strong>{item.label}</strong>
                      <b>{item.status}</b>
                    </div>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
            </section>
            <section
              className="stock-analysis-page__v6-state-variants-section"
              data-testid="stock-analysis-v6-state-variants-section"
              aria-label="门禁状态稿"
            >
              <header className="stock-analysis-page__evidence-section-head">
                <h2>门禁状态稿</h2>
                <p>页面必须显式暴露的异常状态，避免把观察结果当正式结论</p>
              </header>
              <div className="stock-analysis-page__v6-state-variant-grid">
                {gateStateVariantRows.map((item) => (
                  <article
                    key={item.key}
                    className="stock-analysis-page__v6-state-variant-card"
                    data-tone={item.tone}
                  >
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
            </section>
          </section>
        ) : null}

        {readinessItems.length > 0 ? (
          <section
            className="stock-analysis-page__api-readiness-section"
            data-testid="stock-analysis-api-readiness-shell"
            aria-label="规则准备度与数据缺口"
          >
            <header className="stock-analysis-page__evidence-section-head">
              <h2>规则准备度与数据缺口</h2>
              <p>{readinessItems.length} 项明细</p>
            </header>
            <div
              className="stock-analysis-page__api-readiness-strip"
              data-testid="stock-analysis-api-readiness-strip"
              aria-label="规则准备度"
            >
              {readinessItems.map((item) => (
                <div key={item.key} data-status={item.status}>
                  <h3>
                    <span>{item.label}</span>
                    <b>{item.statusLabel}</b>
                  </h3>
                  <strong className="stock-analysis-page__api-readiness-metric" title={item.metric}>
                    {item.metric}
                  </strong>
                  <p title={item.summary}>{item.summary}</p>
                  <small title={`${item.inputsLabel} · ${item.detail}`}>
                    <span>{item.inputsLabel}</span>
                    <em>{item.detail}</em>
                  </small>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </details>
  );
}
