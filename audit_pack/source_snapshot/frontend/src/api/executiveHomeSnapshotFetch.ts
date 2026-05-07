import type { ApiEnvelope, GetHomeSnapshotOptions, HomeSnapshotPayload } from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";

export async function fetchHomeSnapshotEnvelope(
  fetchImpl: typeof fetch,
  baseUrl: string,
  options?: GetHomeSnapshotOptions,
): Promise<ApiEnvelope<HomeSnapshotPayload>> {
  const params = new URLSearchParams();
  if (options?.reportDate) params.set("report_date", options.reportDate);
  if (options?.allowPartial) params.set("allow_partial", "true");
  const qs = params.toString();
  const response = await fetchImpl(
    `${baseUrl}/ui/home/snapshot${qs ? `?${qs}` : ""}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: /ui/home/snapshot (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<HomeSnapshotPayload>;
}
