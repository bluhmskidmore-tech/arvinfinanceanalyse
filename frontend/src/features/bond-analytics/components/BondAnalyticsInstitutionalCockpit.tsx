import { useMemo, type CSSProperties } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card } from "antd";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import type {
  AssetStructureItem,
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
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type { ActionAttributionResponse } from "../types";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  BOND_ANALYTICS_MACRO_BAR_SERIES,
  buildMacroPointForDeltaDisplay,
  coalesceMacroSeriesDelta,
} from "../lib/bondAnalyticsMacroSeries";
import { formatBp, formatPct, formatWan, formatYi } from "../utils/formatters";
import { panelStyle } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const dt = designTokens;
const infoAccent = dt.color.info[500];
const gradBar = `linear-gradient(90deg, ${dt.color.info[300]} 0%, ${infoAccent} 100%)`;
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

function isFiniteNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return Number.isFinite(n) ? n : Number.NaN;
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
  detail?: string;
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
    const rawDv01 = Math.abs(bondNumericRaw(row.payload?.total_dv01));
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
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
}) {
  const leadHolding = unavailable ? null : holdings[0] ?? null;
  const leadName = leadHolding
    ? leadHolding.instrument_name ?? leadHolding.instrument_code
    : unavailable
      ? "读面暂未返回"
      : "暂无持仓明细";
  const leadDetail = leadHolding ? leadHolding.instrument_code : undefined;
  const statusLabel = unavailable ? "读面暂未返回" : `${holdings.length} 只可见`;

  return (
    <div data-testid="bond-analysis-holdings-mobile-readout" className={styles.mobileTableReadout}>
      <div className={styles.mobileReadoutHeader}>
        <span>前十大持仓</span>
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

function ReferenceKpiTile({
  label,
  value,
  detail,
  status,
  tone = "default",
}: {
  label: string;
  value: string;
  detail: string;
  status?: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div className={styles.referenceKpiTile}>
      <div className={styles.referenceKpiHeader}>
        <div className={styles.referenceKpiLabel}>{label}</div>
        {status ? <span>{status}</span> : null}
      </div>
      <div
        className={styles.referenceKpiValue}
        data-tone={tone}
      >
        {value}
      </div>
      <div className={styles.referenceKpiDetail}>{detail}</div>
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
    },
    {
      label: "曲线证据",
      value: hasCurveReadout ? "正式曲线可读" : "正式曲线待返回",
      detail: hasCurveReadout ? "返回字段：期限点收益率与日变动" : "返回字段：期限桶仅作暴露观察",
      missing: hasCurveReadout ? "缺失项：正式 KRD" : "缺失项：正式曲线 / 正式 KRD",
    },
    {
      label: "信用证据",
      value: Number.isFinite(spreadMedianBp) || Number.isFinite(creditWeight) ? "已返回" : "待返回",
      detail: `返回字段：${buildReadoutFacts({ duration: Number.NaN, creditWeight, spreadMedianBp }).join(" · ") || "—"}`,
      missing: `缺失项：${creditMissing.length > 0 ? creditMissing.join(" / ") : "—"}`,
    },
    {
      label: "资金证据",
      value: hasDv01Readout ? "DV01已返回" : "DV01待返回",
      detail: `返回字段：组合 DV01 ${dv01Display}`,
      missing: hasDv01Readout ? "缺失项：—" : "缺失项：DV01",
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
          <div key={row.label} className={styles.referenceJudgmentRow}>
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

function ReferenceCurveReadout({
  curves,
}: {
  curves: YieldCurveTermStructureCurvePayload[];
}) {
  const readableCurves = curves.filter(curveHasReadout).slice(0, 3);

  if (readableCurves.length === 0) {
    return (
      <div data-testid="bond-analysis-yield-curve-empty" className={styles.curvePendingPanel}>
        <strong>正式曲线 / KRD 读面待返回</strong>
        <span>当前未返回正式收益率曲线期限点与日变动，不用期限桶冒充 KRD，也不前端补造缺失点。</span>
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
                background: item.color ?? gradBar,
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
              background: item.color ?? gradBar,
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
    const color = item.color ?? [dt.color.primary[600], dt.color.info[500], dt.color.success[500], dt.color.warning[500]][index % 4];
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
        {items.slice(0, 5).map((item) => (
          <div key={item.key} className={styles.referenceDonutLegendRow}>
            <span style={{ background: item.color ?? dt.color.primary[500] }} />
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
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
}) {
  if (unavailable) {
    return <div className={styles.tableEmpty}>{TOP_HOLDINGS_HOME_NOTE}</div>;
  }

  if (holdings.length === 0) {
    return <div className={styles.tableEmpty}>暂无持仓明细</div>;
  }

  return (
    <div className={styles.holdingsTableRows}>
      {holdings.map((item) => (
        <div key={item.instrument_code} className={styles.holdingsTableRow}>
          <div className={styles.holdingNameCell}>
            <strong>{item.instrument_name ?? item.instrument_code}</strong>
            <span>{item.instrument_code}</span>
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

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  actionAttribution = null,
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

  const [
    headlineQ,
    _spreadQ,
    maturityQ,
    holdingsQ,
    portfolioHlQ,
    assetStructureQ,
    riskQ,
    industryQ,
  ] = useQueries({
    queries: [
      {
        queryKey: apiQueryKeys.bondDashboardHeadline(client.mode, dashboardReportDate),
        queryFn: () => client.getBondDashboardHeadlineKpis(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "spread", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardSpreadAnalysis(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "maturity", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardMaturityStructure(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "holdings", client.mode, dashboardReportDate],
        queryFn: () => client.getBondAnalyticsTopHoldings(dashboardReportDate, 10),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(client.mode, dashboardReportDate),
        queryFn: () => client.getBondAnalyticsPortfolioHeadlines(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "asset-structure", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardAssetStructure(dashboardReportDate, "bond_type"),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "risk-indicators", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardRiskIndicators(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "industry-distribution", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardIndustryDistribution(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
    ],
  });
  const dv01AccountingQueries = useQueries({
    queries: DV01_ACCOUNTING_CLASSES.map((item) => ({
      queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
        client.mode,
        dashboardReportDate,
        item.value,
        DV01_HOME_TOP_N,
        DV01_HOME_SHOCK_BPS,
      ),
      queryFn: () =>
        client.getBondAnalyticsDv01Risk(dashboardReportDate, {
          accountingClass: item.value,
          topN: DV01_HOME_TOP_N,
          shockBps: DV01_HOME_SHOCK_BPS,
        }),
      enabled: Boolean(dashboardReportDate),
    })),
  });
  const yieldCurveQ = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsYieldCurveTermStructure(
      client.mode,
      dashboardReportDate,
      HOME_YIELD_CURVE_TYPES,
    ),
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(dashboardReportDate, {
        curveTypes: HOME_YIELD_CURVE_TYPES,
      }),
    enabled: Boolean(dashboardReportDate),
    retry: false,
    staleTime: 60_000,
  });

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
      .map(({ item, rawMarketValue }) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        color: dt.color.success[500],
      }));
  }, [maturityQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const dashboardAssetItems = useMemo(() => {
    const palette = [dt.color.primary[700], dt.color.info[500], dt.color.success[600], dt.color.warning[500], dt.color.neutral[400]];
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
    const palette = [dt.color.primary[700], dt.color.info[500], dt.color.success[600], dt.color.warning[500], dt.color.neutral[500]];
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
    Number.isFinite(totalActionPnl) && totalActionPnl !== 0
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
    color: [dt.color.primary[600], dt.color.info[500], dt.color.success[500], dt.color.warning[500], dt.color.neutral[500], dt.color.primary[300]][index % 6],
  }));
  const durationRows = maturityItems.slice(0, 3).map((item) => ({
    ...item,
    detail: `市值 ${item.caption}`,
  }));
  const riskRows = [
    {
      label: "组合久期",
      value: riskQ.data?.result ? formatDurationDisplay(riskQ.data.result.weighted_duration) : durationDisplay,
      detail: "来自风险指标读面",
    },
    {
      label: "组合 DV01",
      value: dv01Display,
      detail: "利率敏感度",
    },
    {
      label: "信用占比",
      value: riskQ.data?.result ? formatPct(riskQ.data.result.credit_ratio) : creditWeightDisplay,
      detail: "信用债市值占比",
    },
    {
      label: "利差 DV01",
      value: riskQ.data?.result ? formatWan(riskQ.data.result.total_spread_dv01) : "—",
      detail: "信用利差敏感度",
    },
  ];
  const topbarReportDate = dashboardReportDate || reportDate || "—";
  const topbarReportStatus = isDashboardDateFallback
    ? `快照回退 ${dashboardReportDate || "—"}`
    : dashboardReportDate
      ? "报告日匹配"
      : "报告日待确认";
  const topbarReadoutStatus = headlineQ.isPending ? "加载中" : headline ? "已返回" : "待返回";
  const topbarReadoutDetail = headlineQ.isPending
    ? "首屏 KPI 加载中"
    : headline
      ? "首屏 KPI 已返回"
      : "首屏 KPI 待返回";

  return (
    <section data-testid="bond-analysis-phase3-cockpit" className={styles.phaseSection}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <section data-testid="bond-analysis-reference-dashboard" className={styles.referenceDashboard}>
        <div data-testid="bond-analysis-reference-topbar" className={styles.referenceTopbar}>
          <div className={styles.referenceTopbarIdentity}>
            <div className={styles.holdingsKicker}>债券分析</div>
            <h2 className={styles.referenceTitle}>固定收益交易台</h2>
            <p className={styles.referenceSubtitle}>
              报告日 {topbarReportDate} · 首屏只展示后端读面与已确认下钻入口。
            </p>
          </div>
          <div className={styles.referenceTopbarReadout}>
            <span>核心读面</span>
            <strong>{conclusion.body}</strong>
            <small>{conclusion.detail}</small>
          </div>
          <div className={styles.referenceTopbarStatus}>
            <div data-testid="bond-analysis-topbar-status-item">
              <span>报告日</span>
              <strong>{topbarReportStatus}</strong>
              <small>{topbarReportDate}</small>
            </div>
            <div data-testid="bond-analysis-topbar-status-item">
              <span>首屏 KPI</span>
              <strong>{topbarReadoutStatus}</strong>
              <small>{topbarReadoutDetail}</small>
            </div>
          </div>
        </div>

        <div data-testid="bond-analysis-daily-judgment" className={styles.referenceSignalStrip}>
          <div data-testid="bond-analysis-cockpit-conclusion" className={styles.referenceSignalConclusion}>
            <div className={styles.referenceSignalLead}>
              <div className={styles.conclusionKicker}>证据展开 · 固定收益读面</div>
              <strong>首屏读面拆解</strong>
              <span>{conclusion.detail}</span>
            </div>
            <div className={styles.referenceSignalSummary}>
              <div>
                <span>久期</span>
                <strong className={styles.referenceSignalMetric}>{durationDisplay}</strong>
              </div>
              <div>
                <span>信用利差</span>
                <strong className={styles.referenceSignalMetric}>{formatSpreadBpDisplay(spreadMedian)}</strong>
              </div>
              <div>
                <span>信用占比</span>
                <strong className={styles.referenceSignalMetric}>{creditWeightDisplay}</strong>
              </div>
            </div>
          </div>
          <div className={styles.deskVerdictGrid}>
            {deskVerdictFields.map((field) => (
              <div key={field.label} className={styles.deskVerdictField}>
                <span>{field.label}</span>
                <strong>{field.value}</strong>
                <small>{field.detail}</small>
              </div>
            ))}
          </div>
        </div>

        <ReferenceMarketTicker series={macroSeries} unavailable={macroUnavailable} />

        <div className={styles.holdingsKpiRail}>
          <div data-testid="bond-analysis-kpi-ribbon" className={styles.holdingsKpiGrid}>
            <ReferenceKpiTile label="久期" value={durationDisplay} detail={leadMaturity ? `最重期限桶 ${leadMaturity.label}` : "期限结构待读面"} status={Number.isFinite(dur) ? "已读" : "待读面"} />
            <ReferenceKpiTile label="组合到期收益率" value={k ? formatPct(k.weighted_ytm) : "—"} detail={previousK ? `上期 ${formatPct(previousK.weighted_ytm)}` : "收益率待读面"} status={k ? "已读" : "待读面"} />
            <ReferenceKpiTile label="信用利差" value={formatSpreadBpDisplay(spreadMedian)} detail="信用利差中位数" status={Number.isFinite(spreadMedianBp) ? "已读" : "待读面"} />
            <ReferenceKpiTile label="DV01" value={dv01Display} detail="风险指标读面" status={hasDv01Readout ? "已读" : "待读面"} />
            <ReferenceKpiTile label="Carry+Roll" value="—" detail="接口未返回 / 待读面" status="缺口" />
            <ReferenceKpiTile label="月度收益" value={actionPnlDisplay} detail={actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待读面"} status={actionAttribution ? "已读" : "待读面"} tone={actionPnlTone} />
            <ReferenceKpiTile label="总收益" value={unrealizedPnlDisplay} detail={`较上期 ${formatSignedPct(unrealizedPnlMomPct)}`} status={k ? "已读" : "待读面"} tone={unrealizedPnlTone} />
          </div>
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
            title={<SectionCardTitle eyebrow="持仓证据明细" title="前十大返回持仓" />}
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
            <HoldingsMobileReadout holdings={topHoldings} unavailable={topHoldingsUnavailable} />
            <div data-testid="bond-analysis-holdings-evidence-strip" className={styles.holdingsEvidenceStrip}>
              <div>
                <span>返回持仓</span>
                <strong>{topHoldingsUnavailable ? "待返回" : `${topHoldings.length} 条`}</strong>
                <small>仅展示后端返回的前十大持仓。</small>
              </div>
              <div>
                <span>评级缺口</span>
                <strong>{topHoldingsUnavailable ? "—" : `${holdingRatingGapCount} 条`}</strong>
                <small>缺失评级保持 —，不补造评级。</small>
              </div>
              <div>
                <span>数值缺口</span>
                <strong>{topHoldingsUnavailable ? "—" : `${holdingMetricGapCount} 项`}</strong>
                <small>市值 / 收益率 / 久期 / 权重。</small>
              </div>
            </div>
            <div
              data-testid="bond-analysis-holdings-raw-grid"
              className={styles.holdingsTable}
            >
              <div className={styles.holdingsTableHeader}>
                <span>债券</span>
                <span>券种</span>
                <span>评级</span>
                <span>市值</span>
                <span>收益率</span>
                <span>久期</span>
                <span>权重</span>
              </div>
              <HoldingRows holdings={topHoldings} unavailable={topHoldingsUnavailable} />
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

        <div className={styles.referenceFooterGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="收益证据" title="本期估值收益" />}
            data-testid="bond-analysis-summary-card"
            style={dashboardCardStyle}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerMetricPanel}>
              <strong>{unrealizedPnlDisplay}</strong>
              <span>{Number.isFinite(unrealizedPnlMomPct) ? `较上期 ${formatSignedPct(unrealizedPnlMomPct)}` : "收益走势明细待读面返回"}</span>
              <div data-testid="bond-analysis-return-trend-boundary" className={styles.footerEvidenceNote}>
                未返回收益时序明细时不绘制趋势占位。
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-return-decomposition" onClick={() => onOpenModuleDetail?.("return-decomposition")}>
                打开收益拆解
              </Button>
            </div>
          </Card>

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
              <div className={styles.footerChangeSplit}>
                <span>市值 {formatSignedPct(marketValueMomPct)}</span>
                <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : "—"}</span>
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-action-attribution-footer" onClick={() => onOpenModuleDetail?.("action-attribution")}>
                打开动作归因
              </Button>
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
              {riskRows.slice(0, 3).map((row) => (
                <div key={row.label}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </div>
              ))}
              <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread-footer" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                打开信用利差
              </Button>
            </div>
          </Card>
        </div>
      </section>
    </section>
  );
}
