import { useMemo } from "react";
import { Card } from "antd";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";
import { buildYieldCurveTermStructureChartOption } from "../lib/yieldCurveTermStructureChartOption";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import {
  MaturityColumnChart,
  SectionCardTitle,
  type DistributionItem,
} from "./BondAnalyticsCockpitPrimitives";
import { cardBodyStyle } from "./bondAnalyticsCockpitTokens";
import { curveHasReadout, curvePointHasReadout } from "./bondAnalyticsCockpitCurveZoneSupport";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";
import zone from "./BondAnalyticsCockpitCurveZone.module.css";

const HOME_CURVE_LABELS: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

/* 三列决策区中的主图高度：保留曲线形态可读性，同时避免单卡拖长整行。 */
const CURVE_CHART_HEIGHT = 210;

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

/* source_version / vendor 原始 ID 属证据层（DESIGN §6 溯源分层）：只进 title 供复核，不进正文。 */
function buildCurveSourceReviewTitle(curves: YieldCurveTermStructureCurvePayload[]): string {
  const sourceParts = curves.map(
    (curve) => `${curveLabel(curve.curve_type)} 来源版本 ${curve.source_version || "待返回"}`,
  );
  const vendorNames = Array.from(
    new Set(curves.map((curve) => curve.vendor_name).filter(Boolean)),
  );
  return [
    ...sourceParts,
    vendorNames.length ? `vendor ${vendorNames.join(" / ")}` : "vendor 待返回",
  ].join("；");
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

  const lineSeries = base.series
    .filter(
      (series) =>
        series &&
        typeof series === "object" &&
        "type" in series &&
        series.type === "line",
    )
    /* 紧凑卡图例只留曲线名（「国债 收益率」→「国债」）：纵轴已标注收益率 (%)，
       后缀在窄图例里是冗余；仅改本紧凑视图，不动下钻完整图的序列名。 */
    .map((series) => ({
      ...series,
      name:
        "name" in series && typeof series.name === "string"
          ? series.name.replace(/ 收益率$/, "")
          : (series as { name?: string }).name,
    }));
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
      <BaseChart option={option} height={CURVE_CHART_HEIGHT} />
    </div>
  );
}

