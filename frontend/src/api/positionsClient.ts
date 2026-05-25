/**
 * Positions domain client slice.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AdbComparisonResponse,
  AdbCoveragePayload,
  AdbMonthlyResponse,
  AdbPayload,
  BondPositionItem,
  CockpitWarningsPayload,
  ContributionSplitPayload,
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
  YieldByPeriodPayload,
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
  getYieldByPeriod: (options: {
    year: number;
    periodType?: "monthly" | "quarterly" | "yearly";
  }) => Promise<YieldByPeriodPayload>;
  getLiabilityCounterparty: (options: {
    reportDate?: string | null;
    topN?: number;
  }) => Promise<LiabilityCounterpartyPayload>;
  getLiabilityKnowledgeBrief: () => Promise<ApiEnvelope<LiabilityKnowledgeBriefPayload>>;
  getCockpitWarnings: (reportDate?: string | null) => Promise<ApiEnvelope<CockpitWarningsPayload>>;
  getContributionSplit: (reportDate?: string | null) => Promise<ApiEnvelope<ContributionSplitPayload>>;
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
  getAdbCoverage: (startDate: string, endDate: string) => Promise<AdbCoveragePayload>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type PositionsCoreClientMethods = Pick<
  PositionsClientMethods,
  | "getPositionsBondSubTypes"
  | "getPositionsBondsList"
  | "getPositionsCounterpartyBonds"
  | "getPositionsInterbankProductTypes"
  | "getPositionsInterbankList"
  | "getPositionsCounterpartyInterbankSplit"
  | "getPositionsStatsRating"
  | "getPositionsStatsIndustry"
  | "getPositionsCustomerDetails"
  | "getPositionsCustomerTrend"
>;

type PositionsMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsurePositionsMockBundle = () => Promise<PositionsMockBundle>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

export type PositionsClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

export function createDemoPositionsClient(
  delay: Delay,
  ensureMockClientBundle: EnsurePositionsMockBundle,
): PositionsCoreClientMethods {
  return {
    async getPositionsBondSubTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.sub_types",
        { sub_types: ["利率债", "信用债"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondsList(options: {
      reportDate?: string | null;
      subType?: string | null;
      page: number;
      pageSize: number;
      includeIssued?: boolean;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyBonds(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
      page?: number;
      pageSize?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.bonds",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
          total_weighted_rate: null,
          total_weighted_coupon_rate: null,
          total_customers: 0,
          cr10_ratio: "62.34%",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankProductTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.product_types",
        { product_types: ["拆借", "存放"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankList(options: {
      reportDate?: string | null;
      productType?: string | null;
      direction?: PositionDirection | "ALL" | null;
      page: number;
      pageSize: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyInterbankSplit(options: {
      startDate: string;
      endDate: string;
      productType?: string | null;
      topN?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.interbank.split",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          asset_total_amount: "0",
          asset_total_avg_daily: "0",
          asset_total_weighted_rate: null,
          asset_customer_count: 0,
          liability_total_amount: "0",
          liability_total_avg_daily: "0",
          liability_total_weighted_rate: null,
          liability_customer_count: 0,
          asset_items: [],
          liability_items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsRating(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.rating",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsIndustry(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.industry",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerDetails(options: {
      customerName: string;
      reportDate?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.details",
        {
          customer_name: options.customerName,
          report_date: options.reportDate ?? "",
          total_market_value: "0",
          bond_count: 0,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerTrend(options: {
      customerName: string;
      endDate?: string | null;
      days?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.trend",
        {
          customer_name: options.customerName,
          start_date: options.endDate ?? "",
          end_date: options.endDate ?? "",
          days: options.days ?? 30,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };
}

export function createRealPositionsClient(
  options: PositionsClientFactoryOptions,
): PositionsCoreClientMethods {
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getPositionsBondSubTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<SubTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds/sub_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsBondsList: ({
      reportDate,
      subType,
      page,
      pageSize,
      includeIssued,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (includeIssued) {
        params.set("include_issued", "true");
      }
      return requestJson<PageResponse<BondPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds?${params.toString()}`,
      );
    },
    getPositionsCounterpartyBonds: ({
      startDate,
      endDate,
      subType,
      topN,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      params.set("page", String(page ?? 1));
      params.set("page_size", String(pageSize ?? 50));
      return requestJson<CounterpartyStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/bonds?${params.toString()}`,
      );
    },
    getPositionsInterbankProductTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<ProductTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank/product_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsInterbankList: ({
      reportDate,
      productType,
      direction,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (direction && direction !== "ALL") {
        params.set("direction", direction);
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      return requestJson<PageResponse<InterbankPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank?${params.toString()}`,
      );
    },
    getPositionsCounterpartyInterbankSplit: ({
      startDate,
      endDate,
      productType,
      topN,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<InterbankCounterpartySplitResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/interbank/split?${params.toString()}`,
      );
    },
    getPositionsStatsRating: ({ startDate, endDate, subType }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      return requestJson<RatingStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/rating?${params.toString()}`,
      );
    },
    getPositionsStatsIndustry: ({ startDate, endDate, subType, topN }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<IndustryStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/industry?${params.toString()}`,
      );
    },
    getPositionsCustomerDetails: ({ customerName, reportDate }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      return requestJson<CustomerBondDetailsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/details?${params.toString()}`,
      );
    },
    getPositionsCustomerTrend: ({ customerName, endDate, days }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (endDate?.trim()) {
        params.set("end_date", endDate.trim());
      }
      if (days !== undefined) {
        params.set("days", String(days));
      }
      return requestJson<CustomerBalanceTrendResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/trend?${params.toString()}`,
      );
    },
  };
}
