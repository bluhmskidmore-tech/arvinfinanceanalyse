export type DateString = string;
export type IsoDateTimeString = string;
export type CurrencyCode = "CNY" | "USD" | "EUR" | "HKD" | string;
export type BondMarket = "CIBM" | "SSE" | "SZSE" | "OTC" | "HKEX" | string;
export type IssuerType =
  | "sovereign"
  | "policy_bank"
  | "local_government"
  | "commercial_bank"
  | "corporate"
  | "asset_backed"
  | "other";
export type CouponType = "fixed" | "floating" | "zero_coupon" | "step_up" | "other";
export type PaymentFrequency =
  | "ANNUAL"
  | "SEMI_ANNUAL"
  | "QUARTERLY"
  | "MONTHLY"
  | "AT_MATURITY";
export type BondRating =
  | "AAA"
  | "AA+"
  | "AA"
  | "AA-"
  | "A+"
  | "A"
  | "A-"
  | "BBB+"
  | "BBB"
  | "BBB-"
  | "BB+"
  | "BB"
  | "B"
  | "CCC"
  | "CC"
  | "C"
  | "D"
  | "NR";
export type LiquidityRating = "L1" | "L2" | "L3" | "L4";
export type DataFreshness = "live" | "delayed" | "stale" | "fallback";
export type SortDirection = "asc" | "desc";
export type BondMetricKey =
  | "cleanPrice"
  | "yieldToMaturity"
  | "creditSpreadBp"
  | "modifiedDuration"
  | "convexity"
  | "tradeVolume"
  | "liquidityRating";

export interface DataQualityMeta {
  asOfDate: DateString;
  source: string;
  freshness: DataFreshness;
  isStale: boolean;
  fallbackDate?: DateString;
  lastUpdatedAt?: IsoDateTimeString;
  traceId?: string;
  note?: string;
}

export interface BondBasicInfo {
  bondId: string;
  bondCode: string;
  isin?: string;
  market: BondMarket;
  shortName: string;
  fullName?: string;
  issuerId: string;
  issuerName: string;
  issuerType: IssuerType;
  currency: CurrencyCode;
  couponType: CouponType;
  couponRate?: number;
  issueDate: DateString;
  maturityDate: DateString;
  paymentFrequency?: PaymentFrequency;
}

export interface BondMarketData {
  cleanPrice: number;
  dirtyPrice?: number;
  yieldToMaturity: number;
  yieldChangeBp: number;
  priceChangePct: number;
  tradeVolume?: number;
  tradeAmount?: number;
  bidPrice?: number;
  askPrice?: number;
  midPrice?: number;
  quoteTime?: IsoDateTimeString;
  dataQuality: DataQualityMeta;
}

export interface BondRiskMetrics {
  rating: BondRating;
  internalRating?: string;
  modifiedDuration: number;
  macaulayDuration?: number;
  convexity?: number;
  dv01?: number;
  creditSpreadBp?: number;
  zSpreadBp?: number;
  optionAdjustedSpreadBp?: number;
  liquidityRating: LiquidityRating;
  riskScore: number;
}

export interface TimeSeriesPoint {
  date: DateString;
  value: number;
  change?: number;
  label?: string;
}

export interface BondRatingHistoryEvent {
  effectiveDate: DateString;
  agency: string;
  previousRating?: BondRating;
  newRating: BondRating;
  outlook?: string;
  note?: string;
}

export interface BondHistoricalSeries {
  priceHistory: TimeSeriesPoint[];
  yieldHistory: TimeSeriesPoint[];
  spreadHistory?: TimeSeriesPoint[];
  ratingHistory: BondRatingHistoryEvent[];
}

export interface Bond extends BondBasicInfo {
  sector?: string;
  tags?: string[];
  marketData: BondMarketData;
  riskMetrics: BondRiskMetrics;
  history: BondHistoricalSeries;
}

export interface RangeFilter {
  min?: number;
  max?: number;
}

export interface PaginationQuery {
  page?: number;
  pageSize?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasNextPage?: boolean;
}

export interface BondListQuery extends PaginationQuery {
  query?: string;
  sortBy?: BondMetricKey | "rating" | "maturityDate" | "issuerName";
  sortOrder?: SortDirection;
  ratings?: BondRating[];
  issuerTypes?: IssuerType[];
  markets?: BondMarket[];
  maturityDateFrom?: DateString;
  maturityDateTo?: DateString;
}

export interface BondSearchRequest extends BondListQuery {
  yieldRange?: RangeFilter;
  durationRange?: RangeFilter;
  liquidityRatings?: LiquidityRating[];
  sectors?: string[];
  tags?: string[];
}
