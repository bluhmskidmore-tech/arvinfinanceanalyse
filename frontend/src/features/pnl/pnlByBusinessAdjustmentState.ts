import { type PnlByBusinessManualAdjustmentRequest } from "../../api/contracts";

export type ManualAdjustmentDraft = Pick<
  PnlByBusinessManualAdjustmentRequest,
  "manual_adjustment" | "approval_status" | "reason"
>;

export const EMPTY_MANUAL_ADJUSTMENT_DRAFT: ManualAdjustmentDraft = {
  manual_adjustment: "",
  approval_status: "approved",
  reason: "",
};
export function normalizeAdjustmentStatus(status: string): PnlByBusinessManualAdjustmentRequest["approval_status"] {
  if (status === "pending" || status === "rejected") {
    return status;
  }
  return "approved";
}
