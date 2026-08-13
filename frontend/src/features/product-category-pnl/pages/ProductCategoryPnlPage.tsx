import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  DecimalLike,
  ProductCategoryAttributionPayload,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../api/contracts";
import { LazyReactECharts } from "./LazyReactECharts";
import {
  loadReactECharts,
  prefetchReactEChartsWhenIdle,
} from "./lazyReactEChartsLoader";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import MonthlyOperatingAnalysisBranch from "./MonthlyOperatingAnalysisBranch";
import "./ProductCategoryPnlPage.css";
import { ProductCategoryFormalReadinessBand } from "./ProductCategoryFormalReadinessBand";
import { ProductCategoryGovernanceStrip } from "./ProductCategoryGovernanceStrip";
import {
  buildDualAxisChartOption,
  buildIncomeYearComparisonChartOption,
  buildInterestEarningAssetLiabilityScaleChartOption,
  buildInterestSpreadChartOption,
  buildInterestSpreadYearComparisonChartOption,
  buildLiabilitySideTrendChartOption,
  buildProductCategoryComparisonReadout,
  buildSingleAxisChartOption,
  countProductCategoryComparableReportMonths,
  PRODUCT_CATEGORY_DARK_CHART_THEME,
} from "./ProductCategoryComparisonCharts";
import {
  DerivedChartPanel,
  ProductCategoryComparisonChartReadout,
  ProductCategoryInterestSpreadAttributionPanel,
} from "./ProductCategoryComparisonChartPanels";
import {
  type ProductCategoryAttributionCompare,
  ProductCategoryAttributionBridge,
  ProductCategoryAttributionPanel,
  ProductCategoryLiabilityCurrencyMatrixMobileReadout,
  ProductCategoryLiabilityDetailMatrixMobileReadout,
  ProductCategoryLiabilityFallbackMobileReadout,
} from "./ProductCategoryAttributionPanels";
import { isProductCategoryAttributionDetailRow } from "./productCategoryPnlPageModel";
import {
  ProductCategoryManagementMonitoring,
  ProductCategoryOperatingActionBacktestPanel,
  ProductCategoryOperatingAnalysisPanel,
} from "./ProductCategoryOperatingPanels";
import {
  ProductCategoryFinancialAnalysisPanel,
  type ScenarioActionClosureStatus,
  type ScenarioReviewActionStatus,
  type ScenarioReviewIssueReason,
} from "./ProductCategoryScenarioPanels";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  type ProductCategoryInterestSpreadAttributionSelection,
  type ProductCategoryInterestSpreadBasis,
  type ProductCategoryCandidateMetricStatus,
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryDataHealth,
  buildProductCategoryLiabilitySideTrendSurface,
  buildProductCategoryTrendSnapshot,
  buildLedgerPnlHrefForReportDate,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryForeignDisplayValue,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  nextDefaultReportDateIfUnset,
  selectProductCategoryAttributionWaterfallSurface,
  selectProductCategoryCurrencyNetIncomeChart,
  selectProductCategoryDecisionFocusSurface,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChart,
  selectProductCategoryInterestEarningAssetLiabilityScaleChart,
  selectProductCategoryInterestEarningIncomeScaleChart,
  selectProductCategoryInterestEarningSpreadChart,
  selectProductCategoryInterestEarningSpreadYearComparisonChart,
  selectProductCategoryOperatingAnalysisSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryInterestSpreadAttributionSurface,
  selectProductCategoryInterestSpreadChart,
  selectProductCategoryInterestSpreadYearComparisonChart,
  selectProductCategoryManagementMonitoringSurface,
  selectProductCategoryRootCauseSurface,
  selectProductCategoryScenarioExplanation,
  selectProductCategoryScenarioSensitivitySurface,
  selectProductCategoryTplScaleYieldChart,
  selectProductCategoryTwoYearInterestSpreadReportPoints,
  selectProductCategoryTrendReportPoints,
} from "./productCategoryPnlPageModel";
import { EM_DASH } from "../../../utils/format";

function ProductCategoryCandidateMetricNotice(props: {
  testId: string;
  title: string;
  status: ProductCategoryCandidateMetricStatus;
}) {
  return (
    <PageStateSurface
      variant="definition-pending"
      testId={props.testId}
      title={
        <span
          title={`status=${props.status.status}; formal_use_allowed=${props.status.formalUseAllowed}; pending_confirmation=${props.status.pendingConfirmation}`}
        >
          {props.title}
        </span>
      }
      description={`${props.status.label}：${props.status.disclaimer}`}
    />
  );
}

function formatProductCategoryRefreshStatusLine(
  snapshot: { status: string; run_id?: string } | null,
): string {
  const statusPart = snapshot ? `状态：${snapshot.status}` : "状态：启动中…";
  const runPart = snapshot?.run_id ? `；run_id：${snapshot.run_id}` : "";
  return `正在刷新产品分类损益数据。${statusPart}${runPart}。刷新期间「刷新损益数据」等部分控件将暂时不可用。`;
}

function buildAdjustmentDraft(
  reportDate: string,
): ProductCategoryManualAdjustmentRequest {
  return {
    report_date: reportDate,
    operator: "DELTA",
    approval_status: "approved",
    account_code: "",
    currency: "CNX",
    account_name: "",
    beginning_balance: null,
    ending_balance: null,
    monthly_pnl: null,
    daily_avg_balance: null,
    annual_avg_balance: null,
  };
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} className="product-category-section-lead">
      <span className="product-category-section-lead__eyebrow">
        {props.eyebrow}
      </span>
      <h2 className="product-category-section-lead__title">{props.title}</h2>
      <p className="product-category-section-lead__description">
        {props.description}
      </p>
    </div>
  );
}

const PRODUCT_CATEGORY_SECTION_LINKS = [
  ["经营总览", "#product-category-overview"],
  ["差异归因", "#product-category-attribution"],
  ["产品结构", "#product-category-products"],
  ["负债结构", "#product-category-liabilities"],
  ["完整报表", "#product-category-report"],
  ["治理审计", "#product-category-governance"],
] as const;

function ProductCategorySectionNav() {
  return (
    <nav
      className="product-category-section-nav"
      aria-label="产品分类损益页面分区"
      data-testid="product-category-section-nav"
    >
      <span className="product-category-section-nav__label">分析路径</span>
      {PRODUCT_CATEGORY_SECTION_LINKS.map(([label, href], index) => (
        <a key={href} href={href}>
          <small aria-hidden="true">{String(index + 1).padStart(2, "0")}</small>
          <span>{label}</span>
        </a>
      ))}
    </nav>
  );
}

type ProductCategoryGovernanceEvidenceProps = {
  reportDate: string;
  selectedView: string;
  scenarioApplied: boolean;
  resultMeta?: ResultMeta;
};

function ProductCategoryGovernanceEvidence(
  props: ProductCategoryGovernanceEvidenceProps,
) {
  const scenarioStateLabel = props.scenarioApplied
    ? "已应用情景预览"
    : "正式基线";
  const basisLabel = props.resultMeta?.basis ?? "pending";
  const qualityLabel = props.resultMeta?.quality_flag ?? "pending";
  const vendorLabel = props.resultMeta?.vendor_status ?? "pending";
  const fallbackLabel = props.resultMeta?.fallback_mode ?? "pending";
  const generatedAtLabel = props.resultMeta?.generated_at ?? "pending";
  const traceIdLabel = props.resultMeta?.trace_id ?? "pending";
  const needsDataStateReview =
    props.resultMeta !== undefined &&
    (props.resultMeta.quality_flag !== "ok" ||
      props.resultMeta.vendor_status === "vendor_stale" ||
      props.resultMeta.vendor_status === "vendor_unavailable" ||
      props.resultMeta.fallback_mode !== "none");

  return (
    <div
      data-testid="product-category-certification-blockers"
      className="product-category-governance-evidence"
      aria-label="产品分类损益认证阻断状态"
    >
      <section
        data-testid="product-category-governance-signing-blockers"
        className="product-category-governance-evidence__layer"
      >
        <h3>签署阻断</h3>
        <ProductCategoryOwnerSignableStatus />
      </section>
      <section
        data-testid="product-category-governance-source-version"
        className="product-category-governance-evidence__layer"
      >
        <h3>来源与版本</h3>
        <div
          data-testid="product-category-formal-readiness-status"
          className="product-category-formal-readiness__status-grid"
        >
          <span>report_date={props.reportDate || "pending"}</span>
          <span>view={props.selectedView}</span>
          <span>{scenarioStateLabel}</span>
          <span>basis={basisLabel}</span>
          <span>quality={qualityLabel}</span>
          <span>vendor={vendorLabel}</span>
          <span>fallback={fallbackLabel}</span>
          <span>generated_at={generatedAtLabel}</span>
          <span>trace_id={traceIdLabel}</span>
          {needsDataStateReview ? (
            <span>数据状态待复核</span>
          ) : null}
        </div>
      </section>
      <section
        data-testid="product-category-governance-audit-evidence"
        className="product-category-governance-evidence__layer"
      >
        <h3>审计证据</h3>
        <div className="product-category-formal-readiness__certification-strip">
          <span>签署前需重新运行核算</span>
          <span>单位：亿元</span>
          <span>日期基准：report_date</span>
          <span>数据来源：正式只读模型</span>
        </div>
      </section>
    </div>
  );
}

function ProductCategoryOwnerSignableStatus() {
  return (
    <section
      data-testid="product-category-owner-signable-status"
      className="product-category-owner-signable-status"
      aria-label="产品分类损益签署状态"
    >
      <div className="product-category-owner-signable-status__heading">
        <span>签署状态</span>
        <strong>待认证</strong>
        <small>3项待完成</small>
      </div>
      <div className="product-category-owner-signable-status__fields">
        <span>可签署：否</span>
        <span>已认证：否</span>
        <span>待业主审批</span>
        <span>黄金样本待审批</span>
        <span>人工抽核未完成：已核 10 个单元</span>
      </div>
    </section>
  );
}

type FormalTableDisplayMode = "key" | "full";

type ProductCategoryFormalTableMobileReadoutProps = {
  reportDate: string;
  selectedView: string;
  selectedCategoryId: string | null;
  grandTotal?: ProductCategoryPnlRow | null;
  rows: ProductCategoryPnlRow[];
  onOpenAttributionEvidence?: (categoryId: string) => void;
};

function ProductCategoryFormalTableReadoutField(props: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="product-category-formal-table-mobile-readout__field">
      <span className="product-category-formal-table-mobile-readout__label">
        {props.label}
      </span>
      <strong className="product-category-formal-table-mobile-readout__value">
        {props.value}
      </strong>
      {props.detail ? (
        <small className="product-category-formal-table-mobile-readout__detail">
          {props.detail}
        </small>
      ) : null}
    </div>
  );
}

function ProductCategoryFormalTableMobileReadout(
  props: ProductCategoryFormalTableMobileReadoutProps,
) {
  const focusedBusinessRow =
    props.rows.find(
      (row) => !row.is_total && row.category_id === props.selectedCategoryId,
    ) ??
    props.rows.find((row) => !row.is_total) ??
    props.rows[0] ??
    null;
  const selectedViewLabel = props.selectedView === "monthly" ? "月度" : "汇总";
  const focusedBusinessSideLabel = focusedBusinessRow
    ? focusedBusinessRow.side === "asset"
      ? "资产"
      : focusedBusinessRow.side === "liability"
        ? "负债"
        : focusedBusinessRow.side
    : "详表暂无业务行";

  return (
    <section
      id="product-category-formal-mobile-focus"
      data-testid="product-category-formal-table-mobile-readout"
      className="product-category-formal-table-mobile-readout"
      aria-label="产品分类正式表移动读数"
    >
      <div className="product-category-formal-table-mobile-readout__header">
        <span className="product-category-formal-table-mobile-readout__eyebrow">
          当前核查
        </span>
        <h3 className="product-category-formal-table-mobile-readout__title">
          {focusedBusinessRow?.category_name ?? "正式报表"}
        </h3>
      </div>
      <div className="product-category-formal-table-mobile-readout__meta">
        <span>
          {props.reportDate
            ? formatProductCategoryReportMonthLabel(props.reportDate)
            : "报告月待选"}
        </span>
        <span>视图：{selectedViewLabel}</span>
        <span>{focusedBusinessSideLabel}</span>
      </div>
      <div className="product-category-formal-table-mobile-readout__fields">
        <ProductCategoryFormalTableReadoutField
          label="规模日均"
          value={
            focusedBusinessRow
              ? formatProductCategoryRowDisplayValue(
                  focusedBusinessRow,
                  focusedBusinessRow.cnx_scale,
                )
              : EM_DASH
          }
          detail="综本规模"
        />
        <ProductCategoryFormalTableReadoutField
          label="人民币净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryRowDisplayValue(
                  focusedBusinessRow,
                  focusedBusinessRow.cny_net,
                )
              : EM_DASH
          }
          detail="正式表返回值"
        />
        <ProductCategoryFormalTableReadoutField
          label="外币净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryForeignDisplayValue(
                  focusedBusinessRow,
                  focusedBusinessRow.foreign_net,
                )
              : EM_DASH
          }
          detail="外币原值"
        />
        <ProductCategoryFormalTableReadoutField
          label="营业净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryRowDisplayValue(
                  focusedBusinessRow,
                  focusedBusinessRow.business_net_income,
                )
              : EM_DASH
          }
          detail="当前产品"
        />
        <ProductCategoryFormalTableReadoutField
          label="加权收益率"
          value={
            focusedBusinessRow
              ? formatProductCategoryYieldValue(
                  focusedBusinessRow.weighted_yield,
                )
              : EM_DASH
          }
          detail="正式表返回值"
        />
        <ProductCategoryFormalTableReadoutField
          label="合计经营净收入"
          value={formatProductCategoryValue(
            props.grandTotal?.business_net_income,
          )}
          detail="总表参照"
        />
      </div>
      {focusedBusinessRow && props.onOpenAttributionEvidence ? (
        <button
          aria-label={`打开 ${focusedBusinessRow.category_name} 归因证据`}
          className="product-category-formal-table-mobile-readout__action"
          onClick={() =>
            props.onOpenAttributionEvidence?.(focusedBusinessRow.category_id)
          }
          type="button"
        >
          查看当前产品归因证据
        </button>
      ) : null}
    </section>
  );
}

function ProductCategoryFormalSelectionContext(props: {
  reportDate: string;
  selectedView: string;
  sourceLabel: string;
  row: ProductCategoryPnlRow;
  onOpenAttributionEvidence?: (categoryId: string) => void;
}) {
  return (
    <section
      id="product-category-formal-selection-context"
      data-testid="product-category-formal-selection-context"
      className="product-category-formal-selection-context"
      aria-label={`${props.row.category_name} 正式表核查上下文`}
    >
      <div className="product-category-formal-selection-context__identity">
        <span>当前核查</span>
        <h3>{props.row.category_name}</h3>
        <p>
          {formatProductCategoryReportMonthLabel(props.reportDate)} ·{" "}
          {props.selectedView === "monthly" ? "月度" : "汇总"} |{" "}
          {props.sourceLabel}
        </p>
      </div>
      <dl className="product-category-formal-selection-context__metrics">
        <div>
          <dt>规模日均</dt>
          <dd>
            {formatProductCategoryRowDisplayValue(
              props.row,
              props.row.cnx_scale,
            )}
          </dd>
        </div>
        <div>
          <dt>人民币净收入</dt>
          <dd>
            {formatProductCategoryRowDisplayValue(props.row, props.row.cny_net)}
          </dd>
        </div>
        <div>
          <dt>外币净收入</dt>
          <dd>
            {formatProductCategoryForeignDisplayValue(
              props.row,
              props.row.foreign_net,
            )}
          </dd>
        </div>
        <div>
          <dt>营业净收入</dt>
          <dd>
            {formatProductCategoryRowDisplayValue(
              props.row,
              props.row.business_net_income,
            )}
          </dd>
        </div>
        <div>
          <dt>加权收益率</dt>
          <dd>{formatProductCategoryYieldValue(props.row.weighted_yield)}</dd>
        </div>
      </dl>
      {props.onOpenAttributionEvidence ? (
        <button
          type="button"
          onClick={() =>
            props.onOpenAttributionEvidence?.(props.row.category_id)
          }
        >
          查看归因证据
        </button>
      ) : null}
    </section>
  );
}

function reportDateYearMonth(
  reportDate: string,
): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12
  ) {
    return null;
  }
  return { year, month };
}

function uniqueProductCategoryReportDates(
  points: ReadonlyArray<{ reportDate: string }>,
): string[] {
  const seen = new Set<string>();
  const reportDates: string[] = [];
  points.forEach((point) => {
    if (!point.reportDate || seen.has(point.reportDate)) {
      return;
    }
    seen.add(point.reportDate);
    reportDates.push(point.reportDate);
  });
  return reportDates;
}

/**
 * Measured against the live read model: a few medium chunks beat both per-period requests
 * (queue behind the browser's per-host connection limit) and one giant chunk (queues
 * behind the backend's bounded worker pool).
 */
const PRODUCT_CATEGORY_HISTORY_BATCH_SIZE = 10;

const PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY =
  "moss.product-category-pnl.trend-workspace-open";

/**
 * 图表折叠区位于页面约 1400px 处、与另外几条外观相同的折叠条并列，默认折叠会被读成
 * "图表不见了"。因此默认展开并记住读者自己的选择；展开成本很低，因为每张图仍要等进入视口才挂载。
 */
function readProductCategoryTrendWorkspacePreference(): boolean {
  try {
    const stored = globalThis.localStorage?.getItem(
      PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY,
    );
    return stored === "0" ? false : true;
  } catch {
    return true;
  }
}

function persistProductCategoryTrendWorkspacePreference(open: boolean): void {
  try {
    globalThis.localStorage?.setItem(
      PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY,
      open ? "1" : "0",
    );
  } catch {
    // 隐私模式或存储被禁用时忽略：偏好丢失不影响功能。
  }
}

function chunkProductCategoryReportDates(
  reportDates: string[],
  size = PRODUCT_CATEGORY_HISTORY_BATCH_SIZE,
): string[][] {
  const chunks: string[][] = [];
  for (let index = 0; index < reportDates.length; index += size) {
    chunks.push(reportDates.slice(index, index + size));
  }
  return chunks;
}

function monthAnchoredInterestSpreadSelection(
  current: ProductCategoryInterestSpreadAttributionSelection,
  reportDate: string,
): ProductCategoryInterestSpreadAttributionSelection {
  const parsed = reportDateYearMonth(reportDate);
  if (!parsed || current.month === parsed.month) {
    return current;
  }
  return { ...current, month: parsed.month };
}

function diagnosticsToneClassName(
  tone: "neutral" | "positive" | "negative",
): string {
  if (tone === "positive") {
    return "product-category-diagnostics__value--positive";
  }
  if (tone === "negative") {
    return "product-category-diagnostics__value--negative";
  }
  return "";
}

function formalValueToneClassName(
  value: DecimalLike | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "product-category-formal-table__cell--neutral";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "product-category-formal-table__cell--neutral";
  }
  if (parsed > 0) {
    return "product-category-formal-table__cell--positive";
  }
  if (parsed < 0) {
    return "product-category-formal-table__cell--negative";
  }
  return "product-category-formal-table__cell--neutral";
}

function formalForeignValueToneClassName(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): string {
  if (value === null || value === undefined) {
    return formalValueToneClassName(value);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return formalValueToneClassName(value);
  }
  return formalValueToneClassName(row.side === "liability" ? -parsed : parsed);
}

function formalCategoryIndentClassName(level: number): string {
  const clampedLevel = Math.min(Math.max(Math.trunc(level), 0), 8);
  return `product-category-formal-table__category-indent product-category-formal-table__category-indent--level-${clampedLevel}`;
}

type ProductCategoryApiLedgerRow = {
  method: "GET" | "POST";
  path: string;
  status: string;
  tone: "live" | "loading" | "error" | "contracted";
};

type ProductCategoryAdjustmentMutationKind =
  "create" | "edit" | "revoke" | "restore";

type ProductCategoryApiContractLedgerProps = {
  readRows: ProductCategoryApiLedgerRow[];
  writeRows: ProductCategoryApiLedgerRow[];
  adjustmentCount: number;
  eventCount: number;
  canExport: boolean;
  isExporting: boolean;
  exportError: string | null;
  exportedFilename: string | null;
  onCreateAdjustment: () => void;
  onExport: () => void;
};

