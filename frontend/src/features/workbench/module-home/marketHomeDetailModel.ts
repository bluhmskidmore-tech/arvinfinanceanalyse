import type {
  ChoiceMacroLatestPoint,
  MacroVendorSeries,
  ChoiceNewsEventsPayload,
} from "../../../api/contracts";
import type {
  ModuleHomeDetailRow,
  ModuleHomeDetailChart,
  ModuleHomeTone,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
} from "../../../utils/choiceMacroFormat";
import { EM_DASH } from "../../../utils/format";
import type {
  MarketDataRateQuoteRow,
  MarketDataMoneyMarketRow,
} from "../../market-data/lib/marketDataTerminalModel";
import { buildMarketDataTerminalModel } from "../../market-data/lib/marketDataTerminalModel";
import { summarizeMacroNewsEvent } from "../dashboard-home/adapters/macroNewsPresentation";

export function findMacroPoint(
  latestSeries: ChoiceMacroLatestPoint[],
  rateSeries: ChoiceMacroLatestPoint[],
  seriesIds: string[],
  nameIncludes?: string[],
): ChoiceMacroLatestPoint | undefined {
  const combined = [...rateSeries, ...latestSeries];
  for (const seriesId of seriesIds) {
    const found = combined.find((item) => item.series_id === seriesId);
    if (found) {
      return found;
    }
  }
  if (nameIncludes) {
    for (const token of nameIncludes) {
      const found = combined.find((item) => item.series_name.includes(token));
      if (found) {
        return found;
      }
    }
  }
  return undefined;
}

export function macroPointToDetailRow(
  point: ChoiceMacroLatestPoint,
  label: string,
  source: string,
): ModuleHomeDetailRow {
  const change = formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "" });
  return {
    key: point.series_id,
    label,
    value: formatChoiceMacroValue(point, { spaceBeforeUnit: false }),
    tradeDate: point.trade_date,
    source,
    tone: "ok",
    detail: change || undefined,
  };
}

function rateSnapshotChange(deltaText: string | undefined): string | undefined {
  if (!deltaText || deltaText === EM_DASH || deltaText === "无变动") {
    return undefined;
  }
  return deltaText;
}

function pushRateQuoteRow(
  rows: ModuleHomeDetailRow[],
  seen: Set<string>,
  matched: MarketDataRateQuoteRow,
  label: string,
  key: string,
) {
  if (seen.has(matched.key)) {
    return;
  }
  seen.add(matched.key);
  rows.push({
    key,
    label,
    value: matched.rateText,
    tradeDate: matched.tradeDate,
    source: matched.seriesId,
    tone: "ok",
    detail: rateSnapshotChange(matched.deltaText),
  });
}

function pushMoneyMarketRow(
  rows: ModuleHomeDetailRow[],
  seen: Set<string>,
  matched: MarketDataMoneyMarketRow,
  label: string,
  key: string,
) {
  if (seen.has(matched.key)) {
    return;
  }
  seen.add(matched.key);
  rows.push({
    key,
    label,
    value: matched.rateText,
    tradeDate: matched.tradeDate,
    source: matched.seriesId,
    tone: "ok",
    detail: rateSnapshotChange(matched.deltaText),
  });
}

type HomeKeyRatePick =
  | {
      key: string;
      label: string;
      kind: "rate";
      match: (row: MarketDataRateQuoteRow) => boolean;
    }
  | {
      key: string;
      label: string;
      kind: "money";
      match: (row: MarketDataMoneyMarketRow) => boolean;
    }
  | {
      key: string;
      label: string;
      kind: "macro";
      seriesIds: string[];
      nameIncludes?: string[];
    };

