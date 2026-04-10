import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
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
  const latestTradeDate = useMemo(() => {
    if (latestSeries.length === 0) {
      return "暂无";
    }
    return latestSeries
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [latestSeries]);
  const vendorVersions = useMemo(
    () => [...new Set(latestSeries.map((point) => point.vendor_version))],
    [latestSeries],
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
        <div data-testid="market-data-latest-count">
          <PlaceholderCard
            title="最新点位"
            value={String(latestSeries.length)}
            detail="当前最新切片中返回的 Choice 序列数量。"
          />
        </div>
        <div data-testid="market-data-latest-trade-date">
          <PlaceholderCard
            title="最新交易日"
            value={latestTradeDate}
            detail="按最新点位切片计算出的最大交易日期。"
            valueVariant="text"
          />
        </div>
        <PlaceholderCard
          title="供应商版本"
          value={vendorVersions.join(", ") || "暂无"}
          detail="用于当前市场数据视图的 vendor_version。"
          valueVariant="text"
        />
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
            <div>generated_at: {meta?.generated_at ?? "pending"}</div>
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
            宏观视图与数据源规则预览均为只读分析增强面。如需追规则命中与批次 lineage，请从中台配置入口进入 source preview。
          </div>
        </section>
      </div>

      <div style={{ marginTop: 18 }}>
        <AsyncSection
          title="最新 Choice 点位"
          isLoading={latestQuery.isLoading}
          isError={latestQuery.isError}
          isEmpty={!latestQuery.isLoading && !latestQuery.isError && latestSeries.length === 0}
          onRetry={() => void latestQuery.refetch()}
        >
          <div style={{ display: "grid", gap: 12 }}>
            {latestSeries.map((point) => (
              <div
                key={point.series_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(0, 1.6fr) repeat(3, minmax(0, 0.8fr))",
                  gap: 12,
                  alignItems: "center",
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{point.series_name}</div>
                  <div style={{ color: "#8090a8", fontSize: 12 }}>{point.series_id}</div>
                </div>
                <div>{point.trade_date}</div>
                <div style={{ fontWeight: 600, color: "#162033" }}>
                  {formatPointValue(point.value_numeric, point.unit)}
                </div>
                <div style={{ color: "#5c6b82", fontSize: 12 }}>
                  {point.vendor_version}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>
      </div>
    </section>
  );
}
