import { useMemo, useState, useCallback, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Collapse, Select, Tabs } from "antd";

import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { FilterBar } from "../../../components/FilterBar";
import {
  PageFilterTray,
  PageHeader,
  PageSectionLead,
  type PageSectionLeadProps,
} from "../../../components/page/PagePrimitives";
import {
  pageInsetCardStyle,
  pageSurfacePanelStyle,
} from "../../../components/page/PagePrimitiveStyles";
import type {
  ChoiceMacroLatestPoint,
  ChoiceMacroRecentPoint,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  ResultMeta,
} from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../workbench/components/KpiCard";
import { toneFromSignedDisplayString, toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { LinkageSpreadTenorTable } from "../components/LinkageSpreadTenorTable";
import { LiveResultMetaStrip } from "../components/LiveResultMetaStrip";
import { MacroLatestReadinessBanner } from "../components/MacroLatestReadinessBanner";
import { MoneyMarketTable } from "../components/MoneyMarketTable";
import { NcdMatrix } from "../components/NcdMatrix";
import { NewsAndCalendar } from "../components/NewsAndCalendar";
import { RateQuoteTable } from "../components/RateQuoteTable";
import {
  buildMarketDataCategoryStore,
  marketCatalogRefreshTier,
  marketSeriesRefreshTier,
  type MarketObservationPoint,
} from "../lib/marketDataCategoryStore";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";

const s = designTokens.space;
const fs = designTokens.fontSize;
const c = designTokens.color;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: s[5],
} as const;

const observationGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: s[5],
  marginTop: s[5],
} as const;

const sectionGridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.6fr) minmax(320px, 1fr)",
  gap: s[6],
  marginTop: s[6],
} as const;

const detailPanelStyle = {
  ...pageSurfacePanelStyle,
  background: "#ffffff",
  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.03)",
} as const;

const macroTabPanelStyle = {
  marginTop: s[2],
} as const;

const rateTrendStateStyle = {
  marginTop: s[4],
  padding: s[5],
  borderRadius: s[4],
  background: "#ffffff",
  fontSize: fs[14],
  display: "grid",
  gap: s[3],
} as const;

const rateTrendEmptyStateStyle = {
  ...rateTrendStateStyle,
  border: `1px dashed ${c.primary[200]}`,
  color: c.neutral[500],
} as const;

const blockTitleStyle = {
  margin: `${s[6]}px 0 0`,
  fontSize: fs[16],
  fontWeight: 600,
  color: c.neutral[900],
} as const;

const macroChartShellStyle = {
  ...detailPanelStyle,
  marginTop: s[5],
  background: "#ffffff",
} as const;

const terminalRowGridStyle = {
  ...observationGridStyle,
  marginTop: 0,
} as const;

const marketSectionBlockStyle = {
  marginTop: 48,
} as const;

const marketSectionInnerBlockStyle = {
  marginTop: s[5],
} as const;

const marketSectionLeadStyle = {
  marginBottom: 24,
} as const;

const marketSectionLeadFlushTopStyle = {
  marginTop: 0,
  marginBottom: 24,
} as const;

function MarketSectionBlock({ children }: { children: ReactNode }) {
  return <div style={marketSectionBlockStyle}>{children}</div>;
}

function MarketSectionInnerBlock({ children }: { children: ReactNode }) {
  return <div style={marketSectionInnerBlockStyle}>{children}</div>;
}

function MarketSectionLead({
  flushTop = false,
  ...props
}: Omit<PageSectionLeadProps, "style"> & { flushTop?: boolean }) {
  return (
    <PageSectionLead
      {...props}
      style={flushTop ? marketSectionLeadFlushTopStyle : marketSectionLeadStyle}
    />
  );
}

const filterLabelStyle = {
  display: "grid",
  gap: s[2],
  fontSize: fs[12],
  fontWeight: 600,
  color: c.neutral[600],
} as const;

