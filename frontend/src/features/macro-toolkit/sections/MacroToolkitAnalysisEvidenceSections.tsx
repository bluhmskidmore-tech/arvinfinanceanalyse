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
  MacroToolkitRuntimeStatusPayload,
} from "../../../api/macroToolkitClient";
import { DataStatusStrip } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import {
  formatObservationDeferredSectionLabel,
  repairItemFocusKey,
} from "../lib/macroToolkitDataHealthSupport";
import {
  formatAnalysisBasisLabel,
  formatQualityFlagLabel,
} from "../lib/macroToolkitDisplayFormat";
import { compactText, statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import type {
  MacroToolkitActionReceipt,
  MacroToolkitGovernanceFocusKey,
  MacroToolkitRepairItem,
  RefreshFeedbackTone,
} from "../lib/macroToolkitPageModel";
import { MacroToolkitDataHealthPanel } from "./MacroToolkitDataHealthSections";

export function MacroToolkitAnalysisEvidenceFlow({
  analysis,
  analysisMeta,
  isAuditTargetActive,
  runtimeSections,
  isCoreAnalysis,
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
  limitsDetails,
}: {
  analysis: MacroToolkitAnalysisPayload;
  analysisMeta: ResultMeta | undefined;
  isAuditTargetActive: (href: string, governanceKeys?: MacroToolkitGovernanceFocusKey[]) => boolean;
  runtimeSections: MacroToolkitRuntimeStatusPayload["deferred_sections"];
  isCoreAnalysis: boolean;
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
      <section className="macro-toolkit-analysis-stack">
        <div className="macro-toolkit-analysis-stack__body">
          <section className="macro-toolkit-evidence-review-flow" aria-label="分析证据与数据健康">
            <div className="macro-toolkit-evidence-review-flow__detail" aria-label="分析证据详情">
              <DataStatusStrip className="macro-toolkit-status-strip">
                <span title={`读取口径：${analysisMeta?.basis ?? EM_DASH}`}>
                  <DatabaseOutlined /> {formatAnalysisBasisLabel(analysisMeta?.basis)}
                </span>
                <span title={`质量：${analysisMeta?.quality_flag ?? EM_DASH}`}>
                  <SafetyCertificateOutlined /> {formatQualityFlagLabel(analysisMeta?.quality_flag)}
                </span>
                <span title={`建议：${analysis.conclusion.recommended_action}`}>
                  <ThunderboltOutlined /> {compactText(analysis.conclusion.recommended_action, 24)}
                </span>
              </DataStatusStrip>

              <div className="macro-toolkit-runtime-strip" aria-label="宏观工具运行状态">
                {runtimeSections.length ? (
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
                    {isCoreAnalysis ? "核心分析" : "完整分析"} ·{" "}
                    <Tag color={statusColor(isCoreAnalysis ? "deferred" : "complete")}>
                      {statusLabel(isCoreAnalysis ? "deferred" : "complete")}
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
                  <MacroToolkitDataHealthPanel
                    dataHealth={analysis.data_health}
                    showActions
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
                </div>
              ) : null}
              {sourceBackfillResult ? (
                <Alert type={sourceBackfillFeedbackTone} showIcon message={sourceBackfillResult} />
              ) : null}
              {sourceBackfillError ? <Alert type="error" showIcon message={sourceBackfillError} /> : null}
            </div>
          </section>
        </div>
      </section>
    </>
  );
}
