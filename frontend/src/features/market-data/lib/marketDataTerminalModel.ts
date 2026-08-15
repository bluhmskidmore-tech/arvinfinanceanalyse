import type {
  ApiEnvelope,
  ApiQuality,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  MarketDataBondFuturesRankingsPayload,
  MarketDataBondFuturesRankingRow,
  ResultMeta,
} from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import { EM_DASH } from "../../../utils/format";
import type { LabeledValue } from "../../../pageModel";

export type MarketDataTerminalStatus = "ready" | "empty" | "source-pending";
export type MarketDataConnectedStatus = Exclude<MarketDataTerminalStatus, "source-pending">;

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export type MarketDataTerminalSource = {
  basis: ResultMeta["basis"];
  qualityFlag: ApiQuality;
  fallbackMode: ResultMeta["fallback_mode"];
  sourceVersion: string;
  vendorVersion: string;
  traceId: string;
};

export type MarketDataTerminalRowBase = {
  key: string;
  seriesId: string;
  seriesName: string;
  rateText: string;
  deltaText: string;
  tradeDate: string;
  sourceVersion: string;
  vendorVersion: string;
  qualityFlag: ApiQuality | "unknown";
  sourceMode: string;
  sparklineValues: number[];
};

export type MarketDataRateQuoteRow = MarketDataTerminalRowBase & {
  variety: string;
  tenor: string;
};

export type MarketDataMoneyMarketRow = MarketDataTerminalRowBase & {
  name: string;
};

export type MarketDataBondFuturesRow = {
  key: string;
  tradeDate: string;
  contract: string;
  productCode: string;
  exchange: string;
  memberName: string;
  sourceRowNo: number | null;
  volumeText: string;
  volumeChangeText: string;
  longHoldingText: string;
  longChangeText: string;
  shortHoldingText: string;
  shortChangeText: string;
  sourceVendor: string;
};

export type MarketDataRateQuoteSection = {
  status: MarketDataTerminalStatus;
  rows: MarketDataRateQuoteRow[];
  source: MarketDataTerminalSource | null;
  emptyReason: string;
};

export type MarketDataMoneyMarketSection = {
  status: MarketDataTerminalStatus;
  rows: MarketDataMoneyMarketRow[];
  source: MarketDataTerminalSource | null;
  emptyReason: string;
};

export type MarketDataBondFuturesSection = {
  status: MarketDataConnectedStatus;
  rows: MarketDataBondFuturesRow[];
  source: MarketDataTerminalSource | null;
  emptyReason: string;
  asOfDate: string | null;
  contract: string;
  warnings: string[];
};

export type MarketDataSourcePendingSection = {
  status: "source-pending";
  rows: [];
  source: null;
  emptyReason: string;
};

export type MarketDataTerminalModel = {
  rateQuotes: MarketDataRateQuoteSection;
  moneyMarket: MarketDataMoneyMarketSection;
  bondFutures: MarketDataBondFuturesSection | MarketDataSourcePendingSection;
  bondTrades: MarketDataSourcePendingSection;
  creditTrades: MarketDataSourcePendingSection;
};

const TERMINAL_BASIS_LABELS: Partial<Record<ResultMeta["basis"], string>> = {
  formal: "正式",
  analytical: "分析",
  mock: "回放",
};

const TERMINAL_QUALITY_LABELS: Partial<Record<ApiQuality, string>> = {
  ok: "正常",
  warning: "需复核",
  error: "异常",
  stale: "陈旧",
  missing: "缺失",
};

const TERMINAL_FALLBACK_LABELS: Partial<Record<ResultMeta["fallback_mode"], string>> = {
  none: "无降级",
  latest_snapshot: "最新快照",
};

/** 页内表格区简短口径行，不展示 source_version 等运维长串。 */
export function formatTerminalSourceSummary(source: MarketDataTerminalSource | null | undefined) {
  if (!source) {
    return "来源待确认";
  }
  const basis = TERMINAL_BASIS_LABELS[source.basis] ?? source.basis;
  const quality = TERMINAL_QUALITY_LABELS[source.qualityFlag] ?? source.qualityFlag;
  const fallback = TERMINAL_FALLBACK_LABELS[source.fallbackMode] ?? source.fallbackMode;
  return `口径 ${basis} · 质量 ${quality} · 降级 ${fallback}`;
}

