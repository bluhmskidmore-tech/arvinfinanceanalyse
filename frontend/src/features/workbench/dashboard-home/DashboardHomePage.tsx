import styles from "./dashboardHome.module.css";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeContent } from "./TerminalHomeContent";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

export default function DashboardHomePage() {
  const {
    view,
    reportDate,
    setReportDate,
    toolbarSearch,
    setToolbarSearch,
    allowPartial,
    setAllowPartial,
    refreshSnapshot,
    snapshotQuery,
    effectiveReportDate,
  } = useDashboardHomeViewModel();

  return (
    <section data-testid="dashboard-home-page" className={styles.dhPage}>
      <DashboardHomeToolbar
        title="经营驾驶舱"
        headerStatus={view.headerStatus}
        reportDateInput={reportDate || effectiveReportDate}
        onReportDateChange={setReportDate}
        toolbarSearch={toolbarSearch}
        onSearchChange={setToolbarSearch}
        allowPartial={allowPartial}
        onAllowPartialChange={setAllowPartial}
        onRefresh={() => void refreshSnapshot()}
        refreshLabel={snapshotQuery.isFetching ? "刷新中…" : "刷新"}
      />

      <div className={styles.dhLayout}>
        <main className={styles.dhMain}>
          <TerminalHomeContent view={view} />
        </main>

        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.decisionRail.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
        />
      </div>
    </section>
  );
}
