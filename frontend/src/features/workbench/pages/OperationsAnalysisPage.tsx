import { useMemo, type ReactNode } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, BalanceAnalysisOverviewPayload, ResultMeta } from "../../../api/contracts";
import { AlertList } from "../../../components/AlertList";
import { CalendarList } from "../../../components/CalendarList";
import { FilterBar } from "../../../components/FilterBar";
import {
  PageFilterTray,
  PageHeader,
  PageSurfacePanel,
} from "../../../components/page/PagePrimitives";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { shellTokens } from "../../../theme/tokens";
import { BusinessConclusion } from "../business-analysis/BusinessConclusion";
import { BusinessContributionTable } from "../business-analysis/BusinessContributionTable";
import { ManagementOutput } from "../business-analysis/ManagementOutput";
import { QualityObservation } from "../business-analysis/QualityObservation";
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
import "./OperationsAnalysisPage.css";

const DISPLAY_FONT =
  '"Alibaba PuHuiTi 3.0", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif';

const OPERATIONS_PRODUCT_CATEGORY_VIEW = "monthly";

const pageShellStyle = {
  display: "grid",
  gap: 24,
} as const;

const heroShellStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 0.92fr) minmax(420px, 1.08fr)",
  gap: 22,
  alignItems: "start",
  padding: "24px 24px 22px",
  borderRadius: 24,
  background: "linear-gradient(180deg, rgba(252,251,248,0.99) 0%, rgba(246,248,246,0.98) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 18px 40px rgba(22, 35, 46, 0.06)",
} as const;

const heroHeaderStyle = {
  marginBottom: 0,
} as const;

const controlStyle = {
  minWidth: 172,
  padding: "12px 14px",
  borderRadius: 14,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "rgba(255, 255, 255, 0.88)",
  color: shellTokens.colorTextPrimary,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.75)",
} as const;

const linkStyle = {
  color: shellTokens.colorAccent,
  fontWeight: 700,
  letterSpacing: "0.01em",
  textDecoration: "none",
} as const;

const filterTrayStyle = {
  background: "rgba(255,255,255,0.6)",
  borderColor: "rgba(214, 222, 220, 0.9)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7)",
} as const;

const filterLabelStyle = {
  display: "block",
  marginBottom: 6,
  color: shellTokens.colorTextMuted,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
} as const;

const balanceOverviewGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
  marginTop: 16,
} as const;

const operationsHeroStripStyle = {
  display: "grid",
  gap: 12,
} as const;

const headlineMetricShellStyle = {
  display: "grid",
  gap: 14,
  minHeight: 172,
  padding: "18px 18px 16px",
  borderRadius: 22,
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(250,249,245,0.96) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 16px 36px rgba(22, 35, 46, 0.05)",
} as const;

const compactMetricShellStyle = {
  ...headlineMetricShellStyle,
  minHeight: 138,
  gap: 10,
  padding: "16px 16px 14px",
  borderRadius: 18,
  boxShadow: "0 12px 28px rgba(22, 35, 46, 0.04)",
} as const;

const metricLabelRowStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 10,
} as const;

const metricLabelStyle = {
  margin: 0,
  color: shellTokens.colorTextMuted,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  lineHeight: 1.45,
  textTransform: "uppercase",
} as const;

const metricValueBlockStyle = {
  display: "grid",
  alignContent: "start",
  gap: 8,
  minHeight: 0,
} as const;

const metricUnitRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "baseline",
  gap: "4px 8px",
  minHeight: 0,
} as const;

const metricDetailStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const sectionLeadShellStyle = {
  display: "grid",
  gap: 10,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
} as const;

const sectionTitleStyle = {
  margin: 0,
  maxWidth: 820,
  color: shellTokens.colorTextPrimary,
  fontSize: 24,
  fontWeight: 800,
  letterSpacing: "-0.03em",
  lineHeight: 1.2,
  fontFamily: DISPLAY_FONT,
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 760,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.85,
} as const;

const sectionBlockStyle = {
  display: "grid",
  gap: 16,
} as const;

const focusEntryShellStyle = {
  marginTop: 8,
  marginBottom: 2,
  padding: "18px 22px 22px",
  borderRadius: 24,
  borderLeft: `4px solid ${shellTokens.colorAccent}`,
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.76) 0%, rgba(247,247,242,0.88) 100%)",
} as const;

const recommendationBodyStyle = {
  display: "grid",
  gap: 12,
} as const;

const recommendationTextStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.8,
  maxWidth: 760,
} as const;