/**
 * 行情条目复用共享 `LabeledValue` 词汇（key/label/value/delta）；行情条必有涨跌
 * 展示，故 `delta` 收敛为必填。`tone` 是行情涨跌方向词汇（up/down/flat），不是
 * `MetricTone` 质量语气，保留在本模型。
 */
export type MarketTerminalTickerItem = Pick<LabeledValue, "key" | "label" | "value"> &
  Required<Pick<LabeledValue, "delta">> & {
    tone: "up" | "down" | "flat";
    tradeDate: string;
    seriesId: string;
    sparklineValues: number[];
  };

export type MarketCurveFilter = "treasury" | "cdb" | "both";
export type MarketSourceFilter = "all" | "choice" | "internal";
export type MarketCreditSegmentFilter = "mtn" | "urban" | "both";

const CURVE_FILTER_LABELS: Record<MarketCurveFilter, string | null> = {
  treasury: "国债",
  cdb: "国开",
  both: null,
};

const CREDIT_SEGMENT_LABELS: Record<MarketCreditSegmentFilter, string | null> = {
  mtn: "中票",
  urban: "城投",
  both: null,
};

const SOURCE_FILTER_LABELS: Record<MarketSourceFilter, string | null> = {
  choice: "Choice",
  internal: "内部",
  all: null,
};

export function buildMarketDataActiveFilterSummary(input: {
  curveFilter: MarketCurveFilter;
  creditSegment: MarketCreditSegmentFilter;
  sourceFilter: MarketSourceFilter;
}): string {
  const parts = [
    CURVE_FILTER_LABELS[input.curveFilter],
    CREDIT_SEGMENT_LABELS[input.creditSegment],
    SOURCE_FILTER_LABELS[input.sourceFilter],
  ].filter((label): label is string => Boolean(label));

  return parts.length > 0 ? parts.join(" + ") : "全部";
}

const TICKER_RATE_KEYS_BY_CURVE: Record<MarketCurveFilter, ReadonlySet<string>> = {
  both: new Set(["cgb10y", "cdb10y", "cgb5y", "cdb5y"]),
  treasury: new Set(["cgb10y", "cgb5y"]),
  cdb: new Set(["cdb10y", "cdb5y"]),
};

const TERMINAL_TICKER_RATE_SPECS: Array<{
  key: string;
  label: string;
  variety: string;
  tenor: string;
}> = [
  { key: "cgb10y", label: "10年国债", variety: "国债", tenor: "10Y" },
  { key: "cdb10y", label: "10年国开", variety: "国开", tenor: "10Y" },
  { key: "cgb5y", label: "5年国债", variety: "国债", tenor: "5Y" },
  { key: "cdb5y", label: "5年国开", variety: "国开", tenor: "5Y" },
];

const TERMINAL_TICKER_MONEY_SPECS: Array<{ key: string; label: string; name: string }> = [
  { key: "dr007", label: "DR007", name: "DR007" },
  { key: "omo7d", label: "7天逆回购", name: "公开市场7天逆回购利率" },
];

function tickerToneFromDelta(delta: string): MarketTerminalTickerItem["tone"] {
  // 格式化后 ±0（如 "+0.0bp" / "-0.00%"）视为零变动，归中性（DESIGN §4）。
  const numeric = delta.match(/[-+]?\d+(?:\.\d+)?/);
  if (numeric && Number.parseFloat(numeric[0]) === 0) {
    return "flat";
  }
  if (delta.startsWith("+")) {
    return "up";
  }
  if (delta.startsWith("-")) {
    return "down";
  }
  return "flat";
}

export function buildCatalogVendorNameMap(
  catalog: ReadonlyArray<{ series_id: string; vendor_name?: string | null }>,
): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of catalog) {
    const vendorName = entry.vendor_name?.trim();
    if (vendorName) {
      out.set(entry.series_id, vendorName);
    }
  }
  return out;
}

export function classifyTerminalSource(
  sourceVersion: string,
  vendorVersion: string,
  catalogVendorName?: string | null,
): "choice" | "internal" {
  if (catalogVendorName?.trim().toLowerCase() === "choice") {
    return "choice";
  }
  const haystack = `${sourceVersion} ${vendorVersion}`.toLowerCase();
  return haystack.includes("choice") ? "choice" : "internal";
}

