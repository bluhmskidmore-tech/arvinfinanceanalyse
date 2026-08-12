import type { ApiClient } from "./client";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceNewsEventsBatchPayload,
  ChoiceNewsEventsPayload,
  ResearchCalendarResultPayload,
} from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";
import { mapResearchCalendarApiEvent } from "../lib/researchCalendarApiEvent";

type FetchLike = typeof fetch;

export type HomeMarketTickerClientMethods = Pick<
  ApiClient,
  | "getChoiceMacroLatest"
  | "getMarketDataRates"
  | "getChoiceNewsEvents"
  | "getChoiceNewsEventsBatch"
  | "getResearchCalendarEvents"
>;

type HomeMarketTickerClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

let mockClientPromise: Promise<HomeMarketTickerClientMethods> | null = null;

function loadMockClient(): Promise<HomeMarketTickerClientMethods> {
  if (!mockClientPromise) {
    mockClientPromise = import("./homeMarketTickerMockClient").then(
      ({ createMockHomeMarketTickerClient: createMockClient }) => createMockClient(),
    );
  }
  return mockClientPromise;
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

export function createRealHomeMarketTickerClient({
  fetchImpl,
  baseUrl,
}: HomeMarketTickerClientFactoryOptions): HomeMarketTickerClientMethods {
  return {
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/macro/choice-series/latest"),
    getMarketDataRates: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/market-data/rates"),
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      stockCode,
      includePayloadJson,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) params.set("group_id", groupId.trim());
      if (topicCode?.trim()) params.set("topic_code", topicCode.trim());
      if (stockCode?.trim()) params.set("stock_code", stockCode.trim());
      if (typeof includePayloadJson === "boolean") {
        params.set("include_payload_json", String(includePayloadJson));
      }
      if (errorOnly) params.set("error_only", "true");
      if (receivedFrom?.trim()) params.set("received_from", receivedFrom.trim());
      if (receivedTo?.trim()) params.set("received_to", receivedTo.trim());
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getChoiceNewsEventsBatch: ({ topics, groups }) => {
      const params = new URLSearchParams();
      const topicPairs = (topics ?? [])
        .filter(({ topicCode }) => topicCode.trim())
        .map(({ topicCode, limit }) => `${topicCode.trim()}:${limit}`);
      if (topicPairs.length > 0) params.set("topics", topicPairs.join(","));
      const groupPairs = (groups ?? [])
        .filter(({ groupId }) => groupId.trim())
        .map(({ groupId, limit }) => `${groupId.trim()}:${limit}`);
      if (groupPairs.length > 0) params.set("groups", groupPairs.join(","));
      return requestJson<ChoiceNewsEventsBatchPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest-batch?${params.toString()}`,
      );
    },
    getResearchCalendarEvents: (options) => {
      const params = new URLSearchParams();
      if (options?.startDate?.trim()) params.set("start_date", options.startDate.trim());
      if (options?.endDate?.trim()) {
        params.set("end_date", options.endDate.trim());
      } else if (options?.reportDate?.trim()) {
        params.set("end_date", options.reportDate.trim());
      }
      const query = params.toString();
      return requestJson<ResearchCalendarResultPayload>(
        fetchImpl,
        baseUrl,
        `/ui/calendar/supply-auctions${query ? `?${query}` : ""}`,
      ).then((payload) => payload.result.events.map(mapResearchCalendarApiEvent));
    },
  };
}

export function createMockHomeMarketTickerClient(): HomeMarketTickerClientMethods {
  return new Proxy({} as HomeMarketTickerClientMethods, {
    get(target, property, receiver) {
      if (property === "then") {
        return undefined;
      }
      if (typeof property === "symbol") {
        return Reflect.get(target, property, receiver);
      }
      return async (...args: unknown[]) => {
        const client = await loadMockClient();
        const method = client[property as keyof HomeMarketTickerClientMethods] as (
          ...methodArgs: unknown[]
        ) => unknown;
        return method(...args);
      };
    },
  });
}
