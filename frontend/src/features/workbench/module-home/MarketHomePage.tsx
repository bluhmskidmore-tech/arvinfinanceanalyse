import { useCallback, useState } from "react";

import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { buildModuleHomeView, type ModuleHomeDetailPanel } from "./moduleHomeModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import MarketHomeLayout from "./MarketHomeLayout";
import { useMarketHomeQueries } from "./useMarketHomeQueries";
import dhStyles from "../dashboard-home/dashboardHome.module.css";

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

const CHOICE_MACRO_REFRESH_RESOURCE = "macro_vendor.choice_series";
const CHOICE_MACRO_REFRESH_PERMISSION = `${CHOICE_MACRO_REFRESH_RESOURCE}:refresh`;
const MARKET_REFRESH_TERMINAL_STATUSES = new Set(["completed", "partial", "failed"]);
const MARKET_REFRESH_ACCEPTED_STATUSES = new Set(["completed", "partial"]);

type RefreshableMarketHomeQuery = {
  fetchStatus?: "fetching" | "paused" | "idle";
  refetch: () => Promise<unknown>;
};

function formatChoiceMacroRefreshError(error: unknown) {
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (/not allowed/i.test(message) && message.includes(CHOICE_MACRO_REFRESH_RESOURCE)) {
    return `当前账号没有刷新 Choice 宏观数据权限，请先授予 ${CHOICE_MACRO_REFRESH_PERMISSION}；已保留当前已落库数据。`;
  }
  return message || "刷新市场数据失败";
}

export async function refetchAfterMarketRefresh(query: RefreshableMarketHomeQuery | undefined) {
  if (!query) return;
  await query.refetch();
}

export default function MarketHomePage() {
  const client = useApiClient();
  const queries = useMarketHomeQueries();
  const config = moduleWorkbenchHomeConfigs.market;
  const view = buildModuleHomeView("market", client, queries);
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
        onUpdate: (p) => {
          setRefreshStatus([p.status, p.run_id].filter(Boolean).join(" · "));
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
      setRefreshStatus(
        payload.status === "partial"
          ? "Choice refresh failed; Tushare/public backup refreshed, and market home data was reloaded."
          : "刷新完成，已重新读取市场首页数据。",
      );
    } catch (err) {
      setRefreshError(formatChoiceMacroRefreshError(err));
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
    <section data-testid="module-workbench-home" className={dhStyles.dhPage}>
      <MarketHomeLayout
        view={view}
        config={config}
        latestTradeDate={latestTradeDate}
        formalTradeDate={formalTradeDate}
        isRefreshing={isRefreshing}
        refreshStatus={refreshStatus}
        refreshError={refreshError}
        onRefreshData={handleRefreshData}
      />
    </section>
  );
}
