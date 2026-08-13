import type {
  ApiEnvelope,
  BondPositionChangeItem,
  BondPositionItem,
  BondTopHoldingItem,
  CreditSpreadDetailBondRow,
  Numeric,
  ResultMeta,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type { LabeledValue } from "../../../pageModel";
import { formatPct, formatYi } from "../../bond-analytics/utils/formatters";

export type BondTradingDeskCoverageSource =
  | "top_holdings"
  | "positions"
  | "credit_spread"
  | "none";

export interface BondTradingDeskBondSnapshot {
  bondCode: string;
  bondName: string | null;
  issuerName: string | null;
  rating: string | null;
  assetClass: string | null;
  marketValue: Numeric | string | null;
  faceValue: Numeric | string | null;
  ytm: Numeric | string | null;
  modifiedDuration: Numeric | string | null;
  weight: Numeric | string | null;
  valuationNetPrice: string | null;
  creditSpread: string | null;
  benchmarkYield: string | null;
  spreadDuration: string | null;
  coverageSource: BondTradingDeskCoverageSource;
  coverageNote: string;
}

export interface BondTradingDeskConclusion {
  title: string;
  body: string;
  detail: string;
}

/**
 * KPI 瓦片复用共享 `LabeledValue` 词汇；`caption` 语义等同 `LabeledValue.detail`，
 * 因页面消费方正被并行改动暂不改名，批量迁移阶段收敛为 `detail`。
 */
export type BondTradingDeskMetricTile = Pick<LabeledValue, "key" | "label" | "value"> & {
  caption: string;
};

export interface BondTradingDeskGapSection {
  key: string;
  label: string;
  status: "api_pending" | "not_in_portfolio";
  reason: string;
}

export interface BondTradingDeskDecisionItem {
  key: string;
  label: string;
  description: string;
  href: string;
}

export interface BondTradingDeskPageModel {
  bondCode: string;
  reportDate: string;
  snapshot: BondTradingDeskBondSnapshot | null;
  positionChange: BondPositionChangeItem | null;
  conclusion: BondTradingDeskConclusion;
  metricTiles: BondTradingDeskMetricTile[];
  gapSections: BondTradingDeskGapSection[];
  decisionItems: BondTradingDeskDecisionItem[];
  lookupScopeNote: string;
}

const GAP_SECTIONS: Array<Omit<BondTradingDeskGapSection, "status" | "reason">> = [
  { key: "order_book", label: "五档盘口 / 报价" },
  { key: "constraint_check", label: "约束校验" },
  { key: "peer_compare", label: "相似券对比" },
  { key: "scenario_stress", label: "情景压力" },
  { key: "portfolio_impact", label: "组合冲击" },
];

export function normalizeBondCode(code: string | null | undefined): string {
  return (code ?? "").trim().toUpperCase();
}

export function codesMatch(left: string | null | undefined, right: string | null | undefined): boolean {
  const a = normalizeBondCode(left);
  const b = normalizeBondCode(right);
  return Boolean(a) && a === b;
}

export function buildBondTradingDeskPath(bondCode: string, reportDate: string): string {
  const params = new URLSearchParams();
  params.set("bond_code", bondCode.trim());
  if (reportDate.trim()) {
    params.set("report_date", reportDate.trim());
  }
  return `/bond-trading-desk?${params.toString()}`;
}

function formatOptionalYi(value: Numeric | string | null | undefined): string {
  if (value == null || value === "") return "待返回";
  return formatYi(value);
}

function formatOptionalPct(value: Numeric | string | null | undefined): string {
  if (value == null || value === "") return "待返回";
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) return value;
    return `${parsed.toFixed(2)}%`;
  }
  return formatPct(value);
}

function formatOptionalDisplay(value: Numeric | string | null | undefined): string {
  if (value == null || value === "") return "待返回";
  if (typeof value === "string") return value;
  return value.display || "待返回";
}

function mergeTopHolding(
  bondCode: string,
  row: BondTopHoldingItem,
): BondTradingDeskBondSnapshot {
  return {
    bondCode,
    bondName: row.instrument_name,
    issuerName: row.issuer_name,
    rating: row.rating,
    assetClass: row.asset_class,
    marketValue: row.market_value,
    faceValue: row.face_value,
    ytm: row.ytm,
    modifiedDuration: row.modified_duration,
    weight: row.weight,
    valuationNetPrice: null,
    creditSpread: null,
    benchmarkYield: null,
    spreadDuration: null,
    coverageSource: "top_holdings",
    coverageNote: "来源：债券分析重仓券列表",
  };
}

