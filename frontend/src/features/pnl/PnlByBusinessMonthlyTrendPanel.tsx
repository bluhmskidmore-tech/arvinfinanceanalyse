import { useMemo, useState } from "react";

import type { PnlByBusinessMonthlyBucket } from "../../api/contracts";
import { BaseChart } from "../../components/charts/BaseChart";
import { createLineChartOption, mossChartPalette } from "../../components/charts/chartTheme";
import type { EChartsOption } from "../../lib/echarts";
import { ibTokens } from "../../theme/designSystem";
import { EM_DASH } from "../../utils/format";
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

type TrendView = "pnl" | "balance" | "yield";

const TREND_VIEW_META: Record<
  TrendView,
  { label: string; title: string; description: string; unit: string }
> = {
  pnl: {
    label: "损益 / FTP后",
    title: "损益与 FTP 后收益（万元）",
    description: "优先判断损益方向，以及扣除资金成本后是否仍然为正。",
    unit: "万元",
  },
  balance: {
    label: "日均 / 期末",
    title: "日均与期末余额（亿元）",
    description: "观察规模变化，以及日均余额与月末时点余额的偏离。",
    unit: "亿元",
  },
  yield: {
    label: "收益率 / FTP",
    title: "收益率与 FTP（%）",
    description: "对照年化收益率、FTP 年化利率与 FTP 后年化收益率。",
    unit: "%",
  },
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
  unit: string,
  showZeroLine = false,
): EChartsOption {
  return createLineChartOption({
    tooltip: {
      valueFormatter: (value) => {
        if (value === null || value === undefined || value === "") {
          return EM_DASH;
        }
        const numericValue = Number(value);
        return Number.isFinite(numericValue) ? `${formatAxisValue(numericValue)} ${unit}` : EM_DASH;
      },
    },
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
    series: series.map((item, index) => ({
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
      markLine: showZeroLine && index === 0
        ? {
            silent: true,
            symbol: "none",
            label: { show: false },
            lineStyle: { color: ibTokens.color.inkMuted, width: 1, type: "dashed" as const },
            data: [{ yAxis: 0 }],
          }
        : undefined,
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
  const [activeTrendView, setActiveTrendView] = useState<TrendView>("pnl");
  const trend = useMemo(
    () => buildSelectedBusinessMonthlyTrend(months, selectedBusiness, { periodStartDate, periodEndDate }),
    [months, periodEndDate, periodStartDate, selectedBusiness],
  );
  const chartOptions = useMemo(() => {
    const points = trend.points;
    return {
      balance: buildTrendOption(
        points,
        [
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
        ],
        TREND_VIEW_META.balance.unit,
      ),
      pnl: buildTrendOption(
        points,
        [
          {
            name: "合计损益",
            color: mossChartPalette[0],
            values: points.map((point) => point.totalPnlWan),
          },
          {
            name: "FTP后收益",
            color: mossChartPalette[5],
            values: points.map((point) => point.ftpNetPnlWan),
            lineType: "dashed",
          },
        ],
        TREND_VIEW_META.pnl.unit,
        true,
      ),
      yield: buildTrendOption(
        points,
        [
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
            color: mossChartPalette[5],
            values: points.map((point) => point.ftpNetAnnualizedYieldPct),
          },
        ],
        TREND_VIEW_META.yield.unit,
        true,
      ),
    };
  }, [trend.points]);

  const hasAvailableTrend = trend.availablePointCount > 0;
  const activeTrendMeta = TREND_VIEW_META[activeTrendView];
  const activeTrendOption = chartOptions[activeTrendView];

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
                <span>该月余额样本覆盖/补样待复核：{trend.coverageWarningMonths.join("、")}</span>
              ) : null}
              {trend.missingBucketMonths.length > 0 ? (
                <span>月报缺少整月 bucket 并保留断点：{trend.missingBucketMonths.join("、")}</span>
              ) : null}
              {trend.missingRowMonths.length > 0 ? (
                <span>缺少该业务行并保留断点：{trend.missingRowMonths.join("、")}</span>
              ) : null}
            </div>
          ) : null}
          <div className="pnl-by-business-selected-trend__toolbar">
            <div className="pnl-by-business-selected-trend__tabs" role="group" aria-label="趋势指标">
              {(Object.keys(TREND_VIEW_META) as TrendView[]).map((view) => (
                <button
                  key={view}
                  type="button"
                  aria-pressed={activeTrendView === view}
                  data-testid={`pnl-by-business-trend-tab-${view}`}
                  onClick={() => setActiveTrendView(view)}
                >
                  {TREND_VIEW_META[view].label}
                </button>
              ))}
            </div>
            <span>缺月、缺行保留断点，不按 0 补齐</span>
          </div>
          <article
            className="pnl-by-business-selected-trend__card"
            aria-labelledby="pnl-by-business-trend-active-title"
            data-testid="pnl-by-business-trend-active-panel"
          >
            <h3 id="pnl-by-business-trend-active-title">{activeTrendMeta.title}</h3>
            <p>{activeTrendMeta.description}</p>
            <BaseChart option={activeTrendOption} height={320} />
          </article>
        </>
      )}
    </section>
  );
}