const HOME_KEY_RATE_PICKS: HomeKeyRatePick[] = [
  {
    key: "gov-10y",
    label: "10Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "10Y",
  },
  {
    key: "gov-2y",
    label: "2Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "2Y",
  },
  {
    key: "gov-1y",
    label: "1Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "1Y",
  },
  {
    key: "gov-3y",
    label: "3Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "3Y",
  },
  {
    key: "gov-5y",
    label: "5Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "5Y",
  },
  {
    key: "gov-30y",
    label: "30Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "30Y",
  },
  {
    key: "gov-7y",
    label: "7Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "7Y",
  },
  {
    key: "cdb-10y",
    label: "10Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "10Y",
  },
  {
    key: "cdb-5y",
    label: "5Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "5Y",
  },
  {
    key: "cdb-3y",
    label: "3Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "3Y",
  },
  {
    key: "cdb-1y",
    label: "1Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "1Y",
  },
  {
    key: "dr007",
    label: "DR007",
    kind: "money",
    match: (row) => row.name === "DR007",
  },
  {
    key: "r007",
    label: "R007",
    kind: "macro",
    seriesIds: ["CA.R007", "M003", "EMM00167614"],
    nameIncludes: ["R007", "R-007", "质押式回购加权利率:R007"],
  },
  {
    key: "omo-7d",
    label: "7天逆回购",
    kind: "macro",
    seriesIds: ["M001"],
    nameIncludes: ["7天逆回购", "公开市场7天"],
  },
  {
    key: "ncd-3m",
    label: "3M NCD",
    kind: "macro",
    seriesIds: ["NCD.SHIBOR.3M", "M0041813"],
    nameIncludes: ["3M NCD", "NCD"],
  },
  {
    key: "aa-5y",
    label: "5Y AA信用",
    kind: "macro",
    seriesIds: ["EMM00166683", "legacy.yield.choice.aa_credit.5Y"],
    nameIncludes: ["5Y AA", "AA 信用", "AA信用"],
  },
  {
    key: "shibor-on",
    label: "SHIBOR 隔夜",
    kind: "macro",
    seriesIds: ["EMM00166252"],
    nameIncludes: ["SHIBOR 隔夜", "Shibor 隔夜", "SHIBOR隔夜"],
  },
];