function mergePositionRow(bondCode: string, row: BondPositionItem): BondTradingDeskBondSnapshot {
  return {
    bondCode,
    bondName: row.credit_name,
    issuerName: null,
    rating: null,
    assetClass: row.asset_class ?? row.sub_type,
    marketValue: row.market_value,
    faceValue: row.face_value,
    ytm: row.yield_rate,
    modifiedDuration: null,
    weight: null,
    valuationNetPrice: row.valuation_net_price,
    creditSpread: null,
    benchmarkYield: null,
    spreadDuration: null,
    coverageSource: "positions",
    coverageNote: "来源：持仓债券列表（前 500 条扫描）",
  };
}

function mergeCreditSpreadRow(
  base: BondTradingDeskBondSnapshot,
  row: CreditSpreadDetailBondRow,
): BondTradingDeskBondSnapshot {
  return {
    ...base,
    bondName: base.bondName ?? row.instrument_name,
    rating: base.rating ?? row.rating,
    ytm: base.ytm ?? row.ytm,
    marketValue: base.marketValue ?? row.market_value,
    weight: base.weight ?? row.weight,
    creditSpread: row.credit_spread,
    benchmarkYield: row.benchmark_yield,
    spreadDuration: row.spread_duration,
    coverageSource: base.coverageSource === "none" ? "credit_spread" : base.coverageSource,
    coverageNote:
      base.coverageSource === "none"
        ? "来源：信用利差分析明细（top/bottom 子集）"
        : `${base.coverageNote}；利差字段来自信用利差分析`,
  };
}

export function resolveBondSnapshot(input: {
  bondCode: string;
  topHoldings: BondTopHoldingItem[];
  positions: BondPositionItem[];
  creditSpreadRows: CreditSpreadDetailBondRow[];
}): BondTradingDeskBondSnapshot | null {
  const bondCode = normalizeBondCode(input.bondCode);
  if (!bondCode) return null;

  const topRow = input.topHoldings.find((row) => codesMatch(row.instrument_code, bondCode));
  const positionRow = input.positions.find((row) => codesMatch(row.bond_code, bondCode));
  const spreadRow = input.creditSpreadRows.find((row) => codesMatch(row.instrument_code, bondCode));

  let snapshot: BondTradingDeskBondSnapshot | null = null;
  if (topRow) {
    snapshot = mergeTopHolding(bondCode, topRow);
  } else if (positionRow) {
    snapshot = mergePositionRow(bondCode, positionRow);
  } else if (spreadRow) {
    snapshot = {
      bondCode,
      bondName: spreadRow.instrument_name,
      issuerName: null,
      rating: spreadRow.rating,
      assetClass: spreadRow.tenor_bucket,
      marketValue: spreadRow.market_value,
      faceValue: null,
      ytm: spreadRow.ytm,
      modifiedDuration: null,
      weight: spreadRow.weight,
      valuationNetPrice: null,
      creditSpread: spreadRow.credit_spread,
      benchmarkYield: spreadRow.benchmark_yield,
      spreadDuration: spreadRow.spread_duration,
      coverageSource: "credit_spread",
      coverageNote: "来源：信用利差分析明细（top/bottom 子集）",
    };
  }

  if (snapshot && spreadRow) {
    snapshot = mergeCreditSpreadRow(snapshot, spreadRow);
  }

  return snapshot;
}

export function findPositionChange(
  bondCode: string,
  items: BondPositionChangeItem[],
): BondPositionChangeItem | null {
  const normalized = normalizeBondCode(bondCode);
  if (!normalized) return null;
  return items.find((item) => codesMatch(item.instrument_code, normalized)) ?? null;
}

export function buildBondTradingDeskConclusion(
  bondCode: string,
  snapshot: BondTradingDeskBondSnapshot | null,
  positionChange: BondPositionChangeItem | null,
): BondTradingDeskConclusion {
  if (!normalizeBondCode(bondCode)) {
    return {
      title: "待选择债券",
      body: "请从重仓券、持仓列表深钻进入，或在地址栏提供 bond_code。",
      detail: "本页只拼装既有只读 API，不生成交易指令。",
    };
  }

  if (!snapshot) {
    return {
      title: "未在当前查找范围命中",
      body: `代码 ${normalizeBondCode(bondCode)} 未出现在重仓券（≤500）或持仓列表（前 500）或信用利差 top/bottom 子集中。`,
      detail: "可改从持仓页确认是否持有该券，或等待单券 profile API 落地后再查全量。",
    };
  }

  const mv = formatOptionalYi(snapshot.marketValue);
  const weight = formatOptionalPct(snapshot.weight);
  const ytm = formatOptionalPct(snapshot.ytm);
  const changeHint = positionChange
    ? `；较上期市值变动 ${formatYi(positionChange.change_market_value)}（${positionChange.direction}）`
    : "；持仓变动未出现在当前 top 变动列表";

  return {
    title: "单券读面结论",
    body: `${snapshot.bondName ?? snapshot.bondCode}：市值约 ${mv}，组合权重 ${weight}，YTM ${ytm}${changeHint}。`,
    detail: `${snapshot.coverageNote}。缺口模块（盘口、约束、相似券等）须等后端契约，本页仅标注待返回。`,
  };
}

