import {
  useCallback,
  useMemo,
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

// 宏观工具（toolkit 模式）壳：只负责工具模式的布局与运维面板装配。
// 全部区块从 MacroToolkitPage 纯搬移，行为与文案不变；
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
                {deferredContentStage >= 1 ? (
                  <>
                    {riskSection}
                    {indicatorSection}
                  </>
                ) : null}
                {deferredContentStage >= 2 ? capabilityResultsSection : null}
                {deferredContentStage >= 3 ? (
                  <>
                    {modelSignalMatrixSection}
                    {modelChainSection}
                    {hasonStrategySection}
                  </>
                ) : null}
                {deferredContentStage >= 4 ? strategySection : null}
                {deferredContentStage >= 5 ? (
                  <>
                    {analysisEvidenceFlow}
                    {crisisEvidenceSection}
                  </>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}

        {deferredContentStage >= 6 ? (
          <MacroToolkitOperationsBand operationsConsolePanel={operationsConsolePanel} />
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

        {deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE ? (
          <>
            {reportBundleSection}
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
          </>
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
