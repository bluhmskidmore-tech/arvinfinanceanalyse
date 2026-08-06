import type { CSSProperties, RefObject } from "react";

import type {
  ChoiceNewsEventsPayload,
  ChoiceMacroLatestPoint,
  FxFormalStatusPayload,
  LivermoreStrategyPayload,
  MacroBondLinkagePayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
} from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import { MarketTerminalSparkline } from "../components/MarketTerminalSparkline";
import type {
  MarketDataMoneyMarketRow,
  MarketDataRateQuoteRow,
  MarketDataTerminalRowBase,
  MarketTerminalTickerItem,
} from "../lib/marketDataTerminalModel";
import {
  formatMarketDataFigmaDelta,
  formatMarketDataFigmaValue,
} from "./marketDataFigmaFormat";

import "./marketDataFigmaDesktopView.css";

type MarketDataFigmaDesktopViewProps = {
  watchDate: string;
  statusDate: string | null;
  tickerItems: MarketTerminalTickerItem[];
  rateRows: MarketDataRateQuoteRow[];
  moneyRows: MarketDataMoneyMarketRow[];
  moneySeriesLoading: boolean;
  moneySeriesError: boolean;
  analyticalSubstituteCount: number;
  formalSeriesLoading: boolean;
  formalSeriesError: boolean;
  latestSeries: ChoiceMacroLatestPoint[];
  latestSeriesLoading: boolean;
  latestSeriesError: boolean;
  fxFormalStatus: FxFormalStatusPayload | null | undefined;
  fxFormalLoading: boolean;
  fxFormalError: boolean;
  ncdFundingProxy: NcdFundingProxyPayload | undefined;
  ncdLoading: boolean;
  ncdError: boolean;
  coverageSummary: MarketDataCoverageSummaryPayload | null;
  coverageSections: MarketDataCoverageSection[];
  coverageSummaryState: "loading" | "ready" | "empty" | "error";
  catalogCount: number;
  catalogLoading: boolean;
  catalogError: boolean;
  livermorePayload: LivermoreStrategyPayload | null | undefined;
  livermoreLoading: boolean;
  livermoreError: boolean;
  linkagePayload: MacroBondLinkagePayload | null | undefined;
  linkageLoading: boolean;
  linkageError: boolean;
  newsPayload?: ChoiceNewsEventsPayload | null;
  newsLoading?: boolean;
  newsError?: boolean;
  livermoreRef: RefObject<HTMLDivElement>;
  supplyEvents: ResearchCalendarEvent[];
  supplyLoading: boolean;
  supplyError: boolean;
};

type CoverageTone = "ready" | "watch" | "proxy" | "pending" | "deferred" | "error";

type CoverageItem = {
  key: string;
  label: string;
  tone: CoverageTone;
  statusLabel: string;
  date: string | null;
};

type DatedMarker = {
  key: string;
  label: string;
  date: string;
  tone: "blue" | "green" | "amber";
};

type TapeDisplayItem = {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: "up" | "down" | "flat";
};

const MACRO_SERIES_PRIORITY = [
  "EMM00072301",
  "EMM00087084",
  "EMM00191807",
  "EMM00087085",
  "CA.CSI300",
  "CA.BRENT",
  "CA.COPPER",
  "EMM00058124",
] as const;

const MONEY_ROW_PRIORITY = ["DR001", "DR007", "R007", "OMO", "SHIBOR:3M"] as const;
const NCD_PROXY_TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

const COVERAGE_LABELS: Record<string, string> = {
  formal_rates: "正式市场序列",
  macro_latest: "市场/宏观观察",
  fx_formal: "外汇正式",
  fx_analytical: "外汇分析",
  ncd_proxy: "资金代理",
  bond_futures: "国债期货",
  tushare_supplement: "补充目录",
  cash_bond_trades: "现券成交",
  credit_trades: "信用债成交",
  choice_news: "Choice 资讯",
};

function normalizedDate(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) return null;
  if (/^\d{8}$/.test(trimmed)) {
    return `${trimmed.slice(0, 4)}-${trimmed.slice(4, 6)}-${trimmed.slice(6, 8)}`;
  }
  const isoMatch = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  return isoMatch?.[1] ?? null;
}

function latestDate(values: Array<string | null | undefined>): string | null {
  return values
    .map(normalizedDate)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1) ?? null;
}

function latestChoiceNewsEventDate(
  payload: ChoiceNewsEventsPayload | null | undefined,
): string | null {
  return latestDate(payload?.events.map((event) => event.received_at) ?? []);
}

function shortDate(value: string | null | undefined): string {
  const normalized = normalizedDate(value);
  return normalized ? normalized.slice(5) : "待返回";
}

function rowTruthTone(row: MarketDataTerminalRowBase): "formal" | "analytical" | "restricted" {
  if (row.basis === "formal" && row.formalUseAllowed) return "formal";
  if (row.basis === "formal") return "restricted";
  return "analytical";
}

function rowTruthLabel(row: MarketDataTerminalRowBase): string {
  if (row.basis === "formal") {
    return row.formalUseAllowed ? "正式可用" : "正式受限";
  }
  return row.origin === "macro_latest" ? "分析补位" : "分析观察";
}

function rowQualityLabel(row: MarketDataTerminalRowBase): string {
  const labels: Record<MarketDataTerminalRowBase["qualityFlag"], string> = {
    ok: "正常",
    warning: "需复核",
    stale: "延迟",
    missing: "缺失",
    error: "异常",
    unknown: "待确认",
  };
  return labels[row.qualityFlag];
}

