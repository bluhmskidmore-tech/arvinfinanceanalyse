import dayjs from "dayjs";

import {
  localizeStockBackendText,
  localizeStrategyPanelErrorDetail,
} from "./stockAnalysisPageModel";

type StockRailActionCandidate = {
  stockName: string;
  distanceToBreakoutPct: string;
};

type StockRailRiskRow = {
  status: string;
};

export type StockAnalysisRailReviewState = {
  riskTriggeredCount: number;
  riskWatchCount: number;
  railRiskTone: "negative" | "warning" | "positive";
  railNextActionFullLabel: string;
  railNextActionLabel: string;
};

type StockThemeBreakoutUnsupportedOutput = {
  key: string | null | undefined;
  reason: string | null | undefined;
};

export type StockThemeBreakoutBlockerCopy = {
  text: string | null;
  label: string | null;
};

export function stockPageErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return localizeStockErrorMessage(message);
}

export function stockStrategyPanelErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return localizeStrategyPanelErrorDetail(message);
}

export function rawStockErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

export function localizeStockErrorMessage(message: string) {
  const value = message.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactMessages: Record<string, string> = {
    "strategy unavailable": "策略服务暂不可用，请稍后重试。",
    "confluence unavailable": "联动观察服务暂不可用，请稍后重试。",
  };
  if (exactMessages[normalized]) {
    return exactMessages[normalized];
  }
  if (normalized.includes("not allowed") || normalized.includes("permission") || normalized.includes("forbidden")) {
    return "数据权限待确认，请联系管理员。";
  }
  if (
    (normalized.includes("source_table") || normalized.includes("source table")) &&
    normalized.includes("missing")
  ) {
    return "请求失败：必需数据源缺失，稍后复核供数状态。";
  }
  if (
    normalized.includes("request failed") ||
    normalized.includes("/ui/") ||
    normalized.includes("market-data") ||
    normalized.includes("livermore")
  ) {
    return "供数暂不可用，请稍后复核。";
  }
  return localizeStockBackendText(value);
}

export function stockStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    fail: "未通过",
    ready: "就绪",
    partial: "部分",
    blocked: "阻断",
    unsupported: "不可用",
    available: "已接入",
    complete: "完整",
    pending: "待补",
    missing: "缺数据",
    stale: "已陈旧",
    ok: "正常",
    warning: "需复核",
  };
  return labels[status] ?? "状态待确认";
}

export function stockSupplyQualityLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "正常",
    warning: "需复核",
    stale: "陈旧",
    error: "异常",
    pending: "待确认",
  };
  return labels[normalized] ?? "质量待确认";
}

export function stockSupplyVendorLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "正常",
    vendor_stale: "陈旧",
    vendor_unavailable: "异常",
    degraded: "降级",
    error: "异常",
    pending: "待确认",
  };
  return labels[normalized] ?? "供数待确认";
}

export function stockSupplyFallbackLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  if (!normalized || normalized === "none") return "无回退";
  const labels: Record<string, string> = {
    latest_snapshot: "回退快照",
    cache: "缓存回退",
    mock: "模拟回退",
  };
  return labels[normalized] ?? "回退待确认";
}

export function stockSupplyBasisLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized === "analytical") return "分析口径";
  if (normalized === "formal") return "正式口径";
  return "口径待确认";
}

export function compactStockText(text: string | null | undefined, maxLength = 28) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

export function formatGeneratedAtLabel(value: string | null | undefined) {
  if (!value) return "";
  const sourceTimestamp = value.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
  if (sourceTimestamp) {
    return `${sourceTimestamp[2]}-${sourceTimestamp[3]} ${sourceTimestamp[4]}:${sourceTimestamp[5]}`;
  }
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format("MM-DD HH:mm") : compactStockText(value, 12);
}

export function iconTone(tone?: string) {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "warning") return "warning";
  return "neutral";
}

export function kpiToneToDelta(tone?: string): "up" | "down" | "flat" {
  if (tone === "positive") return "up";
  if (tone === "negative") return "down";
  return "flat";
}

export function filterChipClass(active: boolean): string {
  const base =
    "inline-flex min-h-7 cursor-pointer items-center whitespace-nowrap rounded-full border px-2.5 text-xs font-semibold transition-colors";
  return active
    ? `${base} border-primary-500 bg-primary-50 text-primary-800`
    : `${base} border-neutral-200 bg-neutral-50 text-neutral-700 hover:bg-neutral-100`;
}

