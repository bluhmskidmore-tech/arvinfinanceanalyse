import type { HomeReportDateContext, HomeReportDateMode } from "./dashboardHomeFirstScreenTypes";

/**
 * 首页报告日期展示标签辅助模块。
 *
 * 把 HomeReportDateContext 渲染成一致的可见文本，确保"请求日 / 实际数据日 / 回退原因"
 * 在顶部 Toolbar、首屏 FirstScreen、决策栏 DecisionRail 三处口径完全一致。
 *
 * 语义对齐 docs/page_contracts.md：请求日 ≠ 实际数据日时必须显式说明原因。
 */

const GAP = "—";

/** 把 "2026-04-18" 格式化为紧凑的 "04/18"；非法或空值返回 GAP。 */
export function formatShortDate(iso: string | null | undefined): string {
  const trimmed = iso?.trim();
  if (!trimmed) {
    return GAP;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(trimmed);
  return match ? `${match[2]}/${match[3]}` : trimmed;
}

/** 把 "2026-04-18" 或 "2026-04-18 16:00" 格式化为 "04-18"；非法或空值返回 GAP。 */
export function formatShortDateDash(iso: string | null | undefined): string {
  const short = formatShortDate(iso);
  return short === GAP ? GAP : short.replace("/", "-");
}

/** 模式 → 状态简述，用于状态药丸/标签。 */
export function reportDateModeLabel(mode: HomeReportDateMode): string {
  switch (mode) {
    case "exact":
      return "报告日一致";
    case "fallback":
      return "已回退";
    case "stale":
      return "数据偏旧";
    case "loading":
      return "读取中";
    case "error":
      return "读取失败";
    case "mock":
      return "样例数据";
    case "empty":
      return "暂无数据";
    default:
      return "未知";
  }
}

/**
 * 渲染"请求日 · 实际数据日 · 原因"复合标签。
 *
 * - exact / loading / error / empty：只返回一个清晰的实际数据日（或状态文案）。
 * - fallback / stale：返回 "请求 MM/DD · 实际数据 MM/DD · 原因：..."。
 * - mock：返回 "样例数据日 YYYY-MM-DD"。
 */
export function reportDateContextLabel(ctx: HomeReportDateContext): string {
  if (ctx.mode === "mock") {
    return `样例数据日 ${ctx.actualDataDate || GAP}`;
  }
  if (ctx.mode === "loading") {
    return "主快照读取中";
  }
  if (ctx.mode === "error") {
    return ctx.divergenceReason?.trim() || "首页快照读取失败";
  }
  if (ctx.mode === "empty") {
    return "暂无可用数据日";
  }
  if (ctx.mode === "fallback" || ctx.mode === "stale") {
    const actual = formatShortDate(ctx.actualDataDate);
    const reason = ctx.divergenceReason ?? "请求日与实际数据日不一致";
    if (!hasReportDateDivergence(ctx)) {
      const actualLabel =
        actual === GAP ? "实际数据日暂缺" : `实际数据 ${actual}`;
      return `${actualLabel} · 原因：${reason}`;
    }
    const request = formatShortDate(ctx.requestedDate);
    return `请求 ${request} · 实际数据 ${actual} · 原因：${reason}`;
  }
  // exact
  return `报告日 ${ctx.actualDataDate || GAP}`;
}

/**
 * 是否需要显式展示"请求 vs 实际"分歧说明。
 * fallback / stale 必须展示；其余模式用单一报告日即可。
 */
export function hasReportDateDivergence(ctx: HomeReportDateContext): boolean {
  const requestedDate = ctx.requestedDate.trim();
  const actualDataDate = ctx.actualDataDate.trim();
  return (
    (ctx.mode === "fallback" || ctx.mode === "stale") &&
    requestedDate.length > 0 &&
    actualDataDate.length > 0 &&
    requestedDate !== actualDataDate
  );
}
