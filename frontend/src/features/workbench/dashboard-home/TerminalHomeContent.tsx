import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import styles from "./dashboardHome.module.css";

type TerminalHomeContentProps = {
  view: DashboardHomeBodyView;
  showFirstScreen?: boolean;
};

const TerminalHomeWorkGrid = lazy(() =>
  import("./TerminalHomeWorkGrid").then((module) => ({
    default: module.TerminalHomeWorkGrid,
  })),
);

const TerminalHomeDeferredSections = lazy(() =>
  import("./TerminalHomeDeferredSections").then((module) => ({
    default: module.TerminalHomeDeferredSections,
  })),
);

function buildReportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== "—" ? `${path}?report_date=${encodeURIComponent(trimmed)}` : path;
}

function MarketContextPanel({ view }: { view: DashboardHomeBodyView }) {
  const context = view.marketContext;
  return (
    <article
      data-testid="dashboard-home-market-context"
      className={`${styles.dhCard} ${styles.dhMarketContext}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>今日市场解释</h3>
        <div className={styles.dhPanelHeaderActions}>
          <Link
            to={buildReportDatePath("/bond-analysis", view.reportDate)}
            className={styles.dhPanelDrillLink}
          >
            曲线/利差 →
          </Link>
          <span className={styles.dhMarketContextTemp} data-tone={context.temperatureTone}>
            {context.temperatureLabel}
          </span>
        </div>
      </div>
      <div className={styles.dhMacroTrustStrip} aria-label="今日市场解释数据状态">
        <span>{context.sourceLabel}</span>
        <span>{context.asOfLabel}</span>
        <span>{context.statusLabel}</span>
        <span>{context.refreshLabel}</span>
      </div>
      <div className={styles.dhMarketContextGrid}>
        {context.contextBlocks.map((block) => (
          <div key={block.id} className={styles.dhMarketContextBlock}>
            <span>{block.label}</span>
            <b>{block.title}</b>
            <small>{block.detail}</small>
            <small>{block.foot}</small>
          </div>
        ))}
      </div>
      <ul className={styles.dhMarketContextSummary}>
        {context.aiSummary.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

export function TerminalHomeContent({ view, showFirstScreen = true }: TerminalHomeContentProps) {
  void showFirstScreen;
  return (
    <>
      <MarketContextPanel view={view} />

      <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
        <TerminalHomeWorkGrid view={view} />
      </Suspense>

      <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
        <TerminalHomeDeferredSections view={view} />
      </Suspense>
    </>
  );
}
