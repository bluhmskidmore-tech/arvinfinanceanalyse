import type { Portfolio, PortfolioHolding } from "../../data-structures/PortfolioModel";
import { EmptyState } from "../common/EmptyState";
import { RatingBadge } from "../common/RatingBadge";

export interface PortfolioOverviewProps {
  portfolio?: Portfolio;
  onSelectHolding?: (holding: PortfolioHolding) => void;
}

function formatCurrency(value?: number) {
  return value === undefined
    ? "--"
    : new Intl.NumberFormat("zh-CN", {
        maximumFractionDigits: 0,
      }).format(value);
}

export function PortfolioOverview({ portfolio, onSelectHolding }: PortfolioOverviewProps) {
  if (!portfolio) {
    return <EmptyState title="暂无组合数据" description="可以先选择默认组合或从关注列表创建组合。" />;
  }

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h2 style={{ margin: 0 }}>{portfolio.portfolioName}</h2>
          <p style={{ margin: "6px 0 0", color: "#475467" }}>{portfolio.benchmark}</p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ color: "#475467", fontSize: 12 }}>总市值</div>
          <strong style={{ fontSize: 28 }}>{formatCurrency(portfolio.totalMarketValue)}</strong>
        </div>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {portfolio.holdings.map((holding) => (
          <button
            key={holding.positionId}
            type="button"
            onClick={() => onSelectHolding?.(holding)}
            style={{
              display: "grid",
              gridTemplateColumns: "1.3fr 0.7fr 0.7fr 0.7fr",
              gap: 12,
              textAlign: "left",
              borderRadius: 16,
              border: "1px solid #d0d5dd",
              background: "#fff",
              padding: 16,
            }}
          >
            <div>
              <strong>{holding.bond.shortName}</strong>
              <div style={{ color: "#475467", marginTop: 6 }}>{holding.bond.issuerName}</div>
              <div style={{ marginTop: 8 }}>
                <RatingBadge rating={holding.bond.riskMetrics.rating} />
              </div>
            </div>
            <div>
              <div style={{ color: "#475467", fontSize: 12 }}>权重</div>
              <div>{(holding.weight * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div style={{ color: "#475467", fontSize: 12 }}>持仓成本</div>
              <div>{holding.holdingCost.toFixed(2)}</div>
            </div>
            <div>
              <div style={{ color: "#475467", fontSize: 12 }}>当前市值</div>
              <div>{formatCurrency(holding.marketValue)}</div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
