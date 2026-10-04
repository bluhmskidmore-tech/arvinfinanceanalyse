import type { ApiEnvelope, GetHomeSnapshotOptions, HomeSnapshotPayload } from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";
import { DEFAULT_REQUEST_JSON_TIMEOUT_MS, fetchWithOptionalTimeout } from "./transport";

export async function fetchHomeSnapshotEnvelope(
  fetchImpl: typeof fetch,
  baseUrl: string,
  options?: GetHomeSnapshotOptions,
): Promise<ApiEnvelope<HomeSnapshotPayload>> {
  const params = new URLSearchParams();
  if (options?.reportDate) params.set("report_date", options.reportDate);
  if (options?.allowPartial) params.set("allow_partial", "true");
  const qs = params.toString();
  return fetchWithOptionalTimeout(
    fetchImpl,
    `${baseUrl}/ui/home/snapshot${qs ? `?${qs}` : ""}`,
    { headers: { Accept: "application/json" } },
    DEFAULT_REQUEST_JSON_TIMEOUT_MS,
    "/ui/home/snapshot",
    async (response) => {
      if (!response.ok) {
        const detail = await readHttpJsonDetail(response);
        throw new Error(detail ?? `Request failed: /ui/home/snapshot (${response.status})`);
      }
      return (await response.json()) as ApiEnvelope<HomeSnapshotPayload>;
    },
  );
}
