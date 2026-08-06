import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { ResultMeta } from "../../../api/contracts";
import {
  DataStatusStrip,
  EvidencePanel,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageFilterTray,
  PageStateSurface,
  PageV2Shell,
  type PageStateSurfaceVariant,
} from "../../../components/page/PagePrimitives";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
} from "../../../utils/choiceMacroFormat";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import { formatProductCategoryValue } from "../../product-category-pnl/pages/productCategoryPnlPageModel";
import { pickRepresentativeSeries } from "./marketFinanceModel";

import "./MarketFinanceWorkbenchPage.css";

const MISSING_VALUE = "—";
const MARKET_REPRESENTATIVE_BOUNDARY_NOTE =
  "这是页面配置白名单展示，不等于独立 PAGE contract、跨域正式结论或 owner signoff。";
const PRODUCT_CATEGORY_VIEW = "monthly";
const COMPLETE_EVIDENCE_COUNT = 3;

type EvidenceTone = "ready" | "review" | "error" | "loading" | "empty";

type EvidenceAssessment = {
  tone: EvidenceTone;
  label: string;
  flags: string[];
  usable: boolean;
  healthy: boolean;
  queryError: boolean;
  metadataBlocked: boolean;
};

type EvidenceInput = {
  isLoading: boolean;
  isError: boolean;
  hasData: boolean;
  meta: ResultMeta | undefined;
  isDemo: boolean;
};

const TONE_PRIORITY: Record<EvidenceTone, number> = {
  ready: 0,
  review: 1,
  empty: 2,
  loading: 3,
  error: 4,
};

function presentExistingValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return MISSING_VALUE;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : MISSING_VALUE;
  }
  return value;
}

