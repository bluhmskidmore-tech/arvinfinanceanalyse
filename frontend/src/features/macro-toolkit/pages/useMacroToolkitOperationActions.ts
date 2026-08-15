import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitCommodityFuturesRefreshStatus,
  MacroToolkitPayload,
  MacroToolkitRunResponse,
  MacroToolkitScriptChainRun,
  MacroToolkitScriptRecord,
} from "../../../api/macroToolkitClient";
import { runPollingTask } from "../../../app/jobs/polling";
import { EM_DASH } from "../../../utils/format";
import {
  buildCrisisGapRepairFeedback,
  canRefreshMacroSourceBackfill,
  commodityRefreshRunProducts,
  crisisCommodityShortItemsFromEnvelope,
  crisisCommodityShortItemsFromResult,
  crisisGapGroupFromResult,
  formatCommodityProducts,
  formatCommodityRefreshResult,
  formatCommodityShortfallChanges,
  formatCommodityShortfallEstimates,
  normalizeMacroSourceBackfillAlias,
} from "../lib/macroToolkitCrisisSupport";
import type {
  CommodityRefreshEvidenceChain,
  CommodityShortfallChange,
  CommodityShortfallEstimate,
  CrisisGapGroup,
  CrisisGapRepairFeedback,
} from "../lib/macroToolkitCrisisSupport";
import {
  formatDataHealthRepairLabel,
  repairItemFocusKey,
} from "../lib/macroToolkitDataHealthSupport";
import {
  DEFAULT_MACRO_COMMODITY_PRODUCTS,
  EMPTY_ACTION_RECEIPT,
  MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT,
  MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
  actionReceiptDecisionFields,
  asyncRefreshPendingMessage,
  cffexRefreshTerminalMessage,
  isCffexRefreshTerminal,
  isSourceBackfillTerminal,
  nextActionReceiptId,
  refreshFailureMessage,
  sameCommodityProducts,
  sourceBackfillTerminalMessage,
} from "../lib/macroToolkitPageModel";
import type {
  CommodityRefreshOptions,
  MacroToolkitActionReceipt,
  MacroToolkitGovernanceFocusKey,
  MacroToolkitRepairItem,
  RefreshFeedbackTone,
} from "../lib/macroToolkitPageModel";
import {
  commodityFuturesPermissionBlockMessage,
  formatCommodityFuturesRefreshError,
} from "../lib/macroToolkitStrategyDisplaySupport";

type RefetchableQuery = {
  refetch: () => Promise<unknown>;
};

