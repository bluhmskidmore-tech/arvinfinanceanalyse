import type { MarketOverviewCrisis, MarketOverviewCrisisHistoryPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH, localeOrDash } from "../../../pageModel";
import { MARKET_CHART_STATIC_PALETTE, type MarketChartPalette } from "./marketChartPalette";

/** 只识别市场页已知工程诊断标记；未知业务原因保留原文，不做通用文本清洗。 */
export function isMarketTechnicalReason(reason: string | null | undefined): boolean {
  return Boolean(reason && ["receipt.", "/api/", "result_meta", "刷新回执", "required_refresh_step_not_ready",
    "crisis dependency gate blocked", "macro_analysis_core"]
    .some((marker) => reason.includes(marker)));
}

/** 混合原因只替换已知工程标识，保留原句中的日期、缺口和使用限制。 */
export function marketBusinessReason(reason: string | null | undefined, fallback: string): string {
  if (!reason) return fallback;
  if (!isMarketTechnicalReason(reason)) return reason;
  if (!/[\u3400-\u9fff]/.test(reason)) return fallback;
  return reason
    .replace(/\breceipt(?:\.[a-zA-Z_][\w]*)+/g, "相关数据")
    .replace(/\/api\/[^\s，。；、）)]+/g, "数据服务")
    .replaceAll("required_refresh_step_not_ready", "必要数据更新尚未完成")
    .replaceAll("crisis dependency gate blocked", "评分依据尚未通过核验")
    .replaceAll("macro_analysis_core", "宏观分析")
    .replaceAll("result_meta", "来源信息")
    .replaceAll("刷新回执", "更新结果");
}

export function crisisCurrentPublishable(crisis: MarketOverviewCrisis | undefined): boolean {
  return Boolean(crisis && crisis.current_available === true && !crisis.history_only
    && crisis.status !== "unavailable" && crisis.data_status === "complete"
    && crisis.dependency_gate?.status !== "blocked" && crisis.risk_gate?.eligible === true
    && typeof crisis.score === "number" && Number.isFinite(crisis.score));
}

/** Translate the publication reason only; eligibility remains owned by the snapshot. */
export function crisisPublicationReason(crisis: MarketOverviewCrisis | undefined): string {
  const reason = crisis?.reason?.trim();
  if (reason === "crisis dependency gate blocked: required_refresh_step_not_ready") {
    return "必要的宏观数据刷新尚未通过核验，当前评分暂不发布。";
  }
  if (isMarketTechnicalReason(reason)) return marketBusinessReason(reason, "评分数据尚未通过核验，当前评分暂不发布。");
  if (reason && /[\u3400-\u9fff]/.test(reason)) return reason;
  return crisis ? "评分依据尚未通过核验，当前评分暂不发布。" : "评分数据尚未返回。历史与当前读数不会互相补位。";
}

export function riskRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function riskRows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(riskRecord) : [];
}
export function riskText(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : EM_DASH;
}
export function riskNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export const CRISIS_COMPONENT_LABELS: Record<string, string> = {
  equity_vol: "沪深300实现波动", credit_spread: "AA 5Y 与国债 5Y 利差", fx_vol: "美元兑人民币实现波动",
  commodity_vol: "南华商品实现波动", liquidity_stress: "DR007 与 7 天逆回购利差",
};
export const CRISIS_INPUT_LABELS: Record<string, string> = {
  hs300: "沪深300", aa_5y: "AA 5Y 收益率", gov_5y: "国债 5Y 收益率", usdcny: "美元兑人民币",
  nanhua: "南华商品指数", dr007: "DR007", reverse_repo_7d: "7 天逆回购利率",
};
export const COMMODITY_LABELS: Record<string, string> = {
  rebar: "螺纹钢", iron_ore: "铁矿石", copper: "铜", aluminum: "铝", crude_oil: "原油", gold: "黄金",
};

export function crisisHistoryOption(points: MarketOverviewCrisisHistoryPoint[], palette: MarketChartPalette = MARKET_CHART_STATIC_PALETTE): EChartsOption | null {
  if (!points.some(point => Number.isFinite(point.crisis_score))) return null;
  const number = (value: number | null | undefined) => localeOrDash(value, "zh-CN", { maximumFractionDigits: 4 });
  return {
    animation: false,
    grid: { top: 12, right: 14, bottom: 24, left: 36 },
    xAxis: { type: "category", boundaryGap: false, data: points.map(point => point.date), axisLabel: { formatter: (value: string) => value.slice(5), color: palette.inkMuted } },
    yAxis: { type: "value", scale: true, axisLabel: { color: palette.inkMuted }, splitLine: { lineStyle: { color: palette.lineSoft, type: "dashed" } } },
    tooltip: { trigger: "axis", renderMode: "richText", confine: true, formatter: (params: unknown) => {
      const item = Array.isArray(params) ? riskRecord(params[0]) : riskRecord(params);
      const point = points[Number(item.dataIndex)];
      if (!point) return "";
      return `${point.date}\n历史评分 ${number(point.crisis_score)}\n历史分位 ${point.percentile == null ? EM_DASH : `${number(point.percentile)}%`}\n组成项 ${number(point.available_component_count)} / ${number(point.component_count)}\n${point.data_status === "complete" ? "输入完整" : "部分输入或质量待核验"}`;
    } },
    series: [
      { name: "输入完整", type: "line", showSymbol: points.length === 1, connectNulls: false, lineStyle: { width: 2, color: palette.accent }, itemStyle: { color: palette.accent }, data: points.map(point => point.data_status === "complete" ? riskNumber(point.crisis_score) : null) },
      { name: "部分输入", type: "line", showSymbol: true, symbolSize: 3, connectNulls: false, lineStyle: { width: 2, type: "dashed", color: palette.amber }, itemStyle: { color: palette.amber }, data: points.map((point, index) => point.data_status !== "complete" || index < points.length - 1 && points[index + 1]?.data_status !== "complete" || index > 0 && points[index - 1]?.data_status !== "complete" ? riskNumber(point.crisis_score) : null) },
    ],
  };
}
