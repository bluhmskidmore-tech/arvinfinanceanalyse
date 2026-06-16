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

type ClosedLoopRailProps = ComponentProps<typeof StockAnalysisClosedLoopSummaryRail>;
type RiskExitProps = ComponentProps<typeof StockAnalysisRiskExitSection>;
type BoundaryRailProps = ComponentProps<typeof StockAnalysisBoundaryRail>;

type StockAnalysisEvidenceLedgerRailProps = {
  asOfLabel: string;
  statusLabel: string;
  gateStatusLabel: string;
  evidenceCount: number;
  boundaryCount: number;
  leadCandidateName?: string | null;
  boundaryIssueCount: number;
  sourceVersionSummary: string;
  basisLabel: string;
  qualityLabel: string;
  updatedAtLabel: string;
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
  leadCandidateName,
  boundaryIssueCount,
  sourceVersionSummary,
  basisLabel,
  qualityLabel,
  updatedAtLabel,
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
            <dt>依据</dt>
            <dd>{`证据 ${evidenceCount}，边界缺口 ${boundaryCount}`}</dd>
          </div>
          <div>
            <dt>下一步</dt>
            <dd>{leadCandidateName ? `先复核${leadCandidateName}` : "等待候选"}</dd>
          </div>
          <div>
            <dt>待办</dt>
            <dd>{`${boundaryIssueCount} 项边界`}</dd>
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