const filterControlStyle = {
  width: "100%",
  height: 36,
  padding: `0 ${s[3]}px`,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${c.neutral[300]}`,
  background: "#ffffff",
  fontSize: fs[13],
  color: c.neutral[900],
  outline: "none",
  transition: "border-color 0.2s ease",
} as const;

/** 利率走势：国债 10Y / 国开 5Y / SHIBOR 隔夜（Choice series_id） */
const RATE_TREND_DEFINITIONS = [
  { series_id: "EMM00166466", name: "国债 10Y" },
  { series_id: "EMM00166462", name: "国开 5Y" },
  { series_id: "EMM00166252", name: "SHIBOR 隔夜" },
] as const;

type SpreadTenorSlot = "3Y" | "5Y" | "10Y";

const SPREAD_TENOR_SLOTS: SpreadTenorSlot[] = ["3Y", "5Y", "10Y"];
const TARGET_FAMILY_LABELS: Record<string, string> = {
  treasury: "国债收益率",
  cdb: "国开收益率",
  aaa_credit: "AAA 信用收益率",
  credit_spread: "信用利差",
};

function recentTimelineForMacroPoint(point: ChoiceMacroLatestPoint | undefined) {
  const map = new Map<string, number>();
  if (!point) {
    return map;
  }
  for (const rp of point.recent_points ?? []) {
    map.set(rp.trade_date, rp.value_numeric);
  }
  return map;
}

function buildRateTrendChartOption(series: ChoiceMacroLatestPoint[]): EChartsOption | null {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const dateSet = new Set<string>();
  const maps = RATE_TREND_DEFINITIONS.map((def) => {
    const timeline = recentTimelineForMacroPoint(byId.get(def.series_id));
    for (const d of timeline.keys()) {
      dateSet.add(d);
    }
    return timeline;
  });
  if (dateSet.size === 0) {
    return null;
  }
  let unit = "";
  for (const def of RATE_TREND_DEFINITIONS) {
    const p = byId.get(def.series_id);
    if (p?.unit) {
      unit = p.unit;
      break;
    }
  }
  const categories = [...dateSet].sort((a, b) => a.localeCompare(b));
  const lineSeries = RATE_TREND_DEFINITIONS.map((def, i) => ({
    name: def.name,
    type: "line" as const,
    smooth: true,
    showSymbol: categories.length <= 36,
    connectNulls: true,
    data: categories.map((d) => maps[i].get(d) ?? null),
  }));
  return {
    color: [c.info[500], c.semantic.up, c.warning[400]],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 52, right: 20, top: 28, bottom: 52 },
    xAxis: { type: "category", boundaryGap: false, data: categories },
    yAxis: {
      type: "value",
      scale: true,
      name: unit || undefined,
      axisLabel: { formatter: "{value}" },
    },
    series: lineSeries,
  };
}

function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue =
    typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

function formatRecentPoint(point: ChoiceMacroRecentPoint) {
  return `${point.trade_date} ${point.value_numeric.toFixed(2)}`;
}

function seriesRecentPoints(point: MarketObservationPoint) {
  return point.recent_points ?? [];
}

function seriesPolicyNote(point: MarketObservationPoint) {
  const note = point.policy_note?.trim();
  if (!note) return "分析口径读链路";
  const knownNotes: Record<string, string> = {
    "analytical middle-rate observation only": "仅分析口径中间价观察",
    "analytical index observation only": "仅分析口径指数观察",
    "main refresh date-slice lane": "主刷新日期切片链路",
  };
  return knownNotes[note] ?? note;
}

function seriesFetchModeLabel(point: { fetch_mode?: string | null; fetch_granularity?: string | null }) {
  const fetchMode = point.fetch_mode ?? "date_slice";
  const granularity = point.fetch_granularity ?? "batch";
  const fetchModeLabels: Record<string, string> = {
    date_slice: "日期切片",
    latest: "最新值",
    single_fetch: "单次抓取",
  };
  const granularityLabels: Record<string, string> = {
    batch: "批量",
    single: "单项",
  };
  return `${fetchModeLabels[fetchMode] ?? fetchMode} / ${granularityLabels[granularity] ?? granularity}`;
}

function refreshTierLabel(tier: string) {
  const labels: Record<string, string> = {
    stable: "稳定",
    fallback: "降级",
    isolated: "隔离",
  };
  return labels[tier] ?? tier;
}

function fxAnalyticalGroupTitle(title: string) {
  const labels: Record<string, string> = {
    "Analytical FX: middle-rates": "外汇分析：中间价",
    "Analytical FX: indices": "外汇分析：指数",
  };
  return labels[title] ?? title;
}

function fxAnalyticalGroupDescription(description: string) {
  const labels: Record<string, string> = {
    "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.":
      "目录观察到的中间价序列保留为分析口径视图，不重定义正式口径边界。",
    "RMB index / estimate index series stay analytical-only and never flow into formal FX.":
      "人民币指数和估算指数序列保留为分析口径，不流入正式外汇读面。",
  };
  return labels[description] ?? description;
}

function correlationStrength(point: MacroBondLinkageTopCorrelation) {
  return Math.max(
    Math.abs(point.correlation_1y ?? 0),
    Math.abs(point.correlation_6m ?? 0),
    Math.abs(point.correlation_3m ?? 0),
  );
}

function familyLabel(targetFamily: string) {
  return TARGET_FAMILY_LABELS[targetFamily] ?? targetFamily;
}

function formatCorrelation(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "不可用";
  }
  return value.toFixed(2);
}

function renderCorrelationCard(point: MacroBondLinkageTopCorrelation) {
  return (
    <div
      key={`${point.series_id}:${point.target_family}:${point.target_tenor ?? "none"}`}
      style={{
        display: "grid",
        gap: s[3],
        ...pageInsetCardStyle,
        background: "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: s[3],
          alignItems: "flex-start",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: c.neutral[900] }}>{point.series_name}</div>
          <div style={{ color: c.neutral[500], fontSize: fs[12] }}>{point.series_id}</div>
        </div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: s[2],
            padding: `${s[2]}px ${s[2] + s[1]}px`,
            borderRadius: 999,
            background:
              point.direction === "positive"
                ? c.success[50]
                : point.direction === "negative"
                  ? c.warning[50]
                  : c.primary[50],
            color:
              point.direction === "positive"
                ? c.semantic.up
                : point.direction === "negative"
                  ? c.warning[600]
                  : c.neutral[800],
            fontSize: fs[12],
            fontWeight: 600,
          }}
        >
          {point.direction}
        </div>
      </div>

      <div style={{ color: c.neutral[800], fontSize: fs[13], lineHeight: designTokens.lineHeight.normal }}>
        目标维度：{familyLabel(point.target_family)}
        {point.target_tenor ? ` / ${point.target_tenor}` : " / 期限不可用"}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
          gap: s[3],
        }}
      >
        <div>
          <div style={{ color: c.neutral[500], fontSize: fs[12] }}>3月相关</div>
          <div style={tabularNumsStyle}>{formatCorrelation(point.correlation_3m)}</div>
        </div>
        <div>
          <div style={{ color: c.neutral[500], fontSize: fs[12] }}>6月相关</div>
          <div style={tabularNumsStyle}>{formatCorrelation(point.correlation_6m)}</div>
        </div>
        <div>
          <div style={{ color: c.neutral[500], fontSize: fs[12] }}>1年相关</div>
          <div style={tabularNumsStyle}>{formatCorrelation(point.correlation_1y)}</div>
        </div>
        <div>
          <div style={{ color: c.neutral[500], fontSize: fs[12] }}>领先/滞后</div>
          <div style={tabularNumsStyle}>{`${point.lead_lag_days} 天`}</div>
        </div>
      </div>
    </div>
  );
}

function renderSeriesCards(
  series: MarketObservationPoint[],
  options?: { testIdPrefix?: string },
) {
  const testIdPrefix = options?.testIdPrefix ?? "market-data-series";

  return (
    <div style={{ display: "grid", gap: s[3] }}>
      {series.map((point) => (
        <div
          key={point.series_id}
          data-testid={`${testIdPrefix}-${point.series_id}`}
          style={{
            display: "grid",
            gap: s[3],
            ...pageInsetCardStyle,
            background: "#ffffff",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: s[3],
              flexWrap: "wrap",
            }}
          >
            <div>
              <div style={{ fontWeight: 600 }}>{point.series_name}</div>
              <div style={{ color: c.neutral[500], fontSize: fs[12] }}>{point.series_id}</div>
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: s[2],
                padding: `${s[2]}px ${s[2] + s[1]}px`,
                borderRadius: 999,
                background: c.primary[50],
                color: c.neutral[800],
                fontSize: fs[12],
                fontWeight: 600,
              }}
            >
              <span>{`层级 ${refreshTierLabel(marketSeriesRefreshTier(point))}`}</span>
              <span>路</span>
              <span>{point.quality_flag ?? "warning"}</span>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: s[3],
            }}
          >
            <div>
              <div style={{ color: c.neutral[500], fontSize: fs[12] }}>交易日</div>
              <div>{point.trade_date}</div>
            </div>
            <div>
              <div style={{ color: c.neutral[500], fontSize: fs[12] }}>最新值</div>
              <div style={{ fontWeight: 600, color: c.neutral[900], ...tabularNumsStyle }}>
                {formatChoiceMacroValue(point)}
              </div>
            </div>
            <div>
              <div style={{ color: c.neutral[500], fontSize: fs[12] }}>变动</div>
              <div style={tabularNumsStyle}>{formatChoiceMacroDelta(point, { emptyDisplay: "无" })}</div>
            </div>
            <div>
              <div style={{ color: c.neutral[500], fontSize: fs[12] }}>抓取</div>
              <div>{seriesFetchModeLabel(point)}</div>
            </div>
          </div>

          <div style={{ color: c.neutral[600], fontSize: fs[12], lineHeight: designTokens.lineHeight.relaxed }}>
            来源 {point.source_version} 路供应商 {point.vendor_version}
          </div>
          <div style={{ color: c.neutral[800], fontSize: fs[13], lineHeight: designTokens.lineHeight.relaxed }}>
            {seriesPolicyNote(point)}
          </div>

          <div style={{ display: "flex", gap: s[2], flexWrap: "wrap" }}>
            {seriesRecentPoints(point).map((recentPoint) => (
              <span
                key={`${point.series_id}:${recentPoint.trade_date}:${recentPoint.vendor_version}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: `${s[2]}px ${s[2] + s[1]}px`,
                  borderRadius: 999,
                  background: c.neutral[50],
                  border: `1px solid ${c.primary[200]}`,
                  color: c.neutral[600],
                  fontSize: fs[12],
                }}
              >
                {formatRecentPoint(recentPoint)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MetadataPanel({
  title,
  meta,
  extraLine,
  testId,
}: {
  title: string;
  meta: ResultMeta | undefined;
  extraLine?: string;
  testId: string;
}) {
  return (
    <section data-testid={testId} style={detailPanelStyle}>
      <h2
        style={{
          marginTop: 0,
          marginBottom: s[3],
          fontSize: fs[18],
          fontWeight: 600,
        }}
      >
        {title}
      </h2>
      <div style={{ display: "grid", gap: s[2], color: c.neutral[600], fontSize: fs[14] }}>
        <div>追踪编号：{meta?.trace_id ?? "待定"}</div>
        <div>口径：{meta?.basis ?? "待定"}</div>
        <div>正式可用：{meta ? (meta.formal_use_allowed ? "是" : "否") : "待定"}</div>
        <div>结果类型：{meta?.result_kind ?? "待定"}</div>
        <div>来源版本：{meta?.source_version ?? "待定"}</div>
        <div>供应商版本：{meta?.vendor_version ?? "待定"}</div>
        <div>规则版本：{meta?.rule_version ?? "待定"}</div>
        <div>质量标记：{meta?.quality_flag ?? "待定"}</div>
        <div>供应商状态：{meta?.vendor_status ?? "待定"}</div>
        <div>降级模式：{meta?.fallback_mode ?? "待定"}</div>
        <div>缓存版本：{meta?.cache_version ?? "待定"}</div>
        <div>情景标记：{meta ? (meta.scenario_flag ? "是" : "否") : "待定"}</div>
        <div>生成时间：{meta?.generated_at ?? "待定"}</div>
        {extraLine ? <div>{extraLine}</div> : null}
      </div>
    </section>
  );
}

export default function MarketDataPage() {
  const client = useApiClient();
  const catalogQuery = useQuery({
    queryKey: ["market-data", "macro-foundation", client.mode],
    queryFn: () => client.getMacroFoundation(),
    retry: false,
  });
  const latestQuery = useQuery({
    queryKey: ["market-data", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const fxAnalyticalQuery = useQuery({
    queryKey: ["market-data", "fx-analytical", client.mode],
    queryFn: () => client.getFxAnalytical(),
    retry: false,
  });
  const ncdFundingProxyQuery = useQuery({
    queryKey: ["market-data", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
  });

  const catalog = useMemo(
    () => catalogQuery.data?.result.series ?? [],
    [catalogQuery.data?.result.series],
  );
  const latestSeries = useMemo(
    () => latestQuery.data?.result.series ?? [],
    [latestQuery.data?.result.series],
  );
  const fxAnalyticalGroups = useMemo(
    () => fxAnalyticalQuery.data?.result.groups ?? [],
    [fxAnalyticalQuery.data?.result.groups],
  );
  const ncdFundingProxy = ncdFundingProxyQuery.data?.result;
  const marketDataCategories = useMemo(
    () =>
      buildMarketDataCategoryStore({
        catalog,
        latestSeries,
        fxAnalyticalGroups,
      }),
    [catalog, fxAnalyticalGroups, latestSeries],
  );
  const visibleLatestSeries = marketDataCategories.visibleLatestSeries;
  const stableSeries = marketDataCategories.stableSeries;
  const fallbackSeries = marketDataCategories.fallbackSeries;
  const stableCatalogSeries = marketDataCategories.stableCatalogSeries;
  const missingStableSeries = marketDataCategories.missingStableSeries;
  const stableLatestTradeDate = useMemo(() => {
    if (stableSeries.length === 0) {
      return "—";
    }
    return stableSeries
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [stableSeries]);
  const linkageReportDate = marketDataCategories.linkageReportDate;
  const macroBondLinkageQuery = useQuery({
    queryKey: ["market-data", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });
  const vendorVersions = marketDataCategories.vendorVersions;
  const fxAnalyticalSeriesCount = marketDataCategories.fxAnalyticalSeriesCount;
  const stablePipelineTone = marketDataCategories.stablePipelineTone;
  const rateTrendChartOption = useMemo(
    () => buildRateTrendChartOption(latestSeries),
    [latestSeries],
  );
  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const macroBondLinkageMeta = macroBondLinkageQuery.data?.result_meta;
  const macroBondLinkageWarnings = macroBondLinkage.warnings ?? [];
  const hasPortfolioImpact =
    Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const spreadSlots = useMemo(
    () =>
      SPREAD_TENOR_SLOTS.map((tenor) => ({
        tenor,
        point:
          (macroBondLinkage.top_correlations ?? [])
            .filter(
              (item) =>
                item.target_family === "credit_spread" &&
                item.target_tenor === tenor,
            )
            .sort((left, right) => correlationStrength(right) - correlationStrength(left))[0] ?? null,
      })),
    [macroBondLinkage.top_correlations],
  );
  const nonSpreadTopCorrelations = useMemo(
    () =>
      (macroBondLinkage.top_correlations ?? []).filter(
        (item) => item.target_family !== "credit_spread",
      ),
    [macroBondLinkage.top_correlations],
  );
  const macroMeta = latestQuery.data?.result_meta ?? catalogQuery.data?.result_meta;
  const fxAnalyticalMeta = fxAnalyticalQuery.data?.result_meta;

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const [watchDate, setWatchDate] = useState(() => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  });
  const [curveFilter, setCurveFilter] = useState<"treasury" | "cdb" | "both">("both");
  const [creditSegment, setCreditSegment] = useState<"mtn" | "urban" | "both">("both");
  const [sourceFilter, setSourceFilter] = useState<"all" | "choice" | "internal">("all");
  const [macroDepthTab, setMacroDepthTab] = useState<"curve" | "spreads" | "linkage">("curve");

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setRefreshError("");
    setRefreshStatus("正在刷新宏观数据（回填 30 天）…");
    try {
      const payload = await runPollingTask({
        start: () => client.refreshChoiceMacro(30),
        getStatus: (runId) => client.getChoiceMacroRefreshStatus(runId),
        intervalMs: 3000,
        maxAttempts: 120,
        onUpdate: (p) => {
          setRefreshStatus(
            [p.status, p.run_id].filter(Boolean).join(" · "),
          );
        },
      });
      if (payload.status !== "completed") {
        throw new Error(
          payload.error_message ?? `刷新未完成：${payload.status}`,
        );
      }
      setRefreshStatus("刷新完成");
      await Promise.all([
        catalogQuery.refetch(),
        latestQuery.refetch(),
        fxAnalyticalQuery.refetch(),
        macroBondLinkageQuery.refetch(),
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setRefreshError(msg);
      setRefreshStatus("");
    } finally {
      setIsRefreshing(false);
    }
  }, [client, catalogQuery, latestQuery, fxAnalyticalQuery, macroBondLinkageQuery]);

  return (
    <section>
      <PageHeader
        title="市场数据"
        titleTestId="market-data-page-title"
        eyebrow="总览"
        description="当前页按“市场观察、分析观察、结果证据”三层阅读顺序展示内容。宏观观察与分析口径外汇观察继续共存，但正式外汇中间价状态和结果元数据仍保持为独立后端读面，不在前端补算、不混入口径。"
        badgeLabel={client.mode === "real" ? "真实 DuckDB 读路径" : "本地离线契约回放"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        actions={
          <button
            type="button"
            data-testid="market-data-refresh-button"
            disabled={isRefreshing}
            onClick={() => void handleRefresh()}
            style={{
              padding: `${s[2]}px ${s[5]}px`,
              borderRadius: 999,
              border: "none",
              background: isRefreshing ? c.neutral[400] : c.info[500],
              color: "#ffffff",
              fontSize: fs[13],
              fontWeight: 600,
              cursor: isRefreshing ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {isRefreshing ? "刷新中…" : "刷新宏观数据"}
          </button>
        }
      >
        <div style={{ display: "grid", gap: s[4] }}>
          <p
            style={{
              margin: 0,
              color: c.neutral[600],
              fontSize: fs[13],
            }}
          >
            观察日期 {watchDate}
          </p>

          <div data-testid="market-data-filter-strip">
            <PageFilterTray>
              <FilterBar>
                <label style={filterLabelStyle}>
                  日期
                  <input
                    type="date"
                    value={watchDate}
                    onChange={(e) => setWatchDate(e.target.value)}
                    style={filterControlStyle}
                  />
                </label>
                <label style={filterLabelStyle}>
                  国债 / 国开
                  <Select
                    value={curveFilter}
                    onChange={(v) => setCurveFilter(v)}
                    options={[
                      { value: "treasury", label: "国债" },
                      { value: "cdb", label: "国开" },
                      { value: "both", label: "全部" },
                    ]}
                    style={{ width: 200 }}
                  />
                </label>
                <label style={filterLabelStyle}>
                  中票 / 城投
                  <Select
                    value={creditSegment}
                    onChange={(v) => setCreditSegment(v)}
                    options={[
                      { value: "mtn", label: "中票" },
                      { value: "urban", label: "城投" },
                      { value: "both", label: "全部" },
                    ]}
                    style={{ width: 200 }}
                  />
                </label>
                <label style={filterLabelStyle}>
                  来源
                  <Select
                    value={sourceFilter}
                    onChange={(v) => setSourceFilter(v)}
                    options={[
                      { value: "all", label: "全部" },
                      { value: "choice", label: "Choice" },
                      { value: "internal", label: "内部" },
                    ]}
                    style={{ width: 200 }}
                  />
                </label>
              </FilterBar>
            </PageFilterTray>
          </div>

          {(refreshStatus || refreshError) && (
            <div
              style={{
                padding: `${s[2] + s[1]}px ${s[4]}px`,
                borderRadius: s[3],
                fontSize: fs[13],
                background: refreshError ? c.warning[50] : c.info[50],
                color: refreshError ? c.warning[600] : c.info[500],
              }}
            >
              {refreshError || refreshStatus}
            </div>
          )}
        </div>
      </PageHeader>

      <MarketSectionLead
        eyebrow="总览"
        title="市场概览"
        description="先确认当前序列覆盖、稳定回收和分析观察范围，再进入利率、资金和成交明细。"
        flushTop
      />
      <div style={summaryGridStyle}>
        <div data-testid="market-data-catalog-count">
          <KpiCard
            title="宏观序列目录"
            value={String(catalog.length)}
            detail="已登记的宏观序列数量。"
            tone="default"
          />
        </div>
        <div data-testid="market-data-stable-count">
          <KpiCard
            title="稳定回收"
            value={`${stableSeries.length} / ${stableCatalogSeries.length}`}
            detail="稳定主链路已回收 / 目录应有数量。"
            tone={stablePipelineTone}
          />
        </div>
        <div data-testid="market-data-fallback-count">
          <KpiCard
            title="降级可用"
            value={String(fallbackSeries.length)}
            detail="仅取最新 / 单次抓取降级链路中的序列数量。"
            tone={fallbackSeries.length > 0 ? "warning" : "default"}
          />
        </div>
        <div data-testid="market-data-stable-trade-date">
          <KpiCard
            title="稳定最新日"
            value={stableLatestTradeDate}
            detail="稳定主链路中可见序列的最大交易日期。"
            valueVariant="text"
            tone={stableSeries.length === 0 ? "warning" : "default"}
          />
        </div>
        <div data-testid="market-data-missing-stable-count">
          <KpiCard
            title="稳定缺口"
            value={String(missingStableSeries.length)}
            detail="目录中属于稳定主链路但当前尚未回收的序列数量。"
            tone={
              missingStableSeries.length > 5 ? "error" : missingStableSeries.length > 0 ? "warning" : "default"
            }
          />
        </div>
        <div data-testid="market-data-fx-analytical-group-count">
          <KpiCard
            title="外汇观察分组"
            value={String(fxAnalyticalGroups.length)}
            detail="后端返回的分析口径外汇分组数量。"
          />
        </div>
        <div data-testid="market-data-fx-analytical-series-count">
          <KpiCard
            title="外汇观察序列"
            value={String(fxAnalyticalSeriesCount)}
            detail="分析口径外汇观察值与正式外汇状态保持分离。"
          />
        </div>
        <div data-testid="market-data-linkage-report-date">
          <KpiCard
            title="联动报告日"
            value={linkageReportDate || "—"}
            detail="宏观-债市联动分析使用的报告日期。"
            valueVariant="text"
            tone={linkageReportDate ? "default" : "warning"}
          />
        </div>
      </div>
      <LiveResultMetaStrip
        lead="市场概览·宏观读面（最新优先）"
        meta={macroMeta}
        testId="market-data-overview-live-meta"
      />

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="核心观察"
          title="利率、资金、宏观深度与成交观察"
          description="左侧保留利率行情主表；右侧「宏观深度」页签聚合 V3 client 已支持的曲线（Choice）、结构化信用利差槽位与联动环境/组合影响摘要。V1 其余 `/api/macro/*` 决策类端点未暴露则不在此实现。"
        />
        <div style={terminalRowGridStyle}>
        <RateQuoteTable />
        <div data-testid="market-data-macro-depth-wrap" style={{ ...macroChartShellStyle, marginTop: 0 }}>
          <Tabs
            data-testid="market-data-macro-depth-tabs"
            activeKey={macroDepthTab}
            onChange={(key) => setMacroDepthTab(key as "curve" | "spreads" | "linkage")}
            items={[
              {
                key: "curve",
                label: "曲线（M8）",
                forceRender: true,
                children: (
                  <div data-testid="market-data-macro-tab-curve">
                    <h2 style={{ ...blockTitleStyle, marginTop: 0 }}>收益率曲线</h2>
                    <p
                      style={{
                        marginTop: s[2],
                        marginBottom: 0,
                        color: c.neutral[600],
                        fontSize: fs[14],
                        lineHeight: designTokens.lineHeight.normal,
                      }}
                    >
                      国债 10Y（{RATE_TREND_DEFINITIONS[0].series_id}）、国开 5Y（{RATE_TREND_DEFINITIONS[1].series_id}）、
                      SHIBOR 隔夜（{RATE_TREND_DEFINITIONS[2].series_id}），数据来自各序列的 recent_points。
                    </p>
                    <LiveResultMetaStrip
                      lead="收益率曲线·宏观最新"
                      meta={latestQuery.data?.result_meta}
                      testId="market-data-curve-live-meta"
                    />
                    {latestQuery.isLoading ? (
                      <div
                        style={{
                          marginTop: s[4],
                          padding: s[6],
                          color: c.neutral[600],
                          fontSize: fs[14],
                        }}
                      >
                        加载宏观序列中…
                      </div>
                    ) : latestQuery.isError ? (
                      <Alert
                        action={
                          <Button danger size="small" onClick={() => void latestQuery.refetch()}>
                            重试宏观序列
                          </Button>
                        }
                        data-testid="market-data-rate-trend-error"
                        description="无法确认收益率曲线输入，不按空数据处理；请重试或查看下方宏观序列失败态。"
                        message="宏观最新载入失败"
                        showIcon
                        type="error"
                      />
                    ) : rateTrendChartOption ? (
                      <div data-testid="market-data-rate-trend-chart" style={{ marginTop: s[4] }}>
                        <ReactECharts option={rateTrendChartOption} style={{ height: 360, width: "100%" }} />
                      </div>
                    ) : (
                      <div
                        data-testid="market-data-rate-trend-empty"
                        style={rateTrendEmptyStateStyle}
                      >
                        当前响应中缺少上述利率序列的近期点位，无法绘制走势图。
                      </div>
                    )}
                  </div>
                ),
              },
              {
                key: "spreads",
                label: "信用利差",
                forceRender: true,
                children: (
                  <div data-testid="market-data-macro-tab-spreads" style={macroTabPanelStyle}>
                    <LiveResultMetaStrip
                      lead="信用利差表格·联动读面"
                      meta={macroBondLinkageQuery.data?.result_meta}
                      testId="market-data-spreads-live-meta"
                    />
                    <LinkageSpreadTenorTable slots={spreadSlots} loading={macroBondLinkageQuery.isLoading} />
                  </div>
                ),
              },
              {
                key: "linkage",
                label: "压力与情景（M11/M15）",
                forceRender: true,
                children: (
                  <div data-testid="market-data-macro-tab-linkage" style={macroTabPanelStyle}>
                    <p
                      style={{
                        margin: `0 0 ${s[3]}px`,
                        color: c.neutral[600],
                        fontSize: fs[13],
                        lineHeight: designTokens.lineHeight.normal,
                      }}
                    >
                      摘要来自 <code>getMacroBondLinkageAnalysis</code> 的 <code>environment_score</code> 与{" "}
                      <code>portfolio_impact</code>；完整相关性矩阵仍在下文「宏观-债市联动」折叠区。
                    </p>
                    <div style={summaryGridStyle}>
                      <KpiCard
                        title="环境综合分"
                        value={
                          macroBondLinkage.environment_score?.composite_score != null
                            ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                            : "—"
                        }
                        detail={macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分。"}
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
                        detail="对应联动载荷的流动性评分（非 V1 压力测试原样复刻）。"
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
                ),
              },
            ]}
          />
        </div>
      </div>
      </MarketSectionBlock>

      <div style={observationGridStyle}>
        <MoneyMarketTable />
        <BondFuturesTable />
        <NcdMatrix
          payload={ncdFundingProxy}
          resultMeta={ncdFundingProxyQuery.data?.result_meta}
          isLoading={ncdFundingProxyQuery.isLoading}
          isError={ncdFundingProxyQuery.isError}
          onRetry={() => void ncdFundingProxyQuery.refetch()}
        />
      </div>

      <div style={observationGridStyle}>
        <BondTradeDetail />
        <CreditBondTradesTable />
        <NewsAndCalendar />
      </div>

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="观察"
          title="宏观序列与分析观察"
          description="在市场主观察之后，单独查看 Choice 宏观序列的稳定链路、缺口与外汇分析观察，避免和正式读面混用。"
        />
        <MacroLatestReadinessBanner
          testId="market-data-macro-readiness"
          isLoading={latestQuery.isLoading}
          isError={latestQuery.isError}
          hasSeries={visibleLatestSeries.length > 0}
          meta={latestQuery.data?.result_meta}
        />
        <MarketSectionInnerBlock>
          <AsyncSection
          title="宏观序列观察"
          isLoading={latestQuery.isLoading}
          isError={latestQuery.isError}
          isEmpty={!latestQuery.isLoading && !latestQuery.isError && visibleLatestSeries.length === 0}
          onRetry={() => void latestQuery.refetch()}
        >
          <div style={{ display: "grid", gap: s[6] }}>
            {!latestQuery.isLoading && !latestQuery.isError ? (
              <LiveResultMetaStrip
                lead="本区块·宏观最新"
                meta={latestQuery.data?.result_meta}
                testId="market-data-macro-section-meta"
              />
            ) : null}
            <section data-testid="market-data-stable-section">
              <div style={{ marginBottom: s[3] }}>
                <h2 style={{ margin: 0, fontSize: fs[20], fontWeight: 600 }}>稳定主链路</h2>
                <p style={{ marginTop: s[2], marginBottom: 0, color: c.neutral[600], fontSize: fs[14] }}>
                  面向日常分析的主刷新读面，只显示稳定可取的序列。
                </p>
              </div>
              {renderSeriesCards(stableSeries)}
            </section>

            <section data-testid="market-data-missing-stable-section">
              <div style={{ marginBottom: s[3] }}>
                <h2 style={{ margin: 0, fontSize: fs[20], fontWeight: 600 }}>待补齐稳定链路</h2>
                <p style={{ marginTop: s[2], marginBottom: 0, color: c.neutral[600], fontSize: fs[14] }}>
                  目录中归属稳定链路，但当前刷新尚未回收的序列。
                </p>
              </div>
              {missingStableSeries.length > 0 ? (
                <div style={{ display: "grid", gap: s[3] }}>
                  {missingStableSeries.map((series) => (
                    <div
                      key={series.series_id}
                      style={{
                        display: "grid",
                        gap: s[2],
                        padding: s[4],
                        borderRadius: s[4],
                        border: `1px solid ${c.primary[200]}`,
                        background: "#ffffff",
                      }}
                    >
                      <strong>{series.series_name}</strong>
                      <div style={{ color: c.neutral[600], fontSize: fs[13] }}>
                        {series.series_id} 路 {refreshTierLabel(marketCatalogRefreshTier(series))} 路 {seriesFetchModeLabel(series)}
                      </div>
                      <div style={{ color: c.neutral[800], fontSize: fs[13] }}>
                        {series.policy_note ?? "主刷新日期切片链路"}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    padding: s[4],
                    borderRadius: s[4],
                    border: `1px solid ${c.primary[200]}`,
                    background: "#ffffff",
                    color: c.neutral[600],
                    fontSize: fs[14],
                  }}
                >
                  当前稳定目录已全部回收。
                </div>
              )}
            </section>

            <section data-testid="market-data-fallback-section">
              <div style={{ marginBottom: s[3] }}>
                <h2 style={{ margin: 0, fontSize: fs[20], fontWeight: 600 }}>仅取最新降级</h2>
                <p style={{ marginTop: s[2], marginBottom: 0, color: c.neutral[600], fontSize: fs[14] }}>
                  低频或稀疏序列保留为降级链路展示，不混入稳定主链路。
                </p>
              </div>
              {fallbackSeries.length > 0 ? (
                renderSeriesCards(fallbackSeries)
              ) : (
                <div
                  style={{
                    padding: s[4],
                    borderRadius: s[4],
                    border: `1px solid ${c.primary[200]}`,
                    background: "#ffffff",
                    color: c.neutral[600],
                    fontSize: fs[14],
                  }}
                >
                  当前无仅取最新降级序列。
                </div>
              )}
            </section>
          </div>
          </AsyncSection>
        </MarketSectionInnerBlock>

        <MarketSectionInnerBlock>
          <AsyncSection
          title="外汇分析观察"
          isLoading={fxAnalyticalQuery.isLoading}
          isError={fxAnalyticalQuery.isError}
          isEmpty={
            !fxAnalyticalQuery.isLoading &&
            !fxAnalyticalQuery.isError &&
            fxAnalyticalGroups.length === 0
          }
          onRetry={() => void fxAnalyticalQuery.refetch()}
        >
          <div style={{ display: "grid", gap: s[6] }}>
            {!fxAnalyticalQuery.isLoading && !fxAnalyticalQuery.isError ? (
              <LiveResultMetaStrip
                lead="本区块·外汇分析"
                meta={fxAnalyticalQuery.data?.result_meta}
                testId="market-data-fx-section-meta"
              />
            ) : null}
            {fxAnalyticalGroups.map((group) => (
              <section
                key={group.group_key}
                data-testid={`market-data-fx-group-${group.group_key}`}
              >
                <div style={{ marginBottom: s[3] }}>
                  <h2 style={{ margin: 0, fontSize: fs[20], fontWeight: 600 }}>{fxAnalyticalGroupTitle(group.title)}</h2>
                  <p
                    style={{
                      marginTop: s[2],
                      marginBottom: 0,
                      color: c.neutral[600],
                      fontSize: fs[14],
                      lineHeight: designTokens.lineHeight.relaxed,
                    }}
                  >
                    {fxAnalyticalGroupDescription(group.description)}
                  </p>
                </div>
                {renderSeriesCards(group.series, {
                  testIdPrefix: `market-data-fx-series-${group.group_key}`,
                })}
              </section>
            ))}
          </div>
          </AsyncSection>
        </MarketSectionInnerBlock>
      </MarketSectionBlock>

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="分析口径"
          title="宏观-债市联动"
          description="联动区保留为分析口径折叠块，继续显式标注分析口径和非正式口径，不向正式结果读面越界。"
        />
        <Collapse
          data-testid="market-data-linkage-collapse"
          bordered={false}
        defaultActiveKey={[]}
        items={[
          {
            key: "macro-linkage",
            label: "宏观-债市联动（分析口径，点击展开）",
            forceRender: true,
            children: (
              <AsyncSection
                title="宏观-债市联动"
                isLoading={macroBondLinkageQuery.isLoading}
                isError={macroBondLinkageQuery.isError}
                isEmpty={
                  !macroBondLinkageQuery.isLoading &&
                  !macroBondLinkageQuery.isError &&
                  (macroBondLinkage.top_correlations?.length ?? 0) === 0 &&
                  macroBondLinkageWarnings.length === 0
                }
                onRetry={() => void macroBondLinkageQuery.refetch()}
              >
                <div style={{ display: "grid", gap: s[5] }}>
            <section
              data-testid="market-data-linkage-caveat"
              style={{
                padding: s[4] + s[1],
                borderRadius: s[4] + s[1],
                border: `1px solid ${c.info[200]}`,
                background: `linear-gradient(180deg, ${c.neutral[50]} 0%, ${c.primary[50]} 100%)`,
                display: "grid",
                gap: s[3],
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: s[2],
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: `${s[1] + s[1]}px ${s[2] + s[1]}px`,
                    borderRadius: 999,
                    background: c.info[50],
                    color: c.info[500],
                    fontSize: fs[12],
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  分析口径
                </span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: `${s[1] + s[1]}px ${s[2] + s[1]}px`,
                    borderRadius: 999,
                    background: c.warning[50],
                    color: c.warning[600],
                    fontSize: fs[12],
                    fontWeight: 700,
                  }}
                >
                  非正式口径
                </span>
              </div>
              <div style={{ color: c.neutral[800], fontSize: fs[14], lineHeight: designTokens.lineHeight.relaxed }}>
                本区为宏观联动分析口径。组合影响仅用于研究和配置讨论，属于分析估算，不代表账本口径下的损益（PnL）、
                不代表正式估值归因，也不替代债券分析的正式读面。
              </div>
              {macroBondLinkageWarnings.length > 0 ? (
                <ul
                  data-testid="market-data-linkage-warning-list"
                  style={{
                    margin: 0,
                    paddingLeft: s[5],
                    color: c.neutral[600],
                    fontSize: fs[13],
                    lineHeight: designTokens.lineHeight.relaxed,
                  }}
                >
                  {macroBondLinkageWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <div
                  style={{ color: c.neutral[600], fontSize: fs[13] }}
                  data-testid="market-data-linkage-warning-empty"
                >
                  当前无额外方法警示。
                </div>
              )}
            </section>

            <div style={summaryGridStyle}>
              <div data-testid="market-data-linkage-composite-score">
                <KpiCard
                  title="综合评分"
                  value={
                    macroBondLinkage.environment_score?.composite_score != null
                      ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                      : "不可用"
                  }
                  detail={macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分数据。"}
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.composite_score != null
                      ? macroBondLinkage.environment_score.composite_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-rate-direction">
                <KpiCard
                  title="利率方向"
                  value={macroBondLinkage.environment_score?.rate_direction ?? "不可用"}
                  detail={
                    macroBondLinkage.environment_score?.rate_direction_score != null
                      ? `direction score ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                      : "缺少方向评分。"
                  }
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.rate_direction_score != null
                      ? macroBondLinkage.environment_score.rate_direction_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-liquidity-score">
                <KpiCard
                  title="流动性评分"
                  value={
                    macroBondLinkage.environment_score?.liquidity_score != null
                      ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                      : "不可用"
                  }
                  detail="正值偏松，负值偏紧。"
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.liquidity_score != null
                      ? macroBondLinkage.environment_score.liquidity_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-growth-score">
                <KpiCard
                  title="增长评分"
                  value={
                    macroBondLinkage.environment_score?.growth_score != null
                      ? macroBondLinkage.environment_score.growth_score.toFixed(2)
                      : "不可用"
                  }
                  detail="宏观增长方向的简化分值。"
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.growth_score != null
                      ? macroBondLinkage.environment_score.growth_score
                      : null,
                  )}
                />
              </div>
            </div>

            <section
              data-testid="market-data-linkage-portfolio-impact"
              style={detailPanelStyle}
            >
              <h2 style={{ marginTop: 0, marginBottom: s[2], fontSize: fs[18], fontWeight: 600 }}>
                组合影响估算
              </h2>
              <p style={{ marginTop: 0, color: c.neutral[600], fontSize: fs[13], lineHeight: designTokens.lineHeight.relaxed }}>
                以下数值为分析口径估算，基于宏观环境评分与组合在利率、利差维度上的敏感度静态映射，不代表正式损益。
              </p>
              {hasPortfolioImpact ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: s[3],
                  }}
                >
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>利率变动</div>
                    <div style={tabularNumsStyle}>
                      {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>利差走阔</div>
                    <div style={tabularNumsStyle}>
                      {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>利率影响</div>
                    <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_pnl_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>利差影响</div>
                    <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_pnl_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>合计估算</div>
                    <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                  </div>
                  <div>
                    <div style={{ color: c.neutral[500], fontSize: fs[12] }}>影响占比</div>
                    <div style={tabularNumsStyle}>{macroBondLinkage.portfolio_impact?.impact_ratio_to_market_value ?? "不可用"}</div>
                  </div>
                </div>
              ) : (
                <div
                  data-testid="market-data-linkage-portfolio-impact-unavailable"
                  style={{
                    padding: s[4],
                    borderRadius: designTokens.radius.md + s[1],
                    border: `1px dashed ${c.primary[300]}`,
                    background: "#ffffff",
                    color: c.neutral[500],
                    fontSize: fs[14],
                  }}
                >
                  当前报告日未返回组合影响估算，状态按不可用处理，不在前端补零。
                </div>
              )}
            </section>

            <section data-testid="market-data-linkage-spread-tenors" style={detailPanelStyle}>
              <h2 style={{ marginTop: 0, marginBottom: s[2], fontSize: fs[18], fontWeight: 600 }}>
                信用利差显式维度
              </h2>
              <p style={{ marginTop: 0, color: c.neutral[600], fontSize: fs[13], lineHeight: designTokens.lineHeight.relaxed }}>
                仅按结构化字段渲染，不从标签或目标收益率反推期限。
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: s[3],
                }}
              >
                {spreadSlots.map(({ tenor, point }) => (
                  <div
                    key={tenor}
                    data-testid={`market-data-linkage-spread-slot-${tenor}`}
                    style={{
                      padding: s[4],
                      borderRadius: s[4],
                      border: `1px solid ${c.primary[200]}`,
                      background: "#ffffff",
                      display: "grid",
                      gap: s[2],
                    }}
                  >
                    <div style={{ fontWeight: 600, color: c.neutral[900] }}>{`信用利差 ${tenor}`}</div>
                    {point ? (
                      <>
                        <div style={{ color: c.neutral[600], fontSize: fs[13] }}>{point.series_name}</div>
                        <div style={tabularNumsStyle}>{`1年相关 ${formatCorrelation(point.correlation_1y)}`}</div>
                        <div style={tabularNumsStyle}>{`领先/滞后 ${point.lead_lag_days} 天`}</div>
                      </>
                    ) : (
                      <div style={{ color: c.neutral[500], fontSize: fs[13], lineHeight: designTokens.lineHeight.relaxed }}>
                        不可用：当前载荷未返回该期限的结构化相关性，不在前端推断。
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section data-testid="market-data-linkage-top-correlations" style={detailPanelStyle}>
              <h2 style={{ marginTop: 0, marginBottom: s[2], fontSize: fs[18], fontWeight: 600 }}>
                相关性 Top 10
              </h2>
              {(nonSpreadTopCorrelations.length > 0 ||
                spreadSlots.some((slot) => slot.point !== null)) ? (
                <div style={{ display: "grid", gap: s[3] }}>
                  {(macroBondLinkage.top_correlations ?? []).map((point) =>
                    renderCorrelationCard(point),
                  )}
                </div>
              ) : (
                <div
                  style={{
                    padding: s[4],
                    borderRadius: designTokens.radius.md + s[1],
                    border: `1px dashed ${c.primary[300]}`,
                    background: "#ffffff",
                    color: c.neutral[500],
                    fontSize: fs[14],
                  }}
                >
                  当前无可展示的结构化相关性结果。
                </div>
              )}
            </section>
                </div>
              </AsyncSection>
            ),
          },
        ]}
      />
      </MarketSectionBlock>

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="证据"
          title="目录与结果元数据"
          description="页尾集中展示目录补充信息与结果元数据，保证分析观察之后仍能顺着阅读路径回到数据来源与版本证据。"
        />
        <div style={{ ...sectionGridStyle, marginTop: 0 }}>
        <AsyncSection
          title="宏观序列目录"
          isLoading={catalogQuery.isLoading}
          isError={catalogQuery.isError}
          isEmpty={!catalogQuery.isLoading && !catalogQuery.isError && catalog.length === 0}
          onRetry={() => void catalogQuery.refetch()}
        >
          <div style={{ display: "grid", gap: s[3] }}>
            {catalog.map((series) => (
              <div
                key={series.series_id}
                style={{
                  display: "grid",
                  gap: s[2],
                  padding: s[4],
                  borderRadius: s[4],
                  border: `1px solid ${c.primary[200]}`,
                  background: "#ffffff",
                }}
              >
                <strong>{series.series_name}</strong>
                <div style={{ color: c.neutral[600], fontSize: fs[13] }}>
                  {series.series_id} 路 {series.vendor_name} 路 {series.frequency} 路 {series.unit}
                </div>
                <div style={{ color: c.neutral[500], fontSize: fs[12] }}>
                  供应商版本 {series.vendor_version}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <MetadataPanel
          title="结果元数据"
          meta={macroMeta}
          extraLine={`可见供应商版本：${vendorVersions.join(", ") || "—"}`}
          testId="market-data-result-meta"
        />

        <MetadataPanel
          title="外汇观察元数据"
          meta={fxAnalyticalMeta}
          testId="market-data-fx-analytical-meta"
        />

        <MetadataPanel
          title="联动元数据"
          meta={macroBondLinkageMeta}
          extraLine={`报告日：${linkageReportDate || "待定"}`}
          testId="market-data-linkage-meta"
        />
      </div>
      </MarketSectionBlock>
    </section>
  );
}
