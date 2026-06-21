import type { ComponentProps } from "react";

import { StockAnalysisBoundaryRail } from "./StockAnalysisBoundaryRail";
import { StockAnalysisClosedLoopSummaryRail } from "./StockAnalysisClosedLoopRail";
import { StockAnalysisRiskExitSection } from "./StockAnalysisRiskExitRows";
import {
  SA_SHELL_NUM,
  SA_SHELL_RAIL,
  SA_SHELL_REVIEW_RAIL,
  SA_SHELL_REVIEW_RAIL_HEAD,
} from "../lib/stockAnalysisPageChrome";
import type { StockEndpointEvidenceItem } from "../lib/stockAnalysisPageModel";

type ClosedLoopRailProps = ComponentProps<typeof StockAnalysisClosedLoopSummaryRail>;
type RiskExitProps = ComponentProps<typeof StockAnalysisRiskExitSection>;
type BoundaryRailProps = ComponentProps<typeof StockAnalysisBoundaryRail>;

type StockAnalysisEvidenceLedgerRailProps = {
  asOfLabel: string;
  statusLabel: string;
  gateStatusLabel: string;
  evidenceCount: number;
  boundaryCount: number;
  availableOutputsLabel: string;
  primaryGapLabel: string;
  leadCandidateName?: string | null;
  boundaryIssueCount: number;
  sourceVersionSummary: string;
  basisLabel: string;
  qualityLabel: string;
  updatedAtLabel: string;
  endpointItems: StockEndpointEvidenceItem[];
  diagnosticsOpen: boolean;
  onOpenDiagnostics: () => void;
  onCloseDiagnostics: () => void;
  closedLoopSummary: ClosedLoopRailProps["summary"] | null;
  railRiskTone: ClosedLoopRailProps["riskTone"];
  riskTriggeredCount: number;
  riskWatchCount: number;
  reviewQueueCount: number;
  nextActionLabel: string;
  nextActionFullLabel: string;
  riskRows: RiskExitProps["rows"];
  confluenceError: boolean;
  riskExitUnsupported: RiskExitProps["unsupportedOutput"];
  onOpenRiskDetail: RiskExitProps["onOpenRiskDetail"];
  boundaryItems: BoundaryRailProps["boundaryItems"];
  boundarySummary: BoundaryRailProps["boundarySummary"];
  strategyPayload: BoundaryRailProps["strategyPayload"];
};

