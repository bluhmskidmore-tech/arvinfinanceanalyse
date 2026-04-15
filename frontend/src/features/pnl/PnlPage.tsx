import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { useApiClient } from "../../api/client";
import type { PnlFormalFiRow, PnlNonStdBridgeRow } from "../../api/contracts";
import { runPollingTask } from "../../app/jobs/polling";
import { FilterBar } from "../../components/FilterBar";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
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

const tabBarStyle = {
  display: "flex",
  gap: 8,
  marginBottom: 16,
  flexWrap: "wrap",
} as const;

const debugPanelStyle = {
  marginTop: 24,
  padding: 16,
  borderRadius: 16,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "#ffffff",
} as const;

const debugPreStyle = {
  margin: 0,
  padding: 16,
  overflowX: "auto",
  borderRadius: 12,
  background: shellTokens.colorBgMuted,
  color: shellTokens.colorText,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const actionButtonStyle = {
  padding: "10px 16px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
  fontWeight: 600,
  cursor: "pointer",
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

function resolveSectionState({
  isLoading,
  isError,
  isEmpty,
}: {
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
}): "loading" | "error" | "empty" | "ready" {
  if (isLoading) {
    return "loading";
  }
  if (isError) {
    return "error";
  }
  if (isEmpty) {
    return "empty";
  }
  return "ready";
}

type DataTab = "fi" | "nonstd";

export default function PnlPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [dataTab, setDataTab] = useState<DataTab>("fi");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

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

  const overviewLoading = datesQuery.isLoading || (Boolean(selectedReportDate) && overviewQuery.isLoading);
  const overviewError = datesQuery.isError || overviewQuery.isError;
  const overviewEmpty =
    !datesQuery.isLoading &&
    !overviewQuery.isLoading &&
    !datesQuery.isError &&
    !overviewQuery.isError &&
    (!selectedReportDate ||
      ((overview?.formal_fi_row_count ?? 0) === 0 && (overview?.nonstd_bridge_row_count ?? 0) === 0));

  const dataLoading = datesQuery.isLoading || (Boolean(selectedReportDate) && dataQuery.isLoading);
  const dataError = datesQuery.isError || dataQuery.isError;
  const dataEmpty =
    !datesQuery.isLoading &&
    !dataQuery.isLoading &&
    !datesQuery.isError &&
    !dataQuery.isError &&
    (!selectedReportDate || (formalRows.length === 0 && nonstdRows.length === 0));

  const overviewState = resolveSectionState({
    isLoading: overviewLoading,
    isError: overviewError,
    isEmpty: overviewEmpty,
  });
  const dataState = resolveSectionState({
    isLoading: dataLoading,
    isError: dataError,
    isEmpty: dataEmpty,
  });

  const reportDatePlaceholder = datesQuery.isLoading
    ? "正在载入报告日"
    : datesQuery.isError
      ? "报告日加载失败"
      : "暂无可选报告日";
  const reportDateSelectDisabled = datesQuery.isLoading || datesQuery.isError || reportDates.length === 0;
  const refreshDisabled = !selectedReportDate || isRefreshing;

  const dataTabExtra = (
    <div style={tabBarStyle}>
      <button type="button" style={tabButtonStyle(dataTab === "fi")} onClick={() => setDataTab("fi")}>
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

  const debugSnapshot = {
    client_mode: client.mode,
    selected_report_date: selectedReportDate || null,
    available_report_dates: reportDates,
    overview_state: overviewState,
    data_state: dataState,
    dates: {
      result_meta: datesQuery.data?.result_meta ?? null,
      error: datesQuery.error instanceof Error ? datesQuery.error.message : null,
      report_dates: reportDates,
    },
    overview: {
      result_meta: overviewQuery.data?.result_meta ?? null,
      error: overviewQuery.error instanceof Error ? overviewQuery.error.message : null,
      payload: overview ?? null,
    },
    data: {
      result_meta: dataQuery.data?.result_meta ?? null,
      error: dataQuery.error instanceof Error ? dataQuery.error.message : null,
      payload: selectedReportDate
        ? {
            report_date: selectedReportDate,
            formal_fi_row_count: formalRows.length,
            nonstd_bridge_row_count: nonstdRows.length,
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
            [
              nextPayload.status,
              nextPayload.run_id,
              nextPayload.report_date,
              nextPayload.source_version,
            ]
              .filter(Boolean)
              .join(" · "),
          );
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([datesQuery.refetch(), overviewQuery.refetch(), dataQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新 PnL 失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section data-testid="pnl-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="pnl-page-title"
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
            data-testid="pnl-page-subtitle"
            style={pageSubtitleStyle}
          >
            正式口径 PnL 明细与汇总，数据由后端 API 提供；页面仅展示返回值，不在浏览器端做金融重算。
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
            aria-label="pnl-report-date"
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
          data-testid="pnl-refresh-button"
          type="button"
          disabled={refreshDisabled}
          onClick={() => void handleRefresh()}
          style={actionButtonStyle}
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
      </FilterBar>

      {(refreshStatus || refreshError) && (
        <div
          data-testid="pnl-refresh-status"
          style={{
            marginBottom: 16,
            padding: 14,
            borderRadius: 14,
            border: "1px solid #e4ebf5",
            background: refreshError ? "#fff2f0" : "#f7f9fc",
            color: refreshError ? "#c83b3b" : "#5c6b82",
          }}
        >
          {refreshError ?? refreshStatus}
        </div>
      )}

      <div data-testid="pnl-overview-section" data-state={overviewState} style={{ marginBottom: 24 }}>
        <SectionLead
          eyebrow="Overview"
          title="正式损益汇总"
          description="先确认报告日与刷新状态，再阅读 514 / 516 / 517、手工调整和损益合计；所有数值均来自后端正式 read model。"
        />
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
            <KpiCard
              title="FI 明细行数"
              value={cellText(overview?.formal_fi_row_count)}
              detail="formal_fi 明细行数（后端计数）。"
              unit="行"
            />
            <KpiCard
              title="非标桥接行数"
              value={cellText(overview?.nonstd_bridge_row_count)}
              detail="nonstd_bridge 明细行数（后端计数）。"
              unit="行"
            />
            <KpiCard
              title="利息收入 (514)"
              value={cellText(overview?.interest_income_514)}
              detail="后端返回的汇总金额字符串。"
              tone={toneFromSignedDisplayString(cellText(overview?.interest_income_514))}
            />
            <KpiCard
              title="公允价值变动 (516)"
              value={cellText(overview?.fair_value_change_516)}
              detail="后端返回的汇总金额字符串。"
              tone={toneFromSignedDisplayString(cellText(overview?.fair_value_change_516))}
            />
            <KpiCard
              title="资本利得 (517)"
              value={cellText(overview?.capital_gain_517)}
              detail="后端返回的汇总金额字符串。"
              tone={toneFromSignedDisplayString(cellText(overview?.capital_gain_517))}
            />
            <KpiCard
              title="损益合计"
              value={cellText(overview?.total_pnl)}
              detail="后端返回的汇总损益字符串。"
              tone={toneFromSignedDisplayString(cellText(overview?.total_pnl))}
            />
          </div>
        </AsyncSection>
      </div>

      <div data-testid="pnl-data-section" data-state={dataState} style={{ marginTop: 24 }}>
        <SectionLead
          eyebrow="Details"
          title="正式明细与非标桥接"
          description="FI 明细和非标桥接共用当前报告日，保留原有 tab、AG Grid 和分页行为，不改变正式 PnL 契约。"
        />
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
            <div className="ag-theme-alpine" data-testid="pnl-formal-fi-table" style={agGridShellStyle}>
              <AgGridReact<PnlFormalFiRow>
                rowData={formalRows}
                columnDefs={formalFiColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(params) =>
                  `${String(params.data.trace_id)}-${String(params.data.instrument_code)}-${String(params.data.report_date)}`
                }
              />
            </div>
          ) : (
            <div className="ag-theme-alpine" data-testid="pnl-nonstd-bridge-table" style={agGridShellStyle}>
              <AgGridReact<PnlNonStdBridgeRow>
                rowData={nonstdRows}
                columnDefs={nonstdColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(params) =>
                  `${String(params.data.trace_id)}-${String(params.data.bond_code)}-${String(params.data.report_date)}`
                }
              />
            </div>
          )}
        </AsyncSection>
      </div>

      <details data-testid="pnl-result-meta-panel" style={debugPanelStyle}>
        <summary style={{ cursor: "pointer", fontWeight: 600, color: shellTokens.colorText }}>
          result_meta / 调试
        </summary>
        <div style={{ marginTop: 12 }}>
          <pre style={debugPreStyle}>{JSON.stringify(debugSnapshot, null, 2)}</pre>
        </div>
      </details>
    </section>
  );
}
