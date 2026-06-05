import { Link } from "react-router-dom";

import { LightIcon } from "../../../components/LightIcon";
import {
  resolveDeltaClass,
  type DashboardHomeFirstScreenView,
  type HomeDataStateKind,
} from "./dashboardHomeFirstScreenTypes";
import { HomeSparkline } from "./HomeSparkline";
import styles from "./dashboardHomeShell.module.css";

type TerminalHomeFirstScreenProps = {
  view: DashboardHomeFirstScreenView;
};

const STATE_COPY: Record<HomeDataStateKind, string> = {
  ready: "已接入",
  partial: "部分接入",
  empty: "暂无数据",
  loading: "加载中",
  error: "加载失败",
  stale: "数据过期",
  "backend-gap": "后端待接入",
};

function stateClass(kind: HomeDataStateKind): string {
  if (kind === "ready") return styles.dhTerminalStateReady ?? "";
  if (kind === "partial") return styles.dhTerminalStateWarn ?? "";
  if (kind === "error" || kind === "backend-gap") return styles.dhTerminalStateWarn ?? "";
  if (kind === "stale") return styles.dhTerminalStateStale ?? "";
  return styles.dhTerminalStateMuted ?? "";
}

function DataStateBadge({ kind }: { kind: HomeDataStateKind }) {
  return (
    <span className={`${styles.dhTerminalState} ${stateClass(kind)}`}>
      {STATE_COPY[kind]}
    </span>
  );
}

function EmptyRiskSurface() {
  return (
    <div className={`${styles.dhTerminalStateSurface} ${styles.dhTerminalStateSurfaceCompact}`}>
      <span className={styles.dhTerminalStateIcon}>
        <LightIcon name="info-circle" />
      </span>
      <b>关键风险暂无数据</b>
      <small>当前口径没有可展示记录</small>
    </div>
  );
}

function sparkStroke(tone: DashboardHomeFirstScreenView["terminalKpis"][number]["deltaTone"]): string {
  if (tone === "up" || tone === "warn") return "#b94743";
  if (tone === "down") return "#1f7a55";
  return "#1850a1";
}

function TerminalKpiStrip({ view }: { view: DashboardHomeFirstScreenView }) {
  return (
    <section data-testid="dashboard-home-hero" className={styles.dhTerminalHero}>
      {view.terminalKpis.map((kpi) => (
        <article
          key={kpi.id}
          data-testid={`dashboard-home-kpi-${kpi.id}`}
          className={`${styles.dhCard} ${styles.dhTerminalKpi}`}
        >
          <div className={styles.dhTerminalKpiTop}>
            <span>{kpi.label}</span>
            {kpi.state === "ready" ? null : <DataStateBadge kind={kpi.state} />}
          </div>
          <div className={`${styles.dhTerminalKpiValue} ${styles.dhNum}`}>
            {kpi.value}
            {kpi.unit ? <small>{kpi.unit}</small> : null}
          </div>
          <div className={`${styles.dhTerminalKpiDelta} ${resolveDeltaClass(kpi.deltaTone, styles)}`}>
            {kpi.delta}
          </div>
          <HomeSparkline
            values={kpi.sparkline}
            stroke={sparkStroke(kpi.deltaTone)}
            className={styles.dhTerminalKpiSpark}
            area
          />
        </article>
      ))}
    </section>
  );
}

function RiskStrip({ items }: { items: DashboardHomeFirstScreenView["keyRiskStrip"] }) {
  const hasItems = items.length > 0;
  return (
    <section data-testid="dashboard-home-market" className={`${styles.dhCard} ${styles.dhTerminalRiskStrip}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>关键风险</h3>
        <Link to="/risk-overview" className={styles.dhLink}>
          更多市场数据 →
        </Link>
      </div>
      {hasItems ? (
        <div className={styles.dhTerminalRiskGrid}>
          {items.map((item) => (
            <div key={item.id} className={styles.dhTerminalRiskCell}>
              <span>{item.label}</span>
              <b className={styles.dhNum}>{item.value}</b>
              <em className={resolveDeltaClass(item.deltaTone, styles)}>{item.delta}</em>
            </div>
          ))}
        </div>
      ) : (
        <EmptyRiskSurface />
      )}
    </section>
  );
}

export function TerminalHomeFirstScreen({ view }: TerminalHomeFirstScreenProps) {
  return (
    <>
      <TerminalKpiStrip view={view} />
      <RiskStrip items={view.keyRiskStrip} />
    </>
  );
}
