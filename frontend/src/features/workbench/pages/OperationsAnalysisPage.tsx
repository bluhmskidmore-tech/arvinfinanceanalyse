import { useMemo, type ReactNode } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, BalanceAnalysisOverviewPayload, ResultMeta } from "../../../api/contracts";
import { AlertList } from "../../../components/AlertList";
import { CalendarList } from "../../../components/CalendarList";
import { FilterBar } from "../../../components/FilterBar";
import { DataSourceBadge } from "../../../components/StatusPill";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import {
  PageFilterTray,
  PageHeader,
} from "../../../components/page/PagePrimitives";
import { BusinessConclusion } from "../business-analysis/BusinessConclusion";
import { BusinessContributionTable } from "../business-analysis/BusinessContributionTable";
import { ManagementOutput } from "../business-analysis/ManagementOutput";
import { RevenueCostBridge } from "../business-analysis/RevenueCostBridge";
import { TenorConcentrationPanel } from "../business-analysis/TenorConcentrationPanel";
import {
  OPERATIONS_CALENDAR_MOCK,
  OPERATIONS_WATCH_ITEMS,
} from "../business-analysis/businessAnalysisWorkbenchMocks";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import {
  formatProductCategoryValue,
  selectProductCategoryDetailRows,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";
import { EM_DASH } from "../../../utils/format";
import "./OperationsAnalysisPage.css";

const OPERATIONS_PRODUCT_CATEGORY_VIEW = "monthly";

function OperationsSectionLead({ title }: { title: string }) {
  return (
    <div className="operations-analysis-page__section-lead">
      <h2 className="operations-analysis-page__section-title">{title}</h2>
    </div>
  );
}

/**
 * 静态示例区块默认折叠为一行 <details>；红胶囊「静态示例」声明保留在
 * summary 上，展开后才显示示例内容，避免假精度数字与真实读数同屏。
 */
function StaticSampleSection({
  title,
  badgeLabel = "静态示例数据",
  badgeTestId,
  testId,
  children,
}: {
  title: string;
  badgeLabel?: string;
  badgeTestId: string;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <details className="operations-analysis-page__sample-details" data-testid={testId}>
      <summary className="operations-analysis-page__sample-summary">
        <span className="operations-analysis-page__sample-title">{title}</span>
        <DataSourceBadge
          status="mock"
          label={badgeLabel}
          testId={badgeTestId}
          title="静态占位示例，未接入真实数据源，不作正式判断"
        />
        <span className="operations-analysis-page__sample-cue">示意样例（点开查看）</span>
      </summary>
      <div className="operations-analysis-page__sample-body">{children}</div>
    </details>
  );
}

function OperationsPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="operations-analysis-page__panel">
      <h3 className="operations-analysis-page__panel-title">{title}</h3>
      <div className="operations-analysis-page__panel-content">{children}</div>
    </section>
  );
}

function OperationsMetricCard({
  label,
  value,
  detail,
  unit,
  compact = false,
  status = "normal",
  className,
}: {
  label: string;
  value: string;
  detail?: string;
  unit?: string;
  compact?: boolean;
  status?: "normal" | "warning" | "danger";
  className?: string;
}) {
  const cardClassName = ["operations-analysis-page__metric-card", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={cardClassName}
      data-compact={compact ? "true" : undefined}
      data-status={status}
      data-long-value={value.length >= 8 ? "true" : undefined}
    >
      <div className="operations-analysis-page__metric-label-row">
        <p className="operations-analysis-page__metric-label">{label}</p>
      </div>
      <div className="operations-analysis-page__metric-value-block">
        <div className="operations-analysis-page__metric-unit-row">
          <span className="operations-analysis-page__metric-value">
            {value}
          </span>
          {unit && value !== EM_DASH ? (
            <span className="operations-analysis-page__metric-unit">
              {unit}
            </span>
          ) : null}
        </div>
        {detail ? <p className="operations-analysis-page__metric-detail">{detail}</p> : null}
      </div>
    </div>
  );
}

function formatOverviewNumber(raw: string | number | null | undefined): string {
  return formatBalanceAmountToYiFromYuan(raw);
}

/** 读面查询上限 5000 行；命中上限按截断标注，不当作精确总数直出。 */
const OVERVIEW_ROW_CAP = 5000;

function formatOverviewRowCount(count: number): string {
  return count >= OVERVIEW_ROW_CAP ? `≥${count}（截断）` : String(count);
}

