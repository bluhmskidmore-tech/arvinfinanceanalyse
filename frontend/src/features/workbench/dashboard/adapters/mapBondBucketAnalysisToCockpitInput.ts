import type { PnlByBusinessAnalysisPayload, PnlByBusinessAnalysisRow } from "../../../../api/contracts";

/** Cockpit account-row yield inputs derived from bond_bucket analysis payload. */
export type BondBucketCockpitYieldInput = {
  bondBucketRows: readonly PnlByBusinessAnalysisRow[] | null;
  /** Backend merged_bucket_rows; “其他” ytm must read this, never recompute locally. */
  bondBucketMergedRows: readonly PnlByBusinessAnalysisRow[] | null;
};

/**
 * Production path: PnlByBusinessAnalysisPayload → dashboard cockpit yield fields.
 * Passes `merged_bucket_rows` through as `bondBucketMergedRows` with no local weighting.
 */
export function mapBondBucketAnalysisToCockpitInput(
  payload: PnlByBusinessAnalysisPayload | null | undefined,
): BondBucketCockpitYieldInput {
  if (!payload) {
    return {
      bondBucketRows: null,
      bondBucketMergedRows: null,
    };
  }

  return {
    bondBucketRows: payload.rows,
    bondBucketMergedRows: payload.merged_bucket_rows ?? null,
  };
}
