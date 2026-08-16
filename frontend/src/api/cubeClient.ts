/**
 * Cube client slice. Mock factory lives in cubeMockClient.ts so mock
 * composition stays out of the real-mode bundle.
 */
import type {
  CubeDimensionsPayload,
  CubeQueryRequest,
  CubeQueryResult,
} from "./contracts";

export type CubeClientMethods = {
  getCubeDimensions: (factTable: string) => Promise<CubeDimensionsPayload>;
  executeCubeQuery: (request: CubeQueryRequest) => Promise<CubeQueryResult>;
};

type CubeClientFactoryOptions = {
  fetchImpl: typeof fetch;
  baseUrl: string;
};

export function createRealCubeClient({
  fetchImpl,
  baseUrl,
}: CubeClientFactoryOptions): CubeClientMethods {
  return {
    getCubeDimensions: async (factTable: string) => {
      const response = await fetchImpl(
        `${baseUrl}/api/cube/dimensions/${encodeURIComponent(factTable)}`,
        {
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        throw new Error(`Request failed: /api/cube/dimensions/${factTable} (${response.status})`);
      }
      return response.json() as Promise<CubeDimensionsPayload>;
    },
    executeCubeQuery: async (request: CubeQueryRequest) => {
      const response = await fetchImpl(`${baseUrl}/api/cube/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Cube query failed (${response.status})`);
      }
      return response.json() as Promise<CubeQueryResult>;
    },
  };
}
