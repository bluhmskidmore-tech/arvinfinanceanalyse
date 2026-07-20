import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Tooltip } from "antd";
import "../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { CellClassParams, ColDef, IHeaderParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "../../styles/agGridInstitutional.css";
import ReactECharts, { type EChartsOption } from "../../lib/echarts";

import { useApiClient } from "../../api/client";
import { runPollingTask } from "../../app/jobs/polling";
import { DataSection } from "../../components/DataSection";
import type { DataSectionState } from "../../components/DataSection.types";
import { FilterBar } from "../../components/FilterBar";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { SectionLead } from "../../components/page/SectionLead";
import type {
  Numeric,
  PnlBridgeQuality,
  PnlBridgeRow,
  PnlBridgeSummary,
  ResultMeta,
} from "../../api/contracts";
import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";
import { toneFromNumeric } from "../../utils/tone";
import { KpiCard } from "../../components/KpiCard";
import { pnlSurfaceQualityToTone } from "../workbench/components/kpiFormat";
import { PnlRefreshStatus } from "./PnlRuntimePanels";
import { adaptPnlBridge } from "./adapters/pnlBridgeAdapter";
import "./PnlBridgePage.css";

function kpiToneFromNumeric(n: Numeric): "default" | "positive" | "negative" {
  const tone = toneFromNumeric(n);
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  return "default";
}

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

