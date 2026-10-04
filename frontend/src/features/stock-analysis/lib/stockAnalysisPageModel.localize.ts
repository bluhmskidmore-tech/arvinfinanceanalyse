// Backend text / status localization for the stock-analysis page model.

export function localizeMetaQualityFlag(value: string | undefined): string {
  const normalized = (value ?? "pending").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "质量正常",
    warning: "质量需复核",
    stale: "数据陈旧",
    error: "质量异常",
    pending: "质量待确认",
  };
  return labels[normalized] ?? "质量待确认";
}

export function localizeMetaVendorStatus(value: string | undefined): string {
  const normalized = (value ?? "pending").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "供数正常",
    vendor_stale: "供数陈旧",
    vendor_unavailable: "供数不可用",
    degraded: "供数降级",
    error: "供数异常",
    pending: "供数待确认",
  };
  return labels[normalized] ?? "供数待确认";
}

export function localizeFallbackMode(value: string | undefined): string {
  const normalized = (value ?? "none").trim().toLowerCase();
  if (!normalized || normalized === "none") return "数据正常";
  const labels: Record<string, string> = {
    latest_snapshot: "数据延迟",
    cache: "数据延迟",
    mock: "演示数据",
  };
  return labels[normalized] ?? "待确认";
}

export function localizeStockDataFamily(inputFamily: string | null | undefined): string {
  const value = inputFamily?.trim();
  if (!value) return "待补";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    breadth: "市场宽度",
    limit_up_quality: "涨停质量",
    sector_strength: "板块强弱",
    sector_rank: "板块强弱",
    stock_universe: "股票池",
    stock_candidates: "趋势候选",
    stock_candidate: "趋势候选",
    uptrend_momentum_candidates: "上升趋势",
    uptrend_momentum: "上升趋势",
    fresh_trend_watchlist: "新趋势观察",
    mean_reversion_candidates: "超跌池",
    factor_screen_candidates: "多因子",
    factor_screen: "多因子",
    theme_breakout: "题材观察",
    theme_taxonomy: "\u9898\u6750\u5206\u7c7b",
    hybrid_fusion: "融合池",
    risk_exit: "风险退出",
    position_risk: "持仓风险",
    market_gate: "市场门控",
    pmi: "PMI",
    credit_impulse: "信用脉冲",
    macro_score: "宏观分",
    price_spread: "价差",
  };
  return labels[normalized] ?? "输入待确认";
}

export function localizeDataGapStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ready: "已就绪",
    missing: "缺数据",
    stale: "已陈旧",
    partial: "部分",
    blocked: "阻断",
  };
  return labels[normalized] ?? (normalized ? "状态待确认" : "待补");
}

