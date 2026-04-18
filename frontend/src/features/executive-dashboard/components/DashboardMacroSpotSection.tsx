import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";

function pickSpotSeries(series: ChoiceMacroLatestPoint[]) {
  return series
    .filter((p) => (p.refresh_tier ?? "stable") !== "isolated")
    .slice(0, 6);
}

function formatMacroValue(point: ChoiceMacroLatestPoint): string {
  const v = point.value_numeric;
  const u = (point.unit ?? "").toLowerCase();
  if (!Number.isFinite(v)) {
    return "—";
  }
  if (u.includes("bp") && !u.includes("bps")) {
    return formatNumeric(formatRawAsNumeric({ raw: v, unit: "bp", sign_aware: false }));
  }
  if (u.includes("%")) {
    return formatNumeric(formatRawAsNumeric({ raw: v / 100, unit: "pct", sign_aware: false }));
  }
  if (Math.abs(v) >= 200) {
    return formatNumeric(formatRawAsNumeric({ raw: v, unit: "count", sign_aware: false }));
  }
  const core = formatNumeric(formatRawAsNumeric({ raw: v, unit: "ratio", sign_aware: false, precision: 3 }));
  const suffix = point.unit?.trim();
  return suffix && !suffix.includes("%") ? `${core} ${suffix}` : core;
}

function toState(isLoading: boolean, isError: boolean, count: number): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "宏观快照加载失败" };
  if (count === 0) return { kind: "empty", hint: "Choice 宏观序列暂无可用条目。" };
  return { kind: "ok" };
}

const CARD_STYLE = {
  display: "grid",
  gap: 6,
  padding: 14,
  borderRadius: 16,
  background: "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,249,253,0.98) 100%)",
  border: "1px solid #e4ebf5",
} as const;

export function DashboardMacroSpotSection() {
  const client = useApiClient();
  const query = useQuery({
    queryKey: ["dashboard", "choice-macro-spot", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });

  const points = useMemo(
    () => pickSpotSeries(query.data?.result.series ?? []),
    [query.data?.result.series],
  );

  const state = useMemo(
    () => toState(query.isLoading, query.isError, points.length),
    [query.isLoading, query.isError, points.length],
  );

  return (
    <div data-testid="dashboard-macro-spot-section">
      <DataSection title="市场监控（宏观快照）" state={state} onRetry={() => void query.refetch()}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 12,
          }}
        >
          {points.map((p) => (
            <div key={p.series_id} style={CARD_STYLE}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#8090a8" }}>{p.series_name}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#162033", fontVariantNumeric: "tabular-nums" }}>
                {formatMacroValue(p)}
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>交易日 {p.trade_date}</div>
            </div>
          ))}
        </div>
      </DataSection>
    </div>
  );
}
