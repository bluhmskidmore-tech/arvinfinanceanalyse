import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import { DashboardCockpitSection } from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

const DASHBOARD_SPOT_PRIORITY_SERIES_IDS: ReadonlyArray<readonly string[]> = [
  ["M001"],
  ["CA.DR007", "M002", "EMM00167613"],
  ["M003", "EMM00166458"],
  ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
  ["CA.US_GOV_10Y", "EMG00001310", "E1003238"],
  ["CA.CN_US_SPREAD", "EM1"],
] as const;

function pickSpotSeries(series: ChoiceMacroLatestPoint[]) {
  const candidates = series.filter((point) => (point.refresh_tier ?? "stable") !== "isolated");
  const selected: ChoiceMacroLatestPoint[] = [];
  const seen = new Set<string>();

  for (const seriesIds of DASHBOARD_SPOT_PRIORITY_SERIES_IDS) {
    const point = candidates.find((candidate) => seriesIds.includes(candidate.series_id));
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

function isIndexUnit(unit: string): boolean {
  const normalized = unit.trim().toLowerCase();
  if (!normalized) return false;
  return normalized.includes("index") || normalized.includes("point");
}

function defaultRatioPrecision(value: number): number {
  const abs = Math.abs(value);
  if (abs >= 1000) return 1;
  if (abs >= 10) return 2;
  return 3;
}

function normalizeDisplayUnit(point: ChoiceMacroLatestPoint): string {
  const normalized = point.unit?.trim();
  if (!normalized) return "";
  if (normalized.toLowerCase() === "unknown") return "";
  if (point.series_name.startsWith("中间价:")) return "";
  return normalized;
}

function formatMacroValue(point: ChoiceMacroLatestPoint): string {
  const value = point.value_numeric;
  const suffix = normalizeDisplayUnit(point);
  const unit = suffix.toLowerCase();
  if (!Number.isFinite(value)) {
    return "—";
  }
  if (point.series_id === "EMM00000015" && suffix === "亿元") {
    const converted = formatNumeric(
      formatRawAsNumeric({ raw: value / 10_000, unit: "ratio", sign_aware: false, precision: 2 }),
    );
    return `${converted} 万亿元`;
  }
  if (unit.includes("bp") && !unit.includes("bps")) {
    return formatNumeric(formatRawAsNumeric({ raw: value, unit: "bp", sign_aware: false }));
  }
  if (unit.includes("%")) {
    return formatNumeric(formatRawAsNumeric({ raw: value / 100, unit: "pct", sign_aware: false }));
  }

  const core = formatNumeric(
    formatRawAsNumeric({
      raw: value,
      unit: "ratio",
      sign_aware: false,
      precision: defaultRatioPrecision(value),
    }),
  );

  if (isIndexUnit(suffix)) {
    return suffix ? `${core} ${suffix}` : core;
  }

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
      eyebrow="市场上下文"
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