export function buildBondTradingDeskMetricTiles(
  snapshot: BondTradingDeskBondSnapshot | null,
): BondTradingDeskMetricTile[] {
  if (!snapshot) {
    return [
      { key: "market_value", label: "市值", value: EM_DASH, caption: "" },
      { key: "weight", label: "组合权重", value: EM_DASH, caption: "" },
      { key: "ytm", label: "YTM", value: EM_DASH, caption: "" },
      { key: "duration", label: "修正久期", value: EM_DASH, caption: "" },
      { key: "credit_spread", label: "信用利差", value: EM_DASH, caption: "" },
      { key: "net_price", label: "估值净价", value: EM_DASH, caption: "" },
    ];
  }

  return [
    {
      key: "market_value",
      label: "市值",
      value: formatOptionalYi(snapshot.marketValue),
      caption: "只读拼装",
    },
    {
      key: "weight",
      label: "组合权重",
      value: formatOptionalPct(snapshot.weight),
      caption: "重仓券/利差列表",
    },
    {
      key: "ytm",
      label: "YTM",
      value: formatOptionalPct(snapshot.ytm),
      caption: "到期收益率",
    },
    {
      key: "duration",
      label: "修正久期",
      value: formatOptionalDisplay(snapshot.modifiedDuration),
      caption: snapshot.modifiedDuration ? "重仓券字段" : "待返回",
    },
    {
      key: "credit_spread",
      label: "信用利差",
      value: snapshot.creditSpread ?? "待返回",
      caption: snapshot.creditSpread ? "利差分析" : "未在利差子集",
    },
    {
      key: "net_price",
      label: "估值净价",
      value: snapshot.valuationNetPrice ?? "待返回",
      caption: snapshot.valuationNetPrice ? "持仓列表" : "待返回",
    },
  ];
}

export function buildBondTradingDeskGapSections(
  snapshot: BondTradingDeskBondSnapshot | null,
): BondTradingDeskGapSection[] {
  const portfolioStatus: BondTradingDeskGapSection["status"] = snapshot ? "api_pending" : "not_in_portfolio";
  const portfolioReason = snapshot
    ? "后端尚无单券专用契约，本模块等待 API 返回。"
    : "尚未命中组合持仓拼装范围，请先确认 bond_code 与报告日。";

  return GAP_SECTIONS.map((section) => ({
    ...section,
    status: portfolioStatus,
    reason: portfolioReason,
  }));
}

export function buildBondTradingDeskDecisionItems(reportDate: string): BondTradingDeskDecisionItem[] {
  const rd = reportDate.trim();
  const suffix = rd ? `?report_date=${encodeURIComponent(rd)}` : "";
  return [
    {
      key: "bond_analysis",
      label: "返回组合债券分析",
      description: "查看组合级曲线、归因与风险模块。",
      href: `/bond-analysis${suffix}`,
    },
    {
      key: "positions",
      label: "打开持仓列表",
      description: "核对全量持仓与对手方明细。",
      href: `/positions${suffix}`,
    },
    {
      key: "credit_spread",
      label: "信用利差分析",
      description: "组合级利差环境与 top/bottom 券。",
      href: `/bond-analysis${suffix}#credit-spread`,
    },
  ];
}

export type BondTradingDeskComposeSourceKey =
  | "top_holdings"
  | "positions"
  | "credit_spread"
  | "position_changes";

export type BondTradingDeskComposeSourceStatus = {
  key: BondTradingDeskComposeSourceKey;
  label: string;
  status: "ready" | "failed";
  detail: string;
  qualityFlag?: string | null;
  fallbackMode?: string | null;
};

export interface BondTradingDeskComposeResult {
  model: BondTradingDeskPageModel;
  sourceStatuses: BondTradingDeskComposeSourceStatus[];
  partialFailure: boolean;
}

const COMPOSE_SOURCE_LABELS: Record<BondTradingDeskComposeSourceKey, string> = {
  top_holdings: "重仓券",
  positions: "持仓列表",
  credit_spread: "信用利差",
  position_changes: "持仓变动",
};

