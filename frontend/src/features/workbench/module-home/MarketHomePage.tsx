import { useCallback, useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroRefreshPayload } from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import {
  buildModuleHomeView,
  type ModuleHomeDetailPanel,
} from "./moduleHomeModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import MarketHomeLayout from "./MarketHomeLayout";
import { useMarketHomeQueries } from "./useMarketHomeQueries";
import { refetchAfterMarketRefresh } from "./marketHomeRefresh";

function latestTradeDateFromSeries(series: Array<{ trade_date?: string | null }>) {
  return series
    .map((point) => point.trade_date)
    .filter((date): date is string => Boolean(date))
    .sort((left, right) => right.localeCompare(left))[0];
}

function latestTradeDateFromPanel(panel: ModuleHomeDetailPanel | undefined) {
  return panel?.rows
    .map((row) => row.tradeDate)
    .filter((date) => /^\d{4}-\d{2}-\d{2}$/.test(date))
    .sort()
    .at(-1);
}

function panelByKey(panels: ModuleHomeDetailPanel[] | undefined, key: string) {
  return panels?.find((panel) => panel.key === key);
}

const MARKET_REFRESH_TERMINAL_STATUSES = new Set(["completed", "partial", "degraded", "failed"]);
const MARKET_REFRESH_ACCEPTED_STATUSES = new Set(["completed", "partial", "degraded"]);
const MARKET_REFRESH_FAILED_DATA_NOTICE = "当前展示的仍是上次成功刷新的数据。";

function formatChoiceMacroRefreshError(error: unknown) {
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (/not allowed|permission|forbidden|denied|无权限|权限不足/i.test(message)) {
    return "当前账号没有刷新 Choice 宏观数据的权限。";
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
  const queries = useMarketHomeQueries();
  const config = moduleWorkbenchHomeConfigs.market;
  const view = useMemo(
    () => buildModuleHomeView("market", client, queries),
    [client, queries],
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState("");
  const [refreshError, setRefreshError] = useState("");

  const handleRefreshData = useCallback(async () => {
    setIsRefreshing(true);
    setRefreshError("");
    setRefreshStatus("正在刷新宏观数据（回填 30 天）…");
    try {
      const payload = await runPollingTask({
        start: () => client.refreshChoiceMacro(30),
        getStatus: (runId) => client.getChoiceMacroRefreshStatus(runId),
        intervalMs: 3000,
        maxAttempts: 120,
        isTerminal: (status) => MARKET_REFRESH_TERMINAL_STATUSES.has(status),
        onUpdate: () => {
          setRefreshStatus("刷新任务处理中，正在读取最新市场数据…");
        },
      });
      if (!MARKET_REFRESH_ACCEPTED_STATUSES.has(payload.status)) {
        throw new Error(payload.error_message ?? `刷新未完成：${payload.status}`);
      }

      await Promise.all([
        refetchAfterMarketRefresh(queries.choiceLatest),
        refetchAfterMarketRefresh(queries.marketRates),
        refetchAfterMarketRefresh(queries.marketCatalog),
        refetchAfterMarketRefresh(queries.macroToolkitAnalysis),
        refetchAfterMarketRefresh(queries.macroToolkitStrategySummaries),
        refetchAfterMarketRefresh(queries.newsEvents),
      ]);
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
      setRefreshError(appendFailedDataNotice(formatChoiceMacroRefreshError(err)));
      setRefreshStatus("");
    } finally {
      setIsRefreshing(false);
    }
  }, [client, queries]);

  const latestSeries = queries.choiceLatest?.data?.result.series ?? [];
  const rateSeries = queries.marketRates?.data?.result.series ?? [];
  const macroSnapshotPanel = panelByKey(view.detailPanels, "latest-macro-snapshot");
  const keyRatePanel = panelByKey(view.detailPanels, "key-rate-snapshot");
  const formalRatePanel = panelByKey(view.detailPanels, "formal-rate-series");
  const yieldCurvePanel = panelByKey(view.detailPanels, "yield-curve-quotes");
  const latestTradeDate =
    latestTradeDateFromPanel(macroSnapshotPanel) ??
    latestTradeDateFromSeries(latestSeries) ??
    latestTradeDateFromPanel(keyRatePanel) ??
    "";
  const formalTradeDate =
    latestTradeDateFromPanel(formalRatePanel) ??
    latestTradeDateFromPanel(yieldCurvePanel) ??
    latestTradeDateFromSeries(rateSeries) ??
    latestTradeDate;

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
        latestTradeDate={latestTradeDate}
        formalTradeDate={formalTradeDate}
        isRefreshing={isRefreshing}
        refreshStatus={refreshStatus}
        refreshError={refreshError}
        queries={queries}
        onRefreshData={handleRefreshData}
      />
    </section>
  );
}