export function matchesSourceFilter(
  row: Pick<MarketDataTerminalRowBase, "seriesId" | "sourceVersion" | "vendorVersion">,
  sourceFilter: MarketSourceFilter,
  catalogVendorNames?: ReadonlyMap<string, string>,
): boolean {
  if (sourceFilter === "all") {
    return true;
  }
  const catalogVendorName = catalogVendorNames?.get(row.seriesId);
  return (
    classifyTerminalSource(row.sourceVersion, row.vendorVersion, catalogVendorName) === sourceFilter
  );
}

export function filterRateQuoteRows(
  rows: MarketDataRateQuoteRow[],
  curveFilter: MarketCurveFilter,
  sourceFilter: MarketSourceFilter = "all",
  catalogVendorNames?: ReadonlyMap<string, string>,
): MarketDataRateQuoteRow[] {
  const sourceFiltered = rows.filter((row) => matchesSourceFilter(row, sourceFilter, catalogVendorNames));
  if (curveFilter === "both") {
    return sourceFiltered;
  }
  const variety = curveFilter === "treasury" ? "国债" : "国开";
  return sourceFiltered.filter((row) => row.variety === variety);
}

export function filterMoneyMarketRows(
  rows: MarketDataMoneyMarketRow[],
  sourceFilter: MarketSourceFilter = "all",
  catalogVendorNames?: ReadonlyMap<string, string>,
): MarketDataMoneyMarketRow[] {
  return rows.filter((row) => matchesSourceFilter(row, sourceFilter, catalogVendorNames));
}

export function filterTerminalTickerItems(
  items: MarketTerminalTickerItem[],
  curveFilter: MarketCurveFilter,
  sourceFilter: MarketSourceFilter,
  model: MarketDataTerminalModel,
  catalogVendorNames?: ReadonlyMap<string, string>,
): MarketTerminalTickerItem[] {
  const allowedRateKeys = TICKER_RATE_KEYS_BY_CURVE[curveFilter];
  const allowedSeriesIds = new Set([
    ...model.rateQuotes.rows
      .filter((row) => matchesSourceFilter(row, sourceFilter, catalogVendorNames))
      .map((row) => row.seriesId),
    ...model.moneyMarket.rows
      .filter((row) => matchesSourceFilter(row, sourceFilter, catalogVendorNames))
      .map((row) => row.seriesId),
  ]);

  return items.filter((item) => {
    if (!allowedSeriesIds.has(item.seriesId)) {
      return false;
    }
    if (item.key.startsWith("cgb") || item.key.startsWith("cdb")) {
      return allowedRateKeys.has(item.key);
    }
    return true;
  });
}

export function buildTerminalTickerItems(model: MarketDataTerminalModel): MarketTerminalTickerItem[] {
  const items: MarketTerminalTickerItem[] = [];

  for (const spec of TERMINAL_TICKER_RATE_SPECS) {
    const row = model.rateQuotes.rows.find(
      (candidate) => candidate.variety === spec.variety && candidate.tenor === spec.tenor,
    );
    if (!row) {
      continue;
    }
    items.push({
      key: spec.key,
      label: spec.label,
      value: row.rateText,
      delta: row.deltaText,
      tone: tickerToneFromDelta(row.deltaText),
      tradeDate: row.tradeDate,
      seriesId: row.seriesId,
      sparklineValues: row.sparklineValues,
    });
  }

  for (const spec of TERMINAL_TICKER_MONEY_SPECS) {
    const row = model.moneyMarket.rows.find((candidate) => candidate.name === spec.name);
    if (!row) {
      continue;
    }
    items.push({
      key: spec.key,
      label: spec.label,
      value: row.rateText,
      delta: row.deltaText,
      tone: tickerToneFromDelta(row.deltaText),
      tradeDate: row.tradeDate,
      seriesId: row.seriesId,
      sparklineValues: row.sparklineValues,
    });
  }

  return items;
}

type BuildMarketDataTerminalModelOptions = {
  ratesEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  latestEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  bondFuturesRankingsEnvelope?: ApiEnvelope<MarketDataBondFuturesRankingsPayload>;
};

type SourcePoint = {
  point: ChoiceMacroLatestPoint;
  meta: ResultMeta;
};

type RateSpec = {
  seriesIds: string[];
  variety: string;
  tenor: string;
};

type MoneySpec = {
  seriesIds: string[];
  name: string;
};

