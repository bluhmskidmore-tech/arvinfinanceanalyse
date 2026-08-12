import { Suspense, lazy, type ReactNode } from "react";

import type { EChartsOption } from "../../../lib/echarts";
import { SECTOR_STRENGTH_VISIBLE_LIMIT } from "../lib/stockAnalysisChartModel";

const LazyReactECharts = lazy(() => import("../../../lib/echarts"));

type SectorStrengthCardState = "ready" | "loading" | "empty" | "error";

type StockAnalysisSectorStrengthCardProps = {
  state: SectorStrengthCardState;
  chartOption: EChartsOption | null;
  sectorCount: number;
  sourceLabel: string;
  leaderLabel: string | null;
  emptyReason?: string | null;
  errorMessage?: string | null;
};

function CardShell({ children, pill }: { children: ReactNode; pill: ReactNode }) {
  return (
    <section
      className="stock-analysis-page__fs-card"
      data-testid="stock-analysis-sector-strength-card"
      aria-label="板块强度"
    >
      <header className="stock-analysis-page__fs-card-head">
        <h2>板块强度</h2>
        {pill}
      </header>
      {children}
    </section>
  );
}

/** First-screen compact sector-strength chart backed by sector snapshot or rank-series support. */
export function StockAnalysisSectorStrengthCard({
  state,
  chartOption,
  sectorCount,
  sourceLabel,
  leaderLabel,
  emptyReason,
  errorMessage,
}: StockAnalysisSectorStrengthCardProps) {
  if (state === "loading") {
    return (
      <CardShell pill={<span className="stock-analysis-page__fs-card-pill">读取中</span>}>
        <div
          className="stock-analysis-page__fs-sector-placeholder"
          role="status"
          aria-label="板块强度读取中"
          data-testid="stock-analysis-sector-strength-loading"
        />
      </CardShell>
    );
  }

  if (state === "error") {
    return (
      <CardShell pill={<span className="stock-analysis-page__fs-card-pill" data-tone="negative">读取失败</span>}>
        <p className="stock-analysis-page__fs-card-empty" role="status">
          {errorMessage ?? "板块强度读取失败，请稍后重试。"}
        </p>
      </CardShell>
    );
  }

  if (state === "empty" || !chartOption) {
    return (
      <CardShell pill={<span className="stock-analysis-page__fs-card-pill" data-tone="warning">待补</span>}>
        <p
          className="stock-analysis-page__fs-card-empty"
          role="status"
          data-testid="stock-analysis-sector-strength-empty"
          title={emptyReason ?? undefined}
        >
          {emptyReason ?? "板块强弱数据未落地，等待输入补齐。"}
        </p>
      </CardShell>
    );
  }

  const visibleSectorCount = Math.min(sectorCount, SECTOR_STRENGTH_VISIBLE_LIMIT);

  return (
    <CardShell
      pill={
        <span className="stock-analysis-page__fs-card-pill stock-analysis-page__tabular">
          {sectorCount} 个板块
        </span>
      }
    >
      <div className="stock-analysis-page__fs-sector-chart" data-testid="stock-analysis-sector-strength-first-screen">
        <Suspense fallback={<div className="stock-analysis-page__fs-sector-placeholder" aria-hidden="true" />}>
          <LazyReactECharts
            option={chartOption}
            className="stock-analysis-page__echart stock-analysis-page__fs-sector-echart"
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
          />
        </Suspense>
      </div>
      <footer className="stock-analysis-page__fs-card-foot">
        {leaderLabel ? <span>首位 {leaderLabel}</span> : <span>排序按综合得分</span>}
        <span>共 {sectorCount} 个板块，展示前 {visibleSectorCount}</span>
        <span>{sourceLabel}</span>
      </footer>
    </CardShell>
  );
}
