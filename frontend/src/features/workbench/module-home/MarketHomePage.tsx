import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroRefreshPayload } from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { buildModuleHomeView } from "./moduleHomeModel";
import type { MarketFinancialChartSection } from "./marketFinancialChartsModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import MarketHomeLayout from "./MarketHomeLayout";
import { useMarketHomeQueries } from "./useMarketHomeQueries";
import { refetchAfterMarketRefresh } from "./marketHomeRefresh";
import { buildMarketHomeSnapshotState } from "./marketHomeSnapshotState";

async function refetchLoadedMarketQuery(
  query: { data?: unknown; isError?: boolean; refetch: () => Promise<unknown> } | undefined,
) {
  if (query?.data === undefined && !query?.isError) return;
  await refetchAfterMarketRefresh(query);
}

const MARKET_REFRESH_TERMINAL_STATUSES = new Set(["completed", "partial", "degraded", "failed"]);
const MARKET_REFRESH_ACCEPTED_STATUSES = new Set(["completed", "partial", "degraded"]);
const MARKET_REFRESH_FAILED_DATA_NOTICE = "当前展示的仍是上次成功刷新的数据。";

function readTrimmedText(value: unknown) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function pickChoiceMacroRefreshStructuredDetail(error: unknown) {
  if (typeof error === "string") {
    return {
      message: error.trim(),
      code: "",
      runId: "",
      lastStatus: "",
    };
  }
  if (!error || typeof error !== "object") {
    return {
      message: "",
      code: "",
      runId: "",
      lastStatus: "",
    };
  }
  const errorRecord = error as Record<string, unknown>;
  const detail =
    errorRecord.detail && typeof errorRecord.detail === "object" && !Array.isArray(errorRecord.detail)
      ? (errorRecord.detail as Record<string, unknown>)
      : null;
  return {
    message:
      readTrimmedText(detail?.message) ||
      readTrimmedText(detail?.error_message) ||
      readTrimmedText(detail?.detail) ||
      readTrimmedText(errorRecord.message),
    code: readTrimmedText(detail?.code),
    runId: readTrimmedText(detail?.run_id) || readTrimmedText(errorRecord.runId),
    lastStatus: readTrimmedText(detail?.last_status),
  };
}

function pickPollingTimeoutContext(message: string) {
  const runIdMatch = /run_id:\s*([^) ,；。]+)/i.exec(message);
  const lastStatusMatch = /(?:最后状态|last status):\s*([^)，；。]+)/i.exec(message);
  return {
    runId: runIdMatch?.[1]?.trim() ?? "",
    lastStatus: lastStatusMatch?.[1]?.trim() ?? "",
  };
}

function formatChoiceMacroRefreshTerminalContext(runId: string, lastStatus: string) {
  const parts = [];
  if (runId) {
    parts.push(`run_id ${runId}`);
  }
  if (lastStatus) {
    parts.push(`最后状态 ${lastStatus}`);
  }
  if (parts.length === 0) {
    return "";
  }
  return `（${parts.join("，")}）`;
}

function formatChoiceMacroRefreshError(error: unknown) {
  const { message, code, runId, lastStatus } = pickChoiceMacroRefreshStructuredDetail(error);
  const messageWithContext = [message, code ? `code=${code}` : "", runId ? `run_id=${runId}` : "", lastStatus ? `last_status=${lastStatus}` : ""]
    .filter(Boolean)
    .join(" ");
  if (/not allowed|permission|forbidden|denied|无权限|权限不足/i.test(message)) {
    return "当前账号没有刷新 Choice 宏观数据的权限。";
  }
  if (
    /governed deadline|deadline|choice_macro_refresh_deadline/i.test(messageWithContext) &&
    /terminal[_\s-]?status[_\s-]?unavailable|terminal status is unavailable|终态/i.test(messageWithContext)
  ) {
    return `Choice 宏观刷新超时，治理截止时间前未收到终态${formatChoiceMacroRefreshTerminalContext(runId, lastStatus)}；请稍后重试或检查刷新任务状态。`;
  }
  if (/terminal[_\s-]?status[_\s-]?unavailable|terminal status is unavailable/i.test(messageWithContext)) {
    return `Choice 宏观刷新状态失联，系统暂时拿不到终态${formatChoiceMacroRefreshTerminalContext(runId, lastStatus)}；请稍后重试或检查刷新任务状态。`;
  }
  if (/任务轮询超时/i.test(message)) {
    const pollingContext = pickPollingTimeoutContext(message);
    return `Choice 宏观刷新超时，轮询窗口内未收到终态${formatChoiceMacroRefreshTerminalContext(
      pollingContext.runId,
      pollingContext.lastStatus,
    )}；请稍后重试或检查刷新任务状态。`;
  }
  if (/timeout|timed out|超时/i.test(message)) {
    return "市场数据源响应超时，请稍后重试。";
  }
  if (/vendor|供应方/i.test(message)) {
    return "供应方数据刷新异常，请稍后重试。";
  }
  return "市场数据刷新失败，请稍后重试。";
}