const alignedPanelStyle = {
  display: "grid",
  gap: 16,
  height: "100%",
  padding: 22,
  borderRadius: 24,
  background:
    "linear-gradient(180deg, rgba(252,251,248,0.98) 0%, rgba(247,247,242,0.95) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 18px 44px rgba(22, 35, 46, 0.06)",
} as const;

const alignedPanelTitleStyle = {
  margin: 0,
  color: shellTokens.colorTextPrimary,
  fontSize: 18,
  fontWeight: 750,
  letterSpacing: "-0.02em",
  lineHeight: 1.3,
  fontFamily: DISPLAY_FONT,
} as const;

const alignedPanelContentStyle = {
  display: "grid",
  gap: 12,
  alignContent: "start",
  minHeight: 0,
} as const;

const entryHeaderStyle = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: 12,
  width: "100%",
} as const;

const entryTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 750,
  lineHeight: 1.3,
  letterSpacing: "-0.02em",
  color: shellTokens.colorTextPrimary,
  fontFamily: DISPLAY_FONT,
} as const;

const entryIntroStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.8,
  maxWidth: 760,
} as const;

function OperationsSectionLead({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadShellStyle}>
      <span style={sectionEyebrowStyle}>{eyebrow}</span>
      <h2 style={sectionTitleStyle}>{title}</h2>
      <p style={sectionDescriptionStyle}>{description}</p>
    </div>
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
    <PageSurfacePanel as="section" style={alignedPanelStyle}>
      <h3 style={alignedPanelTitleStyle}>{title}</h3>
      <div style={alignedPanelContentStyle}>{children}</div>
    </PageSurfacePanel>
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
  const valueColor =
    status === "warning"
      ? shellTokens.colorWarning
      : status === "danger"
        ? shellTokens.colorDanger
        : shellTokens.colorTextPrimary;

  return (
    <div className={className} style={compact ? compactMetricShellStyle : headlineMetricShellStyle}>
      <div style={metricLabelRowStyle}>
        <p style={metricLabelStyle}>{label}</p>
      </div>
      <div style={metricValueBlockStyle}>
        <div style={metricUnitRowStyle}>
          <span
            style={{
              color: valueColor,
              fontSize: compact ? 22 : 30,
              fontWeight: 800,
              letterSpacing: "-0.03em",
              lineHeight: compact ? 1.15 : 1.08,
              fontFamily: DISPLAY_FONT,
            }}
          >
            {value}
          </span>
          {unit ? (
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: compact ? 12 : 13,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {unit}
            </span>
          ) : null}
        </div>
        {detail ? <p style={metricDetailStyle}>{detail}</p> : null}
      </div>
    </div>
  );
}

function formatOverviewNumber(raw: string | number | null | undefined): string {
  return formatBalanceAmountToYiFromYuan(raw);
}

