import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ClockCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert } from "antd";
import { cardVariants } from "@heroui/styles";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitScriptRecord,
} from "../../../api/macroToolkitClient";
import {
  MT_SHELL_NUM,
  MT_SHELL_PAGE,
  MT_SHELL_STATUS_PILL,
  MT_SHELL_STATUS_ROW,
  MT_SHELL_TITLE,
  MT_SHELL_TITLE_BRAND,
  MT_SHELL_TOPBAR,
  MT_SHELL_TOPBAR_LEFT,
} from "../lib/macroToolkitPageChrome";

import "./MacroToolkitPage.css";

import { MacroStatusIcon, MetricTile } from "../lib/MacroToolkitStatusPrimitives";
import {
  canRefreshMacroSourceBackfill,
  formatCommodityRefreshActionLabel,
  suggestedCommodityRefreshStartDate,
} from "../lib/macroToolkitCrisisSupport";
import { CrisisScoreEvidencePanel } from "../panels/MacroToolkitCrisisPanels";
import { MacroToolkitModelChainPanel } from "../panels/MacroToolkitModelChainPanel";
import { MacroToolkitReportBundlePanel } from "../panels/MacroToolkitReportBundlePanel";
import {
  HasonMacroStrategyPanel,
  ModelSignalMatrix,
} from "../panels/MacroToolkitSignalPanels";
import { deriveModelReadinessFromHasonStrategy } from "../panels/macroToolkitModelEvidenceShared";
import {
  compareRepairPriority,
  coverageValue,
  repairItemFocusKey,
} from "../lib/macroToolkitDataHealthSupport";
import {
  formatObservationEvidence,
  formatObservationRecommendation,
  formatObservationSignalTitle,
  formatQueryError,
  isMacroToolkitReadForbidden,
  isObservationOutputSignal,
  isReadyStatus,
} from "../lib/macroToolkitDisplayFormat";
import { buildMacroToolkitCommitteeModel } from "../lib/macroToolkitCommitteeModel";
import {
  MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
  MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
  pickDefaultCommitteeScript,
} from "../lib/macroToolkitPageModel";
import type { MacroToolkitGovernanceFocusKey } from "../lib/macroToolkitPageModel";
import {
  hasCompleteRealStrategyChain,
  hasRealStrategySource,
} from "../lib/macroToolkitStrategyDisplaySupport";
import { MacroToolkitAnalysisEvidenceFlow } from "../sections/MacroToolkitAnalysisEvidenceSections";
import {
  MacroToolkitHeaderControls,
  MacroToolkitInitialAnalysisLoading,
  MacroToolkitPageErrorState,
} from "../sections/MacroToolkitPageStates";
import { useMacroToolkitOperationActions } from "./useMacroToolkitOperationActions";
import {
  MacroToolkitObservationComparisonSection,
  MacroToolkitObservationDecisionSummary,
} from "../sections/MacroToolkitObservationSections";
import { MacroToolkitContractBoundary } from "../sections/MacroToolkitPrimitives";
import { MacroToolkitObservationView } from "./MacroToolkitObservationView";
import { MacroToolkitOperationsView } from "./MacroToolkitOperationsView";
import { useMacroToolkitDeferredContent } from "./useMacroToolkitDeferredContent";

const EMPTY_SCRIPTS: MacroToolkitScriptRecord[] = [];
const MACRO_TOOLKIT_READ_STALE_MS = 60_000;
const MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS = 1_500;

const MACRO_TOOLKIT_HERO_CARD_SLOTS = cardVariants({ variant: "default" });

type MacroToolkitPageMode = "toolkit" | "observation";

type MacroToolkitPageProps = {
  mode?: MacroToolkitPageMode;
};

