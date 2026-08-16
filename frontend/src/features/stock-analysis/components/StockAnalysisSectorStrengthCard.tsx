import type { ReactNode } from "react";

import {
  SECTOR_STRENGTH_VISIBLE_LIMIT,
  type SectorStrengthBarRow,
} from "../lib/stockAnalysisChartModel";
import "./StockAnalysisSectorStrengthCard.css";

type SectorStrengthCardState = "ready" | "loading" | "empty" | "error";

type StockAnalysisSectorStrengthCardProps = {
  state: SectorStrengthCardState;
  bars: SectorStrengthBarRow[];
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

/**
 * First-screen compact sector-strength bars backed by sector snapshot or
 * rank-series support.
 *
 * Deliberately not an ECharts instance: this card sits on the settled first
 * screen, and its eager chart mount was what pulled echarts+zrender (~230 kB
 * gz) into every first paint. Rows are plain text plus one inline SVG track
 * per row; colours come from the `--dh-api-*` theme tokens only.
 */
export function StockAnalysisSectorStrengthCard({
  state,
  bars,
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

  if (state === "empty" || bars.length === 0) {
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
      <div
        className="stock-analysis-page__fs-sector-chart stock-analysis-sector-bars"
        data-testid="stock-analysis-sector-strength-first-screen"
        role="list"
        aria-label="板块强度排序条形"
      >
        {bars.map((bar) => (
          <div
            key={bar.key}
            className="stock-analysis-sector-bars__row"
            role="listitem"
            title={bar.title}
            data-active={bar.active ? "true" : undefined}
            data-testid={`stock-analysis-sector-strength-bar-${bar.key}`}
          >
            <span className="stock-analysis-sector-bars__name">{bar.name}</span>
            <svg
              className="stock-analysis-sector-bars__svg"
              aria-hidden="true"
              focusable="false"
            >
              <rect
                className="stock-analysis-sector-bars__track"
                x="0"
                y="0"
                width="100%"
                height="100%"
                rx="3"
              />
              <rect
                className="stock-analysis-sector-bars__fill"
                x={`${(bar.barStartFraction * 100).toFixed(3)}%`}
                y="0"
                width={`${(bar.barSpanFraction * 100).toFixed(3)}%`}
                height="100%"
                rx="3"
              />
            </svg>
            <span className="stock-analysis-sector-bars__value stock-analysis-page__tabular">
              {bar.valueLabel}
            </span>
          </div>
        ))}
      </div>
      <footer className="stock-analysis-page__fs-card-foot">
        {leaderLabel ? <span>首位 {leaderLabel}</span> : <span>排序按综合得分</span>}
        <span>共 {sectorCount} 个板块，展示前 {visibleSectorCount}</span>
        <span>{sourceLabel}</span>
      </footer>
    </CardShell>
  );
}
