export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    current: "已对齐",
    lagging: "轻微滞后",
    stale: "陈旧",
    missing: "缺失",
    unknown: "待确认",
    ready: "数据齐备",
    partial: "部分就绪",
    not_required: "无需数据",
    complete: "已完成",
    degraded: "部分降级",
    unavailable: "不可用",
    deferred: "已延后",
    loading: "加载中",
    failed: "失败",
    idle: "空闲",
    queued: "已排队",
    running: "运行中",
    completed: "已完成",
    aligned: "已对齐",
    fallback: "最近快照",
    library_ready: "函数已迁入",
    wired: "已接线",
    visible: "已展示",
    not_wired: "未接线",
    planned: "待接入",
    sample_only: "样例展示",
    observation_ready: "观察就绪",
  };
  return labels[status] ?? status;
}

export function statusColor(status: string) {
  if (["current", "ready", "library_ready", "complete", "wired", "visible"].includes(status)) {
    return "green";
  }
  if (
    ["lagging", "partial", "planned", "degraded", "sample_only", "deferred", "loading", "observation_ready"].includes(
      status,
    )
  ) {
    return "gold";
  }
  if (["stale", "missing", "not_wired", "unavailable", "failed"].includes(status)) return "red";
  return "default";
}

export function observationStatusLabel(status: string | null | undefined) {
  if (status === "observation_ready" || status === "degraded" || status === "partial") return "观察就绪";
  return statusLabel(status ?? "unknown");
}

export function compactText(text: string | null | undefined, maxLength = 34) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

export function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}