export function StockAnalysisEvidenceLedgerRail({
  asOfLabel,
  statusLabel,
  gateStatusLabel,
  evidenceCount,
  boundaryCount,
  availableOutputsLabel,
  primaryGapLabel,
  leadCandidateName,
  boundaryIssueCount,
  sourceVersionSummary,
  basisLabel,
  qualityLabel,
  updatedAtLabel,
  endpointItems,
  diagnosticsOpen,
  onOpenDiagnostics,
  onCloseDiagnostics,
  closedLoopSummary,
  railRiskTone,
  riskTriggeredCount,
  riskWatchCount,
  reviewQueueCount,
  nextActionLabel,
  nextActionFullLabel,
  riskRows,
  confluenceError,
  riskExitUnsupported,
  onOpenRiskDetail,
  boundaryItems,
  boundarySummary,
  strategyPayload,
}: StockAnalysisEvidenceLedgerRailProps) {
  return (
    <aside
      className={`${SA_SHELL_RAIL} stock-analysis-page__decision-rail`}
      aria-label="风险与数据可信度"
      data-testid="stock-analysis-first-screen-rail"
    >
      <article className={SA_SHELL_REVIEW_RAIL} data-testid="stock-analysis-evidence-ledger">
        <div className={SA_SHELL_REVIEW_RAIL_HEAD}>
          <span>
            判断依据
            <span className="stock-analysis-page__visually-hidden">证据账本</span>
          </span>
          <b className={SA_SHELL_NUM}>{asOfLabel}</b>
        </div>
        <dl className="stock-analysis-page__home-rail-list" data-testid="stock-analysis-home-rail-decision">
          <div className="stock-analysis-page__home-rail-list-primary">
            <dt>结论</dt>
            <dd>{`${statusLabel}，${gateStatusLabel}`}</dd>
          </div>
          <div>
            <dt>关键证据</dt>
            <dd>{`证据 ${evidenceCount}，边界缺口 ${boundaryCount}`}</dd>
          </div>
          <div>
            <dt>可用输出</dt>
            <dd>{availableOutputsLabel}</dd>
          </div>
          <div>
            <dt>主要缺口</dt>
            <dd>{primaryGapLabel}</dd>
          </div>
          <div>
            <dt>风险退出</dt>
            <dd>{riskExitUnsupported ? "阻断" : riskTriggeredCount > 0 ? `触发 ${riskTriggeredCount}` : `触发 0，观察 ${riskWatchCount}`}</dd>
          </div>
          <div>
            <dt>下一步</dt>
            <dd>{leadCandidateName ? `先复核${leadCandidateName}` : "等待候选"}</dd>
          </div>
        </dl>
        <div className="stock-analysis-page__home-rail-data-note" data-testid="stock-analysis-home-rail-data-note">
          <h3>数据口径</h3>
          <p>来源：{sourceVersionSummary}</p>
          <p>口径：{basisLabel}</p>
          <p>质量：{qualityLabel}</p>
          <p>更新时间：{updatedAtLabel}</p>
          <p className="stock-analysis-page__home-rail-data-status">数据已更新 · 复核读数</p>
        </div>
        {endpointItems.length > 0 ? (
          <section
            className="stock-analysis-page__endpoint-evidence"
            data-testid="stock-analysis-endpoint-evidence-rail"
            aria-label="接口证据状态"
          >
            <div className="stock-analysis-page__endpoint-evidence-head">
              <h3>接口证据</h3>
              <span>{endpointItems.length} 条链路</span>
            </div>
            <ul>
              {endpointItems.map((item) => (
                <li
                  key={item.key}
                  data-tone={item.tone}
                  data-testid={`stock-analysis-endpoint-evidence-${item.key}`}
                >
                  <div>
                    <span>{item.label}</span>
                    <strong>{item.statusLabel}</strong>
                  </div>
                  <p>{item.detail}</p>
                  <small>{item.dateLabel}</small>
                  <small>{item.issueLabel}</small>
                  <small>{item.metaLabel}</small>
                  <small>{item.traceLabel}</small>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <button
          type="button"
          className="stock-analysis-page__home-rail-diagnostic-entry"
          data-testid="stock-analysis-home-rail-diagnostic-entry"
          aria-expanded={diagnosticsOpen}
          onClick={onOpenDiagnostics}
        >
          <span>完整诊断</span>
          <strong>
            {closedLoopSummary?.referenceRating.label ?? "闭环待确认"} · {boundaryIssueCount} 项边界
          </strong>
        </button>
        {closedLoopSummary ? (
          <StockAnalysisClosedLoopSummaryRail
            summary={closedLoopSummary}
            riskTone={railRiskTone}
            riskTriggeredCount={riskTriggeredCount}
            boundaryIssueCount={boundaryIssueCount}
            reviewQueueCount={reviewQueueCount}
            nextActionLabel={nextActionLabel}
            nextActionFullLabel={nextActionFullLabel}
          />
        ) : null}
        <StockAnalysisRiskExitSection
          rows={riskRows}
          riskTriggeredCount={riskTriggeredCount}
          riskWatchCount={riskWatchCount}
          confluenceError={confluenceError}
          unsupportedOutput={riskExitUnsupported}
          onOpenRiskDetail={onOpenRiskDetail}
        />
        <StockAnalysisBoundaryRail
          boundaryItems={boundaryItems}
          boundarySummary={boundarySummary}
          strategyPayload={strategyPayload}
          diagnosticsDrawerOpen={diagnosticsOpen}
          onOpenDiagnostics={onOpenDiagnostics}
          onCloseDiagnostics={onCloseDiagnostics}
          showInlineDiagnosticsAction={false}
        />
      </article>
    </aside>
  );
}
