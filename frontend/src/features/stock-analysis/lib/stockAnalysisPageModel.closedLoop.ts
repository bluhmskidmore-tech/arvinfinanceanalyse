// Closed-loop summary, replay closure and freshness meta for the stock-analysis page model.
import type {
  BacktestWindowSummaryStatus,
  ConfluenceReplayBlockedDate,
  ConfluenceReplayStatus,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  StockAnalysisReplayClosure,
} from "../../../api/contracts";
import type {
  StockClosedLoopSummary,
  StockClosedLoopSummaryItem,
  StockClosedLoopTone,
  StockClosedLoopVerdict,
  StockDecisionReferenceRating,
  StockViewModelMeta,
} from "./stockAnalysisPageModel.types";
import { finiteCount } from "./stockAnalysisPageModel.format";
import {
  localizeFallbackMode,
  localizeMarketDataStatus,
  localizeMetaQualityFlag,
  localizeMetaVendorStatus,
  localizeStockBackendText,
} from "./stockAnalysisPageModel.localize";

type NormalizedConfluenceReplayBlockedDate = Omit<ConfluenceReplayBlockedDate, "reason_code"> & {
  reason_code: string;
};

type NormalizedConfluenceReplayStatus = Omit<ConfluenceReplayStatus, "blocked_dates"> & {
  blocked_dates: NormalizedConfluenceReplayBlockedDate[];
  maturity_status?: string;
  matched_entry_count: number;
  has_required_horizon_stats: boolean;
};

export function pickStockFreshnessMeta(meta: StockViewModelMeta | null | undefined): StockViewModelMeta {
  return {
    quality_flag: meta?.quality_flag,
    vendor_status: meta?.vendor_status,
    fallback_mode: meta?.fallback_mode,
  };
}

export function mergeStockClosedLoopMeta(
  hasClosedLoopState: boolean,
  strategyMeta: StockViewModelMeta | null | undefined,
  confluenceMeta: StockViewModelMeta | null | undefined,
): StockViewModelMeta {
  if (!hasClosedLoopState) return strategyMeta ?? {};
  return {
    quality_flag: confluenceMeta?.quality_flag ?? strategyMeta?.quality_flag,
    vendor_status: confluenceMeta?.vendor_status ?? strategyMeta?.vendor_status,
    fallback_mode: confluenceMeta?.fallback_mode ?? strategyMeta?.fallback_mode,
    source_version: confluenceMeta?.source_version ?? strategyMeta?.source_version,
    rule_version: confluenceMeta?.rule_version ?? strategyMeta?.rule_version,
    trace_id: confluenceMeta?.trace_id ?? strategyMeta?.trace_id,
  };
}

export function buildStockClosedLoopFreshnessIssue(
  meta: StockViewModelMeta | null | undefined,
): string | null {
  if (!meta) return null;
  const issues: string[] = [];
  if (meta.quality_flag && meta.quality_flag !== "ok") {
    issues.push(localizeMetaQualityFlag(meta.quality_flag));
  }
  if (meta.vendor_status && meta.vendor_status !== "ok") {
    issues.push(localizeMetaVendorStatus(meta.vendor_status));
  }
  if (meta.fallback_mode && meta.fallback_mode !== "none") {
    issues.push(localizeFallbackMode(meta.fallback_mode));
  }
  return issues.length > 0 ? `闭环供数未通过新鲜度检查（${issues.join(" / ")}）` : null;
}

function stockClosedLoopFreshnessStatus(
  meta: StockViewModelMeta | null | undefined,
): "error" | "stale" | "degraded" | null {
  if (!meta) return null;
  if (meta.quality_flag === "error" || meta.vendor_status === "vendor_unavailable") {
    return "error";
  }
  if (
    meta.quality_flag === "stale" ||
    meta.vendor_status === "vendor_stale" ||
    (meta.fallback_mode != null && meta.fallback_mode !== "none")
  ) {
    return "stale";
  }
  if (
    (meta.quality_flag != null && meta.quality_flag !== "ok") ||
    (meta.vendor_status != null && meta.vendor_status !== "ok")
  ) {
    return "degraded";
  }
  return null;
}

