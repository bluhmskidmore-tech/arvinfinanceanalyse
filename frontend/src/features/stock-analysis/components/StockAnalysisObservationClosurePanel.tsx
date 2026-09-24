import type { StockObservationClosureSummary } from "../lib/stockAnalysisPageModel";

function toneColorToTextClass(tone: string) {
  switch (tone) {
    case "positive":
      return "text-success-600";
    case "negative":
      return "text-danger-600";
    case "warning":
      return "text-warning-600";
    default:
      return "text-default-700";
  }
}

/** Evidence-layer observation closure controls: unresolved reasons and next evidence actions. */
export function StockAnalysisObservationClosurePanel({
  closureSummary,
}: {
  closureSummary: StockObservationClosureSummary;
}) {
  return (
    <section
      className="stock-analysis-page__fs-card"
      data-testid="stock-analysis-observation-closure-panel"
      data-tone={closureSummary.tone}
      aria-label="观测闭环总控"
    >
      <header className="stock-analysis-page__fs-card-head">
        <div className="stock-analysis-page__min-w-0">
          <p className="stock-analysis-page__dh-section-eyebrow">观测闭环总控</p>
          <h2>{closureSummary.headline}</h2>
          <p className="stock-analysis-page__dh-section-desc">
            接口链路 {closureSummary.endpointLoadedCount}/{closureSummary.endpointTotal} · 待复核项{" "}
            {closureSummary.unresolvedReasons.length}
          </p>
        </div>
        <span
          className="stock-analysis-page__fs-card-pill"
          data-formal-use={closureSummary.formalUseAllowed ? "true" : "false"}
        >
          正式用途：{closureSummary.formalUseAllowed ? "是" : "否"}
        </span>
      </header>

      <dl className="stock-analysis-page__evidence-contract-grid">
        <div>
          <dt>接口链路</dt>
          <dd className="stock-analysis-page__tabular">{`${closureSummary.endpointLoadedCount}/${closureSummary.endpointTotal}`}</dd>
        </div>
        <div>
          <dt>待复核项</dt>
          <dd className="stock-analysis-page__tabular">{closureSummary.unresolvedReasons.length}</dd>
        </div>
        <div>
          <dt>读取失败</dt>
          <dd className="stock-analysis-page__tabular">{closureSummary.endpointErrorCount}</dd>
        </div>
        <div>
          <dt>元信息缺口</dt>
          <dd className="stock-analysis-page__tabular">{closureSummary.metaMissingCount}</dd>
        </div>
      </dl>

      <details className="stock-analysis-page__fs-rail-card">
        <summary className="cursor-pointer text-sm font-semibold text-foreground">未闭环明细</summary>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-foreground">未闭环原因</h3>
            <ul data-testid="stock-analysis-observation-closure-reasons" className="flex flex-col gap-2">
              {closureSummary.unresolvedReasons.slice(0, 5).map((reason) => (
                <li key={reason.key} data-tone={reason.tone} className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-default-600">{reason.endpointLabel}</span>
                  <strong className={`font-semibold ${toneColorToTextClass(reason.tone)}`}>{reason.displayText}</strong>
                  <small className="hidden" title={reason.fieldPath}>字段来源已记录</small>
                </li>
              ))}
              {closureSummary.unresolvedReasons.length === 0 ? (
                <li data-tone="neutral" className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-default-600">证据项</span>
                  <strong className="font-semibold text-default-500">暂无新增待复核项</strong>
                  <small className="text-xs text-default-400">仍保留观测边界，不代表正式通过</small>
                </li>
              ) : null}
            </ul>
          </div>
          <div>
            <h3 className="mb-3 text-sm font-semibold text-foreground">下一步证据动作</h3>
            <ul data-testid="stock-analysis-observation-closure-actions" className="flex flex-col gap-2">
              {closureSummary.nextEvidenceActions.slice(0, 5).map((action) => (
                <li key={action.key} className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-default-600">{action.source}</span>
                  <strong className="font-semibold text-foreground">{action.actionText}</strong>
                  <small className="hidden" title={action.fieldPath}>证据字段已定位</small>
                </li>
              ))}
              {closureSummary.nextEvidenceActions.length === 0 ? (
                <li className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-default-600">治理</span>
                  <strong className="font-semibold text-foreground">等待业务 owner 审批与人工复核</strong>
                  <small className="text-xs text-default-400 ml-1">{closureSummary.approvalStatus}</small>
                </li>
              ) : null}
            </ul>
          </div>
        </div>
      </details>
    </section>
  );
}