export function useMacroToolkitOperationActions({
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
}: {
  analysis: MacroToolkitAnalysisPayload | undefined;
  analysisQuery: RefetchableQuery;
  commodityFuturesRefresh: MacroToolkitCommodityFuturesRefreshStatus | null;
  crisisScoreResult: MacroToolkitCapabilityResult | null;
  fullAnalysisError: string | null;
  isCoreAnalysis: boolean;
  loadFullAnalysis: (options?: {
    force?: boolean;
  }) => Promise<ApiEnvelope<MacroToolkitAnalysisPayload> | null>;
  payload: MacroToolkitPayload | undefined;
  scriptsQuery: RefetchableQuery;
  selectedScript: MacroToolkitScriptRecord | null;
  setCommitteeActionLocatorKey: (key: string | null) => void;
  setFocusedRepairKey: (key: string | null) => void;
  setFullAnalysisEnvelope: (envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null) => void;
  setFullAnalysisError: (error: string | null) => void;
  setSelectedEvidenceHref: (href: string | null) => void;
  setSelectedGovernanceFocus: (key: MacroToolkitGovernanceFocusKey) => void;
  strategyQuery: RefetchableQuery;
}) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [actionReceipt, setActionReceipt] = useState<MacroToolkitActionReceipt>(EMPTY_ACTION_RECEIPT);
  const [actionReceipts, setActionReceipts] = useState<MacroToolkitActionReceipt[]>([]);
  const [confirmedReceiptIds, setConfirmedReceiptIds] = useState<Set<string>>(() => new Set());

  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [chainRunResult, setChainRunResult] = useState<MacroToolkitScriptChainRun | null>(null);
  const [chainRunError, setChainRunError] = useState<string | null>(null);
  const [chainRunModelId, setChainRunModelId] = useState<string | null>(null);
  const [isRunningChain, setIsRunningChain] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshFeedbackTone, setRefreshFeedbackTone] = useState<RefreshFeedbackTone>("success");
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
  const [stockRefreshResult, setStockRefreshResult] = useState<string | null>(null);
  const [stockRefreshError, setStockRefreshError] = useState<string | null>(null);
  const [isRefreshingChoiceStock, setIsRefreshingChoiceStock] = useState(false);
  const [sourceBackfillResult, setSourceBackfillResult] = useState<string | null>(null);
  const [sourceBackfillError, setSourceBackfillError] = useState<string | null>(null);
  const [sourceBackfillFeedbackTone, setSourceBackfillFeedbackTone] =
    useState<RefreshFeedbackTone>("success");
  const [crisisGapRepairFeedback, setCrisisGapRepairFeedback] = useState<CrisisGapRepairFeedback | null>(null);
  const [refreshingSourceAlias, setRefreshingSourceAlias] = useState<string | null>(null);
  const [commodityRefreshResult, setCommodityRefreshResult] = useState<string | null>(null);
  const [commodityRefreshError, setCommodityRefreshError] = useState<string | null>(null);
  const [commodityRefreshRun, setCommodityRefreshRun] = useState<MacroToolkitCommodityFuturesRefreshRun | null>(null);
  const [commoditySuggestedSelection, setCommoditySuggestedSelection] = useState<string[]>([]);
  const [commodityEvidenceReloadMessage, setCommodityEvidenceReloadMessage] = useState<string | null>(null);
  const [commodityRefreshEvidenceChain, setCommodityRefreshEvidenceChain] =
    useState<CommodityRefreshEvidenceChain | null>(null);
  const [commodityShortfallChanges, setCommodityShortfallChanges] = useState<CommodityShortfallChange[]>([]);
  const [commodityShortfallEstimates, setCommodityShortfallEstimates] = useState<CommodityShortfallEstimate[]>([]);
  const [isRefreshingCommodity, setIsRefreshingCommodity] = useState(false);
  const [selectedCommodityProducts, setSelectedCommodityProducts] = useState<string[]>([
    ...DEFAULT_MACRO_COMMODITY_PRODUCTS,
  ]);
  const [isRunning, setIsRunning] = useState(false);

  // 卸载时取消来源补齐 / CFFEX / 选股刷新的长任务轮询（最长 240×5s），
  // 避免离开页面后继续请求并对已卸载组件 setState、批量 refetch。
  const unmountAbortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    unmountAbortRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const clearFullAnalysisCache = useCallback(async (options?: { preserveCrisisGapRepairFeedback?: boolean }) => {
    setFullAnalysisEnvelope(null);
    setFullAnalysisError(null);
    if (!options?.preserveCrisisGapRepairFeedback) {
      setCrisisGapRepairFeedback(null);
    }
    await queryClient.cancelQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
  }, [queryClient, setFullAnalysisEnvelope, setFullAnalysisError]);

  const recordActionReceipt = useCallback((receipt: MacroToolkitActionReceipt) => {
    setActionReceipt(receipt);
    if (receipt.status === "idle") {
      return;
    }
    setActionReceipts((current) => {
      const withoutSameAction = current.filter((item) => item.id !== receipt.id);
      return [receipt, ...withoutSameAction].slice(0, MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT);
    });
  }, []);

  const confirmActionReceipt = useCallback((receiptId: string) => {
    setConfirmedReceiptIds((current) => {
      if (current.has(receiptId)) {
        return current;
      }
      const next = new Set(current);
      next.add(receiptId);
      return next;
    });
  }, []);

  const commodityPermission = commodityRefreshRun?.permission ?? commodityFuturesRefresh?.permission ?? null;

  const isCommodityRefreshAllowed = commodityPermission?.allowed === true;

  const reviewFullAnalysisRepair = useCallback(async (item: MacroToolkitRepairItem) => {
    const receiptId = nextActionReceiptId("full-analysis");
    const receiptDecision = actionReceiptDecisionFields("full-analysis");
    const target = formatDataHealthRepairLabel(item, false);
    setFocusedRepairKey(repairItemFocusKey(item));
    setCommitteeActionLocatorKey(repairItemFocusKey(item));
    setSelectedEvidenceHref("#macro-toolkit-data-health-detail");
    setSelectedGovernanceFocus("data-health");
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "完整分析复核",
      status: "running",
      time: "进行中",
      target,
      artifact: "完整分析读取中",
      nextStep: "等待完整分析返回后复核数据健康",
    });
    const response = await loadFullAnalysis({ force: item.scope === "full" });
    if (response) {
      const fullRepairCount = response.result.data_health?.repair_items?.length ?? 0;
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "完整分析复核",
        status: "completed",
        time: "刚刚",
        target,
        artifact: fullRepairCount ? `完整分析仍有 ${fullRepairCount} 项待处理` : "完整分析已返回",
        nextStep: "复核完整分析回执并确认数据健康签核",
      });
      return response;
    }
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "完整分析复核",
      status: "failed",
      time: "刚刚",
      target,
      artifact: fullAnalysisError ?? "完整分析读取失败",
      nextStep: "检查完整分析读取权限和接口状态",
    });
    return null;
  }, [
    fullAnalysisError,
    loadFullAnalysis,
    recordActionReceipt,
    setCommitteeActionLocatorKey,
    setFocusedRepairKey,
    setSelectedEvidenceHref,
    setSelectedGovernanceFocus,
  ]);

  const refreshMacroSourceBackfill = useCallback(
    async (item: MacroToolkitRepairItem, gapGroup?: CrisisGapGroup) => {
      const alias = normalizeMacroSourceBackfillAlias(item.alias);
      if (!alias || !canRefreshMacroSourceBackfill(item)) {
        return;
      }
      const signal = unmountAbortRef.current?.signal;
      const receiptId = nextActionReceiptId("source-backfill");
      const receiptDecision = actionReceiptDecisionFields("source-backfill");
      setRefreshingSourceAlias(alias);
      setSourceBackfillError(null);
      setSourceBackfillResult(null);
      setSourceBackfillFeedbackTone("info");
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "来源补齐",
        status: "running",
        time: "进行中",
        target: alias,
        artifact: "宏观来源补齐中",
        nextStep: "等待补齐完成后重读完整分析",
      });
      if (gapGroup) {
        setCrisisGapRepairFeedback({
          groupKey: gapGroup.key,
          groupLabel: gapGroup.label,
          status: "pending",
          message: "正在补齐并重读完整分析",
          detail: item.action?.label ?? alias,
        });
      }
      try {
        const refresh = await runPollingTask({
          start: async () => {
            const response = await client.refreshMacroSourceBackfill({
              alias,
              endDate: item.reference_date ?? analysis?.as_of_date ?? undefined,
              sources: undefined,
            });
            return {
              ...response.result.refresh,
              report_date: response.result.refresh.report_date ?? undefined,
              source_version: response.result.refresh.source_version ?? undefined,
            };
          },
          getStatus: async (runId) => {
            const response = await client.getMacroSourceBackfillRefreshStatus(runId);
            return {
              ...response.result.refresh,
              report_date: response.result.refresh.report_date ?? undefined,
              source_version: response.result.refresh.source_version ?? undefined,
            };
          },
          intervalMs: 5_000,
          maxAttempts: 240,
          signal,
          isTerminal: isSourceBackfillTerminal,
          onUpdate: (payload) => {
            if (isSourceBackfillTerminal(payload.status)) return;
            setSourceBackfillFeedbackTone("info");
            setSourceBackfillResult(asyncRefreshPendingMessage("来源补齐", payload.status));
          },
        });
        if (refresh.status === "failed") {
          throw new Error(refreshFailureMessage("来源补齐", refresh.failure_category));
        }
        if (signal?.aborted) return;
        const isCompleted = refresh.status === "completed";
        const isPartial = refresh.status === "partial";
        const resultMessage = sourceBackfillTerminalMessage(refresh);
        setSourceBackfillFeedbackTone(isCompleted ? "success" : "warning");
        setSourceBackfillResult(resultMessage);
        recordActionReceipt({
          id: receiptId,
          ...receiptDecision,
          action: "来源补齐",
          status: isCompleted ? "completed" : "warning",
          time: "刚刚",
          target: alias,
          artifact: resultMessage,
          nextStep: isCompleted ? "重读完整分析并复核数据健康" : "复核未完成来源，数据健康保持阻断",
        });
        if (isCompleted || isPartial) {
          await clearFullAnalysisCache({ preserveCrisisGapRepairFeedback: Boolean(gapGroup) });
          const reloaded = await loadFullAnalysis();
          if (gapGroup) {
            const reloadedFeedback = buildCrisisGapRepairFeedback(gapGroup, reloaded, resultMessage);
            setCrisisGapRepairFeedback(
              isPartial
                ? {
                    ...reloadedFeedback,
                    status: "partial",
                    message: "来源补齐部分完成，完整分析已重读",
                  }
                : reloadedFeedback,
            );
          }
        } else if (gapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: gapGroup.key,
            groupLabel: gapGroup.label,
            status: "partial",
            message: refresh.status === "blocked" ? "来源补齐受阻，缺口仍需处理" : "来源未返回可补齐数据",
            detail: resultMessage,
          });
        }
      } catch (error) {
        if (signal?.aborted) return;
        const errorMessage = error instanceof Error ? error.message : "来源补齐失败";
        setSourceBackfillError(errorMessage);
        setSourceBackfillResult(null);
        recordActionReceipt({
          id: receiptId,
          ...receiptDecision,
          action: "来源补齐",
          status: "failed",
          time: "刚刚",
          target: alias,
          artifact: errorMessage,
          nextStep: "检查来源补齐授权和数据源",
        });
        if (gapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: gapGroup.key,
            groupLabel: gapGroup.label,
            status: "failed",
            message: "补齐失败，缺口仍需处理",
            detail: errorMessage,
          });
        }
      } finally {
        if (!signal?.aborted) {
          setRefreshingSourceAlias(null);
        }
      }
    },
    [analysis?.as_of_date, clearFullAnalysisCache, client, loadFullAnalysis, recordActionReceipt],
  );

  const runSelectedScript = useCallback(async () => {
    if (!selectedScript) {
      return;
    }
    const receiptId = nextActionReceiptId("script");
    const receiptDecision = actionReceiptDecisionFields("script");
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "运行脚本",
      status: "running",
      time: "进行中",
      target: selectedScript.name,
      artifact: payload?.output_dir ?? "data/macro_toolkit/output",
      nextStep: "等待脚本返回后核对脚本产物",
    });
    try {
      const result = await client.runMacroToolkitScript(selectedScript.name);
      setRunResult(result);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "运行脚本",
        status: result.status === "completed" ? "completed" : result.status === "timeout" ? "warning" : "failed",
        time: "刚刚",
        target: selectedScript.name,
        artifact: `输出文件 ${result.output_files.length} · 退出码 ${result.exit_code ?? "无"}`,
        nextStep: "核对脚本产物与注册表状态",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "运行失败";
      setRunError(errorMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "运行脚本",
        status: "failed",
        time: "刚刚",
        target: selectedScript.name,
        artifact: errorMessage,
        nextStep: "检查脚本注册表和运行日志",
      });
    } finally {
      setIsRunning(false);
    }
  }, [
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    payload?.output_dir,
    recordActionReceipt,
    scriptsQuery,
    selectedScript,
    strategyQuery,
  ]);

  const runScriptChain = useCallback(async (dryRun: boolean, modelId?: string) => {
    const receiptId = nextActionReceiptId(dryRun ? "script-chain-dry-run" : "script-chain");
    const receiptDecision = actionReceiptDecisionFields("script");
    setChainRunModelId(modelId ?? null);
    setIsRunningChain(true);
    setChainRunError(null);
    setChainRunResult(null);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: dryRun ? "预检模型运行链" : "运行模型链",
      status: "running",
      time: "进行中",
      target: "macro_toolkit_chain",
      artifact: payload?.output_dir ?? "data/macro_toolkit/output",
      nextStep: dryRun ? "核对 manifest 与 expected_outputs" : "等待模型链返回后核对产物回执",
    });
    try {
      const response = await client.runMacroToolkitScriptChain({ dryRun });
      const result = response.result.run;
      setChainRunResult(result);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预检模型运行链" : "运行模型链",
        status: result.status === "completed" || result.status === "dry_run" ? "completed" : "warning",
        time: "刚刚",
        target: "macro_toolkit_chain",
        artifact: `步骤 ${result.receipts.length}/${result.manifest.length} · 缺口 ${result.readiness_after.degraded_count}`,
        nextStep: "核对 model_readiness 与 receipts",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "模型链运行失败";
      setChainRunError(errorMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预检模型运行链" : "运行模型链",
        status: "failed",
        time: "刚刚",
        target: "macro_toolkit_chain",
        artifact: errorMessage,
        nextStep: "检查执行权限、脚本依赖和运行链回执",
      });
    } finally {
      setIsRunningChain(false);
    }
  }, [
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    payload?.output_dir,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const refreshCffexMemberRank = useCallback(async () => {
    const signal = unmountAbortRef.current?.signal;
    const receiptId = nextActionReceiptId("cffex");
    const receiptDecision = actionReceiptDecisionFields("cffex");
    setIsRefreshingCffex(true);
    setRefreshError(null);
    setRefreshResult(null);
    setRefreshFeedbackTone("info");
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "刷新 CFFEX 席位",
      status: "running",
      time: "进行中",
      target: "CFFEX 席位",
      artifact: "中金所席位读取中",
      nextStep: "等待刷新完成后核对席位状态",
    });
    try {
      const refresh = await runPollingTask({
        start: async () => {
          const response = await client.refreshCffexMemberRank({
            tradeDate: analysis?.as_of_date ?? undefined,
          });
          return {
            ...response.result.refresh,
            report_date: response.result.refresh.report_date ?? undefined,
            source_version: response.result.refresh.source_version ?? undefined,
          };
        },
        getStatus: async (runId) => {
          const response = await client.getCffexMemberRankRefreshStatus(runId);
          return {
            ...response.result.refresh,
            report_date: response.result.refresh.report_date ?? undefined,
            source_version: response.result.refresh.source_version ?? undefined,
          };
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        signal,
        isTerminal: isCffexRefreshTerminal,
        onUpdate: (payload) => {
          if (isCffexRefreshTerminal(payload.status)) return;
          setRefreshFeedbackTone("info");
          setRefreshResult(asyncRefreshPendingMessage("CFFEX席位刷新", payload.status));
        },
      });
      if (refresh.status === "failed") {
        throw new Error(refreshFailureMessage("CFFEX席位刷新", refresh.failure_category));
      }
      if (signal?.aborted) return;
      const isCompleted = refresh.status === "completed";
      const resultMessage = cffexRefreshTerminalMessage(refresh);
      setRefreshFeedbackTone(isCompleted ? "success" : "warning");
      setRefreshResult(resultMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新 CFFEX 席位",
        status: isCompleted ? "completed" : "warning",
        time: "刚刚",
        target: "CFFEX 席位",
        artifact: resultMessage,
        nextStep: isCompleted ? "核对 CFFEX席位状态" : "复核未完成来源，席位状态保持待确认",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      if (signal?.aborted) return;
      const errorMessage = error instanceof Error ? error.message : "刷新席位失败";
      setRefreshError(errorMessage);
      setRefreshResult(null);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新 CFFEX 席位",
        status: "failed",
        time: "刚刚",
        target: "CFFEX 席位",
        artifact: errorMessage,
        nextStep: "检查席位刷新权限和数据源",
      });
    } finally {
      if (!signal?.aborted) {
        setIsRefreshingCffex(false);
      }
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const refreshChoiceStock = useCallback(async () => {
    const signal = unmountAbortRef.current?.signal;
    const receiptId = nextActionReceiptId("choice-stock");
    const receiptDecision = actionReceiptDecisionFields("choice-stock");
    setIsRefreshingChoiceStock(true);
    setStockRefreshError(null);
    setStockRefreshResult("正在刷新股票历史数据和完整因子");
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "刷新股票策略",
      status: "running",
      time: "进行中",
      target: "Choice 股票历史 + 因子",
      artifact: "等待异步任务完成",
      nextStep: "完成后核对策略供数闭环",
    });
    try {
      const refresh = await runPollingTask<MacroToolkitChoiceStockRefreshRun>({
        start: async () => {
          const response = await client.refreshChoiceStock({
            asOfDate: analysis?.as_of_date ?? undefined,
            refreshHistory: true,
            refreshFactors: true,
            factorMaxStockCount: null,
          });
          return response.result.refresh;
        },
        getStatus: async (runId) => {
          const response = await client.getChoiceStockRefreshStatus(runId);
          return response.result.refresh;
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        signal,
        onUpdate: (payload) => {
          setStockRefreshResult(
            payload.status === "completed"
              ? `刷新完成：历史 ${payload.history_row_count ?? EM_DASH} 行，因子 ${payload.factor_row_count ?? EM_DASH} 行`
              : `刷新状态：${payload.status}`,
          );
        },
      });
      if (refresh.status !== "completed") {
        throw new Error(
          refreshFailureMessage("股票刷新", refresh.failure_category),
        );
      }
      if (signal?.aborted) return;
      setStockRefreshResult(
        `刷新完成：历史 ${refresh.history_row_count ?? EM_DASH} 行，因子 ${refresh.factor_row_count ?? EM_DASH} 行`,
      );
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新股票策略",
        status: "completed",
        time: "刚刚",
        target: "Choice 股票历史 + 因子",
        artifact: `历史 ${refresh.history_row_count ?? EM_DASH} 行 · 因子 ${refresh.factor_row_count ?? EM_DASH} 行`,
        nextStep: "核对策略展示和刷新状态",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      if (signal?.aborted) return;
      const errorMessage = error instanceof Error ? error.message : "刷新股票数据失败";
      setStockRefreshError(errorMessage);
      setStockRefreshResult(null);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新股票策略",
        status: "failed",
        time: "刚刚",
        target: "Choice 股票历史 + 因子",
        artifact: errorMessage,
        nextStep: "检查 Choice 授权和异步任务状态",
      });
    } finally {
      if (!signal?.aborted) {
        setIsRefreshingChoiceStock(false);
      }
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const refreshCommodityFutures = useCallback(async (options?: CommodityRefreshOptions) => {
    const dryRun = options?.dryRun ?? false;
    const products = options?.products ?? selectedCommodityProducts;
    const receiptId = nextActionReceiptId(dryRun ? "commodity-dry-run" : "commodity-refresh");
    const receiptDecision = actionReceiptDecisionFields(dryRun ? "commodity-dry-run" : "commodity-refresh");
    if (products.length === 0) {
      setCommodityRefreshError("请至少选择一个商品期货品种");
      setCommodityRefreshResult(null);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      return;
    }
    if (options?.products && !sameCommodityProducts(selectedCommodityProducts, options.products)) {
      setSelectedCommodityProducts(options.products);
    }
    if (!isCommodityRefreshAllowed) {
      setCommodityRefreshError(commodityFuturesPermissionBlockMessage(commodityPermission));
      setCommodityRefreshResult(null);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      return;
    }
    setIsRefreshingCommodity(true);
    setCommodityRefreshError(null);
    setCommodityRefreshResult(null);
    setCommodityRefreshRun(null);
    setCommoditySuggestedSelection(options?.suggestedSelection ?? []);
    setCommodityEvidenceReloadMessage(null);
    setCommodityRefreshEvidenceChain(null);
    setCommodityShortfallChanges([]);
    setCommodityShortfallEstimates([]);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: dryRun ? "预估商品期货" : "刷新商品期货",
      status: "running",
      time: "进行中",
      target: formatCommodityProducts(products),
      artifact: dryRun ? "估算写入行数" : "fact_commodity_futures_daily",
      nextStep: dryRun ? "根据预计行数决定是否正式刷新" : "刷新后核对商品期货状态",
    });
    const shouldReloadFullAnalysis = !dryRun && !isCoreAnalysis;
    const shortfallsBeforeRefresh = crisisCommodityShortItemsFromResult(crisisScoreResult);
    const commodityGapGroup = crisisGapGroupFromResult(crisisScoreResult, "commodity");
    if (shouldReloadFullAnalysis && commodityGapGroup) {
      setCrisisGapRepairFeedback({
        groupKey: commodityGapGroup.key,
        groupLabel: commodityGapGroup.label,
        status: "pending",
        message: "正在刷新并重读完整分析",
        detail: formatCommodityProducts(products),
      });
    }
    try {
      const response = await client.refreshCommodityFutures({
        startDate: options?.startDate,
        endDate: analysis?.as_of_date ?? undefined,
        products,
        dryRun,
      });
      const refresh = response.result.refresh;
      setCommodityRefreshRun(refresh);
      setCommodityRefreshResult(formatCommodityRefreshResult(refresh));
      const isQueuedRefresh = refresh.status === "queued";
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预估商品期货" : "刷新商品期货",
        status: refresh.status === "completed" || refresh.status === "dry_run" ? "completed" : "warning",
        time: "刚刚",
        target: formatCommodityProducts(products),
        artifact: formatCommodityRefreshResult(refresh),
        nextStep: dryRun ? "根据预计行数决定是否正式刷新" : "核对商品期货状态与完整分析证据",
      });
      if (dryRun) {
        setCommodityShortfallEstimates(formatCommodityShortfallEstimates(shortfallsBeforeRefresh, refresh));
        return;
      }
      setCommodityRefreshEvidenceChain({
        suggestedProducts: options?.suggestedSelection ?? products,
        refreshedProducts: commodityRefreshRunProducts(refresh),
        fullReloaded: false,
      });
      if (isQueuedRefresh) {
        setCommodityEvidenceReloadMessage("商品期货刷新已排队，等待后台任务完成。");
        if (commodityGapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: commodityGapGroup.key,
            groupLabel: commodityGapGroup.label,
            status: "pending",
            message: "商品期货刷新已排队。",
            detail: formatCommodityRefreshResult(refresh),
          });
        }
        await scriptsQuery.refetch();
        return;
      }
      await clearFullAnalysisCache({ preserveCrisisGapRepairFeedback: shouldReloadFullAnalysis && Boolean(commodityGapGroup) });
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      if (shouldReloadFullAnalysis) {
        setCommodityEvidenceReloadMessage("正在重新读取完整分析证据");
        const reloaded = await loadFullAnalysis({ force: true });
        const shortfallsAfterRefresh = crisisCommodityShortItemsFromEnvelope(reloaded);
        setCommodityShortfallChanges(
          formatCommodityShortfallChanges(shortfallsBeforeRefresh, shortfallsAfterRefresh),
        );
        setCommodityRefreshEvidenceChain((chain) =>
          chain
            ? {
                ...chain,
                fullReloaded: Boolean(reloaded),
              }
            : chain,
        );
        if (commodityGapGroup) {
          setCrisisGapRepairFeedback(
            buildCrisisGapRepairFeedback(commodityGapGroup, reloaded, formatCommodityRefreshResult(refresh)),
          );
        }
        setCommodityEvidenceReloadMessage(
          reloaded ? "完整分析证据已重新读取" : "完整分析证据重新读取失败，请重新完整分析",
        );
      }
    } catch (error) {
      const errorMessage = formatCommodityFuturesRefreshError(error);
      setCommodityRefreshError(errorMessage);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预估商品期货" : "刷新商品期货",
        status: "failed",
        time: "刚刚",
        target: formatCommodityProducts(products),
        artifact: errorMessage,
        nextStep: "检查商品期货刷新授权和数据源",
      });
      if (commodityGapGroup) {
        setCrisisGapRepairFeedback({
          groupKey: commodityGapGroup.key,
          groupLabel: commodityGapGroup.label,
          status: "failed",
          message: dryRun ? "预估失败，缺口仍需处理" : "刷新失败，缺口仍需处理",
          detail: errorMessage,
        });
      }
    } finally {
      setIsRefreshingCommodity(false);
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    crisisScoreResult,
    isCoreAnalysis,
    isCommodityRefreshAllowed,
    loadFullAnalysis,
    commodityPermission,
    recordActionReceipt,
    scriptsQuery,
    selectedCommodityProducts,
    strategyQuery,
  ]);

  return {
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
  };
}

export type MacroToolkitOperationActionsModel = ReturnType<
  typeof useMacroToolkitOperationActions
>;