export default function MacroToolkitPage({ mode = "toolkit" }: MacroToolkitPageProps) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const showOperations = mode === "toolkit";
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedGovernanceFocus, setSelectedGovernanceFocus] =
    useState<MacroToolkitGovernanceFocusKey>("evidence");
  const [selectedEvidenceHref, setSelectedEvidenceHref] = useState<string | null>(null);
  const [selectedExecutionHref, setSelectedExecutionHref] = useState<string | null>(null);
  const [focusedRepairKey, setFocusedRepairKey] = useState<string | null>(null);
  const [committeeActionLocatorKey, setCommitteeActionLocatorKey] = useState<string | null>(null);
  const committeeActionLocatorRef = useRef<HTMLDivElement | null>(null);
  const [fullAnalysisEnvelope, setFullAnalysisEnvelope] =
    useState<ApiEnvelope<MacroToolkitAnalysisPayload> | null>(null);
  const [fullAnalysisError, setFullAnalysisError] = useState<string | null>(null);
  const [isLoadingFullAnalysis, setIsLoadingFullAnalysis] = useState(false);

  const deferredContent = useMacroToolkitDeferredContent({
    showOperations,
    selectedEvidenceHref,
    selectedExecutionHref,
    setSelectedEvidenceHref,
    setSelectedExecutionHref,
    setSelectedGovernanceFocus,
  });

  const analysisQuery = useQuery({
    queryKey: ["macro-toolkit", "analysis"],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "core" }),
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const scriptsQuery = useQuery({
    queryKey: ["macro-toolkit", "scripts"],
    queryFn: () => client.getMacroToolkitScripts(),
    enabled: showOperations,
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const strategyQuery = useQuery({
    queryKey: ["macro-toolkit", "strategy-summaries"],
    queryFn: ({ signal }) => client.getMacroToolkitStrategySummaries({ signal }),
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const modelChainQuery = useQuery({
    queryKey: ["macro-toolkit", "model-chain-results"],
    queryFn: ({ signal }) => client.fetchMacroToolkitModelChainResults({ signal }),
    enabled: showOperations,
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const fetchFullAnalysis = useCallback(
    () =>
      client.getMacroToolkitAnalysis({
        detail: "full",
        historyLimit: MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
      }),
    [client],
  );

  const loadFullAnalysis = useCallback(async (options?: { force?: boolean }) => {
    setIsLoadingFullAnalysis(true);
    setFullAnalysisError(null);
    try {
      await queryClient.cancelQueries({ queryKey: ["macro-toolkit", "strategy-summaries"] });
      if (options?.force) {
        await queryClient.cancelQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
        queryClient.removeQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
      }
      const response = await queryClient.fetchQuery({
        queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
        queryFn: fetchFullAnalysis,
        staleTime: MACRO_TOOLKIT_READ_STALE_MS,
      });
      setFullAnalysisEnvelope(response);
      return response;
    } catch (error) {
      setFullAnalysisError(formatQueryError(error));
      return null;
    } finally {
      setIsLoadingFullAnalysis(false);
    }
  }, [fetchFullAnalysis, queryClient]);

  useEffect(() => {
    if (fullAnalysisEnvelope || analysisQuery.data?.result.runtime_status?.analysis_scope !== "core") {
      return;
    }
    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await queryClient.fetchQuery({
            queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
            queryFn: fetchFullAnalysis,
            staleTime: MACRO_TOOLKIT_READ_STALE_MS,
          });
          if (!cancelled) {
            setFullAnalysisEnvelope(response);
          }
        } catch {
          // Keep the core screen until the user explicitly retries full analysis.
        }
      })();
    }, MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [analysisQuery.data?.result.runtime_status?.analysis_scope, fetchFullAnalysis, fullAnalysisEnvelope, queryClient]);

  const payload = showOperations ? scriptsQuery.data?.result : undefined;
  const analysisEnvelope = fullAnalysisEnvelope ?? analysisQuery.data;
  const analysis = analysisEnvelope?.result;
  const scripts = payload?.scripts ?? EMPTY_SCRIPTS;
  const capabilityResults = analysis?.capability_results ?? [];
  const strategyPayload = strategyQuery.data?.result;
  const strategySummaries = strategyPayload?.strategy_summaries ?? analysis?.strategy_summaries ?? [];
  const shadowPortfolioReport =
    strategyPayload?.shadow_portfolio_report ?? analysis?.shadow_portfolio_report ?? null;
  const macroEtfStrategy = strategyPayload?.macro_etf_strategy ?? null;
  const fullRealStrategyCount = strategySummaries.filter((strategy) => hasCompleteRealStrategyChain(strategy)).length;
  const partialRealStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && !hasCompleteRealStrategyChain(strategy),
  ).length;
  const degradedStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && strategy.status !== "complete",
  ).length;
  const sampleStrategyCount = strategySummaries.filter((strategy) => strategy.status === "sample_only").length;
  const hasLoadedStrategySummaries = strategySummaries.length > 0;
  const strategySupplyState =
    strategyQuery.isFetching && !hasLoadedStrategySummaries
      ? "loading"
      : strategyQuery.isError && !hasLoadedStrategySummaries
        ? "failed"
        : "loaded";
  const hasRealStrategyData = strategySummaries.some((strategy) => hasRealStrategySource(strategy));
  const strategyDescription =
    strategySupplyState === "loading"
      ? "策略摘要正在生成。"
      : strategySupplyState === "failed"
        ? "策略摘要读取失败，当前不能判断策略供数闭环。"
        : hasRealStrategyData
          ? "展示已合入宏观模块的 A股策略能力；已接入股票行情或因子快照，不作为正式投资信号。"
          : "展示已合入宏观模块的 A股策略能力；当前为合成样例和模块可用性检查，不作为正式投资信号。";

  const filteredScripts = useMemo(() => {
    if (selectedGroup === "all") {
      return scripts;
    }
    return scripts.filter((script) => script.group === selectedGroup);
  }, [scripts, selectedGroup]);

  useEffect(() => {
    if (selectedName || filteredScripts.length === 0) {
      return;
    }
    setSelectedName((pickDefaultCommitteeScript(filteredScripts) ?? filteredScripts[0]!).name);
  }, [filteredScripts, selectedName]);

  const selectedScript = useMemo(
    () =>
      scripts.find((script) => script.name === selectedName) ??
      pickDefaultCommitteeScript(filteredScripts) ??
      null,
    [filteredScripts, scripts, selectedName],
  );
  const cffexStatus = payload?.cffex_member_rank ?? analysis?.cffex_member_rank ?? null;
  const choiceStockRefresh =
    strategyPayload?.choice_stock_refresh ?? payload?.choice_stock_refresh ?? analysis?.choice_stock_refresh ?? null;
  const commodityFuturesRefresh = payload?.commodity_futures_refresh ?? null;
  const commodityStatus = commodityFuturesRefresh?.status ?? null;
  const omittedEntries = Object.entries(payload?.omitted_scripts ?? {});
  const sourceChecks = payload?.source_checks ?? analysis?.source_checks ?? [];
  const capabilityItems = payload?.capabilities ?? analysis?.capabilities ?? [];
  const analysisMeta = analysisEnvelope?.result_meta;
  const sourceHitCount = sourceChecks.filter((check) => check.row_count > 0).length;
  const availableScriptCount = scripts.filter((script) => script.available).length;
  const readyCapabilityCount = capabilityItems.filter((item) => isReadyStatus(item.data_status)).length;
  const wiredCapabilityCount = capabilityItems.filter((item) =>
    isReadyStatus(item.route_status) && isReadyStatus(item.frontend_status),
  ).length;
  const crisisScoreResult = capabilityResults.find((result) => result.key === "crisis_score_cn") ?? null;
  const decisionSummaryResult = capabilityResults.find((result) => result.key === "decision_summary") ?? null;
  const degradedResultCount = capabilityResults.filter((result) => result.status !== "complete").length;
  const missingIndicatorCount = analysis?.indicators.filter((indicator) => indicator.quality === "missing").length ?? 0;
  const analysisSignalCards = analysis?.signal_cards ?? [];
  // 脚本产物等运维元信息不进入核心信号区；产物状态保留在深度证据入口与执行区。
  const analyticalSignalCards = analysisSignalCards.filter((card) => !isObservationOutputSignal(card));
  const visibleSignalCards = analyticalSignalCards;
  const primarySignal =
    analyticalSignalCards
      .filter((card) => card.score != null)
      .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))[0] ?? null;
  const isCoreAnalysis = analysis?.runtime_status?.analysis_scope === "core";
  const queryErrors = [analysisQuery.error, ...(showOperations ? [scriptsQuery.error] : []), strategyQuery.error];
  const queryErrorText = queryErrors
    .filter(Boolean)
    .map(formatQueryError)
    .join("；");
  const failedReadMessages = queryErrors
    .filter(Boolean)
    .map(formatQueryError);
  const observationFailedReadMessages = [
    analysisQuery.isError ? "读取核心分析失败" : "",
    strategyQuery.isError ? "读取策略摘要失败" : "",
  ].filter(Boolean);
  const hasReadScopeBlocker = failedReadMessages.some(isMacroToolkitReadForbidden);
  const runtimeSections = analysis?.runtime_status?.deferred_sections ?? [];
  const hasonStrategy = analysis?.hason_strategy ?? null;
  const showFullAnalysisActionInRuntime = isCoreAnalysis && runtimeSections.length > 0;
  const observationRuntimeSummary = isCoreAnalysis
    ? runtimeSections.length
      ? `${runtimeSections.length} 项证据延后确认`
      : "等待完整分析确认"
    : "证据已完整读取";
  const dataFreshnessDetail = showOperations
    ? `${missingIndicatorCount} 个指标缺失；${sourceHitCount} 个源命中`
    : analysis?.data_health
      ? `来源覆盖 ${coverageValue(analysis.data_health.source_coverage)}`
      : "来源覆盖待确认";
  const repairItems = analysis?.data_health?.repair_items ?? [];
  const repairItemCount = repairItems.length;
  const primaryRepairItem = [...repairItems].sort(compareRepairPriority)[0] ?? null;
  const primaryActionableRepairItem =
    repairItems.find(canRefreshMacroSourceBackfill) ?? primaryRepairItem ?? null;
  const operationActions = useMacroToolkitOperationActions({
    analysis,
    analysisQuery,
    commodityFuturesRefresh,
    crisisScoreResult,
    fullAnalysisError,
    isCoreAnalysis,
    loadFullAnalysis,
    payload,
    scriptsQuery,
    selectedScript,
    setCommitteeActionLocatorKey,
    setFocusedRepairKey,
    setFullAnalysisEnvelope,
    setFullAnalysisError,
    setSelectedEvidenceHref,
    setSelectedGovernanceFocus,
    strategyQuery,
  });
  const {
    actionReceipts,
    chainRunError,
    chainRunModelId,
    chainRunResult,
    clearFullAnalysisCache,
    commodityRefreshEvidenceChain,
    commodityRefreshResult,
    commodityShortfallChanges,
    commodityShortfallEstimates,
    confirmedReceiptIds,
    crisisGapRepairFeedback,
    isCommodityRefreshAllowed,
    isRefreshingCffex,
    isRefreshingChoiceStock,
    isRefreshingCommodity,
    isRunning,
    isRunningChain,
    refreshCommodityFutures,
    refreshMacroSourceBackfill,
    refreshingSourceAlias,
    reviewFullAnalysisRepair,
    runScriptChain,
    selectedCommodityProducts,
    setCommodityEvidenceReloadMessage,
    setCommodityRefreshError,
    setCommodityRefreshEvidenceChain,
    setCommodityRefreshResult,
    setCommodityRefreshRun,
    setCommodityShortfallChanges,
    setCommodityShortfallEstimates,
    setCommoditySuggestedSelection,
    setSelectedCommodityProducts,
    sourceBackfillError,
    sourceBackfillFeedbackTone,
    sourceBackfillResult,
  } = operationActions;
  const shouldShowCommodityPermissionNotice = !isCommodityRefreshAllowed;
  const commodityRefreshDisabled = selectedCommodityProducts.length === 0 || !isCommodityRefreshAllowed;
  const isMacroRefreshing =
    analysisQuery.isFetching ||
    (showOperations && scriptsQuery.isFetching) ||
    strategyQuery.isFetching ||
    isRefreshingCommodity ||
    isLoadingFullAnalysis;
  const isOperationActionBusy =
    isMacroRefreshing ||
    isRunning ||
    isRunningChain ||
    isRefreshingChoiceStock ||
    isRefreshingCffex ||
    refreshingSourceAlias != null;
  const commodityRefreshActionLabel = formatCommodityRefreshActionLabel(commodityShortfallEstimates);
  const focusDataHealthRepair = useCallback(() => {
    const repairKey = primaryActionableRepairItem ? repairItemFocusKey(primaryActionableRepairItem) : null;
    setSelectedEvidenceHref("#macro-toolkit-data-health-detail");
    setSelectedGovernanceFocus("data-health");
    setFocusedRepairKey(repairKey);
    setCommitteeActionLocatorKey(repairKey);
  }, [primaryActionableRepairItem]);
  useEffect(() => {
    if (!committeeActionLocatorKey || selectedEvidenceHref !== "#macro-toolkit-data-health-detail") return;
    const actionLocator = committeeActionLocatorRef.current;
    if (typeof actionLocator?.scrollIntoView !== "function") return;
    const block: ScrollLogicalPosition = window.innerWidth <= 640 ? "center" : "nearest";
    actionLocator.scrollIntoView({ block, inline: "nearest" });
  }, [committeeActionLocatorKey, selectedEvidenceHref]);
  const committeeModel = buildMacroToolkitCommitteeModel({
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
  });
  const { completedDataHealthReceipt } = committeeModel;
  const isAuditTargetActive = useCallback(
    (href: string, governanceKeys: MacroToolkitGovernanceFocusKey[] = []) =>
      selectedEvidenceHref ? selectedEvidenceHref === href : governanceKeys.includes(selectedGovernanceFocus),
    [selectedEvidenceHref, selectedGovernanceFocus],
  );
  const observationBoundaryPanel = !showOperations ? (
    <div className="macro-toolkit-observation-boundaries">
      <MacroToolkitContractBoundary
        formalUseAllowed={analysisMeta?.formal_use_allowed}
        resultKind={analysisMeta?.result_kind}
        ruleVersion={analysisMeta?.rule_version}
        plainLanguage
      />
      <Alert
        type="info"
        showIcon
        data-testid="macro-observation-readonly-boundary"
        message="只读宏观观察"
        description="本页只展示宏观分析证据；刷新、脚本执行和运营注册表保留在宏观工具页。"
      />
    </div>
  ) : null;
  const observationDecisionSummary =
    !showOperations && analysis ? (
      <MacroToolkitObservationDecisionSummary
        decisionSummaryResult={decisionSummaryResult}
        isCoreAnalysis={isCoreAnalysis}
        analysisBasis={analysisMeta?.basis ?? null}
      />
    ) : null;
  const observationFirstScreenLoop =
    !showOperations ? (
      <div
        className={MACRO_TOOLKIT_HERO_CARD_SLOTS.base({
          className: "macro-toolkit-observation-loop border border-default-200 bg-content1 text-foreground",
        })}
        aria-label="宏观观察首屏闭环"
        data-slot="card"
      >
        <div
          className={MACRO_TOOLKIT_HERO_CARD_SLOTS.header({ className: "macro-toolkit-observation-loop__head p-0" })}
          data-slot="card-header"
        >
          <span>观察闭环</span>
          <strong>{analysis?.as_of_date ?? "日期待确认"}</strong>
        </div>
        <div
          className={MACRO_TOOLKIT_HERO_CARD_SLOTS.content({ className: "macro-toolkit-observation-loop__grid p-0" })}
          data-slot="card-content"
        >
          <div>
            <span>当前判断</span>
            <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
            <small>{formatObservationRecommendation(analysis?.conclusion.recommended_action)}</small>
          </div>
          <div>
            <span>关键证据</span>
            <strong>{primarySignal ? formatObservationSignalTitle(primarySignal) : "证据待确认"}</strong>
            <small>
              {analysis?.default_data_sources?.length
                ? `已接入 ${analysis.default_data_sources.length} 类系统数据源；`
                : "来源待确认；"}
              {primarySignal ? formatObservationEvidence(primarySignal.evidence) : "观察证据待补齐"}
            </small>
          </div>
          <div>
            <span>使用边界</span>
            <strong>只读观察</strong>
            <small>不作为正式投资信号；刷新、脚本和完整审计留在宏观工具页。</small>
          </div>
        </div>
      </div>
    ) : null;

  const cockpitSection = (
    <section
      data-testid="macro-toolkit-tailwind-cockpit"
      className={MACRO_TOOLKIT_HERO_CARD_SLOTS.base({
        className: `macro-toolkit-cockpit macro-toolkit-cockpit--${
          showOperations ? "toolkit" : "observation"
        } border border-default-200 bg-background/95 text-foreground shadow-sm`,
      })}
      data-slot="card"
    >
      <div
        className={MACRO_TOOLKIT_HERO_CARD_SLOTS.content({ className: "macro-toolkit-cockpit__body p-0" })}
        data-slot="card-content"
      >
        <div
          className="macro-toolkit-cockpit__analysis macro-toolkit-house-view"
          data-testid="macro-toolkit-house-view"
          aria-label={showOperations ? "宏观工具 House View" : "宏观观察结论"}
        >
          <div className="macro-toolkit-panel-kicker">
            <span>{showOperations ? "投研结论" : "观察结论"}</span>
            <strong>{showOperations ? "可执行宏观判断" : "只读宏观判断"}</strong>
          </div>
          {observationDecisionSummary}
          <div className="macro-toolkit-cockpit__conclusion">
            <div className="macro-toolkit-cockpit__label">
              <MacroStatusIcon tone={analysis?.conclusion.tone ?? "missing"}>
                {analysis?.conclusion.tone === "negative" || !analysis ? <WarningOutlined /> : <LineChartOutlined />}
              </MacroStatusIcon>
              投研观点
            </div>
            <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
            <p title={analysis?.conclusion.summary}>
              {analysis?.conclusion.summary ?? "正在从系统数据源生成宏观判断。"}
            </p>
            {showOperations && analysis?.warnings.length ? (
              <small
                className="macro-toolkit-cockpit__limits"
                title={analysis.warnings.join(" ")}
              >
                {analysis.warnings.length} 项输入受限，不影响已展示结论
              </small>
            ) : null}
          </div>
          {showOperations ? (
            <div className="macro-toolkit-brief-metrics">
              <MetricTile
                icon={<LineChartOutlined />}
                label="主信号"
                value={primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : EM_DASH}
                detail={
                  primarySignal?.score == null
                    ? "尚无可排序信号"
                    : `评分 ${primarySignal.score.toFixed(1)}`
                }
                detailTitle={
                  primarySignal?.evidence.length ? primarySignal.evidence.join(" / ") : undefined
                }
                tone={primarySignal?.tone === "positive" ? "positive" : primarySignal ? "neutral" : "missing"}
              />
            </div>
          ) : (
            observationFirstScreenLoop
          )}
        </div>
      </div>
    </section>
  );

  const isAnalysisLoading = analysisQuery.isLoading && !analysis;
  const observationSignalRiskLoadingSection = !showOperations && !analysis ? (
    <MacroToolkitObservationComparisonSection signalCards={[]} primarySignal={null} isLoading />
  ) : null;
  const initialAnalysisLoadingSection = isAnalysisLoading ? (
    <MacroToolkitInitialAnalysisLoading
      showOperations={showOperations}
      observationSignalRiskLoadingSection={observationSignalRiskLoadingSection}
    />
  ) : null;
  const analysisFailedAlert = analysisQuery.isError ? (
    <Alert type="error" showIcon message="宏观分析结果加载失败" />
  ) : null;
  const fullAnalysisErrorAlert = fullAnalysisError ? (
    <Alert type="error" showIcon message="完整分析加载失败" description={fullAnalysisError} />
  ) : null;
  const crisisEvidenceSection =
    analysis && crisisScoreResult ? (
      <CrisisScoreEvidencePanel
        result={crisisScoreResult}
        analysisMeta={analysisMeta}
        analysisAsOfDate={analysis.as_of_date ?? null}
        repairItems={analysis.data_health?.repair_items ?? []}
        refreshingSourceAlias={refreshingSourceAlias}
        commodityRefreshResult={commodityRefreshResult}
        commodityRefreshEvidenceChain={commodityRefreshEvidenceChain}
        commodityShortfallChanges={commodityShortfallChanges}
        commodityShortfallEstimates={commodityShortfallEstimates}
        repairFeedback={crisisGapRepairFeedback}
        sourceBackfillResult={sourceBackfillResult}
        sourceBackfillError={sourceBackfillError}
        onRepairSourceBackfill={(item, group) => {
          void refreshMacroSourceBackfill(item, group);
        }}
        onApplyCommodityRefreshProducts={(products) => {
          setSelectedCommodityProducts(products);
          setCommoditySuggestedSelection(products);
          setCommodityRefreshResult(null);
          setCommodityRefreshError(null);
          setCommodityRefreshRun(null);
          setCommodityEvidenceReloadMessage(null);
          setCommodityRefreshEvidenceChain(null);
          setCommodityShortfallChanges([]);
          setCommodityShortfallEstimates([]);
        }}
        onPreviewCommodityRefreshProducts={(products) => {
          void refreshCommodityFutures({
            dryRun: true,
            products,
            suggestedSelection: products,
            startDate: suggestedCommodityRefreshStartDate(crisisScoreResult),
          });
        }}
        onRefreshCommodityProducts={(products) => {
          void refreshCommodityFutures({
            dryRun: false,
            products,
            suggestedSelection: products,
            startDate: suggestedCommodityRefreshStartDate(crisisScoreResult),
          });
        }}
      />
    ) : null;
  const hasonStrategySection = hasonStrategy ? (
    <HasonMacroStrategyPanel
      strategy={hasonStrategy}
      modelReadiness={analysis?.model_readiness}
      variant={showOperations ? "detail" : "observation"}
    />
  ) : null;
  const modelSignalReadiness = analysis?.model_readiness?.length
    ? analysis.model_readiness
    : hasonStrategySection && analysis?.hason_strategy
      ? deriveModelReadinessFromHasonStrategy(analysis.hason_strategy)
      : [];
  const modelSignalMatrixSection = modelSignalReadiness.length ? (
    <ModelSignalMatrix
      modelReadiness={modelSignalReadiness}
      readinessSummary={analysis?.readiness_summary}
      chainRunResult={chainRunResult}
      chainRunError={chainRunError}
      chainRunModelId={chainRunModelId}
      isRunningChain={isRunningChain}
      showActions={showOperations}
      onRunChain={runScriptChain}
    />
  ) : null;
  const modelChainResults = modelChainQuery.data?.result;
  const modelChainSection = modelChainResults?.steps.length ? (
    <MacroToolkitModelChainPanel results={modelChainResults} />
  ) : null;
  // 分析限制全文交给证据区折叠（limitsDetails）；首屏只留 house view 结论区的一句中文摘要。
  const analysisWarningsAlert = analysis?.warnings.length ? (
    <Alert type="warning" showIcon message="分析限制" description={analysis.warnings.join(" ")} />
  ) : null;
  const analysisEvidenceFlow = analysis ? (
    <MacroToolkitAnalysisEvidenceFlow
      analysis={analysis}
      analysisMeta={analysisMeta}
      showOperations={showOperations}
      isAuditTargetActive={isAuditTargetActive}
      observationBoundaryPanel={observationBoundaryPanel}
      runtimeSections={runtimeSections}
      isCoreAnalysis={isCoreAnalysis}
      observationRuntimeSummary={observationRuntimeSummary}
      showFullAnalysisActionInRuntime={showFullAnalysisActionInRuntime}
      isLoadingFullAnalysis={isLoadingFullAnalysis}
      loadFullAnalysis={loadFullAnalysis}
      focusedRepairKey={focusedRepairKey}
      completedDataHealthReceipt={completedDataHealthReceipt}
      confirmedReceiptIds={confirmedReceiptIds}
      setFocusedRepairKey={setFocusedRepairKey}
      refreshMacroSourceBackfill={refreshMacroSourceBackfill}
      reviewFullAnalysisRepair={reviewFullAnalysisRepair}
      refreshingSourceAlias={refreshingSourceAlias}
      sourceBackfillResult={sourceBackfillResult}
      sourceBackfillFeedbackTone={sourceBackfillFeedbackTone}
      sourceBackfillError={sourceBackfillError}
      primarySignal={primarySignal}
      dataFreshnessDetail={dataFreshnessDetail}
      missingIndicatorCount={missingIndicatorCount}
      capabilityResults={capabilityResults}
      degradedResultCount={degradedResultCount}
      limitsDetails={analysisWarningsAlert}
    />
  ) : null;
  const reportBundleSection = analysis ? (
    <MacroToolkitReportBundlePanel bundle={analysis.report_bundle} />
  ) : null;

  if (!payload && !analysis && (analysisQuery.isError || (showOperations && scriptsQuery.isError))) {
    return (
      <MacroToolkitPageErrorState
        showOperations={showOperations}
        queryErrorText={queryErrorText}
        analysisQuery={analysisQuery}
        scriptsQuery={scriptsQuery}
        strategyQuery={strategyQuery}
        hasReadScopeBlocker={hasReadScopeBlocker}
        failedReadMessages={failedReadMessages}
        observationFailedReadMessages={observationFailedReadMessages}
      />
    );
  }

  return (
    <section
      className={`${MT_SHELL_PAGE} macro-toolkit-page theme-dh-api`}
      data-testid="macro-toolkit-page"
      data-moss-theme-scope="macro-toolkit"
    >
      <header
        className={`${MT_SHELL_TOPBAR} macro-toolkit-page__header`}
        data-testid="macro-toolkit-toolbar"
      >
        <div className={`${MT_SHELL_TOPBAR_LEFT} macro-toolkit-page__header-main`}>
          <div className={MT_SHELL_TITLE_BRAND}>
            <h1 className={MT_SHELL_TITLE}>{showOperations ? "宏观工具" : "宏观分析结果"}</h1>
          </div>
          <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__badge`}>
            {showOperations ? "工具控制台" : "只读观察"}
          </span>
          <div className={`${MT_SHELL_STATUS_ROW} macro-toolkit-page__toolbar-info`} aria-label="宏观工具状态">
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <ClockCircleOutlined aria-hidden="true" />
              观察日{" "}
              <span className={MT_SHELL_NUM}>{analysis?.as_of_date ?? EM_DASH}</span>
            </span>
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <DatabaseOutlined aria-hidden="true" />
              缺口 {repairItemCount}
            </span>
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <ThunderboltOutlined aria-hidden="true" />
              能力 {readyCapabilityCount}/{capabilityItems.length || 0}
            </span>
          </div>
        </div>
        <MacroToolkitHeaderControls
          showOperations={showOperations}
          clearFullAnalysisCache={clearFullAnalysisCache}
          analysisQuery={analysisQuery}
          scriptsQuery={scriptsQuery}
          strategyQuery={strategyQuery}
          isMacroRefreshing={isMacroRefreshing}
          deferredContentStage={deferredContent.deferredContentStage}
          receiptTechnicalDetailsExpanded={deferredContent.receiptTechnicalDetailsExpanded}
          revealAllDeferredContent={deferredContent.revealAllDeferredContent}
        />
        <p className="macro-toolkit-page__header-summary">
          {showOperations
            ? "先看结论、信号和指标结果；数据核对与脚本执行收在页面后段。"
            : "只展示宏观分析证据；刷新、脚本和注册表保留在宏观工具页。"}
        </p>
      </header>

      {showOperations ? (
        <MacroToolkitOperationsView
          analysis={analysis}
          analysisMeta={analysisMeta}
          payload={payload}
          scripts={scripts}
          scriptsQuery={scriptsQuery}
          strategyQuery={strategyQuery}
          capabilityResults={capabilityResults}
          crisisScoreResult={crisisScoreResult}
          visibleSignalCards={visibleSignalCards}
          availableScriptCount={availableScriptCount}
          sourceChecks={sourceChecks}
          sourceHitCount={sourceHitCount}
          isCoreAnalysis={isCoreAnalysis}
          isLoadingFullAnalysis={isLoadingFullAnalysis}
          loadFullAnalysis={loadFullAnalysis}
          strategyDescription={strategyDescription}
          choiceStockRefresh={choiceStockRefresh}
          strategySupplyState={strategySupplyState}
          fullRealStrategyCount={fullRealStrategyCount}
          partialRealStrategyCount={partialRealStrategyCount}
          degradedStrategyCount={degradedStrategyCount}
          sampleStrategyCount={sampleStrategyCount}
          strategySummaries={strategySummaries}
          shadowPortfolioReport={shadowPortfolioReport}
          macroEtfStrategy={macroEtfStrategy}
          hasRealStrategyData={hasRealStrategyData}
          cffexStatus={cffexStatus}
          commodityStatus={commodityStatus}
          omittedEntries={omittedEntries}
          selectedScript={selectedScript}
          filteredScripts={filteredScripts}
          selectedGroup={selectedGroup}
          setSelectedGroup={setSelectedGroup}
          setSelectedName={setSelectedName}
          selectedEvidenceHref={selectedEvidenceHref}
          setSelectedEvidenceHref={setSelectedEvidenceHref}
          selectedExecutionHref={selectedExecutionHref}
          setSelectedExecutionHref={setSelectedExecutionHref}
          selectedGovernanceFocus={selectedGovernanceFocus}
          setSelectedGovernanceFocus={setSelectedGovernanceFocus}
          focusDataHealthRepair={focusDataHealthRepair}
          isOperationActionBusy={isOperationActionBusy}
          commodityRefreshDisabled={commodityRefreshDisabled}
          commodityRefreshActionLabel={commodityRefreshActionLabel}
          shouldShowCommodityPermissionNotice={shouldShowCommodityPermissionNotice}
          operationActions={operationActions}
          committeeModel={committeeModel}
          deferredContent={deferredContent}
          cockpitSection={cockpitSection}
          analysisFailedAlert={analysisFailedAlert}
          fullAnalysisErrorAlert={fullAnalysisErrorAlert}
          initialAnalysisLoadingSection={initialAnalysisLoadingSection}
          analysisEvidenceFlow={analysisEvidenceFlow}
          crisisEvidenceSection={crisisEvidenceSection}
          modelSignalMatrixSection={modelSignalMatrixSection}
          modelChainSection={modelChainSection}
          hasonStrategySection={hasonStrategySection}
          reportBundleSection={reportBundleSection}
        />
      ) : (
        <MacroToolkitObservationView
          analysis={analysis}
          visibleSignalCards={visibleSignalCards}
          primarySignal={primarySignal}
          selectedEvidenceHref={selectedEvidenceHref}
          strategySummaries={strategySummaries}
          strategySupplyState={strategySupplyState}
          fullRealStrategyCount={fullRealStrategyCount}
          partialRealStrategyCount={partialRealStrategyCount}
          degradedStrategyCount={degradedStrategyCount}
          sampleStrategyCount={sampleStrategyCount}
          shadowPortfolioReport={shadowPortfolioReport}
          strategyQuery={strategyQuery}
          capabilityResults={capabilityResults}
          degradedResultCount={degradedResultCount}
          hasonStrategy={hasonStrategy}
          isCoreAnalysis={isCoreAnalysis}
          handleDeferredContentLinkClick={deferredContent.handleDeferredContentLinkClick}
          cockpitSection={cockpitSection}
          analysisFailedAlert={analysisFailedAlert}
          fullAnalysisErrorAlert={fullAnalysisErrorAlert}
          initialAnalysisLoadingSection={initialAnalysisLoadingSection}
          analysisEvidenceFlow={analysisEvidenceFlow}
          modelSignalMatrixSection={modelSignalMatrixSection}
          crisisEvidenceSection={crisisEvidenceSection}
          reportBundleSection={reportBundleSection}
        />
      )}
    </section>
  );
}
