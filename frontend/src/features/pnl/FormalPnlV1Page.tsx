import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import "../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { useApiClient } from "../../api/client";
import type { LiabilityYieldKpi, Numeric, PnlBasis, PnlV1DetailRow } from "../../api/contracts";
import { formatNumeric } from "../../utils/format";
import { runPollingTask } from "../../app/jobs/polling";
import { FilterBar } from "../../components/FilterBar";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { SectionLead } from "../../components/page/SectionLead";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../components/KpiCard";
import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";
import { PnlRefreshStatus } from "./PnlRuntimePanels";
import { resolvePnlSectionState } from "./PnlRuntimeSupport";
import "./FormalPnlV1Page.css";

function cellText(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
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

const v1DetailColumnDefs: ColDef<PnlV1DetailRow>[] = [
  { field: "asset_code", headerName: "资产代码", width: 140, pinned: "left" },
  { field: "bond_name", headerName: "资产名称", width: 180 },
  { field: "portfolio", headerName: "组合", width: 130 },
  { field: "asset_type", headerName: "投资类型", width: 120 },
  { field: "asset_class", headerName: "资产分类", width: 140 },
  { field: "market_value", headerName: "市值", width: 130, type: "numericColumn" },
  { field: "interest_income", headerName: "514利息收入", width: 140, type: "numericColumn" },
  { field: "fair_value_change", headerName: "516公允价值", width: 140, type: "numericColumn" },
  { field: "capital_gain", headerName: "517投资收益", width: 140, type: "numericColumn" },
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

function formatWan(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return cellText(null);
  }
  const parsed = Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return (parsed / 10000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function tabButtonClassName(active: boolean) {
  return active
    ? "formal-pnl-v1-tab-button formal-pnl-v1-tab-button--active"
    : "formal-pnl-v1-tab-button";
}

export default function FormalPnlV1Page() {
  const client = useApiClient();
  const [basis, setBasis] = useState<PnlBasis>("formal");
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [dataTab, setDataTab] = useState<DataTab>("fi");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const v1DetailColDefs = useMemo(() => withNumericFormatters(v1DetailColumnDefs), []);

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

  const dataQuery = useQuery({
    queryKey: ["pnl", "v1-data", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getPnlV1Data(selectedReportDate),
    retry: false,
  });

  const overviewQuery = useQuery({
    queryKey: ["pnl", "overview", client.mode, basis, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getFormalPnlOverview(selectedReportDate, basis),
    retry: false,
  });

  const yieldQuery = useQuery({
    queryKey: ["pnl", "yield-metrics", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate) && dataTab === "yield",
    queryFn: () => client.getLiabilityYieldMetrics(selectedReportDate),
    retry: false,
  });

  const allRows = useMemo(() => dataQuery.data?.result.rows ?? [], [dataQuery.data?.result.rows]);
  const formalRows = useMemo(() => allRows.filter((row) => row.source === "FI"), [allRows]);
  const nonstdRows = useMemo(() => allRows.filter((row) => row.source === "NonStd"), [allRows]);
  const overview = overviewQuery.data?.result ?? null;

  const overviewLoading = datesQuery.isLoading || (Boolean(selectedReportDate) && overviewQuery.isLoading);
  const overviewError = datesQuery.isError || overviewQuery.isError;
  const overviewEmpty =
    !datesQuery.isLoading &&
    !overviewQuery.isLoading &&
    !datesQuery.isError &&
    !overviewQuery.isError &&
    (!selectedReportDate || overview === null);

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
    <div className="formal-pnl-v1-tab-bar">
      <button type="button" className={tabButtonClassName(dataTab === "fi")} onClick={() => setDataTab("fi")}>
        固收损益
      </button>
      <button
        type="button"
        className={tabButtonClassName(dataTab === "nonstd")}
        onClick={() => setDataTab("nonstd")}
      >
        非标桥接
      </button>
      <button type="button" className={tabButtonClassName(dataTab === "yield")} onClick={() => setDataTab("yield")}>
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
    <section data-testid="formal-pnl-v1-page">
      <div className="formal-pnl-v1-page-header">
        <div>
          <h1
            data-testid="pnl-page-title"
            className="formal-pnl-v1-title"
          >
            正式损益明细
          </h1>
          <p
            data-testid="pnl-page-subtitle"
            className="formal-pnl-v1-subtitle"
          >
            查看正式口径损益汇总与明细，包括固收明细和非标桥接行。页面只展示后端结果，不在前端重算。
          </p>
        </div>
        <div className="formal-pnl-v1-header-actions">
          <span
            data-testid="pnl-page-role-badge"
            className="formal-pnl-v1-badge formal-pnl-v1-badge--role"
          >
            正式明细
          </span>
          <span
            className={`formal-pnl-v1-badge ${
              client.mode === "real" ? "formal-pnl-v1-badge--real" : "formal-pnl-v1-badge--mock"
            }`}
          >
            {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
          </span>
          <a
            data-testid="pnl-ledger-link"
            href={ledgerPnlHref}
            className="formal-pnl-v1-link"
          >
            查看总账损益
          </a>
        </div>
      </div>

      <FilterBar className="formal-pnl-v1-filter">
        <div>
          <span className="formal-pnl-v1-filter-label">口径</span>
          <div className="formal-pnl-v1-tab-bar">
            <button
              type="button"
              className={tabButtonClassName(basis === "formal")}
              onClick={() => setBasis("formal")}
            >
              正式口径
            </button>
            <button
              type="button"
              className={tabButtonClassName(basis === "analytical")}
              onClick={() => setBasis("analytical")}
            >
              分析口径
            </button>
          </div>
        </div>
        <label>
          <span className="formal-pnl-v1-filter-label">报告日</span>
          <select
            aria-label="pnl-report-date"
            value={selectedReportDate}
            disabled={reportDateSelectDisabled}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            className="formal-pnl-v1-control"
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
          className="formal-pnl-v1-refresh-button"
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
      </FilterBar>

      <PnlRefreshStatus testId="pnl-refresh-status" status={refreshStatus} error={refreshError} />

      {basis === "analytical" ? (
        <div data-testid="pnl-basis-note" className="formal-pnl-v1-basis-note">
          当前为分析口径只读视图。刷新按钮仅适用于正式重算，损益桥接仍保持正式口径。
        </div>
      ) : null}

      <div data-testid="pnl-overview-section" data-state={overviewState} className="formal-pnl-v1-overview-section">
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
          <div data-testid="pnl-overview-cards" className="formal-pnl-v1-summary-grid">
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
              value={formatWan(overview?.interest_income_514)}
              detail="后端返回的汇总金额字符串。"
              unit="万元"
              tone={toneFromSignedDisplayString(formatWan(overview?.interest_income_514))}
            />
            <KpiCard
              title="公允价值变动 (516)"
              value={formatWan(overview?.fair_value_change_516)}
              detail="后端返回的汇总金额字符串。"
              unit="万元"
              tone={toneFromSignedDisplayString(formatWan(overview?.fair_value_change_516))}
            />
            <KpiCard
              title="资本利得 (517)"
              value={formatWan(overview?.capital_gain_517)}
              detail="后端返回的汇总金额字符串。"
              unit="万元"
              tone={toneFromSignedDisplayString(formatWan(overview?.capital_gain_517))}
            />
            <KpiCard
              title="损益合计"
              value={formatWan(overview?.total_pnl)}
              detail="后端返回的汇总损益字符串。"
              unit="万元"
              tone={toneFromSignedDisplayString(formatWan(overview?.total_pnl))}
            />
          </div>
        </AsyncSection>
      </div>

      <div data-testid="pnl-data-section" data-state={dataState} className="formal-pnl-v1-data-section">
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
            <div className="ag-theme-alpine formal-pnl-v1-grid-shell" data-testid="pnl-formal-fi-table">
              <AgGridReact<PnlV1DetailRow>
                rowData={formalRows}
                columnDefs={v1DetailColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(params) =>
                  `${String(params.data.trace_id)}-${String(params.data.asset_code)}-${String(params.data.report_date)}`
                }
              />
            </div>
          ) : dataTab === "nonstd" ? (
            <div className="ag-theme-alpine formal-pnl-v1-grid-shell" data-testid="pnl-nonstd-bridge-table">
              <AgGridReact<PnlV1DetailRow>
                rowData={nonstdRows}
                columnDefs={v1DetailColDefs}
                defaultColDef={gridDefaultColDef}
                animateRows
                pagination
                paginationPageSize={50}
                getRowId={(params) =>
                  `${String(params.data.trace_id)}-${String(params.data.asset_code)}-${String(params.data.report_date)}`
                }
              />
            </div>
          ) : (
            <div data-testid="pnl-yield-kpi-grid" className="formal-pnl-v1-summary-grid">
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
          { key: "overview", title: "Pnl overview", meta: overviewQuery.data?.result_meta },
          { key: "dates", title: "报告日列表", meta: datesQuery.data?.result_meta },
          { key: "data", title: "V1明细口径", meta: dataQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
