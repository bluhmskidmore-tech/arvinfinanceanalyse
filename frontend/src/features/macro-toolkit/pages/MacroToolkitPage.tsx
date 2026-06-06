import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CopyOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Checkbox, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitCapability,
  MacroToolkitCapabilityResult,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitCommodityFuturesRefreshStatus,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitChoiceStockRefreshPermission,
  MacroToolkitAShareRiskPayload,
  MacroToolkitAnalysisPayload,
  MacroToolkitDataHealth,
  MacroToolkitHasonStrategy,
  MacroToolkitInputEvidence,
  MacroToolkitIndicator,
  MacroToolkitOutputFile,
  MacroToolkitRunResponse,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitShadowPortfolio,
  MacroToolkitShadowPortfolioHolding,
  MacroToolkitShadowPortfolioPeriodReturn,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSourceCheck,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import {
  DataStatusStrip,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";

import "./MacroToolkitPage.css";

const GROUP_LABELS: Record<string, string> = {
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

const EMPTY_SCRIPTS: MacroToolkitScriptRecord[] = [];
const COMMITTEE_EVIDENCE_SCRIPT_PRIORITY = [
  "signal_aggregator",
  "risk_monitor",
  "crisis_score_cn",
  "merrill_clock_cn",
  "crowding_cn",
] as const;
const MACRO_TOOLKIT_ANALYSIS_KIND = "macro_toolkit.analysis";
const MACRO_TOOLKIT_UI_RULE_VERSION = "rv_macro_toolkit_ui_v1";
const MACRO_TOOLKIT_READ_STALE_MS = 60_000;
const MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS = 1_500;
const MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY = ["macro-toolkit", "analysis", "full"] as const;
const MACRO_COMMODITY_SHADOW_RULE_VERSION = "shadow_rule_v1";
const MACRO_COMMODITY_SHADOW_MIN_SAMPLES = 20;
const MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES = 5;
const MACRO_COMMODITY_SHADOW_MIN_CORRELATION = 0.2;
const MACRO_COMMODITY_SUGGESTED_REFRESH_LOOKBACK_DAYS = 45;
const MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT = 4;
const BUSINESS_EVIDENCE_LABELS: Record<string, string> = {
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
const MACRO_COMMODITY_PRODUCT_OPTIONS = [
  { value: "RB", label: "螺纹钢", description: "黑色链条" },
  { value: "I", label: "铁矿石", description: "黑色链条" },
  { value: "CU", label: "铜", description: "有色金属" },
  { value: "AL", label: "铝", description: "有色金属" },
  { value: "SC", label: "原油", description: "能源" },
  { value: "AU", label: "黄金", description: "避险资产" },
  { value: "NHCI", label: "南华指数", description: "Crisis Score 输入" },
] as const;
const DEFAULT_MACRO_COMMODITY_PRODUCTS = MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => option.value);
const MACRO_COMMODITY_FIELD_TO_PRODUCT: Record<string, string> = {
  rebar: "RB",
  iron_ore: "I",
  copper: "CU",
  aluminum: "AL",
  crude_oil: "SC",
  gold: "AU",
};
const NANHUA_COMMODITY_PRODUCT_CODE = "NHCI";
const NANHUA_CRISIS_ALIAS = "NH0100.NHF";
const NANHUA_SYSTEM_SERIES_ID = "NHCI.NH";

type MacroToolkitPageMode = "toolkit" | "observation";
type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];
type CommodityRefreshOptions = {
  dryRun?: boolean;
  products?: string[];
  suggestedSelection?: string[];
  startDate?: string;
};
type CommodityShortfallChange = {
  field: string;
  label: string;
  before: string;
  after: string;
  remainingGap: number;
  resolved: boolean;
};
type CommodityShortfallEstimate = CommodityShortfallChange & {
  estimatedRows: number;
  canFill: boolean;
};
type CommodityRefreshEvidenceChain = {
  suggestedProducts: string[];
  refreshedProducts: string[];
  fullReloaded: boolean;
};
type CrisisGapRepairFeedback = {
  groupKey: CrisisGapGroupKey;
  groupLabel: string;
  status: "pending" | "resolved" | "partial" | "failed";
  message: string;
  detail: string;
};

type MacroToolkitGovernanceFocusKey = "evidence" | "data-health" | "analysis-scope" | "execution" | "artifacts";

type MacroToolkitGovernanceFocusItem = {
  key: MacroToolkitGovernanceFocusKey;
  label: string;
  focusTitle: string;
  href: string;
  value: string | number;
  detail: string;
  status: string;
  tone: MacroToolkitSignalCard["tone"];
  icon: ReactNode;
};

type MacroToolkitEvidenceBookRow = {
  key: string;
  subject: string;
  support: string;
  gap: string;
  owner: string;
  href: string;
};

type MacroToolkitCommitteePackItem = MacroToolkitEvidenceBookRow & {
  packSubject: string;
  status: "archived" | "blocking" | "pending";
  statusLabel: string;
  receipt: MacroToolkitActionReceipt | null;
  receiptConfirmed: boolean;
};

type MacroToolkitCommitteeChecklistItem = MacroToolkitEvidenceBookRow & {
  condition: string;
  status: "pass" | "block" | "pending";
  statusLabel: string;
  action: string;
};

type MacroToolkitCommitteeWorkQueueItem = MacroToolkitCommitteeChecklistItem & {
  priorityLabel: "阻断项" | "待确认项";
  executionHref: string;
};

type MacroToolkitEvidenceBookRowAction = {
  label: string;
  status: string;
  kind: "button" | "link";
  href?: string;
  busy?: boolean;
  disabled?: boolean;
  onClick?: () => void;
};

type MacroToolkitSignoffLaneItem = {
  owner: string;
  status: "approved" | "blocked" | "pending" | "reviewed";
  statusLabel: string;
  subject: string;
};

type MacroToolkitActionReceiptStatus = "idle" | "running" | "completed" | "warning" | "failed";

type MacroToolkitActionReceipt = {
  id: string;
  action: string;
  status: MacroToolkitActionReceiptStatus;
  time: string;
  target: string;
  artifact: string;
  nextStep: string;
  decisionImpact: string;
  reviewOwner: string;
  evidenceEntry: string;
  evidenceHref: string;
};

type MacroToolkitDeepEvidenceQueueItem = {
  key: string;
  label: string;
  value: string;
  detail: string;
  href: string;
};

const EMPTY_ACTION_RECEIPT: MacroToolkitActionReceipt = {
  id: "idle",
  action: "等待执行",
  status: "idle",
  time: "未执行",
  target: "尚未选择",
  artifact: "暂无输出",
  nextStep: "先选择需要刷新的对象或脚本",
  decisionImpact: "等待动作",
  reviewOwner: "待分配",
  evidenceEntry: "Action Console",
  evidenceHref: "#macro-toolkit-operations-console",
};

let macroToolkitActionReceiptSequence = 0;

function nextActionReceiptId(kind: string) {
  macroToolkitActionReceiptSequence += 1;
  return `${kind}:${macroToolkitActionReceiptSequence}`;
}

function actionReceiptDecisionFields(
  kind:
    | "script"
    | "cffex"
    | "choice-stock"
    | "commodity-dry-run"
    | "commodity-refresh"
    | "source-backfill"
    | "full-analysis",
) {
  const fields = {
    script: {
      decisionImpact: "脚本产物闭环",
      reviewOwner: "宏观策略负责人",
      evidenceEntry: "脚本产物",
      evidenceHref: "#macro-toolkit-script-artifact-detail",
    },
    cffex: {
      decisionImpact: "期指席位结构",
      reviewOwner: "数据运营负责人",
      evidenceEntry: "CFFEX席位状态",
      evidenceHref: "#macro-toolkit-cffex-detail",
    },
    "source-backfill": {
      decisionImpact: "来源数据补齐",
      reviewOwner: "数据运营负责人",
      evidenceEntry: "来源补齐",
      evidenceHref: "#macro-toolkit-data-health-detail",
    },
    "full-analysis": {
      decisionImpact: "完整证据复核",
      reviewOwner: "宏观策略负责人",
      evidenceEntry: "完整分析回执",
      evidenceHref: "#macro-toolkit-data-health-detail",
    },
    "choice-stock": {
      decisionImpact: "A股策略供数",
      reviewOwner: "权益策略负责人",
      evidenceEntry: "策略展示",
      evidenceHref: "#macro-toolkit-strategy-detail",
    },
    "commodity-dry-run": {
      decisionImpact: "商品刷新预案",
      reviewOwner: "数据运营负责人",
      evidenceEntry: "商品期货刷新",
      evidenceHref: "#macro-toolkit-commodity-detail",
    },
    "commodity-refresh": {
      decisionImpact: "商品冲击证据",
      reviewOwner: "数据运营负责人",
      evidenceEntry: "商品期货刷新",
      evidenceHref: "#macro-toolkit-commodity-detail",
    },
  } satisfies Record<string, Pick<MacroToolkitActionReceipt, "decisionImpact" | "reviewOwner" | "evidenceEntry" | "evidenceHref">>;
  return fields[kind];
}

const MACRO_SOURCE_BACKFILL_ALIASES = new Set(["M0041813"]);

type MacroToolkitPageProps = {
  mode?: MacroToolkitPageMode;
};

function normalizeMacroSourceBackfillAlias(alias: string | null | undefined) {
  return alias?.trim().toUpperCase() ?? "";
}

function canRefreshMacroSourceBackfill(item: MacroToolkitRepairItem) {
  return (
    item.action?.kind === "source_backfill_required" &&
    MACRO_SOURCE_BACKFILL_ALIASES.has(normalizeMacroSourceBackfillAlias(item.alias))
  );
}

function needsManualReviewEscalation(item: MacroToolkitRepairItem) {
  return Boolean(item.action?.kind === "source_backfill_required" && !canRefreshMacroSourceBackfill(item));
}

function needsFullAnalysisReview(item: MacroToolkitRepairItem) {
  return item.action?.kind === "load_full_analysis";
}

function repairTriageLaneItems(repairItems: MacroToolkitRepairItem[]) {
  const autoRefreshItems = repairItems.filter(canRefreshMacroSourceBackfill);
  const manualEscalationItems = repairItems.filter(needsManualReviewEscalation);
  const fullAnalysisItems = repairItems.filter(needsFullAnalysisReview);
  return [
    {
      key: "auto-refresh",
      label: "自动补齐",
      count: autoRefreshItems.length,
      owner: "数据运营负责人",
      action: "执行来源补齐",
      sample: formatRepairTriageSample(autoRefreshItems),
    },
    {
      key: "manual-escalation",
      label: "人工升级",
      count: manualEscalationItems.length,
      owner: "数据运营负责人",
      action: "升级处理",
      sample: formatRepairTriageSample(manualEscalationItems),
    },
    {
      key: "full-analysis",
      label: "能力复核",
      count: fullAnalysisItems.length,
      owner: "宏观策略负责人",
      action: "复核完整分析",
      sample: formatRepairTriageSample(fullAnalysisItems),
    },
  ];
}

function formatRepairTriageSample(items: MacroToolkitRepairItem[]) {
  const firstItem = items[0];
  if (!firstItem) {
    return "无待处理项";
  }
  return `${formatDataHealthRepairLabel(firstItem, firstItem.type === "deferred")}${
    firstItem.alias ? ` / ${firstItem.alias}` : ""
  }`;
}

function repairItemFocusKey(item: MacroToolkitRepairItem) {
  return normalizeMacroSourceBackfillAlias(item.alias) || item.key || item.label || item.type || "repair";
}

function sameCommodityProducts(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

function groupLabel(group: string) {
  return GROUP_LABELS[group] ?? group;
}

function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function formatSourceCheck(check: MacroToolkitSourceCheck) {
  if (!check.latest) {
    return "未命中";
  }
  return `${check.latest.series_id} · ${check.latest.date}`;
}

function statusTone(status: MacroToolkitRunResponse["status"]) {
  if (status === "completed") return "success";
  if (status === "timeout") return "warning";
  return "error";
}

function toneTagColor(tone: MacroToolkitSignalCard["tone"]) {
  if (tone === "positive") return "green";
  if (tone === "negative") return "red";
  if (tone === "missing") return "default";
  return "blue";
}

function riskLevelColor(level: MacroToolkitAShareRiskPayload["risk_level"]) {
  if (level === "green") return "green";
  if (level === "yellow") return "gold";
  if (level === "orange") return "orange";
  if (level === "red") return "red";
  return "default";
}

function riskLevelTone(level: MacroToolkitAShareRiskPayload["risk_level"]): MacroToolkitSignalCard["tone"] {
  if (level === "green") return "positive";
  if (level === "unknown") return "missing";
  return level === "yellow" ? "neutral" : "negative";
}

function statusLabel(status: string) {
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

function statusColor(status: string) {
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

function compactText(text: string | null | undefined, maxLength = 34) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function formatBusinessEvidenceLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim();
  if (!normalized) {
    return "";
  }
  return BUSINESS_EVIDENCE_LABELS[normalized] ?? normalized;
}

function formatBusinessEvidenceList(values: (string | null | undefined)[] | null | undefined, fallback = "证据待确认") {
  const labels = (values ?? [])
    .map(formatBusinessEvidenceLabel)
    .filter(Boolean);
  const uniqueLabels = Array.from(new Set(labels));
  return uniqueLabels.length ? uniqueLabels.join(" / ") : fallback;
}

function formatAnalysisBasisLabel(basis: string | null | undefined) {
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

function formatQualityFlagLabel(flag: string | null | undefined) {
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

function governanceFocusFromEvidenceHref(href: string): MacroToolkitGovernanceFocusKey {
  if (href === "#macro-toolkit-data-health-detail") return "data-health";
  if (href === "#macro-toolkit-tool-execution-detail") return "execution";
  if (href === "#macro-toolkit-strategy-detail") return "execution";
  if (href === "#macro-toolkit-operations-actions") return "execution";
  return "evidence";
}

function committeeWorkQueueExecutionHref(item: MacroToolkitCommitteeChecklistItem) {
  if (item.key === "tool-execution") return "#macro-toolkit-operations-actions";
  return item.href;
}

function committeePackSubmissionImpact(item: MacroToolkitCommitteePackItem) {
  if (item.receiptConfirmed) return "可提交复核";
  if (item.receipt) return "回执待签核";
  if (item.status === "blocking") return "阻断最终提交";
  if (item.status === "pending") return "待补证据后提交";
  return "可进入复核";
}

function committeePackReceiptStatus(item: MacroToolkitCommitteePackItem) {
  if (item.receiptConfirmed) return "已签核";
  if (item.receipt) return "回执待复核";
  if (item.status === "archived") return "证据留痕";
  return "等待回执";
}

function committeeEvidenceBookDeliveryStatus(item: MacroToolkitCommitteePackItem) {
  if (!item.receipt && item.status === "blocking") return "阻断提交";
  return item.statusLabel;
}

function committeePackEvidenceEntryLabel(item: MacroToolkitCommitteePackItem) {
  if (!item.receipt) return "证据入口";
  return item.receiptConfirmed ? "签核证据" : "回执入口";
}

function latestCompletedReceiptForOwner(receipts: MacroToolkitActionReceipt[], owner: string) {
  return receipts.find((receipt) => receipt.status === "completed" && receipt.reviewOwner === owner) ?? null;
}

function latestCompletedReceiptForQueueItem(
  receipts: MacroToolkitActionReceipt[],
  item: MacroToolkitCommitteeWorkQueueItem,
) {
  return receipts.find((receipt) => receiptMatchesCommitteeQueueItem(receipt, item)) ?? null;
}

function receiptMatchesCommitteeQueueItem(
  receipt: MacroToolkitActionReceipt,
  item: MacroToolkitCommitteeWorkQueueItem,
) {
  return receiptMatchesCommitteeEvidence(receipt, item.key, item.href, item.owner, item.executionHref);
}

function receiptMatchesCommitteeEvidence(
  receipt: MacroToolkitActionReceipt,
  key: string,
  href: string,
  owner: string,
  executionHref?: string,
) {
  if (receipt.status !== "completed") {
    return false;
  }
  if (receipt.evidenceHref === href || receipt.evidenceHref === executionHref) {
    return true;
  }
  if (key === "strategy-supply") {
    return receipt.evidenceHref === "#macro-toolkit-strategy-detail";
  }
  if (key === "tool-execution") {
    return [
      "#macro-toolkit-script-artifact-detail",
      "#macro-toolkit-cffex-detail",
      "#macro-toolkit-commodity-detail",
    ].includes(receipt.evidenceHref);
  }
  if (key === "data-health") {
    return receipt.evidenceHref === "#macro-toolkit-data-health-detail";
  }
  return false;
}

function committeeSignoffLaneItems(
  items: MacroToolkitCommitteeWorkQueueItem[],
  receipts: MacroToolkitActionReceipt[] = [],
  confirmedReceiptIds: Set<string> = new Set(),
): MacroToolkitSignoffLaneItem[] {
  return ["宏观策略负责人", "数据运营负责人", "权益策略负责人"].map((owner) => {
    const ownerItems = items.filter((item) => item.owner === owner);
    const blocker = ownerItems.find((item) => item.status === "block");
    const pending = ownerItems.find((item) => item.status === "pending");
    const reviewedItem = ownerItems.find((item) => latestCompletedReceiptForQueueItem(receipts, item));
    const reviewedReceipt = reviewedItem ? latestCompletedReceiptForQueueItem(receipts, reviewedItem) : null;
    if (reviewedItem && reviewedReceipt && confirmedReceiptIds.has(reviewedReceipt.id) && !blocker) {
      return {
        owner,
        status: "reviewed",
        statusLabel: "已签核确认",
        subject: reviewedReceipt.evidenceEntry,
      };
    }
    if (reviewedItem && reviewedReceipt && !blocker) {
      return {
        owner,
        status: "reviewed",
        statusLabel: "已留痕复核",
        subject: reviewedReceipt.evidenceEntry,
      };
    }
    const completedReceipt = latestCompletedReceiptForOwner(receipts, owner);
    if (completedReceipt && !blocker && !pending) {
      return {
        owner,
        status: "reviewed",
        statusLabel: confirmedReceiptIds.has(completedReceipt.id) ? "已签核确认" : "已留痕复核",
        subject: completedReceipt.evidenceEntry,
      };
    }
    if (blocker) {
      return {
        owner,
        status: "blocked",
        statusLabel: "阻断签核",
        subject: blocker.condition,
      };
    }
    if (pending) {
      return {
        owner,
        status: "pending",
        statusLabel: "待补证据",
        subject: pending.condition,
      };
    }
    return {
      owner,
      status: "approved",
      statusLabel: "可签核",
      subject: "证据留痕",
    };
  });
}

function pickDefaultCommitteeScript(scripts: MacroToolkitScriptRecord[]) {
  const availableScripts = scripts.filter((script) => script.available);
  const runnableScripts = availableScripts.length ? availableScripts : scripts;
  for (const preferredName of COMMITTEE_EVIDENCE_SCRIPT_PRIORITY) {
    const preferredScript = runnableScripts.find((script) => script.name === preferredName);
    if (preferredScript) {
      return preferredScript;
    }
  }
  return runnableScripts[0] ?? null;
}

function formatObservationRecommendation(action: string | null | undefined) {
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

function formatObservationEvidence(evidence: string[] | null | undefined) {
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

function isObservationOutputSignal(card: MacroToolkitSignalCard) {
  return card.key === "outputs" || /脚本产物|输出文件|output/i.test(card.title);
}

function formatObservationSignalTitle(card: MacroToolkitSignalCard) {
  if (isObservationOutputSignal(card)) {
    return "分析证据";
  }
  return card.title;
}

function formatObservationSignalStance(card: MacroToolkitSignalCard) {
  if (isObservationOutputSignal(card)) {
    return card.stance === "已生成" ? "已归纳" : "待确认";
  }
  return card.stance;
}

function macroStatusIconTone(tone: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing") {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "missing") return "missing";
  return "neutral";
}

function MacroStatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing";
  children: ReactNode;
}) {
  return (
    <span className={`macro-toolkit-status-icon macro-toolkit-status-icon--${macroStatusIconTone(tone)}`}>
      {children}
    </span>
  );
}

function MacroToolkitContractBoundary({
  formalUseAllowed,
  resultKind,
  ruleVersion,
  plainLanguage = false,
}: {
  formalUseAllowed?: boolean;
  resultKind?: string;
  ruleVersion?: string;
  plainLanguage?: boolean;
}) {
  const resultKindText = plainLanguage ? "宏观分析结果" : resultKind ?? MACRO_TOOLKIT_ANALYSIS_KIND;
  const versionText = plainLanguage ? "规则版本已记录" : ruleVersion ?? MACRO_TOOLKIT_UI_RULE_VERSION;
  return (
    <div
      className="macro-toolkit-contract-boundary"
      data-testid="macro-toolkit-contract-boundary"
      aria-label="宏观工具口径边界"
    >
      <span>
        <SafetyCertificateOutlined />
        分析/工具口径
      </span>
      <strong>{formalUseAllowed ? "正式可用" : "非正式口径"}</strong>
      <small>{resultKindText}</small>
      <small>{versionText}</small>
    </div>
  );
}

function latestIndicatorDate(indicators: MacroToolkitIndicator[]) {
  const dates = indicators
    .map((indicator) => indicator.latest_date)
    .filter((date): date is string => Boolean(date))
    .sort();
  return dates.at(-1) ?? "缺失";
}

function IndicatorObservationSummary({ indicators }: { indicators: MacroToolkitIndicator[] }) {
  const usableIndicators = indicators.filter((indicator) => indicator.quality === "ok");
  const missingIndicators = indicators.length - usableIndicators.length;
  const visibleIndicators = indicators.slice(0, 4);
  return (
    <div className="macro-toolkit-indicator-observation" aria-label="指标证据摘要">
      <div className="macro-toolkit-indicator-observation__head">
        <div>
          <span>指标证据摘要</span>
          <strong>数据源已确认，细节留在完整工具页</strong>
        </div>
        <Tag color={missingIndicators > 0 ? "gold" : "green"}>
          {usableIndicators.length}/{indicators.length || 0} 可用
        </Tag>
      </div>
      <div className="macro-toolkit-indicator-observation__grid">
        <MetricTile
          icon={<DatabaseOutlined />}
          label="指标覆盖"
          value={`${usableIndicators.length}/${indicators.length || 0}`}
          detail={missingIndicators ? `${missingIndicators} 个指标待补齐。` : "当前观察指标均可用。"}
          tone={missingIndicators ? "missing" : "neutral"}
          detailMaxLength={40}
        />
        <MetricTile
          icon={<ClockCircleOutlined />}
          label="最新日期"
          value={latestIndicatorDate(indicators)}
          detail="用于观察页结论排序，不展示源表审计。"
          tone="neutral"
          detailMaxLength={40}
        />
      </div>
      <div className="macro-toolkit-indicator-observation__list">
        {visibleIndicators.map((indicator) => (
          <div
            className={[
              "macro-toolkit-indicator-observation__item",
              indicator.quality === "missing" ? "macro-toolkit-indicator-observation__item--missing" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={indicator.alias}
          >
            <div>
              <span>{indicator.label}</span>
              <strong>{formatValue(indicator.latest_value, indicator.unit)}</strong>
            </div>
            <small>
              {indicator.group} · {formatChange(indicator.change, indicator.change_pct)} ·{" "}
              {indicator.latest_date ?? "日期缺失"}
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

function observationSignalRiskSummary(
  signal: MacroToolkitSignalCard | null,
  risk: MacroToolkitAShareRiskPayload | undefined,
  isLoading: boolean,
) {
  if (isLoading) {
    return "观察证据加载中，暂不形成合读判断。";
  }
  if (!signal && !risk) {
    return "主信号和风险预警待确认，当前不形成观察判断。";
  }
  if (!risk) {
    return "主信号已返回，风险证据延后确认；先不放大信号解释权重。";
  }
  if (!signal) {
    return "风险预警已返回，主信号待确认；先按风险边界观察。";
  }
  const signalTone = signal.tone;
  const riskTone = riskLevelTone(risk.risk_level);
  if (signalTone === "positive" && riskTone === "negative") {
    return "主信号偏正面，但市场踩踏风险偏高，先压低信号解释权重。";
  }
  if (signalTone === "negative" && riskTone === "positive") {
    return "主信号偏谨慎，市场踩踏风险暂低，继续观察是否修复。";
  }
  if (riskTone === "negative") {
    return "风险预警偏高，观察结论优先参考风险边界。";
  }
  return "主信号和风险预警未明显冲突，可继续观察证据延续性。";
}

function ObservationSignalRiskComparison({
  signalCards,
  primarySignal,
  risk,
  isLoading = false,
}: {
  signalCards: MacroToolkitSignalCard[];
  primarySignal: MacroToolkitSignalCard | null;
  risk?: MacroToolkitAShareRiskPayload;
  isLoading?: boolean;
}) {
  const signal = primarySignal ?? signalCards.find((card) => card.score != null) ?? signalCards[0] ?? null;
  const signalTone = signal?.tone ?? "missing";
  const riskTone = risk ? riskLevelTone(risk.risk_level) : "missing";
  const riskScore = risk?.risk_score === null || risk?.risk_score === undefined ? "缺失" : risk.risk_score;
  const riskSummary = risk?.summary || (isLoading ? "观察证据加载中" : "风险摘要待确认。");
  const signalEvidence = signal ? formatObservationEvidence(signal.evidence) : isLoading ? "观察证据加载中" : "主信号证据待确认";
  const riskContent = risk ? (
    <>
      <strong>{`${risk.risk_name} · ${riskScore}`}</strong>
      <p title={riskSummary}>{compactText(riskSummary, 68)}</p>
      <div className="macro-toolkit-observation-signal-risk__metrics">
        <span>
          <small>上涨家数</small>
          <b>{formatRiskMetric(risk.metrics.up_count)}</b>
        </span>
        <span>
          <small>跌停家数</small>
          <b>{formatRiskMetric(risk.metrics.limit_down_count)}</b>
        </span>
        <span>
          <small>成交额/20日</small>
          <b>{formatRiskMetric(risk.metrics.turnover_ratio_ma20, "ratio")}</b>
        </span>
      </div>
    </>
  ) : (
    <>
      <strong>{isLoading ? "观察证据加载中" : "完整分析后确认风险边界"}</strong>
      <p title={riskSummary}>
        {isLoading ? compactText(riskSummary, 68) : "需合并 A股宽度、跌停和成交压力。"}
      </p>
    </>
  );
  return (
    <div className="macro-toolkit-observation-signal-risk" aria-label="信号风险对照">
      <div className="macro-toolkit-observation-signal-risk__grid">
        <div className={`macro-toolkit-observation-signal-risk__lane macro-toolkit-observation-signal-risk__lane--${signalTone}`}>
          <div className="macro-toolkit-observation-signal-risk__lane-head">
            <span>核心信号</span>
            <Tag color={toneTagColor(signalTone)}>
              {signal ? formatObservationSignalStance(signal) : isLoading ? "加载中" : "待确认"}
            </Tag>
          </div>
          <strong>{signal ? formatObservationSignalTitle(signal) : isLoading ? "观察证据加载中" : "信号待确认"}</strong>
          <div className="macro-toolkit-observation-signal-risk__score">
            <b>{signal?.score === null || signal?.score === undefined ? "缺失" : signal.score}</b>
            <ScoreTrack score={signal?.score} />
          </div>
          <small title={signalEvidence}>{compactText(signalEvidence, 58)}</small>
        </div>

        <div className={`macro-toolkit-observation-signal-risk__lane macro-toolkit-observation-signal-risk__lane--${riskTone}`}>
          <div className="macro-toolkit-observation-signal-risk__lane-head">
            <span>风险预警</span>
            <div className="macro-toolkit-tag-row">
              <Tag color={risk ? statusColor(risk.status) : "default"}>
                {risk ? statusLabel(risk.status) : isLoading ? "加载中" : "证据缺口"}
              </Tag>
              {risk ? <Tag color={riskLevelColor(risk.risk_level)}>{risk.risk_name}</Tag> : null}
            </div>
          </div>
          {riskContent}
        </div>
      </div>

      <div className="macro-toolkit-observation-signal-risk__note">
        <span>观察判断</span>
        <strong>{observationSignalRiskSummary(signal, risk, isLoading)}</strong>
        <small>仅用于只读宏观观察，不作为正式投资信号。</small>
      </div>
    </div>
  );
}

function InvestmentEvidenceSummary({
  indicators,
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
}: {
  indicators: MacroToolkitIndicator[];
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
}) {
  const usableIndicators = indicators.filter((indicator) => indicator.quality === "ok");
  const missingIndicators = indicators.length - usableIndicators.length;
  const visibleIndicators = indicators.slice(0, 3);
  const shadowObservation = shadowPortfolioObservationText(shadowPortfolioReport);
  const shadowObservationDetail = shadowPortfolioReport
    ? "影子组合仅作观察边界，不进入正式投资信号。"
    : shadowObservation.detail;
  const bestStrategy = strategySummaries.find((strategy) => strategy.status === "complete") ?? strategySummaries[0] ?? null;
  return (
    <div className="macro-toolkit-investment-evidence" aria-label="投研证据摘要">
      <div className="macro-toolkit-investment-evidence__head">
        <div>
          <span>证据支撑</span>
          <strong>策略、指标和影子组合边界压缩成观察支撑</strong>
        </div>
        <Tag color="gold">非正式投资信号</Tag>
      </div>
      <div className="macro-toolkit-investment-evidence__lanes">
        <div className="macro-toolkit-investment-evidence__lane">
          <div className="macro-toolkit-investment-evidence__lane-head">
            <span>策略证据</span>
            <strong>{fullRealStrategyCount}/{strategySummaries.length || 0}</strong>
          </div>
          <div className="macro-toolkit-investment-evidence__metric-row">
            <MetricTile
              icon={<DatabaseOutlined />}
              label="真实供数"
              value={`${fullRealStrategyCount}/${strategySummaries.length || 0}`}
              detail={strategyObservationDetail(
                strategySummaries,
                fullRealStrategyCount,
                partialRealStrategyCount,
                degradedStrategyCount,
                sampleStrategyCount,
              )}
              tone={fullRealStrategyCount > 0 ? "neutral" : "missing"}
              detailMaxLength={42}
            />
            <MetricTile
              icon={<SafetyCertificateOutlined />}
              label={shadowObservation.label}
              value={shadowObservation.value}
              detail={shadowObservationDetail}
              tone={shadowObservation.tone}
              detailMaxLength={42}
            />
          </div>
          <div className="macro-toolkit-investment-evidence__note">
            <span>{bestStrategy?.label ?? "策略摘要"}</span>
            <small>{strategyObservationNote(bestStrategy, strategySupplyState)}</small>
          </div>
        </div>
        <div className="macro-toolkit-investment-evidence__lane">
          <div className="macro-toolkit-investment-evidence__lane-head">
            <span>指标证据</span>
            <strong>{usableIndicators.length}/{indicators.length || 0}</strong>
          </div>
          <div className="macro-toolkit-investment-evidence__metric-row">
            <MetricTile
              icon={<DatabaseOutlined />}
              label="数据源已确认"
              value={`${usableIndicators.length}/${indicators.length || 0}`}
              detail={missingIndicators ? `${missingIndicators} 个指标待补齐。` : "当前观察指标均可用。"}
              tone={missingIndicators ? "missing" : "neutral"}
              detailMaxLength={42}
            />
            <MetricTile
              icon={<ClockCircleOutlined />}
              label="最新日期"
              value={latestIndicatorDate(indicators)}
              detail="用于观察结论排序，不展示源表审计。"
              tone="neutral"
              detailMaxLength={42}
            />
          </div>
          <div className="macro-toolkit-investment-evidence__indicators" aria-label="观察指标摘要">
            {visibleIndicators.map((indicator) => (
              <span key={indicator.alias}>
                <strong>{indicator.label}</strong>
                <small>
                  {formatValue(indicator.latest_value, indicator.unit)} · {indicator.latest_date ?? "日期缺失"}
                </small>
              </span>
            ))}
          </div>
        </div>
        <div className="macro-toolkit-investment-evidence__note macro-toolkit-investment-evidence__note--boundary">
          <span>观察边界</span>
          <small>完整审计留在工具页；本页只保留证据支撑，不作为正式投资信号。</small>
        </div>
      </div>
    </div>
  );
}

function formatValue(value: number | null, unit = "") {
  if (value === null) {
    return "缺失";
  }
  const digits = Math.abs(value) >= 100 ? 2 : 4;
  return `${value.toFixed(digits)}${unit}`;
}

function formatChange(change: number | null, changePct: number | null) {
  if (change === null && changePct === null) {
    return "无可比";
  }
  if (changePct !== null) {
    return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  }
  return `${change! >= 0 ? "+" : ""}${change!.toFixed(4)}`;
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function clampScore(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }
  return Math.min(100, Math.max(0, score));
}

function ScoreTrack({ score }: { score: number | null | undefined }) {
  return <progress className="macro-toolkit-score-track" value={clampScore(score)} max={100} aria-hidden="true" />;
}

function formatQueryError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "宏观工具接口暂不可用";
}

function isMacroToolkitReadForbidden(message: string) {
  return /not allowed/i.test(message) && /read\s+macro_toolkit/i.test(message);
}

const MACRO_TOOLKIT_READ_SCOPE_REQUEST_TEXT = [
  "申请授予 macro_toolkit/read",
  "resource=macro_toolkit",
  "action=read",
  "页面=/macro-toolkit",
  "用途=读取宏观工具 core/full 分析、脚本注册表、策略摘要和 Crisis Score 证据面板",
  "授权后点击重试读取",
].join("\n");

function MacroToolkitReadScopeBlocker() {
  const [copyStatus, setCopyStatus] = useState<"idle" | "success" | "error">("idle");

  const copyScopeRequest = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (typeof writeText !== "function") {
      setCopyStatus("error");
      return;
    }
    try {
      await writeText.call(clipboard, MACRO_TOOLKIT_READ_SCOPE_REQUEST_TEXT);
      setCopyStatus("success");
    } catch {
      setCopyStatus("error");
    }
  }, []);

  return (
    <div className="macro-toolkit-read-scope-blocker" aria-label="宏观工具读取权限缺口">
      <div>
        <span>缺少宏观工具读取权限</span>
        <strong>macro_toolkit/read</strong>
        <small>当前账号未被允许读取宏观工具；授权后点击重试读取。</small>
      </div>
      <div className="macro-toolkit-read-scope-blocker__actions">
        <Button
          aria-label="复制授权申请"
          icon={<CopyOutlined aria-hidden="true" />}
          size="small"
          type="default"
          onClick={() => void copyScopeRequest()}
        >
          {copyStatus === "success" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制授权申请"}
        </Button>
        {copyStatus !== "idle" ? (
          <span
            aria-atomic="true"
            aria-live="polite"
            className={`macro-toolkit-read-scope-blocker__copy-status macro-toolkit-read-scope-blocker__copy-status--${copyStatus}`}
            role="status"
          >
            {copyStatus === "success" ? "授权申请已复制" : "复制失败，请手动选择授权信息"}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function isReadyStatus(status: string) {
  return ["current", "ready", "library_ready", "complete", "wired", "visible", "ok"].includes(status);
}

export default function MacroToolkitPage({ mode = "toolkit" }: MacroToolkitPageProps) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const showOperations = mode === "toolkit";
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedGovernanceFocus, setSelectedGovernanceFocus] =
    useState<MacroToolkitGovernanceFocusKey>("evidence");
  const [detailDensity, setDetailDensity] = useState<"compact" | "expanded">("compact");
  const [actionReceipt, setActionReceipt] = useState<MacroToolkitActionReceipt>(EMPTY_ACTION_RECEIPT);
  const [actionReceipts, setActionReceipts] = useState<MacroToolkitActionReceipt[]>([]);
  const [confirmedReceiptIds, setConfirmedReceiptIds] = useState<Set<string>>(() => new Set());
  const [selectedEvidenceHref, setSelectedEvidenceHref] = useState<string | null>(null);
  const [selectedExecutionHref, setSelectedExecutionHref] = useState<string | null>(null);
  const [receiptTechnicalDetailsExpanded, setReceiptTechnicalDetailsExpanded] = useState(false);
  const [focusedRepairKey, setFocusedRepairKey] = useState<string | null>(null);
  const [committeeActionLocatorKey, setCommitteeActionLocatorKey] = useState<string | null>(null);
  const [committeePackReceiptCopyStatus, setCommitteePackReceiptCopyStatus] = useState<"idle" | "success" | "error">("idle");
  const committeeActionLocatorRef = useRef<HTMLDivElement | null>(null);
  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
  const [stockRefreshResult, setStockRefreshResult] = useState<string | null>(null);
  const [stockRefreshError, setStockRefreshError] = useState<string | null>(null);
  const [isRefreshingChoiceStock, setIsRefreshingChoiceStock] = useState(false);
  const [sourceBackfillResult, setSourceBackfillResult] = useState<string | null>(null);
  const [sourceBackfillError, setSourceBackfillError] = useState<string | null>(null);
  const [crisisGapRepairFeedback, setCrisisGapRepairFeedback] = useState<CrisisGapRepairFeedback | null>(null);
  const [refreshingSourceAlias, setRefreshingSourceAlias] = useState<string | null>(null);
  const [commodityRefreshResult, setCommodityRefreshResult] = useState<string | null>(null);
  const [commodityRefreshError, setCommodityRefreshError] = useState<string | null>(null);
  const [commodityRefreshRun, setCommodityRefreshRun] = useState<MacroToolkitCommodityFuturesRefreshRun | null>(null);
  const [commoditySuggestedSelection, setCommoditySuggestedSelection] = useState<string[]>([]);
  const [commodityEvidenceReloadMessage, setCommodityEvidenceReloadMessage] = useState<string | null>(null);
  const [commodityRefreshEvidenceChain, setCommodityRefreshEvidenceChain] =
    useState<CommodityRefreshEvidenceChain | null>(null);
  const [commodityShortfallChanges, setCommodityShortfallChanges] = useState<CommodityShortfallChange[]>([]);
  const [commodityShortfallEstimates, setCommodityShortfallEstimates] = useState<CommodityShortfallEstimate[]>([]);
  const [isRefreshingCommodity, setIsRefreshingCommodity] = useState(false);
  const [selectedCommodityProducts, setSelectedCommodityProducts] = useState<string[]>([
    ...DEFAULT_MACRO_COMMODITY_PRODUCTS,
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [fullAnalysisEnvelope, setFullAnalysisEnvelope] =
    useState<ApiEnvelope<MacroToolkitAnalysisPayload> | null>(null);
  const [fullAnalysisError, setFullAnalysisError] = useState<string | null>(null);
  const [isLoadingFullAnalysis, setIsLoadingFullAnalysis] = useState(false);

  const analysisQuery = useQuery({
    queryKey: ["macro-toolkit", "analysis"],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "core" }),
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const scriptsQuery = useQuery({
    queryKey: ["macro-toolkit", "scripts"],
    queryFn: () => client.getMacroToolkitScripts(),
    enabled: showOperations,
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const strategyQuery = useQuery({
    queryKey: ["macro-toolkit", "strategy-summaries"],
    queryFn: ({ signal }) => client.getMacroToolkitStrategySummaries({ signal }),
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const fetchFullAnalysis = useCallback(
    () => client.getMacroToolkitAnalysis({ detail: "full" }),
    [client],
  );

  const clearFullAnalysisCache = useCallback(async (options?: { preserveCrisisGapRepairFeedback?: boolean }) => {
    setFullAnalysisEnvelope(null);
    setFullAnalysisError(null);
    if (!options?.preserveCrisisGapRepairFeedback) {
      setCrisisGapRepairFeedback(null);
    }
    await queryClient.cancelQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
  }, [queryClient]);

  const recordActionReceipt = useCallback((receipt: MacroToolkitActionReceipt) => {
    setActionReceipt(receipt);
    if (receipt.status === "idle") {
      return;
    }
    setActionReceipts((current) => {
      const withoutSameAction = current.filter((item) => item.id !== receipt.id);
      return [receipt, ...withoutSameAction].slice(0, MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT);
    });
  }, []);

  const confirmActionReceipt = useCallback((receiptId: string) => {
    setConfirmedReceiptIds((current) => {
      if (current.has(receiptId)) {
        return current;
      }
      const next = new Set(current);
      next.add(receiptId);
      return next;
    });
  }, []);

  const payload = showOperations ? scriptsQuery.data?.result : undefined;
  const analysisEnvelope = fullAnalysisEnvelope ?? analysisQuery.data;
  const analysis = analysisEnvelope?.result;
  const scripts = payload?.scripts ?? EMPTY_SCRIPTS;
  const capabilityResults = analysis?.capability_results ?? [];
  const strategyPayload = strategyQuery.data?.result;
  const strategySummaries = strategyPayload?.strategy_summaries ?? analysis?.strategy_summaries ?? [];
  const shadowPortfolioReport =
    strategyPayload?.shadow_portfolio_report ?? analysis?.shadow_portfolio_report ?? null;
  const fullRealStrategyCount = strategySummaries.filter((strategy) => hasCompleteRealStrategyChain(strategy)).length;
  const partialRealStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && !hasCompleteRealStrategyChain(strategy),
  ).length;
  const degradedStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && strategy.status !== "complete",
  ).length;
  const sampleStrategyCount = strategySummaries.filter((strategy) => strategy.status === "sample_only").length;
  const hasLoadedStrategySummaries = strategySummaries.length > 0;
  const strategySupplyState =
    strategyQuery.isFetching && !hasLoadedStrategySummaries
      ? "loading"
      : strategyQuery.isError && !hasLoadedStrategySummaries
        ? "failed"
        : "loaded";
  const hasRealStrategyData = strategySummaries.some((strategy) => hasRealStrategySource(strategy));
  const strategyDescription =
    strategySupplyState === "loading"
      ? "策略摘要正在生成，核心信号已先返回；市场踩踏风险和功能结果需打开完整分析后显示。"
      : strategySupplyState === "failed"
        ? "策略摘要读取失败，当前不能判断策略供数闭环。"
        : hasRealStrategyData
          ? "展示已合入宏观模块的 A股策略能力；已接入股票行情或因子快照，不作为正式投资信号。"
          : "展示已合入宏观模块的 A股策略能力；当前为合成样例和模块可用性检查，不作为正式投资信号。";
  const groupOptions = useMemo(
    () => [
      { value: "all", label: "全部分组" },
      ...[...(payload?.groups ?? [])].sort().map((group) => ({
        value: group,
        label: groupLabel(group),
      })),
    ],
    [payload?.groups],
  );

  const filteredScripts = useMemo(() => {
    if (selectedGroup === "all") {
      return scripts;
    }
    return scripts.filter((script) => script.group === selectedGroup);
  }, [scripts, selectedGroup]);

  useEffect(() => {
    if (selectedName || filteredScripts.length === 0) {
      return;
    }
    setSelectedName((pickDefaultCommitteeScript(filteredScripts) ?? filteredScripts[0]!).name);
  }, [filteredScripts, selectedName]);

  const selectedScript = useMemo(
    () =>
      scripts.find((script) => script.name === selectedName) ??
      pickDefaultCommitteeScript(filteredScripts) ??
      null,
    [filteredScripts, scripts, selectedName],
  );
  const outputDetail = payload?.output_files.length
    ? `${payload.output_files[0]!.name} · ${formatSize(payload.output_files[0]!.size_bytes)}`
    : payload?.output_dir ?? "data/macro_toolkit/output";
  const cffexStatus = payload?.cffex_member_rank ?? analysis?.cffex_member_rank ?? null;
  const choiceStockRefresh =
    strategyPayload?.choice_stock_refresh ?? payload?.choice_stock_refresh ?? analysis?.choice_stock_refresh ?? null;
  const commodityFuturesRefresh = payload?.commodity_futures_refresh ?? null;
  const commodityPermission = commodityRefreshRun?.permission ?? commodityFuturesRefresh?.permission ?? null;
  const commodityStatus = commodityFuturesRefresh?.status ?? null;
  const defaultBusinessEvidenceSources = formatBusinessEvidenceList(
    payload?.default_data_sources ?? analysis?.default_data_sources,
  );
  const executionBusinessEvidence = formatBusinessEvidenceList([
    ...(scriptsQuery.data?.result_meta.tables_used ?? []),
    ...(payload?.default_data_sources ?? analysis?.default_data_sources ?? []),
    ...(cffexStatus?.row_count ? ["bond_futures_history.csv"] : []),
    ...(commodityStatus ? [commodityStatus.table] : []),
    ...(hasRealStrategyData ? ["choice_stock_daily_observation", "choice_stock_factor_snapshot"] : []),
  ]);
  const outputReceiptDetail = payload?.output_files.length
    ? `${payload.output_files.length} 个产物 · 产物回执已归档`
    : outputDetail;
  const isCommodityRefreshAllowed = commodityPermission?.allowed === true;
  const shouldShowCommodityPermissionNotice = !isCommodityRefreshAllowed;
  const commodityRefreshDisabled = selectedCommodityProducts.length === 0 || !isCommodityRefreshAllowed;
  const omittedEntries = Object.entries(payload?.omitted_scripts ?? {});
  const sourceChecks = payload?.source_checks ?? analysis?.source_checks ?? [];
  const capabilityItems = payload?.capabilities ?? analysis?.capabilities ?? [];
  const analysisMeta = analysisEnvelope?.result_meta;
  const sourceHitCount = sourceChecks.filter((check) => check.row_count > 0).length;
  const availableScriptCount = scripts.filter((script) => script.available).length;
  const receiptWorkpaperItems = [
    {
      key: "archive",
      label: "产物归档",
      value: `${payload?.output_files.length ?? 0} 个产物`,
      detail: "明细在下方展开",
    },
    {
      key: "source",
      label: "来源命中",
      value: `${sourceHitCount}/${sourceChecks.length}`,
      detail: sourceChecks.length ? "来源证据已留痕" : "来源证据待返回",
    },
    {
      key: "execution",
      label: "执行能力",
      value: `${availableScriptCount}/${scripts.length}`,
      detail: scripts.length ? "可执行能力已归档" : "执行能力待返回",
    },
    {
      key: "receipt",
      label: "留痕状态",
      value: `${actionReceipts.length} 条`,
      detail: actionReceipts.length ? "回执队列可复核" : "等待操作回执",
    },
  ];
  const readyCapabilityCount = capabilityItems.filter((item) => isReadyStatus(item.data_status)).length;
  const wiredCapabilityCount = capabilityItems.filter((item) =>
    isReadyStatus(item.route_status) && isReadyStatus(item.frontend_status),
  ).length;
  const crisisScoreResult = capabilityResults.find((result) => result.key === "crisis_score_cn") ?? null;
  const degradedResultCount = capabilityResults.filter((result) => result.status !== "complete").length;
  const missingIndicatorCount = analysis?.indicators.filter((indicator) => indicator.quality === "missing").length ?? 0;
  const analysisSignalCards = analysis?.signal_cards ?? [];
  const visibleSignalCards = showOperations
    ? analysisSignalCards
    : analysisSignalCards.filter((card) => !isObservationOutputSignal(card));
  const analyticalSignalCards = analysisSignalCards.filter((card) => !isObservationOutputSignal(card));
  const primarySignal =
    analyticalSignalCards
      .filter((card) => card.score != null)
      .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))[0] ?? null;
  const isCoreAnalysis = analysis?.runtime_status?.analysis_scope === "core";
  const isMacroRefreshing =
    analysisQuery.isFetching ||
    (showOperations && scriptsQuery.isFetching) ||
    strategyQuery.isFetching ||
    isRefreshingCommodity ||
    isLoadingFullAnalysis;
  const isOperationActionBusy =
    isMacroRefreshing ||
    isRunning ||
    isRefreshingChoiceStock ||
    isRefreshingCffex ||
    refreshingSourceAlias != null;
  const queryErrors = [analysisQuery.error, ...(showOperations ? [scriptsQuery.error] : []), strategyQuery.error];
  const queryErrorText = queryErrors
    .filter(Boolean)
    .map(formatQueryError)
    .join("；");
  const failedReadMessages = queryErrors
    .filter(Boolean)
    .map(formatQueryError);
  const observationFailedReadMessages = [
    analysisQuery.isError ? "读取核心分析失败" : "",
    strategyQuery.isError ? "读取策略摘要失败" : "",
  ].filter(Boolean);
  const hasReadScopeBlocker = failedReadMessages.some(isMacroToolkitReadForbidden);
  const runtimeSections = analysis?.runtime_status?.deferred_sections ?? [];
  const hasonStrategy = analysis?.hason_strategy ?? null;
  const showFullAnalysisActionInRuntime = isCoreAnalysis && runtimeSections.length > 0;
  const observationRuntimeSummary = isCoreAnalysis
    ? runtimeSections.length
      ? `${runtimeSections.length} 项证据延后确认`
      : "等待完整分析确认"
    : "证据已完整读取";
  const dataFreshnessDetail = showOperations
    ? `${missingIndicatorCount} 个指标缺失；${sourceHitCount} 个源命中`
    : analysis?.data_health
      ? `来源覆盖 ${coverageValue(analysis.data_health.source_coverage)}`
      : "来源覆盖待确认";
  const commodityRefreshActionLabel = formatCommodityRefreshActionLabel(commodityShortfallEstimates);
  const repairItems = analysis?.data_health?.repair_items ?? [];
  const repairItemCount = repairItems.length;
  const repairTriageItems = repairTriageLaneItems(repairItems);
  const primaryRepairItem = [...repairItems].sort(compareRepairPriority)[0] ?? null;
  const primaryActionableRepairItem =
    repairItems.find(canRefreshMacroSourceBackfill) ?? primaryRepairItem ?? null;
  const focusDataHealthRepair = useCallback(() => {
    const repairKey = primaryActionableRepairItem ? repairItemFocusKey(primaryActionableRepairItem) : null;
    setSelectedEvidenceHref("#macro-toolkit-data-health-detail");
    setSelectedGovernanceFocus("data-health");
    setFocusedRepairKey(repairKey);
    setCommitteeActionLocatorKey(repairKey);
  }, [primaryActionableRepairItem]);
  const handleDataHealthRepairActionClick = useCallback(
    (event?: ReactMouseEvent<HTMLAnchorElement> | Event) => {
      event?.preventDefault();
      focusDataHealthRepair();
    },
    [focusDataHealthRepair],
  );
  useEffect(() => {
    if (!committeeActionLocatorKey || selectedEvidenceHref !== "#macro-toolkit-data-health-detail") return;
    const actionLocator = committeeActionLocatorRef.current;
    if (typeof actionLocator?.scrollIntoView !== "function") return;
    const block: ScrollLogicalPosition = window.innerWidth <= 640 ? "center" : "nearest";
    actionLocator.scrollIntoView({ block, inline: "nearest" });
  }, [committeeActionLocatorKey, selectedEvidenceHref]);
  useEffect(() => {
    if (selectedEvidenceHref === "#macro-toolkit-script-artifact-detail") {
      setReceiptTechnicalDetailsExpanded(true);
    }
  }, [selectedEvidenceHref]);
  const completedDataHealthReceipt =
    actionReceipts.find((receipt) =>
      receiptMatchesCommitteeEvidence(
        receipt,
        "data-health",
        "#macro-toolkit-data-health-detail",
        "数据运营负责人",
      ),
    ) ?? null;
  const hasDataHealthRepairReceipt = Boolean(completedDataHealthReceipt);
  const completedDataHealthReceiptConfirmed = completedDataHealthReceipt
    ? confirmedReceiptIds.has(completedDataHealthReceipt.id)
    : false;
  const hasDataHealthRepairReceiptPending = hasDataHealthRepairReceipt && !completedDataHealthReceiptConfirmed;
  const hasDataHealthHardBlocker = repairItemCount > 0 && !completedDataHealthReceipt;
  const committeeReadinessStatus = hasDataHealthHardBlocker
    ? "暂缓提交"
    : hasDataHealthRepairReceiptPending
      ? "待复核回执"
      : isCoreAnalysis
        ? "待补全证据"
        : "可进入复核";
  const committeeReadinessBlocker = hasDataHealthHardBlocker
    ? formatCommitteeReadinessBlocker(primaryRepairItem, repairItemCount)
    : hasDataHealthRepairReceiptPending
      ? "数据健康回执待复核"
      : completedDataHealthReceiptConfirmed
        ? "数据健康签核已确认"
    : isCoreAnalysis
      ? observationRuntimeSummary
      : degradedResultCount
        ? `${degradedResultCount} 个结果降级`
        : "无关键卡点";
  const committeeReadinessOwner = repairItemCount ? "数据运营负责人" : isCoreAnalysis ? "宏观策略负责人" : "数据运营负责人";
  const committeeReadinessHref = repairItemCount
    ? "#macro-toolkit-data-health-detail"
    : isCoreAnalysis
      ? "#macro-toolkit-analysis-detail"
      : "#macro-toolkit-tool-execution-detail";
  const committeeReadinessAction = completedDataHealthReceiptConfirmed
    ? "查看签核证据"
    : hasDataHealthRepairReceiptPending
    ? "复核数据健康回执"
    : repairItemCount
      ? "处理数据缺口"
      : isCoreAnalysis
        ? "查看证据覆盖"
        : "进入操作台";
  const committeeRedlineTitle = hasDataHealthHardBlocker
    ? "数据缺口阻止提交"
    : hasDataHealthRepairReceiptPending
      ? "数据健康回执待复核"
      : completedDataHealthReceiptConfirmed
        ? "数据健康签核已确认"
    : isCoreAnalysis
      ? "完整证据未确认"
      : degradedResultCount
        ? "能力结果待复核"
        : "无硬性红线";
  const committeeRedlineAction = hasDataHealthHardBlocker
    ? formatObservationRepairSummary(repairItems)
    : hasDataHealthRepairReceiptPending
      ? "复核来源补齐回执，确认数据健康证据后再进入投委会签核。"
      : completedDataHealthReceiptConfirmed
        ? "来源补齐回执已签核，数据健康红线已解除；继续复核策略供数与工具执行证据。"
    : isCoreAnalysis
      ? "打开完整分析后确认完整分析补充项，再复核投委会材料。"
      : degradedResultCount
        ? "先复核降级结果，再判断是否进入投委会材料。"
        : "材料可进入复核，继续保留证据留痕。";
  const dataHealthSignoffPriority = primaryRepairItem
    ? `${committeePriorityLabel(primaryRepairItem.priority)} · ${formatDataHealthRepairLabel(
        primaryRepairItem,
        true,
      )}${primaryRepairItem.alias ? ` / ${primaryRepairItem.alias}` : ""}`
    : "无待处理数据项";
  const dataHealthSignoffCoverage = analysis?.data_health
    ? `${coverageValue(analysis.data_health.source_coverage)} 来源 · ${analysis.data_health.indicator_coverage.hit_count}/${analysis.data_health.indicator_coverage.total_count} 指标`
    : "覆盖率待确认";
  const dataHealthSignoffRequirement = repairItemCount
    ? "完成数据缺口回执 + 重读完整分析"
    : "保留数据健康快照";
  const dataHealthSignoffGuardrail = repairItemCount
    ? "不得由 CFFEX/商品/工具回执替代"
    : "无硬阻断，可进入签核";
  const currentRepairItem = primaryActionableRepairItem ?? primaryRepairItem;
  const currentRepairReceipt = currentRepairItem || completedDataHealthReceipt ? completedDataHealthReceipt : null;
  const currentRepairReceiptConfirmed = currentRepairReceipt ? confirmedReceiptIds.has(currentRepairReceipt.id) : false;
  const currentRepairLabel = currentRepairItem
    ? `${formatDataHealthRepairLabel(currentRepairItem, currentRepairItem.type === "deferred")}${
        currentRepairItem.alias ? ` / ${currentRepairItem.alias}` : ""
      }`
    : currentRepairReceipt
      ? currentRepairReceipt.evidenceEntry
    : "无待处理数据项";
  const currentRepairNeedsManualEscalation = Boolean(currentRepairItem && needsManualReviewEscalation(currentRepairItem));
  const currentRepairNeedsFullAnalysisReview = Boolean(currentRepairItem && needsFullAnalysisReview(currentRepairItem));
  const currentRepairStatus = currentRepairReceipt
    ? repairTicketReceiptStatus(currentRepairReceipt, currentRepairReceiptConfirmed)
    : currentRepairItem
      ? repairTicketReceiptStatus(currentRepairReceipt, currentRepairReceiptConfirmed)
      : "无需处理";
  const currentRepairAction = currentRepairReceiptConfirmed
    ? "查看签核证据"
    : currentRepairReceipt
      ? "复核数据健康回执"
      : currentRepairNeedsManualEscalation
        ? "升级人工复核"
        : currentRepairNeedsFullAnalysisReview
          ? "复核完整分析"
          : repairItemCount
            ? "处理数据缺口"
            : "打开数据健康证据";
  const currentRepairNeedsSignoff = Boolean(currentRepairReceipt && !currentRepairReceiptConfirmed);
  const currentRepairPrimaryActionMovedToPipeline = Boolean(
    currentRepairItem &&
      !currentRepairReceipt &&
      !currentRepairNeedsManualEscalation &&
      !currentRepairNeedsFullAnalysisReview,
  );
  const confirmCurrentRepairReceipt = useCallback(() => {
    if (!currentRepairReceipt || currentRepairReceiptConfirmed) return;
    focusDataHealthRepair();
    confirmActionReceipt(currentRepairReceipt.id);
  }, [confirmActionReceipt, currentRepairReceipt, currentRepairReceiptConfirmed, focusDataHealthRepair]);
  const committeeActionLocatorItem = committeeActionLocatorKey
    ? (repairItems.find((item) => repairItemFocusKey(item) === committeeActionLocatorKey) ?? null)
    : null;
  const committeeActionLocatorLabel = committeeActionLocatorItem
    ? `${formatDataHealthRepairLabel(committeeActionLocatorItem, committeeActionLocatorItem.type === "deferred")}${
        committeeActionLocatorItem.alias ? ` / ${committeeActionLocatorItem.alias}` : ""
      }`
    : "";
  const committeeClosureRailItems = currentRepairItem
    ? [
        {
          step: "1",
          phase: "处理",
          status: currentRepairReceipt ? "处理完成" : "当前卡点",
          detail: currentRepairLabel,
          action: currentRepairReceipt
            ? "查看处理单"
            : currentRepairPrimaryActionMovedToPipeline
              ? "主入口在首屏流水线"
              : currentRepairAction,
          tone: currentRepairReceipt ? "done" : "active",
          kind: currentRepairReceipt ? "link" : "status",
        },
        {
          step: "2",
          phase: "回执",
          status: currentRepairReceipt ? "回执已生成" : "等待执行",
          detail: currentRepairReceipt?.evidenceEntry ?? repairTicketReceipt(currentRepairItem),
          action: currentRepairReceipt ? "查看回执证据" : "等待回执",
          tone: currentRepairReceipt ? "done" : "pending",
          kind: "status",
        },
        {
          step: "3",
          phase: "签核",
          status: currentRepairReceiptConfirmed ? "签核已确认" : currentRepairReceipt ? "待复核签核" : "等待回执",
          detail: currentRepairReceiptConfirmed
            ? "签核留痕完成"
            : currentRepairReceipt
              ? repairTicketOwner(currentRepairItem)
              : "回执后签核",
          action: currentRepairReceiptConfirmed
            ? "查看签核证据"
            : currentRepairReceipt
              ? "复核数据健康回执"
              : "等待回执",
          tone: currentRepairReceiptConfirmed ? "done" : currentRepairReceipt ? "active" : "pending",
          kind: currentRepairReceipt && !currentRepairReceiptConfirmed ? "signoff" : "status",
          receiptId: currentRepairReceipt?.id,
          ariaLabel: "复核签核-数据健康",
        },
        {
          step: "4",
          phase: "放行",
          status: currentRepairReceiptConfirmed ? "可放行" : currentRepairReceipt ? "等待签核" : committeeReadinessStatus,
          detail: currentRepairReceiptConfirmed ? "数据健康签核完成" : currentRepairReceipt ? "签核后解除红线" : committeeReadinessBlocker,
          action: currentRepairReceiptConfirmed ? "查看签核证据" : currentRepairReceipt ? "等待签核确认" : "暂缓提交",
          tone: currentRepairReceiptConfirmed ? "active" : "pending",
          kind: currentRepairReceiptConfirmed ? "link" : "status",
        },
      ]
    : [
        {
          step: "1",
          phase: "处理",
          status: "无待处理项",
          detail: "数据健康无硬阻断",
          action: "打开数据健康证据",
          tone: "done",
          kind: "status",
        },
        {
          step: "2",
          phase: "回执",
          status: "无需补齐",
          detail: "保留数据快照",
          action: "查看证据",
          tone: "done",
          kind: "status",
        },
        {
          step: "3",
          phase: "签核",
          status: "可进入复核",
          detail: committeeReadinessOwner,
          action: "进入签核",
          tone: "active",
          kind: "status",
        },
        {
          step: "4",
          phase: "放行",
          status: "可放行",
          detail: "无数据健康红线",
          action: "查看签核证据",
          tone: "pending",
          kind: "status",
        },
      ];
  const workflowAnalysisState = isCoreAnalysis ? `core · 待完整分析 ${runtimeSections.length}` : "full · 完整分析";
  const workflowToolState = showOperations
    ? `脚本 ${availableScriptCount}/${scripts.length} · 源 ${sourceHitCount}/${sourceChecks.length}`
    : "只读观察";
  const governanceFocusItems: MacroToolkitGovernanceFocusItem[] = [
    {
      key: "evidence",
      label: "证据覆盖",
      focusTitle: "证据覆盖",
      href: "#macro-toolkit-analysis-detail",
      value: formatPercent(analysis?.coverage.hit_rate),
      detail: `${analysis?.coverage.hit_count ?? 0}/${analysis?.coverage.indicator_count ?? 0} 指标命中`,
      status: analysis ? (analysis.coverage.hit_count === analysis.coverage.indicator_count ? "available" : "core-not-full") : "data-pending",
      tone: analysis?.coverage.hit_rate === 1 ? "positive" : "neutral",
      icon: <SafetyCertificateOutlined />,
    },
    {
      key: "data-health",
      label: "待处理数据",
      focusTitle: "数据健康",
      href: "#macro-toolkit-data-health-detail",
      value: repairItemCount,
      detail: repairItemCount ? "存在待处理数据项，详见数据健康" : "数据健康无待处理项",
      status: repairItemCount ? "data-pending" : "available",
      tone: repairItemCount ? "missing" : "positive",
      icon: <ExclamationCircleOutlined />,
    },
    {
      key: "analysis-scope",
      label: "分析口径",
      focusTitle: "分析口径",
      href: "#macro-toolkit-analysis-detail",
      value: isCoreAnalysis ? "核心" : "完整",
      detail: workflowAnalysisState,
      status: isCoreAnalysis ? "core-not-full" : "available",
      tone: isCoreAnalysis ? "missing" : "positive",
      icon: <ClockCircleOutlined />,
    },
    {
      key: "execution",
      label: "能力闭环",
      focusTitle: "能力闭环",
      href: "#macro-toolkit-tool-execution-detail",
      value: `${readyCapabilityCount}/${capabilityItems.length || 0}`,
      detail: `${wiredCapabilityCount} 项已接到页面/API`,
      status:
        capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length && wiredCapabilityCount === capabilityItems.length
          ? "available"
          : "non-formal",
      tone:
        capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length && wiredCapabilityCount === capabilityItems.length
          ? "positive"
          : "neutral",
      icon: <ThunderboltOutlined />,
    },
  ];
  const selectedGovernanceFocusItem =
    governanceFocusItems.find((item) => item.key === selectedGovernanceFocus) ?? governanceFocusItems[0]!;
  const isAuditTargetActive = useCallback(
    (href: string, governanceKeys: MacroToolkitGovernanceFocusKey[] = []) =>
      selectedEvidenceHref ? selectedEvidenceHref === href : governanceKeys.includes(selectedGovernanceFocus),
    [selectedEvidenceHref, selectedGovernanceFocus],
  );
  const evidenceBookRows: MacroToolkitEvidenceBookRow[] = analysis
    ? [
        {
          key: "primary-signal",
          subject: "主信号",
          support: primarySignal
            ? `${primarySignal.title} · ${primarySignal.stance} · ${primarySignal.score ?? "缺分"}`
            : "主信号待返回",
          gap: isCoreAnalysis ? observationRuntimeSummary : `${analysis.coverage.hit_count}/${analysis.coverage.indicator_count} 指标命中`,
          owner: "宏观策略负责人",
          href: "#macro-toolkit-analysis-detail",
        },
        {
          key: "data-health",
          subject: "数据健康",
          support: `${formatPercent(analysis.coverage.hit_rate)} 覆盖 · ${sourceHitCount}/${sourceChecks.length || 0} 源命中`,
          gap: repairItemCount ? `${repairItemCount} 项待处理` : "无待处理项",
          owner: "数据运营负责人",
          href: "#macro-toolkit-data-health-detail",
        },
        {
          key: "strategy-supply",
          subject: "策略供数",
          support:
            strategySupplyState === "loaded"
              ? `完整链路 ${fullRealStrategyCount}/${strategySummaries.length}`
              : `策略供数 ${statusLabel(strategySupplyState)}`,
          gap:
            strategySupplyState === "failed"
              ? "读取失败"
              : degradedStrategyCount
                ? `${degradedStrategyCount} 项降级`
                : strategySummaries.length
                  ? "无供数降级"
                  : "等待策略摘要",
          owner: "权益策略负责人",
          href: "#macro-toolkit-strategy-detail",
        },
        {
          key: "tool-execution",
          subject: "工具执行",
          support: showOperations
            ? `脚本 ${availableScriptCount}/${scripts.length} · 能力 ${readyCapabilityCount}/${capabilityItems.length || 0}`
            : "只读观察，不暴露操作",
          gap:
            degradedResultCount > 0
              ? `${degradedResultCount} 个结果降级或不可用`
              : capabilityItems.length > 0 && readyCapabilityCount === capabilityItems.length
                ? "能力闭环完成"
                : "能力闭环待确认",
          owner: "数据运营负责人",
          href: "#macro-toolkit-tool-execution-detail",
        },
      ]
    : [];
  const committeePackItems: MacroToolkitCommitteePackItem[] = evidenceBookRows.map((row) => {
    const isBlocking = row.key === "data-health" && hasDataHealthHardBlocker;
    const isPending =
      !isBlocking && /待|降级|失败|缺失|不可用|延后|等待/.test(`${row.support} ${row.gap}`);
    const receipt =
      actionReceipts.find((item) =>
        receiptMatchesCommitteeEvidence(
          item,
          row.key,
          row.href,
          row.owner,
        ),
      ) ?? null;
    return {
      ...row,
      packSubject: row.key === "primary-signal" ? "结论底稿" : row.subject,
      status: isBlocking ? "blocking" : isPending ? "pending" : "archived",
      statusLabel: receipt
        ? confirmedReceiptIds.has(receipt.id)
          ? "已签核"
          : "回执待复核"
        : isBlocking
          ? "阻止提交"
          : isPending
            ? "待确认"
            : "已归档",
      receipt,
      receiptConfirmed: receipt ? confirmedReceiptIds.has(receipt.id) : false,
    };
  });
  const committeePackItemByKey = new Map(committeePackItems.map((item) => [item.key, item]));
  const committeeChecklistItems: MacroToolkitCommitteeChecklistItem[] = committeePackItems.map((item) => {
    const status = item.status === "blocking" ? "block" : item.status === "pending" ? "pending" : "pass";
    const actions = {
      block: item.key === "data-health" ? "先完成数据缺口复核" : "先解除提交阻断",
      pending: item.key === "strategy-supply" ? "确认策略供数链路" : item.key === "tool-execution" ? "复核工具执行结果" : "补齐待确认材料",
      pass: "保留证据留痕",
    } satisfies Record<MacroToolkitCommitteeChecklistItem["status"], string>;
    return {
      ...item,
      condition: item.key === "primary-signal" ? "证据口径" : item.subject,
      status,
      statusLabel: status === "block" ? "未通过" : status === "pending" ? "待确认" : "已通过",
      action: actions[status],
    };
  });
  const committeePackReviewReadyCount = committeePackItems.filter(
    (item) => item.status === "archived" || item.receipt,
  ).length;
  const committeePackReceiptReviewCount = committeePackItems.filter((item) => item.receipt && !item.receiptConfirmed).length;
  const deepEvidenceQueueItems: MacroToolkitDeepEvidenceQueueItem[] = [
    {
      key: "strategy",
      label: "策略证据",
      value:
        strategySupplyState === "loaded"
          ? `完整链路 ${fullRealStrategyCount}/${strategySummaries.length}`
          : statusLabel(strategySupplyState),
      detail: degradedStrategyCount ? `${degradedStrategyCount} 项降级待复核` : strategyDescription,
      href: "#macro-toolkit-strategy-detail",
    },
    {
      key: "crisis-score",
      label: "Crisis Score",
      value: crisisScoreResult ? statusLabel(crisisScoreResult.status) : "待完整分析",
      detail: isCoreAnalysis ? observationRuntimeSummary : `${degradedResultCount} 个结果降级或不可用`,
      href: "#macro-toolkit-analysis-detail",
    },
    {
      key: "hason",
      label: "Hason",
      value: hasonStrategy ? statusLabel(hasonStrategy.status) : "待完整分析",
      detail: hasonStrategy
        ? `模块 ${hasonStrategy.readiness.ready_modules}/${hasonStrategy.readiness.total_modules} · 缺失脚本 ${hasonStrategy.readiness.missing_script_count}`
        : observationRuntimeSummary,
      href: "#macro-toolkit-analysis-detail",
    },
    {
      key: "scripts",
      label: "脚本与产物",
      value: `${payload?.output_files.length ?? 0} 个产物`,
      detail: showOperations ? `脚本 ${availableScriptCount}/${scripts.length} · ${omittedEntries.length} 个未纳入` : "只读观察",
      href: "#macro-toolkit-script-artifact-detail",
    },
  ];
  const committeeWorkQueueItems: MacroToolkitCommitteeWorkQueueItem[] = committeeChecklistItems
    .filter((item) => item.status !== "pass")
    .map((item) => ({
      ...item,
      priorityLabel: item.status === "block" ? "阻断项" : "待确认项",
      executionHref: committeeWorkQueueExecutionHref(item),
    }));
  const isCommitteeChecklistItemOpen = (item: MacroToolkitCommitteeChecklistItem) =>
    !committeePackItemByKey.get(item.key)?.receiptConfirmed;
  const committeeLeadChecklistItem =
    committeeChecklistItems.find(
      (item) => item.status === "block" && item.href === committeeReadinessHref && isCommitteeChecklistItemOpen(item),
    ) ??
    committeeChecklistItems.find((item) => item.status === "block" && isCommitteeChecklistItemOpen(item)) ??
    committeeChecklistItems.find(
      (item) => item.status !== "pass" && item.href === committeeReadinessHref && isCommitteeChecklistItemOpen(item),
    ) ??
    committeeChecklistItems.find((item) => item.status === "pending" && isCommitteeChecklistItemOpen(item)) ??
    null;
  const committeeLeadChecklistHref = committeeLeadChecklistItem?.href ?? committeeReadinessHref;
  const committeeWorkQueueBlockCount = committeeWorkQueueItems.filter((item) => item.status === "block").length;
  const committeeWorkQueuePendingCount = committeeWorkQueueItems.filter((item) => item.status === "pending").length;
  const committeeChecklistPassCount = committeeChecklistItems.filter((item) => item.status === "pass").length;
  const committeeSignoffLaneSummaryItems = committeeSignoffLaneItems(
    committeeWorkQueueItems,
    actionReceipts,
    confirmedReceiptIds,
  );
  const committeeSignoffReadyCount = committeeSignoffLaneSummaryItems.filter(
    (item) => item.status === "approved" || item.status === "reviewed",
  ).length;
  const isCommitteeFinalSignoffReady =
    committeePackItems.length > 0 &&
    committeePackReviewReadyCount === committeePackItems.length &&
    committeeSignoffReadyCount === committeeSignoffLaneSummaryItems.length &&
    committeeWorkQueueBlockCount === 0 &&
    committeePackReceiptReviewCount === 0;
  const committeeFinalSignoffStatus = isCommitteeFinalSignoffReady ? "可提交复核" : "暂缓提交";
  const committeeFinalResidualRiskCount = committeeWorkQueueBlockCount + committeePackReceiptReviewCount;
  const committeeFinalPackValue = committeePackItems.length
    ? `${committeePackReviewReadyCount}/${committeePackItems.length}`
    : "待确认";
  const committeeFinalSignoffValue = committeePackItems.length
    ? `${committeeSignoffReadyCount}/${committeeSignoffLaneSummaryItems.length}`
    : "待确认";
  const committeeFinalResidualRiskValue = committeePackItems.length ? String(committeeFinalResidualRiskCount) : "待确认";
  const committeeFinalReceiptReviewValue = committeePackItems.length ? String(committeePackReceiptReviewCount) : "待确认";
  const committeeLeadPackItem = committeeLeadChecklistItem
    ? committeePackItemByKey.get(committeeLeadChecklistItem.key) ?? null
    : null;
  const committeeLeadReceipt = committeeLeadPackItem?.receipt ?? null;
  const committeeLeadExecutionHref = committeeLeadChecklistItem
    ? committeeWorkQueueExecutionHref(committeeLeadChecklistItem)
    : null;
  const hasCommitteeOpenSubmissionLane = Boolean(
    committeeLeadChecklistItem &&
      !hasDataHealthHardBlocker &&
      !hasDataHealthRepairReceiptPending &&
      !isCoreAnalysis &&
      !committeeLeadPackItem?.receiptConfirmed,
  );
  const committeeDecisionStatus = hasCommitteeOpenSubmissionLane
    ? committeeLeadReceipt
      ? "待复核回执"
      : "待确认闭环"
    : committeeReadinessStatus;
  const committeeDecisionBlocker =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? committeeLeadReceipt
        ? `${committeeLeadChecklistItem.condition}回执待复核`
        : `${committeeLeadChecklistItem.condition}待确认`
      : committeeReadinessBlocker;
  const committeeDecisionOwner =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem ? committeeLeadChecklistItem.owner : committeeReadinessOwner;
  const committeeFinalSignoffOwner = isCommitteeFinalSignoffReady ? "主席复核" : committeeDecisionOwner;
  const committeeDecisionHref =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? (committeeLeadReceipt?.evidenceHref ?? committeeLeadExecutionHref ?? committeeLeadChecklistItem.href)
      : committeeReadinessHref;
  const committeeDecisionAction =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem
      ? committeeLeadReceipt
        ? `复核${committeeLeadChecklistItem.condition}回执`
        : committeeLeadChecklistItem.action
      : committeeReadinessAction;
  const committeeFinalGateOutcome = isCommitteeFinalSignoffReady ? "准入提交" : "未达提交标准";
  const committeeFinalGateTone = isCommitteeFinalSignoffReady ? "ready" : "blocked";
  const committeeFinalGateBlockerText =
    committeeLeadChecklistItem?.key === "data-health" ? `数据缺口 · ${committeeDecisionBlocker}` : committeeDecisionBlocker;
  const committeePackReceiptBlockerCopyText =
    committeeLeadChecklistItem?.key === "data-health" ? `数据缺口 · ${committeeDecisionBlocker}` : committeeDecisionBlocker;
  const committeePackReceiptTraceText = `${committeeLeadChecklistItem?.condition ?? "证据口径"} · ${
    committeeLeadChecklistItem?.owner ?? committeeDecisionOwner
  }`;
  const committeePackReceiptCopyText = [
    "投委会材料包封面回执",
    `提交结论 ${committeeFinalSignoffStatus}`,
    `首要卡点 ${committeePackReceiptBlockerCopyText}`,
    `责任人 ${committeeFinalSignoffOwner}`,
    `下一动作 ${committeeDecisionAction}`,
    `提交包 ${committeeFinalPackValue}`,
    `签核 ${committeeFinalSignoffValue}`,
    `剩余风险 ${committeeFinalResidualRiskValue}`,
    `待复核回执 ${committeeFinalReceiptReviewValue}`,
    `证据留痕 ${committeePackReceiptTraceText}`,
    "来源 Evidence Book 同步材料包、回执与签核状态",
  ].join("\n");
  const committeeDecisionActionCurrent =
    committeeDecisionHref === "#macro-toolkit-operations-actions"
      ? selectedExecutionHref === committeeDecisionHref
      : selectedEvidenceHref === committeeDecisionHref;
  const copyCommitteePackReceipt = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (typeof writeText !== "function") {
      setCommitteePackReceiptCopyStatus("error");
      return;
    }
    try {
      await writeText.call(clipboard, committeePackReceiptCopyText);
      setCommitteePackReceiptCopyStatus("success");
    } catch {
      setCommitteePackReceiptCopyStatus("error");
    }
  }, [committeePackReceiptCopyText]);
  const handleCommitteeDecisionActionClick = useCallback(
    (event: ReactMouseEvent<HTMLAnchorElement>) => {
      if (committeeDecisionHref === "#macro-toolkit-data-health-detail") {
        event.preventDefault();
        focusDataHealthRepair();
        return;
      }
      if (committeeDecisionHref === "#macro-toolkit-operations-actions") {
        setSelectedExecutionHref(committeeDecisionHref);
        setSelectedGovernanceFocus("execution");
        return;
      }
      setSelectedEvidenceHref(committeeDecisionHref);
      setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(committeeDecisionHref));
    },
    [committeeDecisionHref, focusDataHealthRepair],
  );
  const houseViewDossierItems = [
    {
      label: "观点依据",
      value: primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : (analysis?.conclusion.stance ?? "证据待确认"),
      detail: analysis
        ? `证据覆盖 ${formatPercent(analysis.coverage.hit_rate)} · ${sourceHitCount}/${sourceChecks.length || 0} 源命中`
        : "证据覆盖待确认",
    },
    {
      label: "触发条件",
      value: committeeDecisionAction,
      detail: `${committeeDecisionBlocker} · 责任人 ${committeeDecisionOwner}`,
    },
    {
      label: "风险反证",
      value: committeeWorkQueueBlockCount ? `${committeeWorkQueueBlockCount} 个硬阻断` : "反证可审",
      detail: committeePackReceiptReviewCount
        ? `${committeePackReceiptReviewCount} 项回执待复核`
        : `${committeeWorkQueuePendingCount} 项待确认`,
    },
  ];
  const committeeDeliverySteps = [
    {
      label: "结论",
      value: committeeDecisionStatus,
      detail: committeeDecisionBlocker,
    },
    {
      label: "证据",
      value: `${committeeChecklistPassCount}/${committeeChecklistItems.length}`,
      detail: `${committeePackReviewReadyCount}/${committeePackItems.length} 项材料可审`,
    },
    {
      label: "执行",
      value: committeeDecisionAction,
      detail: committeeDecisionOwner,
    },
    {
      label: "回执",
      value: `${actionReceipts.length}`,
      detail: committeePackReceiptReviewCount ? `${committeePackReceiptReviewCount} 项待复核` : "回执已归档",
    },
    {
      label: "签核",
      value: `${committeeSignoffReadyCount}/${committeeSignoffLaneSummaryItems.length}`,
      detail: committeeSignoffReadyCount === committeeSignoffLaneSummaryItems.length ? "签核轨道已就绪" : "等待责任人确认",
    },
  ];
  const committeeDeliveryChain = (
    <section className="macro-toolkit-committee-delivery-chain" aria-label="投委会交付链">
      <div className="macro-toolkit-committee-delivery-chain__summary">
        <span>投委会交付链</span>
        <strong>{committeeDecisionStatus}</strong>
        <small>下一步：{committeeDecisionAction}</small>
      </div>
      <div className="macro-toolkit-committee-delivery-chain__steps">
        {committeeDeliverySteps.map((step) => (
          <div className="macro-toolkit-committee-delivery-chain__step" key={step.label}>
            <span>{step.label}</span>
            <strong>{step.value}</strong>
            <small>{step.detail}</small>
          </div>
        ))}
      </div>
    </section>
  );
  const observationBoundaryPanel = !showOperations ? (
    <div className="macro-toolkit-observation-boundaries">
      <MacroToolkitContractBoundary
        formalUseAllowed={analysisMeta?.formal_use_allowed}
        resultKind={analysisMeta?.result_kind}
        ruleVersion={analysisMeta?.rule_version}
        plainLanguage
      />
      <Alert
        type="info"
        showIcon
        data-testid="macro-observation-readonly-boundary"
        message="只读宏观观察"
        description="本页只展示宏观分析证据；刷新、脚本执行和运营注册表保留在宏观工具页。"
      />
    </div>
  ) : null;
  const observationFirstScreenLoop =
    !showOperations ? (
      <div className="macro-toolkit-observation-loop" aria-label="宏观观察首屏闭环">
        <div className="macro-toolkit-observation-loop__head">
          <span>观察闭环</span>
          <strong>{analysis?.as_of_date ?? "日期待确认"}</strong>
        </div>
        <div className="macro-toolkit-observation-loop__grid">
          <div>
            <span>当前判断</span>
            <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
            <small>{formatObservationRecommendation(analysis?.conclusion.recommended_action)}</small>
          </div>
          <div>
            <span>关键证据</span>
            <strong>{primarySignal ? formatObservationSignalTitle(primarySignal) : "证据待确认"}</strong>
            <small>
              {analysis?.default_data_sources?.length
                ? `已接入 ${analysis.default_data_sources.length} 类系统数据源；`
                : "来源待确认；"}
              {primarySignal ? formatObservationEvidence(primarySignal.evidence) : "观察证据待补齐"}
            </small>
          </div>
          <div>
            <span>使用边界</span>
            <strong>只读观察</strong>
            <small>不作为正式投资信号；刷新、脚本和完整审计留在宏观工具页。</small>
          </div>
        </div>
      </div>
    ) : null;

  useEffect(() => {
    if (fullAnalysisEnvelope || analysisQuery.data?.result.runtime_status?.analysis_scope !== "core") {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      void queryClient.prefetchQuery({
        queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
        queryFn: fetchFullAnalysis,
        staleTime: MACRO_TOOLKIT_READ_STALE_MS,
      });
    }, MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [analysisQuery.data?.result.runtime_status?.analysis_scope, fetchFullAnalysis, fullAnalysisEnvelope, queryClient]);

  const loadFullAnalysis = useCallback(async (options?: { force?: boolean }) => {
    setIsLoadingFullAnalysis(true);
    setFullAnalysisError(null);
    try {
      await queryClient.cancelQueries({ queryKey: ["macro-toolkit", "strategy-summaries"] });
      if (options?.force) {
        await queryClient.cancelQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
        queryClient.removeQueries({ queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY });
      }
      const response = await queryClient.fetchQuery({
        queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
        queryFn: fetchFullAnalysis,
        staleTime: MACRO_TOOLKIT_READ_STALE_MS,
      });
      setFullAnalysisEnvelope(response);
      return response;
    } catch (error) {
      setFullAnalysisError(formatQueryError(error));
      return null;
    } finally {
      setIsLoadingFullAnalysis(false);
    }
  }, [fetchFullAnalysis, queryClient]);

  const reviewFullAnalysisRepair = useCallback(async (item: MacroToolkitRepairItem) => {
    const receiptId = nextActionReceiptId("full-analysis");
    const receiptDecision = actionReceiptDecisionFields("full-analysis");
    const target = formatDataHealthRepairLabel(item, false);
    setFocusedRepairKey(repairItemFocusKey(item));
    setCommitteeActionLocatorKey(repairItemFocusKey(item));
    setSelectedEvidenceHref("#macro-toolkit-data-health-detail");
    setSelectedGovernanceFocus("data-health");
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "完整分析复核",
      status: "running",
      time: "进行中",
      target,
      artifact: "完整分析读取中",
      nextStep: "等待完整分析返回后复核数据健康",
    });
    const response = await loadFullAnalysis({ force: item.scope === "full" });
    if (response) {
      const fullRepairCount = response.result.data_health?.repair_items?.length ?? 0;
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "完整分析复核",
        status: "completed",
        time: "刚刚",
        target,
        artifact: fullRepairCount ? `完整分析仍有 ${fullRepairCount} 项待处理` : "完整分析已返回",
        nextStep: "复核完整分析回执并确认数据健康签核",
      });
      return response;
    }
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "完整分析复核",
      status: "failed",
      time: "刚刚",
      target,
      artifact: fullAnalysisError ?? "完整分析读取失败",
      nextStep: "检查完整分析读取权限和接口状态",
    });
    return null;
  }, [fullAnalysisError, loadFullAnalysis, recordActionReceipt]);

  const reviewCurrentFullAnalysisRepair = useCallback(() => {
    if (!currentRepairItem || !currentRepairNeedsFullAnalysisReview || currentRepairReceipt) return;
    void reviewFullAnalysisRepair(currentRepairItem);
  }, [currentRepairItem, currentRepairNeedsFullAnalysisReview, currentRepairReceipt, reviewFullAnalysisRepair]);

  const refreshMacroSourceBackfill = useCallback(
    async (item: MacroToolkitRepairItem, gapGroup?: CrisisGapGroup) => {
      const alias = normalizeMacroSourceBackfillAlias(item.alias);
      if (!alias || !canRefreshMacroSourceBackfill(item)) {
        return;
      }
      const receiptId = nextActionReceiptId("source-backfill");
      const receiptDecision = actionReceiptDecisionFields("source-backfill");
      setRefreshingSourceAlias(alias);
      setSourceBackfillError(null);
      setSourceBackfillResult(null);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "来源补齐",
        status: "running",
        time: "进行中",
        target: alias,
        artifact: "宏观来源补齐中",
        nextStep: "等待补齐完成后重读完整分析",
      });
      if (gapGroup) {
        setCrisisGapRepairFeedback({
          groupKey: gapGroup.key,
          groupLabel: gapGroup.label,
          status: "pending",
          message: "正在补齐并重读完整分析",
          detail: item.action?.label ?? alias,
        });
      }
      try {
        const response = await client.refreshMacroSourceBackfill({
          alias,
          endDate: item.reference_date ?? analysis?.as_of_date ?? undefined,
          sources: undefined,
        });
        const refresh = response.result.refresh;
        const resultMessage = `来源补齐完成：${refresh.alias} 新增 ${refresh.total_added} 行`;
        setSourceBackfillResult(resultMessage);
        recordActionReceipt({
          id: receiptId,
          ...receiptDecision,
          action: "来源补齐",
          status: "completed",
          time: "刚刚",
          target: alias,
          artifact: `新增 ${refresh.total_added} 行`,
          nextStep: "重读完整分析并复核数据健康",
        });
        await clearFullAnalysisCache({ preserveCrisisGapRepairFeedback: Boolean(gapGroup) });
        const reloaded = await loadFullAnalysis();
        if (gapGroup) {
          setCrisisGapRepairFeedback(buildCrisisGapRepairFeedback(gapGroup, reloaded, resultMessage));
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "来源补齐失败";
        setSourceBackfillError(errorMessage);
        recordActionReceipt({
          id: receiptId,
          ...receiptDecision,
          action: "来源补齐",
          status: "failed",
          time: "刚刚",
          target: alias,
          artifact: errorMessage,
          nextStep: "检查来源补齐授权和数据源",
        });
        if (gapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: gapGroup.key,
            groupLabel: gapGroup.label,
            status: "failed",
            message: "补齐失败，缺口仍需处理",
            detail: errorMessage,
          });
        }
      } finally {
        setRefreshingSourceAlias(null);
      }
    },
    [analysis?.as_of_date, clearFullAnalysisCache, client, loadFullAnalysis, recordActionReceipt],
  );

  const runSelectedScript = useCallback(async () => {
    if (!selectedScript) {
      return;
    }
    const receiptId = nextActionReceiptId("script");
    const receiptDecision = actionReceiptDecisionFields("script");
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "运行脚本",
      status: "running",
      time: "进行中",
      target: selectedScript.name,
      artifact: payload?.output_dir ?? "data/macro_toolkit/output",
      nextStep: "等待脚本返回后核对脚本产物",
    });
    try {
      const result = await client.runMacroToolkitScript(selectedScript.name);
      setRunResult(result);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "运行脚本",
        status: result.status === "completed" ? "completed" : result.status === "timeout" ? "warning" : "failed",
        time: "刚刚",
        target: selectedScript.name,
        artifact: `输出文件 ${result.output_files.length} · 退出码 ${result.exit_code ?? "无"}`,
        nextStep: "核对脚本产物与注册表状态",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "运行失败";
      setRunError(errorMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "运行脚本",
        status: "failed",
        time: "刚刚",
        target: selectedScript.name,
        artifact: errorMessage,
        nextStep: "检查脚本注册表和运行日志",
      });
    } finally {
      setIsRunning(false);
    }
  }, [
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    payload?.output_dir,
    recordActionReceipt,
    scriptsQuery,
    selectedScript,
    strategyQuery,
  ]);

  const refreshCffexMemberRank = useCallback(async () => {
    const receiptId = nextActionReceiptId("cffex");
    const receiptDecision = actionReceiptDecisionFields("cffex");
    setIsRefreshingCffex(true);
    setRefreshError(null);
    setRefreshResult(null);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "刷新 CFFEX 席位",
      status: "running",
      time: "进行中",
      target: "CFFEX 席位",
      artifact: "中金所席位读取中",
      nextStep: "等待刷新完成后核对席位状态",
    });
    try {
      const response = await client.refreshCffexMemberRank({
        tradeDate: analysis?.as_of_date ?? undefined,
      });
      const rank = response.result.cffex_member_rank;
      setRefreshResult(`刷新完成：${rank.row_count} 行，最新交易日 ${rank.latest_trade_date ?? "缺失"}`);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新 CFFEX 席位",
        status: "completed",
        time: "刚刚",
        target: "CFFEX 席位",
        artifact: `中金所席位 ${rank.row_count} 行 · ${rank.latest_trade_date ?? "日期缺失"}`,
        nextStep: "核对 CFFEX席位状态",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "刷新席位失败";
      setRefreshError(errorMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新 CFFEX 席位",
        status: "failed",
        time: "刚刚",
        target: "CFFEX 席位",
        artifact: errorMessage,
        nextStep: "检查席位刷新权限和数据源",
      });
    } finally {
      setIsRefreshingCffex(false);
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const refreshChoiceStock = useCallback(async () => {
    const receiptId = nextActionReceiptId("choice-stock");
    const receiptDecision = actionReceiptDecisionFields("choice-stock");
    setIsRefreshingChoiceStock(true);
    setStockRefreshError(null);
    setStockRefreshResult("正在刷新股票历史数据和完整因子");
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: "刷新股票策略",
      status: "running",
      time: "进行中",
      target: "Choice 股票历史 + 因子",
      artifact: "等待异步任务完成",
      nextStep: "完成后核对策略供数闭环",
    });
    try {
      const refresh = await runPollingTask<MacroToolkitChoiceStockRefreshRun>({
        start: async () => {
          const response = await client.refreshChoiceStock({
            asOfDate: analysis?.as_of_date ?? undefined,
            refreshHistory: true,
            refreshFactors: true,
            factorMaxStockCount: null,
          });
          return response.result.refresh;
        },
        getStatus: async (runId) => {
          const response = await client.getChoiceStockRefreshStatus(runId);
          return response.result.refresh;
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        onUpdate: (payload) => {
          setStockRefreshResult(
            payload.status === "completed"
              ? `刷新完成：历史 ${payload.history_row_count ?? "-"} 行，因子 ${payload.factor_row_count ?? "-"} 行`
              : `刷新状态：${payload.status}`,
          );
        },
      });
      if (refresh.status !== "completed") {
        throw new Error(refresh.error_message ?? `股票刷新未完成：${refresh.status}`);
      }
      setStockRefreshResult(
        `刷新完成：历史 ${refresh.history_row_count ?? "-"} 行，因子 ${refresh.factor_row_count ?? "-"} 行`,
      );
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新股票策略",
        status: "completed",
        time: "刚刚",
        target: "Choice 股票历史 + 因子",
        artifact: `历史 ${refresh.history_row_count ?? "-"} 行 · 因子 ${refresh.factor_row_count ?? "-"} 行`,
        nextStep: "核对策略展示和刷新状态",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "刷新股票数据失败";
      setStockRefreshError(errorMessage);
      setStockRefreshResult(null);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新股票策略",
        status: "failed",
        time: "刚刚",
        target: "Choice 股票历史 + 因子",
        artifact: errorMessage,
        nextStep: "检查 Choice 授权和异步任务状态",
      });
    } finally {
      setIsRefreshingChoiceStock(false);
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const committeeDecisionButtonAction =
    hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem?.key === "strategy-supply"
      ? committeeLeadReceipt
        ? {
            label: "复核策略供数回执",
            onClick: () => {
              confirmActionReceipt(committeeLeadReceipt.id);
              setSelectedEvidenceHref("#macro-toolkit-strategy-detail");
              setSelectedGovernanceFocus("execution");
            },
            busy: false,
            status: "确认签核",
          }
        : {
            label: "执行策略供数刷新",
            onClick: () => {
              setSelectedExecutionHref("#macro-toolkit-operations-actions");
              setSelectedGovernanceFocus("execution");
              void refreshChoiceStock();
            },
            busy: isRefreshingChoiceStock,
            status: "生成回执",
          }
      : hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem?.key === "tool-execution"
        ? committeeLeadReceipt
          ? {
              label: "复核工具执行回执",
              onClick: () => {
                confirmActionReceipt(committeeLeadReceipt.id);
                setSelectedEvidenceHref(committeeLeadReceipt.evidenceHref);
                setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(committeeLeadReceipt.evidenceHref));
              },
              busy: false,
              status: "确认签核",
            }
          : {
              label: "复核工具执行结果",
              onClick: () => {
                setSelectedExecutionHref("#macro-toolkit-operations-actions");
                setSelectedGovernanceFocus("execution");
                void runSelectedScript();
              },
              busy: isRunning || !selectedScript,
              status: selectedScript ? "生成回执" : "等待脚本",
          }
      : null;
  const evidenceBookRowAction = (item: MacroToolkitCommitteePackItem): MacroToolkitEvidenceBookRowAction => {
    const href = item.receipt?.evidenceHref ?? item.href;
    if (item.receiptConfirmed) {
      return {
        label: "查看签核证据",
        status: "签核已确认",
        kind: "link",
        href,
      };
    }
    if (item.receipt) {
      const receipt = item.receipt;
      return {
        label:
          item.key === "data-health"
            ? "复核数据健康回执"
            : item.key === "strategy-supply"
              ? "复核策略供数回执"
              : item.key === "tool-execution"
                ? "复核工具执行回执"
                : "复核回执",
        status: "确认签核",
        kind: "button",
        onClick: () => {
          confirmActionReceipt(receipt.id);
          setSelectedEvidenceHref(receipt.evidenceHref);
          setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(receipt.evidenceHref));
        },
      };
    }
    if (item.key === "data-health" && item.status === "blocking") {
      const repairItem = primaryActionableRepairItem ?? primaryRepairItem;
      return {
        label: currentRepairNeedsFullAnalysisReview ? "复核完整分析" : "处理数据缺口",
        status: repairItem ? "生成回执" : "等待缺口",
        kind: "button",
        disabled: !repairItem,
        busy: Boolean(repairItem?.alias && refreshingSourceAlias === normalizeMacroSourceBackfillAlias(repairItem.alias)),
        onClick: () => {
          if (!repairItem) return;
          if (needsFullAnalysisReview(repairItem)) {
            void reviewFullAnalysisRepair(repairItem);
            return;
          }
          void refreshMacroSourceBackfill(repairItem);
        },
      };
    }
    if (item.key === "strategy-supply" && item.status === "pending") {
      return {
        label: "执行策略供数刷新",
        status: "生成回执",
        kind: "button",
        busy: isRefreshingChoiceStock,
        onClick: () => {
          setSelectedExecutionHref("#macro-toolkit-operations-actions");
          setSelectedGovernanceFocus("execution");
          void refreshChoiceStock();
        },
      };
    }
    if (item.key === "tool-execution" && item.status === "pending") {
      return {
        label: "复核工具执行结果",
        status: selectedScript ? "生成回执" : "等待脚本",
        kind: "button",
        busy: isRunning,
        disabled: !selectedScript,
        onClick: () => {
          setSelectedExecutionHref("#macro-toolkit-operations-actions");
          setSelectedGovernanceFocus("execution");
          void runSelectedScript();
        },
      };
    }
    return {
      label: committeePackEvidenceEntryLabel(item),
      status: committeePackReceiptStatus(item),
      kind: "link",
      href,
    };
  };
  const committeePrimaryActionMovedToPipeline = !committeeDecisionButtonAction && committeeDecisionAction === "处理数据缺口";
  const renderCommitteeDecisionAction = (
    variant: "memo" | "compact" | "readiness" | "redline" | "tile" | "house" | "pipeline",
  ) => {
    const actionInner =
      variant === "memo" || variant === "compact" ? (
        <>
          <span>{variant === "memo" ? "下一动作" : "硬阻断"}</span>
          {variant === "compact" ? <strong>{committeeDecisionBlocker}</strong> : <small>执行下一动作</small>}
          {variant === "compact" ? <small>{committeeDecisionButtonAction?.label ?? committeeDecisionAction}</small> : <strong>{committeeDecisionButtonAction?.label ?? committeeDecisionAction}</strong>}
        </>
      ) : variant === "house" ? (
        <>
          <span>下一动作</span>
          <strong>{committeeDecisionButtonAction?.label ?? committeeDecisionAction}</strong>
          <small>{committeeDecisionButtonAction?.status ?? committeeDecisionBlocker}</small>
        </>
      ) : variant === "readiness" ? (
        committeeDecisionButtonAction?.label ?? committeeDecisionAction
      ) : variant === "pipeline" ? (
        <>
          <span>流水线下一步</span>
          <strong>{committeeDecisionButtonAction?.label ?? committeeDecisionAction}</strong>
          <small>{committeeDecisionButtonAction?.status ?? `${committeeLeadChecklistItem?.condition ?? "工具执行"}回执`}</small>
        </>
      ) : variant === "redline" ? (
        "证据入口"
      ) : (
        committeeDecisionButtonAction?.label ?? committeeDecisionAction
      );

    if (committeeDecisionButtonAction) {
      return (
        <button
          type="button"
          className={`macro-toolkit-committee-action macro-toolkit-committee-action--${variant}`}
          disabled={committeeDecisionButtonAction.busy}
          aria-current={committeeDecisionActionCurrent ? "true" : undefined}
          aria-label={variant === "pipeline" ? `流水线下一步 ${committeeDecisionButtonAction.label}` : committeeDecisionButtonAction.label}
          onClick={committeeDecisionButtonAction.onClick}
        >
          {actionInner}
          {variant === "readiness" || variant === "redline" || variant === "tile" ? (
            <small>{committeeDecisionButtonAction.status}</small>
          ) : null}
        </button>
      );
    }

    return (
      <a
        className={`macro-toolkit-committee-action macro-toolkit-committee-action--${variant}`}
        href={committeeDecisionHref}
        aria-current={committeeDecisionActionCurrent ? "true" : undefined}
        onClick={handleCommitteeDecisionActionClick}
      >
        {actionInner}
      </a>
    );
  };

  const refreshCommodityFutures = useCallback(async (options?: CommodityRefreshOptions) => {
    const dryRun = options?.dryRun ?? false;
    const products = options?.products ?? selectedCommodityProducts;
    const receiptId = nextActionReceiptId(dryRun ? "commodity-dry-run" : "commodity-refresh");
    const receiptDecision = actionReceiptDecisionFields(dryRun ? "commodity-dry-run" : "commodity-refresh");
    if (products.length === 0) {
      setCommodityRefreshError("请至少选择一个商品期货品种");
      setCommodityRefreshResult(null);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      return;
    }
    if (options?.products && !sameCommodityProducts(selectedCommodityProducts, options.products)) {
      setSelectedCommodityProducts(options.products);
    }
    if (!isCommodityRefreshAllowed) {
      setCommodityRefreshError(commodityFuturesPermissionBlockMessage(commodityPermission));
      setCommodityRefreshResult(null);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      return;
    }
    setIsRefreshingCommodity(true);
    setCommodityRefreshError(null);
    setCommodityRefreshResult(null);
    setCommodityRefreshRun(null);
    setCommoditySuggestedSelection(options?.suggestedSelection ?? []);
    setCommodityEvidenceReloadMessage(null);
    setCommodityRefreshEvidenceChain(null);
    setCommodityShortfallChanges([]);
    setCommodityShortfallEstimates([]);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: dryRun ? "预估商品期货" : "刷新商品期货",
      status: "running",
      time: "进行中",
      target: formatCommodityProducts(products),
      artifact: dryRun ? "估算写入行数" : "fact_commodity_futures_daily",
      nextStep: dryRun ? "根据预计行数决定是否正式刷新" : "刷新后核对商品期货状态",
    });
    const shouldReloadFullAnalysis = !dryRun && !isCoreAnalysis;
    const shortfallsBeforeRefresh = crisisCommodityShortItemsFromResult(crisisScoreResult);
    const commodityGapGroup = crisisGapGroupFromResult(crisisScoreResult, "commodity");
    if (shouldReloadFullAnalysis && commodityGapGroup) {
      setCrisisGapRepairFeedback({
        groupKey: commodityGapGroup.key,
        groupLabel: commodityGapGroup.label,
        status: "pending",
        message: "正在刷新并重读完整分析",
        detail: formatCommodityProducts(products),
      });
    }
    try {
      const response = await client.refreshCommodityFutures({
        startDate: options?.startDate,
        endDate: analysis?.as_of_date ?? undefined,
        products,
        dryRun,
      });
      const refresh = response.result.refresh;
      setCommodityRefreshRun(refresh);
      setCommodityRefreshResult(formatCommodityRefreshResult(refresh));
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预估商品期货" : "刷新商品期货",
        status: refresh.status === "completed" || refresh.status === "dry_run" ? "completed" : "warning",
        time: "刚刚",
        target: formatCommodityProducts(products),
        artifact: formatCommodityRefreshResult(refresh),
        nextStep: dryRun ? "根据预计行数决定是否正式刷新" : "核对商品期货状态与完整分析证据",
      });
      if (dryRun) {
        setCommodityShortfallEstimates(formatCommodityShortfallEstimates(shortfallsBeforeRefresh, refresh));
        return;
      }
      setCommodityRefreshEvidenceChain({
        suggestedProducts: options?.suggestedSelection ?? products,
        refreshedProducts: commodityRefreshRunProducts(refresh),
        fullReloaded: false,
      });
      await clearFullAnalysisCache({ preserveCrisisGapRepairFeedback: shouldReloadFullAnalysis && Boolean(commodityGapGroup) });
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      if (shouldReloadFullAnalysis) {
        setCommodityEvidenceReloadMessage("正在重新读取完整分析证据");
        const reloaded = await loadFullAnalysis({ force: true });
        const shortfallsAfterRefresh = crisisCommodityShortItemsFromEnvelope(reloaded);
        setCommodityShortfallChanges(
          formatCommodityShortfallChanges(shortfallsBeforeRefresh, shortfallsAfterRefresh),
        );
        setCommodityRefreshEvidenceChain((chain) =>
          chain
            ? {
                ...chain,
                fullReloaded: Boolean(reloaded),
              }
            : chain,
        );
        if (commodityGapGroup) {
          setCrisisGapRepairFeedback(
            buildCrisisGapRepairFeedback(commodityGapGroup, reloaded, formatCommodityRefreshResult(refresh)),
          );
        }
        setCommodityEvidenceReloadMessage(
          reloaded ? "完整分析证据已重新读取" : "完整分析证据重新读取失败，请重新完整分析",
        );
      }
    } catch (error) {
      const errorMessage = formatCommodityFuturesRefreshError(error);
      setCommodityRefreshError(errorMessage);
      setCommodityRefreshRun(null);
      setCommodityEvidenceReloadMessage(null);
      setCommodityRefreshEvidenceChain(null);
      setCommodityShortfallChanges([]);
      setCommodityShortfallEstimates([]);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预估商品期货" : "刷新商品期货",
        status: "failed",
        time: "刚刚",
        target: formatCommodityProducts(products),
        artifact: errorMessage,
        nextStep: "检查商品期货刷新授权和数据源",
      });
      if (commodityGapGroup) {
        setCrisisGapRepairFeedback({
          groupKey: commodityGapGroup.key,
          groupLabel: commodityGapGroup.label,
          status: "failed",
          message: dryRun ? "预估失败，缺口仍需处理" : "刷新失败，缺口仍需处理",
          detail: errorMessage,
        });
      }
    } finally {
      setIsRefreshingCommodity(false);
    }
  }, [
    analysis?.as_of_date,
    analysisQuery,
    clearFullAnalysisCache,
    client,
    crisisScoreResult,
    isCoreAnalysis,
    isCommodityRefreshAllowed,
    loadFullAnalysis,
    commodityPermission,
    recordActionReceipt,
    scriptsQuery,
    selectedCommodityProducts,
    strategyQuery,
  ]);

  const indicatorColumns: ColumnsType<MacroToolkitIndicator> = [
    {
      title: "指标",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{item.label}</span>
          <span className="macro-toolkit-script-file">{item.alias}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      width: 120,
      render: (group: string) => <Tag>{group}</Tag>,
    },
    {
      title: "最新值",
      dataIndex: "latest_value",
      key: "latest_value",
      width: 150,
      render: (_, item) => <IndicatorValueCell item={item} />,
    },
    {
      title: "变化",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 110,
      render: (_, item) => <DeltaCell change={item.change} changePct={item.change_pct} />,
    },
    {
      title: "日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: 120,
      render: (date: string | null, item) => (
        <div className="macro-toolkit-date-cell">
          <span>{date ?? "缺失"}</span>
          <Tag color={item.quality === "ok" ? "green" : "red"}>
            {item.quality === "ok" ? "可用" : "缺失"}
          </Tag>
        </div>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: string | null, item) => (
        <div className="macro-toolkit-source-cell">
          <span>{source ?? "未命中"}</span>
          <small>{item.series_id ?? item.alias}</small>
        </div>
      ),
    },
  ];

  const scriptColumns: ColumnsType<MacroToolkitScriptRecord> = [
    {
      title: "脚本",
      dataIndex: "name",
      key: "name",
      render: (_, script) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{script.name}</span>
          <span className="macro-toolkit-script-file">{script.filename}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      render: (group: string) => <Tag>{groupLabel(group)}</Tag>,
      width: 120,
    },
    {
      title: "数据源",
      dataIndex: "default_data_sources",
      key: "default_data_sources",
      render: (sources: string[]) => (
        <div className="macro-toolkit-tag-row">
          {sources.map((source) => (
            <Tag color={source === "choice" ? "blue" : "green"} key={source}>
              {source}
            </Tag>
          ))}
        </div>
      ),
      width: 160,
    },
    {
      title: "依赖",
      dataIndex: "optional_dependencies",
      key: "optional_dependencies",
      render: (deps: string[]) =>
        deps.length > 0 ? deps.join(" / ") : "内置",
    },
    {
      title: "状态",
      dataIndex: "available",
      key: "available",
      render: (available: boolean) => (
        <Tag color={available ? "green" : "red"}>{available ? "可运行" : "缺失"}</Tag>
      ),
      width: 100,
    },
  ];

  const capabilityColumns: ColumnsType<MacroToolkitCapability> = [
    {
      title: "功能",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">
            {item.legacy_module} · {item.label}
          </span>
          <span className="macro-toolkit-script-file">{item.group}</span>
        </div>
      ),
    },
    {
      title: "代码",
      dataIndex: "implementation_status",
      key: "implementation_status",
      width: 120,
      render: (status: string) => <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>,
    },
    {
      title: "页面/API",
      dataIndex: "route_status",
      key: "route_status",
      width: 140,
      render: (status: string, item) => (
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
          <Tag color={statusColor(item.frontend_status)}>{statusLabel(item.frontend_status)}</Tag>
        </div>
      ),
    },
    {
      title: "数据",
      dataIndex: "data_status",
      key: "data_status",
      width: 140,
      render: (status: string, item) => <CapabilityDataCell status={status} item={item} />,
    },
    {
      title: "下一步",
      dataIndex: "next_step",
      key: "next_step",
    },
  ];

  const outputColumns: ColumnsType<MacroToolkitOutputFile> = [
    { title: "文件", dataIndex: "name", key: "name" },
    {
      title: "大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: "更新时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 220,
    },
  ];

  const isAnalysisLoading = analysisQuery.isLoading && !analysis;
  const signalSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow={showOperations ? "signals" : "总览"}
        title="核心信号"
        description={
          showOperations
            ? "由系统内 Choice/Tushare 序列直接计算，脚本产物作为补充证据。"
            : "汇总宏观指标、市场风险和资金条件，保留当前观察所需的主要证据。"
        }
      />
      <div className="macro-toolkit-signal-grid">
        {visibleSignalCards.map((card) => (
          <div
            className={`macro-toolkit-signal-card macro-toolkit-signal-card--${card.tone}`}
            key={card.key}
          >
            <div className="macro-toolkit-signal-head">
              <span>{showOperations ? card.title : formatObservationSignalTitle(card)}</span>
              <Tag color={toneTagColor(card.tone)}>
                {showOperations ? card.stance : formatObservationSignalStance(card)}
              </Tag>
            </div>
            <strong>{card.score === null ? "缺失" : card.score}</strong>
            <ScoreTrack score={card.score} />
            <small>{showOperations ? card.evidence.join(" / ") : formatObservationEvidence(card.evidence)}</small>
          </div>
        ))}
      </div>
    </section>
  ) : null;
  const riskSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow={showOperations ? "risk" : "预警"}
        title="市场踩踏风险"
        description="接入宏观分析结果链路的 A股盘后宽度、跌停、成交与回落压力判断。"
      />
      <AShareRiskPanel risk={analysis.a_share_risk} />
    </section>
  ) : null;
  const observationSignalRiskComparisonSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="对照"
        title="信号风险对照"
        description="把主信号和市场踩踏风险放在同一张观察卡里，先看一致性，再看证据边界。"
      />
      <ObservationSignalRiskComparison
        signalCards={visibleSignalCards}
        primarySignal={primarySignal}
        risk={analysis.a_share_risk}
      />
    </section>
  ) : null;
  const observationSignalRiskLoadingSection = !showOperations && !analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="对照"
        title="信号风险对照"
        description="把主信号和市场踩踏风险放在同一张观察卡里，先看一致性，再看证据边界。"
      />
      <ObservationSignalRiskComparison signalCards={[]} primarySignal={null} isLoading />
    </section>
  ) : null;
  const crisisEvidenceSection =
    analysis && crisisScoreResult ? (
      <CrisisScoreEvidencePanel
        result={crisisScoreResult}
        analysisMeta={analysisMeta}
        analysisAsOfDate={analysis.as_of_date ?? null}
        repairItems={analysis.data_health?.repair_items ?? []}
        refreshingSourceAlias={refreshingSourceAlias}
        commodityRefreshResult={commodityRefreshResult}
        commodityRefreshEvidenceChain={commodityRefreshEvidenceChain}
        commodityShortfallChanges={commodityShortfallChanges}
        commodityShortfallEstimates={commodityShortfallEstimates}
        repairFeedback={crisisGapRepairFeedback}
        sourceBackfillResult={sourceBackfillResult}
        sourceBackfillError={sourceBackfillError}
        onRepairSourceBackfill={(item, group) => {
          void refreshMacroSourceBackfill(item, group);
        }}
        onApplyCommodityRefreshProducts={(products) => {
          setSelectedCommodityProducts(products);
          setCommoditySuggestedSelection(products);
          setCommodityRefreshResult(null);
          setCommodityRefreshError(null);
          setCommodityRefreshRun(null);
          setCommodityEvidenceReloadMessage(null);
          setCommodityRefreshEvidenceChain(null);
          setCommodityShortfallChanges([]);
          setCommodityShortfallEstimates([]);
        }}
        onPreviewCommodityRefreshProducts={(products) => {
          void refreshCommodityFutures({
            dryRun: true,
            products,
            suggestedSelection: products,
            startDate: suggestedCommodityRefreshStartDate(crisisScoreResult),
          });
        }}
        onRefreshCommodityProducts={(products) => {
          void refreshCommodityFutures({
            dryRun: false,
            products,
            suggestedSelection: products,
            startDate: suggestedCommodityRefreshStartDate(crisisScoreResult),
          });
        }}
      />
    ) : null;
  const strategySection = analysis ? (
    <section
      id="macro-toolkit-strategy-detail"
      data-testid="macro-toolkit-strategy-detail"
      className={`macro-toolkit-section ${
        selectedEvidenceHref === "#macro-toolkit-strategy-detail" ? "macro-toolkit-section--audit-focus" : ""
      }`}
    >
      <PageSectionLead eyebrow="strategies" title="策略展示" description={strategyDescription} />
      {showOperations ? (
        <div className="macro-toolkit-stock-refresh-panel">
          <div className="macro-toolkit-cffex-metrics">
            <MetricTile
              label="股票历史"
              value={choiceStockRefresh?.daily_observation?.stock_count ?? 0}
              detail={choiceStockTableDetail(choiceStockRefresh?.daily_observation, "latest_trade_date")}
            />
            <MetricTile
              label="完整因子"
              value={choiceStockRefresh?.factor_snapshot?.stock_count ?? 0}
              detail={choiceStockTableDetail(choiceStockRefresh?.factor_snapshot, "as_of_date")}
            />
            <MetricTile
              label="刷新状态"
              value={choiceStockRefreshValue(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
              detail={choiceStockRefreshDetail(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
            />
          </div>
          <div className="macro-toolkit-cffex-actions">
            <Button
              icon={<ReloadOutlined />}
              loading={isRefreshingChoiceStock}
              disabled={isOperationActionBusy && !isRefreshingChoiceStock}
              onClick={() => void refreshChoiceStock()}
              aria-label="刷新股票策略明细"
            >
              刷新股票策略明细
            </Button>
            {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
            {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
          </div>
        </div>
      ) : null}
      <div className="macro-toolkit-strategy-supply-strip" aria-label="策略供数闭环">
        <span className="macro-toolkit-strategy-supply-label">
          <DatabaseOutlined />
          策略供数闭环
        </span>
        {strategySupplyState === "loaded" ? (
          <>
            <span>
              <DatabaseOutlined />
              完整链路 {fullRealStrategyCount}/{strategySummaries.length}
            </span>
            <span>
              <SafetyCertificateOutlined />
              部分链路 {partialRealStrategyCount}
            </span>
            <span>
              <SafetyCertificateOutlined />
              降级 {degradedStrategyCount}
            </span>
            <span>
              <SafetyCertificateOutlined />
              样例 {sampleStrategyCount}
            </span>
          </>
        ) : (
          <span>
            <ClockCircleOutlined />
            策略供数 {statusLabel(strategySupplyState)}
          </span>
        )}
        <span>
          <ClockCircleOutlined />
          股票历史 {choiceStockTableSummary(choiceStockRefresh?.daily_observation, "latest_trade_date")}
        </span>
        <span>
          <ClockCircleOutlined />
          因子快照 {choiceStockTableSummary(choiceStockRefresh?.factor_snapshot, "as_of_date")}
        </span>
      </div>
      {!showOperations ? (
        <StrategyObservationSummary
          strategySummaries={strategySummaries}
          strategySupplyState={strategySupplyState}
          fullRealStrategyCount={fullRealStrategyCount}
          partialRealStrategyCount={partialRealStrategyCount}
          degradedStrategyCount={degradedStrategyCount}
          sampleStrategyCount={sampleStrategyCount}
          shadowPortfolioReport={shadowPortfolioReport}
        />
      ) : (
        <>
          <ShadowPortfolioReportPanel report={shadowPortfolioReport} />
          {strategySummaries.length ? (
            <div className="macro-toolkit-strategy-grid">
              {strategySummaries.map((strategy) => (
                <StrategySummaryCard strategy={strategy} key={strategy.key} />
              ))}
            </div>
          ) : strategyQuery.isFetching ? (
            <Alert
              type="info"
              showIcon
              message="策略展示正在生成"
              description="核心信号已先返回；市场踩踏风险需打开完整分析后显示。"
            />
          ) : strategyQuery.isError ? (
            <Alert type="warning" showIcon message="策略展示暂不可用" description={formatQueryError(strategyQuery.error)} />
          ) : (
            <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
          )}
        </>
      )}
      {!showOperations && strategyQuery.isFetching && !strategySummaries.length ? (
        <Alert
          type="info"
          showIcon
          message="策略展示正在生成"
          description="核心信号已先返回；完整策略证据打开完整分析后确认。"
        />
      ) : strategyQuery.isFetching ? (
        null
      ) : strategyQuery.isError ? (
        !showOperations ? (
          <Alert type="warning" showIcon message="策略展示暂不可用" description={formatQueryError(strategyQuery.error)} />
        ) : null
      ) : !showOperations && !strategySummaries.length ? (
        <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
      ) : null}
    </section>
  ) : null;
  const indicatorSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="indicators"
        title="指标矩阵"
        description={
          showOperations
            ? "展示每个宏观指标的最新值、变化、日期和数据来源。"
            : "只展示当前观察需要的指标结论；源表、行数和序列审计留在完整工具页。"
        }
      />
      {!showOperations ? (
        <IndicatorObservationSummary indicators={analysis.indicators} />
      ) : (
        <Table
          className="macro-toolkit-table--wide"
          rowKey="alias"
          size="small"
          columns={indicatorColumns}
          dataSource={analysis.indicators}
          pagination={false}
          tableLayout="fixed"
          scroll={{ x: 920 }}
          rowClassName={(item) => (item.quality === "missing" ? "macro-toolkit-row--missing" : "")}
        />
      )}
    </section>
  ) : null;
  const investmentEvidenceSection = analysis ? (
    <section
      id="macro-toolkit-strategy-detail"
      data-testid="macro-toolkit-investment-evidence-detail"
      className={`macro-toolkit-section ${
        selectedEvidenceHref === "#macro-toolkit-strategy-detail" ? "macro-toolkit-section--audit-focus" : ""
      }`}
    >
      <PageSectionLead
        eyebrow="交叉验证"
        title="投研证据摘要"
        description="合并展示策略链路、影子组合边界和指标覆盖，只保留观察结论。"
      />
      <InvestmentEvidenceSummary
        indicators={analysis.indicators}
        strategySummaries={strategySummaries}
        strategySupplyState={strategySupplyState}
        fullRealStrategyCount={fullRealStrategyCount}
        partialRealStrategyCount={partialRealStrategyCount}
        degradedStrategyCount={degradedStrategyCount}
        sampleStrategyCount={sampleStrategyCount}
        shadowPortfolioReport={shadowPortfolioReport}
      />
      {!showOperations && strategyQuery.isFetching && !strategySummaries.length ? (
        <Alert
          type="info"
          showIcon
          message="策略证据正在生成"
          description="核心信号已先返回；完整策略证据打开完整分析后确认。"
        />
      ) : strategyQuery.isError ? (
        <Alert type="warning" showIcon message="策略证据暂不可用" description={formatQueryError(strategyQuery.error)} />
      ) : null}
    </section>
  ) : null;
  const capabilityResultsSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="results"
        title="功能结果"
        description="M7-M16 已按现有宏观纯函数和正式事实表输出结果，缺口只保留为数据降级提示。"
      />
      {capabilityResults.length ? (
        <div className="macro-toolkit-capability-result-grid">
          {capabilityResults.map((result) => (
            <CapabilityResultCard result={result} key={result.key} />
          ))}
        </div>
      ) : isCoreAnalysis ? (
        <Alert
          type="info"
          showIcon
          message="M7-M16 功能结果正在生成"
          description="核心信号已先返回；市场踩踏风险和功能结果需打开完整分析后显示。"
          action={
            <Button
              aria-label="查看完整分析"
              size="small"
              icon={<LineChartOutlined />}
              loading={isLoadingFullAnalysis}
              onClick={() => void loadFullAnalysis()}
            >
              查看完整分析
            </Button>
          }
        />
      ) : (
        <div className="macro-toolkit-empty-output">暂无 M7-M16 功能结果。</div>
      )}
    </section>
  ) : null;
  const hasonStrategySection = hasonStrategy ? (
    <HasonMacroStrategyPanel strategy={hasonStrategy} variant={showOperations ? "detail" : "observation"} />
  ) : null;
  const observationEvidenceTraceSummary = analysis ? (
    <ObservationEvidenceTraceSummary
      dataHealth={analysis.data_health}
      capabilityResults={capabilityResults}
      degradedResultCount={degradedResultCount}
      hasonStrategy={hasonStrategy ?? undefined}
      isCoreAnalysis={isCoreAnalysis}
    />
  ) : null;
  const analysisWarningsAlert = analysis?.warnings.length ? (
    <Alert type="warning" showIcon message="分析限制" description={analysis.warnings.join(" ")} />
  ) : null;
  const investmentBriefPanel = showOperations ? (
    <div
      className="macro-toolkit-investment-brief"
      data-testid="macro-toolkit-investment-brief"
      aria-label="宏观工具投委会摘要"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>Investment Committee Brief</span>
        <strong>{analysis?.as_of_date ?? "日期待确认"}</strong>
      </div>
      <div className="macro-toolkit-committee-first-screen-pipeline" aria-label="投委会首屏流水线">
        <div className="macro-toolkit-committee-first-screen-pipeline__head">
          <span>投委会首屏流水线</span>
          <strong>{committeeDecisionStatus}</strong>
          <small>{committeeRedlineTitle}</small>
        </div>
        <div className="macro-toolkit-committee-first-screen-pipeline__step">
          <span>结论</span>
          <strong>{committeeDecisionStatus}</strong>
          <small>
            提交包 {committeePackReviewReadyCount}/{committeePackItems.length}
          </small>
        </div>
        <div className="macro-toolkit-committee-first-screen-pipeline__step">
          <span>首要卡点</span>
          <strong>{committeeDecisionBlocker}</strong>
          <small>{committeeDecisionOwner}</small>
        </div>
        <div className="macro-toolkit-committee-first-screen-pipeline__step macro-toolkit-committee-first-screen-pipeline__step--action">
          {renderCommitteeDecisionAction("pipeline")}
        </div>
        <div className="macro-toolkit-committee-first-screen-pipeline__step">
          <span>签核</span>
          <strong>
            {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
          </strong>
          <small>待复核回执 {committeePackReceiptReviewCount}</small>
        </div>
      </div>
      <div className="macro-toolkit-committee-decision-memo" aria-label="投委会决策稿">
        <div className="macro-toolkit-committee-decision-memo__verdict">
          <span>投委会决策稿</span>
          <strong>
            <small>结论</small>
            {committeeDecisionStatus}
          </strong>
          <em>{committeeRedlineTitle}</em>
        </div>
        <div className="macro-toolkit-committee-decision-memo__grid">
          <div>
            <span>阻断</span>
            <strong>{committeeDecisionBlocker}</strong>
            <small>{committeeDecisionOwner}</small>
          </div>
          {committeePrimaryActionMovedToPipeline ? (
            <div className="macro-toolkit-committee-decision-memo__rationale">
              <span>判断口径</span>
              <strong>{committeeDecisionAction}</strong>
              <small>主入口在首屏流水线</small>
            </div>
          ) : (
            renderCommitteeDecisionAction("memo")
          )}
          <div>
            <span>放行条件</span>
            <strong>
              提交包 {committeePackReviewReadyCount}/{committeePackItems.length} · 签核 {committeeSignoffReadyCount}/
              {committeeSignoffLaneSummaryItems.length}
            </strong>
            <small>
              硬阻断 {committeeWorkQueueBlockCount} · 待复核回执 {committeePackReceiptReviewCount}
            </small>
          </div>
        </div>
      </div>
      <div className="macro-toolkit-committee-next-step-strip" aria-label="投委会下一步执行条">
        <div className="macro-toolkit-committee-next-step-strip__verdict">
          <span>投委会下一步执行条</span>
          <strong>{committeeDecisionStatus}</strong>
          <small>{committeeRedlineTitle}</small>
        </div>
        <div className="macro-toolkit-committee-next-step-strip__action">
          <span>主入口已上移</span>
          <strong>流水线下一步：{committeeDecisionButtonAction?.label ?? committeeDecisionAction}</strong>
          <small>{committeeDecisionButtonAction?.status ?? committeeDecisionBlocker}</small>
        </div>
        <div>
          <span>责任人</span>
          <strong>{committeeDecisionOwner}</strong>
          <small>{committeeDecisionBlocker}</small>
        </div>
        <div>
          <span>回执要求</span>
          <strong>{committeeLeadChecklistItem?.condition ?? "工具执行"}回执</strong>
          <small>完成后进入签核留痕</small>
        </div>
      </div>
      <div className="macro-toolkit-mobile-committee-strip" aria-label="投委会移动首屏摘要">
        <div>
          <span>提交判断</span>
          <strong>{committeeDecisionStatus}</strong>
        </div>
        {renderCommitteeDecisionAction("compact")}
        <div>
          <span>提交包</span>
          <strong>
            {committeePackReviewReadyCount}/{committeePackItems.length}
          </strong>
        </div>
        <div>
          <span>签核</span>
          <strong>
            {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
          </strong>
        </div>
      </div>
      <div
        className={`macro-toolkit-committee-final-signoff macro-toolkit-committee-final-signoff--${
          isCommitteeFinalSignoffReady ? "ready" : "blocked"
        }`}
        aria-label="最终投委会签核态"
      >
        <div className="macro-toolkit-committee-final-signoff__decision">
          <span>最终投委会签核态</span>
          <strong>{committeeFinalSignoffStatus}</strong>
          <small>{committeeFinalSignoffOwner}</small>
        </div>
        <div className="macro-toolkit-committee-final-signoff__metrics">
          <div>
            <span>提交包</span>
            <strong>
              提交包 {committeeFinalPackValue}
            </strong>
          </div>
          <div>
            <span>签核</span>
            <strong>签核 {committeeFinalSignoffValue}</strong>
          </div>
          <div>
            <span>剩余风险</span>
            <strong>剩余风险 {committeeFinalResidualRiskValue}</strong>
          </div>
          <div>
            <span>回执</span>
            <strong>待复核回执 {committeeFinalReceiptReviewValue}</strong>
          </div>
        </div>
      </div>
      <div className="macro-toolkit-committee-readiness" data-testid="macro-toolkit-committee-readiness">
        <div className="macro-toolkit-committee-readiness__decision">
          <span>投委会复核状态</span>
          <strong>{committeeDecisionStatus}</strong>
        </div>
        <div>
          <span>主要卡点</span>
          <strong>{committeeDecisionBlocker}</strong>
        </div>
        <div>
          <span>责任人</span>
          <strong>{committeeDecisionOwner}</strong>
        </div>
        <div className="macro-toolkit-committee-readiness__action">
          {committeePrimaryActionMovedToPipeline ? (
            <>
              <span>执行说明</span>
              <strong>{committeeDecisionAction}</strong>
              <small>首屏流水线承接</small>
            </>
          ) : (
            <>
              <span>行动入口</span>
              {renderCommitteeDecisionAction("readiness")}
            </>
          )}
        </div>
      </div>
      <div className="macro-toolkit-current-repair-status" aria-label="投委会当前处理状态">
        <div className="macro-toolkit-current-repair-status__head">
          <span>当前处理状态</span>
          <strong>{currentRepairStatus}</strong>
        </div>
        <div className="macro-toolkit-current-repair-status__tape" aria-label="当前处理执行带">
          <div className="macro-toolkit-current-repair-status__tape-item macro-toolkit-current-repair-status__tape-item--primary">
            <span>执行带 · 当前处理单</span>
            <strong>{currentRepairLabel}</strong>
            <small>{currentRepairStatus}</small>
          </div>
          <div className="macro-toolkit-current-repair-status__tape-item">
            <span>责任人/SLA</span>
            <strong>{currentRepairItem ? repairTicketOwner(currentRepairItem) : committeeReadinessOwner}</strong>
            <small>{currentRepairItem ? repairTicketSla(currentRepairItem) : "持续留痕"}</small>
          </div>
          <div className="macro-toolkit-current-repair-status__tape-item">
            <span>预期回执 / 回执状态</span>
            <strong>{currentRepairItem ? repairTicketReceipt(currentRepairItem) : "数据健康快照"}</strong>
            <small>{currentRepairReceipt ? currentRepairStatus : "等待执行"}</small>
          </div>
          <div className="macro-toolkit-current-repair-status__tape-item">
            <span>回执证据/签核</span>
            <strong>{currentRepairReceipt?.evidenceEntry ?? "等待执行"}</strong>
            <small>{currentRepairReceiptConfirmed ? "签核完成" : currentRepairReceipt ? "待复核签核" : "回执后签核"}</small>
          </div>
          {currentRepairNeedsSignoff ? (
            <button
              type="button"
              className="macro-toolkit-current-repair-status__tape-action"
              aria-label={currentRepairAction}
              aria-current={selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? "true" : undefined}
              onClick={confirmCurrentRepairReceipt}
            >
              <span>下一动作</span>
              <strong>{currentRepairAction}</strong>
              <small>确认签核</small>
            </button>
          ) : currentRepairNeedsFullAnalysisReview && currentRepairItem ? (
            <button
              type="button"
              className="macro-toolkit-current-repair-status__tape-action"
              aria-label={currentRepairAction}
              aria-current={selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? "true" : undefined}
              disabled={isLoadingFullAnalysis}
              onClick={reviewCurrentFullAnalysisRepair}
            >
              <span>下一动作</span>
              <strong>{currentRepairAction}</strong>
              <small>生成回执</small>
            </button>
          ) : currentRepairPrimaryActionMovedToPipeline ? (
            <div className="macro-toolkit-current-repair-status__tape-action macro-toolkit-current-repair-status__tape-action--audit">
              <span>审计状态</span>
              <strong>主入口在首屏流水线</strong>
              <small>{currentRepairAction}</small>
            </div>
          ) : (
            <a
              className="macro-toolkit-current-repair-status__tape-action"
              href="#macro-toolkit-data-health-detail"
              aria-label={currentRepairAction}
              aria-current={selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? "true" : undefined}
              onClick={handleDataHealthRepairActionClick}
            >
              <span>下一动作</span>
              <strong>{currentRepairAction}</strong>
              <small>打开处理单</small>
            </a>
          )}
        </div>
        {repairItemCount ? (
          <div className="macro-toolkit-current-repair-status__triage" aria-label="投委会阻断分层">
            {repairTriageItems.map((item) => (
              <div
                key={item.key}
                className={`macro-toolkit-current-repair-status__triage-item macro-toolkit-current-repair-status__triage-item--${item.key}`}
              >
                <span>{item.label}</span>
                <strong>{item.count} 项</strong>
                <em>{item.owner}</em>
                <small>{item.sample}</small>
                <b>{item.action}</b>
              </div>
            ))}
          </div>
        ) : null}
        {currentRepairItem && currentRepairNeedsFullAnalysisReview ? (
          <div className="macro-toolkit-current-repair-status__full-review" aria-label="完整分析复核包">
            <span>完整分析复核包</span>
            <strong>延后证据待确认</strong>
            <em>完整分析回执</em>
            <small>提交影响 · {repairTicketSubmissionImpact(currentRepairItem)}</small>
            <small>
              {repairTicketOwner(currentRepairItem)} · {repairTicketSla(currentRepairItem)}
            </small>
          </div>
        ) : null}
        {currentRepairItem && currentRepairNeedsManualEscalation ? (
          <div className="macro-toolkit-current-repair-status__manual" aria-label="人工复核升级处理包">
            <span>人工复核升级处理包</span>
            <strong>不可自动补齐</strong>
            <em>升级处理</em>
            <small>提交影响 · {repairTicketSubmissionImpact(currentRepairItem)}</small>
            <small>
              {repairTicketOwner(currentRepairItem)} · {repairTicketSla(currentRepairItem)}
            </small>
          </div>
        ) : null}
        {committeeActionLocatorItem && selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? (
          <div
            className="macro-toolkit-current-repair-status__locator"
            ref={committeeActionLocatorRef}
            aria-label="投委会动作定位回执"
            aria-live="polite"
          >
            <span>动作已定位</span>
            <strong>{committeeActionLocatorLabel}</strong>
            <em>{repairTicketOwner(committeeActionLocatorItem)}</em>
            <small>{repairTicketReceipt(committeeActionLocatorItem)}</small>
            <a href="#macro-toolkit-data-health-detail">打开处理单</a>
            {canRefreshMacroSourceBackfill(committeeActionLocatorItem) && !completedDataHealthReceipt ? (
              <button
                type="button"
                disabled={
                  refreshingSourceAlias === normalizeMacroSourceBackfillAlias(committeeActionLocatorItem.alias)
                }
                onClick={() => {
                  void refreshMacroSourceBackfill(committeeActionLocatorItem);
                }}
              >
                执行来源补齐
              </button>
            ) : needsFullAnalysisReview(committeeActionLocatorItem) && !completedDataHealthReceipt ? (
              <button
                type="button"
                disabled={isLoadingFullAnalysis}
                onClick={() => {
                  void reviewFullAnalysisRepair(committeeActionLocatorItem);
                }}
              >
                复核完整分析
              </button>
            ) : needsManualReviewEscalation(committeeActionLocatorItem) ? (
              <>
                <small>不可自动补齐</small>
                <small>提交影响 · {repairTicketSubmissionImpact(committeeActionLocatorItem)}</small>
                <small>升级处理</small>
              </>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="macro-toolkit-committee-closure-rail" aria-label="投委会闭环流水线">
        <div className="macro-toolkit-committee-closure-rail__head">
          <span>状态轴 · 辅助留痕</span>
          <strong>{currentRepairStatus}</strong>
        </div>
        <div className="macro-toolkit-committee-closure-rail__axis" aria-label="投委会闭环状态轴">
          <span className="macro-toolkit-committee-closure-rail__axis-label">状态轴</span>
          {committeeClosureRailItems.map((item) => {
            const stepContents = (
              <>
                <span>{item.step}</span>
                <strong>{item.phase}</strong>
                <em>{item.status}</em>
                <small>{item.detail}</small>
                <b>{item.action}</b>
              </>
            );
            const className = `macro-toolkit-committee-closure-rail__step macro-toolkit-committee-closure-rail__step--${item.tone}`;
            const isCurrent =
              selectedEvidenceHref === "#macro-toolkit-data-health-detail" && item.tone === "active"
                ? "true"
                : undefined;
            const signoffReceiptId = item.receiptId;
            const signoffAriaLabel = item.ariaLabel;

            if (item.kind === "signoff" && signoffReceiptId && signoffAriaLabel) {
              return (
                <button
                  key={item.phase}
                  type="button"
                  className={className}
                  aria-current={isCurrent}
                  aria-label={signoffAriaLabel}
                  onClick={() => {
                    focusDataHealthRepair();
                    confirmActionReceipt(signoffReceiptId);
                  }}
                >
                  {stepContents}
                </button>
              );
            }

            if (item.kind === "status") {
              return (
                <div key={item.phase} className={className} aria-current={isCurrent}>
                  {stepContents}
                </div>
              );
            }

            return (
              <a
                key={item.phase}
                className={className}
                href="#macro-toolkit-data-health-detail"
                aria-current={isCurrent}
                onClick={handleDataHealthRepairActionClick}
              >
                {stepContents}
              </a>
            );
          })}
        </div>
      </div>
      <div className="macro-toolkit-committee-readiness-summary" aria-label="投委会提交包就绪摘要">
        <div>
          <span>提交包就绪度</span>
          <strong>
            {committeePackReviewReadyCount}/{committeePackItems.length}
          </strong>
        </div>
        <div>
          <span>签核就绪</span>
          <strong>
            {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
          </strong>
        </div>
        <div>
          <span>硬阻断</span>
          <strong>{committeeWorkQueueBlockCount}</strong>
        </div>
        <div>
          <span>待复核回执</span>
          <strong>{committeePackReceiptReviewCount}</strong>
        </div>
      </div>
      <div className="macro-toolkit-committee-decision-language" aria-label="投委会提交判断口径">
        <div className="macro-toolkit-committee-decision-language__head">
          <span>提交判断口径</span>
          <strong>同源于提交判断矩阵</strong>
        </div>
        <div className="macro-toolkit-committee-decision-language__grid">
          {committeeChecklistItems.map((item) => (
            <a
              key={item.key}
              className={`macro-toolkit-committee-decision-language__item macro-toolkit-committee-decision-language__item--${item.status}`}
              href={item.href}
              aria-current={selectedEvidenceHref === item.href ? "true" : undefined}
              onClick={() => {
                setSelectedEvidenceHref(item.href);
                setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(item.href));
              }}
            >
              <span>{item.condition}</span>
              <strong>{item.statusLabel}</strong>
              <small>{item.owner}</small>
              <em>证据入口</em>
            </a>
          ))}
        </div>
      </div>
      <div className="macro-toolkit-committee-redline" aria-label="投委会提交红线">
        <div className="macro-toolkit-committee-redline__decision">
          <span>提交红线</span>
          <strong>{committeeRedlineTitle}</strong>
          <small>{committeeDecisionBlocker}</small>
        </div>
        <div className="macro-toolkit-committee-redline__owner">
          <span>责任人</span>
          <strong>{committeeDecisionOwner}</strong>
          <small>投委会提交前完成复核留痕</small>
        </div>
        <div className="macro-toolkit-committee-redline__action">
          <span>提交前动作</span>
          <strong>{committeeRedlineAction}</strong>
          {renderCommitteeDecisionAction("redline")}
        </div>
      </div>
      <div className="macro-toolkit-data-health-signoff-pack" aria-label="数据健康签核证据包">
        <div className="macro-toolkit-data-health-signoff-pack__head">
          <span>数据健康签核包</span>
          <strong>{repairItemCount ? "阻断签核前置" : "可签核"}</strong>
        </div>
        <div className="macro-toolkit-data-health-signoff-pack__grid">
          <div>
            <span>最高优先级</span>
            <strong>{dataHealthSignoffPriority}</strong>
            <small>{repairItemCount ? `共 ${repairItemCount} 项待处理` : "无待处理项"}</small>
          </div>
          <div>
            <span>来源覆盖</span>
            <strong>{dataHealthSignoffCoverage}</strong>
            <small>{dataFreshnessDetail}</small>
          </div>
          <div>
            <span>责任/SLA</span>
            <strong>{committeeReadinessOwner}</strong>
            <small>{repairItemCount ? "T+0 盘前" : "持续留痕"}</small>
          </div>
          <div>
            <span>签核前置</span>
            <strong>{dataHealthSignoffRequirement}</strong>
            <small>{dataHealthSignoffGuardrail}</small>
          </div>
        </div>
        <a
          href="#macro-toolkit-data-health-detail"
          aria-current={selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? "true" : undefined}
          onClick={focusDataHealthRepair}
        >
          打开数据健康证据
        </a>
      </div>
      <div className="macro-toolkit-committee-checklist" aria-label="投委会提交条件摘要">
        <div className="macro-toolkit-committee-checklist__head">
          <span>提交条件摘要</span>
          <strong>
            {committeeChecklistItems.filter((item) => item.status === "pass").length}/{committeeChecklistItems.length}
          </strong>
        </div>
        <div className="macro-toolkit-committee-checklist__summary-grid">
          <div>
            <span>已通过</span>
            <strong>{committeeChecklistPassCount}</strong>
          </div>
          <div>
            <span>阻断</span>
            <strong>{committeeWorkQueueBlockCount}</strong>
          </div>
          <div>
            <span>待确认</span>
            <strong>{committeeWorkQueuePendingCount}</strong>
          </div>
          <a
            href={committeeLeadChecklistHref}
            aria-current={selectedEvidenceHref === committeeLeadChecklistHref ? "true" : undefined}
            onClick={() => {
              if (committeeLeadChecklistHref === "#macro-toolkit-data-health-detail") {
                focusDataHealthRepair();
                return;
              }
              setSelectedEvidenceHref(committeeLeadChecklistHref);
              setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(committeeLeadChecklistHref));
            }}
          >
            <span>主卡点</span>
            <strong>{committeeLeadChecklistItem?.condition ?? "无阻断"}</strong>
            <small>证据入口</small>
          </a>
        </div>
      </div>
      <div className="macro-toolkit-committee-pack" aria-label="投委会材料包">
        <div className="macro-toolkit-committee-pack__head">
          <span>投委会材料包</span>
          <strong>{committeePackItems.filter((item) => item.status === "archived").length}/{committeePackItems.length}</strong>
        </div>
        <div className="macro-toolkit-committee-pack__grid">
          {committeePackItems.map((item) => (
            <a
              key={item.key}
              className={`macro-toolkit-committee-pack__item macro-toolkit-committee-pack__item--${item.status}`}
              href={item.receipt?.evidenceHref ?? item.href}
              aria-label={`投委会材料包-${item.subject}`}
              aria-current={selectedEvidenceHref === (item.receipt?.evidenceHref ?? item.href) ? "true" : undefined}
              onClick={() => {
                const href = item.receipt?.evidenceHref ?? item.href;
                if (href === "#macro-toolkit-data-health-detail") {
                  focusDataHealthRepair();
                  return;
                }
                setSelectedEvidenceHref(href);
                setSelectedGovernanceFocus(
                  href === "#macro-toolkit-data-health-detail"
                    ? "data-health"
                    : href === "#macro-toolkit-tool-execution-detail" || href === "#macro-toolkit-script-artifact-detail"
                      ? "execution"
                      : "evidence",
                );
              }}
            >
              <span>{item.packSubject}</span>
              <strong>{item.statusLabel}</strong>
              <small>{compactText(item.receipt?.evidenceEntry ?? item.gap, 34)}</small>
            </a>
          ))}
        </div>
        <div className="macro-toolkit-committee-pack__review-index" aria-label="投委会材料包审阅索引">
          <div className="macro-toolkit-committee-pack__review-head">
            <span>审阅索引</span>
            <strong>材料</strong>
            <strong>状态</strong>
            <strong>责任人</strong>
            <strong>提交影响</strong>
            <strong>证据入口</strong>
          </div>
          {committeePackItems.map((item) => {
            const href = item.receipt?.evidenceHref ?? item.href;
            const submissionImpact = committeePackSubmissionImpact(item);
            const evidenceLabel = committeePackEvidenceEntryLabel(item);
            return (
              <div
                key={item.key}
                className={`macro-toolkit-committee-pack__review-row macro-toolkit-committee-pack__review-row--${item.status}`}
              >
                <span>{item.packSubject}</span>
                <strong>{item.statusLabel}</strong>
                <small>{item.owner}</small>
                <small>{submissionImpact}</small>
                <a
                  href={href}
                  aria-current={selectedEvidenceHref === href ? "true" : undefined}
                  onClick={() => {
                    if (href === "#macro-toolkit-data-health-detail") {
                      focusDataHealthRepair();
                      return;
                    }
                    setSelectedEvidenceHref(href);
                    setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
                  }}
                >
                  {item.subject} {evidenceLabel}
                </a>
              </div>
            );
          })}
        </div>
      </div>
      <div className="macro-toolkit-investment-brief__grid">
        <div className="macro-toolkit-investment-brief__item macro-toolkit-investment-brief__item--decision">
          <span>投资结论</span>
          <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
          <small>{compactText(analysis?.conclusion.summary ?? "正在生成宏观判断。", 72)}</small>
        </div>
        <div className="macro-toolkit-investment-brief__item">
          <span>关键证据</span>
          <strong>{formatPercent(analysis?.coverage.hit_rate)}</strong>
          <small>
            {primarySignal
              ? `${primarySignal.title} · ${primarySignal.stance} · ${primarySignal.score ?? "缺分"}`
              : "主信号待返回"}
          </small>
          <a
            href="#macro-toolkit-analysis-detail"
            aria-current={selectedEvidenceHref === "#macro-toolkit-analysis-detail" ? "true" : undefined}
            onClick={() => {
              setSelectedEvidenceHref("#macro-toolkit-analysis-detail");
              setSelectedGovernanceFocus("evidence");
            }}
          >
            查看证据覆盖
          </a>
        </div>
        <div className="macro-toolkit-investment-brief__item">
          <span>待复核缺口</span>
          <strong>{repairItemCount ? `${repairItemCount} 项` : "无待处理项"}</strong>
          <small>{isCoreAnalysis ? observationRuntimeSummary : `${degradedResultCount} 个结果降级或不可用`}</small>
          <a
            href="#macro-toolkit-data-health-detail"
            aria-current={selectedEvidenceHref === "#macro-toolkit-data-health-detail" ? "true" : undefined}
            onClick={handleDataHealthRepairActionClick}
          >
            处理数据缺口
          </a>
        </div>
        <div className="macro-toolkit-investment-brief__item macro-toolkit-investment-brief__item--action">
          <span>下一步动作</span>
          <strong>{committeeDecisionAction}</strong>
          <small>{committeeDecisionBlocker}</small>
          {renderCommitteeDecisionAction("tile")}
        </div>
      </div>
    </div>
  ) : null;
  const governanceGatePanel = showOperations ? (
    <div
      className="macro-toolkit-governance-gate"
      data-testid="macro-toolkit-governance-gate"
      aria-label="宏观工具口径与数据闸门"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>Governance Gate</span>
        <strong>口径与数据闸门</strong>
      </div>
      <MacroToolkitContractBoundary
        formalUseAllowed={analysisMeta?.formal_use_allowed}
        resultKind={analysisMeta?.result_kind}
        ruleVersion={analysisMeta?.rule_version}
      />
      <GovernanceAuditMap
        items={governanceFocusItems}
        selectedKey={selectedGovernanceFocusItem.key}
        onSelect={setSelectedGovernanceFocus}
      />
    </div>
  ) : null;
  const operationsConsolePanel = showOperations ? (
    <div
      id="macro-toolkit-operations-console"
      className="macro-toolkit-operations-console"
      data-testid="macro-toolkit-operations-console"
    >
      <div className="macro-toolkit-operations-console__head">
        <div>
          <span>Action Console</span>
          <strong>{selectedScript?.name ?? "脚本注册表读取中"}</strong>
          <small>执行脚本、刷新数据源、确认产物状态。</small>
        </div>
        <Tag color={scripts.length > 0 && availableScriptCount === scripts.length ? "green" : "gold"}>
          脚本 {availableScriptCount}/{scripts.length}
        </Tag>
      </div>
      <CommitteeWorkQueue
        items={committeeWorkQueueItems}
        checklistItems={committeeChecklistItems}
        blockerCount={committeeWorkQueueBlockCount}
        pendingCount={committeeWorkQueuePendingCount}
        receiptCount={actionReceipts.length}
        latestReceipt={actionReceipts[0] ?? null}
        receipts={actionReceipts}
        confirmedReceiptIds={confirmedReceiptIds}
        gateStatus={committeeDecisionStatus}
        selectedEvidenceHref={selectedEvidenceHref}
        selectedExecutionHref={selectedExecutionHref}
        onSelectEvidence={(href, governanceFocus) => {
          setSelectedEvidenceHref(href);
          setSelectedGovernanceFocus(governanceFocus);
        }}
        onSelectExecution={(href, governanceFocus) => {
          setSelectedExecutionHref(href);
          if (href !== "#macro-toolkit-operations-actions") {
            setSelectedEvidenceHref(href);
          }
          setSelectedGovernanceFocus(governanceFocus);
        }}
        onConfirmReceipt={confirmActionReceipt}
      />
      <ActionReceiptPanel receipt={actionReceipt} />
      <ActionReceiptQueue
        receipts={actionReceipts}
        selectedEvidenceHref={selectedEvidenceHref}
        onSelectEvidence={setSelectedEvidenceHref}
      />
      <div className="macro-toolkit-operations-console__metrics">
        <MetricTile
          icon={<DatabaseOutlined />}
          label="业务证据"
          value={defaultBusinessEvidenceSources}
          detail="分析、刷新和脚本共享同一证据口径"
          detailMaxLength={38}
        />
        <MetricTile
          icon={<ClockCircleOutlined />}
          label="席位日期"
          value={cffexStatus?.latest_trade_date ?? "缺失"}
          detail={`中金所席位 ${cffexStatus?.row_count ?? 0} 行`}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="商品期货"
          value={commodityNanhuaStatusValue(commodityStatus)}
          detail={commodityNanhuaStatusDetail(commodityStatus)}
          tone={commodityNanhuaStatusTone(commodityStatus)}
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="输出文件"
          value={payload?.output_files.length ?? 0}
          detail={outputDetail}
        />
      </div>
      <div
        id="macro-toolkit-operations-actions"
        className={`macro-toolkit-operations-console__actions ${
          selectedExecutionHref === "#macro-toolkit-operations-actions"
            ? "macro-toolkit-operations-console__actions--active"
            : ""
        }`}
        data-testid="macro-toolkit-operations-actions"
      >
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          disabled={!selectedScript || (isOperationActionBusy && !isRunning)}
          loading={isRunning}
          onClick={() => void runSelectedScript()}
        >
          运行选中脚本
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingChoiceStock}
          disabled={isOperationActionBusy && !isRefreshingChoiceStock}
          onClick={() => void refreshChoiceStock()}
          aria-label="刷新股票策略明细"
        >
          刷新股票策略明细
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingCffex}
          disabled={isOperationActionBusy && !isRefreshingCffex}
          onClick={() => void refreshCffexMemberRank()}
        >
          刷新席位明细
        </Button>
        <Button
          icon={<InfoCircleOutlined />}
          loading={isRefreshingCommodity}
          disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
          onClick={() => void refreshCommodityFutures({ dryRun: true })}
        >
          预估明细刷新
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingCommodity}
          disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
          aria-label={commodityRefreshActionLabel}
          onClick={() => void refreshCommodityFutures({ dryRun: false })}
        >
          {commodityRefreshActionLabel}
        </Button>
      </div>
      {scriptsQuery.isError ? <Alert type="error" showIcon message="脚本注册表加载失败" /> : null}
      {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
      {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
      {refreshResult ? <Alert type="success" showIcon message={refreshResult} /> : null}
      {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
      {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
      {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
      {runResult ? (
        <Alert
          type={statusTone(runResult.status)}
          showIcon
          message={`脚本运行：${runResult.status}`}
          description={`输出文件 ${runResult.output_files.length} · 退出码 ${runResult.exit_code ?? "无"}`}
        />
      ) : null}
      {runError ? <Alert type="error" showIcon message={runError} /> : null}
    </div>
  ) : null;

  if (!payload && !analysis && (analysisQuery.isError || (showOperations && scriptsQuery.isError))) {
    return (
      <PageStateSurface
        variant="error"
        testId="macro-toolkit-error-state"
        className="macro-toolkit-error-state"
        title={showOperations ? "宏观工具暂不可用" : "宏观观察暂不可用"}
        description={
          showOperations
            ? queryErrorText || "后端宏观模块没有返回可展示数据。"
            : "核心分析暂时没有返回；请稍后重试或打开宏观工具页查看诊断。"
        }
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void analysisQuery.refetch();
              if (showOperations) {
                void scriptsQuery.refetch();
              }
              void strategyQuery.refetch();
            }}
            loading={analysisQuery.isFetching || (showOperations && scriptsQuery.isFetching) || strategyQuery.isFetching}
          >
            重试读取
          </Button>
        }
      >
        <MacroToolkitContractBoundary plainLanguage={!showOperations} />
        {!showOperations ? (
          <Alert
            type="info"
            showIcon
            data-testid="macro-observation-readonly-boundary"
            message="只读宏观观察"
            description="本页只展示宏观分析证据；刷新、脚本执行和运营注册表保留在宏观工具页。"
          />
        ) : null}
        {hasReadScopeBlocker ? <MacroToolkitReadScopeBlocker /> : null}
        <div className="macro-toolkit-error-sources" aria-label="宏观工具失败来源">
          <span>{showOperations ? "失败来源" : "读取状态"}</span>
          {(showOperations ? failedReadMessages : observationFailedReadMessages).length ? (
            (showOperations ? failedReadMessages : observationFailedReadMessages).map((message, index) => (
              <small key={`${message}-${index}`}>{message}</small>
            ))
          ) : (
            <small>{showOperations ? "后端宏观模块没有返回可展示数据。" : "宏观观察暂时没有可展示数据。"}</small>
          )}
        </div>
      </PageStateSurface>
    );
  }

  return (
    <div
      className={`macro-toolkit-page macro-toolkit-page--details-${detailDensity}`}
      data-testid="macro-toolkit-page"
    >
      <section
        data-testid="macro-toolkit-tailwind-cockpit"
        className={`macro-toolkit-cockpit macro-toolkit-cockpit--${showOperations ? "toolkit" : "observation"}`}
      >
        <div className="macro-toolkit-cockpit__header">
          <div className="macro-toolkit-cockpit__title-block">
            <div className="macro-toolkit-cockpit__meta">
              <ClockCircleOutlined />
              <span>{analysis?.as_of_date ?? "DATE_MISSING"}</span>
              <Tag color={showOperations ? "blue" : "default"}>{showOperations ? "工具控制台" : "只读观察"}</Tag>
            </div>
            <h1>{showOperations ? "宏观工具" : "宏观分析结果"}</h1>
            <p>
              {showOperations
                ? "把宏观分析、数据刷新、脚本运行和产物确认收在同一个首屏闭环里。"
                : "只展示宏观分析证据；刷新、脚本和注册表保留在宏观工具页。"}
            </p>
          </div>
          <div className="macro-toolkit-cockpit__header-actions">
            {showOperations ? (
              <>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    void clearFullAnalysisCache();
                    void analysisQuery.refetch();
                    void scriptsQuery.refetch();
                    void strategyQuery.refetch();
                  }}
                  loading={isMacroRefreshing}
                >
                  刷新结果
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => void scriptsQuery.refetch()}
                  loading={scriptsQuery.isFetching}
                >
                  刷新注册表
                </Button>
              </>
            ) : null}
          </div>
        </div>

        <div className="macro-toolkit-cockpit__body">
          <div
            className="macro-toolkit-cockpit__analysis macro-toolkit-house-view"
            data-testid="macro-toolkit-house-view"
            aria-label={showOperations ? "宏观工具 House View" : "宏观观察结论"}
          >
            <div className="macro-toolkit-panel-kicker">
              <span>{showOperations ? "House View" : "观察结论"}</span>
              <strong>{showOperations ? "可执行宏观判断" : "只读宏观判断"}</strong>
            </div>
            <div className="macro-toolkit-cockpit__conclusion">
              <div className="macro-toolkit-cockpit__label">
                <MacroStatusIcon tone={analysis?.conclusion.tone ?? "missing"}>
                  {analysis?.conclusion.tone === "negative" || !analysis ? <WarningOutlined /> : <LineChartOutlined />}
                </MacroStatusIcon>
                投研观点
              </div>
              <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
              <p title={analysis?.conclusion.summary}>
                {analysis?.conclusion.summary ?? "正在从系统数据源生成宏观判断。"}
              </p>
            </div>
            {showOperations ? (
              <>
                <div className="macro-toolkit-house-view__decision-chain" aria-label="House View 投委会决策链">
                  <div className="macro-toolkit-house-view__decision-head">
                    <span>投委会提交判断</span>
                    <strong>{committeeDecisionStatus}</strong>
                    <small>{committeeDecisionOwner}</small>
                  </div>
                  <div className="macro-toolkit-house-view__decision-body">
                    <div>
                      <span>首要卡点</span>
                      <strong>{committeeDecisionBlocker}</strong>
                      <small>{committeeRedlineTitle}</small>
                    </div>
                    {renderCommitteeDecisionAction("house")}
                  </div>
                  <div className="macro-toolkit-house-view__decision-metrics">
                    <div>
                      <span>提交包</span>
                      <strong>
                        {committeePackReviewReadyCount}/{committeePackItems.length}
                      </strong>
                    </div>
                    <div>
                      <span>签核</span>
                      <strong>
                        {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
                      </strong>
                    </div>
                    <div>
                      <span>待复核回执</span>
                      <strong>{committeePackReceiptReviewCount}</strong>
                    </div>
                  </div>
                </div>
                <div className="macro-toolkit-house-view__dossier" aria-label="House View 依据档案">
                  {houseViewDossierItems.map((item) => (
                    <div className="macro-toolkit-house-view__dossier-item" key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </div>
                <div className="macro-toolkit-brief-metrics">
                  <MetricTile
                    icon={<LineChartOutlined />}
                    label="主信号"
                    value={primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : "缺失"}
                    detail={
                      primarySignal?.score == null
                        ? "尚无可排序信号"
                        : `${primarySignal.evidence.join(" / ")} · ${primarySignal.score.toFixed(1)}`
                    }
                    tone={primarySignal?.tone === "positive" ? "positive" : primarySignal ? "neutral" : "missing"}
                  />
                  <MetricTile
                    icon={<ClockCircleOutlined />}
                    label="分析日期"
                    value={analysis?.as_of_date ?? "缺失"}
                    detail={(analysis?.default_data_sources ?? []).join(" + ") || "choice + tushare"}
                  />
                  <MetricTile
                    icon={<ThunderboltOutlined />}
                    label="能力闭环"
                    value={`${readyCapabilityCount}/${capabilityItems.length || 0}`}
                    detail={`${wiredCapabilityCount} 项已接到页面/API`}
                  />
                </div>
              </>
            ) : (
              observationFirstScreenLoop
            )}
          </div>

          {investmentBriefPanel}
        </div>
      </section>

      {showOperations ? (
        <section className="macro-toolkit-operations-band" aria-label="宏观工具操作与治理区">
          <div className="macro-toolkit-committee-workspace" aria-label="投委会提交作业区">
            <div className="macro-toolkit-committee-workspace__head">
              <div>
                <span>投委会提交作业区</span>
                <strong>{committeeDecisionStatus}</strong>
                <small>{committeeDecisionBlocker}</small>
              </div>
              <div className="macro-toolkit-committee-workspace__scorecard" aria-label="投委会提交作业区状态">
                <div>
                  <span>提交包</span>
                  <strong>
                    {committeePackReviewReadyCount}/{committeePackItems.length}
                  </strong>
                </div>
                <div>
                  <span>签核</span>
                  <strong>
                    {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
                  </strong>
                </div>
                <div>
                  <span>硬阻断</span>
                  <strong>{committeeWorkQueueBlockCount}</strong>
                </div>
                <div>
                  <span>回执</span>
                  <strong>{committeePackReceiptReviewCount}</strong>
                </div>
              </div>
            </div>
            <aside className="macro-toolkit-committee-workspace__rail" aria-label="投委会治理侧栏">
              <span className="macro-toolkit-committee-workspace__section-label">治理侧栏</span>
              {governanceGatePanel}
              <div className="macro-toolkit-committee-workspace__evidence-links">
                <div className="macro-toolkit-committee-workspace__evidence-head">
                  <span>深度证据入口</span>
                  <strong>{deepEvidenceQueueItems.length} 个追踪面</strong>
                </div>
                <div className="macro-toolkit-committee-workspace__evidence-grid" aria-label="深度证据入口">
                  {deepEvidenceQueueItems.map((item) => (
                    <a key={item.key} href={item.href}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                    </a>
                  ))}
                </div>
              </div>
            </aside>
            <div className="macro-toolkit-committee-workspace__main" aria-label="投委会提交主作业区">
              <span className="macro-toolkit-committee-workspace__section-label">主作业区</span>
              {operationsConsolePanel}
              <div className="macro-toolkit-detail-density" data-testid="macro-toolkit-detail-density">
                <div>
                  <span>详情默认精简</span>
                  <strong>{detailDensity === "compact" ? "深度证据仍可展开" : "全部详情已展开"}</strong>
                </div>
                <div className="macro-toolkit-detail-density__queue" aria-label="深度证据摘要队列">
                  {deepEvidenceQueueItems.map((item) => (
                    <a key={item.key} href={item.href}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                      <em>证据入口</em>
                    </a>
                  ))}
                </div>
                <div className="macro-toolkit-detail-density__actions" role="group" aria-label="详情展开密度">
                  <Button
                    size="small"
                    type={detailDensity === "compact" ? "primary" : "default"}
                    onClick={() => setDetailDensity("compact")}
                  >
                    精简
                  </Button>
                  <Button
                    size="small"
                    type={detailDensity === "expanded" ? "primary" : "default"}
                    onClick={() => setDetailDensity("expanded")}
                  >
                    全部展开
                  </Button>
                </div>
              </div>
            </div>
          </div>
          <nav className="macro-toolkit-workflow-map" aria-label="宏观工具细节区导航">
            <a href="#macro-toolkit-analysis-detail">
              <span>01 分析证据</span>
              <strong>{workflowAnalysisState}</strong>
            </a>
            <a href="#macro-toolkit-data-health-detail">
              <span>02 数据健康</span>
              <strong>{repairItemCount ? `${repairItemCount} 项待处理` : "无待处理项"}</strong>
            </a>
            <a href="#macro-toolkit-tool-execution-detail">
              <span>03 工具执行</span>
              <strong>{workflowToolState}</strong>
            </a>
            <a href="#macro-toolkit-script-artifact-detail">
              <span>04 脚本与产物</span>
              <strong>{`${payload?.output_files.length ?? 0} 个产物 · ${omittedEntries.length} 个未纳入`}</strong>
            </a>
          </nav>
        </section>
      ) : null}

      {analysisQuery.isError ? (
        <Alert type="error" showIcon message="宏观分析结果加载失败" />
      ) : null}

      {fullAnalysisError ? (
        <Alert type="error" showIcon message="完整分析加载失败" description={fullAnalysisError} />
      ) : null}

      {isAnalysisLoading ? (
        <>
          <div data-testid="macro-toolkit-initial-analysis-loading">
            <Alert
              type="info"
              showIcon
              message="核心分析加载中"
              description={
                showOperations
                  ? "页面口径边界已就绪；核心信号和脚本注册表会在后端返回后自动补上。"
                  : "页面口径边界已就绪；观察结论和证据对照会在后端返回后自动补上。"
              }
            />
          </div>
          {showOperations ? (
            <>
              <section className="macro-toolkit-section">
                <PageSectionLead
                  eyebrow="signals"
                  title="核心信号"
                  description="等待后端宏观 analysis 结果返回。"
                />
                <div className="macro-toolkit-empty-output">核心分析加载中，暂不显示占位结论。</div>
              </section>
              <section className="macro-toolkit-section">
                <PageSectionLead
                  eyebrow="risk"
                  title="市场踩踏风险"
                  description="等待 A 股宽度、跌停、成交与回落压力判断返回。"
                />
                <div className="macro-toolkit-empty-output">市场踩踏风险加载中，暂不推导风险等级。</div>
              </section>
            </>
          ) : (
            observationSignalRiskLoadingSection
          )}
        </>
      ) : null}

      {analysis ? (
        <>
          <div
            id="macro-toolkit-analysis-detail"
            data-testid="macro-toolkit-analysis-detail"
            className={`macro-toolkit-anchor-target ${
              isAuditTargetActive("#macro-toolkit-analysis-detail", ["evidence", "analysis-scope"])
                ? "macro-toolkit-anchor-target--active"
                : ""
            }`}
          />
          <section
            className={showOperations ? "macro-toolkit-analysis-stack" : "macro-toolkit-observation-evidence"}
            aria-label={showOperations ? undefined : "宏观观察证据与限制"}
          >
            {!showOperations ? (
              <div className="macro-toolkit-observation-evidence__head">
                <span>观察证据与限制</span>
                <div className="macro-toolkit-observation-evidence__legend">
                  <span>运行状态</span>
                  <span>数据健康</span>
                  <span>投研总览</span>
                </div>
              </div>
            ) : null}
            <div
              className={
                showOperations ? "macro-toolkit-analysis-stack__body" : "macro-toolkit-observation-evidence__body"
              }
            >
          <section
            className={
              showOperations
                ? "macro-toolkit-evidence-review-flow"
                : "macro-toolkit-observation-evidence__contents"
            }
            aria-label={showOperations ? "投委会证据包审阅流" : undefined}
          >
            {showOperations ? (
              <aside className="macro-toolkit-evidence-review-flow__rail" aria-label="投委会证据包审阅摘要">
                <div className="macro-toolkit-evidence-review-flow__rail-head">
                  <span>投委会证据包审阅流</span>
                  <strong>审阅摘要</strong>
                </div>
                <div className="macro-toolkit-evidence-review-flow__review-card macro-toolkit-evidence-review-flow__review-card--blocker">
                  <span>当前阻断</span>
                  <strong>{committeeDecisionBlocker}</strong>
                  <small>{committeeRedlineTitle}</small>
                </div>
                <div className="macro-toolkit-evidence-review-flow__review-grid">
                  <div>
                    <span>责任人</span>
                    <strong>{committeeDecisionOwner}</strong>
                  </div>
                  <div>
                    <span>证据位置</span>
                    <strong>{committeeLeadChecklistItem?.condition ?? "数据健康"}</strong>
                  </div>
                  <div>
                    <span>签核动作</span>
                    <strong>{committeeDecisionAction}</strong>
                  </div>
                </div>
                {renderCommitteeDecisionAction("tile")}
              </aside>
            ) : null}
            <div
              className={
                showOperations
                  ? "macro-toolkit-evidence-review-flow__detail"
                  : "macro-toolkit-observation-evidence__contents"
              }
              aria-label={showOperations ? "投委会证据包详情" : undefined}
            >
          {showOperations ? (
            <section
              className="macro-toolkit-evidence-book"
              data-testid="macro-toolkit-evidence-book"
              aria-label="宏观工具证据复核总账"
            >
              <div className="macro-toolkit-evidence-book__head">
                <div>
                  <span>Evidence Book</span>
                  <strong>证据复核总账</strong>
                </div>
                <Tag color={repairItemCount ? "gold" : "green"}>
                  {repairItemCount ? `${repairItemCount} 项缺口` : "复核就绪"}
                </Tag>
              </div>
              <div className="macro-toolkit-evidence-book__submission-summary" aria-label="证据复核总账提交包总览">
                <div>
                  <span>提交包可审</span>
                  <strong>
                    {committeePackReviewReadyCount}/{committeePackItems.length}
                  </strong>
                </div>
                <div>
                  <span>签核</span>
                  <strong>
                    {committeeSignoffReadyCount}/{committeeSignoffLaneSummaryItems.length}
                  </strong>
                </div>
                <div>
                  <span>待复核回执</span>
                  <strong>{committeePackReceiptReviewCount}</strong>
                </div>
                <div>
                  <span>硬阻断</span>
                  <strong>{committeeWorkQueueBlockCount}</strong>
                </div>
              </div>
              <div
                className={`macro-toolkit-evidence-book__submission-gate macro-toolkit-evidence-book__submission-gate--${committeeFinalGateTone}`}
                aria-label="投委会最终提交门禁"
              >
                <div className="macro-toolkit-evidence-book__submission-gate-main">
                  <span>Submission Gate</span>
                  <strong>投委会最终提交门禁</strong>
                  <small>{committeeFinalGateOutcome}</small>
                </div>
                <div className="macro-toolkit-evidence-book__submission-gate-verdict">
                  <div>
                    <span>当前结论</span>
                    <strong>{committeeFinalSignoffStatus}</strong>
                  </div>
                  <div>
                    <span>首要阻断</span>
                    <strong>{committeeFinalGateBlockerText}</strong>
                  </div>
                  <div>
                    <span>责任人</span>
                    <strong>{committeeFinalSignoffOwner}</strong>
                  </div>
                  <div>
                    <span>下一动作</span>
                    <strong>{committeeDecisionAction}</strong>
                  </div>
                </div>
                <div className="macro-toolkit-evidence-book__submission-gate-metrics">
                  <span>提交包 {committeeFinalPackValue}</span>
                  <span>签核 {committeeFinalSignoffValue}</span>
                  <span>剩余风险 {committeeFinalResidualRiskValue}</span>
                  <span>待复核回执 {committeeFinalReceiptReviewValue}</span>
                </div>
              </div>
              <div className="macro-toolkit-evidence-book__pack-receipt" aria-label="投委会材料包封面回执">
                <div className="macro-toolkit-evidence-book__pack-receipt-main">
                  <span>Pack Receipt</span>
                  <strong>投委会材料包封面回执</strong>
                  <small>Evidence Book 同步材料包、回执与签核状态</small>
                  <div className="macro-toolkit-evidence-book__pack-receipt-actions">
                    <Button
                      aria-label="复制材料包摘要"
                      icon={<CopyOutlined aria-hidden="true" />}
                      size="small"
                      type="default"
                      onClick={() => void copyCommitteePackReceipt()}
                    >
                      {committeePackReceiptCopyStatus === "success"
                        ? "已复制"
                        : committeePackReceiptCopyStatus === "error"
                          ? "复制失败"
                          : "复制材料包摘要"}
                    </Button>
                    {committeePackReceiptCopyStatus !== "idle" ? (
                      <span
                        aria-atomic="true"
                        aria-live="polite"
                        className={`macro-toolkit-evidence-book__pack-receipt-copy-status macro-toolkit-evidence-book__pack-receipt-copy-status--${committeePackReceiptCopyStatus}`}
                        role="status"
                      >
                        {committeePackReceiptCopyStatus === "success"
                          ? "材料包摘要已复制"
                          : "复制失败，请手动选择材料包摘要"}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="macro-toolkit-evidence-book__pack-receipt-verdict">
                  <div>
                    <span>提交结论</span>
                    <strong>{committeeFinalSignoffStatus}</strong>
                  </div>
                  <div>
                    <span>首要卡点</span>
                    <strong>{committeeDecisionBlocker}</strong>
                  </div>
                  <div>
                    <span>责任人</span>
                    <strong>{committeeFinalSignoffOwner}</strong>
                  </div>
                  <div>
                    <span>下一动作</span>
                    <strong>{committeeDecisionAction}</strong>
                  </div>
                </div>
                <div className="macro-toolkit-evidence-book__pack-receipt-metrics">
                  <span>提交包 {committeeFinalPackValue}</span>
                  <span>签核 {committeeFinalSignoffValue}</span>
                  <span>剩余风险 {committeeFinalResidualRiskValue}</span>
                  <span>待复核回执 {committeeFinalReceiptReviewValue}</span>
                </div>
                <div className="macro-toolkit-evidence-book__pack-receipt-trace">
                  <span>证据留痕</span>
                  <strong>{committeePackReceiptTraceText}</strong>
                </div>
              </div>
              <div className="macro-toolkit-evidence-book__grid">
                {evidenceBookRows.map((row) => {
                  const packItem = committeePackItemByKey.get(row.key);
                  const href = packItem?.receipt?.evidenceHref ?? row.href;
                  const evidenceLabel = packItem ? committeePackEvidenceEntryLabel(packItem) : "证据入口";
                  const rowAction = packItem ? evidenceBookRowAction(packItem) : null;
                  const isCurrent = selectedEvidenceHref === href || (!packItem?.receipt && selectedEvidenceHref === row.href);
                  return (
                    <div
                      key={row.key}
                      className="macro-toolkit-evidence-book__row"
                      role="group"
                      aria-label={`${row.subject}证据处理闭环`}
                      aria-current={isCurrent ? "true" : undefined}
                    >
                      <a
                        className="macro-toolkit-evidence-book__evidence-link"
                        href={href}
                        aria-label={`${row.subject} ${evidenceLabel}`}
                        aria-current={isCurrent ? "true" : undefined}
                        onClick={() => {
                          if (href === "#macro-toolkit-data-health-detail") {
                            focusDataHealthRepair();
                            return;
                          }
                          setSelectedEvidenceHref(href);
                          setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
                        }}
                      >
                        <strong>{row.subject}</strong>
                        <span>
                          <small>结论支撑</small>
                          {row.support}
                        </span>
                        <span>
                          <small>数据缺口</small>
                          {row.gap}
                        </span>
                        <span className="macro-toolkit-evidence-book__delivery">
                          <small>交付状态</small>
                          <b>{packItem ? committeeEvidenceBookDeliveryStatus(packItem) : "待确认"}</b>
                          <i>
                            提交影响：{packItem ? committeePackSubmissionImpact(packItem) : "待确认"} · 回执状态：
                            {packItem ? committeePackReceiptStatus(packItem) : "等待回执"}
                          </i>
                        </span>
                        <span>
                          <small>复核角色 / 责任人</small>
                          {row.owner}
                        </span>
                      </a>
                      <span className="macro-toolkit-evidence-book__action">
                        {rowAction?.kind === "button" ? (
                          <button
                            type="button"
                            disabled={rowAction.disabled || rowAction.busy}
                            aria-label={rowAction.label}
                            onClick={rowAction.onClick}
                          >
                            <strong>{rowAction.label}</strong>
                            <small>{rowAction.status}</small>
                          </button>
                        ) : (
                          <a
                            href={rowAction?.href ?? href}
                            aria-label={rowAction?.label ?? evidenceLabel}
                            onClick={() => {
                              const actionHref = rowAction?.href ?? href;
                              if (actionHref === "#macro-toolkit-data-health-detail") {
                                focusDataHealthRepair();
                                return;
                              }
                              setSelectedEvidenceHref(actionHref);
                              setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(actionHref));
                            }}
                          >
                            <strong>{rowAction?.label ?? evidenceLabel}</strong>
                            <small>{rowAction?.status ?? "证据留痕"}</small>
                          </a>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}
          <DataStatusStrip className="macro-toolkit-status-strip">
            {showOperations ? (
              <>
                <span title={`读取口径：${analysisMeta?.basis ?? "-"}`}>
                  <DatabaseOutlined /> {formatAnalysisBasisLabel(analysisMeta?.basis)}
                </span>
                <span title={`质量：${analysisMeta?.quality_flag ?? "-"}`}>
                  <SafetyCertificateOutlined /> {formatQualityFlagLabel(analysisMeta?.quality_flag)}
                </span>
                <span title={`建议：${analysis.conclusion.recommended_action}`}>
                  <ThunderboltOutlined /> {compactText(analysis.conclusion.recommended_action, 24)}
                </span>
              </>
            ) : (
              <>
                <span title="当前观察使用已记录的宏观分析口径。">
                  <DatabaseOutlined /> 分析口径已记录
                </span>
                <span title="数据质量状态已记录，具体诊断保留在宏观工具页。">
                  <SafetyCertificateOutlined /> 质量状态已记录
                </span>
                <span title={formatObservationRecommendation(analysis.conclusion.recommended_action)}>
                  <ThunderboltOutlined /> {formatObservationRecommendation(analysis.conclusion.recommended_action)}
                </span>
              </>
            )}
          </DataStatusStrip>
          {!showOperations ? observationBoundaryPanel : null}

          <div className="macro-toolkit-runtime-strip" aria-label="宏观工具运行状态">
            {showOperations && runtimeSections.length ? (
              runtimeSections.map((section) => (
                <span key={section.key}>
                  <ClockCircleOutlined />
                  {formatObservationDeferredSectionLabel(section.label ?? section.key)} ·{" "}
                  <Tag color={statusColor(section.status)}>{statusLabel(section.status)}</Tag>
                </span>
              ))
            ) : (
              <span>
                <ClockCircleOutlined />
                {showOperations ? (isCoreAnalysis ? "核心分析" : "完整分析") : isCoreAnalysis ? "待完整分析" : "完整分析"} ·{" "}
                <Tag color={statusColor(isCoreAnalysis ? "deferred" : "complete")}>
                  {showOperations ? statusLabel(isCoreAnalysis ? "deferred" : "complete") : observationRuntimeSummary}
                </Tag>
              </span>
            )}
            {showFullAnalysisActionInRuntime ? (
              <span className="macro-toolkit-runtime-strip__action">
                下一步：
                <Button
                  aria-label="查看完整分析"
                  size="small"
                  icon={<LineChartOutlined />}
                  loading={isLoadingFullAnalysis}
                  onClick={() => void loadFullAnalysis()}
                >
                  查看完整分析
                </Button>
              </span>
            ) : null}
          </div>

          {analysis.data_health ? (
            <div
              id="macro-toolkit-data-health-detail"
              data-testid="macro-toolkit-data-health-detail"
              className={`macro-toolkit-anchor-target ${
                isAuditTargetActive("#macro-toolkit-data-health-detail", ["data-health"])
                  ? "macro-toolkit-anchor-target--active"
                  : ""
              }`}
            >
              {showOperations ? (
                <MacroToolkitDataHealthPanel
                  dataHealth={analysis.data_health}
                  showActions={showOperations}
                  focusedRepairKey={focusedRepairKey}
                  dataHealthReceipt={completedDataHealthReceipt}
                  dataHealthReceiptConfirmed={
                    completedDataHealthReceipt ? confirmedReceiptIds.has(completedDataHealthReceipt.id) : false
                  }
                  onRepairAction={(item) => {
                    setFocusedRepairKey(repairItemFocusKey(item));
                    if (item.action?.kind === "source_backfill_required") {
                      void refreshMacroSourceBackfill(item);
                      return;
                    }
                    if (item.action?.kind === "load_full_analysis") {
                      void reviewFullAnalysisRepair(item);
                      return;
                    }
                    void loadFullAnalysis({ force: item.scope === "full" });
                  }}
                  repairActionLoading={isLoadingFullAnalysis}
                  refreshingSourceAlias={refreshingSourceAlias}
                />
              ) : (
                <MacroToolkitDataHealthSummary dataHealth={analysis.data_health} />
              )}
            </div>
          ) : null}
          {sourceBackfillResult ? <Alert type="success" showIcon message={sourceBackfillResult} /> : null}
          {sourceBackfillError ? <Alert type="error" showIcon message={sourceBackfillError} /> : null}

          <div className="macro-toolkit-readiness-strip" aria-label="宏观工具投研总览">
            <ReadinessTile
              icon={<LineChartOutlined />}
              label="主信号"
              value={
                primarySignal
                  ? showOperations
                    ? `${primarySignal.title} · ${primarySignal.stance}`
                    : `${formatObservationSignalTitle(primarySignal)} · ${formatObservationSignalStance(primarySignal)}`
                  : "缺失"
              }
              detail={
                showOperations
                  ? (primarySignal?.evidence.join(" / ") ?? "暂无可排序信号")
                  : formatObservationEvidence(primarySignal?.evidence)
              }
              tone={primarySignal?.tone ?? "missing"}
            />
            <ReadinessTile
              icon={<ClockCircleOutlined />}
              label="数据新鲜度"
              value={analysis.as_of_date ?? "缺失"}
              detail={dataFreshnessDetail}
              tone={missingIndicatorCount > 0 ? "neutral" : "positive"}
            />
            <ReadinessTile
              icon={<ThunderboltOutlined />}
              label={showOperations ? "模型结果" : "证据边界"}
              value={showOperations ? `${capabilityResults.length} 个功能输出` : "已记录"}
              detail={showOperations ? `${degradedResultCount} 个降级或不可用结果` : "能力盘点留在证据追踪，不进入投研结论。"}
              tone={degradedResultCount > 0 ? "neutral" : "positive"}
            />
          </div>
            </div>
          </section>
            </div>
          </section>

          {showOperations ? (
            <>
              {hasonStrategySection}
              {analysisWarningsAlert}
              {signalSection}
              {crisisEvidenceSection}
              {riskSection}
              {indicatorSection}
              {capabilityResultsSection}
              {strategySection}
            </>
          ) : (
            <>
              {analysisWarningsAlert}
              <div className="macro-toolkit-observation-flow" aria-label="宏观观察阅读顺序">
                {observationSignalRiskComparisonSection}
                {investmentEvidenceSection}
              </div>
              <div className="macro-toolkit-observation-evidence-flow" aria-label="宏观观察证据追踪">
                {crisisEvidenceSection}
                {observationEvidenceTraceSummary}
              </div>
            </>
          )}
        </>
      ) : null}

      {showOperations ? (
        <section className="macro-toolkit-section">
          <PageSectionLead
            eyebrow="closure"
            title="功能补齐方案"
            description="按 V1 宏观分析 M7-M16 对齐，区分代码迁入、API/页面接线和数据命中。"
          />
          {capabilityItems.length ? (
            <Table
              className="macro-toolkit-table--wide"
              rowKey="key"
              size="small"
              columns={capabilityColumns}
              dataSource={capabilityItems}
              pagination={false}
              tableLayout="fixed"
              scroll={{ x: 920 }}
            />
          ) : scriptsQuery.isFetching ? (
            <Alert
              type="info"
              showIcon
              message="功能补齐方案正在读取"
              description="不会阻塞核心信号和市场踩踏风险。"
            />
          ) : (
            <div className="macro-toolkit-empty-output">暂无功能补齐方案。</div>
          )}
        </section>
      ) : null}

      {showOperations ? (
        <section className="macro-toolkit-execution-receipt-workspace" aria-label="执行证据与产物回执区">
          <div className="macro-toolkit-execution-receipt-workspace__head">
            <div>
              <span>执行证据与产物回执区</span>
              <strong>执行证据</strong>
              <small>把可执行脚本、席位和商品刷新先归入证据，再用产物与数据源命中形成回执。</small>
            </div>
            <div className="macro-toolkit-execution-receipt-workspace__status" aria-label="执行证据与产物状态">
              <div>
                <span>脚本就绪</span>
                <strong>
                  {availableScriptCount}/{scripts.length}
                </strong>
              </div>
              <div>
                <span>输出文件</span>
                <strong>{payload?.output_files.length ?? 0}</strong>
              </div>
              <div>
                <span>源别名</span>
                <strong>
                  {sourceHitCount}/{sourceChecks.length}
                </strong>
              </div>
              <div>
                <span>回执</span>
                <strong>{actionReceipts.length}</strong>
              </div>
            </div>
          </div>

          <div className="macro-toolkit-execution-receipt-workspace__execution" aria-label="执行证据详情">
            <span className="macro-toolkit-execution-receipt-workspace__section-label">执行证据</span>
          <section
            id="macro-toolkit-tool-execution-detail"
            data-testid="macro-toolkit-tool-execution-detail"
            className={`macro-toolkit-section macro-toolkit-operations-section ${
              selectedGovernanceFocus === "execution" ||
              selectedEvidenceHref === "#macro-toolkit-tool-execution-detail"
                ? "macro-toolkit-section--audit-focus"
                : ""
            }`}
          >
            <div className="macro-toolkit-section-headline">
              <PageSectionLead
                eyebrow="toolkit"
                title="执行闭环总览"
                description="把脚本状态、数据证据和产物回执合并成投委会可复核的执行闭环。"
              />
              <Button
                icon={<ReloadOutlined />}
                onClick={() => void scriptsQuery.refetch()}
                loading={scriptsQuery.isFetching}
              >
                刷新
              </Button>
            </div>
            {scriptsQuery.isFetching && !payload ? (
              <Alert
                type="info"
                showIcon
                message="脚本注册表正在读取"
                description="脚本状态会稍后补上，核心分析已可先查看。"
              />
            ) : null}
            <div className="macro-toolkit-operations-brief">
              <MetricTile
                label="脚本就绪"
                value={`${availableScriptCount}/${scripts.length}`}
                detail="可执行能力已归入执行证据"
                tone={availableScriptCount === scripts.length ? "positive" : "neutral"}
              />
              <MetricTile
                label="业务证据"
                value={executionBusinessEvidence}
                detail="底层源名留在审计明细"
                detailMaxLength={38}
              />
              <MetricTile label="产物回执" value={payload?.output_files.length ?? 0} detail={outputReceiptDetail} />
              <MetricTile
                label="来源映射"
                value={`${sourceHitCount}/${sourceChecks.length}`}
                detail="旧别名已映射到当前业务证据"
              />
            </div>
          </section>

          {scriptsQuery.isError ? <Alert type="error" showIcon message="宏观工具加载失败" /> : null}

          {payload ? (
            <DataStatusStrip className="macro-toolkit-status-strip">
              <span>证据口径：{formatBusinessEvidenceLabel(scriptsQuery.data?.result_meta.basis)}</span>
              <span>业务证据：{executionBusinessEvidence}</span>
              <span>质量状态：{formatQualityFlagLabel(scriptsQuery.data?.result_meta.quality_flag)}</span>
            </DataStatusStrip>
          ) : null}

          {payload?.warnings.length ? (
            <Alert
              type="warning"
              showIcon
              message="仍有未落库的数据面"
              description={payload.warnings.join(" ")}
            />
          ) : null}

          <section
            id="macro-toolkit-cffex-detail"
            data-testid="macro-toolkit-cffex-detail"
            className={`macro-toolkit-section ${
              selectedEvidenceHref === "#macro-toolkit-cffex-detail" ? "macro-toolkit-section--audit-focus" : ""
            }`}
          >
            <PageSectionLead
              eyebrow="cffex"
              title="CFFEX席位状态"
              description="crowding_cn 等脚本依赖的中金所席位排名读面。"
            />
            <div className="macro-toolkit-cffex-panel">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  label="席位行数"
                  value={cffexStatus?.row_count ?? 0}
                  detail={cffexStatus?.status ?? "未读取"}
                />
                <MetricTile
                  label="最新交易日"
                  value={cffexStatus?.latest_trade_date ?? "缺失"}
                  detail={`对齐 ${cffexStatus?.reference_date ?? analysis?.as_of_date ?? "待定"}`}
                />
                <MetricTile
                  label="新鲜度"
                  value={statusLabel(cffexStatus?.freshness_status ?? "unknown")}
                  detail={
                    cffexStatus?.stale_days == null ? "待确认" : `落后 ${cffexStatus.stale_days} 天`
                  }
                />
              </div>
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCffex}
                  disabled={isOperationActionBusy && !isRefreshingCffex}
                  onClick={() => void refreshCffexMemberRank()}
                >
                  刷新席位明细
                </Button>
                {refreshResult ? <Alert type="success" showIcon message={refreshResult} /> : null}
                {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
              </div>
            </div>
          </section>

          <section
            id="macro-toolkit-commodity-detail"
            data-testid="macro-toolkit-commodity-detail"
            className={`macro-toolkit-section ${
              selectedEvidenceHref === "#macro-toolkit-commodity-detail" ? "macro-toolkit-section--audit-focus" : ""
            }`}
          >
            <PageSectionLead
              eyebrow="commodity"
              title="商品期货状态"
              description="刷新南华指数和宏观旁证商品期货；Crisis Score 公式仍只读取南华输入。"
            />
            <div className="macro-toolkit-cffex-panel" aria-label="商品期货刷新">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="已选品种"
                  value={`${selectedCommodityProducts.length}/${MACRO_COMMODITY_PRODUCT_OPTIONS.length}`}
                  detail={
                    selectedCommodityProducts.length === MACRO_COMMODITY_PRODUCT_OPTIONS.length
                      ? "默认全选，可缩小范围"
                      : selectedCommodityProducts.join(" / ") || "未选择"
                  }
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品权限"
                  value={choiceStockPermissionValue(commodityPermission)}
                  detail={commodityFuturesPermissionDetail(commodityPermission)}
                  detailTitle={choiceStockPermissionDetail(commodityPermission, "macro_toolkit.commodity_futures")}
                  tone={shouldShowCommodityPermissionNotice ? "missing" : "neutral"}
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="南华输入"
                  value={commodityNanhuaStatusValue(commodityStatus)}
                  detail={commodityNanhuaStatusDetail(commodityStatus)}
                  tone={commodityNanhuaStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<ClockCircleOutlined />}
                  label="最新日期"
                  value={commodityLatestDateValue(commodityStatus)}
                  detail={commodityTableStatusDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="覆盖品种"
                  value={commodityCoverageValue(commodityStatus)}
                  detail={commodityCoverageDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="数据来源"
                  value={commoditySourceValue(commodityStatus)}
                  detail={commoditySourceDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="证据归属"
                  value="商品期货证据"
                  detail="刷新后重新读取完整分析证据"
                />
              </div>
              <div className="macro-toolkit-commodity-selector">
                <span className="macro-toolkit-commodity-selector-label">刷新品种</span>
                <Checkbox.Group
                  className="macro-toolkit-commodity-products"
                  value={selectedCommodityProducts}
                  onChange={(values) => {
                    setSelectedCommodityProducts(values.map(String));
                    setCommoditySuggestedSelection([]);
                    setCommodityRefreshResult(null);
                    setCommodityRefreshError(null);
                    setCommodityRefreshRun(null);
                    setCommodityEvidenceReloadMessage(null);
                    setCommodityShortfallChanges([]);
                    setCommodityShortfallEstimates([]);
                  }}
                >
                  {MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => (
                    <Checkbox key={option.value} value={option.value}>
                      <span className="macro-toolkit-commodity-product-text">
                        <span>{option.label}</span>
                        <small>
                          {option.value} · {option.description}
                        </small>
                      </span>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </div>
              {commoditySuggestedSelection.length ? (
                <Alert
                  type="info"
                  showIcon
                  message={`已按 Crisis Score 建议选择：${commoditySuggestedSelection.join(" / ")}`}
                  description="下一步先预估商品期货，再根据预计行数决定是否刷新。"
                />
              ) : null}
              {shouldShowCommodityPermissionNotice ? (
                <Alert
                  type="warning"
                  showIcon
                  message={commodityFuturesPermissionNoticeTitle(commodityPermission)}
                  description={commodityFuturesPermissionNotice(commodityPermission)}
                />
              ) : null}
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<InfoCircleOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
                  onClick={() => void refreshCommodityFutures({ dryRun: true })}
                >
                  预估明细刷新
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
                  aria-label={commodityRefreshActionLabel}
                  onClick={() => void refreshCommodityFutures({ dryRun: false })}
                >
                  {commodityRefreshActionLabel}
                </Button>
                {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
                {commodityEvidenceReloadMessage ? (
                  <Alert
                    type={commodityEvidenceReloadMessage.includes("失败") ? "error" : "success"}
                    showIcon
                    message={commodityEvidenceReloadMessage}
                  />
                ) : null}
                {commodityShortfallChanges.length ? (
                  <Alert
                    type="success"
                    showIcon
                    message="Crisis Score 样本缺口变化"
                    description={formatCommodityShortfallChangeList(commodityShortfallChanges)}
                  />
                ) : null}
                {commodityShortfallEstimates.length ? (
                  <Alert
                    type={commodityShortfallEstimates.every((item) => item.canFill) ? "success" : "warning"}
                    showIcon
                    message="Crisis Score 样本预估"
                    description={formatCommodityShortfallEstimateList(commodityShortfallEstimates)}
                  />
                ) : null}
                {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
              </div>
              {commodityRefreshRun ? <CommodityRefreshResultPanel refresh={commodityRefreshRun} /> : null}
            </div>
          </section>

          </div>

          <aside className="macro-toolkit-execution-receipt-workspace__receipt" aria-label="产物回执详情">
            <span className="macro-toolkit-execution-receipt-workspace__section-label">产物回执</span>
            {committeeDeliveryChain}
            <section className="macro-toolkit-receipt-workpaper" aria-label="产物审计底稿">
              <div className="macro-toolkit-receipt-workpaper__head">
                <span>产物审计底稿</span>
                <strong>回执先审，明细后查</strong>
                <small>脚本、文件和日志保留在下方明细；投委会先看归档、来源、执行和留痕。</small>
              </div>
              <div className="macro-toolkit-receipt-workpaper__grid">
                {receiptWorkpaperItems.map((item) => (
                  <div className="macro-toolkit-receipt-workpaper__item" key={item.key}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small>{item.detail}</small>
                  </div>
                ))}
              </div>
            </section>
            <section
              className={`macro-toolkit-receipt-technical-details ${
                receiptTechnicalDetailsExpanded
                  ? "macro-toolkit-receipt-technical-details--expanded"
                  : "macro-toolkit-receipt-technical-details--collapsed"
              }`}
              aria-label="底稿技术明细"
            >
              <div className="macro-toolkit-receipt-technical-details__head">
                <div>
                  <span>底稿技术明细</span>
                  <strong>脚本、来源、注册表和日志</strong>
                  <small>{receiptTechnicalDetailsExpanded ? "已展开" : "默认收起"} · 审计追溯保留在这里</small>
                </div>
                <Button
                  size="small"
                  icon={receiptTechnicalDetailsExpanded ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                  aria-label={receiptTechnicalDetailsExpanded ? "收起明细" : "展开明细"}
                  aria-expanded={receiptTechnicalDetailsExpanded}
                  onClick={() => setReceiptTechnicalDetailsExpanded((expanded) => !expanded)}
                >
                  {receiptTechnicalDetailsExpanded ? "收起明细" : "展开明细"}
                </Button>
              </div>
              <div className="macro-toolkit-receipt-technical-details__body">
                <section
                  id="macro-toolkit-script-artifact-detail"
                  data-testid="macro-toolkit-script-artifact-detail"
                  className={`macro-toolkit-section ${
                    selectedGovernanceFocus === "artifacts" ||
                    selectedEvidenceHref === "#macro-toolkit-script-artifact-detail"
                      ? "macro-toolkit-section--audit-focus"
                      : ""
                  }`}
                >
                  <PageSectionLead
                    eyebrow="outputs"
                    title="脚本产物"
                    description="运行脚本后自动刷新这里，便于确认 CSV、图片或报告是否生成。"
                  />
                  {payload?.output_files.length ? (
                    <Table
                      className="macro-toolkit-table--receipt"
                      rowKey="path"
                      size="small"
                      columns={outputColumns}
                      dataSource={payload.output_files}
                      pagination={false}
                      scroll={{ x: 640 }}
                    />
                  ) : (
                    <div className="macro-toolkit-empty-output">尚未发现输出文件。</div>
                  )}
                </section>

                <section className="macro-toolkit-section">
                  <PageSectionLead
                    eyebrow="source"
                    title="系统数据源命中"
                    description="这些旧代码别名已经映射到当前系统的 Choice/Tushare 数据面。"
                  />
                  <div className="macro-toolkit-source-grid">
                    {sourceChecks.map((check) => (
                      <div className="macro-toolkit-source-item" key={check.alias}>
                        <span>{check.alias}</span>
                        <strong>{check.row_count}</strong>
                        <small>{formatSourceCheck(check)}</small>
                      </div>
                    ))}
                  </div>
                </section>

                {omittedEntries.length ? (
                  <section className="macro-toolkit-section">
                    <PageSectionLead
                      eyebrow="omitted"
                      title="未纳入脚本"
                      description="这些源文件保留为迁移证据，但暂不作为可执行宏观工作流。"
                    />
                    <div className="macro-toolkit-omitted-list">
                      {omittedEntries.map(([filename, reason]) => (
                        <div className="macro-toolkit-omitted-item" key={filename}>
                          <span>{filename}</span>
                          <small>{reason}</small>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}

                <section className="macro-toolkit-section">
                  <PageSectionLead
                    eyebrow="scripts"
                    title="脚本注册表"
                    description="脚本从原 macro_toolkit 聚合到后端宏观模块，前端通过注册表展示。"
                  />
                  <div className="macro-toolkit-toolbar">
                    <Select
                      value={selectedGroup}
                      options={groupOptions}
                      onChange={(value) => {
                        setSelectedGroup(value);
                        setSelectedName(null);
                      }}
                    />
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      disabled={!selectedScript || (isOperationActionBusy && !isRunning)}
                      loading={isRunning}
                      onClick={() => void runSelectedScript()}
                    >
                      运行选中脚本
                    </Button>
                  </div>
                  <Table
                    className="macro-toolkit-table--receipt"
                    rowKey="name"
                    size="small"
                    columns={scriptColumns}
                    dataSource={filteredScripts}
                    pagination={{ pageSize: 8, showSizeChanger: false }}
                    scroll={{ x: 640 }}
                    rowClassName={(script) =>
                      script.name === selectedScript?.name ? "macro-toolkit-row--selected" : ""
                    }
                    onRow={(script) => ({
                      onClick: () => setSelectedName(script.name),
                    })}
                  />
                </section>

                <section className="macro-toolkit-section">
                  <PageSectionLead
                    eyebrow="run"
                    title="运行结果"
                    description={selectedScript ? selectedScript.name : "暂无选中脚本"}
                  />
                  <div className="macro-toolkit-run-panel">
                    <div className="macro-toolkit-run-title">
                      <ToolOutlined />
                      <span>{selectedScript?.filename ?? "未选择"}</span>
                    </div>
                    {runError ? <Alert type="error" showIcon message={runError} /> : null}
                    {runResult ? (
                      <Alert
                        type={statusTone(runResult.status)}
                        showIcon
                        message={`状态：${runResult.status}`}
                        description={`退出码：${runResult.exit_code ?? "无"} · 输出文件：${runResult.output_files.length}`}
                      />
                    ) : null}
                    <pre className="macro-toolkit-console">
                      {runResult?.stdout || runResult?.stderr || "尚未运行。"}
                    </pre>
                  </div>
                </section>
              </div>
            </section>
          </aside>
        </section>
      ) : null}
    </div>
  );
}

function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const evidence = result.evidence.length ? result.evidence : result.warnings;
  const inputEvidence = normalizeInputEvidence(result);
  return (
    <div
      className={`macro-toolkit-capability-result macro-toolkit-capability-result--${result.tone}`}
    >
      <div className="macro-toolkit-capability-result-head">
        <span>
          {result.legacy_module} · {result.label}
        </span>
        <Tag color={statusColor(result.status)}>{statusLabel(result.status)}</Tag>
      </div>
      <strong>{metric ? formatMetricDisplay(metric) : result.score ?? statusLabel(result.status)}</strong>
      <ScoreTrack score={result.score} />
      <p>{result.headline}</p>
      <small>{evidence.slice(0, 3).join(" / ") || "暂无证据"}</small>
      {inputEvidence ? (
        <div className="macro-toolkit-input-evidence">
          {inputEvidence.missingInputs.length ? (
            <span>缺失输入：{inputEvidence.missingInputs.join(" / ")}</span>
          ) : null}
          {inputEvidence.sources.length ? <span>数据源：{inputEvidence.sources.join(" / ")}</span> : null}
          {inputEvidence.latestDates.length ? <span>最新日期：{inputEvidence.latestDates.join(" / ")}</span> : null}
          {inputEvidence.inputs.length ? (
            <small>
              {inputEvidence.inputs
                .slice(0, 3)
                .map((item) => `${item.label || item.field}: ${item.series_id ?? "缺失"} ${item.latest_date ?? ""}`.trim())
                .join(" / ")}
            </small>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CrisisGapAction({
  group,
  repairItems,
  commodityRefreshProducts,
  refreshingSourceAlias,
  commodityRefreshResult,
  commodityShortfallEstimates,
  sourceBackfillResult,
  sourceBackfillError,
  onRefreshCommodityProducts,
  onPreviewCommodityRefreshProducts,
  onRepairSourceBackfill,
}: {
  group: CrisisGapGroup;
  repairItems: MacroToolkitRepairItem[];
  commodityRefreshProducts: string[];
  refreshingSourceAlias: string | null;
  commodityRefreshResult: string | null;
  commodityShortfallEstimates: CommodityShortfallEstimate[];
  sourceBackfillResult: string | null;
  sourceBackfillError: string | null;
  onRefreshCommodityProducts?: (products: string[]) => void;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem, group: CrisisGapGroup) => void;
}) {
  const canRefreshSuggestedCommodities =
    group.key === "commodity" &&
    commodityRefreshProducts.length > 0 &&
    commodityShortfallEstimates.length > 0 &&
    commodityShortfallEstimates.every((item) => item.canFill) &&
    Boolean(onRefreshCommodityProducts);
  if (group.key === "commodity" && commodityRefreshProducts.length && onPreviewCommodityRefreshProducts) {
    return (
      <div className="macro-toolkit-crisis-gap-action">
        <Button
          size="small"
          type="primary"
          icon={<InfoCircleOutlined />}
          aria-label="按建议预估"
          onClick={() => onPreviewCommodityRefreshProducts(commodityRefreshProducts)}
        >
          按建议预估
        </Button>
        {commodityRefreshResult ? <small>{commodityRefreshResult}</small> : null}
        {commodityShortfallEstimates.length ? (
          <small>{formatCommodityShortfallEstimateList(commodityShortfallEstimates)}</small>
        ) : null}
        {canRefreshSuggestedCommodities ? (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            aria-label="按建议刷新并重读"
            onClick={() => onRefreshCommodityProducts?.(commodityRefreshProducts)}
          >
            按建议刷新并重读
          </Button>
        ) : null}
      </div>
    );
  }

  const repairItem = findCrisisGapRepairItem(group, repairItems);
  if (!repairItem || !onRepairSourceBackfill) {
    return null;
  }
  const alias = normalizeMacroSourceBackfillAlias(repairItem.alias);
  return (
    <div className="macro-toolkit-crisis-gap-action">
      <Button
        size="small"
        icon={<ReloadOutlined />}
        loading={refreshingSourceAlias === alias}
        aria-label={repairItem.action?.label ?? "需要补齐来源数据"}
        onClick={() => onRepairSourceBackfill(repairItem, group)}
      >
        {repairItem.action?.label ?? "需要补齐来源数据"}
      </Button>
      {sourceBackfillResult ? <small>{sourceBackfillResult}</small> : null}
      {sourceBackfillError ? <small>{sourceBackfillError}</small> : null}
    </div>
  );
}

function CrisisGapRepairFeedback({ feedback }: { feedback: CrisisGapRepairFeedback }) {
  return (
    <div
      className={`macro-toolkit-crisis-gap-feedback macro-toolkit-crisis-gap-feedback--${feedback.status}`}
      data-testid="crisis-gap-repair-feedback"
    >
      <span>{feedback.groupLabel}</span>
      <strong>{feedback.message}</strong>
      <small>{feedback.detail}</small>
    </div>
  );
}

function CrisisCommodityClosurePanel({
  changes,
  evidenceChain,
}: {
  changes: CommodityShortfallChange[];
  evidenceChain: CommodityRefreshEvidenceChain | null;
}) {
  const resolvedCount = changes.filter((item) => item.resolved).length;
  return (
    <div className="macro-toolkit-crisis-commodity-closure" aria-label="Crisis Score 样本刷新闭环">
      <div>
        <span>样本缺口刷新闭环</span>
        <strong>
          已补齐 {resolvedCount}/{changes.length}
        </strong>
      </div>
      {evidenceChain ? (
        <div className="macro-toolkit-crisis-commodity-closure__chain">
          <small>建议品种 {formatCommodityProductsInline(evidenceChain.suggestedProducts)}</small>
          <small>实际刷新 {formatCommodityProductsInline(evidenceChain.refreshedProducts)}</small>
          <small>{evidenceChain.fullReloaded ? "完整分析已重读" : "完整分析重读待确认"}</small>
        </div>
      ) : null}
      <div className="macro-toolkit-crisis-commodity-closure__grid">
        {changes.map((item) => (
          <small key={item.field}>
            {item.label} · 刷新前 {item.before} · 刷新后 {item.after} · 剩余缺口 {item.remainingGap}
          </small>
        ))}
      </div>
    </div>
  );
}

function CrisisCommodityShadowDecisionPanel({
  coverage,
  admission,
  approvalPack,
  commodityInput = null,
  analysisMeta,
  analysisAsOfDate = null,
}: {
  coverage: CrisisCommodityCoverage;
  admission: CrisisCommodityAdmission | null;
  approvalPack: CrisisCommodityApprovalPack | null;
  commodityInput?: MacroToolkitInputEvidenceItem | null;
  analysisMeta?: ResultMeta | null;
  analysisAsOfDate?: string | null;
}) {
  const promotionItems = coverage.items.map(commodityPromotionRuleItem);
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const rejectedCount = promotionItems.filter((item) => item.status === "not_recommended").length;
  const reviewQueueItems = coverage.items.filter(isCommodityShadowReviewReady);
  const shortQueueItems = coverage.items.filter(isCommodityShadowHistoryShort);
  const auditPackCopyText = buildCommodityPromotionAuditPackCopyText(promotionItems, {
    manualCount,
    rejectedCount,
    analysisMeta,
    analysisAsOfDate,
    reviewQueueItems,
    shortQueueItems,
    coverageItems: coverage.items,
    commodityInput,
    summary: coverage.candidate_summary,
  });
  const [auditPackCopyStatus, setAuditPackCopyStatus] = useState<"idle" | "success" | "error">("idle");
  const handleCopyAuditPack = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (typeof writeText !== "function") {
      setAuditPackCopyStatus("error");
      return;
    }
    try {
      await writeText(auditPackCopyText);
      setAuditPackCopyStatus("success");
    } catch {
      setAuditPackCopyStatus("error");
    }
  }, [auditPackCopyText]);
  const summary = coverage.candidate_summary;
  if (!summary) {
    return null;
  }
  const reviewableCount = summary.shadow_evaluation_ready_count;
  const shortCount = summary.shadow_evaluation_short_count;
  const totalCount = coverage.tracked_count || coverage.items.length;
  const formalCommodityInputText = commodityInput
    ? `${commodityInput.label || commodityInput.field} · ${formatCrisisInputIdentifiers(commodityInput)}`
    : "南华商品输入缺失";
  const shadowCandidateText = formatCommodityActionQueueLabels(reviewQueueItems);
  return (
    <div className="macro-toolkit-crisis-shadow-decision" aria-label="候选商品影子评估决策面板">
      <div className="macro-toolkit-crisis-shadow-decision__head">
        <div>
          <span>候选商品影子评估</span>
          <strong>
            可复核 {reviewableCount}/{totalCount}
          </strong>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="default">当前未计入 Crisis Score</Tag>
          <Tag color={summary.approval_required ? "gold" : "green"}>
            {summary.approval_required ? "转正前需审批" : "暂无审批要求"}
          </Tag>
          <Tag color={shortCount ? "orange" : "green"}>样本不足 {shortCount}</Tag>
        </div>
      </div>
      <CommodityShadowActionQueue
        reviewItems={reviewQueueItems}
        shortItems={shortQueueItems}
        summary={summary}
      />
      <CommodityCandidateReviewConclusion
        admission={admission}
        items={coverage.items}
        promotionItems={promotionItems}
      />
      <CommodityCandidateApprovalPackPanel approvalPack={approvalPack} />
      <div className="macro-toolkit-crisis-shadow-decision__grid">
        {coverage.items.map((item) => (
          <div className="macro-toolkit-crisis-shadow-decision__item" key={item.field}>
            <div className="macro-toolkit-capability-result-head">
              <span>{item.label || item.field}</span>
              <Tag color={commodityShadowStatusColor(item.shadow_evaluation?.status)}>
                {item.shadow_evaluation?.label ?? "影子评估待确认"}
              </Tag>
            </div>
            <strong>{formatCommodityCoverageIdentifiers(item)}</strong>
            <small>
              {item.source ?? "source missing"} · {item.series_id ?? "series missing"} ·{" "}
              {item.used_in_formula ? "已纳入公式" : "当前未计入 Crisis Score"}
            </small>
            {item.shadow_evaluation ? (
              <>
                <small>{formatCommodityShadowDecisionMetrics(item.shadow_evaluation)}</small>
                <small>{item.shadow_evaluation.next_step}</small>
              </>
            ) : item.candidate_decision ? (
              <small>{item.candidate_decision.next_step}</small>
            ) : null}
          </div>
        ))}
      </div>
      <div className="macro-toolkit-crisis-promotion-rule-pack" aria-label="候选商品转正规则包">
        <div className="macro-toolkit-crisis-promotion-rule-pack__head">
          <div>
            <span>候选商品转正规则包</span>
            <strong>
              待人工判断 {manualCount} · 不建议进入公式 {rejectedCount}
            </strong>
          </div>
          <small>规则只用于审批前复核，不改变 Crisis Score 公式</small>
          <small>规则版本 {MACRO_COMMODITY_SHADOW_RULE_VERSION}</small>
          <small>
            准入检查：样本&gt;={MACRO_COMMODITY_SHADOW_MIN_SAMPLES} / 危机样本&gt;=
            {MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} / 相关性可读 / 命中率可读
          </small>
          <small>样本阈值 &gt;={MACRO_COMMODITY_SHADOW_MIN_SAMPLES} 个重叠样本</small>
          <small>
            危机样本阈值 &gt;={MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} 个高 Crisis Score 样本
          </small>
          <small>
            相关性阈值 |corr|&gt;={MACRO_COMMODITY_SHADOW_MIN_CORRELATION.toFixed(2)} 才可直接通过
          </small>
          <div className="macro-toolkit-crisis-promotion-rule-pack__actions">
            <Button
              aria-label="复制审计包"
              icon={<CopyOutlined aria-hidden="true" />}
              size="small"
              type="default"
              onClick={() => void handleCopyAuditPack()}
            >
              {auditPackCopyStatus === "success"
                ? "已复制"
                : auditPackCopyStatus === "error"
                  ? "复制失败"
                  : "复制审计包"}
            </Button>
            {auditPackCopyStatus !== "idle" ? (
              <span
                aria-atomic="true"
                aria-label="审计包复制状态"
                aria-live="polite"
                className={`macro-toolkit-crisis-promotion-rule-pack__copy-status macro-toolkit-crisis-promotion-rule-pack__copy-status--${auditPackCopyStatus}`}
                role="status"
              >
                {auditPackCopyStatus === "success" ? "审计包已复制" : "复制失败，请手动选择审计包文本"}
              </span>
            ) : null}
          </div>
        </div>
        <div className="macro-toolkit-crisis-promotion-rule-pack__audit" aria-label="shadow_rule_v1 审计注记">
          <strong>{MACRO_COMMODITY_SHADOW_RULE_VERSION} 审计注记</strong>
          <small>用途：商品候选进入公式前的影子复核</small>
          <small>边界：不写入 Crisis Score，不改变权重</small>
          <small>审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交</small>
        </div>
        <div
          className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary"
          aria-label="Crisis Score 商品公式输入边界"
        >
          <div className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary-item">
            <span>正式输入</span>
            <strong>{formalCommodityInputText}</strong>
            <small>
              {commodityInput ? "已纳入 Crisis Score 公式" : "已纳入 Crisis Score 公式的南华输入未命中"}
            </small>
          </div>
          <div className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary-item">
            <span>影子候选</span>
            <strong>{shadowCandidateText}</strong>
            <small>当前未计入 Crisis Score</small>
          </div>
        </div>
        <div className="macro-toolkit-crisis-promotion-rule-pack__grid">
          {promotionItems.map((item) => (
            <div className="macro-toolkit-crisis-promotion-rule-pack__item" key={item.field}>
              <small>
                {item.label} · {commodityPromotionRuleStatusLabel(item.status)} · {item.reason}
              </small>
              {item.checks.map((check) => (
                <small key={`${item.field}-${check.name}`}>
                  {item.label} · {check.name} {commodityPromotionRuleCheckStatusLabel(check.status)} {check.value}
                </small>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CrisisCommodityShadowImpactPanel({
  currentScore,
  coverage,
  shadowImpact,
}: {
  currentScore: number | null;
  coverage: CrisisCommodityCoverage;
  shadowImpact: CrisisCommodityShadowImpact | null;
}) {
  const promotionItems = coverage.items.map(commodityPromotionRuleItem);
  const driverItems = promotionItems.filter((item) => item.status !== "not_recommended");
  const driverFields = new Set(driverItems.map((item) => item.field));
  const driverCoverageItems = coverage.items.filter((item) => driverFields.has(item.field));
  const readyCount = promotionItems.filter((item) => item.status === "ready_for_review").length;
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const hasShadowScore = shadowImpact?.shadow_score != null;
  const impactDrivers = shadowImpact?.candidate_contributions.length
    ? shadowImpact.candidate_contributions
    : null;
  return (
    <div className="macro-toolkit-crisis-shadow-impact" aria-label="Crisis Score v2 影子影响评估">
      <div className="macro-toolkit-crisis-shadow-impact__head">
        <div>
          <span>Crisis Score v2 影子影响评估</span>
          <strong>{hasShadowScore ? "shadow score 只读试算" : "影子分数待公式确认"}</strong>
        </div>
        <small>
          {shadowImpact?.formula_version ?? "商品候选当前只做影子影响判断"}；不改变正式 Crisis Score。
        </small>
      </div>
      <div className="macro-toolkit-crisis-shadow-impact__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="正式 Crisis Score"
          value={shadowImpact?.current_score ?? currentScore ?? "缺失"}
          detail="不改变正式 Crisis Score"
          tone={(shadowImpact?.current_score ?? currentScore) == null ? "missing" : "neutral"}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="v2 shadow score"
          value={shadowImpact?.shadow_score ?? "影子分数待公式确认"}
          detail={
            shadowImpact
              ? `delta ${formatSignedDelta(shadowImpact.delta)} · ${shadowImpact.formula_version}`
              : "不能直接换算为分数"
          }
          tone="neutral"
        />
        <MetricTile
          icon={<ArrowUpOutlined />}
          label="影响方向"
          value={shadowImpact ? commodityShadowImpactDirectionLabel(shadowImpact.direction) : "待公式/权重确认"}
          detail={
            shadowImpact
              ? `${shadowImpact.scope} · ${formatCommodityShadowImpactWarnings(shadowImpact)}`
              : formatCommodityShadowImpactDirectionDetail(driverCoverageItems)
          }
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="候选驱动"
          value={`${shadowImpact?.candidate_count ?? driverItems.length} 个待复核`}
          detail={
            shadowImpact
              ? `可进入公式前审批 ${shadowImpact.approval_required ? "是" : "否"}`
              : `可进入人工复核 ${readyCount} / 继续观察 ${manualCount}`
          }
          tone="neutral"
        />
      </div>
      {shadowImpact?.warnings.length ? (
        <div className="macro-toolkit-tag-row" aria-label="影子影响警示">
          {shadowImpact.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      ) : null}
      <div className="macro-toolkit-crisis-shadow-impact__grid">
        {impactDrivers
          ? impactDrivers.map((item) => (
              <div className="macro-toolkit-crisis-shadow-impact__item" key={item.field}>
                <div className="macro-toolkit-capability-result-head">
                  <span>{item.label || item.field}</span>
                  <Tag color="blue">{item.status}</Tag>
                </div>
                <small>{formatCommodityShadowContributionDetail(item)}</small>
                <small>{item.used_in_official_score ? "已纳入正式分数" : "不改变正式 Crisis Score"}</small>
              </div>
            ))
          : driverCoverageItems.map((item) => {
          const promotionItem = promotionItems.find((candidate) => candidate.field === item.field);
          return (
            <div className="macro-toolkit-crisis-shadow-impact__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityReviewConclusionColor(promotionItem?.status ?? "not_recommended")}>
                  {commodityReviewConclusionLabel(promotionItem?.status ?? "not_recommended")}
                </Tag>
              </div>
              <small>{formatCommodityShadowImpactDriverDetail(item)}</small>
              <small>不能直接换算为分数</small>
            </div>
          );
        })}
      </div>
      {shadowImpact?.warnings.length ? (
        <small className="macro-toolkit-crisis-shadow-impact__note">
          {shadowImpact.warnings.join(" / ")}
        </small>
      ) : null}
      <small className="macro-toolkit-crisis-shadow-impact__note">
        {shadowImpact?.next_step ?? "审批建议：先复核候选相关性，再确认 v2 权重"}
      </small>
    </div>
  );
}

function CommodityCandidateReviewConclusion({
  admission,
  items,
  promotionItems,
}: {
  admission: CrisisCommodityAdmission | null;
  items: CrisisCommodityCoverageItem[];
  promotionItems: CommodityPromotionRuleItem[];
}) {
  if (admission) {
    return (
      <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选复核结论">
        <div className="macro-toolkit-crisis-review-conclusion__head">
          <div>
            <span>商品候选复核结论</span>
            <strong>
              商品候选准入评估：建议纳入 {admission.decision_counts.recommend_include} · 继续观察{" "}
              {admission.decision_counts.watch} · 暂不纳入 {admission.decision_counts.do_not_include}
            </strong>
          </div>
          <small>{admission.rule_version} · {admission.scope}</small>
          <small>审批前不改变正式 Crisis Score</small>
        </div>
        {admission.warnings.length ? (
          <div className="macro-toolkit-tag-row" aria-label="商品候选准入警告">
            {admission.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
        <div className="macro-toolkit-crisis-review-conclusion__grid">
          {admission.items.map((item) => (
            <div className="macro-toolkit-crisis-review-conclusion__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityAdmissionDecisionColor(item.decision)}>{item.decision_label}</Tag>
              </div>
              <strong>{item.reason}</strong>
              <small>{formatCommodityAdmissionMetrics(item)}</small>
              <small>下一步：{formatCommodityAdmissionNextStep(item)}</small>
            </div>
          ))}
        </div>
        <small className="macro-toolkit-crisis-shadow-impact__note">{admission.next_step}</small>
      </div>
    );
  }
  const promotionByField = new Map(promotionItems.map((item) => [item.field, item]));
  const readyCount = promotionItems.filter((item) => item.status === "ready_for_review").length;
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const rejectedCount = promotionItems.filter((item) => item.status === "not_recommended").length;
  return (
    <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选复核结论">
      <div className="macro-toolkit-crisis-review-conclusion__head">
        <div>
          <span>商品候选复核结论</span>
          <strong>
            可进入人工复核 {readyCount} · 继续观察 {manualCount} · 不建议纳入 {rejectedCount}
          </strong>
        </div>
        <small>复用 shadow_rule_v1 判断，只做展示，不改变 Crisis Score 公式或权重</small>
      </div>
      <div className="macro-toolkit-crisis-review-conclusion__grid">
        {items.map((item) => {
          const promotionItem = promotionByField.get(item.field) ?? commodityPromotionRuleItem(item);
          return (
            <div className="macro-toolkit-crisis-review-conclusion__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityReviewConclusionColor(promotionItem.status)}>
                  {commodityReviewConclusionLabel(promotionItem.status)}
                </Tag>
              </div>
              <strong>{promotionItem.reason}</strong>
              <small>{formatCommodityReviewConclusionMetrics(item)}</small>
              <small>{formatCommodityReviewConclusionNextStep(promotionItem.status, item)}</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CommodityCandidateApprovalPackPanel({
  approvalPack,
}: {
  approvalPack: CrisisCommodityApprovalPack | null;
}) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "success" | "error">("idle");
  const handleCopyApprovalPack = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (!approvalPack || typeof writeText !== "function") {
      setCopyStatus("error");
      return;
    }
    try {
      await writeText(approvalPack.copy_text);
      setCopyStatus("success");
    } catch {
      setCopyStatus("error");
    }
  }, [approvalPack]);

  if (!approvalPack) {
    return null;
  }

  return (
    <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选审批材料">
      <div className="macro-toolkit-crisis-review-conclusion__head">
        <div>
          <span>商品候选审批材料</span>
          <strong>{approvalPack.summary}</strong>
        </div>
        <small>{approvalPack.pack_version} · {approvalPack.scope}</small>
        <small>shadow delta {formatSignedDeltaFromPack(approvalPack.copy_text)}</small>
      </div>
      <div className="macro-toolkit-tag-row" aria-label="商品候选审批材料警告">
        {approvalPack.warnings.map((warning) => (
          <Tag color="gold" key={warning}>
            {warning}
          </Tag>
        ))}
      </div>
      <div className="macro-toolkit-crisis-review-conclusion__grid">
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>建议纳入</span>
          <strong>{approvalPack.decision_counts.recommend_include}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.recommended_fields)}</small>
        </div>
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>继续观察</span>
          <strong>{approvalPack.decision_counts.watch}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.watch_fields)}</small>
        </div>
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>暂不纳入</span>
          <strong>{approvalPack.decision_counts.do_not_include}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.rejected_fields)}</small>
        </div>
      </div>
      <div className="macro-toolkit-crisis-promotion-rule-pack__actions">
        <Button
          aria-label="复制审批材料"
          icon={<CopyOutlined aria-hidden="true" />}
          size="small"
          type="default"
          onClick={() => void handleCopyApprovalPack()}
        >
          {copyStatus === "success" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制审批材料"}
        </Button>
        {copyStatus !== "idle" ? (
          <small
            aria-label="审批材料复制状态"
            className={`macro-toolkit-crisis-promotion-rule-pack__copy-status macro-toolkit-crisis-promotion-rule-pack__copy-status--${copyStatus}`}
          >
            {copyStatus === "success" ? "审批材料已复制" : "复制失败，请手动选择审批材料文本"}
          </small>
        ) : null}
      </div>
    </div>
  );
}

function CommodityShadowActionQueue({
  reviewItems,
  shortItems,
  summary,
}: {
  reviewItems: CrisisCommodityCoverageItem[];
  shortItems: CrisisCommodityCoverageItem[];
  summary: CrisisCommodityCandidateSummary;
}) {
  return (
    <div className="macro-toolkit-crisis-shadow-action-queue" aria-label="商品候选下一动作队列">
      <div className="macro-toolkit-crisis-shadow-action-queue__item">
        <span>人工复核队列</span>
        <strong>{formatCommodityActionQueueLabels(reviewItems)}</strong>
        <small>相关性与命中率可读，但进入公式前仍需审批确认</small>
      </div>
      <div className="macro-toolkit-crisis-shadow-action-queue__item">
        <span>补历史样本队列</span>
        <strong>{formatCommodityActionQueueLabels(shortItems)}</strong>
        <small>当前未计入 Crisis Score；先补齐重叠样本和危机期样本</small>
      </div>
      <div className="macro-toolkit-crisis-shadow-action-queue__next">
        <span>处理顺序</span>
        <strong>{formatCommodityActionQueueNextStep(reviewItems, shortItems, summary)}</strong>
      </div>
    </div>
  );
}

type CommodityRefreshProductRow = {
  key: string;
  productCode: string;
  productName: string;
  seriesId: string;
  status: "estimated" | "written" | "missing";
  estimatedRows: number | null;
  rowCount: number | null;
  rowCountLabel: string;
  latestDate: string;
  latestValue: number | null;
  vendor: string;
  table: string;
  isNanhua: boolean;
};

function CommodityRefreshResultPanel({ refresh }: { refresh: MacroToolkitCommodityFuturesRefreshRun }) {
  const rows = normalizeCommodityRefreshRows(refresh);
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const nanhuaRow = rows.find((row) => row.isNanhua);
  const summary = refresh.summary;
  const nanhuaMessage =
    nanhuaRow && !isDryRun && nanhuaRow.status === "written"
      ? "Crisis Score 南华输入已更新"
      : nanhuaRow
        ? "NHCI / NH0100.NHF 已纳入本次检查"
        : "NHCI / NH0100.NHF 未选择";
  const columns: ColumnsType<CommodityRefreshProductRow> = [
    {
      title: "品种",
      dataIndex: "productName",
      key: "productName",
      render: (_, row) => (
        <div className="macro-toolkit-commodity-refresh-product">
          <span>{row.productName}</span>
          <small>{commodityRefreshIdentifierText(row)}</small>
        </div>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (_, row) => <Tag color={commodityRefreshStatusColor(row.status)}>{commodityRefreshStatusText(row.status)}</Tag>,
    },
    {
      title: "行数",
      dataIndex: "rowCountLabel",
      key: "rowCountLabel",
      width: 110,
    },
    {
      title: "最新日期 / 值",
      dataIndex: "latestDate",
      key: "latestDate",
      render: (_, row) => (
        <span>
          {row.latestDate}
          {row.latestValue == null ? "" : ` / ${formatNumberValue(row.latestValue, 2)}`}
        </span>
      ),
    },
    {
      title: "来源",
      dataIndex: "vendor",
      key: "vendor",
      width: 120,
    },
    {
      title: "写入表",
      dataIndex: "table",
      key: "table",
      render: (table: string) => <span className="macro-toolkit-nowrap-soft">{table}</span>,
    },
  ];

  return (
    <div className="macro-toolkit-commodity-refresh-result" aria-label="商品期货刷新结果">
      <div className="macro-toolkit-commodity-refresh-summary">
        <span>{isDryRun ? "预估结果" : "刷新结果"}</span>
        <strong>{formatCommodityRefreshResult(refresh)}</strong>
        <Tag color={nanhuaRow && !isDryRun && nanhuaRow.status === "written" ? "green" : "blue"}>{nanhuaMessage}</Tag>
      </div>
      {summary ? <CommodityRefreshSummaryStrip summary={summary} isDryRun={isDryRun} /> : null}
      <Table
        className="macro-toolkit-table--wide"
        rowKey="key"
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 760 }}
      />
    </div>
  );
}

function CommodityRefreshSummaryStrip({
  summary,
  isDryRun,
}: {
  summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>;
  isDryRun: boolean;
}) {
  return (
    <div className="macro-toolkit-commodity-refresh-closure" aria-label="商品期货刷新后闭环">
      <span>{isDryRun ? "预估基线" : "刷新后闭环"}</span>
      <strong>{commodityRefreshRowDeltaText(summary)}</strong>
      <strong>{commodityRefreshLatestDateText(summary)}</strong>
      <strong>{commodityRefreshCoverageText(summary)}</strong>
      <strong>{commodityRefreshNanhuaText(summary)}</strong>
      <strong>{commodityRefreshSourceText(summary)}</strong>
    </div>
  );
}

function CrisisScoreEvidencePanel({
  result,
  analysisMeta = null,
  analysisAsOfDate = null,
  repairItems = [],
  refreshingSourceAlias = null,
  commodityRefreshResult = null,
  commodityRefreshEvidenceChain = null,
  commodityShortfallChanges = [],
  commodityShortfallEstimates = [],
  repairFeedback = null,
  sourceBackfillResult = null,
  sourceBackfillError = null,
  onRepairSourceBackfill,
  onApplyCommodityRefreshProducts,
  onPreviewCommodityRefreshProducts,
  onRefreshCommodityProducts,
}: {
  result: MacroToolkitCapabilityResult;
  analysisMeta?: ResultMeta | null;
  analysisAsOfDate?: string | null;
  repairItems?: MacroToolkitRepairItem[];
  refreshingSourceAlias?: string | null;
  commodityRefreshResult?: string | null;
  commodityRefreshEvidenceChain?: CommodityRefreshEvidenceChain | null;
  commodityShortfallChanges?: CommodityShortfallChange[];
  commodityShortfallEstimates?: CommodityShortfallEstimate[];
  repairFeedback?: CrisisGapRepairFeedback | null;
  sourceBackfillResult?: string | null;
  sourceBackfillError?: string | null;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem, group: CrisisGapGroup) => void;
  onApplyCommodityRefreshProducts?: (products: string[]) => void;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
  onRefreshCommodityProducts?: (products: string[]) => void;
}) {
  const normalizedEvidence = normalizeInputEvidence(result);
  const inputEvidence = normalizedEvidence?.inputs ?? [];
  const rawResult = result.result;
  const availableComponentCount = toDisplayNumber(rawResult.available_component_count);
  const componentCount = toDisplayNumber(rawResult.component_count);
  const components = Array.isArray(rawResult.components)
    ? rawResult.components.filter(isCrisisComponent)
    : [];
  const weights = isRecord(rawResult.weights) ? rawResult.weights : {};
  const commodityInput = inputEvidence.find(isNanhuaCrisisInput);
  const commodityCoverage = normalizeCommodityCoverage(rawResult.commodity_coverage);
  const commodityShadowImpact = normalizeCommodityShadowImpact(rawResult.shadow_impact);
  const commodityAdmission = normalizeCommodityAdmission(rawResult.commodity_candidate_admission);
  const commodityApprovalPack = normalizeCommodityApprovalPack(rawResult.commodity_candidate_approval_pack);
  const commodityShortRefreshProducts = commodityCoverage?.candidate_summary
    ? commodityShadowRefreshProducts(commodityCoverage.candidate_summary)
    : [];
  const commodityShortRefreshHint = formatCommodityShadowRefreshHint(commodityShortRefreshProducts);
  const warnings = uniqueDisplayParts([...result.warnings, ...(normalizedEvidence?.missingInputs ?? [])]);
  const crisisGapGroups = buildCrisisGapGroups(inputEvidence, warnings, commodityCoverage);
  const crisisGapCount = crisisGapGroups.reduce((total, group) => total + group.items.length, 0);
  const crisisGapDetail = formatCrisisGapSummaryDetail(crisisGapGroups);

  return (
    <section
      className="macro-toolkit-section macro-toolkit-crisis-evidence"
      aria-label="Crisis Score 数据来源"
    >
      <PageSectionLead
        eyebrow="crisis evidence"
        title="Crisis Score 数据来源"
        description="完整分析返回后展示每个输入、组件权重和缺口；缺失输入保持缺失，不折算为 0。"
      />

      <div className="macro-toolkit-crisis-evidence__summary">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="分数组件覆盖"
          value={`${availableComponentCount}/${componentCount}`}
          detail={components.map((component) => component.key).join(" / ") || "components missing"}
          tone={result.status === "complete" ? "positive" : "neutral"}
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="商品期货输入"
          value={commodityInput?.available ? "已命中" : "缺失"}
          detail={formatCrisisInputDetail(commodityInput)}
          tone={commodityInput?.available ? "positive" : "missing"}
          detailMaxLength={72}
        />
        <MetricTile
          icon={<WarningOutlined />}
          label="缺口提示"
          value={crisisGapCount}
          detail={crisisGapDetail}
          tone={crisisGapCount ? "neutral" : "positive"}
        />
      </div>

      {commodityShortfallChanges.length ? (
        <CrisisCommodityClosurePanel
          changes={commodityShortfallChanges}
          evidenceChain={commodityRefreshEvidenceChain}
        />
      ) : null}

      {crisisGapGroups.length ? (
        <div className="macro-toolkit-crisis-gap-list" aria-label="Crisis Score 缺口清单">
          <div className="macro-toolkit-crisis-gap-list__head">
            <strong>Crisis Score 缺口清单</strong>
            <small>缺失不按 0 处理；补齐后重新运行完整分析确认分数。</small>
          </div>
          {repairFeedback ? <CrisisGapRepairFeedback feedback={repairFeedback} /> : null}
          <div className="macro-toolkit-crisis-gap-list__grid">
            {crisisGapGroups.map((group) => (
              <div className="macro-toolkit-crisis-gap-group" key={group.key}>
                <span>{group.label}</span>
                {group.items.map((item) => (
                  <small key={`${item.label}-${item.warning}`}>
                    {item.label} · {item.warning} · {item.detail}
                  </small>
                ))}
                <CrisisGapAction
                  group={group}
                  repairItems={repairItems}
                  commodityRefreshProducts={commodityShortRefreshProducts}
                  refreshingSourceAlias={refreshingSourceAlias}
                  commodityRefreshResult={commodityRefreshResult}
                  commodityShortfallEstimates={commodityShortfallEstimates}
                  sourceBackfillResult={sourceBackfillResult}
                  sourceBackfillError={sourceBackfillError}
                  onRefreshCommodityProducts={onRefreshCommodityProducts}
                  onPreviewCommodityRefreshProducts={onPreviewCommodityRefreshProducts}
                  onRepairSourceBackfill={onRepairSourceBackfill}
                />
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="macro-toolkit-crisis-evidence__components">
        {components.map((component) => (
          <div className="macro-toolkit-crisis-component" key={component.key}>
            <span>{component.label}</span>
            <strong>{formatValue(component.z_score, "")}</strong>
            <small>
              {component.key} · weight {formatCrisisWeight(component.key, weights)} · raw{" "}
              {formatValue(component.raw_value, "")}
            </small>
          </div>
        ))}
      </div>

      {commodityCoverage ? (
        <div className="macro-toolkit-crisis-commodity-coverage">
          <MetricTile
            icon={<DatabaseOutlined />}
            label="商品旁证覆盖"
            value={`${commodityCoverage.available_count}/${commodityCoverage.tracked_count}`}
            detail={`${commodityCoverage.role} · 非公式输入`}
            tone="neutral"
          />
          <small className="macro-toolkit-crisis-coverage-note">
            Crisis Score 公式仍仅使用 {commodityCoverage.used_in_crisis_score.join(" / ") || "nanhua"}；本区块为{" "}
            {commodityCoverage.role}
          </small>
          <small className="macro-toolkit-crisis-coverage-note">
            候选商品仅做影子评估，当前未计入 Crisis Score 分数。
          </small>
          {commodityCoverage.candidate_summary ? (
            <>
              <div className="macro-toolkit-crisis-evidence__summary">
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品扩展候选"
                  value={`${commodityCoverage.candidate_summary.shadow_review_ready_count} 个就绪`}
                  detail={formatCommodityCandidateSummaryDetail(commodityCoverage.candidate_summary)}
                  tone="neutral"
                />
                <MetricTile
                  icon={<WarningOutlined />}
                  label="公式变更需审批"
                  value={commodityCoverage.candidate_summary.approval_required ? "是" : "否"}
                  detail={
                    commodityCoverage.candidate_summary.formula_change_required
                      ? "从旁证进入 Crisis Score 公式需要版本化审批"
                      : "当前无公式变更"
                  }
                  tone="neutral"
                />
                <MetricTile
                  icon={<ToolOutlined />}
                  label="下一步"
                  value="影子评估"
                  detail={commodityCoverage.candidate_summary.next_step || "下一步待确认"}
                  tone="neutral"
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="影子评估结果"
                  value={`${commodityCoverage.candidate_summary.shadow_evaluation_ready_count} 个可读`}
                  detail={formatCommodityShadowSummary(commodityCoverage)}
                  tone="neutral"
                />
              </div>
              <CrisisCommodityShadowImpactPanel
                currentScore={result.score}
                coverage={commodityCoverage}
                shadowImpact={commodityShadowImpact}
              />
              <CrisisCommodityShadowDecisionPanel
                admission={commodityAdmission}
                approvalPack={commodityApprovalPack}
                coverage={commodityCoverage}
                commodityInput={commodityInput ?? null}
                analysisMeta={analysisMeta}
                analysisAsOfDate={analysisAsOfDate}
              />
              <small className="macro-toolkit-crisis-coverage-note">
                {commodityCoverage.candidate_summary.next_step || "商品扩展候选下一步待确认"}
              </small>
              {commodityCoverage.candidate_summary.shadow_evaluation_next_step ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {commodityCoverage.candidate_summary.shadow_evaluation_next_step}
                </small>
              ) : null}
              {commodityCoverage.candidate_summary.shadow_evaluation_short_items.length ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {formatCommodityShadowShortfallList(commodityCoverage.candidate_summary)}
                </small>
              ) : null}
              {commodityShortRefreshHint ? (
                <div className="macro-toolkit-crisis-coverage-action">
                  <small className="macro-toolkit-crisis-coverage-note">{commodityShortRefreshHint}</small>
                  {onApplyCommodityRefreshProducts ? (
                    <Button
                      size="small"
                      icon={<ToolOutlined />}
                      aria-label="按建议选择"
                      onClick={() => onApplyCommodityRefreshProducts(commodityShortRefreshProducts)}
                    >
                      按建议选择
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}
          <div className="macro-toolkit-crisis-input-grid">
            {commodityCoverage.items.map((item) => (
              <div
                className={[
                  "macro-toolkit-crisis-input",
                  item.available ? "macro-toolkit-crisis-input--available" : "macro-toolkit-crisis-input--missing",
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={item.field}
              >
                <div className="macro-toolkit-capability-result-head">
                  <span>{item.label || item.field}</span>
                  <Tag color={item.available ? "green" : "red"}>{item.available ? "命中" : "缺失"}</Tag>
                </div>
                <strong>{formatCommodityCoverageIdentifiers(item)}</strong>
                <small>
                  {item.field} · {formatCrisisRowCount(item.row_count)} · {item.latest_date ?? "日期缺失"} ·{" "}
                  {formatCommodityCoverageDateStatus(item.date_alignment_status)}
                </small>
                <small>
                  {item.source ?? "source missing"} · {item.series_id ?? "series missing"} · matched{" "}
                  {item.matched_alias ?? "alias missing"} · {item.used_in_formula ? "纳入公式" : "未纳入公式"}
                </small>
                {item.candidate_decision ? (
                  <small>
                    {item.candidate_decision.label} · {item.candidate_decision.reason} ·{" "}
                    {item.candidate_decision.next_step}
                  </small>
                ) : null}
                {item.shadow_evaluation ? (
                  <small>
                    {item.shadow_evaluation.label} · {item.shadow_evaluation.summary} ·{" "}
                    {formatCommodityShadowDetail(item.shadow_evaluation)}
                  </small>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="macro-toolkit-crisis-input-grid">
        {inputEvidence.map((item) => (
          <div
            className={[
              "macro-toolkit-crisis-input",
              item.available ? "macro-toolkit-crisis-input--available" : "macro-toolkit-crisis-input--missing",
              item.field === "nanhua" ? "macro-toolkit-crisis-input--commodity" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={`${item.field}-${item.aliases?.join("-") ?? item.label}`}
          >
            <div className="macro-toolkit-capability-result-head">
              <span>{item.label || item.field}</span>
              <Tag color={item.available ? "green" : "red"}>{item.available ? "命中" : "缺失"}</Tag>
            </div>
            <strong>{item.aliases?.join(" / ") || item.series_id || "alias missing"}</strong>
            <small>
              {item.field} · {formatCrisisRowCount(item.row_count)} · {item.latest_date ?? "日期缺失"}
            </small>
            <small>
              {item.source ?? "source missing"} · {item.series_id ?? "series missing"} · value{" "}
              {item.value == null ? "缺失" : formatValue(item.value, "")}
            </small>
            {item.warning ? <Tag color={item.available ? "default" : "red"}>{item.warning}</Tag> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function HasonMacroStrategyPanel({
  strategy,
  variant = "detail",
}: {
  strategy: MacroToolkitHasonStrategy;
  variant?: "detail" | "observation";
}) {
  const readiness = strategy.readiness;
  const readinessText = `${readiness.ready_modules}/${readiness.total_modules}`;
  const runtimeOutputsCurrent = strategy.runtime_output_status === "current";
  const runtimeOutputGaps = strategy.runtime_output_gaps;
  const runtimeOutputValue = runtimeOutputsCurrent
    ? "current"
    : `${strategy.runtime_output_status} · ${runtimeOutputGaps.length}`;
  const runtimeOutputDetail = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : strategy.required_runtime_outputs.join(" / ");
  const runtimeGapText = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : runtimeOutputsCurrent
      ? "none"
      : "freshness not confirmed";
  const tracedScripts = strategy.source_trace;
  const tracedScriptPreview = tracedScripts.slice(0, 5);
  if (variant === "observation") {
    return (
      <section
        className="macro-toolkit-section macro-toolkit-hason-strategy macro-toolkit-hason-strategy--observation"
        data-testid="macro-toolkit-hason-strategy"
      >
        <div className="macro-toolkit-hason-strategy__head">
          <div>
            <span>Hason 观察框架</span>
            <strong>宏观对冲观察框架</strong>
            <small>只展示投研观察边界，完整模块和脚本审计留在工具页。</small>
          </div>
          <div className="macro-toolkit-tag-row">
            <Tag color={statusColor(strategy.status)}>{observationStatusLabel(strategy.status)}</Tag>
            <Tag color="gold">仅作观察</Tag>
            <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
              {strategy.formal_use_allowed ? "正式可用" : "非正式信号"}
            </Tag>
          </div>
        </div>

        <div className="macro-toolkit-hason-strategy__metrics">
          <MetricTile
            icon={<SafetyCertificateOutlined />}
            label="观察覆盖"
            value={readinessText}
            detail={`${formatPercent(readiness.ratio)} 覆盖，缺口需人工复核。`}
            tone="neutral"
            detailMaxLength={40}
          />
          <MetricTile
            icon={<ToolOutlined />}
            label="缺口复核"
            value={readiness.missing_script_count + readiness.missing_modules}
            detail={`${readiness.partial_modules} 个部分就绪，${readiness.missing_modules} 个模块待补齐。`}
            tone={readiness.missing_script_count || readiness.missing_modules ? "missing" : "neutral"}
            detailMaxLength={40}
          />
          <MetricTile
            icon={<DatabaseOutlined />}
            label="运行证据"
            value={runtimeOutputsCurrent ? "已对齐" : observationStatusLabel(strategy.runtime_output_status)}
            detail={runtimeOutputGaps.length ? `${runtimeOutputGaps.length} 项输出待复核。` : "运行输出未发现待复核项。"}
            tone={runtimeOutputsCurrent ? "neutral" : "missing"}
            detailMaxLength={40}
          />
        </div>
      </section>
    );
  }
  return (
    <section className="macro-toolkit-section macro-toolkit-hason-strategy" data-testid="macro-toolkit-hason-strategy">
      <div className="macro-toolkit-hason-strategy__head">
        <div>
          <span>Hason macro strategy</span>
          <strong>{strategy.framework_name}</strong>
          <small>{strategy.boundary}</small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
          <Tag color="blue">{strategy.basis}</Tag>
          <Tag color={strategy.observation_only ? "gold" : "green"}>
            {strategy.observation_only ? "observation-only" : "actionable"}
          </Tag>
          <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
            {strategy.formal_metric_id ?? "no formal MTR"}
          </Tag>
        </div>
      </div>

      <div className="macro-toolkit-hason-strategy__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="Readiness"
          value={readinessText}
          detail={`${formatPercent(readiness.ratio)} module coverage`}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Module gaps"
          value={`${readiness.missing_script_count} missing script`}
          detail={`${readiness.partial_modules} partial / ${readiness.missing_modules} missing module`}
          tone="neutral"
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="Runtime outputs"
          value={runtimeOutputValue}
          detail={runtimeOutputDetail}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Script trace"
          value={tracedScripts.length}
          detail={tracedScriptPreview.map(formatHasonTraceScript).join(" / ") || "no script available"}
          tone="neutral"
          testId="macro-toolkit-hason-script-trace"
        />
      </div>

      <div className="macro-toolkit-hason-module-grid">
        {strategy.modules.map((module) => (
          <div
            className="macro-toolkit-hason-module"
            data-testid={`macro-toolkit-hason-module-${module.key}`}
            key={module.key}
          >
            <div className="macro-toolkit-capability-result-head">
              <span>{module.key}</span>
              <Tag color={hasonModuleStatusColor(module.status)}>{hasonModuleStatusLabel(module.status)}</Tag>
            </div>
            <strong>{module.label}</strong>
            <small>可用脚本：{module.available_scripts.join(" / ") || "无"}</small>
            {module.missing_scripts.length ? (
              <small className="macro-toolkit-hason-module__missing">
                缺失脚本：{module.missing_scripts.join(" / ")}
              </small>
            ) : null}
            <div className="macro-toolkit-tag-row">
              {module.evidence.map((item) => (
                <Tag color="blue" key={`${module.key}-${item}`}>
                  {item}
                </Tag>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-hason-runtime" data-testid="macro-toolkit-hason-runtime-gaps">
        <span>runtime outputs · {strategy.runtime_output_status}</span>
        <strong>{runtimeGapText}</strong>
        {strategy.runtime_outputs.length ? (
          <small>
            {strategy.runtime_outputs.map(formatHasonRuntimeOutput).join(" / ")}
          </small>
        ) : null}
      </div>
    </section>
  );
}

function formatHasonRuntimeOutput(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return (
    `${item.name}: ${item.freshness_status} ${hasonFreshnessBasisLabel(item.freshness_basis)}` +
    `${hasonContentDateText(item)}` +
    `${hasonInvalidDateText(item)}` +
    `${item.modified_date ? ` file ${item.modified_date}` : ""}`
  );
}

function hasonContentDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  if (item.content_date_min && item.content_date_max && item.content_date_min !== item.content_date_max) {
    return ` content ${item.content_date_min}..${item.content_date_max}`;
  }
  return item.content_date ? ` content ${item.content_date}` : "";
}

function hasonInvalidDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return item.content_date_invalid_count > 0 ? ` ${item.content_date_invalid_count} invalid date` : "";
}

function hasonFreshnessBasisLabel(basis: string) {
  const labels: Record<string, string> = {
    csv_content: "CSV content date",
    file_modified_date: "file modified date",
    missing: "file missing",
  };
  return labels[basis] ?? basis;
}

function hasonModuleStatusLabel(status: string) {
  const labels: Record<string, string> = {
    integrated: "script-chain complete",
    partial: "script-chain partial",
    missing: "script-chain missing",
  };
  return labels[status] ?? status;
}

function hasonModuleStatusColor(status: string) {
  if (status === "integrated") return "default";
  return statusColor(status);
}

function formatHasonTraceScript(item: MacroToolkitHasonStrategy["source_trace"][number]) {
  const modules = Array.isArray(item.modules) ? item.modules : [];
  const moduleText = modules.length ? `[${modules.join("+")}]` : "";
  return `${item.script}${moduleText}${item.available ? "" : ":missing"}`;
}

function ReadinessTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: MacroToolkitSignalCard["tone"];
}) {
  const Icon = tone === "negative" || tone === "missing" ? ExclamationCircleOutlined : CheckCircleOutlined;
  return (
    <div className={`macro-toolkit-readiness-tile macro-toolkit-readiness-tile--${tone}`}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <Icon />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 28)}</small>
    </div>
  );
}

function GovernanceAuditMap({
  items,
  selectedKey,
  onSelect,
}: {
  items: MacroToolkitGovernanceFocusItem[];
  selectedKey: MacroToolkitGovernanceFocusKey;
  onSelect: (key: MacroToolkitGovernanceFocusKey) => void;
}) {
  const selectedItem = items.find((item) => item.key === selectedKey) ?? items[0]!;
  return (
    <div className="macro-toolkit-governance-audit">
      <div
        className={`macro-toolkit-governance-audit__focus macro-toolkit-governance-audit__focus--${selectedItem.tone}`}
        data-testid="macro-toolkit-governance-focus"
        aria-live="polite"
      >
        <span>审计焦点</span>
        <strong>{selectedItem.focusTitle}</strong>
        <small>{selectedItem.detail}</small>
      </div>
      <div className="macro-toolkit-governance-gate__metrics">
        {items.map((item) => (
          <a
            href={item.href}
            key={item.key}
            className={`macro-toolkit-governance-link macro-toolkit-governance-link--${item.tone}`}
            aria-current={item.key === selectedKey ? "true" : undefined}
            onClick={() => onSelect(item.key)}
          >
            <span>
              <MacroStatusIcon tone={item.tone}>{item.icon}</MacroStatusIcon>
              {item.label}
            </span>
            <strong>{item.value}</strong>
            <small title={item.detail}>{compactText(item.detail, 34)}</small>
            <Tag color={governanceStatusColor(item.status)}>{item.status}</Tag>
          </a>
        ))}
      </div>
    </div>
  );
}

function governanceStatusColor(status: string) {
  if (status === "available") return "green";
  if (status === "failed") return "red";
  if (status === "data-pending" || status === "core-not-full") return "gold";
  return "default";
}

function CommitteeWorkQueue({
  items,
  checklistItems,
  blockerCount,
  pendingCount,
  receiptCount,
  latestReceipt,
  receipts,
  confirmedReceiptIds,
  gateStatus,
  selectedEvidenceHref,
  selectedExecutionHref,
  onSelectEvidence,
  onSelectExecution,
  onConfirmReceipt,
}: {
  items: MacroToolkitCommitteeWorkQueueItem[];
  checklistItems: MacroToolkitCommitteeChecklistItem[];
  blockerCount: number;
  pendingCount: number;
  receiptCount: number;
  latestReceipt: MacroToolkitActionReceipt | null;
  receipts: MacroToolkitActionReceipt[];
  confirmedReceiptIds: Set<string>;
  gateStatus: string;
  selectedEvidenceHref: string | null;
  selectedExecutionHref: string | null;
  onSelectEvidence: (href: string, governanceFocus: MacroToolkitGovernanceFocusKey) => void;
  onSelectExecution: (href: string, governanceFocus: MacroToolkitGovernanceFocusKey) => void;
  onConfirmReceipt: (receiptId: string) => void;
}) {
  const gateTone = blockerCount > 0 ? "block" : pendingCount > 0 ? "pending" : "pass";
  const leadItem = items.find((item) => item.status === "block") ?? items[0] ?? null;
  const workQueueSla = blockerCount > 0 ? "T+0 盘前" : pendingCount > 0 ? "T+0 收盘前" : "持续留痕";
  const receiptRequirement = latestReceipt ? `${latestReceipt.evidenceEntry} 已留痕` : "完成回执 + 证据留痕";
  const signoffItems = committeeSignoffLaneItems(items, receipts, confirmedReceiptIds);
  const reviewedItemCount = items.filter((item) => latestCompletedReceiptForQueueItem(receipts, item)).length;
  const matrixItems = checklistItems.map((item) => ({
    ...item,
    executionHref: committeeWorkQueueExecutionHref(item),
  }));
  const deskStages = [
    { label: "问题定位", value: leadItem?.condition ?? "无阻断", detail: leadItem?.statusLabel ?? "待办清零" },
    { label: "责任归属", value: leadItem?.owner ?? "投委会秘书", detail: workQueueSla },
    { label: "证据动作", value: leadItem?.action ?? "保留证据留痕", detail: leadItem?.support ?? "证据簿" },
    { label: "回执复核", value: `${reviewedItemCount}/${items.length}`, detail: receiptRequirement },
    { label: "提交判断", value: gateStatus, detail: gateTone === "block" ? "阻断未解除" : gateTone === "pending" ? "等待确认" : "可进入签核" },
  ];
  return (
    <section
      className={`macro-toolkit-committee-work-queue macro-toolkit-committee-work-queue--${gateTone}`}
      data-testid="macro-toolkit-committee-work-queue"
      aria-label="投委会作业队列"
    >
      <div className="macro-toolkit-committee-work-queue__head">
        <div>
          <span>投委会作业队列</span>
          <strong>提交门禁</strong>
          <small>{gateStatus}</small>
        </div>
        <Tag color={gateTone === "block" ? "red" : gateTone === "pending" ? "gold" : "green"}>{gateStatus}</Tag>
      </div>
      <div className="macro-toolkit-committee-work-queue__metrics">
        <div>
          <span>提交前待办</span>
          <strong>{items.length} 项</strong>
        </div>
        <div>
          <span>阻断项</span>
          <strong>{blockerCount}</strong>
        </div>
        <div>
          <span>待确认项</span>
          <strong>{pendingCount}</strong>
        </div>
        <div>
          <span>已执行回执</span>
          <strong>{receiptCount}</strong>
        </div>
      </div>
      <div className="macro-toolkit-committee-work-queue__control" aria-label="投委会提交作业控制">
        <div>
          <span>提交作业控制</span>
          <strong>{gateTone === "block" ? "先解阻断" : gateTone === "pending" ? "待确认闭环" : "可提交复核"}</strong>
        </div>
        <div>
          <span>牵头责任人</span>
          <strong>{leadItem?.owner ?? "投委会秘书"}</strong>
        </div>
        <div>
          <span>SLA</span>
          <strong>{workQueueSla}</strong>
        </div>
        <div>
          <span>回执要求</span>
          <strong>{receiptRequirement}</strong>
        </div>
        <div>
          <span>优先处理</span>
          <strong>{leadItem?.condition ?? "保留证据留痕"}</strong>
        </div>
      </div>
      <div className="macro-toolkit-committee-work-queue__matrix" aria-label="投委会提交判断矩阵">
        <div className="macro-toolkit-committee-work-queue__matrix-head">
          <span>提交判断矩阵</span>
          <strong>{checklistItems.filter((item) => item.status === "pass").length}/{checklistItems.length}</strong>
        </div>
        <div className="macro-toolkit-committee-work-queue__matrix-columns" aria-hidden="true">
          <span>条件</span>
          <span>判断</span>
          <span>责任人</span>
          <span>证据</span>
          <span>动作</span>
        </div>
        {matrixItems.map((item) => {
          const evidenceFocus = governanceFocusFromEvidenceHref(item.href);
          const executionFocus = governanceFocusFromEvidenceHref(item.executionHref);
          return (
            <div
              key={item.key}
              className={`macro-toolkit-committee-work-queue__matrix-row macro-toolkit-committee-work-queue__matrix-row--${item.status}`}
            >
              <div>
                <span>{item.condition}</span>
                <strong>{item.statusLabel}</strong>
              </div>
              <strong>{item.statusLabel}</strong>
              <span>{item.owner}</span>
              <a
                href={item.href}
                aria-current={selectedEvidenceHref === item.href ? "true" : undefined}
                onClick={() => onSelectEvidence(item.href, evidenceFocus)}
              >
                {item.condition} 证据入口
              </a>
              <a
                href={item.executionHref}
                aria-current={selectedExecutionHref === item.executionHref ? "true" : undefined}
                onClick={() => onSelectExecution(item.executionHref, executionFocus)}
              >
                {item.condition} 动作入口
              </a>
            </div>
          );
        })}
      </div>
      <div className="macro-toolkit-committee-work-queue__desk" aria-label="投委会闭环作业台">
        {deskStages.map((stage) => (
          <div key={stage.label}>
            <span>{stage.label}</span>
            <strong>{stage.value}</strong>
            <small>{stage.detail}</small>
          </div>
        ))}
      </div>
      <div className="macro-toolkit-committee-work-queue__signoff" aria-label="投委会签核轨道">
        <div className="macro-toolkit-committee-work-queue__signoff-head">
          <span>签核轨道</span>
          <strong>
            {signoffItems.filter((item) => item.status === "approved" || item.status === "reviewed").length}/
            {signoffItems.length}
          </strong>
        </div>
        <div className="macro-toolkit-committee-work-queue__signoff-grid">
          {signoffItems.map((item) => (
            <div
              key={item.owner}
              className={`macro-toolkit-committee-work-queue__signoff-item macro-toolkit-committee-work-queue__signoff-item--${item.status}`}
            >
              <span>{item.owner}</span>
              <strong>{item.statusLabel}</strong>
              <small>{item.subject}</small>
            </div>
          ))}
        </div>
      </div>
      {items.length ? (
        <div className="macro-toolkit-committee-work-queue__todos" aria-label="投委会提交链路">
          <div className="macro-toolkit-committee-work-queue__todo-columns" aria-hidden="true">
            <span>问题/条件</span>
            <span>提交判断</span>
            <span>下一步动作</span>
            <span>责任人</span>
            <span>SLA</span>
            <span>回执状态</span>
            <span>签核动作</span>
          </div>
          {items.map((item) => {
            const evidenceFocus = governanceFocusFromEvidenceHref(item.href);
            const executionFocus = governanceFocusFromEvidenceHref(item.executionHref);
            const itemReceipt = latestCompletedReceiptForQueueItem(receipts, item);
            const isReceiptConfirmed = itemReceipt ? confirmedReceiptIds.has(itemReceipt.id) : false;
            const itemSla = item.status === "block" ? "T+0 盘前" : "T+0 收盘前";
            const receiptState = itemReceipt
              ? `${isReceiptConfirmed ? "签核已确认" : "回执闭环"} · ${itemReceipt.evidenceEntry}`
              : "待执行留痕";
            const signoffAction = itemReceipt
              ? isReceiptConfirmed
                ? "查看签核证据"
                : "复核签核"
              : item.status === "block"
                ? "先执行"
                : "补证据";
            return (
              <div
                key={item.key}
                aria-label={`投委会提交链路-${item.condition}`}
                className={`macro-toolkit-committee-work-queue__todo macro-toolkit-committee-work-queue__todo--${item.status}${
                  itemReceipt ? " macro-toolkit-committee-work-queue__todo--reviewed" : ""
                }`}
              >
                <a
                  className="macro-toolkit-committee-work-queue__todo-main"
                  href={item.href}
                  aria-current={selectedEvidenceHref === item.href ? "true" : undefined}
                  onClick={() => onSelectEvidence(item.href, evidenceFocus)}
                >
                  <span>{item.priorityLabel}</span>
                  <strong>{item.condition}</strong>
                  <small>{item.statusLabel}</small>
                  <em>{item.action}</em>
                  <small>{item.owner}</small>
                  <small>{itemSla}</small>
                  <small>{receiptState}</small>
                </a>
                {itemReceipt && !isReceiptConfirmed ? (
                  <button
                    type="button"
                    className="macro-toolkit-committee-work-queue__execution"
                    aria-label={`复核签核-${item.condition}`}
                    onClick={() => onConfirmReceipt(itemReceipt.id)}
                  >
                    <span>{itemReceipt.evidenceEntry}</span>
                    <strong>回执待复核</strong>
                    <small>{signoffAction}</small>
                  </button>
                ) : (
                  <a
                    className="macro-toolkit-committee-work-queue__execution"
                    href={itemReceipt?.evidenceHref ?? item.executionHref}
                    aria-current={
                      selectedExecutionHref === item.executionHref ||
                      selectedEvidenceHref === itemReceipt?.evidenceHref
                        ? "true"
                        : undefined
                    }
                    onClick={() =>
                      itemReceipt
                        ? onSelectEvidence(itemReceipt.evidenceHref, governanceFocusFromEvidenceHref(itemReceipt.evidenceHref))
                        : onSelectExecution(item.executionHref, executionFocus)
                    }
                  >
                    <span>{itemReceipt?.evidenceEntry ?? item.condition}</span>
                    <strong>{isReceiptConfirmed ? "已签核" : "执行入口"}</strong>
                    <small>{signoffAction}</small>
                  </a>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="macro-toolkit-committee-work-queue__empty">提交前待办已清零，继续保留证据留痕。</div>
      )}
      <div className="macro-toolkit-committee-work-queue__receipt">
        <span>最新回执</span>
        {latestReceipt ? (
          <>
            <strong>{latestReceipt.action}</strong>
            <a
              href={latestReceipt.evidenceHref}
              aria-current={selectedEvidenceHref === latestReceipt.evidenceHref ? "true" : undefined}
              onClick={() =>
                onSelectEvidence(latestReceipt.evidenceHref, governanceFocusFromEvidenceHref(latestReceipt.evidenceHref))
              }
            >
              {latestReceipt.evidenceEntry} · {compactText(latestReceipt.nextStep, 28)}
            </a>
          </>
        ) : (
          <>
            <strong>等待执行</strong>
            <small>执行动作后自动关联证据入口</small>
          </>
        )}
      </div>
    </section>
  );
}

function ActionReceiptPanel({ receipt }: { receipt: MacroToolkitActionReceipt }) {
  return (
    <div
      className={`macro-toolkit-action-receipt macro-toolkit-action-receipt--${receipt.status}`}
      data-testid="macro-toolkit-action-receipt"
      aria-label="宏观工具操作回执"
      aria-live="polite"
    >
      <div className="macro-toolkit-action-receipt__head">
        <span>最近回执</span>
        <strong>{receipt.action}</strong>
      </div>
      <div className="macro-toolkit-action-receipt__grid">
        <ReceiptField label="状态" value={actionReceiptStatusLabel(receipt.status)} />
        <ReceiptField label="时间" value={receipt.time} />
        <ReceiptField label="影响对象" value={receipt.target} />
        <ReceiptField label="输出产物" value={receipt.artifact} />
        <ReceiptField label="下一步" value={receipt.nextStep} />
      </div>
    </div>
  );
}

function ActionReceiptQueue({
  receipts,
  selectedEvidenceHref,
  onSelectEvidence,
}: {
  receipts: MacroToolkitActionReceipt[];
  selectedEvidenceHref: string | null;
  onSelectEvidence: (href: string) => void;
}) {
  return (
    <div
      className="macro-toolkit-action-queue"
      data-testid="macro-toolkit-action-queue"
      aria-label="宏观工具操作审计队列"
    >
      <div className="macro-toolkit-action-queue__head">
        <span>操作审计队列</span>
        <strong>{receipts.length} 条</strong>
      </div>
      {receipts.length ? (
        <>
          <div className="macro-toolkit-action-queue__columns" aria-hidden="true">
            <span>动作</span>
            <span>决策影响</span>
            <span>复核角色</span>
            <span>证据入口</span>
          </div>
          <ul className="macro-toolkit-action-queue__list">
            {receipts.map((receipt) => (
              <li
                key={receipt.id}
                className={`macro-toolkit-action-queue__item macro-toolkit-action-queue__item--${receipt.status}`}
              >
                <div>
                  <strong>{receipt.action}</strong>
                  <span>{actionReceiptStatusLabel(receipt.status)}</span>
                </div>
                <small title={`${receipt.decisionImpact} · ${receipt.target}`}>
                  {compactText(`${receipt.decisionImpact} · ${receipt.target}`, 32)}
                </small>
                <small title={receipt.reviewOwner}>{compactText(receipt.reviewOwner, 24)}</small>
                <a
                  href={receipt.evidenceHref}
                  title={`${receipt.evidenceEntry} · ${receipt.nextStep}`}
                  aria-current={receipt.evidenceHref === selectedEvidenceHref ? "true" : undefined}
                  onClick={() => onSelectEvidence(receipt.evidenceHref)}
                >
                  {compactText(`${receipt.evidenceEntry} · ${receipt.nextStep}`, 34)}
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="macro-toolkit-action-queue__empty">暂无操作记录</div>
      )}
    </div>
  );
}

function ReceiptField({ label, value }: { label: string; value: string }) {
  return (
    <div className="macro-toolkit-action-receipt__field">
      <span>{label}</span>
      <strong title={value}>{compactText(value, 40)}</strong>
    </div>
  );
}

function actionReceiptStatusLabel(status: MacroToolkitActionReceiptStatus) {
  const labels: Record<MacroToolkitActionReceiptStatus, string> = {
    idle: "等待执行",
    running: "进行中",
    completed: "已完成",
    warning: "需复核",
    failed: "失败",
  };
  return labels[status];
}

function MacroToolkitDataHealthSummary({ dataHealth }: { dataHealth: MacroToolkitDataHealth }) {
  const repairItems = dataHealth.repair_items ?? [];
  const missingIndicators = dataHealth.indicator_coverage.missing;
  const missingAliases = dataHealth.source_coverage.missing_aliases;
  const repairSummary = repairItems.length ? formatObservationRepairSummary(repairItems) : "当前无待处理数据项。";
  return (
    <section className="macro-toolkit-data-health-summary" aria-label="数据健康摘要">
      <div className="macro-toolkit-data-health-summary__head">
        <span>
          <MacroStatusIcon tone={repairItems.length || missingIndicators.length || missingAliases.length ? "missing" : "neutral"}>
            <DatabaseOutlined />
          </MacroStatusIcon>
          数据健康摘要
        </span>
        <Tag color={dataHealth.analysis_scope === "core" ? "gold" : "green"}>
          {dataHealth.analysis_scope === "core" ? "首屏口径" : "完整口径"}
        </Tag>
      </div>
      <div className="macro-toolkit-data-health-summary__grid">
        <div>
          <span>指标覆盖</span>
          <strong>
            {dataHealth.indicator_coverage.hit_count}/{dataHealth.indicator_coverage.total_count}
          </strong>
          <small>{formatMissingIndicatorDetail(missingIndicators)}</small>
        </div>
        <div>
          <span>来源覆盖</span>
          <strong>{coverageValue(dataHealth.source_coverage)}</strong>
          <small>{dataHealth.source_coverage.deferred ? "来源检查延后确认" : missingAliases.length ? "有来源待补齐" : "来源全部命中"}</small>
        </div>
        <div>
          <span>观察复核提示</span>
          <strong>{repairItems.length ? `${repairItems.length} 项` : "无"}</strong>
          <small>{repairSummary}</small>
        </div>
      </div>
    </section>
  );
}

function ObservationEvidenceTraceSummary({
  dataHealth,
  capabilityResults,
  degradedResultCount,
  hasonStrategy,
  isCoreAnalysis,
}: {
  dataHealth?: MacroToolkitDataHealth;
  capabilityResults: MacroToolkitCapabilityResult[];
  degradedResultCount: number;
  hasonStrategy?: MacroToolkitHasonStrategy;
  isCoreAnalysis: boolean;
}) {
  const repairItems = dataHealth?.repair_items ?? [];
  const missingIndicatorLabels =
    dataHealth?.indicator_coverage.missing.map((item) => item.label ?? item.alias ?? item.key).filter(Boolean) ?? [];
  const missingIndicatorDetail = dataHealth
    ? missingIndicatorLabels.length
      ? `缺口 ${formatCompactObservationList(missingIndicatorLabels)}。`
      : "指标全部命中。"
    : "完整分析后确认数据健康。";
  const sourceCoverageDetail = dataHealth
    ? dataHealth.source_coverage.deferred
      ? "完整分析补充项待确认。"
      : dataHealth.source_coverage.missing_aliases.length
        ? `来源待补齐 ${formatCompactObservationList(dataHealth.source_coverage.missing_aliases)}。`
        : "来源全部命中。"
    : "来源完整分析后确认。";
  const repairDetail = repairItems.length
    ? `${repairItems.length} 项复核提示：${formatCompactObservationList(repairItems.map(formatObservationRepairTraceItem))}；${formatObservationRepairSummary(repairItems)}`
    : "当前无复核提示。";
  const indicatorCoverage = dataHealth
    ? `${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`
    : "待确认";
  const capabilityValue = capabilityResults.length
    ? `${capabilityResults.length} 项证据`
    : "延后确认";
  const capabilityDetail = degradedResultCount
    ? `${degradedResultCount} 项证据需复核；不是正式投资信号。`
    : capabilityResults.length
      ? "能力证据仅解释覆盖情况，不是正式投资信号。"
      : "不按 0 处理。";
  const hasonValue = hasonStrategy ? observationStatusLabel(hasonStrategy.status) : "待确认";
  const hasonDetail = hasonStrategy
    ? `${hasonStrategy.readiness.ready_modules}/${hasonStrategy.readiness.total_modules} 覆盖，${hasonStrategy.readiness.missing_modules} 个模块待复核。`
    : "观察框架完整分析后确认。";
  return (
    <section className="macro-toolkit-observation-trace-summary" aria-label="证据追踪摘要">
      <div className="macro-toolkit-observation-trace-summary__head">
        <div>
          <span>证据追踪摘要</span>
          <strong>{isCoreAnalysis ? "首屏证据已压缩展示" : "完整证据已压缩展示"}</strong>
        </div>
        <Tag color={isCoreAnalysis ? "gold" : "green"}>{isCoreAnalysis ? "延后确认" : "完整分析"}</Tag>
      </div>
      <div className="macro-toolkit-observation-trace-summary__grid">
        <div>
          <span>数据健康</span>
          <strong>指标覆盖 {indicatorCoverage}</strong>
          <small>{missingIndicatorDetail}</small>
          <small>{sourceCoverageDetail}</small>
          <small>{repairDetail}</small>
        </div>
        <div>
          <span>能力证据</span>
          <strong>{capabilityValue}</strong>
          <small>{capabilityDetail}</small>
        </div>
        <div>
          <span>观察框架</span>
          <strong>{hasonValue}</strong>
          <small>{hasonDetail}</small>
        </div>
      </div>
    </section>
  );
}

function MacroToolkitDataHealthPanel({
  dataHealth,
  showActions = false,
  plainLanguage = false,
  onRepairAction,
  repairActionLoading = false,
  refreshingSourceAlias = null,
  focusedRepairKey = null,
  dataHealthReceipt = null,
  dataHealthReceiptConfirmed = false,
}: {
  dataHealth: MacroToolkitDataHealth;
  showActions?: boolean;
  plainLanguage?: boolean;
  onRepairAction?: (item: MacroToolkitRepairItem) => void;
  repairActionLoading?: boolean;
  refreshingSourceAlias?: string | null;
  focusedRepairKey?: string | null;
  dataHealthReceipt?: MacroToolkitActionReceipt | null;
  dataHealthReceiptConfirmed?: boolean;
}) {
  const missingAliases = dataHealth.source_coverage.missing_aliases;
  const missingIndicators = dataHealth.indicator_coverage.missing;
  const repairItems = dataHealth.repair_items ?? [];
  const visibleRepairItems = repairItems.slice(0, 6);
  const hiddenRepairItemCount = repairItems.length - visibleRepairItems.length;
  const focusedRepairItem = focusedRepairKey
    ? (repairItems.find((item) => repairItemFocusKey(item) === focusedRepairKey) ?? null)
    : null;
  const observationRepairSummary = plainLanguage ? formatObservationRepairSummary(repairItems) : null;
  const deferredText = dataHealth.deferred_sections.length
    ? `延后加载：${dataHealth.deferred_sections.map(formatObservationDeferredSectionLabel).join(" / ")}`
    : "完整结果已加载";
  return (
    <section className="macro-toolkit-data-health" aria-label="数据健康总览">
      <div className="macro-toolkit-data-health__head">
        <span>
          <MacroStatusIcon tone={dataHealth.warnings.length ? "missing" : "neutral"}>
            <DatabaseOutlined />
          </MacroStatusIcon>
          数据健康总览
        </span>
        <Tag color={dataHealth.analysis_scope === "core" ? "gold" : "green"}>
          {dataHealth.analysis_scope === "core" ? "core 首屏" : "full 完整"}
        </Tag>
      </div>
      <div className="macro-toolkit-data-health__grid">
        <HealthMetricTile
          label="指标覆盖"
          value={`${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`}
          detail={formatMissingIndicatorDetail(missingIndicators)}
          tone={dataHealth.indicator_coverage.missing_count > 0 ? "neutral" : "positive"}
        />
        <HealthMetricTile
          label="来源覆盖"
          value={coverageValue(dataHealth.source_coverage)}
          detail={
            dataHealth.source_coverage.deferred
              ? "来源检查延后加载"
              : missingAliases.length
                ? `缺失 ${missingAliases.join(" / ")}`
                : "来源全部命中"
          }
          tone={dataHealth.source_coverage.deferred ? "neutral" : missingAliases.length ? "missing" : "positive"}
        />
        <HealthMetricTile
          label="最新来源日期"
          value={dataHealth.source_coverage.latest_date ?? "延后加载"}
          detail={deferredText}
          tone={dataHealth.source_coverage.latest_date ? "positive" : "neutral"}
        />
        <HealthMetricTile
          label="能力降级"
          value={capabilityIssueCount(dataHealth)}
          detail={capabilityHealthDetail(dataHealth)}
          tone={capabilityIssueCount(dataHealth) > 0 ? "neutral" : "positive"}
        />
      </div>
      {(missingIndicators.length || missingAliases.length || dataHealth.warnings.length) ? (
        <div className="macro-toolkit-data-health__notes">
          {missingIndicators.map((item) => (
            <Tag color="gold" key={item.alias ?? item.key ?? item.label}>
              {item.alias ?? item.key ?? item.label} 缺失
            </Tag>
          ))}
          {missingAliases.map((alias) => (
            <Tag color="red" key={alias}>
              {alias} 来源未命中
            </Tag>
          ))}
          {dataHealth.warnings.map((warning) => (
            <Tag color="red" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      ) : null}
      {repairItems.length ? (
        <div className="macro-toolkit-data-health__repairs" aria-label="待处理数据项">
          <div className="macro-toolkit-data-health__repairs-head">
            <span>待处理数据项</span>
            <Tag color={repairItems.some((item) => item.priority === "high") ? "red" : "gold"}>
              {repairItems.length} 项
            </Tag>
          </div>
          {observationRepairSummary ? (
            <div className="macro-toolkit-data-health__repair-summary">
              <span>观察复核提示</span>
              <strong>{observationRepairSummary}</strong>
            </div>
          ) : null}
          {focusedRepairItem ? (
            <MacroToolkitRepairTicket
              item={focusedRepairItem}
              receipt={dataHealthReceipt}
              receiptConfirmed={dataHealthReceiptConfirmed}
            />
          ) : null}
          <div className="macro-toolkit-data-health__repair-list">
            {visibleRepairItems.map((item) => {
              const itemFocusKey = repairItemFocusKey(item);
              const isFocusedRepair = focusedRepairKey === itemFocusKey;
              return (
                <div
                  className={`macro-toolkit-data-health__repair macro-toolkit-data-health__repair--${item.priority ?? "medium"}${
                    isFocusedRepair ? " macro-toolkit-data-health__repair--focused" : ""
                  }`}
                  key={item.key ?? `${item.type}-${item.label}-${item.suggested_action}`}
                  aria-label={`${isFocusedRepair ? "当前处理数据项" : "待处理数据项"}-${itemFocusKey}`}
                  aria-current={isFocusedRepair ? "true" : undefined}
                >
                <div className="macro-toolkit-data-health__repair-main">
                  <span>
                    <Tag color={repairPriorityColor(item.priority)}>{repairPriorityLabel(item.priority)}</Tag>
                    <Tag color={statusColor(item.type ?? "")}>{repairTypeLabel(item.type)}</Tag>
                    {formatDataHealthRepairLabel(item, plainLanguage)}
                  </span>
                  <small title={formatDataHealthRepairAction(item, plainLanguage)}>
                    {compactText(formatDataHealthRepairAction(item, plainLanguage), 78)}
                  </small>
                  {!plainLanguage && item.action?.reason ? (
                    <small title={item.action.reason}>
                      {item.action.label ? `${item.action.label}：` : ""}
                      {compactText(item.action.reason, 56)}
                    </small>
                  ) : null}
                </div>
                <div className="macro-toolkit-data-health__repair-meta">
                  {item.alias ? <Tag color="default">{item.alias}</Tag> : null}
                  {item.latest_date ? <Tag color="blue">最新 {item.latest_date}</Tag> : null}
                  {item.stale_days ? <Tag color="gold">落后 {item.stale_days} 天</Tag> : null}
                  {item.source_table ? <Tag color="default">{item.source_table}</Tag> : null}
                </div>
                {!plainLanguage && item.action ? (
                  <div className="macro-toolkit-data-health__repair-action">
                    {showActions && item.action.enabled && item.action.kind === "load_full_analysis" ? (
                      <Button
                        size="small"
                        icon={<LineChartOutlined />}
                        loading={repairActionLoading}
                        aria-label={item.action.label ?? "查看完整分析"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "查看完整分析"}
                      </Button>
                    ) : showActions && item.action.enabled && canRefreshMacroSourceBackfill(item) ? (
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={refreshingSourceAlias === normalizeMacroSourceBackfillAlias(item.alias)}
                        aria-label={item.action.label ?? "需要补齐来源数据"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "需要补齐来源数据"}
                      </Button>
                    ) : (
                      <small title={item.action.reason ?? ""}>
                        {item.action.label ?? "待处理"} · {item.action.reason ?? "需要人工确认"}
                      </small>
                    )}
                  </div>
                ) : null}
                </div>
              );
            })}
          </div>
          {hiddenRepairItemCount > 0 ? (
            <small className="macro-toolkit-data-health__repair-overflow">
              还有 {hiddenRepairItemCount} 项未显示；请查看完整分析或后端明细确认。
            </small>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function MacroToolkitRepairTicket({
  item,
  receipt = null,
  receiptConfirmed = false,
}: {
  item: MacroToolkitRepairItem;
  receipt?: MacroToolkitActionReceipt | null;
  receiptConfirmed?: boolean;
}) {
  const itemFocusKey = repairItemFocusKey(item);
  const ticketAction = (item.action?.label ?? formatDataHealthRepairAction(item, false));
  const nextStep = ticketAction || "复核数据缺口";
  const receiptStatus = repairTicketReceiptStatus(receipt, receiptConfirmed);
  return (
    <div className="macro-toolkit-data-health__repair-ticket" aria-label={`当前处理单-${itemFocusKey}`}>
      <div className="macro-toolkit-data-health__repair-ticket-head">
        <span>当前处理单</span>
        <strong>{formatDataHealthRepairLabel(item, false)}</strong>
      </div>
      <div className="macro-toolkit-data-health__repair-ticket-grid">
        <div>
          <span>责任人</span>
          <strong>{repairTicketOwner(item)}</strong>
        </div>
        <div>
          <span>SLA</span>
          <strong>{repairTicketSla(item)}</strong>
        </div>
        <div>
          <span>预期回执</span>
          <strong>{repairTicketReceipt(item)}</strong>
        </div>
        <div>
          <span>提交影响</span>
          <strong>{repairTicketSubmissionImpact(item)}</strong>
        </div>
        <div>
          <span>回执状态</span>
          <strong>{receiptStatus}</strong>
        </div>
        <div>
          <span>回执证据</span>
          <strong>{receipt?.evidenceEntry ?? "等待执行"}</strong>
        </div>
      </div>
      {receipt && receiptConfirmed ? (
        <a className="macro-toolkit-data-health__repair-ticket-evidence" href={receipt.evidenceHref}>
          查看签核证据
        </a>
      ) : null}
      <small title={formatDataHealthRepairAction(item, false)}>{compactText(nextStep, 88)}</small>
    </div>
  );
}

function HealthMetricTile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string | number;
  detail: string;
  tone: MacroToolkitSignalCard["tone"];
}) {
  return (
    <div className={`macro-toolkit-data-health__tile macro-toolkit-data-health__tile--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 32)}</small>
    </div>
  );
}

function coverageValue(coverage: MacroToolkitDataHealth["source_coverage"]) {
  return coverage.deferred ? "延后加载" : `${coverage.hit_count}/${coverage.total_count}`;
}

function formatMissingIndicatorDetail(items: MacroToolkitDataHealth["indicator_coverage"]["missing"]) {
  return items.length
    ? `缺失 ${items.map((item) => item.alias ?? item.key ?? item.label).filter(Boolean).join(" / ")}`
    : "指标全部命中";
}

function formatCompactObservationList(items: Array<string | null | undefined>, limit = 4) {
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

function capabilityIssueCount(dataHealth: MacroToolkitDataHealth) {
  return dataHealth.capability_results.degraded + dataHealth.capability_results.unavailable;
}

function capabilityHealthDetail(dataHealth: MacroToolkitDataHealth) {
  if (dataHealth.capability_results.deferred) {
    return "能力结果延后加载，未按 0 处理";
  }
  return `${dataHealth.capability_results.complete} 完整 / ${dataHealth.capability_results.degraded} 降级 / ${dataHealth.capability_results.unavailable} 不可用`;
}

function formatObservationDeferredSectionLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    capability_results: "能力结果",
    capabilities: "能力边界",
    source_checks: "来源证据",
    strategy_summaries: "策略证据",
    a_share_risk: "风险证据",
  };
  return labels[value ?? ""] ?? (value || "证据链确认");
}

function formatDataHealthRepairLabel(item: MacroToolkitRepairItem, plainLanguage: boolean) {
  if (item.type === "deferred") {
    return formatObservationDeferredSectionLabel(item.label ?? item.key);
  }
  if (!plainLanguage) {
    return item.label ?? item.alias ?? item.key ?? "未命名数据项";
  }
  return item.label ?? item.alias ?? item.key ?? "未命名数据项";
}

function formatDataHealthRepairAction(item: MacroToolkitRepairItem, plainLanguage: boolean) {
  const action = item.suggested_action ?? "";
  return item.type === "deferred" || plainLanguage
    ? "打开完整分析后确认这部分证据，不把首屏延后加载当作缺失。"
    : action;
}

function repairTicketOwner(item: MacroToolkitRepairItem) {
  if (item.action?.kind === "load_full_analysis" || item.type === "deferred" || item.type === "degraded") {
    return "宏观策略负责人";
  }
  return "数据运营负责人";
}

function repairTicketSla(item: MacroToolkitRepairItem) {
  if (item.priority === "high" || canRefreshMacroSourceBackfill(item)) {
    return "T+0 盘前";
  }
  if (item.type === "deferred" || item.action?.kind === "load_full_analysis") {
    return "完整分析前";
  }
  return "T+1 盘前";
}

function repairTicketReceipt(item: MacroToolkitRepairItem) {
  if (canRefreshMacroSourceBackfill(item)) {
    return "来源补齐回执";
  }
  if (item.action?.kind === "load_full_analysis") {
    return "完整分析回执";
  }
  return "人工复核记录";
}

function repairTicketSubmissionImpact(item: MacroToolkitRepairItem) {
  if (item.priority === "high" || item.type === "missing") {
    return "暂缓提交";
  }
  if (item.type === "deferred") {
    return "等待完整分析";
  }
  return "待复核后提交";
}

function repairTicketReceiptStatus(receipt: MacroToolkitActionReceipt | null, receiptConfirmed: boolean) {
  if (!receipt) {
    return "待执行留痕";
  }
  return receiptConfirmed ? "签核已确认" : "回执待复核";
}

function formatObservationRepairTraceItem(item: MacroToolkitRepairItem) {
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

function formatObservationRepairSummary(items: MacroToolkitRepairItem[]) {
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

function observationStatusLabel(status: string | null | undefined) {
  if (status === "observation_ready" || status === "degraded" || status === "partial") return "观察就绪";
  return statusLabel(status ?? "unknown");
}

function repairPriorityColor(priority: string | null | undefined) {
  if (priority === "high") return "red";
  if (priority === "low") return "blue";
  return "gold";
}

function repairPriorityLabel(priority: string | null | undefined) {
  if (priority === "high") return "高";
  if (priority === "low") return "低";
  return "中";
}

function committeePriorityLabel(priority: string | null | undefined) {
  if (priority === "high") return "高优先级";
  if (priority === "low") return "低优先级";
  return "中优先级";
}

function repairPriorityRank(priority: string | null | undefined) {
  if (priority === "high") return 0;
  if (priority === "medium") return 1;
  if (priority === "low") return 2;
  return 3;
}

function compareRepairPriority(left: MacroToolkitRepairItem, right: MacroToolkitRepairItem) {
  return repairPriorityRank(left.priority) - repairPriorityRank(right.priority);
}

function formatCommitteeReadinessBlocker(item: MacroToolkitRepairItem | null, totalCount: number) {
  if (!item) {
    return totalCount ? `共 ${totalCount} 项数据缺口` : "无关键卡点";
  }
  const label = formatDataHealthRepairLabel(item, true);
  const alias = item.alias && item.alias !== label ? ` / ${item.alias}` : "";
  return `${committeePriorityLabel(item.priority)} · ${label}${alias} · 共 ${totalCount} 项`;
}

function repairTypeLabel(type: string | null | undefined) {
  const labels: Record<string, string> = {
    missing: "缺失",
    stale: "滞后",
    degraded: "降级",
    deferred: "完整分析后确认",
  };
  return labels[type ?? ""] ?? (type || "待确认");
}

function IndicatorValueCell({ item }: { item: MacroToolkitIndicator }) {
  return (
    <div className="macro-toolkit-number-cell">
      <strong>{formatValue(item.latest_value, item.unit)}</strong>
      <small>{item.row_count.toLocaleString()} rows</small>
    </div>
  );
}

function DeltaCell({ change, changePct }: { change: number | null; changePct: number | null }) {
  const direction = changePct ?? change;
  const hasDirection = direction !== null;
  const isPositive = hasDirection && direction > 0;
  const isNegative = hasDirection && direction < 0;

  return (
    <div
      className={[
        "macro-toolkit-delta-cell",
        isPositive ? "macro-toolkit-delta-cell--up" : "",
        isNegative ? "macro-toolkit-delta-cell--down" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isPositive ? <ArrowUpOutlined /> : null}
      {isNegative ? <ArrowDownOutlined /> : null}
      <span>{formatChange(change, changePct)}</span>
    </div>
  );
}

function CapabilityDataCell({
  status,
  item,
}: {
  status: string;
  item: MacroToolkitCapability;
}) {
  const ratio = item.data_required_count > 0 ? item.data_hit_count / item.data_required_count : 1;
  return (
    <div className="macro-toolkit-capability-data-cell">
      <div>
        <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
        <span>
          {item.data_hit_count}/{item.data_required_count}
        </span>
      </div>
      <ScoreTrack score={ratio * 100} />
    </div>
  );
}

function normalizeInputEvidence(result: MacroToolkitCapabilityResult) {
  const raw = result.input_evidence ?? result.result.input_evidence;
  if (!raw) {
    return null;
  }
  const inputs = raw.inputs ?? [];
  const missingInputs = raw.missing_inputs ?? [];
  const sources = raw.sources ?? [];
  const latestDates = raw.latest_dates ?? [];
  if (!inputs.length && !missingInputs.length && !sources.length && !latestDates.length) {
    return null;
  }
  return { inputs, missingInputs, sources, latestDates };
}

type CrisisComponent = {
  key: string;
  label: string;
  raw_value: number | null;
  z_score: number | null;
  weight: number | null;
};

type CrisisCommodityCoverageItem = {
  field: string;
  label: string;
  aliases: string[];
  matched_alias: string | null;
  role: string;
  used_in_formula: boolean;
  available: boolean;
  row_count: number | null;
  latest_date: string | null;
  report_date: string | null;
  date_alignment_status: string | null;
  series_id: string | null;
  source: string | null;
  value: number | null;
  candidate_decision: CrisisCommodityCandidateDecision | null;
  shadow_evaluation: CrisisCommodityShadowEvaluation | null;
};

type CrisisCommodityCandidateDecision = {
  status: string;
  label: string;
  reason: string;
  next_step: string;
};

type CrisisCommodityCandidateSummary = {
  shadow_review_ready_count: number;
  needs_current_data_count: number;
  missing_data_count: number;
  shadow_evaluation_ready_count: number;
  shadow_evaluation_short_count: number;
  shadow_evaluation_status_counts: Record<string, number>;
  shadow_evaluation_short_items: CrisisCommodityShadowShortItem[];
  suggested_refresh_products: string[];
  shadow_evaluation_next_step: string;
  formula_change_required: boolean;
  approval_required: boolean;
  next_step: string;
};

type CrisisCommodityShadowShortItem = {
  field: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  latest_date: string | null;
};

type CrisisCommodityShadowEvaluation = {
  status: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  window_start: string | null;
  window_end: string | null;
  target: string;
  candidate_metric: string;
  same_day_correlation: number | null;
  lead_1d_correlation: number | null;
  lag_1d_correlation: number | null;
  crisis_hit_rate: number | null;
  crisis_sample_count: number | null;
  summary: string;
  next_step: string;
};

type CrisisCommodityCoverage = {
  role: string;
  tracked_count: number;
  available_count: number;
  used_in_crisis_score: string[];
  candidate_summary: CrisisCommodityCandidateSummary | null;
  items: CrisisCommodityCoverageItem[];
};

type CrisisCommodityShadowContribution = {
  field: string;
  label: string;
  series_id: string | null;
  source: string | null;
  latest_date: string | null;
  sample_count: number | null;
  candidate_metric: string;
  candidate_value: number | null;
  weight: number | null;
  contribution: number | null;
  used_in_official_score: boolean;
  status: string;
};

type CrisisCommodityShadowImpact = {
  formula_version: string;
  scope: string;
  current_score: number | null;
  shadow_score: number | null;
  delta: number | null;
  direction: string;
  included_candidates: string[];
  candidate_count: number;
  candidate_contributions: CrisisCommodityShadowContribution[];
  weights: Record<string, number>;
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
  next_step: string;
};

type CrisisCommodityAdmissionDecision = "recommend_include" | "watch" | "do_not_include";

type CrisisCommodityAdmissionItem = {
  field: string;
  label: string;
  decision: CrisisCommodityAdmissionDecision;
  decision_label: string;
  reason: string;
  next_step: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  crisis_sample_count: number | null;
  minimum_crisis_sample_count: number | null;
  crisis_hit_rate: number | null;
  max_abs_correlation: number | null;
  correlation_threshold: number | null;
  latest_date: string | null;
  series_id: string | null;
  source: string | null;
  used_in_official_score: boolean;
};

type CrisisCommodityAdmission = {
  rule_version: string;
  scope: string;
  decision_counts: Record<CrisisCommodityAdmissionDecision, number>;
  items: CrisisCommodityAdmissionItem[];
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
  next_step: string;
};

type CrisisCommodityApprovalPack = {
  pack_version: string;
  scope: string;
  source_rule_version: string;
  shadow_formula_version: string;
  decision_counts: Record<CrisisCommodityAdmissionDecision, number>;
  recommended_fields: string[];
  watch_fields: string[];
  rejected_fields: string[];
  summary: string;
  copy_text: string;
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
};

type MacroToolkitInputEvidenceItem = NonNullable<MacroToolkitInputEvidence["inputs"]>[number];
type CrisisGapGroupKey = "equity" | "liquidity" | "commodity" | "curve_credit" | "fx" | "other";
type CrisisGapItem = {
  label: string;
  warning: string;
  detail: string;
  identifiers: string[];
};
type CrisisGapGroup = {
  key: CrisisGapGroupKey;
  label: string;
  items: CrisisGapItem[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCrisisComponent(value: unknown): value is CrisisComponent {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.key === "string" && typeof value.label === "string";
}

function normalizeCommodityCoverage(value: unknown): CrisisCommodityCoverage | null {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return null;
  }
  const items = value.items.map(normalizeCommodityCoverageItem).filter((item) => item !== null);
  if (!items.length) {
    return null;
  }
  return {
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    tracked_count: typeof value.tracked_count === "number" ? value.tracked_count : items.length,
    available_count:
      typeof value.available_count === "number" ? value.available_count : items.filter((item) => item.available).length,
    used_in_crisis_score: Array.isArray(value.used_in_crisis_score)
      ? value.used_in_crisis_score.map((item) => String(item)).filter(Boolean)
      : [],
    candidate_summary: normalizeCommodityCandidateSummary(value.candidate_summary),
    items,
  };
}

function normalizeCommodityCandidateSummary(value: unknown): CrisisCommodityCandidateSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    shadow_review_ready_count:
      typeof value.shadow_review_ready_count === "number" ? value.shadow_review_ready_count : 0,
    needs_current_data_count:
      typeof value.needs_current_data_count === "number" ? value.needs_current_data_count : 0,
    missing_data_count: typeof value.missing_data_count === "number" ? value.missing_data_count : 0,
    shadow_evaluation_ready_count:
      typeof value.shadow_evaluation_ready_count === "number" ? value.shadow_evaluation_ready_count : 0,
    shadow_evaluation_short_count:
      typeof value.shadow_evaluation_short_count === "number" ? value.shadow_evaluation_short_count : 0,
    shadow_evaluation_status_counts: normalizeNumberRecord(value.shadow_evaluation_status_counts),
    shadow_evaluation_short_items: Array.isArray(value.shadow_evaluation_short_items)
      ? value.shadow_evaluation_short_items.map(normalizeCommodityShadowShortItem).filter((item) => item !== null)
      : [],
    suggested_refresh_products: Array.isArray(value.suggested_refresh_products)
      ? value.suggested_refresh_products.map((item) => String(item).trim()).filter(Boolean)
      : [],
    shadow_evaluation_next_step:
      typeof value.shadow_evaluation_next_step === "string" ? value.shadow_evaluation_next_step : "",
    formula_change_required: value.formula_change_required === true,
    approval_required: value.approval_required === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "",
  };
}

function normalizeCommodityShadowShortItem(value: unknown): CrisisCommodityShadowShortItem | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
  };
}

function normalizeNumberRecord(value: unknown) {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number")
      .map(([key, count]) => [key, count]),
  );
}

function normalizeCommodityCoverageItem(value: unknown): CrisisCommodityCoverageItem | null {
  if (!isRecord(value) || typeof value.field !== "string" || typeof value.label !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: value.label,
    aliases: Array.isArray(value.aliases) ? value.aliases.map((item) => String(item)).filter(Boolean) : [],
    matched_alias: typeof value.matched_alias === "string" ? value.matched_alias : null,
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    used_in_formula: value.used_in_formula === true,
    available: value.available === true,
    row_count: typeof value.row_count === "number" ? value.row_count : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    report_date: typeof value.report_date === "string" ? value.report_date : null,
    date_alignment_status: typeof value.date_alignment_status === "string" ? value.date_alignment_status : null,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    value: typeof value.value === "number" ? value.value : null,
    candidate_decision: normalizeCommodityCandidateDecision(value.candidate_decision),
    shadow_evaluation: normalizeCommodityShadowEvaluation(value.shadow_evaluation),
  };
}

function normalizeCommodityCandidateDecision(value: unknown): CrisisCommodityCandidateDecision | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "候选状态待确认",
    reason: typeof value.reason === "string" ? value.reason : "候选原因待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function normalizeCommodityShadowEvaluation(value: unknown): CrisisCommodityShadowEvaluation | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "影子评估待确认",
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    window_start: typeof value.window_start === "string" ? value.window_start : null,
    window_end: typeof value.window_end === "string" ? value.window_end : null,
    target: typeof value.target === "string" ? value.target : "crisis_score",
    candidate_metric: typeof value.candidate_metric === "string" ? value.candidate_metric : "daily_return",
    same_day_correlation: typeof value.same_day_correlation === "number" ? value.same_day_correlation : null,
    lead_1d_correlation: typeof value.lead_1d_correlation === "number" ? value.lead_1d_correlation : null,
    lag_1d_correlation: typeof value.lag_1d_correlation === "number" ? value.lag_1d_correlation : null,
    crisis_hit_rate: typeof value.crisis_hit_rate === "number" ? value.crisis_hit_rate : null,
    crisis_sample_count: typeof value.crisis_sample_count === "number" ? value.crisis_sample_count : null,
    summary: typeof value.summary === "string" ? value.summary : "影子评估摘要待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function normalizeCommodityShadowImpact(value: unknown): CrisisCommodityShadowImpact | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    formula_version: typeof value.formula_version === "string" ? value.formula_version : "formula missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    current_score: typeof value.current_score === "number" ? value.current_score : null,
    shadow_score: typeof value.shadow_score === "number" ? value.shadow_score : null,
    delta: typeof value.delta === "number" ? value.delta : null,
    direction: typeof value.direction === "string" ? value.direction : "unknown",
    included_candidates: Array.isArray(value.included_candidates)
      ? value.included_candidates.map((item) => String(item)).filter(Boolean)
      : [],
    candidate_count: typeof value.candidate_count === "number" ? value.candidate_count : 0,
    candidate_contributions: Array.isArray(value.candidate_contributions)
      ? value.candidate_contributions.map(normalizeCommodityShadowContribution).filter((item) => item !== null)
      : [],
    weights: normalizeNumberRecord(value.weights),
    warnings: Array.isArray(value.warnings) ? value.warnings.map((item) => String(item)).filter(Boolean) : [],
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function normalizeCommodityShadowContribution(value: unknown): CrisisCommodityShadowContribution | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    candidate_metric: typeof value.candidate_metric === "string" ? value.candidate_metric : "metric missing",
    candidate_value: typeof value.candidate_value === "number" ? value.candidate_value : null,
    weight: typeof value.weight === "number" ? value.weight : null,
    contribution: typeof value.contribution === "number" ? value.contribution : null,
    used_in_official_score: value.used_in_official_score === true,
    status: typeof value.status === "string" ? value.status : "status missing",
  };
}

function normalizeCommodityAdmission(value: unknown): CrisisCommodityAdmission | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    rule_version: typeof value.rule_version === "string" ? value.rule_version : "rule missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    decision_counts: normalizeCommodityAdmissionDecisionCounts(value.decision_counts),
    items: Array.isArray(value.items)
      ? value.items.map(normalizeCommodityAdmissionItem).filter((item) => item !== null)
      : [],
    warnings: Array.isArray(value.warnings) ? value.warnings.map((item) => String(item)).filter(Boolean) : [],
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

function normalizeCommodityAdmissionDecisionCounts(value: unknown): Record<CrisisCommodityAdmissionDecision, number> {
  const record = isRecord(value) ? value : {};
  return {
    recommend_include: typeof record.recommend_include === "number" ? record.recommend_include : 0,
    watch: typeof record.watch === "number" ? record.watch : 0,
    do_not_include: typeof record.do_not_include === "number" ? record.do_not_include : 0,
  };
}

function normalizeCommodityAdmissionItem(value: unknown): CrisisCommodityAdmissionItem | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    decision: normalizeCommodityAdmissionDecision(value.decision),
    decision_label: typeof value.decision_label === "string" ? value.decision_label : "准入结论待确认",
    reason: typeof value.reason === "string" ? value.reason : "准入原因待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    crisis_sample_count: typeof value.crisis_sample_count === "number" ? value.crisis_sample_count : null,
    minimum_crisis_sample_count:
      typeof value.minimum_crisis_sample_count === "number" ? value.minimum_crisis_sample_count : null,
    crisis_hit_rate: typeof value.crisis_hit_rate === "number" ? value.crisis_hit_rate : null,
    max_abs_correlation: typeof value.max_abs_correlation === "number" ? value.max_abs_correlation : null,
    correlation_threshold: typeof value.correlation_threshold === "number" ? value.correlation_threshold : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    used_in_official_score: value.used_in_official_score === true,
  };
}

function normalizeCommodityAdmissionDecision(value: unknown): CrisisCommodityAdmissionDecision {
  if (value === "recommend_include" || value === "watch" || value === "do_not_include") {
    return value;
  }
  return "do_not_include";
}

function normalizeCommodityApprovalPack(value: unknown): CrisisCommodityApprovalPack | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    pack_version: typeof value.pack_version === "string" ? value.pack_version : "pack missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    source_rule_version:
      typeof value.source_rule_version === "string" ? value.source_rule_version : "source rule missing",
    shadow_formula_version:
      typeof value.shadow_formula_version === "string" ? value.shadow_formula_version : "shadow formula missing",
    decision_counts: normalizeCommodityAdmissionDecisionCounts(value.decision_counts),
    recommended_fields: normalizeStringList(value.recommended_fields),
    watch_fields: normalizeStringList(value.watch_fields),
    rejected_fields: normalizeStringList(value.rejected_fields),
    summary: typeof value.summary === "string" ? value.summary : "审批材料摘要待确认",
    copy_text: typeof value.copy_text === "string" ? value.copy_text : "",
    warnings: normalizeStringList(value.warnings),
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
  };
}

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function toDisplayNumber(value: unknown) {
  return typeof value === "number" || typeof value === "string" ? value : "缺失";
}

function formatCrisisWeight(key: string, weights: Record<string, unknown>) {
  const weight = weights[key];
  return typeof weight === "number" ? formatPercent(weight) : "缺失";
}

function formatCrisisRowCount(rowCount: number | null | undefined) {
  return typeof rowCount === "number" ? `${rowCount} rows` : "行数缺失";
}

function formatCommodityCoverageDateStatus(status: string | null | undefined) {
  if (status === "aligned") {
    return "同日";
  }
  if (status === "lagging") {
    return "滞后";
  }
  if (status === "missing") {
    return "日期缺失";
  }
  return "对齐状态缺失";
}

function formatCommodityCandidateSummaryDetail(summary: CrisisCommodityCandidateSummary) {
  return `影子评估就绪 ${summary.shadow_review_ready_count}，待补当日 ${summary.needs_current_data_count}，缺失 ${summary.missing_data_count}`;
}

function formatCommodityShadowSummary(coverage: CrisisCommodityCoverage) {
  const firstReady = coverage.items.find((item) => item.shadow_evaluation?.status === "review_ready")?.shadow_evaluation;
  const summary = coverage.candidate_summary;
  if (!firstReady) {
    return summary?.shadow_evaluation_next_step || "影子评估样本不足";
  }
  const shortText = summary?.shadow_evaluation_short_count
    ? `${summary.shadow_evaluation_short_count} 个样本不足`
    : "样本不足 0";
  return [
    `${summary?.shadow_evaluation_ready_count ?? 0} 个可读`,
    shortText,
    formatCommodityShadowDetail(firstReady),
    summary?.shadow_evaluation_next_step,
  ]
    .filter(Boolean)
    .join(" · ");
}

function formatCommodityShadowDetail(evaluation: CrisisCommodityShadowEvaluation) {
  const parts = [
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `危机期命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
  ];
  if (evaluation.status === "history_short" && typeof evaluation.minimum_sample_count === "number") {
    parts.push(`最低样本 ${evaluation.minimum_sample_count}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.sample_gap === "number") {
    parts.push(`还差 ${evaluation.sample_gap}`);
  }
  return parts.join(" · ");
}

function formatCommodityShadowDecisionMetrics(evaluation: CrisisCommodityShadowEvaluation) {
  const parts = [
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `领先相关 ${formatSignedDecimal(evaluation.lead_1d_correlation)}`,
    `滞后相关 ${formatSignedDecimal(evaluation.lag_1d_correlation)}`,
    `危机期命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `危机样本 ${evaluation.crisis_sample_count ?? "缺失"}`,
  ];
  if (evaluation.window_start || evaluation.window_end) {
    parts.push(`窗口 ${evaluation.window_start ?? "缺失"} -> ${evaluation.window_end ?? "缺失"}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.minimum_sample_count === "number") {
    parts.push(`最低样本 ${evaluation.minimum_sample_count}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.sample_gap === "number") {
    parts.push(`还差 ${evaluation.sample_gap}`);
  }
  return parts.join(" · ");
}

type CommodityPromotionRuleStatus = "ready_for_review" | "manual_review" | "not_recommended";
type CommodityPromotionRuleCheck = {
  name: string;
  status: CommodityPromotionRuleStatus;
  value: string;
};
type CommodityPromotionRuleItem = {
  field: string;
  label: string;
  status: CommodityPromotionRuleStatus;
  reason: string;
  checks: CommodityPromotionRuleCheck[];
};

function commodityPromotionRuleItem(item: CrisisCommodityCoverageItem): CommodityPromotionRuleItem {
  const evaluation = item.shadow_evaluation;
  if (!evaluation || evaluation.status !== "review_ready") {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "not_recommended",
      reason: "样本不足，先补齐历史数据",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  const hasEnoughSamples =
    (evaluation.sample_count ?? 0) >= (evaluation.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES);
  const hasCrisisSamples = (evaluation.crisis_sample_count ?? 0) >= MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES;
  const correlation = Math.max(
    Math.abs(evaluation.same_day_correlation ?? 0),
    Math.abs(evaluation.lead_1d_correlation ?? 0),
    Math.abs(evaluation.lag_1d_correlation ?? 0),
  );
  const hasReadableMetrics = evaluation.crisis_hit_rate != null && correlation > 0;
  if (!hasEnoughSamples || !hasCrisisSamples || evaluation.crisis_hit_rate == null) {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "not_recommended",
      reason: "准入样本或危机期指标不足",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  if (!hasReadableMetrics || correlation < MACRO_COMMODITY_SHADOW_MIN_CORRELATION) {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "manual_review",
      reason: "相关性偏弱，需人工复核",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  return {
    field: item.field,
    label: item.label || item.field,
    status: "ready_for_review",
    reason: "影子指标满足准入检查，仍需审批确认",
    checks: commodityPromotionRuleChecks(evaluation),
  };
}

function commodityPromotionRuleChecks(
  evaluation: CrisisCommodityShadowEvaluation | null,
): CommodityPromotionRuleCheck[] {
  const isReviewReady = evaluation?.status === "review_ready";
  const sampleCount = evaluation?.sample_count ?? null;
  const minimumSampleCount = evaluation?.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES;
  const crisisSampleCount = isReviewReady ? (evaluation.crisis_sample_count ?? null) : null;
  const correlation = isReviewReady
    ? Math.max(
        Math.abs(evaluation.same_day_correlation ?? 0),
        Math.abs(evaluation.lead_1d_correlation ?? 0),
        Math.abs(evaluation.lag_1d_correlation ?? 0),
      )
    : null;
  return [
    {
      name: "样本检查",
      status:
        typeof sampleCount === "number" && sampleCount >= minimumSampleCount
          ? "ready_for_review"
          : "not_recommended",
      value: `${sampleCount ?? "缺失"}/${minimumSampleCount}`,
    },
    {
      name: "危机样本检查",
      status:
        typeof crisisSampleCount === "number" && crisisSampleCount >= MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES
          ? "ready_for_review"
          : "not_recommended",
      value: `${crisisSampleCount ?? "缺失"}/${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES}`,
    },
    {
      name: "相关性检查",
      status:
        correlation == null
          ? "not_recommended"
          : correlation >= MACRO_COMMODITY_SHADOW_MIN_CORRELATION
            ? "ready_for_review"
            : "manual_review",
      value: typeof correlation === "number" ? formatSignedDecimal(correlation) : "缺失",
    },
    {
      name: "命中率检查",
      status: evaluation?.crisis_hit_rate == null ? "not_recommended" : "ready_for_review",
      value: formatPercent(evaluation?.crisis_hit_rate),
    },
  ];
}

function commodityPromotionRuleStatusLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "通过";
  }
  if (status === "manual_review") {
    return "待人工判断";
  }
  return "不建议进入公式";
}

function commodityPromotionRuleCheckStatusLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "通过";
  }
  if (status === "manual_review") {
    return "待人工判断";
  }
  return "未通过";
}

function commodityReviewConclusionLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "可进入人工复核";
  }
  if (status === "manual_review") {
    return "继续观察";
  }
  return "不建议纳入";
}

function commodityReviewConclusionColor(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "green";
  }
  if (status === "manual_review") {
    return "gold";
  }
  return "red";
}

function commodityAdmissionDecisionColor(decision: CrisisCommodityAdmissionDecision) {
  if (decision === "recommend_include") {
    return "green";
  }
  if (decision === "watch") {
    return "gold";
  }
  return "red";
}

function formatCommodityAdmissionMetrics(item: CrisisCommodityAdmissionItem) {
  const sampleText =
    item.decision === "do_not_include" || item.sample_count == null
      ? `样本 ${item.sample_count ?? "缺失"}/${item.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES}`
      : `样本 ${item.sample_count}`;
  return [
    sampleText,
    `危机样本 ${item.crisis_sample_count ?? "缺失"}`,
    `命中率 ${formatPercent(item.crisis_hit_rate)}`,
    `最大相关 ${formatSignedDecimal(item.max_abs_correlation)}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
    item.source ? `来源 ${item.source}` : null,
    item.series_id ? `series ${item.series_id}` : null,
    item.used_in_official_score ? "已纳入正式 Crisis Score" : "审批前不改变正式 Crisis Score",
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

function formatCommodityAdmissionNextStep(item: CrisisCommodityAdmissionItem) {
  if (item.decision === "recommend_include") {
    return "提交人工复核与权重审批";
  }
  if (item.decision === "watch") {
    return "复核相关性与危机期命中率";
  }
  return item.next_step;
}

function formatCommodityApprovalPackFields(fields: string[]) {
  return fields.length ? fields.join(" / ") : "无";
}

function formatSignedDeltaFromPack(copyText: string) {
  const match = copyText.match(/shadow delta\s+([+-]?\d+(?:\.\d+)?)/);
  return match?.[1] ?? "缺失";
}

function formatCommodityReviewConclusionMetrics(item: CrisisCommodityCoverageItem) {
  const evaluation = item.shadow_evaluation;
  if (!evaluation) {
    return "影子评估缺失";
  }
  const minimumSampleCount = evaluation.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES;
  const sampleText =
    evaluation.status === "history_short" || evaluation.sample_count == null
      ? `样本 ${evaluation.sample_count ?? "缺失"}/${minimumSampleCount}`
      : `样本 ${evaluation.sample_count}`;
  return [
    sampleText,
    `危机样本 ${evaluation.crisis_sample_count ?? "缺失"}`,
    `命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

function formatCommodityReviewConclusionNextStep(
  status: CommodityPromotionRuleStatus,
  item: CrisisCommodityCoverageItem,
) {
  if (status === "ready_for_review") {
    return "下一步：提交人工复核与权重审批";
  }
  if (status === "manual_review") {
    return "下一步：复核相关性与危机期命中率";
  }
  const sampleGap = item.shadow_evaluation?.sample_gap;
  return typeof sampleGap === "number"
    ? `下一步：先补齐历史数据，还差 ${sampleGap} 个样本`
    : "下一步：先补齐历史数据";
}

function formatCommodityShadowImpactDirectionDetail(items: CrisisCommodityCoverageItem[]) {
  if (!items.length) {
    return "暂无可复核商品候选";
  }
  return `${formatCommodityActionQueueLabels(items)} 需要 v2 权重后确认方向`;
}

function formatCommodityShadowImpactDriverDetail(item: CrisisCommodityCoverageItem) {
  const evaluation = item.shadow_evaluation;
  if (!evaluation) {
    return "影子评估缺失";
  }
  return [
    `命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

function commodityShadowImpactDirectionLabel(direction: string) {
  if (direction === "higher_stress") {
    return "压力上行";
  }
  if (direction === "lower_stress") {
    return "压力下行";
  }
  if (direction === "unchanged") {
    return "基本不变";
  }
  return "待确认";
}

function formatSignedDelta(value: number | null | undefined, digits = 2) {
  if (value == null) {
    return "缺失";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function formatCommodityShadowImpactWarnings(shadowImpact: CrisisCommodityShadowImpact) {
  return shadowImpact.warnings.length ? shadowImpact.warnings.join(" / ") : "warnings missing";
}

function formatCommodityShadowContributionDetail(item: CrisisCommodityShadowContribution) {
  return [
    `${item.candidate_metric} ${formatSignedDelta(item.candidate_value, 2)}`,
    `贡献 ${formatSignedDelta(item.contribution, 4)}`,
    `权重 ${formatPercent(item.weight)}`,
    `样本 ${item.sample_count ?? "缺失"}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

function buildCommodityPromotionAuditPackCopyText(
  promotionItems: CommodityPromotionRuleItem[],
  counts: {
    manualCount: number;
    rejectedCount: number;
    analysisMeta?: ResultMeta | null;
    analysisAsOfDate?: string | null;
    reviewQueueItems: CrisisCommodityCoverageItem[];
    shortQueueItems: CrisisCommodityCoverageItem[];
    coverageItems: CrisisCommodityCoverageItem[];
    commodityInput: MacroToolkitInputEvidenceItem | null;
    summary: CrisisCommodityCandidateSummary | null;
  },
) {
  const reviewQueueText = formatCommodityActionQueueLabels(counts.reviewQueueItems);
  const shortQueueText = formatCommodityActionQueueLabels(counts.shortQueueItems);
  const nextStepText = counts.summary
    ? formatCommodityActionQueueNextStep(counts.reviewQueueItems, counts.shortQueueItems, counts.summary)
    : "下一步待确认";
  return [
    "Crisis Score 商品候选审计包",
    `分析日期 ${counts.analysisMeta?.as_of_date ?? counts.analysisAsOfDate ?? "缺失"}`,
    `source_version ${counts.analysisMeta?.source_version ?? "缺失"}`,
    `vendor_version ${counts.analysisMeta?.vendor_version ?? "缺失"}`,
    `rule_version ${counts.analysisMeta?.rule_version ?? "缺失"}`,
    `cache_version ${counts.analysisMeta?.cache_version ?? "缺失"}`,
    `规则版本 ${MACRO_COMMODITY_SHADOW_RULE_VERSION}`,
    "用途：商品候选进入公式前的影子复核",
    "边界：不写入 Crisis Score，不改变权重",
    "审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交",
    `准入检查：样本>=${MACRO_COMMODITY_SHADOW_MIN_SAMPLES} / 危机样本>=${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} / 相关性可读 / 命中率可读`,
    `样本阈值 >=${MACRO_COMMODITY_SHADOW_MIN_SAMPLES} 个重叠样本`,
    `危机样本阈值 >=${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} 个高 Crisis Score 样本`,
    `相关性阈值 |corr|>=${MACRO_COMMODITY_SHADOW_MIN_CORRELATION.toFixed(2)} 才可直接通过`,
    `人工复核队列 ${reviewQueueText}`,
    `补历史样本队列 ${shortQueueText}`,
    `处理顺序 ${nextStepText}`,
    formatOfficialCommodityInputAuditLine(counts.commodityInput),
    `待人工判断 ${counts.manualCount}`,
    `不建议进入公式 ${counts.rejectedCount}`,
    ...counts.coverageItems.map(formatCommodityAuditSourceLine),
    ...promotionItems.flatMap((item) => [
      `${item.label} · ${commodityPromotionRuleStatusLabel(item.status)} · ${item.reason}`,
      ...item.checks.map(
        (check) =>
          `${item.label} · ${check.name} ${commodityPromotionRuleCheckStatusLabel(check.status)} ${check.value}`,
      ),
    ]),
  ].join("\n");
}

function commodityShadowStatusColor(status: string | null | undefined) {
  if (status === "review_ready") {
    return "green";
  }
  if (status === "history_short") {
    return "orange";
  }
  return "default";
}

function formatCommodityAuditSourceLine(item: CrisisCommodityCoverageItem) {
  const formulaText = item.used_in_formula ? "已纳入公式" : "当前未计入 Crisis Score";
  return [
    `候选来源 ${item.label || item.field}`,
    item.series_id ?? "series 缺失",
    `aliases ${item.aliases.length ? item.aliases.join(" / ") : "缺失"}`,
    `matched ${item.matched_alias ?? "缺失"}`,
    item.source ?? "source 缺失",
    `latest ${item.latest_date ?? "缺失"}`,
    `report ${item.report_date ?? "缺失"}`,
    formatCommodityCoverageDateStatus(item.date_alignment_status),
    `rows ${item.row_count ?? "缺失"}`,
    formulaText,
  ].join(" · ");
}

function formatOfficialCommodityInputAuditLine(input: MacroToolkitInputEvidenceItem | null) {
  if (!input) {
    return "正式商品输入 缺失 · 已纳入 Crisis Score 公式的南华输入未命中";
  }
  return [
    `正式商品输入 ${input.label || input.field}`,
    formatCrisisInputIdentifiers(input),
    `source ${input.source ?? "缺失"}`,
    `latest ${input.latest_date ?? "缺失"}`,
    `rows ${input.row_count ?? "缺失"}`,
    `value ${formatValue(input.value ?? null, "")}`,
    "已纳入 Crisis Score 公式",
  ].join(" · ");
}

function isCommodityShadowReviewReady(item: CrisisCommodityCoverageItem) {
  return item.shadow_evaluation?.status === "review_ready";
}

function isCommodityShadowHistoryShort(item: CrisisCommodityCoverageItem) {
  return item.shadow_evaluation?.status === "history_short";
}

function formatCommodityActionQueueLabels(items: CrisisCommodityCoverageItem[]) {
  if (!items.length) {
    return "无";
  }
  return items.map((item) => item.label || item.field).join(" / ");
}

function formatCommodityActionQueueNextStep(
  reviewItems: CrisisCommodityCoverageItem[],
  shortItems: CrisisCommodityCoverageItem[],
  summary: CrisisCommodityCandidateSummary,
) {
  if (shortItems.length && reviewItems.length) {
    return `下一步：先补齐样本不足品种，再复核${formatCommodityActionQueueShortNames(reviewItems)}的相关性与命中率`;
  }
  if (shortItems.length) {
    return "下一步：先补齐样本不足品种，再重新运行完整分析";
  }
  if (reviewItems.length) {
    return `下一步：复核${formatCommodityActionQueueShortNames(reviewItems)}的相关性与命中率`;
  }
  return summary.shadow_evaluation_next_step || "下一步待确认";
}

function formatCommodityActionQueueShortNames(items: CrisisCommodityCoverageItem[]) {
  return items.map((item) => commodityChineseShortName(item.label || item.field)).join("、");
}

function commodityChineseShortName(label: string) {
  const normalized = label.toLowerCase();
  if (normalized.includes("copper")) {
    return "铜";
  }
  if (normalized.includes("crude")) {
    return "原油";
  }
  if (normalized.includes("aluminum")) {
    return "铝";
  }
  if (normalized.includes("gold")) {
    return "黄金";
  }
  if (normalized.includes("rebar")) {
    return "螺纹钢";
  }
  if (normalized.includes("iron")) {
    return "铁矿石";
  }
  return label;
}

function formatCommodityShadowShortfallList(summary: CrisisCommodityCandidateSummary) {
  const items = summary.shadow_evaluation_short_items.map((item) => {
    const sampleText =
      typeof item.sample_count === "number" && typeof item.minimum_sample_count === "number"
        ? `${item.sample_count}/${item.minimum_sample_count}`
        : "样本缺失";
    const gapText = typeof item.sample_gap === "number" ? `还差 ${item.sample_gap}` : "缺口待确认";
    const dateText = item.latest_date ? `，最新 ${item.latest_date}` : "";
    return `${item.label || item.field} ${sampleText}，${gapText}${dateText}`;
  });
  return `样本不足：${items.join("；")}`;
}

function crisisCommodityShortItemsFromResult(
  result: MacroToolkitCapabilityResult | null | undefined,
): CrisisCommodityShadowShortItem[] {
  if (!result) {
    return [];
  }
  const coverage = normalizeCommodityCoverage(
    (result as { commodity_coverage?: unknown }).commodity_coverage ?? result.result.commodity_coverage,
  );
  return coverage?.candidate_summary?.shadow_evaluation_short_items ?? [];
}

function suggestedCommodityRefreshStartDate(result: MacroToolkitCapabilityResult | null | undefined) {
  const latestDates = crisisCommodityShortItemsFromResult(result)
    .map((item) => item.latest_date)
    .filter((date): date is string => Boolean(date));
  if (!latestDates.length) {
    return undefined;
  }
  const earliestLatestDate = latestDates.sort()[0];
  const parsed = new Date(`${earliestLatestDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  parsed.setUTCDate(parsed.getUTCDate() - MACRO_COMMODITY_SUGGESTED_REFRESH_LOOKBACK_DAYS);
  return parsed.toISOString().slice(0, 10);
}

function crisisCommodityShortItemsFromEnvelope(
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null | undefined,
): CrisisCommodityShadowShortItem[] {
  const result = envelope?.result.capability_results.find((item) => item.key === "crisis_score_cn") ?? null;
  return crisisCommodityShortItemsFromResult(result);
}

function formatCommodityShortfallChanges(
  beforeItems: CrisisCommodityShadowShortItem[],
  afterItems: CrisisCommodityShadowShortItem[],
): CommodityShortfallChange[] {
  const afterByField = new Map(afterItems.map((item) => [item.field, item]));
  return beforeItems
    .map((before) => {
      if (before.sample_count == null || before.minimum_sample_count == null) {
        return null;
      }
      const after = afterByField.get(before.field);
      const afterSample = after?.sample_count ?? before.minimum_sample_count;
      const afterMinimum = after?.minimum_sample_count ?? before.minimum_sample_count;
      const remainingGap = Math.max(0, afterMinimum - afterSample);
      return {
        field: before.field,
        label: before.label || before.field,
        before: `${before.sample_count}/${before.minimum_sample_count}`,
        after: `${afterSample}/${afterMinimum}`,
        remainingGap,
        resolved: remainingGap === 0,
      };
    })
    .filter((item): item is CommodityShortfallChange => item !== null);
}

function formatCommodityShortfallChangeList(changes: CommodityShortfallChange[]) {
  return changes.map((item) => `${item.label} ${item.before} -> ${item.after}`).join("；");
}

function formatCommodityShortfallEstimates(
  beforeItems: CrisisCommodityShadowShortItem[],
  refresh: MacroToolkitCommodityFuturesRefreshRun,
): CommodityShortfallEstimate[] {
  const rowsByProduct = new Map(
    normalizeCommodityRefreshRows(refresh).map((row) => [row.productCode, row.estimatedRows ?? row.rowCount ?? 0]),
  );
  return beforeItems
    .map((item) => {
      if (item.sample_count == null || item.minimum_sample_count == null) {
        return null;
      }
      const product = MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field];
      const estimatedRows = product ? rowsByProduct.get(product) ?? 0 : 0;
      const afterSample = Math.min(item.minimum_sample_count, item.sample_count + estimatedRows);
      return {
        field: item.field,
        label: item.label || item.field,
        before: `${item.sample_count}/${item.minimum_sample_count}`,
        after: `${afterSample}/${item.minimum_sample_count}`,
        estimatedRows,
        canFill: afterSample >= item.minimum_sample_count,
      };
    })
    .filter((item): item is CommodityShortfallEstimate => item !== null && item.estimatedRows > 0);
}

function formatCommodityShortfallEstimateList(estimates: CommodityShortfallEstimate[]) {
  const canFillAll = estimates.every((item) => item.canFill);
  const prefix = canFillAll
    ? "预计可补齐最低样本，建议刷新商品期货"
    : "预计仍有样本缺口，刷新后仍不会闭环";
  const items = estimates.map((item) => {
    const remainingGap = item.canFill ? 0 : commodityShortfallRemainingGap(item.after);
    const conclusion = item.canFill
      ? `可补齐至 ${item.after}`
      : `预计到 ${item.after}${remainingGap == null ? "" : `，还差 ${remainingGap}`}`;
    return `${item.label} ${item.before}，预计 +${item.estimatedRows}，${conclusion}`;
  });
  return `${prefix}：${items.join("；")}`;
}

function formatCommodityRefreshActionLabel(estimates: CommodityShortfallEstimate[]) {
  if (!estimates.length) {
    return "刷新商品期货";
  }
  return estimates.every((item) => item.canFill)
    ? "刷新商品期货：刷新并重算证据"
    : "刷新商品期货：仍有缺口，谨慎刷新";
}

function commodityShortfallRemainingGap(sampleText: string) {
  const match = /^(\d+)\/(\d+)$/.exec(sampleText);
  if (!match) {
    return null;
  }
  return Math.max(0, Number(match[2]) - Number(match[1]));
}

function commodityShadowRefreshProducts(summary: CrisisCommodityCandidateSummary) {
  const backendSuggestions = summary.suggested_refresh_products.filter(
    (item, index, array) => array.indexOf(item) === index,
  );
  if (backendSuggestions.length) {
    return backendSuggestions;
  }
  return summary.shadow_evaluation_short_items
    .map((item) => MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field])
    .filter((item, index, array): item is string => Boolean(item) && array.indexOf(item) === index);
}

function formatCommodityShadowRefreshHint(products: string[]) {
  return products.length ? `建议刷新品种：${products.join(" / ")}` : "";
}

function formatCommodityProducts(products: string[]) {
  return products.length ? `品种 ${products.join(" / ")}` : "品种待选择";
}

function formatCommodityProductsInline(products: string[]) {
  return products.length ? products.join(" / ") : "待确认";
}

function commodityRefreshRunProducts(refresh: MacroToolkitCommodityFuturesRefreshRun) {
  return normalizeCommodityRefreshRows(refresh)
    .map((row) => row.productCode)
    .filter((item, index, array) => Boolean(item) && array.indexOf(item) === index);
}

function formatSignedDecimal(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(2) : "缺失";
}

const CRISIS_GAP_GROUP_LABELS: Record<CrisisGapGroupKey, string> = {
  equity: "股票风险输入",
  liquidity: "利率与流动性输入",
  commodity: "商品期货输入",
  curve_credit: "曲线与信用输入",
  fx: "汇率输入",
  other: "其他输入",
};

function uniqueDisplayParts(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => value?.trim()).filter((value): value is string => Boolean(value))));
}

function buildCrisisGapGroups(
  inputEvidence: MacroToolkitInputEvidenceItem[],
  warnings: string[],
  commodityCoverage?: CrisisCommodityCoverage | null,
): CrisisGapGroup[] {
  const warningSet = new Set(warnings);
  const itemsByGroup = new Map<CrisisGapGroupKey, CrisisGapItem[]>();
  const pushItem = (groupKey: CrisisGapGroupKey, item: CrisisGapItem) => {
    const items = itemsByGroup.get(groupKey) ?? [];
    if (!items.some((candidate) => candidate.warning === item.warning && candidate.label === item.label)) {
      items.push(item);
    }
    itemsByGroup.set(groupKey, items);
  };

  for (const input of inputEvidence) {
    const warning = input.warning;
    const isMissing = input.available === false || (warning ? warningSet.has(warning) : false);
    if (!isMissing || !warning) {
      continue;
    }
    pushItem(crisisGapGroupKey(input.field, warning), {
      label: input.label || input.field,
      warning,
      detail: crisisGapInputDetail(input),
      identifiers: crisisGapInputIdentifiers(input),
    });
    warningSet.delete(warning);
  }

  for (const warning of warningSet) {
    pushItem(crisisGapGroupKey("", warning), {
      label: warning.replace(/_MISSING$/, "").toLowerCase(),
      warning,
      detail: "输入证据缺失，缺失不按 0 处理",
      identifiers: [warning],
    });
  }

  for (const item of commodityCoverage?.candidate_summary?.shadow_evaluation_short_items ?? []) {
    pushItem("commodity", {
      label: item.label || item.field,
      warning: "COMMODITY_SAMPLE_SHORT",
      detail: formatCommodityShortfallGapDetail(item),
      identifiers: uniqueDisplayParts([item.field, item.label, "COMMODITY_SAMPLE_SHORT"]),
    });
  }

  return (["equity", "liquidity", "commodity", "curve_credit", "fx", "other"] as CrisisGapGroupKey[])
    .map((key) => ({ key, label: CRISIS_GAP_GROUP_LABELS[key], items: itemsByGroup.get(key) ?? [] }))
    .filter((group) => group.items.length);
}

function formatCrisisGapSummaryDetail(groups: CrisisGapGroup[]) {
  if (!groups.length) {
    return "无缺失输入";
  }
  return groups
    .map((group) => `${group.label}: ${uniqueDisplayParts(group.items.map((item) => item.warning)).join(" / ")}`)
    .join("；");
}

function buildCrisisGapRepairFeedback(
  previousGroup: CrisisGapGroup,
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null,
  actionMessage: string,
): CrisisGapRepairFeedback {
  if (!envelope) {
    return {
      groupKey: previousGroup.key,
      groupLabel: previousGroup.label,
      status: "failed",
      message: "完整分析重读失败",
      detail: actionMessage,
    };
  }
  const currentGroup = crisisGapGroupFromEnvelope(envelope, previousGroup.key);
  if (!currentGroup) {
    return {
      groupKey: previousGroup.key,
      groupLabel: previousGroup.label,
      status: "resolved",
      message: "已补齐，完整分析已重读",
      detail: actionMessage,
    };
  }
  return {
    groupKey: previousGroup.key,
    groupLabel: previousGroup.label,
    status: "partial",
    message: "完整分析已重读，仍有缺口",
    detail: currentGroup.items.map((item) => item.warning).join(" / ") || actionMessage,
  };
}

function crisisGapGroupFromEnvelope(
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload>,
  groupKey: CrisisGapGroupKey,
) {
  const result = envelope.result.capability_results.find((item) => item.key === "crisis_score_cn");
  return crisisGapGroupFromResult(result, groupKey);
}

function crisisGapGroupFromResult(
  result: MacroToolkitCapabilityResult | null | undefined,
  groupKey: CrisisGapGroupKey,
) {
  if (!result) {
    return null;
  }
  const normalizedEvidence = normalizeInputEvidence(result);
  const inputEvidence = normalizedEvidence?.inputs ?? [];
  const warnings = uniqueDisplayParts([...(result.warnings ?? []), ...(normalizedEvidence?.missingInputs ?? [])]);
  const commodityCoverage = normalizeCommodityCoverage(
    (result as { commodity_coverage?: unknown }).commodity_coverage ?? result.result.commodity_coverage,
  );
  return buildCrisisGapGroups(inputEvidence, warnings, commodityCoverage).find((group) => group.key === groupKey) ?? null;
}

function crisisGapGroupKey(field: string, warning: string): CrisisGapGroupKey {
  const token = `${field} ${warning}`.toUpperCase();
  if (token.includes("HS300") || token.includes("EQUITY") || token.includes("STOCK")) {
    return "equity";
  }
  if (token.includes("DR007") || token.includes("REVERSE_REPO") || token.includes("LIQUIDITY")) {
    return "liquidity";
  }
  if (token.includes("NANHUA") || token.includes("COMMODITY")) {
    return "commodity";
  }
  if (token.includes("AA_") || token.includes("GOV_") || token.includes("CREDIT") || token.includes("CURVE")) {
    return "curve_credit";
  }
  if (token.includes("USDCNY") || token.includes("FX")) {
    return "fx";
  }
  return "other";
}

function crisisGapInputDetail(input: MacroToolkitInputEvidenceItem) {
  const rowText = formatCrisisRowCount(input.row_count);
  const dateText = input.latest_date ?? "日期缺失";
  const sourceText = input.source ?? "source missing";
  return `${rowText} · ${dateText} · ${sourceText} · 缺失不按 0 处理`;
}

function crisisGapInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  return uniqueDisplayParts([input.field, input.warning, ...(input.aliases ?? []), input.series_id]);
}

function formatCommodityShortfallGapDetail(item: CrisisCommodityShadowShortItem) {
  const sampleText =
    item.sample_count == null || item.minimum_sample_count == null
      ? "样本缺失"
      : `${item.sample_count}/${item.minimum_sample_count}`;
  const gapText = item.sample_gap == null ? "缺口待确认" : `还差 ${item.sample_gap}`;
  const dateText = item.latest_date ? `最新 ${item.latest_date}` : "日期缺失";
  return `${sampleText} · ${gapText} · ${dateText} · 缺失不按 0 处理`;
}

function findCrisisGapRepairItem(group: CrisisGapGroup, repairItems: MacroToolkitRepairItem[]) {
  const groupIdentifiers = new Set(
    group.items.flatMap((item) => item.identifiers).map((identifier) => identifier.toUpperCase()),
  );
  return repairItems.find((item) => {
    if (!canRefreshMacroSourceBackfill(item)) {
      return false;
    }
    const itemIdentifiers = uniqueDisplayParts([item.alias, item.key, item.label]).map((identifier) =>
      identifier.toUpperCase(),
    );
    return itemIdentifiers.some((identifier) => groupIdentifiers.has(identifier));
  });
}

function isNanhuaCrisisInput(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([input.field, ...(input.aliases ?? []), input.series_id]).map((item) =>
    item.toUpperCase(),
  );
  return (
    identifiers.includes("NANHUA") ||
    identifiers.includes(NANHUA_CRISIS_ALIAS) ||
    identifiers.includes(NANHUA_SYSTEM_SERIES_ID)
  );
}

function formatCrisisInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([
    ...(input.aliases ?? []),
    ...(isNanhuaCrisisInput(input) ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    input.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

function formatCommodityCoverageIdentifiers(item: CrisisCommodityCoverageItem) {
  const identifiers = uniqueDisplayParts([
    ...item.aliases,
    item.matched_alias,
    ...(item.field === "nanhua" || item.used_in_formula ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    item.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

function formatCrisisInputDetail(input: MacroToolkitInputEvidenceItem | undefined) {
  if (!input) {
    return "Nanhua commodity index / NH0100.NHF 未命中";
  }
  return `${input.label || input.field} · ${formatCrisisInputIdentifiers(input)} · ${
    input.latest_date ?? "日期缺失"
  }`;
}

function hasRealStrategySource(strategy: MacroToolkitStrategySummary) {
  return (
    strategy.result.price_source === "choice_stock_daily_observation" ||
    strategy.result.factor_source === "choice_stock_factor_snapshot"
  );
}

function hasCompleteRealStrategyChain(strategy: MacroToolkitStrategySummary) {
  if (strategy.status !== "complete" || strategyDataStatus(strategy) !== "complete") {
    return false;
  }
  const hasPriceSource = strategy.result.price_source === "choice_stock_daily_observation";
  const hasFactorSource = strategy.result.factor_source === "choice_stock_factor_snapshot";
  if (strategy.key === "multi_factor_selection") {
    return hasFactorSource;
  }
  if (strategy.key === "low_crowding_regime_multifactor") {
    return hasPriceSource && hasFactorSource;
  }
  return hasPriceSource;
}

function strategyDataStatus(strategy: MacroToolkitStrategySummary) {
  return typeof strategy.result.data_status === "string" && strategy.result.data_status.trim()
    ? strategy.result.data_status.trim()
    : strategy.status;
}

function choiceStockTableDetail(
  table: { row_count?: number; latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  return `行数 ${table?.row_count ?? 0} · ${choiceStockTableSummary(table, dateField)}`;
}

function choiceStockTableSummary(
  table: { latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  const dateText = table?.[dateField] ?? "缺失";
  const statusText = statusLabel(table?.freshness_status ?? "unknown");
  const fallbackText = choiceStockFallbackText(table);
  return [dateText, statusText, fallbackText].filter(Boolean).join(" · ");
}

function normalizeCommodityRefreshRows(refresh: MacroToolkitCommodityFuturesRefreshRun): CommodityRefreshProductRow[] {
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const table = refresh.table ?? "fact_commodity_futures_daily";
  return (refresh.products ?? []).filter(isRecord).map((item, index) => {
    const rawProductCode = commodityRefreshProductCode(item.product_code, index);
    const rawSeriesId = commodityRefreshString(item.series_id);
    const productCode = normalizeCommodityRefreshProductCode(rawProductCode, rawSeriesId);
    const option = MACRO_COMMODITY_PRODUCT_OPTIONS.find((candidate) => candidate.value === productCode);
    const productName = commodityRefreshString(item.name_zh) || option?.label || productCode;
    const estimatedRows = commodityRefreshNumber(item.estimated_rows);
    const writtenRows = commodityRefreshNumber(item.row_count);
    const rowCount = isDryRun ? estimatedRows ?? writtenRows : writtenRows ?? estimatedRows;
    const seriesId = rawSeriesId || commodityRefreshSeriesId(productCode);
    const latestDate = commodityRefreshString(item.latest_date) || (isDryRun ? refresh.end_date ?? "待刷新" : refresh.end_date ?? "缺失");
    const latestValue = commodityRefreshNumber(item.latest_value);
    const status = commodityRefreshProductStatus({ isDryRun, rowCount });
    return {
      key: `${productCode}-${index}`,
      productCode,
      productName,
      seriesId,
      status,
      estimatedRows,
      rowCount,
      rowCountLabel: rowCount == null ? "缺失" : `${isDryRun ? "预计 " : ""}${rowCount} 行`,
      latestDate,
      latestValue,
      vendor: commodityRefreshString(item.vendor) || (isDryRun ? "estimate_only" : "缺失"),
      table,
      isNanhua: isNanhuaCommodityRefreshRow(productCode, seriesId),
    };
  });
}

function commodityRefreshProductCode(value: unknown, index: number) {
  const code = commodityRefreshString(value);
  if (!code) {
    return `#${index + 1}`;
  }
  const normalized = code.toUpperCase();
  return normalized === NANHUA_CRISIS_ALIAS ? NANHUA_COMMODITY_PRODUCT_CODE : normalized;
}

function normalizeCommodityRefreshProductCode(productCode: string, seriesId: string | null) {
  const candidates = [productCode, seriesId ?? ""].map((item) => item.trim().toUpperCase()).filter(Boolean);
  for (const candidate of candidates) {
    if (candidate === NANHUA_CRISIS_ALIAS || candidate === NANHUA_SYSTEM_SERIES_ID) {
      return NANHUA_COMMODITY_PRODUCT_CODE;
    }
    if (candidate === "CA.COPPER") {
      return "CU";
    }
    if (candidate === "CA.ALUMINUM") {
      return "AL";
    }
    if (candidate.startsWith("COMMODITY.")) {
      const code = candidate.slice("COMMODITY.".length);
      if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === code)) {
        return code;
      }
    }
    if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === candidate)) {
      return candidate;
    }
  }
  return productCode;
}

function commodityRefreshString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function commodityRefreshNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function commodityRefreshSeriesId(productCode: string) {
  const normalized = productCode.trim().toUpperCase();
  if (normalized === NANHUA_COMMODITY_PRODUCT_CODE || normalized === NANHUA_CRISIS_ALIAS) {
    return NANHUA_SYSTEM_SERIES_ID;
  }
  if (normalized === "NHII") {
    return "NHII.NH";
  }
  if (normalized === "CU") {
    return "CA.COPPER";
  }
  if (normalized === "AL") {
    return "CA.ALUMINUM";
  }
  return normalized.startsWith("#") ? "缺失" : `COMMODITY.${normalized}`;
}

function isNanhuaCommodityRefreshRow(productCode: string, seriesId: string) {
  const normalizedProductCode = productCode.trim().toUpperCase();
  const normalizedSeriesId = seriesId.trim().toUpperCase();
  return (
    normalizedProductCode === NANHUA_COMMODITY_PRODUCT_CODE ||
    normalizedProductCode === NANHUA_CRISIS_ALIAS ||
    normalizedSeriesId === NANHUA_SYSTEM_SERIES_ID ||
    normalizedSeriesId === NANHUA_CRISIS_ALIAS
  );
}

function commodityRefreshIdentifierText(row: CommodityRefreshProductRow) {
  const identifiers = row.isNanhua
    ? [row.productCode, NANHUA_CRISIS_ALIAS, row.seriesId]
    : [row.productCode, row.seriesId];
  return Array.from(new Set(identifiers.filter(Boolean))).join(" / ");
}

function commodityRefreshProductStatus({
  isDryRun,
  rowCount,
}: {
  isDryRun: boolean;
  rowCount: number | null;
}): CommodityRefreshProductRow["status"] {
  if (rowCount == null || rowCount <= 0) {
    return "missing";
  }
  return isDryRun ? "estimated" : "written";
}

function commodityRefreshStatusText(status: CommodityRefreshProductRow["status"]) {
  if (status === "estimated") {
    return "预计可写";
  }
  if (status === "written") {
    return "已写入";
  }
  return "未命中";
}

function commodityRefreshStatusColor(status: CommodityRefreshProductRow["status"]) {
  if (status === "missing") {
    return "red";
  }
  return status === "written" ? "green" : "blue";
}

function formatCommodityRefreshResult(refresh: MacroToolkitCommodityFuturesRefreshRun) {
  const productCount = refresh.product_count ?? refresh.products?.length ?? 0;
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const rowCount = isDryRun
    ? refresh.estimated_total_rows ?? refresh.row_count ?? 0
    : refresh.row_count ?? refresh.estimated_total_rows ?? 0;
  const action = isDryRun ? "预估完成" : "刷新完成";
  const tradingDays = isDryRun && refresh.estimated_trading_days ? `，约 ${refresh.estimated_trading_days} 个交易日` : "";
  return `商品期货${action}：${productCount} 个品种，${rowCount} 行${tradingDays}`;
}

function commodityRefreshRowDeltaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshNullableNumberText(summary.row_count_before);
  const after = commodityRefreshNullableNumberText(summary.row_count_after);
  const delta = summary.row_count_delta == null ? "变化缺失" : `${summary.row_count_delta >= 0 ? "+" : ""}${summary.row_count_delta}`;
  return `行数 ${before} → ${after}（${delta}）`;
}

function commodityRefreshLatestDateText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.latest_trade_date_before ?? "缺失";
  const after = summary.latest_trade_date_after ?? "缺失";
  return `最新日期 ${before} → ${after}`;
}

function commodityRefreshCoverageText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshCountPair(summary.available_product_count_before, summary.target_product_count);
  const after = commodityRefreshCountPair(summary.available_product_count_after, summary.target_product_count);
  const newlyAvailable = summary.newly_available_products.length
    ? `新增 ${summary.newly_available_products.join(" / ")}`
    : "新增 无";
  const missing = summary.missing_products_after.length ? `缺失 ${summary.missing_products_after.join(" / ")}` : "缺失 无";
  return `覆盖 ${before} → ${after}，${newlyAvailable}，${missing}`;
}

function commodityRefreshNanhuaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.nanhua_latest_date_before ?? "缺失";
  const after = summary.nanhua_latest_date_after ?? "缺失";
  const value = formatNumberValue(summary.nanhua_latest_value_after, 2);
  return `南华 ${before} → ${after}，${value}`;
}

function commodityRefreshSourceText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const source = summary.source_vendors_after.length ? summary.source_vendors_after.join(" / ") : "缺失";
  return `来源 ${source}`;
}

function commodityRefreshNullableNumberText(value: number | null) {
  return value == null ? "缺失" : String(value);
}

function commodityRefreshCountPair(value: number | null, total: number | null) {
  return value == null || total == null ? "缺失" : `${value}/${total}`;
}

type CommodityHealthStatus = NonNullable<NonNullable<MacroToolkitCommodityFuturesRefreshStatus>["status"]>;

function commodityStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.status === "ok" ? "positive" : "missing";
}

function commodityNanhuaStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.nanhua_input?.status === "hit" ? "positive" : "missing";
}

function commodityNanhuaStatusValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  if (status.nanhua_input?.status !== "hit") {
    return "缺失";
  }
  const latestValue = formatNumberValue(status.nanhua_input.latest_value, 2);
  return latestValue === "缺失" ? "已命中" : `已命中 ${latestValue}`;
}

function commodityNanhuaStatusDetail(status: CommodityHealthStatus | null | undefined) {
  const input = status?.nanhua_input;
  if (!input || input.status !== "hit") {
    return "NHCI / NH0100.NHF 未命中";
  }
  const date = input.latest_trade_date ?? "日期缺失";
  const value = formatNumberValue(input.latest_value, 2);
  const source = input.source_version || input.vendor_version || "来源缺失";
  return `${input.product_code} / ${input.series_id} · ${date} · ${value} · ${source}`;
}

function commodityLatestDateValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.latest_trade_date ?? "暂无数据";
}

function commodityTableStatusDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "商品期货证据状态待确认";
  }
  const rowText = status.row_count == null ? "行数缺失" : `${status.row_count} 行`;
  return `商品期货证据 · ${commodityTableStatusLabel(status.status)} · ${rowText}`;
}

function commodityCoverageValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  const coverage = status.coverage;
  return `${coverage.available_product_count}/${coverage.target_product_count}`;
}

function commodityCoverageDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "覆盖品种待确认";
  }
  const available = status.coverage.available_products.length ? status.coverage.available_products.join(" / ") : "无命中";
  const missing = status.coverage.missing_products.length ? ` · 缺失 ${status.coverage.missing_products.join(" / ")}` : "";
  return `${available}${missing}`;
}

function commoditySourceValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.source_vendors.length ? status.source_vendors.join(" / ") : "缺失";
}

function commoditySourceDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "来源待确认";
  }
  const nanhua = status.nanhua_input;
  const source = nanhua?.source_version || nanhua?.vendor_version || status.source_vendors.join(" / ") || "来源缺失";
  return `商品期货证据 · ${formatBusinessEvidenceLabel(source)}`;
}

function commodityTableStatusLabel(status: string) {
  if (status === "ok") {
    return "正常";
  }
  if (status === "empty_table") {
    return "暂无数据";
  }
  if (status === "missing_table") {
    return "未接入";
  }
  if (status === "unreadable_database") {
    return "读取失败";
  }
  return status || "未知";
}

function commodityFuturesPermissionErrorMessage() {
  return "当前账号没有商品期货刷新权限，请先授予 macro_toolkit.commodity_futures:refresh。";
}

function commodityFuturesPermissionPendingMessage() {
  return "商品期货刷新授权待确认，请先确认 macro_toolkit.commodity_futures:dry_run / refresh。";
}

function commodityFuturesPermissionBlockMessage(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  return permission?.allowed === false ? commodityFuturesPermissionErrorMessage() : commodityFuturesPermissionPendingMessage();
}

function formatCommodityFuturesRefreshError(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  if (/not allowed/i.test(message) && message.includes("macro_toolkit.commodity_futures")) {
    return commodityFuturesPermissionErrorMessage();
  }
  return message || "刷新商品期货失败";
}

function commodityFuturesPermissionDetail(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "商品期货刷新授权待确认";
  }
  const actions = permission.actions?.length ? permission.actions.join(" / ") : "dry_run / refresh";
  const user = permission.user_id || "anonymous";
  return `${permission.allowed ? "可刷新" : "未授权"} · ${actions} · ${user}`;
}

function commodityFuturesPermissionNoticeTitle(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  return permission?.allowed === false ? "缺少商品期货刷新授权" : "商品期货刷新授权待确认";
}

function commodityFuturesPermissionNotice(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  const resource = permission?.resource ?? "macro_toolkit.commodity_futures";
  const actions = permission?.actions?.length ? permission.actions.join(" / ") : "dry_run / refresh";
  const user = permission?.user_id || "anonymous";
  const role = permission?.role || "unknown";
  return `请在 scope store 授予 ${resource} 的 action refresh；dry_run / refresh 都需要这条授权。当前用户 ${user}，角色 ${role}，动作 ${actions}。`;
}

function choiceStockFallbackText(
  table: { fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
) {
  if (table?.fallback_mode !== "latest_available" || !table.fallback_date) {
    return "";
  }
  return `fallback ${table.fallback_mode} · 最近可用 ${table.fallback_date}`;
}

function choiceStockPermissionValue(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "待确认";
  }
  if (permission.allowed === false) {
    return "未授权";
  }
  return permission.allowed === true || permission.mode === "identity_only" ? "已授权" : "待确认";
}

function choiceStockRefreshValue(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  if (choiceStockHasRunEvidence(refresh)) {
    return statusLabel(refresh.status);
  }
  return choiceStockPermissionValue(permission);
}

function choiceStockRefreshDetail(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  const hasRunEvidence = choiceStockHasRunEvidence(refresh);
  const permissionDetail = choiceStockPermissionDetail(hasRunEvidence ? (refresh.permission ?? permission) : permission);
  if (!hasRunEvidence) {
    return permissionDetail;
  }
  const runId = refresh.run_id ?? "none";
  const reportDate = refresh.report_date ?? "unknown";
  const triggerMode = refresh.trigger_mode ?? "unknown";
  const historyRows = refresh.history_row_count ?? "-";
  const factorRows = refresh.factor_row_count ?? "-";
  const source = refresh.source_version?.trim();
  const vendor = refresh.vendor_version?.trim();
  const rule = refresh.rule_version?.trim();
  const cache = refresh.cache_version?.trim();
  const versionText = [
    source ? `source ${source}` : "",
    vendor ? `vendor ${vendor}` : "",
    rule ? `rule ${rule}` : "",
    cache ? `cache ${cache}` : "",
  ].filter(Boolean).join(" · ");
  const version = versionText ? ` · ${versionText}` : "";
  const failureText = choiceStockRefreshFailureText(refresh);
  const failure = failureText ? ` · failure ${failureText}` : "";
  return `run ${runId} · report ${reportDate} · trigger ${triggerMode} · rows history ${historyRows} / factor ${factorRows}${version}${failure} · ${permissionDetail}`;
}

function choiceStockHasRunEvidence(refresh: MacroToolkitChoiceStockRefreshRun | null | undefined): refresh is MacroToolkitChoiceStockRefreshRun {
  return Boolean(refresh?.run_id);
}

function choiceStockRefreshFailureText(refresh: MacroToolkitChoiceStockRefreshRun) {
  const category = refresh.failure_category?.trim();
  const reason = refresh.failure_reason?.trim();
  if (category && reason) {
    return `${category}: ${reason}`;
  }
  return reason || refresh.error_message?.trim() || category || "";
}

function choiceStockPermissionDetail(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
  defaultResource = "choice_stock.refresh",
) {
  if (!permission) {
    return `resource ${defaultResource}`;
  }
  const resource = permission.resource ?? defaultResource;
  const mode = permission.mode || "unknown";
  const actions = permission.actions?.length ? permission.actions.join(" / ") : "unknown";
  const user = permission.user_id || "anonymous";
  return `resource ${resource} · mode ${mode} · actions ${actions} · user ${user}`;
}

function formatSignedRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  const percent = value * 100;
  return `${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%`;
}

function formatPlainRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumberValue(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return value.toFixed(digits);
}

function portfolioConstraintText(portfolio: MacroToolkitShadowPortfolio) {
  const constraints = portfolio.constraints;
  const parts = [
    constraints.pe_max == null ? "" : `PE≤${constraints.pe_max}`,
    constraints.pb_max == null ? "" : `PB≤${constraints.pb_max}`,
    constraints.turnover_cap == null ? "" : `换手≤${Math.round(constraints.turnover_cap * 100)}%`,
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : "沿用正式规则约束";
}

function portfolioWeightsText(portfolio: MacroToolkitShadowPortfolio) {
  const labels: Record<string, string> = {
    value: "价值",
    quality: "质量",
    momentum: "动量",
    low_vol: "低波",
    dividend: "红利",
  };
  return Object.entries(portfolio.weights)
    .map(([key, value]) => `${labels[key] ?? key}${Math.round(value * 100)}%`)
    .join(" / ");
}

function costResultText(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  const result = portfolio.cost_results.find((item) => item.cost_bps === costBps);
  if (!result) {
    return `${costBps}bp 缺失`;
  }
  return `${costBps}bp ${formatSignedRatio(result.total_return)} / 超额 ${formatSignedRatio(result.excess_return)}`;
}

function portfolioCostResult(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  return portfolio.cost_results.find((item) => item.cost_bps === costBps);
}

function shadowPortfolioPeriodRows(
  report: MacroToolkitShadowPortfolioReport,
  portfolio: MacroToolkitShadowPortfolio,
) {
  return report.period_returns.filter((row) => row.portfolio_key === portfolio.key);
}

function shadowPortfolioPeriodWinLossText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "周期缺失";
  }
  const wins = rows.filter((row) => row.excess_return > 0).length;
  return `${wins}赢 / ${rows.length - wins}输`;
}

function shadowPortfolioPeriodRangeText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "最佳缺失 / 最差缺失";
  }
  const best = rows.reduce((winner, row) => (row.excess_return > winner.excess_return ? row : winner), rows[0]!);
  const worst = rows.reduce((loser, row) => (row.excess_return < loser.excess_return ? row : loser), rows[0]!);
  return `最佳 ${formatSignedRatio(best.excess_return)} / 最差 ${formatSignedRatio(worst.excess_return)}`;
}

function shadowPortfolioCostGateText(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const passingCosts = [20, 50].filter((costBps) => {
    const referenceCost = portfolioCostResult(reference, costBps);
    const candidateCost = portfolioCostResult(candidate, costBps);
    return (
      referenceCost != null &&
      candidateCost != null &&
      candidateCost.total_return > referenceCost.total_return &&
      candidateCost.excess_return > referenceCost.excess_return
    );
  });
  if (passingCosts.length === 2) {
    return "20bp/50bp 均胜出";
  }
  if (passingCosts.length) {
    return `${passingCosts.join("bp / ")}bp 胜出`;
  }
  return "成本后未胜出";
}

function shadowPortfolioAdmissionText(candidate: MacroToolkitShadowPortfolio) {
  if (!candidate.admission) {
    return "准入口径缺失";
  }
  return `${candidate.admission.label} · ${candidate.admission.summary}`;
}

function admissionCriterionText(threshold: unknown) {
  if (threshold == null) {
    return "";
  }
  if (Array.isArray(threshold)) {
    return threshold.length ? threshold.join(" / ") : "无";
  }
  if (typeof threshold === "string" || typeof threshold === "number" || typeof threshold === "boolean") {
    return String(threshold);
  }
  return "";
}

function holdingCodeList(holdings: MacroToolkitShadowPortfolioHolding[]) {
  return holdings.slice(0, 3).map((holding) => holding.stock_code).join(" / ") || "无";
}

function shadowPortfolioHoldingDiff(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const referenceCodes = new Set(reference.latest_holdings.map((holding) => holding.stock_code));
  const candidateCodes = new Set(candidate.latest_holdings.map((holding) => holding.stock_code));
  const overlap = candidate.latest_holdings.filter((holding) => referenceCodes.has(holding.stock_code));
  const candidateOnly = candidate.latest_holdings.filter((holding) => !referenceCodes.has(holding.stock_code));
  const referenceOnly = reference.latest_holdings.filter((holding) => !candidateCodes.has(holding.stock_code));
  return {
    overlapText: `持仓重合 ${overlap.length}/${Math.max(candidate.latest_holdings.length, 1)}`,
    candidateOnlyText: `新增观察 ${holdingCodeList(candidateOnly)}`,
    referenceOnlyText: `正式独有 ${holdingCodeList(referenceOnly)}`,
  };
}

function periodChipText(row: MacroToolkitShadowPortfolioPeriodReturn) {
  return `${row.start_date.slice(5)}→${row.end_date.slice(5)} ${formatSignedRatio(row.excess_return)}`;
}

function shadowPortfolioFactorWindowText(report: MacroToolkitShadowPortfolioReport) {
  const firstDate = report.factor_dates[0];
  const lastDate = report.factor_dates.at(-1) ?? report.as_of_date;
  if (!firstDate || !lastDate) {
    return `${report.completed_periods}周期`;
  }
  return `${firstDate} → ${lastDate} / ${report.completed_periods}周期`;
}

function shadowPortfolioCostModelText(report: MacroToolkitShadowPortfolioReport) {
  const costs = report.cost_model.cost_bps.length ? `${report.cost_model.cost_bps.join("/")}bp` : "成本缺失";
  const initialBuild = report.cost_model.initial_build_included ? "含初始建仓" : "不含初始建仓";
  const finalLiquidation = report.cost_model.final_liquidation_included ? "含期末清仓" : "不含期末清仓";
  return `${costs} · ${initialBuild} · ${finalLiquidation}`;
}

function shadowPortfolioReviewAction(candidate: MacroToolkitShadowPortfolio) {
  if (candidate.admission?.status === "passed") {
    return "进入正式候选评审，不自动替换正式规则";
  }
  if (candidate.admission?.status === "needs_review") {
    return "补齐历史与告警复核后再评审";
  }
  if (candidate.admission?.status === "failed") {
    return "保持影子观察，暂不进入正式候选";
  }
  return "等待准入口径补齐";
}

function shadowPortfolioWarningText(warning: string) {
  if (warning === "DUCKDB_BUSY") {
    return "本地股票历史库正在刷新或被落库任务占用，稍后刷新页面即可重试。";
  }
  if (warning.startsWith("DUCKDB_OPEN_FAILED")) {
    return "DuckDB 读连接打开失败，暂时不能生成影子组合回测。";
  }
  if (warning === "DUCKDB_NOT_FOUND") {
    return "本地股票历史库不存在，暂时不能生成影子组合回测。";
  }
  if (warning.startsWith("MISSING_TABLES")) {
    return "本地股票历史表或因子快照表缺失，暂时不能生成影子组合回测。";
  }
  if (warning === "FACTOR_HISTORY_TOO_SHORT" || warning === "SHORT_HISTORY") {
    return "因子快照历史偏短，当前结果只能作为只读观察。";
  }
  if (warning === "READ_ONLY_SHADOW_NOT_PRODUCTION") {
    return "只读影子评估，不能作为正式投研信号。";
  }
  return warning;
}

function shadowPortfolioUnavailableDescription(warnings: readonly string[]) {
  const visibleWarnings = Array.from(new Set(warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return visibleWarnings.join(" / ") || "本地股票历史或因子快照不足。";
}

function ShadowPortfolioEvidencePack({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!candidates.length) {
    return null;
  }
  const warnings = Array.from(new Set(report.warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return (
    <div className="macro-toolkit-shadow-evidence" aria-label="影子组合准入证据包">
      <div className="macro-toolkit-capability-result-head">
        <span>准入证据包</span>
        <Tag color="default">只读评估</Tag>
      </div>
      <div className="macro-toolkit-shadow-evidence__facts">
        <span>
          <b>规则版本</b>
          {report.rule_version}
        </span>
        <span>
          <b>回测窗口</b>
          {shadowPortfolioFactorWindowText(report)}
        </span>
        <span>
          <b>成本模型</b>
          {shadowPortfolioCostModelText(report)}
        </span>
        <span>
          <b>数据来源</b>
          {report.tables_used.join(" / ") || "数据表缺失"}
        </span>
      </div>
      <div className="macro-toolkit-shadow-evidence__actions">
        {candidates.map((candidate) => (
          <span key={`evidence-${candidate.key}`}>
            <b>评审动作</b>
            {candidate.label}：{shadowPortfolioReviewAction(candidate)}
          </span>
        ))}
      </div>
      <div className="macro-toolkit-shadow-evidence__warnings">
        {(warnings.length ? warnings : ["无额外告警。"]).map((warning) => (
          <span key={warning}>{warning}</span>
        ))}
      </div>
    </div>
  );
}

function ShadowPortfolioReview({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const reference =
    report.portfolios.find((portfolio) => portfolio.role === "production_reference") ?? report.portfolios[0];
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!reference || !candidates.length) {
    return null;
  }
  return (
    <div className="macro-toolkit-shadow-review" aria-label="影子组合稳健性审查">
      {candidates.map((candidate) => {
        const rows = shadowPortfolioPeriodRows(report, candidate);
        const holdingDiff = shadowPortfolioHoldingDiff(reference, candidate);
        return (
          <div className="macro-toolkit-shadow-review__item" key={`review-${candidate.key}`}>
            <div className="macro-toolkit-capability-result-head">
              <span>稳健性审查</span>
              <Tag color="blue">{candidate.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-review__facts">
              <span>
                <b>周期胜负</b>
                {shadowPortfolioPeriodWinLossText(rows)}
              </span>
              <span>
                <b>区间分布</b>
                {shadowPortfolioPeriodRangeText(rows)}
              </span>
              <span>
                <b>成本后结论</b>
                {shadowPortfolioCostGateText(reference, candidate)}
              </span>
              <span>
                <b>准入结论</b>
                {shadowPortfolioAdmissionText(candidate)}
              </span>
              <span>
                <b>持仓差异</b>
                {holdingDiff.overlapText}
              </span>
            </div>
            {candidate.admission?.criteria.length ? (
              <div className="macro-toolkit-shadow-review__criteria">
                {candidate.admission.criteria.map((criterion) => {
                  const thresholdText = admissionCriterionText(criterion.threshold);
                  return (
                    <div
                      className={`macro-toolkit-shadow-review__criterion ${
                        criterion.passed
                          ? "macro-toolkit-shadow-review__criterion--pass"
                          : "macro-toolkit-shadow-review__criterion--fail"
                      }`}
                      key={`${candidate.key}-${criterion.key}`}
                    >
                      <b>{criterion.label}</b>
                      {criterion.passed ? "通过" : "未通过"}
                      {thresholdText ? ` · ${thresholdText}` : ""}
                    </div>
                  );
                })}
              </div>
            ) : null}
            {rows.length ? (
              <div className="macro-toolkit-shadow-review__periods">
                {rows.slice(-4).map((row) => (
                  <span key={`${candidate.key}-${row.start_date}-${row.end_date}`}>{periodChipText(row)}</span>
                ))}
              </div>
            ) : null}
            <div className="macro-toolkit-shadow-holdings macro-toolkit-shadow-holdings--diff">
              <span>{holdingDiff.candidateOnlyText}</span>
              <span>{holdingDiff.referenceOnlyText}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function shadowPortfolioObservationText(report: MacroToolkitShadowPortfolioReport | null) {
  if (!report) {
    return {
      label: "影子组合待确认",
      value: "未返回",
      detail: "完整分析可继续确认只读组合证据。",
      tone: "missing" as const,
    };
  }
  if (report.status !== "complete") {
    return {
      label: "影子组合只读",
      value: "待确认",
      detail: shadowPortfolioUnavailableDescription(report.warnings),
      tone: "missing" as const,
    };
  }
  const candidate = report.portfolios.find((portfolio) => portfolio.role === "shadow_candidate");
  const action = candidate ? shadowPortfolioReviewAction(candidate) : "保持观察，不替换正式规则";
  return {
    label: "影子组合只读",
    value: report.as_of_date ?? "日期缺失",
    detail: `${report.completed_periods} 个周期 · ${action}`,
    tone: "neutral" as const,
  };
}

function strategyObservationDetail(
  strategySummaries: MacroToolkitStrategySummary[],
  fullRealStrategyCount: number,
  partialRealStrategyCount: number,
  degradedStrategyCount: number,
  sampleStrategyCount: number,
) {
  if (!strategySummaries.length) {
    return "暂无策略摘要，完整分析后再确认。";
  }
  return [
    `真实链路 ${fullRealStrategyCount}`,
    partialRealStrategyCount ? `部分链路 ${partialRealStrategyCount}` : "",
    degradedStrategyCount ? `降级 ${degradedStrategyCount}` : "",
    sampleStrategyCount ? `样例 ${sampleStrategyCount}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function strategyObservationNote(strategy: MacroToolkitStrategySummary | null, strategySupplyState: string) {
  if (!strategy) {
    return `策略供数 ${statusLabel(strategySupplyState)}`;
  }
  const dataStatus = strategyDataStatus(strategy);
  if (hasCompleteRealStrategyChain(strategy)) {
    return `${statusLabel(dataStatus)} · 已接入真实行情或因子快照，仍仅作观察。`;
  }
  if (hasRealStrategySource(strategy)) {
    return `${statusLabel(dataStatus)} · 部分真实供数，缺口需在完整分析中复核。`;
  }
  return `${statusLabel(dataStatus)} · 当前仅展示策略可用性，不作为正式投资信号。`;
}

function StrategyObservationSummary({
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
}: {
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
}) {
  const shadowObservation = shadowPortfolioObservationText(shadowPortfolioReport);
  const bestStrategy = strategySummaries.find((strategy) => strategy.status === "complete") ?? strategySummaries[0] ?? null;
  return (
    <div className="macro-toolkit-strategy-observation" aria-label="策略证据摘要">
      <div className="macro-toolkit-strategy-observation__head">
        <div>
          <span>策略证据摘要</span>
          <strong>只保留观察结论，完整审计留在工具页</strong>
        </div>
        <Tag color="gold">非正式投资信号</Tag>
      </div>
      <div className="macro-toolkit-strategy-observation__grid">
        <MetricTile
          icon={<DatabaseOutlined />}
          label="真实供数"
          value={`${fullRealStrategyCount}/${strategySummaries.length || 0}`}
          detail={strategyObservationDetail(
            strategySummaries,
            fullRealStrategyCount,
            partialRealStrategyCount,
            degradedStrategyCount,
            sampleStrategyCount,
          )}
          tone={fullRealStrategyCount > 0 ? "neutral" : "missing"}
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label={shadowObservation.label}
          value={shadowObservation.value}
          detail={shadowObservation.detail}
          tone={shadowObservation.tone}
          detailMaxLength={44}
        />
        <MetricTile
          icon={<InfoCircleOutlined />}
          label="投研使用"
          value="观察"
          detail="不自动替换正式策略，不作为正式投资信号。"
          tone="neutral"
          detailMaxLength={44}
        />
      </div>
      <div className="macro-toolkit-strategy-observation__note">
        <span>{bestStrategy?.label ?? "策略摘要"}</span>
        <small>{strategyObservationNote(bestStrategy, strategySupplyState)}</small>
      </div>
    </div>
  );
}

function ShadowPortfolioReportPanel({ report }: { report: MacroToolkitShadowPortfolioReport | null }) {
  if (!report) {
    return null;
  }
  if (report.status !== "complete") {
    return (
      <div className="macro-toolkit-shadow-report macro-toolkit-shadow-report--warning" aria-label="影子组合报告">
        <Alert
          type="warning"
          showIcon
          message="影子组合报告暂不可用"
          description={shadowPortfolioUnavailableDescription(report.warnings)}
        />
        {report.warnings.length ? (
          <div className="macro-toolkit-tag-row">
            {report.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="macro-toolkit-shadow-report" aria-label="影子组合报告">
      <div className="macro-toolkit-shadow-report__head">
        <div>
          <span>只读影子组合</span>
          <strong>{report.as_of_date ?? "日期缺失"}</strong>
          <small>
            {report.completed_periods} 个完成调仓周期 / {report.benchmark?.label ?? "基准缺失"}
          </small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="blue">{report.rule_version}</Tag>
          {report.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      </div>
      <div className="macro-toolkit-shadow-report__grid">
        {report.portfolios.map((portfolio) => (
          <div className="macro-toolkit-shadow-card" key={portfolio.key}>
            <div className="macro-toolkit-capability-result-head">
              <span>{portfolio.role === "shadow_candidate" ? "影子观察" : "正式参照"}</span>
              <Tag color={portfolio.role === "shadow_candidate" ? "blue" : "default"}>{portfolio.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-card__metrics">
              <MetricTile label="总收益" value={formatSignedRatio(portfolio.total_return)} detail="不含生产替换" />
              <MetricTile label="超额" value={formatSignedRatio(portfolio.excess_return)} detail="相对因子池等权" />
              <MetricTile label="最大回撤" value={formatSignedRatio(portfolio.max_drawdown)} detail={`胜率 ${formatPlainRatio(portfolio.win_rate)}`} />
              <MetricTile label="估值" value={`PE ${formatNumberValue(portfolio.average_pe)}`} detail={`PB ${formatNumberValue(portfolio.average_pb)}`} />
            </div>
            <div className="macro-toolkit-strategy-trace">
              <span>
                <b>权重</b>
                {portfolioWeightsText(portfolio)}
              </span>
              <span>
                <b>约束</b>
                {portfolioConstraintText(portfolio)}
              </span>
              <span>
                <b>换手</b>
                {formatPlainRatio(portfolio.average_turnover)}
              </span>
              <span>
                <b>20bp</b>
                {costResultText(portfolio, 20)}
              </span>
              <span>
                <b>50bp</b>
                {costResultText(portfolio, 50)}
              </span>
            </div>
            {portfolio.latest_holdings.length ? (
              <div className="macro-toolkit-shadow-holdings">
                {portfolio.latest_holdings.slice(0, 5).map((holding) => (
                  <span key={`${portfolio.key}-${holding.stock_code}`}>
                    {holding.rank}. {holding.stock_code} · {holding.industry}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <ShadowPortfolioReview report={report} />
      <ShadowPortfolioEvidencePack report={report} />
    </div>
  );
}

function StrategySummaryCard({ strategy }: { strategy: MacroToolkitStrategySummary }) {
  const metric = strategy.primary_metric;
  const dataStatus = strategyDataStatus(strategy);
  const priceSource =
    typeof strategy.result.price_source === "string" && strategy.result.price_source.trim()
      ? strategy.result.price_source
      : "价格来源缺失";
  const factorSource =
    typeof strategy.result.factor_source === "string" && strategy.result.factor_source.trim()
      ? strategy.result.factor_source
      : "因子来源缺失";
  const warnings = strategy.warnings;
  const sourceVersions = strategyTraceList(strategy.result.source_versions);
  const vendorVersions = strategyTraceList(strategy.result.vendor_versions);
  const factorSourceVersions = strategyTraceList(strategy.result.factor_source_versions);
  const factorVendorVersions = strategyTraceList(strategy.result.factor_vendor_versions);
  const factorRuleVersions = strategyTraceList(strategy.result.factor_rule_versions);
  const factorRunIds = strategyTraceList(strategy.result.factor_run_ids);
  const missingFactorInputs = strategyTraceList(strategy.result.missing_factor_inputs, Number.POSITIVE_INFINITY);
  const asOfDate = strategyScalarText(strategy.result.as_of_date);
  const factorAsOfDate = strategyScalarText(strategy.result.factor_as_of_date);
  const factorDateStatus = strategyScalarText(strategy.result.factor_date_status);

  return (
    <div className={`macro-toolkit-strategy-card macro-toolkit-strategy-card--${strategy.tone}`}>
      <div className="macro-toolkit-capability-result-head">
        <span>{strategy.group}</span>
        <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
      </div>
      <strong>{strategy.label}</strong>
      <div className="macro-toolkit-strategy-metric">
        <span>{metric?.label ?? "状态"}</span>
        <b>{metric ? `${metric.value}${metric.unit}` : statusLabel(strategy.status)}</b>
      </div>
      <small>{strategy.evidence.slice(0, 2).join(" / ") || "暂无证据"}</small>
      <div className="macro-toolkit-strategy-trace" aria-label={`${strategy.label}策略追踪`}>
        <span>
          <b>数据状态</b>
          {statusLabel(dataStatus)} <em>{dataStatus}</em>
        </span>
        <span>
          <b>价格</b>
          {priceSource}
        </span>
        <span>
          <b>因子</b>
          {factorSource}
        </span>
        {asOfDate ? (
          <span>
            <b>行情日</b>
            {asOfDate}
          </span>
        ) : null}
        {factorAsOfDate ? (
          <span>
            <b>因子日</b>
            {factorAsOfDate}
            {factorDateStatus ? ` · ${statusLabel(factorDateStatus)}` : ""}
          </span>
        ) : null}
        {sourceVersions ? (
          <span>
            <b>价格版本</b>
            {sourceVersions}
          </span>
        ) : null}
        {vendorVersions ? (
          <span>
            <b>行情厂商</b>
            {vendorVersions}
          </span>
        ) : null}
        {factorSourceVersions ? (
          <span>
            <b>因子版本</b>
            {factorSourceVersions}
          </span>
        ) : null}
        {factorVendorVersions ? (
          <span>
            <b>因子厂商</b>
            {factorVendorVersions}
          </span>
        ) : null}
        {factorRuleVersions ? (
          <span>
            <b>因子规则</b>
            {factorRuleVersions}
          </span>
        ) : null}
        {factorRunIds ? (
          <span>
            <b>因子运行</b>
            {factorRunIds}
          </span>
        ) : null}
        {missingFactorInputs ? (
          <span>
            <b>缺失输入</b>
            {missingFactorInputs}
          </span>
        ) : null}
        {warnings.length ? (
          <div className="macro-toolkit-strategy-warnings">
            {warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function strategyTraceList(value: unknown, maxItems = 3) {
  if (!Array.isArray(value)) {
    return "";
  }
  const items = value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
  return (Number.isFinite(maxItems) ? items.slice(0, maxItems) : items).join(" / ");
}

function strategyScalarText(value: unknown) {
  if (typeof value !== "string" && typeof value !== "number") {
    return "";
  }
  return String(value).trim();
}

const A_SHARE_RISK_METRICS: Array<{
  key: string;
  label: string;
  format?: "percent" | "ratio";
}> = [
  { key: "up_count", label: "上涨家数" },
  { key: "up_ratio", label: "上涨比例", format: "percent" },
  { key: "drop_3_count", label: "跌超3%" },
  { key: "drop_5_count", label: "跌超5%" },
  { key: "limit_down_count", label: "跌停家数" },
  { key: "near_down_count", label: "近跌停" },
  { key: "turnover_ratio_ma20", label: "成交额/20日", format: "ratio" },
  { key: "index_drawdown_from_high", label: "回落幅度", format: "percent" },
];

function AShareRiskPanel({ risk }: { risk?: MacroToolkitAShareRiskPayload }) {
  if (!risk) {
    return (
      <div className="macro-toolkit-empty-output">
        市场踩踏风险数据未返回，当前不能形成风险等级判断。
      </div>
    );
  }
  const tone = riskLevelTone(risk.risk_level);
  const scoreText = risk.risk_score === null ? "缺失" : risk.risk_score;
  return (
    <div className={`macro-toolkit-a-share-risk macro-toolkit-a-share-risk--${tone}`}>
      <div className="macro-toolkit-a-share-risk__summary">
        <div className="macro-toolkit-capability-result-head">
          <span>
            <MacroStatusIcon tone={tone}>
              {tone === "negative" ? <WarningOutlined /> : <ClockCircleOutlined />}
            </MacroStatusIcon>
            {risk.trade_date ?? "日期缺失"}
          </span>
          <div className="macro-toolkit-tag-row">
            <Tag color={statusColor(risk.status)}>{statusLabel(risk.status)}</Tag>
            <Tag color={riskLevelColor(risk.risk_level)}>{risk.risk_name}</Tag>
          </div>
        </div>
        <strong>{scoreText}</strong>
        <ScoreTrack score={risk.risk_score} />
        <p title={risk.summary}>{compactText(risk.summary || "风险摘要缺失。", 38)}</p>
        <small title={risk.position_rule}>{compactText(risk.position_rule || "仓位规则缺失，不能据此放大仓位。", 30)}</small>
      </div>

      <div className="macro-toolkit-a-share-risk__metrics">
        {A_SHARE_RISK_METRICS.map((metric) => (
          <div className="macro-toolkit-strategy-metric" key={metric.key}>
            <span>{metric.label}</span>
            <b>{formatRiskMetric(risk.metrics[metric.key], metric.format)}</b>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-a-share-risk__lists">
        <RiskList title="触发规则" items={risk.triggered_rules} emptyText="未触发明确踩踏规则。" />
        <RiskList title="观察条件" items={risk.watch_next} emptyText="暂无下一步观察条件。" />
        <RiskList title="数据提示" items={risk.warnings} emptyText={risk.status === "complete" ? "数据能力完整。" : "降级原因缺失。"} />
      </div>
    </div>
  );
}

function RiskList({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  const visibleItems = items.length ? items : [emptyText];
  return (
    <div className="macro-toolkit-a-share-risk__list">
      <span>{title}</span>
      {visibleItems.slice(0, 4).map((item) => (
        <small key={item} title={item}>
          {compactText(item, 26)}
        </small>
      ))}
    </div>
  );
}

function formatRiskMetric(value: number | null | undefined, format?: "percent" | "ratio") {
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

function formatMetricDisplay(metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>) {
  return `${metric.label} ${metric.value}${metric.unit}`;
}

function MetricTile({
  icon,
  label,
  value,
  detail,
  detailTitle,
  tone = "neutral",
  testId,
  detailMaxLength = 26,
}: {
  icon?: ReactNode;
  label: string;
  value: string | number;
  detail: string;
  detailTitle?: string;
  tone?: "neutral" | "positive" | "missing";
  testId?: string;
  detailMaxLength?: number;
}) {
  return (
    <div className={`macro-toolkit-metric macro-toolkit-metric--${tone}`} data-testid={testId}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <InfoCircleOutlined />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detailTitle ?? detail}>{compactText(detail, detailMaxLength)}</small>
    </div>
  );
}
