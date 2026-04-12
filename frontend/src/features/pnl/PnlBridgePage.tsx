import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { CellClassParams, ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import ReactECharts, { type EChartsOption } from "../../lib/echarts";

import { useApiClient } from "../../api/client";
import type { PnlBridgeQuality, PnlBridgeRow, PnlBridgeSummary } from "../../api/contracts";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
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

const POS_COLOR = "#5b8ff9";
const NEG_COLOR = "#e8684a";

/** 仅将后端字符串解析为坐标轴数值，不做损益重算。 */
function chartAxisNumber(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function buildWaterfallOption(summary: PnlBridgeSummary): EChartsOption {
  const categoryLabels = [
    "Carry",
    "Roll-down",
    "利率曲线",
    "信用利差",
    "外汇",
    "已实现交易",
    "未实现公允",
    "手工调整",
    "合计",
  ];
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
  ];
  const drivers = [
    chartAxisNumber(summary.total_carry),
    chartAxisNumber(summary.total_roll_down),
    chartAxisNumber(summary.total_treasury_curve),
    chartAxisNumber(summary.total_credit_spread),
    chartAxisNumber(summary.total_fx_translation),
    chartAxisNumber(summary.total_realized_trading),
    chartAxisNumber(summary.total_unrealized_fv),
    chartAxisNumber(summary.total_manual_adjustment),
  ];
  const totalExplained = chartAxisNumber(summary.total_explained_pnl);

  const help: number[] = [];
  const upward: (number | string)[] = [];
  const downward: (number | string)[] = [];
  let acc = 0;
  for (const v of drivers) {
    if (v >= 0) {
      help.push(acc);
      upward.push(v);
      downward.push("-");
      acc += v;
    } else {
      help.push(acc + v);
      upward.push("-");
      downward.push(-v);
      acc += v;
    }
  }
  if (totalExplained >= 0) {
    help.push(0);
    upward.push(totalExplained);
    downward.push("-");
  } else {
    help.push(totalExplained);
    upward.push("-");
    downward.push(-totalExplained);
  }

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        if (!Array.isArray(params) || params.length === 0) {
          return "";
        }
        const first = params[0] as { dataIndex?: number };
        const idx = first.dataIndex;
        if (typeof idx !== "number" || idx < 0 || idx >= categoryLabels.length) {
          return "";
        }
        const name = categoryLabels[idx];
        const text = displayStrings[idx] ?? "";
        return `${name}<br/>${text}`;
      },
    },
    legend: {
      data: ["正向", "负向"],
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 56, right: 20, top: 28, bottom: 72 },
    xAxis: {
      type: "category",
      data: categoryLabels,
      axisLabel: { interval: 0, rotate: 28, fontSize: 11, color: "#5c6b82" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { type: "dashed" as const, color: "#e4ebf5" } },
      axisLabel: { fontSize: 11, color: "#5c6b82" },
    },
    series: [
      {
        name: "placeholder",
        type: "bar",
        stack: "wf",
        silent: true,
        itemStyle: {
          borderColor: "transparent",
          color: "transparent",
        },
        emphasis: {
          itemStyle: {
            borderColor: "transparent",
            color: "transparent",
          },
        },
        data: help,
      },
      {
        name: "正向",
        type: "bar",
        stack: "wf",
        label: { show: true, position: "top", fontSize: 10, color: "#162033" },
        itemStyle: { color: POS_COLOR },
        data: upward,
      },
      {
        name: "负向",
        type: "bar",
        stack: "wf",
        label: { show: true, position: "bottom", fontSize: 10, color: "#162033" },
        itemStyle: { color: NEG_COLOR },
        data: downward,
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

function thousandsValueFormatter(params: ValueFormatterParams) {
  const v = params.value;
  if (v === null || v === undefined || v === "") {
    return "—";
  }
  const raw = String(v).replace(/,/g, "");
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return String(v);
  }
  return n.toLocaleString("zh-CN");
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
  {
    field: "beginning_dirty_mv",
    headerName: "期初脏价市值",
    width: 140,
    type: "numericColumn",
  },
  { field: "ending_dirty_mv", headerName: "期末脏价市值", width: 140, type: "numericColumn" },
  { field: "carry", headerName: "Carry", width: 110, type: "numericColumn" },
  { field: "roll_down", headerName: "Roll-down", width: 110, type: "numericColumn" },
  { field: "treasury_curve", headerName: "国债曲线", width: 110, type: "numericColumn" },
  { field: "credit_spread", headerName: "信用利差", width: 110, type: "numericColumn" },
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

  const datesQuery = useQuery({
    queryKey: ["pnl", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates(),
    retry: false,
  });

  useEffect(() => {
    const firstDate = datesQuery.data?.result.report_dates?.[0];
    if (!selectedReportDate && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [datesQuery.data?.result.report_dates, selectedReportDate]);

  const bridgeQuery = useQuery({
    queryKey: ["pnl", "bridge", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getPnlBridge(selectedReportDate),
    retry: false,
  });

  const summary = bridgeQuery.data?.result.summary;
  const rows = bridgeQuery.data?.result.rows ?? [];
  const warnings = bridgeQuery.data?.result.warnings ?? [];

  const chartOption = useMemo(
    () => (summary ? buildWaterfallOption(summary) : null),
    [summary],
  );

  const bridgeColDefs = useMemo<ColDef<PnlBridgeRow>[]>(
    () =>
      bridgeColumnDefsBase.map((def) =>
        def.type === "numericColumn" ? { ...def, valueFormatter: thousandsValueFormatter } : def,
      ),
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

  const summaryLoading =
    datesQuery.isLoading || (Boolean(selectedReportDate) && bridgeQuery.isLoading);
  const summaryError = datesQuery.isError || bridgeQuery.isError;
  const summaryEmpty =
    !datesQuery.isLoading &&
    !bridgeQuery.isLoading &&
    !datesQuery.isError &&
    !bridgeQuery.isError &&
    (!selectedReportDate ||
      (summary !== undefined &&
        summary.row_count === 0 &&
        rows.length === 0));

  const tableLoading = summaryLoading;
  const tableError = summaryError;
  const tableEmpty =
    !datesQuery.isLoading &&
    !bridgeQuery.isLoading &&
    !datesQuery.isError &&
    !bridgeQuery.isError &&
    (!selectedReportDate || rows.length === 0);

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
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
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          正式口径损益桥接由后端 <code>/api/pnl/bridge</code>{" "}
          提供；本页仅展示返回结果与汇总图表，不在浏览器端做金融重算。
        </p>
      </div>

      <div style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="pnl-bridge-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ marginBottom: 24 }}>
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
                <PlaceholderCard
                  title="行数"
                  value={cellText(summary.row_count)}
                  detail="summary.row_count"
                />
                <PlaceholderCard
                  title="质量 ok"
                  value={cellText(summary.ok_count)}
                  detail="summary.ok_count"
                />
                <PlaceholderCard
                  title="质量 warning"
                  value={cellText(summary.warning_count)}
                  detail="summary.warning_count"
                />
                <PlaceholderCard
                  title="质量 error"
                  value={cellText(summary.error_count)}
                  detail="summary.error_count"
                />
                <PlaceholderCard
                  title="合计 explained PnL"
                  value={summary.total_explained_pnl}
                  detail="summary.total_explained_pnl"
                />
                <PlaceholderCard
                  title="合计 actual PnL"
                  value={summary.total_actual_pnl}
                  detail="summary.total_actual_pnl"
                />
                <PlaceholderCard
                  title="合计 residual"
                  value={summary.total_residual}
                  detail="summary.total_residual"
                />
                <PlaceholderCard
                  title="质量 quality_flag"
                  value={summary.quality_flag}
                  detail="summary.quality_flag（取各行最差等级）"
                  surfaceTone={summary.quality_flag}
                />
              </div>

              {chartOption ? (
                <div style={{ marginTop: 24 }}>
                  <div style={{ marginBottom: 8, fontWeight: 600, color: "#162033" }}>
                    桥接分解（汇总分项，瀑布图）
                  </div>
                  <ReactECharts option={chartOption} style={{ height: 360, width: "100%" }} />
                </div>
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
                    {warnings.map((w) => (
                      <li key={w} style={{ marginBottom: 6 }}>
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </AsyncSection>
      </div>

      <AsyncSection
        title="桥接明细"
        isLoading={tableLoading}
        isError={tableError}
        isEmpty={tableEmpty}
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
            getRowId={(p) =>
              `${String(p.data.instrument_code)}-${String(p.data.portfolio_name)}-${String(p.data.accounting_basis)}`
            }
          />
        </div>
      </AsyncSection>
    </section>
  );
}
