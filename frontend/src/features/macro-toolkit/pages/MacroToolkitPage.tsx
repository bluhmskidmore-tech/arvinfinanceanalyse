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
import { cardVariants } from "@heroui/styles";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { flushSync } from "react-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import type {
  MacroToolkitCapabilityResult,
  MacroToolkitCffexRefreshRun,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitCommodityFuturesRefreshStatus,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitChoiceStockRefreshPermission,
  MacroToolkitAShareRiskPayload,
  MacroToolkitAnalysisPayload,
  MacroToolkitDataHealth,
  MacroToolkitHasonStrategy,
  MacroToolkitIndicator,
  MacroToolkitMacroEtfStrategySnapshot,
  MacroToolkitDualFrequencyCandidate,
  MacroToolkitOutputFile,
  MacroToolkitRunResponse,
  MacroToolkitScriptRecord,
  MacroToolkitScriptChainRun,
  MacroToolkitSignalCard,
  MacroToolkitShadowPortfolio,
  MacroToolkitShadowPortfolioHolding,
  MacroToolkitShadowPortfolioPeriodReturn,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSourceBackfillRefreshRun,
  MacroToolkitSourceCheck,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import {
  DataStatusStrip,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import {
  MT_SHELL_MAIN,
  MT_SHELL_NUM,
  MT_SHELL_PAGE,
  MT_SHELL_STATUS_PILL,
  MT_SHELL_STATUS_ROW,
  MT_SHELL_TITLE,
  MT_SHELL_TITLE_BRAND,
  MT_SHELL_TOPBAR,
  MT_SHELL_TOPBAR_LEFT,
  MT_SHELL_TOPBAR_RIGHT,
} from "../lib/macroToolkitPageChrome";
import { isEvidenceBookRowPending } from "../lib/macroToolkitCommitteeEvidence";

import { formatCrisisTopContributorSummary } from "../lib/crisisScoreDisplay";

import "./MacroToolkitPage.css";

import {
  MacroStatusIcon,
  MetricTile,
  compactText,
  formatPercent,
  observationStatusLabel,
  statusColor,
  statusLabel,
} from "../lib/macroToolkitPanelShared";
import {
  buildCrisisGapRepairFeedback,
  canRefreshMacroSourceBackfill,
  commodityRefreshRunProducts,
  crisisCommodityShortItemsFromEnvelope,
  crisisCommodityShortItemsFromResult,
  crisisGapGroupFromResult,
  formatCommodityProducts,
  formatCommodityRefreshActionLabel,
  formatCommodityRefreshResult,
  formatCommodityShortfallChangeList,
  formatCommodityShortfallChanges,
  formatCommodityShortfallEstimates,
  formatCommodityShortfallEstimateList,
  formatNumberValue,
  formatValue,
  isCrisisComponent,
  normalizeInputEvidence,
  normalizeMacroSourceBackfillAlias,
  suggestedCommodityRefreshStartDate,
} from "../lib/macroToolkitCrisisSupport";
import type {
  CommodityRefreshEvidenceChain,
  CommodityShortfallChange,
  CommodityShortfallEstimate,
  CrisisGapRepairFeedback,
  CrisisGapGroup,
} from "../lib/macroToolkitCrisisSupport";
import { CrisisScoreEvidencePanel, CommodityRefreshResultPanel } from "../panels/MacroToolkitCrisisPanels";
import { MacroToolkitModelChainPanel } from "../panels/MacroToolkitModelChainPanel";
import { MacroToolkitReportBundlePanel } from "../panels/MacroToolkitReportBundlePanel";
import {
  HasonMacroStrategyPanel,
  ModelSignalMatrix,
  deriveModelReadinessFromHasonStrategy,
} from "../panels/MacroToolkitSignalPanels";

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
const MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN = "800px 0px";
const MACRO_TOOLKIT_READ_STALE_MS = 60_000;
const MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS = 1_500;
const MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT = 430;
const MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE = 7;
type MacroToolkitDeferredContentStage = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

const MACRO_TOOLKIT_DEFERRED_TARGET_STAGES: Record<
  string,
  MacroToolkitDeferredContentStage
> = {
  "#macro-toolkit-strategy-detail": 3,
  "#macro-toolkit-model-readiness-detail": 4,
  "#macro-toolkit-crisis-detail": 4,
  "#macro-toolkit-analysis-detail": 5,
  "#macro-toolkit-data-health-detail": 5,
  "#macro-toolkit-operations-actions": 6,
  "#macro-toolkit-operations-console": 6,
  "#macro-toolkit-tool-execution-detail": 7,
  "#macro-toolkit-cffex-detail": 7,
  "#macro-toolkit-commodity-detail": 7,
  "#macro-toolkit-script-artifact-detail": 7,
};

function macroToolkitDeferredContentStageForHref(
  href: string,
): MacroToolkitDeferredContentStage | null {
  return MACRO_TOOLKIT_DEFERRED_TARGET_STAGES[href] ?? null;
}
const MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY = [
  "macro-toolkit",
  "analysis",
  "full",
  MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
] as const;
const MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT = 4;
const MACRO_TOOLKIT_HERO_CARD_SLOTS = cardVariants({ variant: "default" });
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

type MacroToolkitPageMode = "toolkit" | "observation";
type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];
type CommodityRefreshOptions = {
  dryRun?: boolean;
  products?: string[];
  suggestedSelection?: string[];
  startDate?: string;
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

type MacroToolkitPageProps = {
  mode?: MacroToolkitPageMode;
};

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

function chainRunAlertType(status: string): "success" | "warning" | "error" | "info" {
  if (status === "failed" || status === "timeout") return "error";
  if (status === "degraded") return "warning";
  if (status === "completed" || status === "dry_run") return "success";
  return "info";
}

type RefreshFeedbackTone = "success" | "warning" | "info";

const CFFEX_REFRESH_TERMINAL_STATUSES = new Set(["completed", "partial", "failed"]);
const SOURCE_BACKFILL_TERMINAL_STATUSES = new Set([
  "completed",
  "partial",
  "no_rows",
  "blocked",
  "failed",
]);

function isCffexRefreshTerminal(status: string) {
  return CFFEX_REFRESH_TERMINAL_STATUSES.has(status);
}

function isSourceBackfillTerminal(status: string) {
  return SOURCE_BACKFILL_TERMINAL_STATUSES.has(status);
}

function asyncRefreshPendingMessage(subject: string, status: string) {
  const statusLabel =
    status === "queued"
      ? "已排队"
      : status === "running"
        ? "执行中"
        : status === "retrying"
          ? "重试中"
          : status;
  return `${subject}${statusLabel}，等待后台任务完成`;
}

function refreshFailureMessage(subject: string, failureCategory: string | null | undefined) {
  return failureCategory ? `${subject}失败（类别：${failureCategory}）` : `${subject}失败`;
}

function cffexRefreshTerminalMessage(refresh: MacroToolkitCffexRefreshRun) {
  const rowCount = refresh.row_count == null ? "行数待确认" : `${refresh.row_count} 行`;
  const tradeDate = refresh.trade_date ?? refresh.report_date ?? "日期缺失";
  return refresh.status === "partial"
    ? `席位刷新部分完成：${rowCount}，交易日 ${tradeDate}；部分来源未完成，请复核`
    : `刷新完成：${rowCount}，交易日 ${tradeDate}`;
}

function sourceBackfillTerminalMessage(refresh: MacroToolkitSourceBackfillRefreshRun) {
  if (refresh.status === "partial") {
    const added = refresh.total_added == null ? "新增行数待确认" : `新增 ${refresh.total_added} 行`;
    return `来源补齐部分完成：${refresh.alias} ${added}，请复核未完成来源`;
  }
  if (refresh.status === "no_rows") {
    return `来源补齐未新增数据：${refresh.alias}，请复核日期范围和数据源`;
  }
  if (refresh.status === "blocked") {
    return `来源补齐受阻：${refresh.alias}，请复核权限、来源和任务状态`;
  }
  const added = refresh.total_added == null ? "新增行数待确认" : `新增 ${refresh.total_added} 行`;
  return `来源补齐完成：${refresh.alias} ${added}`;
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
  if (
    href === "#macro-toolkit-tool-execution-detail" ||
    href === "#macro-toolkit-cffex-detail" ||
    href === "#macro-toolkit-commodity-detail" ||
    href === "#macro-toolkit-script-artifact-detail" ||
    href === "#macro-toolkit-strategy-detail" ||
    href === "#macro-toolkit-operations-actions" ||
    href === "#macro-toolkit-operations-console"
  ) {
    return "execution";
  }
  return "evidence";
}

function committeeWorkQueueExecutionHref(item: MacroToolkitCommitteeChecklistItem) {
  if (item.key === "tool-execution") return "#macro-toolkit-operations-actions";
  return item.href;
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

function formatSignalCardScore(card: MacroToolkitSignalCard): string | number {
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
            <b>{signal ? formatSignalCardScore(signal) : isLoading ? "加载中" : "待确认"}</b>
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

function formatChange(change: number | null, changePct: number | null) {
  if (change === null && changePct === null) {
    return "无可比";
  }
  if (changePct !== null) {
    return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  }
  return `${change! >= 0 ? "+" : ""}${change!.toFixed(4)}`;
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
  const deferredContentSentinelRef = useRef<HTMLDivElement | null>(null);
  const [deferredContentStage, setDeferredContentStage] =
    useState<MacroToolkitDeferredContentStage>(() =>
      !showOperations
        ? MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
        : typeof window !== "undefined"
          ? (macroToolkitDeferredContentStageForHref(window.location.hash) ?? 0)
          : 0,
  );
  const [pendingDeferredHashTarget, setPendingDeferredHashTarget] = useState<
    string | null
  >(() =>
    showOperations &&
    typeof window !== "undefined" &&
    macroToolkitDeferredContentStageForHref(window.location.hash) !== null
      ? window.location.hash
      : null,
  );
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedGovernanceFocus, setSelectedGovernanceFocus] =
    useState<MacroToolkitGovernanceFocusKey>("evidence");
  const [actionReceipt, setActionReceipt] = useState<MacroToolkitActionReceipt>(EMPTY_ACTION_RECEIPT);
  const [actionReceipts, setActionReceipts] = useState<MacroToolkitActionReceipt[]>([]);
  const [confirmedReceiptIds, setConfirmedReceiptIds] = useState<Set<string>>(() => new Set());
  const [selectedEvidenceHref, setSelectedEvidenceHref] = useState<string | null>(null);
  const [selectedExecutionHref, setSelectedExecutionHref] = useState<string | null>(null);
  const [receiptTechnicalDetailsExpanded, setReceiptTechnicalDetailsExpanded] = useState(
    () =>
      showOperations &&
      typeof window !== "undefined" &&
      window.location.hash === "#macro-toolkit-script-artifact-detail",
  );
  const [focusedRepairKey, setFocusedRepairKey] = useState<string | null>(null);
  const [committeeActionLocatorKey, setCommitteeActionLocatorKey] = useState<string | null>(null);
  const committeeActionLocatorRef = useRef<HTMLDivElement | null>(null);
  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [chainRunResult, setChainRunResult] = useState<MacroToolkitScriptChainRun | null>(null);
  const [chainRunError, setChainRunError] = useState<string | null>(null);
  const [chainRunModelId, setChainRunModelId] = useState<string | null>(null);
  const [isRunningChain, setIsRunningChain] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshFeedbackTone, setRefreshFeedbackTone] = useState<RefreshFeedbackTone>("success");
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
  const [stockRefreshResult, setStockRefreshResult] = useState<string | null>(null);
  const [stockRefreshError, setStockRefreshError] = useState<string | null>(null);
  const [isRefreshingChoiceStock, setIsRefreshingChoiceStock] = useState(false);
  const [sourceBackfillResult, setSourceBackfillResult] = useState<string | null>(null);
  const [sourceBackfillError, setSourceBackfillError] = useState<string | null>(null);
  const [sourceBackfillFeedbackTone, setSourceBackfillFeedbackTone] =
    useState<RefreshFeedbackTone>("success");
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

  const revealAllDeferredContent = useCallback(() => {
    if (!showOperations) {
      return;
    }
    setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
    setReceiptTechnicalDetailsExpanded(true);
  }, [showOperations]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const handleBeforePrint = () => {
      flushSync(revealAllDeferredContent);
    };
    window.addEventListener("beforeprint", handleBeforePrint);
    return () => window.removeEventListener("beforeprint", handleBeforePrint);
  }, [revealAllDeferredContent, showOperations]);

  useEffect(() => {
    if (
      !showOperations ||
      deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
    ) {
      return undefined;
    }

    const sentinel = deferredContentSentinelRef.current;
    if (typeof window.IntersectionObserver === "undefined" || !sentinel) {
      setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
      return undefined;
    }

    const nextStage = (deferredContentStage + 1) as MacroToolkitDeferredContentStage;
    const observer = new window.IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          setDeferredContentStage((currentStage) =>
            Math.max(currentStage, nextStage) as MacroToolkitDeferredContentStage,
          );
          observer.disconnect();
        }
      },
      {
        rootMargin:
          deferredContentStage === MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE - 1
            ? "0px"
            : MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN,
        threshold: 0.01,
      },
    );
    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [deferredContentStage, showOperations]);

  const revealDeferredContentForHref = useCallback(
    (href: string | null) => {
      if (!showOperations || !href) {
        return;
      }
      const requestedStage = macroToolkitDeferredContentStageForHref(href);
      if (requestedStage === null) {
        return;
      }
      if (href === "#macro-toolkit-script-artifact-detail") {
        setReceiptTechnicalDetailsExpanded(true);
      }
      setDeferredContentStage((currentStage) =>
        Math.max(currentStage, requestedStage) as MacroToolkitDeferredContentStage,
      );
    },
    [showOperations],
  );

  const syncDeferredContentSelectionForHref = useCallback((href: string) => {
    if (macroToolkitDeferredContentStageForHref(href) === null) {
      return;
    }
    if (
      href === "#macro-toolkit-operations-actions" ||
      href === "#macro-toolkit-operations-console"
    ) {
      setSelectedExecutionHref(href);
    } else {
      setSelectedEvidenceHref(href);
    }
    setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
  }, []);

  useEffect(() => {
    revealDeferredContentForHref(selectedExecutionHref);
    revealDeferredContentForHref(selectedEvidenceHref);
  }, [
    revealDeferredContentForHref,
    selectedEvidenceHref,
    selectedExecutionHref,
  ]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const revealHashTarget = () => {
      const href = window.location.hash;
      setPendingDeferredHashTarget(
        macroToolkitDeferredContentStageForHref(href) !== null ? href : null,
      );
      syncDeferredContentSelectionForHref(href);
      revealDeferredContentForHref(href);
    };
    revealHashTarget();
    window.addEventListener("hashchange", revealHashTarget);
    return () => window.removeEventListener("hashchange", revealHashTarget);
  }, [
    revealDeferredContentForHref,
    showOperations,
    syncDeferredContentSelectionForHref,
  ]);

  useEffect(() => {
    if (
      !showOperations ||
      !pendingDeferredHashTarget?.startsWith("#macro-toolkit-")
    ) {
      return undefined;
    }
    const requestedStage = macroToolkitDeferredContentStageForHref(
      pendingDeferredHashTarget,
    );
    if (
      requestedStage === null ||
      deferredContentStage < requestedStage ||
      (pendingDeferredHashTarget === "#macro-toolkit-script-artifact-detail" &&
        !receiptTechnicalDetailsExpanded)
    ) {
      return undefined;
    }

    let frame: number | null = null;
    const scrollToHashTarget = () => {
      const target = document.getElementById(pendingDeferredHashTarget.slice(1));
      if (typeof target?.scrollIntoView !== "function") {
        return false;
      }
      target.scrollIntoView({ block: "start", inline: "nearest" });
      setPendingDeferredHashTarget((currentTarget) =>
        currentTarget === pendingDeferredHashTarget ? null : currentTarget,
      );
      return true;
    };
    const scheduleScroll = () => {
      if (typeof window.requestAnimationFrame === "function") {
        frame = window.requestAnimationFrame(() => {
          scrollToHashTarget();
        });
        return;
      }
      scrollToHashTarget();
    };
    if (document.getElementById(pendingDeferredHashTarget.slice(1))) {
      scheduleScroll();
      return () => {
        if (frame !== null) {
          window.cancelAnimationFrame(frame);
        }
      };
    }
    if (typeof window.MutationObserver === "undefined") {
      scheduleScroll();
      return undefined;
    }
    const observer = new window.MutationObserver(() => {
      if (!document.getElementById(pendingDeferredHashTarget.slice(1))) {
        return;
      }
      observer.disconnect();
      scheduleScroll();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [
    deferredContentStage,
    pendingDeferredHashTarget,
    receiptTechnicalDetailsExpanded,
    showOperations,
  ]);

  const handleDeferredContentLinkClick = useCallback(
    (event: ReactMouseEvent<HTMLElement>) => {
      if (!showOperations) {
        return;
      }
      const target = event.target;
      const anchor =
        target instanceof Element
          ? target.closest<HTMLAnchorElement>('a[href^="#macro-toolkit-"]')
          : null;
      if (anchor) {
        const href = anchor.getAttribute("href");
        if (!href || macroToolkitDeferredContentStageForHref(href) === null) {
          return;
        }
        setPendingDeferredHashTarget(href);
        syncDeferredContentSelectionForHref(href);
        revealDeferredContentForHref(href);
      }
    },
    [
      revealDeferredContentForHref,
      showOperations,
      syncDeferredContentSelectionForHref,
    ],
  );

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

  const modelChainQuery = useQuery({
    queryKey: ["macro-toolkit", "model-chain-results"],
    queryFn: ({ signal }) => client.fetchMacroToolkitModelChainResults({ signal }),
    enabled: showOperations,
    staleTime: MACRO_TOOLKIT_READ_STALE_MS,
  });

  const fetchFullAnalysis = useCallback(
    () =>
      client.getMacroToolkitAnalysis({
        detail: "full",
        historyLimit: MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
      }),
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
  const macroEtfStrategy = strategyPayload?.macro_etf_strategy ?? null;
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
  const decisionSummaryResult = capabilityResults.find((result) => result.key === "decision_summary") ?? null;
  const degradedResultCount = capabilityResults.filter((result) => result.status !== "complete").length;
  const missingIndicatorCount = analysis?.indicators.filter((indicator) => indicator.quality === "missing").length ?? 0;
  const analysisSignalCards = analysis?.signal_cards ?? [];
  // 脚本产物等运维元信息不进入核心信号区；产物状态保留在深度证据入口与执行区。
  const analyticalSignalCards = analysisSignalCards.filter((card) => !isObservationOutputSignal(card));
  const visibleSignalCards = analyticalSignalCards;
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
    isRunningChain ||
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
  const workflowAnalysisState = isCoreAnalysis ? `core · 待完整分析 ${runtimeSections.length}` : "full · 完整分析";
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
    const isPending = !isBlocking && isEvidenceBookRowPending(row.support, row.gap);
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
  const committeeWorkQueueBlockCount = committeeWorkQueueItems.filter((item) => item.status === "block").length;
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
  const committeeDecisionActionCurrent =
    committeeDecisionHref === "#macro-toolkit-operations-actions"
      ? selectedExecutionHref === committeeDecisionHref
      : selectedEvidenceHref === committeeDecisionHref;
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
  const observationDecisionSummary =
    !showOperations && analysis ? (
      <div
        className="macro-toolkit-observation-decision"
        data-testid="macro-observation-decision-summary"
        aria-label="宏观决策摘要主结论"
      >
        {decisionSummaryResult ? (
          <>
            <CapabilityResultCard result={decisionSummaryResult} />
            {decisionSummaryResult.warnings.length ? (
              <Alert
                type="warning"
                showIcon
                message="决策摘要限制"
                description={decisionSummaryResult.warnings.join(" / ")}
              />
            ) : null}
          </>
        ) : (
          <Alert
            type="info"
            showIcon
            message="宏观决策摘要暂未返回"
            description={
              isCoreAnalysis
                ? "核心分析已先返回；决策摘要需打开完整分析后确认。"
                : "后端未返回决策摘要结果，本页不推导宏观结论。"
            }
          />
        )}
      </div>
    ) : null;
  const observationFirstScreenLoop =
    !showOperations ? (
      <div
        className={MACRO_TOOLKIT_HERO_CARD_SLOTS.base({
          className: "macro-toolkit-observation-loop border border-default-200 bg-content1 text-foreground",
        })}
        aria-label="宏观观察首屏闭环"
        data-slot="card"
      >
        <div
          className={MACRO_TOOLKIT_HERO_CARD_SLOTS.header({ className: "macro-toolkit-observation-loop__head p-0" })}
          data-slot="card-header"
        >
          <span>观察闭环</span>
          <strong>{analysis?.as_of_date ?? "日期待确认"}</strong>
        </div>
        <div
          className={MACRO_TOOLKIT_HERO_CARD_SLOTS.content({ className: "macro-toolkit-observation-loop__grid p-0" })}
          data-slot="card-content"
        >
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
    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await queryClient.fetchQuery({
            queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
            queryFn: fetchFullAnalysis,
            staleTime: MACRO_TOOLKIT_READ_STALE_MS,
          });
          if (!cancelled) {
            setFullAnalysisEnvelope(response);
          }
        } catch {
          // Keep the core screen until the user explicitly retries full analysis.
        }
      })();
    }, MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
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
      setSourceBackfillFeedbackTone("info");
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
        const refresh = await runPollingTask({
          start: async () => {
            const response = await client.refreshMacroSourceBackfill({
              alias,
              endDate: item.reference_date ?? analysis?.as_of_date ?? undefined,
              sources: undefined,
            });
            return {
              ...response.result.refresh,
              report_date: response.result.refresh.report_date ?? undefined,
              source_version: response.result.refresh.source_version ?? undefined,
            };
          },
          getStatus: async (runId) => {
            const response = await client.getMacroSourceBackfillRefreshStatus(runId);
            return {
              ...response.result.refresh,
              report_date: response.result.refresh.report_date ?? undefined,
              source_version: response.result.refresh.source_version ?? undefined,
            };
          },
          intervalMs: 5_000,
          maxAttempts: 240,
          isTerminal: isSourceBackfillTerminal,
          onUpdate: (payload) => {
            if (isSourceBackfillTerminal(payload.status)) return;
            setSourceBackfillFeedbackTone("info");
            setSourceBackfillResult(asyncRefreshPendingMessage("来源补齐", payload.status));
          },
        });
        if (refresh.status === "failed") {
          throw new Error(refreshFailureMessage("来源补齐", refresh.failure_category));
        }
        const isCompleted = refresh.status === "completed";
        const isPartial = refresh.status === "partial";
        const resultMessage = sourceBackfillTerminalMessage(refresh);
        setSourceBackfillFeedbackTone(isCompleted ? "success" : "warning");
        setSourceBackfillResult(resultMessage);
        recordActionReceipt({
          id: receiptId,
          ...receiptDecision,
          action: "来源补齐",
          status: isCompleted ? "completed" : "warning",
          time: "刚刚",
          target: alias,
          artifact: resultMessage,
          nextStep: isCompleted ? "重读完整分析并复核数据健康" : "复核未完成来源，数据健康保持阻断",
        });
        if (isCompleted || isPartial) {
          await clearFullAnalysisCache({ preserveCrisisGapRepairFeedback: Boolean(gapGroup) });
          const reloaded = await loadFullAnalysis();
          if (gapGroup) {
            const reloadedFeedback = buildCrisisGapRepairFeedback(gapGroup, reloaded, resultMessage);
            setCrisisGapRepairFeedback(
              isPartial
                ? {
                    ...reloadedFeedback,
                    status: "partial",
                    message: "来源补齐部分完成，完整分析已重读",
                  }
                : reloadedFeedback,
            );
          }
        } else if (gapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: gapGroup.key,
            groupLabel: gapGroup.label,
            status: "partial",
            message: refresh.status === "blocked" ? "来源补齐受阻，缺口仍需处理" : "来源未返回可补齐数据",
            detail: resultMessage,
          });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "来源补齐失败";
        setSourceBackfillError(errorMessage);
        setSourceBackfillResult(null);
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

  const runScriptChain = useCallback(async (dryRun: boolean, modelId?: string) => {
    const receiptId = nextActionReceiptId(dryRun ? "script-chain-dry-run" : "script-chain");
    const receiptDecision = actionReceiptDecisionFields("script");
    setChainRunModelId(modelId ?? null);
    setIsRunningChain(true);
    setChainRunError(null);
    setChainRunResult(null);
    recordActionReceipt({
      id: receiptId,
      ...receiptDecision,
      action: dryRun ? "预检模型运行链" : "运行模型链",
      status: "running",
      time: "进行中",
      target: "macro_toolkit_chain",
      artifact: payload?.output_dir ?? "data/macro_toolkit/output",
      nextStep: dryRun ? "核对 manifest 与 expected_outputs" : "等待模型链返回后核对产物回执",
    });
    try {
      const response = await client.runMacroToolkitScriptChain({ dryRun });
      const result = response.result.run;
      setChainRunResult(result);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预检模型运行链" : "运行模型链",
        status: result.status === "completed" || result.status === "dry_run" ? "completed" : "warning",
        time: "刚刚",
        target: "macro_toolkit_chain",
        artifact: `步骤 ${result.receipts.length}/${result.manifest.length} · 缺口 ${result.readiness_after.degraded_count}`,
        nextStep: "核对 model_readiness 与 receipts",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "模型链运行失败";
      setChainRunError(errorMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: dryRun ? "预检模型运行链" : "运行模型链",
        status: "failed",
        time: "刚刚",
        target: "macro_toolkit_chain",
        artifact: errorMessage,
        nextStep: "检查执行权限、脚本依赖和运行链回执",
      });
    } finally {
      setIsRunningChain(false);
    }
  }, [
    analysisQuery,
    clearFullAnalysisCache,
    client,
    loadFullAnalysis,
    payload?.output_dir,
    recordActionReceipt,
    scriptsQuery,
    strategyQuery,
  ]);

  const refreshCffexMemberRank = useCallback(async () => {
    const receiptId = nextActionReceiptId("cffex");
    const receiptDecision = actionReceiptDecisionFields("cffex");
    setIsRefreshingCffex(true);
    setRefreshError(null);
    setRefreshResult(null);
    setRefreshFeedbackTone("info");
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
      const refresh = await runPollingTask({
        start: async () => {
          const response = await client.refreshCffexMemberRank({
            tradeDate: analysis?.as_of_date ?? undefined,
          });
          return {
            ...response.result.refresh,
            report_date: response.result.refresh.report_date ?? undefined,
            source_version: response.result.refresh.source_version ?? undefined,
          };
        },
        getStatus: async (runId) => {
          const response = await client.getCffexMemberRankRefreshStatus(runId);
          return {
            ...response.result.refresh,
            report_date: response.result.refresh.report_date ?? undefined,
            source_version: response.result.refresh.source_version ?? undefined,
          };
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        isTerminal: isCffexRefreshTerminal,
        onUpdate: (payload) => {
          if (isCffexRefreshTerminal(payload.status)) return;
          setRefreshFeedbackTone("info");
          setRefreshResult(asyncRefreshPendingMessage("CFFEX席位刷新", payload.status));
        },
      });
      if (refresh.status === "failed") {
        throw new Error(refreshFailureMessage("CFFEX席位刷新", refresh.failure_category));
      }
      const isCompleted = refresh.status === "completed";
      const resultMessage = cffexRefreshTerminalMessage(refresh);
      setRefreshFeedbackTone(isCompleted ? "success" : "warning");
      setRefreshResult(resultMessage);
      recordActionReceipt({
        id: receiptId,
        ...receiptDecision,
        action: "刷新 CFFEX 席位",
        status: isCompleted ? "completed" : "warning",
        time: "刚刚",
        target: "CFFEX 席位",
        artifact: resultMessage,
        nextStep: isCompleted ? "核对 CFFEX席位状态" : "复核未完成来源，席位状态保持待确认",
      });
      await clearFullAnalysisCache();
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
      await loadFullAnalysis();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "刷新席位失败";
      setRefreshError(errorMessage);
      setRefreshResult(null);
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
        throw new Error(
          refreshFailureMessage("股票刷新", refresh.failure_category),
        );
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

  const committeeDecisionButtonAction = hasDataHealthRepairReceiptPending && completedDataHealthReceipt
    ? {
        label: "复核数据健康回执",
        onClick: () => {
          focusDataHealthRepair();
          confirmActionReceipt(completedDataHealthReceipt.id);
        },
        busy: false,
        status: "确认签核",
      }
    : hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem?.key === "strategy-supply"
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
  const renderCommitteeDecisionAction = (variant: "tile") => {
    const actionInner = committeeDecisionButtonAction?.label ?? committeeDecisionAction;

    if (committeeDecisionButtonAction) {
      return (
        <button
          type="button"
          className={`macro-toolkit-committee-action macro-toolkit-committee-action--${variant}`}
          disabled={committeeDecisionButtonAction.busy}
          aria-current={committeeDecisionActionCurrent ? "true" : undefined}
          aria-label={committeeDecisionButtonAction.label}
          onClick={committeeDecisionButtonAction.onClick}
        >
          {actionInner}
          <small>{committeeDecisionButtonAction.status}</small>
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
      const isQueuedRefresh = refresh.status === "queued";
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
      if (isQueuedRefresh) {
        setCommodityEvidenceReloadMessage("商品期货刷新已排队，等待后台任务完成。");
        if (commodityGapGroup) {
          setCrisisGapRepairFeedback({
            groupKey: commodityGapGroup.key,
            groupLabel: commodityGapGroup.label,
            status: "pending",
            message: "商品期货刷新已排队。",
            detail: formatCommodityRefreshResult(refresh),
          });
        }
        await scriptsQuery.refetch();
        return;
      }
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
      title: "近期走势",
      key: "recent_points",
      width: 140,
      render: (_, item) => <IndicatorSparkline item={item} />,
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
        eyebrow={showOperations ? "信号" : "总览"}
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
            <strong>{formatSignalCardScore(card)}</strong>
            <ScoreTrack score={card.score} />
            {card.key === "crisis_score_cn" && crisisScoreResult
              ? (() => {
                  const rawComponents = Array.isArray(crisisScoreResult.result?.components)
                    ? crisisScoreResult.result.components.filter(isCrisisComponent)
                    : [];
                  const summary = formatCrisisTopContributorSummary(rawComponents);
                  return summary ? (
                    <small className="macro-toolkit-signal-component-summary" data-testid="macro-toolkit-crisis-signal-component-summary">
                      {summary}
                    </small>
                  ) : null;
                })()
              : null}
            <small>{showOperations ? card.evidence.join(" / ") : formatObservationEvidence(card.evidence)}</small>
          </div>
        ))}
      </div>
    </section>
  ) : null;
  const riskSection = analysis ? (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow={showOperations ? "风险" : "预警"}
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
      <PageSectionLead eyebrow="策略" title="策略展示" description={strategyDescription} />
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
      {macroEtfStrategy ? <DualFrequencyRiskBudgetPanel snapshot={macroEtfStrategy} /> : null}
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
        eyebrow="指标"
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
        eyebrow="结果"
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
    <HasonMacroStrategyPanel
      strategy={hasonStrategy}
      modelReadiness={analysis?.model_readiness}
      variant={showOperations ? "detail" : "observation"}
    />
  ) : null;
  const modelSignalReadiness = analysis?.model_readiness?.length
    ? analysis.model_readiness
    : hasonStrategySection && analysis?.hason_strategy
      ? deriveModelReadinessFromHasonStrategy(analysis.hason_strategy)
      : [];
  const modelSignalMatrixSection = modelSignalReadiness.length ? (
    <ModelSignalMatrix
      modelReadiness={modelSignalReadiness}
      readinessSummary={analysis?.readiness_summary}
      chainRunResult={chainRunResult}
      chainRunError={chainRunError}
      chainRunModelId={chainRunModelId}
      isRunningChain={isRunningChain}
      showActions={showOperations}
      onRunChain={runScriptChain}
    />
  ) : null;
  const modelChainResults = modelChainQuery.data?.result;
  const modelChainSection = modelChainResults?.steps.length ? (
    <MacroToolkitModelChainPanel results={modelChainResults} />
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
  const analysisEvidenceFlow = analysis ? (
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
            aria-label={showOperations ? "分析证据与数据健康" : undefined}
          >
            <div
              className={
                showOperations
                  ? "macro-toolkit-evidence-review-flow__detail"
                  : "macro-toolkit-observation-evidence__contents"
              }
              aria-label={showOperations ? "分析证据详情" : undefined}
            >
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
              {sourceBackfillResult ? (
                <Alert type={sourceBackfillFeedbackTone} showIcon message={sourceBackfillResult} />
              ) : null}
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
    </>
  ) : null;
  const investmentBriefPanel = showOperations ? (
    <div
      className="macro-toolkit-investment-brief"
      data-testid="macro-toolkit-investment-brief"
      aria-label="宏观工具投委会摘要"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>投委会门禁</span>
        <strong>{analysis?.as_of_date ?? "日期待确认"}</strong>
      </div>
      <section className="macro-toolkit-submission-cockpit" aria-label="投委会提交门禁">
        <div className="macro-toolkit-submission-cockpit__verdict">
          <span>提交判断</span>
          <strong>{committeeFinalSignoffStatus}</strong>
          <small>{committeeFinalGateOutcome}</small>
        </div>
        <div className="macro-toolkit-submission-cockpit__owner">
          <span>责任人</span>
          <strong>{committeeFinalSignoffOwner}</strong>
          <small>{committeeDecisionBlocker}</small>
        </div>
        <div className="macro-toolkit-submission-cockpit__metrics">
          <div>
            <span>提交包</span>
            <strong>{committeeFinalPackValue}</strong>
          </div>
          <div>
            <span>签核</span>
            <strong>{committeeFinalSignoffValue}</strong>
          </div>
          <div>
            <span>剩余风险</span>
            <strong>{committeeFinalResidualRiskValue}</strong>
          </div>
          <div>
            <span>待复核回执</span>
            <strong>{committeeFinalReceiptReviewValue}</strong>
          </div>
        </div>
        <div className="macro-toolkit-submission-cockpit__lanes" aria-label="投委会提交链路总览">
          {committeeChecklistItems.map((item) => {
            const href = committeePackItemByKey.get(item.key)?.receipt?.evidenceHref ?? item.href;
            const actionLabel = item.key === "data-health" && item.status === "block" ? "处理数据缺口" : item.action;
            return (
              <a
                key={item.key}
                className={`macro-toolkit-submission-cockpit__lane macro-toolkit-submission-cockpit__lane--${item.status}`}
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
                <span>{item.condition}</span>
                <strong>{item.statusLabel}</strong>
                <small>{item.owner}</small>
                <em>{actionLabel}</em>
              </a>
            );
          })}
        </div>
        <div className="macro-toolkit-submission-cockpit__action">
          {renderCommitteeDecisionAction("tile")}
        </div>
      </section>
    </div>
  ) : null;
  const governanceGatePanel = showOperations ? (
    <div
      className="macro-toolkit-governance-gate"
      data-testid="macro-toolkit-governance-gate"
      aria-label="宏观工具口径与数据闸门"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>治理闸门</span>
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
          <span>操作台</span>
          <strong>{selectedScript?.name ?? "脚本注册表读取中"}</strong>
          <small>执行脚本、刷新数据源、确认产物状态。</small>
        </div>
        <Tag color={scripts.length > 0 && availableScriptCount === scripts.length ? "green" : "gold"}>
          脚本 {availableScriptCount}/{scripts.length}
        </Tag>
      </div>
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
          icon={<InfoCircleOutlined />}
          loading={isRunningChain}
          disabled={isOperationActionBusy && !isRunningChain}
          onClick={() => void runScriptChain(true)}
        >
          预检模型链
        </Button>
        <Button
          icon={<PlayCircleOutlined />}
          loading={isRunningChain}
          disabled={isOperationActionBusy && !isRunningChain}
          onClick={() => void runScriptChain(false)}
        >
          运行模型链
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
      {refreshResult ? <Alert type={refreshFeedbackTone} showIcon message={refreshResult} /> : null}
      {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
      {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
      {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
      {chainRunResult ? (
        <Alert
          type={chainRunAlertType(chainRunResult.status)}
          showIcon
          message={`模型链：${chainRunResult.status}`}
          description={`步骤 ${chainRunResult.receipts.length}/${chainRunResult.manifest.length} · 产物支撑 ${chainRunResult.readiness_after.artifact_backed_count}/${chainRunResult.readiness_after.total_count} · 仅观察`}
        />
      ) : null}
      {chainRunError ? <Alert type="error" showIcon message={chainRunError} /> : null}
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
    <section
      className={`${MT_SHELL_PAGE} macro-toolkit-page theme-dh-api`}
      data-testid="macro-toolkit-page"
    >
      <header
        className={`${MT_SHELL_TOPBAR} macro-toolkit-page__header`}
        data-testid="macro-toolkit-toolbar"
      >
        <div className={`${MT_SHELL_TOPBAR_LEFT} macro-toolkit-page__header-main`}>
          <div className={MT_SHELL_TITLE_BRAND}>
            <h1 className={MT_SHELL_TITLE}>{showOperations ? "宏观工具" : "宏观分析结果"}</h1>
          </div>
          <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__badge`}>
            {showOperations ? "工具控制台" : "只读观察"}
          </span>
          <div className={`${MT_SHELL_STATUS_ROW} macro-toolkit-page__toolbar-info`} aria-label="宏观工具状态">
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <ClockCircleOutlined aria-hidden="true" />
              观察日{" "}
              <span className={MT_SHELL_NUM}>{analysis?.as_of_date ?? "DATE_MISSING"}</span>
            </span>
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <SafetyCertificateOutlined aria-hidden="true" />
              门禁 {committeeDecisionStatus}
            </span>
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <DatabaseOutlined aria-hidden="true" />
              缺口 {repairItemCount}
            </span>
            <span className={`${MT_SHELL_STATUS_PILL} macro-toolkit-page__toolbar-pill`}>
              <ThunderboltOutlined aria-hidden="true" />
              能力 {readyCapabilityCount}/{capabilityItems.length || 0}
            </span>
          </div>
        </div>
        <div className={`${MT_SHELL_TOPBAR_RIGHT} macro-toolkit-page__header-controls`}>
          {showOperations ? (
            <>
              <Button
                className="macro-toolkit-page__dh-topbar-btn"
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
                className="macro-toolkit-page__dh-topbar-btn"
                icon={<ReloadOutlined />}
                onClick={() => void scriptsQuery.refetch()}
                loading={scriptsQuery.isFetching}
              >
                刷新注册表
              </Button>
              <Button
                className="macro-toolkit-page__dh-topbar-btn"
                data-testid="macro-toolkit-expand-all-content"
                icon={<ArrowDownOutlined />}
                aria-label="展开全部内容以便页内搜索或打印"
                disabled={
                  deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE &&
                  receiptTechnicalDetailsExpanded
                }
                onClick={revealAllDeferredContent}
              >
                {deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE &&
                receiptTechnicalDetailsExpanded
                  ? "已展开全部"
                  : "展开全部"}
              </Button>
            </>
          ) : null}
        </div>
        <p className="macro-toolkit-page__header-summary">
          {showOperations
            ? "先看结论、信号和指标结果；数据核对与脚本执行收在页面后段。"
            : "只展示宏观分析证据；刷新、脚本和注册表保留在宏观工具页。"}
        </p>
      </header>

      <main
        className={`${MT_SHELL_MAIN} macro-toolkit-page__main`}
        onClickCapture={handleDeferredContentLinkClick}
      >
      <section
        data-testid="macro-toolkit-tailwind-cockpit"
        className={MACRO_TOOLKIT_HERO_CARD_SLOTS.base({
          className: `macro-toolkit-cockpit macro-toolkit-cockpit--${
            showOperations ? "toolkit" : "observation"
          } border border-default-200 bg-background/95 text-foreground shadow-sm`,
        })}
        data-slot="card"
      >
        <div
          className={MACRO_TOOLKIT_HERO_CARD_SLOTS.content({ className: "macro-toolkit-cockpit__body p-0" })}
          data-slot="card-content"
        >
          <div
            className="macro-toolkit-cockpit__analysis macro-toolkit-house-view"
            data-testid="macro-toolkit-house-view"
            aria-label={showOperations ? "宏观工具 House View" : "宏观观察结论"}
          >
            <div className="macro-toolkit-panel-kicker">
              <span>{showOperations ? "投研结论" : "观察结论"}</span>
              <strong>{showOperations ? "可执行宏观判断" : "只读宏观判断"}</strong>
            </div>
            {observationDecisionSummary}
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

      {showOperations && deferredContentStage === 0 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-deferred-content-sentinel"
          aria-hidden="true"
        />
      ) : null}

      {!showOperations || deferredContentStage >= 1 ? (
      <div className="macro-toolkit-page__content">
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
                  eyebrow="信号"
                  title="核心信号"
                  description="等待后端宏观 analysis 结果返回。"
                />
                <div className="macro-toolkit-empty-output">核心分析加载中，暂不显示占位结论。</div>
              </section>
              <section className="macro-toolkit-section">
                <PageSectionLead
                  eyebrow="风险"
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
          {showOperations ? (
            <>
              {deferredContentStage >= 1 ? (
                <>
                  {analysisWarningsAlert}
                  {signalSection}
                  {indicatorSection}
                </>
              ) : null}
              {deferredContentStage >= 2 ? (
                <>
                  {capabilityResultsSection}
                  {riskSection}
                </>
              ) : null}
              {deferredContentStage >= 3 ? strategySection : null}
              {deferredContentStage >= 4 ? (
                <>
                  {modelSignalMatrixSection}
                  {modelChainSection}
                  {hasonStrategySection}
                  {crisisEvidenceSection}
                </>
              ) : null}
              {deferredContentStage >= 5 ? analysisEvidenceFlow : null}
            </>
          ) : (
            <>
              {analysisEvidenceFlow}
              {analysisWarningsAlert}
              <div className="macro-toolkit-observation-flow" aria-label="宏观观察阅读顺序">
                {observationSignalRiskComparisonSection}
                {modelSignalMatrixSection}
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
      </div>
      ) : null}

      {!showOperations || deferredContentStage >= 6 ? (
        <>
          {showOperations ? (
            <section className="macro-toolkit-operations-band" aria-label="宏观工具操作与治理区">
              <div className="macro-toolkit-committee-workspace">
                <aside className="macro-toolkit-committee-workspace__rail" aria-label="治理侧栏">
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
                <div className="macro-toolkit-committee-workspace__main" aria-label="操作台">
                  {operationsConsolePanel}
                </div>
              </div>
            </section>
          ) : null}

          {analysis ? <MacroToolkitReportBundlePanel bundle={analysis.report_bundle} /> : null}
        </>
      ) : null}

      {showOperations &&
      deferredContentStage >= 1 &&
      deferredContentStage < 6 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-progressive-deferred-content-sentinel"
          data-deferred-stage={deferredContentStage}
          aria-hidden="true"
        />
      ) : null}

      {showOperations && deferredContentStage === 6 ? (
        <div
          ref={deferredContentSentinelRef}
          className="macro-toolkit-deferred-content-sentinel"
          data-testid="macro-toolkit-execution-deferred-content-sentinel"
          aria-hidden="true"
        />
      ) : null}

      {showOperations &&
      deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE ? (
        <section className="macro-toolkit-execution-receipt-workspace" aria-label="执行证据与产物回执区">
          <div className="macro-toolkit-execution-receipt-workspace__head">
            <div>
              <span>执行与产物</span>
              <strong>执行证据</strong>
              <small>把可执行脚本、席位和商品刷新先归入证据，再用产物与数据源命中形成回执。</small>
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
                eyebrow="执行"
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
              eyebrow="席位"
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
                {refreshResult ? <Alert type={refreshFeedbackTone} showIcon message={refreshResult} /> : null}
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
              eyebrow="商品"
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
                  aria-controls="macro-toolkit-receipt-technical-details-body"
                  onClick={() => setReceiptTechnicalDetailsExpanded((expanded) => !expanded)}
                >
                  {receiptTechnicalDetailsExpanded ? "收起明细" : "展开明细"}
                </Button>
              </div>
              {receiptTechnicalDetailsExpanded ? (
                <div
                  id="macro-toolkit-receipt-technical-details-body"
                  className="macro-toolkit-receipt-technical-details__body"
                >
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
                    eyebrow="产物"
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
                    eyebrow="来源"
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
                      eyebrow="未纳入"
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
                    eyebrow="脚本"
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
                    <Button
                      icon={<InfoCircleOutlined />}
                      disabled={isOperationActionBusy && !isRunningChain}
                      loading={isRunningChain}
                      onClick={() => void runScriptChain(true)}
                    >
                      预检模型链
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
                    eyebrow="运行"
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
                    {chainRunResult ? (
                      <Alert
                        type={chainRunAlertType(chainRunResult.status)}
                        showIcon
                        message={`模型链：${chainRunResult.status}`}
                        description={`步骤：${chainRunResult.receipts.length}/${chainRunResult.manifest.length} · 缺口：${chainRunResult.readiness_after.degraded_count}`}
                      />
                    ) : null}
                    <pre className="macro-toolkit-console">
                      {runResult?.stdout || runResult?.stderr || "尚未运行。"}
                    </pre>
                  </div>
                </section>
                </div>
              ) : null}
            </section>
          </aside>
        </section>
      ) : null}
      </main>
    </section>
  );
}

function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const evidence = result.evidence.length ? result.evidence : result.warnings;
  const inputEvidence = normalizeInputEvidence(result);
  const rawResult = result.result;
  const crisisComponents =
    result.key === "crisis_score_cn" && Array.isArray(rawResult.components)
      ? rawResult.components.filter(isCrisisComponent)
      : [];
  const componentSummary =
    result.key === "crisis_score_cn" ? formatCrisisTopContributorSummary(crisisComponents) : null;
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
      {componentSummary ? (
        <small className="macro-toolkit-crisis-component-summary" data-testid="macro-toolkit-crisis-capability-component-summary">
          {componentSummary}
        </small>
      ) : null}
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

const INDICATOR_SPARKLINE_WIDTH = 120;
const INDICATOR_SPARKLINE_HEIGHT = 28;
const INDICATOR_SPARKLINE_PADDING = 2;

function IndicatorSparkline({ item }: { item: MacroToolkitIndicator }) {
  const points = item.recent_points ?? [];
  if (points.length < 2) {
    return <span className="macro-toolkit-sparkline__empty">—</span>;
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const innerWidth = INDICATOR_SPARKLINE_WIDTH - INDICATOR_SPARKLINE_PADDING * 2;
  const innerHeight = INDICATOR_SPARKLINE_HEIGHT - INDICATOR_SPARKLINE_PADDING * 2;
  const step = innerWidth / (points.length - 1);
  const coords = points.map((point, index) => {
    const x = INDICATOR_SPARKLINE_PADDING + index * step;
    const y = INDICATOR_SPARKLINE_PADDING + innerHeight * (1 - (point.value - min) / span);
    return [Number(x.toFixed(2)), Number(y.toFixed(2))] as const;
  });
  const [lastX, lastY] = coords[coords.length - 1]!;
  const firstDate = points[0]!.date;
  const lastDate = points[points.length - 1]!.date;
  return (
    <svg
      className="macro-toolkit-sparkline"
      viewBox={`0 0 ${INDICATOR_SPARKLINE_WIDTH} ${INDICATOR_SPARKLINE_HEIGHT}`}
      width={INDICATOR_SPARKLINE_WIDTH}
      height={INDICATOR_SPARKLINE_HEIGHT}
      role="img"
      aria-label={`${item.label} 近 ${points.length} 期走势`}
    >
      <title>{`${firstDate} ~ ${lastDate} · ${points.length} 期`}</title>
      <polyline points={coords.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" strokeWidth="1.5" />
      <circle cx={lastX} cy={lastY} r="2" />
    </svg>
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
  return refresh.failure_category?.trim() || "";
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

function dualFrequencyStatus(candidate: MacroToolkitDualFrequencyCandidate) {
  return candidate.data_status?.status ?? candidate.status ?? "unknown";
}

function dualFrequencyStatusText(status: string) {
  const labels: Record<string, string> = {
    warning: "存在缺口",
    not_evaluated: "未评估",
    attack: "进攻",
    defense: "防守",
    cooldown: "冷却",
    ramp: "恢复",
  };
  return labels[status] ?? statusLabel(status);
}

function dualFrequencyRatio(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

function dualFrequencyMultiplier(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `×${value.toFixed(2)}` : "—";
}

function dualFrequencyCount(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)
    : "—";
}

function dualFrequencyHistory(candidate: MacroToolkitDualFrequencyCandidate) {
  return candidate.provenance?.history ?? candidate.data_status?.history ?? null;
}

function dualFrequencyUniqueTexts(values: Array<string | null | undefined>) {
  return [...new Set(values.filter((value): value is string => Boolean(value)))];
}

function dualFrequencySourceText(candidate: MacroToolkitDualFrequencyCandidate) {
  const history = dualFrequencyHistory(candidate);
  return dualFrequencyUniqueTexts(history?.tables_used ?? []).join(" / ") || "来源未返回";
}

function dualFrequencyVersionText(candidate: MacroToolkitDualFrequencyCandidate) {
  const history = dualFrequencyHistory(candidate);
  const sources = Object.values(history?.sources ?? {});
  const sourceVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.source_versions ?? []));
  const vendorVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.vendor_versions ?? []));
  const ruleVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.rule_versions ?? []));
  const summarize = (label: string, values: string[]) => {
    if (!values.length) return "";
    return `${label} ${values[0]}${values.length > 1 ? ` 等${values.length}项` : ""}`;
  };
  const parts = [
    candidate.formula_version ? `公式 ${candidate.formula_version}` : "",
    candidate.rule_version ? `规则 ${candidate.rule_version}` : "",
    summarize("源版本", sourceVersions),
    summarize("供应商版本", vendorVersions),
    summarize("数据规则", ruleVersions),
  ].filter(Boolean);
  return parts.join(" · ") || "版本未返回";
}

function dualFrequencyAlignmentText(alignment: string | undefined) {
  const labels: Record<string, string> = {
    exact: "同日对齐",
    prior_observation: "前一交易日",
    no_observation: "无可用观察",
  };
  return alignment ? labels[alignment] ?? alignment : "对齐状态未返回";
}

function DualFrequencyRiskBudgetPanel({
  snapshot,
}: {
  snapshot: MacroToolkitMacroEtfStrategySnapshot;
}) {
  const candidate = snapshot.dual_frequency;
  if (!candidate) {
    return (
      <div
        className="macro-toolkit-strategy-observation macro-toolkit-dual-frequency"
        aria-label="双频风险预算候选"
      >
        <div className="macro-toolkit-strategy-observation__head">
          <div>
            <span>双频风险预算（候选）</span>
            <strong>候选快照未返回</strong>
          </div>
          <Tag color="gold">不进入下单</Tag>
        </div>
        <Alert
          type="warning"
          showIcon
          message="双频候选暂不可用"
          description="策略摘要未返回双频状态，页面不会用零值或演示值补位。"
        />
        <div className="macro-toolkit-strategy-observation__note">
          <span>观察用途</span>
          <small>非正式投资信号，不替换正式策略，不进入下单。</small>
        </div>
      </div>
    );
  }

  const boundaryConfirmed =
    snapshot.boundary === "observation_only" &&
    snapshot.execution_enabled === false &&
    candidate.boundary === "observation_only" &&
    candidate.execution_enabled === false;
  const slowCap = boundaryConfirmed ? candidate.slow?.cap : null;
  const fastState = candidate.fast?.state ?? null;
  const fastMultiplier = boundaryConfirmed ? candidate.fast?.multiplier : null;
  const preSurvivalTarget = boundaryConfirmed ? candidate.pre_survival_target_total_weight : null;
  const finalTarget = boundaryConfirmed ? candidate.final_target_total_weight : null;
  const survivalStatus = candidate.survival?.status ?? candidate.survival?.state ?? "not_evaluated";
  const status = dualFrequencyStatus(candidate);
  const dataStatus = candidate.data_status;
  const history = dualFrequencyHistory(candidate);
  const asOfDate =
    history?.effective_as_of_date ??
    history?.latest_trade_date ??
    dataStatus?.latest_trade_date ??
    candidate.fast?.signal_date ??
    candidate.as_of_date ??
    snapshot.as_of_date ??
    null;
  const sourceText = dualFrequencySourceText(candidate);
  const versionText = dualFrequencyVersionText(candidate);
  const warnings = dualFrequencyUniqueTexts(candidate.warnings ?? []);
  const amountSource = history?.sources?.market_amount;
  const amountSampleText =
    amountSource?.valid_amount_observation_count != null ||
    amountSource?.null_amount_observation_count != null
      ? `有效 ${dualFrequencyCount(amountSource?.valid_amount_observation_count)} · 空值 ${dualFrequencyCount(amountSource?.null_amount_observation_count)}`
      : "成交额样本计数未返回";
  const statusText = boundaryConfirmed ? dualFrequencyStatusText(status) : "边界待确认";
  const fastStateText = fastState ? dualFrequencyStatusText(fastState) : "待确认";
  const survivalText = dualFrequencyStatusText(survivalStatus);
  const survivalDate = candidate.survival?.signal_date ?? null;
  const survivalDetail =
    survivalStatus === "not_evaluated"
      ? "缺少权威组合净值或状态，生存层暂未评估。"
      : survivalDate
        ? `生存层数据日 ${survivalDate}`
        : "生存层状态由后端只读候选返回。";
  const headline =
    fastState && slowCap != null
      ? `快频${fastStateText}，慢频上限 ${dualFrequencyRatio(slowCap)}`
      : "快频状态或慢频上限待确认";
  const qualityDetail = [
    statusText,
    history?.status ? `历史 ${dualFrequencyStatusText(history.status)}` : "",
    dataStatus?.usable_row_count != null ? `可用 ${dataStatus.usable_row_count} 行` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className="macro-toolkit-strategy-observation macro-toolkit-dual-frequency"
      aria-label="双频风险预算候选"
    >
      <div className="macro-toolkit-strategy-observation__head">
        <div>
          <span>双频风险预算（候选）</span>
          <strong>{headline}</strong>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={boundaryConfirmed ? statusColor(status) : "red"}>{statusText}</Tag>
          <Tag color="gold">不进入下单</Tag>
        </div>
      </div>
      {!boundaryConfirmed ? (
        <Alert
          type="error"
          showIcon
          message="只读边界未确认"
          description="候选目标值已隐藏；确认 observation_only 且执行关闭后才展示。"
        />
      ) : null}
      <div className="macro-toolkit-strategy-observation__grid">
        <MetricTile
          icon={<ThunderboltOutlined />}
          label="快频状态"
          value={fastStateText}
          detail={
            candidate.fast?.signal_date
              ? `信号数据日 ${candidate.fast.signal_date}`
              : "快频信号日期未返回。"
          }
          tone={fastState ? "neutral" : "missing"}
          testId="macro-toolkit-dual-fast-state"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="慢频上限"
          value={dualFrequencyRatio(slowCap)}
          detail="沿用宏观 ETF 慢频仓位上限。"
          tone={slowCap == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-slow-cap"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="快频乘数"
          value={dualFrequencyMultiplier(fastMultiplier)}
          detail="进攻为 1.00，防守保护按后端候选规则返回。"
          tone={fastMultiplier == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-fast-multiplier"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<InfoCircleOutlined />}
          label="生存层前目标"
          value={dualFrequencyRatio(preSurvivalTarget)}
          detail="生存层应用前的只读候选预算。"
          tone={preSurvivalTarget == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-pre-survival"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<WarningOutlined />}
          label="生存层"
          value={survivalText}
          detail={survivalDetail}
          tone={survivalStatus === "not_evaluated" ? "missing" : "neutral"}
          testId="macro-toolkit-dual-survival"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="最终目标"
          value={dualFrequencyRatio(finalTarget)}
          detail={
            finalTarget == null
              ? "生存层未完成，最终目标保持为空。"
              : "完整候选目标，仍不进入下单。"
          }
          tone={finalTarget == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-final-target"
          detailMaxLength={44}
        />
      </div>
      <div className="macro-toolkit-strategy-trace" aria-label="双频风险预算证据">
        <span>
          <b>观察日</b>
          {candidate.as_of_date ?? snapshot.as_of_date ?? "日期未返回"}
        </span>
        <span>
          <b>数据日</b>
          {asOfDate ? `${asOfDate} · ${dualFrequencyAlignmentText(dataStatus?.as_of_alignment)}` : "日期未返回"}
        </span>
        <span title={sourceText}>
          <b>来源</b>
          {sourceText}
        </span>
        <span>
          <b>质量</b>
          {qualityDetail || "质量未返回"}
        </span>
        <span title={versionText}>
          <b>版本</b>
          {compactText(versionText, 140)}
        </span>
      </div>
      <div className="macro-toolkit-strategy-observation__note">
        <span>成交额口径</span>
        <small>成交额采用全 A 股日汇总代理，非沪深300成分成交额；源单位未确认，仅使用无量纲量比。</small>
        <small>{amountSampleText}</small>
      </div>
      {warnings.length ? (
        <div className="macro-toolkit-strategy-warnings" aria-label="双频风险预算告警">
          <Alert
            type="warning"
            showIcon
            message={`候选告警 ${warnings.length} 项`}
            description={
              <span title={warnings.join(" | ")}>{compactText(warnings.join("；"), 180)}</span>
            }
          />
        </div>
      ) : null}
      <div className="macro-toolkit-strategy-observation__note">
        <span>观察用途</span>
        <small>非正式投资信号，不替换正式策略，不进入下单。</small>
      </div>
    </div>
  );
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
