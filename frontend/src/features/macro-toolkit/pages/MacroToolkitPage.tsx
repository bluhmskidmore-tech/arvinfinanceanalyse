import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
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
import { flushSync } from "react-dom";

import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitScriptRecord,
} from "../../../api/macroToolkitClient";
import {
  MT_SHELL_MAIN,
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

import { MacroStatusIcon, MetricTile } from "../lib/macroToolkitPanelShared";
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
  deriveModelReadinessFromHasonStrategy,
} from "../panels/MacroToolkitSignalPanels";
import {
  compareRepairPriority,
  coverageValue,
  repairItemFocusKey,
} from "../lib/macroToolkitDataHealthSupport";
import {
  formatBusinessEvidenceList,
  formatObservationEvidence,
  formatObservationRecommendation,
  formatObservationSignalTitle,
  formatQueryError,
  formatSize,
  groupLabel,
  isMacroToolkitReadForbidden,
  isObservationOutputSignal,
  isReadyStatus,
} from "../lib/macroToolkitDisplayFormat";
import { buildMacroToolkitCommitteeModel } from "../lib/macroToolkitCommitteeModel";
import {
  MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
  MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN,
  MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE,
  MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
  governanceFocusFromEvidenceHref,
  macroToolkitDeferredContentStageForHref,
  pickDefaultCommitteeScript,
} from "../lib/macroToolkitPageModel";
import type {
  MacroToolkitDeferredContentStage,
  MacroToolkitGovernanceFocusKey,
} from "../lib/macroToolkitPageModel";
import {
  hasCompleteRealStrategyChain,
  hasRealStrategySource,
} from "../lib/macroToolkitStrategyDisplaySupport";
import { MacroToolkitCapabilityResultsSection } from "../sections/MacroToolkitCapabilityCards";
import { MacroToolkitAnalysisEvidenceFlow } from "../sections/MacroToolkitAnalysisEvidenceSections";
import {
  MacroToolkitExecutionReceiptWorkspace,
  MacroToolkitOperationsConsolePanel,
} from "../sections/MacroToolkitExecutionSections";
import {
  MacroToolkitHeaderControls,
  MacroToolkitInitialAnalysisLoading,
  MacroToolkitPageErrorState,
} from "../sections/MacroToolkitPageStates";
import { MacroToolkitSignalSection } from "../sections/MacroToolkitSignalSections";
import { useMacroToolkitOperationActions } from "./useMacroToolkitOperationActions";
import { ObservationEvidenceTraceSummary } from "../sections/MacroToolkitDataHealthSections";
import {
  MacroToolkitCommitteeDecisionAction,
  MacroToolkitDeepEvidenceRailCard,
  MacroToolkitGovernanceGatePanel,
  MacroToolkitInvestmentBriefPanel,
  MacroToolkitOperationsBand,
} from "../sections/MacroToolkitGovernanceSections";
import { MacroToolkitIndicatorSection } from "../sections/MacroToolkitIndicatorSections";
import {
  MacroToolkitInvestmentEvidenceSection,
  MacroToolkitObservationComparisonSection,
  MacroToolkitObservationDecisionSummary,
} from "../sections/MacroToolkitObservationSections";
import { MacroToolkitContractBoundary } from "../sections/MacroToolkitPrimitives";
import { MacroToolkitRiskSection } from "../sections/MacroToolkitRiskSections";
import { MacroToolkitStrategySection } from "../sections/MacroToolkitStrategySections";

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
  const deferredContentSentinelRef = useRef<HTMLDivElement | null>(null);
  const [deferredContentStage, setDeferredContentStage] =
    useState<MacroToolkitDeferredContentStage>(() =>
      !showOperations
        ? MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
        : typeof window !== "undefined"
          ? (macroToolkitDeferredContentStageForHref(window.location.hash) ?? 0)
          : 0,
  );
  const [pendingDeferredHashTarget, setPendingDeferredHashTarget] = useState<
    string | null
  >(() =>
    showOperations &&
    typeof window !== "undefined" &&
    macroToolkitDeferredContentStageForHref(window.location.hash) !== null
      ? window.location.hash
      : null,
  );
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedGovernanceFocus, setSelectedGovernanceFocus] =
    useState<MacroToolkitGovernanceFocusKey>("evidence");
  const [selectedEvidenceHref, setSelectedEvidenceHref] = useState<string | null>(null);
  const [selectedExecutionHref, setSelectedExecutionHref] = useState<string | null>(null);
  const [receiptTechnicalDetailsExpanded, setReceiptTechnicalDetailsExpanded] = useState(
    () =>
      showOperations &&
      typeof window !== "undefined" &&
      window.location.hash === "#macro-toolkit-script-artifact-detail",
  );
  const [focusedRepairKey, setFocusedRepairKey] = useState<string | null>(null);
  const [committeeActionLocatorKey, setCommitteeActionLocatorKey] = useState<string | null>(null);
  const committeeActionLocatorRef = useRef<HTMLDivElement | null>(null);
  const [fullAnalysisEnvelope, setFullAnalysisEnvelope] =
    useState<ApiEnvelope<MacroToolkitAnalysisPayload> | null>(null);
  const [fullAnalysisError, setFullAnalysisError] = useState<string | null>(null);
  const [isLoadingFullAnalysis, setIsLoadingFullAnalysis] = useState(false);

  const revealAllDeferredContent = useCallback(() => {
    if (!showOperations) {
      return;
    }
    setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
    setReceiptTechnicalDetailsExpanded(true);
  }, [showOperations]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const handleBeforePrint = () => {
      flushSync(revealAllDeferredContent);
    };
    window.addEventListener("beforeprint", handleBeforePrint);
    return () => window.removeEventListener("beforeprint", handleBeforePrint);
  }, [revealAllDeferredContent, showOperations]);

  useEffect(() => {
    if (
      !showOperations ||
      deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
    ) {
      return undefined;
    }

    const sentinel = deferredContentSentinelRef.current;
    if (typeof window.IntersectionObserver === "undefined" || !sentinel) {
      setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
      return undefined;
    }

    const nextStage = (deferredContentStage + 1) as MacroToolkitDeferredContentStage;
    const observer = new window.IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          setDeferredContentStage((currentStage) =>
            Math.max(currentStage, nextStage) as MacroToolkitDeferredContentStage,
          );
          observer.disconnect();
        }
      },
      {
        rootMargin:
          deferredContentStage === MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE - 1
            ? "0px"
            : MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN,
        threshold: 0.01,
      },
    );
    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [deferredContentStage, showOperations]);

  const revealDeferredContentForHref = useCallback(
    (href: string | null) => {
      if (!showOperations || !href) {
        return;
      }
      const requestedStage = macroToolkitDeferredContentStageForHref(href);
      if (requestedStage === null) {
        return;
      }
      if (href === "#macro-toolkit-script-artifact-detail") {
        setReceiptTechnicalDetailsExpanded(true);
      }
      setDeferredContentStage((currentStage) =>
        Math.max(currentStage, requestedStage) as MacroToolkitDeferredContentStage,
      );
    },
    [showOperations],
  );

  const syncDeferredContentSelectionForHref = useCallback((href: string) => {
    if (macroToolkitDeferredContentStageForHref(href) === null) {
      return;
    }
    if (
      href === "#macro-toolkit-operations-actions" ||
      href === "#macro-toolkit-operations-console"
    ) {
      setSelectedExecutionHref(href);
    } else {
      setSelectedEvidenceHref(href);
    }
    setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
  }, []);

  useEffect(() => {
    revealDeferredContentForHref(selectedExecutionHref);
    revealDeferredContentForHref(selectedEvidenceHref);
  }, [
    revealDeferredContentForHref,
    selectedEvidenceHref,
    selectedExecutionHref,
  ]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const revealHashTarget = () => {
      const href = window.location.hash;
      setPendingDeferredHashTarget(
        macroToolkitDeferredContentStageForHref(href) !== null ? href : null,
      );
      syncDeferredContentSelectionForHref(href);
      revealDeferredContentForHref(href);
    };
    revealHashTarget();
    window.addEventListener("hashchange", revealHashTarget);
    return () => window.removeEventListener("hashchange", revealHashTarget);
  }, [
    revealDeferredContentForHref,
    showOperations,
    syncDeferredContentSelectionForHref,
  ]);

  useEffect(() => {
    if (
      !showOperations ||
      !pendingDeferredHashTarget?.startsWith("#macro-toolkit-")
    ) {
      return undefined;
    }
    const requestedStage = macroToolkitDeferredContentStageForHref(
      pendingDeferredHashTarget,
    );
    if (
      requestedStage === null ||
      deferredContentStage < requestedStage ||
      (pendingDeferredHashTarget === "#macro-toolkit-script-artifact-detail" &&
        !receiptTechnicalDetailsExpanded)
    ) {
      return undefined;
    }

    let frame: number | null = null;
    const scrollToHashTarget = () => {
      const target = document.getElementById(pendingDeferredHashTarget.slice(1));
      if (typeof target?.scrollIntoView !== "function") {
        return false;
      }
      target.scrollIntoView({ block: "start", inline: "nearest" });
      setPendingDeferredHashTarget((currentTarget) =>
        currentTarget === pendingDeferredHashTarget ? null : currentTarget,
      );
      return true;
    };
    const scheduleScroll = () => {
      if (typeof window.requestAnimationFrame === "function") {
        frame = window.requestAnimationFrame(() => {
          scrollToHashTarget();
        });
        return;
      }
      scrollToHashTarget();
    };
    if (document.getElementById(pendingDeferredHashTarget.slice(1))) {
      scheduleScroll();
      return () => {
        if (frame !== null) {
          window.cancelAnimationFrame(frame);
        }
      };
    }
    if (typeof window.MutationObserver === "undefined") {
      scheduleScroll();
      return undefined;
    }
    const observer = new window.MutationObserver(() => {
      if (!document.getElementById(pendingDeferredHashTarget.slice(1))) {
        return;
      }
      observer.disconnect();
      scheduleScroll();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [
    deferredContentStage,
    pendingDeferredHashTarget,
    receiptTechnicalDetailsExpanded,
    showOperations,
  ]);

  const handleDeferredContentLinkClick = useCallback(
    (event: ReactMouseEvent<HTMLElement>) => {
      if (!showOperations) {
        return;
      }
      const target = event.target;
      const anchor =
        target instanceof Element
          ? target.closest<HTMLAnchorElement>('a[href^="#macro-toolkit-"]')
          : null;
      if (anchor) {
        const href = anchor.getAttribute("href");
        if (!href || macroToolkitDeferredContentStageForHref(href) === null) {
          return;
        }
        setPendingDeferredHashTarget(href);
        syncDeferredContentSelectionForHref(href);
        revealDeferredContentForHref(href);
      }
    },
    [
      revealDeferredContentForHref,
      showOperations,
      syncDeferredContentSelectionForHref,
    ],
  );

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
  const outputDetail = payload?.output_files.length
    ? `${payload.output_files[0]!.name} · ${formatSize(payload.output_files[0]!.size_bytes)}`
    : payload?.output_dir ?? "data/macro_toolkit/output";
  const cffexStatus = payload?.cffex_member_rank ?? analysis?.cffex_member_rank ?? null;
  const choiceStockRefresh =
    strategyPayload?.choice_stock_refresh ?? payload?.choice_stock_refresh ?? analysis?.choice_stock_refresh ?? null;
  const commodityFuturesRefresh = payload?.commodity_futures_refresh ?? null;
  const commodityStatus = commodityFuturesRefresh?.status ?? null;
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
  const {
    actionReceipt,
    actionReceipts,
    chainRunError,
    chainRunModelId,
    chainRunResult,
    clearFullAnalysisCache,
    commodityEvidenceReloadMessage,
    commodityPermission,
    commodityRefreshError,
    commodityRefreshEvidenceChain,
    commodityRefreshResult,
    commodityRefreshRun,
    commodityShortfallChanges,
    commodityShortfallEstimates,
    commoditySuggestedSelection,
    confirmActionReceipt,
    confirmedReceiptIds,
    crisisGapRepairFeedback,
    isCommodityRefreshAllowed,
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
    refreshMacroSourceBackfill,
    refreshResult,
    refreshingSourceAlias,
    reviewFullAnalysisRepair,
    runError,
    runResult,
    runScriptChain,
    runSelectedScript,
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
    stockRefreshError,
    stockRefreshResult,
  } = useMacroToolkitOperationActions({
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
  useEffect(() => {
    if (selectedEvidenceHref === "#macro-toolkit-script-artifact-detail") {
      setReceiptTechnicalDetailsExpanded(true);
    }
  }, [selectedEvidenceHref]);
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
  } = buildMacroToolkitCommitteeModel({
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
  const selectedGovernanceFocusItem =
    governanceFocusItems.find((item) => item.key === selectedGovernanceFocus) ?? governanceFocusItems[0]!;
  const isAuditTargetActive = useCallback(
    (href: string, governanceKeys: MacroToolkitGovernanceFocusKey[] = []) =>
      selectedEvidenceHref ? selectedEvidenceHref === href : governanceKeys.includes(selectedGovernanceFocus),
    [selectedEvidenceHref, selectedGovernanceFocus],
  );
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
    [committeeDecisionHref, focusDataHealthRepair],
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

  const isAnalysisLoading = analysisQuery.isLoading && !analysis;
  const signalSection = analysis ? (
    <MacroToolkitSignalSection
      showOperations={showOperations}
      visibleSignalCards={visibleSignalCards}
      crisisScoreResult={crisisScoreResult}
    />
  ) : null;
  const riskSection = analysis ? (
    <MacroToolkitRiskSection showOperations={showOperations} risk={analysis.a_share_risk} />
  ) : null;
  const observationSignalRiskComparisonSection = analysis ? (
    <MacroToolkitObservationComparisonSection
      signalCards={visibleSignalCards}
      primarySignal={primarySignal}
      risk={analysis.a_share_risk}
    />
  ) : null;
  const observationSignalRiskLoadingSection = !showOperations && !analysis ? (
    <MacroToolkitObservationComparisonSection signalCards={[]} primarySignal={null} isLoading />
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
  const strategySection = analysis ? (
    <MacroToolkitStrategySection
      showOperations={showOperations}
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
    <MacroToolkitIndicatorSection showOperations={showOperations} analysis={analysis} />
  ) : null;
  const investmentEvidenceSection = analysis ? (
    <MacroToolkitInvestmentEvidenceSection
      analysis={analysis}
      showOperations={showOperations}
      selectedEvidenceHref={selectedEvidenceHref}
      strategySummaries={strategySummaries}
      strategySupplyState={strategySupplyState}
      fullRealStrategyCount={fullRealStrategyCount}
      partialRealStrategyCount={partialRealStrategyCount}
      degradedStrategyCount={degradedStrategyCount}
      sampleStrategyCount={sampleStrategyCount}
      shadowPortfolioReport={shadowPortfolioReport}
      strategyQuery={strategyQuery}
    />
  ) : null;
  const capabilityResultsSection = analysis ? (
    <MacroToolkitCapabilityResultsSection
      capabilityResults={capabilityResults}
      isCoreAnalysis={isCoreAnalysis}
      isLoadingFullAnalysis={isLoadingFullAnalysis}
      loadFullAnalysis={loadFullAnalysis}
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
  const observationEvidenceTraceSummary = analysis ? (
    <ObservationEvidenceTraceSummary
      dataHealth={analysis.data_health}
      capabilityResults={capabilityResults}
      degradedResultCount={degradedResultCount}
      hasonStrategy={hasonStrategy ?? undefined}
      isCoreAnalysis={isCoreAnalysis}
    />
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
  const investmentBriefPanel = showOperations ? (
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
  ) : null;
  const governanceGatePanel = showOperations ? (
    <MacroToolkitGovernanceGatePanel
      analysisMeta={analysisMeta}
      governanceFocusItems={governanceFocusItems}
      selectedGovernanceFocusItem={selectedGovernanceFocusItem}
      setSelectedGovernanceFocus={setSelectedGovernanceFocus}
    />
  ) : null;
  const operationsConsolePanel = showOperations ? (
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
          deferredContentStage={deferredContentStage}
          receiptTechnicalDetailsExpanded={receiptTechnicalDetailsExpanded}
          revealAllDeferredContent={revealAllDeferredContent}
        />
        <p className="macro-toolkit-page__header-summary">
          {showOperations
            ? "先看结论、信号和指标结果；数据核对与脚本执行收在页面后段。"
            : "只展示宏观分析证据；刷新、脚本和注册表保留在宏观工具页。"}
        </p>
      </header>

      <main
        className={`${MT_SHELL_MAIN} macro-toolkit-page__main${
          showOperations ? " macro-toolkit-page__main--with-rail" : ""
        }`}
        onClickCapture={handleDeferredContentLinkClick}
      >
      <div className="macro-toolkit-page__primary">
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
                  value={primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : "缺失"}
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

      {showOperations && analysis ? (
        <div className="macro-toolkit-page__content macro-toolkit-first-screen-flow">
          {signalSection}
        </div>
      ) : null}

      {showOperations && deferredContentStage === 0 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-deferred-content-sentinel"
          aria-hidden="true"
        />
      ) : null}

      {!showOperations || deferredContentStage >= 1 ? (
      <div className="macro-toolkit-page__content">
      {analysisQuery.isError ? (
        <Alert type="error" showIcon message="宏观分析结果加载失败" />
      ) : null}

      {fullAnalysisError ? (
        <Alert type="error" showIcon message="完整分析加载失败" description={fullAnalysisError} />
      ) : null}

      {isAnalysisLoading ? (
        <MacroToolkitInitialAnalysisLoading
          showOperations={showOperations}
          observationSignalRiskLoadingSection={observationSignalRiskLoadingSection}
        />
      ) : null}

      {analysis ? (
        <>
          {showOperations ? (
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
          ) : (
            <>
              {analysisEvidenceFlow}
              <div className="macro-toolkit-observation-flow" aria-label="宏观观察阅读顺序">
                {observationSignalRiskComparisonSection}
                {modelSignalMatrixSection}
                {investmentEvidenceSection}
              </div>
              <div className="macro-toolkit-observation-evidence-flow" aria-label="宏观观察证据追踪">
                {crisisEvidenceSection}
                {observationEvidenceTraceSummary}
              </div>
            </>
          )}
        </>
      ) : null}
      </div>
      ) : null}

      {showOperations && deferredContentStage >= 6 ? (
        <MacroToolkitOperationsBand operationsConsolePanel={operationsConsolePanel} />
      ) : null}

      {showOperations &&
      deferredContentStage >= 1 &&
      deferredContentStage < 6 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-progressive-deferred-content-sentinel"
          data-deferred-stage={deferredContentStage}
          aria-hidden="true"
        />
      ) : null}

      {showOperations && deferredContentStage === 6 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-execution-deferred-content-sentinel"
          aria-hidden="true"
        />
      ) : null}

      {!showOperations ||
      deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE ? (
        <>
          {analysis ? <MacroToolkitReportBundlePanel bundle={analysis.report_bundle} /> : null}
          {showOperations ? (
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
          ) : null}
        </>
      ) : null}
      </div>
      {showOperations ? (
        <aside
          className="macro-toolkit-meta-rail"
          aria-label="治理与证据栏"
          data-testid="macro-toolkit-meta-rail"
        >
          {investmentBriefPanel}
          <MacroToolkitDeepEvidenceRailCard deepEvidenceQueueItems={deepEvidenceQueueItems} />
          {governanceGatePanel}
        </aside>
      ) : null}
      </main>
    </section>
  );
}
