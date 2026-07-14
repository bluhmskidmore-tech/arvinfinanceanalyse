import { useEffect, useState, type ReactNode } from "react";
import type {
  StockObservationClosureSummary,
  WorkbenchDataDigest,
  WorkbenchFact,
} from "../lib/stockAnalysisPageModel";

export type StockAnalysisLedgerMetric = {
  label: string;
  value: string;
  detail?: string;
  tone?: "positive" | "neutral" | "warning" | "negative";
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
  auditStripText?: string;
  pagePurposeText?: string;
  supplementItems?: StockAnalysisDecisionSupplementItem[];
  decisionMemoTiles?: StockAnalysisDecisionMemoTile[];
  supplyStatusRows?: StockAnalysisSupplyStatusRow[];
  workbenchContract?: StockAnalysisWorkbenchContractSummary;
  onOpenTopReviewStock?: () => void;
  sourceGateTone?: string;
  sourceGateLabel?: string;
  sourceGateDetail?: string;
  sourceVersion?: string;
  digest?: WorkbenchDataDigest;
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
  closureSummary?: StockObservationClosureSummary;
  railContent?: ReactNode;
};

function StockWorkbenchFactCard({
  fact,
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  fact: WorkbenchFact;
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  const isInteractive = typeof onFactSelect === "function";
  const isActive = isInteractive && activeFactId === fact.id;

  const toneColors: Record<string, string> = {
    positive: "bg-success-50 text-success-700 border-success-200 dark:bg-success-900/20 border-l-success",
    negative: "bg-danger-50 text-danger-700 border-danger-200 dark:bg-danger-900/20 border-l-danger",
    warning: "bg-warning-50 text-warning-700 border-warning-200 dark:bg-warning-900/20 border-l-warning",
    watch: "bg-secondary-50 text-secondary-700 border-secondary-200 dark:bg-secondary-900/20 border-l-secondary",
    ok: "bg-success-50 text-success-700 border-success-200 dark:bg-success-900/20 border-l-success",
    neutral: "bg-default-50 text-default-700 border-default-200 dark:bg-default-900/20 border-l-default",
  };

  const toneClass = toneColors[fact.tone || "neutral"] || toneColors.neutral;
  const activeClass = isActive ? "ring-2 ring-primary ring-offset-1 border-primary-500" : "";
  const interactiveClass = isInteractive ? "hover:bg-default-100 dark:hover:bg-default-800 cursor-pointer transition-colors" : "";

  const content = (
    <div className="p-3 gap-1 overflow-hidden">
      <span className="text-xs font-medium text-default-500 truncate">{fact.label}</span>
      <strong className="text-lg font-bold text-foreground truncate">{fact.value}</strong>
      {fact.subValue ? <small className="text-xs text-default-400 truncate">{fact.subValue}</small> : null}
      <em className="hidden" title={fact.sourcePath}>字段来源已记录</em>
    </div>
  );

  if (isInteractive) {
    return (
      <button
        type="button"
        className={`w-full border-l-4 border-y border-r text-left ${toneClass} ${activeClass} ${interactiveClass}`}
        data-testid={`stock-analysis-workbench-fact-${fact.id}`}
        data-tone={fact.tone}
        data-primary={fact.isPrimary ? "true" : "false"}
        data-active={isActive ? "true" : "false"}
        aria-current={isActive ? "true" : undefined}
        aria-controls={factControlsId}
        onClick={() => onFactSelect(fact)}
      >
        {content}
      </button>
    );
  }

  return (
    <article
      className={`w-full border-l-4 border-y border-r ${toneClass}`}
      data-testid={`stock-analysis-workbench-fact-${fact.id}`}
      data-tone={fact.tone}
      data-primary={fact.isPrimary ? "true" : "false"}
      data-active="false"
    >
      {content}
    </article>
  );
}

function StockWorkbenchFactGrid({
  title,
  eyebrow,
  facts,
  layout = "default",
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  title: string;
  eyebrow?: string;
  facts: WorkbenchFact[];
  layout?: "primary" | "secondary" | "slow" | "default";
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  if (facts.length === 0) return null;

  const layoutClass = {
    primary: "grid-cols-2 sm:grid-cols-4 lg:grid-cols-5",
    secondary: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
    slow: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
    default: "grid-cols-2 sm:grid-cols-3",
  }[layout] || "grid-cols-2";

  return (
    <section className="mb-6 flex flex-col gap-3" data-layout={layout}>
      <div className="flex flex-col">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">{title}</h3>
        {eyebrow ? <p className="text-xs text-default-500">{eyebrow}</p> : null}
      </div>
      <div className={`grid gap-3 ${layoutClass}`} data-layout={layout}>
        {facts.map((fact) => (
          <StockWorkbenchFactCard
            key={fact.id}
            fact={fact}
            onFactSelect={onFactSelect}
            activeFactId={activeFactId}
            factControlsId={factControlsId}
          />
        ))}
      </div>
    </section>
  );
}

function sourceEvidenceLabel(item: StockAnalysisLedgerCell): string {
  if (item.key === "tables") return "来源覆盖";
  if (item.key === "evidence") return "证据覆盖";
  if (item.key === "rule") return "规则状态";
  if (item.key === "trace") return "追踪状态";
  return item.label;
}

function sourceEvidenceValue(item: StockAnalysisLedgerCell): string {
  if (item.key === "rule" && item.value !== "待返回") return "已签核";
  if (item.key === "trace" && item.value !== "待返回") return "已追踪";
  return item.value;
}

function sourceEvidenceDetail(item: StockAnalysisLedgerCell): string | undefined {
  if ((item.key === "rule" || item.key === "trace") && item.value !== "待返回") {
    return "完整来源见诊断";
  }
  return item.detail;
}

function StockWorkbenchDigest({
  digest,
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  digest: WorkbenchDataDigest;
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  const auditFacts = [...digest.candidateFacts, ...digest.evidenceFacts];
  const hasAuditDetails = auditFacts.length > 0 || digest.slowFacts.length > 0;
  const hasSelectedAuditFact =
    activeFactId != null &&
    [...auditFacts, ...digest.slowFacts].some((fact) => fact.id === activeFactId);
  const [auditOpen, setAuditOpen] = useState(hasSelectedAuditFact);

  useEffect(() => {
    if (hasSelectedAuditFact) {
      setAuditOpen(true);
    }
  }, [hasSelectedAuditFact]);

  return (
    <section
      className="flex flex-col gap-4 rounded-xl bg-default-50/50 p-3 border border-default-200/50"
      data-testid="stock-analysis-workbench-digest"
      aria-label="首屏供数摘要"
    >
      <StockWorkbenchFactGrid
        title="核心口径"
        eyebrow="核心事实"
        facts={digest.primaryFacts}
        layout="primary"
        onFactSelect={onFactSelect}
        activeFactId={activeFactId}
        factControlsId={factControlsId}
      />
      {hasAuditDetails ? (
        <section className="flex flex-col gap-4" data-layout="audit">
          <button
            type="button"
            className="flex flex-col items-start gap-1 rounded-lg border border-default-200 bg-white dark:bg-default-100 p-3 text-left transition-colors hover:bg-default-100 dark:hover:bg-default-200"
            aria-expanded={auditOpen}
            aria-controls="stock-analysis-workbench-audit-details"
            onClick={() => setAuditOpen((current) => !current)}
          >
            <span className="text-xs font-medium text-default-500">完整证据账本 / 审计明细</span>
            <strong className="text-lg font-bold text-foreground">{auditOpen ? "收起" : "展开"}</strong>
            <small className="text-xs text-default-400">展开查看候选、接口与慢链路补证。</small>
          </button>
          {auditOpen ? (
            <div id="stock-analysis-workbench-audit-details" data-testid="stock-analysis-workbench-audit-details" className="flex flex-col gap-6 pt-2">
              <StockWorkbenchFactGrid
                title="候选与证据"
                eyebrow="候选与接口证据"
                facts={auditFacts}
                layout="secondary"
                onFactSelect={onFactSelect}
                activeFactId={activeFactId}
                factControlsId={factControlsId}
              />
              <StockWorkbenchFactGrid
                title="慢接口补证"
                eyebrow="非阻塞补证"
                facts={digest.slowFacts}
                layout="slow"
                onFactSelect={onFactSelect}
                activeFactId={activeFactId}
                factControlsId={factControlsId}
              />
            </div>
          ) : null}
        </section>
      ) : null}
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
  auditStripText,
  pagePurposeText,
  supplementItems = [],
  decisionMemoTiles = [],
  supplyStatusRows = [],
  workbenchContract,
  onOpenTopReviewStock,
  sourceGateTone = "watch",
  sourceGateLabel = "来源核验",
  sourceGateDetail = "质量 需复核 回退快照",
  digest,
  onFactSelect,
  activeFactId,
  factControlsId,
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
  const [sourceOpen, setSourceOpen] = useState(false);
  const sourceGateReviewText = sourceGateTone === "watch" ? "部分缺失 仅分析使用" : "";
  const detailShellOpen = activeFactId != null;

  const toneColorToTextClass = (tone: string) => {
    switch (tone) {
      case "positive": return "text-success-600";
      case "negative": return "text-danger-600";
      case "warning": return "text-warning-600";
      default: return "text-default-700";
    }
  };

  return (
    <>
      <section
        className="stock-analysis-page__dh-hero flex w-full flex-col gap-4 p-3 lg:p-4"
        data-testid="stock-analysis-tailwind-cockpit"
        aria-label="策略复核决策"
      >
        <div className="flex flex-col gap-4" data-testid="stock-analysis-decision-panel">
          <span className="sr-only" title={`数据日期 ${asOfLabel}`}>
            {asOfLabel}
          </span>
          <span className="sr-only" title={`请求日期 ${requestedAsOfLabel ?? "默认"}`}>
            {requestedAsOfLabel ?? "默认"}
          </span>
          <span className="sr-only">
            数据日 {asOfLabel} 数据日期 {asOfLabel} 请求日期 {requestedAsOfLabel ?? "默认"}
          </span>
          <section className="sr-only" data-testid="stock-analysis-decision-memo">
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

          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between" data-testid="stock-analysis-queue-report-head">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-primary">{kicker}</span>
              <h1 className="text-xl font-bold tracking-tight text-foreground">{headline}</h1>
              <p className="max-w-2xl text-sm text-default-500">{lead}</p>
              {supplementItems.length > 0 ? (
                <div
                  className="mt-1 flex flex-wrap items-center gap-3"
                  data-testid="stock-analysis-decision-supplement-strip"
                  aria-label="首屏补充信息"
                >
                  {supplementItems.map((item) => (
                    <span key={item.label} title={item.detail} className="flex items-baseline gap-1.5 text-xs">
                      <small className="text-default-500">{item.label}</small>
                      <strong className="font-semibold text-foreground">{item.value}</strong>
                      {item.detail ? <em className="text-default-400 not-italic">{item.detail}</em> : null}
                    </span>
                  ))}
                </div>
              ) : null}
              {auditStripText ? (
                <div
                  className="stock-analysis-page__gate-audit-strip"
                  data-testid="stock-analysis-gate-audit-strip"
                  role="status"
                >
                  {auditStripText}
                </div>
              ) : null}
              {workbenchContract ? (
                <section
                  className="mt-2 flex flex-col gap-3 rounded-lg border border-default-200 bg-default-50/70 p-3"
                  data-testid="stock-analysis-workbench-contract"
                  aria-label="页面复核业务契约"
                >
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-semibold uppercase tracking-wider text-default-500">
                      页面核心问题
                    </span>
                    <strong className="text-sm font-semibold text-foreground">{workbenchContract.question}</strong>
                    <small className="text-xs text-default-500">{workbenchContract.reason}</small>
                  </div>
                  <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <div className="flex flex-col">
                      <dt className="text-xs text-default-500">结论状态</dt>
                      <dd className="text-sm font-semibold text-foreground">
                        {workbenchContract.answerLabel}
                      </dd>
                    </div>
                    <div className="flex flex-col">
                      <dt className="text-xs text-default-500">候选复核</dt>
                      <dd className="text-sm font-semibold text-foreground">
                        {workbenchContract.canReviewCandidates ? "可复核" : "只读观察"}
                      </dd>
                    </div>
                    <div className="flex flex-col">
                      <dt className="text-xs text-default-500">首要复核标的</dt>
                      <dd className="text-sm font-semibold text-foreground">
                        {workbenchContract.topReviewStock && onOpenTopReviewStock ? (
                          <button
                            type="button"
                            className="stock-analysis-page__top-review-action"
                            aria-label={`打开 ${workbenchContract.topReviewStock} 复核详情`}
                            onClick={onOpenTopReviewStock}
                          >
                            {workbenchContract.topReviewStock}
                          </button>
                        ) : (
                          workbenchContract.topReviewStock ?? "暂无"
                        )}
                      </dd>
                    </div>
                    <div className="flex flex-col">
                      <dt className="text-xs text-default-500">使用边界</dt>
                      <dd className="text-sm font-semibold text-foreground">
                        {workbenchContract.formalUseAllowed ? "正式口径可用" : "仅供观察"}
                      </dd>
                    </div>
                  </dl>
                  <div className="flex flex-wrap gap-2 text-xs text-default-500">
                    <span>数据入口 {workbenchContract.routeLabel}</span>
                    <span>结果口径 {workbenchContract.resultKindLabel}</span>
                    {workbenchContract.includeLabel ? <span>{workbenchContract.includeLabel}</span> : null}
                    <span>首要阻断 {workbenchContract.primaryBlocker ?? "无"}</span>
                  </div>
                </section>
              ) : null}
            </div>

            <dl aria-label="首屏复核摘要" className="flex shrink-0 flex-wrap gap-3 rounded-sm bg-default-100/50 p-3">
              {metrics.map((item) => (
                <div key={item.label} className="flex flex-col" data-tone={item.tone ?? "neutral"}>
                  <dt className="text-xs font-medium text-default-500">{item.label}</dt>
                  <dd className="text-lg font-bold text-foreground">
                    <span>{item.value}</span>
                    {item.detail ? <small className="text-xs text-default-400 mt-1">{item.detail}</small> : null}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          {digest || closureSummary ? (
            <details
              className="rounded-lg border border-default-200 bg-default-50/50 p-3"
              data-testid="stock-analysis-evidence-detail-shell"
              open={detailShellOpen || undefined}
            >
              <summary className="cursor-pointer text-sm font-semibold text-foreground">
                <span>证据与口径明细</span>
                <small className="ml-2 text-xs font-normal text-default-500">核心口径 / 条件 / 链路 / 审计明细</small>
              </summary>
              <div className="mt-3 flex flex-col gap-4">
                {digest ? (
                  <StockWorkbenchDigest
                    digest={digest}
                    onFactSelect={onFactSelect}
                    activeFactId={activeFactId}
                    factControlsId={factControlsId}
                  />
                ) : null}

                {closureSummary ? (
                  <section
                    className="flex flex-col gap-4 rounded-xl border-l-4 p-4 bg-default-50/50 border-default-300 dark:border-default-700"
                    data-testid="stock-analysis-observation-closure-panel"
                    data-tone={closureSummary.tone}
                    aria-label="观测闭环总控"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex flex-col gap-1">
                        <span className="text-xs font-semibold uppercase tracking-wider text-default-500">观测闭环总控</span>
                        <h2 className="text-lg font-bold text-foreground">{closureSummary.headline}</h2>
                        <p className="text-sm text-default-600">
                          接口链路 {closureSummary.endpointLoadedCount}/{closureSummary.endpointTotal} · 待复核项{" "}
                          {closureSummary.unresolvedReasons.length}
                        </p>
                      </div>
                      <span
                        className="rounded-full bg-default-100 px-3 py-1 text-xs font-semibold text-default-700"
                        data-formal-use={closureSummary.formalUseAllowed ? "true" : "false"}
                      >
                        正式用途：{closureSummary.formalUseAllowed ? "是" : "否"}
                      </span>
                    </div>

                    <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-3 border-y border-default-200">
                      <div className="flex flex-col">
                        <dt className="text-xs text-default-500">接口链路</dt>
                        <dd className="text-lg font-semibold">{`${closureSummary.endpointLoadedCount}/${closureSummary.endpointTotal}`}</dd>
                      </div>
                      <div className="flex flex-col">
                        <dt className="text-xs text-default-500">待复核项</dt>
                        <dd className="text-lg font-semibold">{closureSummary.unresolvedReasons.length}</dd>
                      </div>
                      <div className="flex flex-col">
                        <dt className="text-xs text-default-500">读取失败</dt>
                        <dd className="text-lg font-semibold">{closureSummary.endpointErrorCount}</dd>
                      </div>
                      <div className="flex flex-col">
                        <dt className="text-xs text-default-500">元信息缺口</dt>
                        <dd className="text-lg font-semibold">{closureSummary.metaMissingCount}</dd>
                      </div>
                    </dl>

                    <details className="rounded-lg border border-default-200 bg-white/70 p-3 dark:bg-default-100">
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
                ) : null}

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="stock-analysis-market-context-strip">
                  {conditionCells.map((item, index) => (
                    <div key={item.key} className="bg-default-50/50" data-testid={legacyMarketContextIds[index]} data-tone={item.tone ?? "neutral"}>
                      <div className="p-4 flex flex-col gap-1 items-center text-center">
                        <span className="text-xs font-medium text-default-500">{item.label}</span>
                        <strong className="text-lg font-bold text-foreground">{item.value}</strong>
                        {item.detail ? <small className="text-xs text-default-400">{item.detail}</small> : null}
                      </div>
                    </div>
                  ))}
                </div>

                <section className="flex flex-col items-start gap-4" aria-label="供数与链路">
                  <button
                    type="button"
                    className="text-sm font-medium text-primary hover:underline focus:outline-none"
                    onClick={() => setSourceOpen((current) => !current)}
                    aria-expanded={sourceOpen}
                    aria-controls="stock-analysis-api-evidence-strip"
                  >
                    {sourceOpen ? "收起供数与链路明细" : "展开供数与链路明细"}
                  </button>
                  {sourceOpen ? (
                    <div
                      className="grid w-full grid-cols-2 md:grid-cols-4 gap-4 rounded-lg bg-default-100/50 p-4"
                      data-testid="stock-analysis-api-evidence-strip"
                      id="stock-analysis-api-evidence-strip"
                      aria-label="真实后端 API 证据"
                    >
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-default-500">来源状态</span>
                        <strong className="text-sm font-semibold text-foreground">完整来源见诊断</strong>
                        <small className="text-xs text-default-400">首屏仅保留摘要，不暴露完整来源版本。</small>
                      </div>
                      {sourceCells.map((item) => {
                        const detail = sourceEvidenceDetail(item);
                        return (
                          <div key={item.key} className="flex flex-col gap-1">
                            <span className="text-xs text-default-500">{sourceEvidenceLabel(item)}</span>
                            <strong className="text-sm font-semibold text-foreground">{sourceEvidenceValue(item)}</strong>
                            {detail ? <small className="text-xs text-default-400">{detail}</small> : null}
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </section>
              </div>
            </details>
          ) : null}

          <section className="sr-only" data-testid="stock-analysis-kpi-section" aria-label="选股快照">
            <div data-equity-kpi-card="true" data-testid="stock-analysis-kpi-market-state">
              市场状态 温和
            </div>
            <div data-equity-kpi-card="true" data-testid="stock-analysis-kpi-review-queue">
              复核队列
            </div>
          </section>

          {supplyStatusRows.length > 0 ? (
            <section
              className="sr-only"
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
            className="sr-only"
            data-testid="stock-analysis-source-gate-strip"
            data-tone={sourceGateTone}
          >
            来源核验 {sourceGateLabel} {sourceGateReviewText} {sourceGateDetail}
          </div>
          {pagePurposeText ? (
            <div className="sr-only" data-testid="stock-analysis-page-purpose">
              {pagePurposeText}
            </div>
          ) : null}
        </div>
      </section>

      {railContent ?? (
        <aside
          className="stock-analysis-page__api-ledger-rail flex w-full shrink-0 flex-col gap-4 rounded-xl bg-default-50 p-5 border border-default-200/50"
          data-testid="stock-analysis-first-screen-rail"
          aria-label="判断依据"
        >
            <div className="flex items-center justify-between border-b border-default-200 pb-3">
              <strong className="text-base font-bold text-foreground">判断依据</strong>
              <span className="font-mono text-sm text-default-500">{asOfLabel}</span>
            </div>
            <dl className="flex flex-col gap-4" data-testid="stock-analysis-evidence-ledger">
              <div className="sr-only">
                <button data-testid="stock-analysis-home-rail-diagnostic-entry" type="button" aria-expanded="false">
                  诊断
                </button>
              </div>
              <div className="sr-only" data-testid="stock-analysis-closed-loop-summary">
                证据账本 闭环摘要
              </div>
              <div className="sr-only" data-testid="stock-analysis-boundary-rail">
                数据口径与边界
              </div>
              {railRows.map((item) => (
                <div key={item.label} className="flex flex-col">
                  <dt className="text-sm text-default-500">{item.label}</dt>
                  <dd className="text-base font-semibold text-foreground">{item.value}</dd>
                  {item.detail ? <small className="text-xs text-default-400 mt-0.5">{item.detail}</small> : null}
                </div>
              ))}
            </dl>
          </aside>
      )}
    </>
  );
}
