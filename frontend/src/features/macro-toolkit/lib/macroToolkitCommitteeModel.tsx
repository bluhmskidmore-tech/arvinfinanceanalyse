import {
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapability,
  MacroToolkitCapabilityResult,
  MacroToolkitHasonStrategy,
  MacroToolkitPayload,
  MacroToolkitRuntimeStatusPayload,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitSourceCheck,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { isEvidenceBookRowPending } from "./macroToolkitCommitteeEvidence";
import { formatCommitteeReadinessBlocker } from "./macroToolkitDataHealthSupport";
import {
  committeeSignoffLaneItems,
  committeeWorkQueueExecutionHref,
  receiptMatchesCommitteeEvidence,
} from "./macroToolkitPageModel";
import type {
  MacroToolkitActionReceipt,
  MacroToolkitCommitteeChecklistItem,
  MacroToolkitCommitteePackItem,
  MacroToolkitCommitteeWorkQueueItem,
  MacroToolkitDeepEvidenceQueueItem,
  MacroToolkitEvidenceBookRow,
  MacroToolkitGovernanceFocusItem,
  MacroToolkitRepairItem,
} from "./macroToolkitPageModel";
import { formatPercent, statusLabel } from "./macroToolkitPanelShared";

export function buildMacroToolkitCommitteeModel({
  actionReceipts,
  analysis,
  availableScriptCount,
  capabilityItems,
  confirmedReceiptIds,
  crisisScoreResult,
  degradedResultCount,
  degradedStrategyCount,
  fullRealStrategyCount,
  hasonStrategy,
  isCoreAnalysis,
  observationRuntimeSummary,
  omittedEntries,
  payload,
  primaryRepairItem,
  primarySignal,
  readyCapabilityCount,
  repairItemCount,
  runtimeSections,
  scripts,
  showOperations,
  sourceChecks,
  sourceHitCount,
  strategyDescription,
  strategySummaries,
  strategySupplyState,
  wiredCapabilityCount,
}: {
  actionReceipts: MacroToolkitActionReceipt[];
  analysis: MacroToolkitAnalysisPayload | undefined;
  availableScriptCount: number;
  capabilityItems: MacroToolkitCapability[];
  confirmedReceiptIds: Set<string>;
  crisisScoreResult: MacroToolkitCapabilityResult | null;
  degradedResultCount: number;
  degradedStrategyCount: number;
  fullRealStrategyCount: number;
  hasonStrategy: MacroToolkitHasonStrategy | null;
  isCoreAnalysis: boolean;
  observationRuntimeSummary: string;
  omittedEntries: [string, string][];
  payload: MacroToolkitPayload | undefined;
  primaryRepairItem: MacroToolkitRepairItem | null;
  primarySignal: MacroToolkitSignalCard | null;
  readyCapabilityCount: number;
  repairItemCount: number;
  runtimeSections: MacroToolkitRuntimeStatusPayload["deferred_sections"];
  scripts: MacroToolkitScriptRecord[];
  showOperations: boolean;
  sourceChecks: MacroToolkitSourceCheck[];
  sourceHitCount: number;
  strategyDescription: string;
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  wiredCapabilityCount: number;
}) {
  const completedDataHealthReceipt =
    actionReceipts.find((receipt) =>
      receiptMatchesCommitteeEvidence(
        receipt,
        "data-health",
        "#macro-toolkit-data-health-detail",
        "数据运营负责人",
      ),
    ) ?? null;
  const hasDataHealthRepairReceipt = Boolean(completedDataHealthReceipt);
  const completedDataHealthReceiptConfirmed = completedDataHealthReceipt
    ? confirmedReceiptIds.has(completedDataHealthReceipt.id)
    : false;
  const hasDataHealthRepairReceiptPending = hasDataHealthRepairReceipt && !completedDataHealthReceiptConfirmed;
  const hasDataHealthHardBlocker = repairItemCount > 0 && !completedDataHealthReceipt;
  const committeeReadinessStatus = hasDataHealthHardBlocker
    ? "暂缓提交"
    : hasDataHealthRepairReceiptPending
      ? "待复核回执"
      : isCoreAnalysis
        ? "待补全证据"
        : "可进入复核";
  const committeeReadinessBlocker = hasDataHealthHardBlocker
    ? formatCommitteeReadinessBlocker(primaryRepairItem, repairItemCount)
    : hasDataHealthRepairReceiptPending
      ? "数据健康回执待复核"
      : completedDataHealthReceiptConfirmed
        ? "数据健康签核已确认"
    : isCoreAnalysis
      ? observationRuntimeSummary
      : degradedResultCount
        ? `${degradedResultCount} 个结果降级`
        : "无关键卡点";
  const committeeReadinessOwner = repairItemCount ? "数据运营负责人" : isCoreAnalysis ? "宏观策略负责人" : "数据运营负责人";
  const committeeReadinessHref = repairItemCount
    ? "#macro-toolkit-data-health-detail"
    : isCoreAnalysis
      ? "#macro-toolkit-analysis-detail"
      : "#macro-toolkit-tool-execution-detail";
  const committeeReadinessAction = completedDataHealthReceiptConfirmed
    ? "查看签核证据"
    : hasDataHealthRepairReceiptPending
    ? "复核数据健康回执"
    : repairItemCount
      ? "处理数据缺口"
      : isCoreAnalysis
        ? "查看证据覆盖"
        : "进入操作台";
  const workflowAnalysisState = isCoreAnalysis ? `core · 待完整分析 ${runtimeSections.length}` : "full · 完整分析";
  const governanceFocusItems: MacroToolkitGovernanceFocusItem[] = [
    {
      key: "evidence",
      label: "证据覆盖",
      focusTitle: "证据覆盖",
      href: "#macro-toolkit-analysis-detail",
      value: formatPercent(analysis?.coverage.hit_rate),
      detail: `${analysis?.coverage.hit_count ?? 0}/${analysis?.coverage.indicator_count ?? 0} 指标命中`,
      status: analysis ? (analysis.coverage.hit_count === analysis.coverage.indicator_count ? "available" : "core-not-full") : "data-pending",
      tone: analysis?.coverage.hit_rate === 1 ? "positive" : "neutral",
      icon: <SafetyCertificateOutlined />,
    },
    {
      key: "data-health",
      label: "待处理数据",
      focusTitle: "数据健康",
      href: "#macro-toolkit-data-health-detail",
      value: repairItemCount,
      detail: repairItemCount ? "存在待处理数据项，详见数据健康" : "数据健康无待处理项",
      status: repairItemCount ? "data-pending" : "available",
      tone: repairItemCount ? "missing" : "positive",
      icon: <ExclamationCircleOutlined />,
    },
    {
      key: "analysis-scope",
      label: "分析口径",
      focusTitle: "分析口径",
      href: "#macro-toolkit-analysis-detail",
      value: isCoreAnalysis ? "核心" : "完整",
      detail: workflowAnalysisState,
      status: isCoreAnalysis ? "core-not-full" : "available",
      tone: isCoreAnalysis ? "missing" : "positive",
      icon: <ClockCircleOutlined />,
    },
    {
      key: "execution",
      label: "能力闭环",
      focusTitle: "能力闭环",
      href: "#macro-toolkit-tool-execution-detail",
      value: `${readyCapabilityCount}/${capabilityItems.length || 0}`,
      detail: `${wiredCapabilityCount} 项已接到页面/API`,
      status:
        capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length && wiredCapabilityCount === capabilityItems.length
          ? "available"
          : "non-formal",
      tone:
        capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length && wiredCapabilityCount === capabilityItems.length
          ? "positive"
          : "neutral",
      icon: <ThunderboltOutlined />,
    },
  ];
  const evidenceBookRows: MacroToolkitEvidenceBookRow[] = analysis
    ? [
        {
          key: "primary-signal",
          subject: "主信号",
          support: primarySignal
            ? `${primarySignal.title} · ${primarySignal.stance} · ${primarySignal.score ?? "缺分"}`
            : "主信号待返回",
          gap: isCoreAnalysis ? observationRuntimeSummary : `${analysis.coverage.hit_count}/${analysis.coverage.indicator_count} 指标命中`,
          owner: "宏观策略负责人",
          href: "#macro-toolkit-analysis-detail",
        },
        {
          key: "data-health",
          subject: "数据健康",
          support: `${formatPercent(analysis.coverage.hit_rate)} 覆盖 · ${sourceHitCount}/${sourceChecks.length || 0} 源命中`,
          gap: repairItemCount ? `${repairItemCount} 项待处理` : "无待处理项",
          owner: "数据运营负责人",
          href: "#macro-toolkit-data-health-detail",
        },
        {
          key: "strategy-supply",
          subject: "策略供数",
          support:
            strategySupplyState === "loaded"
              ? `完整链路 ${fullRealStrategyCount}/${strategySummaries.length}`
              : `策略供数 ${statusLabel(strategySupplyState)}`,
          gap:
            strategySupplyState === "failed"
              ? "读取失败"
              : degradedStrategyCount
                ? `${degradedStrategyCount} 项降级`
                : strategySummaries.length
                  ? "无供数降级"
                  : "等待策略摘要",
          owner: "权益策略负责人",
          href: "#macro-toolkit-strategy-detail",
        },
        {
          key: "tool-execution",
          subject: "工具执行",
          support: showOperations
            ? `脚本 ${availableScriptCount}/${scripts.length} · 能力 ${readyCapabilityCount}/${capabilityItems.length || 0}`
            : "只读观察，不暴露操作",
          gap:
            degradedResultCount > 0
              ? `${degradedResultCount} 个结果降级或不可用`
              : capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length
                ? "能力闭环完成"
                : "能力闭环待确认",
          owner: "数据运营负责人",
          href: "#macro-toolkit-tool-execution-detail",
        },
      ]
    : [];
  const committeePackItems: MacroToolkitCommitteePackItem[] = evidenceBookRows.map((row) => {
    const isBlocking = row.key === "data-health" && hasDataHealthHardBlocker;
    const isPending = !isBlocking && isEvidenceBookRowPending(row.support, row.gap);
    const receipt =
      actionReceipts.find((item) =>
        receiptMatchesCommitteeEvidence(
          item,
          row.key,
          row.href,
          row.owner,
        ),
      ) ?? null;
    return {
      ...row,
      packSubject: row.key === "primary-signal" ? "结论底稿" : row.subject,
      status: isBlocking ? "blocking" : isPending ? "pending" : "archived",
      statusLabel: receipt
        ? confirmedReceiptIds.has(receipt.id)
          ? "已签核"
          : "回执待复核"
        : isBlocking
          ? "阻止提交"
          : isPending
            ? "待确认"
            : "已归档",
      receipt,
      receiptConfirmed: receipt ? confirmedReceiptIds.has(receipt.id) : false,
    };
  });
  const committeePackItemByKey = new Map(committeePackItems.map((item) => [item.key, item]));
  const committeeChecklistItems: MacroToolkitCommitteeChecklistItem[] = committeePackItems.map((item) => {
    const status = item.status === "blocking" ? "block" : item.status === "pending" ? "pending" : "pass";
    const actions = {
      block: item.key === "data-health" ? "先完成数据缺口复核" : "先解除提交阻断",
      pending: item.key === "strategy-supply" ? "确认策略供数链路" : item.key === "tool-execution" ? "复核工具执行结果" : "补齐待确认材料",
      pass: "保留证据留痕",
    } satisfies Record<MacroToolkitCommitteeChecklistItem["status"], string>;
    return {
      ...item,
      condition: item.key === "primary-signal" ? "证据口径" : item.subject,
      status,
      statusLabel: status === "block" ? "未通过" : status === "pending" ? "待确认" : "已通过",
      action: actions[status],
    };
  });
  const committeePackReviewReadyCount = committeePackItems.filter(
    (item) => item.status === "archived" || item.receipt,
  ).length;
  const committeePackReceiptReviewCount = committeePackItems.filter((item) => item.receipt && !item.receiptConfirmed).length;
  const deepEvidenceQueueItems: MacroToolkitDeepEvidenceQueueItem[] = [
    {
      key: "strategy",
      label: "策略证据",
      value:
        strategySupplyState === "loaded"
          ? `完整链路 ${fullRealStrategyCount}/${strategySummaries.length}`
          : statusLabel(strategySupplyState),
      detail: degradedStrategyCount ? `${degradedStrategyCount} 项降级待复核` : strategyDescription,
      href: "#macro-toolkit-strategy-detail",
    },
    {
      key: "crisis-score",
      label: "Crisis Score",
      value: crisisScoreResult ? statusLabel(crisisScoreResult.status) : "待完整分析",
      detail: isCoreAnalysis ? observationRuntimeSummary : `${degradedResultCount} 个结果降级或不可用`,
      href: "#macro-toolkit-analysis-detail",
    },
    {
      key: "hason",
      label: "Hason",
      value: hasonStrategy ? statusLabel(hasonStrategy.status) : "待完整分析",
      detail: hasonStrategy
        ? `模块 ${hasonStrategy.readiness.ready_modules}/${hasonStrategy.readiness.total_modules} · 缺失脚本 ${hasonStrategy.readiness.missing_script_count}`
        : observationRuntimeSummary,
      href: "#macro-toolkit-analysis-detail",
    },
    {
      key: "scripts",
      label: "脚本与产物",
      value: `${payload?.output_files.length ?? 0} 个产物`,
      detail: showOperations ? `脚本 ${availableScriptCount}/${scripts.length} · ${omittedEntries.length} 个未纳入` : "只读观察",
      href: "#macro-toolkit-script-artifact-detail",
    },
  ];
  const committeeWorkQueueItems: MacroToolkitCommitteeWorkQueueItem[] = committeeChecklistItems
    .filter((item) => item.status !== "pass")
    .map((item) => ({
      ...item,
      priorityLabel: item.status === "block" ? "阻断项" : "待确认项",
      executionHref: committeeWorkQueueExecutionHref(item),
    }));
  const isCommitteeChecklistItemOpen = (item: MacroToolkitCommitteeChecklistItem) =>
    !committeePackItemByKey.get(item.key)?.receiptConfirmed;
  const committeeLeadChecklistItem =
    committeeChecklistItems.find(
      (item) => item.status === "block" && item.href === committeeReadinessHref && isCommitteeChecklistItemOpen(item),
    ) ??
    committeeChecklistItems.find((item) => item.status === "block" && isCommitteeChecklistItemOpen(item)) ??
    committeeChecklistItems.find(
      (item) => item.status !== "pass" && item.href === committeeReadinessHref && isCommitteeChecklistItemOpen(item),
    ) ??
    committeeChecklistItems.find((item) => item.status === "pending" && isCommitteeChecklistItemOpen(item)) ??
    null;
  const committeeWorkQueueBlockCount = committeeWorkQueueItems.filter((item) => item.status === "block").length;
  const committeeSignoffLaneSummaryItems = committeeSignoffLaneItems(
    committeeWorkQueueItems,
    actionReceipts,
    confirmedReceiptIds,
  );
  const committeeSignoffReadyCount = committeeSignoffLaneSummaryItems.filter(
    (item) => item.status === "approved" || item.status === "reviewed",
  ).length;
  const isCommitteeFinalSignoffReady =
    committeePackItems.length > 0 &&
    committeePackReviewReadyCount === committeePackItems.length &&
    committeeSignoffReadyCount === committeeSignoffLaneSummaryItems.length &&
    committeeWorkQueueBlockCount === 0 &&
    committeePackReceiptReviewCount === 0;
  const committeeFinalSignoffStatus = isCommitteeFinalSignoffReady ? "可提交复核" : "暂缓提交";
  const committeeFinalResidualRiskCount = committeeWorkQueueBlockCount + committeePackReceiptReviewCount;
  const committeeFinalPackValue = committeePackItems.length
    ? `${committeePackReviewReadyCount}/${committeePackItems.length}`
    : "待确认";
  const committeeFinalSignoffValue = committeePackItems.length
    ? `${committeeSignoffReadyCount}/${committeeSignoffLaneSummaryItems.length}`
    : "待确认";
  const committeeFinalResidualRiskValue = committeePackItems.length ? String(committeeFinalResidualRiskCount) : "待确认";
  const committeeFinalReceiptReviewValue = committeePackItems.length ? String(committeePackReceiptReviewCount) : "待确认";
  const committeeLeadPackItem = committeeLeadChecklistItem
    ? committeePackItemByKey.get(committeeLeadChecklistItem.key) ?? null
    : null;
  const committeeLeadReceipt = committeeLeadPackItem?.receipt ?? null;
  const committeeLeadExecutionHref = committeeLeadChecklistItem
    ? committeeWorkQueueExecutionHref(committeeLeadChecklistItem)
    : null;
  const hasCommitteeOpenSubmissionLane = Boolean(
    committeeLeadChecklistItem &&
      !hasDataHealthHardBlocker &&
      !hasDataHealthRepairReceiptPending &&
      !isCoreAnalysis &&
      !committeeLeadPackItem?.receiptConfirmed,
  );
  const committeeDecisionStatus = hasCommitteeOpenSubmissionLane
    ? committeeLeadReceipt
      ? "待复核回执"
      : "待确认闭环"
    : committeeReadinessStatus;
  const committeeDecisionBlocker =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? committeeLeadReceipt
        ? `${committeeLeadChecklistItem.condition}回执待复核`
        : `${committeeLeadChecklistItem.condition}待确认`
      : committeeReadinessBlocker;
  const committeeDecisionOwner =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem ? committeeLeadChecklistItem.owner : committeeReadinessOwner;
  const committeeFinalSignoffOwner = isCommitteeFinalSignoffReady ? "主席复核" : committeeDecisionOwner;
  const committeeDecisionHref =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? (committeeLeadReceipt?.evidenceHref ?? committeeLeadExecutionHref ?? committeeLeadChecklistItem.href)
      : committeeReadinessHref;
  const committeeDecisionAction =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? committeeLeadReceipt
        ? `复核${committeeLeadChecklistItem.condition}回执`
        : committeeLeadChecklistItem.action
      : committeeReadinessAction;
  const committeeFinalGateOutcome = isCommitteeFinalSignoffReady ? "准入提交" : "未达提交标准";
  return {
    committeeChecklistItems,
    committeeDecisionAction,
    committeeDecisionBlocker,
    committeeDecisionHref,
    committeeDecisionStatus,
    committeeFinalGateOutcome,
    committeeFinalPackValue,
    committeeFinalReceiptReviewValue,
    committeeFinalResidualRiskValue,
    committeeFinalSignoffOwner,
    committeeFinalSignoffStatus,
    committeeFinalSignoffValue,
    committeeLeadChecklistItem,
    committeeLeadReceipt,
    committeePackItemByKey,
    completedDataHealthReceipt,
    deepEvidenceQueueItems,
    governanceFocusItems,
    hasCommitteeOpenSubmissionLane,
    hasDataHealthRepairReceiptPending,
  };
}
