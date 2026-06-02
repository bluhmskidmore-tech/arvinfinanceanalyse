import { useApiClient } from "../../../api/client";
import { buildModuleHomeView } from "./moduleHomeModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import MarketHomeLayout from "./MarketHomeLayout";
import { useMarketHomeQueries } from "./useMarketHomeQueries";
import dhStyles from "../dashboard-home/dashboardHome.module.css";

export default function MarketHomePage() {
  const client = useApiClient();
  const queries = useMarketHomeQueries();
  const config = moduleWorkbenchHomeConfigs.market;
  const view = buildModuleHomeView("market", client, queries);

  const latestSeries = queries.choiceLatest?.data?.result.series ?? [];
  const rateSeries = queries.marketRates?.data?.result.series ?? [];
  const latestTradeDate =
    latestSeries[0]?.trade_date ??
    view.detailPanels?.find((panel) => panel.key === "key-rate-snapshot")?.rows[0]?.tradeDate ??
    "";
  const formalTradeDate = rateSeries[0]?.trade_date ?? latestTradeDate;

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
