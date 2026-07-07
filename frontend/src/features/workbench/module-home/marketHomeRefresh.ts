export type RefreshableMarketHomeQuery = {
  fetchStatus?: "fetching" | "paused" | "idle";
  refetch: () => Promise<unknown>;
};

export async function refetchAfterMarketRefresh(query: RefreshableMarketHomeQuery | undefined) {
  if (!query) return;
  await query.refetch();
}
