import { Suspense } from "react";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";
import { formatCorrelation, type CorrelationMatrix } from "../lib/crossAssetAnalytics";
import { FrontendAnalyticsChip } from "./MomentumAndVolatilityPanels";
import { LazyCrossAssetECharts } from "./CrossAssetECharts";
import "./CorrelationAndRegimePanels.css";
import {
  resolveCrossAssetChartPalette,
  type CrossAssetChartTheme,
} from "../lib/crossAssetChartTheme";

type CorrelationSummaryCard = {
  id: string;
  title: string;
  pair: string;
  value: string;
};

function formatCorrelationPair(matrix: CorrelationMatrix, rowIndex: number, colIndex: number) {
  return `${matrix.labels[rowIndex]} / ${matrix.labels[colIndex]}`;
}

export function CorrelationHeatmapPanel({
  matrix,
  theme = "light",
}: {
  matrix: CorrelationMatrix;
  theme?: CrossAssetChartTheme;
}) {
  if (matrix.keys.length < 2) return null;
  const palette = resolveCrossAssetChartPalette(theme);
  const n = matrix.keys.length;
  const summaryCards = buildCorrelationSummaryCards(matrix);
  const option: EChartsOption = {
    animation: false,
    grid: { left: 154, right: 12, top: 28, bottom: 56 },
    tooltip: {
      trigger: "item",
      renderMode: "richText",
      backgroundColor: palette.tooltipBg,
      borderColor: palette.tooltipBorder,
      textStyle: { color: palette.text, fontSize: 12 },
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const value = item?.value as [number, number, number | string] | undefined;
        if (!value) return "";
        return `${matrix.labels[value[1]]} × ${matrix.labels[value[0]]}\n${formatCorrelation(typeof value[2] === "number" ? value[2] : null)}`;
      },
    },
    xAxis: {
      type: "category", position: "top", data: matrix.keys.map((_, index) => String(index + 1)),
      axisTick: { show: false }, axisLine: { show: false },
      axisLabel: { interval: 0, color: palette.textSoft, fontSize: 12 },
      splitArea: { show: true, areaStyle: { color: [palette.heatmapMid] } },
    },
    yAxis: {
      type: "category", inverse: true,
      data: matrix.labels.map((label, index) => `${index + 1}  ${label}`),
      axisTick: { show: false }, axisLine: { show: false },
      axisLabel: { interval: 0, color: palette.textSoft, fontSize: 12, width: 146, overflow: "truncate" },
    },
    visualMap: {
      min: -1, max: 1, dimension: 2, calculable: false, orient: "horizontal",
      left: "center", bottom: 4, itemWidth: 10, itemHeight: 130,
      text: ["正相关 +1", "负相关 −1"], textStyle: { color: palette.textSoft, fontSize: 12 },
      inRange: { color: [palette.heatmapLow, palette.heatmapMid, palette.heatmapHigh] },
    },
    series: [{
      type: "heatmap",
      data: matrix.cells.flatMap((row, ri) => row.map((cell, ci) => [ci, ri, cell.value ?? "-"])),
      itemStyle: { borderWidth: 1, borderColor: palette.emphasisBorder },
      emphasis: { itemStyle: { borderColor: palette.text, borderWidth: 2 } },
    }],
  };
  return (
    <section className="ca-correlation ca-correlation--chart" data-testid="cross-asset-correlation-heatmap">
      <h2 className="ca-correlation__title">资产相关性矩阵 <FrontendAnalyticsChip /></h2>
      <p className="ca-correlation__subtitle">基于短期序列窗口的 Pearson 相关系数。横轴编号与纵轴资产一致，悬停查看数值。</p>
      <div className="ca-correlation__summary" data-testid="cross-asset-correlation-summary">
        {summaryCards.map((card) => (
          <article className="ca-correlation__summary-card" key={card.id}>
            <span>{card.title}</span><em>{card.value}</em>
            <strong title={card.pair}>{card.pair}</strong>
          </article>
        ))}
      </div>
      <div className="ca-correlation__chart-scroll" data-testid="cross-asset-correlation-chart" role="img" aria-label={`${n} 项资产相关性热力图，完整数值可展开下方表格查看`}>
        <Suspense fallback={<div className="ca-correlation__chart-loading">正在加载相关性热力图…</div>}>
          <LazyCrossAssetECharts option={option} className="ca-correlation__canvas" notMerge lazyUpdate />
        </Suspense>
      </div>
      <p className="ca-correlation__chart-note">空白格表示暂无可比数据。</p>
      <details className="ca-correlation__details" data-testid="cross-asset-correlation-details">
        <summary><span>完整相关性数值</span><strong>{n} 项资产</strong></summary>
        <div className="ca-correlation__matrix-wrap" data-testid="cross-asset-correlation-matrix-wrap">
          <table className="ca-correlation__value-table">
            <caption>列编号对应首列资产编号</caption>
            <thead><tr><th scope="col">资产</th>{matrix.keys.map((key, index) => <th scope="col" key={key} title={matrix.labels[index]}>{index + 1}</th>)}</tr></thead>
            <tbody>{matrix.cells.map((row, ri) => (
              <tr key={matrix.keys[ri]}>
                <th scope="row">{ri + 1} {matrix.labels[ri]}</th>
                {row.map((cell) => <td key={`${cell.rowKey}-${cell.colKey}`}>{formatCorrelation(cell.value)}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function buildCorrelationSummaryCards(matrix: CorrelationMatrix): CorrelationSummaryCard[] {
  const pairs = matrix.cells
    .flatMap((row, rowIndex) =>
      row.slice(rowIndex + 1).map((cell, offset) => ({
        rowIndex,
        colIndex: rowIndex + offset + 1,
        value: cell.value,
      })),
    )
    .filter((pair) => pair.value != null);

  const fallback = {
    pair: "暂无可比组合",
    value: EM_DASH,
  };
  const strongestPositive = pairs.slice().sort((left, right) => (right.value ?? -Infinity) - (left.value ?? -Infinity))[0];
  const strongestNegative = pairs.slice().sort((left, right) => (left.value ?? Infinity) - (right.value ?? Infinity))[0];

  function cardValue(pair: (typeof pairs)[number] | undefined) {
    if (!pair) {
      return fallback;
    }
    return {
      pair: formatCorrelationPair(matrix, pair.rowIndex, pair.colIndex),
      value: formatCorrelation(pair.value),
    };
  }

  const positive = cardValue(strongestPositive);
  const negative = cardValue(strongestNegative);

  return [
    {
      id: "positive",
      title: strongestPositive && strongestPositive.value! > 0 ? "最强共振" : "最高相关",
      pair: positive.pair,
      value: positive.value,
    },
    {
      id: "negative",
      title: strongestNegative && strongestNegative.value! < 0 ? "最强背离" : "最低相关",
      pair: negative.pair,
      value: negative.value,
    },
  ];
}
