import { useMemo, type CSSProperties, type ReactNode } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Alert, Button, Card } from "antd";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import type {
  ApiEnvelope,
  AssetStructureItem,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
  BondTopHoldingItem,
  ChoiceMacroLatestPoint,
  DV01RiskPayload,
  Numeric,
  YieldCurveTermStructureCurvePayload,
} from "../../../api/contracts";
import { bondNumericRaw, bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";
import {
  buildKpiValuePair,
  computeRelativeChangePct,
  toBp,
} from "../lib/bondAnalyticsHomeCalculations";
import type {
  BondAnalyticsActiveModuleContext,
  BondAnalyticsReadinessItem,
} from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { BondAnalyticsDecisionRail } from "./BondAnalyticsDecisionRail";
import type { ActionAttributionResponse } from "../types";
import { designTokens, ibTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  BOND_ANALYTICS_MACRO_BAR_SERIES,
  buildMacroPointForDeltaDisplay,
  coalesceMacroSeriesDelta,
} from "../lib/bondAnalyticsMacroSeries";
import { formatBp, formatPct, formatWan, formatYi } from "../utils/formatters";
import { buildYieldCurveTermStructureChartOption } from "../lib/yieldCurveTermStructureChartOption";
import ReactECharts from "../../../lib/echarts";
import {
  BOND_HOLDINGS_COCKPIT_SCOPE_NOTE,
  BOND_HOLDINGS_EMPTY_NOTE,
} from "../lib/bondHoldingsEvidenceCopy";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { panelStyle } from "./bondAnalyticsCockpitTokens";
import {
  InstitutionalKpiRail,
  InstitutionalKpiTile,
} from "../../workbench/shared/InstitutionalKpiTile";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const dt = designTokens;
const IB_ACCENT_BAR = "var(--ib-accent)";
const DONUT_CHART_COLORS = mossChartCategoricalPalette.slice(0, 5);
const DISTRIBUTION_CHART_COLORS = [...DONUT_CHART_COLORS, ibTokens.color.gold];
const deskPanelShadow = "0 2px 6px rgba(22, 35, 46, 0.035)";
const dashboardCardStyle: CSSProperties = {
  ...panelStyle(displayTokens.surface.section),
  border: `1px solid ${dt.color.neutral[200]}`,
  borderRadius: dt.radius.sm,
  boxShadow: deskPanelShadow,
};
const cardBodyStyle = { padding: 14 } as const;

const PORTFOLIO_HEADLINES_STRUCTURE_NOTE = "组合信用摘要暂未返回，资产结构稍后补齐。";
const PORTFOLIO_HEADLINES_CREDIT_NOTE = "组合信用摘要暂未返回，债券只数、集中度和 DV01 稍后补齐。";
const TOP_HOLDINGS_CARD_TITLE = "前十大返回持仓";
const TOP_HOLDINGS_MOBILE_LABEL = "前十大持仓";
const TOP_HOLDINGS_COUNT_LABEL = "返回持仓";
const TOP_HOLDINGS_HOME_NOTE = "前十大持仓暂未返回，首页先保留组合规模与浮盈快照。";
const TOP_HOLDINGS_RATING_NOTE = "持仓明细暂未返回，评级分布稍后补齐。";
const BOND_ANALYTICS_CURRENCY_BASIS_TEXT =
  "金额指标按人民币/CNY口径展示，外币债券市值、摊余成本、应计利息等已折算为人民币。";
const DV01_HOME_TOP_N = 1;
const DV01_HOME_SHOCK_BPS = "1";
const DV01_ACCOUNTING_CLASSES = [
  { label: "AC", value: "AC" },
  { label: "OCI", value: "OCI" },
  { label: "TPL", value: "TPL" },
  { label: "全部", value: "all" },
] as const;
const HOME_YIELD_CURVE_TYPES = "treasury,cdb";
const HOME_CURVE_LABELS: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};
const COCKPIT_BUNDLE_INDUSTRY_TOP_N = 10;
const COCKPIT_BUNDLE_ANALYTICS_TOP_N = 10;
const COCKPIT_BUNDLE_SECTIONS = [
  "headline-kpis",
  "maturity-structure",
  "top-holdings",
  "portfolio-headlines",
  "asset-structure",
  "risk-indicators",
  "industry-distribution",
  "dv01-risk-ac",
  "dv01-risk-oci",
  "dv01-risk-tpl",
  "dv01-risk-all",
  "yield-curve-term-structure",
] as const satisfies readonly BondDashboardBundleSectionId[];

type Dv01AccountingClassValue = (typeof DV01_ACCOUNTING_CLASSES)[number]["value"];
const DV01_BUNDLE_SECTION_BY_ACCOUNTING_CLASS = {
  AC: "dv01-risk-ac",
  OCI: "dv01-risk-oci",
  TPL: "dv01-risk-tpl",
  all: "dv01-risk-all",
} as const satisfies Record<Dv01AccountingClassValue, BondDashboardBundleSectionId>;

type BundleSectionQuery<TSection extends BondDashboardBundleSectionId> = {
  data: BondDashboardBundleSectionEnvelopeMap[TSection] | undefined;
  error: Error | null;
  isError: boolean;
  isPending: boolean;
  isLoading: boolean;
};

function bundleSectionQuery<TSection extends BondDashboardBundleSectionId>(
  bundleQ: UseQueryResult<ApiEnvelope<BondDashboardBundlePayload>, Error>,
  section: TSection,
): BundleSectionQuery<TSection> {
  const status = bundleQ.data?.result.section_statuses?.[section];
  const sectionFailed = status?.status === "error";
  const data = bundleQ.data?.result.sections[section] as
    | BondDashboardBundleSectionEnvelopeMap[TSection]
    | undefined;
  return {
    data: sectionFailed ? undefined : data,
    error: sectionFailed
      ? new Error(status?.message ?? `${section} section failed`)
      : bundleQ.error ?? null,
    isError: bundleQ.isError || sectionFailed,
    isPending: bundleQ.isPending,
    isLoading: bundleQ.isLoading,
  };
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return n === null ? Number.NaN : n;
}

function numOrNullAware(raw: Numeric | null | undefined): number {
  const n = bondNumericRawOrNull(raw);
  return n === null ? Number.NaN : n;
}

function formatNumericString(raw: string | number | null | undefined) {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(raw);
  }
  return parsed.toLocaleString("zh-CN");
}

function formatNumericDisplay(value: Numeric | null | undefined): string {
  return value?.display || "—";
}

function formatTextEvidenceDisplay(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "—";
}

function formatDurationDisplay(value: Numeric | null | undefined): string {
  const display = formatNumericDisplay(value);
  return display === "—" ? display : `${display} 年`;
}

function formatMoneyDisplay(value: Numeric | null | undefined): string {
  if (value == null) {
    return "—";
  }
  return formatYi(value);
}

function formatMoneyEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? "—" : formatYi(value);
}

function formatNumericEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? "—" : formatNumericDisplay(value);
}

function formatPctEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? "—" : formatPct(value);
}

function formatWanEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? "—" : formatWan(value);
}

