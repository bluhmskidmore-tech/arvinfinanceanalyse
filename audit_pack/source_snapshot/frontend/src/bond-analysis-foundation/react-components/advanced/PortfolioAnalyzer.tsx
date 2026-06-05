import type { Portfolio } from "../../data-structures/PortfolioModel";
import { PortfolioAllocationChart, type AllocationDatum } from "../charts/PortfolioAllocationChart";
import { PortfolioStats } from "../dashboard/PortfolioStats";

export interface PortfolioAnalyzerProps {
  portfolio?: Portfolio;
  summaryLines?: string[];
  allocations?: AllocationDatum[];
}

export function PortfolioAnalyzer({
  portfolio,
  summaryLines = [],
  allocations = [],
}: PortfolioAnalyzerProps) {
  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ margin: 0 }}>组合分析工具</h2>
        <p style={{ margin: "6px 0 0", color: "#475467" }}>
          {portfolio ? `正在分析 ${portfolio.portfolioName}` : "先选择一个投资组合。"}
        </p>
      </div>
      <PortfolioStats statistics={portfolio?.statistics} />
      <PortfolioAllocationChart allocations={allocations} />
      {summaryLines.length ? (
        <div style={{ borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff", padding: 16 }}>
          <strong>分析结论</strong>
          <ul style={{ marginBottom: 0 }}>
            {summaryLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
