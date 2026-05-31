import { Link } from "react-router-dom";
import {
  ApartmentOutlined,
  ArrowRightOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  DotChartOutlined,
  FileSearchOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  TableOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";

import type { DashboardHomeView } from "../dashboardHomeView";
import { resolveDeltaClass } from "../dashboardHomeView";
import styles from "../dashboardHome.module.css";

const QUICK_ICON_MAP: Record<string, ReactNode> = {
  positions: <TableOutlined />,
  attribution: <BarChartOutlined />,
  duration: <LineChartOutlined />,
  credit: <DotChartOutlined />,
  industry: <ApartmentOutlined />,
  trades: <FundProjectionScreenOutlined />,
  reports: <DatabaseOutlined />,
  cube: <FileSearchOutlined />,
};

type BottomGridSectionProps = {
  exposureRows: DashboardHomeView["exposureRows"];
  balanceMetrics: DashboardHomeView["balanceMetrics"];
  quickDrilldowns: DashboardHomeView["quickDrilldowns"];
};

export function BottomGridSection({
  exposureRows,
  balanceMetrics,
  quickDrilldowns,
}: BottomGridSectionProps) {
  return (
    <section data-testid="dashboard-home-bottom-grid" className={styles.dhBottomGrid}>
      <article className={`${styles.dhCard} ${styles.dhTableCard}`}>
        <div className={styles.dhSectionTitle}>
          <span>
            账户与暴露摘要
            <span className={styles.dhExposureSubtitle}>按组合 · 日收益待后端</span>
          </span>
          <Link to="/positions" className={styles.dhLink}>
            查看账户详情 →
          </Link>
        </div>
        <div className={styles.dhTableCardBody}>
          <table className={styles.dhTable}>
          <thead>
            <tr>
              <th>账户</th>
              <th>类型</th>
              <th>资产规模（亿）</th>
              <th>占比</th>
              <th>久期</th>
              <th>利率敏感度（万）</th>
              <th>日收益（万）</th>
            </tr>
          </thead>
          <tbody>
            {exposureRows.map((row) => (
              <tr
                key={row.id}
                className={row.account === "风险总计" ? styles.dhTotal : undefined}
              >
                <td>{row.account}</td>
                <td>{row.type}</td>
                <td className={styles.dhNum}>{row.assetScale}</td>
                <td>{row.weight}</td>
                <td>{row.duration}</td>
                <td className={styles.dhNum}>{row.dv01}</td>
                <td
                  className={
                    row.tone === "negative"
                      ? styles.dhUpRed
                      : row.tone === "positive"
                        ? styles.dhDownGreen
                        : styles.dhMuted
                  }
                >
                  {row.dailyPnl}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </article>

      <article className={`${styles.dhCard} ${styles.dhTableCard}`}>
        <div className={styles.dhSectionTitle}>
          <span>经营与资产负债摘要</span>
        </div>
        <div className={`${styles.dhMetricGrid} ${styles.dhTableCardBody}`}>
          {balanceMetrics.map((metric) => (
            <div
              key={metric.id}
              className={`${styles.dhMiniMetric}${metric.placeholder ? ` ${styles.dhDimmed}` : ""}`}
              title={metric.placeholder ? "专题接入中" : undefined}
            >
              <div className={styles.dhStatLabel}>
                {metric.label}
                {metric.placeholder ? (
                  <span className={styles.dhBadgePlaceholderInline}> · 接入中</span>
                ) : null}
              </div>
              <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{metric.value}</div>
              {metric.delta ? (
                <div
                  className={`${styles.dhStatLabel} ${metric.deltaTone ? resolveDeltaClass(metric.deltaTone, styles) : ""}`}
                >
                  {metric.delta}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </article>

      <article className={`${styles.dhCard} ${styles.dhTableCard}`}>
        <div className={styles.dhSectionTitle}>
          <span>快速钻取</span>
        </div>
        <div className={`${styles.dhQuickGrid} ${styles.dhTableCardBody}`}>
          {quickDrilldowns.map((item) => (
            <Link key={item.id} to={item.path} className={styles.dhQuick}>
              <span className={styles.dhQuickIcon}>
                {QUICK_ICON_MAP[item.icon] ?? <ArrowRightOutlined />}
              </span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </article>
    </section>
  );
}
