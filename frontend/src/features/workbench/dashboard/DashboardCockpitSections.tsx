import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import "./DashboardCockpitSections.css";
import "./dashboardCockpitTheme.css";

import type {
  DashboardCockpitAccountRow,
  DashboardCockpitAnalysisCard,
  DashboardCockpitCalendarItem,
  DashboardCockpitMetricItem,
  DashboardCockpitPortfolioItem,
  DashboardCockpitRiskItem,
  DashboardCockpitTickerItem,
  DashboardCockpitWatchRow,
  DashboardCockpitWaterfallItem,
} from "./dashboardCockpitModel";
import { getDashboardCockpitSectionStatusLabel } from "./dashboardCockpitModel";
import { COCKPIT_CHART_PALETTE } from "./dashboardCockpitVisualTokens";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function toneClass(tone: string): string {
  return `dashboard-cockpit-tone-${tone}`;
}

function statusClass(status: string): string {
  return `dashboard-cockpit-status-${status}`;
}

function parseDisplayNumber(value: string): number | null {
  const normalized = value.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  if (!normalized) return null;
  const parsed = Number(normalized[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

type MiniChartPoint = {
  x: number;
  y: number;
};

const MINI_CHART_WIDTH = 720;
const MINI_CHART_HEIGHT = 132;
const MINI_CHART_PLOT_HEIGHT = 118;

function buildMiniChartCoordinates(
  values: readonly number[],
  width = MINI_CHART_WIDTH,
  height = MINI_CHART_PLOT_HEIGHT,
): MiniChartPoint[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;

  return values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / spread) * (height - 22) - 11;
      return { x, y };
    });
}

function serializeMiniChartPoints(points: readonly MiniChartPoint[]): string {
  return points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
}

function buildMiniChartArea(points: readonly MiniChartPoint[], height = MINI_CHART_PLOT_HEIGHT): string {
  if (points.length === 0) return "";
  const baseline = height - 4;
  const first = points[0];
  const last = points[points.length - 1];
  return [
    `${first.x.toFixed(1)},${baseline.toFixed(1)}`,
    serializeMiniChartPoints(points),
    `${last.x.toFixed(1)},${baseline.toFixed(1)}`,
  ].join(" ");
}

const PORTFOLIO_COLORS = COCKPIT_CHART_PALETTE;
const CURVE_SERIES_IDS = new Set([
  "CA.CN_GOV_10Y",
  "E1000180",
  "EMM00166466",
  "EMM00166502",
  "CA.DR007",
  "M002",
  "EMM00167613",
]);

