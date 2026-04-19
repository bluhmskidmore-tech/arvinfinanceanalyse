import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

function pickSpotSeries(series: ChoiceMacroLatestPoint[]) {
  return series
    .filter((point) => (point.refresh_tier ?? "stable") !== "isolated")
    .slice(0, 6);
}

function formatMacroValue(point: ChoiceMacroLatestPoint): string {
  const value = point.value_numeric;
  const unit = (point.unit ?? "").toLowerCase();
  if (!Number.isFinite(value)) {
    return "—";
  }
  if (unit.includes("bp") && !unit.includes("bps")) {
    return formatNumeric(formatRawAsNumeric({ raw: value, unit: "bp", sign_aware: false }));
  }
  if (unit.includes("%")) {
    return formatNumeric(formatRawAsNumeric({ raw: value / 100, unit: "pct", sign_aware: false }));
  }
  if (Math.abs(value) >= 200) {
    return formatNumeric(formatRawAsNumeric({ raw: value, unit: "count", sign_aware: false }));
  }
  const core = formatNumeric(
    formatRawAsNumeric({ raw: value, unit: "ratio", sign_aware: false, precision: 3 }),
  );
  const suffix = point.unit?.trim();
  return suffix && !suffix.includes("%") ? `${core} ${suffix}` : core;
}

function toState(
  isLoading: boolean,
  isError: boolean,
  count: number,
): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "市场快照加载失败" };
  if (count === 0) return { kind: "empty", hint: "Choice 宏观序列当前暂无可用条目。" };
  return { kind: "ok" };
}

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
    <DashboardCockpitSection
      testId="dashboard-macro-spot-section"
      eyebrow="Market Context"
      title="市场快照"
      state={state}
      onRetry={() => void query.refetch()}
    >
      <div
        data-testid="dashboard-macro-spot-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(148px, 1fr))",
          gap: 12,
        }}
      >
        {points.map((point) => (
          <article key={point.series_id} style={cockpitInsetCardStyle}>
            <span style={{ color: shellTokens.colorTextMuted, fontSize: 11, fontWeight: 700 }}>
              {point.series_name}
            </span>
            <strong
              style={{
                color: shellTokens.colorTextPrimary,
                fontSize: 22,
                lineHeight: 1.1,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.03em",
              }}
            >
              {formatMacroValue(point)}
            </strong>
            <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
              交易日 {point.trade_date}
            </span>
          </article>
        ))}
      </div>
    </DashboardCockpitSection>
  );
}
