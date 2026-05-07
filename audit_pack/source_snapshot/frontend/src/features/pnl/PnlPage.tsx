import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import "../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { useApiClient } from "../../api/client";
import type { LiabilityYieldKpi, Numeric, PnlBasis, PnlFormalFiRow, PnlNonStdBridgeRow } from "../../api/contracts";
import { formatNumeric } from "../../utils/format";
import { runPollingTask } from "../../app/jobs/polling";
import { FilterBar } from "../../components/FilterBar";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";
import { displayTokens } from "../../theme/displayTokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";
import { PnlRefreshStatus } from "./PnlRuntimePanels";
import {
  pnlActionButtonStyle,
  resolvePnlSectionState,
} from "./PnlRuntimeSupport";

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
  color: designTokens.color.neutral[600],
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
  color: designTokens.color.neutral[500],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: designTokens.color.neutral[600],
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
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "#ffffff",
  color: designTokens.color.neutral[900],
} as const;

const basisNoteStyle = {
  marginBottom: 18,
  padding: "12px 14px",
  borderRadius: 14,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: designTokens.color.neutral[50],
  color: designTokens.color.neutral[600],
  fontSize: 13,
  lineHeight: 1.65,
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
    border: active ? `1px solid ${designTokens.color.primary[600]}` : `1px solid ${shellTokens.colorBorderSoft}`,
    background: active ? designTokens.color.primary[50] : "#ffffff",
    color: active ? designTokens.color.primary[600] : designTokens.color.neutral[900],
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

type DataTab = "fi" | "nonstd" | "yield";

function formatYieldNumeric(value: Numeric | null | undefined) {
  if (value == null) {
    return "—";
  }
  return formatNumeric(value);
}

function isYieldKpiAllNull(kpi: LiabilityYieldKpi | null | undefined) {
  if (!kpi) {
    return true;
  }
  return (
    kpi.asset_yield == null &&
    kpi.liability_cost == null &&
    kpi.market_liability_cost == null &&
    kpi.nim == null
  );
}

export default function PnlPage() {
  const client = useApiClient();
  const [basis, setBasis] = useState<PnlBasis>("formal");
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
    queryKey: ["pnl", "dates", client.mode, basis],
    queryFn: () => client.getFormalPnlDates(basis),
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
    queryKey: ["pnl", "overview", client.mode, basis, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getFormalPnlOverview(selectedReportDate, basis),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["pnl", "data", client.mode, basis, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getFormalPnlData(selectedReportDate, basis),
    retry: false,
  });

  const yieldQuery = useQuery({
    queryKey: ["pnl", "yield-metrics", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate) && dataTab === "yield",
    queryFn: () => client.getLiabilityYieldMetrics(selectedReportDate),
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

  const yieldKpi = yieldQuery.data?.kpi ?? null;
  const yieldLoading = Boolean(selectedReportDate) && dataTab === "yield" && yieldQuery.isLoading;
  const yieldError = dataTab === "yield" && yieldQuery.isError;
  const yieldEmpty =
    dataTab === "yield" &&
    !yieldQuery.isLoading &&
    !yieldQuery.isError &&
    isYieldKpiAllNull(yieldKpi);

  const detailLoading = dataTab === "yield" ? yieldLoading : dataLoading;
  const detailError = dataTab === "yield" ? yieldError : dataError;
  const detailEmpty = dataTab === "yield" ? yieldEmpty : dataEmpty;

  const overviewState = resolvePnlSectionState({
    isLoading: overviewLoading,
    isError: overviewError,
    isEmpty: overviewEmpty,
  });
  const dataState = resolvePnlSectionState({
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
  const refreshDisabled = !selectedReportDate || isRefreshing || basis !== "formal";
  const ledgerPnlHref = selectedReportDate
    ? `/ledger-pnl?report_date=${encodeURIComponent(selectedReportDate)}`
    : "/ledger-pnl";

  const dataTabExtra = (
    <div style={tabBarStyle}>
      <button type="button" style={tabButtonStyle(dataTab === "fi")} onClick={() => setDataTab("fi")}>
        固收损益
      </button>
      <button
        type="button"
        style={tabButtonStyle(dataTab === "nonstd")}
        onClick={() => setDataTab("nonstd")}
      >
        非标桥接
      </button>
      <button type="button" style={tabButtonStyle(dataTab === "yield")} onClick={() => setDataTab("yield")}>
        收益与息差
      </button>
    </div>
  );

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
      setRefreshError(error instanceof Error ? error.message : "刷新损益失败");
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
            正式损益明细
          </h1>
          <p
            data-testid="pnl-page-subtitle"
            style={pageSubtitleStyle}
          >
            查看正式口径损益汇总与明细，包括固收明细和非标桥接行。页面只展示后端结果，不在前端重算。
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
          <span
            data-testid="pnl-page-role-badge"
            style={{
              ...modeBadgeStyle,
              background: designTokens.color.neutral[50],
              color: designTokens.color.neutral[900],
              border: `1px solid ${shellTokens.colorBorderSoft}`,
            }}
          >
            正式明细
          </span>
          <span
            style={{
              ...modeBadgeStyle,
              background:
                client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
              color:
                client.mode === "real"
                  ? displayTokens.apiMode.realForeground
                  : displayTokens.apiMode.mockForeground,
            }}
          >
            {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
          </span>
          <a
            data-testid="pnl-ledger-link"
            href={ledgerPnlHref}
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
            查看总账损益
          </a>
        </div>
      </div>

      <FilterBar style={controlBarStyle}>
        <div>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>口径</span>
          <div style={tabBarStyle}>
            <button
              type="button"
              style={tabButtonStyle(basis === "formal")}
              onClick={() => setBasis("formal")}
            >
              正式口径
            </button>
            <button
              type="button"
              style={tabButtonStyle(basis === "analytical")}
              onClick={() => setBasis("analytical")}
            >
              分析口径
            </button>
          </div>
        </div>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>报告日</span>
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
          style={pnlActionButtonStyle}
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
      </FilterBar>

      <PnlRefreshStatus testId="pnl-refresh-status" status={refreshStatus} error={refreshError} />

      {basis === "analytical" ? (
        <div data-testid="pnl-basis-note" style={basisNoteStyle}>
          当前为分析口径只读视图。刷新按钮仅适用于正式重算，损益桥接仍保持正式口径。
        </div>
      ) : null}

      <div data-testid="pnl-overview-section" data-state={overviewState} style={{ marginBottom: 24 }}>
        <SectionLead
          eyebrow="总览"
          title="正式损益汇总"
          description="先确认报告日与刷新状态，再阅读 514 / 516 / 517、手工调整和损益合计；所有数值均来自后端正式读模型。"
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
              title="固收明细行数"
              value={cellText(overview?.formal_fi_row_count)}
              detail="正式固收明细行数（后端计数）。"
              unit="行"
            />
            <KpiCard
              title="非标桥接行数"
              value={cellText(overview?.nonstd_bridge_row_count)}
              detail="非标桥接明细行数（后端计数）。"
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
          eyebrow="明细"
          title={dataTab === "yield" ? "收益与息差（分析口径）" : "正式明细与非标桥接"}
          description={
            dataTab === "yield"
              ? "与收益管理同源接口 `/api/analysis/yield_metrics`（经 `getLiabilityYieldMetrics`），仅展示后端返回的指标数值；不含历史曲线/散点等未暴露端点。"
              : "固收明细和非标桥接共用当前报告日，保留原有页签、明细表和分页行为，不改变正式损益契约。"
          }
        />
        <AsyncSection
          title="明细数据"
          extra={dataTabExtra}
          isLoading={detailLoading}
          isError={detailError}
          isEmpty={detailEmpty}
          onRetry={() => {
            if (dataTab === "yield") {
              void yieldQuery.refetch();
            } else {
              void Promise.all([datesQuery.refetch(), dataQuery.refetch()]);
            }
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
          ) : dataTab === "nonstd" ? (
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
          ) : (
            <div data-testid="pnl-yield-kpi-grid" style={summaryGridStyle}>
              <KpiCard
                title="资产收益率"
                value={formatYieldNumeric(yieldKpi?.asset_yield ?? null)}
                detail="后端资产收益率显示值。"
                tone={toneFromSignedDisplayString(formatYieldNumeric(yieldKpi?.asset_yield ?? null))}
              />
              <KpiCard
                title="负债成本"
                value={formatYieldNumeric(yieldKpi?.liability_cost ?? null)}
                detail="后端负债成本显示值。"
                tone={toneFromSignedDisplayString(formatYieldNumeric(yieldKpi?.liability_cost ?? null))}
              />
              <KpiCard
                title="市场负债成本"
                value={formatYieldNumeric(yieldKpi?.market_liability_cost ?? null)}
                detail="后端市场负债成本显示值。"
                tone={toneFromSignedDisplayString(formatYieldNumeric(yieldKpi?.market_liability_cost ?? null))}
              />
              <KpiCard
                title="净息差 (NIM)"
                value={formatYieldNumeric(yieldKpi?.nim ?? null)}
                detail="后端净息差显示值。"
                tone={toneFromSignedDisplayString(formatYieldNumeric(yieldKpi?.nim ?? null))}
              />
            </div>
          )}
        </AsyncSection>
      </div>

      <FormalResultMetaPanel
        testId="pnl-result-meta-panel"
        sections={[
          { key: "dates", title: "报告日列表", meta: datesQuery.data?.result_meta },
          { key: "overview", title: "正式损益汇总", meta: overviewQuery.data?.result_meta },
          { key: "data", title: "正式明细与桥接", meta: dataQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
