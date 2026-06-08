import { Link } from "react-router-dom";

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
  ready: "已回传",
  partial: "部分",
  empty: "空",
  loading: "读取",
  error: "失败",
  stale: "沿用",
  "backend-gap": "待接",
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
    <div className={styles.dhRiskEmptyRow}>
      <span>关键风险</span>
      <b>主快照未返回风险条目</b>
      <small>入口保留</small>
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
      <div className={styles.dhReportHead}>
        <div>
          <span className={styles.dhReportKicker}>主快照</span>
          <h2>经营读数</h2>
        </div>
        <dl className={styles.dhReportMeta}>
          <div>
            <dt>报告日</dt>
            <dd className={styles.dhNum}>{view.reportDate}</dd>
          </div>
          <div>
            <dt>条目</dt>
            <dd className={styles.dhNum}>{view.terminalKpis.length}</dd>
          </div>
        </dl>
      </div>

      <div className={styles.dhMetricTableWrap}>
        <table className={styles.dhMetricTable}>
          <thead>
            <tr>
              <th>序</th>
              <th>指标</th>
              <th>当前值</th>
              <th>较前日</th>
              <th>状态</th>
              <th>近日报告</th>
            </tr>
          </thead>
          <tbody>
            {view.terminalKpis.map((kpi, index) => (
              <tr key={kpi.id} data-testid={`dashboard-home-kpi-${kpi.id}`}>
                <td data-label="序" className={`${styles.dhMetricSeq} ${styles.dhNum}`}>
                  {String(index + 1).padStart(2, "0")}
                </td>
                <td data-label="指标" className={styles.dhMetricName}>
                  {kpi.label}
                </td>
                <td data-label="当前值" className={`${styles.dhMetricValueCell} ${styles.dhNum}`}>
                  <span>{kpi.value}</span>
                  {kpi.unit ? <small>{kpi.unit}</small> : null}
                </td>
                <td
                  data-label="较前日"
                  className={`${styles.dhMetricDeltaCell} ${resolveDeltaClass(kpi.deltaTone, styles)}`}
                >
                  {kpi.delta}
                </td>
                <td data-label="状态">
                  <DataStateBadge kind={kpi.state} />
                </td>
                <td data-label="近日报告" className={styles.dhMetricSparkCell}>
                  <HomeSparkline
                    values={kpi.sparkline}
                    stroke={sparkStroke(kpi.deltaTone)}
                    className={styles.dhMetricTableSpark}
                    area
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RiskStrip({ items }: { items: DashboardHomeFirstScreenView["keyRiskStrip"] }) {
  const hasItems = items.length > 0;
  return (
    <section data-testid="dashboard-home-market" className={styles.dhTerminalRiskStrip}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>风险核验</h3>
        <Link to="/risk-overview" className={styles.dhLink}>
          风险工作台
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
