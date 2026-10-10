import { useMemo } from "react";

import { useApiClient } from "../../../api/client";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { buildModuleHomeView } from "./moduleHomeModel";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import PortfolioHomeLayout from "./PortfolioHomeLayout";
import { usePortfolioHomeQueries } from "./usePortfolioHomeQueries";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import styles from "./portfolioHome.module.css";

export default function PortfolioHomePage() {
  const client = useApiClient();
  const { queries, balanceReportDate, balancePublicationStatusQuery, balanceOverviewServingMode } = usePortfolioHomeQueries();
  const config = moduleWorkbenchHomeConfigs.portfolio;
  const view = useMemo(
    () => buildModuleHomeView("portfolio", client, queries),
    [client, queries],
  );
  const bondReportDate = queries.bondDates?.data?.result.report_dates[0] ?? "";

  return (
    <section
      data-testid="module-workbench-home"
      data-moss-theme-scope="portfolio-home"
      className={`theme-dh-api ${dhStyles.dhLightPage} ${styles.portfolioPage}`}
    >
      {balancePublicationStatusQuery.isError ? (
        <PageStateSurface
          variant="error"
          title="资产负债发布状态读取失败"
          description="当前无法确认发布快照，已暂停展示资产负债总览与口径分解。"
          testId="portfolio-balance-publication-state"
        />
      ) : balanceOverviewServingMode === "pending" ? (
        <PageStateSurface
          variant="loading"
          title="正在确认资产负债发布快照"
          testId="portfolio-balance-publication-state"
        />
      ) : balanceOverviewServingMode === "blocked" ? (
        <PageStateSurface
          variant="stale"
          title="资产负债发布快照尚未就绪"
          description="当前报告日没有可用的发布快照，资产负债总览与口径分解暂不展示。"
          testId="portfolio-balance-publication-state"
        />
      ) : balanceOverviewServingMode === "published" ? (
        queries.balanceOverview?.isError || queries.balanceBasis?.isError ? (
          <PageStateSurface
            variant="error"
            title="资产负债发布快照读取失败"
            description="总览或口径分解未通过当前快照读取与版本校验，两者已暂停展示。"
            testId="portfolio-balance-publication-state"
          />
        ) : queries.balanceOverview?.data && queries.balanceBasis?.data ? (
          <PageStateSurface
            variant="neutral"
            description={`资产负债总览与口径分解均来自 ${balanceReportDate} 的同一已发布快照。`}
            testId="portfolio-balance-publication-state"
          />
        ) : (
          <PageStateSurface
            variant="loading"
            title="正在读取资产负债发布快照"
            description="等待总览与口径分解的同版本数据。"
            testId="portfolio-balance-publication-state"
          />
        )
      ) : null}
      {balanceOverviewServingMode === "published" && queries.balanceDates?.isError ? (
        <PageStateSurface
          variant="definition-pending"
          title="实时日期列表读取失败"
          description={`总览日期来自已发布快照（${balanceReportDate}），未使用实时日期列表。`}
          testId="portfolio-balance-live-dates-state"
        />
      ) : null}
      <PortfolioHomeLayout
        view={view}
        config={config}
        balanceReportDate={balanceReportDate}
        bondReportDate={bondReportDate}
      />
    </section>
  );
}
