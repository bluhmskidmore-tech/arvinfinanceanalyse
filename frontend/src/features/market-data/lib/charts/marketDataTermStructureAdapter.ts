import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import type {
  MarketDataRateQuoteRow,
  MarketDataTerminalSource,
} from "../marketDataTerminalModel";

const TENOR_ORDER = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

const CURVE_TYPE_BY_VARIETY: Record<string, string> = {
  国债: "treasury",
  国开: "cdb",
};

function tenorRank(tenor: string): number {
  const index = TENOR_ORDER.indexOf(tenor as (typeof TENOR_ORDER)[number]);
  return index >= 0 ? index : TENOR_ORDER.length + 1;
}

function parseRatePercentText(rateText: string): Numeric | null {
  const match = rateText.trim().match(/^([\d.]+)%$/);
  if (!match) {
    return null;
  }
  const percentPoints = Number.parseFloat(match[1]!);
  if (!Number.isFinite(percentPoints)) {
    return null;
  }
  // Numeric 契约中 unit="pct" 的 raw 是小数分数（后端 0.011217 ↔ display "+1.12%"），
  // 行情文本是百分点，需除以 100 归一，否则图表按契约 ×100 会画出 bp 量级。
  return {
    raw: percentPoints / 100,
    unit: "pct",
    display: rateText,
    precision: 2,
    sign_aware: false,
  };
}

function parseDeltaBpText(deltaText: string): Numeric | null {
  const normalized = deltaText.trim();
  if (!normalized || normalized === "无变动" || normalized === "--" || normalized === "—") {
    return null;
  }
  const match = normalized.match(/^([+-]?)([\d.]+)bp$/i);
  if (!match) {
    return null;
  }
  const sign = match[1] === "-" ? -1 : 1;
  const raw = sign * Number.parseFloat(match[2]!);
  if (!Number.isFinite(raw)) {
    return null;
  }
  return { raw, unit: "bp", display: deltaText, precision: 1, sign_aware: true };
}

function rowToTermPoint(row: MarketDataRateQuoteRow) {
  return {
    tenor: row.tenor,
    yield_pct: parseRatePercentText(row.rateText),
    delta_bp_prev: parseDeltaBpText(row.deltaText),
  };
}

function buildCurvePayload(
  curveType: string,
  rows: MarketDataRateQuoteRow[],
  source: MarketDataTerminalSource | null,
): YieldCurveTermStructureCurvePayload | null {
  const sorted = [...rows].sort((left, right) => tenorRank(left.tenor) - tenorRank(right.tenor));
  const points = sorted.map(rowToTermPoint).filter((point) => point.yield_pct?.raw != null);
  if (points.length === 0) {
    return null;
  }
  const tradeDate = sorted.find((row) => row.tradeDate)?.tradeDate ?? "";
  return {
    curve_type: curveType,
    trade_date_requested: tradeDate,
    trade_date_resolved: tradeDate || null,
    points,
    source_version: source?.sourceVersion ?? "",
    rule_version: "",
    vendor_name: "",
    vendor_version: source?.vendorVersion ?? "",
  };
}

export function adaptRateQuoteRowsToTermStructureCurves(
  rows: readonly MarketDataRateQuoteRow[],
  source: MarketDataTerminalSource | null,
  activeCurve: "treasury" | "cdb" | "both" = "both",
): YieldCurveTermStructureCurvePayload[] {
  const treasuryRows = rows.filter((row) => row.variety === "国债");
  const cdbRows = rows.filter((row) => row.variety === "国开");
  const curves: YieldCurveTermStructureCurvePayload[] = [];

  if (activeCurve === "treasury" || activeCurve === "both") {
    const treasury = buildCurvePayload(CURVE_TYPE_BY_VARIETY["国债"]!, treasuryRows, source);
    if (treasury) {
      curves.push(treasury);
    }
  }
  if (activeCurve === "cdb" || activeCurve === "both") {
    const cdb = buildCurvePayload(CURVE_TYPE_BY_VARIETY["国开"]!, cdbRows, source);
    if (cdb) {
      curves.push(cdb);
    }
  }

  return curves;
}
