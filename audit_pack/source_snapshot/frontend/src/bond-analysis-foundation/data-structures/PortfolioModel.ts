import type {
  Bond,
  CurrencyCode,
  DataQualityMeta,
  DateString,
  IsoDateTimeString,
} from "./BondModel";

export interface PortfolioHolding {
  positionId: string;
  bond: Bond;
  weight: number;
  faceValue?: number;
  quantity?: number;
  holdingCost: number;
  marketValue: number;
  unrealizedPnl: number;
  realizedPnl?: number;
  contributionYield: number;
}

export interface PortfolioStatistics {
  averageYield: number;
  weightedDuration: number;
  concentrationRatio: number;
  riskScore: number;
  dailyPnl?: number;
  monthlyPnl?: number;
  trackingError?: number;
}

export interface CurveExposurePoint {
  tenor: string;
  weight: number;
}

export interface BucketExposurePoint {
  bucket: string;
  weight: number;
}

export interface IssuerExposurePoint {
  issuerName: string;
  weight: number;
}

export interface StressTestResult {
  scenarioId: string;
  scenarioName: string;
  estimatedPnl: number;
  estimatedReturnBp?: number;
  note?: string;
}

export interface PortfolioAnalytics {
  asOfDate: DateString;
  curveExposure: CurveExposurePoint[];
  ratingExposure: BucketExposurePoint[];
  issuerExposure: IssuerExposurePoint[];
  stressTests: StressTestResult[];
  dataQuality?: DataQualityMeta;
}

export interface Portfolio {
  portfolioId: string;
  portfolioName: string;
  createdAt: IsoDateTimeString;
  managerName?: string;
  benchmark?: string;
  baseCurrency?: CurrencyCode;
  totalMarketValue: number;
  cashBalance?: number;
  statistics: PortfolioStatistics;
  holdings: PortfolioHolding[];
  analytics?: PortfolioAnalytics;
  dataQuality?: DataQualityMeta;
}

export interface PortfolioCreateRequest {
  portfolioName: string;
  benchmark?: string;
  baseCurrency?: CurrencyCode;
  managerName?: string;
  holdingBondIds?: string[];
}

export type PortfolioUpdateRequest = Partial<PortfolioCreateRequest>;
