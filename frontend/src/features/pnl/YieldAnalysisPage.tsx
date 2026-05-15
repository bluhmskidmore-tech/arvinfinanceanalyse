import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { Spin } from "antd";

import { useApiClient } from "../../api/client";
import type { LiabilityYieldHistoryPoint, Numeric, PnlV1DetailRow } from "../../api/contracts";
import { fmtPct, formatNumeric, formatPercent } from "../../utils/format";
import { BaseChart } from "../../components/charts/BaseChart";
import { designTokens } from "../../theme/designSystem";
import { runPollingTask } from "../../app/jobs/polling";
import { PnlFilterBar } from "./yieldAnalysis/PnlFilterBar";
import { RankingBarsCard } from "./yieldAnalysis/RankingBarsCard";
import { YieldByPeriodPanel } from "./yieldAnalysis/YieldByPeriodPanel";
import { buildYieldAnalysisAggregates } from "./yieldAnalysis/yieldAnalysisAggregates";
import "./yieldAnalysis/yieldAnalysis.css";

type MainTab = "yield" | "pnl" | "period";

const STANDARD_PNL_DETAIL_HEADERS = [
  { label: "资产代码", align: "left" },
  { label: "债券名称", align: "left" },
  { label: "投资组合", align: "left" },
  { label: "资产类型", align: "left" },
  { label: "利息收入", align: "right" },
  { label: "公允价值变动", align: "right" },
  { label: "投资收益", align: "right" },
  { label: "总损益", align: "right" },
] as const;

const NONSTD_PNL_DETAIL_HEADERS = [
  { label: "资产代码", align: "left" },
  { label: "资产类型（映射）", align: "left" },
  { label: "利息收入514", align: "right" },
  { label: "公允价值变动516", align: "right" },
  { label: "资本利得517", align: "right" },
  { label: "总损益", align: "right" },
] as const;

function numericRaw(value: Numeric | null | undefined): number | null | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return value.raw ?? undefined;
}

function formatMonthLabel(dateStr: string) {
  const d = new Date(`${dateStr}T12:00:00`);
  if (Number.isNaN(d.getTime())) {
    return dateStr;
  }
  return `${d.getFullYear()}年${String(d.getMonth() + 1).padStart(2, "0")}月`;
}

function parseMoney(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function fmtWanYuan(value: number) {
  return `${(value / 10_000).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtSignedWanYuan(value: number) {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${fmtWanYuan(value)} 万`;
}

function pnlTone(value: number) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

const chartAxisMuted = designTokens.color.warm.taupe;
const chartMarketCost = designTokens.color.warm.slateBlue;
const chartSpread = designTokens.color.warm.sage;
const chartAssetYield = designTokens.color.warm.charcoal;
const chartLiabilityDash = designTokens.color.warm.taupe;
const chartScatter = designTokens.color.warm.terracotta;

function historyChartOption(history: LiabilityYieldHistoryPoint[]): EChartsOption {
  const dates = history.map((h) => h.date);
  const asset = history.map((h) => (h.asset_yield != null ? h.asset_yield * 100 : null));
  const mkt = history.map((h) => (h.market_liability_cost != null ? h.market_liability_cost * 100 : null));
  const liab = history.map((h) => (h.liability_cost != null ? h.liability_cost * 100 : null));
  const spread = history.map((h) => {
    if (h.asset_yield == null || h.market_liability_cost == null) return null;
    return (h.asset_yield - h.market_liability_cost) * 100;
  });
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["市场负债成本(%)", "息差(%)", "资产收益(%)", "综合负债成本(%)"], top: 0 },
    grid: { left: 48, right: 24, top: 40, bottom: 32 },
    xAxis: { type: "category", data: dates, axisLabel: { color: chartAxisMuted } },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%`, color: chartAxisMuted } },
    series: [
      { name: "市场负债成本(%)", type: "line", data: mkt, smooth: true, areaStyle: { opacity: 0.12 }, lineStyle: { color: chartMarketCost } },
      { name: "息差(%)", type: "line", data: spread, smooth: true, areaStyle: { color: `${chartSpread}26` }, lineStyle: { color: chartSpread } },
      { name: "资产收益(%)", type: "line", data: asset, smooth: true, lineStyle: { width: 2, color: chartAssetYield } },
      { name: "综合负债成本(%)", type: "line", data: liab, smooth: true, lineStyle: { type: "dashed", color: chartLiabilityDash } },
    ],
  };
}

function scatterChartOption(
  points: { x: number; y: number; z: number; name: string }[],
): EChartsOption {
  const data = points.map((p) => [p.x, p.y * 100, p.z, p.name]);
  return {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const p = params as { value?: [number, number, number, string] };
        const v = p.value;
        if (!v) return "";
        return `${v[3]}<br/>久期(近似): ${v[0].toFixed(2)}y<br/>收益率: ${v[1].toFixed(2)}%<br/>规模: ${v[2].toLocaleString("zh-CN")}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: { type: "value", name: "久期(y)", nameLocation: "middle", nameGap: 28, axisLabel: { color: chartAxisMuted } },
    yAxis: { type: "value", name: "收益率(%)", axisLabel: { color: chartAxisMuted } },
    series: [
      {
        type: "scatter",
        symbolSize: 12,
        data,
        itemStyle: { color: chartScatter, opacity: 0.75 },
      },
    ],
  };
}

