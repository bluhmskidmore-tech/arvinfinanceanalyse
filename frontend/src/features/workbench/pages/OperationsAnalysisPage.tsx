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
    return "无结果元信息";
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
            ? "陈旧"
            : meta.quality_flag;
  const vendor =
    meta.vendor_status === "ok"
      ? "正常"
      : meta.vendor_status === "vendor_stale"
        ? "供应商陈旧"
        : meta.vendor_status === "vendor_unavailable"
          ? "供应商不可用"
          : meta.vendor_status;
  const fallback =
    meta.fallback_mode === "latest_snapshot"
      ? "最新快照降级"
      : meta.fallback_mode;
  const fb = meta.fallback_mode !== "none" ? `，回退 ${fallback}` : "";
  return `口径 ${basis}，质量 ${quality}，供应 ${vendor}${fb}`;
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
    detail: "来自数据源预览总览的来源摘要数量。",
  });
  const macroStatusCard = buildStatusCardContent({
    isError: macroCatalogQuery.isError || macroLatestQuery.isError,
    value: String(macroLatest.length),
    detail: `宏观目录 ${macroCatalog.length} 条，最新交易日 ${latestTradeDate}`,
  });
  const newsStatusCard = buildStatusCardContent({
    isError: newsQuery.isError,
    value: String(newsTotal),
    detail: "来自 Choice 新闻事件流的当前查询总行数。",
  });
  const formalFxStatusCard = buildStatusCardContent({
    isError: fxFormalStatusQuery.isError,
    value: `${fxFormalStatus?.materialized_count ?? 0} / ${fxFormalStatus?.candidate_count ?? 0}`,
    detail: `物化/候选（对账）${fxFormalStatus?.materialized_count ?? 0} / ${
      fxFormalStatus?.candidate_count ?? 0
    }，最新交易日 ${fxFormalStatus?.latest_trade_date ?? "待定"}，沿用前值 ${
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
        title: "经营口径证据链不完整",
        detail:
          "产品分类损益正式读模型或源批次预览未形成可读结果。先核验总账对账 + 日均配对链路，再下经营判断。",
        actionLabel: "复核源预览",
        actionTo: "/source-preview",
      };
    }

    if (!latestProductCategoryReportDate || !productCategoryPnlQuery.data?.result) {
      return {
        title: "等待产品分类损益证据",
        detail:
          "当前尚未解析到 product-category report date。经营页不再用资产负债余额读面替代经营口径。",
        actionLabel: "打开产品分类损益",
        actionTo: "/product-category-pnl",
      };
    }

    if (missingFxRows.length > 0) {
      return {
        title: "经营判断可用但需关注 FX 覆盖",
        detail: `产品分类损益已解析到 ${productCategoryPnl.report_date} / ${productCategoryPnl.view}，但正式 FX 状态仍缺 ${missingFxRows.length} 对。先用产品分类 formal 结果作经营判断，再核验外币覆盖。`,
        actionLabel: "打开市场数据",
        actionTo: "/market-data",
      };
    }

    return {
      title: "产品分类经营口径可用于本期判断",
      detail: `当前证据解析到 ${productCategoryPnl.report_date} / ${productCategoryPnl.view}，首屏以 /ui/pnl/product-category 的资产、负债、合计经营净收入为准。`,
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
        : `正式经营口径 /ui/pnl/product-category，视图 ${
            productCategoryPnl?.view ?? OPERATIONS_PRODUCT_CATEGORY_VIEW
          }；${productProv}`;
      const productDateDetail = productErr
        ? ""
        : `总账对账 + 日均配对链路；${productProv}`;
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
        detail: productErr ? "" : `正式产品分类行（不含合计行）；${productProv}`,
      },
      {
        title: "源批次",
        value: sourceStatusCard.value,
        detail: sourceHeadlineDetail,
      },
      {
        title: "宏观点位",
        value: macroStatusCard.value,
        detail: macroHeadlineDetail,
      },
      {
        title: "正式 FX",
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
    sourceQuery.isError ? "源批次预览" : null,
    macroCatalogQuery.isError || macroLatestQuery.isError ? "宏观点位" : null,
    fxFormalStatusQuery.isError ? "正式 FX 状态" : null,
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
          detail: "正式读面资产端市值",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-market-value",
          label: "负债端市值",
          value: formatOverviewNumber(balanceOverview.liability_total_market_value_amount),
          detail: "正式读面负债端市值",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-asset-amortized",
          label: "资产端摊余成本",
          value: formatOverviewNumber(balanceOverview.asset_total_amortized_cost_amount),
          detail: "正式读面资产端摊余成本",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-amortized",
          label: "负债端摊余成本",
          value: formatOverviewNumber(balanceOverview.liability_total_amortized_cost_amount),
          detail: "正式读面负债端摊余成本",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-asset-accrued",
          label: "资产端应计利息",
          value: formatOverviewNumber(balanceOverview.asset_total_accrued_interest_amount),
          detail: "正式读面资产端应计利息",
          unit: "亿元",
        },
        {
          testId: "operations-entry-balance-liability-accrued",
          label: "负债端应计利息",
          value: formatOverviewNumber(balanceOverview.liability_total_accrued_interest_amount),
          detail: "正式读面负债端应计利息",
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
            eyebrow="受治理经营视图"
            description="从产品分类损益正式读模型出发，先给经营判断与可执行动作；资产负债余额读面只保留为专题入口。"
            badgeLabel={client.mode === "real" ? "真实只读链路" : "本地演示数据"}
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
            title={`${
              client.mode === "real"
                ? "链路：真实只读 API。"
                : "链路：本地演示（mock 客户端，非生产）。"
            }首屏只放总账对账 + 日均配对链路产出的 /ui/pnl/product-category formal 经营口径；源批次、宏观、新闻与正式 FX 物化/候选对账只作为可核验证据，不在首屏展开明细。`}
          >
            首屏读数为产品分类损益正式经营口径，由总账对账 + 日均配对链路生成；源批次、宏观、新闻与正式
            FX 物化/候选对账仅作核验证据。
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
                首屏查询失败：{failedFirstScreenReads.join("、")}；对应读数以{" "}
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
              新闻事件 {newsStatusCard.value} 行（Choice 事件流，仅作核验证据）。
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
                : `本表受治理元数据：${formatResultMetaProvenance(productCategoryPnlQuery.data.result_meta)}`
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
                专题入口：资产负债正式读面
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
                ；此处为正式工作簿速览，明细进入专题页核对。
              </p>
              <div className="operations-analysis-page__balance-overview-grid">
                {[
                  ...balanceOverviewAmountCards,
                  {
                    testId: "operations-entry-balance-market-value",
                    label: "总市值合计",
                    value: formatOverviewNumber(balanceOverview!.total_market_value_amount),
                    detail: "正式读面总市值",
                  },
                  {
                    testId: "operations-entry-balance-amortized",
                    label: "摊余成本合计",
                    value: formatOverviewNumber(balanceOverview!.total_amortized_cost_amount),
                    detail: "正式读面摊余成本",
                  },
                  {
                    testId: "operations-entry-balance-accrued",
                    label: "应计利息合计",
                    value: formatOverviewNumber(balanceOverview!.total_accrued_interest_amount),
                    detail: "正式读面应计利息",
                  },
                ].map((item) => (
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
                读面行数：明细 {formatOverviewRowCount(balanceOverview.detail_row_count)}
                {" / "}汇总 {formatOverviewRowCount(balanceOverview.summary_row_count)}。
              </p>
            </div>
          ) : null}
        </PageAsyncSection>
      </div>
      </div>
      </div>

    </section>
  );
}
