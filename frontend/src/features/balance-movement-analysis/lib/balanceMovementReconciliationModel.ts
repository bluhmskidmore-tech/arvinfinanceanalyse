/**
 * 余额变动读模型的对账结论词汇表。
 *
 * 后端有两套互相独立的控制：横截面的"头寸 vs 总账"和时间序列的"本月期初 vs
 * 上月期末"。页面必须把 `gl_only`（根本没有对手方）、`mismatch`（真的对不平）和
 * `chain_broken`（跨月接不上）呈现成三种不同的状态，否则用户区分不出来。
 */
import type {
  BalanceMovementPositionSourceUnavailable,
  BalanceMovementRow,
} from "../../../api/contracts";

import { nullableNumber } from "./balanceMovementShareModel";

type ReconciliationStatus = BalanceMovementRow["reconciliation_status"];
type ChainStatus = BalanceMovementRow["chain_status"];

export const CHAIN_STATUS_UNRECORDED_TEXT = "未记录";
export const NOT_APPLICABLE_TEXT = "不适用";
const POSITION_SOURCE_UNAVAILABLE: BalanceMovementPositionSourceUnavailable = "unavailable";
const YI = 100000000;

// 按联合类型建表：后端新增一个对账取值时这里会编译报错，而不是把英文码漏到页面上。
export const reconciliationStatusLabels: Record<ReconciliationStatus, string> = {
  matched: "一致",
  mismatch: "对不平",
  gl_only: "无头寸对手方",
  zqtz_only: "无总账对手方",
  chain_broken: "跨月断裂",
};

export const reconciliationStatusHints: Record<ReconciliationStatus, string> = {
  matched: "头寸与总账在容差内一致，且本月期初接得上上月期末。",
  mismatch: "头寸与总账两侧都有余额但金额不符，差额见 ZQTZ 诊断差异列。",
  gl_only: "该分类只有总账余额、头寸源没有对应持仓，无法完成对账；不等于已对平。",
  zqtz_only: "该分类只有头寸余额、总账没有对应科目，无法完成对账；不等于已对平。",
  chain_broken: "头寸与总账本期对得上，但本月期初余额接不上上月期末，勾稽链断裂。",
};

export type ReconciliationStatusTone = "ok" | "mismatch" | "no-counterparty" | "chain-broken";

// 三类结论要能一眼分开：对不平是"两侧都有数、金额不符"，无对手方是"压根没法比"，
// 跨月断裂是"横截面对得上、但本月期初接不上上月期末"。
export const reconciliationStatusTones: Record<ReconciliationStatus, ReconciliationStatusTone> = {
  matched: "ok",
  mismatch: "mismatch",
  gl_only: "no-counterparty",
  zqtz_only: "no-counterparty",
  chain_broken: "chain-broken",
};

const reconciliationStatusKeys = Object.keys(
  reconciliationStatusLabels,
) as ReconciliationStatus[];

const chainStatusLabels: Record<NonNullable<ChainStatus>, string> = {
  continuous: "衔接",
  broken: "断裂",
  no_prior_month: "无上月基准",
};

/**
 * 列值为 null = 该行写于控制结论落库之前。它和"已判定为无上月基准"不是一回事，
 * 合并显示会让未覆盖的历史行看起来像已经检查过。
 */
export function chainStatusLabel(status: ChainStatus): string {
  return status === null ? CHAIN_STATUS_UNRECORDED_TEXT : chainStatusLabels[status];
}

/**
 * 头寸源当期整体缺失时 zqtz_amount 恒为 0、reconciliation_diff 恒为 -总账余额，
 * 两者都不是真实计量结果。印 0 会被读成"辅助账为零"，印差额会被读成真实缺口。
 */
export function hasPositionCounterparty(row: BalanceMovementRow): boolean {
  return row.position_source_basis !== POSITION_SOURCE_UNAVAILABLE;
}

/** 无对手方时不展示已格式化的金额，改印"不适用"。 */
export function counterpartyAmountText(row: BalanceMovementRow, formatted: string): string {
  return hasPositionCounterparty(row) ? formatted : NOT_APPLICABLE_TEXT;
}

export function statusToneClass(status: ReconciliationStatus): string {
  return `balance-movement-detail-table__status balance-movement-detail-table__status--${reconciliationStatusTones[status]}`;
}

export function countReconciliationStatuses(
  rows: BalanceMovementRow[],
): Record<ReconciliationStatus, number> {
  const counts: Record<ReconciliationStatus, number> = {
    matched: 0,
    mismatch: 0,
    gl_only: 0,
    zqtz_only: 0,
    chain_broken: 0,
  };
  for (const row of rows) {
    counts[row.reconciliation_status] += 1;
  }
  return counts;
}

/** 首屏只有一行字的位置，也要说清是哪一类不通过，而不是笼统的"需关注"。 */
export function reconciliationConcernLabel(
  counts: Record<ReconciliationStatus, number>,
): string {
  if (counts.mismatch > 0) {
    return "分桶对不平";
  }
  if (counts.chain_broken > 0) {
    return "跨月勾稽断裂";
  }
  if (counts.gl_only + counts.zqtz_only > 0) {
    return "缺对账对手方";
  }
  return "需关注";
}

export function chainTieoutText(rows: BalanceMovementRow[]): string {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = chainStatusLabel(row.chain_status);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()].map(([label, count]) => `${label} ${count}`).join(" · ");
}

/** 页面持有金额格式化口径，这里只负责结论口径。 */
export function reconciliationTieoutSummary(
  rows: BalanceMovementRow[],
  formatSignedYi: (valueYi: number) => string,
): string {
  if (rows.length === 0) {
    return "暂无对账行";
  }
  const counts = countReconciliationStatuses(rows);
  const unmatched = reconciliationStatusKeys
    .filter((status) => status !== "matched" && counts[status] > 0)
    .map((status) => `${reconciliationStatusLabels[status]} ${counts[status]}`)
    .join(" · ");
  // 无对手方的行差额是"没有对账"的产物，把它加进合计会伪造出一个可比缺口。
  const comparableRows = rows.filter(hasPositionCounterparty);
  const comparableDiff = comparableRows.reduce(
    (total, row) => total + (nullableNumber(row.reconciliation_diff) ?? 0),
    0,
  );
  const diffText =
    comparableRows.length === 0
      ? NOT_APPLICABLE_TEXT
      : `${formatSignedYi(comparableDiff / YI)} 亿`;
  return [
    `${counts.matched} / ${rows.length} 一致${unmatched ? `（${unmatched}）` : ""}`,
    `可比差异 ${diffText}`,
    `跨月勾稽 ${chainTieoutText(rows)}`,
  ].join(" · ");
}
