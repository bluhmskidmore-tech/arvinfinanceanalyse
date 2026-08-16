import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Tooltip } from "antd";
import "../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { CellClassParams, ColDef, IHeaderParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "../../styles/agGridInstitutional.css";
import ReactECharts from "../../lib/echarts";

import { useApiClient } from "../../api/client";
import { runPollingTask } from "../../app/jobs/polling";
import type { DataSectionState } from "../../components/DataSection.types";
import { FilterBar } from "../../components/FilterBar";
import { PageDataSection } from "../../components/page/PageDataSection";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { SectionLead } from "../../components/page/SectionLead";
import type {
  Numeric,
  PnlBridgeEffectAvailability,
  PnlBridgeEffectAvailabilityReason,
  PnlBridgeQuality,
  PnlBridgeRow,
  PnlBridgeSummary,
} from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { TONE_DH_CSS_VAR, toneFromNumeric } from "../../utils/tone";
import { KpiCard } from "../../components/KpiCard";
import { pnlSurfaceQualityToTone } from "../workbench/components/kpiFormat";
import { PnlRefreshStatus } from "./PnlRuntimePanels";
import { PNL_GRID_LOCALE_TEXT } from "./PnlRuntimeSupport";
import { adaptPnlBridge } from "./adapters/pnlBridgeAdapter";
import {
  bridgeYuanOriginalTitle,
  buildBridgeWarningDisplays,
  buildCurveAvailabilityNotices,
  buildPnlBridgeFirstScreenMetaNotice,
  buildWaterfallOption,
  effectAvailabilityCellText,
  formatBridgeYuanCompact,
} from "./pnlBridgePageSupport";
import "./PnlBridgePage.css";

function kpiToneFromNumeric(n: Numeric): "default" | "positive" | "negative" {
  const tone = toneFromNumeric(n);
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  return "default";
}

function cellText(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return EM_DASH;
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
  return EM_DASH;
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
    <Tooltip
      title="仅资产端，人民币口径"
      /* 弹层挂页根容器防 portal 主题逃逸（positions / bond-dashboard 同配方）。 */
      getPopupContainer={(node) =>
        (node.closest('[data-moss-theme-scope="pnl-bridge"]') as HTMLElement) ?? document.body
      }
    >
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
    valueFormatter: (params) => (params.data?.[field] as Numeric | undefined)?.display ?? EM_DASH,
    ...extra,
  };
}

const MARKET_EFFECT_AVAILABILITY_FIELDS = {
  roll_down: ["roll_down_availability", "roll_down_availability_reason"],
  treasury_curve: ["treasury_curve_availability", "treasury_curve_availability_reason"],
  credit_spread: ["credit_spread_availability", "credit_spread_availability_reason"],
} as const satisfies Record<
  string,
  readonly [keyof PnlBridgeRow & `${string}_availability`, keyof PnlBridgeRow]
>;

type MarketEffectField = keyof typeof MARKET_EFFECT_AVAILABILITY_FIELDS;

/**
 * 市场效应列：可用时与其它金额列完全一致，不可用/不适用时显示文字而不是 0。
 *
 * `valueGetter` 一并返回 null，否则按"国债曲线"排序会把缺曲线的结构性 0 和真实
 * 的零变动混在一起——恰好是本次整改要消灭的那种混淆的另一种形态。
 */