export function buildClosedLoopSummary(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
  meta: StockViewModelMeta = {},
  replayClosure: StockAnalysisReplayClosure | null | undefined = undefined,
): StockClosedLoopSummary {
  const state = confluence?.closed_loop_state ?? null;
  const adversarial = confluence?.adversarial_context ?? null;
  const entryStatus = state?.entry_gate ?? deriveEntryGateStatus(state);
  const adversarialStatus = adversarial?.risk_gate ?? "missing";
  const exitStatus = state?.exit_gate ?? deriveExitGateStatus(payload, confluence);
  const exitCounts = closedLoopExitCounts(payload, confluence);
  const replayStatusRaw = state?.replay_status ?? "missing";
  const replayStatus = normalizeClosedLoopStatus(replayStatusRaw, "missing");
  const replayEvidence = confluence?.replay_evidence ?? null;
  const lineageStatus =
    stockClosedLoopFreshnessStatus(meta) ??
    state?.lineage_status ??
    deriveLineageStatus(adversarial, state);
  const fallbackMode = meta.fallback_mode ?? "none";
  const macroAuthorityStatus = confluence?.macro_context?.authority_status ?? "missing";
  const macroAuthorityReasons = (confluence?.macro_context?.authority_reasons ?? [])
    .map((reason) => localizeStockBackendText(reason))
    .filter(Boolean);

  const items: StockClosedLoopSummaryItem[] = [
    {
      key: "entry_gate",
      label: "入场观察门",
      status: entryStatus,
      statusLabel: closedLoopStatusLabel("entry_gate", entryStatus),
      tone: closedLoopTone("entry_gate", entryStatus),
      detail:
        entryStatus === "missing"
          ? "待补：闭环入场状态未接通"
          : `市场门控 ${localizeMarketDataStatus(payload.market_gate.state)} / 宏观权威（PMI+信用代理） ${closedLoopStatusLabel(
              "entry_gate",
              macroAuthorityStatus,
            )}${macroAuthorityReasons.length > 0 ? `：${macroAuthorityReasons.join("；")}` : ""}`,
    },
    {
      key: "adversarial_gate",
      label: "反拥挤拦截",
      status: adversarialStatus,
      statusLabel: closedLoopStatusLabel("adversarial_gate", adversarialStatus),
      tone: closedLoopTone("adversarial_gate", adversarialStatus),
      detail:
        adversarialStatus === "missing"
          ? "待补：反拥挤证据缺失，不能视为中性证明"
          : closedLoopAdversarialDetail(adversarial),
    },
    {
      key: "risk_exit",
      label: "风险退出",
      status: exitStatus,
      statusLabel: closedLoopStatusLabel("risk_exit", exitStatus),
      tone: closedLoopTone("risk_exit", exitStatus),
      detail:
        exitStatus === "missing"
          ? "待补：风险退出状态未接通"
          : `${exitCounts.watchCount} 条观察 / ${exitCounts.triggeredCount} 条触发`,
    },
    replayClosure === undefined
      ? {
          key: "replay",
          label: "回放证据",
          status: replayStatus,
          statusLabel: closedLoopStatusLabel("replay", replayStatus),
          tone: closedLoopTone("replay", replayStatus),
          detail: closedLoopReplayDetail(replayStatusRaw, replayStatus, replayEvidence),
          badges: closedLoopReplayBadges(replayStatusRaw),
        }
      : replayClosure
        ? buildCurrentRuleReplayClosureItem(replayClosure)
        : buildMissingCurrentRuleReplayClosureItem(),
    {
      key: "lineage",
      label: "血缘状态",
      status: lineageStatus,
      statusLabel: closedLoopStatusLabel("lineage", lineageStatus),
      tone: closedLoopTone("lineage", lineageStatus),
      detail: `质量 ${localizeMetaQualityFlag(meta.quality_flag)} / 供数状态 ${localizeMetaVendorStatus(
        meta.vendor_status,
      )}${
        fallbackMode !== "none" ? ` / ${localizeFallbackMode(fallbackMode)}` : ""
      }`,
    },
  ];

  const boundaryCount = items.filter((item) => item.tone !== "positive").length;
  const referenceRating = buildDecisionReferenceRating(items);
  return {
    summaryLabel: boundaryCount > 0 ? `${boundaryCount} 项待复核` : "全部通过",
    boundaryCount,
    referenceRating,
    verdict: buildClosedLoopVerdict(referenceRating, items),
    items,
  };
}

function buildMissingCurrentRuleReplayClosureItem(): StockClosedLoopSummaryItem {
  return {
    key: "replay",
    label: "回放证据",
    status: "insufficient",
    statusLabel: "当前规则回放新契约缺失 / 证据不足",
    tone: "warning",
    detail:
      "工作台请求已成功，但 replay_closure 未返回；不能把旧回放状态视为当前规则认证证据。仅作观察，不推导策略有效性。",
    badges: ["当前规则", "新契约缺失"],
  };
}