function formatSignedPct(pct: number | null): string {
  if (!isFiniteNumber(pct)) {
    return "—";
  }
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatCurveNumeric(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? "—" : value?.display || "—";
}

function curvePointHasReadout(point: YieldCurveTermStructureCurvePayload["points"][number]) {
  return bondNumericRawOrNull(point.yield_pct) !== null || bondNumericRawOrNull(point.delta_bp_prev) !== null;
}

function curveHasReadout(curve: YieldCurveTermStructureCurvePayload) {
  return curve.points.some(curvePointHasReadout);
}

function tenorSortValue(tenor: string) {
  const match = tenor.trim().match(/^(\d+(?:\.\d+)?)([DWMY])$/i);
  if (!match) {
    return Number.POSITIVE_INFINITY;
  }
  const amount = Number.parseFloat(match[1]);
  const unit = match[2].toUpperCase();
  if (!Number.isFinite(amount)) {
    return Number.POSITIVE_INFINITY;
  }
  switch (unit) {
    case "D":
      return amount;
    case "W":
      return amount * 7;
    case "M":
      return amount * 30;
    case "Y":
      return amount * 365;
    default:
      return Number.POSITIVE_INFINITY;
  }
}

function sortCurvePoints(points: YieldCurveTermStructureCurvePayload["points"]) {
  return [...points]
    .filter(curvePointHasReadout)
    .sort((left, right) => {
      const leftValue = tenorSortValue(left.tenor);
      const rightValue = tenorSortValue(right.tenor);
      if (leftValue !== rightValue) {
        return leftValue - rightValue;
      }
      return left.tenor.localeCompare(right.tenor, "zh-CN");
    });
}

function pickLargestCurveDeltaPoint(points: YieldCurveTermStructureCurvePayload["points"]) {
  return [...points]
    .filter((point) => bondNumericRawOrNull(point.delta_bp_prev) !== null)
    .sort((left, right) => {
      const deltaGap =
        Math.abs(bondNumericRawOrNull(right.delta_bp_prev) ?? 0) -
        Math.abs(bondNumericRawOrNull(left.delta_bp_prev) ?? 0);
      if (deltaGap !== 0) {
        return deltaGap;
      }
      return tenorSortValue(left.tenor) - tenorSortValue(right.tenor);
    })[0] ?? null;
}

function pickLargestCurveDeltaReadout(curves: YieldCurveTermStructureCurvePayload[]) {
  return curves
    .map((curve) => ({
      curve,
      point: pickLargestCurveDeltaPoint(curve.points),
    }))
    .filter((item): item is {
      curve: YieldCurveTermStructureCurvePayload;
      point: YieldCurveTermStructureCurvePayload["points"][number];
    } => item.point !== null)
    .sort((left, right) => {
      const deltaGap =
        Math.abs(bondNumericRawOrNull(right.point.delta_bp_prev) ?? 0) -
        Math.abs(bondNumericRawOrNull(left.point.delta_bp_prev) ?? 0);
      if (deltaGap !== 0) {
        return deltaGap;
      }
      const curveGap = curveLabel(left.curve.curve_type).localeCompare(
        curveLabel(right.curve.curve_type),
        "zh-CN",
      );
      if (curveGap !== 0) {
        return curveGap;
      }
      return tenorSortValue(left.point.tenor) - tenorSortValue(right.point.tenor);
    })[0] ?? null;
}

function curveDeltaTone(value: Numeric | null | undefined): "up" | "down" | "flat" {
  const raw = bondNumericRawOrNull(value);
  if (raw === null || raw === 0) {
    return "flat";
  }
  return raw > 0 ? "up" : "down";
}

function curveLabel(curveType: string): string {
  return HOME_CURVE_LABELS[curveType] ?? curveType;
}

function buildCurveComparisonTenors(curves: YieldCurveTermStructureCurvePayload[]) {
  return Array.from(
    new Set(
      curves.flatMap((curve) => sortCurvePoints(curve.points).map((point) => point.tenor)),
    ),
  )
    .sort((left, right) => {
      const leftValue = tenorSortValue(left);
      const rightValue = tenorSortValue(right);
      if (leftValue !== rightValue) {
        return leftValue - rightValue;
      }
      return left.localeCompare(right, "zh-CN");
    })
    .slice(0, 8);
}

function curvePointByTenor(
  curve: YieldCurveTermStructureCurvePayload,
  tenor: string,
) {
  return sortCurvePoints(curve.points).find((point) => point.tenor === tenor) ?? null;
}

function normalizeSpreadBp(spreadMedian: Numeric | null | undefined): number {
  return toBp(spreadMedian) ?? Number.NaN;
}

function formatSpreadBpDisplay(spreadMedian: Numeric | null | undefined): string {
  const spreadBp = toBp(spreadMedian);
  return spreadBp === null ? "—" : formatBp(spreadBp);
}

function buildReadoutFacts(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const { duration, creditWeight, spreadMedianBp } = args;
  const facts: string[] = [];

  if (Number.isFinite(duration)) {
    facts.push(`久期 ${duration.toFixed(2)} 年`);
  }
  if (Number.isFinite(spreadMedianBp)) {
    facts.push(`信用利差 ${spreadMedianBp.toFixed(1)} bp`);
  }
  if (Number.isFinite(creditWeight)) {
    facts.push(`信用占比 ${(creditWeight * 100).toFixed(1)}%`);
  }

  return facts;
}

function buildMissingReadoutLabels(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const missing: string[] = [];

  if (!Number.isFinite(args.duration)) {
    missing.push("久期");
  }
  if (!Number.isFinite(args.spreadMedianBp)) {
    missing.push("信用利差");
  }
  if (!Number.isFinite(args.creditWeight)) {
    missing.push("信用占比");
  }

  return missing;
}

function buildCockpitConclusion(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const facts = buildReadoutFacts(args);
  const missingReadouts = buildMissingReadoutLabels(args);

  if (facts.length === 0) {
    return {
      title: "读面待确认",
      body: "核心债券读面仍在返回。",
      detail: "等待久期、信用利差或组合信用摘要返回后更新首屏读面。",
    };
  }

  if (missingReadouts.length > 0) {
    return {
      title: "部分读面",
      body: "部分核心债券读面已返回。",
      detail: `${facts.join(" · ")}；待返回 ${missingReadouts.join(" / ")}。`,
    };
  }

  return {
    title: "核心读面",
    body: "久期、信用利差与信用占比读面已返回。",
    detail: facts.join(" · "),
  };
}

function buildDeskVerdictFields(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
  dv01Display: string;
  reportDate: string;
  dashboardReportDate: string;
  isDashboardDateFallback: boolean;
  headlinePending: boolean;
  hasHeadline: boolean;
  hasCurveReadout: boolean;
  curvePending: boolean;
}) {
  const {
    duration,
    creditWeight,
    spreadMedianBp,
    dv01Display,
    reportDate,
    dashboardReportDate,
    isDashboardDateFallback,
    headlinePending,
    hasHeadline,
    hasCurveReadout,
    curvePending,
  } = args;
  const displayDate = dashboardReportDate || "—";
  const requestedDate = reportDate || "—";

  if (isDashboardDateFallback) {
    return [
      {
        label: "核心读面",
        value: "目标日快照缺口",
        detail: `请求 ${requestedDate}，展示 ${displayDate} 历史快照。`,
      },
      {
        label: "数据边界",
        value: "目标报告日读面",
        detail: "待读面补齐后再更新当前报告日首屏。",
      },
      {
        label: "报告日状态",
        value: `快照回退 ${displayDate}`,
        detail: headlinePending ? "headline KPI 加载中。" : "仅作历史快照参考。",
      },
      {
        label: "下钻入口",
        value: "等待目标日快照",
        detail: "回退快照不形成当前结论。",
      },
    ];
  }

  const readoutFacts = buildReadoutFacts({ duration, creditWeight, spreadMedianBp });
  const readoutField = readoutFacts.length > 0
    ? {
        value: readoutFacts.join(" / "),
        detail: "仅展示已返回读面。",
      }
    : {
        value: "久期 / 利差 / 信用占比待返回",
        detail: "核心债券读面仍在返回。",
      };

  const boundaryField = !hasCurveReadout
    ? {
        value: curvePending ? "正式曲线加载中" : "正式曲线待返回",
        detail: curvePending ? "期限点加载中。" : "正式曲线待读面。",
      }
    : {
        value: "正式曲线已返回",
        detail: "期限点收益率与日变动可读。",
      };

  return [
    {
      label: "核心读面",
      value: readoutField.value,
      detail: readoutField.detail,
    },
    {
      label: "数据边界",
      value: boundaryField.value,
      detail: boundaryField.detail,
    },
    {
      label: "报告日状态",
      value: headlinePending ? "headline 加载中" : hasHeadline ? "报告日匹配" : "等 headline",
      detail: `报告日 ${displayDate}。`,
    },
    {
      label: "下钻入口",
      value: hasCurveReadout ? "打开正式下钻" : "正式下钻待返回",
      detail: hasCurveReadout ? `组合 DV01 ${dv01Display}。` : "先展示已返回读面，不补造下钻结论。",
    },
  ];
}

function SectionCardTitle({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className={styles.sectionCardTitle}>
      <div className={styles.sectionCardTitleEyebrow}>{eyebrow}</div>
      <div className={styles.sectionCardTitleText}>{title}</div>
    </div>
  );
}

type AccountingDv01SummaryRow = {
  label: string;
  value: string;
  payload: DV01RiskPayload | null;
};

