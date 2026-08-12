import type { MacroToolkitDataHealth } from "../../../api/macroToolkitClient";
import {
  canRefreshMacroSourceBackfill,
  normalizeMacroSourceBackfillAlias,
} from "./macroToolkitCrisisSupport";
import type { MacroToolkitActionReceipt, MacroToolkitRepairItem } from "./macroToolkitPageModel";

export function repairItemFocusKey(item: MacroToolkitRepairItem) {
  return normalizeMacroSourceBackfillAlias(item.alias) || item.key || item.label || item.type || "repair";
}

export function coverageValue(coverage: MacroToolkitDataHealth["source_coverage"]) {
  return coverage.deferred ? "延后加载" : `${coverage.hit_count}/${coverage.total_count}`;
}

export function formatMissingIndicatorDetail(items: MacroToolkitDataHealth["indicator_coverage"]["missing"]) {
  return items.length
    ? `缺失 ${items.map((item) => item.alias ?? item.key ?? item.label).filter(Boolean).join(" / ")}`
    : "指标全部命中";
}

export function formatCompactObservationList(items: Array<string | null | undefined>, limit = 4) {
  const visibleItems = Array.from(
    new Set(items.map((item) => item?.trim()).filter((item): item is string => Boolean(item))),
  );
  if (!visibleItems.length) {
    return "待确认";
  }
  const shownItems = visibleItems.slice(0, limit).join(" / ");
  const hiddenCount = visibleItems.length - limit;
  return hiddenCount > 0 ? `${shownItems}，另 ${hiddenCount} 项` : shownItems;
}

export function capabilityIssueCount(dataHealth: MacroToolkitDataHealth) {
  return dataHealth.capability_results.degraded + dataHealth.capability_results.unavailable;
}

export function capabilityHealthDetail(dataHealth: MacroToolkitDataHealth) {
  if (dataHealth.capability_results.deferred) {
    return "能力结果延后加载，未按 0 处理";
  }
  return `${dataHealth.capability_results.complete} 完整 / ${dataHealth.capability_results.degraded} 降级 / ${dataHealth.capability_results.unavailable} 不可用`;
}

export function formatObservationDeferredSectionLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    capability_results: "能力结果",
    capabilities: "能力边界",
    source_checks: "来源证据",
    strategy_summaries: "策略证据",
    a_share_risk: "风险证据",
  };
  return labels[value ?? ""] ?? (value || "证据链确认");
}

export function formatDataHealthRepairLabel(item: MacroToolkitRepairItem, plainLanguage: boolean) {
  if (item.type === "deferred") {
    return formatObservationDeferredSectionLabel(item.label ?? item.key);
  }
  if (!plainLanguage) {
    return item.label ?? item.alias ?? item.key ?? "未命名数据项";
  }
  return item.label ?? item.alias ?? item.key ?? "未命名数据项";
}

export function formatDataHealthRepairAction(item: MacroToolkitRepairItem, plainLanguage: boolean) {
  const action = item.suggested_action ?? "";
  return item.type === "deferred" || plainLanguage
    ? "打开完整分析后确认这部分证据，不把首屏延后加载当作缺失。"
    : action;
}

