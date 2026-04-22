import type { Bond } from "../../data-structures/BondModel";
import { PriceChangeIndicator } from "../common/PriceChangeIndicator";
import { RatingBadge } from "../common/RatingBadge";

export interface BondTableRowProps {
  bond: Bond;
  selected?: boolean;
  onSelect?: (bond: Bond) => void;
}

export function BondTableRow({ bond, selected = false, onSelect }: BondTableRowProps) {
  return (
    <tr style={{ background: selected ? "#eef4ff" : "transparent" }}>
      <td style={{ padding: "12px 10px" }}>
        <button type="button" onClick={() => onSelect?.(bond)}>
          查看 {bond.shortName}
        </button>
      </td>
      <td style={{ padding: "12px 10px" }}>{bond.bondCode}</td>
      <td style={{ padding: "12px 10px" }}>{bond.issuerName}</td>
      <td style={{ padding: "12px 10px" }}>{bond.marketData.cleanPrice.toFixed(2)}</td>
      <td style={{ padding: "12px 10px" }}>{bond.marketData.yieldToMaturity.toFixed(2)}%</td>
      <td style={{ padding: "12px 10px" }}>
        <PriceChangeIndicator
          direction={bond.marketData.yieldChangeBp > 0 ? "up" : bond.marketData.yieldChangeBp < 0 ? "down" : "flat"}
          value={`${bond.marketData.yieldChangeBp > 0 ? "+" : ""}${bond.marketData.yieldChangeBp}bp`}
        />
      </td>
      <td style={{ padding: "12px 10px" }}>
        <RatingBadge rating={bond.riskMetrics.rating} />
      </td>
    </tr>
  );
}
