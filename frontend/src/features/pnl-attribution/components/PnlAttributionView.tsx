import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useApiClient } from "../../../api/client";
import { isAgentFrontendEnabled } from "../../../app/navigation";
import { FilterBar } from "../../../components/FilterBar";
import type { DataSectionState } from "../../../components/DataSection.types";
import type {
  AdvancedAttributionSummary,
  CampisiDecisionGradePayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  PnlCompositionPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  ResultMeta,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { PnLCompositionChart } from "./PnLCompositionChart";
import { TPLMarketChart, type ProductCategoryTplMonthlyPoint } from "./TPLMarketChart";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { AdvancedAttributionTabPanels } from "./PnlAttributionAdvancedTab";
import { ProductCategoryTabPanels } from "./PnlAttributionProductCategoryTab";
import {
  VolumeRateBridgePanel,
  VolumeRateTabCharts,
} from "./PnlAttributionVolumeRateTab";
import { cx } from "./pnlAttributionClassNames";
import {
  PnlAttributionErrorRegion,
  SectionLead,
} from "./pnlAttributionPrimitives";
import "./PnlAttributionView.css";
import {
  buildVolumeRateBridgeSummary,
  type AdvancedAttributionQualitySummary,
  type DualReportDateResolution,
  findProductCategoryReportDateForPeriod,
  formatGeneratedAtDisplay,
  formatGovernanceToken,
  formatMetaDateLabel,
  resolveDualReportDates,
  selectProductCategoryTplRow,
  summarizePnlAttributionError,
  summarizeAdvancedAttributionQuality,
  type PnlAttributionTab,
} from "./pnlAttributionViewModel";

const LazyPnlAttributionAgentDrawer = lazy(() =>
  import("./PnlAttributionAgentDrawer").then((module) => ({
    default: module.PnlAttributionAgentDrawer,
  })),
);

function tabButtonClassName(
  active: boolean,
  variant: "default" | "advanced" = "default",
) {
  return cx(
    "pnl-attribution-tab-button",
    active && "pnl-attribution-tab-button--active",
    variant === "advanced" && "pnl-attribution-tab-button--advanced",
  );
}

function LensBoundaryPanel() {
  return (
    <div className="pnl-attribution-section">
      <SectionLead title="口径边界" description="" />
      <div className="pnl-attribution-lens-grid">
        <section
          data-testid="pnl-attribution-product-category-lens-card"
          aria-label="产品分类经营归因口径边界"
          className="pnl-attribution-lens-card"
        >
          <SectionLead
            variant="card"
            eyebrow="产品分类经营口径"
            title="经营净收入归因"
            description="经营净收入、FTP 后；来源为产品分类正式读模型，只消费产品分类 monthly / YTD / attribution 接口。"
          />
          <div className="pnl-attribution-lens-status" data-testid="pnl-attribution-product-category-lens-status">
            证据状态：正式读模型已就绪；报告日由页面日期协调器校验。
          </div>
          <div className="pnl-attribution-lens-source">
            来源：/ui/pnl/product-category, /ui/pnl/product-category/attribution
          </div>
        </section>
        <section
          data-testid="pnl-attribution-formal-lens-card"
          aria-label="正式 FI 与债券分析归因口径边界"
          className="pnl-attribution-lens-card"
        >
          <SectionLead
            variant="card"
            eyebrow="正式 FI / 债券分析口径"
            title="会计损益与债券市场归因"
            description="含非标桥接、未扣 FTP、非产品分类经营净收入；仅用于正式 FI、TPL 市场和债券分析归因。"
          />
          <div className="pnl-attribution-lens-status" data-testid="pnl-attribution-formal-lens-status">
            证据状态：正式归因口径已就绪；TPL 市场例外在工作台中单独标注。
          </div>
          <div className="pnl-attribution-lens-source">来源：/api/pnl-attribution/*</div>
        </section>
      </div>
    </div>
  );
}

function PnlAttributionSourceDateMessage(props: {
  resolution: DualReportDateResolution | null;
  dateError: string | null;
  isLoading: boolean;
}) {
  if (props.isLoading) {
    return (
      <div
        data-testid="pnl-attribution-date-loading"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        正在加载产品分类与正式 FI 报告日...
      </div>
    );
  }
  if (props.dateError) {
    // 中文结论正文；原始错误（含接口路径）收进 title（§6 证据层）。
    const summary = summarizePnlAttributionError(props.dateError);
    return (
      <div
        data-testid="pnl-attribution-date-error"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
        title={summary?.detail}
      >
        报告日来源加载失败：{summary?.message ?? props.dateError}
      </div>
    );
  }
  if (!props.resolution) {
    return null;
  }
  if (!props.resolution.hasFormalDate || !props.resolution.hasProductCategoryDate) {
    const source =
      props.resolution.missingSource === "formal-attribution"
        ? "正式 FI / 债券分析"
        : props.resolution.missingSource === "product-category"
          ? "产品分类"
          : "产品分类和正式 FI / 债券分析";
    return (
      <div
        data-testid="pnl-attribution-source-date-warning"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        {source}来源当前无可用报告日；另一套口径仍可独立查看，不再强制共同日期。
      </div>
    );
  }
  if (!props.resolution.datesAligned) {
    return (
      <div
        data-testid="pnl-attribution-date-mismatch"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        两套口径报告日不一致：正式 FI / 债券分析{" "}
        {props.resolution.formalReportDate}；产品分类{" "}
        {props.resolution.productCategoryReportDate}。页面将分开取数，不做跨口径闭合。
      </div>
    );
  }
  return null;
}

function compactMetaValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function compactMetaStatus(value: ResultMeta["quality_flag"]) {
  if (value === "warning") {
    return {
      label: "预警",
      quality: "warning",
    };
  }
  if (value === "error" || value === "missing") {
    return {
      label: value === "missing" ? "缺失" : "错误",
      quality: value,
    };
  }
  if (value === "stale") {
    return {
      label: "陈旧",
      quality: "stale",
    };
  }
  return {
    label: "正常",
    quality: "normal",
  };
}

/**
 * 结果元信息条只保留证据层字段（口径/结果类型/日期/trace/规则版本）；
 * 质量与降级状态按 §6 去重只在归因决策条露出一次。
 */
function CurrentViewMetaStrip(props: {
  title: string;
  meta: ResultMeta;
  testId: string;
  isHomeCampisiModel: boolean;
}) {
  // 生成时间收敛为 YYYY-MM-DD HH:mm，微秒级 ISO 原值只进 title（§6 证据层）。
  const generatedAt = formatGeneratedAtDisplay(props.meta.generated_at);
  const fields: Array<{ label: string; text: string; title?: string }> = [
    {
      label: "口径",
      text:
        props.isHomeCampisiModel &&
        props.meta.basis === "formal" &&
        props.meta.formal_use_allowed === false
          ? "正式来源·模型归因"
          : props.meta.basis === "formal"
          ? "正式口径"
          : compactMetaValue(props.meta.basis),
    },
    { label: "结果类型", text: compactMetaValue(props.meta.result_kind) },
    { label: "数据截至日", text: compactMetaValue(props.meta.as_of_date) },
    { label: "生成时间", text: generatedAt.text, title: generatedAt.title },
    { label: "追踪编号", text: compactMetaValue(props.meta.trace_id) },
    { label: "规则版本", text: compactMetaValue(props.meta.rule_version) },
  ];

  return (
    <section
      data-testid={props.testId}
      className="pnl-attribution-meta-strip"
    >
      <div className="pnl-attribution-meta-strip__copy">
        <span className="pnl-attribution-meta-strip__eyebrow">
          当前视图结果元信息
        </span>
        <strong className="pnl-attribution-meta-strip__title">
          {props.title}
        </strong>
      </div>
      <div className="pnl-attribution-meta-strip__grid">
        {fields.map((field) => (
          <div
            key={field.label}
            className="pnl-attribution-meta-strip__field"
          >
            <span className="pnl-attribution-meta-strip__label">
              {field.label}
            </span>
            <span
              title={field.title || field.text}
              className="pnl-attribution-meta-strip__value"
            >
              {field.text}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function pnlAttributionLensSummary(activeTab: PnlAttributionTab) {
  if (activeTab === "product-category") {
    return {
      label: "产品分类经营归因",
      detail: "FTP 后经营净收入；只读取 /ui/pnl/product-category。",
      source: "/ui/pnl/product-category",
    };
  }
  if (activeTab === "tpl-market") {
    return {
      label: "TPL 混合口径例外",
      detail: "市场序列来自 /api/pnl-attribution/tpl-market；bond_tpl 月度行来自 /ui/pnl/product-category。",
      source: "/api/pnl-attribution/tpl-market + /ui/pnl/product-category",
    };
  }
  if (activeTab === "advanced") {
    return {
      label: "正式 FI / Campisi 归因",
      detail: "正式 FI、债券分析、Campisi 决策级解释；不等同产品分类经营净收入。",
      source: "/api/pnl-attribution/*",
    };
  }
  return {
    label: "正式 FI / 债券归因",
    detail: "正式 FI 归因视图；不跨口径闭合产品分类经营净收入。",
    source: "/api/pnl-attribution/*",
  };
}

function pnlAttributionLensId(activeTab: PnlAttributionTab) {
  if (activeTab === "product-category") {
    return "product_category_operating";
  }
  if (activeTab === "tpl-market") {
    return "tpl_mixed_exception";
  }
  if (activeTab === "advanced") {
    return "formal_fi_campisi";
  }
  return "formal_fi";
}

function formatDateResolutionSummary(
  resolution: DualReportDateResolution | null,
  activeTab: PnlAttributionTab,
) {
  if (!resolution) {
    return "报告日来源待确认";
  }
  const activeDate =
    activeTab === "product-category"
      ? resolution.productCategoryReportDate
      : resolution.formalReportDate;
  if (!resolution.hasFormalDate || !resolution.hasProductCategoryDate) {
    return `缺少来源；当前可用报告日 ${activeDate ?? EM_DASH}`;
  }
  if (!resolution.datesAligned) {
    return `日期分离：正式 FI ${resolution.formalReportDate ?? EM_DASH} / 产品分类 ${resolution.productCategoryReportDate ?? EM_DASH}`;
  }
  return `共同报告日 ${activeDate ?? EM_DASH}`;
}

function PnlAttributionDecisionStrip(props: {
  activeTab: PnlAttributionTab;
  compareType: "mom" | "yoy";
  isHomeCampisiMode: boolean;
  homeCampisiBasis?: CampisiFourEffectsPayload["basis"];
  homeCampisiClosure?: CampisiFourEffectsPayload["formal_closure"];
  currentViewDateTitle: string;
  currentViewMeta: ResultMeta | null;
  qualitySummary?: AdvancedAttributionQualitySummary;
  dateResolution: DualReportDateResolution | null;
  isLoading: boolean;
  hasError: boolean;
}) {
  const lens = props.isHomeCampisiMode
    ? props.homeCampisiBasis === "formal_report_pnl_bridge" ? {
        label: "正式桥四效应",
        detail: "首页指定月度区间的正式损益桥归因；会计记录纳入、市场效应覆盖和来源质量分别核对。",
        source: "/api/pnl-attribution/campisi/four-effects",
      } : {
        label: "持仓模型四效应",
        detail: "首页指定区间的 Campisi 持仓模型四效应；仅展示该区间的金额与输入覆盖，正式损益核对以本次响应为准。",
        source: "/api/pnl-attribution/campisi/four-effects",
      }
    : pnlAttributionLensSummary(props.activeTab);
  const qualityFlag = props.qualitySummary
    ? props.qualitySummary.qualityFlag
    : props.currentViewMeta?.quality_flag;
  const quality = qualityFlag
    ? compactMetaStatus(qualityFlag)
    : null;
  const qualityState = qualityFlag ?? "pending";
  const fallback = props.qualitySummary
    ? props.qualitySummary.fallbackLabel
    : props.currentViewMeta?.fallback_mode === "none"
      ? "未降级"
      : compactMetaValue(props.currentViewMeta?.fallback_mode);
  const dateSummary = formatDateResolutionSummary(
    props.dateResolution,
    props.activeTab,
  );
  const homeClosure = props.homeCampisiClosure;
  const homeClosureText = homeClosure?.status === "unavailable"
    ? "正式损益核对不可用"
    : homeClosure?.status === "warning"
      ? "正式损益核对有差异"
      : homeClosure?.status === "closed" &&
          homeClosure.formal_actual_pnl != null &&
          homeClosure.residual_to_formal_pnl != null
        ? "正式损益已核对"
        : "正式损益待核对";
  const action =
    props.hasError
      ? "先处理加载错误"
        : props.isLoading
          ? "等待当前视图加载"
        : props.isHomeCampisiMode
          ? "核对输入覆盖"
        : props.activeTab === "product-category"
          ? "先看经营归因闭合"
          : props.activeTab === "tpl-market"
            ? "核对混合口径来源"
            : props.activeTab === "advanced"
              ? "复核 Campisi 决策级"
              : "检查正式 FI 归因";
  // 治理字段正文中文化；candidate_or_pending 等原 token 为证据引用，只进 title（§6）。
  // 质量状态只在分区头徽标露出一次（§6 去重），不再重复成字段行。
  const fields: Array<{ label: string; text: string; title?: string }> = [
    { label: "页面状态", ...formatGovernanceToken("candidate_or_pending") },
    { label: "正式使用", ...formatGovernanceToken("formal_use_allowed=false") },
    { label: "业主批准", ...formatGovernanceToken("owner approval pending") },
    props.isHomeCampisiMode
      ? { label: "正式损益核对", text: homeClosureText }
      : { label: "口径闭合", ...formatGovernanceToken("closure_approved=false") },
    { label: "当前口径", text: lens.label },
    { label: "报告日", text: dateSummary },
    { label: "来源", text: lens.source },
    { label: "视图期间", text: props.currentViewDateTitle },
    { label: "降级", text: fallback },
    { label: "比较", text: props.isHomeCampisiMode ? "指定区间" : props.compareType === "mom" ? "环比" : "同比" },
    { label: "下一步", text: action },
  ];

  return (
    <section
      data-testid="pnl-attribution-decision-strip"
      className="pnl-attribution-decision-strip"
    >
      <div className="pnl-attribution-section-head pnl-attribution-decision-strip__head">
        <h2 className="pnl-attribution-section-head__title">归因决策条</h2>
        <span
          className="pnl-attribution-decision-strip__badge"
          data-quality={qualityState}
        >
          {quality?.label ?? "待加载"}
        </span>
      </div>
      <div className="pnl-attribution-decision-strip__body">
        <div className="pnl-attribution-decision-strip__copy">
          <strong className="pnl-attribution-decision-strip__title">
            {lens.label}
          </strong>
          <span className="pnl-attribution-decision-strip__detail">
            {lens.detail}
          </span>
        </div>
        <div className="pnl-attribution-decision-strip__grid">
          {fields.map((field) => (
            <div className="pnl-attribution-decision-strip__field" key={field.label}>
              <span className="pnl-attribution-decision-strip__label">
                {field.label}
              </span>
              <span
                className="pnl-attribution-decision-strip__value"
                title={field.title ?? field.text}
              >
                {field.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

type Props = {
  reportDate?: string;
  homeCampisiWindow?: { startDate: string; endDate: string };
  homeCampisiError?: string;
};

export function PnlAttributionView({ reportDate, homeCampisiWindow, homeCampisiError }: Props) {
  const client = useApiClient();
  const [activeTab, setActiveTab] = useState<PnlAttributionTab>(
    homeCampisiWindow || homeCampisiError ? "advanced" : "product-category",
  );
  const [compareType, setCompareType] = useState<"mom" | "yoy">("mom");
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [agentPanelMounted, setAgentPanelMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateLoading, setDateLoading] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);
  const [dateResolution, setDateResolution] =
    useState<DualReportDateResolution | null>(null);
  const [selectedFormalReportDate, setSelectedFormalReportDate] =
    useState<string | null>(reportDate ?? null);
  const [
    selectedProductCategoryReportDate,
    setSelectedProductCategoryReportDate,
  ] = useState<string | null>(reportDate ?? null);

  const [volumeRateData, setVolumeRateData] =
    useState<VolumeRateAttributionPayload | null>(null);
  const [tplMarketData, setTplMarketData] =
    useState<TPLMarketCorrelationPayload | null>(null);
  const [tplProductCategoryMonthlyPoints, setTplProductCategoryMonthlyPoints] =
    useState<ProductCategoryTplMonthlyPoint[]>([]);
  const [compositionData, setCompositionData] =
    useState<PnlCompositionPayload | null>(null);
  const [productCategoryMonthlyData, setProductCategoryMonthlyData] =
    useState<ProductCategoryPnlPayload | null>(null);
  const [productCategoryYtdData, setProductCategoryYtdData] =
    useState<ProductCategoryPnlPayload | null>(null);
  const [productCategoryAttributionData, setProductCategoryAttributionData] =
    useState<ProductCategoryAttributionPayload | null>(null);
  const [volumeRateMeta, setVolumeRateMeta] = useState<ResultMeta | null>(null);
  const [tplMarketMeta, setTplMarketMeta] = useState<ResultMeta | null>(null);
  const [compositionMeta, setCompositionMeta] = useState<ResultMeta | null>(
    null,
  );
  const [productCategoryMonthlyMeta, setProductCategoryMonthlyMeta] =
    useState<ResultMeta | null>(null);
  const [productCategoryYtdMeta, setProductCategoryYtdMeta] =
    useState<ResultMeta | null>(null);
  const [productCategoryAttributionMeta, setProductCategoryAttributionMeta] =
    useState<ResultMeta | null>(null);
  const [advancedSummaryMeta, setAdvancedSummaryMeta] =
    useState<ResultMeta | null>(null);

  const [carryRollDownData, setCarryRollDownData] =
    useState<CarryRollDownPayload | null>(null);
  const [spreadData, setSpreadData] = useState<SpreadAttributionPayload | null>(
    null,
  );
  const [krdData, setKrdData] = useState<KRDAttributionPayload | null>(null);
  const [advancedSummary, setAdvancedSummary] =
    useState<AdvancedAttributionSummary | null>(null);
  const [campisiFourEffects, setCampisiFourEffects] =
    useState<CampisiFourEffectsPayload | null>(null);
  const [campisiEnhanced, setCampisiEnhanced] =
    useState<CampisiEnhancedPayload | null>(null);
  const [campisiMaturityBuckets, setCampisiMaturityBuckets] =
    useState<CampisiMaturityBucketsPayload | null>(null);
  const [campisiDecisionGrade, setCampisiDecisionGrade] =
    useState<CampisiDecisionGradePayload | null>(null);
  const [campisiDecisionGradeError, setCampisiDecisionGradeError] =
    useState<string | null>(null);
  const [carryMeta, setCarryMeta] = useState<ResultMeta | null>(null);
  const [spreadMeta, setSpreadMeta] = useState<ResultMeta | null>(null);
  const [krdMeta, setKrdMeta] = useState<ResultMeta | null>(null);
  const [campisiFourMeta, setCampisiFourMeta] = useState<ResultMeta | null>(
    null,
  );
  const [campisiEnhancedMeta, setCampisiEnhancedMeta] =
    useState<ResultMeta | null>(null);
  const [campisiMaturityMeta, setCampisiMaturityMeta] =
    useState<ResultMeta | null>(null);
  const [campisiDecisionGradeMeta, setCampisiDecisionGradeMeta] =
    useState<ResultMeta | null>(null);

  const isProductCategoryTab = activeTab === "product-category";
  const effectiveReportDate = isProductCategoryTab
    ? (reportDate ?? selectedProductCategoryReportDate ?? undefined)
    : (reportDate ?? selectedFormalReportDate ?? undefined);
  const activeHomeCampisiWindow = activeTab === "advanced" &&
    homeCampisiWindow?.endDate === effectiveReportDate
    ? homeCampisiWindow
    : undefined;

  const openAgentPanel = useCallback(() => {
    setAgentPanelMounted(true);
    setAgentPanelOpen(true);
  }, []);

  const loadDateOptions = useCallback(async () => {
    setDateLoading(true);
    setDateError(null);
    try {
      const [businessDatesEnvelope, productCategoryDatesEnvelope] =
        await Promise.all([
          client.getFormalPnlDates(),
          client.getProductCategoryDates(),
        ]);
      const businessDates = businessDatesEnvelope.result.formal_fi_report_dates
        ?.length
        ? businessDatesEnvelope.result.formal_fi_report_dates
        : businessDatesEnvelope.result.report_dates;
      const resolution = resolveDualReportDates({
        businessDates,
        productCategoryDates: productCategoryDatesEnvelope.result.report_dates,
        preferredReportDate: reportDate,
      });
      setDateResolution(resolution);
      setSelectedFormalReportDate(reportDate ?? resolution.formalReportDate);
      setSelectedProductCategoryReportDate(reportDate ?? resolution.productCategoryReportDate);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "报告日来源加载失败";
      setDateError(msg);
      setSelectedFormalReportDate(reportDate ?? null);
      setSelectedProductCategoryReportDate(reportDate ?? null);
    } finally {
      setDateLoading(false);
    }
  }, [client, reportDate]);

  // 请求序号守卫：loadData 一次要写十余个 setState；快速切换页签 /
  // 环比同比 / 报告日时，只允许最新一次请求落地，防止先发后至的
  // 响应用旧口径覆盖正式归因数据。
  const loadDataRequestSeqRef = useRef(0);

  const loadData = useCallback(async () => {
    if (homeCampisiError) {
      setError(homeCampisiError);
      return;
    }
    if (!effectiveReportDate) {
      return;
    }
    const requestId = ++loadDataRequestSeqRef.current;
    const isStale = () => requestId !== loadDataRequestSeqRef.current;
    setLoading(true);
    setError(null);
    setCampisiDecisionGradeError(null);
    try {
      if (activeTab === "volume-rate") {
        const data = await client.getVolumeRateAttribution({
          reportDate: effectiveReportDate,
          compareType,
        });
        if (isStale()) return;
        setVolumeRateData(data.result);
        setVolumeRateMeta(data.result_meta);
      } else if (activeTab === "tpl-market") {
        const data = await client.getTplMarketCorrelation({
          months: 12,
          reportDate: effectiveReportDate,
        });
        if (isStale()) return;
        setTplMarketData(data.result);
        setTplMarketMeta(data.result_meta);
        const productCategoryDates = dateResolution?.productCategoryDates.length
          ? dateResolution.productCategoryDates
          : selectedProductCategoryReportDate
            ? [selectedProductCategoryReportDate]
            : [];
        const productCategoryTplPoints = await Promise.all(
          data.result.data_points.map(async (point): Promise<ProductCategoryTplMonthlyPoint> => {
            const productCategoryReportDate = findProductCategoryReportDateForPeriod(
              productCategoryDates,
              point.period,
            );
            if (!productCategoryReportDate) {
              return {
                period: point.period,
                reportDate: null,
                row: null,
              };
            }
            const monthly = await client.getProductCategoryPnl({
              reportDate: productCategoryReportDate,
              view: "monthly",
            });
            return {
              period: point.period,
              reportDate: monthly.result.report_date ?? productCategoryReportDate,
              row: selectProductCategoryTplRow(monthly.result),
            };
          }),
        );
        if (isStale()) return;
        setTplProductCategoryMonthlyPoints(productCategoryTplPoints);
      } else if (activeTab === "composition") {
        const data = await client.getPnlCompositionBreakdown({
          reportDate: effectiveReportDate,
          includeTrend: true,
          trendMonths: 6,
        });
        if (isStale()) return;
        setCompositionData(data.result);
        setCompositionMeta(data.result_meta);
      } else if (activeTab === "product-category") {
        const [monthly, ytd, attribution] = await Promise.all([
          client.getProductCategoryPnl({
            reportDate: effectiveReportDate,
            view: "monthly",
          }),
          client.getProductCategoryPnl({
            reportDate: effectiveReportDate,
            view: "ytd",
          }),
          client.getProductCategoryAttribution({
            reportDate: effectiveReportDate,
            compare: compareType,
          }),
        ]);
        if (isStale()) return;
        setProductCategoryMonthlyData(monthly.result);
        setProductCategoryMonthlyMeta(monthly.result_meta);
        setProductCategoryYtdData(ytd.result);
        setProductCategoryYtdMeta(ytd.result_meta);
        setProductCategoryAttributionData(attribution.result);
        setProductCategoryAttributionMeta(attribution.result_meta);
      } else if (activeHomeCampisiWindow) {
        const campisiFour = await client.getPnlCampisiFourEffects({
          startDate: activeHomeCampisiWindow.startDate,
          endDate: activeHomeCampisiWindow.endDate,
          lookbackDays: 30,
          detail: "full",
        });
        if (isStale()) return;
        const result = campisiFour.result;
        const formalCoverage = result.input_quality?.formal_bridge_coverage;
        const homeSourceVerified = result.basis === "formal_report_pnl_bridge"
          ? formalCoverage?.source === "pnl.bridge.rows" &&
            formalCoverage.basis === "formal_report_pnl_bridge"
          : Boolean(result.effect_availability?.position_change);
        if (
          result.period_start !== activeHomeCampisiWindow.startDate ||
          result.period_end !== activeHomeCampisiWindow.endDate ||
          result.report_date !== activeHomeCampisiWindow.endDate ||
          !homeSourceVerified
        ) {
          throw new Error("首页 Campisi 区间或归因来源未能核对，当前明细不可用。");
        }
        setCampisiFourEffects(result);
        setCampisiFourMeta(campisiFour.result_meta);
      } else {
        // The formal FI facts are monthly flows. Use the preceding month-end
        // snapshot instead of a fixed 30-day window (which misses 31-day months).
        const campisiBaseline = new Date(`${effectiveReportDate.slice(0, 7)}-01T00:00:00Z`);
        campisiBaseline.setUTCDate(0);
        const campisiStartDate = campisiBaseline.toISOString().slice(0, 10);
        const [
          carry,
          spread,
          krd,
          summary,
          campisiFour,
          campisiEnhancedData,
          campisiBuckets,
        ] = await Promise.all([
          client.getPnlCarryRollDown(effectiveReportDate),
          client.getPnlSpreadAttribution({
            reportDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlKrdAttribution({
            reportDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlAdvancedAttributionSummary(effectiveReportDate),
          client.getPnlCampisiFourEffects({
            startDate: campisiStartDate,
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlCampisiEnhanced({
            startDate: campisiStartDate,
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlCampisiMaturityBuckets({
            startDate: campisiStartDate,
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
        ]);
        if (isStale()) return;
        setCarryRollDownData(carry.result);
        setCarryMeta(carry.result_meta);
        setSpreadData(spread.result);
        setSpreadMeta(spread.result_meta);
        setKrdData(krd.result);
        setKrdMeta(krd.result_meta);
        setAdvancedSummary(summary.result);
        setAdvancedSummaryMeta(summary.result_meta);
        setCampisiFourEffects(campisiFour.result);
        setCampisiFourMeta(campisiFour.result_meta);
        setCampisiEnhanced(campisiEnhancedData.result);
        setCampisiEnhancedMeta(campisiEnhancedData.result_meta);
        setCampisiMaturityBuckets(campisiBuckets.result);
        setCampisiMaturityMeta(campisiBuckets.result_meta);
        setCampisiDecisionGrade(null);
        setCampisiDecisionGradeMeta(null);
        try {
          const campisiDecision = await client.getPnlCampisiDecisionGrade({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          });
          if (isStale()) return;
          setCampisiDecisionGrade(campisiDecision.result);
          setCampisiDecisionGradeMeta(campisiDecision.result_meta);
        } catch (decisionError: unknown) {
          if (isStale()) return;
          setCampisiDecisionGrade(null);
          setCampisiDecisionGradeMeta(null);
          setCampisiDecisionGradeError(
            decisionError instanceof Error
              ? decisionError.message
              : "Campisi 决策级解释加载失败",
          );
        }
      }
    } catch (e: unknown) {
      if (isStale()) return;
      const msg = e instanceof Error ? e.message : "加载失败";
      setError(msg);
    } finally {
      if (!isStale()) {
        setLoading(false);
      }
    }
  }, [
    activeTab,
    activeHomeCampisiWindow,
    client,
    compareType,
    dateResolution,
    effectiveReportDate,
    homeCampisiError,
    selectedProductCategoryReportDate,
  ]);

  useEffect(() => {
    void loadDateOptions();
  }, [loadDateOptions]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const keyFindings =
    activeTab === "advanced"
      ? (advancedSummary?.key_insights ?? [])
      : [];
  // 同一次 loadData 失败会打空整个页签：错误在区级收敛为一条横幅，
  // 不再逐面板重复（§6 去重；§11.3 同一状态文案 3 处以上为一票否决项）。
  // 报告日来源失败且没有可用报告日时 loadData 不会发起，面板既无 meta 也无 error，
  // 会停在「加载中」：把上游失败态显式落到当前视图，重试走报告日来源。
  const dateSourceBlocked = dateError !== null && !effectiveReportDate;
  const errorSummary = summarizePnlAttributionError(
    error ?? (dateSourceBlocked ? "报告日来源不可用，当前视图未发起取数；重试将先重新读取报告日。" : null),
  );
  const retryCurrentView = () => {
    void (dateSourceBlocked ? loadDateOptions() : loadData());
  };
  const volumeRateBridgeSummary = buildVolumeRateBridgeSummary(volumeRateData);
  const currentViewMeta =
    activeTab === "volume-rate"
      ? volumeRateMeta
      : activeTab === "tpl-market"
        ? tplMarketMeta
        : activeTab === "composition"
          ? compositionMeta
          : activeTab === "product-category"
            ? (productCategoryAttributionMeta ??
              productCategoryMonthlyMeta ??
              productCategoryYtdMeta)
            : (activeHomeCampisiWindow ? campisiFourMeta : advancedSummaryMeta);
  const advancedQualitySummary = activeTab === "advanced"
    ? summarizeAdvancedAttributionQuality(activeHomeCampisiWindow
      ? [campisiFourMeta]
      : [advancedSummaryMeta, carryMeta, spreadMeta, krdMeta,
        campisiFourMeta, campisiEnhancedMeta, campisiMaturityMeta, campisiDecisionGradeMeta])
    : undefined;
  const currentViewDate = formatMetaDateLabel(activeTab, {
    volumeRateData,
    tplMarketData,
    compositionData,
    advancedSummary,
    productCategoryAttributionData,
    productCategoryMonthlyData,
    productCategoryYtdData,
  });
  const currentViewMetaTitle = activeHomeCampisiWindow
    ? `Campisi 四效应区间：${campisiFourEffects?.period_start ?? activeHomeCampisiWindow.startDate} 至 ${campisiFourEffects?.period_end ?? activeHomeCampisiWindow.endDate}`
    : `${currentViewDate.label}：${currentViewDate.value}`;
  const homeCampisiState: DataSectionState = derivePnlDataSectionState({
    meta: campisiFourMeta,
    isLoading: loading,
    isError: error !== null,
    errorMessage: error,
    isEmpty: !campisiFourEffects,
  });
  const agentPanelFilters = useMemo(
    () => ({
      active_tab: activeTab,
      compare_type: compareType,
      attribution_lens: pnlAttributionLensId(activeTab),
      formal_report_date: selectedFormalReportDate,
      product_category_report_date: selectedProductCategoryReportDate,
      dates_aligned: dateResolution?.datesAligned ?? null,
      result_basis: currentViewMeta?.basis ?? null,
      source_formal_use_allowed: currentViewMeta?.formal_use_allowed ?? null,
      formal_use_allowed: false,
    }),
    [
      activeTab,
      compareType,
      currentViewMeta?.basis,
      currentViewMeta?.formal_use_allowed,
      dateResolution?.datesAligned,
      selectedFormalReportDate,
      selectedProductCategoryReportDate,
    ],
  );

  const tplMarketState: DataSectionState = derivePnlDataSectionState({
    meta: tplMarketMeta,
    isLoading: loading && activeTab === "tpl-market",
    isError: error !== null && activeTab === "tpl-market",
    errorMessage: error,
    isEmpty: !tplMarketData || (tplMarketData.data_points?.length ?? 0) === 0,
  });

  const compositionState: DataSectionState = derivePnlDataSectionState({
    meta: compositionMeta,
    isLoading: loading && activeTab === "composition",
    isError: error !== null && activeTab === "composition",
    errorMessage: error,
    isEmpty: !compositionData,
  });

  return (
    <div className="pnl-attribution-shell">
      <div className="pnl-attribution-page-header">
        <div className="pnl-attribution-page-header__inner">
          <div className="pnl-attribution-page-header__copy">
            <h1
              data-testid="pnl-attribution-page-title"
              className="pnl-attribution-page-header__title"
            >
              损益归因分析
            </h1>
            <p className="pnl-attribution-page-header__description">
              本页保留产品分类经营口径与正式 FI / 债券分析口径；两套数据分开取数、
              分开元信息，不再跨口径汇总或闭合。
            </p>
          </div>
          <div className="pnl-attribution-page-header__actions">
            <span
              className="pnl-attribution-mode-badge"
              data-mode={client.mode}
            >
              {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
            </span>
            {isAgentFrontendEnabled() ? (
              <button
                type="button"
                data-testid="pnl-attribution-agent-open"
                onClick={openAgentPanel}
                aria-label="打开损益复核助手"
                className="pnl-attribution-tab-button"
              >
                损益复核
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading || dateLoading}
              className="pnl-attribution-tab-button"
            >
              {loading ? "刷新中…" : "刷新"}
            </button>
          </div>
        </div>

        {keyFindings.length > 0 && (
          <div
            className="pnl-attribution-findings"
            data-context={activeTab === "advanced" ? "advanced" : "default"}
          >
            <div className="pnl-attribution-findings__title">
              {activeTab === "advanced" ? "高级归因要点" : "关键发现"}
            </div>
            <ul className="pnl-attribution-findings__list">
              {keyFindings.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <PnlAttributionDecisionStrip
        activeTab={activeTab}
        compareType={compareType}
        isHomeCampisiMode={activeHomeCampisiWindow !== undefined}
        homeCampisiBasis={campisiFourEffects?.basis}
        homeCampisiClosure={campisiFourEffects?.formal_closure}
        currentViewDateTitle={currentViewMetaTitle}
        currentViewMeta={currentViewMeta}
        qualitySummary={advancedQualitySummary}
        dateResolution={dateResolution}
        isLoading={loading || dateLoading}
        hasError={error !== null || dateError !== null}
      />

      <LensBoundaryPanel />

      <PnlAttributionSourceDateMessage
        resolution={dateResolution}
        dateError={dateError}
        isLoading={dateLoading}
      />

      <div className="pnl-attribution-section">
        <SectionLead
          title="双口径归因工作台"
          description="产品分类经营归因只读取 /ui/pnl/product-category；正式 FI / 债券分析主要读取 /api/pnl-attribution/*。TPL 市场页签是明确的混合口径例外：/api/pnl-attribution/tpl-market 提供市场序列，/ui/pnl/product-category 提供 bond_tpl 月度行。"
          testId="pnl-attribution-workbench-lead"
        />
        <FilterBar className="pnl-attribution-tab-row">
          <button
            type="button"
            className={tabButtonClassName(activeTab === "volume-rate")}
            onClick={() => setActiveTab("volume-rate")}
          >
            规模 / 利率效应
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "tpl-market")}
            onClick={() => setActiveTab("tpl-market")}
          >
            TPL 市场相关性
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "composition")}
            onClick={() => setActiveTab("composition")}
          >
            损益构成
          </button>
          <button
            data-testid="pnl-attribution-tab-product-category"
            type="button"
            className={tabButtonClassName(activeTab === "product-category")}
            onClick={() => setActiveTab("product-category")}
          >
            产品分类归因
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "advanced", "advanced")}
            onClick={() => setActiveTab("advanced")}
          >
            高级归因 + Campisi
          </button>
          {(activeTab === "volume-rate" ||
            activeTab === "product-category") && (
            <div className="pnl-attribution-tab-row__compare-group">
              <button
                type="button"
                className={tabButtonClassName(compareType === "mom")}
                onClick={() => setCompareType("mom")}
              >
                环比
              </button>
              <button
                type="button"
                className={tabButtonClassName(compareType === "yoy")}
                onClick={() => setCompareType("yoy")}
              >
                同比
              </button>
            </div>
          )}
        </FilterBar>
      </div>

      <SectionLead
        title="当前归因视图"
        description="下方内容随页签切换；请按当前口径阅读来源、单位、报告日和质量提示。"
        testId="pnl-attribution-current-view-lead"
      />

      {activeTab === "volume-rate" &&
      volumeRateData &&
      volumeRateBridgeSummary &&
      !loading &&
      !error ? (
        <VolumeRateBridgePanel
          data={volumeRateData}
          summary={volumeRateBridgeSummary}
        />
      ) : null}

      {currentViewMeta ? (
        <CurrentViewMetaStrip
          testId="pnl-attribution-current-view-meta"
          title={currentViewMetaTitle}
          meta={currentViewMeta}
          isHomeCampisiModel={activeHomeCampisiWindow !== undefined}
        />
      ) : null}

      {errorSummary ? (
        /* 错误态区级收敛：一条中文横幅 + 面板收缩，错误正文全页只出现一次（§6）。 */
        <PnlAttributionErrorRegion
          activeTab={activeTab}
          summary={errorSummary}
          onRetry={retryCurrentView}
        />
      ) : (
        <>
          {activeTab === "advanced" ? (
            activeHomeCampisiWindow ? (
              <>
                <div data-testid="pnl-attribution-home-campisi-window" className="pnl-attribution-section">
                  首页同区间四效应明细：{campisiFourEffects?.period_start ?? activeHomeCampisiWindow.startDate} 至 {campisiFourEffects?.period_end ?? activeHomeCampisiWindow.endDate}。
                  {campisiFourEffects ? campisiFourEffects.basis === "formal_report_pnl_bridge"
                    ? "当前为正式损益桥归因；" : "当前为持仓模型归因；"
                    : "正在核对归因来源；"}
                  本入口只展示该区间的 Campisi 四效应；其他高级归因沿用各自月度口径，未在此套用。
                </div>
                <CampisiAttributionPanel
                  data={campisiFourEffects}
                  state={homeCampisiState}
                  onRetry={() => void loadData()}
                />
              </>
            ) : <AdvancedAttributionTabPanels
              carryData={carryRollDownData}
              spreadData={spreadData}
              krdData={krdData}
              summaryData={advancedSummary}
              campisiData={null}
              campisiFourEffects={campisiFourEffects}
              campisiEnhanced={campisiEnhanced}
              campisiMaturityBuckets={campisiMaturityBuckets}
              campisiDecisionGrade={campisiDecisionGrade}
              carryMeta={carryMeta}
              spreadMeta={spreadMeta}
              krdMeta={krdMeta}
              summaryMeta={advancedSummaryMeta}
              campisiFourMeta={campisiFourMeta}
              campisiEnhancedMeta={campisiEnhancedMeta}
              campisiMaturityMeta={campisiMaturityMeta}
              campisiDecisionGradeMeta={campisiDecisionGradeMeta}
              isLoading={loading}
              errorMessage={error}
              decisionGradeErrorMessage={campisiDecisionGradeError}
              onRetry={() => void loadData()}
            />
          ) : null}

          {activeTab === "product-category" ? (
            <ProductCategoryTabPanels
              monthlyData={productCategoryMonthlyData}
              ytdData={productCategoryYtdData}
              attributionData={productCategoryAttributionData}
              monthlyMeta={productCategoryMonthlyMeta}
              ytdMeta={productCategoryYtdMeta}
              attributionMeta={productCategoryAttributionMeta}
              isLoading={loading}
              errorMessage={error}
              onRetry={() => void loadData()}
            />
          ) : null}

          {activeTab === "volume-rate" ? (
            <VolumeRateTabCharts
              data={volumeRateData}
              meta={volumeRateMeta}
              isLoading={loading}
              errorMessage={error}
              onRetry={() => void loadData()}
            />
          ) : null}

          {activeTab === "tpl-market" ? (
            <TPLMarketChart
              data={tplMarketData}
              state={tplMarketState}
              onRetry={() => void loadData()}
              productCategoryTplMonthlyPoints={tplProductCategoryMonthlyPoints}
            />
          ) : null}

          {activeTab === "composition" ? (
            <PnLCompositionChart
              data={compositionData}
              state={compositionState}
              onRetry={() => void loadData()}
            />
          ) : null}
        </>
      )}

      {agentPanelMounted ? (
        <Suspense fallback={null}>
          <LazyPnlAttributionAgentDrawer
            open={agentPanelOpen}
            reportDate={effectiveReportDate ?? null}
            currentFilters={agentPanelFilters}
            onClose={() => setAgentPanelOpen(false)}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