function rowTruthText(row: MarketDataTerminalRowBase): string {
  const parts = [rowTruthLabel(row), shortDate(row.tradeDate), rowQualityLabel(row)];
  if (row.fallbackMode !== "none") parts.push("回退快照");
  if (row.vendorStatus === "vendor_stale") parts.push("供应商延迟");
  if (row.vendorStatus === "vendor_unavailable") parts.push("供应商不可用");
  return parts.join(" · ");
}

function coverageTone(section: MarketDataCoverageSection): CoverageTone {
  if (section.status === "error" || section.quality_flag === "error") return "error";
  if (section.status === "source_pending") return "pending";
  if (section.vendor_status === "vendor_unavailable") return "error";
  if (section.status === "empty") return "watch";
  if (section.status === "deferred") return "deferred";
  if (section.status === "proxy_only" || section.proxy_only) return "proxy";
  if (
    section.status === "warning"
    || section.status === "stale"
    || section.quality_flag !== "ok"
    || section.vendor_status === "vendor_stale"
    || section.fallback_mode !== "none"
  ) return "watch";
  return "ready";
}

function coverageStatusText(tone: CoverageTone): string {
  const labels: Record<CoverageTone, string> = {
    ready: "就绪",
    watch: "观察",
    proxy: "代理",
    pending: "待接入",
    deferred: "按需",
    error: "异常",
  };
  return labels[tone];
}

function buildCoverageItems(input: {
  sections: MarketDataCoverageSection[];
  coverageSummaryState: MarketDataFigmaDesktopViewProps["coverageSummaryState"];
  catalogCount: number;
  catalogLoading: boolean;
  catalogError: boolean;
  livermorePayload: LivermoreStrategyPayload | null | undefined;
  livermoreLoading: boolean;
  livermoreError: boolean;
  linkagePayload: MacroBondLinkagePayload | null | undefined;
  linkageLoading: boolean;
  linkageError: boolean;
  newsPayload?: ChoiceNewsEventsPayload | null;
  newsLoading?: boolean;
  newsError?: boolean;
}): CoverageItem[] {
  const items = input.sections.map((section) => {
    const tone = coverageTone(section);
    return {
      key: section.key,
      label: COVERAGE_LABELS[section.key] ?? section.label,
      tone,
      statusLabel: section.status === "empty"
        ? "无数据"
        : coverageStatusText(tone),
      date: normalizedDate(section.latest_trade_date ?? section.as_of_date),
    };
  });

  if (input.sections.length === 0 && input.coverageSummaryState !== "ready") {
    const tone: CoverageTone = input.coverageSummaryState === "error"
      ? "error"
      : input.coverageSummaryState === "empty"
        ? "watch"
        : "deferred";
    items.push({
      key: "coverage_summary",
      label: "覆盖摘要",
      tone,
      statusLabel: input.coverageSummaryState === "loading"
        ? "加载中"
        : input.coverageSummaryState === "empty"
          ? "无数据"
          : coverageStatusText(tone),
      date: null,
    });
    return items;
  }

  items.push({
    key: "macro_catalog",
    label: "宏观目录",
    tone: input.catalogError
      ? "error"
      : input.catalogLoading
        ? "deferred"
        : input.catalogCount > 0
          ? "ready"
          : "watch",
    statusLabel: input.catalogError
      ? "异常"
      : input.catalogLoading
        ? "加载中"
        : input.catalogCount > 0
          ? "就绪"
          : "无数据",
    date: null,
  });

  const livermoreHasDegradedModule = input.livermorePayload?.module_states.some(
    (module) => module.state !== "ready" || module.render_mode !== "primary",
  ) ?? false;
  const strategyTone: CoverageTone = input.livermoreError
    ? "error"
    : input.livermorePayload
      ? input.livermorePayload.module_states.length > 0 && !livermoreHasDegradedModule
        ? "ready"
        : "watch"
      : "deferred";
  items.push({
    key: "strategy_observation",
    label: "策略观察",
    tone: strategyTone,
    statusLabel: input.livermoreLoading && !input.livermorePayload
      ? "加载中"
      : coverageStatusText(strategyTone),
    date: normalizedDate(input.livermorePayload?.as_of_date),
  });

  const linkageHasEvidence = Boolean(
    input.linkagePayload
      && (
        input.linkagePayload.top_correlations.length > 0
        || (input.linkagePayload.spread_tenor_correlations?.length ?? 0) > 0
        || (input.linkagePayload.research_views?.length ?? 0) > 0
        || (input.linkagePayload.transmission_axes?.length ?? 0) > 0
        || (input.linkagePayload.method_variants?.conservative.top_correlations.length ?? 0) > 0
        || (input.linkagePayload.method_variants?.market_timing.top_correlations.length ?? 0) > 0
      )
  );
  const linkageTone: CoverageTone = input.linkageError
    ? "error"
    : input.linkagePayload
      ? "watch"
      : "deferred";
  items.push({
    key: "macro_bond_linkage",
    label: "宏债链路",
    tone: linkageTone,
    statusLabel: input.linkageLoading && !input.linkagePayload
      ? "加载中"
      : input.linkagePayload && !linkageHasEvidence
        ? "无结果"
        : coverageStatusText(linkageTone),
    date: normalizedDate(input.linkagePayload?.report_date),
  });

  if (input.newsPayload !== undefined || input.newsLoading || input.newsError) {
    const newsTone: CoverageTone = input.newsError
      ? "error"
      : input.newsLoading
        ? "deferred"
        : "watch";
    items.push({
      key: "choice_news",
      label: COVERAGE_LABELS.choice_news,
      tone: newsTone,
      statusLabel: input.newsError
        ? "异常"
        : input.newsLoading
          ? "加载中"
          : (input.newsPayload?.events.length ?? 0) > 0
            ? "分析观察"
            : "无数据",
      date: latestChoiceNewsEventDate(input.newsPayload),
    });
  }

  return items;
}

