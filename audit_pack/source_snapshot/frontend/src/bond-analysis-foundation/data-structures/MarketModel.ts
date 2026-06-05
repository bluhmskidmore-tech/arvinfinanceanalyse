import type { DataQualityMeta, DateString, TimeSeriesPoint } from "./BondModel";

export type YieldCurveTenor = "1Y" | "2Y" | "3Y" | "5Y" | "7Y" | "10Y" | "20Y" | "30Y";

export interface YieldCurvePoint {
  tenor: YieldCurveTenor | string;
  yieldValue: number;
  changeBp?: number;
}

export interface YieldCurve {
  curveId: string;
  curveName: string;
  asOfDate: DateString;
  points: YieldCurvePoint[];
  dataQuality?: DataQualityMeta;
}

export interface MarketIndex {
  indexId: string;
  indexName: string;
  indexType: "bond" | "volatility" | "credit_spread" | "liquidity" | string;
  currentValue: number;
  changePct?: number;
  changeBp?: number;
  asOfDate: DateString;
}

export interface MarketIndexSnapshot {
  asOfDate: DateString;
  indices: MarketIndex[];
  dataQuality?: DataQualityMeta;
}

export interface RealTimeBondQuote {
  bondCode: string;
  lastPrice: number;
  yieldToMaturity: number;
  changePct: number;
  tradeVolume: number;
  tradeAmount: number;
  quoteTime: string;
}

export interface HistoricalSeriesQuery {
  from?: DateString;
  to?: DateString;
  interval?: "1D" | "1W" | "1M";
}

export interface YieldCurveQuery {
  curveId?: string;
  asOfDate?: DateString;
}

export interface MarketIndicesQuery {
  asOfDate?: DateString;
  indexTypes?: string[];
}

export type HistoricalSeries = TimeSeriesPoint[];