export function mergeDerivedSpreads(
  formal: Partial<Record<string, number | null>> | undefined,
  latest: Partial<Record<string, number | null>> | undefined,
): Partial<Record<string, number | null>> | undefined {
  if (!formal && !latest) {
    return undefined;
  }
  const keys = new Set([...Object.keys(formal ?? {}), ...Object.keys(latest ?? {})]);
  const merged: Partial<Record<string, number | null>> = {};
  for (const key of keys) {
    const formalValue = formal?.[key];
    if (formalValue !== null && formalValue !== undefined && Number.isFinite(formalValue)) {
      merged[key] = formalValue;
      continue;
    }
    const latestValue = latest?.[key];
    if (latestValue !== null && latestValue !== undefined && Number.isFinite(latestValue)) {
      merged[key] = latestValue;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

export function buildDerivedSpreadRows(
  derivedSpreads: Partial<Record<string, number | null>> | undefined,
  tradeDate: string,
): ModuleHomeDetailRow[] {
  if (!derivedSpreads) {
    return [];
  }
  const rows: ModuleHomeDetailRow[] = [];
  const spreadSpecs: Array<{ key: string; label: string; field: string }> = [
    { key: "term-spread-10y-2y", label: "10Y-2Y 利差", field: "term_spread_10y_2y" },
    { key: "term-spread-10y-1y", label: "10Y-1Y 利差", field: "term_spread_10y_1y" },
    { key: "term-spread-10y-5y", label: "10Y-5Y 利差", field: "term_spread_10y_5y" },
    { key: "credit-spread-aa-3y", label: "AA-3Y 信用利差", field: "credit_spread_aa_3y" },
  ];
  for (const spec of spreadSpecs) {
    const value = derivedSpreads[spec.field];
    if (value === null || value === undefined || !Number.isFinite(value)) {
      continue;
    }
    rows.push({
      key: spec.key,
      label: spec.label,
      value: `${value.toFixed(1)} bp`,
      tradeDate,
      source: "market_derived",
      tone: "ok",
    });
  }
  return rows;
}

export function buildMarketKeyRateRows(
  latestSeries: ChoiceMacroLatestPoint[],
  rateSeries: ChoiceMacroLatestPoint[],
  terminalModel: ReturnType<typeof buildMarketDataTerminalModel>,
): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [];
  const seen = new Set<string>();

  for (const pick of HOME_KEY_RATE_PICKS) {
    if (pick.kind === "rate") {
      const matched = terminalModel.rateQuotes.rows.find(pick.match);
      if (!matched) {
        continue;
      }
      pushRateQuoteRow(rows, seen, matched, pick.label, pick.key);
      continue;
    }
    if (pick.kind === "money") {
      const matched = terminalModel.moneyMarket.rows.find(pick.match);
      if (!matched) {
        continue;
      }
      pushMoneyMarketRow(rows, seen, matched, pick.label, pick.key);
      continue;
    }
    const point = findMacroPoint(latestSeries, rateSeries, pick.seriesIds, pick.nameIncludes);
    if (!point || seen.has(point.series_id)) {
      continue;
    }
    seen.add(point.series_id);
    rows.push(macroPointToDetailRow(point, pick.label, point.series_id));
  }

  for (const matched of terminalModel.rateQuotes.rows) {
    if (rows.length >= 14) {
      break;
    }
    pushRateQuoteRow(rows, seen, matched, `${matched.variety} ${matched.tenor}`, matched.key);
  }

  for (const matched of terminalModel.moneyMarket.rows) {
    if (rows.length >= 14) {
      break;
    }
    pushMoneyMarketRow(rows, seen, matched, matched.name, matched.key);
  }

  return rows.slice(0, 14);
}

export function catalogTierCounts(series: MacroVendorSeries[]) {
  const tiers: Record<string, number> = {
    stable: 0,
    fallback: 0,
    isolated: 0,
    other: 0,
  };
  for (const item of series) {
    const tier = item.refresh_tier ?? "other";
    if (tier in tiers) {
      tiers[tier] += 1;
    } else {
      tiers.other += 1;
    }
  }
  return tiers;
}

function parseRatePercent(value: string): number | null {
  const match = value.match(/([\d.]+)/);
  if (!match) {
    return null;
  }
  const parsed = Number.parseFloat(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function isPercentRateRow(row: ModuleHomeDetailRow): boolean {
  if (!row.value.includes("%")) {
    return false;
  }
  const parsed = parseRatePercent(row.value);
  return parsed !== null && parsed >= 0 && parsed <= 20;
}

export function buildPercentRateChart(
  rows: ModuleHomeDetailRow[],
  title: string,
): ModuleHomeDetailChart | undefined {
  const parsed = rows
    .filter(isPercentRateRow)
    .map((row) => ({ label: row.label, value: parseRatePercent(row.value)! }));
  if (parsed.length < 2) {
    return undefined;
  }
  return {
    title,
    unit: "%",
    orientation: "horizontal",
    categories: parsed.map((item) => item.label),
    values: parsed.map((item) => item.value),
  };
}

const MACRO_SNAPSHOT_PRIORITY_IDS = [
  "CA.CSI300",
  "CA.CSI300_PCT_CHG",
  "CA.CSI300_PE",
  "CA.BRENT",
  "CA.COPPER",
  "CA.ALUMINUM",
  "CA.USD_CNY",
  "CA.USDCNY",
  "CA.HSI",
  "CA.SPX",
] as const;

export function buildYieldCurveQuoteRows(
  terminalModel: ReturnType<typeof buildMarketDataTerminalModel>,
): ModuleHomeDetailRow[] {
  return terminalModel.rateQuotes.rows.map((row) => ({
    key: row.key,
    label: `${row.variety} ${row.tenor}`,
    value: row.deltaText && row.deltaText !== EM_DASH ? `${row.rateText} · ${row.deltaText}` : row.rateText,
    tradeDate: row.tradeDate,
    source: row.seriesId,
    tone: "ok" as ModuleHomeTone,
  }));
}

export function buildLatestMacroSnapshotRows(
  latestSeries: ChoiceMacroLatestPoint[],
  excludeSeriesIds: Set<string>,
): ModuleHomeDetailRow[] {
  const byId = new Map(latestSeries.map((point) => [point.series_id, point]));
  const rows: ModuleHomeDetailRow[] = [];
  const seen = new Set<string>();

  for (const seriesId of MACRO_SNAPSHOT_PRIORITY_IDS) {
    const point = byId.get(seriesId);
    if (!point || seen.has(point.series_id) || excludeSeriesIds.has(point.series_id)) {
      continue;
    }
    seen.add(point.series_id);
    rows.push(macroPointToDetailRow(point, point.series_name, point.series_id));
  }

  for (const point of latestSeries) {
    if (rows.length >= 24) {
      break;
    }
    if (seen.has(point.series_id) || excludeSeriesIds.has(point.series_id)) {
      continue;
    }
    if (point.series_id.startsWith("CA.") || /指数|期货|Brent|原油|铜|铝|汇率/.test(point.series_name)) {
      seen.add(point.series_id);
      rows.push(macroPointToDetailRow(point, point.series_name, point.series_id));
    }
  }

  return rows;
}

export function buildNewsEventsSnapshotRows(
  payload: ChoiceNewsEventsPayload | undefined,
): ModuleHomeDetailRow[] {
  if (!payload || payload.events.length === 0) {
    return [];
  }
  // 来源标注按实际数据链路写 Tushare 备份（choice_news_event 表现存记录全部来自
  // Tushare 备份链路，从未有 Choice 供应商新闻）；choice-events 仅保留为接口路径名。
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "news-events-total",
      label: "事件总数",
      value: `${payload.total_rows} 条`,
      tradeDate: EM_DASH,
      source: "Tushare 备份链路",
      tone: payload.total_rows > 0 ? "ok" : "muted",
    },
  ];
  for (const [index, event] of payload.events.slice(0, 5).entries()) {
    const headline = summarizeMacroNewsEvent(event);
    rows.push({
      key: `news-event-${event.event_key || index}`,
      label: event.topic_code || "新闻事件",
      value: headline || event.payload_text?.trim() || "待解析标题",
      detail: event.received_at?.slice(0, 10) ?? undefined,
      tradeDate: event.received_at?.slice(0, 10) ?? EM_DASH,
      source: event.content_type || "Tushare 备份链路",
      tone: event.error_code === 0 ? "ok" : "watch",
    });
  }
  return rows;
}

export const MARKET_CURVE_TERM_SPREAD_KEYS = [
  "term-spread-10y-2y",
  "term-spread-10y-5y",
  "term-spread-10y-1y",
] as const;

const MARKET_CURVE_CREDIT_SPREAD_MATCHERS = [
  "credit-spread",
  "credit_spread",
  "信用利差",
  "aa-国债",
  "aa5y",
] as const;

export function findMarketCreditSpreadRow(rows: ModuleHomeDetailRow[]): ModuleHomeDetailRow | undefined {
  return rows.find((row) => {
    if (row.key.startsWith("term-spread-")) {
      return false;
    }
    const haystack = `${row.key} ${row.label}`.toLowerCase();
    return MARKET_CURVE_CREDIT_SPREAD_MATCHERS.some((token) => haystack.includes(token.toLowerCase()));
  });
}

export function buildMarketCurveSpreadRows(keyRatePanel?: ModuleHomeDetailPanel): {
  termSpreadRows: ModuleHomeDetailRow[];
  creditSpreadRow?: ModuleHomeDetailRow;
} {
  const rows = keyRatePanel?.rows ?? [];
  const termSpreadRows = MARKET_CURVE_TERM_SPREAD_KEYS.map((key) => rows.find((row) => row.key === key)).filter(
    (row): row is ModuleHomeDetailRow => Boolean(row),
  );
  const creditSpreadRow = findMarketCreditSpreadRow(rows);
  return { termSpreadRows, creditSpreadRow };
}