/** 查询失败时值位统一 EM_DASH；失败原因收敛到首屏失败横幅一处，不逐卡重复。 */
function buildStatusCardContent(input: {
  isError: boolean;
  value: string;
  detail: string;
}) {
  if (input.isError) {
    return {
      value: EM_DASH,
      detail: "",
    };
  }
  return input;
}

/** Page-local: 受治理元信息一行，不扩展指标含义，只标明口径 / 质量 / 供应商 / 回退。 */
function formatResultMetaProvenance(meta: ResultMeta | undefined): string {
  if (!meta) {
    return "数据说明待确认";
  }
  const basis = meta.basis === "formal" ? "正式口径" : meta.basis === "analytical" ? "分析口径" : meta.basis;
  const quality =
    meta.quality_flag === "ok"
      ? "正常"
      : meta.quality_flag === "warning"
        ? "预警"
        : meta.quality_flag === "error"
          ? "错误"
          : meta.quality_flag === "stale"
            ? "已过期"
            : meta.quality_flag;
  const vendor =
    meta.vendor_status === "ok"
      ? "正常"
      : meta.vendor_status === "vendor_stale"
        ? "更新延迟"
        : meta.vendor_status === "vendor_unavailable"
          ? "暂不可用"
          : meta.vendor_status;
  const fallback =
    meta.fallback_mode === "latest_snapshot"
      ? "使用最近可用数据"
      : meta.fallback_mode;
  const usage = meta.formal_use_allowed === false
    ? "；仅供分析，尚未获准正式使用"
    : meta.formal_use_allowed !== true ? "；正式使用状态待确认" : "";
  const qualityNote = meta.quality_flag !== "ok" ? `；数据质量：${quality}` : "";
  const vendorNote = meta.vendor_status !== "ok" ? `；数据来源${vendor}` : "";
  const fallbackNote = meta.fallback_mode !== "none" ? `；${fallback}` : "";
  return `${basis}${usage}${qualityNote}${vendorNote}${fallbackNote}`;
}