export function statusIconClass(tone?: string): string {
  const base = "inline-grid h-5 w-5 shrink-0 place-items-center rounded border text-xs leading-none";
  if (tone === "positive") return `${base} border-success-200 bg-success-50 text-success-700`;
  if (tone === "warning") return `${base} border-warning-200 bg-warning-50 text-warning-700`;
  if (tone === "negative") return `${base} border-danger-200 bg-danger-50 text-danger-700`;
  return `${base} border-primary-200 bg-primary-50 text-primary-700`;
}

export function toneTextClass(tone?: string): string {
  if (tone === "positive") return "text-success-600";
  if (tone === "warning") return "text-warning-600";
  if (tone === "negative") return "text-danger-600";
  return "text-neutral-600";
}

export function tonePillClass(tone?: string): string {
  if (tone === "positive") return "border border-success-200 bg-success-50 text-success-700";
  if (tone === "warning") return "border border-warning-200 bg-warning-50 text-warning-700";
  if (tone === "negative") return "border border-danger-200 bg-danger-50 text-danger-700";
  return "border border-neutral-200 bg-neutral-50 text-neutral-600";
}

export function buildStockRailActionLabel(
  candidate: StockRailActionCandidate | null | undefined,
  fallback: string | null | undefined,
) {
  if (candidate) return `首位 ${candidate.stockName} · ${candidate.distanceToBreakoutPct}`;
  if (!fallback) return "等待复核";
  if (fallback.includes("多因子")) return "多因子池";
  if (fallback.includes("候选")) return "候选复核";
  if (fallback.includes("风险")) return "风险复核";
  return compactStockText(fallback, 14) || "等待复核";
}

export function buildStockAnalysisRailReviewState({
  reviewQueue,
  riskRows,
  nextReviewAction,
}: {
  reviewQueue: StockRailActionCandidate[];
  riskRows: StockRailRiskRow[];
  nextReviewAction?: string | null;
}): StockAnalysisRailReviewState {
  const riskTriggeredCount = riskRows.filter((row) => row.status === "triggered").length;
  const riskWatchCount = riskRows.filter((row) => row.status === "watch").length;
  const primaryCandidate = reviewQueue[0];
  const fallbackAction = nextReviewAction ?? "\u7b49\u5f85\u590d\u6838\u961f\u5217";

  return {
    riskTriggeredCount,
    riskWatchCount,
    railRiskTone: riskTriggeredCount > 0 ? "negative" : riskWatchCount > 0 ? "warning" : "positive",
    railNextActionFullLabel: primaryCandidate
      ? `${primaryCandidate.stockName} \u00b7 \u8ddd\u89c2\u5bdf ${primaryCandidate.distanceToBreakoutPct}`
      : fallbackAction,
    railNextActionLabel: buildStockRailActionLabel(primaryCandidate, nextReviewAction),
  };
}

export function buildThemeBreakoutBlockerCopy(
  output: StockThemeBreakoutUnsupportedOutput | null | undefined,
): StockThemeBreakoutBlockerCopy {
  const text = output?.reason ? localizeStockBackendText(output.reason, output.key) : null;
  if (!text) return { text: null, label: null };

  return {
    text,
    label: isThemeBreakoutGateBlocker(text) ? "\u95e8\u63a7\u6682\u505c" : compactStockText(text, 10),
  };
}

function isThemeBreakoutGateBlocker(text: string): boolean {
  return text.includes("\u95e8\u63a7") || text.includes("\u8fc7\u70ed");
}

export function riskStatusLabel(status: "triggered" | "watch") {
  return status === "triggered" ? "触发复核" : "观察中";
}

function isTechnicalRiskExitReason(reason: string | null | undefined) {
  const normalized = reason?.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const compact = normalized?.replace(/_/g, "");
  return (
    normalized?.includes("external_vendor") ||
    normalized?.includes("vendor_") ||
    normalized?.includes("source_table") ||
    compact?.includes("externalvendor") ||
    compact?.includes("vendor") ||
    compact?.includes("sourcetable") ||
    compact?.includes("choicestock")
  );
}

export function riskExitBlockedSummary(reason: string | null | undefined) {
  const normalized = reason?.trim();
  if (!normalized) return "供数状态待确认";
  if (isTechnicalRiskExitReason(normalized)) return "风险退出待确认";
  if (/position_snapshot|ACTIVE A-share/i.test(normalized)) return "持仓快照缺失";
  return compactStockText(normalized, 24);
}

export function riskExitBlockedDetail(reason: string | null | undefined, key: string | null | undefined) {
  const normalized = reason?.trim();
  if (isTechnicalRiskExitReason(normalized)) return "风险退出待确认";
  return localizeStockBackendText(reason, key);
}
