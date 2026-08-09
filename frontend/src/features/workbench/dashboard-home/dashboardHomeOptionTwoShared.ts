import type { HomeDataStateKind } from "./dashboardHomeFirstScreenTypes";

export type HomeStatusKind = HomeDataStateKind | "fallback";

export function compactClock(value: string | undefined): string {
  const match = /(?:\d{4}-\d{2}-\d{2}[ T])?(\d{2}:\d{2})/.exec(value?.trim() ?? "");
  return match?.[1] ?? "—";
}

export function stateLabel(kind: HomeStatusKind): string {
  switch (kind) {
    case "ready":
      return "已就绪";
    case "partial":
      return "部分可用";
    case "loading":
      return "读取中";
    case "stale":
      return "数据偏旧";
    case "fallback":
      return "回退数据";
    case "error":
      return "不可用";
    case "empty":
      return "暂无数据";
    default:
      return "待接入";
  }
}

export function statusTone(kind: HomeStatusKind): "ok" | "warn" | "bad" | "muted" {
  if (kind === "ready") return "ok";
  if (kind === "partial" || kind === "stale" || kind === "fallback") return "warn";
  if (kind === "error") return "bad";
  return "muted";
}

export function reportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== "—"
    ? `${path}?report_date=${encodeURIComponent(trimmed)}`
    : path;
}
