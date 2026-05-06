import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";

const MARKET_STRIP_PRIORITY_IDS: ReadonlyArray<readonly string[]> = [
  ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
  ["EMM00166502"],
  ["CA.CN_US_SPREAD", "EM1"],
  ["CA.DR007", "M002", "EMM00167613"],
  ["CA.USDCNY", "EMM00058124"],
  ["CA.US_GOV_10Y", "EMG00001310", "E1003238"],
] as const;

function pickMarketStripPoints(points: ChoiceMacroLatestPoint[]): ChoiceMacroLatestPoint[] {
  const candidates = points.filter((point) => (point.refresh_tier ?? "stable") !== "isolated");
  const selected: ChoiceMacroLatestPoint[] = [];
  const seen = new Set<string>();

  for (const ids of MARKET_STRIP_PRIORITY_IDS) {
    const point = candidates.find((candidate) => ids.includes(candidate.series_id));
    if (!point || seen.has(point.series_id)) {
      continue;
    }
    selected.push(point);
    seen.add(point.series_id);
  }

  for (const point of candidates) {
    if (seen.has(point.series_id)) {
      continue;
    }
    selected.push(point);
    seen.add(point.series_id);
    if (selected.length >= 6) {
      break;
    }
  }

  return selected.slice(0, 6);
}

export function DashboardMarketStrip() {
  const client = useApiClient();
  const query = useQuery({
    queryKey: ["dashboard", "home-market-strip", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });

  const points = useMemo(
    () => pickMarketStripPoints(query.data?.result.series ?? []),
    [query.data?.result.series],
  );

  const statusLabel = query.isLoading
    ? "载入中"
    : query.isError
      ? "暂不可用"
      : points.length > 0
        ? "最近交易日"
        : "暂无数据";

  return (
    <section data-testid="dashboard-market-strip" className="dashboard-home-panel dashboard-home-market-strip">
      <div className="dashboard-market-strip__header">
        <div className="dashboard-home-section-heading">
          <span className="dashboard-home-section-eyebrow">市场上下文</span>
          <h2 className="dashboard-home-section-title">市场快照</h2>
        </div>
        <span className="dashboard-home-badge dashboard-governance-tone-info">{statusLabel}</span>
      </div>
      {query.isError ? (
        <div
          data-testid="dashboard-market-strip-unavailable"
          className="dashboard-market-strip__degraded"
        >
          <div className="dashboard-market-strip__degraded-copy">
            <strong className="dashboard-home-strong">市场数据暂不可用</strong>
            <span className="dashboard-home-muted">不展示替代数字，下方明细穿透仍可继续查看。</span>
          </div>
          <div className="dashboard-market-strip__placeholder" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <button type="button" className="dashboard-home-link-button" onClick={() => void query.refetch()}>
            重试
          </button>
        </div>
      ) : points.length === 0 ? (
        <div className="dashboard-market-strip__state">
          <span className="dashboard-home-muted">
            {query.isLoading ? "市场快照载入中。" : "Choice 宏观序列当前暂无可用条目。"}
          </span>
        </div>
      ) : (
        <div data-testid="dashboard-macro-spot-grid" className="dashboard-market-strip__grid">
          {points.map((point) => (
            <article key={point.series_id} className="dashboard-market-strip__item">
              <span className="dashboard-home-muted-label dashboard-market-strip__label" title={point.series_name}>
                {point.series_name}
              </span>
              <strong className="dashboard-market-strip__value">
                {formatChoiceMacroValue(point, { spaceBeforeUnit: false })}
              </strong>
              <span className="dashboard-market-strip__delta">
                {formatChoiceMacroDelta(point, { spaceBeforeUnit: false })}
              </span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
