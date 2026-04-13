import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  ChoiceMacroLatestPoint,
  ChoiceMacroRecentPoint,
  FxAnalyticalSeriesPoint,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  ResultMeta,
} from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const sectionGridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.3fr) minmax(320px, 1fr)",
  gap: 18,
  marginTop: 18,
} as const;

const detailPanelStyle = {
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
} as const;

const blockTitleStyle = {
  margin: "24px 0 0",
  fontSize: 16,
  fontWeight: 600,
  color: "#162033",
} as const;

const macroChartShellStyle = {
  ...detailPanelStyle,
  marginTop: 18,
} as const;

const placeholderBlockStyle = {
  marginTop: 12,
  padding: 20,
  borderRadius: 16,
  border: "1px dashed #c5d0e0",
  background: "#ffffff",
  color: "#8090a8",
  fontSize: 14,
  lineHeight: 1.65,
} as const;

/** 利率走势：国债 10Y / 国开 5Y / SHIBOR 隔夜（Choice series_id） */
const RATE_TREND_DEFINITIONS = [
  { series_id: "EMM00166466", name: "国债 10Y" },
  { series_id: "EMM00166462", name: "国开 5Y" },
  { series_id: "EMM00166252", name: "SHIBOR 隔夜" },
] as const;

type MarketObservationPoint = ChoiceMacroLatestPoint | FxAnalyticalSeriesPoint;
type SpreadTenorSlot = "3Y" | "5Y" | "10Y";

const SPREAD_TENOR_SLOTS: SpreadTenorSlot[] = ["3Y", "5Y", "10Y"];
const TARGET_FAMILY_LABELS: Record<string, string> = {
  treasury: "国债收益率",
  cdb: "国开收益率",
  aaa_credit: "AAA 信用收益率",
  credit_spread: "信用利差",
};

function recentTimelineForMacroPoint(point: ChoiceMacroLatestPoint | undefined) {
  const map = new Map<string, number>();
  if (!point) {
    return map;
  }
  for (const rp of point.recent_points ?? []) {
    map.set(rp.trade_date, rp.value_numeric);
  }
  return map;
}

function buildRateTrendChartOption(series: ChoiceMacroLatestPoint[]): EChartsOption | null {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const dateSet = new Set<string>();
  const maps = RATE_TREND_DEFINITIONS.map((def) => {
    const timeline = recentTimelineForMacroPoint(byId.get(def.series_id));
    for (const d of timeline.keys()) {
      dateSet.add(d);
    }
    return timeline;
  });
  if (dateSet.size === 0) {
    return null;
  }
  let unit = "";
  for (const def of RATE_TREND_DEFINITIONS) {
    const p = byId.get(def.series_id);
    if (p?.unit) {
      unit = p.unit;
      break;
    }
  }
  const categories = [...dateSet].sort((a, b) => a.localeCompare(b));
  const lineSeries = RATE_TREND_DEFINITIONS.map((def, i) => ({
    name: def.name,
    type: "line" as const,
    smooth: true,
    showSymbol: categories.length <= 36,
    connectNulls: true,
    data: categories.map((d) => maps[i].get(d) ?? null),
  }));
  return {
    color: ["#1f5eff", "#2f8f63", "#e67e22"],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 52, right: 20, top: 28, bottom: 52 },
    xAxis: { type: "category", boundaryGap: false, data: categories },
    yAxis: {
      type: "value",
      scale: true,
      name: unit || undefined,
      axisLabel: { formatter: "{value}" },
    },
    series: lineSeries,
  };
}

function formatPointValue(value: number, unit: string) {
  return `${value.toFixed(2)}${unit ? ` ${unit}` : ""}`;
}

function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue =
    typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