function MobileReadoutField({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: ReactNode;
}) {
  return (
    <div className={styles.mobileReadoutField}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function pickLargestDv01Row(rows: AccountingDv01SummaryRow[]) {
  let largest: AccountingDv01SummaryRow | null = null;
  let largestDv01 = Number.NEGATIVE_INFINITY;

  for (const row of rows) {
    const dv01 = bondNumericRaw(row.payload?.total_dv01);
    const rawDv01 = dv01 === null ? Number.NaN : Math.abs(dv01);
    if (Number.isFinite(rawDv01) && rawDv01 > largestDv01) {
      largest = row;
      largestDv01 = rawDv01;
    }
  }

  return largest;
}

function AccountingDv01MobileReadout({
  rows,
  isLoading,
  hasError,
}: {
  rows: AccountingDv01SummaryRow[];
  isLoading: boolean;
  hasError: boolean;
}) {
  const largestRow = pickLargestDv01Row(rows);
  const stateLabel = hasError ? "读面暂未返回" : isLoading ? "读取中" : "移动摘要";
  const largestDv01Display = largestRow
    ? formatWanEvidenceDisplay(largestRow.payload?.total_dv01)
    : hasError
      ? "读面暂未返回"
      : isLoading
        ? "读取中"
        : "暂无可用分类";

  return (
    <div
      data-testid="bond-analysis-accounting-dv01-mobile-readout"
      className={styles.mobileTableReadout}
    >
      <div className={styles.mobileReadoutHeader}>
        <span>会计分类 DV01</span>
        <strong>{stateLabel}</strong>
      </div>
      <div className={styles.mobileReadoutGrid}>
        <MobileReadoutField
          label="最高 DV01 分类"
          value={largestRow?.label ?? "—"}
          detail={largestDv01Display}
        />
        <MobileReadoutField
          label="面值加权久期"
          value={formatDurationDisplay(largestRow?.payload?.face_weighted_modified_duration)}
        />
        <MobileReadoutField
          label="DV01"
          value={largestDv01Display}
        />
        <MobileReadoutField
          label="面值"
          value={formatMoneyDisplay(largestRow?.payload?.total_face_value)}
        />
        <MobileReadoutField
          label="持仓数"
          value={largestRow?.payload ? formatNumericString(largestRow.payload.position_count) : "—"}
        />
      </div>
    </div>
  );
}

function AccountingDv01SummaryPanel({
  rows,
  isLoading,
  hasError,
  onOpenModuleDetail,
}: {
  rows: AccountingDv01SummaryRow[];
  isLoading: boolean;
  hasError: boolean;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}) {
  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="分类风险" title="会计分类 DV01" />}
      extra={
        <Button
          size="small"
          type="text"
          data-testid="bond-analysis-home-open-dv01-risk"
          onClick={() => onOpenModuleDetail?.("dv01-risk")}
        >
          打开 DV01 风险
        </Button>
      }
      data-testid="bond-analysis-accounting-dv01-summary"
      className={styles.accountingDv01Card}
      style={dashboardCardStyle}
      styles={{ body: { padding: 0 } }}
    >
      <AccountingDv01MobileReadout rows={rows} isLoading={isLoading} hasError={hasError} />
      <div
        data-testid="bond-analysis-accounting-dv01-raw-grid"
        className={styles.accountingDv01Grid}
      >
        <div className={styles.accountingDv01Header}>
          <span>分类</span>
          <span>面值加权久期</span>
          <span>DV01</span>
          <span>面值</span>
          <span>持仓数</span>
        </div>
        {rows.map((row) => (
          <div className={styles.accountingDv01Row} key={row.value}>
            <strong>{row.label}</strong>
            <span className={styles.accountingDv01Number}>{formatDurationDisplay(row.payload?.face_weighted_modified_duration)}</span>
            <span className={styles.accountingDv01Number}>{formatWanEvidenceDisplay(row.payload?.total_dv01)}</span>
            <span className={styles.accountingDv01Number}>{formatMoneyDisplay(row.payload?.total_face_value)}</span>
            <span className={styles.accountingDv01Number}>
              {row.payload ? formatNumericString(row.payload.position_count) : "—"}
            </span>
          </div>
        ))}
      </div>
      {isLoading ? <div className={styles.accountingDv01Note}>分类 DV01 正在读取。</div> : null}
      {hasError ? <div className={styles.accountingDv01Note}>分类 DV01 读面暂未返回。</div> : null}
    </Card>
  );
}

function HoldingsMobileReadout({
  holdings,
  unavailable,
  reportDate,
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
  reportDate: string;
}) {
  const leadHolding = unavailable ? null : holdings[0] ?? null;
  const leadName = leadHolding
    ? leadHolding.instrument_name ?? leadHolding.instrument_code
    : unavailable
      ? "读面暂未返回"
      : "暂无持仓明细";
  const leadDetail = leadHolding ? (
    <Link
      to={buildBondTradingDeskPath(leadHolding.instrument_code, reportDate)}
      data-testid={`bond-trading-desk-link-${leadHolding.instrument_code}`}
    >
      {leadHolding.instrument_code}
    </Link>
  ) : undefined;
  const statusLabel = unavailable ? "读面暂未返回" : `${holdings.length} 只可见`;

  return (
    <div data-testid="bond-analysis-holdings-mobile-readout" className={styles.mobileTableReadout}>
      <div className={styles.mobileReadoutHeader}>
        <span>{TOP_HOLDINGS_MOBILE_LABEL}</span>
        <strong>{statusLabel}</strong>
      </div>
      <div className={styles.mobileReadoutGrid}>
        <MobileReadoutField label="最大持仓" value={leadName} detail={leadDetail} />
        <MobileReadoutField label="评级" value={formatTextEvidenceDisplay(leadHolding?.rating)} />
        <MobileReadoutField label="市值" value={formatMoneyEvidenceDisplay(leadHolding?.market_value)} />
        <MobileReadoutField label="收益率" value={formatPctEvidenceDisplay(leadHolding?.ytm)} />
        <MobileReadoutField label="久期" value={formatNumericEvidenceDisplay(leadHolding?.modified_duration)} />
        <MobileReadoutField label="权重" value={formatPctEvidenceDisplay(leadHolding?.weight)} />
      </div>
    </div>
  );
}

function ReferenceMarketTicker({
  series,
  unavailable,
}: {
  series: ChoiceMacroLatestPoint[];
  unavailable: boolean;
}) {
  const byId = new Map(series.map((point) => [point.series_id, point]));
  const hasAnyLevel = BOND_ANALYTICS_MACRO_BAR_SERIES.some((item) => byId.has(item.series_id));

  return (
    <div data-testid="bond-analysis-market-ticker" className={styles.referenceMarketTicker}>
      {BOND_ANALYTICS_MACRO_BAR_SERIES.map((item) => {
        const point = byId.get(item.series_id);
        const delta = coalesceMacroSeriesDelta(point);
        const displayPoint = point ? buildMacroPointForDeltaDisplay(point, delta) : null;
        const tone =
          displayPoint?.latest_change == null
            ? "flat"
            : displayPoint.latest_change > 0
              ? "up"
              : displayPoint.latest_change < 0
                ? "down"
                : "flat";

        return (
          <div key={item.series_id} className={styles.referenceTickerCell}>
            <span>{item.shortLabel}</span>
            <strong>{point ? formatChoiceMacroValue(point, { spaceBeforeUnit: false }) : "—"}</strong>
            <small data-tone={tone}>
              {displayPoint
                ? formatChoiceMacroDelta(displayPoint, {
                    emptyDisplay: unavailable || !hasAnyLevel ? "待读取" : "—",
                    spaceBeforeUnit: false,
                  })
                : unavailable || !hasAnyLevel
                  ? "待读取"
                  : "—"}
            </small>
          </div>
        );
      })}
    </div>
  );
}

function ReferenceJudgmentMatrix({
  duration,
  creditWeight,
  spreadMedianBp,
  dv01Display,
  hasDv01Readout,
  hasCurveReadout,
  marketValueMomPct,
}: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
  dv01Display: string;
  hasDv01Readout: boolean;
  hasCurveReadout: boolean;
  marketValueMomPct: number | null;
}) {
  const creditMissing = [
    Number.isFinite(spreadMedianBp) ? null : "信用利差",
    Number.isFinite(creditWeight) ? null : "信用占比",
  ].filter(Boolean);
  const rows = [
    {
      label: "利率证据",
      value: Number.isFinite(duration) ? "已返回" : "待返回",
      detail: Number.isFinite(duration) ? `返回字段：组合久期 ${duration.toFixed(2)} 年` : "返回字段：—",
      missing: Number.isFinite(duration) ? "缺失项：—" : "缺失项：久期",
      isReturned: Number.isFinite(duration),
    },
    {
      label: "曲线证据",
      value: hasCurveReadout ? "正式曲线可读" : "正式曲线待返回",
      detail: hasCurveReadout ? "返回字段：期限点收益率与日变动" : "返回字段：期限桶仅作暴露观察",
      missing: hasCurveReadout ? "缺失项：正式 KRD" : "缺失项：正式曲线 / 正式 KRD",
      isReturned: hasCurveReadout,
    },
    {
      label: "信用证据",
      value: Number.isFinite(spreadMedianBp) || Number.isFinite(creditWeight) ? "已返回" : "待返回",
      detail: `返回字段：${buildReadoutFacts({ duration: Number.NaN, creditWeight, spreadMedianBp }).join(" · ") || "—"}`,
      missing: `缺失项：${creditMissing.length > 0 ? creditMissing.join(" / ") : "—"}`,
      isReturned: Number.isFinite(spreadMedianBp) || Number.isFinite(creditWeight),
    },
    {
      label: "资金证据",
      value: hasDv01Readout ? "DV01已返回" : "DV01待返回",
      detail: `返回字段：组合 DV01 ${dv01Display}`,
      missing: hasDv01Readout ? "缺失项：—" : "缺失项：DV01",
      isReturned: hasDv01Readout,
    },
  ];

  return (
    <div data-testid="bond-analysis-judgment-matrix" className={styles.referenceJudgmentPanel}>
      <div className={styles.referenceEvidenceNotice}>
        <span>证据边界</span>
        <strong>只展示后端返回事实，不生成交易判断或风险阈值。</strong>
      </div>
      <div className={styles.referenceJudgmentMatrix}>
        {rows.map((row) => (
          <div
            key={row.label}
            className={styles.referenceJudgmentCard}
            data-readout-status={row.isReturned ? "returned" : "pending"}
          >
            <span>{row.label}</span>
            <strong>{row.value}</strong>
            <small>{row.detail}</small>
            <em>{row.missing}</em>
          </div>
        ))}
      </div>
      <div className={styles.strategyTagGrid}>
        <div>
          <span>组合久期</span>
          <strong>{Number.isFinite(duration) ? `${duration.toFixed(2)} 年` : "—"}</strong>
        </div>
        <div>
          <span>市值环比</span>
          <strong>{formatSignedPct(marketValueMomPct)}</strong>
        </div>
        <div>
          <span>曲线状态</span>
          <strong>{hasCurveReadout ? "已返回" : "待返回"}</strong>
        </div>
        <div>
          <span>风险锚点</span>
          <strong>DV01事实</strong>
        </div>
        <div>
          <span>前端边界</span>
          <strong>只展示返回事实</strong>
        </div>
      </div>
    </div>
  );
}

