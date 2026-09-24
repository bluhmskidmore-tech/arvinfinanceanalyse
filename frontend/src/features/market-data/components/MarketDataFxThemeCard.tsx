import { useMemo } from "react";

import type { FxAnalyticalEventRow, FxAnalyticalGroup } from "../../../api/contracts";
import { buildMarketDataMultiSeriesTimeChartOption } from "../lib/charts/marketDataSeriesTimeChartOption";
import {
  canRenderMacroThemeChart,
  MACRO_THEME_CHART_MAX_SERIES,
} from "../lib/marketDataMacroThemeGroups";
import { MarketDataChartShell } from "./MarketDataChartShell";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";
import { MarketDataSeriesCompactTable } from "./MarketDataSeriesCompactTable";

type MarketDataFxThemeCardProps = {
  group: FxAnalyticalGroup;
  title: string;
  contextEvents?: readonly FxAnalyticalEventRow[];
};

const FX_CONTEXT_EVENT_LIMIT = 4;
const FX_CONTEXT_CURRENCY_LIMIT = 5;

function formatFxGroupDescription(description: string): string {
  const labels: Record<string, string> = {
    "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.":
      "目录观测到的中间价序列仅作为分析口径，不重定义正式口径。",
    "RMB index / estimate index series stay analytical-only and never flow into formal FX.":
      "人民币指数与估算指数仅作为分析观察，不进入正式外汇口径。",
  };
  if (description === "FX swap / C-Swap series stay analytical-only and never write into formal FX.") {
    return "外汇掉期 / C-Swap 序列仅作为分析观察，不写入正式外汇口径。";
  }
  if (description === "Tushare economic-calendar events for major FX currencies are analytical-only event context.") {
    return "Tushare 经济日历中主要外汇币种相关事件，仅作为外汇分析背景。";
  }
  return labels[description] ?? description;
}

function formatFxEventDate(eventDate: string): string {
  if (/^\d{8}$/.test(eventDate)) {
    return `${eventDate.slice(0, 4)}-${eventDate.slice(4, 6)}-${eventDate.slice(6, 8)}`;
  }
  return eventDate;
}

function isPresentValue(value: string | null | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function formatFxEventValues(event: FxAnalyticalEventRow): string {
  const parts = [
    isPresentValue(event.value) ? `今值 ${event.value}` : null,
    isPresentValue(event.pre_value) ? `前值 ${event.pre_value}` : null,
    isPresentValue(event.fore_value) ? `预测 ${event.fore_value}` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" / ") : "待公布";
}

function MarketDataFxEventList({
  events,
  testId,
}: {
  events: readonly FxAnalyticalEventRow[];
  testId: string;
}) {
  if (events.length === 0) {
    return null;
  }

  return (
    <div className="market-data-fx-event-list" data-testid={testId}>
      {events.map((event) => (
        <article
          key={event.event_id}
          className="market-data-fx-event-item"
          data-testid={`market-data-fx-event-${event.event_id}`}
          data-quality={event.quality_flag ?? "warning"}
        >
          <div className="market-data-fx-event-item__meta">
            <span>{formatFxEventDate(event.event_date)}</span>
            {event.event_time ? <span>{event.event_time}</span> : null}
            {event.currency ? (
              <span className="market-data-fx-event-item__currency">{event.currency}</span>
            ) : null}
            {event.country ? <span>{event.country}</span> : null}
          </div>
          <div className="market-data-fx-event-item__title">{event.event}</div>
          <div className="market-data-fx-event-item__values">{formatFxEventValues(event)}</div>
        </article>
      ))}
    </div>
  );
}

function summarizeFxEventCurrencies(events: readonly FxAnalyticalEventRow[]) {
  const counts = new Map<string, number>();
  for (const event of events) {
    const key = event.currency?.trim() || "N/A";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, FX_CONTEXT_CURRENCY_LIMIT);
}

function MarketDataFxEventInsight({
  events,
  testId,
}: {
  events: readonly FxAnalyticalEventRow[];
  testId: string;
}) {
  if (events.length === 0) {
    return null;
  }

  const currencyCounts = summarizeFxEventCurrencies(events);
  const recentEvents = events.slice(0, FX_CONTEXT_EVENT_LIMIT);

  return (
    <section className="market-data-fx-event-insight" data-testid={testId}>
      <header className="market-data-fx-event-insight__head">
        <strong>事件背景</strong>
        <span>{events.length} 条</span>
      </header>
      <div className="market-data-fx-event-insight__chips" aria-label="外汇事件币种分布">
        {currencyCounts.map(([currency, count]) => (
          <span key={currency}>
            {currency} {count}
          </span>
        ))}
      </div>
      <ul className="market-data-fx-event-insight__list">
        {recentEvents.map((event) => (
          <li key={event.event_id}>
            <span>{formatFxEventDate(event.event_date)}</span>
            <strong>{event.event}</strong>
            <em>{formatFxEventValues(event)}</em>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MarketDataFxThemeCard({
  group,
  title,
  contextEvents = [],
}: MarketDataFxThemeCardProps) {
  const events = group.events ?? [];
  const observationCount = group.series.length + events.length;
  const showThemeChart = canRenderMacroThemeChart(group.series);
  const chartOption = useMemo(
    () =>
      showThemeChart
        ? buildMarketDataMultiSeriesTimeChartOption(group.series.slice(0, MACRO_THEME_CHART_MAX_SERIES))
        : null,
    [group.series, showThemeChart],
  );
  const testId = `market-data-fx-group-card-${group.group_key}`;

  return (
    <MarketDataSeriesCategoryCard
      title={title}
      caption={formatFxGroupDescription(group.description)}
      count={observationCount}
      tone="analytical"
      showLinkTierTag={false}
      testId={testId}
    >
      {showThemeChart ? (
        <div className="market-data-macro-theme-card__chart" data-testid={`${testId}-chart`}>
          <MarketDataChartShell
            option={chartOption}
            height={180}
            testId={`${testId}-multi-series-chart`}
            emptyMessage="该外汇主题暂无可绘制的近期走势。"
          />
        </div>
      ) : null}
      {group.series.length > 0 ? (
        <MarketDataSeriesCompactTable
          series={group.series}
          testIdPrefix={`market-data-fx-series-${group.group_key}`}
          compactSparseColumns
        />
      ) : null}
      {group.group_key === "fx_index" ? (
        <MarketDataFxEventInsight
          events={contextEvents}
          testId={`${testId}-insight`}
        />
      ) : null}
      <MarketDataFxEventList events={events} testId={`${testId}-events`} />
    </MarketDataSeriesCategoryCard>
  );
}