function formatRefreshWarning(message: string) {
  if (/permission|not allowed|forbidden|denied|无权限|权限不足/i.test(message)) {
    return "部分数据源权限不足";
  }
  if (/timeout|timed out|超时/i.test(message)) {
    return "部分数据源响应超时";
  }
  if (/vendor|供应方/i.test(message)) {
    return "供应方数据异常";
  }
  if (/supplement|gate[_\s-]?supplement|补充数据/i.test(message)) {
    return "补充数据刷新未完成";
  }
  if (/[\u3400-\u9fff]/u.test(message) && !/failed|error|exception/i.test(message)) {
    return message.trim();
  }
  return "部分序列未通过完整性校验";
}

function formatDegradedRefreshStatus(payload: ChoiceMacroRefreshPayload) {
  const warningText = Array.from(
    new Set(
      [...(payload.warnings ?? []), payload.warning_code ?? ""]
        .filter((item) => item.trim().length > 0)
        .map(formatRefreshWarning),
    ),
  ).join("；") || "部分序列未通过完整性校验";
  return `刷新完成，但存在质量告警：${warningText}。数据已更新，请注意核对相关序列。`;
}

function appendFailedDataNotice(message: string) {
  const trimmed = message.trimEnd();
  const needsSeparator = trimmed.length > 0 && !/[。！？；]$/.test(trimmed);
  return `${trimmed}${needsSeparator ? "。" : ""}${MARKET_REFRESH_FAILED_DATA_NOTICE}`;
}

