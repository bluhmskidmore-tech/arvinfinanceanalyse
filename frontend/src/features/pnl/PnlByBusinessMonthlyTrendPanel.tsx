import { useMemo } from "react";

import type { PnlByBusinessMonthlyBucket } from "../../api/contracts";
import { BaseChart } from "../../components/charts/BaseChart";
import { createLineChartOption, mossChartPalette } from "../../components/charts/chartTheme";
import type { EChartsOption } from "../../lib/echarts";
import {
  buildSelectedBusinessMonthlyTrend,
  type PnlByBusinessMonthlyTrendPoint,
  type PnlByBusinessTrendSelection,
} from "./pnlByBusinessMonthlyTrend";

type TrendSeries = {
  name: string;
  color: string;
  values: Array<number | null>;
  lineType?: "solid" | "dashed";
};

type PnlByBusinessMonthlyTrendPanelProps = {
  months: PnlByBusinessMonthlyBucket[];
  selectedBusiness: PnlByBusinessTrendSelection | undefined;
  periodStartDate?: string | null;
  periodEndDate?: string | null;
  isLoading: boolean;
  isError: boolean;
};

function formatAxisValue(value: number): string {
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function buildTrendOption(
  points: PnlByBusinessMonthlyTrendPoint[],
  series: TrendSeries[],
): EChartsOption {
  return createLineChartOption({
    legend: {
      data: series.map((item) => item.name),
      top: 0,
    },
    grid: { left: 12, right: 18, top: 48, bottom: 12, containLabel: true },
    xAxis: {
      type: "category",
      data: points.map((point) => point.monthKey),
      axisLabel: { interval: 0, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: formatAxisValue },
    },
    series: series.map((item) => ({
      name: item.name,
      type: "line" as const,
      data: item.values,
      connectNulls: false,
      showSymbol: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { color: item.color, width: 2, type: item.lineType ?? "solid" },
      itemStyle: { color: item.color },
      emphasis: { focus: "series" as const },
    })),
  });
}

export function PnlByBusinessMonthlyTrendPanel({
  months,
  selectedBusiness,
  periodStartDate,
  periodEndDate,
  isLoading,
  isError,
}: PnlByBusinessMonthlyTrendPanelProps) {
  const trend = useMemo(
    () => buildSelectedBusinessMonthlyTrend(months, selectedBusiness, { periodStartDate, periodEndDate }),
    [months, periodEndDate, periodStartDate, selectedBusiness],
  );
  const chartOptions = useMemo(() => {
    const points = trend.points;
    return {
      balance: buildTrendOption(points, [
        {
          name: "日均余额",
          color: mossChartPalette[0],
          values: points.map((point) => point.avgBalanceYi),
        },
        {
          name: "期末余额",
          color: mossChartPalette[1],
          values: points.map((point) => point.currentBalanceYi),
          lineType: "dashed",
        },
      ]),
      pnl: buildTrendOption(points, [
        {
          name: "合计损益",
          color: mossChartPalette[0],
          values: points.map((point) => point.totalPnlWan),
        },
        {
          name: "FTP后收益",
          color: mossChartPalette[4],
          values: points.map((point) => point.ftpNetPnlWan),
          lineType: "dashed",
        },
      ]),
      yield: buildTrendOption(points, [
        {
          name: "年化收益率",
          color: mossChartPalette[0],
          values: points.map((point) => point.annualizedYieldPct),
        },
        {
          name: "FTP年化利率",
          color: mossChartPalette[2],
          values: points.map((point) => point.ftpRatePct),
          lineType: "dashed",
        },
        {
          name: "FTP后年化收益率",
          color: mossChartPalette[4],
          values: points.map((point) => point.ftpNetAnnualizedYieldPct),
        },
      ]),
    };
  }, [trend.points]);

  const hasAvailableTrend = trend.availablePointCount > 0;

  return (
    <section
      className="pnl-by-business-analysis-block pnl-by-business-selected-trend"
      data-testid="pnl-by-business-selected-monthly-trend"
    >
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>选中业务月度趋势</h2>
          <p>
            {trend.businessLabel} · 月报接口原值；余额仅换算为亿元、损益仅换算为万元，收益率与 FTP 不在前端重算。
          </p>
        </div>
        <span className="pnl-by-business-section-pill">
          {trend.availablePointCount}/{trend.points.length} 个月
        </span>
      </div>

      {isLoading ? (
        <div className="pnl-by-business-analysis-state">正在读取选中业务月度趋势</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">选中业务月度趋势读取失败</div>
      ) : !selectedBusiness ? (
        <div className="pnl-by-business-analysis-state">请选择业务种类后查看月度趋势</div>
      ) : !hasAvailableTrend ? (
        <div className="pnl-by-business-analysis-state">
          暂无所选业务月度趋势；月报接口未返回“{trend.businessLabel}”对应 row_key，未按 0 补齐。
        </div>
      ) : (
        <>
          {trend.coverageWarningMonths.length > 0 ||
          trend.missingBucketMonths.length > 0 ||
          trend.missingRowMonths.length > 0 ? (
            <div className="pnl-by-business-selected-trend__quality" role="note">
              {trend.coverageWarningMonths.length > 0 ? (
                <span>覆盖/补样待复核：{trend.coverageWarningMonths.join("、")}</span>
              ) : null}
              {trend.missingBucketMonths.length > 0 ? (
                <span>月报缺少整月 bucket 并保留断点：{trend.missingBucketMonths.join("、")}</span>
              ) : null}
              {trend.missingRowMonths.length > 0 ? (
                <span>缺少该业务行并保留断点：{trend.missingRowMonths.join("、")}</span>
              ) : null}
            </div>
          ) : null}
          <div className="pnl-by-business-selected-trend__grid">
            <article className="pnl-by-business-selected-trend__card">
              <h3>日均与期末余额（亿元）</h3>
              <p>看规模变化及日均与期末的偏离。</p>
              <BaseChart option={chartOptions.balance} height={250} />
            </article>
            <article className="pnl-by-business-selected-trend__card">
              <h3>损益与FTP后收益（万元）</h3>
              <p>看损益变化及资金成本扣除后的方向。</p>
              <BaseChart option={chartOptions.pnl} height={250} />
            </article>
            <article className="pnl-by-business-selected-trend__card">
              <h3>收益率与FTP（%）</h3>
              <p>同时观察年化收益率、FTP利率与FTP后年化收益率。</p>
              <BaseChart option={chartOptions.yield} height={250} />
            </article>
          </div>
        </>
      )}
    </section>
  );
}
