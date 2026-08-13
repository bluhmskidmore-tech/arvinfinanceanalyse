import { useMemo } from "react";
import { Card } from "antd";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";
import { buildYieldCurveTermStructureChartOption } from "../lib/yieldCurveTermStructureChartOption";
import ReactECharts from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import {
  MaturityColumnChart,
  ProgressStack,
  SectionCardTitle,
} from "./BondAnalyticsCockpitPrimitives";
import { cardBodyStyle } from "./bondAnalyticsCockpitTokens";
import { curveHasReadout, curvePointHasReadout } from "./bondAnalyticsCockpitCurveZoneSupport";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const HOME_CURVE_LABELS: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

function formatCurveNumeric(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : value?.display || EM_DASH;
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
      textStyle: { fontSize: 11, color: nocturneTokens.color.inkMuted },
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
              交易日 {firstResolvedDate ?? readableCurves[0]?.trade_date_requested ?? EM_DASH} · vendor {vendorSummary || "待返回"}
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

export function ReferenceYieldCurvePanel({
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
                报告日 {reportDate || EM_DASH} · 曲线交易日 {resolvedDate ?? "待解析"}
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
