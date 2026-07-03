import { Button } from "antd";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import { externalDataQueryOptions } from "../../../app/externalDataRefreshPolicy";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import { type EChartsOption } from "../../../lib/echarts";
import { LinkageSpreadTenorTable } from "../components/LinkageSpreadTenorTable";
import { LiveResultMetaStrip } from "../components/LiveResultMetaStrip";
import { MacroLatestReadinessBanner } from "../components/MacroLatestReadinessBanner";
import {
  MarketDataLinkageCorrelationChart,
  MarketDataLinkageEnvironmentChart,
} from "../components/MarketDataLinkageCharts";
import { MarketDataLinkageSummaryBand } from "../components/MarketDataLinkageSummaryBand";
import { MarketDataChartShell } from "../components/MarketDataChartShell";
import { KpiCard } from "../../../components/KpiCard";
import { toneFromSignedDisplayString, toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { formatSignedNumber } from "../lib/marketDataFormat";
import { buildMarketDataMultiSeriesTimeChartOption } from "../lib/charts/marketDataSeriesTimeChartOption";
import { RATE_TREND_DEFINITIONS } from "./marketDataMacroConstants";
import "./MarketDataPage.css";

const MARKET_DATA_SHOW_CURVE_META_STRIP = false;
const MAX_EXTRA_SERIES = 5;
const LIQUIDITY_COMPOSITE_POLARITY_NOTE =
  "流动性正值=宽松；综合分正值=对债偏紧，综合计算中流动性取反。";

type MacroDepthTabKey = "curve" | "spreads" | "linkage";

type SpreadTenorSlot = { tenor: "3Y" | "5Y" | "10Y"; point: MacroBondLinkageTopCorrelation | null };

type MacroBondLinkagePartial = Partial<MacroBondLinkagePayload>;

export type MarketDataMacroDepthTabsProps = {
  macroDepthTab: MacroDepthTabKey;
  onMacroDepthTabChange: (key: MacroDepthTabKey) => void;
  latestQuery: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>, Error>;
  latestSeries: readonly ChoiceMacroLatestPoint[];
  rateTrendChartOption: EChartsOption | null;
  macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, Error>;
  spreadSlots: SpreadTenorSlot[];
  macroBondLinkage: MacroBondLinkagePartial;
  nonSpreadTopCorrelations: readonly MacroBondLinkageTopCorrelation[];
  embedded?: boolean;
};

const macroDepthTabLabels: Array<{ key: MacroDepthTabKey; label: string }> = [
  { key: "curve", label: "曲线（M8）" },
  { key: "spreads", label: "信用利差" },
  { key: "linkage", label: "压力与情景（M11/M15）" },
];

function scrollToAnchor(id: string) {
  requestAnimationFrame(() => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function qualityChipSuffix(flag: ChoiceMacroLatestPoint["quality_flag"]) {
  if (!flag || flag === "ok") {
    return null;
  }
  if (flag === "stale") {
    return " · 陈旧";
  }
  return ` · ${flag}`;
}

export function MarketDataMacroDepthTabs({
  macroDepthTab,
  onMacroDepthTabChange,
  latestQuery,
  latestSeries,
  rateTrendChartOption,
  macroBondLinkageQuery,
  spreadSlots,
  macroBondLinkage,
  nonSpreadTopCorrelations,
  embedded = false,
}: MarketDataMacroDepthTabsProps) {
  const client = useApiClient();
  const [extraSeriesIds, setExtraSeriesIds] = useState<string[]>([]);
  const derivedSpreads = latestQuery.data?.result.derived_spreads;
  const latestSeriesIds = useMemo(
    () => latestSeries.map((point) => point.series_id),
    [latestSeries],
  );
  const externalDataWatermarksQuery = useQuery({
    queryKey: ["market-data", "external-data-watermarks", client.mode],
    queryFn: () => client.getExternalDataWatermarks(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    refetchOnWindowFocus: false,
  });

  const selectableSeries = useMemo(
    () =>
      latestSeries.filter(
        (point) => !RATE_TREND_DEFINITIONS.some((def) => def.series_id === point.series_id),
      ),
    [latestSeries],
  );

  const multiSeriesOption = useMemo(() => {
    const defaultIds = RATE_TREND_DEFINITIONS.map((def) => def.series_id);
    const selectedIds = [...defaultIds, ...extraSeriesIds].slice(0, MAX_EXTRA_SERIES + defaultIds.length);
    const selected = selectedIds
      .map((seriesId) => latestSeries.find((point) => point.series_id === seriesId))
      .filter((point): point is ChoiceMacroLatestPoint => Boolean(point));
    return buildMarketDataMultiSeriesTimeChartOption(selected);
  }, [extraSeriesIds, latestSeries]);

  const chartOption = multiSeriesOption ?? rateTrendChartOption;
  const correlationRows = useMemo(() => {
    const spreadRows = spreadSlots.map((slot) => slot.point).filter(Boolean) as MacroBondLinkageTopCorrelation[];
    return spreadRows.length > 0 ? spreadRows : nonSpreadTopCorrelations;
  }, [nonSpreadTopCorrelations, spreadSlots]);

  const openSpreadsTab = useCallback(() => {
    onMacroDepthTabChange("spreads");
    scrollToAnchor("market-data-linkage-correlation");
  }, [onMacroDepthTabChange]);

  const openLinkageTab = useCallback(() => {
    onMacroDepthTabChange("linkage");
    scrollToAnchor("market-data-linkage-environment-bar");
  }, [onMacroDepthTabChange]);

  return (
    <div
      data-testid="market-data-macro-depth-wrap"
      className={
        embedded
          ? "market-data-terminal-embedded market-data-macro-chart-shell--flush-top"
          : "market-data-detail-panel market-data-macro-chart-shell--flush-top"
      }
    >
      <div
        data-testid="market-data-macro-depth-tabs"
        className="market-data-macro-depth-tabs"
        role="tablist"
        aria-label="宏观深度视图"
      >
        {macroDepthTabLabels.map((tab) => {
          const active = macroDepthTab === tab.key;
          return (
            <button
              key={tab.key}
              id={`market-data-macro-tab-trigger-${tab.key}`}
              data-testid={`market-data-macro-tab-trigger-${tab.key}`}
              className={`market-data-macro-depth-tab${active ? " market-data-macro-depth-tab--active" : ""}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`market-data-macro-tab-${tab.key}`}
              onClick={() => onMacroDepthTabChange(tab.key)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <MacroLatestReadinessBanner
        testId="market-data-macro-readiness"
        isLoading={latestQuery.isLoading}
        isError={latestQuery.isError}
        hasSeries={latestSeries.length > 0}
        meta={latestQuery.data?.result_meta}
        watermarkLedger={externalDataWatermarksQuery.data}
        watermarkIsLoading={externalDataWatermarksQuery.isLoading}
        watermarkIsError={externalDataWatermarksQuery.isError}
        seriesIds={latestSeriesIds}
      />

      {macroDepthTab === "curve" ? (
        <div
          data-testid="market-data-macro-tab-curve"
          id="market-data-macro-tab-curve"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-curve"
        >
          <h2 className="market-data-block-title market-data-block-title--flush">收益率曲线</h2>
          <p className="market-data-curve-intro">
            国债、国开与 SHIBOR 近期走势，来自 macro latest 的 recent_points。
          </p>
          {selectableSeries.length > 0 ? (
            <div className="market-data-curve-series-picker" data-testid="market-data-curve-series-picker">
              <div className="market-data-curve-series-picker-actions">
                <Button
                  size="small"
                  type="link"
                  data-testid="market-data-curve-series-reset"
                  disabled={extraSeriesIds.length === 0}
                  onClick={() => setExtraSeriesIds([])}
                >
                  恢复默认
                </Button>
              </div>
              {selectableSeries.slice(0, 8).map((point) => {
                const active = extraSeriesIds.includes(point.series_id);
                const staleSuffix = qualityChipSuffix(point.quality_flag);
                return (
                  <button
                    key={point.series_id}
                    type="button"
                    className={`market-data-curve-series-chip${active ? " market-data-curve-series-chip--active" : ""}`}
                    data-testid={`market-data-curve-series-chip-${point.series_id}`}
                    onClick={() =>
                      setExtraSeriesIds((current) => {
                        if (current.includes(point.series_id)) {
                          return current.filter((id) => id !== point.series_id);
                        }
                        if (current.length >= MAX_EXTRA_SERIES) {
                          return current;
                        }
                        return [...current, point.series_id];
                      })
                    }
                  >
                    {point.series_name}
                    {staleSuffix ? <span className="market-data-curve-series-chip-stale">{staleSuffix}</span> : null}
                  </button>
                );
              })}
            </div>
          ) : null}
          {MARKET_DATA_SHOW_CURVE_META_STRIP ? (
            <LiveResultMetaStrip
              lead="收益率曲线·宏观最新"
              meta={latestQuery.data?.result_meta}
              testId="market-data-curve-live-meta"
            />
          ) : null}
          <MarketDataChartShell
            option={chartOption}
            height={260}
            isLoading={latestQuery.isLoading}
            isError={latestQuery.isError}
            onRetry={() => void latestQuery.refetch()}
            testId="market-data-rate-trend-chart"
            emptyMessage="当前响应中缺少上述利率序列的近期点位，无法绘制走势图。"
          />
          <MarketDataLinkageSummaryBand
            compositeScore={macroBondLinkage.environment_score?.composite_score}
            compositeDetail={
              macroBondLinkage.environment_score?.signal_description
                ? `${macroBondLinkage.environment_score.signal_description} ${LIQUIDITY_COMPOSITE_POLARITY_NOTE}`
                : LIQUIDITY_COMPOSITE_POLARITY_NOTE
            }
            topCorrelation={correlationRows[0] ?? null}
            onOpenSpreads={openSpreadsTab}
            onOpenLinkage={openLinkageTab}
          />
        </div>
      ) : null}

      {macroDepthTab === "spreads" ? (
        <div
          data-testid="market-data-macro-tab-spreads"
          id="market-data-macro-tab-spreads"
          className="market-data-macro-tab-panel market-data-spreads-tab-panel"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-spreads"
        >
          <LiveResultMetaStrip
            lead="信用利差表格·联动读面"
            meta={macroBondLinkageQuery.data?.result_meta}
            testId="market-data-spreads-live-meta"
          />
          <div className="market-data-spreads-layout">
            <div className="market-data-spreads-layout__cards">
              <LinkageSpreadTenorTable slots={spreadSlots} loading={macroBondLinkageQuery.isLoading} />
            </div>
            <div className="market-data-spreads-layout__chart">
              <MarketDataLinkageCorrelationChart
                correlations={correlationRows}
                note={
                  spreadSlots.some((slot) => slot.point)
                    ? "截面相关（3M/6M/1Y 窗口），与上方利差期限槽位同源。"
                    : "截面相关（3M/6M/1Y 窗口）；利差表无数据时回退展示国债/国开相关。"
                }
              />
            </div>
          </div>
        </div>
      ) : null}

      {macroDepthTab === "linkage" ? (
        <div
          data-testid="market-data-macro-tab-linkage"
          id="market-data-macro-tab-linkage"
          className="market-data-macro-tab-panel"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-linkage"
        >
          <p className="market-data-linkage-tab-intro">
            摘要来自 <code>getMacroBondLinkageAnalysis</code> 的 <code>environment_score</code> 与{" "}
            <code>portfolio_impact</code>；完整相关性矩阵仍在下文「宏观-债市联动」折叠区。
          </p>
          <MarketDataLinkageEnvironmentChart
            environmentScore={macroBondLinkage.environment_score}
            derivedSpreads={derivedSpreads}
          />
          <div className="market-data-summary-grid">
            <KpiCard
              title="环境综合分"
              value={
                macroBondLinkage.environment_score?.composite_score != null
                  ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                  : "—"
              }
              detail={`${
                macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分。"
              } ${LIQUIDITY_COMPOSITE_POLARITY_NOTE}`}
              tone={
                macroBondLinkage.environment_score?.composite_score != null
                  ? toneFromSignedNumber(macroBondLinkage.environment_score.composite_score)
                  : "default"
              }
            />
            <KpiCard
              title="流动性分项"
              value={
                macroBondLinkage.environment_score?.liquidity_score != null
                  ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                  : "—"
              }
              detail="流动性正值偏松、负值偏紧；进入综合分时取反。"
              tone={
                macroBondLinkage.environment_score?.liquidity_score != null
                  ? toneFromSignedNumber(macroBondLinkage.environment_score.liquidity_score)
                  : "default"
              }
            />
            <KpiCard
              title="利率方向"
              value={macroBondLinkage.environment_score?.rate_direction ?? "—"}
              detail={
                macroBondLinkage.environment_score?.rate_direction_score != null
                  ? `方向评分 ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                  : "缺少方向评分。"
              }
              valueVariant="text"
            />
            <KpiCard
              title="组合影响合计"
              value={formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}
              detail="结构化情景下的总影响估计（展示字段，不在前端重算）。"
              tone={toneFromSignedDisplayString(
                formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact),
              )}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