export default function MarketHomePage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [chartsVisible, setChartsVisible] = useState(false);
  const [backendActiveKey, setBackendActiveKey] = useState("choice");
  const [chartSectionKeys, setChartSectionKeys] = useState<MarketFinancialChartSection["key"][]>([]);
  const handleChartsVisible = useCallback(() => setChartsVisible(true), []);
  const queries = useMarketHomeQueries({ chartsVisible, backendActiveKey, chartSectionKeys });
  const config = moduleWorkbenchHomeConfigs.market;
  const view = useMemo(
    () => ({
      ...buildModuleHomeView("market", client, queries),
      ...buildMarketHomeSnapshotState(queries.marketSnapshot),
      // 旧曲线形态来自独立的 full 宏观查询，不并入本次首屏快照的判断。
      marketDeskIntel: undefined,
    }),
    [client, queries],
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState("");
  const [refreshError, setRefreshError] = useState("");

  // 卸载时取消刷新任务轮询，避免离开首页后长任务继续请求并批量 refetch。
  const unmountAbortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    unmountAbortRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const handleRefreshData = useCallback(async () => {
    const signal = unmountAbortRef.current?.signal;
    setIsRefreshing(true);
    setRefreshError("");
    setRefreshStatus("正在刷新宏观数据（回填 30 天）…");
    try {
      const payload = await runPollingTask({
        start: () => client.refreshChoiceMacro(30),
        getStatus: (runId) => client.getChoiceMacroRefreshStatus(runId),
        intervalMs: 3000,
        maxAttempts: 120,
        signal,
        isTerminal: (status) => MARKET_REFRESH_TERMINAL_STATUSES.has(status),
        onUpdate: () => {
          setRefreshStatus("刷新任务处理中，正在读取最新市场数据…");
        },
      });
      if (!MARKET_REFRESH_ACCEPTED_STATUSES.has(payload.status)) {
        throw new Error(payload.error_message ?? `刷新未完成：${payload.status}`);
      }

      if (signal?.aborted) return;
      const reads = [
        { label: "市场快照", read: () => refetchAfterMarketRefresh(queries.marketSnapshot) },
        { label: "最新行情", read: () => refetchLoadedMarketQuery(queries.choiceLatest) },
        { label: "正式利率", read: () => refetchLoadedMarketQuery(queries.marketRates) },
        { label: "数据目录", read: () => refetchLoadedMarketQuery(queries.marketCatalog) },
        { label: "宏观分析", read: () => refetchLoadedMarketQuery(queries.macroToolkitAnalysis) },
        { label: "策略摘要", read: () => refetchLoadedMarketQuery(queries.macroToolkitStrategySummaries) },
        { label: "新闻图表", read: () => refetchLoadedMarketQuery(queries.newsEvents) },
        {
          label: "新闻明细",
          read: () => queryClient.invalidateQueries(
            { queryKey: ["module-home", "market-backend-data", "news"], refetchType: "active" },
            { throwOnError: true },
          ),
        },
      ];
      const results = await Promise.allSettled(reads.map(({ read }) => read()));
      if (signal?.aborted) return;
      const failedReads = reads.filter((_, index) => results[index].status === "rejected");
      if (failedReads.length > 0) {
        setRefreshError(`刷新任务已完成，但${failedReads.map(({ label }) => label).join("、")}重新读取失败；失败区块保留此前可用数据，请重试。`);
        setRefreshStatus("");
        return;
      }
      if (payload.status === "partial") {
        setRefreshStatus(
          "Choice 刷新失败，已使用 Tushare/公开备份源刷新并重新读取市场首页数据；部分序列来自备份口径，请注意核对。",
        );
      } else if (payload.status === "degraded") {
        setRefreshStatus(formatDegradedRefreshStatus(payload));
      } else {
        setRefreshStatus("刷新完成，已重新读取市场首页数据。");
      }
    } catch (err) {
      if (signal?.aborted) return;
      setRefreshError(appendFailedDataNotice(formatChoiceMacroRefreshError(err)));
      setRefreshStatus("");
    } finally {
      if (!signal?.aborted) {
        setIsRefreshing(false);
      }
    }
  }, [client, queries, queryClient]);

  const snapshotDates = queries.marketSnapshot?.data?.result.dates;
  const snapshotChoiceDate = snapshotDates?.surfaces.find(
    (surface) => surface.key === "choice_latest",
  )?.latest;
  const snapshotFormalDate = snapshotDates?.surfaces.find(
    (surface) => surface.key === "rates_formal",
  )?.latest;
  const formalTradeDate = snapshotFormalDate ?? "";
  const tapeSpan = snapshotDates?.tape_span;
  const tapeDateRange =
    tapeSpan?.earliest && tapeSpan.latest
      ? `${tapeSpan.earliest}–${tapeSpan.latest}`
      : tapeSpan?.latest ?? tapeSpan?.earliest ?? snapshotChoiceDate ?? "";

  return (
    // 深色 owner 由 ThemedRouteBoundary 独占；页根只声明 Nocturne scope + theme-dh-api。
    <section
      data-testid="module-workbench-home"
      data-moss-theme-scope="market-overview"
      className="theme-dh-api"
    >
      <MarketHomeLayout
        view={view}
        config={config}
        tapeDateRange={tapeDateRange}
        formalTradeDate={formalTradeDate}
        isRefreshing={isRefreshing}
        refreshStatus={refreshStatus}
        refreshError={refreshError}
        queries={queries}
        onBackendActiveKeyChange={setBackendActiveKey}
        onChartsVisible={handleChartsVisible}
        onChartSectionsChange={setChartSectionKeys}
        onRefreshData={handleRefreshData}
      />
    </section>
  );
}
