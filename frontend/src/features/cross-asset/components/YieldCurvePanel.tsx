import { Suspense, useMemo } from "react";

import { EM_DASH } from "../../../utils/format";
import { buildYieldCurveOption, type YieldCurveSeriesResult } from "../lib/crossAssetYieldCurve";
import { LazyCrossAssetECharts } from "./CrossAssetECharts";

import "./YieldCurvePanel.css";

const UI = {
  eyebrow: "利率结构",
  title: "收益率曲线 · 全期限",
  loading: "正在加载收益率曲线…",
  empty: "当前没有可用的收益率曲线点位（国债 / 国开债 / 企业债）。",
  mixedNote: "不同期限点位可能来自不同交易日，连线不代表同一交易日切面。",
} as const;

function compactDate(value: string): string {
  return value.length >= 10 ? value.slice(5) : value;
}

export function YieldCurvePanel({
  curves,
  loading = false,
  chartEnabled = true,
}: {
  curves: YieldCurveSeriesResult;
  loading?: boolean;
  chartEnabled?: boolean;
}) {
  // Only consumed by the cross-asset drivers page, which is pinned to the terminal theme.
  const option = useMemo(() => buildYieldCurveOption(curves, "terminal"), [curves]);
  const totalPoints = curves.families.reduce((count, family) => count + family.pointCount, 0);

  const dateHint =
    curves.mixedDates && curves.earliestDate && curves.latestDate
      ? `点位日期 ${compactDate(curves.earliestDate)} ~ ${compactDate(curves.latestDate)} 混合`
      : curves.latestDate
        ? `点位日期 ${compactDate(curves.latestDate)}`
        : "暂无点位日期";

  return (
    <section className="yield-curve-panel" data-testid="yield-curve-panel">
      <div className="yield-curve-panel__header">
        <div className="yield-curve-panel__eyebrow">{UI.eyebrow}</div>
        <div className="yield-curve-panel__title-row">
          <h3 className="yield-curve-panel__title">{UI.title}</h3>
          <span className="yield-curve-panel__meta">
            {totalPoints > 0 ? `${curves.families.length} 族 · ${totalPoints} 点` : EM_DASH}
          </span>
        </div>
        <p className="yield-curve-panel__hint" data-testid="yield-curve-panel-hint">
          {totalPoints > 0 ? `${dateHint}；${UI.mixedNote}` : dateHint}
        </p>
      </div>
      {loading ? (
        <div className="yield-curve-panel__loading" data-testid="yield-curve-panel-loading">
          <div className="yield-curve-panel__spinner" />
          {UI.loading}
        </div>
      ) : option ? (
        <div className="yield-curve-panel__chart" data-testid="yield-curve-panel-chart">
          {chartEnabled ? (
            <Suspense
              fallback={
                <div
                  className="yield-curve-panel__loading"
                  data-testid="yield-curve-panel-chart-loading"
                >
                  <div className="yield-curve-panel__spinner" />
                  正在加载图表资源…
                </div>
              }
            >
              <LazyCrossAssetECharts
                option={option}
                className="yield-curve-panel__canvas"
                notMerge
                lazyUpdate
              />
            </Suspense>
          ) : (
            <div
              className="yield-curve-panel__loading"
              data-testid="yield-curve-panel-chart-deferred"
            >
              <div className="yield-curve-panel__spinner" />
              正在准备图表…
            </div>
          )}
        </div>
      ) : (
        <div className="yield-curve-panel__empty" data-testid="yield-curve-panel-empty">
          {UI.empty}
        </div>
      )}
    </section>
  );
}
