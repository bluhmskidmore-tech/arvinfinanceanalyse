import type { DataFreshness } from "../../data-structures/BondModel";
import type { Bond } from "../../data-structures/BondModel";
import type { Portfolio } from "../../data-structures/PortfolioModel";
import { BondWatchlist } from "../bonds/BondWatchlist";
import { EmptyState } from "../common/EmptyState";
import { Loading } from "../common/Loading";
import { MetricCard, type MetricCardProps } from "./MetricCard";
import { PortfolioOverview } from "./PortfolioOverview";
import { PortfolioStats } from "./PortfolioStats";

export interface DashboardStatus {
  freshness: DataFreshness;
  asOfDate: string;
  isStale: boolean;
  fallbackDate?: string;
}

export interface DashboardProps {
  title: string;
  primaryConclusion: string;
  marketSummary: string;
  status?: DashboardStatus;
  metrics: MetricCardProps[];
  portfolio?: Portfolio;
  watchlist?: Bond[];
  loading?: boolean;
  error?: string | null;
  onSelectBond?: (bond: Bond) => void;
}

function statusMessage(status?: DashboardStatus) {
  if (!status) {
    return null;
  }

  if (status.isStale && status.fallbackDate) {
    return `数据为 ${status.asOfDate} 快照，已显式回退日期 ${status.fallbackDate}。`;
  }

  if (status.isStale) {
    return `数据截至 ${status.asOfDate}，当前状态为滞后。`;
  }

  return `数据截至 ${status.asOfDate}，新鲜度 ${status.freshness}。`;
}

export function Dashboard({
  title,
  primaryConclusion,
  marketSummary,
  status,
  metrics,
  portfolio,
  watchlist = [],
  loading = false,
  error,
  onSelectBond,
}: DashboardProps) {
  if (loading) {
    return <Loading />;
  }

  if (error) {
    return <EmptyState title="仪表板加载失败" description={error} />;
  }

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <section
        style={{
          borderRadius: 24,
          padding: 24,
          background: "linear-gradient(135deg, rgba(8, 15, 33, 0.96), rgba(15, 44, 86, 0.88))",
          color: "#f8fafc",
        }}
      >
        <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", opacity: 0.72 }}>
          首屏结论
        </div>
        <h1 style={{ margin: "10px 0 12px" }}>{title}</h1>
        <p style={{ fontSize: 28, margin: 0, maxWidth: 960 }}>{primaryConclusion}</p>
        <p style={{ marginBottom: 0, opacity: 0.84 }}>{marketSummary}</p>
        {status ? <p style={{ marginTop: 12, opacity: 0.84 }}>{statusMessage(status)}</p> : null}
      </section>

      <section style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section style={{ display: "grid", gap: 24, gridTemplateColumns: "1.4fr 1fr" }}>
        <PortfolioOverview portfolio={portfolio} />
        <BondWatchlist bonds={watchlist} onSelectBond={onSelectBond} />
      </section>

      {portfolio ? <PortfolioStats statistics={portfolio.statistics} /> : null}
    </div>
  );
}