function presentBusinessNetIncome(value: string | number | null | undefined): string {
  const formatted = formatProductCategoryValue(value);
  return formatted === "-" ? MISSING_VALUE : formatted;
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function basisLabel(meta: ResultMeta | undefined): string {
  if (!meta) {
    return "元信息未返回";
  }
  if (meta.basis === "formal") {
    return "正式口径";
  }
  if (meta.basis === "analytical") {
    return "分析口径";
  }
  if (meta.basis === "scenario") {
    return "情景口径";
  }
  if (meta.basis === "mock") {
    return "演示口径";
  }
  return "账务口径";
}

function metaFlags(
  meta: ResultMeta | undefined,
  isDemo: boolean,
): string[] {
  if (!meta) {
    return ["元信息缺失"];
  }

  const flags: string[] = [];
  if (meta.quality_flag === "warning") {
    flags.push("质量预警");
  } else if (meta.quality_flag === "error") {
    flags.push("质量错误");
  } else if (meta.quality_flag === "stale") {
    flags.push("数据陈旧");
  } else if (meta.quality_flag === "missing") {
    flags.push("数据缺失");
  }

  if (meta.vendor_status === "vendor_stale") {
    flags.push("供应商陈旧");
  } else if (meta.vendor_status === "vendor_unavailable") {
    flags.push("供应商不可用");
  }
  if (!meta.formal_use_allowed) {
    flags.push("不可用于正式口径");
  }
  if (meta.fallback_mode === "latest_snapshot") {
    flags.push("使用回退");
  }
  if (isDemo || meta.basis === "mock") {
    flags.push("演示模式");
  }
  return unique(flags);
}

function assessEvidence(input: EvidenceInput): EvidenceAssessment {
  if (input.isLoading) {
    return {
      tone: "loading",
      label: "加载中",
      flags: ["加载中"],
      usable: false,
      healthy: false,
      queryError: false,
      metadataBlocked: false,
    };
  }
  if (input.isError) {
    return {
      tone: "error",
      label: "查询失败",
      flags: ["查询失败"],
      usable: false,
      healthy: false,
      queryError: true,
      metadataBlocked: false,
    };
  }
  const flags = metaFlags(input.meta, input.isDemo);
  const blocked =
    !input.meta ||
    input.meta.quality_flag === "error" ||
    input.meta.quality_flag === "missing" ||
    input.meta.vendor_status === "vendor_unavailable" ||
    !input.meta.formal_use_allowed;
  if (blocked) {
    return {
      tone: "error",
      label: flags.length > 0 ? flags.join(" / ") : "元信息缺失",
      flags,
      usable: false,
      healthy: false,
      queryError: false,
      metadataBlocked: true,
    };
  }

  if (!input.hasData) {
    return {
      tone: "empty",
      label: "无数据",
      flags: ["无数据"],
      usable: false,
      healthy: false,
      queryError: false,
      metadataBlocked: false,
    };
  }

  const tone: EvidenceTone = flags.length > 0 ? "review" : "ready";
  return {
    tone,
    label: flags.length > 0 ? flags.join(" / ") : "已有证据",
    flags,
    usable: true,
    healthy: tone === "ready",
    queryError: false,
    metadataBlocked: false,
  };
}

function marketRepresentativeUnavailableLabel(
  assessment: EvidenceAssessment,
): string {
  if (assessment.tone === "loading") {
    return "加载中";
  }
  if (assessment.queryError) {
    return "查询失败";
  }
  if (assessment.metadataBlocked) {
    return "元信息阻断";
  }
  if (assessment.tone === "empty") {
    return "无数据";
  }
  return assessment.label;
}

function notExecutedAssessment(
  tone: EvidenceTone,
  label: string,
): EvidenceAssessment {
  return {
    tone,
    label,
    flags: [label],
    usable: false,
    healthy: false,
    queryError: false,
    metadataBlocked: false,
  };
}

/** 依赖日期目录的明细查询：目录不可用时明确“未执行”原因，不显示误导性的“无数据”。 */
function assessDependentEvidence(
  parent: EvidenceAssessment,
  input: EvidenceInput,
): EvidenceAssessment {
  if (parent.tone === "loading") {
    return notExecutedAssessment("loading", "等待日期目录");
  }
  if (parent.queryError) {
    return notExecutedAssessment("error", "未执行：日期目录查询异常");
  }
  if (parent.metadataBlocked) {
    return notExecutedAssessment("error", "未执行：日期目录受质量阻断");
  }
  if (parent.tone === "empty") {
    return notExecutedAssessment("empty", "未执行：日期目录为空");
  }
  return assessEvidence(input);
}

function combineEvidence(
  assessments: EvidenceAssessment[],
): EvidenceAssessment {
  const tone = assessments.reduce<EvidenceTone>(
    (current, assessment) =>
      TONE_PRIORITY[assessment.tone] > TONE_PRIORITY[current]
        ? assessment.tone
        : current,
    "ready",
  );
  const flags = unique(assessments.flatMap((assessment) => assessment.flags));
  return {
    tone,
    label:
      flags.length > 0
        ? flags.join(" / ")
        : tone === "ready"
          ? "已有证据"
          : "待复核",
    flags,
    usable: assessments.every((assessment) => assessment.usable),
    healthy: assessments.every((assessment) => assessment.healthy),
    queryError: assessments.some((assessment) => assessment.queryError),
    metadataBlocked: assessments.some(
      (assessment) => assessment.metadataBlocked,
    ),
  };
}

function describeMeta(meta: ResultMeta | undefined, isDemo: boolean): string {
  if (!meta) {
    return "结果元信息未返回";
  }
  const quality =
    meta.quality_flag === "ok"
      ? "质量正常"
      : meta.quality_flag === "stale"
        ? "数据陈旧"
        : meta.quality_flag === "warning"
          ? "质量预警"
          : meta.quality_flag === "missing"
            ? "数据缺失"
            : "质量错误";
  const vendor =
    meta.vendor_status === "ok"
      ? "供应商正常"
      : meta.vendor_status === "vendor_stale"
        ? "供应商陈旧"
        : "供应商不可用";
  const formalUse = meta.formal_use_allowed
    ? "允许正式使用"
    : "不可用于正式口径";
  const fallback =
    meta.fallback_mode === "latest_snapshot" ? "使用最新快照回退" : "未使用回退";
  const mode = isDemo ? "，演示客户端" : "";
  return `${basisLabel(meta)}，${quality}，${vendor}，${formalUse}，${fallback}${mode}`;
}

function metricBasisLabel(
  meta: ResultMeta | undefined,
  isDemo: boolean,
): string {
  const mode = isDemo && meta?.basis !== "mock" ? " / 演示客户端" : "";
  return `${basisLabel(meta)}${mode}`;
}

function metaDateEvidence(meta: ResultMeta | undefined): string {
  if (!meta) {
    return "未返回日期元信息";
  }
  const evidence = [
    meta.requested_report_date
      ? `请求日 ${meta.requested_report_date}`
      : null,
    meta.resolved_report_date
      ? `解析日 ${meta.resolved_report_date}`
      : null,
    meta.fallback_date ? `回退日 ${meta.fallback_date}` : null,
    meta.as_of_date ? `数据日 ${meta.as_of_date}` : null,
  ].filter((item): item is string => Boolean(item));
  return evidence.length > 0 ? evidence.join("；") : "未返回日期元信息";
}

function valueWithUnit(value: string, unit: string): string {
  return value === MISSING_VALUE ? MISSING_VALUE : `${value} ${unit}`;
}

function MetricValue({
  value,
  unit,
}: {
  value: string;
  unit?: string;
}) {
  return (
    <span className="market-finance-workbench__metric-value">
      <span>{value}</span>
      {value !== MISSING_VALUE && unit && unit !== MISSING_VALUE ? (
        <span className="market-finance-workbench__metric-unit">{unit}</span>
      ) : null}
    </span>
  );
}

function PanelHeading({ children }: { children: string }) {
  return <h2 className="market-finance-workbench__panel-heading">{children}</h2>;
}

export default function MarketFinanceWorkbenchPage() {
  const client = useApiClient();
  const isDemo = client.mode === "mock";
  const [isRetrying, setIsRetrying] = useState(false);

  const marketRatesQuery = useQuery({
    queryKey: ["market-finance", "market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    retry: false,
  });
  const productDatesQuery = useQuery({
    queryKey: ["market-finance", "product-category-dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });
  const balanceDatesQuery = useQuery({
    queryKey: ["market-finance", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const rawProductDate =
    productDatesQuery.data?.result.report_dates[0] ?? null;
  const rawBalanceDate =
    balanceDatesQuery.data?.result.report_dates[0] ?? null;
  const productDatesAssessment = assessEvidence({
    isLoading: productDatesQuery.isLoading,
    isError: productDatesQuery.isError,
    hasData: Boolean(rawProductDate),
    meta: productDatesQuery.data?.result_meta,
    isDemo,
  });
  const balanceDatesAssessment = assessEvidence({
    isLoading: balanceDatesQuery.isLoading,
    isError: balanceDatesQuery.isError,
    hasData: Boolean(rawBalanceDate),
    meta: balanceDatesQuery.data?.result_meta,
    isDemo,
  });
  const productDate = productDatesAssessment.usable
    ? rawProductDate
    : null;
  const balanceDate = balanceDatesAssessment.usable
    ? rawBalanceDate
    : null;

  const productPnlQuery = useQuery({
    queryKey: [
      "market-finance",
      "product-category-pnl",
      client.mode,
      productDate,
      PRODUCT_CATEGORY_VIEW,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: productDate as string,
        view: PRODUCT_CATEGORY_VIEW,
      }),
    enabled: Boolean(productDate),
    retry: false,
  });
  const balanceOverviewQuery = useQuery({
    queryKey: [
      "market-finance",
      "balance-analysis-overview",
      client.mode,
      balanceDate,
    ],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: balanceDate as string,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: Boolean(balanceDate),
    retry: false,
  });
  const decisionItemsQuery = useQuery({
    queryKey: [
      "market-finance",
      "balance-analysis-decision-items",
      client.mode,
      balanceDate,
    ],
    queryFn: () =>
      client.getBalanceAnalysisDecisionItems({
        reportDate: balanceDate as string,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: Boolean(balanceDate),
    retry: false,
  });

  const marketSeriesCount =
    marketRatesQuery.data?.result.series.length ?? 0;
  const marketAssessment = assessEvidence({
    isLoading: marketRatesQuery.isLoading,
    isError: marketRatesQuery.isError,
    hasData: marketSeriesCount > 0,
    meta: marketRatesQuery.data?.result_meta,
    isDemo,
  });
  const productPnlAssessment = assessDependentEvidence(productDatesAssessment, {
    isLoading: productPnlQuery.isLoading,
    isError: productPnlQuery.isError,
    hasData: Boolean(productPnlQuery.data?.result),
    meta: productPnlQuery.data?.result_meta,
    isDemo,
  });
  const balanceOverviewAssessment = assessDependentEvidence(balanceDatesAssessment, {
    isLoading: balanceOverviewQuery.isLoading,
    isError: balanceOverviewQuery.isError,
    hasData: Boolean(balanceOverviewQuery.data?.result),
    meta: balanceOverviewQuery.data?.result_meta,
    isDemo,
  });
  const pendingDecisionItems =
    decisionItemsQuery.data?.result.rows
      .filter((row) => row.latest_status.status === "pending")
      .slice(0, 3) ?? [];
  const decisionItemsAssessment = assessDependentEvidence(balanceDatesAssessment, {
    isLoading: decisionItemsQuery.isLoading,
    isError: decisionItemsQuery.isError,
    hasData: pendingDecisionItems.length > 0,
    meta: decisionItemsQuery.data?.result_meta,
    isDemo,
  });
  const productAssessment = combineEvidence([
    productDatesAssessment,
    productPnlAssessment,
  ]);
  const balanceAssessment = combineEvidence([
    balanceDatesAssessment,
    balanceOverviewAssessment,
  ]);

  const rawProductPnl = productPnlQuery.data?.result ?? null;
  const rawBalanceOverview = balanceOverviewQuery.data?.result ?? null;
  const productPnl = productAssessment.usable ? rawProductPnl : null;
  const balanceOverview = balanceAssessment.usable
    ? rawBalanceOverview
    : null;

  const marketDate =
    marketRatesQuery.data?.result_meta?.as_of_date ?? null;
  const productReportDate =
    productPnl?.report_date ??
    (productDatesAssessment.usable ? productDate : null);
  const balanceReportDate =
    balanceOverview?.report_date ??
    (balanceDatesAssessment.usable ? balanceDate : null);

  const representativeSeries = marketAssessment.usable
    ? pickRepresentativeSeries(marketRatesQuery.data?.result.series ?? [])
    : [];
  const representativeByKey = new Map(
    representativeSeries.map((item) => [item.key, item]),
  );
  const governmentTenYearSlot = representativeByKey.get("cn-gov-10y");
  const governmentTenYear = governmentTenYearSlot?.point ?? null;
  const hasMarketRepresentativeData = representativeSeries.some(
    (item) => item.point !== null,
  );
  const hasMissingMarketRepresentative = representativeSeries.some(
    (item) => item.point === null,
  );
  const marketKpiValue = governmentTenYear
    ? formatChoiceMacroValue(governmentTenYear, {
        spaceBeforeUnit: false,
        emptyDisplay: MISSING_VALUE,
      })
    : MISSING_VALUE;
  const marketRepresentativeSummary = marketAssessment.usable
    ? representativeSeries
        .map(
          (item) =>
            `${item.label} ${
              item.point
                ? formatChoiceMacroValue(item.point, {
                    spaceBeforeUnit: false,
                    emptyDisplay: MISSING_VALUE,
                  })
                : MISSING_VALUE
            }`,
        )
        .join("；")
    : MISSING_VALUE;
  const ftpValue = presentExistingValue(
    productPnl?.asset_total.baseline_ftp_rate_pct,
  );
  const netIncomeValue = presentBusinessNetIncome(
    productPnl?.grand_total.business_net_income,
  );
  const assetMarketValue = formatBalanceAmountToYiFromYuan(
    balanceOverview?.asset_total_market_value_amount,
  );
  const liabilityMarketValue = formatBalanceAmountToYiFromYuan(
    balanceOverview?.liability_total_market_value_amount,
  );

  const queryAssessments = [
    marketAssessment,
    productDatesAssessment,
    productPnlAssessment,
    balanceDatesAssessment,
    balanceOverviewAssessment,
  ];
  const isLoading = queryAssessments.some(
    (assessment) => assessment.tone === "loading",
  );
  const hasQueryError = queryAssessments.some(
    (assessment) => assessment.queryError,
  );
  const hasMetadataBlock = queryAssessments.some(
    (assessment) => assessment.metadataBlocked,
  );
  const hasBlockingEvidence = hasQueryError || hasMetadataBlock;
  const availableEvidenceCount = [
    marketAssessment.usable,
    productAssessment.usable,
    balanceAssessment.usable,
  ].filter(Boolean).length;
  const hasAnyEvidence = availableEvidenceCount > 0;
  const isEmpty =
    !isLoading && !hasBlockingEvidence && !hasAnyEvidence;
  const queryFlags = unique(
    queryAssessments.flatMap((assessment) => assessment.flags),
  );
  const hasDegradation = queryFlags.some(
    (flag) => flag !== "加载中" && flag !== "无数据",
  );
  const isPartialEvidence =
    !isLoading &&
    availableEvidenceCount > 0 &&
    (availableEvidenceCount < COMPLETE_EVIDENCE_COUNT ||
      hasDegradation);
  const statusFlags = unique([
    ...queryFlags,
    ...(hasMetadataBlock ? ["数据质量阻断"] : []),
    ...(isPartialEvidence ? ["部分证据"] : []),
  ]);
  const hasFallback = statusFlags.includes("使用回退");
  const hasStale =
    statusFlags.includes("数据陈旧") ||
    statusFlags.includes("供应商陈旧");

  let statusTitle = "证据已返回，传导待复核";
  let statusDescription =
    "现有查询可分列市场、FTP、经营和资产负债读数；跨域传导、OCI、资本与 RWA 尚待业务口径确认。";
  let stateVariant: PageStateSurfaceVariant =
    isDemo ? "mock" : "definition-pending";
  let statusTone: EvidenceTone = "review";

  if (isLoading) {
    statusTitle = "正在读取协同证据";
    statusDescription = "市场日频与财务报告期数据正在分别加载，不会在加载完成前形成影响判断。";
    stateVariant = "loading";
    statusTone = "loading";
  } else if (hasQueryError && hasMetadataBlock) {
    statusTitle = "查询异常与数据质量阻断";
    statusDescription =
      "部分请求未完成，另有响应已返回但不可用于判断；仅保留可用证据，不使用默认值补齐。";
    stateVariant = "error";
    statusTone = "error";
  } else if (hasQueryError) {
    statusTitle = hasAnyEvidence ? "部分查询异常" : "数据查询失败";
    statusDescription = hasAnyEvidence
      ? "部分请求未完成；仅展示已成功返回的原始读数，不使用默认值补齐。"
      : "当前查询未完成且没有可核验读数。请重新读取，或分别进入市场与财务专题页核验。";
    stateVariant = "error";
    statusTone = "error";
  } else if (hasMetadataBlock) {
    statusTitle = "数据质量阻断";
    statusDescription = hasAnyEvidence
      ? "部分响应已返回但不可用于判断；其余可用证据仍按原始口径展示。"
      : "响应已返回但不可用于判断；本页不使用被质量状态阻断的读数形成结论。";
    stateVariant = "error";
    statusTone = "error";
  } else if (isEmpty) {
    statusTitle = "暂无可核验数据";
    statusDescription = "市场、经营与资产负债查询均未返回可展示结果，本页不填充演示数字。";
    stateVariant = "empty";
    statusTone = "empty";
  } else if (hasStale) {
    statusTitle = "数据存在陈旧标记";
    statusDescription = "至少一个结果被标记为陈旧。当前读数仅供复核，不生成跨域影响判断。";
    stateVariant = "stale";
    statusTone = "review";
  } else if (hasFallback) {
    statusTitle = "使用回退快照";
    statusDescription = "至少一个结果使用最新快照回退。各指标仍保留自己的数据日期，不合并为同一报告日。";
    stateVariant = "fallback-date";
    statusTone = "review";
  } else if (isDemo) {
    statusTitle = "部分证据可用";
    statusDescription =
      "当前数值来自演示客户端，仅用于页面验收；跨域传导、OCI、资本与 RWA 仍待正式口径确认。";
    stateVariant = "mock";
    statusTone = "review";
  } else if (hasDegradation) {
    statusTitle = "证据需要复核";
    statusDescription =
      "至少一个响应带有非阻断降级标记；当前读数仅供复核，不生成跨域影响判断。";
    stateVariant = "definition-pending";
    statusTone = "review";
  }
  if (!isLoading && statusFlags.length > 0) {
    statusDescription = `${statusDescription} 已检测：${statusFlags.join("、")}。`;
  }

  const heroConclusion = isLoading
    ? "正在分别读取市场与财务证据，完成前不生成管理结论。"
    : hasQueryError && hasMetadataBlock
      ? "查询异常与数据质量阻断同时存在，当前只保留仍可核验的原始证据。"
      : hasQueryError && !hasAnyEvidence
        ? "当前查询未完成，无法判断市场变化对资金成本、资产负债或经营结果的影响。"
        : hasMetadataBlock && !hasAnyEvidence
          ? "响应已返回但不可用于判断，当前不形成市场到财务的影响结论。"
      : isEmpty
        ? "当前没有可核验读数，影响判断保持空缺。"
        : "现有读数已按各自日期分列；跨域传导、OCI 和资本 / RWA 尚无可核验联合口径，暂不生成影响评分。";

  const marketBusinessTone: EvidenceTone = governmentTenYear && !hasMissingMarketRepresentative
    ? marketAssessment.tone
    : marketAssessment.usable
      ? "review"
      : marketAssessment.tone;
  const marketBusinessLabel = governmentTenYear && !hasMissingMarketRepresentative
    ? marketAssessment.label
    : marketAssessment.usable
      ? "待复核"
      : marketAssessment.label;

  const marketTransmissionDetail = marketAssessment.usable
    ? hasMarketRepresentativeData
      ? `${marketRepresentativeSummary}；市场日 ${marketDate ?? MISSING_VALUE}`
      : `页面配置白名单暂无命中代表序列：${marketRepresentativeSummary}；市场日 ${marketDate ?? MISSING_VALUE}`
    : `${marketRepresentativeUnavailableLabel(marketAssessment)}；暂无可核验代表序列。市场日 ${marketDate ?? MISSING_VALUE}`;

  const transmissionNodes = [
    {
      key: "market",
      title: "市场变化",
      tone: marketBusinessTone,
      status: marketBusinessLabel,
      detail: marketTransmissionDetail,
      to: "/market-data",
      action: "查看市场证据",
    },
    {
      key: "funding",
      title: "资金 / FTP",
      tone: productAssessment.tone,
      status: productAssessment.label,
      detail: productPnl
        ? `资产端基准 FTP 率 ${valueWithUnit(ftpValue, "%")}，经营报告日 ${productReportDate ?? MISSING_VALUE}`
        : "产品分类损益未返回基准 FTP 读数。",
      to: "/product-category-pnl",
      action: "查看 FTP 口径",
    },
    {
      key: "alm",
      title: "ALM 约束",
      tone: balanceAssessment.tone,
      status: balanceAssessment.label,
      detail: balanceOverview
        ? `资产负债读面可用，报告日 ${balanceReportDate ?? MISSING_VALUE}`
        : "资产负债读面暂无可核验结果。",
      to: "/balance-analysis",
      action: "查看资产负债",
    },
    {
      key: "pnl-capital",
      title: "损益 / 资本",
      tone: productAssessment.usable
        ? ("review" as const)
        : productAssessment.tone,
      status: productAssessment.usable
        ? "部分可用"
        : productAssessment.label,
      detail: productPnl
        ? `经营净收入 ${valueWithUnit(netIncomeValue, "亿元")}；资本 / RWA 暂无可核验读数`
        : "经营损益、资本与 RWA 尚未形成完整协同证据。",
      to: "/product-category-pnl",
      action: "查看经营读数",
    },
    {
      key: "action",
      title: "管理动作",
      tone: "review" as const,
      status: "待复核",
      detail: "不自动生成建议。待日期、传导与资本口径对齐后进入协同复核。",
      to: "/decision-items",
      action: "进入决策事项",
    },
  ];

  const matrixRows = [
    {
      dimension: "利率 / 资金",
      market: marketRepresentativeSummary,
      finance: "尚未建立与资金成本的正式传导口径",
      state: marketBusinessLabel,
      tone: marketBusinessTone,
      to: "/market-data",
      action: "市场数据",
    },
    {
      dimension: "FTP",
      market: "不在前端推导市场利率向 FTP 的映射",
      finance: productPnl
        ? `资产端基准 FTP 率 ${valueWithUnit(ftpValue, "%")}`
        : MISSING_VALUE,
      state: productAssessment.label,
      tone: productAssessment.tone,
      to: "/product-category-pnl",
      action: "产品分类损益",
    },
    {
      dimension: "ALM",
      market: "不在前端将市场点位映射为期限或流动性缺口",
      finance: balanceOverview
        ? `资产端市值 ${valueWithUnit(assetMarketValue, "亿元")}；负债端市值 ${valueWithUnit(liabilityMarketValue, "亿元")}`
        : MISSING_VALUE,
      state: balanceAssessment.label,
      tone: balanceAssessment.tone,
      to: "/balance-analysis",
      action: "资产负债分析",
    },
    {
      dimension: "OCI / 损益",
      market: "OCI 市场归因未接入本页",
      finance: productPnl
        ? `经营净收入 ${valueWithUnit(netIncomeValue, "亿元")}`
        : MISSING_VALUE,
      state: productPnl
        ? "损益可读，OCI 待复核"
        : productAssessment.label,
      tone: productPnl
        ? ("review" as const)
        : productAssessment.tone,
      to: "/product-category-pnl",
      action: "经营损益",
    },
    {
      dimension: "资本 / RWA",
      market: MISSING_VALUE,
      finance: MISSING_VALUE,
      state: "待复核",
      tone: "review" as const,
      to: null,
      action: "暂无证据入口",
    },
  ];

  const failedRetryTargets = [
    marketRatesQuery,
    productDatesQuery,
    balanceDatesQuery,
    productPnlQuery,
    balanceOverviewQuery,
  ].filter((query) => query.isError);

  function retryFailedQueries() {
    if (isRetrying || failedRetryTargets.length === 0) {
      return;
    }
    setIsRetrying(true);
    void Promise.allSettled(
      failedRetryTargets.map((query) => query.refetch()),
    ).finally(() => {
      setIsRetrying(false);
    });
  }

  return (
    <PageV2Shell testId="market-finance-workbench">
      <div className="market-finance-workbench">
        <PageDecisionHero
          className="market-finance-workbench__hero"
          eyebrow="金市投研 × 计划财务"
          title="金市与计财协同台"
          businessQuestion="当前市场变化如何影响资金成本、资产负债与经营结果？"
          reportDateSlot={
            <div className="market-finance-workbench__hero-dates">
              <span>
                市场数据日 <strong>{marketDate ?? MISSING_VALUE}</strong>
              </span>
              <span>
                经营报告日 <strong>{productReportDate ?? MISSING_VALUE}</strong>
              </span>
              <span>
                资产负债报告日 <strong>{balanceReportDate ?? MISSING_VALUE}</strong>
              </span>
            </div>
          }
          conclusion={heroConclusion}
          actions={
            <div className="market-finance-workbench__hero-actions">
              <Link
                className="market-finance-workbench__action-link market-finance-workbench__action-link--primary"
                to="/market-data"
              >
                下钻市场证据
              </Link>
              <Link
                className="market-finance-workbench__action-link"
                to="/product-category-pnl"
              >
                下钻财务证据
              </Link>
            </div>
          }
        >
          <div className="market-finance-workbench__filter-tray">
            <PageFilterTray testId="market-finance-filter-tray">
              <div
                className="market-finance-workbench__filter-grid"
                role="group"
                aria-label="当前观察范围"
              >
                <div>
                  <span>观察范围</span>
                  <strong>全行</strong>
                </div>
                <div>
                  <span>币种口径</span>
                  <strong>CNY</strong>
                </div>
                <div>
                  <span>经营视图</span>
                  <strong>月度</strong>
                </div>
              </div>
            </PageFilterTray>
          </div>
        </PageDecisionHero>

        <DataStatusStrip
          testId="market-finance-data-status"
          className="market-finance-workbench__data-status"
        >
          <div className="market-finance-workbench__status-item">
            <span>市场数据日</span>
            <strong>{marketDate ?? MISSING_VALUE}</strong>
          </div>
          <div className="market-finance-workbench__status-item">
            <span>财务报告日</span>
            <strong>
              经营 {productReportDate ?? MISSING_VALUE} / 资产负债{" "}
              {balanceReportDate ?? MISSING_VALUE}
            </strong>
          </div>
          <div className="market-finance-workbench__status-item">
            <span>数据模式</span>
            <strong>{isDemo ? "演示模式" : "真实模式"}</strong>
          </div>
          <div className="market-finance-workbench__status-item">
            <span>证据状态</span>
            <strong
              className="market-finance-workbench__status-chip"
              data-tone={statusTone}
            >
              {statusTitle}
            </strong>
          </div>
          <div
            className="market-finance-workbench__status-item"
            data-testid="market-finance-degradation-flags"
          >
            <span>降级标记</span>
            <strong>
              {statusFlags.length > 0
                ? statusFlags.join(" · ")
                : "未检测到降级"}
            </strong>
          </div>
        </DataStatusStrip>

        <section
          className="market-finance-workbench__spine"
          aria-labelledby="market-finance-spine-heading"
        >
          <div className="market-finance-workbench__section-heading">
            <div>
              <p>传导脊柱</p>
              <h2 id="market-finance-spine-heading">从市场观察到管理复核</h2>
            </div>
            <span>仅陈列已有读数、状态与下钻，不计算综合评分</span>
          </div>
          <div
            className="market-finance-workbench__spine-grid"
            data-testid="market-finance-transmission-spine"
          >
            {transmissionNodes.map((node, index) => (
              <article
                key={node.key}
                className="market-finance-workbench__spine-node"
                data-tone={node.tone}
                data-testid={`market-finance-spine-${node.key}`}
              >
                <div className="market-finance-workbench__spine-node-top">
                  <span className="market-finance-workbench__spine-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="market-finance-workbench__status-chip" data-tone={node.tone}>
                    {node.status}
                  </span>
                </div>
                <h3>{node.title}</h3>
                <p>{node.detail}</p>
                <Link to={node.to}>{node.action}</Link>
              </article>
            ))}
          </div>
        </section>

        <KpiBand
          testId="market-finance-kpis"
          className="market-finance-workbench__kpis"
        >
          <KpiBandMetric
            testId="market-finance-kpi-market"
            label={governmentTenYearSlot?.label ?? "市场证据状态"}
            value={<MetricValue value={marketKpiValue} />}
            footer={
              <div className="market-finance-workbench__metric-footer">
                <span>
                  {governmentTenYear
                    ? `较前值 ${formatChoiceMacroDelta(
                        governmentTenYear,
                        {
                          spaceBeforeUnit: false,
                          emptyDisplay: MISSING_VALUE,
                        },
                      )}`
                    : marketAssessment.usable
                      ? `已返回 ${marketSeriesCount} 条序列，业务代表序列待复核`
                    : "暂无可核验读数"}
                </span>
                <span>
                  口径：
                  {metricBasisLabel(
                    marketRatesQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <span>
                  行情日{" "}
                  {governmentTenYear?.trade_date ??
                    marketDate ??
                    MISSING_VALUE}
                </span>
              </div>
            }
          />
          <KpiBandMetric
            testId="market-finance-kpi-ftp"
            label="基准 FTP 率"
            value={<MetricValue value={ftpValue} unit="%" />}
            footer={
              <div className="market-finance-workbench__metric-footer">
                <span>{productPnl ? "资产端基准 FTP" : "暂无可核验读数"}</span>
                <span>
                  口径：
                  {metricBasisLabel(
                    productPnlQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <span>经营报告日 {productReportDate ?? MISSING_VALUE}</span>
              </div>
            }
          />
          <KpiBandMetric
            testId="market-finance-kpi-net-income"
            label="经营净收入"
            value={<MetricValue value={netIncomeValue} unit="亿元" />}
            footer={
              <div className="market-finance-workbench__metric-footer">
                <span>{productPnl ? "产品分类损益合计" : "暂无可核验读数"}</span>
                <span>
                  口径：
                  {metricBasisLabel(
                    productPnlQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <span>经营报告日 {productReportDate ?? MISSING_VALUE}</span>
              </div>
            }
          />
          <KpiBandMetric
            testId="market-finance-kpi-asset-market-value"
            label="资产端市值"
            value={<MetricValue value={assetMarketValue} unit="亿元" />}
            footer={
              <div className="market-finance-workbench__metric-footer">
                <span>
                  {balanceOverview ? "资产负债既有读面" : "暂无可核验读数"}
                </span>
                <span>
                  口径：
                  {metricBasisLabel(
                    balanceOverviewQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <span>资产负债报告日 {balanceReportDate ?? MISSING_VALUE}</span>
              </div>
            }
          />
        </KpiBand>

        <div className="market-finance-workbench__body-grid">
          <section className="market-finance-workbench__matrix-panel">
            <div className="market-finance-workbench__panel-header">
              <div>
                <p>核心对照</p>
                <PanelHeading>市场信号 × 财务约束</PanelHeading>
              </div>
              <span>不制造一致、冲突或影响评分</span>
            </div>
            <div
              className="market-finance-workbench__table-wrap"
              role="region"
              aria-label="市场信号与财务约束对照表"
              tabIndex={0}
            >
              <table data-testid="market-finance-evidence-matrix">
                <thead>
                  <tr>
                    <th scope="col">观察维度</th>
                    <th scope="col">市场侧已有证据</th>
                    <th scope="col">财务侧已有约束</th>
                    <th scope="col">当前状态</th>
                    <th scope="col">下钻</th>
                  </tr>
                </thead>
                <tbody>
                  {matrixRows.map((row) => (
                    <tr key={row.dimension}>
                      <th scope="row">{row.dimension}</th>
                      <td>{row.market}</td>
                      <td>{row.finance}</td>
                      <td>
                        <span
                          className="market-finance-workbench__matrix-status"
                          data-tone={row.tone}
                        >
                          {row.state}
                        </span>
                      </td>
                      <td>
                        {row.to ? (
                          <Link to={row.to}>{row.action}</Link>
                        ) : (
                          <span>{row.action}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <aside className="market-finance-workbench__rail" aria-label="协同辅助信息">
            <section
              className="market-finance-workbench__rail-panel"
              data-testid="market-finance-decision-items"
            >
              <div className="market-finance-workbench__rail-panel-heading">
                <PanelHeading>待协调事项</PanelHeading>
                <span>
                  报告日{" "}
                  {decisionItemsQuery.data?.result.report_date ??
                    balanceDate ??
                    MISSING_VALUE}
                </span>
              </div>
              {decisionItemsAssessment.usable ? (
                <ol className="market-finance-workbench__coordination-list">
                  {pendingDecisionItems.map((item, index) => (
                    <li key={item.decision_key} data-severity={item.severity}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.reason}</p>
                        <Link to="/decision-items">{item.action_label}</Link>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <PageStateSurface
                  testId="market-finance-decision-items-state"
                  variant={
                    decisionItemsAssessment.tone === "loading"
                      ? "loading"
                      : decisionItemsAssessment.tone === "empty"
                        ? "empty"
                        : "error"
                  }
                  title={
                    decisionItemsAssessment.tone === "loading"
                      ? "正在读取待协调事项"
                      : decisionItemsQuery.isError
                        ? "待协调事项读取失败"
                        : decisionItemsAssessment.tone === "empty"
                          ? "暂无待协调事项"
                          : "待协调事项暂不可用"
                  }
                  description={
                    decisionItemsAssessment.tone === "loading"
                      ? "正在按资产负债报告日读取待处理事项。"
                      : decisionItemsQuery.isError
                        ? "其他市场与财务证据不受影响，可单独重试此处。"
                        : decisionItemsAssessment.tone === "empty"
                          ? "当前报告日没有状态为待处理的决策事项。"
                          : decisionItemsAssessment.label
                  }
                  actions={
                    decisionItemsQuery.isError ? (
                      <button
                        className="market-finance-workbench__retry-button"
                        type="button"
                        disabled={decisionItemsQuery.isFetching}
                        onClick={() => void decisionItemsQuery.refetch()}
                      >
                        {decisionItemsQuery.isFetching
                          ? "读取中"
                          : "重新读取待办"}
                      </button>
                    ) : undefined
                  }
                />
              )}
            </section>

            <section className="market-finance-workbench__rail-panel">
              <PanelHeading>数据状态</PanelHeading>
              <PageStateSurface
                testId="market-finance-state-surface"
                variant={stateVariant}
                title={statusTitle}
                description={statusDescription}
                actions={
                  hasQueryError || isRetrying ? (
                    <button
                      className="market-finance-workbench__retry-button"
                      type="button"
                      disabled={isRetrying}
                      onClick={retryFailedQueries}
                    >
                      {isRetrying ? "读取中" : "重新读取"}
                    </button>
                  ) : undefined
                }
              />
            </section>

            <section className="market-finance-workbench__rail-panel">
              <PanelHeading>快捷入口</PanelHeading>
              <nav className="market-finance-workbench__quick-links" aria-label="协同台快捷入口">
                <Link to="/market-data" aria-label="进入市场数据">
                  <span>市场证据</span>
                  <strong>进入市场数据</strong>
                </Link>
                <Link to="/product-category-pnl" aria-label="进入产品分类损益">
                  <span>FTP 与经营</span>
                  <strong>进入产品分类损益</strong>
                </Link>
                <Link to="/balance-analysis" aria-label="进入资产负债分析">
                  <span>ALM 与余额</span>
                  <strong>进入资产负债分析</strong>
                </Link>
                <Link to="/decision-items" aria-label="进入决策事项">
                  <span>协同闭环</span>
                  <strong>进入决策事项</strong>
                </Link>
              </nav>
            </section>
          </aside>
        </div>

        <EvidencePanel
          heading="证据与口径说明"
          className="market-finance-workbench__evidence"
          testId="market-finance-evidence"
        >
          <div className="market-finance-workbench__evidence-grid">
            <article title="/ui/market-data/rates">
              <h3>市场利率证据</h3>
              <p>
                {marketAssessment.usable
                  ? `查询返回 ${marketSeriesCount} 条序列；按页面配置白名单逐槽展示代表序列，未命中槽位显示“—”，状态为“待复核”。${MARKET_REPRESENTATIVE_BOUNDARY_NOTE}`
                  : `查询未返回可展示序列。${MARKET_REPRESENTATIVE_BOUNDARY_NOTE}`}
              </p>
              <span
                data-testid="market-finance-query-status-market-rates"
                data-tone={marketAssessment.tone}
              >
                {marketAssessment.label}
              </span>
              <span>{describeMeta(marketRatesQuery.data?.result_meta, isDemo)}</span>
              <p className="market-finance-workbench__date-evidence">
                {metaDateEvidence(marketRatesQuery.data?.result_meta)}
              </p>
              <code>/ui/market-data/rates</code>
            </article>
            <article title="/ui/pnl/product-category">
              <h3>FTP 与经营证据</h3>
              <p>
                {productPnl
                  ? `产品分类损益，经营报告日 ${productReportDate ?? MISSING_VALUE}`
                  : "查询未返回产品分类损益。"}
              </p>
              <div className="market-finance-workbench__query-evidence">
                <strong>日期目录</strong>
                <span
                  data-testid="market-finance-query-status-product-dates"
                  data-tone={productDatesAssessment.tone}
                >
                  {productDatesAssessment.label}
                </span>
                <span>
                  {describeMeta(
                    productDatesQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <p className="market-finance-workbench__date-evidence">
                  {metaDateEvidence(
                    productDatesQuery.data?.result_meta,
                  )}
                </p>
              </div>
              <div className="market-finance-workbench__query-evidence">
                <strong>损益读数</strong>
                <span
                  data-testid="market-finance-query-status-product-pnl"
                  data-tone={productPnlAssessment.tone}
                >
                  {productPnlAssessment.label}
                </span>
                <span>
                  {describeMeta(
                    productPnlQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <p className="market-finance-workbench__date-evidence">
                  {metaDateEvidence(
                    productPnlQuery.data?.result_meta,
                  )}
                </p>
              </div>
              <code>/ui/pnl/product-category</code>
            </article>
            <article title="/ui/balance-analysis/overview">
              <h3>资产负债证据</h3>
              <p>
                {balanceOverview
                  ? `全头寸 CNY 既有读面，报告日 ${balanceReportDate ?? MISSING_VALUE}`
                  : "查询未返回资产负债读面。"}
              </p>
              <div className="market-finance-workbench__query-evidence">
                <strong>日期目录</strong>
                <span
                  data-testid="market-finance-query-status-balance-dates"
                  data-tone={balanceDatesAssessment.tone}
                >
                  {balanceDatesAssessment.label}
                </span>
                <span>
                  {describeMeta(
                    balanceDatesQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <p className="market-finance-workbench__date-evidence">
                  {metaDateEvidence(
                    balanceDatesQuery.data?.result_meta,
                  )}
                </p>
              </div>
              <div className="market-finance-workbench__query-evidence">
                <strong>资产负债读数</strong>
                <span
                  data-testid="market-finance-query-status-balance-overview"
                  data-tone={balanceOverviewAssessment.tone}
                >
                  {balanceOverviewAssessment.label}
                </span>
                <span>
                  {describeMeta(
                    balanceOverviewQuery.data?.result_meta,
                    isDemo,
                  )}
                </span>
                <p className="market-finance-workbench__date-evidence">
                  {metaDateEvidence(
                    balanceOverviewQuery.data?.result_meta,
                  )}
                </p>
              </div>
              <code>/ui/balance-analysis/overview</code>
            </article>
            <article title="phase-one-boundary">
              <h3>第一阶段边界</h3>
              <p>不补算跨域传导、OCI、资本或 RWA，不生成综合评分与自动管理建议。</p>
              <span>缺少指标契约证据时统一显示待复核。</span>
            </article>
          </div>
        </EvidencePanel>
      </div>
    </PageV2Shell>
  );
}