const RATE_QUOTE_SPECS: RateSpec[] = [
  { seriesIds: ["EMM00166458", "M003"], variety: "国债", tenor: "1Y" },
  { seriesIds: ["EMM00588704"], variety: "国债", tenor: "2Y" },
  { seriesIds: ["EMM00166460"], variety: "国债", tenor: "3Y" },
  { seriesIds: ["EMM00166462"], variety: "国债", tenor: "5Y" },
  { seriesIds: ["EMM00166464"], variety: "国债", tenor: "7Y" },
  { seriesIds: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"], variety: "国债", tenor: "10Y" },
  { seriesIds: ["EMM00166468"], variety: "国债", tenor: "20Y" },
  { seriesIds: ["EMM00166469"], variety: "国债", tenor: "30Y" },
  { seriesIds: ["EMM00166494"], variety: "国开", tenor: "1Y" },
  { seriesIds: ["EMM00166495"], variety: "国开", tenor: "2Y" },
  { seriesIds: ["EMM00166496"], variety: "国开", tenor: "3Y" },
  { seriesIds: ["EMM00166498"], variety: "国开", tenor: "5Y" },
  { seriesIds: ["EMM00166502"], variety: "国开", tenor: "10Y" },
  { seriesIds: ["EMM00166504"], variety: "国开", tenor: "20Y" },
];

const MONEY_MARKET_SPECS: MoneySpec[] = [
  { seriesIds: ["M001"], name: "公开市场7天逆回购利率" },
  { seriesIds: ["CA.DR007", "M002", "EMM00167613"], name: "DR007" },
];

function terminalSource(meta: ResultMeta): MarketDataTerminalSource {
  return {
    basis: meta.basis,
    qualityFlag: meta.quality_flag,
    fallbackMode: meta.fallback_mode,
    sourceVersion: meta.source_version,
    vendorVersion: meta.vendor_version,
    traceId: meta.trace_id,
  };
}

function buildSourcePointMap(
  envelopes: Array<ApiEnvelope<ChoiceMacroLatestPayload> | undefined>,
): Map<string, SourcePoint> {
  const out = new Map<string, SourcePoint>();
  for (const envelope of envelopes) {
    if (!envelope) {
      continue;
    }
    for (const point of envelope.result.series) {
      if (!out.has(point.series_id)) {
        out.set(point.series_id, { point, meta: envelope.result_meta });
      }
    }
  }
  return out;
}

function findSourcePoint(map: Map<string, SourcePoint>, seriesIds: string[]) {
  for (const seriesId of seriesIds) {
    const found = map.get(seriesId);
    if (found) {
      return found;
    }
  }
  return null;
}

export function buildTerminalSparklineValues(point: ChoiceMacroLatestPoint): number[] {
  const sorted = [...(point.recent_points ?? [])].sort((left, right) =>
    left.trade_date.localeCompare(right.trade_date),
  );
  const values = sorted.map((recentPoint) => recentPoint.value_numeric);
  if (values.length === 0) {
    return [point.value_numeric];
  }
  const latest = values[values.length - 1];
  if (latest !== point.value_numeric) {
    values.push(point.value_numeric);
  }
  return values;
}

export function resolveLatestMarketDataTradeDate(
  envelope: ApiEnvelope<ChoiceMacroLatestPayload> | undefined,
): string | null {
  const dates = envelope?.result.series
    .map((point) => point.trade_date)
    .filter((date): date is string => ISO_DATE_RE.test(date)) ?? [];
  if (dates.length === 0) {
    return null;
  }
  return dates.sort((left, right) => left.localeCompare(right))[dates.length - 1] ?? null;
}

function rowBase(sourcePoint: SourcePoint): MarketDataTerminalRowBase {
  const { point, meta } = sourcePoint;
  return {
    key: point.series_id,
    seriesId: point.series_id,
    seriesName: point.series_name,
    rateText: formatChoiceMacroValue(point, { spaceBeforeUnit: false }),
    deltaText: formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "缺前值" }),
    tradeDate: point.trade_date,
    sourceVersion: meta.source_version,
    vendorVersion: point.vendor_version || meta.vendor_version,
    qualityFlag: point.quality_flag ?? meta.quality_flag ?? "unknown",
    sourceMode: point.fetch_mode ?? "unknown",
    sparklineValues: buildTerminalSparklineValues(point),
  };
}

