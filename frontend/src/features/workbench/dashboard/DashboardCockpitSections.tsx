import type { CSSProperties } from "react";

import type {
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

function buildMiniChartPoints(values: readonly number[], width = 360, height = 118): string {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;

  return values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / spread) * (height - 22) - 11;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

type DashboardCockpitMarketTickerProps = {
  items: readonly DashboardCockpitTickerItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

export function DashboardCockpitMarketTicker({
  items,
  isLoading,
  isError,
  onRetry,
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
      className="dashboard-cockpit-card dashboard-cockpit-market-ticker"
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
              <span className="dashboard-cockpit-label">{item.label}</span>
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
};

export function DashboardCockpitMetricRail({ items }: DashboardCockpitMetricRailProps) {
  return (
    <section
      data-testid="dashboard-cockpit-metric-rail"
      className="dashboard-cockpit-card dashboard-cockpit-metric-rail"
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
};

export function DashboardCockpitMainGrid({
  ticker,
  cards,
  waterfall,
}: DashboardCockpitMainGridProps) {
  return (
    <section data-testid="dashboard-cockpit-main-grid" className="dashboard-cockpit-main-grid">
      <DashboardCockpitCurvePanel ticker={ticker} />
      <DashboardCockpitJudgmentCards cards={cards} />
      <DashboardCockpitWaterfall items={waterfall} />
    </section>
  );
}

function DashboardCockpitCurvePanel({ ticker }: { ticker: readonly DashboardCockpitTickerItem[] }) {
  const rateItems = ticker.slice(0, 6);
  const chartItems = rateItems
    .map((item) => ({ item, numericValue: parseDisplayNumber(item.value) }))
    .filter((entry): entry is { item: DashboardCockpitTickerItem; numericValue: number } =>
      entry.numericValue !== null,
    );
  const chartPoints = buildMiniChartPoints(chartItems.map((entry) => entry.numericValue));

  return (
    <section data-testid="dashboard-cockpit-curve-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">收益率曲线与日变动</span>
          <h2 className="dashboard-cockpit-title">行情曲线</h2>
        </div>
        <span className="dashboard-cockpit-badge">trade_date</span>
      </div>
      {chartItems.length >= 2 ? (
        <div className="dashboard-cockpit-mini-chart" aria-hidden="true">
          <svg viewBox="0 0 360 132" role="img">
            <line x1="0" y1="18" x2="360" y2="18" />
            <line x1="0" y1="64" x2="360" y2="64" />
            <line x1="0" y1="110" x2="360" y2="110" />
            <polyline points={chartPoints} />
            {chartPoints.split(" ").map((point, index) => {
              const [x, y] = point.split(",");
              return <circle key={`${point}-${index}`} cx={x} cy={y} r="3.4" />;
            })}
          </svg>
          <div className="dashboard-cockpit-mini-chart__axis">
            {chartItems.map(({ item }) => (
              <span key={item.id}>{item.label}</span>
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
          <h2 className="dashboard-cockpit-title">本日判断组</h2>
        </div>
        <span className="dashboard-cockpit-badge">按契约准入</span>
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
          <span className="dashboard-cockpit-eyebrow">收益/规模归因</span>
          <h2 className="dashboard-cockpit-title">经营贡献拆解</h2>
        </div>
        <span className="dashboard-cockpit-badge">非正式损益归因</span>
      </div>
      <div className="dashboard-cockpit-waterfall__bars">
        {parsedItems.map(({ item, numericValue }) => {
          const barWidth =
            numericValue === null || maxAbsValue === 0
              ? 0
              : Math.max(8, Math.round((Math.abs(numericValue) / maxAbsValue) * 100));

          return (
          <article
            key={item.id}
            className={cx("dashboard-cockpit-waterfall__bar", statusClass(item.status), toneClass(item.tone))}
            style={{ "--bar-width": `${barWidth}%` } as CSSProperties}
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
};

export function DashboardCockpitLowerGrid({
  portfolioMix,
  riskItems,
  calendarItems,
  watchRows,
}: DashboardCockpitLowerGridProps) {
  return (
    <section data-testid="dashboard-cockpit-lower-grid" className="dashboard-cockpit-lower-grid">
      <DashboardCockpitPortfolioPanel items={portfolioMix} />
      <DashboardCockpitRiskPanel items={riskItems} />
      <DashboardCockpitCalendarPanel items={calendarItems} />
      <DashboardCockpitWatchTable rows={watchRows} />
    </section>
  );
}

function DashboardCockpitPortfolioPanel({ items }: { items: readonly DashboardCockpitPortfolioItem[] }) {
  return (
    <section data-testid="dashboard-cockpit-portfolio-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">组合结构</span>
          <h2 className="dashboard-cockpit-title">资产分布</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-portfolio-list">
        {items.map((item) => (
          <article key={item.id} className={cx("dashboard-cockpit-portfolio-row", statusClass(item.status))}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.detail}</em>
          </article>
        ))}
      </div>
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
          >
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.hint}</em>
          </article>
        ))}
      </div>
    </section>
  );
}

function DashboardCockpitCalendarPanel({ items }: { items: readonly DashboardCockpitCalendarItem[] }) {
  return (
    <section data-testid="dashboard-cockpit-calendar-panel" className="dashboard-cockpit-card dashboard-cockpit-panel">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">今日关注</span>
          <h2 className="dashboard-cockpit-title">事件与交易要点</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-calendar-list">
        {items.length === 0 ? (
          <p className="dashboard-cockpit-muted">暂无同源日历上下文。</p>
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

function DashboardCockpitWatchTable({ rows }: { rows: readonly DashboardCockpitWatchRow[] }) {
  return (
    <section data-testid="dashboard-cockpit-watch-table" className="dashboard-cockpit-card dashboard-cockpit-panel dashboard-cockpit-watch">
      <div className="dashboard-cockpit-panel-head">
        <div>
          <span className="dashboard-cockpit-eyebrow">重点债券 / 品种观察</span>
          <h2 className="dashboard-cockpit-title">下钻入口</h2>
        </div>
      </div>
      <div className="dashboard-cockpit-watch__table" role="table">
        <div className="dashboard-cockpit-watch__row dashboard-cockpit-watch__row--head" role="row">
          <span role="columnheader">代码</span>
          <span role="columnheader">名称</span>
          <span role="columnheader">久期/期限</span>
          <span role="columnheader">收益率</span>
          <span role="columnheader">变动</span>
          <span role="columnheader">评级</span>
          <span role="columnheader">关注理由</span>
        </div>
        {rows.map((row) => (
          <div
            key={row.id}
            className={cx("dashboard-cockpit-watch__row", statusClass(row.status))}
            role="row"
          >
            <span role="cell">{row.code}</span>
            <strong role="cell">{row.name}</strong>
            <span role="cell">{row.maturity}</span>
            <span role="cell">{row.yieldValue}</span>
            <span role="cell">{row.dailyChange}</span>
            <span role="cell">{row.rating}</span>
            <span role="cell">{row.reason}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
