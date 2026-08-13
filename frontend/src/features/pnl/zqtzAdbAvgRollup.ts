/**
 * ADB 补充复核 breakdown 使用 classify_zqtz_asset_bond_label（最细一档类目），父级
 * 「非底层投资资产」「证券业资管计划」在该明细里没有单独一行。父级日均不再由前端对
 * 子类求和拼合（子类含「其中：」项，非完备分区，求和不是日均口径）；后端
 * /api/pnl/by-business-ytd 已在父级行返回 avg_balance（元），未命中证据 map 时消费该字段。
 */
export type AdbAvgResolution = {
  valueYuan: number;
  /** direct：ADB 证据 map 直接命中；ytd_row：消费后端 YTD 行的父级 avg_balance 字段 */
  source: "direct" | "ytd_row";
};

/** 返回折算前日均余额（元）与来源；两个来源都缺失或非法时返回 undefined（展示端用 EM_DASH） */
export function resolveAdbAvgYuan(
  businessType: string,
  directMap: Map<string, number>,
  backendAvgBalanceYuan?: string | number | null,
): AdbAvgResolution | undefined {
  const direct = directMap.get(businessType);
  if (direct !== undefined) {
    return { valueYuan: direct, source: "direct" };
  }
  if (backendAvgBalanceYuan === null || backendAvgBalanceYuan === undefined || backendAvgBalanceYuan === "") {
    return undefined;
  }
  const parsed = Number(backendAvgBalanceYuan);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return { valueYuan: parsed, source: "ytd_row" };
}