function formatDelta(value: number | null | undefined, unit: string) {
  if (value == null) {
    return "n/a";
  }
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}${unit ? ` ${unit}` : ""}`;
}

function formatRecentPoint(point: ChoiceMacroRecentPoint) {
  return `${point.trade_date} ${formatPointValue(point.value_numeric, "")}`;
}

function seriesRecentPoints(point: MarketObservationPoint) {
  return point.recent_points ?? [];
}

function seriesRefreshTier(point: MarketObservationPoint) {
  return point.refresh_tier ?? "stable";
}

function seriesPolicyNote(point: MarketObservationPoint) {
  return point.policy_note?.trim() || "analytical read path";
}

function seriesFetchModeLabel(point: MarketObservationPoint) {
  const fetchMode = point.fetch_mode ?? "date_slice";
  const granularity = point.fetch_granularity ?? "batch";
  return `${fetchMode} / ${granularity}`;
}

function correlationStrength(point: MacroBondLinkageTopCorrelation) {
  return Math.max(
    Math.abs(point.correlation_1y ?? 0),
    Math.abs(point.correlation_6m ?? 0),
    Math.abs(point.correlation_3m ?? 0),
  );
}

function familyLabel(targetFamily: string) {
  return TARGET_FAMILY_LABELS[targetFamily] ?? targetFamily;
}

function formatCorrelation(value: number | null | undefined) {
  if (value == null) {
    return "不可用";
  }
  return value.toFixed(2);
}

function renderCorrelationCard(point: MacroBondLinkageTopCorrelation) {
  return (
    <div
      key={`${point.series_id}:${point.target_family}:${point.target_tenor ?? "none"}`}
      style={{
        display: "grid",
        gap: 10,
        padding: 16,
        borderRadius: 16,
        border: "1px solid #e4ebf5",
        background: "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          alignItems: "flex-start",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: "#162033" }}>{point.series_name}</div>
          <div style={{ color: "#8090a8", fontSize: 12 }}>{point.series_id}</div>
        </div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 10px",
            borderRadius: 999,
            background:
              point.direction === "positive"
                ? "#edf8f2"
                : point.direction === "negative"
                  ? "#fff3ee"
                  : "#f3f6fb",
            color:
              point.direction === "positive"
                ? "#2f8f63"
                : point.direction === "negative"
                  ? "#b85b2b"
                  : "#31425b",
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {point.direction}
        </div>
      </div>

      <div style={{ color: "#31425b", fontSize: 13, lineHeight: 1.65 }}>
        目标维度：{familyLabel(point.target_family)}
        {point.target_tenor ? ` / ${point.target_tenor}` : " / tenor unavailable"}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
          gap: 12,
        }}
      >
        <div>
          <div style={{ color: "#8090a8", fontSize: 12 }}>corr 3M</div>
          <div>{formatCorrelation(point.correlation_3m)}</div>
        </div>
        <div>
          <div style={{ color: "#8090a8", fontSize: 12 }}>corr 6M</div>
          <div>{formatCorrelation(point.correlation_6m)}</div>
        </div>
        <div>
          <div style={{ color: "#8090a8", fontSize: 12 }}>corr 1Y</div>
          <div>{formatCorrelation(point.correlation_1y)}</div>
        </div>
        <div>
          <div style={{ color: "#8090a8", fontSize: 12 }}>lead / lag</div>
          <div>{`${point.lead_lag_days} 天`}</div>
        </div>
      </div>
    </div>
  );
}

function catalogRefreshTier(series: { refresh_tier?: "stable" | "fallback" | "isolated" | null }) {
  return series.refresh_tier ?? "stable";
}

function renderSeriesCards(
  series: MarketObservationPoint[],
  options?: { testIdPrefix?: string },
) {
  const testIdPrefix = options?.testIdPrefix ?? "market-data-series";

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {series.map((point) => (
        <div
          key={point.series_id}
          data-testid={`${testIdPrefix}-${point.series_id}`}
          style={{
            display: "grid",
            gap: 10,
            padding: 16,
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div>
              <div style={{ fontWeight: 600 }}>{point.series_name}</div>
              <div style={{ color: "#8090a8", fontSize: 12 }}>{point.series_id}</div>
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 10px",
                borderRadius: 999,
                background: "#f3f6fb",
                color: "#31425b",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              <span>{`tier ${seriesRefreshTier(point)}`}</span>
              <span>路</span>
              <span>{point.quality_flag ?? "warning"}</span>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 12,
            }}
          >
            <div>
              <div style={{ color: "#8090a8", fontSize: 12 }}>trade_date</div>
              <div>{point.trade_date}</div>
            </div>
            <div>
              <div style={{ color: "#8090a8", fontSize: 12 }}>latest</div>
              <div style={{ fontWeight: 600, color: "#162033" }}>
                {formatPointValue(point.value_numeric, point.unit)}
              </div>
            </div>
            <div>
              <div style={{ color: "#8090a8", fontSize: 12 }}>delta</div>
              <div>{formatDelta(point.latest_change, point.unit)}</div>
            </div>
            <div>
              <div style={{ color: "#8090a8", fontSize: 12 }}>fetch</div>
              <div>{seriesFetchModeLabel(point)}</div>
            </div>
          </div>

          <div style={{ color: "#5c6b82", fontSize: 12, lineHeight: 1.7 }}>
            source {point.source_version} 路 vendor {point.vendor_version}
          </div>
          <div style={{ color: "#31425b", fontSize: 13, lineHeight: 1.7 }}>
            {seriesPolicyNote(point)}
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {seriesRecentPoints(point).map((recentPoint) => (
              <span
                key={`${point.series_id}:${recentPoint.trade_date}:${recentPoint.vendor_version}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "6px 10px",
                  borderRadius: 999,
                  background: "#f8fafc",
                  border: "1px solid #e4ebf5",
                  color: "#5c6b82",
                  fontSize: 12,
                }}
              >
                {formatRecentPoint(recentPoint)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MetadataPanel({
  title,
  meta,
  extraLine,
  testId,
}: {
  title: string;
  meta: ResultMeta | undefined;
  extraLine?: string;
  testId: string;
}) {
  return (
    <section data-testid={testId} style={detailPanelStyle}>
      <h2
        style={{
          marginTop: 0,
          marginBottom: 12,
          fontSize: 18,
          fontWeight: 600,
        }}
      >
        {title}
      </h2>
      <div style={{ display: "grid", gap: 8, color: "#5c6b82", fontSize: 14 }}>
        <div>trace_id: {meta?.trace_id ?? "pending"}</div>
        <div>basis: {meta?.basis ?? "pending"}</div>
        <div>formal_use_allowed: {meta ? String(meta.formal_use_allowed) : "pending"}</div>
        <div>result_kind: {meta?.result_kind ?? "pending"}</div>
        <div>source_version: {meta?.source_version ?? "pending"}</div>
        <div>vendor_version: {meta?.vendor_version ?? "pending"}</div>
        <div>rule_version: {meta?.rule_version ?? "pending"}</div>
        <div>quality_flag: {meta?.quality_flag ?? "pending"}</div>
        <div>generated_at: {meta?.generated_at ?? "pending"}</div>
        {extraLine ? <div>{extraLine}</div> : null}
      </div>
    </section>
  );
}

export default function MarketDataPage() {
  const client = useApiClient();
  const catalogQuery = useQuery({
    queryKey: ["market-data", "macro-foundation", client.mode],
    queryFn: () => client.getMacroFoundation(),
    retry: false,
  });
  const latestQuery = useQuery({
    queryKey: ["market-data", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const fxAnalyticalQuery = useQuery({
    queryKey: ["market-data", "fx-analytical", client.mode],
    queryFn: () => client.getFxAnalytical(),
    retry: false,
  });

  const catalog = useMemo(
    () => catalogQuery.data?.result.series ?? [],
    [catalogQuery.data?.result.series],
  );
  const latestSeries = useMemo(
    () => latestQuery.data?.result.series ?? [],
    [latestQuery.data?.result.series],
  );
  const fxAnalyticalGroups = useMemo(
    () => fxAnalyticalQuery.data?.result.groups ?? [],
    [fxAnalyticalQuery.data?.result.groups],
  );
  const visibleLatestSeries = useMemo(
    () => latestSeries.filter((point) => seriesRefreshTier(point) !== "isolated"),
    [latestSeries],
  );
  const stableSeries = useMemo(
    () => visibleLatestSeries.filter((point) => seriesRefreshTier(point) !== "fallback"),
    [visibleLatestSeries],
  );
  const fallbackSeries = useMemo(
    () => visibleLatestSeries.filter((point) => seriesRefreshTier(point) === "fallback"),
    [visibleLatestSeries],
  );
  const stableCatalogSeries = useMemo(
    () => catalog.filter((series) => catalogRefreshTier(series) === "stable"),
    [catalog],
  );
  const missingStableSeries = useMemo(() => {
    const visibleStableIds = new Set(stableSeries.map((point) => point.series_id));
    return stableCatalogSeries.filter((series) => !visibleStableIds.has(series.series_id));
  }, [stableCatalogSeries, stableSeries]);
  const stableLatestTradeDate = useMemo(() => {
    if (stableSeries.length === 0) {
      return "暂无";
    }
    return stableSeries
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [stableSeries]);
  const linkageReportDate = useMemo(() => {
    if (visibleLatestSeries.length === 0) {
      return "";
    }
    return visibleLatestSeries
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [visibleLatestSeries]);
  const macroBondLinkageQuery = useQuery({
    queryKey: ["market-data", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });
  const vendorVersions = useMemo(
    () => [...new Set(visibleLatestSeries.map((point) => point.vendor_version))],
    [visibleLatestSeries],
  );
  const fxAnalyticalSeriesCount = useMemo(
    () => fxAnalyticalGroups.reduce((total, group) => total + group.series.length, 0),
    [fxAnalyticalGroups],
  );
  const rateTrendChartOption = useMemo(
    () => buildRateTrendChartOption(latestSeries),
    [latestSeries],
  );
  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const macroBondLinkageMeta = macroBondLinkageQuery.data?.result_meta;
  const macroBondLinkageWarnings = macroBondLinkage.warnings ?? [];
  const hasPortfolioImpact =
    Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const spreadSlots = useMemo(
    () =>
      SPREAD_TENOR_SLOTS.map((tenor) => ({
        tenor,
        point:
          (macroBondLinkage.top_correlations ?? [])
            .filter(
              (item) =>
                item.target_family === "credit_spread" &&
                item.target_tenor === tenor,
            )
            .sort((left, right) => correlationStrength(right) - correlationStrength(left))[0] ?? null,
      })),
    [macroBondLinkage.top_correlations],
  );
  const nonSpreadTopCorrelations = useMemo(
    () =>
      (macroBondLinkage.top_correlations ?? []).filter(
        (item) => item.target_family !== "credit_spread",
      ),
    [macroBondLinkage.top_correlations],
  );
  const macroMeta = latestQuery.data?.result_meta ?? catalogQuery.data?.result_meta;
  const fxAnalyticalMeta = fxAnalyticalQuery.data?.result_meta;

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            市场数据工作台
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 840,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            页面同时展示宏观观察与 analytical FX 观察，但 formal FX 中间价状态仍保持为单独的后端治理读面，
            不在浏览器侧推导、不混入 macro latest sections。
          </p>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实 DuckDB 读路径" : "本地演示数据"}
        </span>
      </div>

      <div style={summaryGridStyle}>
        <div data-testid="market-data-catalog-count">
          <PlaceholderCard
            title="宏观序列目录"
            value={String(catalog.length)}
            detail="已登记的宏观序列数量。"
          />
        </div>
        <div data-testid="market-data-stable-count">
          <PlaceholderCard
            title="稳定回收"
            value={`${stableSeries.length} / ${stableCatalogSeries.length}`}
            detail="稳定主链路已回收 / 目录应有数量。"
          />
        </div>
        <div data-testid="market-data-fallback-count">
          <PlaceholderCard
            title="降级可用"
            value={String(fallbackSeries.length)}
            detail="latest-only / single-fetch 降级链路中的序列数量。"
          />
        </div>
        <div data-testid="market-data-stable-trade-date">
          <PlaceholderCard
            title="稳定最新日"
            value={stableLatestTradeDate}
            detail="稳定主链路中可见序列的最大交易日期。"
            valueVariant="text"
          />
        </div>
        <div data-testid="market-data-missing-stable-count">
          <PlaceholderCard
            title="稳定缺口"
            value={String(missingStableSeries.length)}
            detail="目录中属于 stable 但当前尚未回收的序列数量。"
          />
        </div>
        <div data-testid="market-data-fx-analytical-group-count">
          <PlaceholderCard
            title="FX analytical groups"
            value={String(fxAnalyticalGroups.length)}
            detail="后端返回的 analytical FX 分组数量。"
          />
        </div>
        <div data-testid="market-data-fx-analytical-series-count">
          <PlaceholderCard
            title="FX analytical series"
            value={String(fxAnalyticalSeriesCount)}
            detail="Analytical FX 观察值与 formal FX 状态保持分离。"
          />
        </div>
      </div>

      <div data-testid="market-data-macro-charts" style={macroChartShellStyle}>
        <h2 style={{ ...blockTitleStyle, marginTop: 0 }}>利率走势图</h2>
        <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14, lineHeight: 1.65 }}>
          国债 10Y（{RATE_TREND_DEFINITIONS[0].series_id}）、国开 5Y（{RATE_TREND_DEFINITIONS[1].series_id}）、
          SHIBOR 隔夜（{RATE_TREND_DEFINITIONS[2].series_id}），数据来自各序列的 recent_points。
        </p>
        {latestQuery.isLoading ? (
          <div
            style={{
              marginTop: 16,
              padding: 24,
              color: "#5c6b82",
              fontSize: 14,
            }}
          >
            加载宏观序列中…
          </div>
        ) : rateTrendChartOption ? (
          <div data-testid="market-data-rate-trend-chart" style={{ marginTop: 16 }}>
            <ReactECharts option={rateTrendChartOption} style={{ height: 360, width: "100%" }} />
          </div>
        ) : (
          <div
            data-testid="market-data-rate-trend-empty"
            style={{
              marginTop: 16,
              padding: 20,
              borderRadius: 16,
              border: "1px solid #e4ebf5",
              background: "#ffffff",
              color: "#8090a8",
              fontSize: 14,
            }}
          >
            当前响应中缺少上述利率序列的近期点位，无法绘制走势图。
          </div>
        )}

        <h2 style={blockTitleStyle}>汇率与流动性</h2>
        <div style={placeholderBlockStyle}>该板块图表待接入（宏观汇率、资金利率等）。</div>

        <h2 style={blockTitleStyle}>增长与物价</h2>
        <div style={{ ...placeholderBlockStyle, marginBottom: 0 }}>
          该板块图表待接入（PMI、PPI、CPI 等）。
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <AsyncSection
          title="可用 Choice 点位"
          isLoading={latestQuery.isLoading}
          isError={latestQuery.isError}
          isEmpty={!latestQuery.isLoading && !latestQuery.isError && visibleLatestSeries.length === 0}
          onRetry={() => void latestQuery.refetch()}
        >
          <div style={{ display: "grid", gap: 24 }}>
            <section data-testid="market-data-stable-section">
              <div style={{ marginBottom: 12 }}>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>稳定主链路</h2>
                <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
                  面向日常分析的主 refresh 读面，只显示稳定可取的序列。
                </p>
              </div>
              {renderSeriesCards(stableSeries)}
            </section>

            <section data-testid="market-data-missing-stable-section">
              <div style={{ marginBottom: 12 }}>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>待补齐 stable</h2>
                <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
                  目录中归属 stable，但当前 refresh 尚未回收的序列。
                </p>
              </div>
              {missingStableSeries.length > 0 ? (
                <div style={{ display: "grid", gap: 12 }}>
                  {missingStableSeries.map((series) => (
                    <div
                      key={series.series_id}
                      style={{
                        display: "grid",
                        gap: 6,
                        padding: 14,
                        borderRadius: 16,
                        border: "1px solid #e4ebf5",
                        background: "#ffffff",
                      }}
                    >
                      <strong>{series.series_name}</strong>
                      <div style={{ color: "#5c6b82", fontSize: 13 }}>
                        {series.series_id} 路 {catalogRefreshTier(series)} 路 {series.fetch_mode ?? "date_slice"} /{" "}
                        {series.fetch_granularity ?? "batch"}
                      </div>
                      <div style={{ color: "#31425b", fontSize: 13 }}>
                        {series.policy_note ?? "main refresh date-slice lane"}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    border: "1px solid #e4ebf5",
                    background: "#ffffff",
                    color: "#5c6b82",
                    fontSize: 14,
                  }}
                >
                  当前 stable 目录已全部回收。
                </div>
              )}
            </section>

            <section data-testid="market-data-fallback-section">
              <div style={{ marginBottom: 12 }}>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>降级 latest-only</h2>
                <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
                  低频或稀疏序列保留为降级链路展示，不混入稳定主链路。
                </p>
              </div>
              {fallbackSeries.length > 0 ? (
                renderSeriesCards(fallbackSeries)
              ) : (
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    border: "1px solid #e4ebf5",
                    background: "#ffffff",
                    color: "#5c6b82",
                    fontSize: 14,
                  }}
                >
                  当前无降级 latest-only 序列。
                </div>
              )}
            </section>
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 18 }}>
        <AsyncSection
          title="FX analytical observations"
          isLoading={fxAnalyticalQuery.isLoading}
          isError={fxAnalyticalQuery.isError}
          isEmpty={
            !fxAnalyticalQuery.isLoading &&
            !fxAnalyticalQuery.isError &&
            fxAnalyticalGroups.length === 0
          }
          onRetry={() => void fxAnalyticalQuery.refetch()}
        >
          <div style={{ display: "grid", gap: 24 }}>
            {fxAnalyticalGroups.map((group) => (
              <section
                key={group.group_key}
                data-testid={`market-data-fx-group-${group.group_key}`}
              >
                <div style={{ marginBottom: 12 }}>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{group.title}</h2>
                  <p
                    style={{
                      marginTop: 8,
                      marginBottom: 0,
                      color: "#5c6b82",
                      fontSize: 14,
                      lineHeight: 1.7,
                    }}
                  >
                    {group.description}
                  </p>
                </div>
                {renderSeriesCards(group.series, {
                  testIdPrefix: `market-data-fx-series-${group.group_key}`,
                })}
              </section>
            ))}
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 18 }}>
        <AsyncSection
          title="宏观-债市联动"
          isLoading={macroBondLinkageQuery.isLoading}
          isError={macroBondLinkageQuery.isError}
          isEmpty={
            !macroBondLinkageQuery.isLoading &&
            !macroBondLinkageQuery.isError &&
            (macroBondLinkage.top_correlations?.length ?? 0) === 0 &&
            macroBondLinkageWarnings.length === 0
          }
          onRetry={() => void macroBondLinkageQuery.refetch()}
        >
          <div style={{ display: "grid", gap: 18 }}>
            <section
              data-testid="market-data-linkage-caveat"
              style={{
                padding: 18,
                borderRadius: 18,
                border: "1px solid #d7e3f3",
                background:
                  "linear-gradient(180deg, rgba(250,252,255,1) 0%, rgba(241,246,252,1) 100%)",
                display: "grid",
                gap: 10,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "5px 10px",
                    borderRadius: 999,
                    background: "#edf3ff",
                    color: "#1f5eff",
                    fontSize: 12,
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  analytical
                </span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "5px 10px",
                    borderRadius: 999,
                    background: "#fff2e9",
                    color: "#b85b2b",
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  non-formal
                </span>
              </div>
              <div style={{ color: "#31425b", fontSize: 14, lineHeight: 1.7 }}>
                本区为宏观联动分析口径。组合影响仅用于研究和配置讨论，属于分析估算，不代表账本口径下的损益（PnL）、
                不代表正式估值归因，也不替代 bond analytics 的正式读面。
              </div>
              {macroBondLinkageWarnings.length > 0 ? (
                <ul
                  data-testid="market-data-linkage-warning-list"
                  style={{
                    margin: 0,
                    paddingLeft: 20,
                    color: "#5c6b82",
                    fontSize: 13,
                    lineHeight: 1.8,
                  }}
                >
                  {macroBondLinkageWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <div
                  style={{ color: "#5c6b82", fontSize: 13 }}
                  data-testid="market-data-linkage-warning-empty"
                >
                  当前无额外方法警示。
                </div>
              )}
            </section>

            <div style={summaryGridStyle}>
              <div data-testid="market-data-linkage-composite-score">
                <PlaceholderCard
                  title="综合评分"
                  value={
                    macroBondLinkage.environment_score?.composite_score != null
                      ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                      : "不可用"
                  }
                  detail={macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分数据。"}
                  valueVariant="text"
                />
              </div>
              <div data-testid="market-data-linkage-rate-direction">
                <PlaceholderCard
                  title="利率方向"
                  value={macroBondLinkage.environment_score?.rate_direction ?? "不可用"}
                  detail={
                    macroBondLinkage.environment_score?.rate_direction_score != null
                      ? `direction score ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                      : "缺少方向评分。"
                  }
                  valueVariant="text"
                />
              </div>
              <div data-testid="market-data-linkage-liquidity-score">
                <PlaceholderCard
                  title="流动性评分"
                  value={
                    macroBondLinkage.environment_score?.liquidity_score != null
                      ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                      : "不可用"
                  }
                  detail="正值偏松，负值偏紧。"
                  valueVariant="text"
                />
              </div>
              <div data-testid="market-data-linkage-growth-score">
                <PlaceholderCard
                  title="增长评分"
                  value={
                    macroBondLinkage.environment_score?.growth_score != null
                      ? macroBondLinkage.environment_score.growth_score.toFixed(2)
                      : "不可用"
                  }
                  detail="宏观增长方向的简化分值。"
                  valueVariant="text"
                />
              </div>
            </div>

            <section
              data-testid="market-data-linkage-portfolio-impact"
              style={detailPanelStyle}
            >
              <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18, fontWeight: 600 }}>
                组合影响估算
              </h2>
              <p style={{ marginTop: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                以下数值为 analytical estimate，基于宏观环境评分与组合在利率、利差维度上的敏感度静态映射，不代表正式损益。
              </p>
              {hasPortfolioImpact ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>rate change</div>
                    <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}</div>
                  </div>
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>spread widening</div>
                    <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}</div>
                  </div>
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>rate impact</div>
                    <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_pnl_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>spread impact</div>
                    <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_pnl_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>total estimate</div>
                    <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: "#8090a8", fontSize: 12 }}>impact ratio</div>
                    <div>{macroBondLinkage.portfolio_impact?.impact_ratio_to_market_value ?? "不可用"}</div>
                  </div>
                </div>
              ) : (
                <div
                  data-testid="market-data-linkage-portfolio-impact-unavailable"
                  style={{
                    padding: 16,
                    borderRadius: 14,
                    border: "1px dashed #d7dfea",
                    background: "#ffffff",
                    color: "#8090a8",
                    fontSize: 14,
                  }}
                >
                  当前报告日未返回组合影响估算，状态按 unavailable 处理，不在前端补零。
                </div>
              )}
            </section>

            <section data-testid="market-data-linkage-spread-tenors" style={detailPanelStyle}>
              <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18, fontWeight: 600 }}>
                信用利差显式维度
              </h2>
              <p style={{ marginTop: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                仅按结构化字段 `target_family / target_tenor` 渲染，不从 label 或 target_yield 反推 tenor。
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: 12,
                }}
              >
                {spreadSlots.map(({ tenor, point }) => (
                  <div
                    key={tenor}
                    data-testid={`market-data-linkage-spread-slot-${tenor}`}
                    style={{
                      padding: 16,
                      borderRadius: 16,
                      border: "1px solid #e4ebf5",
                      background: "#ffffff",
                      display: "grid",
                      gap: 8,
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "#162033" }}>{`credit_spread_${tenor}`}</div>
                    {point ? (
                      <>
                        <div style={{ color: "#5c6b82", fontSize: 13 }}>{point.series_name}</div>
                        <div>{`corr 1Y ${formatCorrelation(point.correlation_1y)}`}</div>
                        <div>{`lead / lag ${point.lead_lag_days} 天`}</div>
                      </>
                    ) : (
                      <div style={{ color: "#8090a8", fontSize: 13, lineHeight: 1.7 }}>
                        unavailable：当前 payload 未返回该 tenor 的结构化相关性，不在前端推断。
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section data-testid="market-data-linkage-top-correlations" style={detailPanelStyle}>
              <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18, fontWeight: 600 }}>
                相关性 Top 10
              </h2>
              {(nonSpreadTopCorrelations.length > 0 ||
                spreadSlots.some((slot) => slot.point !== null)) ? (
                <div style={{ display: "grid", gap: 12 }}>
                  {(macroBondLinkage.top_correlations ?? []).map((point) =>
                    renderCorrelationCard(point),
                  )}
                </div>
              ) : (
                <div
                  style={{
                    padding: 16,
                    borderRadius: 14,
                    border: "1px dashed #d7dfea",
                    background: "#ffffff",
                    color: "#8090a8",
                    fontSize: 14,
                  }}
                >
                  当前无可展示的结构化相关性结果。
                </div>
              )}
            </section>
          </div>
        </AsyncSection>
      </div>

      <div style={sectionGridStyle}>
        <AsyncSection
          title="宏观序列目录"
          isLoading={catalogQuery.isLoading}
          isError={catalogQuery.isError}
          isEmpty={!catalogQuery.isLoading && !catalogQuery.isError && catalog.length === 0}
          onRetry={() => void catalogQuery.refetch()}
        >
          <div style={{ display: "grid", gap: 12 }}>
            {catalog.map((series) => (
              <div
                key={series.series_id}
                style={{
                  display: "grid",
                  gap: 6,
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <strong>{series.series_name}</strong>
                <div style={{ color: "#5c6b82", fontSize: 13 }}>
                  {series.series_id} 路 {series.vendor_name} 路 {series.frequency} 路 {series.unit}
                </div>
                <div style={{ color: "#8090a8", fontSize: 12 }}>
                  vendor_version {series.vendor_version}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <MetadataPanel
          title="Result metadata"
          meta={macroMeta}
          extraLine={`visible_vendor_versions: ${vendorVersions.join(", ") || "暂无"}`}
          testId="market-data-result-meta"
        />

        <MetadataPanel
          title="FX analytical metadata"
          meta={fxAnalyticalMeta}
          testId="market-data-fx-analytical-meta"
        />

        <MetadataPanel
          title="Macro linkage metadata"
          meta={macroBondLinkageMeta}
          extraLine={`report_date: ${linkageReportDate || "pending"}`}
          testId="market-data-linkage-meta"
        />
      </div>
    </section>
  );
}
