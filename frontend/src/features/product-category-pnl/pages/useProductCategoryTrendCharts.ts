import { useMemo } from "react";

import { EM_DASH } from "../../../utils/format";
import {
  buildDualAxisChartOption,
  buildIncomeYearComparisonChartOption,
  buildInterestEarningAssetLiabilityScaleChartOption,
  buildInterestSpreadChartOption,
  buildInterestSpreadYearComparisonChartOption,
  buildLiabilitySideTrendChartOption,
  buildProductCategoryComparisonReadout,
  buildSingleAxisChartOption,
  PRODUCT_CATEGORY_DARK_CHART_THEME,
} from "./ProductCategoryComparisonCharts";
import {
  type ProductCategoryInterestSpreadAttributionSelection,
  type ProductCategoryLiabilitySideTrendSurface,
  type ProductCategoryTrendSnapshot,
  selectProductCategoryCurrencyNetIncomeChart,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChart,
  selectProductCategoryInterestEarningAssetLiabilityScaleChart,
  selectProductCategoryInterestEarningIncomeScaleChart,
  selectProductCategoryInterestEarningSpreadChart,
  selectProductCategoryInterestEarningSpreadYearComparisonChart,
  selectProductCategoryInterestSpreadAttributionSurface,
  selectProductCategoryInterestSpreadChart,
  selectProductCategoryInterestSpreadYearComparisonChart,
  selectProductCategoryTplScaleYieldChart,
} from "./productCategoryPnlPageModel";

