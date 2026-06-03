import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Checkbox, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import type {
  MacroToolkitCapability,
  MacroToolkitCapabilityResult,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitCommodityFuturesRefreshStatus,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitChoiceStockRefreshPermission,
  MacroToolkitAShareRiskPayload,
  MacroToolkitAnalysisPayload,
  MacroToolkitDataHealth,
  MacroToolkitHasonStrategy,
  MacroToolkitInputEvidence,
  MacroToolkitIndicator,
  MacroToolkitOutputFile,
  MacroToolkitRunResponse,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitShadowPortfolio,
  MacroToolkitShadowPortfolioHolding,
  MacroToolkitShadowPortfolioPeriodReturn,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSourceCheck,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import {
  DataStatusStrip,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";

import "./MacroToolkitPage.css";

const GROUP_LABELS: Record<string, string> = {
  allocation: "配置",
  credit: "信用",
  diagnostic: "诊断",
  macro_signal: "宏观信号",
  market_regime: "市场状态",
  news: "新闻",
  rates: "利率",
  report: "报告",
  risk: "风险",
};

const EMPTY_SCRIPTS: MacroToolkitScriptRecord[] = [];
const MACRO_TOOLKIT_ANALYSIS_KIND = "macro_toolkit.analysis";
const MACRO_TOOLKIT_UI_RULE_VERSION = "rv_macro_toolkit_ui_v1";
const MACRO_TOOLKIT_READ_STALE_MS = 60_000;
const MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS = 1_500;
const MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY = ["macro-toolkit", "analysis", "full"] as const;
const MACRO_COMMODITY_PRODUCT_OPTIONS = [
  { value: "RB", label: "螺纹钢", description: "黑色链条" },
  { value: "I", label: "铁矿石", description: "黑色链条" },
  { value: "CU", label: "铜", description: "有色金属" },
  { value: "AL", label: "铝", description: "有色金属" },
  { value: "SC", label: "原油", description: "能源" },
  { value: "AU", label: "黄金", description: "避险资产" },
  { value: "NHCI", label: "南华指数", description: "Crisis Score 输入" },
] as const;
const DEFAULT_MACRO_COMMODITY_PRODUCTS = MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => option.value);
const MACRO_COMMODITY_FIELD_TO_PRODUCT: Record<string, string> = {
  rebar: "RB",
  iron_ore: "I",
  copper: "CU",
  aluminum: "AL",
  crude_oil: "SC",
  gold: "AU",
};
const NANHUA_COMMODITY_PRODUCT_CODE = "NHCI";
const NANHUA_CRISIS_ALIAS = "NH0100.NHF";
const NANHUA_SYSTEM_SERIES_ID = "NHCI.NH";

type MacroToolkitPageMode = "toolkit" | "observation";
type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];
type CommodityRefreshOptions = {
  dryRun?: boolean;
  products?: string[];
  suggestedSelection?: string[];
};
type CommodityShortfallChange = {
  field: string;
  label: string;
  before: string;
  after: string;
};
type CommodityShortfallEstimate = CommodityShortfallChange & {
  estimatedRows: number;
  canFill: boolean;
};

const MACRO_SOURCE_BACKFILL_ALIASES = new Set(["M0041813"]);

type MacroToolkitPageProps = {
  mode?: MacroToolkitPageMode;
};

function normalizeMacroSourceBackfillAlias(alias: string | null | undefined) {
  return alias?.trim().toUpperCase() ?? "";
}

function canRefreshMacroSourceBackfill(item: MacroToolkitRepairItem) {
  return (
    item.action?.kind === "source_backfill_required" &&
    MACRO_SOURCE_BACKFILL_ALIASES.has(normalizeMacroSourceBackfillAlias(item.alias))
  );
}

function sameCommodityProducts(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

function groupLabel(group: string) {
  return GROUP_LABELS[group] ?? group;
}

function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function formatSourceCheck(check: MacroToolkitSourceCheck) {
  if (!check.latest) {
    return "未命中";
  }
  return `${check.latest.series_id} · ${check.latest.date}`;
}

function statusTone(status: MacroToolkitRunResponse["status"]) {
  if (status === "completed") return "success";
  if (status === "timeout") return "warning";
  return "error";
}

function toneTagColor(tone: MacroToolkitSignalCard["tone"]) {
  if (tone === "positive") return "green";
  if (tone === "negative") return "red";
  if (tone === "missing") return "default";
  return "blue";
}

function riskLevelColor(level: MacroToolkitAShareRiskPayload["risk_level"]) {
  if (level === "green") return "green";
  if (level === "yellow") return "gold";
  if (level === "orange") return "orange";
  if (level === "red") return "red";
  return "default";
}

function riskLevelTone(level: MacroToolkitAShareRiskPayload["risk_level"]): MacroToolkitSignalCard["tone"] {
  if (level === "green") return "positive";
  if (level === "unknown") return "missing";
  return level === "yellow" ? "neutral" : "negative";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    current: "已对齐",
    lagging: "轻微滞后",
    stale: "陈旧",
    missing: "缺失",
    unknown: "待确认",
    ready: "数据齐备",
    partial: "部分就绪",
    not_required: "无需数据",
    complete: "已完成",
    degraded: "部分降级",
    unavailable: "不可用",
    deferred: "已延后",
    loading: "加载中",
    failed: "失败",
    idle: "空闲",
    queued: "已排队",
    running: "运行中",
    completed: "已完成",
    aligned: "已对齐",
    fallback: "最近快照",
    library_ready: "函数已迁入",
    wired: "已接线",
    visible: "已展示",
    not_wired: "未接线",
    planned: "待接入",
    sample_only: "样例展示",
    observation_ready: "observation-ready",
  };
  return labels[status] ?? status;
}

function statusColor(status: string) {
  if (["current", "ready", "library_ready", "complete", "wired", "visible"].includes(status)) {
    return "green";
  }
  if (
    ["lagging", "partial", "planned", "degraded", "sample_only", "deferred", "loading", "observation_ready"].includes(
      status,
    )
  ) {
    return "gold";
  }
  if (["stale", "missing", "not_wired", "unavailable", "failed"].includes(status)) return "red";
  return "default";
}

function compactText(text: string | null | undefined, maxLength = 34) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function macroStatusIconTone(tone: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing") {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "missing") return "missing";
  return "neutral";
}

function MacroStatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing";
  children: ReactNode;
}) {
  return (
    <span className={`macro-toolkit-status-icon macro-toolkit-status-icon--${macroStatusIconTone(tone)}`}>
      {children}
    </span>
  );
}

function MacroToolkitContractBoundary({
  formalUseAllowed,
  resultKind,
  ruleVersion,
}: {
  formalUseAllowed?: boolean;
  resultKind?: string;
  ruleVersion?: string;
}) {
  return (
    <div
      className="macro-toolkit-contract-boundary"
      data-testid="macro-toolkit-contract-boundary"
      aria-label="宏观工具口径边界"
    >
      <span>
        <SafetyCertificateOutlined />
        分析/工具口径
      </span>
      <strong>{formalUseAllowed ? "正式可用" : "非正式口径"}</strong>
      <small>{resultKind ?? MACRO_TOOLKIT_ANALYSIS_KIND}</small>
      <small>{ruleVersion ?? MACRO_TOOLKIT_UI_RULE_VERSION}</small>
    </div>
  );
}

function formatValue(value: number | null, unit = "") {
  if (value === null) {
    return "缺失";
  }
  const digits = Math.abs(value) >= 100 ? 2 : 4;
  return `${value.toFixed(digits)}${unit}`;
}

function formatChange(change: number | null, changePct: number | null) {
  if (change === null && changePct === null) {
    return "无可比";
  }
  if (changePct !== null) {
    return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  }
  return `${change! >= 0 ? "+" : ""}${change!.toFixed(4)}`;
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function clampScore(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }
  return Math.min(100, Math.max(0, score));
}

type ScoreStyle = CSSProperties & { "--score": string };

function scoreStyle(score: number | null | undefined): ScoreStyle {
  return { "--score": `${clampScore(score)}%` };
}

function formatQueryError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "宏观工具接口暂不可用";
}

function isReadyStatus(status: string) {
  return ["current", "ready", "library_ready", "complete", "wired", "visible", "ok"].includes(status);
}