function buildCurrentRuleReplayClosureItem(
  closure: StockAnalysisReplayClosure,
): StockClosedLoopSummaryItem {
  const statusLabel = currentRuleReplayClosureStatusLabel(closure);
  const reasonCodes = Array.from(
    new Set(
      [closure.primary_blocker_code, ...closure.reason_codes].filter(
        (value): value is string => typeof value === "string" && value.length > 0,
      ),
    ),
  );
  const certifiedRange = closedLoopReplayRangeLabel(
    "认证范围",
    closure.certified_start_date,
    closure.certified_end_date,
  );
  const modeLabel =
    closure.cohort_mode === "current_rule_certified" ? "当前规则认证批次" : "批次模式待确认";
  const detail = [
    `模式：${modeLabel}`,
    `状态：${statusLabel}`,
    `供数：${currentRuleReplayDataAvailabilityLabel(closure.data_availability)}`,
    `生效认证批次：${closure.active_cohort_count}`,
    certifiedRange,
    `完成日：${closure.counts.completed_dates}/${closure.thresholds.completed_dates}`,
    `匹配样本：${closure.counts.matched_entry_count}/${closure.thresholds.matched_entry_count}`,
    `待成熟尾部：${closure.counts.pending_tail_dates} 日`,
    `阻断待处理：${closure.counts.blocking_pending_dates} 日 / 不支持：${closure.counts.unsupported_dates} 日 / 仅代理：${closure.counts.proxy_only_dates} 日`,
    `T+5 可用：${closure.counts.t5_usable_count} / T+20 可用：${closure.counts.t20_usable_count}`,
    closedLoopReplayMetricBasisLabel(closure.decision_metric_basis),
    `主要阻断：${localizeCurrentRuleReplayReasonCode(closure.primary_blocker_code)}`,
    `原因：${
      reasonCodes.length > 0
        ? reasonCodes.map((reason) => localizeCurrentRuleReplayReasonCode(reason)).join("；")
        : "无"
    }`,
    `批次：${closure.cohort_id ?? "未生效"}`,
    `物化运行：${closure.run_id ?? "待确认"}`,
    `生效运行：${closure.promotion_run_id ?? "未生效"}`,
    "仅作观察，不推导策略有效性",
  ].join(" / ");

  return {
    key: "replay",
    label: "回放证据",
    status: closure.status,
    statusLabel,
    tone: currentRuleReplayClosureTone(closure),
    detail,
    badges: [
      "当前规则",
      `完成 ${closure.counts.completed_dates}/${closure.thresholds.completed_dates}`,
      `匹配 ${closure.counts.matched_entry_count}/${closure.thresholds.matched_entry_count}`,
      `待成熟尾部 ${closure.counts.pending_tail_dates}`,
      `批次 ${closure.cohort_id ?? "未生效"}`,
    ],
  };
}

function currentRuleReplayClosureStatusLabel(closure: StockAnalysisReplayClosure): string {
  if (closure.selection_status === "schema_unavailable") return "受控存储未启用 / 证据不足";
  if (closure.selection_status === "no_active_certified") return "无已生效认证批次 / 证据不足";
  if (
    closure.status === "blocked" ||
    closure.selection_status === "governance_conflict" ||
    closure.selection_status === "governance_error" ||
    closure.selection_status === "as_of_mismatch"
  ) {
    return "治理冲突/阻断";
  }
  if (closure.selection_status !== "unique_active_certified") {
    return "认证批次治理状态待确认 / 证据不足";
  }
  if (closure.active_cohort_count !== 1) {
    return "生效认证批次基数异常 / 证据不足";
  }
  if (closure.status === "ready") return "当前规则回放已认证";
  return "证据不足";
}

function currentRuleReplayClosureTone(closure: StockAnalysisReplayClosure): StockClosedLoopTone {
  if (
    closure.status === "blocked" ||
    closure.selection_status === "governance_conflict" ||
    closure.selection_status === "governance_error" ||
    closure.selection_status === "as_of_mismatch"
  ) {
    return "negative";
  }
  if (
    closure.selection_status !== "unique_active_certified" ||
    closure.active_cohort_count !== 1
  ) {
    return "warning";
  }
  if (closure.data_availability !== "fresh") return "warning";
  if (closure.status === "ready") return "positive";
  return "warning";
}

function currentRuleReplayDataAvailabilityLabel(value: string): string {
  const labels: Record<string, string> = {
    fresh: "新鲜",
    stale: "陈旧",
    fallback: "回退快照",
    no_data: "无数据",
    unsupported: "未启用",
  };
  return labels[value] ?? "待确认";
}

