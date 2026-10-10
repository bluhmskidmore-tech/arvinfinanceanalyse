import { designTokens } from "../../theme/designSystem";

/*
 * AG Grid 本地化（§7 一页一语域）：/pnl 与 /pnl-bridge 明细表分页条与
 * 列筛选控件的英文文案统一中文化；键名与 ag-grid-community localeText 对齐。
 */
export const PNL_GRID_LOCALE_TEXT: Record<string, string> = {
  // 分页条
  page: "页",
  more: "更多",
  to: "至",
  of: "共",
  next: "下一页",
  last: "末页",
  first: "首页",
  previous: "上一页",
  pageSizeSelectorLabel: "每页行数:",
  ariaPageSizeSelectorLabel: "每页行数",
  // 覆盖层
  loadingOoo: "加载中...",
  noRowsToShow: "暂无数据",
  // 列筛选
  searchOoo: "搜索...",
  filterOoo: "筛选...",
  equals: "等于",
  notEqual: "不等于",
  lessThan: "小于",
  greaterThan: "大于",
  lessThanOrEqual: "小于等于",
  greaterThanOrEqual: "大于等于",
  inRange: "介于",
  inRangeStart: "从",
  inRangeEnd: "到",
  contains: "包含",
  notContains: "不包含",
  startsWith: "开头是",
  endsWith: "结尾是",
  blank: "为空",
  notBlank: "不为空",
  blanks: "(空白)",
  selectAll: "(全选)",
  selectAllSearchResults: "(全选搜索结果)",
  noMatches: "无匹配项",
  andCondition: "并且",
  orCondition: "或者",
  applyFilter: "应用",
  resetFilter: "重置",
  clearFilter: "清除",
  cancelFilter: "取消",
};

export type PnlSectionState = "loading" | "error" | "empty" | "ready";

export function resolvePnlSectionState({
  isLoading,
  isError,
  isEmpty,
}: {
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
}): PnlSectionState {
  if (isLoading) {
    return "loading";
  }
  if (isError) {
    return "error";
  }
  if (isEmpty) {
    return "empty";
  }
  return "ready";
}

export const pnlActionButtonStyle = {
  padding: "10px 16px",
  borderRadius: 12,
  border: `1px solid ${designTokens.color.cockpit.border225}`, // 近似替换（原值 #d7dfea）
  background: designTokens.color.institutional.surfaceRaised,
  color: designTokens.color.institutional.text, // 近似替换（原值 #162033）
  fontWeight: 600,
  cursor: "pointer",
} as const;
