import type { ApiClient, ApiClientOptions } from "./client";

export type ResolvedApiClientOptions = Required<ApiClientOptions>;

type ApiClientFactoryRecord = {
  options: ResolvedApiClientOptions;
  create: (options: ApiClientOptions) => ApiClient;
};

const apiClientFactoryRecords = new WeakMap<ApiClient, ApiClientFactoryRecord>();

export function registerApiClientFactory(
  client: ApiClient,
  options: ResolvedApiClientOptions,
  create: ApiClientFactoryRecord["create"],
): ApiClient {
  apiClientFactoryRecords.set(client, { options, create });
  return client;
}

export function getApiClientFactoryRecord(client: ApiClient): ApiClientFactoryRecord | null {
  return apiClientFactoryRecords.get(client) ?? null;
}