function localizeCurrentRuleReplayReasonCode(value: string | null | undefined): string {
  if (!value) return "无";
  const normalized = value.trim().toLowerCase();
  const labels: Record<string, string> = {
    schema_unavailable: "受控存储未启用",
    controlled_schema_unavailable: "受控存储未启用",
    current_rule_cohort_schema_unavailable: "受控存储未启用",
    current_rule_cohort_database_unavailable: "受控存储不可用",
    no_active_certified: "无已生效认证批次",
    no_active_certified_cohort: "无已生效认证批次",
    no_active_current_rule_certified_cohort: "无已生效认证批次",
    governance_conflict: "存在多个已生效认证批次",
    multiple_active_certified_cohorts: "存在多个已生效认证批次",
    multiple_active_current_rule_cohorts: "存在多个已生效认证批次",
    governance_error: "认证批次治理校验失败",
    current_rule_cohort_governance_error: "认证批次治理校验失败",
    current_rule_cohort_read_failed: "认证批次读取失败",
    current_rule_cohort_schema_partial: "受控存储结构不完整",
    as_of_mismatch: "页面日期与认证批次评估日不一致",
    active_cohort_as_of_mismatch: "页面日期与认证批次评估日不一致",
    active_cohort_lookahead: "认证批次评估日晚于页面日期",
    page_as_of_date_unresolved: "页面日期待确认",
    page_as_of_date_invalid: "页面日期格式无效",
    current_rule_cohort_not_ready: "当前规则批次尚未认证",
    current_rule_cohort_ready: "当前规则回放已认证",
    active_current_rule_cohort_not_certified: "生效批次尚未认证",
    active_cohort_page_id_mismatch: "批次页面标识不一致",
    active_cohort_mode_mismatch: "批次模式不一致",
    active_cohort_date_bounds_mismatch: "批次认证日期边界不一致",
    active_cohort_date_order_invalid: "批次认证日期顺序无效",
    active_cohort_version_tuple_mismatch: "批次版本组不一致",
    active_cohort_certificate_status_invalid: "日期认证状态无效",
    active_cohort_signal_certificate_mismatch: "信号日期认证与事实不一致",
    active_cohort_zero_signal_certificate_mismatch: "无信号日期认证不一致",
    active_cohort_pending_certificate_affects_completed: "待处理日期被错误计入完成统计",
    active_cohort_calendar_receipt_mismatch: "交易日历凭据不一致",
    active_cohort_calendar_source_mismatch: "交易日历权威版本不一致",
    active_cohort_certificate_date_outside_certified_range: "日期认证超出批次认证范围",
    active_cohort_certificate_bounds_mismatch: "日期认证边界与批次范围不一致",
    active_cohort_fact_without_certificate: "回放事实缺少日期认证",
    active_cohort_manifest_count_mismatch: "批次清单计数与认证明细不一致",
    active_cohort_fact_count_mismatch: "批次事实行与认证计数不一致",
    active_cohort_stale_fact_count_mismatch: "陈旧事实计数与批次清单不一致",
    active_cohort_duplicate_fact_natural_key: "回放事实存在重复主键",
    active_cohort_duplicate_certificate_natural_key: "日期认证存在重复主键",
    active_cohort_certificate_fact_count_mismatch: "日期认证计数与回放事实不一致",
    active_cohort_control_proof_count_mismatch: "对照样本证明计数不一致",
    active_cohort_noncompleted_certificate_count_invalid: "未完成日期认证计数不合理",
    active_cohort_pending_tail_has_non_maturity_gap: "自然待成熟尾部混入其他缺口",
    active_cohort_zero_signal_certificate_count_mismatch: "无信号日期认证计数不一致",
    active_cohort_completed_certificate_has_source_gap: "已完成日期仍存在来源缺口",
    active_cohort_fact_not_strictly_usable: "回放事实未达到严格可用口径",
    active_cohort_fact_status_invalid: "回放事实状态无效",
    current_rule_replay_readiness_insufficient: "当前规则回放认证条件未满足",
    unique_active_current_rule_certified_cohort: "唯一生效当前规则认证批次",
    decision_metric_basis_not_net_next_open_adj: "决策收益口径未通过认证",
    strict_coverage_not_proven: "严格覆盖尚未证明",
    fallback_coverage_present: "认证窗口包含回退覆盖",
    minimum_completed_dates_not_met: "完成日期不足 20 日",
    minimum_matched_entries_not_met: "匹配样本不足 100 条",
    completed_dates_below_threshold: "完成日期不足 20 日",
    matched_entry_count_below_threshold: "匹配样本不足 100 条",
    blocking_pending_dates: "存在阻断待处理日期",
    blocking_pending_dates_not_zero: "存在阻断待处理日期",
    unsupported_dates: "存在不支持日期",
    unsupported_dates_not_zero: "存在不支持日期",
    proxy_only_dates: "存在仅代理证据日期",
    proxy_only_dates_not_zero: "存在仅代理证据日期",
    stale_execution_rows: "存在陈旧执行证据",
    stale_execution_row_count_not_zero: "存在陈旧执行证据",
    stale_matched_baseline_rows: "存在陈旧匹配基准证据",
    stale_matched_baseline_row_count_not_zero: "存在陈旧匹配基准证据",
  };
  if (labels[normalized]) return labels[normalized];
  if (normalized.startsWith("active_cohort_") && normalized.endsWith("_missing")) {
    return "认证批次关键字段缺失";
  }
  if (normalized.startsWith("active_cohort_") && normalized.endsWith("_invalid")) {
    return "认证批次关键字段无效";
  }
  return "治理原因待确认";
}

