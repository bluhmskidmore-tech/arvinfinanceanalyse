/**
 * Cube client slice. Mock factory lives in cubeMockClient.ts so mock
 * composition stays out of the real-mode bundle.
 */
import type {
  CubeDimensionsPayload,
  CubeQueryRequest,
  CubeQueryResult,
} from "./contracts";
import { ActionRequestError } from "./transport";

export type CubeClientMethods = {
  getCubeDimensions: (factTable: string) => Promise<CubeDimensionsPayload>;
  executeCubeQuery: (request: CubeQueryRequest) => Promise<CubeQueryResult>;
};

type CubeClientFactoryOptions = {
  fetchImpl: typeof fetch;
  baseUrl: string;
};

/** RBAC 拒绝（viewer 角色默认拿不到 cube 读权限）要能被页面识别，不能和网络故障混成同一句「稍后重试」。 */
export function isForbiddenCubeError(error: unknown): boolean {
  return error instanceof ActionRequestError && error.status === 403;
}

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
        throw new ActionRequestError(
          `Request failed: /api/cube/dimensions/${factTable} (${response.status})`,
          { status: response.status },
        );
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
        let detail = text;
        try {
          const body = JSON.parse(text) as { detail?: unknown };
          if (typeof body.detail === "string") detail = body.detail;
        } catch {
          // Non-JSON transport failures still retain their original message.
        }
        throw new ActionRequestError(detail || `Cube query failed (${response.status})`, {
          status: response.status,
        });
      }
      return response.json() as Promise<CubeQueryResult>;
    },
  };
}
