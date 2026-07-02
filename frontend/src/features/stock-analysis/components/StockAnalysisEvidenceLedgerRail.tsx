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
  gapCountLabel?: string;
  availableOutputsLabel: string;
  primaryGapLabel: string;
  leadCandidateName?: string | null;
  boundaryIssueCount: number;
  sourceVersionSummary: string;
  basisLabel: string;
  qualityLabel: string;
  updatedAtLabel: string;
  endpointItems: StockEndpointEvidenceItem[];
  focusedEndpointKey?: string | null;
  onEndpointSelect?: (key: string) => void;
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
  routeLabel?: string;
  resultKindLabel?: string;
  formalUseAllowed?: boolean;
};

export function StockAnalysisEvidenceLedgerRail({
  asOfLabel,
  statusLabel,
  gateStatusLabel,
  evidenceCount,
  boundaryCount,
  gapCountLabel,
  availableOutputsLabel,
  primaryGapLabel,
  leadCandidateName,
  boundaryIssueCount,
  sourceVersionSummary,
  basisLabel,
  qualityLabel,
  updatedAtLabel,
  endpointItems,
  focusedEndpointKey,
  onEndpointSelect,
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
  routeLabel = "/ui/market-data/stock-analysis/workbench",
  resultKindLabel = "market_data.stock_analysis.workbench",
  formalUseAllowed = false,
}: StockAnalysisEvidenceLedgerRailProps) {
  const endpointPreviewBaseItems = endpointItems.slice(0, 4);
  const focusedEndpointItem = focusedEndpointKey
    ? endpointItems.find((item) => item.key === focusedEndpointKey)
    : undefined;
  const endpointPreviewItems =
    focusedEndpointItem && !endpointPreviewBaseItems.some((item) => item.key === focusedEndpointItem.key)
      ? [...endpointPreviewBaseItems.slice(0, 3), focusedEndpointItem]
      : endpointPreviewBaseItems;
  const endpointPreviewKeySet = new Set(endpointPreviewItems.map((item) => item.key));
  const hiddenEndpointCount = endpointItems.length - endpointPreviewItems.length;

  return (
    <aside
      className={`${SA_SHELL_RAIL} stock-analysis-page__decision-rail`}
      aria-label="风险与数据可信度"
      data-testid="stock-analysis-first-screen-rail"
    >
      <article className={SA_SHELL_REVIEW_RAIL} data-testid="stock-analysis-evidence-ledger">
        <div className={SA_SHELL_REVIEW_RAIL_HEAD}>
          <span>
            补证清单
            <span className="stock-analysis-page__visually-hidden">证据账本</span>
            <small className="stock-analysis-page__evidence-ledger-subtitle">
              data_gaps / endpoint evidence / release gate
            </small>
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
            <dd>{`rows ${evidenceCount.toLocaleString("zh-CN")}，缺口 ${gapCountLabel ?? boundaryCount}`}</dd>
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
          <h3>接口口径</h3>
          <p>route：{routeLabel}</p>
          <p>result_kind：{resultKindLabel}</p>
          <p>formal_use_allowed={String(formalUseAllowed)}</p>
          <p className="stock-analysis-page__home-rail-data-status">
            {sourceVersionSummary} · {basisLabel} · {qualityLabel} · {updatedAtLabel}
          </p>
        </div>
        {endpointItems.length > 0 ? (
          <section
            id="stock-analysis-endpoint-evidence-rail"
            className="stock-analysis-page__endpoint-evidence"
            data-testid="stock-analysis-endpoint-evidence-rail"
            aria-label="证据链状态"
          >
            <div className="stock-analysis-page__endpoint-evidence-head">
              <h3>证据链状态</h3>
              <span>{endpointItems.length} 项证据 · 重点 {endpointPreviewItems.length}</span>
            </div>
            <ul>
              {endpointItems.map((item) => {
                const isFocused = focusedEndpointKey === item.key;
                const isPreview = endpointPreviewKeySet.has(item.key);
                return (
                  <li
                    key={item.key}
                    data-tone={item.tone}
                    data-active={isFocused ? "true" : "false"}
                    data-preview={isPreview ? "true" : "false"}
                    data-testid={`stock-analysis-endpoint-evidence-${item.key}`}
                  >
                    <button
                      type="button"
                      aria-current={isFocused ? "true" : undefined}
                      onClick={() => onEndpointSelect?.(item.key)}
                    >
                      <div>
                        <span>{item.label}</span>
                        <strong>{item.statusLabel}</strong>
                      </div>
                      {isPreview ? (
                        <>
                          <p>{item.detail}</p>
                          <small>{item.dateLabel}</small>
                          <small>{item.issueLabel}</small>
                        </>
                      ) : (
                        <p className="stock-analysis-page__endpoint-evidence-index-note">点击定位 · 查看完整诊断</p>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
            {hiddenEndpointCount > 0 ? (
              <button
                type="button"
                className="stock-analysis-page__endpoint-evidence-more"
                aria-label={`打开完整证据诊断，还有 ${hiddenEndpointCount} 项`}
                onClick={onOpenDiagnostics}
              >
                <span>完整诊断</span>
                <strong>{hiddenEndpointCount} 项仅索引</strong>
              </button>
            ) : null}
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