function buildDonutGradient(
  items: Array<{ value: number; color: string }>,
): string {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) {
    return "conic-gradient(#e6edf6 0deg 360deg)";
  }

  let cursor = 0;
  const segments = items.map((item) => {
    const start = cursor;
    const end = cursor + (item.value / total) * 360;
    cursor = end;
    return `${item.color} ${start.toFixed(1)}deg ${end.toFixed(1)}deg`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}

function formatChartAxisValue(value: number): string {
  const absValue = Math.abs(value);
  if (absValue >= 100) return value.toFixed(0);
  if (absValue >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

type DashboardCockpitMarketTickerProps = {
  items: readonly DashboardCockpitTickerItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  className?: string;
};

export function DashboardCockpitMarketTicker({
  items,
  isLoading,
  isError,
  onRetry,
  className,
}: DashboardCockpitMarketTickerProps) {
  const hasStale = items.some((item) => item.status === "stale");
  const statusLabel = isLoading
    ? "载入中"
    : isError
      ? "暂不可用"
      : hasStale
        ? "含最近交易日"
        : items.length > 0
          ? "同日行情"
          : "暂无数据";

  return (
    <section
      data-testid="dashboard-cockpit-market-ticker"
      className={cx("dashboard-cockpit-card dashboard-cockpit-market-ticker", className)}
    >
      <div className="dashboard-cockpit-strip-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">市场行情</span>
          <h2 className="dashboard-cockpit-title">行情横条</h2>
        </div>
        <span className={cx("dashboard-cockpit-badge", hasStale && "dashboard-cockpit-badge--warning")}>
          {statusLabel}
        </span>
      </div>

      {isError ? (
        <div
          data-testid="dashboard-cockpit-market-ticker-unavailable"
          className="dashboard-cockpit-empty"
        >
          <div>
            <strong>市场数据暂不可用</strong>
            <span>不使用替代数字，行情不进入本日判断。</span>
          </div>
          <button type="button" className="dashboard-cockpit-link-button" onClick={onRetry}>
            重试
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="dashboard-cockpit-empty">
          <span>{isLoading ? "行情读面载入中。" : "当前没有可展示的行情读面。"}</span>
        </div>
      ) : (
        <div data-testid="dashboard-cockpit-market-ticker-items" className="dashboard-cockpit-market-ticker__grid">
          {items.map((item) => (
            <article
              key={item.id}
              data-testid={`dashboard-cockpit-market-ticker-${item.id}`}
              className={cx(
                "dashboard-cockpit-market-ticker__item",
                statusClass(item.status),
                toneClass(item.tone),
              )}
            >
              <span className="dashboard-cockpit-market-ticker__label-line">
                <span className="dashboard-cockpit-label">{item.label}</span>
                {item.unitLabel ? <span className="dashboard-cockpit-unit">{item.unitLabel}</span> : null}
              </span>
              <strong className="dashboard-cockpit-number">{item.value}</strong>
              <span className="dashboard-cockpit-delta">{item.delta}</span>
              <span className="dashboard-cockpit-date">
                {item.status === "stale" ? "最近交易日 " : "交易日 "}
                {item.tradeDate}
              </span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type DashboardCockpitMetricRailProps = {
  items: readonly DashboardCockpitMetricItem[];
  className?: string;
};

export function DashboardCockpitMetricRail({
  items,
  className,
}: DashboardCockpitMetricRailProps) {
  return (
    <section
      data-testid="dashboard-cockpit-metric-rail"
      className={cx("dashboard-cockpit-card dashboard-cockpit-metric-rail", className)}
    >
      {items.map((item) => (
        <article
          key={item.id}
          data-testid={`dashboard-cockpit-metric-${item.id}`}
          className={cx(
            "dashboard-cockpit-metric-rail__item",
            statusClass(item.status),
            toneClass(item.tone),
          )}
        >
          <span className="dashboard-cockpit-label">{item.label}</span>
          <strong className="dashboard-cockpit-number">{item.value}</strong>
          <span className="dashboard-cockpit-delta">{item.delta ?? getDashboardCockpitSectionStatusLabel(item.status)}</span>
          <span className="dashboard-cockpit-hint">{item.hint}</span>
        </article>
      ))}
    </section>
  );
}

type DashboardCockpitMainGridProps = {
  ticker: readonly DashboardCockpitTickerItem[];
  cards: readonly DashboardCockpitAnalysisCard[];
  waterfall: readonly DashboardCockpitWaterfallItem[];
  className?: string;
};

export function DashboardCockpitMainGrid({
  ticker,
  cards,
  waterfall,
  className,
}: DashboardCockpitMainGridProps) {
  return (
    <section
      data-testid="dashboard-cockpit-main-grid"
      className={cx("dashboard-cockpit-main-grid", className)}
    >
      <DashboardCockpitCurvePanel ticker={ticker} />
      <DashboardCockpitJudgmentCards cards={cards} />
      <DashboardCockpitWaterfall items={waterfall} />
    </section>
  );
}

function DashboardCockpitCurvePanel({ ticker }: { ticker: readonly DashboardCockpitTickerItem[] }) {
  const curveItems = ticker.filter((item) => CURVE_SERIES_IDS.has(item.id));
  const rateItems = (curveItems.length >= 2 ? curveItems : ticker).slice(0, 6);
  const chartItems = rateItems
    .map((item) => ({ item, numericValue: parseDisplayNumber(item.value) }))
    .filter((entry): entry is { item: DashboardCockpitTickerItem; numericValue: number } =>
      entry.numericValue !== null,
    );
  const numericValues = chartItems.map((entry) => entry.numericValue);
  const valuePoints = buildMiniChartCoordinates(chartItems.map((entry) => entry.numericValue));
  const changePoints = buildMiniChartCoordinates(
    chartItems.map((entry) => parseDisplayNumber(entry.item.delta) ?? 0),
  );
  const valuePolyline = serializeMiniChartPoints(valuePoints);
  const changePolyline = serializeMiniChartPoints(changePoints);
  const valueArea = buildMiniChartArea(valuePoints);
  const lastValuePoint = valuePoints[valuePoints.length - 1] ?? null;
  const lastValue = chartItems[chartItems.length - 1]?.item.value ?? "";
  const minValue = numericValues.length > 0 ? Math.min(...numericValues) : 0;
  const maxValue = numericValues.length > 0 ? Math.max(...numericValues) : 0;
  const midValue = (minValue + maxValue) / 2;
  const axisTicks = [maxValue, midValue, minValue].map(formatChartAxisValue);
  const chartStats = [
    { label: "高", value: formatChartAxisValue(maxValue) },
    { label: "低", value: formatChartAxisValue(minValue) },
    { label: "区间", value: formatChartAxisValue(maxValue - minValue) },
  ];
  const chartSummary = chartItems
    .map(({ item }) => `${item.label} ${item.value} ${item.delta}`)
    .join("；");

  return (
    <section data-testid="dashboard-cockpit-curve-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">收益率曲线与日变动</span>
          <h2 className="dashboard-cockpit-title">行情曲线</h2>
        </div>
        <span className="dashboard-cockpit-badge">交易日</span>
      </div>
      {chartItems.length >= 2 ? (
        <div className="dashboard-cockpit-mini-chart" role="img" aria-label={chartSummary}>
          <svg viewBox={`0 0 ${MINI_CHART_WIDTH} ${MINI_CHART_HEIGHT}`} aria-hidden="true">
            <line className="dashboard-cockpit-mini-chart__grid" x1="0" y1="18" x2={MINI_CHART_WIDTH} y2="18" />
            <line className="dashboard-cockpit-mini-chart__grid" x1="0" y1="64" x2={MINI_CHART_WIDTH} y2="64" />
            <line className="dashboard-cockpit-mini-chart__grid" x1="0" y1="110" x2={MINI_CHART_WIDTH} y2="110" />
            <line className="dashboard-cockpit-mini-chart__vgrid" x1="180" y1="12" x2="180" y2="118" />
            <line className="dashboard-cockpit-mini-chart__vgrid" x1="360" y1="12" x2="360" y2="118" />
            <line className="dashboard-cockpit-mini-chart__vgrid" x1="540" y1="12" x2="540" y2="118" />
            <line className="dashboard-cockpit-mini-chart__rule" x1="0" y1="118" x2={MINI_CHART_WIDTH} y2="118" />
            <polygon className="dashboard-cockpit-mini-chart__area" points={valueArea} />
            <polyline
              className="dashboard-cockpit-mini-chart__line dashboard-cockpit-mini-chart__line--value"
              points={valuePolyline}
            />
            <polyline
              className="dashboard-cockpit-mini-chart__line dashboard-cockpit-mini-chart__line--change"
              points={changePolyline}
            />
            {valuePoints.map((point, index) => (
              <g key={`${point.x}-${point.y}-${index}`}>
                <circle
                  className="dashboard-cockpit-mini-chart__dot"
                  cx={point.x.toFixed(1)}
                  cy={point.y.toFixed(1)}
                />
                <title>
                  {chartItems[index]?.item.label} {chartItems[index]?.item.value} / {chartItems[index]?.item.delta}
                </title>
              </g>
            ))}
            {lastValuePoint ? (
              <text
                className="dashboard-cockpit-mini-chart__value-label"
                x={Math.max(588, lastValuePoint.x - 96).toFixed(1)}
                y={Math.max(14, lastValuePoint.y - 8).toFixed(1)}
              >
                {lastValue}
              </text>
            ) : null}
          </svg>
          <div className="dashboard-cockpit-mini-chart__stats" aria-hidden="true">
            {chartStats.map((stat) => (
              <span key={stat.label}>
                {stat.label}
                <strong>{stat.value}</strong>
              </span>
            ))}
          </div>
          <div className="dashboard-cockpit-mini-chart__legend">
            <span>
              <i className="dashboard-cockpit-mini-chart__legend-dot dashboard-cockpit-mini-chart__legend-dot--value" />
              数值
            </span>
            <span>
              <i className="dashboard-cockpit-mini-chart__legend-dot dashboard-cockpit-mini-chart__legend-dot--change" />
              日变动
            </span>
          </div>
          <div className="dashboard-cockpit-mini-chart__axis">
            {chartItems.map(({ item }) => (
              <span key={item.id}>{item.label}</span>
            ))}
          </div>
          <div className="dashboard-cockpit-mini-chart__y-axis" aria-hidden="true">
            {axisTicks.map((tick, index) => (
              <span key={`${tick}-${index}`}>{tick}</span>
            ))}
          </div>
        </div>
      ) : null}
      <div className="dashboard-cockpit-curve-list">
        {rateItems.length === 0 ? (
          <p className="dashboard-cockpit-muted">缺少行情读面，不展示替代曲线。</p>
        ) : (
          rateItems.map((item) => (
            <div key={item.id} className={cx("dashboard-cockpit-curve-row", toneClass(item.tone))}>
              <span className="dashboard-cockpit-label">{item.label}</span>
              <strong>{item.value}</strong>
              <span>{item.delta}</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function DashboardCockpitJudgmentCards({ cards }: { cards: readonly DashboardCockpitAnalysisCard[] }) {
  return (
    <section data-testid="dashboard-cockpit-judgment-cards" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">利率 / 曲线 / 信用 / 资金</span>
          <h2 className="dashboard-cockpit-title">判断矩阵</h2>
        </div>
        <span className="dashboard-cockpit-badge">同日报告</span>
      </div>
      <div className="dashboard-cockpit-judgment-cards__grid">
        {cards.map((card) => (
          <article
            key={card.id}
            data-testid={`dashboard-cockpit-judgment-card-${card.id}`}
            className={cx(
              "dashboard-cockpit-judgment-card",
              statusClass(card.status),
              toneClass(card.tone),
            )}
          >
            <div className="dashboard-cockpit-judgment-card__head">
              <h3>{card.title}</h3>
              <span>{card.statusLabel}</span>
            </div>
            <p>{card.detail}</p>
            <div className="dashboard-cockpit-judgment-card__foot">
              <span>{card.primaryLabel}</span>
              <strong>{card.primaryValue}</strong>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DashboardCockpitWaterfall({ items }: { items: readonly DashboardCockpitWaterfallItem[] }) {
  const parsedItems = items.map((item) => ({
    item,
    numericValue: parseDisplayNumber(item.value),
  }));
  const maxAbsValue = Math.max(
    ...parsedItems.map((entry) => Math.abs(entry.numericValue ?? 0)),
    0,
  );

  return (
    <section data-testid="dashboard-cockpit-waterfall" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">收益 / 规模</span>
          <h2 className="dashboard-cockpit-title">经营拆解</h2>
        </div>
        <span className="dashboard-cockpit-badge">经营口径</span>
      </div>
      <div className="dashboard-cockpit-waterfall__bars">
        {parsedItems.map(({ item, numericValue }) => {
          const barWidth =
            numericValue === null || maxAbsValue === 0
              ? 0
              : Math.max(8, Math.round((Math.abs(numericValue) / maxAbsValue) * 100));
          const barHeight =
            numericValue === null || maxAbsValue === 0
              ? 0
              : Math.max(10, Math.round((Math.abs(numericValue) / maxAbsValue) * 76));
          const isNegative = numericValue !== null && numericValue < 0;

          return (
            <article
              key={item.id}
              className={cx(
                "dashboard-cockpit-waterfall__bar",
                isNegative && "dashboard-cockpit-waterfall__bar--negative",
                numericValue === null && "dashboard-cockpit-waterfall__bar--empty",
                statusClass(item.status),
                toneClass(item.tone),
              )}
              style={{ "--bar-width": `${barWidth}%`, "--bar-height": `${barHeight}px` } as CSSProperties}
            >
              <span>{item.label}</span>
              <i aria-hidden="true" />
              <strong>{item.value}</strong>
            </article>
          );
        })}
      </div>
    </section>
  );
}

type DashboardCockpitLowerGridProps = {
  portfolioMix: readonly DashboardCockpitPortfolioItem[];
  riskItems: readonly DashboardCockpitRiskItem[];
  calendarItems: readonly DashboardCockpitCalendarItem[];
  watchRows: readonly DashboardCockpitWatchRow[];
  className?: string;
};

export function DashboardCockpitLowerGrid({
  portfolioMix,
  riskItems,
  calendarItems,
  watchRows,
  className,
}: DashboardCockpitLowerGridProps) {
  return (
    <section
      data-testid="dashboard-cockpit-lower-grid"
      className={cx("dashboard-cockpit-lower-grid", className)}
    >
      <DashboardCockpitPortfolioPanel items={portfolioMix} />
      <DashboardCockpitRiskPanel items={riskItems} />
      <DashboardCockpitCalendarPanel items={calendarItems} watchRows={watchRows} />
      <DashboardCockpitWatchTable rows={watchRows} />
    </section>
  );
}

function DashboardCockpitPortfolioPanel({ items }: { items: readonly DashboardCockpitPortfolioItem[] }) {
  const chartItems = items
    .map((item, index) => ({
      item,
      value: parseDisplayNumber(item.value),
      color: PORTFOLIO_COLORS[index % PORTFOLIO_COLORS.length],
    }))
    .filter(
      (entry): entry is { item: DashboardCockpitPortfolioItem; value: number; color: string } =>
        entry.value !== null && entry.value > 0 && entry.item.status !== "blocked",
    );
  const gradient = buildDonutGradient(chartItems);
  const leadItem = chartItems[0]?.item;
  const durationItems = items
    .map((item, index) => ({
      item,
      durationValue: parseDisplayNumber(item.duration),
      color: PORTFOLIO_COLORS[index % PORTFOLIO_COLORS.length],
    }))
    .filter(
      (entry): entry is { item: DashboardCockpitPortfolioItem; durationValue: number; color: string } =>
        entry.durationValue !== null && entry.item.status !== "blocked",
    );
  const maxDuration = Math.max(1, ...durationItems.map((entry) => entry.durationValue));

  return (
    <section data-testid="dashboard-cockpit-portfolio-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">组合结构</span>
          <h2 className="dashboard-cockpit-title">资产分布</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-portfolio-body">
        <div
          data-testid="dashboard-cockpit-portfolio-donut"
          className={cx(
            "dashboard-cockpit-donut",
            chartItems.length === 0 && "dashboard-cockpit-donut--blocked",
          )}
          style={{ "--donut-gradient": gradient } as CSSProperties}
          aria-hidden="true"
        >
          <span>{leadItem?.label ?? "结构"}</span>
          <strong>{leadItem?.value ?? "--"}</strong>
        </div>
        <div className="dashboard-cockpit-portfolio-list">
          <div className="dashboard-cockpit-portfolio-list__head" aria-hidden="true">
            <span>资产</span>
            <span>权重</span>
            <span>市值</span>
            <span>久期</span>
          </div>
          {items.map((item, index) => {
            const swatch = PORTFOLIO_COLORS[index % PORTFOLIO_COLORS.length];
            const mixWidth = Math.max(0, Math.min(100, parseDisplayNumber(item.value) ?? 0));
            return (
              <article key={item.id} className={cx("dashboard-cockpit-portfolio-row", statusClass(item.status))}>
                <i
                  aria-hidden="true"
                  style={{ "--swatch": swatch } as CSSProperties}
                />
                <span className="dashboard-cockpit-portfolio-row__label">{item.label}</span>
                <strong className="dashboard-cockpit-portfolio-row__weight">{item.value}</strong>
                <b
                  className="dashboard-cockpit-portfolio-row__bar"
                  aria-hidden="true"
                  style={{ "--mix-width": `${mixWidth}%`, "--swatch": swatch } as CSSProperties}
                />
                <em className="dashboard-cockpit-portfolio-row__market">{item.marketValue}</em>
                <em className="dashboard-cockpit-portfolio-row__duration">{item.duration}</em>
              </article>
            );
          })}
        </div>
      </div>
      {durationItems.length > 0 ? (
        <div data-testid="dashboard-cockpit-portfolio-duration-band" className="dashboard-cockpit-portfolio-duration-band">
          <div className="dashboard-cockpit-portfolio-duration-band__head">
            <span>久期带</span>
            <em>资产分类对照</em>
          </div>
          <div className="dashboard-cockpit-portfolio-duration-band__rows">
            {durationItems.map(({ item, durationValue, color }) => (
              <article key={item.id}>
                <span>{item.label}</span>
                <b aria-hidden="true">
                  <i
                    style={
                      {
                        "--duration-width": `${Math.max(8, Math.round((durationValue / maxDuration) * 100))}%`,
                        "--swatch": color,
                      } as CSSProperties
                    }
                  />
                </b>
                <strong>{item.duration}</strong>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DashboardCockpitRiskPanel({ items }: { items: readonly DashboardCockpitRiskItem[] }) {
  return (
    <section data-testid="dashboard-cockpit-risk-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">风险监控</span>
          <h2 className="dashboard-cockpit-title">风险摘要</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-risk-grid">
        {items.map((item) => (
          <article
            key={item.id}
            className={cx("dashboard-cockpit-risk-item", statusClass(item.status), toneClass(item.tone))}
            style={{ "--risk-level": `${item.level}%` } as CSSProperties}
          >
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.hint}</em>
            <b className="dashboard-cockpit-risk-item__meter" aria-hidden="true" />
          </article>
        ))}
      </div>
    </section>
  );
}

function DashboardCockpitCalendarPanel({
  items,
  watchRows,
}: {
  items: readonly DashboardCockpitCalendarItem[];
  watchRows: readonly DashboardCockpitWatchRow[];
}) {
  const reviewRows = watchRows.filter((row) => row.status !== "blocked").slice(0, 3);

  return (
    <section
      data-testid="dashboard-cockpit-calendar-panel"
      className="dashboard-cockpit-card dashboard-cockpit-panel dashboard-cockpit-calendar-panel"
    >
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">今日关注</span>
          <h2 className="dashboard-cockpit-title">事件与交易要点</h2>
        </div>
      </div>
      <div
        className={cx(
          "dashboard-cockpit-calendar-list",
          items.length === 0 && "dashboard-cockpit-calendar-list--empty",
        )}
      >
        {items.length === 0 ? (
          <div
            data-testid="dashboard-cockpit-calendar-empty"
            className="dashboard-cockpit-calendar-empty"
          >
            <strong>无同日事件</strong>
            <span>日历仅作上下文，不写入本日判断</span>
            {reviewRows.length > 0 ? (
              <div className="dashboard-cockpit-calendar-review" aria-label="观察清单复核入口">
                <b>转入观察清单</b>
                {reviewRows.map((row) => (
                  <Link key={row.id} className="dashboard-cockpit-calendar-review__link" to={row.route}>
                    <span>{row.name}</span>
                    <em>{row.actionLabel}</em>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          items.map((item) => (
            <article key={item.id} className={cx("dashboard-cockpit-calendar-item", toneClass(item.tone))}>
              <span>{item.time}</span>
              <strong>{item.title}</strong>
              <em>{item.detail}</em>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

type DashboardCockpitAccountTableProps = {
  rows: readonly DashboardCockpitAccountRow[];
  className?: string;
};

export function DashboardCockpitAccountTable({ rows, className }: DashboardCockpitAccountTableProps) {
  return (
    <section
      data-testid="dashboard-cockpit-account-table"
      className={cx(
        "dashboard-cockpit-card",
        "dashboard-cockpit-panel",
        "dashboard-cockpit-account-table",
        "dashboard-home-panel",
        className,
      )}
    >
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">组合 / 资产分层</span>
          <h2 className="dashboard-cockpit-title">账户与暴露摘要</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-account-table__wrap">
        <div className="dashboard-cockpit-account-table__table" role="table">
          <div
            className="dashboard-cockpit-account-table__row dashboard-cockpit-account-table__row--head"
            role="row"
          >
            <span role="columnheader">账户</span>
            <span role="columnheader">分类</span>
            <span role="columnheader">规模</span>
            <span role="columnheader">权重</span>
            <span role="columnheader">久期</span>
            <span role="columnheader">收益率</span>
            <span role="columnheader">日变动</span>
            <span role="columnheader">风险</span>
            <span role="columnheader">来源 / 动作</span>
          </div>
          {rows.map((row) => {
            const change = parseDisplayNumber(row.dailyChange);
            const changeClass =
              change == null
                ? null
                : change > 0
                  ? "dashboard-cockpit-watch__change--positive"
                  : change < 0
                    ? "dashboard-cockpit-watch__change--negative"
                    : "dashboard-cockpit-watch__change--flat";

            return (
              <div
                key={row.id}
                data-testid={`dashboard-cockpit-account-row-${row.id}`}
                className={cx(
                  "dashboard-cockpit-account-table__row",
                  statusClass(row.status),
                  toneClass(row.tone),
                )}
                role="row"
              >
                <strong role="cell">{row.accountName}</strong>
                <span role="cell">{row.segment}</span>
                <span role="cell">{row.exposure}</span>
                <span role="cell">{row.weight}</span>
                <span role="cell">{row.duration}</span>
                <span role="cell">{row.ytm}</span>
                <span className={cx("dashboard-cockpit-account-table__change", changeClass)} role="cell">
                  {row.dailyChange}
                </span>
                <span role="cell">{row.risk}</span>
                <span className="dashboard-cockpit-account-table__action-cell" role="cell" title={row.source}>
                  <span>{row.source}</span>
                  <Link className="dashboard-cockpit-watch__action" to={row.route}>
                    {row.actionLabel}
                  </Link>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function DashboardCockpitWatchTable({ rows }: { rows: readonly DashboardCockpitWatchRow[] }) {
  return (
    <section data-testid="dashboard-cockpit-watch-table" className="dashboard-cockpit-card dashboard-cockpit-panel dashboard-cockpit-watch">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">重点债券 / 品种观察</span>
          <h2 className="dashboard-cockpit-title">观察清单</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-watch__table" role="table">
        <div className="dashboard-cockpit-watch__row dashboard-cockpit-watch__row--head" role="row">
          <span role="columnheader">对象</span>
          <span role="columnheader">名称</span>
          <span role="columnheader">久期/期限</span>
          <span role="columnheader">收益率</span>
          <span role="columnheader">变动</span>
          <span role="columnheader">评级</span>
          <span role="columnheader">动作</span>
        </div>
        {rows.map((row) => {
          const change = parseDisplayNumber(row.dailyChange);
          const changeClass =
            change == null
              ? null
              : change > 0
                ? "dashboard-cockpit-watch__change--positive"
                : change < 0
                  ? "dashboard-cockpit-watch__change--negative"
                  : "dashboard-cockpit-watch__change--flat";

          return (
            <div
              key={row.id}
              className={cx("dashboard-cockpit-watch__row", statusClass(row.status))}
              role="row"
            >
              <span role="cell">{row.code}</span>
              <strong role="cell">{row.name}</strong>
              <span role="cell">{row.maturity}</span>
              <span role="cell">{row.yieldValue}</span>
              <span className={cx("dashboard-cockpit-watch__change", changeClass)} role="cell">
                {row.dailyChange}
              </span>
              <span className="dashboard-cockpit-watch__rating" role="cell">
                {row.rating}
              </span>
              <span className="dashboard-cockpit-watch__reason" role="cell" title={row.reason}>
                <span>{row.reason}</span>
                <Link className="dashboard-cockpit-watch__action" to={row.route}>
                  {row.actionLabel}
                </Link>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