export function localizeDiagnosticScope(inputFamily: string | null | undefined): string {
  const familyLabel = localizeStockDataFamily(inputFamily);
  return familyLabel === "待补" ? "策略诊断" : `${familyLabel}诊断`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function scrubUnknownBackendFamily(value: string, inputFamily: string | null | undefined, familyLabel: string): string {
  const rawFamily = inputFamily?.trim();
  if (!rawFamily || familyLabel !== "输入待确认") return value;
  const spacedFamily = rawFamily.replace(/[_-]+/g, " ");
  return value
    .replace(new RegExp(escapeRegExp(rawFamily), "gi"), familyLabel)
    .replace(new RegExp(escapeRegExp(spacedFamily), "gi"), familyLabel);
}

function isUnknownBackendCodeOnly(value: string, familyLabel: string): boolean {
  if (familyLabel !== "输入待确认") return false;
  return /^[A-Za-z][A-Za-z0-9_.:-]*$/.test(value) && /[_:.-]/.test(value);
}

export function localizeStockBackendText(
  text: string | null | undefined,
  inputFamily?: string | null,
): string {
  const value = text?.trim();
  if (!value) return "说明待补";
  const lower = value.toLowerCase();
  const familyLabel = inputFamily ? localizeStockDataFamily(inputFamily) : "";
  const displayValue = scrubUnknownBackendFamily(value, inputFamily, familyLabel);
  if (isUnknownBackendCodeOnly(value, familyLabel)) return "说明待确认";
  if ((lower.includes("external_vendor") || lower.includes("vendor_")) && /pending|guard|unavailable/.test(lower)) {
    return "风险待确认";
  }
  if (lower.includes("external_vendor") || lower.includes("vendor_")) {
    if (lower.includes("not landed") || lower.includes("未落地")) return `${familyLabel || "输入待确认"} 未落地`;
    return "说明待确认";
  }
  const availableSample = value.match(/\b(T\+\d+)\s+available\s+(\d+)\s*\/\s*(\d+)/i);
  const matureSnapshotSample = value.match(/\b(T\+\d+)\s+matured?\s+snapshots?\s+(\d+)\s*\/\s*(\d+)/i);
  const optimizationSample = value.match(/\b(T\+\d+)\s+sample\s+(\d+)/i);
  const optimizationAvgReturn = value.match(/\bavg(?:erage)?(?:\s+return)?\s*([+-]?\d+(?:\.\d+)?%)/i);
  const optimizationWinRate = value.match(/\bwin\s+rate\s*([+-]?\d+(?:\.\d+)?%)/i);
  if (lower.includes("current market sample") && lower.includes("insufficient")) {
    const sampleText = availableSample
      ? `${availableSample[1].toUpperCase()} ${availableSample[2]}/${availableSample[3]}`
      : "";
    return sampleText ? `样本不足 ${sampleText}` : "样本不足";
  }
  if (matureSnapshotSample) {
    const suffix = lower.includes("waiting for more mature days") ? "等待更多成熟日。" : "可作为强优先复核。";
    return `${matureSnapshotSample[1].toUpperCase()} 已成熟快照 ${matureSnapshotSample[2]}/${matureSnapshotSample[3]}，${suffix}`;
  }
  if (optimizationSample && (optimizationAvgReturn || optimizationWinRate || lower.includes("priority review ranking"))) {
    const parts = [`${optimizationSample[1].toUpperCase()} 样本 ${optimizationSample[2]}`];
    if (optimizationAvgReturn) parts.push(`均值 ${optimizationAvgReturn[1]}`);
    if (optimizationWinRate) parts.push(`胜率 ${optimizationWinRate[1]}`);
    if (lower.includes("priority review ranking")) parts.push("优先复核排序");
    return `${parts.join("，")}。`;
  }
  if (lower.includes("observation-only candidate")) {
    return `${familyLabel || "候选"}仅观察候选。`;
  }
  if (lower.includes("hybrid fusion") && lower.includes("observation-only") && lower.includes("warm/hot")) {
    return "融合策略仅在温和/偏热门控下进入候选；当前门控不满足时只保留观察。";
  }
  if (lower.includes("hybrid fusion") && lower.includes("proxy inputs")) {
    return "融合策略使用代理输入，仅作观察复核。";
  }
  if (lower.includes("stock candidate policy") && lower.includes("inactive in overheat")) {
    return "趋势突破策略在过热门控下暂停；仅在偏热/温和门控下进入候选。";
  }
  if (lower.includes("uptrend momentum watchlist is paused") && lower.includes("warm or hot")) {
    return "上升趋势策略在过热门控下暂停；仅在温和/偏热门控下进入候选。";
  }
  if (lower.includes("mean reversion watchlist is paused") && lower.includes("overheat")) {
    return "超跌反弹观察池在过热门控下暂停；当前由防守趋势候选覆盖。";
  }
  if (lower.includes("daily_limit_flags absent") && lower.includes("replay unsupported")) {
    const dateMatch = value.match(/\b(\d{4}-\d{2}-\d{2})\b/);
    return `涨停封单标记缺失；${dateMatch?.[1] ?? "该日"} 回放不可用。`;
  }
  if (lower.includes("overheat") && lower.includes("rank > 10") && lower.includes("factor")) {
    return "过热门控下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。";
  }
  if (lower.includes("observation-only output") && lower.includes("does not generate trading instructions")) {
    return "仅输出观察结果，不生成交易指令。";
  }
  if (lower.includes("no stock candidates available for observation")) {
    return "当前门控下暂无趋势候选进入观察。";
  }
  if (lower.includes("breadth inputs are unavailable")) {
    return "市场宽度输入不可用。";
  }
  if (
    lower.includes("choice limit-up quality catalog is confirmed") &&
    lower.includes("trend-only slice")
  ) {
    return "涨停质量目录已确认，但落地输入不可用；市场门控已限制为仅趋势切片。";
  }
  if (lower.includes("choice stock materialized input coverage is incomplete")) {
    const dateMatch = value.match(/for (\d{4}-\d{2}-\d{2})/i);
    const itemsMatch = value.match(/request items:\s*(.+)$/i);
    const datePart = dateMatch?.[1] ?? "目标日";
    const itemsPart = itemsMatch?.[1]?.replace(/:/g, "：") ?? "部分输入";
    return `Choice 股票物化输入覆盖不完整（${datePart}）；缺数据项：${itemsPart}。`;
  }
  if (lower.includes("materialized input coverage incomplete")) {
    return `${familyLabel || "策略"}物化输入覆盖不完整。`;
  }
  if (lower.includes("5-day breadth input family is not landed")) {
    return "5日市场宽度输入未落地。";
  }
  if (lower.includes("crowded leaders without breadth confirmation")) {
    return "强势样本拥挤，市场宽度未确认。";
  }
  if (lower.includes("concept membership table pending")) {
    return "概念归属待确认。";
  }
  if (lower.includes("signal confluence diagnostic") && lower.includes("pending") && lower.includes("detail")) {
    return "联动诊断待确认。";
  }
  if (lower.includes("factor_snapshot") && lower.includes("无数据")) {
    return "因子快照无数据。";
  }
  if (lower.includes("position snapshot") && lower.includes("not landed")) {
    return "持仓快照未落地。";
  }
  if (
    lower.includes("risk-exit evidence") &&
    lower.includes("position snapshot") &&
    lower.includes("stale")
  ) {
    return "持仓快照已陈旧，风险退出证据待补。";
  }
  if (
    lower.includes("livermore_position_snapshot") ||
    (lower.includes("position snapshot") && (lower.includes("active a-share") || lower.includes("missing")))
  ) {
    return "持仓快照缺失，暂无可执行风险退出样本。";
  }
  if (
    lower.includes("daily sector strength observation rank is a signed-off analytical formula") &&
    lower.includes("not trading instructions")
  ) {
    return "板块强弱观察排名已按 50% 涨跌幅分位、30% 换手率分位、20% 振幅分位签核；用于复核优先级与行业过滤，不构成交易指令；多日动量、板块资金流与拥挤度不包含在当前版本内。";
  }
  if (
    lower.includes("daily sector score is an analytical observation formula") &&
    lower.includes("metric-definition sign-off")
  ) {
    return "板块强弱为分析观察公式，仍待指标定义签核；多日动量持续性与板块资金流不包含在当前公式内。";
  }
  if (lower.includes("pending")) {
    const pendingLabel =
      lower.includes("t+5") || lower.includes("return") || lower.includes("收益") ? "待成熟" : "待确认";
    return displayValue
      .replace(/最新\s*pending\s*日期/gi, `最新${pendingLabel}日期`)
      .replace(/\bpending\b/gi, pendingLabel);
  }
  if (lower.includes("theme breakout execution is paused") && lower.includes("overheat")) {
    return "市场过热门控下暂停题材观察；历史回放显示该桶拖累。";
  }
  if (lower.includes("market gate is available") && lower.includes("pmi") && lower.includes("credit impulse")) {
    return /not landed|missing|unavailable|待补|缺失/.test(lower)
      ? "市场门控已有可用证据，PMI 与信用脉冲待补。"
      : "市场门控、PMI 与信用脉冲已接入。";
  }
  if (lower.includes("all broad-index and supplement gate inputs are landed")) {
    return "宽基指数与补充门控输入已落地，可用于当前交易日。";
  }
  if (lower.includes("sector ranking is available from landed choice sector inputs")) {
    return "板块排名已接入 Choice 板块输入。";
  }
  if (
    lower.includes("sector rank currently uses the provisional percentile formula") &&
    lower.includes("pctchange") &&
    lower.includes("turn") &&
    lower.includes("amplitude")
  ) {
    return "板块强弱仍使用涨跌幅、换手率与振幅的临时分位公式，需按观测口径复核。";
  }
  if (lower.includes("candidate screening is available for landed choice stock inputs")) {
    return "候选筛选已接入 Choice 个股输入。";
  }
  if (lower.includes("risk and exit output is available from landed position snapshots and close history")) {
    return "风险退出已接入持仓快照与收盘历史。";
  }
  if (lower.includes("sector_rank is available")) {
    return "板块强弱已有可用证据。";
  }
  return displayValue
    .replace(/\bbreadth\b/gi, familyLabel || "市场宽度")
    .replace(/\bmarket gate\b/gi, "市场门控")
    .replace(/\binput family\b/gi, "输入")
    .replace(/\bnot landed\b/gi, "未落地")
    .replace(/\bmissing\b/gi, "缺数据")
    .replace(/\bunsupported\b/gi, "不可用")
    .replace(/\bfallback\b/gi, "回退")
    .replace(/\bproxy-only\b/gi, "仅代理观察")
    .replace(/\bproxy\b/gi, "代理观察")
    .replace(/_/g, " ");
}

export function localizeBasisLabel(basis: string | null | undefined): string {
  const normalized = (basis ?? "").trim().toLowerCase();
  if (normalized === "analytical") return "分析口径（非交易）";
  if (normalized === "formal") return "正式口径";
  if (!normalized) return "口径待补";
  return "口径待确认";
}

export function localizeImplementationStage(stage: string): string {
  const normalized = stage.trim().toLowerCase();
  const labels: Record<string, string> = {
    verification_pending: "证据待齐",
    proxy_reconstruction: "代理重建",
    proxy_only: "仅代理观察",
    landed: "已落地",
    partial: "部分就绪",
    missing_inputs: "输入待补",
    provisional: "临时版",
    ready: "就绪",
    no_data: "暂无数据",
  };
  return labels[normalized] ?? "阶段待确认";
}

export function localizeThemeRadarBadge(isProxy: boolean, formulaVersion?: string | null): string {
  if (isProxy) {
    return "代理观察";
  }
  const version = formulaVersion?.trim();
  return version ? `概念库` : "概念库";
}

export function localizeThemeSourceKind(sourceKind: string | undefined, isProxyDefault: boolean): string {
  const normalized = (sourceKind ?? "").trim().toLowerCase();
  if (normalized === "tushare_current_overlay" || normalized === "tushare_ths_current_overlay") {
    return "当前概念覆盖";
  }
  if (normalized === "proxy" || (!normalized && isProxyDefault)) {
    return "代理主题";
  }
  if (
    normalized === "real_concept" ||
    normalized === "concept" ||
    normalized === "choice_point_in_time"
  ) {
    return "时点概念成分";
  }
  if (normalized.includes("proxy")) {
    return "代理主题";
  }
  if (!normalized) {
    return isProxyDefault ? "代理主题" : "时点概念成分";
  }
  return "来源待确认";
}

export function localizeMarketDataStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toUpperCase();
  const labels: Record<string, string> = {
    NO_DATA: "暂无数据",
    STALE: "数据陈旧",
    PENDING_DATA: "数据待补",
    OFF: "关闭",
    WARM: "温和",
    HOT: "偏热",
    OVERHEAT: "过热",
    UNKNOWN: "状态待确认",
  };
  return labels[normalized] ?? (normalized ? "状态待确认" : "状态待补");
}

export function localizeStrategyPanelErrorDetail(errorMessage: string | null | undefined): string {
  const value = errorMessage?.trim();
  if (!value) return "请求失败：错误详情待补。";
  const lower = value.toLowerCase();
  if (lower.includes("source_table") || lower.includes("source table")) {
    return "请求失败：必需数据源缺失，稍后复核供数状态。";
  }
  if (lower.includes("failed to fetch") || lower.includes("network error")) {
    return "请求失败：暂时无法连接策略分析服务。";
  }
  return `请求失败：${localizeStockBackendText(value)}。`;
}
