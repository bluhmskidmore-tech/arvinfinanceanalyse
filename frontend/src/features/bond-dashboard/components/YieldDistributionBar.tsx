import { useState } from "react";
import { Segmented } from "antd";
import { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import type { BondSectionDataState } from "../sectionStatus";
import { exactDecimalOrNull, formatRatioPercent, formatYi, nativeToNumber } from "../utils/format";

type YieldViewMode = "yield" | "tenor";

const MODE_OPTIONS: { value: YieldViewMode; label: string }[] = [
  { value: "yield", label: "收益率" },
  { value: "tenor", label: "期限" },
];

/** 2026-09-02 迁入 ChartCard：高度取阶梯 hero 档，载入骨架与画布同高由铬件保证。 */
const CHART_HEIGHT = CHART_CARD_HEIGHTS.hero;

export function YieldDistributionBar({
  yieldData,
  tenorData,
  yieldState,
  tenorState,
}: {
  yieldData: YieldDistributionPayload | undefined;
  tenorData: AssetStructurePayload | undefined;
  yieldState: BondSectionDataState;
  tenorState: BondSectionDataState;
}) {
  const [mode, setMode] = useState<YieldViewMode>("yield");

  /* 两个模式各自读一个 bundle 分区，状态也各归各的：收益率分区失败不该让期限模式变红。 */
  const state = mode === "yield" ? yieldState : tenorState;

  const categories =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.yield_bucket)
      : (tenorData?.items ?? []).map((i) => i.category);
  const valuesYi =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => {
          const exact = exactDecimalOrNull(i.total_market_value);
          if (exact !== null) return exact.dividedBy("1e8").toNumber();
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        })
      : (tenorData?.items ?? []).map((i) => {
          const exact = exactDecimalOrNull(i.total_market_value);
          if (exact !== null) return exact.dividedBy("1e8").toNumber();
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        });
  const valueTexts =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => formatYi(i.total_market_value))
      : (tenorData?.items ?? []).map((i) => formatYi(i.total_market_value));
  /* 后端两种 items 均带 bond_count（此前未消费），随 tooltip 披露。 */
  const bondCounts =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.bond_count)
      : (tenorData?.items ?? []).map((i) => i.bond_count);
  /* 期限分段由后端同时给出占比；收益率分段没有该字段，不在前端补算。 */
  const tenorPercentages = (tenorData?.items ?? []).map((i) => formatRatioPercent(i.percentage));

  /* 单系列无图例：铬件 legend="none"；网格底边由铬件按图例行数预留。 */
  const option: EChartsOption = nocturneChartTheme.createBarChartOption({
    grid: { left: 48, right: 24, top: 24 },
    tooltip: {
      /* 只覆盖 formatter，深色底/边/字由主题基座深合并保留。 */
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const first = list[0] as { name?: string; dataIndex?: number; value?: number | null } | undefined;
        if (!first) return "";
        const valueText =
          first.dataIndex === undefined ? EM_DASH : (valueTexts[first.dataIndex] ?? EM_DASH);
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
                  : `${tenorPercentage}%`
              }`
            : "";
        const valueLine = valueText === EM_DASH ? EM_DASH : `${valueText} 亿元`;
        return `${first.name ?? ""}<br/>${valueLine}${percentageText}${countText}`;
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

  /* 加权 YTM 读数只保留 KPI 带一处；question 只说明本图口径。真空收缩为空态（DESIGN.md §12 第 13 条）。 */
  return (
    <ChartCard
      testId="bond-dashboard-yield-distribution-chart"
      title={mode === "yield" ? "收益率分布" : "剩余期限分布（规模）"}
      question={mode === "yield" ? "本图为市值加权口径" : "按期限桶汇总市值（亿元）"}
      unit="亿元"
      height={CHART_HEIGHT}
      legend="none"
      option={categories.length === 0 ? null : option}
      state={state.status === "ready" ? undefined : state.status}
      errorMessage={state.message ?? undefined}
      actions={
        <Segmented
          size="small"
          value={mode}
          aria-label="bond-dashboard-yield-mode"
          onChange={(value) => setMode(value as YieldViewMode)}
          options={MODE_OPTIONS}
          className="bond-dashboard-charts__segmented"
        />
      }
    />
  );
}
