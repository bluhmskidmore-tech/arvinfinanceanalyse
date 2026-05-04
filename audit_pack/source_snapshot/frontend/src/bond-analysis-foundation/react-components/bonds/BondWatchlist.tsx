import type { Bond } from "../../data-structures/BondModel";
import { EmptyState } from "../common/EmptyState";
import { PriceChangeIndicator } from "../common/PriceChangeIndicator";
import { RatingBadge } from "../common/RatingBadge";

export interface BondWatchlistProps {
  bonds: Bond[];
  onSelectBond?: (bond: Bond) => void;
  onRemoveBond?: (bond: Bond) => void;
}

export function BondWatchlist({
  bonds,
  onSelectBond,
  onRemoveBond,
}: BondWatchlistProps) {
  if (bonds.length === 0) {
    return <EmptyState title="监控列表为空" description="先从债券表格中添加重点观察标的。" />;
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h3 style={{ margin: 0 }}>关注列表</h3>
      {bonds.map((bond) => (
        <div
          key={bond.bondId}
          style={{
            borderRadius: 18,
            border: "1px solid #d0d5dd",
            background: "#fff",
            padding: 16,
            display: "grid",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div>
              <strong>{bond.shortName}</strong>
              <div style={{ color: "#475467" }}>{bond.issuerName}</div>
            </div>
            <RatingBadge rating={bond.riskMetrics.rating} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span>{bond.marketData.yieldToMaturity.toFixed(2)}%</span>
            <PriceChangeIndicator
              direction={bond.marketData.yieldChangeBp > 0 ? "up" : bond.marketData.yieldChangeBp < 0 ? "down" : "flat"}
              value={`${bond.marketData.yieldChangeBp > 0 ? "+" : ""}${bond.marketData.yieldChangeBp}bp`}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={() => onSelectBond?.(bond)}>
              查看
            </button>
            <button type="button" onClick={() => onRemoveBond?.(bond)}>
              移除
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