function ReferenceCurveReadout({
  curves,
  krdBucketCount = null,
  krdPending = false,
}: {
  curves: YieldCurveTermStructureCurvePayload[];
  krdBucketCount?: number | null;
  krdPending?: boolean;
}) {
  const readableCurves = useMemo(
    () => curves.filter(curveHasReadout).slice(0, 3),
    [curves],
  );

  if (readableCurves.length === 0) {
    const pendingRows = [
      {
        label: "正式曲线期限点",
        value: "待返回",
        detail: "收益率与日变动未返回",
      },
      {
        label: "正式 KRD",
        value:
          krdBucketCount !== null && krdBucketCount > 0
            ? `已返回 ${krdBucketCount} 桶`
            : krdPending
              ? "读取中"
              : "待返回",
        detail:
          krdBucketCount !== null && krdBucketCount > 0
            ? "明细见下钻 KRD 标签页"
            : "不由期限桶推导",
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
      <div data-testid="bond-analysis-yield-curve-empty" className={zone.pendingPanel}>
        <div className={zone.pendingHeader}>
          <strong>正式曲线 / KRD 读面待返回</strong>
          <span>当前未返回正式收益率曲线期限点与日变动，不用期限桶冒充 KRD，也不前端补造缺失点。</span>
        </div>
        <div className={zone.pendingList}>
          {pendingRows.map((row) => (
            <div key={row.label} className={zone.pendingRow}>
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
  const returnedPointCount = readableCurves.reduce(
    (total, curve) => total + curve.points.filter(curvePointHasReadout).length,
    0,
  );

  return (
    <div data-testid="bond-analysis-yield-curve-readout" className={zone.readout}>
      <div className={zone.readoutLead}>
        <strong className={zone.leadNames} title={buildCurveSourceReviewTitle(readableCurves)}>
          {readableCurves.map((curve) => curveLabel(curve.curve_type)).join(" / ")}
        </strong>
        <span className={zone.leadDelta} data-tone={largestDeltaTone}>
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
        </span>
      </div>
      <ReferenceCurveCompactChart curves={readableCurves} />
      <div className={zone.footerRow}>
        <span>返回曲线：<strong>{readableCurves.length} 条</strong></span>
        <span>展示期限点：<strong>{tenors.length} / {returnedPointCount}</strong></span>
        <small>只列后端返回可读点；空缺期限保持 —</small>
      </div>
      {/* 期限矩阵与曲线图信息重复：降级为折叠明细，主视觉留给曲线形态。 */}
      <details className={styles.curveMatrixDisclosure}>
        <summary className={styles.curveMatrixSummary}>
          <span>期限点明细</span>
          <small>收益率与日变动</small>
        </summary>
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
      </details>
    </div>
  );
}

export function ReferenceYieldCurvePanel({
  reportDate,
  maturityRows,
  curves,
  isLoading,
  hasError,
  krdBucketCount = null,
  krdPending = false,
}: {
  reportDate: string;
  maturityRows: DistributionItem[];
  curves: YieldCurveTermStructureCurvePayload[];
  isLoading: boolean;
  hasError: boolean;
  /** 正式 KRD 读面：null=未返回，数字=已返回桶数（明细见下钻 KRD 曲线风险标签页）。 */
  krdBucketCount?: number | null;
  krdPending?: boolean;
}) {
  const resolvedDate = curves.find((curve) => curve.trade_date_resolved)?.trade_date_resolved;
  const hasCurveData = curves.some(curveHasReadout);
  /* 曲线快照日落后报告日属 stale 形态（§6）：琥珀小徽标显式披露，不静默当作当日曲线。
     两值均为 ISO 日期串，字典序比较即日期序。 */
  const isCurveSnapshotStale = Boolean(
    resolvedDate && reportDate && resolvedDate < reportDate,
  );
  /* 已返回部分曲线时，逐条点名仍待返回的曲线（如 aaa_credit），缺口不静默。 */
  const pendingCurveLabels = hasCurveData
    ? curves.filter((curve) => !curveHasReadout(curve)).map((curve) => curveLabel(curve.curve_type))
    : [];
  const curveStatus: { text: string; tone: "ok" | "pending" | "warn" } = isLoading
    ? { text: "曲线期限点读取中", tone: "pending" }
    : hasError
      ? { text: "曲线接口暂未返回", tone: "warn" }
      : hasCurveData
        ? { text: "曲线期限点已返回", tone: "ok" }
        : { text: "曲线期限点待返回", tone: "pending" };

  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="曲线" title="收益率曲线 / KRD" />}
      data-testid="bond-analysis-yield-curve-panel"
      className={`${styles.referencePanelCard} ${styles.referenceCurveCard}`}
      styles={{ body: cardBodyStyle }}
    >
      <div className={styles.referenceCurveLayout}>
        <div className={styles.referenceCurveHero}>
          <div className={zone.statusHeader}>
            <div className={zone.statusTags}>
              <span className={zone.statusTag} data-tone={curveStatus.tone}>
                {curveStatus.text}
              </span>
              {isCurveSnapshotStale ? (
                <span
                  className={zone.statusTag}
                  data-tone="warn"
                  data-testid="bond-analysis-curve-stale-badge"
                  title={`曲线交易日 ${resolvedDate} 早于报告日 ${reportDate}：展示可得的最近快照，非报告日当日曲线`}
                >
                  快照滞后 {resolvedDate}
                </span>
              ) : null}
              {pendingCurveLabels.map((label) => (
                <span key={label} className={zone.statusTag} data-tone="pending">
                  {label} 待返回
                </span>
              ))}
              {hasCurveData ? (
                krdBucketCount !== null && krdBucketCount > 0 ? (
                  <span
                    className={zone.statusTag}
                    data-tone="ok"
                    title="正式 KRD 读面已返回，期限桶明细见下钻「KRD 曲线风险」标签页"
                  >
                    正式 KRD 已返回（{krdBucketCount} 桶）
                  </span>
                ) : (
                  <span
                    className={zone.statusTag}
                    data-tone="pending"
                    title="正式 KRD 不由期限桶推导，待后端返回读面"
                  >
                    {krdPending ? "正式 KRD 读取中" : "正式 KRD 待返回"}
                  </span>
                )
              ) : null}
            </div>
            <div className={zone.statusMeta}>
              报告日 {reportDate || EM_DASH} · 曲线交易日 {resolvedDate ?? "待解析"}
            </div>
          </div>
          <ReferenceCurveReadout
            curves={curves}
            krdBucketCount={krdBucketCount}
            krdPending={krdPending}
          />
        </div>
        <details className={styles.curveFallbackDisclosure}>
          <summary>
            <span>期限桶校验</span>
            <small>{hasCurveData ? "仅作组合暴露观察" : "正式曲线待返回"}</small>
          </summary>
          <div className={styles.curveFallbackBlock}>
            <div className={styles.curveFallbackHeader}>
              <strong>{hasCurveData ? "期限桶校验 / 暴露观察" : "期限桶占位 / 不冒充 KRD"}</strong>
              <span>{hasCurveData ? "期限桶只用于校验组合期限暴露，不等同于正式 KRD。" : "正式曲线缺口下，只保留期限桶观察，不把 maturity bucket 说成 KRD。"}</span>
            </div>
            <MaturityColumnChart items={maturityRows} emptyText="暂无期限结构" />
          </div>
        </details>
      </div>
    </Card>
  );
}
