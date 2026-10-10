import type {
  LivermoreBreakoutPatternCode,
  LivermorePositionSizeHint,
  StockAnalysisWorkbenchPayload,
} from "../../../api/contracts";
import type {
  StockCandidatePattern,
  StockCandidateReviewQueueItem,
  StockCandidateSourcePool,
} from "./stockAnalysisPageModel";
import { CANDIDATE_SOURCE_POOL_LABELS } from "./stockAnalysisPageModel";
import { attachCandidateSizeHintFields } from "./stockAnalysisPositionSizeHintModel";

type WorkbenchReviewCandidate = StockAnalysisWorkbenchPayload["first_screen"]["review_queue"][number];
type CandidateEvidence = StockCandidateReviewQueueItem["primaryEvidence"][number];

const sourceLabels: Record<string, string> = {
  stock_candidates: "趋势候选",
  factor_screen_candidates: "多因子候选",
  hybrid_fusion_candidates: "融合候选",
  uptrend_momentum_candidates: "动量候选",
  fresh_trend_watchlist: "新趋势观察",
  mean_reversion_candidates: "超跌观察",
  theme_breakout: "题材观察",
};

function textValue(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

/** 后端首屏队列的 source_module 到来源池键；未知模块归入 workbench 兜底。 */
function sourcePoolValue(sourceModule: string): StockCandidateSourcePool {
  return sourceModule in CANDIDATE_SOURCE_POOL_LABELS
    ? (sourceModule as StockCandidateSourcePool)
    : "workbench_review_queue";
}

function rankValue(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isBreakoutPatternCode(value: unknown): value is LivermoreBreakoutPatternCode {
  return value === "breakout" || value === "pullback" || value === "consolidation";
}

function patternValue(code: unknown, label: unknown): StockCandidatePattern | null {
  if (!isBreakoutPatternCode(code)) return null;
  return textValue(label);
}

function rawValue(value: unknown): string | null {
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : null;
  if (typeof value === "string") return value.trim() || null;
  return null;
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** 比率（0-1）→ 百分数字符串；signed 时正数补 +。 */
function ratioPercent(value: unknown, signed = false): string | null {
  const numeric = finiteOrNull(value);
  if (numeric == null) return null;
  const pct = numeric * 100;
  return `${signed && pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/** 元 → 亿元字符串。 */
function yuanToYi(value: unknown): string | null {
  const numeric = finiteOrNull(value);
  if (numeric == null) return null;
  return `${(numeric / 100_000_000).toFixed(2)}亿`;
}

function fixedPoint(value: unknown, digits = 2): string | null {
  const numeric = finiteOrNull(value);
  return numeric == null ? null : numeric.toFixed(digits);
}

function evidenceFields(row: WorkbenchReviewCandidate) {
  const entries: CandidateEvidence[] = [];
  const push = (key: string, label: string, value: string | null) => {
    if (value != null && value !== "") entries.push({ key, label, value });
  };
  // 数值来源字段：展示字符串保持原样，同时把后端原值放进 numeric，供下游按后端单位计算。
  const pushNumeric = (key: string, label: string, raw: unknown, value: string | null) => {
    if (value == null || value === "") return;
    entries.push({ key, label, value, numeric: finiteOrNull(raw) });
  };

  // 首屏既有字段保持原样输出，避免破坏既有契约与测试。
  pushNumeric("score", "观察分", row.score, rawValue(row.score));
  pushNumeric("factor_score", "因子分", row.factor_score, rawValue(row.factor_score));
  pushNumeric("fusion_score", "融合分", row.fusion_score, rawValue(row.fusion_score));
  pushNumeric("pe", "PE 原值", row.pe, fixedPoint(row.pe, 2) ?? rawValue(row.pe));
  pushNumeric("pb", "PB 原值", row.pb, fixedPoint(row.pb, 2) ?? rawValue(row.pb));
  pushNumeric("close", "收盘价", row.close, rawValue(row.close));
  pushNumeric("breakout_level", "突破位", row.breakout_level, rawValue(row.breakout_level));

  // workbench 首屏队列返回但此前未映射的真实字段。
  pushNumeric("pctchange", "涨跌幅", row.pctchange, rawValue(row.pctchange));
  pushNumeric("ps", "市销率", row.ps, fixedPoint(row.ps, 2));
  pushNumeric("roe", "ROE", row.roe, ratioPercent(row.roe));
  pushNumeric("gross_margin", "毛利率", row.gross_margin, ratioPercent(row.gross_margin));
  pushNumeric("dividend_yield", "股息率", row.dividend_yield, ratioPercent(row.dividend_yield));
  pushNumeric("three_month_return", "近3月收益", row.three_month_return, ratioPercent(row.three_month_return, true));
  pushNumeric("twelve_month_return", "近12月收益", row.twelve_month_return, ratioPercent(row.twelve_month_return, true));
  pushNumeric("volatility", "波动率", row.volatility, ratioPercent(row.volatility));
  pushNumeric("daily_amount", "成交额(日)", row.daily_amount, yuanToYi(row.daily_amount));
  pushNumeric("total_mv", "总市值", row.total_mv, yuanToYi(row.total_mv));
  pushNumeric("circ_mv", "流通市值", row.circ_mv, yuanToYi(row.circ_mv));
  pushNumeric(
    "abnormal_turnover",
    "异常换手",
    row.abnormal_turnover,
    fixedPoint(row.abnormal_turnover, 2)?.replace(/^(.+)$/, "$1x") ?? null,
  );
  pushNumeric("close_strength", "收盘强度", row.close_strength, fixedPoint(row.close_strength, 3));
  pushNumeric("gap_norm", "跳空幅度(归一)", row.gap_norm, fixedPoint(row.gap_norm, 3));
  pushNumeric(
    "breakout_extension_norm",
    "突破延伸(归一)",
    row.breakout_extension_norm,
    fixedPoint(row.breakout_extension_norm, 3),
  );
  pushNumeric("ema10", "EMA10", row.ema10, fixedPoint(row.ema10, 2));
  pushNumeric("ma20", "MA20", row.ma20, fixedPoint(row.ma20, 2));
  pushNumeric("ma60", "MA60", row.ma60, fixedPoint(row.ma60, 2));
  pushNumeric("ma120", "MA120", row.ma120, fixedPoint(row.ma120, 2));
  pushNumeric(
    "sector_rank",
    "板块内排名",
    row.sector_rank,
    finiteOrNull(row.sector_rank) != null ? `#${finiteOrNull(row.sector_rank)}` : null,
  );
  pushNumeric(
    "distance_to_breakout_pct",
    "距突破位",
    row.distance_to_breakout_pct,
    fixedPoint(row.distance_to_breakout_pct, 2)?.replace(/^(.+)$/, "$1%") ?? null,
  );
  if (typeof row.liquidity_floor_pass === "boolean") {
    push("liquidity_floor_pass", "流动性门槛", row.liquidity_floor_pass ? "通过" : "未通过");
  }
  // 方案 b：缺因子打分的行透出缺失因子清单（键 → 中文名），解释综合分为何缺省。
  if (Array.isArray(row.factor_missing_inputs) && row.factor_missing_inputs.length > 0) {
    const inputLabels: Record<string, string> = {
      pe: "市盈率",
      pb: "市净率",
      ps: "市销率",
      roe: "ROE",
      gross_margin: "毛利率",
    };
    const labels = row.factor_missing_inputs.map((key) => inputLabels[String(key)] ?? String(key));
    push("factor_missing_inputs", "综合分缺失因子", labels.join("、"));
  }
  return entries;
}

function themeSourceLabel(value: unknown): string | null {
  const sourceKind = textValue(value)?.toLowerCase();
  if (!sourceKind) return null;
  if (sourceKind === "tushare_current_overlay" || sourceKind === "tushare_ths_current_overlay") {
    return "当前概念覆盖";
  }
  if (sourceKind === "real_concept" || sourceKind === "choice_point_in_time") {
    return "时点概念成分";
  }
  if (sourceKind === "proxy") return "代理主题";
  return "来源待确认";
}

function themeMembershipEvidence(row: WorkbenchReviewCandidate) {
  if (!Array.isArray(row.theme_memberships)) return [];
  return row.theme_memberships.flatMap((value, index) => {
    if (value == null || typeof value !== "object") return [];
    const membership = value as Record<string, unknown>;
    const themeKey = textValue(membership.theme_key);
    const themeName = textValue(membership.theme_name) ?? themeKey;
    if (!themeName) return [];
    const themeRank = rawValue(membership.rank);
    const memberRank = rawValue(membership.member_rank);
    const sourceLabel = themeSourceLabel(membership.source_kind);
    const parts = [
      themeRank ? `${themeName} #${themeRank}` : themeName,
      sourceLabel,
      memberRank ? `成分 #${memberRank}` : null,
    ].filter((item): item is string => Boolean(item));
    return [
      {
        key: `theme_membership:${themeKey ?? themeName}:${index}`,
        label: "题材归属",
        value: parts.join(" · "),
      },
    ];
  });
}

function uniqueEvidence(items: CandidateEvidence[]): CandidateEvidence[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const identity = `${item.label}\u0000${item.value}`;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}

function uniqueText(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

function isThemeReviewCandidate(row: WorkbenchReviewCandidate): boolean {
  return textValue(row.source_module) === "theme_breakout" || themeMembershipEvidence(row).length > 0;
}

export function selectStockCandidateThemeEvidence(card: StockCandidateReviewQueueItem): CandidateEvidence[] {
  return uniqueEvidence(
    [...(card.primaryEvidence ?? []), ...(card.supportingEvidence ?? []), ...(card.rawFields ?? [])].filter(
      (item) => item.label === "题材归属" || item.key.startsWith("theme_membership:"),
    ),
  );
}

export function resolveStockAnalysisFormalUseAllowed(
  payloadFormalUseAllowed: boolean | null | undefined,
  resultMetaFormalUseAllowed: boolean | null | undefined,
): boolean {
  return payloadFormalUseAllowed === true && resultMetaFormalUseAllowed === true;
}

export function buildStockAnalysisWorkbenchReviewQueue(
  rows: StockAnalysisWorkbenchPayload["first_screen"]["review_queue"],
): StockCandidateReviewQueueItem[] {
  return rows.flatMap((row, index) => {
    const stockCode = textValue(row.stock_code);
    if (!stockCode) return [];

    const rank = rankValue(row.rank, index + 1);
    const stockName = textValue(row.stock_name) ?? stockCode;
    const sectorCode = textValue(row.sector_code) ?? "";
    const sectorName = textValue(row.sector_name) ?? textValue(row.industry) ?? "接口未提供";
    const sourceModule = textValue(row.source_module) ?? "workbench_review_queue";
    const sourceLabel = sourceLabels[sourceModule] ?? "后端观察队列";
    const rowPattern = patternValue(row.pattern_code, row.pattern);
    const rowDistancePct = finiteNumber(row.distance_to_breakout_pct);
    const rowClose = finiteNumber(row.close);
    const rowBreakoutLevel = finiteNumber(row.breakout_level);
    const rowStalePriceDate = row.price_stale === true ? textValue(row.price_as_of_date) : null;
    const observedFields = evidenceFields(row);
    const membershipEvidence = themeMembershipEvidence(row);
    const sourceEvidence = [
      { key: "source_module", label: "来源模块", value: sourceLabel },
      { key: "api_rank", label: "接口排序", value: `#${rank}` },
    ];
    const sourceIdentityEvidence = {
      key: "source_module_key",
      label: "来源模块标识",
      value: sourceModule,
    };
    const evidence = [...membershipEvidence, ...sourceEvidence, ...observedFields];
    const firstThemeName = Array.isArray(row.theme_memberships)
      ? row.theme_memberships
          .map((value) =>
            value != null && typeof value === "object"
              ? textValue((value as Record<string, unknown>).theme_name)
              : null,
          )
          .find((value): value is string => Boolean(value))
      : null;
    const usesCurrentOverlay = Array.isArray(row.theme_memberships)
      ? row.theme_memberships.some(
          (value) =>
            value != null &&
            typeof value === "object" &&
            themeSourceLabel((value as Record<string, unknown>).source_kind) === "当前概念覆盖",
        )
      : false;
    const boundaryEvidence = [
      "候选来自 workbench 首屏只读队列；门禁与正式用途边界以接口状态为准。",
      ...(usesCurrentOverlay ? ["当前覆盖 · 非时点 · 不可历史使用 · 仅观察"] : []),
    ];

    return [
      {
        rank,
        stockCode,
        stockName,
        sectorCode,
        sectorName,
        headline: `${sourceLabel} #${rank} · ${stockName}`,
        sourcePool: sourcePoolValue(sourceModule),
        sourcePoolLabel: sourceLabel,
        // 首屏 workbench 队列接口不返回池级 walk_forward，不渲染判定徽章。
        walkForward: null,
        pattern: rowPattern ?? "接口未提供",
        patternNote: rowPattern
          ? rowClose != null && rowBreakoutLevel != null
            ? rowStalePriceDate
              ? `收盘 ${rowClose} / 突破位 ${rowBreakoutLevel}（价格日 ${rowStalePriceDate}，停牌滞后）`
              : `收盘 ${rowClose} / 突破位 ${rowBreakoutLevel}（观察口径）`
            : "形态标签由接口按突破位几何返回，观察口径。"
          : "首屏候选接口未提供形态标签，页面不补算。",
        distanceToBreakoutPct:
          rowDistancePct != null ? `${rowDistancePct.toFixed(2)}%` : "待复核",
        // 单行 ≤1 个 ·(§7)：主体“名称（行业） · 来源”，题材补充改逗号衔接。
        reviewFocus: [
          `${stockName}（${sectorName}） · ${sourceLabel}`,
          membershipEvidence.length > 0
            ? `题材归属：${membershipEvidence.map((item) => item.value).join(" / ")}`
            : firstThemeName,
        ]
          .filter(Boolean)
          .join("，"),
        primaryEvidence: evidence.slice(0, 3),
        supportingEvidence: evidence.slice(3),
        boundaryEvidence,
        invalidationFocus: "价格形态与风险退出条件待在个股详情复核。",
        invalidationRules: ["接口未返回正式交易或退出指令。"],
        rawFields: uniqueEvidence([...evidence, sourceIdentityEvidence]),
      },
    ];
  });
}

function candidateReviewIdentity(
  candidate: StockCandidateReviewQueueItem,
  sourceModuleOverride?: string | null,
): string | null {
  const sourceModule = (sourceModuleOverride ?? candidate.rawFields.find((field) => field.key === "source_module_key")?.value)
    ?.trim().toLowerCase();
  const stockCode = candidate.stockCode.trim().toUpperCase();
  if (!sourceModule || !stockCode) return null;
  return `${sourceModule}\u0000${stockCode}`;
}

export function enrichStockAnalysisWorkbenchReviewQueue(
  workbenchQueue: StockCandidateReviewQueueItem[],
  strategyQueue: StockCandidateReviewQueueItem[],
  strategySourceModule: string | null = null,
  positionSizeHint: LivermorePositionSizeHint | null | undefined = null,
): StockCandidateReviewQueueItem[] {
  // 建议仓位 hint 仅对趋势候选（stock_candidates）有业务含义，其他来源不注入徽章字段。
  const sizedStrategyQueue =
    strategySourceModule === "stock_candidates"
      ? attachCandidateSizeHintFields(strategyQueue, positionSizeHint)
      : strategyQueue;
  const strategyByIdentity = new Map(
    sizedStrategyQueue.flatMap((candidate) => {
      const identity = candidateReviewIdentity(candidate, strategySourceModule);
      return identity ? [[identity, candidate] as const] : [];
    }),
  );

  return workbenchQueue.map((workbenchCandidate) => {
    const identity = candidateReviewIdentity(workbenchCandidate);
    const strategyCandidate = identity ? strategyByIdentity.get(identity) : undefined;
    if (!strategyCandidate) return workbenchCandidate;

    const workbenchThemeEvidence = selectStockCandidateThemeEvidence(workbenchCandidate);
    const visibleEvidence = uniqueEvidence([
      ...workbenchThemeEvidence,
      ...strategyCandidate.primaryEvidence,
      ...strategyCandidate.supportingEvidence,
    ]);
    const workbenchHasSectorCode = Boolean(workbenchCandidate.sectorCode.trim());
    const workbenchHasSectorName =
      Boolean(workbenchCandidate.sectorName.trim()) &&
      workbenchCandidate.sectorName !== "接口未提供";
    const strategySectorMatchesWorkbench =
      workbenchHasSectorCode &&
      strategyCandidate.sectorCode.trim().toUpperCase() ===
        workbenchCandidate.sectorCode.trim().toUpperCase();

    return {
      ...strategyCandidate,
      rank: workbenchCandidate.rank,
      stockCode: workbenchCandidate.stockCode,
      stockName:
        workbenchCandidate.stockName === workbenchCandidate.stockCode
          ? strategyCandidate.stockName
          : workbenchCandidate.stockName,
      sectorCode:
        workbenchHasSectorCode
          ? workbenchCandidate.sectorCode
          : workbenchHasSectorName
            ? ""
            : strategyCandidate.sectorCode,
      sectorName: workbenchHasSectorName
        ? workbenchCandidate.sectorName
        : strategySectorMatchesWorkbench || !workbenchHasSectorCode
          ? strategyCandidate.sectorName
          : "接口未提供",
      reviewFocus: uniqueText([strategyCandidate.reviewFocus, workbenchCandidate.reviewFocus]).join(" · "),
      primaryEvidence: visibleEvidence.slice(0, 3),
      supportingEvidence: visibleEvidence.slice(3),
      boundaryEvidence: uniqueText([
        ...strategyCandidate.boundaryEvidence,
        ...workbenchCandidate.boundaryEvidence,
      ]),
      rawFields: uniqueEvidence([
        ...strategyCandidate.rawFields,
        ...workbenchCandidate.rawFields,
      ]),
    };
  });
}

function mergeThemeEvidenceIntoCandidate(
  candidate: StockCandidateReviewQueueItem,
  themeCandidate: StockCandidateReviewQueueItem,
): StockCandidateReviewQueueItem {
  const themeEvidence = uniqueEvidence([
    ...selectStockCandidateThemeEvidence(candidate),
    ...selectStockCandidateThemeEvidence(themeCandidate),
  ]);
  const nonThemeEvidence = [...candidate.primaryEvidence, ...candidate.supportingEvidence].filter(
    (item) => item.label !== "题材归属" && !item.key.startsWith("theme_membership:"),
  );
  const visibleEvidence = uniqueEvidence([...themeEvidence, ...nonThemeEvidence]);
  const themeFocus = themeEvidence.length > 0
    ? `题材归属：${themeEvidence.map((item) => item.value).join(" / ")}`
    : null;

  return {
    ...candidate,
    reviewFocus: uniqueText([candidate.reviewFocus, themeFocus ?? ""]).join(" · "),
    primaryEvidence: visibleEvidence.slice(0, 3),
    supportingEvidence: visibleEvidence.slice(3),
    boundaryEvidence: uniqueText([...candidate.boundaryEvidence, ...themeCandidate.boundaryEvidence]),
    rawFields: uniqueEvidence([...candidate.rawFields, ...themeCandidate.rawFields]),
  };
}

export function mergeStockAnalysisWorkbenchThemeEvidence(
  strategyQueue: StockCandidateReviewQueueItem[],
  rows: StockAnalysisWorkbenchPayload["first_screen"]["review_queue"],
): StockCandidateReviewQueueItem[] {
  const merged = [...strategyQueue];
  const indexByStockCode = new Map(
    merged.map((candidate, index) => [candidate.stockCode.trim().toUpperCase(), index] as const),
  );
  const themeCandidates = rows.flatMap((row) =>
    isThemeReviewCandidate(row) ? buildStockAnalysisWorkbenchReviewQueue([row]) : [],
  );

  for (const themeCandidate of themeCandidates) {
    const stockKey = themeCandidate.stockCode.trim().toUpperCase();
    const existingIndex = indexByStockCode.get(stockKey);
    if (existingIndex == null) {
      indexByStockCode.set(stockKey, merged.length);
      merged.push(themeCandidate);
      continue;
    }
    merged[existingIndex] = mergeThemeEvidenceIntoCandidate(merged[existingIndex], themeCandidate);
  }

  return merged;
}
