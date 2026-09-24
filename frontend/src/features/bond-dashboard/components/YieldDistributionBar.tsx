import { useState } from "react";
import { Segmented } from "antd";
import { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import { nativeToNumber } from "../utils/format";

type YieldViewMode = "yield" | "tenor";

const MODE_OPTIONS: { value: YieldViewMode; label: string }[] = [
  { value: "yield", label: "收益率" },
  { value: "tenor", label: "期限" },
];

export function YieldDistributionBar({
  yieldData,
  tenorData,
  loadingYield,
  loadingTenor,
}: {
  yieldData: YieldDistributionPayload | undefined;
  tenorData: AssetStructurePayload | undefined;
  loadingYield: boolean;
  loadingTenor: boolean;
}) {
  const [mode, setMode] = useState<YieldViewMode>("yield");

  const loading = mode === "yield" ? loadingYield : loadingTenor;
  const payload = mode === "yield" ? yieldData : tenorData;

  const categories =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.yield_bucket)
      : (tenorData?.items ?? []).map((i) => i.category);
  const valuesYi =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => {
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        })
      : (tenorData?.items ?? []).map((i) => {
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        });
  /* 后端两种 items 均带 bond_count（此前未消费），随 tooltip 披露。 */
  const bondCounts =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.bond_count)
      : (tenorData?.items ?? []).map((i) => i.bond_count);
  /* 期限分段由后端同时给出占比；收益率分段没有该字段，不在前端补算。 */
  const tenorPercentages = (tenorData?.items ?? []).map((i) => nativeToNumber(i.percentage));

  const option: EChartsOption = nocturneChartTheme.createBarChartOption({
    grid: { left: 48, right: 24, top: 40, bottom: 32 },
    tooltip: {
      /* 只覆盖 formatter，深色底/边/字由主题基座深合并保留。 */
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const first = list[0] as { name?: string; dataIndex?: number; value?: number | null } | undefined;
        if (!first) return "";
        const value = first.value;
        const valueText =
          value === null || value === undefined
            ? EM_DASH
            : Number(value).toLocaleString("zh-CN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              });
        const count = first.dataIndex === undefined ? undefined : bondCounts[first.dataIndex];
        const countText = count === undefined ? "" : `<br/>${count} 只`;
        const tenorPercentage =
          mode === "tenor" && first.dataIndex !== undefined
            ? tenorPercentages[first.dataIndex]
            : undefined;
        const percentageText =
          mode === "tenor"
            ? `<br/>占比：${
                tenorPercentage === null || tenorPercentage === undefined
                  ? EM_DASH
                  : `${(tenorPercentage * 100).toFixed(2)}%`
              }`
            : "";
        return `${first.name ?? ""}<br/>${valueText} 亿元${percentageText}${countText}`;
      },
    },
    xAxis: {
      type: "category",
      data: categories,
      /* interval:0 防 auto 抽稀（7 桶只显 3 个）；桶标签较长，两种模式统一斜排。 */
      axisLabel: { interval: 0, rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      splitLine: { lineStyle: { type: "dashed" } },
    },
    series: [
      {
        type: "bar",
        data: valuesYi,
        barMaxWidth: 48,
        itemStyle: { color: nocturneChartTheme.categoricalPalette[0] },
      },
    ],
  });

  return (
    <div className="bond-dashboard-page__panel bond-dashboard-charts__panel">
      <div className="bond-dashboard-charts__head">
        <h3 className="bond-dashboard-charts__head-title">
          {mode === "yield" ? "收益率分布" : "剩余期限分布（规模）"}
        </h3>
        <Segmented
          size="small"
          value={mode}
          aria-label="bond-dashboard-yield-mode"
          onChange={(value) => setMode(value as YieldViewMode)}
          options={MODE_OPTIONS}
          className="bond-dashboard-charts__segmented"
        />
      </div>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : (
        <>
          {/* 加权 YTM 读数只保留 KPI 带一处；此处 hint 只说明本图口径。 */}
          {mode === "yield" ? (
            <p className="bond-dashboard-charts__hint">本图为市值加权口径</p>
          ) : (
            <p className="bond-dashboard-charts__hint">按期限桶汇总市值（亿元）</p>
          )}
          {/* 仅真实空 payload 收敛为暂无数据；envelope 未到达时维持图表骨架防高度跳变。 */}
          {payload && categories.length === 0 ? (
            <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
              暂无数据
            </p>
          ) : (
            <div className="bond-dashboard-charts__fill">
              <BaseChart option={option} height={280} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
