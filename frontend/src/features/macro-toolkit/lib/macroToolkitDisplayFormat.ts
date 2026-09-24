import type {
  MacroToolkitAShareRiskPayload,
  MacroToolkitIndicator,
  MacroToolkitPrimarySignal,
  MacroToolkitRunResponse,
  MacroToolkitSignalCard,
  MacroToolkitSourceCheck,
} from "../../../api/macroToolkitClient";
import { statusLabel } from "./macroToolkitPanelShared";

export const BUSINESS_EVIDENCE_LABELS: Record<string, string> = {
  analytical: "证据口径已归档",
  mock: "模拟口径",
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

const OBSERVATION_EVIDENCE_KEY_LABELS: Record<string, string> = {
  score: "评分",
  regime: "状态",
  percentile: "历史分位",
  percentile_1y: "近一年分位",
  state: "状态",
  trend: "趋势",
  stress: "压力",
  short_gap_ratio: "短期缺口占比",
  negative_buckets: "负缺口桶数",
  risk: "风险",
  bond_fx_corr: "债汇相关",
  bond_oil_corr: "债商相关",
  direction: "方向",
  phase: "周期",
  growth: "增长",
  inflation: "通胀",
  liquidity: "流动性",
  top: "首选资产",
  avg: "复合均值",
  bullish: "多头数",
  bearish: "空头数",
  shape: "曲线形态",
  as_of: "数据日",
  warning: "预警",
  avg_corr: "平均相关",
  assets: "资产数",
  vol: "波动",
  "AAA spread": "AAA利差",
  AAA: "AAA利差",
  total_mv: "总市值",
  duration: "久期",
  worst_pnl: "最差损益",
  "5d": "5日变动",
};

/** 证据值里的英文枚举 → 中文（LOW/MEDIUM/HIGH、Unavailable 等展示层直译）。 */
const OBSERVATION_EVIDENCE_VALUE_LABELS: Record<string, string> = {
  Unavailable: "不可用",
  unavailable: "不可用",
  LOW: "低",
  MEDIUM: "中",
  HIGH: "高",
  range: "区间",
};

/** total_mv 一类 14 位金额（元）缩写为亿元；非纯数值原样返回。 */
function formatEvidenceAmountYi(value: string) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || Math.abs(numeric) < 1e8) {
    return value;
  }
  return `${(numeric / 1e8).toFixed(2)} 亿元`;
}

export function formatCapabilityEvidenceValue(key: string, value: string) {
  const trimmed = value.trim();
  if (key === "total_mv") {
    return formatEvidenceAmountYi(trimmed);
  }
  return OBSERVATION_EVIDENCE_VALUE_LABELS[trimmed] ?? trimmed;
}

const EVIDENCE_PAIR_PATTERN = /^([A-Za-z0-9][A-Za-z0-9 _-]*?)=(.+)$/;

/** 后端证据串里的 `key=value` 英文键映射为中文标签；未知键仅把 = 换成空格。 */
export function formatObservationEvidenceItem(item: string) {
  const pair = item.match(EVIDENCE_PAIR_PATTERN);
  if (!pair) {
    return item;
  }
  const key = pair[1]!.trim();
  const label = OBSERVATION_EVIDENCE_KEY_LABELS[key] ?? key;
  return `${label} ${formatCapabilityEvidenceValue(key, pair[2]!)}`;
}

/**
 * 04 功能结果卡证据行：`key=value` token 直出改中文键名 + 格式化值
 * （亿元缩写、Unavailable→不可用、LOW/MEDIUM/HIGH→低/中/高）；
 * 原始 kv 串由调用方收进 title。
 */
export function formatCapabilityEvidenceList(items: string[]) {
  return items.map((item) => formatObservationEvidenceItem(item.replace(/\s+/g, " ").trim()));
}

/** 04 功能结果卡主值里的英文枚举值（如「联动风险 MEDIUM」）→ 中文；原值收 title。 */
export function formatCapabilityMetricValue(value: string | number) {
  if (typeof value === "number") {
    return String(value);
  }
  return OBSERVATION_EVIDENCE_VALUE_LABELS[value.trim()] ?? value;
}

/** Hason 框架英文名的展示层中文名；未知名称原样返回（原文由调用方收 title）。 */
const HASON_FRAMEWORK_DISPLAY_NAMES: Record<string, string> = {
  "Hason macro hedge due-diligence framework": "Hason 宏观对冲尽调框架",
};

export function hasonFrameworkDisplayName(name: string) {
  return HASON_FRAMEWORK_DISPLAY_NAMES[name.trim()] ?? name;
}

/** 操作台区题脚本中文名；未登记脚本回落「脚本执行」，snake 名降副行代码样式。 */
const SCRIPT_DISPLAY_LABELS: Record<string, string> = {
  signal_aggregator: "信号聚合脚本",
  risk_monitor: "风险监控脚本",
  crisis_score_cn: "危机评分脚本",
  merrill_clock_cn: "美林时钟脚本",
  crowding_cn: "拥挤度脚本",
};

export function scriptDisplayLabel(name: string | null | undefined) {
  if (!name) {
    return null;
  }
  return SCRIPT_DISPLAY_LABELS[name] ?? "脚本执行";
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
    )
    .map(formatObservationEvidenceItem);
  if (readableItems.length) {
    return readableItems.join(" / ");
  }
  return items.length ? `${items.length} 条观察证据已归纳` : "观察证据待补齐";
}

const CRISIS_COMPONENT_ZH_LABELS: Record<string, string> = {
  equity_vol: "沪深300波动",
  credit_spread: "信用利差",
  fx_vol: "美元兑人民币波动",
  commodity_vol: "南华商品波动",
  liquidity_stress: "流动性压力",
};

/** Crisis Score 首屏卡的组件贡献摘要中文版；英文原串由调用方收进 title。 */
export function formatCrisisComponentSummaryZh(
  components: readonly { key: string; label?: string | null; z_score?: number | null }[],
  limit = 2,
): string | null {
  const ranked = components
    .filter((component) => typeof component.z_score === "number" && Number.isFinite(component.z_score))
    .sort((left, right) => Math.abs(right.z_score!) - Math.abs(left.z_score!))
    .slice(0, limit);
  if (!ranked.length) {
    return null;
  }
  const parts = ranked.map((component) => {
    const label = CRISIS_COMPONENT_ZH_LABELS[component.key] ?? component.label?.trim() ?? component.key;
    return `${label} z ${component.z_score!.toFixed(2)}`;
  });
  return `主要贡献：${parts.join("；")}`;
}

export function isObservationOutputSignal(card: MacroToolkitSignalCard) {
  return card.key === "outputs" || /脚本产物|输出文件|output/i.test(card.title);
}

/**
 * 主信号解析：只按后端 `primary_signal.key` 取卡。
 *
 * Crisis 是 z-score（2 已是高风险），A股踩踏是 0-100 分，流动性等方向卡是固定
 * 离散状态分，三者不可比较；风险优先规则由后端
 * rv_macro_primary_signal_risk_first_v1 声明。字段缺失、非 selected、key 悬空
 * 或指向 outputs 卡时一律返回 null，前端不得自行排序兜底。
 */
export function pickPrimarySignal(
  cards: MacroToolkitSignalCard[],
  primarySignal: MacroToolkitPrimarySignal | undefined,
): MacroToolkitSignalCard | null {
  if (primarySignal?.selection_status !== "selected" || !primarySignal.key) {
    return null;
  }
  const card = cards.find((item) => item.key === primarySignal.key) ?? null;
  if (!card || isObservationOutputSignal(card)) {
    return null;
  }
  return card;
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