function buildClosedLoopVerdict(
  rating: StockDecisionReferenceRating,
  items: StockClosedLoopSummaryItem[],
): StockClosedLoopVerdict {
  const blockedItem = items.find((item) => item.key === "adversarial_gate" && item.tone === "negative");
  const negativeItem = items.find((item) => item.tone === "negative");
  const warningItem = items.find((item) => item.tone === "warning");
  const primaryItem =
    (rating.code === "blocked" ? blockedItem : undefined) ??
    negativeItem ??
    warningItem ??
    items.find((item) => item.key === "entry_gate") ??
    items[0];
  const evidence = items.slice(0, 4).map((item) => `${item.label}: ${item.statusLabel}`);

  if (rating.code === "blocked") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "闭环阻断，先复核约束项",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "保持仅观察输出，优先处理阻断门、退出触发和降级来源。",
      evidence,
    };
  }
  if (rating.code === "insufficient_data") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "证据不足，不形成有效观察结论",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "先补齐宏观反拥挤、回放窗口或血缘证据，再进入人工复核。",
      evidence,
    };
  }
  if (rating.code === "pause") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "暂缓复核，存在降级边界",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "保留观察队列，但先复核降级、回退、代理观察或待成熟日期。",
      evidence,
    };
  }
  return {
    code: rating.code,
    tone: rating.tone,
    label: rating.label,
    headline: "可进入人工复核队列",
    primaryReason: rating.detail,
    nextStep: "继续按仅观察口径复核候选、退出观察和回放证据，不推导策略收益。",
    evidence,
  };
}

function closedLoopReplayDetail(
  replayStatusRaw: LivermoreSignalConfluencePayload["closed_loop_state"] extends infer State
    ? State extends { replay_status?: infer ReplayStatus }
      ? ReplayStatus
      : unknown
    : unknown,
  replayStatus: string,
  replayEvidence: LivermoreSignalConfluencePayload["replay_evidence"] | null,
): string {
  const windowStatus = replayStatusWindow(replayStatusRaw);
  if (windowStatus) {
    const excludedDates = windowStatus.blocked_dates.map((item) => item.trade_date);
    const blockedReasons = windowStatus.blocked_dates.map(
      (item) => `${item.trade_date} ${localizeReplayReasonCode(item.reason_code)}`,
    );
    const requestedRangeLabel = closedLoopReplayRangeLabel(
      "请求范围",
      windowStatus.requested_snapshot_from ?? windowStatus.snapshot_from,
      windowStatus.requested_snapshot_to ?? windowStatus.snapshot_to,
    );
    const observedRangeLabel = closedLoopReplayRangeLabel(
      "实际覆盖",
      windowStatus.observed_snapshot_from,
      windowStatus.observed_snapshot_to,
    );
    const detailParts = [
      requestedRangeLabel,
      observedRangeLabel,
      closedLoopReplayMetricBasisLabel(windowStatus.metric_basis),
      `成熟度：${closedLoopReplayMaturityLabel(windowStatus.maturity_status)}；${
        windowStatus.has_decision_usable_completed_stats ? "可用于本次复核判断" : "不可用于本次复核判断"
      }`,
      windowStatus.has_decision_usable_completed_stats
        ? `已纳入完成日期：${windowStatus.included_completed_stats_dates.join("、") || "无"}`
        : "暂无可用于判断的完成回放日",
      excludedDates.length > 0
        ? `剔除日期：${excludedDates.join("、")}`
        : "无剔除日期",
      ...blockedReasons,
    ];
    if (windowStatus.completed_zero_signal_dates.length > 0) {
      detailParts.push(`完成但无信号日期：${windowStatus.completed_zero_signal_dates.join("、")}`);
    }
    detailParts.push("仅作观察，不推导策略有效性");
    return detailParts.join(" / ");
  }
  if (replayStatus === "missing") {
    return "待补：候选历史回放未接通";
  }
  if (replayEvidence) {
    const rowCount = Number.isFinite(replayEvidence.row_count) ? replayEvidence.row_count : 0;
    const matchedEntryCount = Number.isFinite(replayEvidence.matched_entry_count)
      ? replayEvidence.matched_entry_count
      : 0;
    return `候选历史回放已接通：${rowCount} 条快照 / 覆盖 ${matchedEntryCount} 个当前候选`;
  }
  return "候选历史回放已接通";
}

function closedLoopReplayBadges(
  replayStatusRaw: LivermoreSignalConfluencePayload["closed_loop_state"] extends infer State
    ? State extends { replay_status?: infer ReplayStatus }
      ? ReplayStatus
      : unknown
    : unknown,
): string[] | undefined {
  const windowStatus = replayStatusWindow(replayStatusRaw);
  if (!windowStatus) {
    return undefined;
  }
  return [
    `完成 ${windowStatus.completed_dates}日`,
    `待成熟 ${windowStatus.pending_dates}日`,
    `不可用 ${windowStatus.unsupported_dates}日`,
    `代理观察 ${windowStatus.proxy_only_dates}日`,
    `完成样本 ${windowStatus.completed_candidate_rows}`,
  ];
}

