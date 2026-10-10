export type RefreshableMarketHomeQuery = {
  fetchStatus?: "fetching" | "paused" | "idle";
  refetch: () => Promise<unknown>;
};

export async function refetchAfterMarketRefresh(query: RefreshableMarketHomeQuery | undefined) {
  if (!query) return;
  const result = await query.refetch();
  // React Query 默认以 isError 结果完成 refetch，不能把 Promise 完成视为读取成功。
  if (result && typeof result === "object" && "isError" in result && result.isError) {
    throw "error" in result && result.error ? result.error : new Error("页面数据重新读取失败");
  }
}
