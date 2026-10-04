import type { BalanceMovementRow } from "../../../api/contracts";
import { formatYuanAmountAsWanPlain } from "../../../utils/format";

import {
  chainStatusLabel,
  reconciliationStatusHints,
  reconciliationStatusLabels,
  reconciliationStatusTones,
} from "../lib/balanceMovementReconciliationModel";

export function ChainReconciliationCell({ row }: { row: BalanceMovementRow }) {
  return (
    <td>
      {chainStatusLabel(row.chain_status)}
      {row.chain_status === "fx_adjusted" && row.chain_fx_adjustment != null && (
        <div title={`${row.chain_fx_currency} 汇率：上期 ${row.chain_fx_prior_rate}，本期 ${row.chain_fx_current_rate}`}>
          折算差 {formatYuanAmountAsWanPlain(row.chain_fx_adjustment)} 万元
        </div>
      )}
    </td>
  );
}

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