function localizeReplayReasonCode(reasonCode: string | null | undefined): string {
  const normalized = (reasonCode ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    missing_daily_limit_flags: "涨跌停标记缺失",
    missing_candidate_history_receipt: "缺少历史回放执行回执",
    missing_required_source_table: "必需数据源缺失",
    forward_returns_pending: "远期收益待成熟",
    proxy_theme_only: "仅代理题材",
    real_theme_inputs_unconfirmed: "真实题材输入待确认",
  };
  if (!normalized) return "原因待补";
  if (normalized.includes("source_table") && normalized.includes("missing")) return "数据源缺失";
  return labels[normalized] ?? "原因待确认";
}

function normalizeClosedLoopStatus(value: unknown, defaultValue: string): string {
  if (typeof value === "string") {
    return value;
  }
  const windowStatus = replayStatusWindow(value);
  if (!windowStatus) return defaultValue;
  const maturityStatus = windowStatus.maturity_status?.trim().toLowerCase();
  if (windowStatus.has_decision_usable_completed_stats !== true) {
    return maturityStatus && maturityStatus !== "ready" ? maturityStatus : "insufficient";
  }
  if (maturityStatus !== "ready") {
    return maturityStatus || "missing";
  }
  return windowStatus.window_status;
}

function replayStatusWindow(value: unknown): NormalizedConfluenceReplayStatus | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as {
    window_status?: unknown;
    snapshot_from?: unknown;
    snapshot_to?: unknown;
    requested_snapshot_from?: unknown;
    requested_snapshot_to?: unknown;
    observed_snapshot_from?: unknown;
    observed_snapshot_to?: unknown;
    metric_basis?: unknown;
    research_metric_basis?: unknown;
    maturity_status?: unknown;
    has_decision_usable_completed_stats?: unknown;
    completed_dates?: unknown;
    pending_dates?: unknown;
    unsupported_dates?: unknown;
    proxy_only_dates?: unknown;
    completed_candidate_rows?: unknown;
    pending_candidate_rows?: unknown;
    unsupported_candidate_rows?: unknown;
    proxy_only_candidate_rows?: unknown;
    matched_entry_count?: unknown;
    has_required_horizon_stats?: unknown;
    included_completed_stats_dates?: unknown;
    blocked_dates?: unknown;
    completed_zero_signal_dates?: unknown;
  };
  if (!isBacktestWindowSummaryStatus(candidate.window_status)) {
    return null;
  }
  return {
    window_status: candidate.window_status,
    snapshot_from: typeof candidate.snapshot_from === "string" ? candidate.snapshot_from : null,
    snapshot_to: typeof candidate.snapshot_to === "string" ? candidate.snapshot_to : null,
    requested_snapshot_from:
      typeof candidate.requested_snapshot_from === "string" ? candidate.requested_snapshot_from : null,
    requested_snapshot_to:
      typeof candidate.requested_snapshot_to === "string" ? candidate.requested_snapshot_to : null,
    observed_snapshot_from:
      typeof candidate.observed_snapshot_from === "string" ? candidate.observed_snapshot_from : null,
    observed_snapshot_to:
      typeof candidate.observed_snapshot_to === "string" ? candidate.observed_snapshot_to : null,
    metric_basis: typeof candidate.metric_basis === "string" ? candidate.metric_basis : null,
    research_metric_basis:
      typeof candidate.research_metric_basis === "string" ? candidate.research_metric_basis : null,
    maturity_status: typeof candidate.maturity_status === "string" ? candidate.maturity_status : undefined,
    has_decision_usable_completed_stats: candidate.has_decision_usable_completed_stats === true,
    completed_dates: finiteCount(candidate.completed_dates),
    pending_dates: finiteCount(candidate.pending_dates),
    unsupported_dates: finiteCount(candidate.unsupported_dates),
    proxy_only_dates: finiteCount(candidate.proxy_only_dates),
    completed_candidate_rows: finiteCount(candidate.completed_candidate_rows),
    pending_candidate_rows: finiteCount(candidate.pending_candidate_rows),
    unsupported_candidate_rows: finiteCount(candidate.unsupported_candidate_rows),
    proxy_only_candidate_rows: finiteCount(candidate.proxy_only_candidate_rows),
    matched_entry_count: finiteCount(candidate.matched_entry_count),
    has_required_horizon_stats: candidate.has_required_horizon_stats === true,
    included_completed_stats_dates: stringList(candidate.included_completed_stats_dates),
    blocked_dates: blockedReplayDates(candidate.blocked_dates),
    completed_zero_signal_dates: stringList(candidate.completed_zero_signal_dates),
  };
}