function buildStatusCardContent(input: {
  isError: boolean;
  value: string;
  detail: string;
}) {
  if (input.isError) {
    return {
      value: "不可用",
      detail: "当前查询失败，请在下方面板重试。",
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
  const fb = meta.fallback_mode !== "none" ? ` · 回退 ${fallback}` : "";
  return `口径 ${basis} · 质量 ${quality} · 供应 ${vendor}${fb}`;
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
    } · 最新交易日 ${fxFormalStatus?.latest_trade_date ?? "待定"} · 沿用前值 ${
      fxFormalStatus?.carry_forward_count ?? 0
    }`,
  });
  const sourceHeadlineDetail = sourceQuery.isError
    ? sourceStatusCard.detail
    : `${sourceStatusCard.detail} · ${formatResultMetaProvenance(sourceQuery.data?.result_meta)}`;
  const macroQueriesFailed = macroCatalogQuery.isError || macroLatestQuery.isError;
  const macroHeadlineDetail = macroQueriesFailed
    ? macroStatusCard.detail
    : `${macroStatusCard.detail} · ${formatResultMetaProvenance(macroLatestQuery.data?.result_meta)}`;
  const newsHeadlineDetail = newsQuery.isError
    ? newsStatusCard.detail
    : `${newsStatusCard.detail} · ${formatResultMetaProvenance(newsQuery.data?.result_meta)}`;
  const formalFxHeadlineDetail = fxFormalStatusQuery.isError
    ? formalFxStatusCard.detail
    : `${formalFxStatusCard.detail} · ${formatResultMetaProvenance(fxFormalStatusQuery.data?.result_meta)}`;

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
        actionLabel: "Open product-category PnL",
        actionTo: "/product-category-pnl",
      };
    }

    if (missingFxRows.length > 0) {
      return {
        title: "经营判断可用但需关注 FX 覆盖",
        detail: `产品分类损益已解析到 ${productCategoryPnl.report_date} / ${productCategoryPnl.view}，但正式 FX 状态仍缺 ${missingFxRows.length} 对。先用产品分类 formal 结果作经营判断，再核验外币覆盖。`,
        actionLabel: "Open market data",
        actionTo: "/market-data",
      };
    }

    return {
      title: "产品分类经营口径可用于本期判断",
      detail: `当前证据解析到 ${productCategoryPnl.report_date} / ${productCategoryPnl.view}，首屏以 /ui/pnl/product-category 的资产、负债、合计经营净收入为准。`,
      actionLabel: "Open product-category PnL",
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

  const operationsHeadlineCards = useMemo(
    () => {
      const productErr = productCategoryPnlQuery.isError;
      const productProv = formatResultMetaProvenance(productCategoryPnlQuery.data?.result_meta);
      const productDetail = productErr
        ? "产品分类损益：查询失败"
        : `正式经营口径 /ui/pnl/product-category · view ${
            productCategoryPnl?.view ?? OPERATIONS_PRODUCT_CATEGORY_VIEW
          } · ${productProv}`;
      const productDateDetail = productErr
        ? "产品分类损益报告月：查询失败"
        : `总账对账 + 日均配对链路 · ${productProv}`;
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
        value: productCategoryPnl?.report_date ?? latestProductCategoryReportDate ?? "待定",
        detail: productDateDetail,
      },
      {
        title: "产品行数",
        value: String(productCategoryRows.length),
        detail: `正式产品分类行（不含 grand_total）· ${productProv}`,
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
      {
        title: "新闻事件",
        value: newsStatusCard.value,
        detail: newsHeadlineDetail,
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
      newsHeadlineDetail,
      newsStatusCard.value,
      productCategoryPnl?.asset_total.business_net_income,
      productCategoryPnl?.grand_total.business_net_income,
      productCategoryPnl?.liability_total.business_net_income,
      productCategoryPnl?.report_date,
      productCategoryPnl?.view,
      productCategoryPnlQuery.data?.result_meta,
      productCategoryPnlQuery.isError,
      productCategoryRows.length,
      sourceHeadlineDetail,
      sourceStatusCard.value,
    ],
  );

  const primaryHeadlineCards = operationsHeadlineCards.slice(0, 3);
  const supportHeadlineCards = operationsHeadlineCards.slice(3);

  return (
    <section
      className="operations-analysis-page"
      data-testid="operations-layout-preview"
      style={pageShellStyle}
    >
      <div style={heroShellStyle}>
        <div className="operations-analysis-page__hero-main">
          <PageHeader
            title="经营分析"
            eyebrow="受治理经营视图"
            description="从产品分类损益正式读模型出发，先给经营判断与可执行动作；资产负债余额读面只保留为专题入口。"
            badgeLabel={client.mode === "real" ? "真实只读链路" : "本地演示数据"}
            badgeTone={client.mode === "real" ? "positive" : "accent"}
            style={heroHeaderStyle}
          />

          <PageFilterTray style={filterTrayStyle}>
            <FilterBar>
              <label>
                <span style={filterLabelStyle}>范围</span>
                <select style={controlStyle} disabled>
                  <option>金融市场条线</option>
                </select>
              </label>
              <label>
                <span style={filterLabelStyle}>口径</span>
                <select style={controlStyle} disabled>
                  <option>产品分类损益</option>
                </select>
              </label>
              <label>
                <span style={filterLabelStyle}>币种</span>
                <select style={controlStyle} disabled>
                  <option>全部</option>
                </select>
              </label>
              <label>
                <span style={filterLabelStyle}>周期</span>
                <select style={controlStyle} disabled>
                  <option>月度</option>
                </select>
              </label>
            </FilterBar>
          </PageFilterTray>

          <p className="operations-analysis-page__provenance" data-testid="operations-hero-provenance">
            {client.mode === "real"
              ? "链路：真实只读 API。"
              : "链路：本地演示（mock 客户端，非生产）。"}
            首屏只放总账对账 + 日均配对链路产出的 <code>/ui/pnl/product-category</code> formal 经营口径；源批次、宏观、新闻与正式 FX 物化/候选对账只作为可核验证据，不在这里展开明细。
            下方「本期关注事项」「近期经营日历」仍为静态示例。
          </p>
        </div>

        <div
          className="operations-analysis-page__kpi-grid"
          data-testid="operations-business-kpis"
          style={operationsHeroStripStyle}
        >
          <div className="operations-analysis-page__primary-metrics">
            {primaryHeadlineCards.map((card) => (
              <OperationsMetricCard
                key={card.title}
                label={card.title}
                value={card.value}
                unit={card.unit}
                detail={card.detail}
                status={card.status}
                className="operations-analysis-page__metric-card operations-analysis-page__metric-card--primary"
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
                className="operations-analysis-page__metric-card operations-analysis-page__metric-card--support"
              />
            ))}
          </div>
        </div>
      </div>

      <div className="operations-analysis-page__decision-layout">
        <div style={sectionBlockStyle}>
          <OperationsSectionLead
            eyebrow="核心视图"
            title="结论、桥接与质量观察"
            description="先阅读已被正式读链路支撑的判断，再看质量观察提示哪些口径仍待补齐。收益成本桥明确保留为示意。"
          />
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
            <RevenueCostBridge />
            <QualityObservation
              sourceCount={sourceSummaries.length}
              macroCount={macroLatest.length}
              newsCount={newsTotal}
              fxMaterializedCount={fxFormalStatus?.materialized_count}
              fxCandidateCount={fxFormalStatus?.candidate_count}
              missingFxCount={missingFxRows.length}
            />
          </div>
        </div>

        <div className="operations-analysis-page__decision-rail">
          <OperationsPanel title={recommendation.title}>
            <div data-testid="operations-entry-recommendation" style={recommendationBodyStyle}>
              <p style={recommendationTextStyle}>{recommendation.detail}</p>
              <div>
                <Link to={recommendation.actionTo} style={linkStyle}>
                  {recommendation.actionLabel}
                </Link>
              </div>
            </div>
          </OperationsPanel>
          <OperationsPanel title="本期关注事项（静态示例）">
            <AlertList items={OPERATIONS_WATCH_ITEMS} />
          </OperationsPanel>
        </div>
      </div>

      <div style={sectionBlockStyle}>
        <OperationsSectionLead
          eyebrow="贡献"
          title="经营贡献与行动项"
          description="产品分类损益行、管理动作和近期日历放在同一层，方便从经营判断进入执行。"
        />
        <div className="operations-analysis-page__contribution-layout" data-testid="operations-contribution-grid">
          <BusinessContributionTable
            reportDate={productCategoryPnl?.report_date ?? latestProductCategoryReportDate}
            view={productCategoryPnl?.view ?? OPERATIONS_PRODUCT_CATEGORY_VIEW}
            rows={productCategoryRows}
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
            <OperationsPanel title="近期经营日历（静态示例）">
              <CalendarList items={OPERATIONS_CALENDAR_MOCK} />
            </OperationsPanel>
            <ManagementOutput
              recommendationTitle={recommendation.title}
              recommendationDetail={recommendation.detail}
              recommendationActionLabel={recommendation.actionLabel}
              missingFxCount={missingFxRows.length}
            />
          </div>
        </div>
      </div>

      <div style={sectionBlockStyle}>
        <OperationsSectionLead
          eyebrow="结构"
          title="期限与集中度 / 专题入口"
          description="期限缺口只保留结构解读；正式工作簿与细项下钻仍进入对应专题页。"
        />
        <div className="operations-analysis-page__structure-layout" data-testid="operations-structure-grid">
          <TenorConcentrationPanel />

          <div
            className="operations-analysis-page__topic-entry"
            data-testid="operations-entry-balance-section"
            style={focusEntryShellStyle}
          >
        <AsyncSection
          title=""
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
            <div style={entryHeaderStyle}>
              <h2 style={entryTitleStyle}>
                专题入口：资产负债正式读面
              </h2>
              <Link to="/balance-analysis" style={linkStyle} aria-label="进入资产负债分析">
                进入资产负债分析
              </Link>
            </div>
          }
        >
          {balanceOverview ? (
            <div>
              <p style={entryIntroStyle}>
                报告日{" "}
                <span data-testid="operations-entry-balance-report-date">
                  {balanceOverview.report_date}
                </span>
                ，头寸范围={balanceOverview.position_scope}，
                币种口径={balanceOverview.currency_basis}。这里只保留正式工作簿速览，
                作为经营分析后的专题入口，不在本页展开完整工作簿。
              </p>
              <div style={balanceOverviewGridStyle}>
                {[
                  {
                    testId: "operations-entry-balance-detail-rows",
                    label: "明细行数",
                    value: String(balanceOverview!.detail_row_count),
                    detail: "正式读面明细行数",
                  },
                  {
                    testId: "operations-entry-balance-summary-rows",
                    label: "汇总行数",
                    value: String(balanceOverview!.summary_row_count),
                    detail: "正式读面汇总行数",
                  },
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
                      unit={
                        item.testId === "operations-entry-balance-market-value" ||
                        item.testId === "operations-entry-balance-amortized" ||
                        item.testId === "operations-entry-balance-accrued"
                          ? "亿元"
                          : undefined
                      }
                      compact
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </AsyncSection>
      </div>
      </div>
      </div>

    </section>
  );
}
