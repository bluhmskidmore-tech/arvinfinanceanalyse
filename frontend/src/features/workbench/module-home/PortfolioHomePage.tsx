import { useMemo } from "react";

import { useApiClient } from "../../../api/client";
import { buildModuleHomeView } from "./moduleHomeModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import PortfolioHomeLayout from "./PortfolioHomeLayout";
import { usePortfolioHomeQueries } from "./usePortfolioHomeQueries";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import styles from "./portfolioHome.module.css";

export default function PortfolioHomePage() {
  const client = useApiClient();
  const queries = usePortfolioHomeQueries();
  const config = moduleWorkbenchHomeConfigs.portfolio;
  const view = useMemo(
    () => buildModuleHomeView("portfolio", client, queries),
    [client, queries],
  );
  const balanceReportDate = queries.balanceDates?.data?.result.report_dates[0] ?? "";
  const bondReportDate = queries.bondDates?.data?.result.report_dates[0] ?? "";

  return (
    <section
      data-testid="module-workbench-home"
      data-moss-theme-scope="portfolio-home"
      className={`theme-dh-api ${dhStyles.dhLightPage} ${styles.portfolioPage}`}
    >
      <PortfolioHomeLayout
        view={view}
        config={config}
        balanceReportDate={balanceReportDate}
        bondReportDate={bondReportDate}
      />
    </section>
  );
}