function marketEffectCol(field: MarketEffectField, headerName: string): ColDef<PnlBridgeRow> {
  const [availabilityField, reasonField] = MARKET_EFFECT_AVAILABILITY_FIELDS[field];
  const unavailableText = (row: PnlBridgeRow | undefined) =>
    effectAvailabilityCellText(
      row?.[availabilityField] as PnlBridgeEffectAvailability | undefined,
      row?.[reasonField] as PnlBridgeEffectAvailabilityReason | null | undefined,
    );
  return {
    field,
    headerName,
    width: 170,
    type: "numericColumn",
    valueGetter: (params) =>
      unavailableText(params.data) === null
        ? (params.data?.[field] as Numeric | undefined)?.raw ?? null
        : null,
    valueFormatter: (params) =>
      unavailableText(params.data) ?? (params.data?.[field] as Numeric | undefined)?.display ?? EM_DASH,
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
  marketEffectCol("roll_down", "骑乘"),
  marketEffectCol("treasury_curve", "国债曲线"),
  marketEffectCol("credit_spread", "信用利差"),
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
    // DOM 单元格样式可解析 CSS 变量：走主题感知 tone 入口（Nocturne scope 内
    // --dh-api-* 解析为 --nct-* 色板），替换原浅色 shellTokens 字面量。
    cellStyle: (params: CellClassParams<PnlBridgeRow, PnlBridgeQuality>) => ({
      color:
        params.value === "ok"
          ? TONE_DH_CSS_VAR.positive
          : params.value === "warning"
            ? TONE_DH_CSS_VAR.warning
            : TONE_DH_CSS_VAR.negative,
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
  const warnings = useMemo(() => vm?.warnings ?? [], [vm?.warnings]);

  const chartOption = useMemo(() => (summary ? buildWaterfallOption(summary) : null), [summary]);
  const conclusion = useMemo(() => buildBridgeConclusion(summary), [summary]);
  const curveAvailabilityNotices = useMemo(() => buildCurveAvailabilityNotices(summary), [summary]);
  const warningDisplays = useMemo(() => buildBridgeWarningDisplays(warnings), [warnings]);

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

  // 去重：首屏 Alert 已给出 stale/fallback 决策级提示时，汇总区 DataSection 不再重复内部横幅
  // （stale/fallback 分支与 ok 分支同样原样渲染 children，仅少一条横幅）；明细区不受影响，
  // 其 DataSection 横幅仍是该区块唯一的状态信号。
  const summaryBodyState = useMemo<DataSectionState>(() => {
    if (firstScreenMetaNotice && (summaryState.kind === "stale" || summaryState.kind === "fallback")) {
      return { kind: "ok" };
    }
    return summaryState;
  }, [firstScreenMetaNotice, summaryState]);

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

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 承担；页根只声明 Nocturne scope
   * （tokens.css 别名块将 --dh-api-* 重映射至 --nct-*，ledger-pnl 同款）。
   */
  return (
    <section data-testid="pnl-bridge-page" data-moss-theme-scope="pnl-bridge">
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
        <PageDataSection
          title="汇总"
          state={summaryBodyState}
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

              {curveAvailabilityNotices.length > 0 ? (
                <div
                  data-testid="pnl-bridge-curve-availability"
                  className="pnl-bridge-curve-availability"
                >
                  <div className="pnl-bridge-curve-availability__title">曲线效应可用性</div>
                  <ul className="pnl-bridge-curve-availability__list">
                    {curveAvailabilityNotices.map((notice) => (
                      <li
                        key={notice.key}
                        className="pnl-bridge-curve-availability__item"
                        data-testid={`pnl-bridge-curve-availability-${notice.key}`}
                      >
                        <span className="pnl-bridge-curve-availability__label">{notice.label}</span>
                        <span>
                          {notice.statusText}：{notice.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

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
                {/* 金额 KPI 按亿/万缩写扫读（§3），后端原值经小注与 title 双通道保留。 */}
                <div className="pnl-bridge-kpi-cell" title={bridgeYuanOriginalTitle(summary.total_explained_pnl)}>
                  <KpiCard
                    title="合计解释损益"
                    value={formatBridgeYuanCompact(summary.total_explained_pnl)}
                    detail={`${summary.total_explained_pnl.display} 元`}
                    tone={kpiToneFromNumeric(summary.total_explained_pnl)}
                  />
                </div>
                <div className="pnl-bridge-kpi-cell" title={bridgeYuanOriginalTitle(summary.total_actual_pnl)}>
                  <KpiCard
                    title="合计实际损益"
                    value={formatBridgeYuanCompact(summary.total_actual_pnl)}
                    detail={`${summary.total_actual_pnl.display} 元`}
                    tone={kpiToneFromNumeric(summary.total_actual_pnl)}
                  />
                </div>
                {/* 残差是闭合质量指标而非盈利读数：按后端质量标记取语义色（超阈红/预警琥珀、
                    闭合中性），禁止机械"正数=绿"（§4，2026-07-19 正缺口禁绿同款决议逻辑）。 */}
                <div className="pnl-bridge-kpi-cell" title={bridgeYuanOriginalTitle(summary.total_residual)}>
                  <KpiCard
                    title="合计残差"
                    value={formatBridgeYuanCompact(summary.total_residual)}
                    detail="实际损益 - 可解释损益"
                    tone={pnlSurfaceQualityToTone(summary.quality_flag)}
                  />
                </div>
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

              {warningDisplays.length > 0 ? (
                <div data-testid="pnl-bridge-warnings" className="pnl-bridge-warnings">
                  <div className="pnl-bridge-warnings__title">预警</div>
                  <ul className="pnl-bridge-warnings__list">
                    {warningDisplays.map((warning) => (
                      <li
                        key={warning.key}
                        className="pnl-bridge-warnings__item"
                        title={warning.originalText ?? undefined}
                      >
                        {warning.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </PageDataSection>
      </div>

      <div data-testid="pnl-bridge-detail-section" data-state={detailState.kind}>
        <SectionLead
          eyebrow="明细"
          title="闭合明细与归因瀑布"
          description="逐行查看债券、组合、会计分类的可解释损益、实际损益和残差，用来定位没有闭合的来源。"
        />
        <PageDataSection
          title="桥接明细"
          state={detailState}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), bridgeQuery.refetch()]);
          }}
        >
          <div className="ag-theme-alpine pnl-bridge-detail-table" data-testid="pnl-bridge-detail-table">
            {/* theme="legacy"：走 ag-theme-alpine CSS 主题链（agGridInstitutional.css 的
                theme-dh-api 深色块 + 页内 --ag-* 变量）。缺省的 v33+ Theming API 会注入
                自带浅色皮肤，正是本页明暗拼接（§11.1）的根因；MossAgGrid 同款先例。 */}
            <AgGridReact<PnlBridgeRow>
              theme="legacy"
              localeText={PNL_GRID_LOCALE_TEXT}
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
        </PageDataSection>
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
