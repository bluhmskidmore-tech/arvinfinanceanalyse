import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type SetStateAction,
} from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitCffexMemberRankStatus,
  MacroToolkitChoiceStockRefreshStatus,
  MacroToolkitCommodityFuturesHealthStatus,
  MacroToolkitMacroEtfStrategySnapshot,
  MacroToolkitPayload,
  MacroToolkitScriptRecord,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSignalCard,
  MacroToolkitStrategySummariesPayload,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { MT_SHELL_MAIN } from "../lib/macroToolkitPageChrome";
import type { MacroToolkitCommitteeModel } from "../lib/macroToolkitCommitteeModel";
import {
  formatBusinessEvidenceList,
  formatSize,
  groupLabel,
} from "../lib/macroToolkitDisplayFormat";
import {
  MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE,
  governanceFocusFromEvidenceHref,
} from "../lib/macroToolkitPageModel";
import type { MacroToolkitGovernanceFocusKey } from "../lib/macroToolkitPageModel";
import { MacroToolkitCapabilityResultsSection } from "../sections/MacroToolkitCapabilityCards";
import {
  MacroToolkitExecutionReceiptWorkspace,
  MacroToolkitOperationsConsolePanel,
} from "../sections/MacroToolkitExecutionSections";
import { compactText, statusLabel } from "../lib/macroToolkitPanelShared";
import {
  MacroToolkitCommitteeDecisionAction,
  MacroToolkitDeepEvidenceRailCard,
  MacroToolkitGovernanceGatePanel,
  MacroToolkitInvestmentBriefPanel,
  MacroToolkitOperationsBand,
} from "../sections/MacroToolkitGovernanceSections";
import { MacroToolkitIndicatorSection } from "../sections/MacroToolkitIndicatorSections";
import { MacroToolkitRiskSection } from "../sections/MacroToolkitRiskSections";
import { MacroToolkitSignalSection } from "../sections/MacroToolkitSignalSections";
import { MacroToolkitStrategySection } from "../sections/MacroToolkitStrategySections";
import type { MacroToolkitDeferredContentModel } from "./useMacroToolkitDeferredContent";
import type { MacroToolkitOperationActionsModel } from "./useMacroToolkitOperationActions";

// 运维与证据层的折叠壳：用原生 details 承载，子内容 DOM 常驻，折叠只影响可见性，
// 不做条件渲染，避免破坏 hash 深链与既有 testid 断言。
// open 由状态推导：阻断级异常（读取失败、依赖阻断、执行失败、资产校验失败）自动展开；
// 常态运维计数（待补项、降级模型数）只进摘要，不触发展开。
function MacroToolkitOpsBlock({
  blockKey,
  title,
  chips,
  blocking,
  forceOpen,
  children,
}: {
  blockKey: string;
  title: string;
  chips: string[];
  blocking: boolean;
  forceOpen: boolean;
  children: ReactNode;
}) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  useEffect(() => {
    // 「展开全部」/打印/深链落到本块时清掉手动折叠态，让强制展开生效。
    if (forceOpen) {
      setManualOpen(null);
    }
  }, [forceOpen]);
  const open = manualOpen ?? (forceOpen || blocking);
  return (
    <details
      className="macro-toolkit-ops-block"
      data-testid={`macro-toolkit-ops-block-${blockKey}`}
      data-ops-blocking={blocking ? "true" : "false"}
      open={open}
      onToggle={(event) => setManualOpen(event.currentTarget.open)}
    >
      <summary className="macro-toolkit-ops-block__summary">
        <span className="macro-toolkit-ops-block__title">{title}</span>
        <span className="macro-toolkit-ops-block__chips">
          {chips.map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </span>
        {blocking ? <span className="macro-toolkit-ops-block__flag">需处理</span> : null}
      </summary>
      <div className="macro-toolkit-ops-block__body">{children}</div>
    </details>
  );
}

type MacroToolkitOpsBlockEntry = {
  key: string;
  title: string;
  chips: string[];
  blocking: boolean;
  anchors: string[];
  minStage: number;
  content: ReactNode;
};

