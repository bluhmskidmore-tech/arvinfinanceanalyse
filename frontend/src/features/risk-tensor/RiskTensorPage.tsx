import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

/** 默认报告日；可通过 URL `?report_date=YYYY-MM-DD` 覆盖。 */
const DEFAULT_REPORT_DATE = "2025-12-31";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

function displayStr(value: string | undefined) {
  if (value === undefined || value === "") {
    return "—";
  }
  return value;
}

/** 仅用于 ECharts 轴值解析，不做组合层面的金融重算。 */
function chartMagnitude(value: string) {
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export default function RiskTensorPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const reportDate = useMemo(() => {
    const fromUrl = searchParams.get("report_date")?.trim();
    return fromUrl || DEFAULT_REPORT_DATE;
  }, [searchParams]);

  const tensorQuery = useQuery({
    queryKey: ["risk-tensor", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
    retry: false,
  });

  const envelope = tensorQuery.data;
  const result = envelope?.result;
  const isEmpty =
    !tensorQuery.isLoading &&
    !tensorQuery.isError &&
    result !== undefined &&
    result.bond_count === 0;

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const labels = ["1Y", "3Y", "5Y", "7Y", "10Y", "30Y"];
    const keys = [
      "krd_1y",
      "krd_3y",
      "krd_5y",
      "krd_7y",
      "krd_10y",
      "krd_30y",
    ] as const;
    const data = keys.map((k) => chartMagnitude(result[k]));
    return {
      grid: { left: 52, right: 16, top: 36, bottom: 28 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#5c6b82" },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#5c6b82" },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      series: [
        {
          type: "bar",
          data,
          itemStyle: { color: "#1f5eff", borderRadius: [6, 6, 0, 0] },
        },
      ],
    };
  }, [result]);

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          风险张量
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          消费正式风险张量接口；展示口径以后端{" "}
          <code style={{ fontSize: 13 }}>/api/risk/tensor</code> 为准。
        </p>
      </div>

      <div style={controlBarStyle}>
        <div
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#ffffff",
            color: "#162033",
            fontSize: 14,
          }}
        >
          报告日：<strong>{reportDate}</strong>
          <span style={{ marginLeft: 8, color: "#8090a8", fontSize: 13 }}>
            （<code style={{ fontSize: 12 }}>?report_date=YYYY-MM-DD</code>）
          </span>
        </div>
      </div>

      <AsyncSection
        title="组合风险张量"
        isLoading={tensorQuery.isLoading}
        isError={tensorQuery.isError}
        isEmpty={isEmpty}
        onRetry={() => void tensorQuery.refetch()}
      >
        {result && (
          <>
            <div data-testid="risk-tensor-kpi-grid" style={summaryGridStyle}>
              <PlaceholderCard
                title="组合 DV01"
                value={displayStr(result.portfolio_dv01)}
                detail="portfolio_dv01，后端字符串口径。"
              />
              <PlaceholderCard
                title="CS01"
                value={displayStr(result.cs01)}
                detail="cs01（信用 spread DV01 聚合）。"
              />
              <PlaceholderCard
                title="组合凸性"
                value={displayStr(result.portfolio_convexity)}
                detail="portfolio_convexity。"
              />
              <PlaceholderCard
                title="债券只数"
                value={String(result.bond_count)}
                detail="bond_count。"
              />
              <PlaceholderCard
                title="总市值"
                value={displayStr(result.total_market_value)}
                detail="total_market_value。"
              />
            </div>

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              KRD 分桶（DV01）
            </h2>
            {krdChartOption ? (
              <ReactECharts option={krdChartOption} style={{ height: 320 }} />
            ) : null}

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              集中度
            </h2>
            <div style={summaryGridStyle}>
              <PlaceholderCard
                title="发行人 HHI"
                value={displayStr(result.issuer_concentration_hhi)}
                detail="issuer_concentration_hhi。"
              />
              <PlaceholderCard
                title="前五大权重"
                value={displayStr(result.issuer_top5_weight)}
                detail="issuer_top5_weight。"
              />
            </div>

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              流动性缺口（市值）
            </h2>
            <div style={summaryGridStyle}>
              <PlaceholderCard
                title="30 日内到期市值"
                value={displayStr(result.liquidity_gap_30d)}
                detail="liquidity_gap_30d。"
              />
              <PlaceholderCard
                title="90 日内到期市值"
                value={displayStr(result.liquidity_gap_90d)}
                detail="liquidity_gap_90d。"
              />
            </div>

            <div
              style={{
                marginTop: 20,
                padding: 12,
                borderRadius: 12,
                border:
                  result.quality_flag === "ok"
                    ? "1px solid #d7dfea"
                    : "1px solid #e8d9a8",
                background: result.quality_flag === "ok" ? "#f6f9fc" : "#fffbeb",
                color: "#162033",
                fontSize: 14,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                质量标记：{result.quality_flag}
              </div>
              {result.warnings.length === 0 ? (
                <div style={{ color: "#5c6b82" }}>无 warnings。</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: 20, color: "#5c6b82" }}>
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </AsyncSection>
    </section>
  );
}