function buildCompactYieldCurveChartOption(curves: YieldCurveTermStructureCurvePayload[]) {
  const base = buildYieldCurveTermStructureChartOption(curves);
  if (!base || !Array.isArray(base.series)) {
    return null;
  }

  const lineSeries = base.series.filter(
    (series) =>
      series &&
      typeof series === "object" &&
      "type" in series &&
      series.type === "line",
  );
  if (!lineSeries.length) {
    return null;
  }

  const yieldAxis = Array.isArray(base.yAxis) ? base.yAxis[0] : base.yAxis;

  return {
    ...base,
    animation: false,
    legend: {
      top: 2,
      right: 4,
      type: "plain" as const,
      itemWidth: 10,
      itemHeight: 8,
      textStyle: { fontSize: 10, color: ibTokens.color.inkMuted },
    },
    grid: { left: 44, right: 12, top: 26, bottom: 22 },
    yAxis: yieldAxis ? [yieldAxis] : base.yAxis,
    series: lineSeries,
  };
}

function ReferenceCurveCompactChart({
  curves,
}: {
  curves: YieldCurveTermStructureCurvePayload[];
}) {
  const option = useMemo(() => buildCompactYieldCurveChartOption(curves), [curves]);

  if (!option) {
    return null;
  }

  return (
    <div
      data-testid="bond-analysis-yield-curve-chart"
      className={styles.curveCompactChart}
      aria-label="正式收益率曲线折线图"
    >
      <ReactECharts option={option} opts={{ renderer: "canvas" }} />
    </div>
  );
}

function ReferenceCurveReadout({
  curves,
}: {
  curves: YieldCurveTermStructureCurvePayload[];
}) {
  const readableCurves = curves.filter(curveHasReadout).slice(0, 3);

  if (readableCurves.length === 0) {
    const pendingRows = [
      {
        label: "正式曲线期限点",
        value: "待返回",
        detail: "收益率与日变动未返回",
      },
      {
        label: "正式 KRD",
        value: "待返回",
        detail: "不由期限桶推导",
      },
      {
        label: "期限桶观察",
        value: "仅作观察",
        detail: "用于暴露校验",
      },
      {
        label: "前端处理",
        value: "不补造",
        detail: "缺口显式保留",
      },
    ];

    return (
      <div data-testid="bond-analysis-yield-curve-empty" className={styles.curvePendingPanel}>
        <div className={styles.curvePendingHeader}>
          <strong>正式曲线 / KRD 读面待返回</strong>
          <span>当前未返回正式收益率曲线期限点与日变动，不用期限桶冒充 KRD，也不前端补造缺失点。</span>
        </div>
        <div className={styles.curvePendingLedger}>
          {pendingRows.map((row) => (
            <div key={row.label} className={styles.curvePendingRow}>
              <span>{row.label}</span>
              <strong>{row.value}</strong>
              <small>{row.detail}</small>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const tenors = buildCurveComparisonTenors(readableCurves);
  const largestDeltaReadout = pickLargestCurveDeltaReadout(readableCurves);
  const largestDeltaTone = curveDeltaTone(largestDeltaReadout?.point.delta_bp_prev);
  const firstResolvedDate = readableCurves.find((curve) => curve.trade_date_resolved)?.trade_date_resolved;
  const vendorSummary = Array.from(
    new Set(readableCurves.map((curve) => curve.vendor_name).filter(Boolean)),
  ).join(" / ");
  const sourceSummary = readableCurves
    .map((curve) => `${curveLabel(curve.curve_type)} ${curve.source_version || "待返回"}`)
    .join(" · ");
  const returnedPointCount = readableCurves.reduce(
    (total, curve) => total + curve.points.filter(curvePointHasReadout).length,
    0,
  );

  return (
    <div data-testid="bond-analysis-yield-curve-readout" className={styles.curveReadoutStack}>
      <div className={styles.curveReadoutBlock}>
        <div className={styles.curveReadoutHeader}>
          <div className={styles.curveReadoutIdentity}>
            <strong>{readableCurves.map((curve) => curveLabel(curve.curve_type)).join(" / ")}</strong>
            <span>
              交易日 {firstResolvedDate ?? readableCurves[0]?.trade_date_requested ?? "—"} · vendor {vendorSummary || "待返回"}
            </span>
            <small>{sourceSummary}</small>
          </div>
          <div className={styles.curveEvidenceTag} data-tone={largestDeltaTone}>
            <span>最大日变动</span>
            <strong>
              {largestDeltaReadout
                ? `${curveLabel(largestDeltaReadout.curve.curve_type)} ${largestDeltaReadout.point.tenor} ${formatCurveNumeric(largestDeltaReadout.point.delta_bp_prev)}`
                : "待返回"}
            </strong>
            <small>
              {largestDeltaReadout
                ? `${formatCurveNumeric(largestDeltaReadout.point.yield_pct)} · 全部返回点扫描`
                : "未返回可判读的日变动"}
            </small>
          </div>
        </div>
        <ReferenceCurveCompactChart curves={readableCurves} />
        <div data-testid="bond-analysis-curve-tenor-matrix" className={styles.curveTenorMatrix}>
          <div className={`${styles.curveMatrixRow} ${styles.curveMatrixHead}`}>
            <span className={styles.curveMatrixLabel}>曲线 / 期限</span>
            {tenors.map((tenor) => (
              <strong key={`tenor-${tenor}`} className={styles.curveMatrixTenor}>
                {tenor}
              </strong>
            ))}
          </div>
          {readableCurves.flatMap((curve) => {
            const label = curveLabel(curve.curve_type);

            return [
              <div key={`${curve.curve_type}-yield`} className={styles.curveMatrixRow}>
                <span className={styles.curveMatrixLabel}>{label} 收益率</span>
                {tenors.map((tenor) => {
                  const point = curvePointByTenor(curve, tenor);
                  return (
                    <span key={`${curve.curve_type}-${tenor}-yield`} className={styles.curveMatrixValue}>
                      {formatCurveNumeric(point?.yield_pct)}
                    </span>
                  );
                })}
              </div>,
              <div key={`${curve.curve_type}-delta`} className={styles.curveMatrixRow}>
                <span className={styles.curveMatrixLabel}>{label} 日变动</span>
                {tenors.map((tenor) => {
                  const point = curvePointByTenor(curve, tenor);
                  return (
                    <span
                      key={`${curve.curve_type}-${tenor}-delta`}
                      className={styles.curveMatrixValue}
                      data-tone={curveDeltaTone(point?.delta_bp_prev)}
                    >
                      {formatCurveNumeric(point?.delta_bp_prev)}
                    </span>
                  );
                })}
              </div>,
            ];
          })}
        </div>
        <div className={styles.curvePointCount}>
          <span>返回曲线：</span>
          <strong>{readableCurves.length} 条</strong>
          <span>展示期限点：</span>
          <strong>{tenors.length} / {returnedPointCount}</strong>
          <small>只列后端返回可读点；空缺期限保持 —</small>
        </div>
      </div>
    </div>
  );
}

function ReferenceYieldCurvePanel({
  reportDate,
  maturityRows,
  curves,
  isLoading,
  hasError,
}: {
  reportDate: string;
  maturityRows: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  curves: YieldCurveTermStructureCurvePayload[];
  isLoading: boolean;
  hasError: boolean;
}) {
  const resolvedDate = curves.find((curve) => curve.trade_date_resolved)?.trade_date_resolved;
  const hasCurveData = curves.some(curveHasReadout);
  const readableCurveCount = curves.filter(curveHasReadout).length;
  const curveStatusText = isLoading
    ? "正式曲线读取中"
    : hasError
      ? "正式曲线接口暂未返回"
      : hasCurveData
        ? "正式 KRD 待读面，仅展示曲线期限点"
        : "正式曲线 / KRD 读面待返回";

  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="主视区" title="曲线 / KRD 观察" />}
      data-testid="bond-analysis-yield-curve-panel"
      className={`${styles.referencePanelCard} ${styles.referenceCurveCard}`}
      styles={{ body: cardBodyStyle }}
    >
      <div className={styles.referenceCurveLayout}>
        <div className={styles.referenceCurveHero}>
          <div className={styles.referenceCurveBanner}>
            <div className={styles.referenceCurveBannerText}>
              <div className={styles.referenceCurveKicker}>正式曲线期限点主视图</div>
              <strong>{curveStatusText}</strong>
              <span>
                报告日 {reportDate || "—"} · 曲线交易日 {resolvedDate ?? "待解析"}
                {isLoading ? " · 正在读取正式曲线" : null}
                {hasError ? " · 曲线接口暂未返回" : null}
              </span>
            </div>
            <div className={styles.referenceCurveBannerStats}>
              <div>
                <span>已返回曲线</span>
                <strong>{readableCurveCount} 条</strong>
              </div>
              <div>
                <span>正式 KRD</span>
                <strong>待返回</strong>
              </div>
            </div>
          </div>
          <div className={styles.referenceCurveMeta}>
            首屏只展示后端返回的收益率曲线期限点与前日变动；KRD 读面待后端正式返回，不在前端推导或补造。
          </div>
          <ReferenceCurveReadout curves={curves} />
        </div>
        <div className={styles.curveFallbackBlock}>
          <div className={styles.curveFallbackHeader}>
            <strong>{hasCurveData ? "期限桶校验 / 暴露观察" : "期限桶占位 / 不冒充 KRD"}</strong>
            <span>{hasCurveData ? "期限桶只用于校验组合期限暴露，不等同于正式 KRD。" : "正式曲线缺口下，只保留期限桶观察，不把 maturity bucket 说成 KRD。"}</span>
          </div>
          <MaturityColumnChart items={maturityRows} emptyText="暂无期限结构" />
          <ProgressStack items={maturityRows.slice(0, 4)} emptyText="暂无期限结构" />
        </div>
      </div>
    </Card>
  );
}

function ReferenceReturnAttributionPanel({
  actionPnlDisplay,
  actionPnlTone,
  actionCount,
  marketValueMomPct,
  dv01Mom,
  unrealizedPnlDisplay,
  unrealizedPnlMomPct,
  onOpenModuleDetail,
}: {
  actionPnlDisplay: string;
  actionPnlTone: "default" | "positive" | "negative";
  actionCount: number | null;
  marketValueMomPct: number | null;
  dv01Mom: number;
  unrealizedPnlDisplay: string;
  unrealizedPnlMomPct: number | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}) {
  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="归因 / DV01" title="收益归因 / DV01 变动证据" />}
      data-testid="bond-analysis-return-attribution-panel"
      className={`${styles.referencePanelCard} ${styles.referenceAttributionCard}`}
      styles={{ body: cardBodyStyle }}
    >
      <div className={styles.referenceAttributionPanel}>
        <div className={styles.attributionLead}>
          <span>动作归因</span>
          <strong data-tone={actionPnlTone}>{actionPnlDisplay}</strong>
          <small>{actionCount !== null ? `${actionCount} 笔动作` : "动作归因待返回"}</small>
        </div>
        <div className={styles.footerChangeSplit}>
          <span>市值 {formatSignedPct(marketValueMomPct)}</span>
          <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : "—"}</span>
        </div>
        <div className={styles.attributionEvidenceGrid}>
          <div>
            <span>归因状态</span>
            <strong>{actionCount !== null ? "已返回" : "待返回"}</strong>
          </div>
          <div>
            <span>动作数</span>
            <strong>{actionCount !== null ? `${actionCount} 笔` : "—"}</strong>
          </div>
          <div>
            <span>DV01变动</span>
            <strong>{Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : "—"}</strong>
          </div>
          <div>
            <span>市值环比</span>
            <strong>{formatSignedPct(marketValueMomPct)}</strong>
          </div>
        </div>
        <div className={styles.attributionLedger}>
          <div>
            <span>本期估值收益</span>
            <strong>{unrealizedPnlDisplay}</strong>
          </div>
          <div>
            <span>较上期</span>
            <strong>{formatSignedPct(unrealizedPnlMomPct)}</strong>
          </div>
        </div>
        <div className={styles.attributionBoundaryNote}>
          收益、动作与 DV01 仅按返回读面列示；未返回字段保持缺口，不在前端补算归因。
        </div>
        <Button size="small" type="text" data-testid="bond-analysis-home-open-action-attribution" onClick={() => onOpenModuleDetail?.("action-attribution")}>
          打开动作归因
        </Button>
      </div>
    </Card>
  );
}

