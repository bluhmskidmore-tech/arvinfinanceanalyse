import type { CSSProperties, ReactNode, RefObject } from "react";

import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ExternalDataWatermarkLedger,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  LivermoreStrategyPayload,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  MacroVendorSeries,
  MarketDataBondFuturesRankingsPayload,
  MarketDataCoverageSummaryPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  ResultMeta,
  TushareSupplementPayload,
} from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { LiveResultMetaStrip } from "./LiveResultMetaStrip";
import { MarketDataLinkageBusinessDetail } from "./MarketDataLinkageBusinessDetail";
import { MarketDataLivermoreBusinessDetail } from "./MarketDataLivermoreBusinessDetail";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";
import "./MarketDataDetailDeck.css";

type ResultMetaItem = {
  key: string;
  label: string;
  meta: ResultMeta | undefined;
};

type DetailQueryKey =
  | "catalog"
  | "formalRates"
  | "macroLatest"
  | "fxFormal"
  | "fxAnalytical"
  | "ncd"
  | "bondFutures"
  | "coverage"
  | "linkage"
  | "livermore"
  | "watermarks"
  | "tushare"
  | "supply";

type DetailStatusMap = Record<DetailQueryKey, boolean>;

type CreditSegment = "both" | "mtn" | "urban";

type CreditSpreadSlot = {
  tenor: string;
  point: MacroBondLinkageTopCorrelation | null;
};

export type MarketDataDetailDeckProps = {
  detailRef: RefObject<HTMLDivElement>;
  catalog: readonly MacroVendorSeries[];
  formalRateSeries: readonly ChoiceMacroLatestPoint[];
  formalDerivedSpreads: ChoiceMacroLatestPayload["derived_spreads"];
  formalUseBlocked: boolean;
  latestSeries: readonly ChoiceMacroLatestPoint[];
  macroDerivedSpreads: ChoiceMacroLatestPayload["derived_spreads"];
  fxFormalStatus: FxFormalStatusPayload | null | undefined;
  fxAnalytical: FxAnalyticalPayload | null | undefined;
  ncdFundingProxy: NcdFundingProxyPayload | null | undefined;
  bondFutures: MarketDataBondFuturesRankingsPayload | null | undefined;
  coverageSummary: MarketDataCoverageSummaryPayload | null | undefined;
  linkage: MacroBondLinkagePayload | null | undefined;
  creditSegment: CreditSegment;
  creditSpreadSlots: readonly CreditSpreadSlot[];
  livermore: LivermoreStrategyPayload | null | undefined;
  watermarks: ExternalDataWatermarkLedger | null | undefined;
  tushare: TushareSupplementPayload | null | undefined;
  supplyEvents: readonly ResearchCalendarEvent[];
  resultMeta: readonly ResultMetaItem[];
  loading: DetailStatusMap;
  error: DetailStatusMap;
  watermarksAccessDenied: boolean;
};

const NCD_TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

function formatNumber(value: number | null | undefined, fractionDigits = 2) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(fractionDigits);
}

function formatPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)}%`;
}

function tierLabel(value: MacroVendorSeries["refresh_tier"]) {
  if (value === "stable") return "稳定";
  if (value === "fallback") return "降级";
  if (value === "isolated") return "隔离";
  return "未分类";
}

function freshnessLabel(value: string | null | undefined) {
  if (value === "fresh") return "新鲜";
  if (value === "stale") return "陈旧";
  if (value === "expired") return "过期";
  return "未知";
}

function directionLabel(value: string | null | undefined) {
  if (value === "positive") return "正向";
  if (value === "negative") return "负向";
  if (value === "neutral") return "中性";
  return value ?? "—";
}

function countBy<T>(rows: readonly T[], select: (row: T) => string | null | undefined) {
  return rows.reduce<Record<string, number>>((counts, row) => {
    const key = select(row) || "unknown";
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

function formalMarketCategory(catalogRow: MacroVendorSeries | undefined): string {
  const tags = new Set((catalogRow?.tags ?? []).map((tag) => tag.toLowerCase()));
  if (tags.has("commodity")) return "商品";
  if (tags.has("equity")) return "股票与指数";
  if (tags.has("fx")) return "外汇";
  if (
    tags.has("rates")
    || tags.has("liquidity")
    || tags.has("shibor")
    || tags.has("ncd")
    || catalogRow?.theme === "money_market"
  ) return "利率与流动性";
  if (tags.has("crisis_score") || catalogRow?.theme === "crisis_score_inputs") return "风险指标";
  if (tags.has("macro")) return "宏观";
  if (catalogRow?.theme) return `其他 · ${catalogRow.theme}`;
  return "未分类";
}

function Sparkline({ values }: { values: readonly number[] }) {
  if (values.length < 2) {
    return <span className="market-data-detail-deck__spark-empty">—</span>;
  }
  const width = 88;
  const height = 24;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - 2 - ((value - min) / range) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const rising = values[values.length - 1] >= values[0];
  return (
    <svg
      className="market-data-detail-deck__spark"
      viewBox={`0 0 ${width} ${height}`}
      aria-label={`${values.length} 个观察点`}
      role="img"
    >
      <polyline points={points} data-tone={rising ? "up" : "down"} />
    </svg>
  );
}

function QueryState({
  loading,
  error,
  empty,
  errorText,
  emptyText,
  testId,
}: {
  loading: boolean;
  error: boolean;
  empty: boolean;
  errorText: string;
  emptyText: string;
  testId: string;
}) {
  if (error) {
    return (
      <div className="market-data-detail-deck__state" data-state="error" data-testid={testId}>
        {errorText}
      </div>
    );
  }
  if (loading && empty) {
    return (
      <div className="market-data-detail-deck__state" data-state="loading" data-testid={testId}>
        数据加载中…
      </div>
    );
  }
  if (empty) {
    return (
      <div className="market-data-detail-deck__state" data-state="empty" data-testid={testId}>
        {emptyText}
      </div>
    );
  }
  return null;
}

function ScrollTable({
  headers,
  children,
  testId,
  tall = false,
}: {
  headers: readonly string[];
  children: ReactNode;
  testId: string;
  tall?: boolean;
}) {
  return (
    <div
      className={`market-data-detail-deck__scroll-panel${tall ? " market-data-detail-deck__scroll-panel--tall" : ""}`}
    >
      <table className="market-data-tushare-table" data-testid={testId}>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function MetricRail({ values }: { values: ChoiceMacroLatestPayload["derived_spreads"] }) {
  if (!values || Object.keys(values).length === 0) return null;
  return (
    <div className="market-data-detail-deck__metric-rail">
      {Object.entries(values).map(([key, value]) => (
        <span key={key}>
          <small>{key}</small>
          <strong style={tabularNumsStyle}>{formatNumber(value, 3)}</strong>
        </span>
      ))}
    </div>
  );
}

function PositionBar({
  longValue,
  shortValue,
}: {
  longValue: number | null | undefined;
  shortValue: number | null | undefined;
}) {
  const long = Math.max(0, longValue ?? 0);
  const short = Math.max(0, shortValue ?? 0);
  const total = Math.max(long + short, 1);
  return (
    <span
      className="market-data-detail-deck__position-bar"
      aria-label={`多头 ${formatNumber(longValue, 0)}，空头 ${formatNumber(shortValue, 0)}`}
    >
      <i data-side="long" style={{ width: `${(long / total) * 100}%` }} />
      <i data-side="short" style={{ width: `${(short / total) * 100}%` }} />
    </span>
  );
}

function CorrelationCell({ value }: { value: number | null | undefined }) {
  const magnitude = value == null ? 0 : Math.min(Math.abs(value), 1);
  return (
    <span
      className="market-data-detail-deck__correlation-cell"
      data-direction={value == null ? "none" : value >= 0 ? "positive" : "negative"}
      style={{ "--market-data-correlation-alpha": String(0.12 + magnitude * 0.5) } as CSSProperties}
    >
      {formatNumber(value, 3)}
    </span>
  );
}

const COVERAGE_SOURCE_PENDING_LABELS: Record<string, string> = {
  cash_bond_trades: "现券成交",
  credit_trades: "信用成交",
  bond_futures: "国债期货",
  tushare_supplement: "补充数据",
  ncd_proxy: "存单代理",
};

function coverageSectionLabel(key: string, fallbackLabel: string): string {
  return COVERAGE_SOURCE_PENDING_LABELS[key] ?? fallbackLabel;
}

function FormalRatesCard({
  rows,
  catalog,
  derivedSpreads,
  formalUseBlocked,
  loading,
  error,
}: {
  rows: readonly ChoiceMacroLatestPoint[];
  catalog: readonly MacroVendorSeries[];
  derivedSpreads: ChoiceMacroLatestPayload["derived_spreads"];
  formalUseBlocked: boolean;
  loading: boolean;
  error: boolean;
}) {
  const catalogBySeriesId = new Map(catalog.map((row) => [row.series_id, row]));
  const categoryBySeriesId = new Map(
    rows.map((row) => [row.series_id, formalMarketCategory(catalogBySeriesId.get(row.series_id))]),
  );
  const categoryCounts = countBy(rows, (row) => categoryBySeriesId.get(row.series_id));
  return (
    <MarketDataSeriesCategoryCard
      title={formalUseBlocked ? "市场序列（正式使用受限）" : "正式市场全量序列"}
      caption={`${formalUseBlocked ? "formal · blocked · 禁止作为正式口径" : "稳定正式口径"} · 返回 ${rows.length} 条 · 按后端 theme / tags 分为 ${Object.keys(categoryCounts).length} 类 · 派生利差 ${Object.keys(derivedSpreads ?? {}).length} 项`}
      count={rows.length}
      tone={formalUseBlocked ? "analytical" : "formal"}
      testId="market-data-detail-formal-rates-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        errorText="正式市场序列读取失败；未使用分析序列替代。"
        emptyText="正式市场序列当前没有返回业务行。"
        testId="market-data-detail-formal-rates-state"
      />
      <MetricRail values={derivedSpreads} />
      {rows.length > 0 ? (
        <div className="market-data-detail-deck__metric-rail" data-testid="market-data-detail-formal-category-rail">
          {Object.entries(categoryCounts)
            .sort(([left], [right]) => left.localeCompare(right, "zh-CN"))
            .map(([label, count]) => (
              <span key={label}><small>{label}</small><strong>{count} 条</strong></span>
            ))}
        </div>
      ) : null}
      {rows.length > 0 ? (
        <ScrollTable
          tall
          headers={["资产类别", "序列", "最新值", "变动", "走势", "交易日", "单位", "质量"]}
          testId="market-data-detail-formal-rates-table"
        >
          {rows.map((row) => (
            <tr key={row.series_id}>
              <td><span className="market-data-detail-deck__chip">{categoryBySeriesId.get(row.series_id)}</span></td>
              <td><strong>{row.series_name}</strong><small>{row.series_id}</small></td>
              <td style={tabularNumsStyle}>{formatNumber(row.value_numeric, 4)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.latest_change, 4)}</td>
              <td><Sparkline values={(row.recent_points ?? []).map((point) => point.value_numeric)} /></td>
              <td>{row.trade_date}</td>
              <td>{row.unit}</td>
              <td>{row.quality_flag ?? "ok"}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function MacroLatestCard({
  rows,
  derivedSpreads,
  loading,
  error,
}: {
  rows: readonly ChoiceMacroLatestPoint[];
  derivedSpreads: ChoiceMacroLatestPayload["derived_spreads"];
  loading: boolean;
  error: boolean;
}) {
  const tiers = countBy(rows, (row) => row.refresh_tier);
  return (
    <MarketDataSeriesCategoryCard
      title="市场与宏观全量观察"
      caption={`稳定 ${tiers.stable ?? 0} · 降级 ${tiers.fallback ?? 0} · 隔离 ${tiers.isolated ?? 0} · 未分类 ${tiers.unknown ?? 0}`}
      count={rows.length}
      tone="analytical"
      testId="market-data-detail-macro-latest-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        errorText="市场与宏观观察读取失败；当前没有以演示值替代。"
        emptyText="市场与宏观观察当前没有返回业务行。"
        testId="market-data-detail-macro-latest-state"
      />
      <MetricRail values={derivedSpreads} />
      {rows.length > 0 ? (
        <ScrollTable
          tall
          headers={["序列", "最新值", "变动", "走势", "交易日", "层级", "读取策略"]}
          testId="market-data-detail-macro-latest-table"
        >
          {rows.map((row) => (
            <tr key={row.series_id}>
              <td><strong>{row.series_name}</strong><small>{row.series_id}</small></td>
              <td style={tabularNumsStyle}>{formatNumber(row.value_numeric, 4)} {row.unit}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.latest_change, 4)}</td>
              <td><Sparkline values={(row.recent_points ?? []).map((point) => point.value_numeric)} /></td>
              <td>{row.trade_date}</td>
              <td>
                <span className="market-data-detail-deck__chip" data-tier={row.refresh_tier ?? "unknown"}>
                  {tierLabel(row.refresh_tier)}
                </span>
              </td>
              <td>{row.fetch_mode ?? "—"} / {row.fetch_granularity ?? "—"}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function CatalogCard({
  rows,
  loading,
  error,
}: {
  rows: readonly MacroVendorSeries[];
  loading: boolean;
  error: boolean;
}) {
  const tiers = countBy(rows, (row) => row.refresh_tier);
  return (
    <MarketDataSeriesCategoryCard
      title="正式目录与刷新策略"
      caption={`正式目录只保留 stable：稳定 ${tiers.stable ?? 0} · 其他 ${rows.length - (tiers.stable ?? 0)}`}
      count={rows.length}
      tone="formal"
      testId="market-data-detail-catalog-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        errorText="正式目录读取失败。"
        emptyText="正式目录当前没有返回条目。"
        testId="market-data-detail-catalog-state"
      />
      {rows.length > 0 ? (
        <ScrollTable
          tall
          headers={["序列", "供应商", "频率 / 单位", "层级", "读取策略", "策略说明"]}
          testId="market-data-detail-catalog-table"
        >
          {rows.map((row) => (
            <tr key={row.series_id}>
              <td><strong>{row.series_name}</strong><small>{row.series_id}</small></td>
              <td>{row.vendor_name}<small>{row.vendor_version}</small></td>
              <td>{row.frequency} / {row.unit}</td>
              <td>
                <span className="market-data-detail-deck__chip" data-tier={row.refresh_tier ?? "unknown"}>
                  {tierLabel(row.refresh_tier)}
                </span>
              </td>
              <td>{row.fetch_mode ?? "—"} / {row.fetch_granularity ?? "—"}</td>
              <td>{row.policy_note ?? "—"}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function NcdCard({
  payload,
  loading,
  error,
}: {
  payload: NcdFundingProxyPayload | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const rows = payload?.rows ?? [];
  return (
    <MarketDataSeriesCategoryCard
      title="同业存单资金代理"
      caption={`${payload?.proxy_label ?? "资金代理"} · 截至 ${payload?.as_of_date ?? "—"} · 非正式期限×评级矩阵`}
      count={rows.length}
      tone="liquidity"
      testId="market-data-detail-ncd-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        errorText="资金代理读取失败；未生成存单矩阵替代值。"
        emptyText="资金代理当前没有返回期限点位。"
        testId="market-data-detail-ncd-state"
      />
      {rows.length > 0 ? (
        <div className="market-data-detail-deck__ncd-table" data-testid="market-data-detail-ncd-grid">
          <div className="market-data-detail-deck__ncd-head">
            <span>代理行</span>
            {NCD_TENORS.map((tenor) => <span key={tenor}>{tenor}</span>)}
            <span>样本数</span>
          </div>
          {rows.map((row) => (
            <div className="market-data-detail-deck__ncd-row" key={row.row_key}>
              <strong>{row.label}</strong>
              {NCD_TENORS.map((tenor) => (
                <span key={tenor} style={tabularNumsStyle}>{formatPct(row[tenor])}</span>
              ))}
              <span style={tabularNumsStyle}>{row.quote_count ?? "—"}</span>
            </div>
          ))}
        </div>
      ) : null}
      {payload?.formal_ncd_matrix_status ? (
        <dl className="market-data-detail-deck__definition-grid">
          <div><dt>正式矩阵状态</dt><dd>{payload.formal_ncd_matrix_status.status}</dd></div>
          <div><dt>所需形状</dt><dd>{payload.formal_ncd_matrix_status.required_shape}</dd></div>
          <div><dt>当前代理基础</dt><dd>{payload.formal_ncd_matrix_status.current_proxy_basis}</dd></div>
          <div><dt>Choice</dt><dd>{payload.formal_ncd_matrix_status.choice_status}</dd></div>
          <div><dt>Tushare</dt><dd>{payload.formal_ncd_matrix_status.tushare_status}</dd></div>
        </dl>
      ) : null}
      {payload?.warnings.map((warning) => (
        <div className="market-data-detail-deck__state" data-state="warning" key={warning}>{warning}</div>
      ))}
    </MarketDataSeriesCategoryCard>
  );
}

function CoverageCard({
  payload,
  loading,
  error,
}: {
  payload: MarketDataCoverageSummaryPayload | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const sections = payload?.sections ?? [];
  const sourcePendingSections = sections.filter((section) => section.source_pending);
  return (
    <MarketDataSeriesCategoryCard
      title="覆盖契约与缺口"
      caption={payload ? `${payload.headline.readiness_label} · 截至 ${payload.as_of_date ?? "—"}` : "后端治理摘要原样展示"}
      count={sections.length}
      tone="neutral"
      testId="market-data-detail-coverage-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={sections.length === 0}
        errorText="覆盖摘要不可用；页面没有生成替代治理状态。"
        emptyText="覆盖摘要没有返回治理分区。"
        testId="market-data-detail-coverage-state"
      />
      {payload ? (
        <div className="market-data-detail-deck__metric-rail">
          <span><small>分析预警</small><strong>{payload.headline.analytical_warning_count}</strong></span>
          <span><small>待接入</small><strong>{payload.headline.source_pending_count}</strong></span>
          <span><small>代理数据</small><strong>{payload.headline.proxy_only_count}</strong></span>
          <span><small>正式片段</small><strong>{payload.headline.formal_fragment_ready ? "就绪" : "未就绪"}</strong></span>
        </div>
      ) : null}
      {payload ? (
        <div
          className="market-data-detail-deck__state"
          data-state={sourcePendingSections.length > 0 ? "warning" : "ready"}
          data-testid="market-data-source-pending-contract-note"
        >
          {sourcePendingSections.length > 0
            ? `尚未接入：${sourcePendingSections
              .map((section) => coverageSectionLabel(section.key, section.label))
              .join(" / ")}`
            : "当前覆盖摘要未报告待接入业务域。"}
        </div>
      ) : null}
      {sections.length > 0 ? (
        <ScrollTable
          tall
          headers={["业务域", "状态", "口径", "质量 / 降级", "数量", "数据日", "说明"]}
          testId="market-data-detail-coverage-table"
        >
          {sections.map((row) => (
            <tr key={row.key}>
              <td><strong>{row.label}</strong><small>{row.key}</small></td>
              <td>{row.status}</td>
              <td>{row.basis} / {row.formal_use_allowed ? "正式可用" : "非正式"}</td>
              <td>{row.quality_flag} / {row.fallback_mode} / {row.vendor_status}</td>
              <td style={tabularNumsStyle}>{row.row_count ?? row.series_count ?? row.group_count ?? "—"}</td>
              <td>{row.latest_trade_date ?? row.as_of_date ?? "—"}</td>
              <td>{row.message}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
      {payload?.actions.length ? (
        <ul className="market-data-detail-deck__compact-list">
          {payload.actions.map((action) => (
            <li key={action.key}><strong>{action.severity}</strong><span>{action.label}</span></li>
          ))}
        </ul>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function LivermoreCard({
  payload,
  loading,
  error,
}: {
  payload: LivermoreStrategyPayload | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const modules = payload?.module_states ?? [];
  return (
    <MarketDataSeriesCategoryCard
      title="Livermore 策略数据状态"
      caption={`请求 ${payload?.requested_as_of_date ?? "—"} · 实际 ${payload?.as_of_date ?? "—"} · 模块 ${modules.length}`}
      count={modules.length}
      tone="analytical"
      testId="market-data-detail-livermore-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={!payload}
        errorText="策略数据读取失败；没有把降级状态显示成就绪。"
        emptyText="策略数据当前没有返回。"
        testId="market-data-detail-livermore-state"
      />
      {payload ? (
        <>
          <div className="market-data-detail-deck__kpi-row market-data-detail-deck__kpi-row--four">
            <div><span>市场门状态</span><strong>{payload.market_gate.state}</strong></div>
            <div><span>风险敞口</span><strong style={tabularNumsStyle}>{formatNumber(payload.market_gate.exposure, 2)}</strong></div>
            <div><span>通过条件</span><strong style={tabularNumsStyle}>{payload.market_gate.passed_conditions}/{payload.market_gate.available_conditions}</strong></div>
            <div><span>数据缺口</span><strong style={tabularNumsStyle}>{payload.data_gaps.length}</strong></div>
          </div>
          <ScrollTable
            headers={["模块", "状态", "展示方式", "数据日", "原因"]}
            testId="market-data-detail-livermore-modules-table"
          >
            {modules.map((module) => (
              <tr key={module.key}>
                <td>{module.key}</td>
                <td>{module.state}</td>
                <td>{module.render_mode}</td>
                <td>{module.source_date ?? "—"}</td>
                <td>{module.reasons.join("；") || "—"}</td>
              </tr>
            ))}
          </ScrollTable>
          <div className="market-data-detail-deck__split">
            <div>
              <h4>规则准备度</h4>
              <ul className="market-data-detail-deck__compact-list">
                {payload.rule_readiness.map((item) => (
                  <li key={item.key}><strong>{item.title}</strong><span>{item.status} · {item.summary}</span></li>
                ))}
              </ul>
            </div>
            <div>
              <h4>诊断与数据缺口</h4>
              <ul className="market-data-detail-deck__compact-list">
                {payload.diagnostics.map((item) => (
                  <li key={`${item.code}-${item.message}`}><strong>{item.severity} · {item.code}</strong><span>{item.message}</span></li>
                ))}
                {payload.data_gaps.map((item) => (
                  <li key={`${item.input_family}-${item.input ?? "all"}`}><strong>{item.input_family} · {item.status}</strong><span>{item.evidence}</span></li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function FxCard({
  formal,
  analytical,
  loadingFormal,
  errorFormal,
  loadingAnalytical,
  errorAnalytical,
}: {
  formal: FxFormalStatusPayload | null | undefined;
  analytical: FxAnalyticalPayload | null | undefined;
  loadingFormal: boolean;
  errorFormal: boolean;
  loadingAnalytical: boolean;
  errorAnalytical: boolean;
}) {
  const formalRows = formal?.rows ?? [];
  const groups = analytical?.groups ?? [];
  const analyticalCount = groups.reduce((total, group) => total + group.series.length + (group.events?.length ?? 0), 0);
  return (
    <MarketDataSeriesCategoryCard
      title="外汇正式状态与分析分组"
      caption={`正式 ${formalRows.length}/${formal?.candidate_count ?? "—"} · 分析组 ${groups.length} · 分析行 ${analyticalCount}`}
      count={formalRows.length + analyticalCount}
      tone="analytical"
      testId="market-data-detail-fx-card"
    >
      <div className="market-data-detail-deck__stack">
        <section data-testid="market-data-fx-formal-collapse" data-expanded="true">
          <QueryState
            loading={loadingFormal}
            error={errorFormal}
            empty={formalRows.length === 0}
            errorText="正式外汇状态读取失败。"
            emptyText="正式外汇状态当前没有返回候选行。"
            testId="market-data-detail-fx-formal-state"
          />
          {formalRows.length > 0 ? (
            <div data-testid="market-data-fx-formal-table">
              <ScrollTable
                headers={["货币对", "中间价", "交易日 / 观察日", "营业日 / 顺延", "来源", "状态"]}
                testId="market-data-detail-fx-formal-table"
              >
                {formalRows.map((row) => (
                  <tr key={row.series_id}>
                    <td><strong>{row.pair_label}</strong><small>{row.series_id}</small></td>
                    <td style={tabularNumsStyle}>{formatNumber(row.mid_rate, 4)}</td>
                    <td>{row.trade_date ?? "—"} / {row.observed_trade_date ?? "—"}</td>
                    <td>{row.is_business_day == null ? "—" : row.is_business_day ? "营业日" : "非营业日"} / {row.is_carry_forward ? "顺延" : "未顺延"}</td>
                    <td>{row.source_name ?? "—"} / {row.vendor_name ?? "—"}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </ScrollTable>
            </div>
          ) : null}
        </section>
        <QueryState
          loading={loadingAnalytical}
          error={errorAnalytical}
          empty={groups.length === 0}
          errorText="分析外汇读取失败；没有使用正式外汇行替代。"
          emptyText="分析外汇当前没有返回分组。"
          testId="market-data-detail-fx-analytical-state"
        />
        {groups.map((group) => (
          <section className="market-data-detail-deck__group-card" key={group.group_key}>
            <header>
              <div><strong>{group.title}</strong><span>{group.description}</span></div>
              <em>{group.series.length} 条序列 · {group.events?.length ?? 0} 条事件</em>
            </header>
            {group.series.length > 0 ? (
              <ScrollTable
                headers={["序列", "最新值", "变动", "走势", "交易日", "层级 / 质量"]}
                testId={`market-data-detail-fx-group-${group.group_key}`}
              >
                {group.series.map((row) => (
                  <tr key={row.series_id}>
                    <td><strong>{row.series_name}</strong><small>{row.series_id}</small></td>
                    <td style={tabularNumsStyle}>{formatNumber(row.value_numeric, 4)} {row.unit}</td>
                    <td style={tabularNumsStyle}>{formatNumber(row.latest_change, 4)}</td>
                    <td><Sparkline values={(row.recent_points ?? []).map((point) => point.value_numeric)} /></td>
                    <td>{row.trade_date}</td>
                    <td>{tierLabel(row.refresh_tier)} / {row.quality_flag ?? "—"}</td>
                  </tr>
                ))}
              </ScrollTable>
            ) : null}
            {group.events?.length ? (
              <ScrollTable
                headers={["日期 / 时间", "国家 / 币种", "事件", "公布 / 前值 / 预期"]}
                testId={`market-data-detail-fx-events-${group.group_key}`}
              >
                {group.events.map((row) => (
                  <tr key={row.event_id}>
                    <td>{row.event_date} {row.event_time ?? ""}</td>
                    <td>{row.country ?? "—"} / {row.currency ?? "—"}</td>
                    <td>{row.event}</td>
                    <td>{row.value ?? "—"} / {row.pre_value ?? "—"} / {row.fore_value ?? "—"}</td>
                  </tr>
                ))}
              </ScrollTable>
            ) : null}
          </section>
        ))}
      </div>
    </MarketDataSeriesCategoryCard>
  );
}

function BondFuturesCard({
  payload,
  loading,
  error,
}: {
  payload: MarketDataBondFuturesRankingsPayload | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const rows = payload?.rows ?? [];
  return (
    <MarketDataSeriesCategoryCard
      title="国债期货席位排行"
      caption={`${payload?.contract ?? "T.CFE"} · 数据日 ${payload?.as_of_date ?? "—"} · 分析口径`}
      count={rows.length}
      tone="analytical"
      testId="market-data-detail-bond-futures-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        errorText="国债期货席位排行读取失败。"
        emptyText="当前合约没有返回席位排行。"
        testId="market-data-detail-bond-futures-state"
      />
      {rows.length > 0 ? (
        <ScrollTable
          tall
          headers={["排名 / 成员", "成交量 / 变动", "多头 / 变动", "空头 / 变动", "多空结构", "合约 / 市场", "数据日 / 来源"]}
          testId="market-data-detail-bond-futures-table"
        >
          {rows.map((row) => (
            <tr key={`${row.contract}-${row.member_name}-${row.source_row_no ?? "none"}`}>
              <td><strong>{row.source_row_no ?? "—"} · {row.member_name}</strong><small>{row.product_code}</small></td>
              <td style={tabularNumsStyle}>{formatNumber(row.volume, 0)} / {formatNumber(row.volume_change, 0)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.long_holding, 0)} / {formatNumber(row.long_change, 0)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.short_holding, 0)} / {formatNumber(row.short_change, 0)}</td>
              <td><PositionBar longValue={row.long_holding} shortValue={row.short_holding} /></td>
              <td>{row.contract} / {row.exchange}</td>
              <td>{row.trade_date} / {row.source_vendor}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
      {payload?.warnings.map((warning) => (
        <div className="market-data-detail-deck__state" data-state="warning" key={warning}>{warning}</div>
      ))}
    </MarketDataSeriesCategoryCard>
  );
}

type CorrelationTrack = {
  key: string;
  label: string;
  rows: readonly MacroBondLinkageTopCorrelation[];
};

function correlationRowIdentity(row: MacroBondLinkageTopCorrelation): string {
  return JSON.stringify([
    row.series_id,
    row.target_family,
    row.target_tenor,
    row.target_yield,
    row.correlation_3m,
    row.correlation_6m,
    row.correlation_1y,
    row.lead_lag_days,
    row.alignment_mode,
    row.effective_observation_span_days,
  ]);
}

function correlationRowsMatch(
  left: readonly MacroBondLinkageTopCorrelation[],
  right: readonly MacroBondLinkageTopCorrelation[],
): boolean {
  if (left.length !== right.length) return false;
  const rightRows = new Set(right.map(correlationRowIdentity));
  return left.every((row) => rightRows.has(correlationRowIdentity(row)));
}

function LinkageCard({
  payload,
  creditSegment,
  creditSpreadSlots,
  loading,
  error,
}: {
  payload: MacroBondLinkagePayload | null | undefined;
  creditSegment: CreditSegment;
  creditSpreadSlots: readonly CreditSpreadSlot[];
  loading: boolean;
  error: boolean;
}) {
  const conservativeRows = payload?.method_variants?.conservative.top_correlations ?? [];
  const conservativeMatchesTop = payload
    ? correlationRowsMatch(payload.top_correlations, conservativeRows)
    : false;
  const tracks: CorrelationTrack[] = payload
    ? [
        {
          key: "top",
          label: conservativeMatchesTop && conservativeRows.length > 0
            ? "主相关 / 保守对齐"
            : "主相关",
          rows: payload.top_correlations,
        },
        { key: "spread", label: "利差期限", rows: payload.spread_tenor_correlations ?? [] },
        ...(!conservativeMatchesTop
          ? [{ key: "conservative", label: "保守对齐", rows: conservativeRows }]
          : []),
        { key: "market-timing", label: "市场时点", rows: payload.method_variants?.market_timing.top_correlations ?? [] },
      ].filter((track) => track.rows.length > 0)
    : [];
  const rowCount = tracks.reduce((total, track) => total + track.rows.length, 0);
  const visibleCreditSlots = creditSpreadSlots.filter(
    (slot): slot is CreditSpreadSlot & { point: MacroBondLinkageTopCorrelation } =>
      slot.point !== null,
  );
  const creditSegmentLabel = creditSegment === "mtn"
    ? "中票"
    : creditSegment === "urban"
      ? "城投"
      : "全部信用";
  return (
    <MarketDataSeriesCategoryCard
      title="宏债联动与相关性"
      caption={`${payload?.report_date ?? "—"} · 相关行 ${rowCount} · 研究视图 ${payload?.research_views?.length ?? 0} · 传导轴 ${payload?.transmission_axes?.length ?? 0}`}
      count={rowCount}
      tone="analytical"
      testId="market-data-detail-linkage-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={!payload}
        errorText="宏债联动读取失败；没有生成替代相关性。"
        emptyText="宏债联动当前没有返回结果。"
        testId="market-data-detail-linkage-state"
      />
      {payload ? (
        <div className="market-data-detail-deck__stack">
          <div className="market-data-detail-deck__kpi-row">
            <div><span>综合分数</span><strong style={tabularNumsStyle}>{formatNumber(payload.environment_score.composite_score, 2)}</strong></div>
            <div><span>利率方向</span><strong>{payload.environment_score.rate_direction ?? "—"}</strong></div>
            <div><span>组合影响</span><strong style={tabularNumsStyle}>{payload.portfolio_impact.total_estimated_impact == null ? "—" : String(payload.portfolio_impact.total_estimated_impact)}</strong></div>
          </div>
          <section
            className="market-data-detail-deck__group-card"
            data-testid="market-data-detail-credit-spread-filtered"
            data-filter={creditSegment}
          >
            <header>
              <strong>信用利差筛选结果</strong>
              <em>{creditSegmentLabel} · {visibleCreditSlots.length} 行</em>
            </header>
            {visibleCreditSlots.length > 0 ? (
              <ScrollTable
                headers={["期限", "序列", "3M", "6M", "1Y", "领先滞后"]}
                testId="market-data-detail-credit-spread-filtered-table"
              >
                {visibleCreditSlots.map((slot) => (
                  <tr key={`${creditSegment}-${slot.tenor}-${slot.point.series_id}`}>
                    <td>{slot.tenor}</td>
                    <td>
                      <strong>{slot.point.series_name}</strong>
                      <small>{slot.point.series_id} · {slot.point.target_family}</small>
                    </td>
                    <td><CorrelationCell value={slot.point.correlation_3m} /></td>
                    <td><CorrelationCell value={slot.point.correlation_6m} /></td>
                    <td><CorrelationCell value={slot.point.correlation_1y} /></td>
                    <td style={tabularNumsStyle}>{slot.point.lead_lag_days} 天</td>
                  </tr>
                ))}
              </ScrollTable>
            ) : (
              <div className="market-data-detail-deck__state" data-state="empty">
                当前信用分层没有对应的利差相关行。
              </div>
            )}
          </section>
          {tracks.map((track) => (
            <section className="market-data-detail-deck__group-card" key={track.key}>
              <header><strong>{track.label}</strong><em>{track.rows.length} 行</em></header>
              <ScrollTable
                headers={["序列 / 目标", "3M", "6M", "1Y", "方向", "领先滞后", "样本 / 置信度", "有效观察跨度", "对齐"]}
                testId={`market-data-detail-linkage-${track.key}-table`}
              >
                {track.rows.map((row, index) => (
                  <tr key={`${track.key}-${row.series_id}-${row.target_family}-${row.target_tenor ?? "none"}-${index}`}>
                    <td>
                      <strong>{row.series_name}</strong>
                      <small>{row.series_id} · {row.target_family} / {row.target_tenor ?? row.target_yield ?? "—"}</small>
                    </td>
                    <td><CorrelationCell value={row.correlation_3m} /></td>
                    <td><CorrelationCell value={row.correlation_6m} /></td>
                    <td><CorrelationCell value={row.correlation_1y} /></td>
                    <td>{directionLabel(row.direction)}</td>
                    <td style={tabularNumsStyle}>{row.lead_lag_days} 天</td>
                    <td style={tabularNumsStyle}>{row.sample_size ?? "—"} / {formatNumber(row.lead_lag_confidence, 3)}</td>
                    <td style={tabularNumsStyle}>
                      {row.effective_observation_span_days == null
                        ? "—"
                        : `${row.effective_observation_span_days} 天`}
                    </td>
                    <td>{row.alignment_mode ?? "—"}{row.winsorized ? " · winsor" : ""}{row.zscore_applied ? " · z-score" : ""}</td>
                  </tr>
                ))}
              </ScrollTable>
            </section>
          ))}
        </div>
      ) : null}
    </MarketDataSeriesCategoryCard>
  );
}

function WatermarksSupplyCard({
  watermarks,
  supplyEvents,
  loadingWatermarks,
  errorWatermarks,
  watermarksAccessDenied,
  loadingSupply,
  errorSupply,
}: {
  watermarks: ExternalDataWatermarkLedger | null | undefined;
  supplyEvents: readonly ResearchCalendarEvent[];
  loadingWatermarks: boolean;
  errorWatermarks: boolean;
  watermarksAccessDenied: boolean;
  loadingSupply: boolean;
  errorSupply: boolean;
}) {
  const entries = watermarks?.entries ?? [];
  const freshness = countBy(entries, (row) => row.freshness_tier);
  return (
    <MarketDataSeriesCategoryCard
      title="数据水位与供给事件"
      caption={`水位 ${entries.length} · 新鲜 ${freshness.fresh ?? 0} · 陈旧 ${freshness.stale ?? 0} · 过期 ${freshness.expired ?? 0} · 供给 ${supplyEvents.length}`}
      count={entries.length + supplyEvents.length}
      tone="liquidity"
      testId="market-data-detail-watermark-card"
    >
      <div className="market-data-detail-deck__stack">
        <QueryState
          loading={loadingWatermarks}
          error={errorWatermarks}
          empty={entries.length === 0}
          errorText={watermarksAccessDenied ? "当前账号缺少数据水位读取权限；没有把受限结果显示成空数据。" : "数据水位读取失败；没有把异常显示成正常。"}
          emptyText="数据水位当前没有返回条目。"
          testId="market-data-detail-watermark-state"
        />
        {watermarks ? (
          <div className="market-data-detail-deck__metric-rail">
            <span><small>目录</small><strong>{watermarks.summary.catalog_count}</strong></span>
            <span><small>可用</small><strong>{watermarks.summary.available_count}</strong></span>
            <span><small>无数据</small><strong>{watermarks.summary.no_data_count}</strong></span>
            <span><small>不可用</small><strong>{watermarks.summary.unavailable_count}</strong></span>
            <span><small>最近入仓</small><strong>{watermarks.summary.last_successful_ingest ?? "—"}</strong></span>
          </div>
        ) : null}
        {entries.length > 0 ? (
          <ScrollTable
            tall
            headers={["序列", "域 / 来源", "频率 / 单位", "行数", "业务日 / 装载时间", "年龄", "新鲜度", "数据状态"]}
            testId="market-data-detail-watermark-table"
          >
            {entries.map((entry) => (
              <tr key={`${entry.series_id}-${entry.vendor_name}`}>
                <td><strong>{entry.series_name}</strong><small>{entry.series_id}</small></td>
                <td>{entry.domain} / {entry.source_family} / {entry.vendor_name}</td>
                <td>{entry.frequency ?? "—"} / {entry.unit ?? "—"}</td>
                <td style={tabularNumsStyle}>{entry.row_count}</td>
                <td>{entry.latest_business_date ?? "—"} / {entry.latest_loaded_at ?? "—"}</td>
                <td style={tabularNumsStyle}>{entry.age_days ?? "—"} 天</td>
                <td><span className="market-data-detail-deck__chip" data-freshness={entry.freshness_tier ?? "unknown"}>{freshnessLabel(entry.freshness_tier)}</span></td>
                <td>{entry.data_status}{entry.error_message ? ` · ${entry.error_message}` : ""}</td>
              </tr>
            ))}
          </ScrollTable>
        ) : null}
        <QueryState
          loading={loadingSupply}
          error={errorSupply}
          empty={supplyEvents.length === 0}
          errorText="供给事件读取失败。"
          emptyText="当前没有供给或招标事件。"
          testId="market-data-detail-supply-state"
        />
        {supplyEvents.length > 0 ? (
          <ScrollTable
            headers={["日期", "类型 / 级别", "发行人", "金额", "标题", "说明 / 来源"]}
            testId="market-data-detail-supply-table"
          >
            {supplyEvents.map((event) => (
              <tr key={event.id}>
                <td>{event.date}</td>
                <td>{event.kind} / {event.severity}</td>
                <td>{event.issuer ?? "—"}</td>
                <td>{event.amount_label ?? "—"}</td>
                <td>{event.title}</td>
                <td>
                  {event.note ?? "—"}
                  {event.source_url ? <a href={event.source_url} target="_blank" rel="noreferrer">{event.source_label ?? "查看来源"}</a> : null}
                </td>
              </tr>
            ))}
          </ScrollTable>
        ) : null}
      </div>
    </MarketDataSeriesCategoryCard>
  );
}

function TushareCard({
  payload,
  loading,
  error,
}: {
  payload: TushareSupplementPayload | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const moneyRows = payload?.money_supply_rows ?? [];
  const ecoRows = payload?.eco_cal_rows ?? [];
  const moneyTotal = payload?.money_supply_total_count;
  const ecoTotal = payload?.eco_cal_total_count;
  const moneyCoverage = moneyTotal == null
    ? `${moneyRows.length} 个独立月份`
    : `${moneyRows.length}/${moneyTotal} 个独立月份（${payload?.money_supply_truncated ? "仅显示当前窗口" : "已展示全部"}）`;
  const ecoCoverage = ecoTotal == null
    ? `${ecoRows.length} 个独立事件`
    : `${ecoRows.length}/${ecoTotal} 个独立事件（${payload?.eco_cal_truncated ? "仅显示当前窗口" : "已展示全部"}）`;
  return (
    <MarketDataSeriesCategoryCard
      title="货币供给与经济日历"
      caption={`货币供给 ${moneyCoverage} · 经济日历 ${ecoCoverage} · 货币金额及同比/环比单位未随 DTO 返回`}
      count={moneyRows.length + ecoRows.length}
      tone="stable"
      testId="market-data-detail-tushare-card"
    >
      <QueryState
        loading={loading}
        error={error}
        empty={moneyRows.length + ecoRows.length === 0}
        errorText="补充数据读取失败；没有以重复或演示行替代。"
        emptyText="补充数据当前没有返回。"
        testId="market-data-detail-tushare-state"
      />
      {moneyRows.length > 0 ? (
        <ScrollTable
          headers={["月份", "M0（单位未提供）", "M0 同比 / 环比（单位未提供）", "M1（单位未提供）", "M1 同比 / 环比（单位未提供）", "M2（单位未提供）", "M2 同比 / 环比（单位未提供）"]}
          testId="market-data-detail-money-supply-table"
        >
          {moneyRows.map((row) => (
            <tr key={row.month}>
              <td>{row.month}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m0, 2)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m0_yoy, 2)} / {formatNumber(row.m0_mom, 2)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m1, 2)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m1_yoy, 2)} / {formatNumber(row.m1_mom, 2)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m2, 2)}</td>
              <td style={tabularNumsStyle}>{formatNumber(row.m2_yoy, 2)} / {formatNumber(row.m2_mom, 2)}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
      {ecoRows.length > 0 ? (
        <ScrollTable
          tall
          headers={["日期 / 时间", "国家 / 币种", "事件", "公布值", "前值", "预期"]}
          testId="market-data-detail-eco-table"
        >
          {ecoRows.map((row) => (
            <tr key={row.event_id}>
              <td>{row.event_date} {row.event_time ?? ""}</td>
              <td>{row.country ?? "—"} / {row.currency ?? "—"}</td>
              <td>{row.event}</td>
              <td>{row.value ?? "—"}</td>
              <td>{row.pre_value ?? "—"}</td>
              <td>{row.fore_value ?? "—"}</td>
            </tr>
          ))}
        </ScrollTable>
      ) : null}
      {payload?.warnings.map((warning) => (
        <div className="market-data-detail-deck__state" data-state="warning" key={warning}>{warning}</div>
      ))}
    </MarketDataSeriesCategoryCard>
  );
}

function ResultMetaCard({ items }: { items: readonly ResultMetaItem[] }) {
  return (
    <MarketDataSeriesCategoryCard
      title="口径、日期与证据"
      caption={`${items.filter((item) => item.meta).length}/${items.length} 项返回结构化元数据`}
      count={items.length}
      tone="neutral"
      testId="market-data-detail-result-meta-card"
    >
      <div className="market-data-detail-deck__meta-grid" data-testid="market-data-detail-result-meta-grid">
        {items.map((item) => (
          <div className="market-data-detail-deck__meta-item" key={item.key}>
            {item.meta ? (
              <>
                <LiveResultMetaStrip
                  meta={item.meta}
                  testId={`market-data-detail-result-meta-${item.key}`}
                  lead={item.label}
                />
                <details>
                  <summary>计算与证据字段</summary>
                  <dl>
                    <div><dt>规则版本</dt><dd>{item.meta.rule_version}</dd></div>
                    <div><dt>缓存版本</dt><dd>{item.meta.cache_version}</dd></div>
                    <div><dt>生成时间</dt><dd>{item.meta.generated_at}</dd></div>
                    <div><dt>日期基础</dt><dd>{item.meta.date_basis ?? "—"}</dd></div>
                    <div><dt>证据行数</dt><dd>{item.meta.evidence_rows ?? "—"}</dd></div>
                    <div><dt>事实表</dt><dd>{item.meta.tables_used?.join("、") || "—"}</dd></div>
                  </dl>
                </details>
              </>
            ) : (
              <div className="market-data-detail-deck__state" data-state="empty">{item.label}：未返回元数据。</div>
            )}
          </div>
        ))}
      </div>
    </MarketDataSeriesCategoryCard>
  );
}

export function MarketDataDetailDeck({
  detailRef,
  catalog,
  formalRateSeries,
  formalDerivedSpreads,
  formalUseBlocked,
  latestSeries,
  macroDerivedSpreads,
  fxFormalStatus,
  fxAnalytical,
  ncdFundingProxy,
  bondFutures,
  coverageSummary,
  linkage,
  creditSegment,
  creditSpreadSlots,
  livermore,
  watermarks,
  tushare,
  supplyEvents,
  resultMeta,
  loading,
  error,
  watermarksAccessDenied,
}: MarketDataDetailDeckProps) {
  const watermarkStatus = loading.watermarks
    ? "加载中"
    : watermarksAccessDenied
      ? "受限"
      : error.watermarks
        ? "异常"
        : watermarks
          ? String(watermarks.entries.length)
          : "无数据";
  return (
    <div
      ref={detailRef}
      id="market-data-detail-deck"
      className="market-data-section-block market-data-detail-deck"
      data-testid="market-data-detail-deck"
    >
      <header className="market-data-series-category-card__head market-data-detail-deck__head">
        <div className="market-data-series-category-card__titles">
          <span className="market-data-pill-tag market-data-pill-tag--info">明细与证据</span>
          <h2 className="market-data-series-category-card__title">后端数据分类展示</h2>
          <p className="market-data-series-category-card__caption">
            按业务域、口径、数据日期和质量状态展开；滚动表格保留当前返回的全部业务行。
          </p>
        </div>
        <div className="market-data-detail-deck__status-rail">
          <span>正式目录 {catalog.length}</span>
          <span>正式市场 {formalRateSeries.length}</span>
          <span>分析观察 {latestSeries.length}</span>
          <span>水位 {watermarkStatus}</span>
          <span>供给 {supplyEvents.length}</span>
        </div>
      </header>

      <div className="market-data-detail-deck__body">
        <FormalRatesCard
          rows={formalRateSeries}
          catalog={catalog}
          derivedSpreads={formalDerivedSpreads}
          formalUseBlocked={formalUseBlocked}
          loading={loading.formalRates}
          error={error.formalRates}
        />
        <MacroLatestCard rows={latestSeries} derivedSpreads={macroDerivedSpreads} loading={loading.macroLatest} error={error.macroLatest} />
        <CatalogCard rows={catalog} loading={loading.catalog} error={error.catalog} />
        <NcdCard payload={ncdFundingProxy} loading={loading.ncd} error={error.ncd} />
        <CoverageCard payload={coverageSummary} loading={loading.coverage} error={error.coverage} />
        <LivermoreCard payload={livermore} loading={loading.livermore} error={error.livermore} />
        {livermore ? <MarketDataLivermoreBusinessDetail payload={livermore} /> : null}
        <FxCard
          formal={fxFormalStatus}
          analytical={fxAnalytical}
          loadingFormal={loading.fxFormal}
          errorFormal={error.fxFormal}
          loadingAnalytical={loading.fxAnalytical}
          errorAnalytical={error.fxAnalytical}
        />
        <BondFuturesCard payload={bondFutures} loading={loading.bondFutures} error={error.bondFutures} />
        <LinkageCard
          payload={linkage}
          creditSegment={creditSegment}
          creditSpreadSlots={creditSpreadSlots}
          loading={loading.linkage}
          error={error.linkage}
        />
        {linkage ? <MarketDataLinkageBusinessDetail payload={linkage} /> : null}
        <WatermarksSupplyCard
          watermarks={watermarks}
          supplyEvents={supplyEvents}
          loadingWatermarks={loading.watermarks}
          errorWatermarks={error.watermarks}
          watermarksAccessDenied={watermarksAccessDenied}
          loadingSupply={loading.supply}
          errorSupply={error.supply}
        />
        <TushareCard payload={tushare} loading={loading.tushare} error={error.tushare} />
        <ResultMetaCard items={resultMeta} />
      </div>
    </div>
  );
}
