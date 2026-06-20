import { useApiClient } from "../../../api/client";
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

export default function MarketHomePage() {
  const client = useApiClient();
  const queries = useMarketHomeQueries();
  const config = moduleWorkbenchHomeConfigs.market;
  const view = buildModuleHomeView("market", client, queries);

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
      />
    </section>
  );
}