function closedLoopReplayRangeLabel(
  label: string,
  snapshotFrom: string | null | undefined,
  snapshotTo: string | null | undefined,
): string {
  if (snapshotFrom && snapshotTo) return `${label}：${snapshotFrom} 至 ${snapshotTo}`;
  if (snapshotFrom) return `${label}：自 ${snapshotFrom} 起，截止日待确认`;
  if (snapshotTo) return `${label}：起始日待确认，截至 ${snapshotTo}`;
  return `${label}待确认`;
}

function closedLoopReplayMetricBasisLabel(value: string | null | undefined): string {
  if (value === "net_next_open_adj") {
    return "决策口径：次日开盘、含费、复权净收益";
  }
  return "决策口径待确认";
}

function closedLoopReplayMaturityLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  const labels: Record<string, string> = {
    ready: "已成熟",
    partial: "部分成熟",
    insufficient: "样本不足",
    pending: "待成熟",
    unsupported: "不可用",
    proxy_only: "仅代理观察",
    missing: "待确认",
  };
  return (normalized && labels[normalized]) || "待确认";
}

function isBacktestWindowSummaryStatus(value: unknown): value is BacktestWindowSummaryStatus {
  return value === "valid" || value === "partial" || value === "unsupported";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function blockedReplayDates(value: unknown): NormalizedConfluenceReplayBlockedDate[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const row = item as {
      trade_date?: unknown;
      status?: unknown;
      reason_code?: unknown;
      signal_kinds?: unknown;
    };
    if (typeof row.trade_date !== "string" || typeof row.reason_code !== "string") {
      return [];
    }
    return [
      {
        trade_date: row.trade_date,
        status: normalizeBlockedReplayDateStatus(row.status, row.reason_code),
        reason_code: row.reason_code,
        signal_kinds: stringList(row.signal_kinds),
      },
    ];
  });
}

function normalizeBlockedReplayDateStatus(
  value: unknown,
  reasonCode: string,
): ConfluenceReplayBlockedDate["status"] {
  if (value === "pending" || value === "unsupported" || value === "proxy_only") {
    return value;
  }
  if (reasonCode === "forward_returns_pending") {
    return "pending";
  }
  if (reasonCode === "proxy_theme_only" || reasonCode === "real_theme_inputs_unconfirmed") {
    return "proxy_only";
  }
  return "unsupported";
}

function buildDecisionReferenceRating(items: StockClosedLoopSummaryItem[]): StockDecisionReferenceRating {
  const negativeItems = items.filter((item) => item.tone === "negative");
  if (negativeItems.length > 0) {
    return {
      code: "blocked",
      label: "拦截",
      tone: "negative",
      detail: `${closedLoopItemLabels(negativeItems)} 已触发拦截或退出，先保留复核队列。`,
    };
  }

  const missingItems = items.filter(
    (item) =>
      String(item.status).toLowerCase() === "missing" ||
      item.status === "unsupported" ||
      item.status === "insufficient",
  );
  if (missingItems.length > 0) {
    return {
      code: "insufficient_data",
      label: "数据不足",
      tone: "warning",
      detail: `${closedLoopItemLabels(missingItems)} 待补，不能作为中性证明。`,
    };
  }

  const warningItems = items.filter((item) => item.tone === "warning");
  if (warningItems.length > 0) {
    return {
      code: "pause",
      label: "暂缓",
      tone: "warning",
      detail: `${closedLoopItemLabels(warningItems)} 仍有降级或仅观察边界。`,
    };
  }

  return {
    code: "reviewable",
    label: "可复核",
    tone: "positive",
    detail: "闭环证据完整，可进入人工复核队列。",
  };
}

function closedLoopItemLabels(items: StockClosedLoopSummaryItem[]): string {
  return items.map((item) => item.label).join("、");
}

function closedLoopStatusLabel(key: StockClosedLoopSummaryItem["key"], status: string): string {
  const normalized = String(status).toLowerCase();
  if (normalized === "valid") return "可用";
  if (normalized === "ready" || normalized === "landed") return "可用";
  if (normalized === "missing_inputs" || normalized === "no_data") return "待补";
  if (normalized === "partial") return "部分有效";
  if (normalized === "insufficient") return "样本不足";
  if (normalized === "pending") return "待成熟";
  if (normalized === "proxy_only") return "仅代理观察";
  if (normalized === "unsupported") return "不可用";
  if (normalized === "missing") return "待补";
  if (normalized === "degrade" || normalized === "degraded" || normalized === "stale" || normalized === "error") {
    return "降级";
  }
  if (normalized === "observe_only") return "仅观察";
  if (normalized === "block" || normalized === "blocked") return "阻断";
  if (normalized === "triggered") return "已触发";
  if (normalized === "available") return "已接通";
  if (normalized === "complete") return "完整";
  if (normalized === "open") return "开放";
  if (normalized === "watch") return "观察中";
  if (normalized === "pass" || normalized === "allow" || normalized === "ok") return "通过";
  return key === "lineage" ? "待确认" : "状态待确认";
}

