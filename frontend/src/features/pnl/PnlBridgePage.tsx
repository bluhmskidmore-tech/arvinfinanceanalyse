import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "antd";
import { AgGridReact } from "ag-grid-react";
import type { CellClassParams, ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import ReactECharts, { type EChartsOption } from "../../lib/echarts";

import { useApiClient } from "../../api/client";
import { runPollingTask } from "../../app/jobs/polling";
import { FilterBar } from "../../components/FilterBar";
import type { PnlBridgeQuality, PnlBridgeRow, PnlBridgeSummary } from "../../api/contracts";
import { formatWan } from "../bond-analytics/utils/formatters";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import { pnlSurfaceQualityToTone, toneFromSignedDisplayString } from "../workbench/components/kpiFormat";
import { PnlDebugPanel, PnlRefreshStatus } from "./PnlRuntimePanels";
import {
  pnlActionButtonStyle,
  resolvePnlSectionState,
} from "./PnlRuntimeSupport";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
} as const;

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 10,
  marginBottom: 0,
  maxWidth: 860,
  color: "#5c6b82",
  fontSize: 15,
  lineHeight: 1.75,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginBottom: 16,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

const BRIDGE_CATEGORIES = [
  "票息",
  "骑乘",
  "国债曲线",
  "信用利差",
  "汇兑",
  "已实现交易",
  "未实现公允",
  "人工调整",
  "解释合计",
  "实际PnL",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

function chartAxisNumber(value: string): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function buildWaterfallOption(summary: PnlBridgeSummary): EChartsOption {
  const displayStrings = [
    summary.total_carry,
    summary.total_roll_down,
    summary.total_treasury_curve,
    summary.total_credit_spread,
    summary.total_fx_translation,
    summary.total_realized_trading,
    summary.total_unrealized_fv,
    summary.total_manual_adjustment,
    summary.total_explained_pnl,
    summary.total_actual_pnl,
  ];

  const stepValues = [
    chartAxisNumber(summary.total_carry),
    chartAxisNumber(summary.total_roll_down),
    chartAxisNumber(summary.total_treasury_curve),
    chartAxisNumber(summary.total_credit_spread),
    chartAxisNumber(summary.total_fx_translation),
    chartAxisNumber(summary.total_realized_trading),
    chartAxisNumber(summary.total_unrealized_fv),
    chartAxisNumber(summary.total_manual_adjustment),
  ];

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const value of stepValues) {
    if (value >= 0) {
      helperRaw.push(running);
      valueRaw.push(value);
      barColors.push("#cf1322");
      running += value;
    } else {
      helperRaw.push(running + value);
      valueRaw.push(-value);
      barColors.push("#3f8600");
      running += value;
    }
  }

  helperRaw.push(0);
  valueRaw.push(chartAxisNumber(summary.total_explained_pnl));
  barColors.push("#1f5eff");

  helperRaw.push(0);
  valueRaw.push(chartAxisNumber(summary.total_actual_pnl));
  barColors.push("#1f5eff");

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((item: { seriesName?: string }) => item.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = BRIDGE_CATEGORIES[idx] ?? "";
        return `${label}<br/>${formatWan(String(displayStrings[idx] ?? "0"))}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 44, containLabel: true },
    xAxis: {
      type: "category",
      data: [...BRIDGE_CATEGORIES],
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: "#5c6b82" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { type: "dashed" as const, color: "#e4ebf5" } },
      axisLabel: { fontSize: 11, color: "#5c6b82" },
    },
    series: [
      {
        name: "辅助",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "效应",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((value, index) => ({
          value,
          itemStyle: { color: barColors[index] },
        })),
      },
    ],
  };
}

function cellText(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function thousandsValueFormatter(params: ValueFormatterParams) {
  const value = params.value;
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const numeric = Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return numeric.toLocaleString("zh-CN");
}

function fxTranslationValueFormatter(params: ValueFormatterParams) {
  const value = params.value;
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return formatWan(String(value).replace(/,/g, ""));
}

const bridgeGridDefaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true,
};

const bridgeColumnDefsBase: ColDef<PnlBridgeRow>[] = [
  { field: "instrument_code", headerName: "债券代码", width: 140, pinned: "left" },
  { field: "portfolio_name", headerName: "组合", width: 120 },
  { field: "accounting_basis", headerName: "会计分类", width: 100 },
  { field: "beginning_dirty_mv", headerName: "期初脏价市值", width: 140, type: "numericColumn" },
  { field: "ending_dirty_mv", headerName: "期末脏价市值", width: 140, type: "numericColumn" },
  { field: "carry", headerName: "Carry", width: 110, type: "numericColumn" },
  { field: "roll_down", headerName: "Roll-down", width: 110, type: "numericColumn" },
  { field: "treasury_curve", headerName: "国债曲线", width: 110, type: "numericColumn" },
  { field: "credit_spread", headerName: "信用利差", width: 110, type: "numericColumn" },
  {
    field: "fx_translation",
    headerName: "汇兑效应",
    width: 110,
    type: "numericColumn",
    valueFormatter: fxTranslationValueFormatter,
  },
  { field: "realized_trading", headerName: "已实现交易", width: 120, type: "numericColumn" },
  { field: "unrealized_fv", headerName: "未实现公允", width: 120, type: "numericColumn" },
  { field: "manual_adjustment", headerName: "手工调整", width: 120, type: "numericColumn" },
  { field: "explained_pnl", headerName: "可解释损益", width: 130, type: "numericColumn" },
  { field: "actual_pnl", headerName: "实际损益", width: 120, type: "numericColumn" },
  { field: "residual", headerName: "残差", width: 100, type: "numericColumn" },
  {
    field: "quality_flag",
    headerName: "质量",
    width: 80,
    cellStyle: (params: CellClassParams<PnlBridgeRow, PnlBridgeQuality>) => ({
      color:
        params.value === "ok"
          ? shellTokens.colorSuccess
          : params.value === "warning"
            ? shellTokens.colorWarning
            : shellTokens.colorDanger,
      fontWeight: 600,
    }),
  },
];

export default function PnlBridgePage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["pnl", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDates, selectedReportDate]);

  const bridgeQuery = useQuery({
    queryKey: ["pnl", "bridge", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getPnlBridge(selectedReportDate),
    retry: false,
  });

  const summary = bridgeQuery.data?.result.summary;
  const rows = bridgeQuery.data?.result.rows ?? [];
  const warnings = bridgeQuery.data?.result.warnings ?? [];

  const chartOption = useMemo(() => (summary ? buildWaterfallOption(summary) : null), [summary]);

  const bridgeColDefs = useMemo<ColDef<PnlBridgeRow>[]>(
    () =>
      bridgeColumnDefsBase.map((def) => {
        if (def.type !== "numericColumn" || def.valueFormatter) {
          return def;
        }
        return { ...def, valueFormatter: thousandsValueFormatter };
      }),
    [],
  );

  const agGridShellStyle = useMemo(
    () =>
      ({
        height: 480,
        width: "100%",
        borderRadius: 16,
        overflow: "hidden",
        border: `1px solid ${shellTokens.colorBorderSoft}`,
        marginTop: 18,
        "--ag-header-background-color": shellTokens.colorBgMuted,
        "--ag-header-foreground-color": shellTokens.colorTextSecondary,
        "--ag-row-hover-color": shellTokens.colorBgMuted,
        "--ag-border-color": shellTokens.colorBorderSoft,
        "--ag-font-family": '"PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", sans-serif',
        "--ag-font-size": "13px",
      }) as import("react").CSSProperties,
    [],
  );

  const summaryLoading = datesQuery.isLoading || (Boolean(selectedReportDate) && bridgeQuery.isLoading);
  const summaryError = datesQuery.isError || bridgeQuery.isError;
  const summaryEmpty =
    !datesQuery.isLoading &&
    !bridgeQuery.isLoading &&
    !datesQuery.isError &&
    !bridgeQuery.isError &&
    (!selectedReportDate || (summary !== undefined && summary.row_count === 0 && rows.length === 0));

  const detailLoading = summaryLoading;
  const detailError = summaryError;
  const detailEmpty =
    !datesQuery.isLoading &&
    !bridgeQuery.isLoading &&
    !datesQuery.isError &&
    !bridgeQuery.isError &&
    (!selectedReportDate || rows.length === 0);

  const summaryState = resolvePnlSectionState({
    isLoading: summaryLoading,
    isError: summaryError,
    isEmpty: summaryEmpty,
  });
  const detailState = resolvePnlSectionState({
    isLoading: detailLoading,
    isError: detailError,
    isEmpty: detailEmpty,
  });

  const reportDatePlaceholder = datesQuery.isLoading
    ? "正在载入报告日"
    : datesQuery.isError
      ? "报告日加载失败"
      : "暂无可选报告日";
  const reportDateSelectDisabled = datesQuery.isLoading || datesQuery.isError || reportDates.length === 0;
  const refreshDisabled = !selectedReportDate || isRefreshing;

  const debugSnapshot = {
    client_mode: client.mode,
    selected_report_date: selectedReportDate || null,
    available_report_dates: reportDates,
    summary_state: summaryState,
    detail_state: detailState,
    dates: {
      result_meta: datesQuery.data?.result_meta ?? null,
      error: datesQuery.error instanceof Error ? datesQuery.error.message : null,
      report_dates: reportDates,
    },
    bridge: {
      result_meta: bridgeQuery.data?.result_meta ?? null,
      error: bridgeQuery.error instanceof Error ? bridgeQuery.error.message : null,
      payload: selectedReportDate
        ? {
            report_date: selectedReportDate,
            row_count: rows.length,
            summary_row_count: summary?.row_count ?? null,
          }
        : null,
    },
    refresh: {
      status: refreshStatus,
      error: refreshError,
    },
  };

  async function handleRefresh() {
    if (!selectedReportDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshFormalPnl(selectedReportDate),
        getStatus: (runId) => client.getFormalPnlImportStatus(runId),
        onUpdate: (nextPayload) => {
          setRefreshStatus(
            [nextPayload.status, nextPayload.run_id, nextPayload.report_date, nextPayload.source_version]
              .filter(Boolean)
              .join(" · "),
          );
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新 PnL Bridge 失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section data-testid="pnl-bridge-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="pnl-bridge-page-title"
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            损益桥接
          </h1>
          <p
            data-testid="pnl-bridge-page-subtitle"
            style={pageSubtitleStyle}
          >
            正式口径损益桥接由后端 <code>/api/pnl/bridge</code> 提供；本页仅展示返回结果与汇总图表，不在浏览器端做金融重算。
          </p>
        </div>
        <span
          style={{
            ...modeBadgeStyle,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
          }}
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="pnl-bridge-report-date"
            value={selectedReportDate}
            disabled={reportDateSelectDisabled}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
          >
            {reportDates.length === 0 ? (
              <option value="">{reportDatePlaceholder}</option>
            ) : (
              reportDates.map((reportDate) => (
                <option key={reportDate} value={reportDate}>
                  {reportDate}
                </option>
              ))
            )}
          </select>
        </label>
        <button
          data-testid="pnl-bridge-refresh-button"
          type="button"
          disabled={refreshDisabled}
          onClick={() => void handleRefresh()}
          style={pnlActionButtonStyle}
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
      </FilterBar>

      <PnlRefreshStatus testId="pnl-bridge-refresh-status" status={refreshStatus} error={refreshError} />

      <div data-testid="pnl-bridge-summary-section" data-state={summaryState} style={{ marginBottom: 24 }}>
        <SectionLead
          eyebrow="Overview"
          title="正式桥接汇总"
          description="先确认报告日与刷新状态，再阅读 explained PnL、actual PnL、residual 和质量标识；所有数值均来自后端 bridge read model。"
        />
        <AsyncSection
          title="汇总"
          isLoading={summaryLoading}
          isError={summaryError}
          isEmpty={summaryEmpty}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
          }}
        >
          {summary ? (
            <>
              <div data-testid="pnl-bridge-summary-cards" style={summaryGridStyle}>
                <KpiCard title="行数" value={cellText(summary.row_count)} detail="summary.row_count" unit="行" />
                <KpiCard title="质量 ok" value={cellText(summary.ok_count)} detail="summary.ok_count" tone="default" />
                <KpiCard
                  title="质量 warning"
                  value={cellText(summary.warning_count)}
                  detail="summary.warning_count"
                  tone="warning"
                />
                <KpiCard title="质量 error" value={cellText(summary.error_count)} detail="summary.error_count" tone="error" />
                <KpiCard
                  title="合计 explained PnL"
                  value={summary.total_explained_pnl}
                  detail="summary.total_explained_pnl"
                  tone={toneFromSignedDisplayString(summary.total_explained_pnl)}
                />
                <KpiCard
                  title="合计 actual PnL"
                  value={summary.total_actual_pnl}
                  detail="summary.total_actual_pnl"
                  tone={toneFromSignedDisplayString(summary.total_actual_pnl)}
                />
                <KpiCard
                  title="合计 residual"
                  value={summary.total_residual}
                  detail="summary.total_residual"
                  tone={toneFromSignedDisplayString(summary.total_residual)}
                />
                <KpiCard
                  title="质量 quality_flag"
                  value={summary.quality_flag}
                  detail="summary.quality_flag（取各行最差等级）"
                  tone={pnlSurfaceQualityToTone(summary.quality_flag)}
                />
              </div>

              {chartOption ? (
                <Card
                  data-testid="pnl-bridge-waterfall-card"
                  title="PnL Bridge 效应拆解"
                  size="small"
                  style={{
                    marginTop: 24,
                    borderRadius: 18,
                    border: "1px solid #e8edf4",
                    boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
                    background: "#ffffff",
                  }}
                  styles={{ body: { padding: "12px 16px 16px" } }}
                >
                  <div style={{ height: 400 }}>
                    <ReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} opts={{ renderer: "canvas" }} />
                  </div>
                </Card>
              ) : null}

              {warnings.length > 0 ? (
                <div
                  data-testid="pnl-bridge-warnings"
                  style={{
                    marginTop: 24,
                    padding: 16,
                    borderRadius: 14,
                    background: "#fffbeb",
                    border: "1px solid #f5e0a8",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: 8, color: "#92400e" }}>Warnings</div>
                  <ul style={{ margin: 0, paddingLeft: 20, color: "#5c6b82" }}>
                    {warnings.map((warning) => (
                      <li key={warning} style={{ marginBottom: 6 }}>
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </AsyncSection>
      </div>

      <div data-testid="pnl-bridge-detail-section" data-state={detailState}>
        <SectionLead
          eyebrow="Details"
          title="桥接明细与归因瀑布"
          description="瀑布图和明细表共用当前报告日，保留原有图表、AG Grid、分页和 result_meta 调试链路，不改变正式桥接契约。"
        />
        <AsyncSection
          title="桥接明细"
          isLoading={detailLoading}
          isError={detailError}
          isEmpty={detailEmpty}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
          }}
        >
          <div className="ag-theme-alpine" data-testid="pnl-bridge-detail-table" style={agGridShellStyle}>
            <AgGridReact<PnlBridgeRow>
              rowData={rows}
              columnDefs={bridgeColDefs}
              defaultColDef={bridgeGridDefaultColDef}
              animateRows
              pagination
              paginationPageSize={50}
              getRowId={(params) =>
                `${String(params.data.instrument_code)}-${String(params.data.portfolio_name)}-${String(params.data.accounting_basis)}`
              }
            />
          </div>
        </AsyncSection>
      </div>

      <PnlDebugPanel testId="pnl-bridge-result-meta-panel" snapshot={debugSnapshot} />
    </section>
  );
}