function readComposeEnvelopeMeta(
  settled: PromiseSettledResult<unknown>,
): ResultMeta | null {
  if (settled.status !== "fulfilled") return null;
  const envelope = settled.value as ApiEnvelope<unknown> | undefined;
  return envelope?.result_meta ?? null;
}

export function formatComposeMetaNote(meta: ResultMeta | null | undefined): string {
  if (!meta) return "";
  const notes: string[] = [];
  if (meta.quality_flag && meta.quality_flag !== "ok") {
    notes.push(`quality=${meta.quality_flag}`);
  }
  if (meta.fallback_mode && meta.fallback_mode !== "none") {
    notes.push(`fallback=${meta.fallback_mode}`);
  }
  if (meta.formal_use_allowed === false) {
    notes.push("formal_use_allowed=false");
  }
  return notes.length > 0 ? ` · ${notes.join(" ")}` : "";
}

function composeSourceStatus(
  key: BondTradingDeskComposeSourceKey,
  settled: PromiseSettledResult<unknown>,
  readyDetail: string,
): BondTradingDeskComposeSourceStatus {
  if (settled.status === "fulfilled") {
    const meta = readComposeEnvelopeMeta(settled);
    return {
      key,
      label: COMPOSE_SOURCE_LABELS[key],
      status: "ready",
      detail: `${readyDetail}${formatComposeMetaNote(meta)}`,
      qualityFlag: meta?.quality_flag ?? null,
      fallbackMode: meta?.fallback_mode ?? null,
    };
  }
  const reason =
    settled.reason instanceof Error ? settled.reason.message : String(settled.reason ?? "unknown");
  return { key, label: COMPOSE_SOURCE_LABELS[key], status: "failed", detail: reason };
}

export function buildBondTradingDeskComposeResult(input: {
  bondCode: string;
  reportDate: string;
  topHoldings: BondTopHoldingItem[];
  positions: BondPositionItem[];
  creditSpreadRows: CreditSpreadDetailBondRow[];
  positionChanges: BondPositionChangeItem[];
  sourceSettled: {
    topHoldings: PromiseSettledResult<unknown>;
    positions: PromiseSettledResult<unknown>;
    creditSpread: PromiseSettledResult<unknown>;
    positionChanges: PromiseSettledResult<unknown>;
  };
}): BondTradingDeskComposeResult {
  const sourceStatuses = [
    composeSourceStatus(
      "top_holdings",
      input.sourceSettled.topHoldings,
      `${input.topHoldings.length} 条`,
    ),
    composeSourceStatus(
      "positions",
      input.sourceSettled.positions,
      `${input.positions.length} 条（前 500）`,
    ),
    composeSourceStatus(
      "credit_spread",
      input.sourceSettled.creditSpread,
      `${input.creditSpreadRows.length} 条（top/bottom）`,
    ),
    composeSourceStatus(
      "position_changes",
      input.sourceSettled.positionChanges,
      `${input.positionChanges.length} 条`,
    ),
  ];

  return {
    model: buildBondTradingDeskPageModel({
      bondCode: input.bondCode,
      reportDate: input.reportDate,
      topHoldings: input.topHoldings,
      positions: input.positions,
      creditSpreadRows: input.creditSpreadRows,
      positionChanges: input.positionChanges,
    }),
    sourceStatuses,
    partialFailure: sourceStatuses.some((item) => item.status === "failed"),
  };
}

export function buildBondTradingDeskPageModel(input: {
  bondCode: string;
  reportDate: string;
  topHoldings: BondTopHoldingItem[];
  positions: BondPositionItem[];
  creditSpreadRows: CreditSpreadDetailBondRow[];
  positionChanges: BondPositionChangeItem[];
}): BondTradingDeskPageModel {
  const bondCode = normalizeBondCode(input.bondCode);
  const snapshot = resolveBondSnapshot({
    bondCode,
    topHoldings: input.topHoldings,
    positions: input.positions,
    creditSpreadRows: input.creditSpreadRows,
  });
  const positionChange = findPositionChange(bondCode, input.positionChanges);

  return {
    bondCode,
    reportDate: input.reportDate,
    snapshot,
    positionChange,
    conclusion: buildBondTradingDeskConclusion(bondCode, snapshot, positionChange),
    metricTiles: buildBondTradingDeskMetricTiles(snapshot),
    gapSections: buildBondTradingDeskGapSections(snapshot),
    decisionItems: buildBondTradingDeskDecisionItems(input.reportDate),
    lookupScopeNote:
      "查找范围：重仓券 top_n≤500、持仓 bonds 第 1 页 page_size≤500、信用利差 top/bottom 列表。",
  };
}
