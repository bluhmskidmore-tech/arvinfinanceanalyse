/** PnL by-business（primary 对账）域契约：从 contracts.ts 下放的域类型。 */
import type { PnlByBusinessUntracedBreakdownRow } from "./contracts";

export type PnlByBusinessSummary = {
  business_count: number;
  total_pnl: string;
  total_scale_amount: string;
  /** 514/516/517 分列合计与 rows 同源（后端逐列求和），表脚直读，前端不得复算。 */
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
  /** 全部 rows 的损益行数合计（含未追溯行）。 */
  pnl_row_count: number;
  traced_pnl_row_count: number;
  untraced_pnl_row_count: number;
  untraced_breakdown?: PnlByBusinessUntracedBreakdownRow[];
};
