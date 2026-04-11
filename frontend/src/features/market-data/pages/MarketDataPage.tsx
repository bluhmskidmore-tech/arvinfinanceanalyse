import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../api/contracts";
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

function formatPointValue(value: number, unit: string) {
  return `${value.toFixed(2)}${unit ? ` ${unit}` : ""}`;
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

function seriesRecentPoints(point: ChoiceMacroLatestPoint) {
  return point.recent_points ?? [];
}

function seriesRefreshTier(point: ChoiceMacroLatestPoint) {
  return point.refresh_tier ?? "stable";
}

function seriesPolicyNote(point: ChoiceMacroLatestPoint) {
  return point.policy_note?.trim() || "analytical read path";
}

function seriesFetchModeLabel(point: ChoiceMacroLatestPoint) {
  const fetchMode = point.fetch_mode ?? "date_slice";
  const granularity = point.fetch_granularity ?? "batch";
  return `${fetchMode} / ${granularity}`;
}

function renderSeriesCards(series: ChoiceMacroLatestPoint[]) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {series.map((point) => (
        <div
          key={point.series_id}
          data-testid={`market-data-series-${point.series_id}`}
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
              <div style={{ color: "#8090a8", fontSize: 12 }}>
                {point.series_id}
              </div>
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
              <span>·</span>
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
            source {point.source_version} · vendor {point.vendor_version}
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

  const catalog = useMemo(() => catalogQuery.data?.result.series ?? [], [catalogQuery.data?.result.series]);
  const latestSeries = useMemo(
    () => latestQuery.data?.result.series ?? [],
    [latestQuery.data?.result.series],
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
  const stableLatestTradeDate = useMemo(() => {
    if (stableSeries.length === 0) {
      return "暂无";
    }
    return stableSeries
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [stableSeries]);
  const vendorVersions = useMemo(
    () => [...new Set(visibleLatestSeries.map((point) => point.vendor_version))],
    [visibleLatestSeries],
  );
  const meta = latestQuery.data?.result_meta ?? catalogQuery.data?.result_meta;

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
            读取 DuckDB 物化后的宏观目录与最新 Choice 点位，仅作为分析增强视图使用，不在前端拼接正式金融口径。
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
            title="稳定可用"
            value={String(stableSeries.length)}
            detail="主 refresh 稳定链路中的序列数量。"
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
                  {series.series_id} · {series.vendor_name} · {series.frequency} · {series.unit}
                </div>
                <div style={{ color: "#8090a8", fontSize: 12 }}>
                  vendor_version {series.vendor_version}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <section
          data-testid="market-data-result-meta"
          style={{
            padding: 24,
            borderRadius: 20,
            background: "#fbfcfe",
            border: "1px solid #e4ebf5",
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
          }}
        >
          <h2
            style={{
              marginTop: 0,
              marginBottom: 12,
              fontSize: 18,
              fontWeight: 600,
            }}
          >
            Result metadata
          </h2>
          <div style={{ display: "grid", gap: 8, color: "#5c6b82", fontSize: 14 }}>
            <div>trace_id: {meta?.trace_id ?? "pending"}</div>
            <div>basis: {meta?.basis ?? "pending"}</div>
            <div>result_kind: {meta?.result_kind ?? "pending"}</div>
            <div>source_version: {meta?.source_version ?? "pending"}</div>
            <div>vendor_version: {meta?.vendor_version ?? "pending"}</div>
            <div>rule_version: {meta?.rule_version ?? "pending"}</div>
            <div>quality_flag: {meta?.quality_flag ?? "pending"}</div>
            <div>generated_at: {meta?.generated_at ?? "pending"}</div>
            <div>visible_vendor_versions: {vendorVersions.join(", ") || "暂无"}</div>
          </div>
          <div
            style={{
              marginTop: 16,
              padding: 14,
              borderRadius: 16,
              background: "#ffffff",
              border: "1px solid #e4ebf5",
              color: "#5c6b82",
              fontSize: 13,
              lineHeight: 1.7,
            }}
          >
            宏观视图仅用于分析增强和外部数据观察，不承载 formal finance 口径；待供应商确认的 isolated 序列不会进入当前读面。
          </div>
        </section>
      </div>
    </section>
  );
}