function ProductCategoryApiContractLedger(
  props: ProductCategoryApiContractLedgerProps,
) {
  const readErrorCount = props.readRows.filter(
    (row) => row.tone === "error",
  ).length;
  const readLoadingCount = props.readRows.filter(
    (row) => row.tone === "loading",
  ).length;

  return (
    <section
      className="product-category-api-ledger"
      data-testid="product-category-api-contract-ledger"
      aria-label="产品分类损益后端端点衔接状态"
    >
      <header className="product-category-api-ledger__header">
        <div>
          <p className="product-category-api-ledger__eyebrow">
            后端端点与治理闭环
          </p>
          <h2>11 个前端衔接动作</h2>
          <p>
            本清单展示前端集成与本会话调用状态，不是服务健康检查；写操作已衔接且受权限控制，
            不代表本次会话已执行或已完成治理签署。
          </p>
        </div>
        <span
          className={`product-category-api-ledger__runtime ${
            readErrorCount > 0
              ? "is-error"
              : readLoadingCount > 0
                ? "is-loading"
                : "is-live"
          }`}
          data-testid="product-category-api-contract-runtime"
        >
          读接口已联调 {props.readRows.length}/{props.readRows.length} ·
          写接口已联调 {props.writeRows.length}/{props.writeRows.length}
        </span>
      </header>

      <div className="product-category-api-ledger__columns">
        <section data-testid="product-category-api-read-surfaces">
          <h3>只读接口</h3>
          <div className="product-category-api-ledger__rows">
            {props.readRows.map((row) => (
              <div
                className={`product-category-api-ledger__row is-${row.tone}`}
                data-endpoint-state={row.tone}
                data-testid={`product-category-api-endpoint-${row.path
                  .replace(/[^a-z0-9]+/gi, "-")
                  .replace(/^-|-$/g, "")
                  .toLowerCase()}`}
                key={`${row.method}:${row.path}`}
              >
                <span className="product-category-api-ledger__method">
                  {row.method}
                </span>
                <code>{row.path}</code>
                <strong>{row.status}</strong>
              </div>
            ))}
          </div>
        </section>
        <section data-testid="product-category-api-write-surfaces">
          <h3>写入与轮询接口</h3>
          <div className="product-category-api-ledger__rows">
            {props.writeRows.map((row) => (
              <div
                className={`product-category-api-ledger__row is-${row.tone}`}
                data-endpoint-state={row.tone}
                key={`${row.method}:${row.path}`}
              >
                <span className="product-category-api-ledger__method">
                  {row.method}
                </span>
                <code>{row.path}</code>
                <strong>{row.status}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <footer className="product-category-api-ledger__workflow">
        <div>
          <h3>手工调整与审计流</h3>
          <strong>
            {props.adjustmentCount} 项生效 · {props.eventCount} 项事件
          </strong>
          <p>
            {props.exportedFilename
              ? `已导出 ${props.exportedFilename}；`
              : "可导出 CSV；"}
            新增 → 编辑 → 撤销 → 恢复；所有动作写入事件流，刷新状态通过 run_id
            轮询。
          </p>
          {props.exportError ? (
            <p className="product-category-api-ledger__error" role="alert">
              {props.exportError}
            </p>
          ) : null}
        </div>
        <div className="product-category-api-ledger__actions">
          <button type="button" onClick={props.onCreateAdjustment}>
            新增调整
          </button>
          <button
            type="button"
            data-testid="product-category-export-adjustments"
            disabled={!props.canExport || props.isExporting}
            onClick={props.onExport}
          >
            {props.isExporting ? "导出中..." : "导出 CSV"}
          </button>
          <a href="/product-category-pnl/audit">打开审计账本</a>
        </div>
      </footer>
    </section>
  );
}

function downloadProductCategoryAdjustmentsCsv(
  filename: string,
  content: string,
) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function formatProductCategoryTrendMetric(
  value: number | null | undefined,
  unit: string,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}${unit}`;
}

export default function ProductCategoryPnlPage() {
  const client = useApiClient();
  const [selectedBranch, setSelectedBranch] = useState<
    "product_category_pnl" | "monthly_operating_analysis"
  >("product_category_pnl");
  const [formalTableDisplayMode, setFormalTableDisplayMode] =
    useState<FormalTableDisplayMode>("key");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedView, setSelectedView] = useState("monthly");
  const [scenarioRate, setScenarioRate] = useState("1.75");
  const [appliedScenarioRate, setAppliedScenarioRate] = useState("");
  const [scenarioRateTouched, setScenarioRateTouched] = useState(false);
  const [attributionCompare, setAttributionCompare] =
    useState<ProductCategoryAttributionCompare>("mom");
  const [attributionDetailsOpen, setAttributionDetailsOpen] = useState(false);
  const [attributionDetailSelection, setAttributionDetailSelection] = useState<{
    contextKey: string;
    categoryId: string;
  } | null>(null);
  const attributionDetailsRef = useRef<HTMLDetailsElement>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshPollSnapshot, setRefreshPollSnapshot] = useState<{
    status: string;
    run_id?: string;
  } | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [diagnosticsWorkspaceOpen, setDiagnosticsWorkspaceOpen] =
    useState(false);
  const [trendWorkspaceOpen, setTrendWorkspaceOpen] = useState(
    readProductCategoryTrendWorkspacePreference,
  );
  const [backtestWorkspaceOpen, setBacktestWorkspaceOpen] = useState(false);
  const [scenarioSensitivityRequested, setScenarioSensitivityRequested] =
    useState(false);
  const [
    selectedScenarioReviewCategoryId,
    setSelectedScenarioReviewCategoryId,
  ] = useState<string | null>(null);
  const [scenarioReviewActionStatuses, setScenarioReviewActionStatuses] =
    useState<Record<string, ScenarioReviewActionStatus>>({});
  const [scenarioReviewIssueReasons, setScenarioReviewIssueReasons] = useState<
    Record<string, ScenarioReviewIssueReason>
  >({});
  const [scenarioActionClosureStatuses, setScenarioActionClosureStatuses] =
    useState<Record<string, ScenarioActionClosureStatus>>({});
  const [
    scenarioActionClosureMemoCategoryId,
    setScenarioActionClosureMemoCategoryId,
  ] = useState<string | null>(null);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(
    null,
  );
  const [adjustmentMutationKind, setAdjustmentMutationKind] =
    useState<ProductCategoryAdjustmentMutationKind | null>(null);
  const isSubmittingAdjustment = adjustmentMutationKind !== null;
  const [isExportingAdjustments, setIsExportingAdjustments] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [adjustmentExportError, setAdjustmentExportError] = useState<
    string | null
  >(null);
  const [exportedAdjustmentFilename, setExportedAdjustmentFilename] = useState<
    string | null
  >(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [
    interestSpreadAttributionSelection,
    setInterestSpreadAttributionSelection,
  ] = useState<ProductCategoryInterestSpreadAttributionSelection>({
    basis: "weighted",
    month: 1,
  });
  const [adjustmentDraft, setAdjustmentDraft] =
    useState<ProductCategoryManualAdjustmentRequest>(buildAdjustmentDraft(""));

  const datesQuery = useQuery({
    queryKey: ["product-category-pnl", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    const next = nextDefaultReportDateIfUnset(
      selectedDate,
      datesQuery.data?.result.report_dates,
    );
    if (next !== null) {
      setSelectedDate(next);
      setInterestSpreadAttributionSelection((current) =>
        monthAnchoredInterestSpreadSelection(current, next),
      );
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    setAdjustmentDraft((current) => ({
      ...current,
      report_date: selectedDate,
    }));
  }, [selectedDate]);

  useEffect(() => {
    prefetchReactEChartsWhenIdle();
  }, []);

  useEffect(() => {
    if (!selectedDate || scenarioRateTouched) {
      return;
    }
    const defaultRate =
      defaultProductCategoryScenarioRateForReportDate(selectedDate);
    setScenarioRate(defaultRate);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  }, [scenarioRateTouched, selectedDate]);

  const handleReportDateChange = (nextDate: string) => {
    const defaultRate =
      defaultProductCategoryScenarioRateForReportDate(nextDate);
    setSelectedDate(nextDate);
    setInterestSpreadAttributionSelection((current) =>
      monthAnchoredInterestSpreadSelection(current, nextDate),
    );
    setScenarioRate(defaultRate);
    setScenarioRateTouched(false);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  };

  const baselineQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "baseline",
      client.mode,
      selectedDate,
      selectedView,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const scenarioQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "scenario",
      client.mode,
      selectedDate,
      selectedView,
      appliedScenarioRate,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
        scenarioRatePct: appliedScenarioRate,
      }),
    enabled: Boolean(selectedDate && appliedScenarioRate),
    retry: false,
  });

  const scenarioSensitivityQueries = useQueries({
    queries: PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => ({
      queryKey: [
        "product-category-pnl",
        "scenario-sensitivity",
        client.mode,
        selectedDate,
        selectedView,
        option.value,
      ],
      queryFn: () =>
        client.getProductCategoryPnl({
          reportDate: selectedDate,
          view: selectedView,
          scenarioRatePct: option.value,
        }),
      enabled: Boolean(
        selectedDate &&
        baselineQuery.data?.result &&
        scenarioSensitivityRequested,
      ),
      retry: false,
    })),
  });

  const adjustmentsQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "adjustments",
      client.mode,
      selectedDate,
    ],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const attributionQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "attribution",
      client.mode,
      selectedDate,
      attributionCompare,
    ],
    queryFn: () =>
      client.getProductCategoryAttribution({
        reportDate: selectedDate,
        compare: attributionCompare,
      }),
    enabled: Boolean(selectedDate && selectedView === "monthly"),
    retry: false,
  });
  const managementMomAttributionQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "attribution",
      client.mode,
      selectedDate,
      "mom",
    ],
    queryFn: () =>
      client.getProductCategoryAttribution({
        reportDate: selectedDate,
        compare: "mom",
      }),
    enabled: Boolean(selectedDate && selectedView === "monthly"),
    retry: false,
  });

  const baseline = baselineQuery.data?.result;
  const dataHealth = buildProductCategoryDataHealth({
    datesLoading: datesQuery.isLoading,
    datesError: datesQuery.isError,
    reportDates: datesQuery.data?.result.report_dates,
    selectedDate,
    baselineLoading: baselineQuery.isLoading || baselineQuery.isFetching,
    baselineError: baselineQuery.isError,
    baseline,
    meta: baselineQuery.data?.result_meta,
  });
  const canRenderBaselineDerivedAnalysis =
    Boolean(baseline) &&
    (dataHealth.state === "ready" || dataHealth.state === "degraded");
  const scenario = scenarioQuery.data?.result;
  const displayedGrandTotal = selectDisplayedProductCategoryGrandTotal(
    scenario?.grand_total,
    baseline?.grand_total,
  );
  const baselineRate = baseline?.asset_total.baseline_ftp_rate_pct ?? "1.75";
  const currentSceneRate = scenario?.scenario_rate_pct ?? baselineRate;
  const managementScenarioDistinct = Boolean(appliedScenarioRate);
  const displayedAssetTotal = scenario?.asset_total ?? baseline?.asset_total;
  const displayedLiabilityTotal =
    scenario?.liability_total ?? baseline?.liability_total;
  const currentSelectedPayload = scenario ?? baseline;
  const currentSelectedResultMeta = scenario
    ? scenarioQuery.data?.result_meta
    : baselineQuery.data?.result_meta;
  const trendDiagnosticsLoaded = Boolean(selectedDate);
  const selectedYearMonth = useMemo(
    () => reportDateYearMonth(selectedDate),
    [selectedDate],
  );
  // 经营修复监控面板常显在所有折叠区之外，但仅在月度视图、未应用 FTP 场景、
  // 且选中 6 月末报告期时才会消费 1—6 月连续历史快照（见 selectProductCategoryManagementMonitoringSurface）。
  // 该面板本身不是折叠区消费方，须显式纳入门控，否则历史数据永远不会为它触发加载。
  const managementMonitoringConsumesHistory =
    selectedView === "monthly" &&
    !managementScenarioDistinct &&
    selectedYearMonth?.month === 6 &&
    canRenderBaselineDerivedAnalysis;
  // 趋势历史快照被趋势、诊断（负债结构核查）、动作回测三个折叠区，以及经营修复监控面板共同消费：
  // 任一折叠区展开，或经营修复监控处于会消费历史数据的状态，都必须触发历史加载。
  const trendHistoryConsumerOpen =
    trendWorkspaceOpen ||
    diagnosticsWorkspaceOpen ||
    backtestWorkspaceOpen ||
    managementMonitoringConsumesHistory;
  const attributionHistoryConsumerOpen =
    trendWorkspaceOpen || backtestWorkspaceOpen;

  const rowsToRender = useMemo(
    () => selectProductCategoryDetailRows(baseline?.rows, scenario?.rows),
    [baseline?.rows, scenario?.rows],
  );
  const operatingAnalysisSurface = useMemo(
    () =>
      selectProductCategoryOperatingAnalysisSurface({
        rows: rowsToRender,
        grandTotal: displayedGrandTotal,
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, displayedGrandTotal, rowsToRender],
  );
  const scenarioSensitivityPayloads = useMemo(
    () =>
      scenarioSensitivityQueries.flatMap((query) =>
        query.data?.result ? [query.data.result] : [],
      ),
    [scenarioSensitivityQueries],
  );
  const scenarioSensitivitySurface = useMemo(
    () =>
      selectProductCategoryScenarioSensitivitySurface({
        baseline,
        scenarios: scenarioSensitivityPayloads,
      }),
    [baseline, scenarioSensitivityPayloads],
  );
  const scenarioReviewRows =
    scenarioSensitivitySurface.pressureSummary.reviewRows;
  const selectedScenarioExplanationCategoryId =
    scenarioReviewRows.find(
      (row) => row.categoryId === selectedScenarioReviewCategoryId,
    )?.categoryId ??
    scenarioReviewRows[0]?.categoryId ??
    null;
  const scenarioExplanation = useMemo(
    () =>
      selectProductCategoryScenarioExplanation({
        categoryId: selectedScenarioExplanationCategoryId,
        baseline,
        scenarios: scenarioSensitivityPayloads,
        attribution: attributionQuery.data?.result,
      }),
    [
      attributionQuery.data?.result,
      baseline,
      scenarioSensitivityPayloads,
      selectedScenarioExplanationCategoryId,
    ],
  );
  const handleScenarioReviewActionStatus = useCallback(
    (
      categoryId: string,
      actionIndex: number,
      status: ScenarioReviewActionStatus,
    ) => {
      const actionStatusKey = `${categoryId}:${actionIndex}`;
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [actionStatusKey]: status,
      }));
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          if (!(actionStatusKey in current)) {
            return current;
          }
          const next = { ...current };
          delete next[actionStatusKey];
          return next;
        });
      }
    },
    [],
  );
  const handleScenarioReviewIssueReason = useCallback(
    (
      categoryId: string,
      actionIndex: number,
      reason: ScenarioReviewIssueReason,
    ) => {
      setScenarioReviewIssueReasons((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: reason,
      }));
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: "issue",
      }));
    },
    [],
  );
  const handleBulkScenarioReviewActionStatus = useCallback(
    (
      categoryId: string,
      actionCount: number,
      status: ScenarioReviewActionStatus,
    ) => {
      setScenarioReviewActionStatuses((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          next[`${categoryId}:${index}`] = status;
        }
        return next;
      });
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          const next = { ...current };
          for (let index = 0; index < actionCount; index += 1) {
            delete next[`${categoryId}:${index}`];
          }
          return next;
        });
      }
    },
    [],
  );
  const handleResetScenarioReviewActions = useCallback(
    (categoryId: string, actionCount: number) => {
      setScenarioReviewActionStatuses((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          delete next[`${categoryId}:${index}`];
        }
        return next;
      });
      setScenarioReviewIssueReasons((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          delete next[`${categoryId}:${index}`];
        }
        return next;
      });
    },
    [],
  );
  const handleScenarioActionClosureStatus = useCallback(
    (categoryId: string, status: ScenarioActionClosureStatus) => {
      setScenarioActionClosureStatuses((current) => ({
        ...current,
        [categoryId]: status,
      }));
    },
    [],
  );
  const attributionWaterfallSurface = useMemo(
    () =>
      selectProductCategoryAttributionWaterfallSurface(
        attributionQuery.data?.result,
      ),
    [attributionQuery.data?.result],
  );
  const rootCauseSurface = useMemo(
    () =>
      selectProductCategoryRootCauseSurface({
        rows: baseline?.rows ?? [],
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, baseline?.rows],
  );
  const attributionDetailContextKey = useMemo(() => {
    const attribution = attributionQuery.data?.result;
    if (
      selectedView !== "monthly" ||
      !attribution ||
      attribution.state !== "complete"
    ) {
      return null;
    }
    return [
      selectedDate,
      selectedView,
      attributionCompare,
      attribution.current_report_date,
      attribution.prior_report_date,
      scenario?.scenario_rate_pct ?? "baseline",
    ].join(":");
  }, [
    attributionCompare,
    attributionQuery.data?.result,
    scenario?.scenario_rate_pct,
    selectedDate,
    selectedView,
  ]);
  const selectedAttributionDetailCategoryId =
    attributionDetailContextKey === null
      ? null
      : attributionDetailSelection?.contextKey === attributionDetailContextKey
        ? attributionDetailSelection.categoryId
        : (rootCauseSurface.headline?.categoryId ?? null);
  const selectedFormalRow =
    rowsToRender.find(
      (row) =>
        !row.is_total &&
        row.category_id === selectedAttributionDetailCategoryId,
    ) ?? null;
  const attributionDetailCategoryIds = useMemo(() => {
    const attribution = attributionQuery.data?.result;
    if (
      selectedView !== "monthly" ||
      !attribution ||
      attribution.state !== "complete"
    ) {
      return new Set<string>();
    }
    return new Set(
      attribution.rows
        .filter(isProductCategoryAttributionDetailRow)
        .map((row) => row.category_id),
    );
  }, [attributionQuery.data?.result, selectedView]);
  const handleAttributionDetailSelection = useCallback(
    (categoryId: string) => {
      if (!attributionDetailContextKey) {
        return;
      }
      setAttributionDetailSelection({
        contextKey: attributionDetailContextKey,
        categoryId,
      });
    },
    [attributionDetailContextKey],
  );
  const handleAttributionDetailDrilldown = useCallback(
    (categoryId: string) => {
      handleAttributionDetailSelection(categoryId);
      setAttributionDetailsOpen(true);
      const scrollToSelectedDetail = () => {
        const selectedDetail = document.getElementById(
          "product-category-attribution-selected-detail",
        );
        (selectedDetail ?? attributionDetailsRef.current)?.scrollIntoView?.({
          block: "center",
        });
      };
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(scrollToSelectedDetail);
      } else {
        scrollToSelectedDetail();
      }
    },
    [handleAttributionDetailSelection],
  );
  const handleLocateFormalRow = useCallback(
    (categoryId: string) => {
      handleAttributionDetailSelection(categoryId);
      const scrollToFormalRow = () => {
        const formalRow = document.getElementById(
          `product-category-formal-row-${categoryId}`,
        );
        const mobileFocus = document.getElementById(
          "product-category-formal-mobile-focus",
        );
        const reviewContext = document.getElementById(
          "product-category-formal-selection-context",
        );
        const scrollTarget =
          mobileFocus && mobileFocus.getClientRects().length > 0
            ? mobileFocus
            : (reviewContext ?? formalRow);
        scrollTarget?.scrollIntoView?.({ block: "center" });
        formalRow
          ?.querySelector<HTMLButtonElement>(
            "[data-product-category-formal-row-action]",
          )
          ?.focus({ preventScroll: true });
      };
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(scrollToFormalRow);
      } else {
        scrollToFormalRow();
      }
    },
    [handleAttributionDetailSelection],
  );
  const decisionFocusSurface = useMemo(
    () =>
      selectProductCategoryDecisionFocusSurface({
        rows: rowsToRender,
        grandTotal: displayedGrandTotal,
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, displayedGrandTotal, rowsToRender],
  );
  const trendReportPoints = useMemo(
    () =>
      selectProductCategoryTrendReportPoints(
        selectedDate,
        datesQuery.data?.result.report_dates,
        selectedView,
      ),
    [datesQuery.data?.result.report_dates, selectedDate, selectedView],
  );
  const currentTrendPoint = useMemo(
    () => trendReportPoints.find((point) => point.reportDate === selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryPoints = useMemo(
    () =>
      trendReportPoints.filter((point) => point.reportDate !== selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryReportDates = useMemo(
    () => uniqueProductCategoryReportDates(trendHistoryPoints),
    [trendHistoryPoints],
  );
  const trendHistoryView = trendHistoryPoints[0]?.view ?? selectedView;
  const trendHistoryBatches = useMemo(
    () => chunkProductCategoryReportDates(trendHistoryReportDates),
    [trendHistoryReportDates],
  );
  const trendHistoryQueries = useQueries({
    queries: trendHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-batch",
        client.mode,
        batchReportDates.join(","),
        trendHistoryView,
        appliedScenarioRate,
      ],
      queryFn: () =>
        client.getProductCategoryHistory({
          reportDates: batchReportDates,
          view: trendHistoryView,
          ...(appliedScenarioRate
            ? { scenarioRatePct: appliedScenarioRate }
            : {}),
        }),
      enabled: Boolean(trendHistoryConsumerOpen && trendDiagnosticsLoaded),
      retry: false,
    })),
  });
  const trendHistoryAttributionQueries = useQueries({
    queries: trendHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-attribution-batch",
        client.mode,
        batchReportDates.join(","),
        "mom",
      ],
      queryFn: () =>
        client.getProductCategoryAttributionHistory({
          reportDates: batchReportDates,
          compare: "mom",
        }),
      enabled: Boolean(
        attributionHistoryConsumerOpen &&
        trendDiagnosticsLoaded &&
        selectedView === "monthly",
      ),
      retry: false,
    })),
  });
  const interestSpreadComparisonReportPoints = useMemo(
    () =>
      selectProductCategoryTwoYearInterestSpreadReportPoints(
        selectedDate,
        datesQuery.data?.result.report_dates,
        selectedView,
      ),
    [datesQuery.data?.result.report_dates, selectedDate, selectedView],
  );
  const interestSpreadComparisonCurrentPoint = useMemo(
    () =>
      interestSpreadComparisonReportPoints.find(
        (point) => point.reportDate === selectedDate,
      ),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  const interestSpreadComparisonHistoryPoints = useMemo(
    () =>
      interestSpreadComparisonReportPoints.filter(
        (point) => point.reportDate !== selectedDate,
      ),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  // Only the months the trend batch does not already cover, so the two batches stay disjoint
  // and opening the diagnostics workspace alone never pulls the wider comparison window.
  const interestSpreadOnlyReportDates = useMemo(() => {
    const covered = new Set(trendHistoryReportDates);
    return uniqueProductCategoryReportDates(
      interestSpreadComparisonHistoryPoints,
    ).filter((reportDate) => !covered.has(reportDate));
  }, [interestSpreadComparisonHistoryPoints, trendHistoryReportDates]);
  const interestSpreadHistoryView =
    interestSpreadComparisonHistoryPoints[0]?.view ?? selectedView;
  const interestSpreadHistoryBatches = useMemo(
    () => chunkProductCategoryReportDates(interestSpreadOnlyReportDates),
    [interestSpreadOnlyReportDates],
  );
  const interestSpreadHistoryQueries = useQueries({
    queries: interestSpreadHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-batch",
        client.mode,
        batchReportDates.join(","),
        interestSpreadHistoryView,
        appliedScenarioRate,
      ],
      queryFn: () =>
        client.getProductCategoryHistory({
          reportDates: batchReportDates,
          view: interestSpreadHistoryView,
          ...(appliedScenarioRate
            ? { scenarioRatePct: appliedScenarioRate }
            : {}),
        }),
      enabled: Boolean(trendWorkspaceOpen && trendDiagnosticsLoaded),
      retry: false,
    })),
  });
  /** Merged period lookup so each consumer resolves its own points regardless of which batch carried them. */
  const historyPayloadByReportDate = useMemo(() => {
    const byReportDate = new Map<
      string,
      { payload: ProductCategoryPnlPayload; resultMeta: ResultMeta | undefined }
    >();
    [...trendHistoryQueries, ...interestSpreadHistoryQueries].forEach(
      (query) => {
        query.data?.result.items.forEach((item) => {
          if (item.status !== "ok" || !item.result) {
            return;
          }
          byReportDate.set(item.report_date, {
            payload: item.result,
            resultMeta: item.result_meta ?? undefined,
          });
        });
      },
    );
    return byReportDate;
  }, [interestSpreadHistoryQueries, trendHistoryQueries]);
  const trendHistoryLoading =
    trendHistoryQueries.some((query) => query.isLoading) ||
    interestSpreadHistoryQueries.some((query) => query.isLoading);
  const trendHistoryErrored =
    trendHistoryQueries.some((query) => query.isError) ||
    interestSpreadHistoryQueries.some((query) => query.isError);
  const trendSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload
              ? [
                  buildProductCategoryTrendSnapshot(
                    currentSelectedPayload,
                    currentTrendPoint?.label,
                    currentSelectedResultMeta,
                  ),
                ]
              : []),
            ...trendHistoryPoints.flatMap((point) => {
              const entry = historyPayloadByReportDate.get(point.reportDate);
              return entry
                ? [
                    buildProductCategoryTrendSnapshot(
                      entry.payload,
                      point.label,
                      entry.resultMeta,
                    ),
                  ]
                : [];
            }),
          ]
        : [],
    [
      currentSelectedPayload,
      currentSelectedResultMeta,
      currentTrendPoint?.label,
      historyPayloadByReportDate,
      trendDiagnosticsLoaded,
      trendHistoryPoints,
    ],
  );
  const operatingActionBacktestPayloads = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(baseline ? [baseline] : []),
            ...trendHistoryPoints.flatMap((point) => {
              const entry = historyPayloadByReportDate.get(point.reportDate);
              return entry ? [entry.payload] : [];
            }),
          ]
        : baseline
          ? [baseline]
          : [],
    [
      baseline,
      historyPayloadByReportDate,
      trendDiagnosticsLoaded,
      trendHistoryPoints,
    ],
  );
  const operatingActionBacktestAttributions = useMemo(() => {
    const byReportDate = new Map<
      string,
      ProductCategoryAttributionPayload | null
    >();
    if (attributionQuery.data?.result && attributionCompare === "mom") {
      byReportDate.set(
        attributionQuery.data.result.report_date,
        attributionQuery.data.result,
      );
    }
    trendHistoryAttributionQueries.forEach((query) => {
      query.data?.result.items.forEach((item) => {
        if (item.status === "ok" && item.result) {
          byReportDate.set(item.result.report_date, item.result);
        }
      });
    });
    return byReportDate;
  }, [
    attributionCompare,
    attributionQuery.data?.result,
    trendHistoryAttributionQueries,
  ]);
  const operatingActionBacktestSurface = useMemo(
    () =>
      selectProductCategoryOperatingActionBacktestSurface({
        payloads: operatingActionBacktestPayloads,
        attributionsByReportDate: operatingActionBacktestAttributions,
      }),
    [operatingActionBacktestAttributions, operatingActionBacktestPayloads],
  );
  const managementMonitoringSurface = useMemo(
    () =>
      selectProductCategoryManagementMonitoringSurface({
        reportDate: selectedDate,
        snapshots: trendSnapshots,
        currentAttribution: managementMomAttributionQuery.data?.result,
        scenarioDistinct: managementScenarioDistinct,
      }),
    [
      managementMomAttributionQuery.data?.result,
      managementScenarioDistinct,
      selectedDate,
      trendSnapshots,
    ],
  );
  const interestSpreadComparisonSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload && interestSpreadComparisonCurrentPoint
              ? [
                  buildProductCategoryTrendSnapshot(
                    currentSelectedPayload,
                    interestSpreadComparisonCurrentPoint.label,
                    currentSelectedResultMeta,
                  ),
                ]
              : []),
            ...interestSpreadComparisonHistoryPoints.flatMap((point) => {
              const entry = historyPayloadByReportDate.get(point.reportDate);
              return entry
                ? [
                    buildProductCategoryTrendSnapshot(
                      entry.payload,
                      point.label,
                      entry.resultMeta,
                    ),
                  ]
                : [];
            }),
          ]
        : [],
    [
      currentSelectedPayload,
      currentSelectedResultMeta,
      historyPayloadByReportDate,
      interestSpreadComparisonCurrentPoint,
      interestSpreadComparisonHistoryPoints,
      trendDiagnosticsLoaded,
    ],
  );
  const diagnosticsSurface = useMemo(
    () =>
      buildProductCategoryDiagnosticsSurface({
        rows: rowsToRender,
        assetTotal: displayedAssetTotal,
        liabilityTotal: displayedLiabilityTotal,
        grandTotal: displayedGrandTotal,
        interestSpread: currentSelectedPayload?.interest_spread ?? null,
        trendSnapshots,
      }),
    [
      currentSelectedPayload?.interest_spread,
      displayedAssetTotal,
      displayedGrandTotal,
      displayedLiabilityTotal,
      rowsToRender,
      trendSnapshots,
    ],
  );
  const hasDiagnosticsSurface =
    diagnosticsSurface.matrixRows.length > 0 ||
    diagnosticsSurface.matrixEmptyCopy !== null ||
    diagnosticsSurface.negativeWatchlistRows.length > 0 ||
    diagnosticsSurface.negativeWatchlistEmptyCopy !== null ||
    diagnosticsSurface.spreadAttribution.state === "ready" ||
    (diagnosticsSurface.spreadAttribution.state === "incomplete" &&
      diagnosticsSurface.spreadAttribution.reason.length > 0);
  const liabilitySideTrendSurface = useMemo(
    () => buildProductCategoryLiabilitySideTrendSurface(trendSnapshots),
    [trendSnapshots],
  );
  const tplScaleYieldChart = useMemo(
    () => selectProductCategoryTplScaleYieldChart(trendSnapshots),
    [trendSnapshots],
  );
  const currencyNetIncomeChart = useMemo(
    () => selectProductCategoryCurrencyNetIncomeChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningIncomeScaleChart = useMemo(
    () => selectProductCategoryInterestEarningIncomeScaleChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningAssetLiabilityScaleChart = useMemo(
    () =>
      selectProductCategoryInterestEarningAssetLiabilityScaleChart(
        trendSnapshots,
      ),
    [trendSnapshots],
  );
  const interestSpreadChart = useMemo(
    () => selectProductCategoryInterestSpreadChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningSpreadChart = useMemo(
    () => selectProductCategoryInterestEarningSpreadChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const cnyInterestSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
        "cny",
      ),
    [interestSpreadComparisonSnapshots],
  );
  const interestEarningSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestEarningSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const cnyInterestEarningSpreadYearComparisonChart = useMemo(
    () =>
      selectProductCategoryInterestEarningSpreadYearComparisonChart(
        interestSpreadComparisonSnapshots,
        "cny",
      ),
    [interestSpreadComparisonSnapshots],
  );
  const intermediateBusinessIncomeYearComparisonChart = useMemo(
    () =>
      selectProductCategoryIntermediateBusinessIncomeYearComparisonChart(
        interestSpreadComparisonSnapshots,
      ),
    [interestSpreadComparisonSnapshots],
  );
  const interestSpreadAttributionSurface = useMemo(
    () =>
      selectedYearMonth
        ? selectProductCategoryInterestSpreadAttributionSurface(
            interestSpreadComparisonSnapshots,
            interestSpreadAttributionSelection,
            selectedYearMonth.year,
          )
        : null,
    [
      interestSpreadAttributionSelection,
      interestSpreadComparisonSnapshots,
      selectedYearMonth,
    ],
  );
  const handleInterestSpreadAttributionPointClick = useCallback(
    (
      basis: ProductCategoryInterestSpreadBasis,
      monthKeys: number[] | undefined,
      params: { dataIndex?: number },
    ) => {
      if (typeof params.dataIndex !== "number") {
        return;
      }
      const month = monthKeys?.[params.dataIndex];
      if (!month) {
        return;
      }
      setInterestSpreadAttributionSelection({ basis, month });
    },
    [],
  );
  const tplScaleYieldOption = useMemo(
    () =>
      tplScaleYieldChart
        ? buildDualAxisChartOption({
            labels: tplScaleYieldChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "%",
            series: [
              {
                name: "人民币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.cnyScale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "外币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.foreignScale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
              },
              {
                name: "收益率（%）",
                type: "line",
                data: tplScaleYieldChart.weightedYield,
                yAxisIndex: 1,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
            ],
          })
        : null,
    [tplScaleYieldChart],
  );
  const currencyNetIncomeOption = useMemo(
    () =>
      currencyNetIncomeChart
        ? buildSingleAxisChartOption({
            labels: currencyNetIncomeChart.labels,
            axisName: "亿元",
            series: [
              {
                name: "人民币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.cnyNet,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "外币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.foreignNet,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
              },
            ],
          })
        : null,
    [currencyNetIncomeChart],
  );
  const interestEarningIncomeScaleOption = useMemo(
    () =>
      interestEarningIncomeScaleChart
        ? buildDualAxisChartOption({
            labels: interestEarningIncomeScaleChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "亿元",
            series: [
              {
                name: "生息资产规模（亿元）",
                type: "bar",
                data: interestEarningIncomeScaleChart.scale,
                yAxisIndex: 0,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue,
              },
              {
                name: "生息资产收入（亿元）",
                type: "line",
                data: interestEarningIncomeScaleChart.income,
                yAxisIndex: 1,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
            ],
          })
        : null,
    [interestEarningIncomeScaleChart],
  );
  const interestEarningAssetLiabilityScaleOption = useMemo(
    () =>
      interestEarningAssetLiabilityScaleChart
        ? buildInterestEarningAssetLiabilityScaleChartOption({
            labels: interestEarningAssetLiabilityScaleChart.labels,
            series: [
              {
                name: "生息资产日均额（亿元）",
                data: interestEarningAssetLiabilityScaleChart.interestEarningAssetScale,
                /* nocturne accent 半透明（原 dh-api 钢蓝 rgba，canvas 不消费 CSS 变量）。 */
                color: "rgba(145,132,217,0.72)",
                borderColor: "rgba(145,132,217,0.4)",
              },
              {
                name: "附息负债日均额（亿元）",
                data: interestEarningAssetLiabilityScaleChart.interestBearingLiabilityScale,
                /* nocturne warn 半透明（原 dh-api 金琥珀 rgba）。 */
                color: "rgba(213,178,110,0.72)",
                borderColor: "rgba(213,178,110,0.4)",
              },
            ],
          })
        : null,
    [interestEarningAssetLiabilityScaleChart],
  );
  const interestSpreadOption = useMemo(
    () =>
      interestSpreadChart
        ? buildInterestSpreadChartOption({
            labels: interestSpreadChart.labels,
            series: [
              {
                name: "生息资产收益率（%）",
                data: interestSpreadChart.assetYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
              {
                name: "负债端加权收益率（%）",
                data: interestSpreadChart.liabilityYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              },
              {
                name: "生息资产利差（%）",
                data: interestSpreadChart.spread,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.red,
              },
            ],
          })
        : null,
    [interestSpreadChart],
  );
  const interestEarningSpreadOption = useMemo(
    () =>
      interestEarningSpreadChart
        ? buildInterestSpreadChartOption({
            labels: interestEarningSpreadChart.labels,
            series: [
              {
                name: "生息资产收益率（%）",
                data: interestEarningSpreadChart.assetYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.green,
              },
              {
                name: "负债端成本率（%）",
                data: interestEarningSpreadChart.liabilityYield,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              },
              {
                name: "生息资产负债利差（%）",
                data: interestEarningSpreadChart.spread,
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.red,
              },
            ],
          })
        : null,
    [interestEarningSpreadChart],
  );
  const comparisonCurrentSeriesName = selectedYearMonth
    ? `${selectedYearMonth.year}年`
    : null;
  const interestSpreadYearComparisonOption = useMemo(
    () =>
      interestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: interestSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: interestSpreadYearComparisonChart.series.map((series) => ({
              name: series.year,
              data: series.spread,
              color:
                series.year === comparisonCurrentSeriesName
                  ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                  : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
            })),
          })
        : null,
    [comparisonCurrentSeriesName, interestSpreadYearComparisonChart],
  );
  const cnyInterestSpreadYearComparisonOption = useMemo(
    () =>
      cnyInterestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: cnyInterestSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: cnyInterestSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [cnyInterestSpreadYearComparisonChart, comparisonCurrentSeriesName],
  );
  const interestEarningSpreadYearComparisonOption = useMemo(
    () =>
      interestEarningSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: interestEarningSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: interestEarningSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [comparisonCurrentSeriesName, interestEarningSpreadYearComparisonChart],
  );
  const cnyInterestEarningSpreadYearComparisonOption = useMemo(
    () =>
      cnyInterestEarningSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: cnyInterestEarningSpreadYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: cnyInterestEarningSpreadYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.spread,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [cnyInterestEarningSpreadYearComparisonChart, comparisonCurrentSeriesName],
  );
  const intermediateBusinessIncomeYearComparisonOption = useMemo(
    () =>
      intermediateBusinessIncomeYearComparisonChart
        ? buildIncomeYearComparisonChartOption({
            labels: intermediateBusinessIncomeYearComparisonChart.labels,
            currentSeriesName: comparisonCurrentSeriesName,
            series: intermediateBusinessIncomeYearComparisonChart.series.map(
              (series) => ({
                name: series.year,
                data: series.income,
                color:
                  series.year === comparisonCurrentSeriesName
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
              }),
            ),
          })
        : null,
    [
      comparisonCurrentSeriesName,
      intermediateBusinessIncomeYearComparisonChart,
    ],
  );
  const liabilitySideTrendOption = useMemo(
    () =>
      liabilitySideTrendSurface.chart
        ? buildLiabilitySideTrendChartOption({
            labels: liabilitySideTrendSurface.chart.labels,
            averageDaily: liabilitySideTrendSurface.chart.totalAverageDaily,
            rate: liabilitySideTrendSurface.chart.totalRate,
          })
        : null,
    [liabilitySideTrendSurface.chart],
  );
  const interestEarningSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: interestEarningSpreadYearComparisonChart?.labels,
      series: interestEarningSpreadYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.spread }),
      ),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const cnyInterestEarningSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: cnyInterestEarningSpreadYearComparisonChart?.labels,
      series: cnyInterestEarningSpreadYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.spread }),
      ),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const interestSpreadComparisonReadout = buildProductCategoryComparisonReadout(
    {
      labels: interestSpreadYearComparisonChart?.labels,
      series: interestSpreadYearComparisonChart?.series.map((series) => ({
        year: series.year,
        data: series.spread,
      })),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    },
  );
  const cnyInterestSpreadComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: cnyInterestSpreadYearComparisonChart?.labels,
      series: cnyInterestSpreadYearComparisonChart?.series.map((series) => ({
        year: series.year,
        data: series.spread,
      })),
      valueUnit: "%",
      deltaUnit: "bp",
      deltaScale: 100,
    });
  const intermediateBusinessIncomeComparisonReadout =
    buildProductCategoryComparisonReadout({
      labels: intermediateBusinessIncomeYearComparisonChart?.labels,
      series: intermediateBusinessIncomeYearComparisonChart?.series.map(
        (series) => ({ year: series.year, data: series.income }),
      ),
      valueUnit: "亿元",
      deltaUnit: "亿元",
      deltaScale: 1,
    });
  // Per-period load state is still reported one comparison month at a time; each month
  // resolves against whichever batch carries it, and an unrequested batch counts as neither
  // loaded nor failed (same as the previously disabled per-period query).
  const comparisonHistoryStatus = useMemo(() => {
    const ownerByReportDate = new Map<
      string,
      { isError: boolean; isFetching: boolean; hasData: boolean }
    >();
    const indexOwners = (
      batches: string[][],
      queries: Array<{ isError: boolean; isFetching: boolean; data?: unknown }>,
    ) => {
      batches.forEach((batchReportDates, index) => {
        const query = queries[index];
        if (!query) {
          return;
        }
        batchReportDates.forEach((reportDate) => {
          ownerByReportDate.set(reportDate, {
            isError: query.isError,
            isFetching: query.isFetching,
            hasData: Boolean(query.data),
          });
        });
      });
    };
    indexOwners(trendHistoryBatches, trendHistoryQueries);
    indexOwners(interestSpreadHistoryBatches, interestSpreadHistoryQueries);

    let loaded = 0;
    let failed = 0;
    let loading = 0;
    interestSpreadComparisonHistoryPoints.forEach((point) => {
      if (historyPayloadByReportDate.has(point.reportDate)) {
        loaded += 1;
        return;
      }
      const owner = ownerByReportDate.get(point.reportDate);
      if (!owner) {
        return;
      }
      if (owner.isError) {
        failed += 1;
      } else if (owner.isFetching) {
        loading += 1;
      } else if (owner.hasData) {
        failed += 1;
      }
    });
    return {
      total: interestSpreadComparisonHistoryPoints.length,
      loaded,
      failed,
      loading,
    };
  }, [
    historyPayloadByReportDate,
    interestSpreadComparisonHistoryPoints,
    interestSpreadHistoryBatches,
    interestSpreadHistoryQueries,
    trendHistoryBatches,
    trendHistoryQueries,
  ]);
  const comparisonHistoryTotal = comparisonHistoryStatus.total;
  const comparisonHistoryLoaded = comparisonHistoryStatus.loaded;
  const comparisonHistoryFailed = comparisonHistoryStatus.failed;
  const comparisonHistoryLoading = comparisonHistoryStatus.loading;
  const comparisonPeriodTotal = comparisonHistoryTotal + (selectedDate ? 1 : 0);
  const comparisonPeriodLoaded =
    comparisonHistoryLoaded + (baselineQuery.data?.result ? 1 : 0);
  const comparisonPeriodFailed =
    comparisonHistoryFailed + (baselineQuery.isError ? 1 : 0);
  const comparisonPeriodLoading =
    comparisonHistoryLoading + (baselineQuery.isFetching ? 1 : 0);
  const comparisonLoadState: "loading" | "partial" | "complete" | "error" =
    comparisonPeriodFailed > 0
      ? comparisonPeriodLoaded > 0
        ? "partial"
        : "error"
      : comparisonPeriodLoading > 0
        ? "loading"
        : comparisonPeriodLoaded < comparisonPeriodTotal
          ? "partial"
          : "complete";
  const comparisonLoadLabel = [
    `对比期载入 ${comparisonPeriodLoaded}/${comparisonPeriodTotal}`,
    comparisonPeriodLoading > 0 ? `载入中 ${comparisonPeriodLoading}` : null,
    comparisonPeriodFailed > 0
      ? `失败 ${comparisonPeriodFailed}`
      : comparisonLoadState === "partial"
        ? "载入不全"
        : null,
  ]
    .filter(Boolean)
    .join("；");
  const comparisonComparableMonthCount = selectedYearMonth
    ? countProductCategoryComparableReportMonths(
        interestSpreadComparisonSnapshots,
        selectedYearMonth.year,
      )
    : 0;
  const comparisonPriorPeriodLabel = selectedYearMonth
    ? `${selectedYearMonth.year - 1}年全年`
    : "上年全年待选";
  const comparisonCurrentPeriodLabel = selectedYearMonth
    ? `${selectedYearMonth.year}年截至${selectedYearMonth.month}月`
    : "当前年截止月待选";
  const trendLatestIndex = Math.max(
    (interestEarningIncomeScaleChart?.labels.length ?? 1) - 1,
    0,
  );
  const spreadLatestIndex = Math.max(
    (interestSpreadChart?.labels.length ?? 1) - 1,
    0,
  );
  const liabilityLatestIndex = Math.max(
    (liabilitySideTrendSurface.chart?.labels.length ?? 1) - 1,
    0,
  );
  const trendHeaderMetrics = {
    earningScale: formatProductCategoryTrendMetric(
      interestEarningIncomeScaleChart?.scale[trendLatestIndex],
      " 亿",
    ),
    liabilityAverage: formatProductCategoryTrendMetric(
      liabilitySideTrendSurface.chart?.totalAverageDaily[liabilityLatestIndex],
      " 亿",
    ),
    netSpread: formatProductCategoryTrendMetric(
      interestSpreadChart?.spread[spreadLatestIndex],
      "%",
    ),
  };
  const liabilityTrendReadout =
    liabilitySideTrendSurface.detailRows.find(
      (row) => row.categoryId === "liability_total",
    ) ??
    liabilitySideTrendSurface.detailRows[0] ??
    null;
  const adjustmentCount =
    adjustmentsQuery.data?.adjustment_count ??
    adjustmentsQuery.data?.adjustments.length ??
    0;
  const adjustmentEventCount =
    adjustmentsQuery.data?.event_total ??
    adjustmentsQuery.data?.events.length ??
    0;
  const readEndpointRows: ProductCategoryApiLedgerRow[] = [
    {
      method: "GET",
      path: "/dates",
      status: datesQuery.isError
        ? "ERROR"
        : datesQuery.isFetching
          ? datesQuery.data
            ? "REFRESHING"
            : "LOADING"
          : `${datesQuery.data?.result.report_dates.length ?? 0} DATES`,
      tone: datesQuery.isError
        ? "error"
        : datesQuery.isFetching
          ? "loading"
          : "live",
    },
    {
      method: "GET",
      path: "/?report_date&view",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : baselineQuery.isError
          ? "ERROR"
          : baselineQuery.isFetching
            ? baselineQuery.data
              ? "REFRESHING"
              : "LOADING"
            : baselineQuery.data
              ? `${baselineQuery.data.result.rows.length} ROWS`
              : "INTEGRATED · IDLE",
      tone: !selectedDate
        ? "contracted"
        : baselineQuery.isError
          ? "error"
          : baselineQuery.isFetching
            ? "loading"
            : baselineQuery.data
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/attribution?compare=mom|yoy",
      status:
        selectedView !== "monthly"
          ? "MONTHLY · IDLE"
          : !selectedDate
            ? "WAITING · REPORT DATE"
            : attributionQuery.isError
              ? "ERROR"
              : attributionQuery.isFetching
                ? attributionQuery.data
                  ? "REFRESHING"
                  : "LOADING"
                : (attributionQuery.data?.result.state?.toUpperCase() ??
                  "INTEGRATED · IDLE"),
      tone:
        selectedView !== "monthly" || !selectedDate
          ? "contracted"
          : attributionQuery.isError
            ? "error"
            : attributionQuery.isFetching
              ? "loading"
              : attributionQuery.data
                ? "live"
                : "contracted",
    },
    {
      method: "GET",
      path: "/manual-adjustments",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : adjustmentsQuery.isError
          ? "ERROR"
          : adjustmentsQuery.isFetching
            ? adjustmentsQuery.data
              ? "REFRESHING"
              : "LOADING"
            : adjustmentsQuery.data
              ? `${adjustmentCount} ACTIVE`
              : "INTEGRATED · IDLE",
      tone: !selectedDate
        ? "contracted"
        : adjustmentsQuery.isError
          ? "error"
          : adjustmentsQuery.isFetching
            ? "loading"
            : adjustmentsQuery.data
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/manual-adjustments/export",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : adjustmentExportError
          ? "ERROR"
          : isExportingAdjustments
            ? "EXPORTING"
            : exportedAdjustmentFilename
              ? "CSV EXPORTED"
              : "READY · ON DEMAND",
      tone: !selectedDate
        ? "contracted"
        : adjustmentExportError
          ? "error"
          : isExportingAdjustments
            ? "loading"
            : exportedAdjustmentFilename
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/refresh-status?run_id",
      status: refreshError
        ? "ERROR"
        : isRefreshing
          ? (refreshPollSnapshot?.status?.toUpperCase() ?? "POLLING")
          : lastRefreshRunId
            ? "RUN COMPLETE"
            : "READY · ON DEMAND",
      tone: refreshError
        ? "error"
        : isRefreshing
          ? "loading"
          : lastRefreshRunId
            ? "live"
            : "contracted",
    },
  ];
  const writeEndpointRows: ProductCategoryApiLedgerRow[] = [
    {
      method: "POST",
      path: "/refresh",
      status: isRefreshing ? "RUNNING" : "AUTH · START RUN",
      tone: isRefreshing ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/manual-adjustments",
      status:
        adjustmentMutationKind === "create" ? "CREATING" : "AUTH · CREATE",
      tone: adjustmentMutationKind === "create" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/edit",
      status:
        adjustmentMutationKind === "edit"
          ? "EDITING"
          : editingAdjustmentId
            ? "READY · EDIT MODE"
            : "AUTH · EDIT",
      tone: adjustmentMutationKind === "edit" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/revoke",
      status:
        adjustmentMutationKind === "revoke" ? "REVOKING" : "AUTH · REVOKE",
      tone: adjustmentMutationKind === "revoke" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/restore",
      status:
        adjustmentMutationKind === "restore" ? "RESTORING" : "AUTH · RESTORE",
      tone: adjustmentMutationKind === "restore" ? "loading" : "contracted",
    },
  ];

  async function runRefreshWorkflow() {
    const payload = await runPollingTask({
      start: () => client.refreshProductCategoryPnl(),
      getStatus: (runId) => client.getProductCategoryRefreshStatus(runId),
      onUpdate: (pollPayload) => {
        setRefreshPollSnapshot({
          status: pollPayload.status,
          run_id: pollPayload.run_id,
        });
      },
    });
    setLastRefreshRunId(payload.run_id);
    if (payload.status !== "completed") {
      throw new Error(payload.detail ?? `刷新任务未完成：${payload.status}`);
    }
    await Promise.all([
      datesQuery.refetch(),
      baselineQuery.refetch(),
      adjustmentsQuery.refetch(),
      ...(selectedView === "monthly"
        ? [attributionQuery.refetch(), managementMomAttributionQuery.refetch()]
        : []),
      ...(trendHistoryConsumerOpen
        ? trendHistoryQueries.map((query) => query.refetch())
        : []),
      ...(attributionHistoryConsumerOpen && selectedView === "monthly"
        ? trendHistoryAttributionQueries.map((query) => query.refetch())
        : []),
      ...(trendWorkspaceOpen
        ? interestSpreadHistoryQueries.map((query) => query.refetch())
        : []),
      ...(scenarioSensitivityRequested
        ? scenarioSensitivityQueries.map((query) => query.refetch())
        : []),
      ...(appliedScenarioRate ? [scenarioQuery.refetch()] : []),
    ]);
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    setRefreshError(null);
    setRefreshPollSnapshot(null);
    try {
      await runRefreshWorkflow();
    } catch (error) {
      setRefreshError(
        error instanceof Error ? error.message : "刷新损益数据失败",
      );
    } finally {
      setIsRefreshing(false);
      setRefreshPollSnapshot(null);
    }
  }

  function updateAdjustmentField<
    K extends keyof ProductCategoryManualAdjustmentRequest,
  >(key: K, value: ProductCategoryManualAdjustmentRequest[K]) {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleManualAdjustmentSubmit() {
    setAdjustmentError(null);
    if (!adjustmentDraft.report_date) {
      setAdjustmentError("请选择报表月份。");
      return;
    }
    if (!adjustmentDraft.account_code.trim()) {
      setAdjustmentError("请输入科目代码。");
      return;
    }
    if (
      !adjustmentDraft.beginning_balance &&
      !adjustmentDraft.ending_balance &&
      !adjustmentDraft.monthly_pnl &&
      !adjustmentDraft.daily_avg_balance &&
      !adjustmentDraft.annual_avg_balance
    ) {
      setAdjustmentError("至少填写一个调整数值。");
      return;
    }

    setAdjustmentMutationKind(editingAdjustmentId ? "edit" : "create");
    try {
      const payload = editingAdjustmentId
        ? await client.updateProductCategoryManualAdjustment(
            editingAdjustmentId,
            adjustmentDraft,
          )
        : await client.createProductCategoryManualAdjustment(adjustmentDraft);
      setLastAdjustmentId(payload.adjustment_id);
      await runRefreshWorkflow();
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      setAdjustmentError(
        error instanceof Error ? error.message : "手工录入失败",
      );
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentRevoke(adjustmentId: string) {
    if (
      !window.confirm(
        `Confirm revoke product-category adjustment ${adjustmentId}?`,
      )
    ) {
      return;
    }
    setAdjustmentError(null);
    setAdjustmentMutationKind("revoke");
    try {
      await client.revokeProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(
        error instanceof Error ? error.message : "撤销手工录入失败",
      );
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentRestore(adjustmentId: string) {
    setAdjustmentError(null);
    setAdjustmentMutationKind("restore");
    try {
      await client.restoreProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(
        error instanceof Error ? error.message : "恢复手工录入失败",
      );
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentsExport() {
    setAdjustmentExportError(null);
    if (!selectedDate) {
      setAdjustmentExportError("请选择报表月份后再导出。");
      return;
    }
    setIsExportingAdjustments(true);
    try {
      const payload =
        await client.exportProductCategoryManualAdjustmentsCsv(selectedDate);
      downloadProductCategoryAdjustmentsCsv(payload.filename, payload.content);
      setExportedAdjustmentFilename(payload.filename);
    } catch (error) {
      setAdjustmentExportError(
        error instanceof Error ? error.message : "导出手工调整失败",
      );
    } finally {
      setIsExportingAdjustments(false);
    }
  }

  function handleManualAdjustmentEdit(adjustment: {
    adjustment_id: string;
    report_date: string;
    operator: "ADD" | "DELTA" | "OVERRIDE";
    approval_status: "approved" | "pending" | "rejected";
    account_code: string;
    currency: "CNX" | "CNY";
    account_name?: string;
    beginning_balance?: string | null;
    ending_balance?: string | null;
    monthly_pnl?: string | null;
    daily_avg_balance?: string | null;
    annual_avg_balance?: string | null;
  }) {
    setEditingAdjustmentId(adjustment.adjustment_id);
    setAdjustmentDraft({
      report_date: adjustment.report_date,
      operator: adjustment.operator,
      approval_status: adjustment.approval_status,
      account_code: adjustment.account_code,
      currency: adjustment.currency,
      account_name: adjustment.account_name ?? "",
      beginning_balance: adjustment.beginning_balance ?? null,
      ending_balance: adjustment.ending_balance ?? null,
      monthly_pnl: adjustment.monthly_pnl ?? null,
      daily_avg_balance: adjustment.daily_avg_balance ?? null,
      annual_avg_balance: adjustment.annual_avg_balance ?? null,
    });
    setAdjustmentError(null);
    setShowManualForm(true);
  }

  const governanceNotices = collectProductCategoryGovernanceNotices(
    baselineQuery.data?.result_meta,
  );
  const formalScenarioDistinct =
    baselineQuery.data?.result_meta && scenarioQuery.data?.result_meta
      ? formatProductCategoryDualMetaDistinctLine(
          baselineQuery.data.result_meta,
          scenarioQuery.data.result_meta,
        )
      : null;

  const reportExtra = canRenderBaselineDerivedAnalysis ? (
    <div
      data-testid="product-category-summary"
      className="product-category-summary"
    >
      <span>当前场景：{currentSceneRate}%</span>
      <span>基准场景：{baselineRate}%</span>
      <span className="product-category-summary__total">
        FTP后经营净收入：
        {formatProductCategoryValue(displayedGrandTotal?.business_net_income)}
      </span>
    </div>
  ) : null;
  const ledgerPnlHref = buildLedgerPnlHrefForReportDate(selectedDate);

  // 深色 owner 由外层 ThemedRouteBoundary 承担；两个分支页根都只声明
  // Nocturne scope（tokens.css 别名块将 --dh-api-* 重映射至 --nct-*，
  // 页内既有 --ib- / --moss-color- 重映射块随 scope 自动翻转，ledger-pnl 同款）。
  if (selectedBranch === "monthly_operating_analysis") {
    return (
      <section data-testid="product-category-page" data-moss-theme-scope="product-category-pnl">
        <FilterBar className="product-category-branch-switcher">
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="false"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="true"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <MonthlyOperatingAnalysisBranch />
      </section>
    );
  }

  return (
    <section
      id="product-category-overview"
      data-testid="product-category-page"
      data-moss-theme-scope="product-category-pnl"
      className="product-category-page-shell theme-dh-api"
    >
      <header
        data-testid="product-category-report-masthead"
        className="product-category-report-masthead"
      >
        <FilterBar className="product-category-branch-switcher">
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="true"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="false"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <PageDecisionHero
          testId="product-category-contract-hero"
          className="product-category-contract-hero"
          titleTestId="product-category-page-title"
          questionTestId="product-category-page-subtitle"
          eyebrow=""
          title="产品分类损益"
          businessQuestion={`报告月 ${
            selectedDate
              ? formatProductCategoryReportMonthLabel(selectedDate)
              : "待选"
          }`}
          reportDateSlot={
            <span data-testid="product-category-report-date-slot">
              {selectedDate || "报告日待选"}
              {` · ${
                baselineQuery.data?.result_meta?.basis === "formal"
                  ? "正式口径"
                  : "口径待确认"
              }`}
              {` | ${selectedView === "monthly" ? "月度视图" : "汇总视图"}`}
            </span>
          }
          actions={
            <div className="product-category-contract-hero__actions">
              <span
                data-testid="product-category-role-badge"
                className={`product-category-contract-hero__chip product-category-contract-hero__chip--${
                  client.mode === "real" ? "real" : "mock"
                }`}
              >
                {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
              </span>
              <a
                data-testid="product-category-audit-link"
                href="/product-category-pnl/audit"
              >
                查看调整审计
              </a>
              <a
                data-testid="product-category-ledger-link"
                href={ledgerPnlHref}
              >
                总账损益
              </a>
              <button
                type="button"
                data-testid="product-category-manual-button"
                onClick={() => {
                  setShowManualForm((current) => !current);
                  setEditingAdjustmentId(null);
                  setAdjustmentError(null);
                  if (showManualForm) {
                    setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
                  }
                }}
                className="product-category-contract-hero__button"
              >
                + 手工录入
              </button>
              <button
                type="button"
                data-testid="product-category-refresh-button"
                onClick={() => void handleRefresh()}
                disabled={isRefreshing}
                className="product-category-contract-hero__button"
              >
                {isRefreshing ? "刷新中..." : "刷新损益数据"}
              </button>
            </div>
          }
        >
          <div className="product-category-contract-hero__status-stack">
            {isRefreshing ? (
              <p
                data-testid="product-category-refresh-status"
                className="product-category-contract-hero__status-line"
              >
                {formatProductCategoryRefreshStatusLine(refreshPollSnapshot)}
              </p>
            ) : null}
            {lastRefreshRunId ? (
              <p className="product-category-contract-hero__status-note">
                最近刷新任务：{lastRefreshRunId}
              </p>
            ) : null}
            {lastAdjustmentId ? (
              <p className="product-category-contract-hero__status-note">
                最近录入调整：{lastAdjustmentId}
              </p>
            ) : null}
            {refreshError ? (
              <p className="product-category-contract-hero__status-error">
                {refreshError}
              </p>
            ) : null}
          </div>
        </PageDecisionHero>
      </header>

      {canRenderBaselineDerivedAnalysis ? (
        <ProductCategoryFormalReadinessBand
          reportDate={selectedDate}
          selectedView={selectedView}
          scenarioApplied={Boolean(scenario)}
          assetTotal={displayedAssetTotal}
          liabilityTotal={displayedLiabilityTotal}
          grandTotal={displayedGrandTotal}
          attribution={attributionQuery.data?.result}
        />
      ) : null}

      <section
        data-testid="product-category-operating-command-rail"
        className="product-category-operating-command-rail"
        aria-label="报告控制与数据状态"
      >
        <section
          data-testid="product-category-unified-controls"
          className="product-category-command-surface"
          aria-label="报告口径与场景"
        >
          <div className="product-category-scenario-controls">
            <label className="product-category-scenario-controls__field">
              选择报告月份
              <select
                aria-label="选择报告月份"
                value={selectedDate}
                onChange={(event) => handleReportDateChange(event.target.value)}
                className="product-category-scenario-controls__select"
              >
                {(datesQuery.data?.result.report_dates ?? []).map(
                  (reportDate) => (
                    <option key={reportDate} value={reportDate}>
                      {formatProductCategoryReportMonthLabel(reportDate)}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label className="product-category-scenario-controls__field">
              视图模式
              <div
                role="group"
                aria-label="视图模式"
                className="product-category-scenario-controls__view-group"
              >
                <button
                  type="button"
                  onClick={() => setSelectedView("monthly")}
                  className={
                    selectedView === "monthly"
                      ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                      : "product-category-scenario-controls__view-button"
                  }
                >
                  月度视图
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedView("ytd")}
                  className={
                    selectedView === "ytd"
                      ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                      : "product-category-scenario-controls__view-button"
                  }
                >
                  汇总视图
                </button>
              </div>
            </label>

            <label className="product-category-scenario-controls__field">
              FTP 场景
              <select
                aria-label="FTP 场景"
                value={scenarioRate}
                onChange={(event) => {
                  setScenarioRateTouched(true);
                  setScenarioRate(event.target.value);
                }}
                className="product-category-scenario-controls__select"
              >
                {PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="product-category-scenario-controls__actions">
            <button
              type="button"
              data-testid="product-category-apply-scenario-button"
              onClick={() => setAppliedScenarioRate(scenarioRate.trim())}
              className="product-category-scenario-controls__apply"
            >
              应用场景
            </button>
          </div>

          {scenarioQuery.isFetching ? (
            <div
              data-testid="product-category-scenario-loading"
              className="product-category-scenario-controls__loading"
              role="status"
            >
              情景计算中，当前展示正式基线。
            </div>
          ) : null}

          {scenarioQuery.isError ? (
            <div
              data-testid="product-category-scenario-error"
              className="product-category-scenario-controls__error"
              role="alert"
            >
              <span>情景计算失败，当前展示为基线口径。</span>
              <button
                type="button"
                onClick={() => void scenarioQuery.refetch()}
              >
                重试情景计算
              </button>
            </div>
          ) : null}
        </section>

        <DataStatusStrip testId="product-category-data-status-strip">
          <ProductCategoryGovernanceStrip
            dataHealth={dataHealth}
            asOfDateGapText={PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY}
            notices={governanceNotices}
            formalScenarioDistinct={formalScenarioDistinct}
            onRetry={
              dataHealth.retryTarget === "dates"
                ? () => void datesQuery.refetch()
                : dataHealth.retryTarget === "baseline"
                  ? () => void baselineQuery.refetch()
                  : null
            }
            evidence={
              <ProductCategoryGovernanceEvidence
                reportDate={selectedDate}
                selectedView={selectedView}
                scenarioApplied={Boolean(scenario)}
                resultMeta={baselineQuery.data?.result_meta}
              />
            }
          />
        </DataStatusStrip>
      </section>

      <ProductCategorySectionNav />
      <a
        data-testid="product-category-next-analysis-preview"
        className="product-category-next-analysis-preview"
        href="#product-category-attribution"
      >
        <span>
          <small>下一分析区</small>
          <strong>归因与趋势</strong>
        </span>
        <span aria-hidden="true">↓</span>
      </a>

      {showManualForm ? (
        <div
          id="product-category-manual-adjustment-form"
          data-testid="product-category-manual-form"
          className="product-category-manual-form"
        >
          <div className="product-category-manual-form__title">
            {editingAdjustmentId ? "编辑手工录入" : "手工录入"}
          </div>
          <div className="product-category-manual-form__grid">
            <label className="product-category-manual-form__field">
              报表日期
              <input
                aria-label="手工录入-报表日期"
                value={adjustmentDraft.report_date}
                readOnly
              />
            </label>
            <label className="product-category-manual-form__field">
              操作方式
              <select
                aria-label="手工录入-操作方式"
                value={adjustmentDraft.operator}
                onChange={(event) =>
                  updateAdjustmentField(
                    "operator",
                    event.target.value as "ADD" | "DELTA" | "OVERRIDE",
                  )
                }
              >
                <option value="ADD">新增</option>
                <option value="DELTA">差额调整</option>
                <option value="OVERRIDE">覆盖</option>
              </select>
            </label>
            <label className="product-category-manual-form__field">
              币种
              <select
                aria-label="手工录入-币种"
                value={adjustmentDraft.currency}
                onChange={(event) =>
                  updateAdjustmentField(
                    "currency",
                    event.target.value as "CNX" | "CNY",
                  )
                }
              >
                <option value="CNX">CNX</option>
                <option value="CNY">CNY</option>
              </select>
            </label>
            <label className="product-category-manual-form__field">
              科目代码
              <input
                aria-label="手工录入-科目代码"
                value={adjustmentDraft.account_code}
                onChange={(event) =>
                  updateAdjustmentField("account_code", event.target.value)
                }
              />
            </label>
            <label className="product-category-manual-form__field">
              科目名称
              <input
                aria-label="手工录入-科目名称"
                value={adjustmentDraft.account_name ?? ""}
                onChange={(event) =>
                  updateAdjustmentField("account_name", event.target.value)
                }
              />
            </label>
            <label className="product-category-manual-form__field">
              审批状态
              <select
                aria-label="手工录入-审批状态"
                value={adjustmentDraft.approval_status}
                onChange={(event) =>
                  updateAdjustmentField(
                    "approval_status",
                    event.target.value as "approved" | "pending" | "rejected",
                  )
                }
              >
                <option value="approved">已通过</option>
                <option value="pending">待审批</option>
                <option value="rejected">已拒绝</option>
              </select>
            </label>
            {[
              ["beginning_balance", "期初余额"],
              ["ending_balance", "期末余额"],
              ["monthly_pnl", "月度损益"],
              ["daily_avg_balance", "月日均"],
              ["annual_avg_balance", "年日均"],
            ].map(([field, label]) => (
              <label
                key={field}
                className="product-category-manual-form__field"
              >
                {label}
                <input
                  aria-label={`手工录入-${label}`}
                  value={
                    (
                      adjustmentDraft as Record<
                        string,
                        string | null | undefined
                      >
                    )[field] ?? ""
                  }
                  onChange={(event) =>
                    updateAdjustmentField(
                      field as keyof ProductCategoryManualAdjustmentRequest,
                      event.target.value || null,
                    )
                  }
                />
              </label>
            ))}
          </div>
          {adjustmentError ? (
            <div
              data-testid="product-category-manual-error"
              className="product-category-manual-form__error"
            >
              {adjustmentError}
            </div>
          ) : null}
          <div className="product-category-manual-form__actions">
            <button
              type="button"
              data-testid="product-category-manual-submit"
              onClick={() => void handleManualAdjustmentSubmit()}
              disabled={isSubmittingAdjustment}
            >
              {isSubmittingAdjustment
                ? "提交中..."
                : editingAdjustmentId
                  ? "保存并刷新"
                  : "提交并刷新"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowManualForm(false);
                setEditingAdjustmentId(null);
                setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      <section
        className="product-category-attribution-workbench"
        data-testid="product-category-attribution-workbench"
        id="product-category-attribution"
      >
        {canRenderBaselineDerivedAnalysis ? (
          <>
            {scenario ? (
              <div
                className="product-category-scenario-signing-warning"
                data-testid="product-category-scenario-signing-warning"
                role="note"
                title="formal_use_allowed=false"
              >
                当前顶部总计来自 FTP {String(scenario.scenario_rate_pct)}%
                场景预览，不可用于签批；下方归因继续使用正式基线响应，二者不得混作同一口径。
              </div>
            ) : null}
            <ProductCategoryAttributionPanel
              selectedView={selectedView}
              compare={attributionCompare}
              payload={attributionQuery.data?.result}
              resultMeta={attributionQuery.data?.result_meta}
              isLoading={attributionQuery.isLoading}
              isError={attributionQuery.isError}
              decisionReadout={
                selectedView === "monthly" &&
                attributionQuery.data?.result.state === "complete" ? (
                  <ProductCategoryAttributionBridge
                    waterfall={attributionWaterfallSurface}
                    rootCause={rootCauseSurface}
                    onOpenDetails={handleLocateFormalRow}
                  />
                ) : null
              }
              detailsOpen={attributionDetailsOpen}
              detailsRef={attributionDetailsRef}
              selectedDetailCategoryId={selectedAttributionDetailCategoryId}
              onCompareChange={setAttributionCompare}
              onDetailsOpenChange={setAttributionDetailsOpen}
              onLocateFormalRow={handleLocateFormalRow}
              onSelectDetailCategory={handleAttributionDetailSelection}
              onRetry={() => void attributionQuery.refetch()}
            />
          </>
        ) : null}
      </section>

      {canRenderBaselineDerivedAnalysis && selectedView === "monthly" ? (
        <ProductCategoryManagementMonitoring
          surface={managementMonitoringSurface}
          isLoading={
            !managementScenarioDistinct &&
            (managementMomAttributionQuery.isLoading || trendHistoryLoading)
          }
          isError={
            !managementScenarioDistinct &&
            (managementMomAttributionQuery.isError || trendHistoryErrored)
          }
          onRetry={() => {
            void Promise.all([
              managementMomAttributionQuery.refetch(),
              ...trendHistoryQueries.map((query) => query.refetch()),
            ]);
          }}
        />
      ) : null}

      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-trend-terminal"
          data-testid="product-category-trend-workspace"
          open={trendWorkspaceOpen}
          onToggle={(event) => {
            const isOpen = event.currentTarget.open;
            setTrendWorkspaceOpen(isOpen);
            persistProductCategoryTrendWorkspacePreference(isOpen);
          }}
        >
          <summary onPointerEnter={() => void loadReactECharts()}>
            <div className="product-category-trend-terminal__header">
              <div className="product-category-trend-terminal__copy">
                <span>趋势与利差</span>
                <strong>趋势与利差候选图表</strong>
                <small>
                  最近 {trendSnapshots.length || 8} 个报告期 · 正式接口历史
                </small>
              </div>
              <div
                className="product-category-trend-terminal__metrics"
                aria-label="最新趋势读数"
              >
                <span>
                  <small>生息规模</small>
                  <strong>{trendHeaderMetrics.earningScale}</strong>
                </span>
                <span>
                  <small>负债均额</small>
                  <strong>{trendHeaderMetrics.liabilityAverage}</strong>
                </span>
                <span>
                  <small>净利差</small>
                  <strong>{trendHeaderMetrics.netSpread}</strong>
                </span>
              </div>
              <span
                className="product-category-trend-terminal__toggle"
                aria-hidden="true"
              >
                {trendWorkspaceOpen ? "收起趋势 ↑" : "展开趋势 ↓"}
              </span>
            </div>
          </summary>

          {trendWorkspaceOpen ? (
            <div className="product-category-trend-terminal__body">
              <section
                className="product-category-trend-terminal__core"
                data-testid="product-category-trend-core-charts"
              >
                <div
                  className="product-category-derived-charts product-category-trend-terminal__grid"
                  data-testid="product-category-derived-chart-grid"
                >
                  <DerivedChartPanel
                    testId="product-category-derived-chart-tpl-scale-yield"
                    title="TPL资产规模收益率走势图"
                    description="跟踪TPL资产人民币规模、外币规模与综合收益率变化。"
                    option={tplScaleYieldOption}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-currency-net-income"
                    title="人民币/外币净收入走势分析图"
                    description="按全市场净收入拆分人民币与外币贡献，观察币种结构变化。"
                    option={currencyNetIncomeOption}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-earning-income-scale"
                    title="生息资产收入规模趋势图"
                    description="跟踪近8个报告期生息资产收入规模的变化趋势。"
                    option={interestEarningIncomeScaleOption}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-spread"
                    title="资产负债利差趋势图"
                    description="跟踪近8个报告期资产端与负债端利差的变化趋势。"
                    option={interestSpreadOption}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-earning-spread"
                    title="生息资产负债利差趋势图"
                    description="对比生息资产收益率、计息负债成本率与利差的变化。"
                    option={interestEarningSpreadOption}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-earning-asset-liability-scale"
                    title="生息资产和附息负债走势图"
                    description="跟踪近8个报告期生息资产与附息负债日均余额的变化趋势。"
                    option={interestEarningAssetLiabilityScaleOption}
                  />
                </div>
              </section>

              <section
                className="product-category-trend-terminal__analysis product-category-trend-terminal__grid"
                data-testid="product-category-trend-analysis"
              >
                <article
                  className="product-category-diagnostics__card product-category-trend-terminal__analysis-card"
                  data-testid="product-category-trend-spread-attribution"
                >
                  <div className="product-category-diagnostics__intro">
                    <h3 className="product-category-diagnostics__title">
                      利差变动归因
                    </h3>
                    <p className="product-category-diagnostics__description">
                      资产端收益率 − 负债端付息率
                    </p>
                  </div>
                  <div className="product-category-diagnostics__spread-grid">
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        {diagnosticsSurface.spreadAttribution.currentLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentSpreadLabel
                        }
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        资产{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentAssetYieldLabel
                        }{" "}
                        / 负债{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentLiabilityYieldLabel
                        }
                      </span>
                    </div>
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        {diagnosticsSurface.spreadAttribution.priorLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {diagnosticsSurface.spreadAttribution.priorSpreadLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        资产变动{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .assetYieldDeltaLabel
                        }{" "}
                        / 负债变动{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .liabilityYieldDeltaLabel
                        }
                      </span>
                    </div>
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        归因结论
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        {diagnosticsSurface.spreadAttribution.driverHint}
                      </span>
                    </div>
                  </div>
                  {diagnosticsSurface.spreadAttribution.state ===
                  "incomplete" ? (
                    <div className="product-category-diagnostics__empty">
                      {diagnosticsSurface.spreadAttribution.reason}
                    </div>
                  ) : (
                    <p className="product-category-trend-terminal__driver-note">
                      本期利差变动{" "}
                      {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}：
                      {diagnosticsSurface.spreadAttribution.driverHint}。
                    </p>
                  )}
                </article>

                <article
                  className="product-category-diagnostics__card product-category-trend-terminal__analysis-card product-category-trend-terminal__liability"
                  data-testid="product-category-trend-liability-card"
                >
                  <div className="product-category-diagnostics__header">
                    <div className="product-category-diagnostics__intro">
                      <h3 className="product-category-diagnostics__title">
                        负债端趋势分析
                      </h3>
                      <p className="product-category-diagnostics__description">
                        负债总额的正式接口历史走势
                      </p>
                    </div>
                    <a href="#product-category-liabilities">负债侧口径 →</a>
                  </div>
                  {liabilitySideTrendOption ? (
                    <LazyReactECharts
                      option={liabilitySideTrendOption}
                      className="product-category-derived-chart__canvas"
                      data-testid="product-category-trend-liability-chart"
                      notMerge
                      lazyUpdate
                    />
                  ) : (
                    <div className="product-category-diagnostics__empty">
                      {liabilitySideTrendSurface.emptyCopy ??
                        "负债端趋势数据不完整。"}
                    </div>
                  )}
                  <div className="product-category-trend-terminal__liability-metrics">
                    <span>
                      <small>最新日均额</small>
                      <strong>
                        {liabilityTrendReadout?.latestAmountLabel ?? EM_DASH}
                      </strong>
                    </span>
                    <span>
                      <small>最新收益率</small>
                      <strong>
                        {liabilityTrendReadout?.latestRateLabel ?? EM_DASH}
                      </strong>
                    </span>
                    <span>
                      <small>日均额变动</small>
                      <strong>
                        {liabilityTrendReadout?.amountDeltaLabel ?? EM_DASH}
                      </strong>
                    </span>
                    <span>
                      <small>收益率变动</small>
                      <strong>
                        {liabilityTrendReadout?.rateDeltaLabel ?? EM_DASH}
                      </strong>
                    </span>
                  </div>
                </article>
              </section>

              <section
                className="product-category-trend-terminal__supporting"
                data-testid="product-category-trend-supporting"
              >
                <header>
                  <span>同比趋势与后端字段归因</span>
                  <small>
                    {comparisonPriorPeriodLabel} →{" "}
                    {comparisonCurrentPeriodLabel}
                    {" · "}日期覆盖 {comparisonComparableMonthCount}/12
                  </small>
                </header>
                <div
                  className="product-category-trend-comparison__statusbar"
                  data-testid="product-category-trend-comparison-status"
                >
                  <div className="product-category-trend-comparison__periods">
                    <span className="product-category-trend-comparison__period">
                      上年参考：{comparisonPriorPeriodLabel}
                    </span>
                    <span className="product-category-trend-comparison__period">
                      当前观察：{comparisonCurrentPeriodLabel}
                    </span>
                    <span className="product-category-trend-comparison__period">
                      日期覆盖 {comparisonComparableMonthCount}/12
                    </span>
                  </div>
                  <span
                    className={`product-category-trend-comparison__load-state is-${comparisonLoadState}`}
                  >
                    {comparisonLoadLabel}
                  </span>
                </div>
                <div
                  className="product-category-derived-charts product-category-trend-terminal__grid"
                  data-testid="product-category-trend-comparison-charts"
                >
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-earning-spread-yoy"
                    title="生息资产利差：今年与上年同月"
                    description="上图对齐两年利差水平，下图直接显示同月同比差（bp）；未进入当前观察期的月份仅保留上年弱参考。"
                    option={interestEarningSpreadYearComparisonOption}
                    comparisonStatus={
                      interestEarningSpreadYearComparisonChart?.comparisonStatus
                    }
                    readout={
                      <ProductCategoryComparisonChartReadout
                        readout={interestEarningSpreadComparisonReadout}
                      />
                    }
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-earning-spread-yoy-cny"
                    title="人民币生息资产利差：今年与上年同月"
                    description="上图对齐人民币利差水平，下图直接显示同月同比差（bp）；未进入当前观察期的月份仅保留上年弱参考。"
                    option={cnyInterestEarningSpreadYearComparisonOption}
                    comparisonStatus={
                      cnyInterestEarningSpreadYearComparisonChart?.comparisonStatus
                    }
                    readout={
                      <ProductCategoryComparisonChartReadout
                        readout={cnyInterestEarningSpreadComparisonReadout}
                      />
                    }
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-spread-yoy"
                    title="资产负债利差：今年与上年同月"
                    description="上图看全口径利差水平，下图看同月同比差（bp）；点击月份联动后端利差字段归因。"
                    option={interestSpreadYearComparisonOption}
                    comparisonStatus={
                      interestSpreadYearComparisonChart?.comparisonStatus
                    }
                    readout={
                      <ProductCategoryComparisonChartReadout
                        readout={interestSpreadComparisonReadout}
                      />
                    }
                    onEvents={{
                      click: (params: unknown) =>
                        handleInterestSpreadAttributionPointClick(
                          "weighted",
                          interestSpreadYearComparisonChart?.monthKeys,
                          params as { dataIndex?: number },
                        ),
                    }}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-interest-spread-yoy-cny"
                    title="人民币资产负债利差：今年与上年同月"
                    description="上图看人民币利差水平，下图看同月同比差（bp）；点击月份联动后端利差字段归因。"
                    option={cnyInterestSpreadYearComparisonOption}
                    comparisonStatus={
                      cnyInterestSpreadYearComparisonChart?.comparisonStatus
                    }
                    readout={
                      <ProductCategoryComparisonChartReadout
                        readout={cnyInterestSpreadComparisonReadout}
                      />
                    }
                    onEvents={{
                      click: (params: unknown) =>
                        handleInterestSpreadAttributionPointClick(
                          "cny",
                          cnyInterestSpreadYearComparisonChart?.monthKeys,
                          params as { dataIndex?: number },
                        ),
                    }}
                  />
                  <DerivedChartPanel
                    testId="product-category-derived-chart-intermediate-business-income-yoy"
                    title="中间业务收入：今年与上年同月"
                    description="并列柱比较同月收入，保留零基线与负值；金额及同比差单位均为亿元。"
                    option={intermediateBusinessIncomeYearComparisonOption}
                    comparisonStatus={
                      intermediateBusinessIncomeYearComparisonChart?.comparisonStatus
                    }
                    readout={
                      <ProductCategoryComparisonChartReadout
                        readout={intermediateBusinessIncomeComparisonReadout}
                      />
                    }
                    wide
                  />
                </div>
                <ProductCategoryInterestSpreadAttributionPanel
                  surface={interestSpreadAttributionSurface}
                  resultMeta={baselineQuery.data?.result_meta}
                />
              </section>
            </div>
          ) : null}
        </details>
      ) : null}

      <details
        data-testid="product-category-adjustment-workspace"
        className="product-category-adjustment-workspace"
      >
        <summary>
          <span>手工调整与审计</span>
          <small>{adjustmentCount} 条当前调整</small>
        </summary>
        <div className="product-category-adjustment-workspace__body">
          <SectionLead
            eyebrow="治理"
            title="手工调整与审计"
            description="手工调整仍走既有新增、更新、撤销、恢复接口，完整事件时间线保留在独立审计视图。仅当审批通过可撤销、仅当已拒绝可恢复；其余审批状态下对应按钮为禁用。撤销、恢复、保存后均触发与全页「刷新损益数据」一致的损益刷新工作流以更新本列表。"
            testId="product-category-adjustment-lead"
          />
          <PageAsyncSection
            title="手工调整历史"
            isLoading={adjustmentsQuery.isLoading}
            isError={adjustmentsQuery.isError}
            isEmpty={
              !adjustmentsQuery.isLoading &&
              !adjustmentsQuery.isError &&
              (adjustmentsQuery.data?.adjustments.length ?? 0) === 0
            }
            fillHeight={false}
            onRetry={() => void adjustmentsQuery.refetch()}
          >
            <div
              data-testid="product-category-adjustment-history"
              className="product-category-adjustment-history"
            >
              <div className="product-category-adjustment-history__title">
                当前状态
              </div>
              {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
                <div
                  key={`current-${item.adjustment_id}`}
                  className="product-category-adjustment-history__row"
                >
                  <div>
                    <div className="product-category-adjustment-history__account-code">
                      {item.account_code}
                    </div>
                    <div className="product-category-adjustment-history__account-name">
                      {item.account_name || "未填写科目名称"}
                    </div>
                    <div className="product-category-adjustment-history__event">
                      最近事件：{item.event_type}
                    </div>
                  </div>
                  <div>{item.currency}</div>
                  <div>{item.operator}</div>
                  <div>{item.approval_status}</div>
                  <button
                    type="button"
                    data-testid={`product-category-edit-${item.adjustment_id}`}
                    disabled={isSubmittingAdjustment}
                    onClick={() =>
                      handleManualAdjustmentEdit({
                        adjustment_id: item.adjustment_id,
                        report_date: item.report_date,
                        operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                        approval_status: item.approval_status as
                          "approved" | "pending" | "rejected",
                        account_code: item.account_code,
                        currency: item.currency as "CNX" | "CNY",
                        account_name: item.account_name,
                        beginning_balance: item.beginning_balance ?? null,
                        ending_balance: item.ending_balance ?? null,
                        monthly_pnl: item.monthly_pnl ?? null,
                        daily_avg_balance: item.daily_avg_balance ?? null,
                        annual_avg_balance: item.annual_avg_balance ?? null,
                      })
                    }
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    data-testid={`product-category-revoke-${item.adjustment_id}`}
                    disabled={
                      item.approval_status !== "approved" ||
                      isSubmittingAdjustment
                    }
                    onClick={() =>
                      void handleManualAdjustmentRevoke(item.adjustment_id)
                    }
                  >
                    撤销
                  </button>
                  <button
                    type="button"
                    data-testid={`product-category-restore-${item.adjustment_id}`}
                    disabled={
                      item.approval_status !== "rejected" ||
                      isSubmittingAdjustment
                    }
                    onClick={() =>
                      void handleManualAdjustmentRestore(item.adjustment_id)
                    }
                  >
                    恢复
                  </button>
                </div>
              ))}
              <div className="product-category-adjustment-history__audit-summary">
                <div className="product-category-adjustment-history__audit-copy">
                  <div className="product-category-adjustment-history__audit-title">
                    完整事件时间线已迁移到独立审计视图
                  </div>
                  <div className="product-category-adjustment-history__audit-note">
                    当前报表月份共有{" "}
                    {(adjustmentsQuery.data?.events ?? []).length} 条调整事件。
                  </div>
                </div>
                <a
                  href="/product-category-pnl/audit"
                  data-testid="product-category-audit-summary-link"
                >
                  查看调整审计
                </a>
              </div>
            </div>
          </PageAsyncSection>
        </div>
      </details>

      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-financial-workspace"
        >
          <summary>
            <span>财务候选分析</span>
            <small>情景敏感度与决策焦点</small>
          </summary>
          <ProductCategoryFinancialAnalysisPanel
            scenarioSensitivity={scenarioSensitivitySurface}
            scenarioExplanation={scenarioExplanation}
            selectedScenarioReviewCategoryId={
              selectedScenarioExplanationCategoryId
            }
            scenarioReviewActionStatuses={scenarioReviewActionStatuses}
            scenarioReviewIssueReasons={scenarioReviewIssueReasons}
            scenarioActionClosureStatuses={scenarioActionClosureStatuses}
            scenarioActionClosureMemoCategoryId={
              scenarioActionClosureMemoCategoryId
            }
            scenarioSensitivityRequested={scenarioSensitivityRequested}
            scenarioSensitivityLoading={scenarioSensitivityQueries.some(
              (query) => query.isLoading,
            )}
            scenarioSensitivityError={scenarioSensitivityQueries.some(
              (query) => query.isError,
            )}
            onLoadScenarioSensitivity={() => {
              setScenarioSensitivityRequested(true);
              if (scenarioSensitivityRequested) {
                scenarioSensitivityQueries.forEach(
                  (query) => void query.refetch(),
                );
              }
            }}
            onSelectScenarioReview={setSelectedScenarioReviewCategoryId}
            onBulkScenarioReviewActionStatus={
              handleBulkScenarioReviewActionStatus
            }
            onResetScenarioReviewActions={handleResetScenarioReviewActions}
            onSetScenarioReviewActionStatus={handleScenarioReviewActionStatus}
            onSetScenarioReviewIssueReason={handleScenarioReviewIssueReason}
            onSetScenarioActionClosureStatus={handleScenarioActionClosureStatus}
            onSelectScenarioActionClosureMemo={
              setScenarioActionClosureMemoCategoryId
            }
            decisionFocus={decisionFocusSurface}
            candidateNotice={
              <ProductCategoryCandidateMetricNotice
                testId="product-category-financial-analysis-candidate-notice"
                title="财务增强为候选分析"
                status={scenarioSensitivitySurface.metricStatus}
              />
            }
          />
        </details>
      ) : null}

      <span
        id="product-category-products"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-operating-workspace"
        >
          <summary>
            <span>产品经营候选分析</span>
            <small>利润结构、压力项与动作队列</small>
          </summary>
          <ProductCategoryOperatingAnalysisPanel
            surface={operatingAnalysisSurface}
            candidateNotice={
              <ProductCategoryCandidateMetricNotice
                testId="product-category-operating-analysis-candidate-notice"
                title="经营分析为候选指标"
                status={operatingAnalysisSurface.metricStatus}
              />
            }
          />
        </details>
      ) : null}
      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-backtest-workspace"
          onToggle={(event) =>
            setBacktestWorkspaceOpen(event.currentTarget.open)
          }
        >
          <summary>
            <span>动作回测候选分析</span>
            <small>历史命中率、校准与复核任务</small>
          </summary>
          <ProductCategoryOperatingActionBacktestPanel
            surface={operatingActionBacktestSurface}
            isHistoryLoaded={trendDiagnosticsLoaded}
            historyLoading={
              trendHistoryLoading ||
              trendHistoryAttributionQueries.some((query) => query.isLoading)
            }
            candidateNotice={
              <ProductCategoryCandidateMetricNotice
                testId="product-category-operating-action-backtest-candidate-notice"
                title="动作回测为候选复核"
                status={operatingActionBacktestSurface.metricStatus}
              />
            }
          />
        </details>
      ) : null}

      <span
        id="product-category-report"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      <SectionLead
        eyebrow="正式口径"
        title="正式产品类别损益表"
        description="表格继续展示后端返回的产品类别读模型，资产/负债符号展示、情景行为和合计行保持原有逻辑。"
        testId="product-category-formal-table-lead"
      />
      <PageAsyncSection
        title="产品类别损益分析表（单位：亿元）"
        isLoading={baselineQuery.isLoading}
        isError={baselineQuery.isError}
        isEmpty={
          !baselineQuery.isLoading &&
          !baselineQuery.isError &&
          rowsToRender.length === 0
        }
        fillHeight={false}
        onRetry={() => void baselineQuery.refetch()}
        extra={reportExtra}
      >
        {selectedFormalRow ? (
          <ProductCategoryFormalSelectionContext
            reportDate={selectedDate}
            selectedView={selectedView}
            sourceLabel={
              scenario?.scenario_rate_pct == null
                ? "正式基线归因定位"
                : `FTP ${String(scenario.scenario_rate_pct)}% 场景（正式基线归因定位）`
            }
            row={selectedFormalRow}
            onOpenAttributionEvidence={
              attributionDetailContextKey
                ? handleAttributionDetailDrilldown
                : undefined
            }
          />
        ) : null}
        <ProductCategoryFormalTableMobileReadout
          reportDate={selectedDate}
          selectedView={selectedView}
          selectedCategoryId={selectedAttributionDetailCategoryId}
          grandTotal={displayedGrandTotal}
          rows={rowsToRender}
          onOpenAttributionEvidence={
            attributionDetailContextKey
              ? handleAttributionDetailDrilldown
              : undefined
          }
        />
        <div
          className="product-category-formal-table-controls"
          data-testid="product-category-formal-table-display-mode"
          role="group"
          aria-label="报表列展示"
        >
          <button
            type="button"
            aria-pressed={formalTableDisplayMode === "key"}
            className={`product-category-formal-table-controls__button ${
              formalTableDisplayMode === "key"
                ? "product-category-formal-table-controls__button--active"
                : ""
            }`}
            onClick={() => setFormalTableDisplayMode("key")}
          >
            关键读数
          </button>
          <button
            type="button"
            aria-pressed={formalTableDisplayMode === "full"}
            className={`product-category-formal-table-controls__button ${
              formalTableDisplayMode === "full"
                ? "product-category-formal-table-controls__button--active"
                : ""
            }`}
            onClick={() => setFormalTableDisplayMode("full")}
          >
            完整口径
          </button>
        </div>
        {formalTableDisplayMode === "full" ? (
          <p className="product-category-formal-table-scroll-hint">
            横向滚动查看完整字段，产品类别列保持可见。
          </p>
        ) : null}
        <div
          data-testid="product-category-formal-table-raw-grid"
          className="product-category-formal-table-wrap"
        >
          <table
            data-testid="product-category-table"
            className={`product-category-formal-table product-category-formal-table--${formalTableDisplayMode}`}
          >
            <colgroup>
              <col className="product-category-formal-table__col--category" />
              <col className="product-category-formal-table__col--scale" />
              {formalTableDisplayMode === "full" ? (
                <>
                  <col className="product-category-formal-table__col--scale" />
                  <col className="product-category-formal-table__col--scale-foreign" />
                  <col className="product-category-formal-table__col--pnl" />
                  <col className="product-category-formal-table__col--pnl" />
                  <col className="product-category-formal-table__col--pnl-ftp" />
                </>
              ) : null}
              <col className="product-category-formal-table__col--pnl-net" />
              {formalTableDisplayMode === "full" ? (
                <>
                  <col className="product-category-formal-table__col--pnl-foreign" />
                  <col className="product-category-formal-table__col--pnl-ftp" />
                </>
              ) : null}
              <col className="product-category-formal-table__col--pnl-net" />
              <col className="product-category-formal-table__col--business-net" />
              <col className="product-category-formal-table__col--yield" />
            </colgroup>
            <thead>
              {formalTableDisplayMode === "key" ? (
                <>
                  <tr className="product-category-formal-table__header-row">
                    <th
                      rowSpan={2}
                      className="product-category-formal-table__head product-category-formal-table__head--category"
                    >
                      产品类别
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--group">
                      规模日均
                    </th>
                    <th
                      colSpan={3}
                      className="product-category-formal-table__head product-category-formal-table__head--group"
                    >
                      净收入
                    </th>
                    <th
                      rowSpan={2}
                      className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--yield"
                    >
                      加权收益率
                    </th>
                  </tr>
                  <tr className="product-category-formal-table__header-row product-category-formal-table__header-row--metrics">
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      综本规模
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--group-start">
                      人民币净收入
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      外币净收入
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--highlight">
                      营业净收入
                    </th>
                  </tr>
                </>
              ) : (
                <>
                  <tr className="product-category-formal-table__header-row">
                    <th
                      rowSpan={2}
                      className="product-category-formal-table__head product-category-formal-table__head--category"
                    >
                      产品类别
                    </th>
                    <th
                      colSpan={3}
                      className="product-category-formal-table__head product-category-formal-table__head--group"
                    >
                      规模日均
                    </th>
                    <th
                      colSpan={8}
                      className="product-category-formal-table__head product-category-formal-table__head--group"
                    >
                      损益
                    </th>
                    <th
                      rowSpan={2}
                      className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--yield"
                    >
                      加权收益率
                    </th>
                  </tr>
                  <tr className="product-category-formal-table__header-row product-category-formal-table__header-row--metrics">
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      综本
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      人民币
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      外币
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--group-start">
                      综本
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      人民币
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      人民币FTP
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      人民币净收入
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      外币
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      外币FTP
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number">
                      外币净收入
                    </th>
                    <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--highlight">
                      营业净收入
                    </th>
                  </tr>
                </>
              )}
            </thead>
            <tbody>
              {rowsToRender.map((row) => {
                const isSelectedFormalRow =
                  !row.is_total &&
                  row.category_id === selectedAttributionDetailCategoryId;
                const canOpenAttributionEvidence =
                  !row.is_total &&
                  attributionDetailCategoryIds.has(row.category_id);
                return (
                  <tr
                    data-selected={isSelectedFormalRow ? "true" : undefined}
                    data-row-level={row.level}
                    data-testid={`product-category-formal-row-${row.category_id}`}
                    id={`product-category-formal-row-${row.category_id}`}
                    key={row.category_id}
                    className={[
                      "product-category-formal-table__row",
                      row.is_total
                        ? "product-category-formal-table__row--total"
                        : "",
                      !row.is_total && row.level === 0
                        ? "product-category-formal-table__row--parent"
                        : "",
                      !row.is_total && row.level > 0
                        ? "product-category-formal-table__row--child"
                        : "",
                      isSelectedFormalRow
                        ? "product-category-formal-table__row--selected"
                        : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <td className="product-category-formal-table__cell product-category-formal-table__cell--category">
                      <div className={formalCategoryIndentClassName(row.level)}>
                        {canOpenAttributionEvidence ? (
                          <button
                            aria-label={`查看 ${row.category_name} 归因证据`}
                            aria-pressed={isSelectedFormalRow}
                            className="product-category-formal-table__category-button"
                            data-product-category-formal-row-action
                            onClick={() =>
                              handleAttributionDetailDrilldown(row.category_id)
                            }
                            type="button"
                          >
                            {row.category_name}
                          </button>
                        ) : (
                          <div>{row.category_name}</div>
                        )}
                      </div>
                    </td>
                    <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                      {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
                    </td>
                    {formalTableDisplayMode === "full" ? (
                      <>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                          {formatProductCategoryRowDisplayValue(
                            row,
                            row.cny_scale,
                          )}
                        </td>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                          {formatProductCategoryForeignDisplayValue(
                            row,
                            row.foreign_scale,
                          )}
                        </td>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--group-start">
                          {formatProductCategoryRowDisplayValue(
                            row,
                            row.cnx_cash,
                          )}
                        </td>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                          {formatProductCategoryRowDisplayValue(
                            row,
                            row.cny_cash,
                          )}
                        </td>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                          {formatProductCategoryRowDisplayValue(
                            row,
                            row.cny_ftp,
                          )}
                        </td>
                      </>
                    ) : null}
                    <td
                      className={[
                        "product-category-formal-table__cell product-category-formal-table__cell--number",
                        formalTableDisplayMode === "key"
                          ? "product-category-formal-table__cell--group-start"
                          : "",
                        formalValueToneClassName(row.cny_net),
                      ].join(" ")}
                    >
                      {formatProductCategoryRowDisplayValue(row, row.cny_net)}
                    </td>
                    {formalTableDisplayMode === "full" ? (
                      <>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                          {formatProductCategoryForeignDisplayValue(
                            row,
                            row.foreign_cash,
                          )}
                        </td>
                        <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                          {formatProductCategoryForeignDisplayValue(
                            row,
                            row.foreign_ftp,
                          )}
                        </td>
                      </>
                    ) : null}
                    <td
                      className={[
                        "product-category-formal-table__cell product-category-formal-table__cell--number",
                        formalForeignValueToneClassName(row, row.foreign_net),
                      ].join(" ")}
                    >
                      {formatProductCategoryForeignDisplayValue(
                        row,
                        row.foreign_net,
                      )}
                    </td>
                    <td
                      className={[
                        "product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--highlight",
                        formalValueToneClassName(row.business_net_income),
                      ].join(" ")}
                    >
                      {formatProductCategoryRowDisplayValue(
                        row,
                        row.business_net_income,
                      )}
                    </td>
                    <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--yield">
                      {formatProductCategoryYieldValue(row.weighted_yield)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </PageAsyncSection>

      <details
        data-testid="product-category-result-meta-workspace"
        className="product-category-result-meta-workspace"
      >
        <summary>
          <span>结果元信息与证据</span>
          <small>口径、版本、质量与追踪字段</small>
        </summary>
        <FormalResultMetaPanel
          testId="product-category-result-meta"
          title="产品分类结果元信息"
          sections={[
            {
              key: "baseline",
              title: "基线读模型",
              meta: baselineQuery.data?.result_meta,
            },
            {
              key: "scenario",
              title: "场景覆盖",
              meta: scenarioQuery.data?.result_meta,
            },
            {
              key: "attribution",
              title: "归因结果",
              meta: attributionQuery.data?.result_meta,
            },
          ]}
        />
      </details>

      {displayedGrandTotal && canRenderBaselineDerivedAnalysis ? (
        <div
          data-testid="product-category-footer-total"
          className="product-category-footer-total"
        >
          全部市场科目FTP后经营净收入：
          {formatProductCategoryValue(displayedGrandTotal.business_net_income)}
        </div>
      ) : null}

      <span
        id="product-category-liabilities"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      {canRenderBaselineDerivedAnalysis && hasDiagnosticsSurface ? (
        <details
          className="product-category-secondary-workspace product-category-secondary-workspace--diagnostics"
          data-testid="product-category-diagnostics-workspace"
          onToggle={(event) =>
            setDiagnosticsWorkspaceOpen(event.currentTarget.open)
          }
        >
          <summary>
            <span>诊断与负债趋势候选分析</span>
            <small>
              经营矩阵、负贡献观察、利差归因与负债结构核查；走势图已移至上方“趋势与利差候选图表”
            </small>
          </summary>
          {diagnosticsWorkspaceOpen ? (
            <div className="product-category-diagnostics-workspace__body">
              <SectionLead
                eyebrow="诊断"
                title="受治理诊断面板"
                description="仅使用当前 payload 行与趋势快照，补充产品经营诊断矩阵、负贡献观察名单和利差变动归因，不改写后端总计。"
                testId="product-category-diagnostics-lead"
              />
              <ProductCategoryCandidateMetricNotice
                testId="product-category-diagnostics-candidate-notice"
                title="诊断与趋势为候选分析"
                status={diagnosticsSurface.metricStatus}
              />
              <div
                className="product-category-diagnostics"
                data-testid="product-category-diagnostics-surface"
              >
                <article
                  className="product-category-diagnostics__card"
                  data-testid="product-category-diagnostics-matrix"
                >
                  <div className="product-category-diagnostics__header">
                    <div className="product-category-diagnostics__intro">
                      <h3 className="product-category-diagnostics__title">
                        产品经营诊断矩阵
                      </h3>
                      <p className="product-category-diagnostics__description">
                        逐行回看规模、营业净收入、收益率和双币净收入拆分，行身份仅取自
                        `category_id/category_name/side`。
                      </p>
                    </div>
                    {diagnosticsSurface.headlineTotalLabel ? (
                      <span
                        className="product-category-diagnostics__summary"
                        data-testid="product-category-diagnostics-summary"
                      >
                        当前FTP后经营净收入 {diagnosticsSurface.headlineTotalLabel}
                      </span>
                    ) : null}
                  </div>
                  {diagnosticsSurface.matrixEmptyCopy ? (
                    <div
                      data-testid="product-category-diagnostics-matrix-empty"
                      className="product-category-diagnostics__empty"
                    >
                      {diagnosticsSurface.matrixEmptyCopy}
                    </div>
                  ) : (
                    <div className="product-category-diagnostics__table-wrap">
                      <table className="product-category-diagnostics__table">
                        <thead>
                          <tr>
                            <th className="product-category-diagnostics__table-head">
                              产品行
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              端别
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              规模
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              营业净收入
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              收益率
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              人民币净收入
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              外币净收入
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              驱动提示
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {diagnosticsSurface.matrixRows.map((item) => (
                            <tr key={item.categoryId}>
                              <td className="product-category-diagnostics__table-cell">
                                {item.categoryLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.sideLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.scaleLabel}
                              </td>
                              <td
                                className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.businessNetIncomeTone)}`}
                              >
                                {item.businessNetIncomeLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.yieldLabel}
                              </td>
                              <td
                                className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.cnyNetTone)}`}
                              >
                                {item.cnyNetLabel}
                              </td>
                              <td
                                className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.foreignNetTone)}`}
                              >
                                {item.foreignNetLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.driverHint}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>

                <article
                  className="product-category-diagnostics__card"
                  data-testid="product-category-diagnostics-watchlist"
                >
                  <div className="product-category-diagnostics__intro">
                    <h3 className="product-category-diagnostics__title">
                      负贡献观察名单
                    </h3>
                    <p className="product-category-diagnostics__description">
                      仅列出 `business_net_income &lt; 0`
                      的行，并按亏损幅度排序；缺失规模或收益率会显式标注。
                    </p>
                  </div>
                  {diagnosticsSurface.negativeWatchlistEmptyCopy ? (
                    <div
                      data-testid="product-category-diagnostics-watchlist-empty"
                      className="product-category-diagnostics__empty"
                    >
                      {diagnosticsSurface.negativeWatchlistEmptyCopy}
                    </div>
                  ) : (
                    <div className="product-category-diagnostics__watchlist">
                      {diagnosticsSurface.negativeWatchlistRows.map((item) => (
                        <div
                          key={item.categoryId}
                          className="product-category-diagnostics__watchlist-row"
                          data-testid={`product-category-diagnostics-watchlist-row-${item.categoryId}`}
                        >
                          <div className="product-category-diagnostics__watchlist-primary">
                            <div className="product-category-diagnostics__metric-value product-category-diagnostics__metric-value--primary">
                              {item.categoryLabel}
                            </div>
                            <div className="product-category-diagnostics__metric-detail">
                              {item.sideLabel}
                            </div>
                          </div>
                          <div className="product-category-diagnostics__metric">
                            <span className="product-category-diagnostics__metric-label">
                              亏损
                            </span>
                            <span className="product-category-diagnostics__metric-value product-category-diagnostics__value--negative">
                              {item.lossLabel}
                            </span>
                          </div>
                          <div className="product-category-diagnostics__metric">
                            <span className="product-category-diagnostics__metric-label">
                              规模
                            </span>
                            <span className="product-category-diagnostics__metric-value">
                              {item.scaleLabel}
                            </span>
                          </div>
                          <div className="product-category-diagnostics__metric">
                            <span className="product-category-diagnostics__metric-label">
                              收益率
                            </span>
                            <span className="product-category-diagnostics__metric-value">
                              {item.yieldLabel}
                            </span>
                          </div>
                          <div className="product-category-diagnostics__metric">
                            <span className="product-category-diagnostics__metric-label">
                              缺口提示
                            </span>
                            <span className="product-category-diagnostics__metric-value">
                              {[
                                item.scaleMissing ? "规模缺失" : null,
                                item.yieldMissing ? "收益率缺失" : null,
                              ]
                                .filter(Boolean)
                                .join(" / ") || "字段齐全"}
                            </span>
                          </div>
                          <div className="product-category-diagnostics__metric">
                            <span className="product-category-diagnostics__metric-label">
                              驱动提示
                            </span>
                            <span className="product-category-diagnostics__metric-detail">
                              {item.driverHint}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>

                <article
                  className="product-category-diagnostics__card"
                  data-testid="product-category-diagnostics-spread"
                >
                  <div className="product-category-diagnostics__intro">
                    <h3 className="product-category-diagnostics__title">
                      利差变动归因
                    </h3>
                    <p className="product-category-diagnostics__description">
                      使用后端返回的资产收益率、负债收益率和利差字段；字段缺失时保留缺口提示。
                    </p>
                  </div>
                  <div className="product-category-diagnostics__spread-grid">
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        {diagnosticsSurface.spreadAttribution.currentLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentSpreadLabel
                        }
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        资产{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentAssetYieldLabel
                        }{" "}
                        / 负债{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .currentLiabilityYieldLabel
                        }
                      </span>
                    </div>
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        {diagnosticsSurface.spreadAttribution.priorLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {diagnosticsSurface.spreadAttribution.priorSpreadLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        资产变动{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .assetYieldDeltaLabel
                        }{" "}
                        / 负债变动{" "}
                        {
                          diagnosticsSurface.spreadAttribution
                            .liabilityYieldDeltaLabel
                        }
                      </span>
                    </div>
                    <div className="product-category-diagnostics__spread-card">
                      <span className="product-category-diagnostics__spread-caption">
                        归因结论
                      </span>
                      <span className="product-category-diagnostics__spread-value">
                        {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}
                      </span>
                      <span className="product-category-diagnostics__spread-detail">
                        {diagnosticsSurface.spreadAttribution.driverHint}
                      </span>
                    </div>
                  </div>
                  {diagnosticsSurface.spreadAttribution.state ===
                  "incomplete" ? (
                    <div
                      data-testid="product-category-diagnostics-spread-incomplete"
                      className="product-category-diagnostics__empty"
                    >
                      {diagnosticsSurface.spreadAttribution.reason}
                    </div>
                  ) : null}
                </article>
              </div>
              <article
                className="product-category-diagnostics__card product-category-liability-side-trend"
                data-testid="product-category-liability-side-trend"
              >
                <div className="product-category-diagnostics__header">
                  <div className="product-category-diagnostics__intro">
                    <h3 className="product-category-diagnostics__title">
                      负债端趋势分析
                    </h3>
                    <p className="product-category-diagnostics__description">
                      负债侧产品类别口径：使用当前产品分类 payload
                      的负债明细行和后端 liability_total，展示日均额与利率走势。
                    </p>
                  </div>
                  <span className="product-category-diagnostics__summary">
                    负债侧产品类别口径
                  </span>
                </div>
                {liabilitySideTrendOption ? (
                  <LazyReactECharts
                    option={liabilitySideTrendOption}
                    className="product-category-derived-chart__canvas"
                    data-testid="product-category-liability-side-trend-chart"
                    notMerge
                    lazyUpdate
                  />
                ) : (
                  <div
                    className="product-category-diagnostics__empty"
                    data-testid="product-category-liability-side-trend-empty"
                  >
                    {liabilitySideTrendSurface.emptyCopy ??
                      "负债端趋势数据不完整，无法绘制完整走势。"}
                  </div>
                )}
                {liabilitySideTrendSurface.incompleteReasons.length > 0 ? (
                  <div
                    className="product-category-diagnostics__empty"
                    data-testid="product-category-liability-side-trend-incomplete"
                  >
                    {liabilitySideTrendSurface.incompleteReasons.join("；")}
                  </div>
                ) : null}
                {liabilitySideTrendSurface.detailMatrix.rows.length > 0 ? (
                  <>
                    <ProductCategoryLiabilityDetailMatrixMobileReadout
                      matrix={liabilitySideTrendSurface.detailMatrix}
                    />
                    <details
                      className="product-category-liability-matrix__disclosure"
                      data-testid="product-category-liability-side-detail-disclosure"
                    >
                      <summary>
                        <span>全币种明细矩阵</span>
                        <small>
                          {
                            liabilitySideTrendSurface.detailMatrix.periods
                              .length
                          }
                          期 ·{" "}
                          {liabilitySideTrendSurface.detailMatrix.rows.length}行
                        </small>
                      </summary>
                      <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
                        <table
                          className="product-category-diagnostics__table product-category-liability-matrix"
                          data-testid="product-category-liability-side-detail-matrix"
                          aria-label="负债端明细趋势矩阵"
                        >
                          <thead>
                            <tr>
                              <th
                                className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                                rowSpan={2}
                                scope="col"
                              >
                                负债明细
                              </th>
                              {liabilitySideTrendSurface.detailMatrix.periods.map(
                                (period) => (
                                  <th
                                    key={period.key}
                                    className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                    colSpan={2}
                                    scope="colgroup"
                                    data-testid={`product-category-liability-side-period-${period.key}`}
                                  >
                                    {period.label}
                                  </th>
                                ),
                              )}
                              <th
                                className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                colSpan={2}
                                scope="colgroup"
                              >
                                {
                                  liabilitySideTrendSurface.detailMatrix
                                    .movementGroupLabel
                                }
                              </th>
                            </tr>
                            <tr>
                              {liabilitySideTrendSurface.detailMatrix.periods.map(
                                (period) => (
                                  <Fragment key={period.key}>
                                    <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                      日均额
                                    </th>
                                    <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                      收益率
                                    </th>
                                  </Fragment>
                                ),
                              )}
                              <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                日均额
                              </th>
                              <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                收益率
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {liabilitySideTrendSurface.detailMatrix.rows.map(
                              (item) => (
                                <tr
                                  key={item.categoryId}
                                  className={
                                    item.isSummary
                                      ? "product-category-liability-matrix__summary-row"
                                      : undefined
                                  }
                                  data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                                >
                                  <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                                    {item.categoryLabel}
                                  </td>
                                  {item.cells.map((cell) => (
                                    <Fragment key={cell.periodKey}>
                                      <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                        {cell.amountLabel}
                                      </td>
                                      <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                        {cell.rateLabel}
                                      </td>
                                    </Fragment>
                                  ))}
                                  <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                    {item.movement.amountLabel}
                                  </td>
                                  <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                    {item.movement.rateLabel}
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    </details>
                    <div className="product-category-liability-matrix__currency-grid">
                      {liabilitySideTrendSurface.detailMatrix.currencyMatrices.map(
                        (currencyMatrix) => (
                          <section
                            key={currencyMatrix.currencyKey}
                            className="product-category-liability-matrix__currency-section"
                          >
                            <h3 className="product-category-liability-matrix__currency-title">
                              {currencyMatrix.currencyLabel}
                            </h3>
                            <ProductCategoryLiabilityCurrencyMatrixMobileReadout
                              matrix={currencyMatrix}
                              periods={
                                liabilitySideTrendSurface.detailMatrix.periods
                              }
                            />
                            <details
                              className="product-category-liability-matrix__disclosure"
                              data-testid={`product-category-liability-side-currency-disclosure-${currencyMatrix.currencyKey}`}
                            >
                              <summary>
                                <span>完整明细矩阵</span>
                                <small>
                                  {
                                    liabilitySideTrendSurface.detailMatrix
                                      .periods.length
                                  }
                                  期 · {currencyMatrix.rows.length}行
                                </small>
                              </summary>
                              <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
                                <table
                                  className="product-category-diagnostics__table product-category-liability-matrix product-category-liability-matrix--currency"
                                  data-testid={`product-category-liability-side-currency-matrix-${currencyMatrix.currencyKey}`}
                                  aria-label={`${currencyMatrix.currencyLabel}负债结构`}
                                >
                                  <thead>
                                    <tr>
                                      <th
                                        className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                                        rowSpan={2}
                                        scope="col"
                                      >
                                        负债明细
                                      </th>
                                      {liabilitySideTrendSurface.detailMatrix.periods.map(
                                        (period) => (
                                          <th
                                            key={period.key}
                                            className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                            colSpan={2}
                                            scope="colgroup"
                                          >
                                            {period.label}
                                          </th>
                                        ),
                                      )}
                                      <th
                                        className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                        colSpan={2}
                                        scope="colgroup"
                                      >
                                        {currencyMatrix.movementGroupLabel}
                                      </th>
                                    </tr>
                                    <tr>
                                      {liabilitySideTrendSurface.detailMatrix.periods.map(
                                        (period) => (
                                          <Fragment key={period.key}>
                                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                              日均额
                                            </th>
                                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                              收益率
                                            </th>
                                          </Fragment>
                                        ),
                                      )}
                                      <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                        日均额
                                      </th>
                                      <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                        收益率
                                      </th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {currencyMatrix.rows.map((item) => (
                                      <tr
                                        key={item.categoryId}
                                        className={
                                          item.isSummary
                                            ? "product-category-liability-matrix__summary-row"
                                            : undefined
                                        }
                                        data-testid={`product-category-liability-side-currency-detail-${currencyMatrix.currencyKey}-${item.categoryId}`}
                                      >
                                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                                          {item.categoryLabel}
                                        </td>
                                        {item.cells.map((cell) => (
                                          <Fragment key={cell.periodKey}>
                                            <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                              {cell.amountLabel}
                                            </td>
                                            <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                              {cell.rateLabel}
                                            </td>
                                          </Fragment>
                                        ))}
                                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                          {item.movement.amountLabel}
                                        </td>
                                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                          {item.movement.rateLabel}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </details>
                          </section>
                        ),
                      )}
                    </div>
                  </>
                ) : liabilitySideTrendSurface.detailRows.length > 0 ? (
                  <>
                    <ProductCategoryLiabilityFallbackMobileReadout
                      rows={liabilitySideTrendSurface.detailRows}
                    />
                    <div className="product-category-diagnostics__table-wrap">
                      <table
                        className="product-category-diagnostics__table"
                        data-testid="product-category-liability-side-detail-table"
                      >
                        <thead>
                          <tr>
                            <th className="product-category-diagnostics__table-head">
                              负债明细
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              最新日均额
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              日均额变动
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              最新利率
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              利率变动
                            </th>
                            <th className="product-category-diagnostics__table-head">
                              对比期
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {liabilitySideTrendSurface.detailRows.map((item) => (
                            <tr
                              key={item.categoryId}
                              data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                            >
                              <td className="product-category-diagnostics__table-cell">
                                {item.categoryLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.latestAmountLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.amountDeltaLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.latestRateLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.rateDeltaLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell">
                                {item.comparisonLabel}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
              </article>
            </div>
          ) : null}
        </details>
      ) : null}

      <ProductCategoryApiContractLedger
        readRows={readEndpointRows}
        writeRows={writeEndpointRows}
        adjustmentCount={adjustmentCount}
        eventCount={adjustmentEventCount}
        canExport={Boolean(selectedDate)}
        isExporting={isExportingAdjustments}
        exportError={adjustmentExportError}
        exportedFilename={exportedAdjustmentFilename}
        onCreateAdjustment={() => {
          setEditingAdjustmentId(null);
          setAdjustmentError(null);
          setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
          setShowManualForm(true);
          const scrollToForm = () =>
            document
              .getElementById("product-category-manual-adjustment-form")
              ?.scrollIntoView?.({ block: "center" });
          if (typeof requestAnimationFrame === "function") {
            requestAnimationFrame(scrollToForm);
          } else {
            scrollToForm();
          }
        }}
        onExport={() => void handleManualAdjustmentsExport()}
      />
    </section>
  );
}
