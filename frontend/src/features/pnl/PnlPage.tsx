import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { useApiClient } from "../../api/client";
import type { PnlFormalFiRow, PnlNonStdBridgeRow } from "../../api/contracts";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
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

const tabBarStyle = {
  display: "flex",
  gap: 8,
  marginBottom: 16,
  flexWrap: "wrap",
} as const;

function tabButtonStyle(active: boolean) {
  return {
    padding: "10px 16px",
    borderRadius: 12,
    border: active ? "1px solid #1f5eff" : "1px solid #d7dfea",
    background: active ? "#edf3ff" : "#ffffff",
    color: active ? "#1f5eff" : "#162033",
    fontWeight: 600,
    cursor: "pointer",
  } as const;
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

const formalFiColumnDefs: ColDef<PnlFormalFiRow>[] = [
  { field: "instrument_code", headerName: "债券代码", width: 140, pinned: "left" },
  { field: "portfolio_name", headerName: "组合", width: 120 },
  { field: "cost_center", headerName: "成本中心", width: 120 },
  { field: "invest_type_std", headerName: "投资类型", width: 120 },
  { field: "accounting_basis", headerName: "会计分类", width: 100 },
  { field: "interest_income_514", headerName: "利息收入(514)", width: 140, type: "numericColumn" },
  { field: "fair_value_change_516", headerName: "公允变动(516)", width: 140, type: "numericColumn" },
  { field: "capital_gain_517", headerName: "资本利得(517)", width: 140, type: "numericColumn" },
  { field: "manual_adjustment", headerName: "手工调整", width: 120, type: "numericColumn" },
  { field: "total_pnl", headerName: "合计损益", width: 130, type: "numericColumn" },
];

const nonstdBridgeColumnDefs: ColDef<PnlNonStdBridgeRow>[] = [
  { field: "bond_code", headerName: "债券代码", width: 140, pinned: "left" },
  { field: "portfolio_name", headerName: "组合", width: 120 },
  { field: "cost_center", headerName: "成本中心", width: 120 },
  { field: "interest_income_514", headerName: "利息收入(514)", width: 140, type: "numericColumn" },
  { field: "fair_value_change_516", headerName: "公允变动(516)", width: 140, type: "numericColumn" },
  { field: "capital_gain_517", headerName: "资本利得(517)", width: 140, type: "numericColumn" },
  { field: "manual_adjustment", headerName: "手工调整", width: 120, type: "numericColumn" },
  { field: "total_pnl", headerName: "合计损益", width: 130, type: "numericColumn" },
];

const gridDefaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true,
};

function withNumericFormatters<T>(defs: ColDef<T>[]): ColDef<T>[] {
  return defs.map((def) =>
    def.type === "numericColumn" ? { ...def, valueFormatter: thousandsValueFormatter } : def,
  );
}

type DataTab = "fi" | "nonstd";

export default function PnlPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [dataTab, setDataTab] = useState<DataTab>("fi");

  const formalFiColDefs = useMemo(() => withNumericFormatters(formalFiColumnDefs), []);
  const nonstdColDefs = useMemo(() => withNumericFormatters(nonstdBridgeColumnDefs), []);

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

  const overviewQuery = useQuery({
    queryKey: ["pnl", "overview", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getFormalPnlOverview(selectedReportDate),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["pnl", "data", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getFormalPnlData(selectedReportDate),
    retry: false,
  });

  const overview = overviewQuery.data?.result;
  const formalRows = dataQuery.data?.result.formal_fi_rows ?? [];
  const nonstdRows = dataQuery.data?.result.nonstd_bridge_rows ?? [];

  const overviewLoading =
    datesQuery.isLoading || (Boolean(selectedReportDate) && overviewQuery.isLoading);
  const overviewError = datesQuery.isError || overviewQuery.isError;
  const overviewEmpty =
    !datesQuery.isLoading &&
    !overviewQuery.isLoading &&
    !datesQuery.isError &&
    !overviewQuery.isError &&
    (!selectedReportDate ||
      ((overview?.formal_fi_row_count ?? 0) === 0 && (overview?.nonstd_bridge_row_count ?? 0) === 0));

  const dataLoading =
    datesQuery.isLoading || (Boolean(selectedReportDate) && dataQuery.isLoading);
  const dataError = datesQuery.isError || dataQuery.isError;
  const dataEmpty =
    !datesQuery.isLoading &&
    !dataQuery.isLoading &&
    !datesQuery.isError &&
    !dataQuery.isError &&
    (!selectedReportDate || (formalRows.length === 0 && nonstdRows.length === 0));

  const dataTabExtra = (
    <div style={tabBarStyle}>
      <button
        type="button"
        style={tabButtonStyle(dataTab === "fi")}
        onClick={() => setDataTab("fi")}
      >
        FI 损益
      </button>
      <button
        type="button"
        style={tabButtonStyle(dataTab === "nonstd")}
        onClick={() => setDataTab("nonstd")}
      >
        非标桥接
      </button>
    </div>
  );

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
          损益明细
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
          正式口径 PnL 明细与汇总，数据由后端 API 提供；页面仅展示返回值，不在浏览器端做金融重算。
        </p>
      </div>

      <div style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="pnl-report-date"
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
          title="汇总概览"
          isLoading={overviewLoading}
          isError={overviewError}
          isEmpty={overviewEmpty}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), overviewQuery.refetch()]);
          }}
        >
          <div data-testid="pnl-overview-cards" style={summaryGridStyle}>
            <PlaceholderCard
              title="FI 明细行数"
              value={cellText(overview?.formal_fi_row_count)}
              detail="formal_fi 明细行数（后端计数）。"
            />
            <PlaceholderCard
              title="非标桥接行数"
              value={cellText(overview?.nonstd_bridge_row_count)}
              detail="nonstd_bridge 明细行数（后端计数）。"
            />
            <PlaceholderCard
              title="利息收入 (514)"
              value={cellText(overview?.interest_income_514)}
              detail="后端返回的汇总金额字符串。"
            />
            <PlaceholderCard
              title="公允价值变动 (516)"
              value={cellText(overview?.fair_value_change_516)}
              detail="后端返回的汇总金额字符串。"
            />
            <PlaceholderCard
              title="资本利得 (517)"
              value={cellText(overview?.capital_gain_517)}
              detail="后端返回的汇总金额字符串。"
            />
            <PlaceholderCard
              title="损益合计"
              value={cellText(overview?.total_pnl)}
              detail="后端返回的汇总损益字符串。"
            />
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="明细数据"
          extra={dataTabExtra}
          isLoading={dataLoading}
          isError={dataError}
          isEmpty={dataEmpty}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), dataQuery.refetch()]);
          }}
        >
          {dataTab === "fi" ? (
            <div
              className="ag-theme-alpine"
              data-testid="pnl-formal-fi-table"
              style={agGridShellStyle}
            >
              <AgGridReact<PnlFormalFiRow>
                rowData={formalRows}
                columnDefs={formalFiColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(p) =>
                  `${String(p.data.trace_id)}-${String(p.data.instrument_code)}-${String(p.data.report_date)}`
                }
              />
            </div>
          ) : (
            <div
              className="ag-theme-alpine"
              data-testid="pnl-nonstd-bridge-table"
              style={agGridShellStyle}
            >
              <AgGridReact<PnlNonStdBridgeRow>
                rowData={nonstdRows}
                columnDefs={nonstdColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(p) =>
                  `${String(p.data.trace_id)}-${String(p.data.bond_code)}-${String(p.data.report_date)}`
                }
              />
            </div>
          )}
        </AsyncSection>
      </div>
    </section>
  );
}
