import type { BalanceMovementRow } from "../../../api/contracts";

import {
  reconciliationStatusHints,
  reconciliationStatusLabels,
  reconciliationStatusTones,
} from "../lib/balanceMovementReconciliationModel";

/**
 * 对账结论标签。`data-tone` 而不是 `data-status` 驱动配色：色阶按语义分组
 * （gl_only / zqtz_only 同为"无对手方"），新增取值必须先在 tones 表里表态。
 */
export function ReconciliationStatusTag({
  status,
}: {
  status: BalanceMovementRow["reconciliation_status"];
}) {
  return (
    <span
      data-status={status}
      data-tone={reconciliationStatusTones[status]}
      title={reconciliationStatusHints[status]}
    >
      {reconciliationStatusLabels[status]}
    </span>
  );
}
