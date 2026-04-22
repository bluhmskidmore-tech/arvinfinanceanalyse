import type { Bond } from "../../data-structures/BondModel";
import { EmptyState } from "../common/EmptyState";
import { RatingBadge } from "../common/RatingBadge";

export interface BondDetailModalProps {
  bond?: Bond | null;
  open: boolean;
  onClose: () => void;
}

export function BondDetailModal({ bond, open, onClose }: BondDetailModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(7, 18, 34, 0.48)",
        display: "grid",
        placeItems: "center",
        padding: 24,
      }}
    >
      <div style={{ width: "min(960px, 100%)", borderRadius: 24, background: "#fff", padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ margin: 0 }}>{bond?.shortName ?? "债券详情"}</h2>
            {bond ? <p style={{ color: "#475467" }}>{bond.issuerName}</p> : null}
          </div>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </div>

        {!bond ? (
          <EmptyState title="未选择债券" description="请从表格或 watchlist 中选择一只债券。" />
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <RatingBadge rating={bond.riskMetrics.rating} />
              <span>代码 {bond.bondCode}</span>
              <span>到期 {bond.maturityDate}</span>
            </div>
            <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
              <div>价格 {bond.marketData.cleanPrice.toFixed(2)}</div>
              <div>收益率 {bond.marketData.yieldToMaturity.toFixed(2)}%</div>
              <div>久期 {bond.riskMetrics.modifiedDuration.toFixed(2)}</div>
              <div>信用利差 {bond.riskMetrics.creditSpreadBp ?? "--"}bp</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
