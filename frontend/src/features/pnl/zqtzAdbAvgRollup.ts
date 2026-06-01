/**
 * 日均 breakdown 使用 classify_zqtz_asset_bond_label（最细一档类目）；父级「非底层投资资产」、
 * 「证券业资管计划」在明细里常常没有单独一行，PnL 父级行却仍汇总损益，
 * 故日均列应对其子类日均（元）求和以便对齐口径。
 * 与 backend/app/core_finance/zqtz_asset_bond_category.py 中 sort_order 83–88 行一致。
 */
export const ADB_AVG_ROLLUP_CHILDREN_BY_PARENT: Record<string, readonly string[]> = {
  非底层投资资产: ["信托计划", "证券业资管计划"],
  证券业资管计划: [
    "其中：结构化融资（券商）",
    "其中：外币委外",
    "其中：本币委外（市值法）",
    "其中：本币专户（成本法）",
  ],
};

/** 返回折算前日均余额（元）；无可用数据时 undefined */
export function resolveAdbAvgYuan(businessType: string, directMap: Map<string, number>): number | undefined {
  return resolveAdbAvgYuanFromRollup(businessType, directMap, new Set());
}

function resolveAdbAvgYuanFromRollup(
  businessType: string,
  directMap: Map<string, number>,
  visiting: Set<string>,
): number | undefined {
  const direct = directMap.get(businessType);
  if (direct !== undefined && direct > 0) {
    return direct;
  }
  if (visiting.has(businessType)) {
    return undefined;
  }
  const children = ADB_AVG_ROLLUP_CHILDREN_BY_PARENT[businessType];
  if (!children?.length) {
    return undefined;
  }
  visiting.add(businessType);
  let sum = 0;
  for (const label of children) {
    const v = resolveAdbAvgYuanFromRollup(label, directMap, visiting);
    if (v !== undefined && v > 0) {
      sum += v;
    }
  }
  visiting.delete(businessType);
  return sum > 0 ? sum : undefined;
}