function closedLoopAdversarialDetail(
  adversarial: LivermoreSignalConfluencePayload["adversarial_context"] | null,
): string {
  const reason = adversarial?.strongest_block_reason?.trim();
  if (reason) {
    return localizeStockBackendText(reason);
  }
  const fallbackValues = [adversarial?.mode, adversarial?.status, adversarial?.risk_gate];
  if (fallbackValues.some(isTechnicalStockFallbackText)) {
    return "\u53cd\u62e5\u6324\u72b6\u6001\u5f85\u786e\u8ba4";
  }
  const mode = adversarial?.mode?.trim().toLowerCase();
  const evidenceLabel =
    mode === "final_signal"
      ? "\u6700\u7ec8\u4fe1\u53f7\u8bc1\u636e"
      : mode === "crowding_latest"
        ? "\u6700\u65b0\u62e5\u6324\u5ea6\u5feb\u7167"
        : "\u53cd\u62e5\u6324\u8bc1\u636e";
  const riskGateLabel = closedLoopStatusLabel("adversarial_gate", adversarial?.risk_gate ?? "missing");
  return `${evidenceLabel}\uff0c\u53cd\u62e5\u6324\u95e8${riskGateLabel}`;
}

function isTechnicalStockFallbackText(value: string | null | undefined): boolean {
  const normalized = value?.toLowerCase() ?? "";
  return (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("choice_stock") ||
    normalized.includes("source_table")
  );
}

function closedLoopExitCounts(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): { watchCount: number; triggeredCount: number } {
  const observations = confluence?.exit_observations ?? [];
  if (observations.length > 0) {
    return {
      watchCount: observations.filter((item) => item.action !== "exit_triggered" && !item.triggered).length,
      triggeredCount: observations.filter((item) => item.action === "exit_triggered" || item.triggered).length,
    };
  }
  return {
    watchCount: payload.risk_exit?.watch_items?.length ?? 0,
    triggeredCount: payload.risk_exit?.items?.length ?? 0,
  };
}

function closedLoopTone(key: StockClosedLoopSummaryItem["key"], status: string): StockClosedLoopTone {
  const normalized = String(status).toLowerCase();
  if (normalized === "partial" || normalized === "unsupported") {
    return "warning";
  }
  if (
    normalized === "missing" ||
    normalized === "degrade" ||
    normalized === "degraded" ||
    normalized === "stale" ||
    normalized === "error" ||
    normalized === "insufficient" ||
    normalized === "pending" ||
    normalized === "proxy_only" ||
    normalized === "observe_only" ||
    normalized === "partial" ||
    normalized === "unsupported"
  ) {
    return "warning";
  }
  if (normalized === "block" || normalized === "blocked" || normalized === "triggered") {
    return "negative";
  }
  if (
    normalized === "pass" ||
    normalized === "allow" ||
    normalized === "ok" ||
    normalized === "open" ||
    normalized === "watch" ||
    normalized === "available" ||
    normalized === "complete"
  ) {
    return "positive";
  }
  return key === "adversarial_gate" ? "warning" : "neutral";
}

function deriveEntryGateStatus(state: LivermoreSignalConfluencePayload["closed_loop_state"] | null): string {
  const status = String((state as Record<string, unknown> | null)?.status ?? "").toLowerCase();
  const action = String((state as Record<string, unknown> | null)?.entry_observation_action ?? "").toLowerCase();
  if (status.includes("blocked") || action === "blocked") return "blocked";
  if (action === "observe_entry_setup") return "open";
  if (action === "observe_only") return "observe_only";
  if (status === "open") return "open";
  if (status === "observe_only") return "observe_only";
  return "missing";
}

function deriveExitGateStatus(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): string {
  const exits = confluence?.exit_observations ?? [];
  if (exits.some((item) => item.action === "exit_triggered" || item.triggered)) return "triggered";
  if (exits.length > 0 || (payload.risk_exit?.watch_items?.length ?? 0) > 0) return "watch";
  if ((payload.risk_exit?.items?.length ?? 0) > 0) return "triggered";
  return "missing";
}

function deriveLineageStatus(
  adversarial: LivermoreSignalConfluencePayload["adversarial_context"] | null | undefined,
  state: LivermoreSignalConfluencePayload["closed_loop_state"] | null,
): string {
  const stateStatus = String((state as Record<string, unknown> | null)?.status ?? "").toLowerCase();
  if (stateStatus.includes("missing")) return "missing";
  if (stateStatus.includes("degraded")) return "degraded";

  const adversarialStatus = String(adversarial?.status ?? "").toLowerCase();
  if (adversarialStatus === "missing") return "missing";
  if (adversarialStatus === "degraded" || adversarialStatus === "error") return "degraded";
  if (adversarialStatus === "ok" || adversarialStatus === "complete") return "complete";
  return "missing";
}