export default function YieldAnalysisPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const reportDateParam = searchParams.get("report_date")?.trim() ?? "";

  const [activeTab, setActiveTab] = useState<MainTab>("pnl");
  const [selectedPnlDate, setSelectedPnlDate] = useState("");
  const [pnlLoading, setPnlLoading] = useState(false);
  const [pnlError, setPnlError] = useState<string | null>(null);
  const [refreshingPnL, setRefreshingPnL] = useState(false);
  const [standardDetailsExpanded, setStandardDetailsExpanded] = useState(true);
  const [pnlFilterSource, setPnlFilterSource] = useState("ALL");
  const [pnlFilterInvestType, setPnlFilterInvestType] = useState("ALL");
  const [pnlFilterPortfolio, setPnlFilterPortfolio] = useState("ALL");
  const [pnlSearch, setPnlSearch] = useState("");

  const yieldQuery = useQuery({
    queryKey: ["yield-analysis", "yield_metrics", client.mode, reportDateParam || "__latest__"],
    queryFn: () => client.getLiabilityYieldMetrics(reportDateParam || null),
    retry: false,
  });

  const datesQuery = useQuery({
    queryKey: ["yield-analysis", "pnl-dates", client.mode],
    queryFn: () => client.getFormalPnlDates("formal"),
    enabled: activeTab === "pnl",
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    if (activeTab !== "pnl") return;
    if (selectedPnlDate) return;
    if (reportDates.length > 0) {
      setSelectedPnlDate(reportDates[0]);
    }
  }, [activeTab, reportDates, selectedPnlDate]);

  useEffect(() => {
    if (activeTab !== "pnl") return;
    setPnlFilterSource("ALL");
    setPnlFilterInvestType("ALL");
    setPnlFilterPortfolio("ALL");
    setPnlSearch("");
  }, [activeTab, selectedPnlDate]);

  const detailQuery = useQuery({
    queryKey: ["yield-analysis", "pnl-v1", client.mode, selectedPnlDate],
    queryFn: () => client.getPnlV1Data(selectedPnlDate),
    enabled: activeTab === "pnl" && Boolean(selectedPnlDate),
    retry: false,
  });

  const pnlDetailData = useMemo(() => detailQuery.data?.result.rows ?? [], [detailQuery.data?.result.rows]);
  const pnlDetailLoading = detailQuery.isLoading;

  const availableMonths = useMemo(() => {
    const sorted = [...reportDates].sort((a, b) => (a > b ? -1 : a < b ? 1 : 0));
    const byMonth = new Map<string, string>();
    for (const d of sorted) {
      const ym = String(d).slice(0, 7);
      if (!byMonth.has(ym)) {
        byMonth.set(ym, d);
      }
    }
    return Array.from(byMonth.entries()).map(([ym, dateStr]) => ({
      ym,
      value: dateStr,
      label: formatMonthLabel(dateStr),
    }));
  }, [reportDates]);

  const pnlFilterOptions = useMemo(() => {
    const rows = pnlDetailData || [];
    const uniqSorted = (arr: string[]) => Array.from(new Set(arr.filter((x) => x && x.trim() !== ""))).sort();
    const sourceKey = (r: PnlV1DetailRow) => String(r?.source || "FI");
    const investKey = (r: PnlV1DetailRow) => String(r?.asset_type || "非标投资");
    const portfolioKey = (r: PnlV1DetailRow) => String(r?.portfolio || "未分组");
    return {
      sources: ["ALL", ...uniqSorted(rows.map(sourceKey))],
      invests: ["ALL", ...uniqSorted(rows.map(investKey))],
      portfolios: ["ALL", ...uniqSorted(rows.map(portfolioKey))],
    };
  }, [pnlDetailData]);

  const pnlFilteredRows = useMemo(() => {
    const rows = pnlDetailData || [];
    const sourceKey = (r: PnlV1DetailRow) => String(r?.source || "FI");
    const investKey = (r: PnlV1DetailRow) => String(r?.asset_type || "非标投资");
    const portfolioKey = (r: PnlV1DetailRow) => String(r?.portfolio || "未分组");
    const q = (pnlSearch || "").trim().toLowerCase();
    return rows.filter((r) => {
      if (pnlFilterSource !== "ALL" && sourceKey(r) !== pnlFilterSource) return false;
      if (pnlFilterInvestType !== "ALL" && investKey(r) !== pnlFilterInvestType) return false;
      if (pnlFilterPortfolio !== "ALL" && portfolioKey(r) !== pnlFilterPortfolio) return false;
      if (q) {
        const name = String(r?.bond_name || "").toLowerCase();
        const code = String(r?.asset_code || "").toLowerCase();
        if (!name.includes(q) && !code.includes(q)) return false;
      }
      return true;
    });
  }, [pnlDetailData, pnlFilterInvestType, pnlFilterPortfolio, pnlFilterSource, pnlSearch]);

  const pnlDetailTotals = useMemo(() => {
    return pnlFilteredRows.reduce(
      (acc, item) => ({
        rowsCount: acc.rowsCount + 1,
        interest: acc.interest + parseMoney(item.interest_income),
        fairValue: acc.fairValue + parseMoney(item.fair_value_change),
        capitalGain: acc.capitalGain + parseMoney(item.capital_gain),
        total: acc.total + parseMoney(item.total_pnl),
      }),
      { rowsCount: 0, interest: 0, fairValue: 0, capitalGain: 0, total: 0 },
    );
  }, [pnlFilteredRows]);

  const standardDetailRows = useMemo(
    () => pnlFilteredRows.filter((r) => r.source === "FI" || !r.source),
    [pnlFilteredRows],
  );
  const nonstdDetailRows = useMemo(() => pnlFilteredRows.filter((r) => r.source === "NonStd"), [pnlFilteredRows]);

  const standardDetailTotals = useMemo(
    () =>
      standardDetailRows.reduce(
        (acc, r) => ({
          interest: acc.interest + parseMoney(r.interest_income),
          fairValue: acc.fairValue + parseMoney(r.fair_value_change),
          capitalGain: acc.capitalGain + parseMoney(r.capital_gain),
          total: acc.total + parseMoney(r.total_pnl),
        }),
        { interest: 0, fairValue: 0, capitalGain: 0, total: 0 },
      ),
    [standardDetailRows],
  );

  const nonstdDetailTotals = useMemo(
    () =>
      nonstdDetailRows.reduce(
        (acc, r) => ({
          interest: acc.interest + parseMoney(r.interest_income),
          fairValue: acc.fairValue + parseMoney(r.fair_value_change),
          capitalGain: acc.capitalGain + parseMoney(r.capital_gain),
          total: acc.total + parseMoney(r.total_pnl),
        }),
        { interest: 0, fairValue: 0, capitalGain: 0, total: 0 },
      ),
    [nonstdDetailRows],
  );

  const aggregatePnL = useMemo(() => buildYieldAnalysisAggregates(pnlFilteredRows), [pnlFilteredRows]);
  const nonstdClassTopRows = useMemo(() => aggregatePnL.by_asset_class_nonstd.slice(0, 12), [aggregatePnL]);
  const largestDriver = useMemo(() => {
    const [first] = aggregatePnL.by_portfolio;
    return first;
  }, [aggregatePnL.by_portfolio]);
  const sourceMixText = useMemo(() => {
    if (pnlFilteredRows.length === 0) return "暂无明细";
    return `${standardDetailRows.length} 标准 / ${nonstdDetailRows.length} 非标`;
  }, [nonstdDetailRows.length, pnlFilteredRows.length, standardDetailRows.length]);

  const yieldData = yieldQuery.data;
  const history = useMemo(() => yieldData?.history ?? [], [yieldData?.history]);
  const scatter = useMemo(() => yieldData?.scatter ?? [], [yieldData?.scatter]);

  const yieldErrorMessage = yieldQuery.isError
    ? yieldQuery.error instanceof Error
      ? yieldQuery.error.message
      : "加载失败"
    : null;

  const nimDelta = useMemo(() => {
    if (history.length < 2) return null;
    const last = history[history.length - 1]?.nim;
    const prev = history[history.length - 2]?.nim;
    if (last == null || prev == null) return null;
    return last - prev;
  }, [history]);

  const yieldReportDate = reportDateParam || yieldData?.report_date || "—";
  const pnlReportDate = selectedPnlDate || "—";

  const pageDescription =
    activeTab === "pnl"
      ? "月度损益聚合（不重算口径）；先看合计与 514/516/517 拆解，再下钻排行与明细。"
      : activeTab === "period"
        ? "按期间查看收益序列与汇总。"
        : "先看静态收益与 NIM，再下钻到损益归因和期间收益。";

  const pageMetaLine =
    activeTab === "pnl"
      ? `报表月份：${pnlReportDate}`
      : activeTab === "yield"
        ? `报告日：${yieldReportDate}`
        : null;

  const yieldLoading = yieldQuery.isLoading;
  const totalPnlTone = pnlTone(pnlDetailTotals.total);

  async function handleRefreshPnL() {
    setRefreshingPnL(true);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshFormalPnl(selectedPnlDate || undefined),
        getStatus: (runId) => client.getFormalPnlImportStatus(runId),
        onUpdate: () => undefined,
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([datesQuery.refetch(), detailQuery.refetch()]);
    } catch (e) {
      setPnlError(e instanceof Error ? e.message : "刷新失败");
    } finally {
      setRefreshingPnL(false);
    }
  }

  async function fetchPnLOverview() {
    if (!selectedPnlDate) return;
    setPnlLoading(true);
    setPnlError(null);
    try {
      await client.getFormalPnlOverview(selectedPnlDate, "formal");
    } catch (e) {
      setPnlError(e instanceof Error ? e.message : "查询失败");
    } finally {
      setPnlLoading(false);
    }
  }

  const trendOption = useMemo(() => (history.length > 0 ? historyChartOption(history) : null), [history]);
  const scatterOption = useMemo(() => (scatter.length > 0 ? scatterChartOption(scatter) : null), [scatter]);

  const kpi = yieldData?.kpi;
  const nimValue = numericRaw(kpi?.nim ?? null);
  const nimNeg = nimValue != null && nimValue < 0;
  const nimUp = nimDelta != null && nimDelta >= 0;

  return (
    <section data-testid="yield-analysis-page" className="yield-analysis-page">
      <div className="yield-analysis-page-header">
        <div className="yield-analysis-page-copy">
          <h1 className="yield-analysis-page-title">收益分析</h1>
          <p className="yield-analysis-page-description">{pageDescription}</p>
          {pageMetaLine ? <p className="yield-analysis-page-meta">{pageMetaLine}</p> : null}
        </div>
        <div className="yield-analysis-page-actions">
          {activeTab !== "pnl" ? (
            <Link to="/pnl-formal-v1" className="yield-analysis-page-link">
              正式明细（表格）
            </Link>
          ) : null}
        </div>
      </div>

      <div className="yield-analysis-main-tabs" role="tablist" aria-label="收益分析主标签">
        {(
          [
            ["yield", "收益总览"],
            ["pnl", "损益归因"],
            ["period", "期间收益"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={activeTab === key}
            className="yield-analysis-main-tab"
            data-active={activeTab === key}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "yield" ? (
        yieldLoading ? (
          <div className="yield-analysis-loading">
            <Spin />
            <p className="yield-analysis-loading-caption">正在加载收益分析...</p>
          </div>
        ) : yieldErrorMessage ? (
          <div className="yield-analysis-note yield-analysis-note--error">{yieldErrorMessage}</div>
        ) : yieldData ? (
          <div className="yield-analysis-section">
            <div className="yield-analysis-kpi-grid">
              <div className="yield-analysis-metric-card">
                <div className="yield-analysis-metric-label">静态资产收益率</div>
                <div className="yield-analysis-metric-value">
                  {kpi?.asset_yield != null ? formatNumeric(kpi.asset_yield) : "—"}
                </div>
                <div className="yield-analysis-metric-caption">收益管理兼容口径，按可计息资产加权；剔除无到期日投资。</div>
              </div>
              <div className="yield-analysis-metric-card">
                <div className="yield-analysis-metric-label">综合负债成本</div>
                <div className="yield-analysis-metric-value">
                  {kpi?.liability_cost != null ? formatNumeric(kpi.liability_cost) : "—"}
                </div>
                <div className="yield-analysis-metric-caption">同业负债与发债成本的综合参考口径。</div>
              </div>
              <div className="yield-analysis-metric-card">
                <div className="yield-analysis-metric-label">市场负债成本（NIM 分母）</div>
                <div className="yield-analysis-metric-value">
                  {kpi?.market_liability_cost != null ? formatNumeric(kpi.market_liability_cost) : "—"}
                </div>
                <div className="yield-analysis-metric-caption">NIM 使用这项成本，不使用左侧综合负债成本。</div>
              </div>
              <div className="yield-analysis-metric-card">
                <div className="yield-analysis-metric-label">静态 NIM</div>
                <div className="yield-analysis-metric-nim-row">
                  <div
                    className={`yield-analysis-metric-nim-value ${nimNeg ? "yield-analysis-metric-nim-value--negative" : ""}`}
                  >
                    {kpi?.nim != null ? formatNumeric(kpi.nim) : "—"}
                  </div>
                  {nimDelta != null ? (
                    <div
                      className={`yield-analysis-metric-nim-delta ${nimUp ? "yield-analysis-metric-nim-delta--up" : "yield-analysis-metric-nim-delta--down"}`}
                    >
                      {fmtPct(nimDelta * 100)} 日变动
                    </div>
                  ) : null}
                </div>
                <div className="yield-analysis-metric-caption">静态资产收益率减市场负债成本；日均分析页使用 ADB 区间口径。</div>
              </div>
            </div>

            <div className="yield-analysis-note yield-analysis-note--warning">
              <strong className="yield-analysis-note-strong">口径提示：</strong>
              本页是收益管理兼容的静态收益/NIM 读面，资产收益率剔除无到期日投资；日均分析页使用区间日均分母。两页可以看方向，不应直接做数值对账。
            </div>

            <div className="yield-analysis-note yield-analysis-note--plain">
              <div className="yield-analysis-plain-meta">
                <span>报告日：{yieldData.report_date || "—"}</span>
                <span
                  className={
                    nimDelta == null
                      ? "yield-analysis-plain-meta__delta--neutral"
                      : nimUp
                        ? "yield-analysis-plain-meta__delta--up"
                        : "yield-analysis-plain-meta__delta--down"
                  }
                >
                  NIM 日变动：{nimDelta == null ? "—" : formatPercent(nimDelta, false)}
                </span>
              </div>
            </div>

            <div className="yield-analysis-chart-grid">
              <div className="yield-analysis-surface yield-analysis-surface--padded">
                <h3 className="yield-analysis-chart-title">息差趋势</h3>
                <p className="yield-analysis-chart-caption">
                  展示资产收益、市场负债成本与综合负债成本的相对关系。
                </p>
                {trendOption ? (
                  <BaseChart option={trendOption} height={360} />
                ) : (
                  <div className="yield-analysis-chart-empty">暂无历史序列</div>
                )}
              </div>
              <div className="yield-analysis-surface yield-analysis-surface--padded">
                <h3 className="yield-analysis-chart-title">收益-久期散点</h3>
                <p className="yield-analysis-chart-caption">以剩余期限（年）近似久期，单券收益率为 YTM。</p>
                {scatterOption ? (
                  <BaseChart option={scatterOption} height={380} />
                ) : (
                  <div className="yield-analysis-chart-empty">暂无散点数据</div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="yield-analysis-empty">当前日期下暂无可展示数据。</div>
        )
      ) : null}

      {activeTab === "pnl" ? (
        <div className="yield-analysis-section">
          <div className="yield-pnl-command-bar" data-testid="yield-analysis-pnl-toolbar">
            <div className="yield-pnl-toolbar__controls">
              <label className="yield-analysis-field yield-pnl-toolbar__field" htmlFor="pnl-yield-month-select">
                <span className="yield-analysis-label">选择报表月份</span>
                <select
                  id="pnl-yield-month-select"
                  className="yield-analysis-control"
                  aria-label="选择报表月份"
                  value={selectedPnlDate}
                  disabled={datesQuery.isLoading || availableMonths.length === 0}
                  onChange={(e) => {
                    setSelectedPnlDate(e.target.value);
                    setPnlError(null);
                    setSearchParams((prev) => {
                      const next = new URLSearchParams(prev);
                      if (e.target.value) next.set("report_date", e.target.value);
                      return next;
                    });
                  }}
                >
                  {availableMonths.length === 0 ? (
                    <option value="">{datesQuery.isLoading ? "加载中..." : "暂无可选日期"}</option>
                  ) : (
                    availableMonths.map((m) => (
                      <option key={m.ym} value={m.value}>
                        {m.label}
                      </option>
                    ))
                  )}
                </select>
              </label>

              <div className="yield-pnl-toolbar__button-group">
                <button
                  type="button"
                  className="yield-pnl-toolbar__button yield-pnl-toolbar__button--secondary"
                  disabled={refreshingPnL || !selectedPnlDate}
                  onClick={() => void handleRefreshPnL()}
                >
                  {refreshingPnL ? "刷新中..." : "刷新数据"}
                </button>
                <button
                  type="button"
                  className="yield-pnl-toolbar__button yield-pnl-toolbar__button--primary"
                  disabled={pnlLoading || !selectedPnlDate}
                  onClick={() => void fetchPnLOverview()}
                >
                  {pnlLoading ? "查询中…" : "查询汇总数据"}
                </button>
                <Link to="/pnl-formal-v1" className="yield-analysis-page-link yield-pnl-command-bar__link">
                  正式明细（表格）
                </Link>
              </div>
            </div>
          </div>

          <div className="yield-pnl-conclusion" data-testid="yield-analysis-pnl-readout">
            <div className="yield-pnl-conclusion__primary">
              <div className="yield-pnl-hero__total">
                <span className="yield-pnl-hero__label">筛选后合计损益</span>
                <strong className={`yield-pnl-hero__value yield-pnl-hero__value--${totalPnlTone}`}>
                  {fmtSignedWanYuan(pnlDetailTotals.total)}
                </strong>
                <span className="yield-pnl-hero__caption">
                  单位：万元 · 明细 {pnlFilteredRows.length} / {pnlDetailData.length} 条
                </span>
              </div>
              <div className="yield-pnl-breakdown" role="list">
                {(
                  [
                    ["514 利息收入", pnlDetailTotals.interest],
                    ["516 公允价值变动", pnlDetailTotals.fairValue],
                    ["517 投资收益", pnlDetailTotals.capitalGain],
                  ] as const
                ).map(([label, val]) => (
                  <div key={label} className="yield-pnl-breakdown__item" data-tone={pnlTone(val)}>
                    <span className="yield-pnl-breakdown__label">{label}</span>
                    <span className="yield-pnl-breakdown__value">{fmtSignedWanYuan(val)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="yield-pnl-conclusion__secondary">
              <span className="yield-pnl-toolbar__meta-item">数据来源：P&L Records</span>
              <span className="yield-pnl-toolbar__meta-item">
                主要贡献组合：{largestDriver ? largestDriver.key : "—"}
              </span>
              <span className="yield-pnl-toolbar__meta-item">来源结构：{sourceMixText}</span>
            </div>
          </div>



          <PnlFilterBar
            filterSource={pnlFilterSource}
            filterInvestType={pnlFilterInvestType}
            filterPortfolio={pnlFilterPortfolio}
            searchText={pnlSearch}
            filterOptions={pnlFilterOptions}
            onSourceChange={setPnlFilterSource}
            onInvestTypeChange={setPnlFilterInvestType}
            onPortfolioChange={setPnlFilterPortfolio}
            onSearchChange={setPnlSearch}
            onClearAll={() => {
              setPnlFilterSource("ALL");
              setPnlFilterInvestType("ALL");
              setPnlFilterPortfolio("ALL");
              setPnlSearch("");
            }}
          />

          {pnlError ? (
            <div className="yield-analysis-note yield-analysis-note--error">{pnlError}</div>
          ) : null}

          {!pnlDetailLoading && pnlDetailData.length > 0 ? (
            pnlFilteredRows.length === 0 ? (
              <div className="yield-analysis-empty">
                筛选条件下无明细结果
              </div>
            ) : (
              <section className="yield-pnl-evidence-section" aria-labelledby="yield-pnl-ranking-heading">
                <h2 id="yield-pnl-ranking-heading" className="yield-pnl-section-heading">
                  按维度排行（点击可筛选）
                </h2>
                <div className="yield-pnl-ranking-grid">
                  <RankingBarsCard title="按投资组合" rows={aggregatePnL.by_portfolio} onPick={(k) => setPnlFilterPortfolio(k)} />
                  <RankingBarsCard title="按数据来源" rows={aggregatePnL.by_source} onPick={(k) => setPnlFilterSource(k)} />
                  <RankingBarsCard title="按科目名称（Top）" rows={aggregatePnL.by_bond_name} onPick={(k) => setPnlSearch(k)} />
                  {nonstdClassTopRows.length > 0 ? (
                    <RankingBarsCard
                      title="按非标分类"
                      rows={aggregatePnL.by_asset_class_nonstd}
                      onPick={(k) => {
                        setPnlFilterSource("NonStd");
                        setPnlSearch(k);
                      }}
                    />
                  ) : null}
                  <RankingBarsCard title="按币种（投资类型）" rows={aggregatePnL.by_asset_type} onPick={(k) => setPnlFilterInvestType(k)} />
                </div>
              </section>
            )
          ) : null}

          {pnlDetailLoading ? (
            <div className="yield-analysis-loading">
              <Spin />
            </div>
          ) : standardDetailRows.length > 0 ? (
            <section className="yield-pnl-evidence-section" aria-labelledby="yield-pnl-standard-detail-heading">
              <h2 id="yield-pnl-standard-detail-heading" className="yield-pnl-section-heading">
                标准债券明细
              </h2>
              <div className="yield-pnl-detail-card" data-testid="yield-analysis-standard-detail">
              <div className="yield-pnl-detail-card__header">
                <div>
                  <strong>标准债券损益明细</strong>
                  <span>共 {standardDetailRows.length} 条 · 单位：万元</span>
                </div>
                <button
                  type="button"
                  onClick={() => setStandardDetailsExpanded((v) => !v)}
                  className="yield-pnl-detail-card__toggle"
                >
                  {standardDetailsExpanded ? "收起明细" : "展开明细"}
                </button>
              </div>
              {standardDetailsExpanded ? (
                <div className="yield-pnl-detail-table-wrap">
                  <table className="yield-pnl-detail-table yield-pnl-detail-table--wide">
                    <thead>
                      <tr>
                        {STANDARD_PNL_DETAIL_HEADERS.map((header) => (
                          <th key={header.label} data-align={header.align}>
                            {header.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {standardDetailRows.map((row, idx) => (
                        <tr key={`${row.trace_id}-${row.asset_code}-${idx}`}>
                          <td>{row.asset_code || "—"}</td>
                          <td className="yield-pnl-detail-table__name" title={row.bond_name}>
                            {row.bond_name || "—"}
                          </td>
                          <td>{row.portfolio || "—"}</td>
                          <td>{row.asset_type || "—"}</td>
                          <td data-align="right">{fmtWanYuan(parseMoney(row.interest_income))}</td>
                          <td data-align="right">{fmtWanYuan(parseMoney(row.fair_value_change))}</td>
                          <td data-align="right">{fmtWanYuan(parseMoney(row.capital_gain))}</td>
                          <td data-align="right" className="yield-pnl-detail-table__total">
                            {fmtWanYuan(parseMoney(row.total_pnl))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <td colSpan={4}>
                          合计
                        </td>
                        <td data-align="right">{fmtWanYuan(standardDetailTotals.interest)}</td>
                        <td data-align="right">{fmtWanYuan(standardDetailTotals.fairValue)}</td>
                        <td data-align="right">{fmtWanYuan(standardDetailTotals.capitalGain)}</td>
                        <td data-align="right">{fmtWanYuan(standardDetailTotals.total)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <div className="yield-pnl-detail-card__collapsed">已收起标准债券明细。</div>
              )}
              </div>
            </section>
          ) : selectedPnlDate && !pnlDetailLoading ? (
            <div className="yield-analysis-empty">暂无明细数据</div>
          ) : null}

          {!pnlDetailLoading && nonstdDetailRows.length > 0 ? (
            <section className="yield-pnl-evidence-section" aria-labelledby="yield-pnl-nonstd-detail-heading">
              <h2 id="yield-pnl-nonstd-detail-heading" className="yield-pnl-section-heading">
                非标明细
              </h2>
              <div className="yield-pnl-detail-card yield-pnl-detail-card--accent" data-testid="yield-analysis-nonstd-detail">
              <div className="yield-pnl-detail-card__header">
                <div>
                  <strong>非标损益明细</strong>
                  <span>共 {nonstdDetailRows.length} 条 · 单位：万元</span>
                </div>
              </div>
              <div className="yield-pnl-detail-table-wrap">
                <table className="yield-pnl-detail-table">
                  <thead>
                    <tr>
                      {NONSTD_PNL_DETAIL_HEADERS.map((header) => (
                        <th key={header.label} data-align={header.align}>
                          {header.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {nonstdDetailRows.map((row, idx) => (
                      <tr key={`ns-${row.trace_id}-${idx}`}>
                        <td>{row.asset_code || "—"}</td>
                        <td>{row.asset_class || row.bond_name || "—"}</td>
                        <td data-align="right">{fmtWanYuan(parseMoney(row.interest_income))}</td>
                        <td data-align="right">{fmtWanYuan(parseMoney(row.fair_value_change))}</td>
                        <td data-align="right">{fmtWanYuan(parseMoney(row.capital_gain))}</td>
                        <td data-align="right" className="yield-pnl-detail-table__total">
                          {fmtWanYuan(parseMoney(row.total_pnl))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={2}>
                        合计
                      </td>
                      <td data-align="right">{fmtWanYuan(nonstdDetailTotals.interest)}</td>
                      <td data-align="right">{fmtWanYuan(nonstdDetailTotals.fairValue)}</td>
                      <td data-align="right">{fmtWanYuan(nonstdDetailTotals.capitalGain)}</td>
                      <td data-align="right">{fmtWanYuan(nonstdDetailTotals.total)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
            </section>
          ) : null}
        </div>
      ) : null}

      {activeTab === "period" ? <YieldByPeriodPanel /> : null}
    </section>
  );
}