// 宏观工具（toolkit 模式）壳：只负责工具模式的布局与运维面板装配。
// 主列按信息分层排两段：前段业务观察与结论（01…07 常展开），
// 后段运维与证据（运维 01…06 默认折叠），中间插一条分层界标。
// 数据编排（查询、派生、操作 hook、投委会模型）仍留在页面主体。
export function MacroToolkitOperationsView({
  analysis,
  analysisMeta,
  payload,
  scripts,
  scriptsQuery,
  strategyQuery,
  capabilityResults,
  crisisScoreResult,
  visibleSignalCards,
  availableScriptCount,
  sourceChecks,
  sourceHitCount,
  isCoreAnalysis,
  isLoadingFullAnalysis,
  loadFullAnalysis,
  strategyDescription,
  choiceStockRefresh,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  strategySummaries,
  shadowPortfolioReport,
  macroEtfStrategy,
  hasRealStrategyData,
  cffexStatus,
  commodityStatus,
  omittedEntries,
  selectedScript,
  filteredScripts,
  selectedGroup,
  setSelectedGroup,
  setSelectedName,
  selectedEvidenceHref,
  setSelectedEvidenceHref,
  selectedExecutionHref,
  setSelectedExecutionHref,
  selectedGovernanceFocus,
  setSelectedGovernanceFocus,
  focusDataHealthRepair,
  isOperationActionBusy,
  commodityRefreshDisabled,
  commodityRefreshActionLabel,
  shouldShowCommodityPermissionNotice,
  operationActions,
  committeeModel,
  deferredContent,
  cockpitSection,
  analysisFailedAlert,
  fullAnalysisErrorAlert,
  initialAnalysisLoadingSection,
  analysisEvidenceFlow,
  crisisEvidenceSection,
  modelSignalMatrixSection,
  modelChainSection,
  hasonStrategySection,
  reportBundleSection,
}: {
  analysis: MacroToolkitAnalysisPayload | undefined;
  analysisMeta: ResultMeta | undefined;
  payload: MacroToolkitPayload | undefined;
  scripts: MacroToolkitScriptRecord[];
  scriptsQuery: UseQueryResult<ApiEnvelope<MacroToolkitPayload>>;
  strategyQuery: UseQueryResult<ApiEnvelope<MacroToolkitStrategySummariesPayload>>;
  capabilityResults: MacroToolkitCapabilityResult[];
  crisisScoreResult: MacroToolkitCapabilityResult | null;
  visibleSignalCards: MacroToolkitSignalCard[];
  availableScriptCount: number;
  sourceChecks: MacroToolkitPayload["source_checks"];
  sourceHitCount: number;
  isCoreAnalysis: boolean;
  isLoadingFullAnalysis: boolean;
  loadFullAnalysis: (options?: { force?: boolean }) => Promise<unknown>;
  strategyDescription: string;
  choiceStockRefresh: MacroToolkitChoiceStockRefreshStatus | null;
  strategySupplyState: "loading" | "failed" | "loaded";
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  strategySummaries: MacroToolkitStrategySummary[];
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
  macroEtfStrategy: MacroToolkitMacroEtfStrategySnapshot | null;
  hasRealStrategyData: boolean;
  cffexStatus: MacroToolkitCffexMemberRankStatus | null;
  commodityStatus: MacroToolkitCommodityFuturesHealthStatus | null;
  omittedEntries: Array<[string, string]>;
  selectedScript: MacroToolkitScriptRecord | null;
  filteredScripts: MacroToolkitScriptRecord[];
  selectedGroup: string;
  setSelectedGroup: Dispatch<SetStateAction<string>>;
  setSelectedName: Dispatch<SetStateAction<string | null>>;
  selectedEvidenceHref: string | null;
  setSelectedEvidenceHref: Dispatch<SetStateAction<string | null>>;
  selectedExecutionHref: string | null;
  setSelectedExecutionHref: Dispatch<SetStateAction<string | null>>;
  selectedGovernanceFocus: MacroToolkitGovernanceFocusKey;
  setSelectedGovernanceFocus: Dispatch<SetStateAction<MacroToolkitGovernanceFocusKey>>;
  focusDataHealthRepair: () => void;
  isOperationActionBusy: boolean;
  commodityRefreshDisabled: boolean;
  commodityRefreshActionLabel: string;
  shouldShowCommodityPermissionNotice: boolean;
  operationActions: MacroToolkitOperationActionsModel;
  committeeModel: MacroToolkitCommitteeModel;
  deferredContent: MacroToolkitDeferredContentModel;
  cockpitSection: ReactNode;
  analysisFailedAlert: ReactNode;
  fullAnalysisErrorAlert: ReactNode;
  initialAnalysisLoadingSection: ReactNode;
  analysisEvidenceFlow: ReactNode;
  crisisEvidenceSection: ReactNode;
  modelSignalMatrixSection: ReactNode;
  modelChainSection: ReactNode;
  hasonStrategySection: ReactNode;
  reportBundleSection: ReactNode;
}) {
  const {
    actionReceipt,
    actionReceipts,
    chainRunError,
    chainRunResult,
    commodityEvidenceReloadMessage,
    commodityPermission,
    commodityRefreshError,
    commodityRefreshResult,
    commodityRefreshRun,
    commodityShortfallChanges,
    commodityShortfallEstimates,
    commoditySuggestedSelection,
    confirmActionReceipt,
    isRefreshingCffex,
    isRefreshingChoiceStock,
    isRefreshingCommodity,
    isRunning,
    isRunningChain,
    refreshCffexMemberRank,
    refreshChoiceStock,
    refreshCommodityFutures,
    refreshError,
    refreshFeedbackTone,
    refreshResult,
    runError,
    runResult,
    runScriptChain,
    runSelectedScript,
    selectedCommodityProducts,
    setCommodityEvidenceReloadMessage,
    setCommodityRefreshError,
    setCommodityRefreshResult,
    setCommodityRefreshRun,
    setCommodityShortfallChanges,
    setCommodityShortfallEstimates,
    setCommoditySuggestedSelection,
    setSelectedCommodityProducts,
    stockRefreshError,
    stockRefreshResult,
  } = operationActions;
  const {
    committeeChecklistItems,
    committeeDecisionAction,
    committeeDecisionBlocker,
    committeeDecisionHref,
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
  } = committeeModel;
  const {
    deferredContentSentinelRef,
    deferredContentStage,
    handleDeferredContentLinkClick,
    operationsLayerExpanded,
    receiptTechnicalDetailsExpanded,
    setReceiptTechnicalDetailsExpanded,
  } = deferredContent;

  const groupOptions = useMemo(
    () => [
      { value: "all", label: "全部分组" },
      ...[...(payload?.groups ?? [])].sort().map((group) => ({
        value: group,
        label: groupLabel(group),
      })),
    ],
    [payload?.groups],
  );
  const outputDetail = payload?.output_files.length
    ? `${payload.output_files[0]!.name} · ${formatSize(payload.output_files[0]!.size_bytes)}`
    : payload?.output_dir ?? "data/macro_toolkit/output";
  const defaultBusinessEvidenceSources = formatBusinessEvidenceList(
    payload?.default_data_sources ?? analysis?.default_data_sources,
  );
  const executionBusinessEvidence = formatBusinessEvidenceList([
    ...(scriptsQuery.data?.result_meta.tables_used ?? []),
    ...(payload?.default_data_sources ?? analysis?.default_data_sources ?? []),
    ...(cffexStatus?.row_count ? ["bond_futures_history.csv"] : []),
    ...(commodityStatus ? [commodityStatus.table] : []),
    ...(hasRealStrategyData ? ["choice_stock_daily_observation", "choice_stock_factor_snapshot"] : []),
  ]);
  const outputReceiptDetail = payload?.output_files.length
    ? `${payload.output_files.length} 个产物 · 产物回执已归档`
    : outputDetail;

  const selectedGovernanceFocusItem =
    governanceFocusItems.find((item) => item.key === selectedGovernanceFocus) ?? governanceFocusItems[0]!;
  const committeeDecisionActionCurrent =
    committeeDecisionHref === "#macro-toolkit-operations-actions"
      ? selectedExecutionHref === committeeDecisionHref
      : selectedEvidenceHref === committeeDecisionHref;
  const handleCommitteeDecisionActionClick = useCallback(
    (event: ReactMouseEvent<HTMLAnchorElement>) => {
      if (committeeDecisionHref === "#macro-toolkit-data-health-detail") {
        event.preventDefault();
        focusDataHealthRepair();
        return;
      }
      if (committeeDecisionHref === "#macro-toolkit-operations-actions") {
        setSelectedExecutionHref(committeeDecisionHref);
        setSelectedGovernanceFocus("execution");
        return;
      }
      setSelectedEvidenceHref(committeeDecisionHref);
      setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(committeeDecisionHref));
    },
    [
      committeeDecisionHref,
      focusDataHealthRepair,
      setSelectedEvidenceHref,
      setSelectedExecutionHref,
      setSelectedGovernanceFocus,
    ],
  );

  const committeeDecisionActionControl = (
    <MacroToolkitCommitteeDecisionAction
      variant="tile"
      hasDataHealthRepairReceiptPending={hasDataHealthRepairReceiptPending}
      completedDataHealthReceipt={completedDataHealthReceipt}
      focusDataHealthRepair={focusDataHealthRepair}
      confirmActionReceipt={confirmActionReceipt}
      hasCommitteeOpenSubmissionLane={hasCommitteeOpenSubmissionLane}
      committeeLeadChecklistItem={committeeLeadChecklistItem}
      committeeLeadReceipt={committeeLeadReceipt}
      setSelectedEvidenceHref={setSelectedEvidenceHref}
      setSelectedGovernanceFocus={setSelectedGovernanceFocus}
      setSelectedExecutionHref={setSelectedExecutionHref}
      refreshChoiceStock={refreshChoiceStock}
      isRefreshingChoiceStock={isRefreshingChoiceStock}
      runSelectedScript={runSelectedScript}
      isRunning={isRunning}
      selectedScript={selectedScript}
      committeeDecisionAction={committeeDecisionAction}
      committeeDecisionActionCurrent={committeeDecisionActionCurrent}
      committeeDecisionHref={committeeDecisionHref}
      handleCommitteeDecisionActionClick={handleCommitteeDecisionActionClick}
    />
  );

  const signalSection = analysis ? (
    <MacroToolkitSignalSection
      showOperations
      visibleSignalCards={visibleSignalCards}
      crisisScoreResult={crisisScoreResult}
    />
  ) : null;
  const riskSection = analysis ? (
    <MacroToolkitRiskSection showOperations risk={analysis.a_share_risk} />
  ) : null;
  const strategySection = analysis ? (
    <MacroToolkitStrategySection
      showOperations
      selectedEvidenceHref={selectedEvidenceHref}
      strategyDescription={strategyDescription}
      choiceStockRefresh={choiceStockRefresh}
      isRefreshingChoiceStock={isRefreshingChoiceStock}
      isOperationActionBusy={isOperationActionBusy}
      refreshChoiceStock={refreshChoiceStock}
      stockRefreshResult={stockRefreshResult}
      stockRefreshError={stockRefreshError}
      strategySupplyState={strategySupplyState}
      fullRealStrategyCount={fullRealStrategyCount}
      partialRealStrategyCount={partialRealStrategyCount}
      degradedStrategyCount={degradedStrategyCount}
      sampleStrategyCount={sampleStrategyCount}
      strategySummaries={strategySummaries}
      shadowPortfolioReport={shadowPortfolioReport}
      strategyQuery={strategyQuery}
      macroEtfStrategy={macroEtfStrategy}
    />
  ) : null;
  const indicatorSection = analysis ? (
    <MacroToolkitIndicatorSection showOperations analysis={analysis} />
  ) : null;
  const capabilityResultsSection = analysis ? (
    <MacroToolkitCapabilityResultsSection
      capabilityResults={capabilityResults}
      isCoreAnalysis={isCoreAnalysis}
      isLoadingFullAnalysis={isLoadingFullAnalysis}
      loadFullAnalysis={loadFullAnalysis}
    />
  ) : null;
  const investmentBriefPanel = (
    <MacroToolkitInvestmentBriefPanel
      analysis={analysis}
      committeeFinalSignoffStatus={committeeFinalSignoffStatus}
      committeeFinalGateOutcome={committeeFinalGateOutcome}
      committeeFinalSignoffOwner={committeeFinalSignoffOwner}
      committeeDecisionBlocker={committeeDecisionBlocker}
      committeeFinalPackValue={committeeFinalPackValue}
      committeeFinalSignoffValue={committeeFinalSignoffValue}
      committeeFinalResidualRiskValue={committeeFinalResidualRiskValue}
      committeeFinalReceiptReviewValue={committeeFinalReceiptReviewValue}
      committeeChecklistItems={committeeChecklistItems}
      committeePackItemByKey={committeePackItemByKey}
      selectedEvidenceHref={selectedEvidenceHref}
      focusDataHealthRepair={focusDataHealthRepair}
      setSelectedEvidenceHref={setSelectedEvidenceHref}
      setSelectedGovernanceFocus={setSelectedGovernanceFocus}
      committeeDecisionActionControl={committeeDecisionActionControl}
    />
  );
  const governanceGatePanel = (
    <MacroToolkitGovernanceGatePanel
      analysisMeta={analysisMeta}
      governanceFocusItems={governanceFocusItems}
      selectedGovernanceFocusItem={selectedGovernanceFocusItem}
      setSelectedGovernanceFocus={setSelectedGovernanceFocus}
    />
  );
  const operationsConsolePanel = (
    <MacroToolkitOperationsConsolePanel
      selectedScript={selectedScript}
      scripts={scripts}
      availableScriptCount={availableScriptCount}
      actionReceipt={actionReceipt}
      actionReceipts={actionReceipts}
      selectedEvidenceHref={selectedEvidenceHref}
      setSelectedEvidenceHref={setSelectedEvidenceHref}
      defaultBusinessEvidenceSources={defaultBusinessEvidenceSources}
      cffexStatus={cffexStatus}
      commodityStatus={commodityStatus}
      payload={payload}
      outputDetail={outputDetail}
      selectedExecutionHref={selectedExecutionHref}
      isOperationActionBusy={isOperationActionBusy}
      isRunning={isRunning}
      runSelectedScript={runSelectedScript}
      isRunningChain={isRunningChain}
      runScriptChain={runScriptChain}
      isRefreshingChoiceStock={isRefreshingChoiceStock}
      refreshChoiceStock={refreshChoiceStock}
      isRefreshingCffex={isRefreshingCffex}
      refreshCffexMemberRank={refreshCffexMemberRank}
      isRefreshingCommodity={isRefreshingCommodity}
      commodityRefreshDisabled={commodityRefreshDisabled}
      refreshCommodityFutures={refreshCommodityFutures}
      commodityRefreshActionLabel={commodityRefreshActionLabel}
      scriptsQuery={scriptsQuery}
      stockRefreshResult={stockRefreshResult}
      stockRefreshError={stockRefreshError}
      refreshResult={refreshResult}
      refreshFeedbackTone={refreshFeedbackTone}
      refreshError={refreshError}
      commodityRefreshResult={commodityRefreshResult}
      commodityRefreshError={commodityRefreshError}
      chainRunResult={chainRunResult}
      chainRunError={chainRunError}
      runResult={runResult}
      runError={runError}
    />
  );

  const executionReceiptWorkspace = (
    <MacroToolkitExecutionReceiptWorkspace
      analysis={analysis}
      payload={payload}
      scriptsQuery={scriptsQuery}
      scripts={scripts}
      availableScriptCount={availableScriptCount}
      executionBusinessEvidence={executionBusinessEvidence}
      outputReceiptDetail={outputReceiptDetail}
      sourceHitCount={sourceHitCount}
      sourceChecks={sourceChecks}
      selectedEvidenceHref={selectedEvidenceHref}
      selectedGovernanceFocus={selectedGovernanceFocus}
      cffexStatus={cffexStatus}
      isRefreshingCffex={isRefreshingCffex}
      refreshCffexMemberRank={refreshCffexMemberRank}
      isOperationActionBusy={isOperationActionBusy}
      refreshResult={refreshResult}
      refreshFeedbackTone={refreshFeedbackTone}
      refreshError={refreshError}
      selectedCommodityProducts={selectedCommodityProducts}
      setSelectedCommodityProducts={setSelectedCommodityProducts}
      setCommoditySuggestedSelection={setCommoditySuggestedSelection}
      setCommodityRefreshResult={setCommodityRefreshResult}
      setCommodityRefreshError={setCommodityRefreshError}
      setCommodityRefreshRun={setCommodityRefreshRun}
      setCommodityEvidenceReloadMessage={setCommodityEvidenceReloadMessage}
      setCommodityShortfallChanges={setCommodityShortfallChanges}
      setCommodityShortfallEstimates={setCommodityShortfallEstimates}
      commodityPermission={commodityPermission}
      shouldShowCommodityPermissionNotice={shouldShowCommodityPermissionNotice}
      commodityStatus={commodityStatus}
      commoditySuggestedSelection={commoditySuggestedSelection}
      isRefreshingCommodity={isRefreshingCommodity}
      commodityRefreshDisabled={commodityRefreshDisabled}
      refreshCommodityFutures={refreshCommodityFutures}
      commodityRefreshActionLabel={commodityRefreshActionLabel}
      commodityRefreshResult={commodityRefreshResult}
      commodityEvidenceReloadMessage={commodityEvidenceReloadMessage}
      commodityShortfallChanges={commodityShortfallChanges}
      commodityShortfallEstimates={commodityShortfallEstimates}
      commodityRefreshError={commodityRefreshError}
      commodityRefreshRun={commodityRefreshRun}
      actionReceipts={actionReceipts}
      receiptTechnicalDetailsExpanded={receiptTechnicalDetailsExpanded}
      setReceiptTechnicalDetailsExpanded={setReceiptTechnicalDetailsExpanded}
      omittedEntries={omittedEntries}
      selectedGroup={selectedGroup}
      groupOptions={groupOptions}
      setSelectedGroup={setSelectedGroup}
      setSelectedName={setSelectedName}
      selectedScript={selectedScript}
      runSelectedScript={runSelectedScript}
      isRunning={isRunning}
      runScriptChain={runScriptChain}
      isRunningChain={isRunningChain}
      filteredScripts={filteredScripts}
      runError={runError}
      runResult={runResult}
      chainRunResult={chainRunResult}
    />
  );

  // 折叠摘要只读既有模型字段（就绪度汇总、数据健康覆盖、Crisis 组件、脚本注册表、
  // 报告清单、来源命中），缺字段时不出该胶囊，不补默认值。
  const readinessSummary = analysis?.readiness_summary;
  const dataHealth = analysis?.data_health;
  const reportBundle = analysis?.report_bundle;
  const crisisDependencyBlocked = crisisScoreResult?.dependency_gate?.status === "blocked";
  const crisisComponentAvailable = crisisScoreResult?.result.available_component_count;
  const crisisComponentTotal = crisisScoreResult?.result.component_count;
  // 阻断级异常＝会让业务判断不可用的失败（读取/执行失败、依赖阻断、资产校验失败）；
  // 常态运维计数（待补项、降级模型数）不算阻断，只进摘要。
  const opsBlockEntries: MacroToolkitOpsBlockEntry[] = [
    {
      key: "model-readiness",
      title: "模型就绪度摘要",
      chips: readinessSummary
        ? [
            `产物支撑 ${readinessSummary.artifact_backed_count}/${readinessSummary.total_count}`,
            `降级 ${readinessSummary.degraded_count}`,
          ]
        : [],
      blocking: Boolean(chainRunError),
      anchors: ["#macro-toolkit-model-readiness-detail"],
      minStage: 3,
      content: modelSignalMatrixSection,
    },
    {
      key: "data-health",
      title: "分析口径与数据健康",
      chips: dataHealth
        ? [
            `${dataHealth.repair_items?.length ?? 0} 项待处理`,
            `指标覆盖 ${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`,
            `来源覆盖 ${dataHealth.source_coverage.hit_count}/${dataHealth.source_coverage.total_count}`,
          ]
        : [],
      blocking: Boolean(analysisFailedAlert) || Boolean(fullAnalysisErrorAlert),
      anchors: ["#macro-toolkit-analysis-detail", "#macro-toolkit-data-health-detail"],
      minStage: 4,
      content: analysisEvidenceFlow,
    },
    {
      key: "crisis-evidence",
      title: "Crisis 证据",
      chips: crisisScoreResult
        ? [
            ...(typeof crisisComponentAvailable === "number" &&
            typeof crisisComponentTotal === "number"
              ? [`分数组件 ${crisisComponentAvailable}/${crisisComponentTotal}`]
              : []),
            crisisDependencyBlocked ? "依赖阻断" : statusLabel(crisisScoreResult.status),
          ]
        : [],
      blocking: crisisDependencyBlocked || crisisScoreResult?.status === "unavailable",
      anchors: ["#macro-toolkit-crisis-detail"],
      minStage: 5,
      content: crisisEvidenceSection,
    },
    {
      key: "operations-console",
      title: "操作台",
      chips: [
        `脚本 ${availableScriptCount}/${scripts.length}`,
        compactText(actionReceipt.action, 14),
      ],
      blocking: Boolean(
        runError || chainRunError || refreshError || commodityRefreshError || stockRefreshError,
      ),
      anchors: ["#macro-toolkit-operations-console", "#macro-toolkit-operations-actions"],
      minStage: 6,
      content: <MacroToolkitOperationsBand operationsConsolePanel={operationsConsolePanel} />,
    },
    {
      key: "report-bundle",
      title: "报告材料包",
      chips: reportBundle
        ? [
            `${reportBundle.artifacts.length} 个文件`,
            ...(reportBundle.as_of_date ? [`材料日 ${reportBundle.as_of_date}`] : []),
            ...(reportBundle.status === "ready"
              ? []
              : [reportBundle.status === "invalid" ? "资产校验失败" : "尚未发布"]),
          ]
        : [],
      blocking: reportBundle?.status === "invalid",
      anchors: [],
      minStage: MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE,
      content: reportBundleSection,
    },
    {
      key: "execution-receipt",
      title: "执行与产物回执",
      chips: [
        `产物 ${payload?.output_files.length ?? 0} 个`,
        `来源命中 ${sourceHitCount}/${sourceChecks.length}`,
      ],
      blocking: scriptsQuery.isError || Boolean(runError),
      anchors: [
        "#macro-toolkit-tool-execution-detail",
        "#macro-toolkit-cffex-detail",
        "#macro-toolkit-commodity-detail",
        "#macro-toolkit-script-artifact-detail",
      ],
      minStage: MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE,
      content: executionReceiptWorkspace,
    },
  ];
  const visibleOpsBlockEntries = opsBlockEntries.filter(
    (entry) => deferredContentStage >= entry.minStage && Boolean(entry.content),
  );

  return (
    <main
      className={`${MT_SHELL_MAIN} macro-toolkit-page__main macro-toolkit-page__main--with-rail`}
      onClickCapture={handleDeferredContentLinkClick}
    >
      <div className="macro-toolkit-page__primary">
        {cockpitSection}

        {analysis ? (
          <div className="macro-toolkit-page__content macro-toolkit-first-screen-flow">
            {signalSection}
          </div>
        ) : null}

        {deferredContentStage === 0 ? (
          <div
            ref={deferredContentSentinelRef}
            className="macro-toolkit-deferred-content-sentinel"
            data-testid="macro-toolkit-deferred-content-sentinel"
            aria-hidden="true"
          />
        ) : null}

        {deferredContentStage >= 1 ? (
          <div className="macro-toolkit-page__content">
            {analysisFailedAlert}
            {fullAnalysisErrorAlert}
            {initialAnalysisLoadingSection}
            {analysis ? (
              <>
                {riskSection}
                {indicatorSection}
                {deferredContentStage >= 2 ? capabilityResultsSection : null}
                {deferredContentStage >= 3 ? (
                  <>
                    {modelChainSection}
                    {hasonStrategySection}
                    {strategySection}
                  </>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}

        {visibleOpsBlockEntries.length ? (
          <div className="macro-toolkit-ops-layer" data-testid="macro-toolkit-ops-layer">
            <div className="macro-toolkit-ops-layer__lead">
              <span>运维与证据层</span>
              <small>以下为数据健康、脚本执行与产物证据，不参与业务方向判断。</small>
            </div>
            {visibleOpsBlockEntries.map((entry) => (
              <MacroToolkitOpsBlock
                key={entry.key}
                blockKey={entry.key}
                title={entry.title}
                chips={entry.chips}
                blocking={entry.blocking}
                forceOpen={
                  operationsLayerExpanded ||
                  (entry.key === "execution-receipt" && receiptTechnicalDetailsExpanded) ||
                  entry.anchors.some(
                    (anchor) =>
                      anchor === selectedEvidenceHref || anchor === selectedExecutionHref,
                  )
                }
              >
                {entry.content}
              </MacroToolkitOpsBlock>
            ))}
          </div>
        ) : null}

        {deferredContentStage >= 1 && deferredContentStage < 6 ? (
          <div
            ref={deferredContentSentinelRef}
            className="macro-toolkit-deferred-content-sentinel"
            data-testid="macro-toolkit-progressive-deferred-content-sentinel"
            data-deferred-stage={deferredContentStage}
            aria-hidden="true"
          />
        ) : null}

        {deferredContentStage === 6 ? (
          <div
            ref={deferredContentSentinelRef}
            className="macro-toolkit-deferred-content-sentinel"
            data-testid="macro-toolkit-execution-deferred-content-sentinel"
            aria-hidden="true"
          />
        ) : null}
      </div>
      <aside
        className="macro-toolkit-meta-rail"
        aria-label="治理与证据栏"
        data-testid="macro-toolkit-meta-rail"
      >
        {investmentBriefPanel}
        <MacroToolkitDeepEvidenceRailCard deepEvidenceQueueItems={deepEvidenceQueueItems} />
        {governanceGatePanel}
      </aside>
    </main>
  );
}