export function buildWaterfallOption(summary: PnlBridgeSummary): EChartsOption {
  const displayStrings = [
    summary.total_carry.display,
    summary.total_roll_down.display,
    summary.total_treasury_curve.display,
    summary.total_credit_spread.display,
    summary.total_fx_translation.display,
    summary.total_realized_trading.display,
    summary.total_unrealized_fv.display,
    summary.total_manual_adjustment.display,
    summary.total_explained_pnl.display,
    summary.total_actual_pnl.display,
  ];

  const stepValues = [
    summary.total_carry.raw,
    summary.total_roll_down.raw,
    summary.total_treasury_curve.raw,
    summary.total_credit_spread.raw,
    summary.total_fx_translation.raw,
    summary.total_realized_trading.raw,
    summary.total_unrealized_fv.raw,
    summary.total_manual_adjustment.raw,
  ];

  const helperRaw: Array<number | null> = [];
  const valueRaw: Array<number | null> = [];
  const barColors: string[] = [];

  let running = 0;
  for (const value of stepValues) {
    // 缺失效应不画 0 值柱：value/helper 传 null，让 ECharts 留出断点，且不推进累计值。
    if (value === null) {
      helperRaw.push(null);
      valueRaw.push(null);
      barColors.push(designTokens.color.neutral[400]);
    } else if (value >= 0) {
      helperRaw.push(running);
      valueRaw.push(value);
      barColors.push(designTokens.color.semantic.profit);
      running += value;
    } else {
      helperRaw.push(running + value);
      valueRaw.push(-value);
      barColors.push(designTokens.color.semantic.loss);
      running += value;
    }
  }

  helperRaw.push(0);
  valueRaw.push(summary.total_explained_pnl.raw);
  barColors.push(designTokens.color.primary[600]);

  helperRaw.push(0);
  valueRaw.push(summary.total_actual_pnl.raw);
  barColors.push(designTokens.color.primary[600]);

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((item: { seriesName?: string }) => item.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = BRIDGE_CATEGORIES[idx] ?? "";
        return `${label}<br/>${displayStrings[idx] ?? "—"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 44, containLabel: true },
    xAxis: {
      type: "category",
      data: [...BRIDGE_CATEGORIES],
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: designTokens.color.neutral[600] },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { type: "dashed" as const, color: designTokens.color.neutral[200] } },
      axisLabel: { fontSize: 11, color: designTokens.color.neutral[600] },
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

function qualityLabel(value: PnlBridgeQuality | null | undefined) {
  if (value === "ok") {
    return "正常";
  }
  if (value === "warning") {
    return "预警";
  }
  if (value === "error") {
    return "错误";
  }
  return "—";
}

function pickMetaEffectiveDate(state: DataSectionState, meta: ResultMeta | null): string | undefined {
  if ((state.kind === "fallback" || state.kind === "stale") && state.effective_date) {
    return state.effective_date;
  }
  return meta?.fallback_date ?? meta?.resolved_report_date ?? meta?.as_of_date ?? undefined;
}

/** Decision-level first-screen notice from envelope result_meta (adapter state). */
export function buildPnlBridgeFirstScreenMetaNotice(
  state: DataSectionState,
  meta: ResultMeta | null,
): string | null {
  if (state.kind === "fallback") {
    const parts = ["首屏读模型已回退至最近可用快照"];
    const effectiveDate = pickMetaEffectiveDate(state, meta);
    if (meta?.requested_report_date && effectiveDate && meta.requested_report_date !== effectiveDate) {
      parts.push(`请求日 ${meta.requested_report_date} 回退至 ${effectiveDate}`);
    } else if (effectiveDate) {
      parts.push(`有效日 ${effectiveDate}`);
    }
    return `${parts.join("；")}。下方 KPI 与瀑布图基于上述回退数据，请以实际数据日期为准。`;
  }

  if (state.kind === "stale") {
    const parts = ["首屏读模型数据偏旧"];
    const effectiveDate = pickMetaEffectiveDate(state, meta);
    if (effectiveDate) {
      parts.push(`有效日 ${effectiveDate}`);
    }
    return `${parts.join("；")}。下方校验状态仍可能显示为正常，因其来自行级闭合质量，不代表读模型新鲜度。`;
  }

  return null;
}

function buildBridgeConclusion(summary: PnlBridgeSummary | undefined) {
  if (!summary) {
    return {
      title: "闭合校验结果",
      body: "等待正式桥接结果，先确认报告日与上游物化状态。",
      detail: "读模型返回后会校验解释损益、实际损益和残差是否闭合。",
    };
  }

  if (summary.quality_flag === "error") {
    return {
      title: "闭合校验结果",
      body: "校验未通过：解释损益与实际损益存在明显偏离。",
      detail: `当前残差 ${summary.total_residual.display}，后端正式质量标记为错误，请结合预警与明细表继续核对。`,
    };
  }

  if (summary.quality_flag === "warning") {
    return {
      title: "闭合校验结果",
      body: "校验预警：解释损益基本贴近实际损益，但仍有残差需要跟踪。",
      detail: `当前残差 ${summary.total_residual.display}，后端正式质量标记为预警，建议结合明细表继续核对。`,
    };
  }

  return {
    title: "闭合校验结果",
    body: "校验通过：解释损益与实际损益基本一致，残差可控。",
    detail: `当前残差 ${summary.total_residual.display}，后端正式质量标记为正常。`,
  };
}

function PnlBridgeBalanceScopeHeader(props: IHeaderParams) {
  return (
    <Tooltip title="仅资产端，人民币口径">
      <span className="pnl-bridge-balance-scope-header">{props.displayName}</span>
    </Tooltip>
  );
}

function numericNumericCol(
  field: keyof PnlBridgeRow,
  headerName: string,
  width: number,
  extra?: Partial<ColDef<PnlBridgeRow>>,
): ColDef<PnlBridgeRow> {
  return {
    field,
    headerName,
    width,
    type: "numericColumn",
    valueGetter: (params) => (params.data?.[field] as Numeric | undefined)?.raw ?? null,
    valueFormatter: (params) => (params.data?.[field] as Numeric | undefined)?.display ?? "—",
    ...extra,
  };
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
  numericNumericCol("beginning_dirty_mv", "期初脏价市值", 140, {
    headerComponent: PnlBridgeBalanceScopeHeader,
  }),
  numericNumericCol("ending_dirty_mv", "期末脏价市值", 140, {
    headerComponent: PnlBridgeBalanceScopeHeader,
  }),
  numericNumericCol("carry", "持有收益", 110),
  numericNumericCol("roll_down", "骑乘", 110),
  numericNumericCol("treasury_curve", "国债曲线", 110),
  numericNumericCol("credit_spread", "信用利差", 110),
  numericNumericCol("fx_translation", "汇兑效应", 110),
  numericNumericCol("realized_trading", "已实现交易", 120),
  numericNumericCol("unrealized_fv", "未实现公允", 120),
  numericNumericCol("manual_adjustment", "手工调整", 120),
  numericNumericCol("explained_pnl", "可解释损益", 130),
  numericNumericCol("actual_pnl", "实际损益", 120),
  numericNumericCol("residual", "残差", 100),
  {
    field: "quality_flag",
    headerName: "质量",
    width: 80,
    valueFormatter: (params) => qualityLabel(params.value),
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

  const adapterOutput = useMemo(
    () => adaptPnlBridge({ envelope: bridgeQuery.data, isLoading: bridgeQuery.isLoading, isError: bridgeQuery.isError }),
    [bridgeQuery.data, bridgeQuery.isLoading, bridgeQuery.isError],
  );

  const vm = adapterOutput.vm;
  const summary = vm?.summary;
  const rows = vm?.rows ?? [];
  const warnings = vm?.warnings ?? [];

  const chartOption = useMemo(() => (summary ? buildWaterfallOption(summary) : null), [summary]);
  const conclusion = useMemo(() => buildBridgeConclusion(summary), [summary]);

  const summaryState = useMemo<DataSectionState>(() => {
    if (datesQuery.isLoading) return { kind: "loading" };
    if (datesQuery.isError) return { kind: "error" };
    if (!selectedReportDate && reportDates.length === 0) return { kind: "empty" };
    return adapterOutput.state;
  }, [adapterOutput.state, datesQuery.isError, datesQuery.isLoading, reportDates.length, selectedReportDate]);

  const detailState = useMemo<DataSectionState>(() => {
    if (summaryState.kind === "ok" || summaryState.kind === "stale" || summaryState.kind === "fallback") {
      return rows.length === 0 ? { kind: "empty" } : summaryState;
    }
    return summaryState;
  }, [rows.length, summaryState]);

  const firstScreenMetaNotice = useMemo(
    () => buildPnlBridgeFirstScreenMetaNotice(summaryState, adapterOutput.meta),
    [adapterOutput.meta, summaryState],
  );

  const reportDatePlaceholder = datesQuery.isLoading
    ? "正在载入报告日"
    : datesQuery.isError
      ? "报告日加载失败"
      : "暂无可选报告日";
  const reportDateSelectDisabled = datesQuery.isLoading || datesQuery.isError || reportDates.length === 0;
  const refreshDisabled = !selectedReportDate || isRefreshing;

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
              .join(" / "),
          );
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新损益桥接失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section data-testid="pnl-bridge-page">
      <div className="pnl-bridge-page-header">
        <div>
          <h1 data-testid="pnl-bridge-page-title" className="pnl-bridge-page-title">
            正式损益闭合校验
          </h1>
          <p data-testid="pnl-bridge-page-subtitle" className="pnl-bridge-page-subtitle">
            校验实际损益是否能被票息、骑乘、曲线、利差、汇兑和公允价值变动解释清楚，重点看残差、质量和数据状态。
          </p>
        </div>
        <div className="pnl-bridge-page-badges">
          <span data-testid="pnl-bridge-page-role-badge" className="pnl-bridge-role-badge">
            闭合校验
          </span>
          <span
            className={
              client.mode === "real"
                ? "pnl-bridge-mode-badge pnl-bridge-mode-badge--real"
                : "pnl-bridge-mode-badge pnl-bridge-mode-badge--mock"
            }
          >
            {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
          </span>
        </div>
      </div>

      <FilterBar className="pnl-bridge-filter-bar">
        <label>
          <span className="pnl-bridge-filter-label">报告日</span>
          <select
            aria-label="pnl-bridge-report-date"
            value={selectedReportDate}
            disabled={reportDateSelectDisabled}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            className="pnl-bridge-report-date-select"
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
          className="pnl-bridge-refresh-button"
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
      </FilterBar>

      <PnlRefreshStatus testId="pnl-bridge-refresh-status" status={refreshStatus} error={refreshError} />

      <div data-testid="pnl-bridge-formal-only-note" className="pnl-bridge-formal-only-note">
        本页当前只校验正式口径的损益桥接闭合；分析口径不在此页展开。
      </div>

      <div
        data-testid="pnl-bridge-summary-section"
        data-state={summaryState.kind}
        className="pnl-bridge-summary-section"
      >
        <SectionLead
          eyebrow="总览"
          title="损益闭合校验汇总"
          description="先看校验是否通过，再核对解释损益、实际损益、残差和质量标识；所有数值均来自后端正式桥接读模型。"
        />
        {firstScreenMetaNotice ? (
          <Alert
            data-testid="pnl-bridge-meta-banner"
            className="pnl-bridge-meta-banner"
            role="status"
            type="warning"
            showIcon
            message="首屏数据为回退/偏旧口径"
            description={firstScreenMetaNotice}
          />
        ) : null}
        <DataSection
          title="汇总"
          state={summaryState}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
          }}
        >
          {summary ? (
            <>
              <div data-testid="pnl-bridge-conclusion" className="pnl-bridge-conclusion-card">
                <div className="pnl-bridge-conclusion-grid">
                  <span className="pnl-bridge-conclusion-eyebrow">{conclusion.title}</span>
                  <div className="pnl-bridge-conclusion-body">{conclusion.body}</div>
                  <div className="pnl-bridge-conclusion-detail">{conclusion.detail}</div>
                </div>
              </div>

              <div data-testid="pnl-bridge-summary-cards" className="pnl-bridge-summary-cards">
                <KpiCard title="行数" value={cellText(summary.row_count)} detail="汇总行数" unit="行" />
                <KpiCard title="质量正常" value={cellText(summary.ok_count)} detail="正常行数" tone="default" />
                <KpiCard
                  title="质量预警"
                  value={cellText(summary.warning_count)}
                  detail="预警行数"
                  tone="warning"
                />
                <KpiCard title="质量错误" value={cellText(summary.error_count)} detail="错误行数" tone="error" />
                <KpiCard
                  title="合计解释损益"
                  value={summary.total_explained_pnl.display}
                  detail="合计解释损益"
                  tone={kpiToneFromNumeric(summary.total_explained_pnl)}
                />
                <KpiCard
                  title="合计实际损益"
                  value={summary.total_actual_pnl.display}
                  detail="合计实际损益"
                  tone={kpiToneFromNumeric(summary.total_actual_pnl)}
                />
                <KpiCard
                  title="合计残差"
                  value={summary.total_residual.display}
                  detail="实际损益 - 可解释损益"
                  tone={kpiToneFromNumeric(summary.total_residual)}
                />
                <KpiCard
                  title="校验状态"
                  value={qualityLabel(summary.quality_flag)}
                  detail="按残差质量取各行最差等级。"
                  tone={pnlSurfaceQualityToTone(summary.quality_flag)}
                />
              </div>

              {chartOption ? (
                <div data-testid="pnl-bridge-waterfall-card" className="pnl-bridge-waterfall-card">
                  <div className="pnl-bridge-waterfall-card__title">解释因子拆解（用于校验闭合）</div>
                  <div className="pnl-bridge-waterfall-card__body">
                    <div className="pnl-bridge-waterfall-chart">
                      <ReactECharts
                        option={chartOption}
                        className="pnl-bridge-waterfall-chart__canvas"
                        opts={{ renderer: "canvas" }}
                      />
                    </div>
                  </div>
                </div>
              ) : null}

              {warnings.length > 0 ? (
                <div data-testid="pnl-bridge-warnings" className="pnl-bridge-warnings">
                  <div className="pnl-bridge-warnings__title">预警</div>
                  <ul className="pnl-bridge-warnings__list">
                    {warnings.map((warning) => (
                      <li key={warning} className="pnl-bridge-warnings__item">
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </DataSection>
      </div>

      <div data-testid="pnl-bridge-detail-section" data-state={detailState.kind}>
        <SectionLead
          eyebrow="明细"
          title="闭合明细与归因瀑布"
          description="逐行查看债券、组合、会计分类的可解释损益、实际损益和残差，用来定位没有闭合的来源。"
        />
        <DataSection
          title="桥接明细"
          state={detailState}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
          }}
        >
          <div className="ag-theme-alpine pnl-bridge-detail-table" data-testid="pnl-bridge-detail-table">
            <AgGridReact<PnlBridgeRow>
              rowData={rows}
              columnDefs={bridgeColumnDefsBase}
              defaultColDef={bridgeGridDefaultColDef}
              animateRows
              pagination
              paginationPageSize={50}
              getRowId={(params) =>
                `${String(params.data.instrument_code)}-${String(params.data.portfolio_name)}-${String(params.data.accounting_basis)}`
              }
            />
          </div>
        </DataSection>
      </div>

      <FormalResultMetaPanel
        testId="pnl-bridge-result-meta-panel"
        sections={[
          { key: "dates", title: "报告日列表", meta: datesQuery.data?.result_meta },
          { key: "bridge", title: "正式桥接读模型", meta: bridgeQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
