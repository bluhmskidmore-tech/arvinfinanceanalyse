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
  const shellTickerItems = useMemo(
    () => buildShellTickerItems(shellTickerQuery.data?.result?.series ?? []),
    [shellTickerQuery.data?.result?.series],
  );

  return (
    <section
      data-testid="workbench-market-ticker"
      className="workbench-market-ticker-shell"
    >
      <span className="workbench-market-ticker-label">
        市场快讯
      </span>
      {shellTickerItems.map((item, index) => (
        <div
          key={item.key}
          className="workbench-market-ticker-item"
        >
          <span className="workbench-market-ticker-meta">
            {item.label}
          </span>
          <strong className="workbench-market-ticker-strong">
            {item.value}
          </strong>
          <span className="workbench-market-ticker-delta" data-tone={item.tone}>
            {item.delta}
          </span>
          {index < shellTickerItems.length - 1 ? (
            <span className="workbench-market-ticker-rule" />
          ) : null}
        </div>
      ))}
    </section>
  );
}

export default WorkbenchShellMarketTicker;
