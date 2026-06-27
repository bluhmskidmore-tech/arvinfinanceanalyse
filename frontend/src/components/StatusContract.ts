export type StatusPillStatus = "normal" | "caution" | "warning" | "danger" | "neutral";

export type BusinessRiskStatus = "normal" | "watch" | "warning" | "blocked";
export type DataQualityStatus = "fresh" | "stale" | "partial" | "unavailable";
export type DataSourceStatus = "official" | "analysis" | "proxy" | "mock";
export type SystemAccessStatus = "connected" | "connecting" | "missing" | "error";
export type ActionPriorityStatus = "p0" | "p1" | "p2" | "watch";

export type StatusContractCategory =
  | "risk"
  | "dataQuality"
  | "dataSource"
  | "systemAccess"
  | "actionPriority";

export type BusinessStatusValue =
  | BusinessRiskStatus
  | DataQualityStatus
  | DataSourceStatus
  | SystemAccessStatus
  | ActionPriorityStatus;

type StatusContractEntry = {
  label: string;
  tone: StatusPillStatus;
  description: string;
};

export type MappedBusinessStatus = StatusContractEntry & {
  category: StatusContractCategory;
  status: BusinessStatusValue;
};

const STATUS_CONTRACT = {
  risk: {
    normal: { label: "正常", tone: "normal", description: "业务风险处于正常区间" },
    watch: { label: "关注", tone: "caution", description: "需要持续观察" },
    warning: { label: "预警", tone: "warning", description: "需要复核或干预" },
    blocked: { label: "阻断", tone: "danger", description: "暂不可继续使用" },
  },
  dataQuality: {
    fresh: { label: "数据正常", tone: "normal", description: "数据可用于当前判断" },
    stale: { label: "数据延迟", tone: "caution", description: "数据时间落后于当前观察日" },
    partial: { label: "部分缺失", tone: "warning", description: "部分数据缺失，结论需复核" },
    unavailable: { label: "不可用", tone: "danger", description: "暂不可用于正式决策" },
  },
  dataSource: {
    official: { label: "正式可用", tone: "normal", description: "正式来源，可进入业务判断" },
    analysis: { label: "仅分析使用", tone: "caution", description: "仅用于观察和复核" },
    proxy: { label: "代理数据", tone: "warning", description: "代理或降级来源，不作正式结论" },
    mock: { label: "演示数据", tone: "danger", description: "演示或样例数据，不作正式判断" },
  },
  systemAccess: {
    connected: { label: "已接入", tone: "normal", description: "系统链路已接入" },
    connecting: { label: "接入中", tone: "caution", description: "系统链路正在接入或读取" },
    missing: { label: "未接入", tone: "warning", description: "数据链路尚未闭合" },
    error: { label: "技术异常", tone: "danger", description: "系统链路异常" },
  },
  actionPriority: {
    p0: { label: "高优先级", tone: "danger", description: "需要优先处理" },
    p1: { label: "中优先级", tone: "warning", description: "需要安排复核" },
    p2: { label: "低优先级", tone: "caution", description: "可排队处理" },
    watch: { label: "观察", tone: "neutral", description: "保持观察" },
  },
} as const satisfies Record<StatusContractCategory, Record<string, StatusContractEntry>>;

function normalizeRawStatus(raw: unknown): string {
  return String(raw ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/_/g, "-");
}

function hasAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle));
}

function dataQualityFromRaw(value: string): DataQualityStatus {
  if (hasAny(value, ["error", "failed", "unavailable", "blocked", "不可用"])) return "unavailable";
  if (hasAny(value, ["stale", "delay", "delayed", "latest-snapshot", "fallback-date", "陈旧", "延迟"])) {
    return "stale";
  }
  if (hasAny(value, ["warning", "warn", "missing", "partial", "empty", "gap", "source-pending", "待接入", "缺失"])) {
    return "partial";
  }
  return "fresh";
}

function dataSourceFromRaw(value: string): DataSourceStatus {
  if (hasAny(value, ["mock", "demo", "sample", "replay", "演示", "样例", "回放"])) return "mock";
  if (hasAny(value, ["proxy", "fallback", "latest-snapshot", "代理", "回退", "降级"])) return "proxy";
  if (hasAny(value, ["analysis", "analytical", "scenario", "仅分析", "分析"])) return "analysis";
  return "official";
}

function systemAccessFromRaw(value: string): SystemAccessStatus {
  if (hasAny(value, ["error", "failed", "exception", "vendor-unavailable", "技术异常", "异常"])) return "error";
  if (hasAny(value, ["missing", "source-pending", "not-read", "backend-gap", "unavailable", "未接入", "待接入"])) {
    return "missing";
  }
  if (hasAny(value, ["loading", "pending", "connecting", "deferred", "接入中", "读取中"])) return "connecting";
  return "connected";
}

function riskFromRaw(value: string): BusinessRiskStatus {
  if (hasAny(value, ["blocked", "danger", "failed", "error", "negative", "阻断"])) return "blocked";
  if (hasAny(value, ["warning", "warn", "prewarn", "预警"])) return "warning";
  if (hasAny(value, ["watch", "caution", "partial", "stale", "关注", "观察"])) return "watch";
  return "normal";
}

function actionPriorityFromRaw(value: string): ActionPriorityStatus {
  if (hasAny(value, ["p0", "critical", "high", "urgent", "高"])) return "p0";
  if (hasAny(value, ["p1", "medium", "warning", "中"])) return "p1";
  if (hasAny(value, ["p2", "low", "低"])) return "p2";
  return "watch";
}

function inferCategory(value: string): StatusContractCategory {
  if (hasAny(value, ["formal", "official", "analytical", "analysis", "proxy", "mock", "scenario"])) {
    return "dataSource";
  }
  if (hasAny(value, ["live", "connected", "loading", "not-read", "backend-gap", "vendor-unavailable"])) {
    return "systemAccess";
  }
  if (hasAny(value, ["p0", "p1", "p2", "urgent", "priority"])) return "actionPriority";
  if (hasAny(value, ["risk", "blocked", "danger", "watch"])) return "risk";
  return "dataQuality";
}

function statusFromRaw(category: StatusContractCategory, value: string): BusinessStatusValue {
  if (category === "risk") return riskFromRaw(value);
  if (category === "dataSource") return dataSourceFromRaw(value);
  if (category === "systemAccess") return systemAccessFromRaw(value);
  if (category === "actionPriority") return actionPriorityFromRaw(value);
  return dataQualityFromRaw(value);
}

export function mapStatusEntry(
  category: StatusContractCategory,
  status: BusinessStatusValue,
): MappedBusinessStatus {
  const entries = STATUS_CONTRACT[category] as Record<string, StatusContractEntry>;
  const entry = entries[status] ?? STATUS_CONTRACT.dataQuality.partial;
  return {
    category,
    status,
    ...entry,
  };
}

export function mapRawStatusToBusinessStatus(
  raw: unknown,
  category?: StatusContractCategory,
): MappedBusinessStatus {
  const value = normalizeRawStatus(raw);
  const resolvedCategory = category ?? inferCategory(value);
  return mapStatusEntry(resolvedCategory, statusFromRaw(resolvedCategory, value));
}
