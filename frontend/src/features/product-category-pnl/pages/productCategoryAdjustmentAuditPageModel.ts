import type { ProductCategoryManualAdjustmentQuery } from "../../../api/contracts";

/**
 * Filter + current/event sort fields shared by `getProductCategoryManualAdjustments` and
 * `exportProductCategoryManualAdjustmentsCsv` (list adds pagination via separate options).
 */
export function buildProductCategoryAuditListExportQuery(
  applied: ProductCategoryManualAdjustmentQuery,
): ProductCategoryManualAdjustmentQuery {
  return {
    adjustmentId: applied.adjustmentId,
    adjustmentIdExact: applied.adjustmentIdExact,
    accountCode: applied.accountCode,
    approvalStatus: applied.approvalStatus,
    eventType: applied.eventType,
    currentSortField: applied.currentSortField,
    currentSortDir: applied.currentSortDir,
    eventSortField: applied.eventSortField,
    eventSortDir: applied.eventSortDir,
    createdAtFrom: applied.createdAtFrom,
    createdAtTo: applied.createdAtTo,
  };
}
