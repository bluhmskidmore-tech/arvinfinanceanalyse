export const BOND_ALIGNMENT_THRESHOLDS = {
  /** Amount fields (yuan, yi, dv01) allow <=0.5% relative deviation. */
  amountRelativeRatio: 0.005,
  /** Yield/spread fields allow <=1bp absolute deviation. */
  yieldOrSpreadBp: 1,
  /** Ratio fields allow <=0.1 percentage-point absolute deviation. */
  ratioPctPoint: 0.1,
} as const;

export type BondAlignmentMetricKind = "amount" | "yieldOrSpread" | "ratio";
