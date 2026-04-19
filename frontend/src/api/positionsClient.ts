/**
 * Positions domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AdbComparisonResponse,
  AdbMonthlyResponse,
  AdbPayload,
  BondPositionItem,
  CounterpartyStatsResponse,
  CustomerBalanceTrendResponse,
  CustomerBondDetailsResponse,
  IndustryStatsResponse,
  InterbankCounterpartySplitResponse,
  InterbankPositionItem,
  LiabilitiesMonthlyPayload,
  LiabilityCounterpartyPayload,
  LiabilityKnowledgeBriefPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
  PageResponse,
  PositionDirection,
  ProductTypesResponse,
  RatingStatsResponse,
  SubTypesResponse,
} from "./contracts";

export type PositionsClientMethods = {
  getPositionsBondSubTypes: (
    reportDate?: string | null,
  ) => Promise<ApiEnvelope<SubTypesResponse>>;
  getPositionsBondsList: (options: {
    reportDate?: string | null;
    subType?: string | null;
    page: number;
    pageSize: number;
    includeIssued?: boolean;
  }) => Promise<ApiEnvelope<PageResponse<BondPositionItem>>>;
  getPositionsCounterpartyBonds: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
    topN?: number;
    page?: number;
    pageSize?: number;
  }) => Promise<ApiEnvelope<CounterpartyStatsResponse>>;
  getPositionsInterbankProductTypes: (
    reportDate?: string | null,
  ) => Promise<ApiEnvelope<ProductTypesResponse>>;
  getPositionsInterbankList: (options: {
    reportDate?: string | null;
    productType?: string | null;
    direction?: PositionDirection | "ALL" | null;
    page: number;
    pageSize: number;
  }) => Promise<ApiEnvelope<PageResponse<InterbankPositionItem>>>;
  getPositionsCounterpartyInterbankSplit: (options: {
    startDate: string;
    endDate: string;
    productType?: string | null;
    topN?: number;
  }) => Promise<ApiEnvelope<InterbankCounterpartySplitResponse>>;
  getPositionsStatsRating: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
  }) => Promise<ApiEnvelope<RatingStatsResponse>>;
  getPositionsStatsIndustry: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
    topN?: number;
  }) => Promise<ApiEnvelope<IndustryStatsResponse>>;
  getPositionsCustomerDetails: (options: {
    customerName: string;
    reportDate?: string | null;
  }) => Promise<ApiEnvelope<CustomerBondDetailsResponse>>;
  getPositionsCustomerTrend: (options: {
    customerName: string;
    endDate?: string | null;
    days?: number;
  }) => Promise<ApiEnvelope<CustomerBalanceTrendResponse>>;
  getLiabilityRiskBuckets: (reportDate?: string | null) => Promise<LiabilityRiskBucketsPayload>;
  getLiabilityYieldMetrics: (reportDate?: string | null) => Promise<LiabilityYieldMetricsPayload>;
  getLiabilityCounterparty: (options: {
    reportDate?: string | null;
    topN?: number;
  }) => Promise<LiabilityCounterpartyPayload>;
  getLiabilityKnowledgeBrief: () => Promise<ApiEnvelope<LiabilityKnowledgeBriefPayload>>;
  getLiabilitiesMonthly: (year: number) => Promise<LiabilitiesMonthlyPayload>;
  getLiabilityAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
  getAdb: (params: { startDate: string; endDate: string }) => Promise<AdbPayload>;
  getAdbComparison: (
    startDate: string,
    endDate: string,
    options?: {
      topN?: number;
    },
  ) => Promise<AdbComparisonResponse>;
  getAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
};
