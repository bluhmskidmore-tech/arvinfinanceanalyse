/**
 * Positions domain client slice.
 * Imported and re-exported by client.ts for backward compatibility.
 * Demo/mock factory lives in positionsMockClient.ts so drill fixtures stay
 * out of the real-mode bundle.
 */
import type {
  ApiEnvelope,
  BondPositionItem,
  CounterpartyStatsResponse,
  CustomerBalanceTrendResponse,
  CustomerBondDetailsResponse,
  IndustryStatsResponse,
  InterbankCounterpartySplitResponse,
  InterbankPositionItem,
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
};

type FetchLike = typeof fetch;

export type PositionsCoreClientMethods = Pick<
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