const REPAIR_ACTION_CODE_PATTERN = /[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+/g;

export function extractRepairActionCodes(action: string) {
  return Array.from(new Set(action.match(REPAIR_ACTION_CODE_PATTERN) ?? []));
}

/**
 * 后端能力缺口的 suggested_action 形如「{label} 当前 unavailable：CODE_A / CODE_B；补齐输入证据后…」。
 * 仅当该模式命中且包含英文缺口代码时给出中文摘要句；其余修复建议（含单代码中文句）原样展示。
 */
export function summarizeRepairAction(action: string) {
  const statusMatch = action.match(/^(.*?) 当前 (unavailable|degraded)[：:]/);
  if (!statusMatch) {
    return null;
  }
  const codes = extractRepairActionCodes(action);
  if (!codes.length) {
    return null;
  }
  return statusMatch[2] === "unavailable"
    ? `核心输入缺失 ${codes.length} 项，补数后重新运行完整分析。`
    : `${codes.length} 项输入待补或降级，补齐后重新运行完整分析。`;
}

export function repairTicketOwner(item: MacroToolkitRepairItem) {
  if (item.action?.kind === "load_full_analysis" || item.type === "deferred" || item.type === "degraded") {
    return "宏观策略负责人";
  }
  return "数据运营负责人";
}

export function repairTicketSla(item: MacroToolkitRepairItem) {
  if (item.priority === "high" || canRefreshMacroSourceBackfill(item)) {
    return "T+0 盘前";
  }
  if (item.type === "deferred" || item.action?.kind === "load_full_analysis") {
    return "完整分析前";
  }
  return "T+1 盘前";
}

export function repairTicketReceipt(item: MacroToolkitRepairItem) {
  if (canRefreshMacroSourceBackfill(item)) {
    return "来源补齐回执";
  }
  if (item.action?.kind === "load_full_analysis") {
    return "完整分析回执";
  }
  return "人工复核记录";
}

export function repairTicketSubmissionImpact(item: MacroToolkitRepairItem) {
  if (item.priority === "high" || item.type === "missing") {
    return "暂缓提交";
  }
  if (item.type === "deferred") {
    return "等待完整分析";
  }
  return "待复核后提交";
}

export function repairTicketReceiptStatus(receipt: MacroToolkitActionReceipt | null, receiptConfirmed: boolean) {
  if (!receipt) {
    return "待执行留痕";
  }
  return receiptConfirmed ? "签核已确认" : "回执待复核";
}

export function formatObservationRepairTraceItem(item: MacroToolkitRepairItem) {
  if (item.type === "deferred") {
    return "完整分析补充项";
  }
  const label = formatDataHealthRepairLabel(item, true);
  if (item.stale_days) {
    return `${label} 落后 ${item.stale_days} 天`;
  }
  if (item.type === "degraded" && item.suggested_action) {
    const missingInput = item.suggested_action.match(/[A-Z][A-Z0-9_]{2,}/)?.[0];
    return missingInput ? `${label} ${missingInput}` : label;
  }
  return label;
}

export function formatObservationRepairSummary(items: MacroToolkitRepairItem[]) {
  if (items.some((item) => item.type === "missing" || item.priority === "high")) {
    return "先补齐高优先级输入，再复核观察结论。";
  }
  if (items.some((item) => item.type === "deferred")) {
    return "完整分析后复核。";
  }
  if (items.some((item) => item.type === "degraded")) {
    return "降级结果需复核输入证据后再使用。";
  }
  return "待处理项已归纳，完整明细保留在宏观工具页。";
}


export function repairPriorityColor(priority: string | null | undefined) {
  if (priority === "high") return "red";
  if (priority === "low") return "blue";
  return "gold";
}

export function repairPriorityLabel(priority: string | null | undefined) {
  if (priority === "high") return "高";
  if (priority === "low") return "低";
  return "中";
}

export function committeePriorityLabel(priority: string | null | undefined) {
  if (priority === "high") return "高优先级";
  if (priority === "low") return "低优先级";
  return "中优先级";
}

export function repairPriorityRank(priority: string | null | undefined) {
  if (priority === "high") return 0;
  if (priority === "medium") return 1;
  if (priority === "low") return 2;
  return 3;
}

export function compareRepairPriority(left: MacroToolkitRepairItem, right: MacroToolkitRepairItem) {
  return repairPriorityRank(left.priority) - repairPriorityRank(right.priority);
}

export function formatCommitteeReadinessBlocker(item: MacroToolkitRepairItem | null, totalCount: number) {
  if (!item) {
    return totalCount ? `共 ${totalCount} 项数据缺口` : "无关键卡点";
  }
  const label = formatDataHealthRepairLabel(item, true);
  const alias = item.alias && item.alias !== label ? ` / ${item.alias}` : "";
  return `${committeePriorityLabel(item.priority)} · ${label}${alias} · 共 ${totalCount} 项`;
}

export function repairTypeLabel(type: string | null | undefined) {
  const labels: Record<string, string> = {
    missing: "缺失",
    stale: "滞后",
    degraded: "降级",
    deferred: "完整分析后确认",
  };
  return labels[type ?? ""] ?? (type || "待确认");
}
