import type { ReactNode } from "react";

import type {
  MacroToolkitCffexRefreshRun,
  MacroToolkitDataHealth,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitSourceBackfillRefreshRun,
} from "../../../api/macroToolkitClient";

export type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];
export type CommodityRefreshOptions = {
  dryRun?: boolean;
  products?: string[];
  suggestedSelection?: string[];
  startDate?: string;
};

export type MacroToolkitGovernanceFocusKey = "evidence" | "data-health" | "analysis-scope" | "execution" | "artifacts";

export type MacroToolkitGovernanceFocusItem = {
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

export type MacroToolkitEvidenceBookRow = {
  key: string;
  subject: string;
  support: string;
  gap: string;
  owner: string;
  href: string;
};

export type MacroToolkitCommitteePackItem = MacroToolkitEvidenceBookRow & {
  packSubject: string;
  status: "archived" | "blocking" | "pending";
  statusLabel: string;
  receipt: MacroToolkitActionReceipt | null;
  receiptConfirmed: boolean;
};

export type MacroToolkitCommitteeChecklistItem = MacroToolkitEvidenceBookRow & {
  condition: string;
  status: "pass" | "block" | "pending";
  statusLabel: string;
  action: string;
};

export type MacroToolkitCommitteeWorkQueueItem = MacroToolkitCommitteeChecklistItem & {
  priorityLabel: "阻断项" | "待确认项";
  executionHref: string;
};

export type MacroToolkitSignoffLaneItem = {
  owner: string;
  status: "approved" | "blocked" | "pending" | "reviewed";
  statusLabel: string;
  subject: string;
};

export type MacroToolkitActionReceiptStatus = "idle" | "running" | "completed" | "warning" | "failed";

export type MacroToolkitActionReceipt = {
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

export type MacroToolkitDeepEvidenceQueueItem = {
  key: string;
  label: string;
  value: string;
  detail: string;
  href: string;
};

export const EMPTY_ACTION_RECEIPT: MacroToolkitActionReceipt = {
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

export function nextActionReceiptId(kind: string) {
  macroToolkitActionReceiptSequence += 1;
  return `${kind}:${macroToolkitActionReceiptSequence}`;
}

export function actionReceiptDecisionFields(
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

export type RefreshFeedbackTone = "success" | "warning" | "info";

export const COMMITTEE_EVIDENCE_SCRIPT_PRIORITY = [
  "signal_aggregator",
  "risk_monitor",
  "crisis_score_cn",
  "merrill_clock_cn",
  "crowding_cn",
] as const;

export const MACRO_COMMODITY_PRODUCT_OPTIONS = [
  { value: "RB", label: "螺纹钢", description: "黑色链条" },
  { value: "I", label: "铁矿石", description: "黑色链条" },
  { value: "CU", label: "铜", description: "有色金属" },
  { value: "AL", label: "铝", description: "有色金属" },
  { value: "SC", label: "原油", description: "能源" },
  { value: "AU", label: "黄金", description: "避险资产" },
  { value: "NHCI", label: "南华指数", description: "Crisis Score 输入" },
] as const;
export const DEFAULT_MACRO_COMMODITY_PRODUCTS = MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => option.value);

export function sameCommodityProducts(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

export const CFFEX_REFRESH_TERMINAL_STATUSES = new Set(["completed", "partial", "failed"]);
export const SOURCE_BACKFILL_TERMINAL_STATUSES = new Set([
  "completed",
  "partial",
  "no_rows",
  "blocked",
  "failed",
]);

export function isCffexRefreshTerminal(status: string) {
  return CFFEX_REFRESH_TERMINAL_STATUSES.has(status);
}

export function isSourceBackfillTerminal(status: string) {
  return SOURCE_BACKFILL_TERMINAL_STATUSES.has(status);
}

export function asyncRefreshPendingMessage(subject: string, status: string) {
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

export function refreshFailureMessage(subject: string, failureCategory: string | null | undefined) {
  return failureCategory ? `${subject}失败（类别：${failureCategory}）` : `${subject}失败`;
}

export function cffexRefreshTerminalMessage(refresh: MacroToolkitCffexRefreshRun) {
  const rowCount = refresh.row_count == null ? "行数待确认" : `${refresh.row_count} 行`;
  const tradeDate = refresh.trade_date ?? refresh.report_date ?? "日期缺失";
  return refresh.status === "partial"
    ? `席位刷新部分完成：${rowCount}，交易日 ${tradeDate}；部分来源未完成，请复核`
    : `刷新完成：${rowCount}，交易日 ${tradeDate}`;
}

export function sourceBackfillTerminalMessage(refresh: MacroToolkitSourceBackfillRefreshRun) {
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

export function governanceFocusFromEvidenceHref(href: string): MacroToolkitGovernanceFocusKey {
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

export function committeeWorkQueueExecutionHref(item: MacroToolkitCommitteeChecklistItem) {
  if (item.key === "tool-execution") return "#macro-toolkit-operations-actions";
  return item.href;
}

export function latestCompletedReceiptForOwner(receipts: MacroToolkitActionReceipt[], owner: string) {
  return receipts.find((receipt) => receipt.status === "completed" && receipt.reviewOwner === owner) ?? null;
}

export function latestCompletedReceiptForQueueItem(
  receipts: MacroToolkitActionReceipt[],
  item: MacroToolkitCommitteeWorkQueueItem,
) {
  return receipts.find((receipt) => receiptMatchesCommitteeQueueItem(receipt, item)) ?? null;
}

export function receiptMatchesCommitteeQueueItem(
  receipt: MacroToolkitActionReceipt,
  item: MacroToolkitCommitteeWorkQueueItem,
) {
  return receiptMatchesCommitteeEvidence(receipt, item.key, item.href, item.owner, item.executionHref);
}

export function receiptMatchesCommitteeEvidence(
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

export function committeeSignoffLaneItems(
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

export function pickDefaultCommitteeScript(scripts: MacroToolkitScriptRecord[]) {
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

export const MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT = 430;
export const MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY = [
  "macro-toolkit",
  "analysis",
  "full",
  MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
] as const;
export const MACRO_TOOLKIT_ACTION_RECEIPT_LIMIT = 4;

export const MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN = "800px 0px";
export const MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE = 7;
export type MacroToolkitDeferredContentStage = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

export const MACRO_TOOLKIT_DEFERRED_TARGET_STAGES: Record<
  string,
  MacroToolkitDeferredContentStage
> = {
  "#macro-toolkit-strategy-detail": 4,
  "#macro-toolkit-model-readiness-detail": 3,
  "#macro-toolkit-crisis-detail": 5,
  "#macro-toolkit-analysis-detail": 5,
  "#macro-toolkit-data-health-detail": 5,
  "#macro-toolkit-operations-actions": 6,
  "#macro-toolkit-operations-console": 6,
  "#macro-toolkit-tool-execution-detail": 7,
  "#macro-toolkit-cffex-detail": 7,
  "#macro-toolkit-commodity-detail": 7,
  "#macro-toolkit-script-artifact-detail": 7,
};

export function macroToolkitDeferredContentStageForHref(
  href: string,
): MacroToolkitDeferredContentStage | null {
  return MACRO_TOOLKIT_DEFERRED_TARGET_STAGES[href] ?? null;
}