export default function MacroToolkitPage({ mode = "toolkit" }: MacroToolkitPageProps) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const showOperations = mode === "toolkit";
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
  const [stockRefreshResult, setStockRefreshResult] = useState<string | null>(null);
  const [stockRefreshError, setStockRefreshError] = useState<string | null>(null);
  const [isRefreshingChoiceStock, setIsRefreshingChoiceStock] = useState(false);
  const [sourceBackfillResult, setSourceBackfillResult] = useState<string | null>(null);
  const [sourceBackfillError, setSourceBackfillError] = useState<string | null>(null);
  const [refreshingSourceAlias, setRefreshingSourceAlias] = useState<string | null>(null);
  const [commodityRefreshResult, setCommodityRefreshResult] = useState<string | null>(null);
  const [commodityRefreshError, setCommodityRefreshError] = useState<string | null>(null);
  const [commodityRefreshRun, setCommodityRefreshRun] = useState<MacroToolkitCommodityFuturesRefreshRun | null>(null);
  const [commoditySuggestedSelection, setCommoditySuggestedSelection] = useState<string[]>([]);
  const [commodityEvidenceReloadMessage, setCommodityEvidenceReloadMessage] = useState<string | null>(null);
  const [commodityShortfallChanges, setCommodityShortfallChanges] = useState<CommodityShortfallChange[]>([]);
  const [commodityShortfallEstimates, setCommodityShortfallEstimates] = useState<CommodityShortfallEstimate[]>([]);
  const [isRefreshingCommodity, setIsRefreshingCommodity] = useState(false);
  const [selectedCommodityProducts, setSelectedCommodityProducts] = useState<string[]>([
    ...DEFAULT_MACRO_COMMODITY_PRODUCTS,
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [fullAnalysisEnvelope, setFullAnalysisEnvelope] =
    useState<ApiEnvelope<MacroToolkitAnalysisPayload> | null>(null);
  const [fullAnalysisError, setFullAnalysisError] = useState<string | null>(null);
  const [isLoadingFullAnalysis, setIsLoadingFullAnalysis] = useState(false);

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

  const fetchFullAnalysis = useCallback(
    () => client.getMacroToolkitAnalysis({ detail: "full" }),
    [client],
  );

  const clearFullAnalysisCache = useCallback(async () => {
    setFullAnalysisEnvelope(null);
    setFullAnalysisError(null);
    await queryClient.cancelQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
  }, [queryClient]);

  const payload = showOperations ? scriptsQuery.data?.result : undefined;
  const analysisEnvelope = fullAnalysisEnvelope ?? analysisQuery.data;
  const analysis = analysisEnvelope?.result;
  const scripts = payload?.scripts ?? EMPTY_SCRIPTS;
  const capabilityResults = analysis?.capability_results ?? [];
  const strategyPayload = strategyQuery.data?.result;
  const strategySummaries = strategyPayload?.strategy_summaries ?? analysis?.strategy_summaries ?? [];
  const shadowPortfolioReport =
    strategyPayload?.shadow_portfolio_report ?? analysis?.shadow_portfolio_report ?? null;
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
      ? "策略摘要正在生成，核心信号已先返回；市场踩踏风险和功能结果需打开完整分析后显示。"
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
    setSelectedName(filteredScripts[0]!.name);
  }, [filteredScripts, selectedName]);

  const selectedScript = useMemo(
    () => scripts.find((script) => script.name === selectedName) ?? filteredScripts[0] ?? null,
    [filteredScripts, scripts, selectedName],
  );
  const outputDetail = payload?.output_files.length
    ? `${payload.output_files[0]!.name} · ${formatSize(payload.output_files[0]!.size_bytes)}`
    : payload?.output_dir ?? "data/macro_toolkit/output";
  const cffexStatus = payload?.cffex_member_rank ?? analysis?.cffex_member_rank ?? null;
  const choiceStockRefresh =
    strategyPayload?.choice_stock_refresh ?? payload?.choice_stock_refresh ?? analysis?.choice_stock_refresh ?? null;
  const commodityFuturesRefresh = payload?.commodity_futures_refresh ?? null;
  const commodityPermission = commodityRefreshRun?.permission ?? commodityFuturesRefresh?.permission ?? null;
  const commodityStatus = commodityFuturesRefresh?.status ?? null;
  const isCommodityRefreshAllowed = commodityPermission?.allowed === true;
  const shouldShowCommodityPermissionNotice = !isCommodityRefreshAllowed;
  const commodityRefreshDisabled = selectedCommodityProducts.length === 0 || !isCommodityRefreshAllowed;
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
  const degradedResultCount = capabilityResults.filter((result) => result.status !== "complete").length;
  const missingIndicatorCount = analysis?.indicators.filter((indicator) => indicator.quality === "missing").length ?? 0;
  const primarySignal =
    analysis?.signal_cards
      .filter((card) => card.score != null)
      .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))[0] ?? null;
  const isCoreAnalysis = analysis?.runtime_status?.analysis_scope === "core";
  const isMacroRefreshing =
    analysisQuery.isFetching ||
    (showOperations && scriptsQuery.isFetching) ||
    strategyQuery.isFetching ||
    isRefreshingCommodity ||
    isLoadingFullAnalysis;
  const queryErrors = [analysisQuery.error, ...(showOperations ? [scriptsQuery.error] : []), strategyQuery.error];
  const queryErrorText = queryErrors
    .filter(Boolean)
    .map(formatQueryError)
    .join("；");
  const failedReadMessages = queryErrors
    .filter(Boolean)
    .map(formatQueryError);
  const runtimeSections = analysis?.runtime_status?.deferred_sections ?? [];
  const hasonStrategy = analysis?.hason_strategy ?? null;
  const showFullAnalysisActionInRuntime = isCoreAnalysis && runtimeSections.length > 0;
  const commodityRefreshActionLabel = formatCommodityRefreshActionLabel(commodityShortfallEstimates);

  useEffect(() => {
    if (fullAnalysisEnvelope || analysisQuery.data?.result.runtime_status?.analysis_scope !== "core") {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      void queryClient.prefetchQuery({
        queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
        queryFn: fetchFullAnalysis,
        staleTime: MACRO_TOOLKIT_READ_STALE_MS,
      });
    }, MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [analysisQuery.data?.result.runtime_status?.analysis_scope, fetchFullAnalysis, fullAnalysisEnvelope, queryClient]);

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

  const refreshMacroSourceBackfill = useCallback(
    async (item: MacroToolkitRepairItem) => {
      const alias = normalizeMacroSourceBackfillAlias(item.alias);
      if (!alias || !canRefreshMacroSourceBackfill(item)) {
        return;
      }
      setRefreshingSourceAlias(alias);
      setSourceBackfillError(null);
      setSourceBackfillResult(null);
      try {
        const response = await client.refreshMacroSourceBackfill({
          alias,
          endDate: item.reference_date ?? analysis?.as_of_date ?? undefined,
          sources: undefined,
        });
        const refresh = response.result.refresh;
        setSourceBackfillResult(`来源补齐完成：${refresh.alias} 新增 ${refresh.total_added} 行`);
        await clearFullAnalysisCache();
        await loadFullAnalysis();
      } catch (error) {
        setSourceBackfillError(error instanceof Error ? error.message : "来源补齐失败");
      } finally {
        setRefreshingSourceAlias(null);
      }
    },
    [analysis?.as_of_date, clearFullAnalysisCache, client, loadFullAnalysis],
  );

  const runSelectedScript = useCallback(async () => {
    if (!selectedScript) {
      return;
    }
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    try {
      const result = await client.runMacroToolkitScript(selectedScript.name);
      setRunResult(result);
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "运行失败");
    } finally {
      setIsRunning(false);
    }
  }, [analysisQuery, clearFullAnalysisCache, client, scriptsQuery, selectedScript, strategyQuery]);

  const refreshCffexMemberRank = useCallback(async () => {
    setIsRefreshingCffex(true);
    setRefreshError(null);
    setRefreshResult(null);
    try {
      const response = await client.refreshCffexMemberRank({
        tradeDate: analysis?.as_of_date ?? undefined,
      });
      const rank = response.result.cffex_member_rank;
      setRefreshResult(`刷新完成：${rank.row_count} 行，最新交易日 ${rank.latest_trade_date ?? "缺失"}`);
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新席位失败");
    } finally {
      setIsRefreshingCffex(false);
    }
  }, [analysis?.as_of_date, clearFullAnalysisCache, client, scriptsQuery, analysisQuery, strategyQuery]);

  const refreshChoiceStock = useCallback(async () => {
    setIsRefreshingChoiceStock(true);
    setStockRefreshError(null);
    setStockRefreshResult("正在刷新股票历史数据和完整因子");
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
        onUpdate: (payload) => {
          setStockRefreshResult(
            payload.status === "completed"
              ? `刷新完成：历史 ${payload.history_row_count ?? "-"} 行，因子 ${payload.factor_row_count ?? "-"} 行`
              : `刷新状态：${payload.status}`,
          );
        },
      });
      if (refresh.status !== "completed") {
        throw new Error(refresh.error_message ?? `股票刷新未完成：${refresh.status}`);
      }
      setStockRefreshResult(
        `刷新完成：历史 ${refresh.history_row_count ?? "-"} 行，因子 ${refresh.factor_row_count ?? "-"} 行`,
      );
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setStockRefreshError(error instanceof Error ? error.message : "刷新股票数据失败");
      setStockRefreshResult(null);
    } finally {
      setIsRefreshingChoiceStock(false);
    }
  }, [analysis?.as_of_date, analysisQuery, clearFullAnalysisCache, client, scriptsQuery, strategyQuery]);

  const refreshCommodityFutures = useCallback(async (options?: CommodityRefreshOptions) => {
    const dryRun = options?.dryRun ?? false;
    const products = options?.products ?? selectedCommodityProducts;
    if (products.length === 0) {
      setCommodityRefreshError("请至少选择一个商品期货品种");
      setCommodityRefreshResult(null);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
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
    setCommodityShortfallChanges([]);
    setCommodityShortfallEstimates([]);
    const shouldReloadFullAnalysis = !dryRun && !isCoreAnalysis;
    const shortfallsBeforeRefresh = crisisCommodityShortItemsFromResult(crisisScoreResult);
    try {
      const response = await client.refreshCommodityFutures({
        endDate: analysis?.as_of_date ?? undefined,
        products,
        dryRun,
      });
      const refresh = response.result.refresh;
      setCommodityRefreshRun(refresh);
      setCommodityRefreshResult(formatCommodityRefreshResult(refresh));
      if (dryRun) {
        setCommodityShortfallEstimates(formatCommodityShortfallEstimates(shortfallsBeforeRefresh, refresh));
        return;
      }
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      if (shouldReloadFullAnalysis) {
        setCommodityEvidenceReloadMessage("正在重新读取完整分析证据");
        const reloaded = await loadFullAnalysis({ force: true });
        const shortfallsAfterRefresh = crisisCommodityShortItemsFromEnvelope(reloaded);
        setCommodityShortfallChanges(
          formatCommodityShortfallChanges(shortfallsBeforeRefresh, shortfallsAfterRefresh),
        );
        setCommodityEvidenceReloadMessage(
          reloaded ? "完整分析证据已重新读取" : "完整分析证据重新读取失败，请重新完整分析",
        );
      }
    } catch (error) {
      setCommodityRefreshError(formatCommodityFuturesRefreshError(error));
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
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
    scriptsQuery,
    selectedCommodityProducts,
    strategyQuery,
  ]);

  const indicatorColumns: ColumnsType<MacroToolkitIndicator> = [
    {
      title: "指标",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{item.label}</span>
          <span className="macro-toolkit-script-file">{item.alias}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      width: 120,
      render: (group: string) => <Tag>{group}</Tag>,
    },
    {
      title: "最新值",
      dataIndex: "latest_value",
      key: "latest_value",
      width: 150,
      render: (_, item) => <IndicatorValueCell item={item} />,
    },
    {
      title: "变化",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 110,
      render: (_, item) => <DeltaCell change={item.change} changePct={item.change_pct} />,
    },
    {
      title: "日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: 120,
      render: (date: string | null, item) => (
        <div className="macro-toolkit-date-cell">
          <span>{date ?? "缺失"}</span>
          <Tag color={item.quality === "ok" ? "green" : "red"}>
            {item.quality === "ok" ? "可用" : "缺失"}
          </Tag>
        </div>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: string | null, item) => (
        <div className="macro-toolkit-source-cell">
          <span>{source ?? "未命中"}</span>
          <small>{item.series_id ?? item.alias}</small>
        </div>
      ),
    },
  ];

  const scriptColumns: ColumnsType<MacroToolkitScriptRecord> = [
    {
      title: "脚本",
      dataIndex: "name",
      key: "name",
      render: (_, script) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{script.name}</span>
          <span className="macro-toolkit-script-file">{script.filename}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      render: (group: string) => <Tag>{groupLabel(group)}</Tag>,
      width: 120,
    },
    {
      title: "数据源",
      dataIndex: "default_data_sources",
      key: "default_data_sources",
      render: (sources: string[]) => (
        <div className="macro-toolkit-tag-row">
          {sources.map((source) => (
            <Tag color={source === "choice" ? "blue" : "green"} key={source}>
              {source}
            </Tag>
          ))}
        </div>
      ),
      width: 160,
    },
    {
      title: "依赖",
      dataIndex: "optional_dependencies",
      key: "optional_dependencies",
      render: (deps: string[]) =>
        deps.length > 0 ? deps.join(" / ") : "内置",
    },
    {
      title: "状态",
      dataIndex: "available",
      key: "available",
      render: (available: boolean) => (
        <Tag color={available ? "green" : "red"}>{available ? "可运行" : "缺失"}</Tag>
      ),
      width: 100,
    },
  ];

  const capabilityColumns: ColumnsType<MacroToolkitCapability> = [
    {
      title: "功能",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">
            {item.legacy_module} · {item.label}
          </span>
          <span className="macro-toolkit-script-file">{item.group}</span>
        </div>
      ),
    },
    {
      title: "代码",
      dataIndex: "implementation_status",
      key: "implementation_status",
      width: 120,
      render: (status: string) => <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>,
    },
    {
      title: "页面/API",
      dataIndex: "route_status",
      key: "route_status",
      width: 140,
      render: (status: string, item) => (
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
          <Tag color={statusColor(item.frontend_status)}>{statusLabel(item.frontend_status)}</Tag>
        </div>
      ),
    },
    {
      title: "数据",
      dataIndex: "data_status",
      key: "data_status",
      width: 140,
      render: (status: string, item) => <CapabilityDataCell status={status} item={item} />,
    },
    {
      title: "下一步",
      dataIndex: "next_step",
      key: "next_step",
    },
  ];

  const outputColumns: ColumnsType<MacroToolkitOutputFile> = [
    { title: "文件", dataIndex: "name", key: "name" },
    {
      title: "大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: "更新时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 220,
    },
  ];

  const isAnalysisLoading = analysisQuery.isLoading && !analysis;

  if (!payload && !analysis && (analysisQuery.isError || (showOperations && scriptsQuery.isError))) {
    return (
      <PageStateSurface
        variant="error"
        testId="macro-toolkit-error-state"
        className="macro-toolkit-error-state"
        title="宏观工具暂不可用"
        description={queryErrorText || "后端宏观模块没有返回可展示数据。"}
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void analysisQuery.refetch();
              if (showOperations) {
                void scriptsQuery.refetch();
              }
              void strategyQuery.refetch();
            }}
            loading={analysisQuery.isFetching || (showOperations && scriptsQuery.isFetching) || strategyQuery.isFetching}
          >
            重试读取
          </Button>
        }
      >
        <MacroToolkitContractBoundary />
        {!showOperations ? (
          <Alert
            type="info"
            showIcon
            data-testid="macro-observation-readonly-boundary"
            message="read-only macro observation"
            description="This route exposes analytical macro evidence only. Refresh actions, script execution, and operational registries stay on /macro-toolkit."
          />
        ) : null}
        <div className="macro-toolkit-error-sources" aria-label="宏观工具失败来源">
          <span>失败来源</span>
          {failedReadMessages.length ? (
            failedReadMessages.map((message) => <small key={message}>{message}</small>)
          ) : (
            <small>后端宏观模块没有返回可展示数据。</small>
          )}
        </div>
      </PageStateSurface>
    );
  }

  return (
    <div className="macro-toolkit-page">
      <section
        data-testid="macro-toolkit-tailwind-cockpit"
        className="overflow-hidden rounded-xl border border-blue-100 bg-white text-slate-900 shadow-lg shadow-blue-100/70"
      >
        <div className="border-b border-blue-100 bg-[linear-gradient(135deg,#ffffff_0%,#f8fbff_52%,#eaf3ff_100%)] p-4 lg:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-slate-500">
                <ClockCircleOutlined className="text-blue-500" />
                <span className="font-mono">{analysis?.as_of_date ?? "DATE_MISSING"}</span>
              </div>
              <h1 className="mt-2 text-2xl font-black leading-tight text-blue-950 lg:text-4xl">宏观分析结果</h1>
            </div>
            {showOperations ? (
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  void clearFullAnalysisCache();
                  void analysisQuery.refetch();
                  void scriptsQuery.refetch();
                  void strategyQuery.refetch();
                }}
                loading={isMacroRefreshing}
              >
                刷新结果
              </Button>
            ) : null}
          </div>

          <div className="mt-4 grid gap-3">
            <MacroToolkitContractBoundary
              formalUseAllowed={analysisMeta?.formal_use_allowed}
              resultKind={analysisMeta?.result_kind}
              ruleVersion={analysisMeta?.rule_version}
            />
            {!showOperations ? (
              <Alert
                type="info"
                showIcon
                data-testid="macro-observation-readonly-boundary"
                message="read-only macro observation"
                description="This route exposes analytical macro evidence only. Refresh actions, script execution, and operational registries stay on /macro-toolkit."
              />
            ) : null}
            <div className="min-w-0 rounded-lg border border-blue-100 bg-blue-50/70 p-4 shadow-sm shadow-blue-100/60">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
                <MacroStatusIcon tone={analysis?.conclusion.tone ?? "missing"}>
                  {analysis?.conclusion.tone === "negative" || !analysis ? <WarningOutlined /> : <LineChartOutlined />}
                </MacroStatusIcon>
                投研观点
              </div>
              <strong className="mt-3 block truncate text-3xl font-black text-blue-950">
                {analysis?.conclusion.stance ?? "读取中"}
              </strong>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-700" title={analysis?.conclusion.summary}>
                {analysis?.conclusion.summary ?? "正在从系统数据源生成宏观判断。"}
              </p>
            </div>
            <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-3">
              <TailwindMetricTile
                icon={<SafetyCertificateOutlined />}
                label="证据覆盖"
                value={formatPercent(analysis?.coverage.hit_rate)}
                detail={`${analysis?.coverage.hit_count ?? 0}/${analysis?.coverage.indicator_count ?? 0} 指标命中`}
              />
              <TailwindMetricTile
                icon={<ClockCircleOutlined />}
                label="分析日期"
                value={analysis?.as_of_date ?? "缺失"}
                detail={(analysis?.default_data_sources ?? []).join(" + ") || "choice + tushare"}
              />
              <TailwindMetricTile
                icon={<ThunderboltOutlined />}
                label="能力闭环"
                value={`${readyCapabilityCount}/${capabilityItems.length || 0}`}
                detail={`${wiredCapabilityCount} 项已接到页面/API`}
              />
            </div>
          </div>
        </div>

      </section>

      {analysisQuery.isError ? (
        <Alert type="error" showIcon message="宏观分析结果加载失败" />
      ) : null}

      {fullAnalysisError ? (
        <Alert type="error" showIcon message="完整分析加载失败" description={fullAnalysisError} />
      ) : null}

      {isAnalysisLoading ? (
        <>
          <div data-testid="macro-toolkit-initial-analysis-loading">
            <Alert
              type="info"
              showIcon
              message="核心分析加载中"
              description="页面口径边界已就绪；核心信号和脚本注册表会在后端返回后自动补上。"
            />
          </div>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="signals"
              title="核心信号"
              description="等待后端宏观 analysis 结果返回。"
            />
            <div className="macro-toolkit-empty-output">核心分析加载中，暂不显示占位结论。</div>
          </section>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="risk"
              title="市场踩踏风险"
              description="等待 A 股宽度、跌停、成交与回落压力判断返回。"
            />
            <div className="macro-toolkit-empty-output">市场踩踏风险加载中，暂不推导风险等级。</div>
          </section>
        </>
      ) : null}

      {analysis ? (
        <>
          <DataStatusStrip className="macro-toolkit-status-strip">
            <span title={`读取口径：${analysisMeta?.basis ?? "-"}`}>
              <DatabaseOutlined /> {analysisMeta?.basis ?? "-"}
            </span>
            <span title={`质量：${analysisMeta?.quality_flag ?? "-"}`}>
              <SafetyCertificateOutlined /> {analysisMeta?.quality_flag ?? "-"}
            </span>
            <span title={`建议：${analysis.conclusion.recommended_action}`}>
              <ThunderboltOutlined /> {compactText(analysis.conclusion.recommended_action, 24)}
            </span>
          </DataStatusStrip>

          {runtimeSections.length ? (
            <div className="macro-toolkit-runtime-strip" aria-label="宏观工具运行状态">
              {runtimeSections.map((section) => (
                <span key={section.key}>
                  <ClockCircleOutlined />
                  {section.label} · <Tag color={statusColor(section.status)}>{statusLabel(section.status)}</Tag>
                </span>
              ))}
              {showFullAnalysisActionInRuntime ? (
                <Button
                  aria-label="查看完整分析"
                  size="small"
                  icon={<LineChartOutlined />}
                  loading={isLoadingFullAnalysis}
                  onClick={() => void loadFullAnalysis()}
                >
                  查看完整分析
                </Button>
              ) : null}
            </div>
          ) : null}

          {analysis.data_health ? (
            <MacroToolkitDataHealthPanel
              dataHealth={analysis.data_health}
              showActions={showOperations}
              onRepairAction={(item) => {
                if (item.action?.kind === "source_backfill_required") {
                  void refreshMacroSourceBackfill(item);
                  return;
                }
                void loadFullAnalysis({ force: item.scope === "full" });
              }}
              repairActionLoading={isLoadingFullAnalysis}
              refreshingSourceAlias={refreshingSourceAlias}
            />
          ) : null}
          {sourceBackfillResult ? <Alert type="success" showIcon message={sourceBackfillResult} /> : null}
          {sourceBackfillError ? <Alert type="error" showIcon message={sourceBackfillError} /> : null}

          <div className="macro-toolkit-readiness-strip" aria-label="宏观工具投研总览">
            <ReadinessTile
              icon={<LineChartOutlined />}
              label="主信号"
              value={primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : "缺失"}
              detail={primarySignal?.evidence.join(" / ") ?? "暂无可排序信号"}
              tone={primarySignal?.tone ?? "missing"}
            />
            <ReadinessTile
              icon={<ClockCircleOutlined />}
              label="数据新鲜度"
              value={analysis.as_of_date ?? "缺失"}
              detail={`${missingIndicatorCount} 个指标缺失；${sourceHitCount} 个源命中`}
              tone={missingIndicatorCount > 0 ? "neutral" : "positive"}
            />
            <ReadinessTile
              icon={<ThunderboltOutlined />}
              label="模型结果"
              value={`${capabilityResults.length} 个功能输出`}
              detail={`${degradedResultCount} 个降级或不可用结果`}
              tone={degradedResultCount > 0 ? "neutral" : "positive"}
            />
          </div>

          {hasonStrategy ? <HasonMacroStrategyPanel strategy={hasonStrategy} /> : null}

          {analysis.warnings.length ? (
            <Alert
              type="warning"
              showIcon
              message="分析限制"
              description={analysis.warnings.join(" ")}
            />
          ) : null}

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="signals"
              title="核心信号"
              description="由系统内 Choice/Tushare 序列直接计算，脚本产物作为补充证据。"
            />
            <div className="macro-toolkit-signal-grid">
              {analysis.signal_cards.map((card) => (
                <div
                  className={`macro-toolkit-signal-card macro-toolkit-signal-card--${card.tone}`}
                  key={card.key}
                  style={scoreStyle(card.score)}
                >
                  <div className="macro-toolkit-signal-head">
                    <span>{card.title}</span>
                    <Tag color={toneTagColor(card.tone)}>{card.stance}</Tag>
                  </div>
                  <strong>{card.score === null ? "缺失" : card.score}</strong>
                  <div className="macro-toolkit-score-track" aria-hidden="true">
                    <span />
                  </div>
                  <small>{card.evidence.join(" / ")}</small>
                </div>
              ))}
            </div>
          </section>

          {crisisScoreResult ? (
            <CrisisScoreEvidencePanel
              result={crisisScoreResult}
              repairItems={analysis.data_health?.repair_items ?? []}
              refreshingSourceAlias={refreshingSourceAlias}
              commodityRefreshResult={commodityRefreshResult}
              commodityShortfallEstimates={commodityShortfallEstimates}
              sourceBackfillResult={sourceBackfillResult}
              sourceBackfillError={sourceBackfillError}
              onRepairSourceBackfill={(item) => {
                void refreshMacroSourceBackfill(item);
              }}
              onApplyCommodityRefreshProducts={(products) => {
                setSelectedCommodityProducts(products);
                setCommoditySuggestedSelection(products);
                setCommodityRefreshResult(null);
                setCommodityRefreshError(null);
                setCommodityRefreshRun(null);
                setCommodityEvidenceReloadMessage(null);
                setCommodityShortfallChanges([]);
                setCommodityShortfallEstimates([]);
              }}
              onPreviewCommodityRefreshProducts={(products) => {
                void refreshCommodityFutures({ dryRun: true, products, suggestedSelection: products });
              }}
            />
          ) : null}

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="risk"
              title="市场踩踏风险"
              description="接入宏观分析结果链路的 A股盘后宽度、跌停、成交与回落压力判断。"
            />
            <AShareRiskPanel risk={analysis.a_share_risk} />
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="indicators"
              title="指标矩阵"
              description="展示每个宏观指标的最新值、变化、日期和数据来源。"
            />
            <Table
              rowKey="alias"
              size="small"
              columns={indicatorColumns}
              dataSource={analysis.indicators}
              pagination={false}
              tableLayout="fixed"
              scroll={{ x: 920 }}
              rowClassName={(item) =>
                item.quality === "missing" ? "macro-toolkit-row--missing" : ""
              }
            />
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="results"
              title="功能结果"
              description="M7-M16 已按现有宏观纯函数和正式事实表输出结果，缺口只保留为数据降级提示。"
            />
            {capabilityResults.length ? (
              <div className="macro-toolkit-capability-result-grid">
                {capabilityResults.map((result) => (
                  <CapabilityResultCard result={result} key={result.key} />
                ))}
              </div>
            ) : isCoreAnalysis ? (
              <Alert
                type="info"
                showIcon
                message="M7-M16 功能结果正在生成"
                description="核心信号已先返回；市场踩踏风险和功能结果需打开完整分析后显示。"
                action={
                  <Button
                    aria-label="查看完整分析"
                    size="small"
                    icon={<LineChartOutlined />}
                    loading={isLoadingFullAnalysis}
                    onClick={() => void loadFullAnalysis()}
                  >
                    查看完整分析
                  </Button>
                }
              />
            ) : (
              <div className="macro-toolkit-empty-output">暂无 M7-M16 功能结果。</div>
            )}
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="strategies"
              title="策略展示"
              description={strategyDescription}
            />
            {showOperations ? (
              <div className="macro-toolkit-stock-refresh-panel">
                <div className="macro-toolkit-cffex-metrics">
                  <MetricTile
                    label="股票历史"
                    value={choiceStockRefresh?.daily_observation?.stock_count ?? 0}
                    detail={choiceStockTableDetail(choiceStockRefresh?.daily_observation, "latest_trade_date")}
                  />
                  <MetricTile
                    label="完整因子"
                    value={choiceStockRefresh?.factor_snapshot?.stock_count ?? 0}
                    detail={choiceStockTableDetail(choiceStockRefresh?.factor_snapshot, "as_of_date")}
                  />
                  <MetricTile
                    label="刷新状态"
                    value={choiceStockRefreshValue(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
                    detail={choiceStockRefreshDetail(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
                  />
                </div>
                <div className="macro-toolkit-cffex-actions">
                  <Button
                    icon={<ReloadOutlined />}
                    loading={isRefreshingChoiceStock}
                    onClick={() => void refreshChoiceStock()}
                  >
                    刷新股票数据
                  </Button>
                  {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
                  {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
                </div>
              </div>
            ) : null}
            <div className="macro-toolkit-strategy-supply-strip" aria-label="策略供数闭环">
              <span className="macro-toolkit-strategy-supply-label">
                <DatabaseOutlined />
                策略供数闭环
              </span>
              {strategySupplyState === "loaded" ? (
                <>
                  <span>
                    <DatabaseOutlined />
                    完整链路 {fullRealStrategyCount}/{strategySummaries.length}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    部分链路 {partialRealStrategyCount}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    降级 {degradedStrategyCount}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    样例 {sampleStrategyCount}
                  </span>
                </>
              ) : (
                <span>
                  <ClockCircleOutlined />
                  策略供数 {statusLabel(strategySupplyState)}
                </span>
              )}
              <span>
                <ClockCircleOutlined />
                股票历史 {choiceStockTableSummary(choiceStockRefresh?.daily_observation, "latest_trade_date")}
              </span>
              <span>
                <ClockCircleOutlined />
                因子快照 {choiceStockTableSummary(choiceStockRefresh?.factor_snapshot, "as_of_date")}
              </span>
            </div>
            <ShadowPortfolioReportPanel report={shadowPortfolioReport} />
            {strategySummaries.length ? (
              <div className="macro-toolkit-strategy-grid">
                {strategySummaries.map((strategy) => (
                  <StrategySummaryCard strategy={strategy} key={strategy.key} />
                ))}
              </div>
            ) : strategyQuery.isFetching ? (
              <Alert
                type="info"
                showIcon
                message="策略展示正在生成"
                description="核心信号已先返回；市场踩踏风险需打开完整分析后显示。"
              />
            ) : strategyQuery.isError ? (
              <Alert
                type="warning"
                showIcon
                message="策略展示暂不可用"
                description={formatQueryError(strategyQuery.error)}
              />
            ) : (
              <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
            )}
          </section>
        </>
      ) : null}

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="closure"
          title="功能补齐方案"
          description="按 V1 宏观分析 M7-M16 对齐，区分代码迁入、API/页面接线和数据命中。"
        />
        {capabilityItems.length ? (
          <Table
            rowKey="key"
            size="small"
            columns={capabilityColumns}
            dataSource={capabilityItems}
            pagination={false}
            tableLayout="fixed"
            scroll={{ x: 920 }}
          />
        ) : scriptsQuery.isFetching ? (
          <Alert
            type="info"
            showIcon
            message="功能补齐方案正在读取"
            description="不会阻塞核心信号和市场踩踏风险。"
          />
        ) : (
          <div className="macro-toolkit-empty-output">暂无功能补齐方案。</div>
        )}
      </section>

      {showOperations ? (
        <>
          <section className="macro-toolkit-section macro-toolkit-operations-section">
            <div className="macro-toolkit-section-headline">
              <PageSectionLead
                eyebrow="toolkit"
                title="宏观工具"
                description="迁移脚本是否已经能在系统 Choice/Tushare 数据源上直接运行？"
                style={{ marginTop: 0 }}
              />
              <Button
                icon={<ReloadOutlined />}
                onClick={() => void scriptsQuery.refetch()}
                loading={scriptsQuery.isFetching}
              >
                刷新
              </Button>
            </div>
            {scriptsQuery.isFetching && !payload ? (
              <Alert
                type="info"
                showIcon
                message="脚本注册表正在读取"
                description="脚本状态会稍后补上，核心分析已可先查看。"
              />
            ) : null}
            <div className="macro-toolkit-operations-brief">
              <MetricTile
                label="脚本就绪"
                value={`${availableScriptCount}/${scripts.length}`}
                detail="已进入宏观模块注册表"
                tone={availableScriptCount === scripts.length ? "positive" : "neutral"}
              />
              <MetricTile
                label="默认数据源"
                value={(payload?.default_data_sources ?? []).join(" + ") || "无"}
                detail="与系统口径保持一致"
              />
              <MetricTile label="输出文件" value={payload?.output_files.length ?? 0} detail={outputDetail} />
              <MetricTile
                label="源别名命中"
                value={`${sourceHitCount}/${sourceChecks.length}`}
                detail="旧代码别名到当前数据面的映射"
              />
            </div>
          </section>

          {scriptsQuery.isError ? <Alert type="error" showIcon message="宏观工具加载失败" /> : null}

          {payload ? (
            <DataStatusStrip className="macro-toolkit-status-strip">
              <span>读取口径：{scriptsQuery.data?.result_meta.basis}</span>
              <span>表：{scriptsQuery.data?.result_meta.tables_used?.join(" / ")}</span>
              <span>质量：{scriptsQuery.data?.result_meta.quality_flag}</span>
            </DataStatusStrip>
          ) : null}

          {payload?.warnings.length ? (
            <Alert
              type="warning"
              showIcon
              message="仍有未落库的数据面"
              description={payload.warnings.join(" ")}
            />
          ) : null}

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="cffex"
              title="CFFEX席位状态"
              description="crowding_cn 等脚本依赖的中金所席位排名读面。"
            />
            <div className="macro-toolkit-cffex-panel">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  label="席位行数"
                  value={cffexStatus?.row_count ?? 0}
                  detail={cffexStatus?.status ?? "未读取"}
                />
                <MetricTile
                  label="最新交易日"
                  value={cffexStatus?.latest_trade_date ?? "缺失"}
                  detail={`对齐 ${cffexStatus?.reference_date ?? analysis?.as_of_date ?? "待定"}`}
                />
                <MetricTile
                  label="新鲜度"
                  value={statusLabel(cffexStatus?.freshness_status ?? "unknown")}
                  detail={
                    cffexStatus?.stale_days == null ? "待确认" : `落后 ${cffexStatus.stale_days} 天`
                  }
                />
              </div>
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCffex}
                  onClick={() => void refreshCffexMemberRank()}
                >
                  刷新席位
                </Button>
                {refreshResult ? <Alert type="success" showIcon message={refreshResult} /> : null}
                {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
              </div>
            </div>
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="commodity"
              title="商品期货状态"
              description="刷新南华指数和宏观旁证商品期货；Crisis Score 公式仍只读取南华输入。"
            />
            <div className="macro-toolkit-cffex-panel" aria-label="商品期货刷新">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="已选品种"
                  value={`${selectedCommodityProducts.length}/${MACRO_COMMODITY_PRODUCT_OPTIONS.length}`}
                  detail={
                    selectedCommodityProducts.length === MACRO_COMMODITY_PRODUCT_OPTIONS.length
                      ? "默认全选，可缩小范围"
                      : selectedCommodityProducts.join(" / ") || "未选择"
                  }
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品权限"
                  value={choiceStockPermissionValue(commodityPermission)}
                  detail={commodityFuturesPermissionDetail(commodityPermission)}
                  tone={shouldShowCommodityPermissionNotice ? "missing" : "neutral"}
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="南华输入"
                  value={commodityNanhuaStatusValue(commodityStatus)}
                  detail={commodityNanhuaStatusDetail(commodityStatus)}
                  tone={commodityNanhuaStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<ClockCircleOutlined />}
                  label="最新日期"
                  value={commodityLatestDateValue(commodityStatus)}
                  detail={commodityTableStatusDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="覆盖品种"
                  value={commodityCoverageValue(commodityStatus)}
                  detail={commodityCoverageDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="数据来源"
                  value={commoditySourceValue(commodityStatus)}
                  detail={commoditySourceDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="目标表"
                  value="fact_commodity_futures_daily"
                  detail="刷新后重新读取完整分析证据"
                />
              </div>
              <div className="macro-toolkit-commodity-selector">
                <span className="macro-toolkit-commodity-selector-label">刷新品种</span>
                <Checkbox.Group
                  className="macro-toolkit-commodity-products"
                  value={selectedCommodityProducts}
                  onChange={(values) => {
                    setSelectedCommodityProducts(values.map(String));
                    setCommoditySuggestedSelection([]);
                    setCommodityRefreshResult(null);
                    setCommodityRefreshError(null);
                    setCommodityRefreshRun(null);
                    setCommodityEvidenceReloadMessage(null);
                    setCommodityShortfallChanges([]);
                    setCommodityShortfallEstimates([]);
                  }}
                >
                  {MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => (
                    <Checkbox key={option.value} value={option.value}>
                      <span className="macro-toolkit-commodity-product-text">
                        <span>{option.label}</span>
                        <small>
                          {option.value} · {option.description}
                        </small>
                      </span>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </div>
              {commoditySuggestedSelection.length ? (
                <Alert
                  type="info"
                  showIcon
                  message={`已按 Crisis Score 建议选择：${commoditySuggestedSelection.join(" / ")}`}
                  description="下一步先预估商品期货，再根据预计行数决定是否刷新。"
                />
              ) : null}
              {shouldShowCommodityPermissionNotice ? (
                <Alert
                  type="warning"
                  showIcon
                  message={commodityFuturesPermissionNoticeTitle(commodityPermission)}
                  description={commodityFuturesPermissionNotice(commodityPermission)}
                />
              ) : null}
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<InfoCircleOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled}
                  onClick={() => void refreshCommodityFutures({ dryRun: true })}
                >
                  预估商品期货
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled}
                  aria-label={commodityRefreshActionLabel}
                  onClick={() => void refreshCommodityFutures({ dryRun: false })}
                >
                  {commodityRefreshActionLabel}
                </Button>
                {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
                {commodityEvidenceReloadMessage ? (
                  <Alert
                    type={commodityEvidenceReloadMessage.includes("失败") ? "error" : "success"}
                    showIcon
                    message={commodityEvidenceReloadMessage}
                  />
                ) : null}
                {commodityShortfallChanges.length ? (
                  <Alert
                    type="success"
                    showIcon
                    message="Crisis Score 样本缺口变化"
                    description={formatCommodityShortfallChangeList(commodityShortfallChanges)}
                  />
                ) : null}
                {commodityShortfallEstimates.length ? (
                  <Alert
                    type={commodityShortfallEstimates.every((item) => item.canFill) ? "success" : "warning"}
                    showIcon
                    message="Crisis Score 样本预估"
                    description={formatCommodityShortfallEstimateList(commodityShortfallEstimates)}
                  />
                ) : null}
                {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
              </div>
              {commodityRefreshRun ? <CommodityRefreshResultPanel refresh={commodityRefreshRun} /> : null}
            </div>
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="outputs"
              title="脚本产物"
              description="运行脚本后自动刷新这里，便于确认 CSV、图片或报告是否生成。"
            />
            {payload?.output_files.length ? (
              <Table
                rowKey="path"
                size="small"
                columns={outputColumns}
                dataSource={payload.output_files}
                pagination={false}
              />
            ) : (
              <div className="macro-toolkit-empty-output">尚未发现输出文件。</div>
            )}
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="source"
              title="系统数据源命中"
              description="这些旧代码别名已经映射到当前系统的 Choice/Tushare 数据面。"
            />
            <div className="macro-toolkit-source-grid">
              {sourceChecks.map((check) => (
                <div className="macro-toolkit-source-item" key={check.alias}>
                  <span>{check.alias}</span>
                  <strong>{check.row_count}</strong>
                  <small>{formatSourceCheck(check)}</small>
                </div>
              ))}
            </div>
          </section>

          {omittedEntries.length ? (
            <section className="macro-toolkit-section">
              <PageSectionLead
                eyebrow="omitted"
                title="未纳入脚本"
                description="这些源文件保留为迁移证据，但暂不作为可执行宏观工作流。"
              />
              <div className="macro-toolkit-omitted-list">
                {omittedEntries.map(([filename, reason]) => (
                  <div className="macro-toolkit-omitted-item" key={filename}>
                    <span>{filename}</span>
                    <small>{reason}</small>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="scripts"
              title="脚本注册表"
              description="脚本从原 macro_toolkit 聚合到后端宏观模块，前端通过注册表展示。"
            />
            <div className="macro-toolkit-toolbar">
              <Select
                value={selectedGroup}
                options={groupOptions}
                onChange={(value) => {
                  setSelectedGroup(value);
                  setSelectedName(null);
                }}
              />
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                disabled={!selectedScript}
                loading={isRunning}
                onClick={() => void runSelectedScript()}
              >
                运行选中脚本
              </Button>
            </div>
            <Table
              rowKey="name"
              size="small"
              columns={scriptColumns}
              dataSource={filteredScripts}
              pagination={{ pageSize: 8, showSizeChanger: false }}
              rowClassName={(script) =>
                script.name === selectedScript?.name ? "macro-toolkit-row--selected" : ""
              }
              onRow={(script) => ({
                onClick: () => setSelectedName(script.name),
              })}
            />
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="run"
              title="运行结果"
              description={selectedScript ? selectedScript.name : "暂无选中脚本"}
            />
            <div className="macro-toolkit-run-panel">
              <div className="macro-toolkit-run-title">
                <ToolOutlined />
                <span>{selectedScript?.filename ?? "未选择"}</span>
              </div>
              {runError ? <Alert type="error" showIcon message={runError} /> : null}
              {runResult ? (
                <Alert
                  type={statusTone(runResult.status)}
                  showIcon
                  message={`状态：${runResult.status}`}
                  description={`退出码：${runResult.exit_code ?? "无"} · 输出文件：${runResult.output_files.length}`}
                />
              ) : null}
              <pre className="macro-toolkit-console">
                {runResult?.stdout || runResult?.stderr || "尚未运行。"}
              </pre>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const evidence = result.evidence.length ? result.evidence : result.warnings;
  const inputEvidence = normalizeInputEvidence(result);
  return (
    <div
      className={`macro-toolkit-capability-result macro-toolkit-capability-result--${result.tone}`}
      style={scoreStyle(result.score)}
    >
      <div className="macro-toolkit-capability-result-head">
        <span>
          {result.legacy_module} · {result.label}
        </span>
        <Tag color={statusColor(result.status)}>{statusLabel(result.status)}</Tag>
      </div>
      <strong>{metric ? formatMetricDisplay(metric) : result.score ?? statusLabel(result.status)}</strong>
      <div className="macro-toolkit-score-track" aria-hidden="true">
        <span />
      </div>
      <p>{result.headline}</p>
      <small>{evidence.slice(0, 3).join(" / ") || "暂无证据"}</small>
      {inputEvidence ? (
        <div className="macro-toolkit-input-evidence">
          {inputEvidence.missingInputs.length ? (
            <span>缺失输入：{inputEvidence.missingInputs.join(" / ")}</span>
          ) : null}
          {inputEvidence.sources.length ? <span>数据源：{inputEvidence.sources.join(" / ")}</span> : null}
          {inputEvidence.latestDates.length ? <span>最新日期：{inputEvidence.latestDates.join(" / ")}</span> : null}
          {inputEvidence.inputs.length ? (
            <small>
              {inputEvidence.inputs
                .slice(0, 3)
                .map((item) => `${item.label || item.field}: ${item.series_id ?? "缺失"} ${item.latest_date ?? ""}`.trim())
                .join(" / ")}
            </small>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CrisisGapAction({
  group,
  repairItems,
  commodityRefreshProducts,
  refreshingSourceAlias,
  commodityRefreshResult,
  commodityShortfallEstimates,
  sourceBackfillResult,
  sourceBackfillError,
  onPreviewCommodityRefreshProducts,
  onRepairSourceBackfill,
}: {
  group: CrisisGapGroup;
  repairItems: MacroToolkitRepairItem[];
  commodityRefreshProducts: string[];
  refreshingSourceAlias: string | null;
  commodityRefreshResult: string | null;
  commodityShortfallEstimates: CommodityShortfallEstimate[];
  sourceBackfillResult: string | null;
  sourceBackfillError: string | null;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem) => void;
}) {
  if (group.key === "commodity" && commodityRefreshProducts.length && onPreviewCommodityRefreshProducts) {
    return (
      <div className="macro-toolkit-crisis-gap-action">
        <Button
          size="small"
          type="primary"
          icon={<InfoCircleOutlined />}
          aria-label="按建议预估"
          onClick={() => onPreviewCommodityRefreshProducts(commodityRefreshProducts)}
        >
          按建议预估
        </Button>
        {commodityRefreshResult ? <small>{commodityRefreshResult}</small> : null}
        {commodityShortfallEstimates.length ? (
          <small>{formatCommodityShortfallEstimateList(commodityShortfallEstimates)}</small>
        ) : null}
      </div>
    );
  }

  const repairItem = findCrisisGapRepairItem(group, repairItems);
  if (!repairItem || !onRepairSourceBackfill) {
    return null;
  }
  const alias = normalizeMacroSourceBackfillAlias(repairItem.alias);
  return (
    <div className="macro-toolkit-crisis-gap-action">
      <Button
        size="small"
        icon={<ReloadOutlined />}
        loading={refreshingSourceAlias === alias}
        aria-label={repairItem.action?.label ?? "需要补齐来源数据"}
        onClick={() => onRepairSourceBackfill(repairItem)}
      >
        {repairItem.action?.label ?? "需要补齐来源数据"}
      </Button>
      {sourceBackfillResult ? <small>{sourceBackfillResult}</small> : null}
      {sourceBackfillError ? <small>{sourceBackfillError}</small> : null}
    </div>
  );
}

type CommodityRefreshProductRow = {
  key: string;
  productCode: string;
  productName: string;
  seriesId: string;
  status: "estimated" | "written" | "missing";
  estimatedRows: number | null;
  rowCount: number | null;
  rowCountLabel: string;
  latestDate: string;
  latestValue: number | null;
  vendor: string;
  table: string;
  isNanhua: boolean;
};

function CommodityRefreshResultPanel({ refresh }: { refresh: MacroToolkitCommodityFuturesRefreshRun }) {
  const rows = normalizeCommodityRefreshRows(refresh);
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const nanhuaRow = rows.find((row) => row.isNanhua);
  const summary = refresh.summary;
  const nanhuaMessage =
    nanhuaRow && !isDryRun && nanhuaRow.status === "written"
      ? "Crisis Score 南华输入已更新"
      : nanhuaRow
        ? "NHCI / NH0100.NHF 已纳入本次检查"
        : "NHCI / NH0100.NHF 未选择";
  const columns: ColumnsType<CommodityRefreshProductRow> = [
    {
      title: "品种",
      dataIndex: "productName",
      key: "productName",
      render: (_, row) => (
        <div className="macro-toolkit-commodity-refresh-product">
          <span>{row.productName}</span>
          <small>{commodityRefreshIdentifierText(row)}</small>
        </div>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (_, row) => <Tag color={commodityRefreshStatusColor(row.status)}>{commodityRefreshStatusText(row.status)}</Tag>,
    },
    {
      title: "行数",
      dataIndex: "rowCountLabel",
      key: "rowCountLabel",
      width: 110,
    },
    {
      title: "最新日期 / 值",
      dataIndex: "latestDate",
      key: "latestDate",
      render: (_, row) => (
        <span>
          {row.latestDate}
          {row.latestValue == null ? "" : ` / ${formatNumberValue(row.latestValue, 2)}`}
        </span>
      ),
    },
    {
      title: "来源",
      dataIndex: "vendor",
      key: "vendor",
      width: 120,
    },
    {
      title: "写入表",
      dataIndex: "table",
      key: "table",
      render: (table: string) => <span className="macro-toolkit-nowrap-soft">{table}</span>,
    },
  ];

  return (
    <div className="macro-toolkit-commodity-refresh-result" aria-label="商品期货刷新结果">
      <div className="macro-toolkit-commodity-refresh-summary">
        <span>{isDryRun ? "预估结果" : "刷新结果"}</span>
        <strong>{formatCommodityRefreshResult(refresh)}</strong>
        <Tag color={nanhuaRow && !isDryRun && nanhuaRow.status === "written" ? "green" : "blue"}>{nanhuaMessage}</Tag>
      </div>
      {summary ? <CommodityRefreshSummaryStrip summary={summary} isDryRun={isDryRun} /> : null}
      <Table
        rowKey="key"
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 760 }}
      />
    </div>
  );
}

function CommodityRefreshSummaryStrip({
  summary,
  isDryRun,
}: {
  summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>;
  isDryRun: boolean;
}) {
  return (
    <div className="macro-toolkit-commodity-refresh-closure" aria-label="商品期货刷新后闭环">
      <span>{isDryRun ? "预估基线" : "刷新后闭环"}</span>
      <strong>{commodityRefreshRowDeltaText(summary)}</strong>
      <strong>{commodityRefreshLatestDateText(summary)}</strong>
      <strong>{commodityRefreshCoverageText(summary)}</strong>
      <strong>{commodityRefreshNanhuaText(summary)}</strong>
      <strong>{commodityRefreshSourceText(summary)}</strong>
    </div>
  );
}

function CrisisScoreEvidencePanel({
  result,
  repairItems = [],
  refreshingSourceAlias = null,
  commodityRefreshResult = null,
  commodityShortfallEstimates = [],
  sourceBackfillResult = null,
  sourceBackfillError = null,
  onRepairSourceBackfill,
  onApplyCommodityRefreshProducts,
  onPreviewCommodityRefreshProducts,
}: {
  result: MacroToolkitCapabilityResult;
  repairItems?: MacroToolkitRepairItem[];
  refreshingSourceAlias?: string | null;
  commodityRefreshResult?: string | null;
  commodityShortfallEstimates?: CommodityShortfallEstimate[];
  sourceBackfillResult?: string | null;
  sourceBackfillError?: string | null;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem) => void;
  onApplyCommodityRefreshProducts?: (products: string[]) => void;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
}) {
  const normalizedEvidence = normalizeInputEvidence(result);
  const inputEvidence = normalizedEvidence?.inputs ?? [];
  const rawResult = result.result;
  const availableComponentCount = toDisplayNumber(rawResult.available_component_count);
  const componentCount = toDisplayNumber(rawResult.component_count);
  const components = Array.isArray(rawResult.components)
    ? rawResult.components.filter(isCrisisComponent)
    : [];
  const weights = isRecord(rawResult.weights) ? rawResult.weights : {};
  const commodityInput = inputEvidence.find(isNanhuaCrisisInput);
  const commodityCoverage = normalizeCommodityCoverage(rawResult.commodity_coverage);
  const commodityShortRefreshProducts = commodityCoverage?.candidate_summary
    ? commodityShadowRefreshProducts(commodityCoverage.candidate_summary)
    : [];
  const commodityShortRefreshHint = formatCommodityShadowRefreshHint(commodityShortRefreshProducts);
  const warnings = uniqueDisplayParts([...result.warnings, ...(normalizedEvidence?.missingInputs ?? [])]);
  const crisisGapGroups = buildCrisisGapGroups(inputEvidence, warnings);

  return (
    <section
      className="macro-toolkit-section macro-toolkit-crisis-evidence"
      aria-label="Crisis Score 数据来源"
    >
      <PageSectionLead
        eyebrow="crisis evidence"
        title="Crisis Score 数据来源"
        description="完整分析返回后展示每个输入、组件权重和缺口；缺失输入保持缺失，不折算为 0。"
      />

      <div className="macro-toolkit-crisis-evidence__summary">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="分数组件覆盖"
          value={`${availableComponentCount}/${componentCount}`}
          detail={components.map((component) => component.key).join(" / ") || "components missing"}
          tone={result.status === "complete" ? "positive" : "neutral"}
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="商品期货输入"
          value={commodityInput?.available ? "已命中" : "缺失"}
          detail={formatCrisisInputDetail(commodityInput)}
          tone={commodityInput?.available ? "positive" : "missing"}
          detailMaxLength={72}
        />
        <MetricTile
          icon={<WarningOutlined />}
          label="缺口提示"
          value={warnings.length}
          detail={warnings.join(" / ") || "无缺失输入"}
          tone={warnings.length ? "neutral" : "positive"}
        />
      </div>

      {crisisGapGroups.length ? (
        <div className="macro-toolkit-crisis-gap-list" aria-label="Crisis Score 缺口清单">
          <div className="macro-toolkit-crisis-gap-list__head">
            <strong>Crisis Score 缺口清单</strong>
            <small>缺失不按 0 处理；补齐后重新运行完整分析确认分数。</small>
          </div>
          <div className="macro-toolkit-crisis-gap-list__grid">
            {crisisGapGroups.map((group) => (
              <div className="macro-toolkit-crisis-gap-group" key={group.key}>
                <span>{group.label}</span>
                {group.items.map((item) => (
                  <small key={`${item.label}-${item.warning}`}>
                    {item.label} · {item.warning} · {item.detail}
                  </small>
                ))}
                <CrisisGapAction
                  group={group}
                  repairItems={repairItems}
                  commodityRefreshProducts={commodityShortRefreshProducts}
                  refreshingSourceAlias={refreshingSourceAlias}
                  commodityRefreshResult={commodityRefreshResult}
                  commodityShortfallEstimates={commodityShortfallEstimates}
                  sourceBackfillResult={sourceBackfillResult}
                  sourceBackfillError={sourceBackfillError}
                  onPreviewCommodityRefreshProducts={onPreviewCommodityRefreshProducts}
                  onRepairSourceBackfill={onRepairSourceBackfill}
                />
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="macro-toolkit-crisis-evidence__components">
        {components.map((component) => (
          <div className="macro-toolkit-crisis-component" key={component.key}>
            <span>{component.label}</span>
            <strong>{formatValue(component.z_score, "")}</strong>
            <small>
              {component.key} · weight {formatCrisisWeight(component.key, weights)} · raw{" "}
              {formatValue(component.raw_value, "")}
            </small>
          </div>
        ))}
      </div>

      {commodityCoverage ? (
        <div className="macro-toolkit-crisis-commodity-coverage">
          <MetricTile
            icon={<DatabaseOutlined />}
            label="商品旁证覆盖"
            value={`${commodityCoverage.available_count}/${commodityCoverage.tracked_count}`}
            detail={`${commodityCoverage.role} · 非公式输入`}
            tone="neutral"
          />
          <small className="macro-toolkit-crisis-coverage-note">
            Crisis Score 公式仍仅使用 {commodityCoverage.used_in_crisis_score.join(" / ") || "nanhua"}；本区块为{" "}
            {commodityCoverage.role}
          </small>
          {commodityCoverage.candidate_summary ? (
            <>
              <div className="macro-toolkit-crisis-evidence__summary">
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品扩展候选"
                  value={`${commodityCoverage.candidate_summary.shadow_review_ready_count} 个就绪`}
                  detail={formatCommodityCandidateSummaryDetail(commodityCoverage.candidate_summary)}
                  tone="neutral"
                />
                <MetricTile
                  icon={<WarningOutlined />}
                  label="公式变更需审批"
                  value={commodityCoverage.candidate_summary.approval_required ? "是" : "否"}
                  detail={
                    commodityCoverage.candidate_summary.formula_change_required
                      ? "从旁证进入 Crisis Score 公式需要版本化审批"
                      : "当前无公式变更"
                  }
                  tone="neutral"
                />
                <MetricTile
                  icon={<ToolOutlined />}
                  label="下一步"
                  value="影子评估"
                  detail={commodityCoverage.candidate_summary.next_step || "下一步待确认"}
                  tone="neutral"
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="影子评估结果"
                  value={`${commodityCoverage.candidate_summary.shadow_evaluation_ready_count} 个可读`}
                  detail={formatCommodityShadowSummary(commodityCoverage)}
                  tone="neutral"
                />
              </div>
              <small className="macro-toolkit-crisis-coverage-note">
                {commodityCoverage.candidate_summary.next_step || "商品扩展候选下一步待确认"}
              </small>
              {commodityCoverage.candidate_summary.shadow_evaluation_next_step ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {commodityCoverage.candidate_summary.shadow_evaluation_next_step}
                </small>
              ) : null}
              {commodityCoverage.candidate_summary.shadow_evaluation_short_items.length ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {formatCommodityShadowShortfallList(commodityCoverage.candidate_summary)}
                </small>
              ) : null}
              {commodityShortRefreshHint ? (
                <div className="macro-toolkit-crisis-coverage-action">
                  <small className="macro-toolkit-crisis-coverage-note">{commodityShortRefreshHint}</small>
                  {onApplyCommodityRefreshProducts ? (
                    <Button
                      size="small"
                      icon={<ToolOutlined />}
                      aria-label="按建议选择"
                      onClick={() => onApplyCommodityRefreshProducts(commodityShortRefreshProducts)}
                    >
                      按建议选择
                    </Button>
                  ) : null}
                  {onPreviewCommodityRefreshProducts ? (
                    <Button
                      size="small"
                      type="primary"
                      icon={<InfoCircleOutlined />}
                      aria-label="按建议预估"
                      onClick={() => onPreviewCommodityRefreshProducts(commodityShortRefreshProducts)}
                    >
                      按建议预估
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}
          <div className="macro-toolkit-crisis-input-grid">
            {commodityCoverage.items.map((item) => (
              <div
                className={[
                  "macro-toolkit-crisis-input",
                  item.available ? "macro-toolkit-crisis-input--available" : "macro-toolkit-crisis-input--missing",
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={item.field}
              >
                <div className="macro-toolkit-capability-result-head">
                  <span>{item.label || item.field}</span>
                  <Tag color={item.available ? "green" : "red"}>{item.available ? "命中" : "缺失"}</Tag>
                </div>
                <strong>{formatCommodityCoverageIdentifiers(item)}</strong>
                <small>
                  {item.field} · {formatCrisisRowCount(item.row_count)} · {item.latest_date ?? "日期缺失"} ·{" "}
                  {formatCommodityCoverageDateStatus(item.date_alignment_status)}
                </small>
                <small>
                  {item.source ?? "source missing"} · {item.series_id ?? "series missing"} · matched{" "}
                  {item.matched_alias ?? "alias missing"} · {item.used_in_formula ? "纳入公式" : "未纳入公式"}
                </small>
                {item.candidate_decision ? (
                  <small>
                    {item.candidate_decision.label} · {item.candidate_decision.reason} ·{" "}
                    {item.candidate_decision.next_step}
                  </small>
                ) : null}
                {item.shadow_evaluation ? (
                  <small>
                    {item.shadow_evaluation.label} · {item.shadow_evaluation.summary} ·{" "}
                    {formatCommodityShadowDetail(item.shadow_evaluation)}
                  </small>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="macro-toolkit-crisis-input-grid">
        {inputEvidence.map((item) => (
          <div
            className={[
              "macro-toolkit-crisis-input",
              item.available ? "macro-toolkit-crisis-input--available" : "macro-toolkit-crisis-input--missing",
              item.field === "nanhua" ? "macro-toolkit-crisis-input--commodity" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={`${item.field}-${item.aliases?.join("-") ?? item.label}`}
          >
            <div className="macro-toolkit-capability-result-head">
              <span>{item.label || item.field}</span>
              <Tag color={item.available ? "green" : "red"}>{item.available ? "命中" : "缺失"}</Tag>
            </div>
            <strong>{item.aliases?.join(" / ") || item.series_id || "alias missing"}</strong>
            <small>
              {item.field} · {formatCrisisRowCount(item.row_count)} · {item.latest_date ?? "日期缺失"}
            </small>
            <small>
              {item.source ?? "source missing"} · {item.series_id ?? "series missing"} · value{" "}
              {item.value == null ? "缺失" : formatValue(item.value, "")}
            </small>
            {item.warning ? <Tag color={item.available ? "default" : "red"}>{item.warning}</Tag> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function HasonMacroStrategyPanel({ strategy }: { strategy: MacroToolkitHasonStrategy }) {
  const readiness = strategy.readiness;
  const readinessText = `${readiness.ready_modules}/${readiness.total_modules}`;
  const runtimeOutputsCurrent = strategy.runtime_output_status === "current";
  const runtimeOutputGaps = strategy.runtime_output_gaps;
  const runtimeOutputValue = runtimeOutputsCurrent
    ? "current"
    : `${strategy.runtime_output_status} · ${runtimeOutputGaps.length}`;
  const runtimeOutputDetail = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : strategy.required_runtime_outputs.join(" / ");
  const runtimeGapText = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : runtimeOutputsCurrent
      ? "none"
      : "freshness not confirmed";
  const tracedScripts = strategy.source_trace;
  const tracedScriptPreview = tracedScripts.slice(0, 5);
  return (
    <section className="macro-toolkit-section macro-toolkit-hason-strategy" data-testid="macro-toolkit-hason-strategy">
      <div className="macro-toolkit-hason-strategy__head">
        <div>
          <span>Hason macro strategy</span>
          <strong>{strategy.framework_name}</strong>
          <small>{strategy.boundary}</small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
          <Tag color="blue">{strategy.basis}</Tag>
          <Tag color={strategy.observation_only ? "gold" : "green"}>
            {strategy.observation_only ? "observation-only" : "actionable"}
          </Tag>
          <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
            {strategy.formal_metric_id ?? "no formal MTR"}
          </Tag>
        </div>
      </div>

      <div className="macro-toolkit-hason-strategy__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="Readiness"
          value={readinessText}
          detail={`${formatPercent(readiness.ratio)} module coverage`}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Module gaps"
          value={`${readiness.missing_script_count} missing script`}
          detail={`${readiness.partial_modules} partial / ${readiness.missing_modules} missing module`}
          tone="neutral"
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="Runtime outputs"
          value={runtimeOutputValue}
          detail={runtimeOutputDetail}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Script trace"
          value={tracedScripts.length}
          detail={tracedScriptPreview.map(formatHasonTraceScript).join(" / ") || "no script available"}
          tone="neutral"
          testId="macro-toolkit-hason-script-trace"
        />
      </div>

      <div className="macro-toolkit-hason-module-grid">
        {strategy.modules.map((module) => (
          <div
            className="macro-toolkit-hason-module"
            data-testid={`macro-toolkit-hason-module-${module.key}`}
            key={module.key}
          >
            <div className="macro-toolkit-capability-result-head">
              <span>{module.key}</span>
              <Tag color={hasonModuleStatusColor(module.status)}>{hasonModuleStatusLabel(module.status)}</Tag>
            </div>
            <strong>{module.label}</strong>
            <small>可用脚本：{module.available_scripts.join(" / ") || "无"}</small>
            {module.missing_scripts.length ? (
              <small className="macro-toolkit-hason-module__missing">
                缺失脚本：{module.missing_scripts.join(" / ")}
              </small>
            ) : null}
            <div className="macro-toolkit-tag-row">
              {module.evidence.map((item) => (
                <Tag color="blue" key={`${module.key}-${item}`}>
                  {item}
                </Tag>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-hason-runtime" data-testid="macro-toolkit-hason-runtime-gaps">
        <span>runtime outputs · {strategy.runtime_output_status}</span>
        <strong>{runtimeGapText}</strong>
        {strategy.runtime_outputs.length ? (
          <small>
            {strategy.runtime_outputs.map(formatHasonRuntimeOutput).join(" / ")}
          </small>
        ) : null}
      </div>
    </section>
  );
}

function formatHasonRuntimeOutput(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return (
    `${item.name}: ${item.freshness_status} ${hasonFreshnessBasisLabel(item.freshness_basis)}` +
    `${hasonContentDateText(item)}` +
    `${hasonInvalidDateText(item)}` +
    `${item.modified_date ? ` file ${item.modified_date}` : ""}`
  );
}

function hasonContentDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  if (item.content_date_min && item.content_date_max && item.content_date_min !== item.content_date_max) {
    return ` content ${item.content_date_min}..${item.content_date_max}`;
  }
  return item.content_date ? ` content ${item.content_date}` : "";
}

function hasonInvalidDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return item.content_date_invalid_count > 0 ? ` ${item.content_date_invalid_count} invalid date` : "";
}

function hasonFreshnessBasisLabel(basis: string) {
  const labels: Record<string, string> = {
    csv_content: "CSV content date",
    file_modified_date: "file modified date",
    missing: "file missing",
  };
  return labels[basis] ?? basis;
}

function hasonModuleStatusLabel(status: string) {
  const labels: Record<string, string> = {
    integrated: "script-chain complete",
    partial: "script-chain partial",
    missing: "script-chain missing",
  };
  return labels[status] ?? status;
}

function hasonModuleStatusColor(status: string) {
  if (status === "integrated") return "default";
  return statusColor(status);
}

function formatHasonTraceScript(item: MacroToolkitHasonStrategy["source_trace"][number]) {
  const modules = Array.isArray(item.modules) ? item.modules : [];
  const moduleText = modules.length ? `[${modules.join("+")}]` : "";
  return `${item.script}${moduleText}${item.available ? "" : ":missing"}`;
}

function ReadinessTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: MacroToolkitSignalCard["tone"];
}) {
  const Icon = tone === "negative" || tone === "missing" ? ExclamationCircleOutlined : CheckCircleOutlined;
  return (
    <div className={`macro-toolkit-readiness-tile macro-toolkit-readiness-tile--${tone}`}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <Icon />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 28)}</small>
    </div>
  );
}

function MacroToolkitDataHealthPanel({
  dataHealth,
  showActions = false,
  onRepairAction,
  repairActionLoading = false,
  refreshingSourceAlias = null,
}: {
  dataHealth: MacroToolkitDataHealth;
  showActions?: boolean;
  onRepairAction?: (item: MacroToolkitRepairItem) => void;
  repairActionLoading?: boolean;
  refreshingSourceAlias?: string | null;
}) {
  const missingAliases = dataHealth.source_coverage.missing_aliases;
  const missingIndicators = dataHealth.indicator_coverage.missing;
  const repairItems = dataHealth.repair_items ?? [];
  const visibleRepairItems = repairItems.slice(0, 6);
  const hiddenRepairItemCount = repairItems.length - visibleRepairItems.length;
  const deferredText = dataHealth.deferred_sections.length
    ? `延后加载：${dataHealth.deferred_sections.join(" / ")}`
    : "完整结果已加载";
  return (
    <section className="macro-toolkit-data-health" aria-label="数据健康总览">
      <div className="macro-toolkit-data-health__head">
        <span>
          <MacroStatusIcon tone={dataHealth.warnings.length ? "missing" : "neutral"}>
            <DatabaseOutlined />
          </MacroStatusIcon>
          数据健康总览
        </span>
        <Tag color={dataHealth.analysis_scope === "core" ? "gold" : "green"}>
          {dataHealth.analysis_scope === "core" ? "core 首屏" : "full 完整"}
        </Tag>
      </div>
      <div className="macro-toolkit-data-health__grid">
        <HealthMetricTile
          label="指标覆盖"
          value={`${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`}
          detail={formatMissingIndicatorDetail(missingIndicators)}
          tone={dataHealth.indicator_coverage.missing_count > 0 ? "neutral" : "positive"}
        />
        <HealthMetricTile
          label="来源覆盖"
          value={coverageValue(dataHealth.source_coverage)}
          detail={
            dataHealth.source_coverage.deferred
              ? "来源检查延后加载"
              : missingAliases.length
                ? `缺失 ${missingAliases.join(" / ")}`
                : "来源全部命中"
          }
          tone={dataHealth.source_coverage.deferred ? "neutral" : missingAliases.length ? "missing" : "positive"}
        />
        <HealthMetricTile
          label="最新来源日期"
          value={dataHealth.source_coverage.latest_date ?? "延后加载"}
          detail={deferredText}
          tone={dataHealth.source_coverage.latest_date ? "positive" : "neutral"}
        />
        <HealthMetricTile
          label="能力降级"
          value={capabilityIssueCount(dataHealth)}
          detail={capabilityHealthDetail(dataHealth)}
          tone={capabilityIssueCount(dataHealth) > 0 ? "neutral" : "positive"}
        />
      </div>
      {(missingIndicators.length || missingAliases.length || dataHealth.warnings.length) ? (
        <div className="macro-toolkit-data-health__notes">
          {missingIndicators.map((item) => (
            <Tag color="gold" key={item.alias ?? item.key ?? item.label}>
              {item.alias ?? item.key ?? item.label} 缺失
            </Tag>
          ))}
          {missingAliases.map((alias) => (
            <Tag color="red" key={alias}>
              {alias} 来源未命中
            </Tag>
          ))}
          {dataHealth.warnings.map((warning) => (
            <Tag color="red" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      ) : null}
      {repairItems.length ? (
        <div className="macro-toolkit-data-health__repairs" aria-label="待处理数据项">
          <div className="macro-toolkit-data-health__repairs-head">
            <span>待处理数据项</span>
            <Tag color={repairItems.some((item) => item.priority === "high") ? "red" : "gold"}>
              {repairItems.length} 项
            </Tag>
          </div>
          <div className="macro-toolkit-data-health__repair-list">
            {visibleRepairItems.map((item) => (
              <div
                className={`macro-toolkit-data-health__repair macro-toolkit-data-health__repair--${item.priority ?? "medium"}`}
                key={item.key ?? `${item.type}-${item.label}-${item.suggested_action}`}
              >
                <div className="macro-toolkit-data-health__repair-main">
                  <span>
                    <Tag color={repairPriorityColor(item.priority)}>{repairPriorityLabel(item.priority)}</Tag>
                    <Tag color={statusColor(item.type ?? "")}>{repairTypeLabel(item.type)}</Tag>
                    {item.label ?? item.alias ?? item.key ?? "未命名数据项"}
                  </span>
                  <small title={item.suggested_action ?? ""}>{compactText(item.suggested_action, 78)}</small>
                  {item.action?.reason ? (
                    <small title={item.action.reason}>
                      {item.action.label ? `${item.action.label}：` : ""}
                      {compactText(item.action.reason, 56)}
                    </small>
                  ) : null}
                </div>
                <div className="macro-toolkit-data-health__repair-meta">
                  {item.alias ? <Tag color="default">{item.alias}</Tag> : null}
                  {item.latest_date ? <Tag color="blue">最新 {item.latest_date}</Tag> : null}
                  {item.stale_days ? <Tag color="gold">落后 {item.stale_days} 天</Tag> : null}
                  {item.source_table ? <Tag color="default">{item.source_table}</Tag> : null}
                </div>
                {item.action ? (
                  <div className="macro-toolkit-data-health__repair-action">
                    {showActions && item.action.enabled && item.action.kind === "load_full_analysis" ? (
                      <Button
                        size="small"
                        icon={<LineChartOutlined />}
                        loading={repairActionLoading}
                        aria-label={item.action.label ?? "查看完整分析"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "查看完整分析"}
                      </Button>
                    ) : showActions && item.action.enabled && canRefreshMacroSourceBackfill(item) ? (
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={refreshingSourceAlias === normalizeMacroSourceBackfillAlias(item.alias)}
                        aria-label={item.action.label ?? "需要补齐来源数据"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "需要补齐来源数据"}
                      </Button>
                    ) : (
                      <small title={item.action.reason ?? ""}>
                        {item.action.label ?? "待处理"} · {item.action.reason ?? "需要人工确认"}
                      </small>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          {hiddenRepairItemCount > 0 ? (
            <small className="macro-toolkit-data-health__repair-overflow">
              还有 {hiddenRepairItemCount} 项未显示；请查看完整分析或后端明细确认。
            </small>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function HealthMetricTile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string | number;
  detail: string;
  tone: MacroToolkitSignalCard["tone"];
}) {
  return (
    <div className={`macro-toolkit-data-health__tile macro-toolkit-data-health__tile--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 32)}</small>
    </div>
  );
}

function coverageValue(coverage: MacroToolkitDataHealth["source_coverage"]) {
  return coverage.deferred ? "延后加载" : `${coverage.hit_count}/${coverage.total_count}`;
}

function formatMissingIndicatorDetail(items: MacroToolkitDataHealth["indicator_coverage"]["missing"]) {
  return items.length
    ? `缺失 ${items.map((item) => item.alias ?? item.key ?? item.label).filter(Boolean).join(" / ")}`
    : "指标全部命中";
}

function capabilityIssueCount(dataHealth: MacroToolkitDataHealth) {
  return dataHealth.capability_results.degraded + dataHealth.capability_results.unavailable;
}

function capabilityHealthDetail(dataHealth: MacroToolkitDataHealth) {
  if (dataHealth.capability_results.deferred) {
    return "能力结果延后加载，未按 0 处理";
  }
  return `${dataHealth.capability_results.complete} 完整 / ${dataHealth.capability_results.degraded} 降级 / ${dataHealth.capability_results.unavailable} 不可用`;
}

function repairPriorityColor(priority: string | null | undefined) {
  if (priority === "high") return "red";
  if (priority === "low") return "blue";
  return "gold";
}

function repairPriorityLabel(priority: string | null | undefined) {
  if (priority === "high") return "高";
  if (priority === "low") return "低";
  return "中";
}

function repairTypeLabel(type: string | null | undefined) {
  const labels: Record<string, string> = {
    missing: "缺失",
    stale: "滞后",
    degraded: "降级",
    deferred: "完整分析后确认",
  };
  return labels[type ?? ""] ?? (type || "待确认");
}

function TailwindMetricTile({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-blue-100 bg-white p-3 shadow-sm shadow-blue-100/60">
      <div className="flex min-w-0 items-center gap-2 text-xs font-bold text-slate-600">
        <span className="grid h-6 w-6 place-items-center rounded-md border border-blue-100 bg-blue-50 text-blue-600">
          {icon}
        </span>
        <span className="truncate">{label}</span>
      </div>
      <strong className="mt-2 block truncate font-mono text-xl text-blue-950">{value}</strong>
      <small className="block truncate text-xs text-slate-500" title={detail}>
        {detail}
      </small>
    </div>
  );
}

function IndicatorValueCell({ item }: { item: MacroToolkitIndicator }) {
  return (
    <div className="macro-toolkit-number-cell">
      <strong>{formatValue(item.latest_value, item.unit)}</strong>
      <small>{item.row_count.toLocaleString()} rows</small>
    </div>
  );
}

function DeltaCell({ change, changePct }: { change: number | null; changePct: number | null }) {
  const direction = changePct ?? change;
  const hasDirection = direction !== null;
  const isPositive = hasDirection && direction > 0;
  const isNegative = hasDirection && direction < 0;

  return (
    <div
      className={[
        "macro-toolkit-delta-cell",
        isPositive ? "macro-toolkit-delta-cell--up" : "",
        isNegative ? "macro-toolkit-delta-cell--down" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isPositive ? <ArrowUpOutlined /> : null}
      {isNegative ? <ArrowDownOutlined /> : null}
      <span>{formatChange(change, changePct)}</span>
    </div>
  );
}

function CapabilityDataCell({
  status,
  item,
}: {
  status: string;
  item: MacroToolkitCapability;
}) {
  const ratio = item.data_required_count > 0 ? item.data_hit_count / item.data_required_count : 1;
  return (
    <div className="macro-toolkit-capability-data-cell" style={scoreStyle(ratio * 100)}>
      <div>
        <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
        <span>
          {item.data_hit_count}/{item.data_required_count}
        </span>
      </div>
      <div className="macro-toolkit-score-track" aria-hidden="true">
        <span />
      </div>
    </div>
  );
}

function normalizeInputEvidence(result: MacroToolkitCapabilityResult) {
  const raw = result.input_evidence ?? result.result.input_evidence;
  if (!raw) {
    return null;
  }
  const inputs = raw.inputs ?? [];
  const missingInputs = raw.missing_inputs ?? [];
  const sources = raw.sources ?? [];
  const latestDates = raw.latest_dates ?? [];
  if (!inputs.length && !missingInputs.length && !sources.length && !latestDates.length) {
    return null;
  }
  return { inputs, missingInputs, sources, latestDates };
}

type CrisisComponent = {
  key: string;
  label: string;
  raw_value: number | null;
  z_score: number | null;
  weight: number | null;
};

type CrisisCommodityCoverageItem = {
  field: string;
  label: string;
  aliases: string[];
  matched_alias: string | null;
  role: string;
  used_in_formula: boolean;
  available: boolean;
  row_count: number | null;
  latest_date: string | null;
  report_date: string | null;
  date_alignment_status: string | null;
  series_id: string | null;
  source: string | null;
  value: number | null;
  candidate_decision: CrisisCommodityCandidateDecision | null;
  shadow_evaluation: CrisisCommodityShadowEvaluation | null;
};

type CrisisCommodityCandidateDecision = {
  status: string;
  label: string;
  reason: string;
  next_step: string;
};

type CrisisCommodityCandidateSummary = {
  shadow_review_ready_count: number;
  needs_current_data_count: number;
  missing_data_count: number;
  shadow_evaluation_ready_count: number;
  shadow_evaluation_short_count: number;
  shadow_evaluation_status_counts: Record<string, number>;
  shadow_evaluation_short_items: CrisisCommodityShadowShortItem[];
  shadow_evaluation_next_step: string;
  formula_change_required: boolean;
  approval_required: boolean;
  next_step: string;
};

type CrisisCommodityShadowShortItem = {
  field: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  latest_date: string | null;
};

type CrisisCommodityShadowEvaluation = {
  status: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  window_start: string | null;
  window_end: string | null;
  target: string;
  candidate_metric: string;
  same_day_correlation: number | null;
  lead_1d_correlation: number | null;
  lag_1d_correlation: number | null;
  crisis_hit_rate: number | null;
  crisis_sample_count: number | null;
  summary: string;
  next_step: string;
};

type CrisisCommodityCoverage = {
  role: string;
  tracked_count: number;
  available_count: number;
  used_in_crisis_score: string[];
  candidate_summary: CrisisCommodityCandidateSummary | null;
  items: CrisisCommodityCoverageItem[];
};

type MacroToolkitInputEvidenceItem = NonNullable<MacroToolkitInputEvidence["inputs"]>[number];
type CrisisGapGroupKey = "equity" | "liquidity" | "commodity" | "curve_credit" | "fx" | "other";
type CrisisGapItem = {
  label: string;
  warning: string;
  detail: string;
  identifiers: string[];
};
type CrisisGapGroup = {
  key: CrisisGapGroupKey;
  label: string;
  items: CrisisGapItem[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCrisisComponent(value: unknown): value is CrisisComponent {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.key === "string" && typeof value.label === "string";
}

function normalizeCommodityCoverage(value: unknown): CrisisCommodityCoverage | null {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return null;
  }
  const items = value.items.map(normalizeCommodityCoverageItem).filter((item) => item !== null);
  if (!items.length) {
    return null;
  }
  return {
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    tracked_count: typeof value.tracked_count === "number" ? value.tracked_count : items.length,
    available_count:
      typeof value.available_count === "number" ? value.available_count : items.filter((item) => item.available).length,
    used_in_crisis_score: Array.isArray(value.used_in_crisis_score)
      ? value.used_in_crisis_score.map((item) => String(item)).filter(Boolean)
      : [],
    candidate_summary: normalizeCommodityCandidateSummary(value.candidate_summary),
    items,
  };
}

function normalizeCommodityCandidateSummary(value: unknown): CrisisCommodityCandidateSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    shadow_review_ready_count:
      typeof value.shadow_review_ready_count === "number" ? value.shadow_review_ready_count : 0,
    needs_current_data_count:
      typeof value.needs_current_data_count === "number" ? value.needs_current_data_count : 0,
    missing_data_count: typeof value.missing_data_count === "number" ? value.missing_data_count : 0,
    shadow_evaluation_ready_count:
      typeof value.shadow_evaluation_ready_count === "number" ? value.shadow_evaluation_ready_count : 0,
    shadow_evaluation_short_count:
      typeof value.shadow_evaluation_short_count === "number" ? value.shadow_evaluation_short_count : 0,
    shadow_evaluation_status_counts: normalizeNumberRecord(value.shadow_evaluation_status_counts),
    shadow_evaluation_short_items: Array.isArray(value.shadow_evaluation_short_items)
      ? value.shadow_evaluation_short_items.map(normalizeCommodityShadowShortItem).filter((item) => item !== null)
      : [],
    shadow_evaluation_next_step:
      typeof value.shadow_evaluation_next_step === "string" ? value.shadow_evaluation_next_step : "",
    formula_change_required: value.formula_change_required === true,
    approval_required: value.approval_required === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "",
  };
}

function normalizeCommodityShadowShortItem(value: unknown): CrisisCommodityShadowShortItem | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
  };
}

function normalizeNumberRecord(value: unknown) {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number")
      .map(([key, count]) => [key, count]),
  );
}

function normalizeCommodityCoverageItem(value: unknown): CrisisCommodityCoverageItem | null {
  if (!isRecord(value) || typeof value.field !== "string" || typeof value.label !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: value.label,
    aliases: Array.isArray(value.aliases) ? value.aliases.map((item) => String(item)).filter(Boolean) : [],
    matched_alias: typeof value.matched_alias === "string" ? value.matched_alias : null,
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    used_in_formula: value.used_in_formula === true,
    available: value.available === true,
    row_count: typeof value.row_count === "number" ? value.row_count : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    report_date: typeof value.report_date === "string" ? value.report_date : null,
    date_alignment_status: typeof value.date_alignment_status === "string" ? value.date_alignment_status : null,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    value: typeof value.value === "number" ? value.value : null,
    candidate_decision: normalizeCommodityCandidateDecision(value.candidate_decision),
    shadow_evaluation: normalizeCommodityShadowEvaluation(value.shadow_evaluation),
  };
}

function normalizeCommodityCandidateDecision(value: unknown): CrisisCommodityCandidateDecision | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "候选状态待确认",
    reason: typeof value.reason === "string" ? value.reason : "候选原因待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function normalizeCommodityShadowEvaluation(value: unknown): CrisisCommodityShadowEvaluation | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "影子评估待确认",
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    window_start: typeof value.window_start === "string" ? value.window_start : null,
    window_end: typeof value.window_end === "string" ? value.window_end : null,
    target: typeof value.target === "string" ? value.target : "crisis_score",
    candidate_metric: typeof value.candidate_metric === "string" ? value.candidate_metric : "daily_return",
    same_day_correlation: typeof value.same_day_correlation === "number" ? value.same_day_correlation : null,
    lead_1d_correlation: typeof value.lead_1d_correlation === "number" ? value.lead_1d_correlation : null,
    lag_1d_correlation: typeof value.lag_1d_correlation === "number" ? value.lag_1d_correlation : null,
    crisis_hit_rate: typeof value.crisis_hit_rate === "number" ? value.crisis_hit_rate : null,
    crisis_sample_count: typeof value.crisis_sample_count === "number" ? value.crisis_sample_count : null,
    summary: typeof value.summary === "string" ? value.summary : "影子评估摘要待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function toDisplayNumber(value: unknown) {
  return typeof value === "number" || typeof value === "string" ? value : "缺失";
}

function formatCrisisWeight(key: string, weights: Record<string, unknown>) {
  const weight = weights[key];
  return typeof weight === "number" ? formatPercent(weight) : "缺失";
}

function formatCrisisRowCount(rowCount: number | null | undefined) {
  return typeof rowCount === "number" ? `${rowCount} rows` : "行数缺失";
}

function formatCommodityCoverageDateStatus(status: string | null | undefined) {
  if (status === "aligned") {
    return "同日";
  }
  if (status === "lagging") {
    return "滞后";
  }
  if (status === "missing") {
    return "日期缺失";
  }
  return "对齐状态缺失";
}

function formatCommodityCandidateSummaryDetail(summary: CrisisCommodityCandidateSummary) {
  return `影子评估就绪 ${summary.shadow_review_ready_count}，待补当日 ${summary.needs_current_data_count}，缺失 ${summary.missing_data_count}`;
}

function formatCommodityShadowSummary(coverage: CrisisCommodityCoverage) {
  const firstReady = coverage.items.find((item) => item.shadow_evaluation?.status === "review_ready")?.shadow_evaluation;
  const summary = coverage.candidate_summary;
  if (!firstReady) {
    return summary?.shadow_evaluation_next_step || "影子评估样本不足";
  }
  const shortText = summary?.shadow_evaluation_short_count
    ? `${summary.shadow_evaluation_short_count} 个样本不足`
    : "样本不足 0";
  return [
    `${summary?.shadow_evaluation_ready_count ?? 0} 个可读`,
    shortText,
    formatCommodityShadowDetail(firstReady),
    summary?.shadow_evaluation_next_step,
  ]
    .filter(Boolean)
    .join(" · ");
}

function formatCommodityShadowDetail(evaluation: CrisisCommodityShadowEvaluation) {
  const parts = [
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `危机期命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
  ];
  if (evaluation.status === "history_short" && typeof evaluation.minimum_sample_count === "number") {
    parts.push(`最低样本 ${evaluation.minimum_sample_count}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.sample_gap === "number") {
    parts.push(`还差 ${evaluation.sample_gap}`);
  }
  return parts.join(" · ");
}

function formatCommodityShadowShortfallList(summary: CrisisCommodityCandidateSummary) {
  const items = summary.shadow_evaluation_short_items.map((item) => {
    const sampleText =
      typeof item.sample_count === "number" && typeof item.minimum_sample_count === "number"
        ? `${item.sample_count}/${item.minimum_sample_count}`
        : "样本缺失";
    const gapText = typeof item.sample_gap === "number" ? `还差 ${item.sample_gap}` : "缺口待确认";
    const dateText = item.latest_date ? `，最新 ${item.latest_date}` : "";
    return `${item.label || item.field} ${sampleText}，${gapText}${dateText}`;
  });
  return `样本不足：${items.join("；")}`;
}

function crisisCommodityShortItemsFromResult(
  result: MacroToolkitCapabilityResult | null | undefined,
): CrisisCommodityShadowShortItem[] {
  if (!result) {
    return [];
  }
  const coverage = normalizeCommodityCoverage(
    (result as { commodity_coverage?: unknown }).commodity_coverage ?? result.result.commodity_coverage,
  );
  return coverage?.candidate_summary?.shadow_evaluation_short_items ?? [];
}

function crisisCommodityShortItemsFromEnvelope(
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null | undefined,
): CrisisCommodityShadowShortItem[] {
  const result = envelope?.result.capability_results.find((item) => item.key === "crisis_score_cn") ?? null;
  return crisisCommodityShortItemsFromResult(result);
}

function formatCommodityShortfallChanges(
  beforeItems: CrisisCommodityShadowShortItem[],
  afterItems: CrisisCommodityShadowShortItem[],
): CommodityShortfallChange[] {
  const afterByField = new Map(afterItems.map((item) => [item.field, item]));
  return beforeItems
    .map((before) => {
      if (before.sample_count == null || before.minimum_sample_count == null) {
        return null;
      }
      const after = afterByField.get(before.field);
      const afterSample = after?.sample_count ?? before.minimum_sample_count;
      const afterMinimum = after?.minimum_sample_count ?? before.minimum_sample_count;
      return {
        field: before.field,
        label: before.label || before.field,
        before: `${before.sample_count}/${before.minimum_sample_count}`,
        after: `${afterSample}/${afterMinimum}`,
      };
    })
    .filter((item): item is CommodityShortfallChange => item !== null);
}

function formatCommodityShortfallChangeList(changes: CommodityShortfallChange[]) {
  return changes.map((item) => `${item.label} ${item.before} -> ${item.after}`).join("；");
}

function formatCommodityShortfallEstimates(
  beforeItems: CrisisCommodityShadowShortItem[],
  refresh: MacroToolkitCommodityFuturesRefreshRun,
): CommodityShortfallEstimate[] {
  const rowsByProduct = new Map(
    normalizeCommodityRefreshRows(refresh).map((row) => [row.productCode, row.estimatedRows ?? row.rowCount ?? 0]),
  );
  return beforeItems
    .map((item) => {
      if (item.sample_count == null || item.minimum_sample_count == null) {
        return null;
      }
      const product = MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field];
      const estimatedRows = product ? rowsByProduct.get(product) ?? 0 : 0;
      const afterSample = Math.min(item.minimum_sample_count, item.sample_count + estimatedRows);
      return {
        field: item.field,
        label: item.label || item.field,
        before: `${item.sample_count}/${item.minimum_sample_count}`,
        after: `${afterSample}/${item.minimum_sample_count}`,
        estimatedRows,
        canFill: afterSample >= item.minimum_sample_count,
      };
    })
    .filter((item): item is CommodityShortfallEstimate => item !== null && item.estimatedRows > 0);
}

function formatCommodityShortfallEstimateList(estimates: CommodityShortfallEstimate[]) {
  const canFillAll = estimates.every((item) => item.canFill);
  const prefix = canFillAll
    ? "预计可补齐最低样本，建议刷新商品期货"
    : "预计仍有样本缺口，刷新后仍不会闭环";
  const items = estimates.map((item) => {
    const remainingGap = item.canFill ? 0 : commodityShortfallRemainingGap(item.after);
    const conclusion = item.canFill
      ? `可补齐至 ${item.after}`
      : `预计到 ${item.after}${remainingGap == null ? "" : `，还差 ${remainingGap}`}`;
    return `${item.label} ${item.before}，预计 +${item.estimatedRows}，${conclusion}`;
  });
  return `${prefix}：${items.join("；")}`;
}

function formatCommodityRefreshActionLabel(estimates: CommodityShortfallEstimate[]) {
  if (!estimates.length) {
    return "刷新商品期货";
  }
  return estimates.every((item) => item.canFill)
    ? "刷新商品期货：刷新并重算证据"
    : "刷新商品期货：仍有缺口，谨慎刷新";
}

function commodityShortfallRemainingGap(sampleText: string) {
  const match = /^(\d+)\/(\d+)$/.exec(sampleText);
  if (!match) {
    return null;
  }
  return Math.max(0, Number(match[2]) - Number(match[1]));
}

function commodityShadowRefreshProducts(summary: CrisisCommodityCandidateSummary) {
  return summary.shadow_evaluation_short_items
    .map((item) => MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field])
    .filter((item, index, array): item is string => Boolean(item) && array.indexOf(item) === index);
}

function formatCommodityShadowRefreshHint(products: string[]) {
  return products.length ? `建议刷新品种：${products.join(" / ")}` : "";
}

function formatSignedDecimal(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(2) : "缺失";
}

const CRISIS_GAP_GROUP_LABELS: Record<CrisisGapGroupKey, string> = {
  equity: "股票风险输入",
  liquidity: "利率与流动性输入",
  commodity: "商品期货输入",
  curve_credit: "曲线与信用输入",
  fx: "汇率输入",
  other: "其他输入",
};

function uniqueDisplayParts(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => value?.trim()).filter((value): value is string => Boolean(value))));
}

function buildCrisisGapGroups(inputEvidence: MacroToolkitInputEvidenceItem[], warnings: string[]): CrisisGapGroup[] {
  const warningSet = new Set(warnings);
  const itemsByGroup = new Map<CrisisGapGroupKey, CrisisGapItem[]>();
  const pushItem = (groupKey: CrisisGapGroupKey, item: CrisisGapItem) => {
    const items = itemsByGroup.get(groupKey) ?? [];
    if (!items.some((candidate) => candidate.warning === item.warning && candidate.label === item.label)) {
      items.push(item);
    }
    itemsByGroup.set(groupKey, items);
  };

  for (const input of inputEvidence) {
    const warning = input.warning;
    const isMissing = input.available === false || (warning ? warningSet.has(warning) : false);
    if (!isMissing || !warning) {
      continue;
    }
    pushItem(crisisGapGroupKey(input.field, warning), {
      label: input.label || input.field,
      warning,
      detail: crisisGapInputDetail(input),
      identifiers: crisisGapInputIdentifiers(input),
    });
    warningSet.delete(warning);
  }

  for (const warning of warningSet) {
    pushItem(crisisGapGroupKey("", warning), {
      label: warning.replace(/_MISSING$/, "").toLowerCase(),
      warning,
      detail: "输入证据缺失，缺失不按 0 处理",
      identifiers: [warning],
    });
  }

  return (["equity", "liquidity", "commodity", "curve_credit", "fx", "other"] as CrisisGapGroupKey[])
    .map((key) => ({ key, label: CRISIS_GAP_GROUP_LABELS[key], items: itemsByGroup.get(key) ?? [] }))
    .filter((group) => group.items.length);
}

function crisisGapGroupKey(field: string, warning: string): CrisisGapGroupKey {
  const token = `${field} ${warning}`.toUpperCase();
  if (token.includes("HS300") || token.includes("EQUITY") || token.includes("STOCK")) {
    return "equity";
  }
  if (token.includes("DR007") || token.includes("REVERSE_REPO") || token.includes("LIQUIDITY")) {
    return "liquidity";
  }
  if (token.includes("NANHUA") || token.includes("COMMODITY")) {
    return "commodity";
  }
  if (token.includes("AA_") || token.includes("GOV_") || token.includes("CREDIT") || token.includes("CURVE")) {
    return "curve_credit";
  }
  if (token.includes("USDCNY") || token.includes("FX")) {
    return "fx";
  }
  return "other";
}

function crisisGapInputDetail(input: MacroToolkitInputEvidenceItem) {
  const rowText = formatCrisisRowCount(input.row_count);
  const dateText = input.latest_date ?? "日期缺失";
  const sourceText = input.source ?? "source missing";
  return `${rowText} · ${dateText} · ${sourceText} · 缺失不按 0 处理`;
}

function crisisGapInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  return uniqueDisplayParts([input.field, input.warning, ...(input.aliases ?? []), input.series_id]);
}

function findCrisisGapRepairItem(group: CrisisGapGroup, repairItems: MacroToolkitRepairItem[]) {
  const groupIdentifiers = new Set(
    group.items.flatMap((item) => item.identifiers).map((identifier) => identifier.toUpperCase()),
  );
  return repairItems.find((item) => {
    if (!canRefreshMacroSourceBackfill(item)) {
      return false;
    }
    const itemIdentifiers = uniqueDisplayParts([item.alias, item.key, item.label]).map((identifier) =>
      identifier.toUpperCase(),
    );
    return itemIdentifiers.some((identifier) => groupIdentifiers.has(identifier));
  });
}

function isNanhuaCrisisInput(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([input.field, ...(input.aliases ?? []), input.series_id]).map((item) =>
    item.toUpperCase(),
  );
  return (
    identifiers.includes("NANHUA") ||
    identifiers.includes(NANHUA_CRISIS_ALIAS) ||
    identifiers.includes(NANHUA_SYSTEM_SERIES_ID)
  );
}

function formatCrisisInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([
    ...(input.aliases ?? []),
    ...(isNanhuaCrisisInput(input) ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    input.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

function formatCommodityCoverageIdentifiers(item: CrisisCommodityCoverageItem) {
  const identifiers = uniqueDisplayParts([
    ...item.aliases,
    item.matched_alias,
    ...(item.field === "nanhua" || item.used_in_formula ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    item.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

function formatCrisisInputDetail(input: MacroToolkitInputEvidenceItem | undefined) {
  if (!input) {
    return "Nanhua commodity index / NH0100.NHF 未命中";
  }
  return `${input.label || input.field} · ${formatCrisisInputIdentifiers(input)} · ${
    input.latest_date ?? "日期缺失"
  }`;
}

function hasRealStrategySource(strategy: MacroToolkitStrategySummary) {
  return (
    strategy.result.price_source === "choice_stock_daily_observation" ||
    strategy.result.factor_source === "choice_stock_factor_snapshot"
  );
}

function hasCompleteRealStrategyChain(strategy: MacroToolkitStrategySummary) {
  if (strategy.status !== "complete" || strategyDataStatus(strategy) !== "complete") {
    return false;
  }
  const hasPriceSource = strategy.result.price_source === "choice_stock_daily_observation";
  const hasFactorSource = strategy.result.factor_source === "choice_stock_factor_snapshot";
  if (strategy.key === "multi_factor_selection") {
    return hasFactorSource;
  }
  if (strategy.key === "low_crowding_regime_multifactor") {
    return hasPriceSource && hasFactorSource;
  }
  return hasPriceSource;
}

function strategyDataStatus(strategy: MacroToolkitStrategySummary) {
  return typeof strategy.result.data_status === "string" && strategy.result.data_status.trim()
    ? strategy.result.data_status.trim()
    : strategy.status;
}

function choiceStockTableDetail(
  table: { row_count?: number; latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  return `行数 ${table?.row_count ?? 0} · ${choiceStockTableSummary(table, dateField)}`;
}

function choiceStockTableSummary(
  table: { latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  const dateText = table?.[dateField] ?? "缺失";
  const statusText = statusLabel(table?.freshness_status ?? "unknown");
  const fallbackText = choiceStockFallbackText(table);
  return [dateText, statusText, fallbackText].filter(Boolean).join(" · ");
}

function normalizeCommodityRefreshRows(refresh: MacroToolkitCommodityFuturesRefreshRun): CommodityRefreshProductRow[] {
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const table = refresh.table ?? "fact_commodity_futures_daily";
  return (refresh.products ?? []).filter(isRecord).map((item, index) => {
    const rawProductCode = commodityRefreshProductCode(item.product_code, index);
    const rawSeriesId = commodityRefreshString(item.series_id);
    const productCode = normalizeCommodityRefreshProductCode(rawProductCode, rawSeriesId);
    const option = MACRO_COMMODITY_PRODUCT_OPTIONS.find((candidate) => candidate.value === productCode);
    const productName = commodityRefreshString(item.name_zh) || option?.label || productCode;
    const estimatedRows = commodityRefreshNumber(item.estimated_rows);
    const writtenRows = commodityRefreshNumber(item.row_count);
    const rowCount = isDryRun ? estimatedRows ?? writtenRows : writtenRows ?? estimatedRows;
    const seriesId = rawSeriesId || commodityRefreshSeriesId(productCode);
    const latestDate = commodityRefreshString(item.latest_date) || (isDryRun ? refresh.end_date ?? "待刷新" : refresh.end_date ?? "缺失");
    const latestValue = commodityRefreshNumber(item.latest_value);
    const status = commodityRefreshProductStatus({ isDryRun, rowCount });
    return {
      key: `${productCode}-${index}`,
      productCode,
      productName,
      seriesId,
      status,
      estimatedRows,
      rowCount,
      rowCountLabel: rowCount == null ? "缺失" : `${isDryRun ? "预计 " : ""}${rowCount} 行`,
      latestDate,
      latestValue,
      vendor: commodityRefreshString(item.vendor) || (isDryRun ? "estimate_only" : "缺失"),
      table,
      isNanhua: isNanhuaCommodityRefreshRow(productCode, seriesId),
    };
  });
}

function commodityRefreshProductCode(value: unknown, index: number) {
  const code = commodityRefreshString(value);
  if (!code) {
    return `#${index + 1}`;
  }
  const normalized = code.toUpperCase();
  return normalized === NANHUA_CRISIS_ALIAS ? NANHUA_COMMODITY_PRODUCT_CODE : normalized;
}

function normalizeCommodityRefreshProductCode(productCode: string, seriesId: string | null) {
  const candidates = [productCode, seriesId ?? ""].map((item) => item.trim().toUpperCase()).filter(Boolean);
  for (const candidate of candidates) {
    if (candidate === NANHUA_CRISIS_ALIAS || candidate === NANHUA_SYSTEM_SERIES_ID) {
      return NANHUA_COMMODITY_PRODUCT_CODE;
    }
    if (candidate === "CA.COPPER") {
      return "CU";
    }
    if (candidate === "CA.ALUMINUM") {
      return "AL";
    }
    if (candidate.startsWith("COMMODITY.")) {
      const code = candidate.slice("COMMODITY.".length);
      if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === code)) {
        return code;
      }
    }
    if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === candidate)) {
      return candidate;
    }
  }
  return productCode;
}

function commodityRefreshString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function commodityRefreshNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function commodityRefreshSeriesId(productCode: string) {
  const normalized = productCode.trim().toUpperCase();
  if (normalized === NANHUA_COMMODITY_PRODUCT_CODE || normalized === NANHUA_CRISIS_ALIAS) {
    return NANHUA_SYSTEM_SERIES_ID;
  }
  if (normalized === "NHII") {
    return "NHII.NH";
  }
  if (normalized === "CU") {
    return "CA.COPPER";
  }
  if (normalized === "AL") {
    return "CA.ALUMINUM";
  }
  return normalized.startsWith("#") ? "缺失" : `COMMODITY.${normalized}`;
}

function isNanhuaCommodityRefreshRow(productCode: string, seriesId: string) {
  const normalizedProductCode = productCode.trim().toUpperCase();
  const normalizedSeriesId = seriesId.trim().toUpperCase();
  return (
    normalizedProductCode === NANHUA_COMMODITY_PRODUCT_CODE ||
    normalizedProductCode === NANHUA_CRISIS_ALIAS ||
    normalizedSeriesId === NANHUA_SYSTEM_SERIES_ID ||
    normalizedSeriesId === NANHUA_CRISIS_ALIAS
  );
}

function commodityRefreshIdentifierText(row: CommodityRefreshProductRow) {
  const identifiers = row.isNanhua
    ? [row.productCode, NANHUA_CRISIS_ALIAS, row.seriesId]
    : [row.productCode, row.seriesId];
  return Array.from(new Set(identifiers.filter(Boolean))).join(" / ");
}

function commodityRefreshProductStatus({
  isDryRun,
  rowCount,
}: {
  isDryRun: boolean;
  rowCount: number | null;
}): CommodityRefreshProductRow["status"] {
  if (rowCount == null || rowCount <= 0) {
    return "missing";
  }
  return isDryRun ? "estimated" : "written";
}

function commodityRefreshStatusText(status: CommodityRefreshProductRow["status"]) {
  if (status === "estimated") {
    return "预计可写";
  }
  if (status === "written") {
    return "已写入";
  }
  return "未命中";
}

function commodityRefreshStatusColor(status: CommodityRefreshProductRow["status"]) {
  if (status === "missing") {
    return "red";
  }
  return status === "written" ? "green" : "blue";
}

function formatCommodityRefreshResult(refresh: MacroToolkitCommodityFuturesRefreshRun) {
  const productCount = refresh.product_count ?? refresh.products?.length ?? 0;
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const rowCount = isDryRun
    ? refresh.estimated_total_rows ?? refresh.row_count ?? 0
    : refresh.row_count ?? refresh.estimated_total_rows ?? 0;
  const action = isDryRun ? "预估完成" : "刷新完成";
  const tradingDays = isDryRun && refresh.estimated_trading_days ? `，约 ${refresh.estimated_trading_days} 个交易日` : "";
  return `商品期货${action}：${productCount} 个品种，${rowCount} 行${tradingDays}`;
}

function commodityRefreshRowDeltaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshNullableNumberText(summary.row_count_before);
  const after = commodityRefreshNullableNumberText(summary.row_count_after);
  const delta = summary.row_count_delta == null ? "变化缺失" : `${summary.row_count_delta >= 0 ? "+" : ""}${summary.row_count_delta}`;
  return `行数 ${before} → ${after}（${delta}）`;
}

function commodityRefreshLatestDateText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.latest_trade_date_before ?? "缺失";
  const after = summary.latest_trade_date_after ?? "缺失";
  return `最新日期 ${before} → ${after}`;
}

function commodityRefreshCoverageText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshCountPair(summary.available_product_count_before, summary.target_product_count);
  const after = commodityRefreshCountPair(summary.available_product_count_after, summary.target_product_count);
  const newlyAvailable = summary.newly_available_products.length
    ? `新增 ${summary.newly_available_products.join(" / ")}`
    : "新增 无";
  const missing = summary.missing_products_after.length ? `缺失 ${summary.missing_products_after.join(" / ")}` : "缺失 无";
  return `覆盖 ${before} → ${after}，${newlyAvailable}，${missing}`;
}

function commodityRefreshNanhuaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.nanhua_latest_date_before ?? "缺失";
  const after = summary.nanhua_latest_date_after ?? "缺失";
  const value = formatNumberValue(summary.nanhua_latest_value_after, 2);
  return `南华 ${before} → ${after}，${value}`;
}

function commodityRefreshSourceText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const source = summary.source_vendors_after.length ? summary.source_vendors_after.join(" / ") : "缺失";
  return `来源 ${source}`;
}

function commodityRefreshNullableNumberText(value: number | null) {
  return value == null ? "缺失" : String(value);
}

function commodityRefreshCountPair(value: number | null, total: number | null) {
  return value == null || total == null ? "缺失" : `${value}/${total}`;
}

type CommodityHealthStatus = NonNullable<NonNullable<MacroToolkitCommodityFuturesRefreshStatus>["status"]>;

function commodityStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.status === "ok" ? "positive" : "missing";
}

function commodityNanhuaStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.nanhua_input?.status === "hit" ? "positive" : "missing";
}

function commodityNanhuaStatusValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  if (status.nanhua_input?.status !== "hit") {
    return "缺失";
  }
  const latestValue = formatNumberValue(status.nanhua_input.latest_value, 2);
  return latestValue === "缺失" ? "已命中" : `已命中 ${latestValue}`;
}

function commodityNanhuaStatusDetail(status: CommodityHealthStatus | null | undefined) {
  const input = status?.nanhua_input;
  if (!input || input.status !== "hit") {
    return "NHCI / NH0100.NHF 未命中";
  }
  const date = input.latest_trade_date ?? "日期缺失";
  const value = formatNumberValue(input.latest_value, 2);
  const source = input.source_version || input.vendor_version || "来源缺失";
  return `${input.product_code} / ${input.series_id} · ${date} · ${value} · ${source}`;
}

function commodityLatestDateValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.latest_trade_date ?? "暂无数据";
}

function commodityTableStatusDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "fact_commodity_futures_daily 状态待确认";
  }
  const rowText = status.row_count == null ? "行数缺失" : `${status.row_count} 行`;
  return `${status.table} · ${commodityTableStatusLabel(status.status)} · ${rowText}`;
}

function commodityCoverageValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  const coverage = status.coverage;
  return `${coverage.available_product_count}/${coverage.target_product_count}`;
}

function commodityCoverageDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "覆盖品种待确认";
  }
  const available = status.coverage.available_products.length ? status.coverage.available_products.join(" / ") : "无命中";
  const missing = status.coverage.missing_products.length ? ` · 缺失 ${status.coverage.missing_products.join(" / ")}` : "";
  return `${available}${missing}`;
}

function commoditySourceValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.source_vendors.length ? status.source_vendors.join(" / ") : "缺失";
}

function commoditySourceDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "来源待确认";
  }
  const nanhua = status.nanhua_input;
  const source = nanhua?.source_version || nanhua?.vendor_version || status.source_vendors.join(" / ") || "来源缺失";
  return `${status.table} · ${source}`;
}

function commodityTableStatusLabel(status: string) {
  if (status === "ok") {
    return "正常";
  }
  if (status === "empty_table") {
    return "暂无数据";
  }
  if (status === "missing_table") {
    return "未接入";
  }
  if (status === "unreadable_database") {
    return "读取失败";
  }
  return status || "未知";
}

function commodityFuturesPermissionErrorMessage() {
  return "当前账号没有商品期货刷新权限，请先授予 macro_toolkit.commodity_futures:refresh。";
}

function commodityFuturesPermissionPendingMessage() {
  return "商品期货刷新授权待确认，请先确认 macro_toolkit.commodity_futures:dry_run / refresh。";
}

function commodityFuturesPermissionBlockMessage(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  return permission?.allowed === false ? commodityFuturesPermissionErrorMessage() : commodityFuturesPermissionPendingMessage();
}

function formatCommodityFuturesRefreshError(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  if (/not allowed/i.test(message) && message.includes("macro_toolkit.commodity_futures")) {
    return commodityFuturesPermissionErrorMessage();
  }
  return message || "刷新商品期货失败";
}

function commodityFuturesPermissionDetail(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "resource macro_toolkit.commodity_futures";
  }
  return choiceStockPermissionDetail(permission, "macro_toolkit.commodity_futures");
}

function commodityFuturesPermissionNoticeTitle(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  return permission?.allowed === false ? "缺少商品期货刷新授权" : "商品期货刷新授权待确认";
}

function commodityFuturesPermissionNotice(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  const resource = permission?.resource ?? "macro_toolkit.commodity_futures";
  const actions = permission?.actions?.length ? permission.actions.join(" / ") : "dry_run / refresh";
  const user = permission?.user_id || "anonymous";
  const role = permission?.role || "unknown";
  return `请在 scope store 授予 ${resource} 的 action refresh；dry_run / refresh 都需要这条授权。当前用户 ${user}，角色 ${role}，动作 ${actions}。`;
}

function choiceStockFallbackText(
  table: { fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
) {
  if (table?.fallback_mode !== "latest_available" || !table.fallback_date) {
    return "";
  }
  return `fallback ${table.fallback_mode} · 最近可用 ${table.fallback_date}`;
}

function choiceStockPermissionValue(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "待确认";
  }
  if (permission.allowed === false) {
    return "未授权";
  }
  return permission.allowed === true || permission.mode === "identity_only" ? "已授权" : "待确认";
}

function choiceStockRefreshValue(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  if (choiceStockHasRunEvidence(refresh)) {
    return statusLabel(refresh.status);
  }
  return choiceStockPermissionValue(permission);
}

function choiceStockRefreshDetail(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  const hasRunEvidence = choiceStockHasRunEvidence(refresh);
  const permissionDetail = choiceStockPermissionDetail(hasRunEvidence ? (refresh.permission ?? permission) : permission);
  if (!hasRunEvidence) {
    return permissionDetail;
  }
  const runId = refresh.run_id ?? "none";
  const reportDate = refresh.report_date ?? "unknown";
  const triggerMode = refresh.trigger_mode ?? "unknown";
  const historyRows = refresh.history_row_count ?? "-";
  const factorRows = refresh.factor_row_count ?? "-";
  const source = refresh.source_version?.trim();
  const vendor = refresh.vendor_version?.trim();
  const rule = refresh.rule_version?.trim();
  const cache = refresh.cache_version?.trim();
  const versionText = [
    source ? `source ${source}` : "",
    vendor ? `vendor ${vendor}` : "",
    rule ? `rule ${rule}` : "",
    cache ? `cache ${cache}` : "",
  ].filter(Boolean).join(" · ");
  const version = versionText ? ` · ${versionText}` : "";
  const failureText = choiceStockRefreshFailureText(refresh);
  const failure = failureText ? ` · failure ${failureText}` : "";
  return `run ${runId} · report ${reportDate} · trigger ${triggerMode} · rows history ${historyRows} / factor ${factorRows}${version}${failure} · ${permissionDetail}`;
}

function choiceStockHasRunEvidence(refresh: MacroToolkitChoiceStockRefreshRun | null | undefined): refresh is MacroToolkitChoiceStockRefreshRun {
  return Boolean(refresh?.run_id);
}

function choiceStockRefreshFailureText(refresh: MacroToolkitChoiceStockRefreshRun) {
  const category = refresh.failure_category?.trim();
  const reason = refresh.failure_reason?.trim();
  if (category && reason) {
    return `${category}: ${reason}`;
  }
  return reason || refresh.error_message?.trim() || category || "";
}

function choiceStockPermissionDetail(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
  defaultResource = "choice_stock.refresh",
) {
  if (!permission) {
    return `resource ${defaultResource}`;
  }
  const resource = permission.resource ?? defaultResource;
  const mode = permission.mode || "unknown";
  const actions = permission.actions?.length ? permission.actions.join(" / ") : "unknown";
  const user = permission.user_id || "anonymous";
  return `resource ${resource} · mode ${mode} · actions ${actions} · user ${user}`;
}

function formatSignedRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  const percent = value * 100;
  return `${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%`;
}

function formatPlainRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumberValue(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return value.toFixed(digits);
}

function portfolioConstraintText(portfolio: MacroToolkitShadowPortfolio) {
  const constraints = portfolio.constraints;
  const parts = [
    constraints.pe_max == null ? "" : `PE≤${constraints.pe_max}`,
    constraints.pb_max == null ? "" : `PB≤${constraints.pb_max}`,
    constraints.turnover_cap == null ? "" : `换手≤${Math.round(constraints.turnover_cap * 100)}%`,
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : "沿用正式规则约束";
}

function portfolioWeightsText(portfolio: MacroToolkitShadowPortfolio) {
  const labels: Record<string, string> = {
    value: "价值",
    quality: "质量",
    momentum: "动量",
    low_vol: "低波",
    dividend: "红利",
  };
  return Object.entries(portfolio.weights)
    .map(([key, value]) => `${labels[key] ?? key}${Math.round(value * 100)}%`)
    .join(" / ");
}

function costResultText(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  const result = portfolio.cost_results.find((item) => item.cost_bps === costBps);
  if (!result) {
    return `${costBps}bp 缺失`;
  }
  return `${costBps}bp ${formatSignedRatio(result.total_return)} / 超额 ${formatSignedRatio(result.excess_return)}`;
}

function portfolioCostResult(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  return portfolio.cost_results.find((item) => item.cost_bps === costBps);
}

function shadowPortfolioPeriodRows(
  report: MacroToolkitShadowPortfolioReport,
  portfolio: MacroToolkitShadowPortfolio,
) {
  return report.period_returns.filter((row) => row.portfolio_key === portfolio.key);
}

function shadowPortfolioPeriodWinLossText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "周期缺失";
  }
  const wins = rows.filter((row) => row.excess_return > 0).length;
  return `${wins}赢 / ${rows.length - wins}输`;
}

function shadowPortfolioPeriodRangeText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "最佳缺失 / 最差缺失";
  }
  const best = rows.reduce((winner, row) => (row.excess_return > winner.excess_return ? row : winner), rows[0]!);
  const worst = rows.reduce((loser, row) => (row.excess_return < loser.excess_return ? row : loser), rows[0]!);
  return `最佳 ${formatSignedRatio(best.excess_return)} / 最差 ${formatSignedRatio(worst.excess_return)}`;
}

function shadowPortfolioCostGateText(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const passingCosts = [20, 50].filter((costBps) => {
    const referenceCost = portfolioCostResult(reference, costBps);
    const candidateCost = portfolioCostResult(candidate, costBps);
    return (
      referenceCost != null &&
      candidateCost != null &&
      candidateCost.total_return > referenceCost.total_return &&
      candidateCost.excess_return > referenceCost.excess_return
    );
  });
  if (passingCosts.length === 2) {
    return "20bp/50bp 均胜出";
  }
  if (passingCosts.length) {
    return `${passingCosts.join("bp / ")}bp 胜出`;
  }
  return "成本后未胜出";
}

function shadowPortfolioAdmissionText(candidate: MacroToolkitShadowPortfolio) {
  if (!candidate.admission) {
    return "准入口径缺失";
  }
  return `${candidate.admission.label} · ${candidate.admission.summary}`;
}

function admissionCriterionText(threshold: unknown) {
  if (threshold == null) {
    return "";
  }
  if (Array.isArray(threshold)) {
    return threshold.length ? threshold.join(" / ") : "无";
  }
  if (typeof threshold === "string" || typeof threshold === "number" || typeof threshold === "boolean") {
    return String(threshold);
  }
  return "";
}

function holdingCodeList(holdings: MacroToolkitShadowPortfolioHolding[]) {
  return holdings.slice(0, 3).map((holding) => holding.stock_code).join(" / ") || "无";
}

function shadowPortfolioHoldingDiff(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const referenceCodes = new Set(reference.latest_holdings.map((holding) => holding.stock_code));
  const candidateCodes = new Set(candidate.latest_holdings.map((holding) => holding.stock_code));
  const overlap = candidate.latest_holdings.filter((holding) => referenceCodes.has(holding.stock_code));
  const candidateOnly = candidate.latest_holdings.filter((holding) => !referenceCodes.has(holding.stock_code));
  const referenceOnly = reference.latest_holdings.filter((holding) => !candidateCodes.has(holding.stock_code));
  return {
    overlapText: `持仓重合 ${overlap.length}/${Math.max(candidate.latest_holdings.length, 1)}`,
    candidateOnlyText: `新增观察 ${holdingCodeList(candidateOnly)}`,
    referenceOnlyText: `正式独有 ${holdingCodeList(referenceOnly)}`,
  };
}

function periodChipText(row: MacroToolkitShadowPortfolioPeriodReturn) {
  return `${row.start_date.slice(5)}→${row.end_date.slice(5)} ${formatSignedRatio(row.excess_return)}`;
}

function shadowPortfolioFactorWindowText(report: MacroToolkitShadowPortfolioReport) {
  const firstDate = report.factor_dates[0];
  const lastDate = report.factor_dates.at(-1) ?? report.as_of_date;
  if (!firstDate || !lastDate) {
    return `${report.completed_periods}周期`;
  }
  return `${firstDate} → ${lastDate} / ${report.completed_periods}周期`;
}

function shadowPortfolioCostModelText(report: MacroToolkitShadowPortfolioReport) {
  const costs = report.cost_model.cost_bps.length ? `${report.cost_model.cost_bps.join("/")}bp` : "成本缺失";
  const initialBuild = report.cost_model.initial_build_included ? "含初始建仓" : "不含初始建仓";
  const finalLiquidation = report.cost_model.final_liquidation_included ? "含期末清仓" : "不含期末清仓";
  return `${costs} · ${initialBuild} · ${finalLiquidation}`;
}

function shadowPortfolioReviewAction(candidate: MacroToolkitShadowPortfolio) {
  if (candidate.admission?.status === "passed") {
    return "进入正式候选评审，不自动替换正式规则";
  }
  if (candidate.admission?.status === "needs_review") {
    return "补齐历史与告警复核后再评审";
  }
  if (candidate.admission?.status === "failed") {
    return "保持影子观察，暂不进入正式候选";
  }
  return "等待准入口径补齐";
}

function shadowPortfolioWarningText(warning: string) {
  if (warning === "DUCKDB_BUSY") {
    return "本地股票历史库正在刷新或被落库任务占用，稍后刷新页面即可重试。";
  }
  if (warning.startsWith("DUCKDB_OPEN_FAILED")) {
    return "DuckDB 读连接打开失败，暂时不能生成影子组合回测。";
  }
  if (warning === "DUCKDB_NOT_FOUND") {
    return "本地股票历史库不存在，暂时不能生成影子组合回测。";
  }
  if (warning.startsWith("MISSING_TABLES")) {
    return "本地股票历史表或因子快照表缺失，暂时不能生成影子组合回测。";
  }
  if (warning === "FACTOR_HISTORY_TOO_SHORT" || warning === "SHORT_HISTORY") {
    return "因子快照历史偏短，当前结果只能作为只读观察。";
  }
  if (warning === "READ_ONLY_SHADOW_NOT_PRODUCTION") {
    return "只读影子评估，不能作为正式投研信号。";
  }
  return warning;
}

function shadowPortfolioUnavailableDescription(warnings: readonly string[]) {
  const visibleWarnings = Array.from(new Set(warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return visibleWarnings.join(" / ") || "本地股票历史或因子快照不足。";
}

function ShadowPortfolioEvidencePack({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!candidates.length) {
    return null;
  }
  const warnings = Array.from(new Set(report.warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return (
    <div className="macro-toolkit-shadow-evidence" aria-label="影子组合准入证据包">
      <div className="macro-toolkit-capability-result-head">
        <span>准入证据包</span>
        <Tag color="default">只读评估</Tag>
      </div>
      <div className="macro-toolkit-shadow-evidence__facts">
        <span>
          <b>规则版本</b>
          {report.rule_version}
        </span>
        <span>
          <b>回测窗口</b>
          {shadowPortfolioFactorWindowText(report)}
        </span>
        <span>
          <b>成本模型</b>
          {shadowPortfolioCostModelText(report)}
        </span>
        <span>
          <b>数据来源</b>
          {report.tables_used.join(" / ") || "数据表缺失"}
        </span>
      </div>
      <div className="macro-toolkit-shadow-evidence__actions">
        {candidates.map((candidate) => (
          <span key={`evidence-${candidate.key}`}>
            <b>评审动作</b>
            {candidate.label}：{shadowPortfolioReviewAction(candidate)}
          </span>
        ))}
      </div>
      <div className="macro-toolkit-shadow-evidence__warnings">
        {(warnings.length ? warnings : ["无额外告警。"]).map((warning) => (
          <span key={warning}>{warning}</span>
        ))}
      </div>
    </div>
  );
}

function ShadowPortfolioReview({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const reference =
    report.portfolios.find((portfolio) => portfolio.role === "production_reference") ?? report.portfolios[0];
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!reference || !candidates.length) {
    return null;
  }
  return (
    <div className="macro-toolkit-shadow-review" aria-label="影子组合稳健性审查">
      {candidates.map((candidate) => {
        const rows = shadowPortfolioPeriodRows(report, candidate);
        const holdingDiff = shadowPortfolioHoldingDiff(reference, candidate);
        return (
          <div className="macro-toolkit-shadow-review__item" key={`review-${candidate.key}`}>
            <div className="macro-toolkit-capability-result-head">
              <span>稳健性审查</span>
              <Tag color="blue">{candidate.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-review__facts">
              <span>
                <b>周期胜负</b>
                {shadowPortfolioPeriodWinLossText(rows)}
              </span>
              <span>
                <b>区间分布</b>
                {shadowPortfolioPeriodRangeText(rows)}
              </span>
              <span>
                <b>成本后结论</b>
                {shadowPortfolioCostGateText(reference, candidate)}
              </span>
              <span>
                <b>准入结论</b>
                {shadowPortfolioAdmissionText(candidate)}
              </span>
              <span>
                <b>持仓差异</b>
                {holdingDiff.overlapText}
              </span>
            </div>
            {candidate.admission?.criteria.length ? (
              <div className="macro-toolkit-shadow-review__criteria">
                {candidate.admission.criteria.map((criterion) => {
                  const thresholdText = admissionCriterionText(criterion.threshold);
                  return (
                    <div
                      className={`macro-toolkit-shadow-review__criterion ${
                        criterion.passed
                          ? "macro-toolkit-shadow-review__criterion--pass"
                          : "macro-toolkit-shadow-review__criterion--fail"
                      }`}
                      key={`${candidate.key}-${criterion.key}`}
                    >
                      <b>{criterion.label}</b>
                      {criterion.passed ? "通过" : "未通过"}
                      {thresholdText ? ` · ${thresholdText}` : ""}
                    </div>
                  );
                })}
              </div>
            ) : null}
            {rows.length ? (
              <div className="macro-toolkit-shadow-review__periods">
                {rows.slice(-4).map((row) => (
                  <span key={`${candidate.key}-${row.start_date}-${row.end_date}`}>{periodChipText(row)}</span>
                ))}
              </div>
            ) : null}
            <div className="macro-toolkit-shadow-holdings macro-toolkit-shadow-holdings--diff">
              <span>{holdingDiff.candidateOnlyText}</span>
              <span>{holdingDiff.referenceOnlyText}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ShadowPortfolioReportPanel({ report }: { report: MacroToolkitShadowPortfolioReport | null }) {
  if (!report) {
    return null;
  }
  if (report.status !== "complete") {
    return (
      <div className="macro-toolkit-shadow-report macro-toolkit-shadow-report--warning" aria-label="影子组合报告">
        <Alert
          type="warning"
          showIcon
          message="影子组合报告暂不可用"
          description={shadowPortfolioUnavailableDescription(report.warnings)}
        />
        {report.warnings.length ? (
          <div className="macro-toolkit-tag-row">
            {report.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="macro-toolkit-shadow-report" aria-label="影子组合报告">
      <div className="macro-toolkit-shadow-report__head">
        <div>
          <span>只读影子组合</span>
          <strong>{report.as_of_date ?? "日期缺失"}</strong>
          <small>
            {report.completed_periods} 个完成调仓周期 / {report.benchmark?.label ?? "基准缺失"}
          </small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="blue">{report.rule_version}</Tag>
          {report.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      </div>
      <div className="macro-toolkit-shadow-report__grid">
        {report.portfolios.map((portfolio) => (
          <div className="macro-toolkit-shadow-card" key={portfolio.key}>
            <div className="macro-toolkit-capability-result-head">
              <span>{portfolio.role === "shadow_candidate" ? "影子观察" : "正式参照"}</span>
              <Tag color={portfolio.role === "shadow_candidate" ? "blue" : "default"}>{portfolio.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-card__metrics">
              <MetricTile label="总收益" value={formatSignedRatio(portfolio.total_return)} detail="不含生产替换" />
              <MetricTile label="超额" value={formatSignedRatio(portfolio.excess_return)} detail="相对因子池等权" />
              <MetricTile label="最大回撤" value={formatSignedRatio(portfolio.max_drawdown)} detail={`胜率 ${formatPlainRatio(portfolio.win_rate)}`} />
              <MetricTile label="估值" value={`PE ${formatNumberValue(portfolio.average_pe)}`} detail={`PB ${formatNumberValue(portfolio.average_pb)}`} />
            </div>
            <div className="macro-toolkit-strategy-trace">
              <span>
                <b>权重</b>
                {portfolioWeightsText(portfolio)}
              </span>
              <span>
                <b>约束</b>
                {portfolioConstraintText(portfolio)}
              </span>
              <span>
                <b>换手</b>
                {formatPlainRatio(portfolio.average_turnover)}
              </span>
              <span>
                <b>20bp</b>
                {costResultText(portfolio, 20)}
              </span>
              <span>
                <b>50bp</b>
                {costResultText(portfolio, 50)}
              </span>
            </div>
            {portfolio.latest_holdings.length ? (
              <div className="macro-toolkit-shadow-holdings">
                {portfolio.latest_holdings.slice(0, 5).map((holding) => (
                  <span key={`${portfolio.key}-${holding.stock_code}`}>
                    {holding.rank}. {holding.stock_code} · {holding.industry}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <ShadowPortfolioReview report={report} />
      <ShadowPortfolioEvidencePack report={report} />
    </div>
  );
}

function StrategySummaryCard({ strategy }: { strategy: MacroToolkitStrategySummary }) {
  const metric = strategy.primary_metric;
  const dataStatus = strategyDataStatus(strategy);
  const priceSource =
    typeof strategy.result.price_source === "string" && strategy.result.price_source.trim()
      ? strategy.result.price_source
      : "价格来源缺失";
  const factorSource =
    typeof strategy.result.factor_source === "string" && strategy.result.factor_source.trim()
      ? strategy.result.factor_source
      : "因子来源缺失";
  const warnings = strategy.warnings;
  const sourceVersions = strategyTraceList(strategy.result.source_versions);
  const vendorVersions = strategyTraceList(strategy.result.vendor_versions);
  const factorSourceVersions = strategyTraceList(strategy.result.factor_source_versions);
  const factorVendorVersions = strategyTraceList(strategy.result.factor_vendor_versions);
  const factorRuleVersions = strategyTraceList(strategy.result.factor_rule_versions);
  const factorRunIds = strategyTraceList(strategy.result.factor_run_ids);
  const missingFactorInputs = strategyTraceList(strategy.result.missing_factor_inputs, Number.POSITIVE_INFINITY);
  const asOfDate = strategyScalarText(strategy.result.as_of_date);
  const factorAsOfDate = strategyScalarText(strategy.result.factor_as_of_date);
  const factorDateStatus = strategyScalarText(strategy.result.factor_date_status);

  return (
    <div className={`macro-toolkit-strategy-card macro-toolkit-strategy-card--${strategy.tone}`}>
      <div className="macro-toolkit-capability-result-head">
        <span>{strategy.group}</span>
        <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
      </div>
      <strong>{strategy.label}</strong>
      <div className="macro-toolkit-strategy-metric">
        <span>{metric?.label ?? "状态"}</span>
        <b>{metric ? `${metric.value}${metric.unit}` : statusLabel(strategy.status)}</b>
      </div>
      <small>{strategy.evidence.slice(0, 2).join(" / ") || "暂无证据"}</small>
      <div className="macro-toolkit-strategy-trace" aria-label={`${strategy.label}策略追踪`}>
        <span>
          <b>数据状态</b>
          {statusLabel(dataStatus)} <em>{dataStatus}</em>
        </span>
        <span>
          <b>价格</b>
          {priceSource}
        </span>
        <span>
          <b>因子</b>
          {factorSource}
        </span>
        {asOfDate ? (
          <span>
            <b>行情日</b>
            {asOfDate}
          </span>
        ) : null}
        {factorAsOfDate ? (
          <span>
            <b>因子日</b>
            {factorAsOfDate}
            {factorDateStatus ? ` · ${statusLabel(factorDateStatus)}` : ""}
          </span>
        ) : null}
        {sourceVersions ? (
          <span>
            <b>价格版本</b>
            {sourceVersions}
          </span>
        ) : null}
        {vendorVersions ? (
          <span>
            <b>行情厂商</b>
            {vendorVersions}
          </span>
        ) : null}
        {factorSourceVersions ? (
          <span>
            <b>因子版本</b>
            {factorSourceVersions}
          </span>
        ) : null}
        {factorVendorVersions ? (
          <span>
            <b>因子厂商</b>
            {factorVendorVersions}
          </span>
        ) : null}
        {factorRuleVersions ? (
          <span>
            <b>因子规则</b>
            {factorRuleVersions}
          </span>
        ) : null}
        {factorRunIds ? (
          <span>
            <b>因子运行</b>
            {factorRunIds}
          </span>
        ) : null}
        {missingFactorInputs ? (
          <span>
            <b>缺失输入</b>
            {missingFactorInputs}
          </span>
        ) : null}
        {warnings.length ? (
          <div className="macro-toolkit-strategy-warnings">
            {warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function strategyTraceList(value: unknown, maxItems = 3) {
  if (!Array.isArray(value)) {
    return "";
  }
  const items = value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
  return (Number.isFinite(maxItems) ? items.slice(0, maxItems) : items).join(" / ");
}

function strategyScalarText(value: unknown) {
  if (typeof value !== "string" && typeof value !== "number") {
    return "";
  }
  return String(value).trim();
}

const A_SHARE_RISK_METRICS: Array<{
  key: string;
  label: string;
  format?: "percent" | "ratio";
}> = [
  { key: "up_count", label: "上涨家数" },
  { key: "up_ratio", label: "上涨比例", format: "percent" },
  { key: "drop_3_count", label: "跌超3%" },
  { key: "drop_5_count", label: "跌超5%" },
  { key: "limit_down_count", label: "跌停家数" },
  { key: "near_down_count", label: "近跌停" },
  { key: "turnover_ratio_ma20", label: "成交额/20日", format: "ratio" },
  { key: "index_drawdown_from_high", label: "回落幅度", format: "percent" },
];

function AShareRiskPanel({ risk }: { risk?: MacroToolkitAShareRiskPayload }) {
  if (!risk) {
    return (
      <div className="macro-toolkit-empty-output">
        市场踩踏风险数据未返回，当前不能形成风险等级判断。
      </div>
    );
  }
  const tone = riskLevelTone(risk.risk_level);
  const scoreText = risk.risk_score === null ? "缺失" : risk.risk_score;
  return (
    <div className={`macro-toolkit-a-share-risk macro-toolkit-a-share-risk--${tone}`}>
      <div className="macro-toolkit-a-share-risk__summary" style={scoreStyle(risk.risk_score)}>
        <div className="macro-toolkit-capability-result-head">
          <span>
            <MacroStatusIcon tone={tone}>
              {tone === "negative" ? <WarningOutlined /> : <ClockCircleOutlined />}
            </MacroStatusIcon>
            {risk.trade_date ?? "日期缺失"}
          </span>
          <div className="macro-toolkit-tag-row">
            <Tag color={statusColor(risk.status)}>{statusLabel(risk.status)}</Tag>
            <Tag color={riskLevelColor(risk.risk_level)}>{risk.risk_name}</Tag>
          </div>
        </div>
        <strong>{scoreText}</strong>
        <div className="macro-toolkit-score-track" aria-hidden="true">
          <span />
        </div>
        <p title={risk.summary}>{compactText(risk.summary || "风险摘要缺失。", 38)}</p>
        <small title={risk.position_rule}>{compactText(risk.position_rule || "仓位规则缺失，不能据此放大仓位。", 30)}</small>
      </div>

      <div className="macro-toolkit-a-share-risk__metrics">
        {A_SHARE_RISK_METRICS.map((metric) => (
          <div className="macro-toolkit-strategy-metric" key={metric.key}>
            <span>{metric.label}</span>
            <b>{formatRiskMetric(risk.metrics[metric.key], metric.format)}</b>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-a-share-risk__lists">
        <RiskList title="触发规则" items={risk.triggered_rules} emptyText="未触发明确踩踏规则。" />
        <RiskList title="观察条件" items={risk.watch_next} emptyText="暂无下一步观察条件。" />
        <RiskList title="数据提示" items={risk.warnings} emptyText={risk.status === "complete" ? "数据能力完整。" : "降级原因缺失。"} />
      </div>
    </div>
  );
}

function RiskList({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  const visibleItems = items.length ? items : [emptyText];
  return (
    <div className="macro-toolkit-a-share-risk__list">
      <span>{title}</span>
      {visibleItems.slice(0, 4).map((item) => (
        <small key={item} title={item}>
          {compactText(item, 26)}
        </small>
      ))}
    </div>
  );
}

function formatRiskMetric(value: number | null | undefined, format?: "percent" | "ratio") {
  if (value == null) {
    return "缺失";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (format === "ratio") {
    return `${value.toFixed(2)}x`;
  }
  return Number.isInteger(value) ? value.toString() : value.toFixed(2);
}

function formatMetricDisplay(metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>) {
  return `${metric.label} ${metric.value}${metric.unit}`;
}

function MetricTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
  testId,
  detailMaxLength = 26,
}: {
  icon?: ReactNode;
  label: string;
  value: string | number;
  detail: string;
  tone?: "neutral" | "positive" | "missing";
  testId?: string;
  detailMaxLength?: number;
}) {
  return (
    <div className={`macro-toolkit-metric macro-toolkit-metric--${tone}`} data-testid={testId}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <InfoCircleOutlined />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, detailMaxLength)}</small>
    </div>
  );
}
