import { type PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { createApiClient, ApiClientProvider } from "../../../api/client";
import { useMacroToolkitOperationActions } from "./useMacroToolkitOperationActions";

it.each([
  ["cffex", "cache"], ["cffex", "reads"],
  ["commodity", "cache"], ["commodity", "reads"],
] as const)("stops %s post-refresh work when unmounted during %s", async (action, stage) => {
  const client = createApiClient({ mode: "mock" });
  vi.spyOn(client, "refreshCffexMemberRank").mockResolvedValue({ result: { refresh: { status: "completed", run_id: "cffex-complete" } }, result_meta: {} } as Awaited<ReturnType<typeof client.refreshCffexMemberRank>>);
  vi.spyOn(client, "refreshCommodityFutures").mockResolvedValue({ result: { refresh: { status: "completed", run_id: "commodity-complete", terminal_snapshot_status: "captured", after_status: { status: "ready" } } }, result_meta: {} } as Awaited<ReturnType<typeof client.refreshCommodityFutures>>);
  const queryClient = new QueryClient();
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  const cancel = vi.spyOn(queryClient, "cancelQueries").mockImplementation(() => stage === "cache" ? pending : Promise.resolve());
  const remove = vi.spyOn(queryClient, "removeQueries");
  const refetch = vi.fn(() => stage === "reads" ? pending : Promise.resolve());
  const loadFullAnalysis = vi.fn(async () => null);
  const options: Parameters<typeof useMacroToolkitOperationActions>[0] = {
    analysis: undefined, analysisQuery: { refetch }, commodityFuturesRefresh: { permission: { mode: "identity_only", allowed: true, user_id: "synthetic", role: "operator" } },
    crisisScoreResult: null, fullAnalysisError: null, isCoreAnalysis: false,
    loadFullAnalysis, modelChainQuery: { refetch }, payload: undefined,
    scriptsQuery: { refetch }, selectedScript: null,
    setCommitteeActionLocatorKey: vi.fn(), setFocusedRepairKey: vi.fn(),
    setFullAnalysisEnvelope: vi.fn(), setFullAnalysisError: vi.fn(),
    setSelectedEvidenceHref: vi.fn(), setSelectedGovernanceFocus: vi.fn(),
    strategyQuery: { refetch },
  };
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={queryClient}><ApiClientProvider client={client}>{children}</ApiClientProvider></QueryClientProvider>;
  const { result, unmount } = renderHook(() => useMacroToolkitOperationActions(options), { wrapper });
  let work!: Promise<void>;
  act(() => { work = action === "cffex" ? result.current.refreshCffexMemberRank() : result.current.refreshCommodityFutures(); });
  await waitFor(() => expect(stage === "cache" ? cancel : refetch).toHaveBeenCalled());
  unmount();
  await act(async () => { release(); await work; });
  expect(loadFullAnalysis).not.toHaveBeenCalled();
  if (stage === "cache") { expect(refetch).not.toHaveBeenCalled(); expect(remove).not.toHaveBeenCalled(); }
  queryClient.clear();
});