export default function OperationsAnalysisPage() {
  const client = useApiClient();

  const sourceQuery = useQuery({
    queryKey: ["operations-entry", "source-preview", client.mode],
    queryFn: () => client.getSourceFoundation(),
    retry: false,
  });
  const macroCatalogQuery = useQuery({
    queryKey: ["operations-entry", "macro-foundation", client.mode],
    queryFn: () => client.getMacroFoundation(),
    retry: false,
  });
  const macroLatestQuery = useQuery({
    queryKey: ["operations-entry", "macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const fxFormalStatusQuery = useQuery({
    queryKey: ["operations-entry", "fx-formal-status", client.mode],
    queryFn: () => client.getFxFormalStatus(),
    retry: false,
  });
  const newsQuery = useQuery({
    queryKey: ["operations-entry", "choice-news", client.mode],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: 3,
        offset: 0,
      }),
    retry: false,
  });
  const balanceDatesQuery = useQuery({
    queryKey: ["operations-entry", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });
  const productCategoryDatesQuery = useQuery({
    queryKey: ["operations-entry", "product-category-dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  const balanceReportDates = balanceDatesQuery.data?.result.report_dates ?? [];
  const latestBalanceReportDate = balanceReportDates[0] ?? null;
  const productCategoryReportDates = productCategoryDatesQuery.data?.result.report_dates ?? [];
  const latestProductCategoryReportDate = productCategoryReportDates[0] ?? null;

  const balanceOverviewQuery = useQuery({
    queryKey: [
      "operations-entry",
      "balance-analysis-overview",
      client.mode,
      latestBalanceReportDate,
    ],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: latestBalanceReportDate as string,
        positionScope: "all",
        currencyBasis: "CNY",
    }),
    enabled: Boolean(latestBalanceReportDate),
    retry: false,
  }) as Omit<UseQueryResult<ApiEnvelope<BalanceAnalysisOverviewPayload>, Error>, "data"> & {
    data: ApiEnvelope<BalanceAnalysisOverviewPayload>;
  };
  const balanceOverview = balanceOverviewQuery.data?.result;

  const productCategoryPnlQuery = useQuery({
    queryKey: [
      "operations-entry",
      "product-category-pnl",
      client.mode,
      latestProductCategoryReportDate,
      OPERATIONS_PRODUCT_CATEGORY_VIEW,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: latestProductCategoryReportDate as string,
        view: OPERATIONS_PRODUCT_CATEGORY_VIEW,
      }),
    enabled: Boolean(latestProductCategoryReportDate),
    retry: false,
  });
  const productCategoryPnl = productCategoryPnlQuery.data?.result;

  const sourceSummaries = useMemo(
    () => sourceQuery.data?.result.sources ?? [],
    [sourceQuery.data?.result.sources],
  );
  const macroCatalog = useMemo(
    () => macroCatalogQuery.data?.result.series ?? [],
    [macroCatalogQuery.data?.result.series],
  );
  const macroLatest = useMemo(
    () => macroLatestQuery.data?.result.series ?? [],
    [macroLatestQuery.data?.result.series],
  );
  const fxFormalStatus = fxFormalStatusQuery.data?.result;
  const fxFormalRows = useMemo(() => fxFormalStatus?.rows ?? [], [fxFormalStatus?.rows]);
  const missingFxRows = useMemo(
    () => fxFormalRows.filter((row) => row.status === "missing"),
    [fxFormalRows],
  );
  const newsTotal = newsQuery.data?.result.total_rows ?? 0;
  const productCategoryRows = useMemo(
    () => selectProductCategoryDetailRows(productCategoryPnl?.rows, null),
    [productCategoryPnl?.rows],
  );

  const latestTradeDate = useMemo(() => {
    if (macroLatest.length === 0) {
      return "暂无";
    }
    return macroLatest
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [macroLatest]);

  const sourceStatusCard = buildStatusCardContent({
    isError: sourceQuery.isError,
    value: String(sourceSummaries.length),
    detail: "已收录的数据来源数量。",
  });
  const macroStatusCard = buildStatusCardContent({
    isError: macroCatalogQuery.isError || macroLatestQuery.isError,
    value: String(macroLatest.length),
    detail: `宏观目录 ${macroCatalog.length} 条，最新交易日 ${latestTradeDate}`,
  });
  const newsStatusCard = buildStatusCardContent({
    isError: newsQuery.isError,
    value: String(newsTotal),
    detail: "Choice 新闻事件数量。",
  });
  const formalFxStatusCard = buildStatusCardContent({
    isError: fxFormalStatusQuery.isError,
    value: `${fxFormalStatus?.materialized_count ?? 0} / ${fxFormalStatus?.candidate_count ?? 0}`,
    detail: `正式记录 / 候选记录，最新交易日 ${fxFormalStatus?.latest_trade_date ?? "待定"}，沿用前值 ${
      fxFormalStatus?.carry_forward_count ?? 0
    }`,
  });
  const sourceHeadlineDetail = sourceQuery.isError
    ? sourceStatusCard.detail
    : `${sourceStatusCard.detail}；${formatResultMetaProvenance(sourceQuery.data?.result_meta)}`;
  const macroQueriesFailed = macroCatalogQuery.isError || macroLatestQuery.isError;
  const macroHeadlineDetail = macroQueriesFailed
    ? macroStatusCard.detail
    : `${macroStatusCard.detail}；${formatResultMetaProvenance(macroLatestQuery.data?.result_meta)}`;
  const formalFxHeadlineDetail = fxFormalStatusQuery.isError
    ? formalFxStatusCard.detail
    : `${formalFxStatusCard.detail}；${formatResultMetaProvenance(fxFormalStatusQuery.data?.result_meta)}`;

  const recommendation = useMemo(() => {
    const hasCriticalError =
      sourceQuery.isError ||
      productCategoryDatesQuery.isError ||
      productCategoryPnlQuery.isError;
    const hasCriticalEmpty =
      sourceSummaries.length === 0 ||
      productCategoryReportDates.length === 0 ||
      !productCategoryPnl ||
      productCategoryRows.length === 0;

    if (hasCriticalError || hasCriticalEmpty) {
      return {
        title: "经营分析数据尚不完整",
        detail:
          "产品分类损益或数据来源暂不可用。请在数据更新中心核对报告日和数据更新情况，补齐后再判断本期经营表现。",
        actionLabel: "打开数据更新中心",
        actionTo: "/platform-config",
      };
    }

    if (!latestProductCategoryReportDate || !productCategoryPnlQuery.data?.result) {
      return {
        title: "等待产品分类损益数据",
        detail:
          "当前暂无可用报告日，请在产品分类损益页查看数据情况。",
        actionLabel: "打开产品分类损益",
        actionTo: "/product-category-pnl",
      };
    }

    if (missingFxRows.length > 0) {
      return {
        title: "本期经营分析需关注汇率缺口",
        detail: `产品分类损益报告日为 ${productCategoryPnl.report_date}，正式汇率仍缺 ${missingFxRows.length} 对。涉及外币的经营判断需先核验汇率覆盖。`,
        actionLabel: "打开市场数据",
        actionTo: "/market-data",
      };
    }

    return {
      title: "查看本期产品分类经营表现",
      detail: `产品分类损益报告日为 ${productCategoryPnl.report_date}。可分别查看资产、负债及合计经营净收入，再进入明细比较各类产品贡献。`,
      actionLabel: "打开产品分类损益",
      actionTo: "/product-category-pnl",
    };
  }, [
    latestProductCategoryReportDate,
    missingFxRows.length,
    productCategoryDatesQuery.isError,
    productCategoryPnl,
    productCategoryPnlQuery.data?.result,
    productCategoryPnlQuery.isError,
    productCategoryReportDates.length,
    productCategoryRows.length,
    sourceQuery.isError,
    sourceSummaries.length,
  ]);

  const pnlReadFailed =
    productCategoryDatesQuery.isError || productCategoryPnlQuery.isError;

  const operationsHeadlineCards = useMemo(
    () => {
      const productErr = pnlReadFailed;
      const productProv = formatResultMetaProvenance(productCategoryPnlQuery.data?.result_meta);
      // 失败原因收敛到首屏失败横幅一处；失败期间卡内不再逐卡重复同一文案。
      const productDetail = productErr
        ? ""
        : `${!productCategoryPnl?.view || productCategoryPnl.view === "monthly" ? "月度" : productCategoryPnl.view}产品分类损益；${productProv}`;
      const productDateDetail = productErr
        ? ""
        : "本期产品分类损益的报告日期";
      return [
      {
        title: "资产净收入",
        value: formatProductCategoryValue(productCategoryPnl?.asset_total.business_net_income),
        unit: "亿元",
        detail: productDetail,
      },
      {
        title: "负债净收入",
        value: formatProductCategoryValue(productCategoryPnl?.liability_total.business_net_income),
        unit: "亿元",
        detail: productDetail,
      },
      {
        title: "经营净收入",
        value: formatProductCategoryValue(productCategoryPnl?.grand_total.business_net_income),
        unit: "亿元",
        detail: productDetail,
      },
      {
        title: "报告月份",
        value: productErr
          ? EM_DASH
          : productCategoryPnl?.report_date ?? latestProductCategoryReportDate ?? EM_DASH,
        detail: productDateDetail,
      },
      {
        title: "产品行数",
        value: productCategoryPnl ? String(productCategoryRows.length) : EM_DASH,
        detail: productErr ? "" : "产品分类明细，不含合计行",
      },
      {
        title: "数据来源",
        value: sourceStatusCard.value,
        detail: sourceHeadlineDetail,
      },
      {
        title: "宏观点位",
        value: macroStatusCard.value,
        detail: macroHeadlineDetail,
      },
      {
        title: "正式汇率",
        value: formalFxStatusCard.value,
        detail: formalFxHeadlineDetail,
        status: fxFormalStatusQuery.isError ? "warning" as const : "normal" as const,
      },
    ];
    },
    [
      formalFxHeadlineDetail,
      formalFxStatusCard.value,
      fxFormalStatusQuery.isError,
      latestProductCategoryReportDate,
      macroHeadlineDetail,
      macroStatusCard.value,
      pnlReadFailed,
      productCategoryPnl,
      productCategoryPnlQuery.data?.result_meta,
      productCategoryRows.length,
      sourceHeadlineDetail,
      sourceStatusCard.value,
    ],
  );

  const failedFirstScreenReads = [
    pnlReadFailed ? "产品分类损益" : null,
    sourceQuery.isError ? "数据来源" : null,
    macroCatalogQuery.isError || macroLatestQuery.isError ? "宏观点位" : null,
    fxFormalStatusQuery.isError ? "正式汇率" : null,
    newsQuery.isError ? "新闻事件" : null,
  ].filter((item): item is string => Boolean(item));

  const firstScreenRetryTargets = [
    productCategoryDatesQuery,
    productCategoryPnlQuery,
    sourceQuery,
    macroCatalogQuery,
    macroLatestQuery,
    fxFormalStatusQuery,
    newsQuery,
  ];
  const isRetryingFirstScreen = firstScreenRetryTargets.some(
    (query) => query.isError && query.isFetching,
  );
  const retryFirstScreenReads = () => {
    for (const query of firstScreenRetryTargets) {
      if (query.isError) {
        void query.refetch();
      }
    }
  };

  const primaryHeadlineCards = operationsHeadlineCards.slice(0, 3);
  const supportHeadlineCards = operationsHeadlineCards.slice(3);
  const balanceOverviewAmountCards = balanceOverview
    ? [
        {
          testId: "operations-entry-balance-asset-market-value",
          label: "资产端市值",
          value: formatOverviewNumber(balanceOverview.asset_total_market_value_amount),
          detail: "资产端市值",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-market-value",
          label: "负债端市值",
          value: formatOverviewNumber(balanceOverview.liability_total_market_value_amount),
          detail: "负债端市值",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-asset-amortized",
          label: "资产端摊余成本",
          value: formatOverviewNumber(balanceOverview.asset_total_amortized_cost_amount),
          detail: "资产端摊余成本",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-amortized",
          label: "负债端摊余成本",
          value: formatOverviewNumber(balanceOverview.liability_total_amortized_cost_amount),
          detail: "负债端摊余成本",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-asset-accrued",
          label: "资产端应计利息",
          value: formatOverviewNumber(balanceOverview.asset_total_accrued_interest_amount),
          detail: "资产端应计利息",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-accrued",
          label: "负债端应计利息",
          value: formatOverviewNumber(balanceOverview.liability_total_accrued_interest_amount),
          detail: "负债端应计利息",
          unit: "亿元",
        },
      ]
    : [];

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 承担；页根只声明 Nocturne scope
   * （tokens.css 别名块将 --dh-api-* 重映射至 --nct-*，ledger-pnl 同款）。
   */
  return (
    <section
      className="operations-analysis-page"
      data-moss-theme-scope="operations-analysis"
      data-testid="operations-layout-preview"
    >
      <div className="operations-analysis-page__hero-shell">
        <div className="operations-analysis-page__hero-main">
          <PageHeader
            title="经营分析"
            description="查看本期经营净收入、各类产品贡献及需要核验的事项。"
            badgeLabel={client.mode === "real" ? "业务数据" : "本地演示数据"}
            badgeTone={client.mode === "real" ? "positive" : "accent"}
            className="operations-analysis-page__hero-header"
          />

          <div className="operations-analysis-page__filter-tray">
            <PageFilterTray>
              <FilterBar>
                <label>
                  <span className="operations-analysis-page__filter-label">范围</span>
                  <select className="operations-analysis-page__filter-control" disabled>
                    <option>金融市场条线</option>
                  </select>
                </label>
                <label>
                  <span className="operations-analysis-page__filter-label">口径</span>
                  <select className="operations-analysis-page__filter-control" disabled>
                    <option>产品分类损益</option>
                  </select>
                </label>
                <label>
                  <span className="operations-analysis-page__filter-label">币种</span>
                  <select className="operations-analysis-page__filter-control" disabled>
                    <option>全部</option>
                  </select>
                </label>
                <label>
                  <span className="operations-analysis-page__filter-label">周期</span>
                  <select className="operations-analysis-page__filter-control" disabled>
                    <option>月度</option>
                  </select>
                </label>
              </FilterBar>
            </PageFilterTray>
          </div>

          <p
            className="operations-analysis-page__provenance"
            data-testid="operations-hero-provenance"
          >
            经营净收入采用月度产品分类损益口径。宏观数据与新闻用于辅助观察，汇率覆盖情况用于核验外币数据。
          </p>
        </div>

        <div
          className="operations-analysis-page__kpi-grid"
          data-testid="operations-business-kpis"
        >
          {failedFirstScreenReads.length > 0 ? (
            <div
              className="operations-analysis-page__kpi-failure-banner"
              role="alert"
              data-testid="operations-first-screen-failure"
            >
              <span>
                数据暂不可用：{failedFirstScreenReads.join("、")}；对应读数以{" "}
                {EM_DASH} 占位，其余读数不受影响。
              </span>
              <button
                type="button"
                className="operations-analysis-page__retry-button"
                disabled={isRetryingFirstScreen}
                onClick={retryFirstScreenReads}
              >
                {isRetryingFirstScreen ? "读取中" : "重试"}
              </button>
            </div>
          ) : null}
          <div className="operations-analysis-page__primary-metrics">
            {primaryHeadlineCards.map((card) => (
              <OperationsMetricCard
                key={card.title}
                label={card.title}
                value={card.value}
                unit={card.unit}
                detail={card.detail}
                status={card.status}
                className="operations-analysis-page__metric-card--primary"
              />
            ))}
          </div>
          <div className="operations-analysis-page__support-metrics">
            {supportHeadlineCards.map((card) => (
              <OperationsMetricCard
                key={card.title}
                label={card.title}
                value={card.value}
                unit={card.unit}
                detail={card.detail}
                status={card.status}
                compact
                className="operations-analysis-page__metric-card--support"
              />
            ))}
          </div>
          {!newsQuery.isError ? (
            <p
              className="operations-analysis-page__kpi-footnote"
              data-testid="operations-news-footnote"
            >
              新闻事件 {newsStatusCard.value} 条（Choice，仅供参考）。
            </p>
          ) : null}
        </div>
      </div>

      <div className="operations-analysis-page__decision-layout">
        <div className="operations-analysis-page__section-block">
          <OperationsSectionLead title="经营结论" />
          <div className="operations-analysis-page__decision-cards" data-testid="operations-conclusion-grid">
            <BusinessConclusion
              reportDate={productCategoryPnl?.report_date}
              view={productCategoryPnl?.view}
              rowCount={productCategoryPnl ? productCategoryRows.length : undefined}
              assetBusinessNetIncome={formatProductCategoryValue(productCategoryPnl?.asset_total.business_net_income)}
              liabilityBusinessNetIncome={formatProductCategoryValue(
                productCategoryPnl?.liability_total.business_net_income,
              )}
              grandBusinessNetIncome={formatProductCategoryValue(productCategoryPnl?.grand_total.business_net_income)}
              missingFxCount={missingFxRows.length}
            />
          </div>
          <StaticSampleSection
            title="收益成本桥（示意瀑布）"
            badgeLabel="示意数据·未接入正式口径"
            badgeTestId="revenue-cost-bridge-sample-badge"
            testId="operations-bridge-sample-section"
          >
            <RevenueCostBridge />
          </StaticSampleSection>
        </div>

        <div className="operations-analysis-page__decision-rail">
          <OperationsPanel title={recommendation.title}>
            <div data-testid="operations-entry-recommendation" className="operations-analysis-page__recommendation-body">
              <p className="operations-analysis-page__recommendation-text">{recommendation.detail}</p>
              <div>
                <Link to={recommendation.actionTo} className="operations-analysis-page__text-link">
                  {recommendation.actionLabel}
                </Link>
              </div>
            </div>
          </OperationsPanel>
          <StaticSampleSection
            title="本期关注事项"
            badgeTestId="operations-watch-static-sample-badge"
            testId="operations-watch-sample-section"
          >
            <AlertList items={OPERATIONS_WATCH_ITEMS} />
          </StaticSampleSection>
        </div>
      </div>

      <div className="operations-analysis-page__section-block">
        <OperationsSectionLead title="经营贡献与行动项" />
        <div className="operations-analysis-page__contribution-layout" data-testid="operations-contribution-grid">
          <BusinessContributionTable
            reportDate={productCategoryPnl?.report_date ?? latestProductCategoryReportDate}
            view={productCategoryPnl?.view ?? OPERATIONS_PRODUCT_CATEGORY_VIEW}
            rows={productCategoryRows}
            assetTotal={productCategoryPnl?.asset_total}
            liabilityTotal={productCategoryPnl?.liability_total}
            grandTotal={productCategoryPnl?.grand_total}
            loading={productCategoryDatesQuery.isLoading || productCategoryPnlQuery.isLoading}
            error={productCategoryDatesQuery.isError || productCategoryPnlQuery.isError}
            onRetry={() => {
              void productCategoryDatesQuery.refetch();
              void productCategoryPnlQuery.refetch();
            }}
            readProvenanceLine={
              productCategoryPnlQuery.isError || !productCategoryPnlQuery.data
                ? undefined
                : formatResultMetaProvenance(productCategoryPnlQuery.data.result_meta)
            }
          />
          <div className="operations-analysis-page__side-stack">
            <StaticSampleSection
              title="近期经营日历"
              badgeTestId="operations-calendar-static-sample-badge"
              testId="operations-calendar-sample-section"
            >
              <CalendarList items={OPERATIONS_CALENDAR_MOCK} />
            </StaticSampleSection>
            <ManagementOutput
              recommendationTitle={recommendation.title}
              recommendationDetail={recommendation.detail}
              recommendationActionLabel={recommendation.actionLabel}
              missingFxCount={missingFxRows.length}
            />
          </div>
        </div>
      </div>

      <div className="operations-analysis-page__section-block">
        <OperationsSectionLead title="期限与集中度 / 专题入口" />
        <div className="operations-analysis-page__structure-layout" data-testid="operations-structure-grid">
          <StaticSampleSection
            title="期限与集中度"
            badgeTestId="operations-tenor-static-sample-badge"
            testId="operations-tenor-sample-section"
          >
            <TenorConcentrationPanel />
          </StaticSampleSection>

          <div
            className="operations-analysis-page__topic-entry"
            data-testid="operations-entry-balance-section"
          >
        <PageAsyncSection
          title=""
          fillHeight={false}
          isLoading={balanceDatesQuery.isLoading || balanceOverviewQuery.isLoading}
          isError={balanceDatesQuery.isError || balanceOverviewQuery.isError}
          isEmpty={
            !balanceDatesQuery.isLoading &&
            !balanceOverviewQuery.isLoading &&
            !balanceDatesQuery.isError &&
            !balanceOverviewQuery.isError &&
            balanceReportDates.length === 0
          }
          onRetry={() => {
            void balanceDatesQuery.refetch();
            void balanceOverviewQuery.refetch();
          }}
          extra={
            <div className="operations-analysis-page__entry-header">
              <h2 className="operations-analysis-page__entry-title">
                专题入口：资产负债分析
              </h2>
              <Link to="/balance-analysis" className="operations-analysis-page__text-link" aria-label="进入资产负债分析">
                进入资产负债分析
              </Link>
            </div>
          }
        >
          {balanceOverview ? (
            <div>
              <p className="operations-analysis-page__entry-intro">
                报告日{" "}
                <span data-testid="operations-entry-balance-report-date">
                  {balanceOverview.report_date}
                </span>
                ，{balanceOverview.position_scope === "all"
                  ? "全部头寸"
                  : balanceOverview.position_scope}{" "}
                / {balanceOverview.currency_basis === "CNY"
                  ? "人民币口径"
                  : balanceOverview.currency_basis}
                ；资产负债明细可进入专题页查看。
              </p>
              <div className="operations-analysis-page__balance-overview-grid">
                {balanceOverviewAmountCards.map((item) => (
                  <div key={item.testId} data-testid={item.testId}>
                    <OperationsMetricCard
                      label={item.label}
                      value={item.value}
                      detail={item.detail}
                      unit="亿元"
                      compact
                    />
                  </div>
                ))}
              </div>
              <p
                className="operations-analysis-page__entry-footnote"
                data-testid="operations-entry-balance-row-footnote"
              >
                记录数：明细 {formatOverviewRowCount(balanceOverview.detail_row_count)}
                {" / "}汇总 {formatOverviewRowCount(balanceOverview.summary_row_count)}。
              </p>
            </div>
          ) : null}
        </PageAsyncSection>
      </div>
      </div>
      </div>

      <details className="operations-analysis-page__diagnostics" data-testid="operations-technical-diagnostics">
        <summary>技术诊断</summary>
        <p>
          经营损益接口：<code>/ui/pnl/product-category</code>，view={productCategoryPnl?.view ?? OPERATIONS_PRODUCT_CATEGORY_VIEW}。
          由总账对账与日均配对链路生成；表格使用接口返回的产品分类及合计。
        </p>
        <p>
          FX 物化/候选对账：{fxFormalStatus?.materialized_count ?? 0} / {fxFormalStatus?.candidate_count ?? 0}。
        </p>
        <pre>{JSON.stringify({
          product_category: productCategoryPnlQuery.data?.result_meta,
          source: sourceQuery.data?.result_meta,
          macro_catalog: macroCatalogQuery.data?.result_meta,
          macro_latest: macroLatestQuery.data?.result_meta,
          fx: fxFormalStatusQuery.data?.result_meta,
          news: newsQuery.data?.result_meta,
          balance: balanceOverviewQuery.data?.result_meta,
        }, null, 2)}</pre>
      </details>

    </section>
  );
}