function selectMacroSeries(series: ChoiceMacroLatestPoint[]): ChoiceMacroLatestPoint[] {
  const byId = new Map(series.map((point) => [point.series_id, point]));
  const prioritized = MACRO_SERIES_PRIORITY.map((id) => byId.get(id)).filter(
    (point): point is ChoiceMacroLatestPoint => Boolean(point),
  );
  if (prioritized.length >= 8) return prioritized.slice(0, 8);
  const seen = new Set(prioritized.map((point) => point.series_id));
  const fallback = series.filter(
    (point) =>
      !seen.has(point.series_id) &&
      point.recent_points &&
      point.recent_points.length >= 2,
  );
  return [...prioritized, ...fallback].slice(0, 8);
}

function shortSeriesLabel(point: ChoiceMacroLatestPoint): string {
  const labels: Record<string, string> = {
    EMM00072301: "CPI 同比",
    EMM00087084: "M1 同比",
    EMM00191807: "社融增速",
    EMM00087085: "M2",
    "CA.CSI300": "沪深300",
    "CA.BRENT": "布伦特",
    "CA.COPPER": "沪铜",
    EMM00058124: "美元中间价",
  };
  const mapped = labels[point.series_id];
  if (mapped) return mapped;
  return point.series_name.replace(/^中国[:：]?/, "").slice(0, 12);
}

function moneyPriority(row: MarketDataMoneyMarketRow): number {
  const haystack = `${row.name} ${row.seriesName}`.toUpperCase();
  const index = MONEY_ROW_PRIORITY.findIndex((keyword) => haystack.includes(keyword));
  return index < 0 ? MONEY_ROW_PRIORITY.length : index;
}

