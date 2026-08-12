import type {
  MacroToolkitAShareRiskPayload,
  MacroToolkitIndicator,
  MacroToolkitRunResponse,
  MacroToolkitSignalCard,
  MacroToolkitSourceCheck,
} from "../../../api/macroToolkitClient";
import { statusLabel } from "./macroToolkitPanelShared";

export const BUSINESS_EVIDENCE_LABELS: Record<string, string> = {
  analytical: "证据口径已归档",
  choice: "宏观数据源",
  tushare: "行情与因子快照",
  fact_choice_macro_daily: "宏观数据源",
  choice_market_snapshot: "行情快照",
  choice_stock_daily_observation: "行情与因子快照",
  choice_stock_factor_snapshot: "行情与因子快照",
  choice_stock_limit_quality: "市场风险证据",
  fact_commodity_futures_daily: "商品期货证据",
  bond_futures_history: "席位排名证据",
  "bond_futures_history.csv": "席位排名证据",
  fact_cffex_member_rank_daily: "席位排名证据",
  vw_cffex_member_rank_daily: "席位排名证据",
  fx_daily_mid: "汇率中间价证据",
  fact_formal_yield_curve_daily: "曲线利率证据",
  std_external_macro_daily: "外部宏观证据",
  system_macro_sources: "宏观数据源",
};

export function toneTagColor(tone: MacroToolkitSignalCard["tone"]) {
  if (tone === "positive") return "green";
  if (tone === "negative") return "red";
  if (tone === "missing") return "default";
  return "blue";
}

export function riskLevelColor(level: MacroToolkitAShareRiskPayload["risk_level"]) {
  if (level === "green") return "green";
  if (level === "yellow") return "gold";
  if (level === "orange") return "orange";
  if (level === "red") return "red";
  return "default";
}

export function riskLevelTone(level: MacroToolkitAShareRiskPayload["risk_level"]): MacroToolkitSignalCard["tone"] {
  if (level === "green") return "positive";
  if (level === "unknown") return "missing";
  return level === "yellow" ? "neutral" : "negative";
}

export function formatBusinessEvidenceLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim();
  if (!normalized) {
    return "";
  }
  return BUSINESS_EVIDENCE_LABELS[normalized] ?? normalized;
}

export function formatBusinessEvidenceList(values: (string | null | undefined)[] | null | undefined, fallback = "证据待确认") {
  const labels = (values ?? [])
    .map(formatBusinessEvidenceLabel)
    .filter(Boolean);
  const uniqueLabels = Array.from(new Set(labels));
  return uniqueLabels.length ? uniqueLabels.join(" / ") : fallback;
}

export function formatChange(change: number | null, changePct: number | null) {
  if (change === null && changePct === null) {
    return "无可比";
  }
  if (changePct !== null) {
    return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  }
  return `${change! >= 0 ? "+" : ""}${change!.toFixed(4)}`;
}

export function formatRiskMetric(value: number | null | undefined, format?: "percent" | "ratio") {
  if (value == null) {
    return "缺失";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (format === "ratio") {
    return `${value.toFixed(2)}x`;
  }
  return Number.isInteger(value) ? value.toString() : value.toFixed(2);
}

export const GROUP_LABELS: Record<string, string> = {
  allocation: "配置",
  credit: "信用",
  diagnostic: "诊断",
  macro_signal: "宏观信号",
  market_regime: "市场状态",
  news: "新闻",
  rates: "利率",
  report: "报告",
  risk: "风险",
};

export function groupLabel(group: string) {
  return GROUP_LABELS[group] ?? group;
}

export function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

export function formatSourceCheck(check: MacroToolkitSourceCheck) {
  if (!check.latest) {
    return "未命中";
  }
  return `${check.latest.series_id} · ${check.latest.date}`;
}

export function statusTone(status: MacroToolkitRunResponse["status"]) {
  if (status === "completed") return "success";
  if (status === "timeout") return "warning";
  return "error";
}

export function chainRunAlertType(status: string): "success" | "warning" | "error" | "info" {
  if (status === "failed" || status === "timeout") return "error";
  if (status === "degraded") return "warning";
  if (status === "completed" || status === "dry_run") return "success";
  return "info";
}

export function formatAnalysisBasisLabel(basis: string | null | undefined) {
  if (!basis) {
    return "口径待确认";
  }
  if (basis === "analytical") {
    return "分析口径";
  }
  if (basis === "read_only_shadow") {
    return "只读影子口径";
  }
  if (basis === "mock") {
    return "模拟口径";
  }
  return basis;
}

export function formatQualityFlagLabel(flag: string | null | undefined) {
  if (!flag) {
    return "质量待确认";
  }
  if (flag === "ok") {
    return "质量可用";
  }
  if (flag === "warning") {
    return "质量待复核";
  }
  if (flag === "error") {
    return "质量阻断";
  }
  return statusLabel(flag);
}

export function formatObservationRecommendation(action: string | null | undefined) {
  const normalized = (action ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "等待观察结论更新";
  }
  if (/补齐|缺失|missing|Choice|Tushare/i.test(normalized)) {
    return "先补齐关键输入，再复核观察结论";
  }
  if (/signal_aggregator|risk_monitor|脚本|运行/i.test(normalized)) {
    return "维持观察，等待交易层信号确认";
  }
  return normalized;
}

export function formatObservationEvidence(evidence: string[] | null | undefined) {
  const items = evidence ?? [];
  const readableItems = items
    .map((item) => item.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .filter(
      (item) =>
        !/final_signal\.csv|signal_aggre|risk_monitor|脚本|Choice\/Tushare|macro_toolkit|analytical|capability_results|source_checks/i.test(
          item,
        ),
    );
  if (readableItems.length) {
    return readableItems.join(" / ");
  }
  return items.length ? `${items.length} 条观察证据已归纳` : "观察证据待补齐";
}

export function isObservationOutputSignal(card: MacroToolkitSignalCard) {
  return card.key === "outputs" || /脚本产物|输出文件|output/i.test(card.title);
}

export function formatObservationSignalTitle(card: MacroToolkitSignalCard) {
  if (isObservationOutputSignal(card)) {
    return "分析证据";
  }
  return card.title;
}

export function formatObservationSignalStance(card: MacroToolkitSignalCard) {
  if (isObservationOutputSignal(card)) {
    return card.stance === "已生成" ? "已归纳" : "待确认";
  }
  return card.stance;
}

export function formatSignalCardScore(card: MacroToolkitSignalCard): string | number {
  if (card.score !== null && card.score !== undefined) {
    return card.score;
  }
  if (card.stance === "完整结果待加载") {
    return "待加载";
  }
  if (card.key === "a_share_stampede_risk" && card.stance === "数据不足" && card.tone === "missing") {
    return "待加载";
  }
  return "缺失";
}

export function latestIndicatorDate(indicators: MacroToolkitIndicator[]) {
  const dates = indicators
    .map((indicator) => indicator.latest_date)
    .filter((date): date is string => Boolean(date))
    .sort();
  return dates.at(-1) ?? "缺失";
}

export function formatQueryError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "宏观工具接口暂不可用";
}

export function isMacroToolkitReadForbidden(message: string) {
  return /not allowed/i.test(message) && /read\s+macro_toolkit/i.test(message);
}

export function isReadyStatus(status: string) {
  return ["current", "ready", "library_ready", "complete", "wired", "visible", "ok"].includes(status);
}
