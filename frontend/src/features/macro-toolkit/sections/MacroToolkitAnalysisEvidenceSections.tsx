import {
  ClockCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Alert, Button, Tag } from "antd";
import type { ReactNode } from "react";

import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitRuntimeStatusPayload,
  MacroToolkitSignalCard,
} from "../../../api/macroToolkitClient";
import { DataStatusStrip } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import {
  formatObservationDeferredSectionLabel,
  repairItemFocusKey,
} from "../lib/macroToolkitDataHealthSupport";
import {
  formatAnalysisBasisLabel,
  formatObservationEvidence,
  formatObservationRecommendation,
  formatObservationSignalStance,
  formatObservationSignalTitle,
  formatQualityFlagLabel,
} from "../lib/macroToolkitDisplayFormat";
import { compactText, statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import type {
  MacroToolkitActionReceipt,
  MacroToolkitGovernanceFocusKey,
  MacroToolkitRepairItem,
  RefreshFeedbackTone,
} from "../lib/macroToolkitPageModel";
import {
  MacroToolkitDataHealthPanel,
  MacroToolkitDataHealthSummary,
} from "./MacroToolkitDataHealthSections";
import { ReadinessTile } from "./MacroToolkitPrimitives";

export function MacroToolkitAnalysisEvidenceFlow({
  analysis,
  analysisMeta,
  showOperations,
  isAuditTargetActive,
  observationBoundaryPanel,
  runtimeSections,
  isCoreAnalysis,
  observationRuntimeSummary,
  showFullAnalysisActionInRuntime,
  isLoadingFullAnalysis,
  loadFullAnalysis,
  focusedRepairKey,
  completedDataHealthReceipt,
  confirmedReceiptIds,
  setFocusedRepairKey,
  refreshMacroSourceBackfill,
  reviewFullAnalysisRepair,
  refreshingSourceAlias,
  sourceBackfillResult,
  sourceBackfillFeedbackTone,
  sourceBackfillError,
  primarySignal,
  dataFreshnessDetail,
  missingIndicatorCount,
  degradedResultCount,
  limitsDetails,
}: {
  analysis: MacroToolkitAnalysisPayload;
  analysisMeta: ResultMeta | undefined;
  showOperations: boolean;
  isAuditTargetActive: (href: string, governanceKeys?: MacroToolkitGovernanceFocusKey[]) => boolean;
  observationBoundaryPanel: ReactNode;
  runtimeSections: MacroToolkitRuntimeStatusPayload["deferred_sections"];
  isCoreAnalysis: boolean;
  observationRuntimeSummary: string;
  showFullAnalysisActionInRuntime: boolean;
  isLoadingFullAnalysis: boolean;
  loadFullAnalysis: (options?: { force?: boolean }) => Promise<ApiEnvelope<MacroToolkitAnalysisPayload> | null>;
  focusedRepairKey: string | null;
  completedDataHealthReceipt: MacroToolkitActionReceipt | null;
  confirmedReceiptIds: Set<string>;
  setFocusedRepairKey: (key: string | null) => void;
  refreshMacroSourceBackfill: (item: MacroToolkitRepairItem) => Promise<void>;
  reviewFullAnalysisRepair: (item: MacroToolkitRepairItem) => Promise<unknown>;
  refreshingSourceAlias: string | null;
  sourceBackfillResult: string | null;
  sourceBackfillFeedbackTone: RefreshFeedbackTone;
  sourceBackfillError: string | null;
  primarySignal: MacroToolkitSignalCard | null;
  dataFreshnessDetail: string;
  missingIndicatorCount: number;
  capabilityResults: MacroToolkitCapabilityResult[];
  degradedResultCount: number;
  limitsDetails?: ReactNode;
}) {
  return (
    <>
      <div
        id="macro-toolkit-analysis-detail"
        data-testid="macro-toolkit-analysis-detail"
        className={`macro-toolkit-anchor-target ${
          isAuditTargetActive("#macro-toolkit-analysis-detail", ["evidence", "analysis-scope"])
            ? "macro-toolkit-anchor-target--active"
            : ""
        }`}
      />
      <section
        className={showOperations ? "macro-toolkit-analysis-stack" : "macro-toolkit-observation-evidence"}
        aria-label={showOperations ? undefined : "宏观观察证据与限制"}
      >
        {!showOperations ? (
          <div className="macro-toolkit-observation-evidence__head">
            <span>观察证据与限制</span>
            <div className="macro-toolkit-observation-evidence__legend">
              <span>运行状态</span>
              <span>数据健康</span>
              <span>投研总览</span>
            </div>
          </div>
        ) : null}
        <div
          className={
            showOperations ? "macro-toolkit-analysis-stack__body" : "macro-toolkit-observation-evidence__body"
          }
        >
          <section
            className={
              showOperations
                ? "macro-toolkit-evidence-review-flow"
                : "macro-toolkit-observation-evidence__contents"
            }
            aria-label={showOperations ? "分析证据与数据健康" : undefined}
          >
            <div
              className={
                showOperations
                  ? "macro-toolkit-evidence-review-flow__detail"
                  : "macro-toolkit-observation-evidence__contents"
              }
              aria-label={showOperations ? "分析证据详情" : undefined}
            >
              <DataStatusStrip className="macro-toolkit-status-strip">
                {showOperations ? (
                  <>
                    <span title={`读取口径：${analysisMeta?.basis ?? EM_DASH}`}>
                      <DatabaseOutlined /> {formatAnalysisBasisLabel(analysisMeta?.basis)}
                    </span>
                    <span title={`质量：${analysisMeta?.quality_flag ?? EM_DASH}`}>
                      <SafetyCertificateOutlined /> {formatQualityFlagLabel(analysisMeta?.quality_flag)}
                    </span>
                    <span title={`建议：${analysis.conclusion.recommended_action}`}>
                      <ThunderboltOutlined /> {compactText(analysis.conclusion.recommended_action, 24)}
                    </span>
                  </>
                ) : (
                  <>
                    <span title={`读取口径：${analysisMeta?.basis ?? EM_DASH}`}>
                      <DatabaseOutlined /> {formatAnalysisBasisLabel(analysisMeta?.basis)}
                    </span>
                    <span title="数据质量状态已记录，具体诊断保留在宏观工具页。">
                      <SafetyCertificateOutlined /> 质量状态已记录
                    </span>
                    <span title={formatObservationRecommendation(analysis.conclusion.recommended_action)}>
                      <ThunderboltOutlined /> {formatObservationRecommendation(analysis.conclusion.recommended_action)}
                    </span>
                  </>
                )}
              </DataStatusStrip>
              {!showOperations ? observationBoundaryPanel : null}

              <div className="macro-toolkit-runtime-strip" aria-label="宏观工具运行状态">
                {showOperations && runtimeSections.length ? (
                  runtimeSections.map((section) => (
                    <span key={section.key}>
                      <ClockCircleOutlined />
                      {formatObservationDeferredSectionLabel(section.label ?? section.key)} ·{" "}
                      <Tag color={statusColor(section.status)}>{statusLabel(section.status)}</Tag>
                    </span>
                  ))
                ) : (
                  <span>
                    <ClockCircleOutlined />
                    {showOperations ? (isCoreAnalysis ? "核心分析" : "完整分析") : isCoreAnalysis ? "待完整分析" : "完整分析"} ·{" "}
                    <Tag color={statusColor(isCoreAnalysis ? "deferred" : "complete")}>
                      {showOperations ? statusLabel(isCoreAnalysis ? "deferred" : "complete") : observationRuntimeSummary}
                    </Tag>
                  </span>
                )}
                {showFullAnalysisActionInRuntime ? (
                  <span className="macro-toolkit-runtime-strip__action">
                    下一步：
                    <Button
                      aria-label="查看完整分析"
                      size="small"
                      icon={<LineChartOutlined />}
                      loading={isLoadingFullAnalysis}
                      onClick={() => void loadFullAnalysis()}
                    >
                      查看完整分析
                    </Button>
                  </span>
                ) : null}
              </div>

              {limitsDetails ? (
                <details className="macro-toolkit-evidence-limits">
                  <summary>分析限制明细</summary>
                  <div className="macro-toolkit-evidence-limits__body">{limitsDetails}</div>
                </details>
              ) : null}

              {analysis.data_health ? (
                <div
                  id="macro-toolkit-data-health-detail"
                  data-testid="macro-toolkit-data-health-detail"
                  className={`macro-toolkit-anchor-target ${
                    isAuditTargetActive("#macro-toolkit-data-health-detail", ["data-health"])
                      ? "macro-toolkit-anchor-target--active"
                      : ""
                  }`}
                >
                  {showOperations ? (
                    <MacroToolkitDataHealthPanel
                      dataHealth={analysis.data_health}
                      showActions={showOperations}
                      focusedRepairKey={focusedRepairKey}
                      dataHealthReceipt={completedDataHealthReceipt}
                      dataHealthReceiptConfirmed={
                        completedDataHealthReceipt ? confirmedReceiptIds.has(completedDataHealthReceipt.id) : false
                      }
                      onRepairAction={(item) => {
                        setFocusedRepairKey(repairItemFocusKey(item));
                        if (item.action?.kind === "source_backfill_required") {
                          void refreshMacroSourceBackfill(item);
                          return;
                        }
                        if (item.action?.kind === "load_full_analysis") {
                          void reviewFullAnalysisRepair(item);
                          return;
                        }
                        void loadFullAnalysis({ force: item.scope === "full" });
                      }}
                      repairActionLoading={isLoadingFullAnalysis}
                      refreshingSourceAlias={refreshingSourceAlias}
                    />
                  ) : (
                    <MacroToolkitDataHealthSummary dataHealth={analysis.data_health} />
                  )}
                </div>
              ) : null}
              {sourceBackfillResult ? (
                <Alert type={sourceBackfillFeedbackTone} showIcon message={sourceBackfillResult} />
              ) : null}
              {sourceBackfillError ? <Alert type="error" showIcon message={sourceBackfillError} /> : null}

              {!showOperations ? (
                <div className="macro-toolkit-readiness-strip" aria-label="宏观工具投研总览">
                  <ReadinessTile
                    icon={<LineChartOutlined />}
                    label="主信号"
                    value={
                      primarySignal
                        ? `${formatObservationSignalTitle(primarySignal)} · ${formatObservationSignalStance(primarySignal)}`
                        : "缺失"
                    }
                    detail={formatObservationEvidence(primarySignal?.evidence)}
                    tone={primarySignal?.tone ?? "missing"}
                  />
                  <ReadinessTile
                    icon={<ClockCircleOutlined />}
                    label="数据新鲜度"
                    value={analysis.as_of_date ?? "缺失"}
                    detail={dataFreshnessDetail}
                    tone={missingIndicatorCount > 0 ? "neutral" : "positive"}
                  />
                  <ReadinessTile
                    icon={<ThunderboltOutlined />}
                    label="证据边界"
                    value="已记录"
                    detail="能力盘点留在证据追踪，不进入投研结论。"
                    tone={degradedResultCount > 0 ? "neutral" : "positive"}
                  />
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </section>
    </>
  );
}