function formatProductCategoryTrendMetric(
  value: number | null | undefined,
  unit: string,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}${unit}`;
}

type ProductCategoryTrendChartsInput = {
  trendSnapshots: ProductCategoryTrendSnapshot[];
  interestSpreadComparisonSnapshots: ProductCategoryTrendSnapshot[];
  liabilitySideTrendSurface: ProductCategoryLiabilitySideTrendSurface;
  liabilityMatrixTrendSurface: ProductCategoryLiabilitySideTrendSurface;
  selectedYearMonth: { year: number; month: number } | null;
  interestSpreadAttributionSelection: ProductCategoryInterestSpreadAttributionSelection;
};

export function useProductCategoryTrendCharts({
  trendSnapshots,
  interestSpreadComparisonSnapshots,
  liabilitySideTrendSurface,
  liabilityMatrixTrendSurface,
  selectedYearMonth,
  interestSpreadAttributionSelection,
}: ProductCategoryTrendChartsInput) {
  const tplScaleYieldChart = useMemo(
    () => selectProductCategoryTplScaleYieldChart(trendSnapshots),
    [trendSnapshots],
  );
  const currencyNetIncomeChart = useMemo(
    () => selectProductCategoryCurrencyNetIncomeChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningIncomeScaleChart = useMemo(
    () => selectProductCategoryInterestEarningIncomeScaleChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningAssetLiabilityScaleChart = useMemo(
    () =>
      selectProductCategoryInterestEarningAssetLiabilityScaleChart(
        trendSnapshots,
      ),
    [trendSnapshots],
  );
  const interestSpreadChart = useMemo(
    () => selectProductCategoryInterestSpreadChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningSpreadChart = useMemo(
    () => selectProductCategoryInterestEarningSpreadChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const cnyInterestSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
        "cny",
      ),
    [interestSpreadComparisonSnapshots],
  );
  const interestEarningSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestEarningSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const cnyInterestEarningSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestEarningSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
        "cny",
      ),
    [interestSpreadComparisonSnapshots],
  );
  const intermediateBusinessIncomeYearComparisonChart = useMemo(
    () =>
      selectProductCategoryIntermediateBusinessIncomeYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const interestSpreadAttributionSurface = useMemo(
    () =>
      selectedYearMonth
        ? selectProductCategoryInterestSpreadAttributionSurface(
            interestSpreadComparisonSnapshots,
            interestSpreadAttributionSelection,
            selectedYearMonth.year,
          )
        : null,
    [
      interestSpreadAttributionSelection,
      interestSpreadComparisonSnapshots,
      selectedYearMonth,
    ],
  );
  const tplScaleYieldOption = useMemo(
    () =>
      tplScaleYieldChart
        ? buildDualAxisChartOption({
            labels: tplScaleYieldChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "%",
            series: [
              {
                name: "人民币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.cnyScale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "外币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.foreignScale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
              },
              {
                name: "收益率（%）",
                type: "line",
                data: tplScaleYieldChart.weightedYield,
                yAxisIndex: 1,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
            ],
          })
        : null,
    [tplScaleYieldChart],
  );
  const currencyNetIncomeOption = useMemo(
    () =>
      currencyNetIncomeChart
        ? buildSingleAxisChartOption({
            labels: currencyNetIncomeChart.labels,
            axisName: "亿元",
            series: [
              {
                name: "人民币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.cnyNet,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "外币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.foreignNet,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
              },
            ],
          })
        : null,
    [currencyNetIncomeChart],
  );
  const interestEarningIncomeScaleOption = useMemo(
    () =>
      interestEarningIncomeScaleChart
        ? buildDualAxisChartOption({
            labels: interestEarningIncomeScaleChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "亿元",
            series: [
              {
                name: "生息资产规模（亿元）",
                type: "bar",
                data: interestEarningIncomeScaleChart.scale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "生息资产收入（亿元）",
                type: "line",
                data: interestEarningIncomeScaleChart.income,
                yAxisIndex: 1,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
            ],
          })
        : null,
    [interestEarningIncomeScaleChart],
  );
  const interestEarningAssetLiabilityScaleOption = useMemo(
    () =>
      interestEarningAssetLiabilityScaleChart
        ? buildInterestEarningAssetLiabilityScaleChartOption({
            labels: interestEarningAssetLiabilityScaleChart.labels,
            series: [
              {
                name: "生息资产日均额（亿元）",
                data: interestEarningAssetLiabilityScaleChart.interestEarningAssetScale,
                /* nocturne accent 半透明（原 dh-api 钢蓝 rgba，canvas 不消费 CSS 变量）。 */
                color: "rgba(145,132,217,0.72)",
                borderColor: "rgba(145,132,217,0.4)",
              },
              {
                name: "附息负债日均额（亿元）",
                data: interestEarningAssetLiabilityScaleChart.interestBearingLiabilityScale,
                /* nocturne warn 半透明（原 dh-api 金琥珀 rgba）。 */
                color: "rgba(213,178,110,0.72)",
                borderColor: "rgba(213,178,110,0.4)",
              },
            ],
          })
        : null,
    [interestEarningAssetLiabilityScaleChart],
  );
  const interestSpreadOption = useMemo(
    () =>
      interestSpreadChart
        ? buildInterestSpreadChartOption({
            labels: interestSpreadChart.labels,
            series: [
              {
                name: "资产端收益率（含TPL）（%）",
                data: interestSpreadChart.assetYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
              {
                name: "负债端成本率（%）",
                data: interestSpreadChart.liabilityYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              },
              {
                name: "资产负债利差（含TPL）（%）",
                data: interestSpreadChart.spread,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.red,
              },
            ],
          })
        : null,
    [interestSpreadChart],
  );
  const interestEarningSpreadOption = useMemo(
    () =>
      interestEarningSpreadChart
        ? buildInterestSpreadChartOption({
            labels: interestEarningSpreadChart.labels,
            series: [
              {
                name: "生息资产收益率（%）",
                data: interestEarningSpreadChart.assetYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
              {
                name: "负债端成本率（%）",
                data: interestEarningSpreadChart.liabilityYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              },
              {
                name: "生息资产负债利差（%）",
                data: interestEarningSpreadChart.spread,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.red,
              },
            ],
          })
        : null,
    [interestEarningSpreadChart],
  );
  const comparisonCurrentSeriesName = selectedYearMonth
    ? `${selectedYearMonth.year}年`
    : null;
  const interestSpreadYearComparisonOption = useMemo(
    () =>
      interestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: interestSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: interestSpreadYearComparisonChart.series.map((series) => ({
              name: series.year,
              data: series.spread,
              color:
                series.year === comparisonCurrentSeriesName
                  ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                  : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
            })),
          })
        : null,
    [comparisonCurrentSeriesName, interestSpreadYearComparisonChart],
  );
  const cnyInterestSpreadYearComparisonOption = useMemo(
    () =>
      cnyInterestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: cnyInterestSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: cnyInterestSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [cnyInterestSpreadYearComparisonChart, comparisonCurrentSeriesName],
  );
  const interestEarningSpreadYearComparisonOption = useMemo(
    () =>
      interestEarningSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: interestEarningSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: interestEarningSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [comparisonCurrentSeriesName, interestEarningSpreadYearComparisonChart],
  );
  const cnyInterestEarningSpreadYearComparisonOption = useMemo(
    () =>
      cnyInterestEarningSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: cnyInterestEarningSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: cnyInterestEarningSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [cnyInterestEarningSpreadYearComparisonChart, comparisonCurrentSeriesName],
  );
  const intermediateBusinessIncomeYearComparisonOption = useMemo(
    () =>
      intermediateBusinessIncomeYearComparisonChart
        ? buildIncomeYearComparisonChartOption({
            labels: intermediateBusinessIncomeYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: intermediateBusinessIncomeYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.income,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [
      comparisonCurrentSeriesName,
      intermediateBusinessIncomeYearComparisonChart,
    ],
  );
  const liabilitySideTrendOption = useMemo(
    () =>
      liabilityMatrixTrendSurface.chart
        ? buildLiabilitySideTrendChartOption({
            labels: liabilityMatrixTrendSurface.chart.labels,
            averageDaily:
              liabilityMatrixTrendSurface.chart.totalAverageDaily,
            rate: liabilityMatrixTrendSurface.chart.totalRate,
          })
        : null,
    [liabilityMatrixTrendSurface.chart],
  );
  const interestEarningSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: interestEarningSpreadYearComparisonChart?.labels,
      series: interestEarningSpreadYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.spread }),
      ),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const cnyInterestEarningSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: cnyInterestEarningSpreadYearComparisonChart?.labels,
      series: cnyInterestEarningSpreadYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.spread }),
      ),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const interestSpreadComparisonReadout = buildProductCategoryComparisonReadout(
    {
      labels: interestSpreadYearComparisonChart?.labels,
      series: interestSpreadYearComparisonChart?.series.map((series) => ({
        year: series.year,
        data: series.spread,
      })),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    },
  );
  const cnyInterestSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: cnyInterestSpreadYearComparisonChart?.labels,
      series: cnyInterestSpreadYearComparisonChart?.series.map((series) => ({
        year: series.year,
        data: series.spread,
      })),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const intermediateBusinessIncomeComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: intermediateBusinessIncomeYearComparisonChart?.labels,
      series: intermediateBusinessIncomeYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.income }),
      ),
      valueUnit: "亿元",
      deltaUnit: "亿元",
      deltaScale: 1,
    });
  const trendLatestIndex = Math.max(
    (interestEarningIncomeScaleChart?.labels.length ?? 1) - 1,
    0,
  );
  const spreadLatestIndex = Math.max(
    (interestSpreadChart?.labels.length ?? 1) - 1,
    0,
  );
  const liabilityLatestIndex = Math.max(
    (liabilitySideTrendSurface.chart?.labels.length ?? 1) - 1,
    0,
  );
  const trendHeaderMetrics = {
    earningScale: formatProductCategoryTrendMetric(
      interestEarningIncomeScaleChart?.scale[trendLatestIndex],
      " 亿",
    ),
    liabilityAverage: formatProductCategoryTrendMetric(
      liabilitySideTrendSurface.chart?.totalAverageDaily[liabilityLatestIndex],
      " 亿",
    ),
    netSpread: formatProductCategoryTrendMetric(
      interestSpreadChart?.spread[spreadLatestIndex],
      "%",
    ),
  };

  return {
    options: {
      tplScaleYield: tplScaleYieldOption,
      currencyNetIncome: currencyNetIncomeOption,
      interestEarningIncomeScale: interestEarningIncomeScaleOption,
      interestEarningAssetLiabilityScale: interestEarningAssetLiabilityScaleOption,
      interestSpread: interestSpreadOption,
      interestEarningSpread: interestEarningSpreadOption,
      liabilitySideTrend: liabilitySideTrendOption,
    },
    comparisons: {
      interestSpread: {
        chart: interestSpreadYearComparisonChart,
        option: interestSpreadYearComparisonOption,
        readout: interestSpreadComparisonReadout,
      },
      cnyInterestSpread: {
        chart: cnyInterestSpreadYearComparisonChart,
        option: cnyInterestSpreadYearComparisonOption,
        readout: cnyInterestSpreadComparisonReadout,
      },
      interestEarningSpread: {
        chart: interestEarningSpreadYearComparisonChart,
        option: interestEarningSpreadYearComparisonOption,
        readout: interestEarningSpreadComparisonReadout,
      },
      cnyInterestEarningSpread: {
        chart: cnyInterestEarningSpreadYearComparisonChart,
        option: cnyInterestEarningSpreadYearComparisonOption,
        readout: cnyInterestEarningSpreadComparisonReadout,
      },
      intermediateBusinessIncome: {
        chart: intermediateBusinessIncomeYearComparisonChart,
        option: intermediateBusinessIncomeYearComparisonOption,
        readout: intermediateBusinessIncomeComparisonReadout,
      },
    },
    interestSpreadAttributionSurface,
    headerMetrics: trendHeaderMetrics,
    liabilityReadout: liabilityMatrixTrendSurface.totalReadout,
  };
}

export type ProductCategoryTrendCharts = ReturnType<
  typeof useProductCategoryTrendCharts
>;
