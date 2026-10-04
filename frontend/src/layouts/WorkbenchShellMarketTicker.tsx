import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../api/clientContext";
import { buildShellTickerItems } from "./workbenchShellTicker";

export function WorkbenchShellMarketTicker() {
  const client = useApiClient();
  const shellTickerQuery = useQuery({
    queryKey: ["workbench-shell", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    staleTime: 60_000,
  });
  const shellTicker = useMemo(
    () => buildShellTickerItems(shellTickerQuery.data?.result?.series ?? []),
    [shellTickerQuery.data?.result?.series],
  );
  const hasItems = shellTicker.items.length > 0;
  let tickerState = "ready";
  let statusMessage: string | undefined;
  if (shellTickerQuery.isError) {
    tickerState = hasItems ? "stale" : "unavailable";
    statusMessage = hasItems ? "行情更新失败，显示上次结果" : "行情加载失败";
  } else if (shellTickerQuery.isPending) {
    tickerState = "loading";
    statusMessage = "行情加载中";
  } else if (!hasItems) {
    tickerState = "empty";
    statusMessage = "暂无可用行情";
  }

  return (
    <section
      data-testid="workbench-market-ticker"
      data-market-ticker-state={tickerState}
      className="workbench-market-ticker-shell"
    >
      <span className="workbench-market-ticker-label">
        市场快讯
      </span>
      {client.mode === "mock" && hasItems ? (
        <span
          data-testid="workbench-market-ticker-fallback-flag"
          className="workbench-market-ticker-fallback-flag"
          title="当前为显式演示模式，行情来自样例数据"
        >
          演示
        </span>
      ) : null}
      {statusMessage ? (
        <span className="workbench-market-ticker-meta" role="status">
          {statusMessage}
        </span>
      ) : null}
      {shellTicker.items.map((item, index) => (
        <div
          key={item.key}
          className="workbench-market-ticker-item"
        >
          <span className="workbench-market-ticker-meta">
            {item.label}
          </span>
          <strong
            className="workbench-market-ticker-strong"
            title={item.tradeDate ? `数据日期 ${item.tradeDate}` : undefined}
          >
            {item.value}
          </strong>
          <span
            className="workbench-market-ticker-delta"
            data-tone={item.tone}
            title={item.deltaTitle}
          >
            {item.delta}
          </span>
          {index < shellTicker.items.length - 1 ? (
            <span className="workbench-market-ticker-rule" />
          ) : null}
        </div>
      ))}
    </section>
  );
}

export default WorkbenchShellMarketTicker;
