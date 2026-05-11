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
import { shellTokens } from "../../theme/tokens";
import { runPollingTask } from "../../app/jobs/polling";
import { PnlFilterBar } from "./yieldAnalysis/PnlFilterBar";
import { RankingBarsCard } from "./yieldAnalysis/RankingBarsCard";
import { YieldByPeriodPanel } from "./yieldAnalysis/YieldByPeriodPanel";
import { buildYieldAnalysisAggregates } from "./yieldAnalysis/yieldAnalysisAggregates";

type MainTab = "yield" | "pnl" | "period";

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

function tabButtonStyle(active: boolean) {
  return {
    padding: "10px 16px",
    borderRadius: 12,
    border: active ? `1px solid ${designTokens.color.neutral[300]}` : "1px solid transparent",
    background: active ? "#ffffff" : "transparent",
    color: active ? designTokens.color.neutral[900] : designTokens.color.neutral[500],
    fontWeight: 600,
    fontSize: 14,
    cursor: "pointer",
    boxShadow: active ? designTokens.shadow.card : "none",
  } as const;
}

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
    xAxis: { type: "category", data: dates, axisLabel: { color: "#64748b" } },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%`, color: "#64748b" } },
    series: [
      { name: "市场负债成本(%)", type: "line", data: mkt, smooth: true, areaStyle: { opacity: 0.12 }, lineStyle: { color: "#6366f1" } },
      { name: "息差(%)", type: "line", data: spread, smooth: true, areaStyle: { color: "rgba(34,197,94,0.15)" }, lineStyle: { color: "#22c55e" } },
      { name: "资产收益(%)", type: "line", data: asset, smooth: true, lineStyle: { width: 2, color: "#1d4ed8" } },
      { name: "综合负债成本(%)", type: "line", data: liab, smooth: true, lineStyle: { type: "dashed", color: "#94a3b8" } },
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
    xAxis: { type: "value", name: "久期(y)", nameLocation: "middle", nameGap: 28, axisLabel: { color: "#64748b" } },
    yAxis: { type: "value", name: "收益率(%)", axisLabel: { color: "#64748b" } },
    series: [
      {
        type: "scatter",
        symbolSize: 12,
        data,
        itemStyle: { color: "#3b82f6", opacity: 0.75 },
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

  const displayReportDate =
    reportDateParam || yieldData?.report_date || selectedPnlDate || "—";

  const yieldLoading = yieldQuery.isLoading;

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
    <section data-testid="yield-analysis-page" style={{ maxWidth: 1120, margin: "0 auto", padding: "8px 0 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 30, fontWeight: 700, color: designTokens.color.neutral[900] }}>收益分析</h1>
          <p style={{ margin: "10px 0 0", fontSize: 15, color: designTokens.color.neutral[600], maxWidth: 720, lineHeight: 1.75 }}>
            先看总览，再下钻到损益归因和期间收益。
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 14, color: designTokens.color.neutral[500] }}>
            报告日：{displayReportDate}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              borderRadius: 999,
              border: `1px solid ${shellTokens.colorBorderSoft}`,
              background: "#fff",
              padding: "8px 16px",
              boxShadow: designTokens.shadow.card,
            }}
          >
            <span style={{ fontSize: 14, fontWeight: 600, color: designTokens.color.neutral[700] }}>Performance</span>
          </div>
          <Link
            to="/pnl-formal-v1"
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "8px 12px",
              borderRadius: 999,
              border: `1px solid ${shellTokens.colorBorderSoft}`,
              background: "#ffffff",
              color: designTokens.color.neutral[900],
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            正式明细（表格）
          </Link>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <div
          style={{
            display: "inline-flex",
            borderRadius: 14,
            border: `1px solid ${shellTokens.colorBorderSoft}`,
            background: designTokens.color.neutral[100],
            padding: 4,
            gap: 4,
          }}
        >
          {(
            [
              ["yield", "收益总览"],
              ["pnl", "损益归因"],
              ["period", "期间收益"],
            ] as const
          ).map(([key, label]) => (
            <button key={key} type="button" style={tabButtonStyle(activeTab === key)} onClick={() => setActiveTab(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "yield" ? (
        yieldLoading ? (
          <div style={{ padding: 48, textAlign: "center" }}>
            <Spin />
            <p style={{ marginTop: 12, color: designTokens.color.neutral[600] }}>正在加载收益分析...</p>
          </div>
        ) : yieldErrorMessage ? (
          <div style={{ borderRadius: 14, border: `1px solid ${designTokens.color.danger[200]}`, background: designTokens.color.danger[50], padding: 16, color: designTokens.color.danger[800] }}>
            {yieldErrorMessage}
          </div>
        ) : yieldData ? (
          <div style={{ display: "grid", gap: 24 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: 16,
              }}
            >
              <div style={{ borderRadius: 12, background: designTokens.color.neutral[50], padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: designTokens.color.neutral[500] }}>资产收益率</div>
                <div style={{ marginTop: 8, fontSize: 24, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                  {kpi?.asset_yield != null ? formatNumeric(kpi.asset_yield) : "—"}
                </div>
                <div style={{ marginTop: 8, fontSize: 12, color: designTokens.color.neutral[500] }}>按债券账面价值加权后的收益率口径。</div>
              </div>
              <div style={{ borderRadius: 12, background: designTokens.color.neutral[50], padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: designTokens.color.neutral[500] }}>综合负债成本</div>
                <div style={{ marginTop: 8, fontSize: 24, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                  {kpi?.liability_cost != null ? formatNumeric(kpi.liability_cost) : "—"}
                </div>
                <div style={{ marginTop: 8, fontSize: 12, color: designTokens.color.neutral[500] }}>同业负债与发债成本的综合参考口径。</div>
              </div>
              <div style={{ borderRadius: 12, background: designTokens.color.neutral[50], padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: designTokens.color.neutral[500] }}>市场负债成本</div>
                <div style={{ marginTop: 8, fontSize: 24, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                  {kpi?.market_liability_cost != null ? formatNumeric(kpi.market_liability_cost) : "—"}
                </div>
                <div style={{ marginTop: 8, fontSize: 12, color: designTokens.color.neutral[500] }}>对应金融市场同业负债成本口径。</div>
              </div>
              <div style={{ borderRadius: 12, background: designTokens.color.neutral[50], padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: designTokens.color.neutral[500] }}>NIM</div>
                <div style={{ marginTop: 8, display: "flex", alignItems: "flex-end", gap: 12 }}>
                  <div
                    style={{
                      fontSize: 24,
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                      color: nimNeg ? designTokens.color.danger[700] : designTokens.color.neutral[900],
                    }}
                  >
                    {kpi?.nim != null ? formatNumeric(kpi.nim) : "—"}
                  </div>
                  {nimDelta != null ? (
                    <div style={{ fontSize: 14, fontWeight: 600, color: nimUp ? designTokens.color.success[700] : designTokens.color.danger[700] }}>
                      {fmtPct(nimDelta * 100)} 日变动
                    </div>
                  ) : null}
                </div>
                <div style={{ marginTop: 8, fontSize: 12, color: designTokens.color.neutral[500] }}>资产收益率减市场负债成本的核心息差指标。</div>
              </div>
            </div>

            <div
              style={{
                borderRadius: 14,
                border: `1px solid ${shellTokens.colorBorderSoft}`,
                background: "#fff",
                padding: "12px 16px",
                fontSize: 13,
                color: designTokens.color.neutral[600],
              }}
            >
              <span style={{ marginRight: 12 }}>报告日：{yieldData.report_date || "—"}</span>
              <span style={{ color: nimDelta == null ? designTokens.color.neutral[500] : nimUp ? designTokens.color.success[700] : designTokens.color.danger[700] }}>
                NIM 日变动：{nimDelta == null ? "—" : formatPercent(nimDelta, false)}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
              <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, padding: 16, background: "#fff" }}>
                <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 700 }}>息差趋势</h3>
                <p style={{ margin: "0 0 12px", fontSize: 12, color: designTokens.color.neutral[600] }}>
                  展示资产收益、市场负债成本与综合负债成本的相对关系。
                </p>
                {trendOption ? <BaseChart option={trendOption} height={360} /> : <div style={{ color: designTokens.color.neutral[500], padding: 24 }}>暂无历史序列</div>}
              </div>
              <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, padding: 16, background: "#fff" }}>
                <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 700 }}>收益-久期散点</h3>
                <p style={{ margin: "0 0 12px", fontSize: 12, color: designTokens.color.neutral[600] }}>
                  以剩余期限（年）近似久期，单券收益率为 YTM。
                </p>
                {scatterOption ? <BaseChart option={scatterOption} height={380} /> : <div style={{ color: designTokens.color.neutral[500], padding: 24 }}>暂无散点数据</div>}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ color: designTokens.color.neutral[500] }}>当前日期下暂无可展示数据。</div>
        )
      ) : null}

      {activeTab === "pnl" ? (
        <div style={{ display: "grid", gap: 20 }}>
          <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, background: "#fff", padding: 24, boxShadow: designTokens.shadow.card }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: designTokens.color.neutral[900] }}>损益表归因分析</h2>
                <p style={{ margin: "8px 0 0", fontSize: 12, fontWeight: 600, color: designTokens.color.neutral[600], maxWidth: 720 }}>
                  基于明细数据自动聚合，支持按投资组合、投资类型、数据来源、债券名称等多维度分析（可筛选）
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <div style={{ border: `1px solid ${shellTokens.colorBorderSoft}`, borderRadius: 8, padding: "8px 14px", background: "#fff" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: designTokens.color.neutral[600] }}>数据来源</div>
                  <div style={{ fontSize: 14, fontWeight: 800 }}>P&L Records</div>
                </div>
                <button
                  type="button"
                  disabled={refreshingPnL || !selectedPnlDate}
                  onClick={() => void handleRefreshPnL()}
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: `2px solid ${designTokens.color.neutral[900]}`,
                    background: refreshingPnL ? designTokens.color.neutral[200] : "#fff",
                    cursor: refreshingPnL ? "not-allowed" : "pointer",
                  }}
                >
                  {refreshingPnL ? "刷新中..." : "刷新数据"}
                </button>
              </div>
            </div>
          </div>

          <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, background: "#fff", padding: 20 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 200px" }}>
                <label
                  htmlFor="pnl-yield-month-select"
                  style={{ display: "block", marginBottom: 8, fontSize: 11, fontWeight: 700, color: designTokens.color.neutral[500] }}
                >
                  选择报表月份
                </label>
                <select
                  id="pnl-yield-month-select"
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
                  style={{
                    width: "100%",
                    height: 44,
                    borderRadius: 10,
                    border: `1px solid ${shellTokens.colorBorderSoft}`,
                    padding: "0 12px",
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
              </div>
              <button
                type="button"
                disabled={pnlLoading || !selectedPnlDate}
                onClick={() => void fetchPnLOverview()}
                style={{
                  height: 44,
                  padding: "0 22px",
                  borderRadius: 10,
                  border: "none",
                  background: designTokens.color.neutral[900],
                  color: "#fff",
                  fontWeight: 600,
                  cursor: pnlLoading || !selectedPnlDate ? "not-allowed" : "pointer",
                  opacity: pnlLoading || !selectedPnlDate ? 0.5 : 1,
                }}
              >
                {pnlLoading ? "查询中…" : "查询汇总数据"}
              </button>
            </div>
          </div>

          <PnlFilterBar
            filterSource={pnlFilterSource}
            filterInvestType={pnlFilterInvestType}
            filterPortfolio={pnlFilterPortfolio}
            searchText={pnlSearch}
            filterOptions={pnlFilterOptions}
            filteredCount={pnlFilteredRows.length}
            totalCount={pnlDetailData.length}
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
            <div style={{ borderRadius: 14, border: `1px solid ${designTokens.color.danger[200]}`, background: designTokens.color.danger[50], padding: 16, color: designTokens.color.danger[800] }}>
              {pnlError}
            </div>
          ) : null}

          {!pnlDetailLoading && pnlDetailData.length > 0 ? (
            pnlFilteredRows.length === 0 ? (
              <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, padding: 40, textAlign: "center", background: "#fff" }}>
                筛选条件下无明细结果
              </div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
                  {(
                    [
                      ["514利息收入", pnlDetailTotals.interest, designTokens.color.success[700]],
                      ["516公允价值变动损益", pnlDetailTotals.fairValue, designTokens.color.primary[600]],
                      ["517投资收益", pnlDetailTotals.capitalGain, designTokens.color.primary[700]],
                      ["合计损益", pnlDetailTotals.total, designTokens.color.neutral[900]],
                    ] as const
                  ).map(([title, val, color]) => (
                    <div key={title} style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, padding: 20, background: "#fff" }}>
                      <div style={{ fontSize: 10, fontWeight: 800, color: designTokens.color.neutral[600] }}>{title}</div>
                      <div style={{ marginTop: 8, fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums", color }}>{fmtWanYuan(val)} 万</div>
                    </div>
                  ))}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
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
              </>
            )
          ) : null}

          {pnlDetailLoading ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <Spin />
            </div>
          ) : standardDetailRows.length > 0 ? (
            <div style={{ borderRadius: 16, border: `1px solid ${shellTokens.colorBorderSoft}`, background: "#fff", overflow: "hidden" }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", borderBottom: `1px solid ${shellTokens.colorBorderSoft}` }}>
                <strong>标准债券损益明细</strong>
                <button type="button" onClick={() => setStandardDetailsExpanded((v) => !v)} style={{ fontSize: 12 }}>
                  {standardDetailsExpanded ? "收起明细" : "展开明细"}
                </button>
              </div>
              {standardDetailsExpanded ? (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ minWidth: 900, width: "100%", borderCollapse: "collapse" }}>
                    <thead style={{ background: designTokens.color.neutral[50] }}>
                      <tr>
                        {["资产代码", "债券名称", "投资组合", "资产类型", "利息收入", "公允价值变动", "投资收益", "总损益"].map((h) => (
                          <th key={h} style={{ padding: "8px 10px", textAlign: h.includes("收入") || h.includes("变动") || h.includes("收益") || h.includes("损益") ? "right" : "left", fontSize: 11, color: designTokens.color.neutral[500] }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {standardDetailRows.map((row, idx) => (
                        <tr key={`${row.trace_id}-${row.asset_code}-${idx}`} style={{ borderTop: `1px solid ${shellTokens.colorBorderSoft}` }}>
                          <td style={{ padding: "8px 10px", fontSize: 12 }}>{row.asset_code || "—"}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={row.bond_name}>
                            {row.bond_name || "—"}
                          </td>
                          <td style={{ padding: "8px 10px", fontSize: 12 }}>{row.portfolio || "—"}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12 }}>{row.asset_type || "—"}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12, textAlign: "right" }}>{fmtWanYuan(parseMoney(row.interest_income))}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12, textAlign: "right" }}>{fmtWanYuan(parseMoney(row.fair_value_change))}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12, textAlign: "right" }}>{fmtWanYuan(parseMoney(row.capital_gain))}</td>
                          <td style={{ padding: "8px 10px", fontSize: 12, textAlign: "right", fontWeight: 700 }}>{fmtWanYuan(parseMoney(row.total_pnl))}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot style={{ background: designTokens.color.neutral[50] }}>
                      <tr>
                        <td colSpan={4} style={{ padding: "8px 10px", fontWeight: 700 }}>
                          合计
                        </td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700 }}>{fmtWanYuan(standardDetailTotals.interest)}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700 }}>{fmtWanYuan(standardDetailTotals.fairValue)}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700 }}>{fmtWanYuan(standardDetailTotals.capitalGain)}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700 }}>{fmtWanYuan(standardDetailTotals.total)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <div style={{ padding: 16, fontSize: 13, color: designTokens.color.neutral[500] }}>已收起标准债券明细。</div>
              )}
            </div>
          ) : selectedPnlDate && !pnlDetailLoading ? (
            <div style={{ padding: 32, textAlign: "center", color: designTokens.color.neutral[500] }}>暂无明细数据</div>
          ) : null}

          {!pnlDetailLoading && nonstdDetailRows.length > 0 ? (
            <div style={{ borderRadius: 16, border: `2px solid ${designTokens.color.neutral[900]}`, overflow: "hidden", background: "#fff" }}>
              <div style={{ padding: "12px 16px", background: designTokens.color.neutral[50], borderBottom: `2px solid ${designTokens.color.neutral[900]}` }}>
                <strong>非标损益明细（单位：万）</strong> · 共 {nonstdDetailRows.length} 条
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: designTokens.color.neutral[100] }}>
                      {["资产代码", "资产类型（映射）", "利息收入514", "公允价值变动516", "资本利得517", "总损益"].map((h) => (
                        <th key={h} style={{ padding: "8px 10px", textAlign: h === "资产代码" || h.startsWith("资产") ? "left" : "right", fontSize: 10, fontWeight: 800 }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {nonstdDetailRows.map((row, idx) => (
                      <tr key={`ns-${row.trace_id}-${idx}`} style={{ borderTop: `1px solid ${shellTokens.colorBorderSoft}` }}>
                        <td style={{ padding: "8px 10px", fontSize: 12 }}>{row.asset_code || "—"}</td>
                        <td style={{ padding: "8px 10px", fontSize: 12 }}>{row.asset_class || row.bond_name || "—"}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontSize: 12 }}>{fmtWanYuan(parseMoney(row.interest_income))}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontSize: 12 }}>{fmtWanYuan(parseMoney(row.fair_value_change))}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontSize: 12 }}>{fmtWanYuan(parseMoney(row.capital_gain))}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontSize: 12, fontWeight: 800 }}>{fmtWanYuan(parseMoney(row.total_pnl))}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: `2px solid ${designTokens.color.neutral[900]}` }}>
                      <td colSpan={2} style={{ padding: "8px 10px", fontWeight: 800 }}>
                        合计
                      </td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 800 }}>{fmtWanYuan(nonstdDetailTotals.interest)}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 800 }}>{fmtWanYuan(nonstdDetailTotals.fairValue)}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 800 }}>{fmtWanYuan(nonstdDetailTotals.capitalGain)}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 800 }}>{fmtWanYuan(nonstdDetailTotals.total)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === "period" ? <YieldByPeriodPanel /> : null}
    </section>
  );
}