function parseDisplayNumber(value: string): number | null {
  const parsed = Number.parseFloat(value.replace(/[,%]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

const CURVE_TENORS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

function curveChartSeries(rows: MarketDataRateQuoteRow[]) {
  const validRows = rows
    .map((row) => ({
      row,
      value:
        row.sparklineValues.at(-1) ??
        parseDisplayNumber(row.rateText),
      tenorIndex: CURVE_TENORS.indexOf(row.tenor as (typeof CURVE_TENORS)[number]),
    }))
    .filter(
      (item): item is {
        row: MarketDataRateQuoteRow;
        value: number;
        tenorIndex: number;
      } => item.value != null && item.tenorIndex >= 0,
    );
  if (validRows.length === 0) return [];
  const values = validRows.map((item) => item.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 0.01);
  return ["国债", "国开"].flatMap((variety) => {
    const points = validRows
      .filter((item) => item.row.variety === variety)
      .sort((left, right) => left.tenorIndex - right.tenorIndex)
      .map((item) => ({
        ...item,
        x: 50 + (item.tenorIndex * 500) / (CURVE_TENORS.length - 1),
        y: 150 - ((item.value - min) / span) * 92,
      }));
    return points.length > 0 ? [{ variety, points }] : [];
  });
}

function buildTapeItems(
  tickerItems: MarketTerminalTickerItem[],
  latestSeries: ChoiceMacroLatestPoint[],
) {
  const latestById = new Map(latestSeries.map((point) => [point.series_id, point]));
  const desiredTickerItems = [
    tickerItems.find((item) => item.label.includes("10年国债")),
    tickerItems.find((item) => item.label === "DR007"),
  ].filter((item): item is MarketTerminalTickerItem => Boolean(item));
  const fxPoint = latestById.get("EMM00058124");
  const csiPoint = latestById.get("CA.CSI300");
  const csiMovePoint = latestById.get("CA.CSI300_PCT_CHG");
  const crossAssetCandidates: Array<TapeDisplayItem | null> = [
    fxPoint
      ? {
          key: fxPoint.series_id,
          label: "USD/CNY",
          value: formatMarketDataFigmaValue(fxPoint),
          delta: formatMarketDataFigmaDelta(fxPoint),
          tone: (fxPoint.latest_change ?? 0) > 0
            ? "up" as const
            : (fxPoint.latest_change ?? 0) < 0
              ? "down" as const
              : "flat" as const,
        }
      : null,
    csiPoint
      ? {
          key: csiPoint.series_id,
          label: "CSI300",
          value: formatChoiceMacroValue(csiPoint, { spaceBeforeUnit: false }),
          delta: csiMovePoint
            ? formatChoiceMacroValue(csiMovePoint, { spaceBeforeUnit: false })
            : formatChoiceMacroDelta(csiPoint, { spaceBeforeUnit: false, emptyDisplay: "—" }),
          tone: (csiMovePoint?.value_numeric ?? csiPoint.latest_change ?? 0) > 0
            ? "up" as const
            : (csiMovePoint?.value_numeric ?? csiPoint.latest_change ?? 0) < 0
              ? "down" as const
              : "flat" as const,
        }
      : null,
  ];
  const crossAssetItems = crossAssetCandidates.filter(
    (item): item is TapeDisplayItem => item !== null,
  );
  const selected: TapeDisplayItem[] = [
    ...desiredTickerItems.map((item) => {
      const point = latestById.get(item.seriesId);
      return {
        key: item.key,
        label: item.label,
        value: item.value,
        delta: point ? formatMarketDataFigmaDelta(point, item.delta) : item.delta,
        tone: item.tone,
      };
    }),
    ...crossAssetItems,
  ];
  const selectedKeys = new Set(selected.map((item) => item.key));
  for (const item of tickerItems) {
    if (selected.length >= 4) break;
    if (selectedKeys.has(item.key)) continue;
    selected.push({
      key: item.key,
      label: item.label,
      value: item.value,
      delta: item.delta,
      tone: item.tone,
    });
    selectedKeys.add(item.key);
  }
  return selected.slice(0, 4);
}

function SectionHeader({
  eyebrow,
  title,
  state,
}: {
  eyebrow: string;
  title: string;
  state: string;
}) {
  return (
    <header className="market-data-figma-section-header">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      <p>{state}</p>
    </header>
  );
}

function CurvePanel({
  rows,
  loading,
  error,
}: {
  rows: MarketDataRateQuoteRow[];
  loading: boolean;
  error: boolean;
}) {
  const series = curveChartSeries(rows);
  return (
    <section
      className="market-data-figma-data-panel market-data-figma-curve-panel"
      data-testid="market-data-figma-curve-panel"
    >
      <h3>国债与国开曲线</h3>
      <p>1Y–30Y 收益率点位与斜率</p>
      {series.length > 0 ? (
        <svg
          viewBox="0 0 588 189"
          preserveAspectRatio="none"
          role="img"
          aria-label="国债与国开收益率曲线"
        >
          {[56, 82, 108, 134, 160].map((y) => (
            <line key={y} x1="50" x2="558" y1={y} y2={y} className="market-data-figma-grid-line" />
          ))}
          {series.map(({ variety, points }) => (
            <g key={variety} data-variety={variety}>
              <polyline
                points={points.map((point) => `${point.x},${point.y}`).join(" ")}
                className="market-data-figma-curve-line"
              />
              {points.map((point) => (
                <circle
                  key={point.row.key}
                  cx={point.x}
                  cy={point.y}
                  r="3"
                  data-basis={point.row.basis}
                  data-origin={point.row.origin}
                >
                  <title>{`${point.row.variety} ${point.row.tenor} ${point.row.rateText} · ${rowTruthText(point.row)}`}</title>
                </circle>
              ))}
            </g>
          ))}
          {CURVE_TENORS.map((tenor, index) => (
            <text
              key={tenor}
              x={50 + (index * 500) / (CURVE_TENORS.length - 1)}
              y="177"
              textAnchor="middle"
            >
              {tenor}
            </text>
          ))}
        </svg>
      ) : (
        <div className="market-data-figma-empty">
          {loading
            ? "正式市场序列加载中…"
            : error
              ? "正式市场序列读取失败；未使用示例曲线。"
              : "当前筛选下暂无可绘制的曲线点位。"}
        </div>
      )}
      {rows.length > 0 ? (
        <div className="market-data-figma-curve-truth-strip" data-testid="market-data-figma-curve-truth-strip">
          {rows.map((row) => (
            <span
              key={row.key}
              data-testid={`market-data-figma-curve-truth-${row.key}`}
              data-tone={rowTruthTone(row)}
              title={`${row.variety} ${row.tenor} ${row.rateText} · ${rowTruthText(row)}`}
            >
              <b>{row.variety} {row.tenor} {row.rateText}</b>
              {" · "}{rowTruthText(row)}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function FundingPanel({
  rows,
  ncdFundingProxy,
  loading,
  error,
  ncdLoading,
  ncdError,
}: {
  rows: MarketDataMoneyMarketRow[];
  ncdFundingProxy: NcdFundingProxyPayload | undefined;
  loading: boolean;
  error: boolean;
  ncdLoading: boolean;
  ncdError: boolean;
}) {
  const marketRows = [...rows]
    .sort((a, b) => moneyPriority(a) - moneyPriority(b))
    .map((row) => ({
      key: row.key,
      label: row.name,
      valueText: row.rateText,
      value: parseDisplayNumber(row.rateText) ?? 0,
      sparklineValues: row.sparklineValues,
      deltaText: row.deltaText,
      basis: row.basis,
      truthTone: rowTruthTone(row),
      truthText: rowTruthText(row),
    }));
  const proxyRows = (ncdFundingProxy?.rows ?? []).flatMap((row) =>
    NCD_PROXY_TENORS.flatMap((tenor) => {
      const value = row[tenor];
      if (value == null) return [];
      return [{
        key: `${row.row_key}:${tenor}`,
        label: `SHIBOR ${tenor}`,
        valueText: `${value.toFixed(3)}%`,
        value,
        sparklineValues: [value],
        deltaText: "",
        basis: "proxy" as const,
        truthTone: "analytical" as const,
        truthText: ["分析代理", shortDate(ncdFundingProxy?.as_of_date), "需复核"].join(" · "),
      }];
    }),
  );
  const displayRows = [...marketRows, ...proxyRows];
  const values = displayRows.map((row) => row.value);
  const max = Math.max(...values, 1);
  return (
    <section
      className="market-data-figma-data-panel market-data-figma-funding-panel"
      data-testid="market-data-figma-funding-panel"
    >
      <h3>资金利率与同业存单代理</h3>
      <p>资金面最新读数与最近走势</p>
      <div className="market-data-figma-funding-list">
        {displayRows.map((row, index) => {
          const width = Math.max(8, ((values[index] ?? 0) / max) * 100);
          return (
            <div className="market-data-figma-funding-row" data-basis={row.basis} key={row.key}>
              <span title={row.basis === "proxy" ? `${row.label} · NCD 资金代理` : row.label}>
                {row.label}
              </span>
              <small
                data-testid={`market-data-figma-funding-truth-${row.key}`}
                data-tone={row.truthTone}
                title={row.truthText}
              >
                {row.truthText}
              </small>
              <i>
                <b style={{ "--market-data-bar": `${width}%` } as CSSProperties} />
              </i>
              <strong>{row.valueText}</strong>
              <MarketTerminalSparkline
                values={row.sparklineValues}
                tone={row.deltaText.startsWith("-") ? "down" : row.deltaText.startsWith("+") ? "up" : "flat"}
                variant="ticker"
              />
            </div>
          );
        })}
        {displayRows.length === 0 ? (
          <div className="market-data-figma-empty">
            {loading || ncdLoading
              ? "资金面与存单代理加载中…"
              : error || ncdError
                ? "资金面或存单代理读取失败；未使用示例值。"
                : "资金面数据尚未返回。"}
          </div>
        ) : null}
      </div>
      <div className="market-data-figma-proxy-note" data-testid="market-data-figma-ncd-proxy-note">
        {ncdError
          ? "NCD 资金代理读取失败；上方仅展示已返回的资金利率"
          : ncdLoading && !ncdFundingProxy
            ? "NCD 资金代理加载中；上方仅展示已返回的资金利率"
            : ncdFundingProxy?.is_actual_ncd_matrix === true
          ? "同业存单正式矩阵已返回"
          : "NCD 仅作资金代理，不等于正式期限×评级矩阵"}
      </div>
    </section>
  );
}

function MacroPanel({
  series,
  loading,
  error,
}: {
  series: ChoiceMacroLatestPoint[];
  loading: boolean;
  error: boolean;
}) {
  const selected = selectMacroSeries(series);
  return (
    <section className="market-data-figma-data-panel" data-testid="market-data-figma-macro-panel">
      <h3>宏观与跨资产最新序列</h3>
      <p>{selected.length} 个序列的最新值与动量</p>
      <div className="market-data-figma-macro-list">
        {selected.map((point) => (
          <div key={point.series_id} className="market-data-figma-macro-row">
            <span title={point.series_name}>{shortSeriesLabel(point)}</span>
            <strong>{formatMarketDataFigmaValue(point)}</strong>
            <em data-tone={(point.latest_change ?? 0) >= 0 ? "up" : "down"}>
              {formatMarketDataFigmaDelta(point)}
            </em>
            <MarketTerminalSparkline
              values={(point.recent_points ?? []).map((recent) => recent.value_numeric)}
              tone={(point.latest_change ?? 0) >= 0 ? "up" : "down"}
              variant="ticker"
            />
          </div>
        ))}
        {selected.length === 0 ? (
          <div className="market-data-figma-empty">
            {loading
              ? "市场与宏观观察加载中…"
              : error
                ? "市场与宏观观察读取失败；未使用演示值。"
                : "宏观与跨资产序列暂未返回。"}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function FxPanel({
  payload,
  latestSeries,
  loading,
  error,
}: {
  payload: FxFormalStatusPayload | null | undefined;
  latestSeries: ChoiceMacroLatestPoint[];
  loading: boolean;
  error: boolean;
}) {
  const formalRows = payload?.rows ?? [];
  const analyticalUsd = latestSeries.find((point) => point.series_id === "EMM00058124");
  const analyticalUnit = analyticalUsd?.unit?.trim() ?? "";
  return (
    <section className="market-data-figma-data-panel" data-testid="market-data-figma-fx-panel">
      <h3>外汇正式状态与分析序列</h3>
      <p>银行间中间价 / 仅展示已返回数据及最新可用值</p>
      <div className="market-data-figma-fx-grid">
        {formalRows.slice(0, 5).map((row) => (
          <article key={row.series_id} data-tone={row.status === "ok" ? "ready" : "pending"}>
            <span>{row.pair_label}</span>
            <strong>{row.mid_rate == null ? "—" : row.mid_rate.toFixed(4)}</strong>
            <em>{row.status === "ok" ? (row.is_carry_forward ? "沿用" : "正常") : "缺失"}</em>
          </article>
        ))}
        {analyticalUsd ? (
          <article data-tone="analytical">
            <span>
              分析观察
              {analyticalUnit ? ` · ${analyticalUnit}` : ""}
            </span>
            <strong>{analyticalUsd.value_numeric.toFixed(4)}</strong>
            <em>{normalizedDate(analyticalUsd.trade_date) ?? "待返回"}</em>
          </article>
        ) : null}
        {formalRows.length === 0 && !analyticalUsd ? (
          <div className="market-data-figma-empty">
            {loading
              ? "正式外汇状态加载中…"
              : error
                ? "正式外汇状态读取失败；未使用分析序列替代。"
                : "外汇数据暂未返回。"}
          </div>
        ) : null}
      </div>
      {error && (formalRows.length > 0 || analyticalUsd) ? (
        <div className="market-data-figma-proxy-note">
          正式外汇状态读取失败；已返回的分析观察不替代正式状态
        </div>
      ) : null}
    </section>
  );
}

function StrategyPanel({
  payload,
  isLoading,
  isError,
}: {
  payload: LivermoreStrategyPayload | null | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  const metrics = [
    { label: "上升趋势候选", value: payload?.uptrend_momentum_candidates?.items.length ?? null, tone: "cyan" },
    { label: "板块数", value: payload?.sector_rank?.items.length ?? null, tone: "blue" },
    { label: "新趋势", value: payload?.fresh_trend_watchlist?.items.length ?? null, tone: "blue" },
    { label: "均值回归", value: payload?.mean_reversion_candidates?.items.length ?? null, tone: "violet" },
    { label: "因子筛选", value: payload?.factor_screen_candidates?.items.length ?? null, tone: "green" },
    { label: "复合信号", value: payload?.hybrid_fusion_candidates?.items.length ?? null, tone: "amber" },
  ];
  const max = Math.max(...metrics.map((metric) => metric.value ?? 0), 1);
  return (
    <section className="market-data-figma-data-panel" data-testid="market-data-figma-strategy-panel">
      <h3>趋势与信号共振</h3>
      <p>候选、板块、回归与融合信号</p>
      {isError ? (
        <div className="market-data-figma-empty">策略观察加载失败，未使用演示数据替代。</div>
      ) : (
        <div className="market-data-figma-strategy-list" aria-busy={isLoading}>
          {metrics.map((metric) => (
            <div key={metric.label} className="market-data-figma-strategy-row">
              <span>{metric.label}</span>
              <i>
                <b
                  data-tone={metric.tone}
                  style={{
                    "--market-data-bar": metric.value == null ? "0%" : `${Math.max(5, (metric.value / max) * 100)}%`,
                  } as CSSProperties}
                />
              </i>
              <strong>{metric.value == null ? (isLoading ? "…" : "—") : metric.value}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SupplyStatusPanel({
  catalogCount,
  supplyEvents,
  supplyLoading,
  supplyError,
  coverageItems,
  strategyDate,
}: {
  catalogCount: number;
  supplyEvents: ResearchCalendarEvent[];
  supplyLoading: boolean;
  supplyError: boolean;
  coverageItems: CoverageItem[];
  strategyDate: string | null;
}) {
  const latestSupplyDate = latestDate(supplyEvents.map((event) => event.date));
  const pendingLabels = coverageItems
    .filter((item) => item.tone === "pending")
    .map((item) => item.label)
    .slice(0, 3);
  return (
    <section
      className="market-data-figma-data-panel market-data-figma-source-panel"
      data-testid="market-data-figma-supply-panel"
    >
      <h3>接入状态与补充源</h3>
      <dl>
        <div>
          <dt>已就绪</dt>
          <dd>✓ 宏观目录 {catalogCount || "—"} 条{strategyDate ? ` · 策略观察 ${strategyDate}` : ""}</dd>
        </div>
        <div>
          <dt>{supplyError ? "供给记录异常" : supplyLoading ? "供给记录加载中" : "供给记录"}</dt>
          <dd>
            {supplyError
              ? "⚠ 暂未取得供给日历"
              : `△ ${supplyEvents.length || "—"} 条${latestSupplyDate ? ` · 最新 ${latestSupplyDate}` : ""}`}
          </dd>
        </div>
        <div>
          <dt>待接入</dt>
          <dd>△ {pendingLabels.length > 0 ? pendingLabels.join(" / ") : "当前无待接入项"}</dd>
        </div>
      </dl>
    </section>
  );
}

function CoverageMatrix({
  items,
  summaryState,
}: {
  items: CoverageItem[];
  summaryState: MarketDataFigmaDesktopViewProps["coverageSummaryState"];
}) {
  const summaryMessage =
    summaryState === "loading"
      ? "覆盖摘要加载中"
      : summaryState === "error"
        ? "覆盖摘要不可用；不生成替代口径"
        : summaryState === "empty"
          ? "覆盖摘要未返回；不生成替代口径"
          : null;
  return (
    <section className="market-data-figma-coverage-card" data-testid="market-data-figma-coverage-matrix">
      <h3>来源覆盖矩阵</h3>
      <p>业务域覆盖 · 状态取自当前查询与覆盖摘要</p>
      {summaryMessage ? (
        <div
          className="market-data-figma-coverage-summary-state"
          data-testid="market-data-figma-coverage-summary-state"
          data-state={summaryState}
        >
          {summaryMessage}
        </div>
      ) : null}
      <div className="market-data-figma-coverage-grid">
        {items.map((item) => (
          <article
            key={item.key}
            data-testid={`market-data-figma-coverage-${item.key}`}
            data-tone={item.tone}
            title={item.date ? `数据日期 ${item.date}` : item.statusLabel}
          >
            <i />
            <span>{item.label}</span>
            <em>{item.statusLabel}</em>
          </article>
        ))}
      </div>
      <footer>
        <span>● 可读</span>
        <span>◐ 观察 / 代理</span>
        <span>○ 待接入 / 按需</span>
      </footer>
    </section>
  );
}

function FreshnessTimeline({
  coverageSummary,
  coverageItems,
  supplyEvents,
  statusDate,
}: {
  coverageSummary: MarketDataCoverageSummaryPayload | null;
  coverageItems: CoverageItem[];
  supplyEvents: ResearchCalendarEvent[];
  statusDate: string | null;
}) {
  const supplyDate = latestDate(supplyEvents.map((event) => event.date));
  const fxDate = latestDate(
    coverageItems.filter((item) => item.key.startsWith("fx_")).map((item) => item.date),
  );
  const strategyDate = coverageItems.find((item) => item.key === "strategy_observation")?.date ?? null;
  const marketDate = latestDate([
    statusDate,
    ...coverageItems
      .filter((item) => item.key === "formal_rates" || item.key === "macro_latest")
      .map((item) => item.date),
  ]);
  const generatedDate = normalizedDate(coverageSummary?.generated_at);
  const markers: DatedMarker[] = [
    supplyDate ? { key: "supply", label: "供给记录", date: supplyDate, tone: "amber" } : null,
    latestDate([fxDate, strategyDate])
      ? { key: "fx-strategy", label: "外汇 / 策略", date: latestDate([fxDate, strategyDate])!, tone: "blue" }
      : null,
    marketDate ? { key: "market", label: "正式市场 / 分析观察", date: marketDate, tone: "green" } : null,
    generatedDate ? { key: "generated", label: "快照生成", date: generatedDate, tone: "blue" } : null,
  ].filter((marker): marker is DatedMarker => Boolean(marker));

  return (
    <section className="market-data-figma-freshness-card" data-testid="market-data-figma-freshness-panel">
      <h3>更新日期与新鲜度</h3>
      <p>实际业务日期 · 不以前端日期补齐</p>
      <div className="market-data-figma-timeline" data-count={markers.length}>
        <div className="market-data-figma-timeline-axis" />
        {markers.map((marker, index) => (
          <article
            key={marker.key}
            data-tone={marker.tone}
            data-position={index % 2 === 0 ? "bottom" : "top"}
            style={{ "--market-data-marker": `${markers.length <= 1 ? 50 : 8 + (index * 84) / (markers.length - 1)}%` } as CSSProperties}
          >
            <i />
            <time>{shortDate(marker.date)}</time>
            <span>{marker.label}</span>
          </article>
        ))}
      </div>
      <div className="market-data-figma-quality-summary">
        <strong>
          正式市场 {coverageItems.find((item) => item.key === "formal_rates")?.statusLabel ?? "待返回"}
          {" · "}
          分析观察 {coverageItems.find((item) => item.key === "macro_latest")?.statusLabel ?? "待返回"}
        </strong>
        <span>最近观测窗口由后端返回，不前端补齐</span>
      </div>
    </section>
  );
}

function VolumeStateCard({
  catalogCount,
  macroCount,
  ratesCount,
  trendCount,
  supplyCount,
  coverageItems,
  statusDate,
}: {
  catalogCount: number;
  macroCount: number;
  ratesCount: number;
  trendCount: number | null;
  supplyCount: number;
  coverageItems: CoverageItem[];
  statusDate: string | null;
}) {
  const rows = [
    { label: "目录", value: catalogCount },
    { label: "市场/宏观", value: macroCount },
    { label: "利率", value: ratesCount },
    { label: "趋势候选", value: trendCount },
    { label: "供给事件", value: supplyCount },
  ];
  const max = Math.max(...rows.map((row) => row.value ?? 0), 1);
  const readyCount = coverageItems.filter((item) => item.tone === "ready").length;
  const watchCount = coverageItems.filter((item) => item.tone === "watch" || item.tone === "proxy").length;
  const pendingCount = coverageItems.filter((item) => item.tone === "pending").length;
  const deferredCount = coverageItems.filter((item) => item.tone === "deferred").length;
  const errorCount = coverageItems.filter((item) => item.tone === "error").length;
  const total = Math.max(coverageItems.length, 1);
  return (
    <section className="market-data-figma-volume-card" data-testid="market-data-figma-volume-panel">
      <h3>记录量与状态分布</h3>
      <p>截至 {statusDate ?? "待返回"} · 当前返回记录数</p>
      <div className="market-data-figma-volume-list">
        {rows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <i>
              <b
                style={{
                  "--market-data-bar": row.value == null ? "0%" : `${Math.max(4, (row.value / max) * 100)}%`,
                } as CSSProperties}
              />
            </i>
            <strong>{row.value == null ? "—" : row.value}</strong>
          </div>
        ))}
      </div>
      <span className="market-data-figma-state-title">来源状态</span>
      <div className="market-data-figma-state-mix">
        <i style={{ width: `${(readyCount / total) * 100}%` }} />
        <i style={{ width: `${(watchCount / total) * 100}%` }} />
        <i style={{ width: `${(pendingCount / total) * 100}%` }} />
        <i style={{ width: `${(deferredCount / total) * 100}%` }} />
        <i style={{ width: `${(errorCount / total) * 100}%` }} />
      </div>
      <footer>
        可读 {readyCount} · 观察/代理 {watchCount} · 待接入 {pendingCount} · 按需 {deferredCount} · 异常 {errorCount}
      </footer>
    </section>
  );
}

export function MarketDataFigmaDesktopView({
  statusDate,
  tickerItems,
  rateRows,
  moneyRows,
  moneySeriesLoading,
  moneySeriesError,
  analyticalSubstituteCount,
  formalSeriesLoading,
  formalSeriesError,
  latestSeries,
  latestSeriesLoading,
  latestSeriesError,
  fxFormalStatus,
  fxFormalLoading,
  fxFormalError,
  ncdFundingProxy,
  ncdLoading,
  ncdError,
  coverageSummary,
  coverageSections,
  coverageSummaryState,
  catalogCount,
  catalogLoading,
  catalogError,
  livermorePayload,
  livermoreLoading,
  livermoreError,
  linkagePayload,
  linkageLoading,
  linkageError,
  newsPayload,
  newsLoading = false,
  newsError = false,
  livermoreRef,
  supplyEvents,
  supplyLoading,
  supplyError,
}: MarketDataFigmaDesktopViewProps) {
  const coverageItems = buildCoverageItems({
    sections: coverageSections,
    coverageSummaryState,
    catalogCount,
    catalogLoading,
    catalogError,
    livermorePayload,
    livermoreLoading,
    livermoreError,
    linkagePayload,
    linkageLoading,
    linkageError,
    newsPayload,
    newsLoading,
    newsError,
  });
  const readyCount = coverageItems.filter((item) => item.tone === "ready").length;
  const attentionCount = coverageItems.filter(
    (item) => item.tone === "watch" || item.tone === "proxy",
  ).length;
  const pendingCount = coverageItems.filter((item) => item.tone === "pending").length;
  const deferredCount = coverageItems.filter((item) => item.tone === "deferred").length;
  const errorCount = coverageItems.filter((item) => item.tone === "error").length;
  const latestBusinessDate =
    latestDate([
      ...tickerItems.map((item) => item.tradeDate),
      ...rateRows.map((row) => row.tradeDate),
      ...moneyRows.map((row) => row.tradeDate),
      ...latestSeries.map((point) => point.trade_date),
      fxFormalStatus?.latest_trade_date,
      ncdFundingProxy?.as_of_date,
      livermorePayload?.as_of_date,
      ...coverageItems.map((item) => item.date),
    ]) ?? normalizedDate(statusDate);
  const trendCount = livermorePayload?.uptrend_momentum_candidates?.items.length ?? null;
  const tapeItems = buildTapeItems(tickerItems, latestSeries);

  return (
    <div className="market-data-figma-desktop" data-testid="market-data-figma-desktop">
      <main className="market-data-figma-content" data-testid="market-data-figma-content">
        <span
          className="market-data-figma-operational-summary"
          data-testid="market-data-figma-operational-summary"
        >
          截至 {latestBusinessDate ?? "待返回"} · 就绪 {readyCount} · 观察/代理 {attentionCount}
          {" · "}待接入 {pendingCount} · 按需 {deferredCount} · 异常 {errorCount}
        </span>
        <section
          className="market-data-figma-section market-data-figma-tape"
          data-testid="market-data-figma-coverage-tape"
        >
          <SectionHeader
            eyebrow="市场覆盖"
            title="全量覆盖与行情带"
            state={`就绪 ${readyCount} · 观察/代理 ${attentionCount} · 待接入 ${pendingCount} · 按需 ${deferredCount} · 异常 ${errorCount}`}
          />
          <div className="market-data-figma-ticker" data-testid="market-data-figma-ticker">
            {tapeItems.map((item) => (
              <span key={item.key}>
                <b>{item.label}</b> {item.value} <em data-tone={item.tone}>{item.delta}</em>
              </span>
            ))}
            <span><b>市场/宏观</b> {latestSeries.length || "—"}</span>
          </div>
        </section>

        <section className="market-data-figma-section market-data-figma-two-up">
          <SectionHeader
            eyebrow="利率与资金面"
            title="利率曲线与资金面"
            state={
              formalSeriesError
                ? `正式市场序列异常 · 资金面${moneySeriesError ? "异常" : "待核"} · ${analyticalSubstituteCount} 条分析观察 · 存单${ncdError ? "异常" : "为代理"}`
                : moneySeriesError
                  ? `资金面序列异常 · 正式利率${formalSeriesLoading ? "加载中" : "可用"} · 存单${ncdError ? "异常" : "为代理"}`
                  : ncdError
                    ? "存单代理异常 · 正式利率与资金面可用"
                    : formalSeriesLoading || moneySeriesLoading
                      ? "利率/资金序列加载中 · 存单为代理"
                      : analyticalSubstituteCount > 0
                        ? `正式数据 + ${analyticalSubstituteCount} 条分析补位 · 存单为代理`
                        : "正式利率 · 存单为代理"
            }
          />
          <div className="market-data-figma-two-up-grid">
            <CurvePanel rows={rateRows} loading={formalSeriesLoading} error={formalSeriesError} />
            <FundingPanel
              rows={moneyRows}
              ncdFundingProxy={ncdFundingProxy}
              loading={moneySeriesLoading}
              error={moneySeriesError}
              ncdLoading={ncdLoading}
              ncdError={ncdError}
            />
          </div>
        </section>

        <section className="market-data-figma-section market-data-figma-two-up">
          <SectionHeader
            eyebrow="宏观、跨资产与外汇"
            title="市场序列与外汇口径"
            state={`市场/宏观 ${latestSeriesError ? "异常" : latestSeriesLoading ? "加载中" : latestSeries.length || "—"} · 外汇正式 ${fxFormalError ? "异常" : fxFormalLoading ? "加载中" : fxFormalStatus?.materialized_count ?? "—"}`}
          />
          <div className="market-data-figma-two-up-grid">
            <MacroPanel
              series={latestSeries}
              loading={latestSeriesLoading}
              error={latestSeriesError}
            />
            <FxPanel
              payload={fxFormalStatus}
              latestSeries={latestSeries}
              loading={fxFormalLoading}
              error={fxFormalError}
            />
          </div>
        </section>

        <section className="market-data-figma-section market-data-figma-two-up" ref={livermoreRef}>
          <SectionHeader
            eyebrow="扩展市场信号"
            title="策略观察、补充源与终端缺口"
            state={`观察 ${livermorePayload ? 1 : 0} · 待接入 ${pendingCount}`}
          />
          <div className="market-data-figma-two-up-grid">
            <StrategyPanel payload={livermorePayload} isLoading={livermoreLoading} isError={livermoreError} />
            <SupplyStatusPanel
              catalogCount={catalogCount}
              supplyEvents={supplyEvents}
              supplyLoading={supplyLoading}
              supplyError={supplyError}
              coverageItems={coverageItems}
              strategyDate={normalizedDate(livermorePayload?.as_of_date)}
            />
          </div>
        </section>

        <section className="market-data-figma-section market-data-figma-coverage-section">
          <SectionHeader
            eyebrow="数据覆盖与新鲜度"
            title="数据覆盖与更新节奏"
            state={`截至 ${latestBusinessDate ?? "待返回"} · 快照`}
          />
          <div className="market-data-figma-coverage-layout">
            <CoverageMatrix items={coverageItems} summaryState={coverageSummaryState} />
            <FreshnessTimeline
              coverageSummary={coverageSummary}
              coverageItems={coverageItems}
              supplyEvents={supplyEvents}
              statusDate={statusDate}
            />
            <VolumeStateCard
              catalogCount={catalogCount}
              macroCount={latestSeries.length}
              ratesCount={rateRows.length}
              trendCount={trendCount}
              supplyCount={supplyEvents.length}
              coverageItems={coverageItems}
              statusDate={latestBusinessDate}
            />
          </div>
        </section>
      </main>
    </div>
  );
}