function sectionStatus(rowCount: number): MarketDataConnectedStatus {
  return rowCount > 0 ? "ready" : "empty";
}

function primarySource(envelope?: ApiEnvelope<ChoiceMacroLatestPayload>) {
  return envelope ? terminalSource(envelope.result_meta) : null;
}

function bondFuturesSource(envelope?: ApiEnvelope<MarketDataBondFuturesRankingsPayload>) {
  return envelope ? terminalSource(envelope.result_meta) : null;
}

/**
 * 席位排行的手数/持仓输出千分位（Intl，如 "12,345"），与 `fixedOrDash` /
 * `signedFixedOrDash` 的 toFixed 拼接形状不同，保留本地实现，勿迁 pageModel。
 */
function formatRankNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EM_DASH;
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function formatRankChange(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0";
  }
  return `${value > 0 ? "+" : ""}${formatRankNumber(value)}`;
}

function bondFuturesRow(row: MarketDataBondFuturesRankingRow): MarketDataBondFuturesRow {
  return {
    key: `${row.contract}:${row.member_name}:${row.source_row_no ?? row.member_name}`,
    tradeDate: row.trade_date,
    contract: row.contract,
    productCode: row.product_code,
    exchange: row.exchange,
    memberName: row.member_name,
    sourceRowNo: row.source_row_no,
    volumeText: formatRankNumber(row.volume),
    volumeChangeText: formatRankChange(row.volume_change),
    longHoldingText: formatRankNumber(row.long_holding),
    longChangeText: formatRankChange(row.long_change),
    shortHoldingText: formatRankNumber(row.short_holding),
    shortChangeText: formatRankChange(row.short_change),
    sourceVendor: row.source_vendor,
  };
}

function buildBondFuturesSection(
  envelope?: ApiEnvelope<MarketDataBondFuturesRankingsPayload>,
): MarketDataBondFuturesSection | MarketDataSourcePendingSection {
  if (!envelope) {
    return {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "国债期货实时行情源尚未纳入市场工作台合同，前端不展示静态示例合约。",
    };
  }
  const rows = envelope.result.rows.map(bondFuturesRow);
  return {
    status: sectionStatus(rows.length),
    rows,
    source: bondFuturesSource(envelope),
    emptyReason: "国债期货排行接口已接入，当前合约暂无席位排行行。",
    asOfDate: envelope.result.as_of_date,
    contract: envelope.result.contract,
    warnings: envelope.result.warnings,
  };
}

export function buildMarketDataTerminalModel({
  ratesEnvelope,
  latestEnvelope,
  bondFuturesRankingsEnvelope,
}: BuildMarketDataTerminalModelOptions): MarketDataTerminalModel {
  const bySeriesId = buildSourcePointMap([ratesEnvelope, latestEnvelope]);
  const rateRows = RATE_QUOTE_SPECS.flatMap((spec) => {
    const sourcePoint = findSourcePoint(bySeriesId, spec.seriesIds);
    if (!sourcePoint) {
      return [];
    }
    return [
      {
        ...rowBase(sourcePoint),
        variety: spec.variety,
        tenor: spec.tenor,
      },
    ];
  });
  const moneyRows = MONEY_MARKET_SPECS.flatMap((spec) => {
    const sourcePoint = findSourcePoint(bySeriesId, spec.seriesIds);
    if (!sourcePoint) {
      return [];
    }
    return [
      {
        ...rowBase(sourcePoint),
        name: spec.name,
      },
    ];
  });

  return {
    rateQuotes: {
      status: sectionStatus(rateRows.length),
      rows: rateRows,
      source: primarySource(ratesEnvelope) ?? primarySource(latestEnvelope),
      emptyReason: "未找到已确认的国债/国开收益率序列，前端不补示例行情。",
    },
    moneyMarket: {
      status: sectionStatus(moneyRows.length),
      rows: moneyRows,
      source: primarySource(ratesEnvelope) ?? primarySource(latestEnvelope),
      emptyReason: "未找到已确认的资金利率序列，前端不补示例成交量或区间。",
    },
    bondFutures: buildBondFuturesSection(bondFuturesRankingsEnvelope),
    bondTrades: {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "现券成交明细源尚未纳入市场工作台合同，前端不展示静态成交流水。",
    },
    creditTrades: {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "信用债成交明细源尚未纳入市场工作台合同，前端不展示静态成交流水。",
    },
  };
}
