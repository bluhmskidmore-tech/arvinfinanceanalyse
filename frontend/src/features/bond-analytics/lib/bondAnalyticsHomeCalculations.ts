import type { BondDashboardHeadlinePayload, Numeric } from "../../../api/contracts";
import { BOND_ALIGNMENT_THRESHOLDS, type BondAlignmentMetricKind } from "./alignmentThresholds";

export type BondHomeKpiKey =
  | "total_market_value"
  | "unrealized_pnl"
  | "weighted_ytm"
  | "weighted_duration"
  | "weighted_coupon"
  | "credit_spread_median"
  | "total_dv01";

export interface BondKpiValuePair {
  current: number | null;
  previous: number | null;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

export function toRawNumber(value: Numeric | null | undefined): number | null {
  if (!value || value.raw === null || !Number.isFinite(value.raw)) {
    return null;
  }
  return value.raw;
}

export function toBp(value: Numeric | null | undefined): number | null {
  const raw = toRawNumber(value);
  if (raw === null) {
    return null;
  }
  if (value?.unit === "bp") {
    return raw;
  }
  return raw * 10000;
}

export function buildKpiValuePair(
  payload: BondDashboardHeadlinePayload | null | undefined,
  key: BondHomeKpiKey,
): BondKpiValuePair {
  return {
    current: toRawNumber(payload?.kpis?.[key] ?? null),
    previous: toRawNumber(payload?.prev_kpis?.[key] ?? null),
  };
}

export function computeRelativeChangePct(
  current: number | null | undefined,
  previous: number | null | undefined,
): number | null {
  if (!isFiniteNumber(current) || !isFiniteNumber(previous) || previous === 0) {
    return null;
  }
  return ((current - previous) / Math.abs(previous)) * 100;
}

export function computeBpDelta(
  current: Numeric | null | undefined,
  previous: Numeric | null | undefined,
): number | null {
  const currentBp = toBp(current);
  const previousBp = toBp(previous);
  if (!isFiniteNumber(currentBp) || !isFiniteNumber(previousBp)) {
    return null;
  }
  return currentBp - previousBp;
}

export interface BondAlignmentCheckResult {
  withinThreshold: boolean;
  actualDeviation: number | null;
  threshold: number;
}

export function checkBondAlignment(args: {
  kind: BondAlignmentMetricKind;
  baseline: number | null | undefined;
  candidate: number | null | undefined;
}): BondAlignmentCheckResult {
  const { kind, baseline, candidate } = args;
  const threshold =
    kind === "amount"
      ? BOND_ALIGNMENT_THRESHOLDS.amountRelativeRatio
      : kind === "yieldOrSpread"
        ? BOND_ALIGNMENT_THRESHOLDS.yieldOrSpreadBp
        : BOND_ALIGNMENT_THRESHOLDS.ratioPctPoint;

  if (!isFiniteNumber(baseline) || !isFiniteNumber(candidate)) {
    return { withinThreshold: false, actualDeviation: null, threshold };
  }

  if (kind === "amount") {
    if (baseline === 0) {
      return {
        withinThreshold: candidate === 0,
        actualDeviation: candidate === 0 ? 0 : Number.POSITIVE_INFINITY,
        threshold,
      };
    }
    const deviation = Math.abs((candidate - baseline) / baseline);
    return { withinThreshold: deviation <= threshold, actualDeviation: deviation, threshold };
  }

  const deviation = Math.abs(candidate - baseline);
  return { withinThreshold: deviation <= threshold, actualDeviation: deviation, threshold };
}