function ProgressStack({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.progressList}>
      {items.map((item) => (
        <div key={item.key} className={styles.referenceProgressRow}>
          <div className={styles.progressHeader}>
            <span>{item.label}</span>
            <span className={styles.progressCaption}>{item.caption}</span>
          </div>
          <div className={styles.referenceProgressTrack}>
            <div
              className={styles.referenceProgressBar}
              style={{
                width: `${Math.max(8, (Math.abs(item.value) / maxValue) * 100)}%`,
                background: item.color ?? IB_ACCENT_BAR,
              }}
            />
          </div>
          {item.detail ? <div className={styles.progressDetail}>{item.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

function EmptyEvidencePanel({ text }: { text: string }) {
  return <div className={styles.emptyEvidencePanel}>{text}</div>;
}

function PendingReadModelPanel({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className={styles.pendingReadModelPanel}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function MaturityColumnChart({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.maturityChart}>
      {items.slice(0, 7).map((item) => (
        <div key={item.key} className={styles.maturityColumn}>
          <span>{item.caption}</span>
          <div
            style={{
              height: `${Math.max(10, (Math.abs(item.value) / maxValue) * 118)}px`,
              background: item.color ?? IB_ACCENT_BAR,
            }}
          />
          <small>{item.label}</small>
        </div>
      ))}
    </div>
  );
}

function buildDonutGradient(items: Array<{ value: number; color?: string }>) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (total <= 0) {
    return "conic-gradient(var(--moss-color-neutral-200) 0 100%)";
  }

  let cursor = 0;
  const stops = items.map((item, index) => {
    const start = cursor;
    cursor += (Math.max(item.value, 0) / total) * 100;
    const color = item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length];
    return `${color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
  });

  return `conic-gradient(${stops.join(", ")})`;
}

function DistributionDonut({
  items,
  center,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  center: string;
  emptyText: string;
}) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (items.length === 0 || total <= 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.referenceDonutPanel}>
      <div className={styles.referenceDonutLegend}>
        {items.slice(0, 5).map((item, index) => (
          <div key={item.key} className={styles.referenceDonutLegendRow}>
            <span style={{ background: item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length] }} />
            <strong>{item.label}</strong>
            <em>{item.caption}</em>
          </div>
        ))}
      </div>
      <div
        className={styles.referenceDonut}
        style={{ "--donut": buildDonutGradient(items) } as CSSProperties}
      >
        <span>{center}</span>
      </div>
    </div>
  );
}

function HoldingRows({
  holdings,
  unavailable,
  reportDate,
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
  reportDate: string;
}) {
  if (unavailable) {
    return <div className={styles.tableEmpty}>{TOP_HOLDINGS_HOME_NOTE}</div>;
  }

  if (holdings.length === 0) {
    return <div className={styles.tableEmpty}>{BOND_HOLDINGS_EMPTY_NOTE}</div>;
  }

  return (
    <div className={styles.holdingsTableRows}>
      {holdings.map((item) => (
        <div key={item.instrument_code} className={styles.holdingsTableRow}>
          <div className={styles.holdingNameCell}>
            <strong>{item.instrument_name ?? item.instrument_code}</strong>
            <Link
              to={buildBondTradingDeskPath(item.instrument_code, reportDate)}
              data-testid={`bond-trading-desk-link-${item.instrument_code}`}
            >
              {item.instrument_code}
            </Link>
          </div>
          <span>{item.asset_class}</span>
          <span>{formatTextEvidenceDisplay(item.rating)}</span>
          <span className={styles.holdingNumericCell}>{formatMoneyEvidenceDisplay(item.market_value)}</span>
          <span className={styles.holdingNumericCell}>{formatPctEvidenceDisplay(item.ytm)}</span>
          <span className={styles.holdingNumericCell}>{formatNumericEvidenceDisplay(item.modified_duration)}</span>
          <span className={styles.holdingNumericCell}>{formatPctEvidenceDisplay(item.weight)}</span>
        </div>
      ))}
    </div>
  );
}

function RegionDistributionPanel({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const topItems = items.slice(0, 8);
  const maxValue = Math.max(...topItems.map((item) => Math.abs(item.value)), 1);

  if (topItems.length === 0) {
    return (
      <div className={styles.regionConcentrationPanel}>
        <EmptyEvidencePanel text={emptyText} />
      </div>
    );
  }

  return (
    <div className={styles.regionConcentrationPanel}>
      <div className={styles.regionList}>
        {topItems.map((item) => (
          <div key={item.key} className={styles.regionRow}>
            <div className={styles.regionRowHeader}>
              <strong>{item.label}</strong>
              <span>{item.caption}</span>
            </div>
            <div className={styles.regionTrack}>
              <i
                style={{
                  width: `${Math.max(7, (Math.abs(item.value) / maxValue) * 100)}%`,
                  background: item.color ?? dt.color.info[400],
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export interface BondAnalyticsInstitutionalCockpitDecisionRailProps {
  activeModuleContext: BondAnalyticsActiveModuleContext;
  activeReadinessItem: BondAnalyticsReadinessItem;
  watchlistItems: BondAnalyticsReadinessItem[];
}

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  decisionRail?: BondAnalyticsInstitutionalCockpitDecisionRailProps;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  actionAttribution = null,
  decisionRail,
  onOpenModuleDetail,
}: BondAnalyticsInstitutionalCockpitProps) {
  const client = useApiClient();
  const dashboardDatesQuery = useQuery({
    queryKey: ["bond-analytics-institutional", "dashboard-dates", client.mode],
    queryFn: () => client.getBondDashboardDates(),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });
  const macroLatestQ = useQuery({
    queryKey: ["bond-analytics-institutional", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    staleTime: 60_000,
  });
  const dashboardReportDate = useMemo(() => {
    if (!reportDate) {
      return "";
    }

    if (!dashboardDatesQuery.data && !dashboardDatesQuery.isError) {
      return "";
    }

    const availableDates = dashboardDatesQuery.data?.result.report_dates ?? [];
    if (availableDates.length > 0) {
      return availableDates.includes(reportDate) ? reportDate : availableDates[0];
    }

    return reportDate;
  }, [dashboardDatesQuery.data, dashboardDatesQuery.isError, reportDate]);
  const isDashboardDateFallback =
    Boolean(reportDate) &&
    Boolean(dashboardReportDate) &&
    dashboardReportDate !== reportDate;
  // Business queries below key off `queryReportDate` rather than waiting for
  // `dashboardReportDate` to resolve first: they fire immediately, optimistically assuming
  // `reportDate` is also a valid bond-dashboard snapshot (the common case). If the dashboard
  // dates lookup later reveals a fallback is needed, `dashboardReportDate` changes and every
  // query below picks up a new queryKey/param and re-fetches for the corrected date. This
  // removes the two-level "dates -> dates -> 12+ business calls" waterfall in the common case
  // without changing the final displayed data for the (rare) fallback case.
  const queryReportDate = dashboardReportDate || reportDate;

  const cockpitBundleQ = useQuery({
    queryKey: apiQueryKeys.bondDashboardBundle(
      client.mode,
      queryReportDate,
      COCKPIT_BUNDLE_SECTIONS,
      COCKPIT_BUNDLE_INDUSTRY_TOP_N,
    ),
    queryFn: () =>
      client.fetchBondDashboardBundle(queryReportDate, COCKPIT_BUNDLE_SECTIONS, {
        industryTopN: COCKPIT_BUNDLE_INDUSTRY_TOP_N,
        analyticsTopN: COCKPIT_BUNDLE_ANALYTICS_TOP_N,
        dv01TopN: DV01_HOME_TOP_N,
        dv01ShockBps: DV01_HOME_SHOCK_BPS,
        curveTypes: HOME_YIELD_CURVE_TYPES,
      }),
    enabled: Boolean(queryReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const headlineQ = bundleSectionQuery(cockpitBundleQ, "headline-kpis");
  const maturityQ = bundleSectionQuery(cockpitBundleQ, "maturity-structure");
  const holdingsQ = bundleSectionQuery(cockpitBundleQ, "top-holdings");
  const portfolioHlQ = bundleSectionQuery(cockpitBundleQ, "portfolio-headlines");
  const assetStructureQ = bundleSectionQuery(cockpitBundleQ, "asset-structure");
  const riskQ = bundleSectionQuery(cockpitBundleQ, "risk-indicators");
  const industryQ = bundleSectionQuery(cockpitBundleQ, "industry-distribution");
  const yieldCurveQ = bundleSectionQuery(cockpitBundleQ, "yield-curve-term-structure");
  const dv01AccountingQueries = DV01_ACCOUNTING_CLASSES.map((item) =>
    bundleSectionQuery(cockpitBundleQ, DV01_BUNDLE_SECTION_BY_ACCOUNTING_CLASS[item.value]),
  );

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;
  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;
  const portfolioHeadlinesUnavailable = portfolioHlQ.isError;
  const topHoldingsUnavailable = holdingsQ.isError;
  const dv01AccountingRows = DV01_ACCOUNTING_CLASSES.map((item, index) => ({
    ...item,
    payload: dv01AccountingQueries[index]?.data?.result ?? null,
  }));
  const dv01AccountingLoading = dv01AccountingQueries.some((query) => query.isLoading);
  const dv01AccountingUnavailable = dv01AccountingQueries.some((query) => query.isError);

  const dur = headline ? numOrNullAware(headline.kpis.weighted_duration) : Number.NaN;
  const riskCreditRatio = riskQ.data?.result ? numOrNullAware(riskQ.data.result.credit_ratio) : Number.NaN;
  const portfolioCreditWeight = portfolioHl ? numOrNullAware(portfolioHl.credit_weight) : Number.NaN;
  const creditWeight = Number.isFinite(riskCreditRatio) ? riskCreditRatio : portfolioCreditWeight;
  const spreadMedian = headline?.kpis.credit_spread_median ?? null;
  const spreadMedianBp = normalizeSpreadBp(spreadMedian);
  const conclusion = isDashboardDateFallback
    ? {
        title: "快照待复核",
        body: "当前请求报告日暂无债券驾驶舱快照。",
        detail: `请求 ${reportDate}，当前展示 ${dashboardReportDate} 快照；主结论需等目标报告日读面补齐后再确认。`,
      }
    : buildCockpitConclusion({
        duration: dur,
        creditWeight,
        spreadMedianBp,
      });

  const k = headline?.kpis;
  const previousK = headline?.prev_kpis;
  const marketValuePair = buildKpiValuePair(headline ?? null, "total_market_value");
  const unrealizedPnlPair = buildKpiValuePair(headline ?? null, "unrealized_pnl");
  const marketValueMomPct = computeRelativeChangePct(marketValuePair.current, marketValuePair.previous);
  const unrealizedPnlMomPct = computeRelativeChangePct(unrealizedPnlPair.current, unrealizedPnlPair.previous);
  const currentDv01Raw = k ? bondNumericRawOrNull(k.total_dv01) : null;
  const previousDv01Raw = previousK ? bondNumericRawOrNull(previousK.total_dv01) : null;
  const dv01Mom = currentDv01Raw !== null && previousDv01Raw !== null ? currentDv01Raw - previousDv01Raw : Number.NaN;

  const maturityItems = useMemo(() => {
    return [...(maturityQ.data?.result.items ?? [])]
      .flatMap((item) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 7)
      .map(({ item, rawMarketValue }, index) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        color: DISTRIBUTION_CHART_COLORS[index % DISTRIBUTION_CHART_COLORS.length],
      }));
  }, [maturityQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const dashboardAssetItems = useMemo(() => {
    const palette = DISTRIBUTION_CHART_COLORS;
    const dashboardItems = [...(assetStructureQ.data?.result.items ?? [])]
      .flatMap((item: AssetStructureItem, index) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, index, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 5)
      .map(({ item, index, rawMarketValue }) => ({
        key: item.category,
        label: item.category || "未分类",
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        detail: `${item.bond_count} 只`,
        color: palette[index % palette.length],
      }));

    if (dashboardItems.length > 0) {
      return dashboardItems;
    }

    return assetClassItems.flatMap((item, index) => {
      const rawMarketValue = bondNumericRawOrNull(item.market_value);
      return rawMarketValue === null
        ? []
        : [
            {
              key: item.asset_class,
              label: item.asset_class,
              value: rawMarketValue,
              caption: formatYi(item.market_value),
              detail: `久期 ${formatNumericDisplay(item.duration)} · 权重 ${formatNumericDisplay(item.weight)}`,
              color: palette[index % palette.length],
            },
          ];
    });
  }, [assetClassItems, assetStructureQ.data]);
  const industryItems = useMemo(() => {
    const palette = DISTRIBUTION_CHART_COLORS;
    return [...(industryQ.data?.result.items ?? [])]
      .flatMap((item, index) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, index, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 8)
      .map(({ item, index, rawMarketValue }) => ({
        key: item.industry_name,
        label: item.industry_name || "未分类",
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        color: palette[index % palette.length],
      }));
  }, [industryQ.data]);
  const topHoldings = (holdingsQ.data?.result.items ?? []).slice(0, 10);
  const ratingDistribution = useMemo(() => {
    const buckets = new Map<string, { count: number; faceValue: number }>();
    for (const item of holdingsQ.data?.result.items ?? []) {
      const rawFaceValue = bondNumericRawOrNull(item.face_value);
      if (rawFaceValue === null) {
        continue;
      }
      const key = item.rating?.trim() || "Unrated";
      const next = buckets.get(key) ?? { count: 0, faceValue: 0 };
      next.count += 1;
      next.faceValue += rawFaceValue;
      buckets.set(key, next);
    }
    return Array.from(buckets.entries())
      .map(([rating, stats]) => ({
        rating,
        count: stats.count,
        faceValue: stats.faceValue,
      }))
      .sort((left, right) => right.faceValue - left.faceValue)
      .slice(0, 6);
  }, [holdingsQ.data?.result.items]);
  const totalActionPnl = bondNumericRaw(actionAttribution?.total_pnl_from_actions ?? null);
  const durationDisplay = Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—";
  const creditWeightDisplay = Number.isFinite(creditWeight) ? `${(creditWeight * 100).toFixed(2)}%` : "—";
  const marketValueDisplay = k ? formatYi(k.total_market_value) : "—";
  const unrealizedPnlDisplay = k ? formatYi(k.unrealized_pnl) : "—";
  const dv01Source = riskQ.data?.result?.total_dv01 ?? portfolioHl?.total_dv01 ?? k?.total_dv01 ?? null;
  const hasDv01Readout = bondNumericRawOrNull(dv01Source) !== null;
  const dv01Display = hasDv01Readout ? formatWan(dv01Source) : "—";
  const unrealizedPnlTone =
    k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default";
  const actionPnlDisplay = actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : "—";
  const actionPnlTone =
    totalActionPnl !== null && Number.isFinite(totalActionPnl) && totalActionPnl !== 0
      ? totalActionPnl > 0
        ? "positive"
        : "negative"
      : "default";
  const macroSeries = macroLatestQ.data?.result.series ?? [];
  const macroUnavailable = macroLatestQ.isError || macroSeries.length === 0;
  const yieldCurveCurves = yieldCurveQ.data?.result.curves ?? [];
  const hasYieldCurveReadout = yieldCurveCurves.some(curveHasReadout);
  const holdingRatingGapCount = topHoldings.filter((item) => !item.rating?.trim()).length;
  const holdingMetricGapCount = topHoldings.reduce((count, item) => {
    return (
      count +
      (bondNumericRawOrNull(item.market_value) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.ytm) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.modified_duration) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.weight) === null ? 1 : 0)
    );
  }, 0);
  const deskVerdictFields = buildDeskVerdictFields({
    duration: dur,
    creditWeight,
    spreadMedianBp,
    dv01Display,
    reportDate,
    dashboardReportDate,
    isDashboardDateFallback,
    headlinePending: headlineQ.isPending,
    hasHeadline: Boolean(headline),
    hasCurveReadout: hasYieldCurveReadout,
    curvePending: yieldCurveQ.isLoading,
  });
  const maturityRows = maturityItems.map((item) => ({
    ...item,
    detail: `规模 ${item.caption}`,
  }));
  const ratingRows = ratingDistribution.map((item, index) => ({
    key: item.rating,
    label: item.rating,
    value: item.faceValue,
    caption: `${item.count} 只`,
    detail: formatYi(item.faceValue),
    color: DISTRIBUTION_CHART_COLORS[index % DISTRIBUTION_CHART_COLORS.length],
  }));
  const durationRows = maturityItems.slice(0, 3).map((item) => ({
    ...item,
    detail: `市值 ${item.caption}`,
  }));
  const durationRiskRow = {
    label: "组合久期",
    value: riskQ.data?.result ? formatDurationDisplay(riskQ.data.result.weighted_duration) : durationDisplay,
    detail: "来自风险指标读面",
  };
  const dv01RiskRow = {
    label: "组合 DV01",
    value: dv01Display,
    detail: "利率敏感度",
  };
  const creditRatioRiskRow = {
    label: "信用占比",
    value: riskQ.data?.result ? formatPct(riskQ.data.result.credit_ratio) : creditWeightDisplay,
    detail: "信用债市值占比",
  };
  const spreadDv01RiskRow = {
    label: "利差 DV01",
    value: riskQ.data?.result ? formatWan(riskQ.data.result.total_spread_dv01) : "—",
    detail: "信用利差敏感度",
  };
  const riskRows = [durationRiskRow, dv01RiskRow, creditRatioRiskRow, spreadDv01RiskRow];
  const footerRiskRows = [durationRiskRow, dv01RiskRow, creditRatioRiskRow];
  const topbarReportDate = dashboardReportDate || reportDate || "—";
  const topbarReportStatus = isDashboardDateFallback
    ? `快照回退 ${dashboardReportDate || "—"}`
    : dashboardReportDate
      ? "报告日匹配"
      : "报告日待确认";
  const topbarReadoutStatus = headlineQ.isPending ? "加载中" : headline ? "已返回" : "待返回";
  const topbarReadoutDetail = headlineQ.isPending
    ? "等待后端返回"
    : headline
      ? "核心读面可用"
      : "核心读面未返回";

  return (
    <section data-testid="bond-analysis-phase3-cockpit" className={styles.phaseSection}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <section data-testid="bond-analysis-reference-dashboard" className={styles.referenceDashboard}>
        <section data-testid="bond-analysis-reference-topbar" className={styles.heroSection}>
          <div className={styles.heroIdentity}>
            <div className={styles.holdingsKicker}>债券分析</div>
            <h2 className={styles.heroTitle}>固定收益交易台</h2>
            <span className={styles.heroReportDate}>报告日 {topbarReportDate}</span>
          </div>

          <div data-testid="bond-analysis-cockpit-conclusion" className={styles.heroMain}>
            <div className={styles.heroConclusion}>
              <strong className={styles.heroHeadline}>{conclusion.body}</strong>
              <p className={styles.heroDetail}>{conclusion.detail}</p>
            </div>
            <div className={styles.heroMetrics}>
              <div className={styles.heroMetric}>
                <span>久期</span>
                <strong>{durationDisplay}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>信用利差</span>
                <strong>{formatSpreadBpDisplay(spreadMedian)}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>信用占比</span>
                <strong>{creditWeightDisplay}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>总收益</span>
                <strong className={styles.heroMetricValue} data-tone={unrealizedPnlTone}>
                  {unrealizedPnlDisplay}
                </strong>
                <small className={styles.heroMetricDelta} data-tone={unrealizedPnlTone}>
                  {formatSignedPct(unrealizedPnlMomPct)}
                </small>
              </div>
            </div>
          </div>
          <div className={styles.heroAside} data-testid="bond-analysis-hero-aside">
            <div data-testid="bond-analysis-daily-judgment" className={styles.heroGovernance}>
              <div className={styles.heroGovernanceLead}>
                <span className={styles.conclusionKicker}>证据展开 · 固定收益读面</span>
                <span className={styles.heroGovernanceHeading}>首屏读面拆解</span>
                <span className={styles.heroGovernanceDetail}>只展示后端返回事实，不补造读面。</span>
              </div>
              <div className={styles.heroGovernanceMetrics}>
                <span>久期 {durationDisplay}</span>
                <span>信用利差 {formatSpreadBpDisplay(spreadMedian)}</span>
                <span>信用占比 {creditWeightDisplay}</span>
              </div>
              <div className={styles.heroGovernanceStatus} data-testid="bond-analysis-daily-judgment-status">
                <span>
                  报告日 {topbarReportStatus} · {topbarReportDate}
                </span>
                <span>
                  首屏 KPI {topbarReadoutStatus} · {topbarReadoutDetail}
                </span>
              </div>
              <div className={styles.heroVerdictRow}>
                {deskVerdictFields.map((field) => (
                  <div key={field.label} className={styles.heroVerdictField}>
                    <span>{field.label}</span>
                    <strong>{field.value}</strong>
                    <small>{field.detail}</small>
                  </div>
                ))}
              </div>
            </div>
            {decisionRail && onOpenModuleDetail ? (
              <aside>
                <BondAnalyticsDecisionRail
                  activeModuleContext={decisionRail.activeModuleContext}
                  activeReadinessItem={decisionRail.activeReadinessItem}
                  watchlistItems={decisionRail.watchlistItems}
                  onOpenModuleDetail={onOpenModuleDetail}
                />
              </aside>
            ) : null}
          </div>
        </section>

        <ReferenceMarketTicker series={macroSeries} unavailable={macroUnavailable} />

        <div className={styles.holdingsKpiRail}>
          <InstitutionalKpiRail testId="bond-analysis-kpi-ribbon" columns={7} flush>
            <InstitutionalKpiTile label="久期" value={durationDisplay} detail={leadMaturity ? `最重期限桶 ${leadMaturity.label}` : "期限结构待读面"} status={Number.isFinite(dur) ? "已读" : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="组合到期收益率" value={k ? formatPct(k.weighted_ytm) : "—"} detail={previousK ? `上期 ${formatPct(previousK.weighted_ytm)}` : "收益率待读面"} status={k ? "已读" : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="信用利差" value={formatSpreadBpDisplay(spreadMedian)} detail="信用利差中位数" status={Number.isFinite(spreadMedianBp) ? "已读" : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="DV01" value={dv01Display} detail="风险指标读面" status={hasDv01Readout ? "已读" : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="Carry+Roll" value="—" detail="接口未返回 / 待读面" status="缺口" priority="gap" />
            <InstitutionalKpiTile label="月度收益" value={actionPnlDisplay} detail={actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待读面"} status={actionAttribution ? "已读" : "待读面"} tone={actionPnlTone} />
            <InstitutionalKpiTile label="总收益" value={unrealizedPnlDisplay} detail={`较上期 ${formatSignedPct(unrealizedPnlMomPct)}`} status={k ? "已读" : "待读面"} tone={unrealizedPnlTone} />
          </InstitutionalKpiRail>
          <div
            data-testid="bond-analysis-currency-basis-banner"
            className={styles.currencyBasisBanner}
          >
            {BOND_ANALYTICS_CURRENCY_BASIS_TEXT}
          </div>
        </div>

        <section data-testid="bond-analysis-analysis-grid" className={styles.referenceAnalysisGrid}>
          <ReferenceYieldCurvePanel
            reportDate={dashboardReportDate || reportDate}
            maturityRows={maturityRows}
            curves={yieldCurveCurves}
            isLoading={yieldCurveQ.isLoading}
            hasError={yieldCurveQ.isError}
          />
          <div className={styles.referenceAnalysisSideStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="证据边界" title="利率 / 曲线 / 信用 / 资金" />}
              data-testid="bond-analysis-evidence-boundary-panel"
              className={`${styles.referencePanelCard} ${styles.referenceEvidenceBoundaryCard}`}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <ReferenceJudgmentMatrix
                duration={dur}
                creditWeight={creditWeight}
                spreadMedianBp={spreadMedianBp}
                dv01Display={dv01Display}
                hasDv01Readout={hasDv01Readout}
                hasCurveReadout={hasYieldCurveReadout}
                marketValueMomPct={marketValueMomPct}
              />
            </Card>
          </div>
          <ReferenceReturnAttributionPanel
            actionPnlDisplay={actionPnlDisplay}
            actionPnlTone={actionPnlTone}
            actionCount={actionAttribution?.total_actions ?? null}
            marketValueMomPct={marketValueMomPct}
            dv01Mom={dv01Mom}
            unrealizedPnlDisplay={unrealizedPnlDisplay}
            unrealizedPnlMomPct={unrealizedPnlMomPct}
            onOpenModuleDetail={onOpenModuleDetail}
          />
        </section>

        <AccountingDv01SummaryPanel
          rows={dv01AccountingRows}
          isLoading={dv01AccountingLoading}
          hasError={dv01AccountingUnavailable}
          onOpenModuleDetail={onOpenModuleDetail}
        />

        <section data-testid="bond-analysis-distribution-grid" className={styles.referenceDistributionGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="结构证据" title="券种分布" />}
            extra={
              <Button
                size="small"
                type="text"
                data-testid="bond-analysis-home-open-portfolio-headlines"
                onClick={() => onOpenModuleDetail?.("portfolio-headlines")}
              >
                查看组合详情
              </Button>
            }
            data-testid="bond-analysis-asset-structure"
            style={dashboardCardStyle}
            className={styles.referenceStructureLeadCard}
            styles={{ body: cardBodyStyle }}
          >
            <DistributionDonut items={dashboardAssetItems} center={marketValueDisplay} emptyText="暂无资产结构" />
            {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_STRUCTURE_NOTE}</div> : null}
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="风险切片" title="久期 / DV01 / 信用" />}
            data-testid="bond-analysis-risk-monitor"
            style={dashboardCardStyle}
            className={`${styles.referenceMaturityCard} ${styles.referenceDistributionSupportCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.riskEvidenceList}>
              {riskRows.map((row) => (
                <div key={row.label} className={styles.riskEvidenceRow}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                  <small>{row.detail}</small>
                </div>
              ))}
              <div className={styles.riskEvidenceBoundary}>
                只列后端返回风险字段；缺失保持占位，不生成阈值判断。
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                打开信用利差
              </Button>
            </div>
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="集中度证据" title="发行人/行业分布" />}
            style={dashboardCardStyle}
            className={styles.referenceDistributionSupportCard}
            styles={{ body: cardBodyStyle }}
          >
            <RegionDistributionPanel items={industryItems} emptyText="暂无发行人/行业读面" />
          </Card>
        </section>

        <div className={styles.referenceBottomGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="持仓证据明细" title={TOP_HOLDINGS_CARD_TITLE} />}
            extra={
              <Button
                size="small"
                type="text"
                data-testid="bond-analysis-home-open-top-holdings"
                onClick={() => onOpenModuleDetail?.("top-holdings")}
              >
                查看完整持仓
              </Button>
            }
            data-testid="bond-analysis-holdings-table"
            style={dashboardCardStyle}
            className={styles.referenceHoldingsCard}
            styles={{ body: { padding: 0 } }}
          >
            <HoldingsMobileReadout
              holdings={topHoldings}
              unavailable={topHoldingsUnavailable}
              reportDate={dashboardReportDate}
            />
            <div data-testid="bond-analysis-holdings-evidence-strip" className={styles.holdingsEvidenceStrip}>
              <div>
                <span>{TOP_HOLDINGS_COUNT_LABEL}</span>
                <strong>{topHoldingsUnavailable ? "待返回" : `${topHoldings.length} 条`}</strong>
                <small>{BOND_HOLDINGS_COCKPIT_SCOPE_NOTE}</small>
              </div>
              <div>
                <span>评级缺口</span>
                <strong>{topHoldingsUnavailable ? "—" : `${holdingRatingGapCount} 条`}</strong>
                <small>缺失评级保持 —，不补造评级。</small>
              </div>
              <div>
                <span>数值缺口</span>
                <strong>{topHoldingsUnavailable ? "—" : `${holdingMetricGapCount} 项`}</strong>
                <small>市值 / YTM / 久期 / 权重。</small>
              </div>
            </div>
            <div
              data-testid="bond-analysis-holdings-raw-grid"
              className={styles.holdingsTable}
            >
              <div
                data-testid="bond-analysis-holdings-scroll-cue"
                className={styles.holdingsScrollCue}
                aria-hidden="true"
              >
                <span />
              </div>
              <div className={styles.holdingsTableHeader}>
                <span>债券</span>
                <span>券种</span>
                <span>评级</span>
                <span>市值</span>
                <span>YTM</span>
                <span>久期</span>
                <span>权重</span>
              </div>
              <HoldingRows
                holdings={topHoldings}
                unavailable={topHoldingsUnavailable}
                reportDate={dashboardReportDate}
              />
            </div>
          </Card>


        </div>

        <aside className={styles.referenceSideStack}>
            <div data-testid="bond-analysis-risk-slice-stack" className={styles.sideStackHeader}>
              <span>风险切片</span>
              <strong>评级 / 期限 / 流动性</strong>
              <small>侧栏只汇总返回切片；接口缺口直接显示。</small>
            </div>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="评级证据" title="按市值" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={ratingRows} emptyText={topHoldingsUnavailable ? TOP_HOLDINGS_RATING_NOTE : "暂无评级分布"} />
              {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_CREDIT_NOTE}</div> : null}
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="期限证据" title="按市值" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={durationRows} emptyText="暂无久期分布" />
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="流动性缺口" title="按读面状态" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <PendingReadModelPanel
                title="流动性读面待返回"
                detail="当前接口未提供流动性分布，不在前端补造。"
              />
            </Card>
        </aside>

        <div data-testid="bond-analysis-footer-evidence-grid" className={styles.referenceFooterGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="收益证据" title="本期估值收益" />}
            data-testid="bond-analysis-summary-card"
            style={dashboardCardStyle}
            className={styles.referenceFooterPrimaryCard}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerMetricPanel}>
              <strong>{unrealizedPnlDisplay}</strong>
              <span>{Number.isFinite(unrealizedPnlMomPct) ? `较上期 ${formatSignedPct(unrealizedPnlMomPct)}` : "收益时序证据待返回"}</span>
              <div className={styles.footerReturnLedger}>
                <div>
                  <span>估值收益</span>
                  <strong>{unrealizedPnlDisplay}</strong>
                </div>
                <div>
                  <span>较上期</span>
                  <strong>{Number.isFinite(unrealizedPnlMomPct) ? formatSignedPct(unrealizedPnlMomPct) : "—"}</strong>
                </div>
                <div>
                  <span>收益时序</span>
                  <strong>待返回</strong>
                </div>
                <div>
                  <span>处理边界</span>
                  <strong>不补造趋势</strong>
                </div>
              </div>
              <div data-testid="bond-analysis-footer-primary-evidence" className={styles.footerEvidenceBlock}>
                <div data-testid="bond-analysis-return-trend-boundary" className={styles.footerEvidenceNote}>
                  收益时序未返回：不绘制趋势占位。
                </div>
                <div className={styles.footerActionBar}>
                  <span>收益证据缺口保留在当前读面上下文中。</span>
                  <Button size="small" type="text" data-testid="bond-analysis-home-open-return-decomposition" onClick={() => onOpenModuleDetail?.("return-decomposition")}>
                    打开收益拆解
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <div data-testid="bond-analysis-footer-support-stack" className={styles.footerSupportStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="动作证据" title="动作归因" />}
              data-testid="bond-analysis-today-focus"
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <div className={styles.footerMetricPanel}>
                <strong>{actionPnlDisplay}</strong>
                <span>{actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待返回"}</span>
                <div className={styles.footerEvidenceBlock}>
                  <div className={styles.footerChangeSplit}>
                    <span>市值 {formatSignedPct(marketValueMomPct)}</span>
                    <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : "—"}</span>
                  </div>
                  <div className={styles.footerActionBar}>
                    <span>市值变动与 DV01 变动用于核对动作归因字段返回范围。</span>
                    <Button
                      size="small"
                      type="text"
                      data-testid="bond-analysis-footer-open-action-attribution"
                      onClick={() => onOpenModuleDetail?.("action-attribution")}
                    >
                      打开动作归因
                    </Button>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="风险读面" title="返回字段" />}
              data-testid="bond-analysis-risk-guardrails"
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <div className={styles.footerRiskList}>
                {footerRiskRows.map((row) => (
                  <div key={row.label} className={styles.footerRiskRow}>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                  </div>
                ))}
                <div className={styles.footerEvidenceNote}>
                  只列已返回风险字段；缺失保持证据缺口，不延伸为审批或阈值结论。
                </div>
                <div className={styles.footerActionBar}>
                  <span>信用利差字段以下钻返回为准；缺失继续保留证据缺口。</span>
                  <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread-footer" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                    打开信用利差
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </section>
    </section>
  );
}
