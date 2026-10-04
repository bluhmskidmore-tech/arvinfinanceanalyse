import { useMemo } from "react";
import type {
  BalanceMovementTrendMonth,
  BalanceMovementRow,
  BalanceZqtzMaturityStructure,
  BalanceMovementPayload,
} from "../../../api/contracts";
import { buildBalanceStructureEvolution } from "../lib/balanceMovementShareModel";
import { reconciliationConcernLabel } from "../lib/balanceMovementReconciliationModel";
import { EM_DASH } from "../../../utils/format";
import {
  buildBusinessCategoryMatrixRows,
  type BusinessMovementMatrixRow,
  basisThreeBucketSum,
  sumBusinessMatrixRowValues,
  toMovementDriver,
  type BalanceMovementDriver,
  isPreviousCalendarMonth,
  trendDelta,
  balanceMovementBuckets,
  trendBucket,
  aggregateBucketReconciliation,
  topBusinessLineMovesByMomAbs,
  topBusinessLineMovesByWindowAbs,
  buildZqtzAssetDetailRows,
  type ZqtzAssetDetailRow,
  sumPrimaryZqtzAssetDetailRows,
  uniqueNonEmptyStrings,
} from "../lib/balanceMovementBusinessModel";
import {
  finiteMetric,
  formatPct,
  formatSignedYiCell,
  sourceKindLabel,
  sourceNotePreview,
  formatSignedYiNumber,
  formatMetaList,
  drilldownStatusLabel,
} from "../lib/balanceMovementPresentation";
import type { CompactMaturityGroup } from "../components/BalanceMovementMaturityConcentration";
import {
  buildHistoricalAnomalyDiagnostics,
  buildExplanationClosure,
  type AnalysisDimensionCard,
  residualTone,
  coverageTone,
} from "../lib/balanceMovementDiagnostics";
import type { ApiEnvelope } from "../../../api/contracts";

export function useBalanceMovementViewModel(detailData: ApiEnvelope<BalanceMovementPayload> | undefined) {

  const rows = useMemo(
    () => detailData?.result.rows ?? [],
    [detailData?.result.rows],
  );
  const summary = detailData?.result.summary;
  const trendMonths = useMemo(
    () => detailData?.result.trend_months ?? [],
    [detailData?.result.trend_months],
  );
  const businessTrendMonths = useMemo(
    () => detailData?.result.business_trend_months ?? [],
    [detailData?.result.business_trend_months],
  );
  const accountingMatrixMonths = useMemo(() => [...trendMonths].reverse(), [trendMonths]);
  const businessMatrixMonths = useMemo(
    () => [...businessTrendMonths].reverse(),
    [businessTrendMonths],
  );
  const businessMatrixRows = useMemo(
    () => buildBusinessCategoryMatrixRows(businessMatrixMonths),
    [businessMatrixMonths],
  );
  const zqtzCalibrationAnalysis = detailData?.result.zqtz_calibration_analysis ?? null;
  const structureMigrationAnalysis =
    detailData?.result.structure_migration_analysis ?? null;
  const differenceAttributionWaterfall =
    detailData?.result.difference_attribution_waterfall ?? null;
  const basisMovementDecomposition =
    detailData?.result.basis_movement_decomposition ?? null;
  const zqtzMaturityStructure =
    detailData?.result.zqtz_maturity_structure ?? null;
  const zqtzConcentrationAnalysis =
    detailData?.result.zqtz_concentration_analysis ?? null;
  const resultMeta = detailData?.result_meta ?? null;
  const resultStatusReasons = resultMeta
    ? [
        resultMeta.quality_flag !== "ok" ? `质量标记 ${resultMeta.quality_flag}` : null,
        resultMeta.fallback_mode !== "none"
          ? `降级模式 ${resultMeta.fallback_mode}`
          : null,
        resultMeta.requested_report_date
          ? `请求报告日 ${resultMeta.requested_report_date}`
          : null,
        resultMeta.resolved_report_date
          ? `实际快照日 ${resultMeta.resolved_report_date}`
          : null,
        resultMeta.fallback_date ? `回退日期 ${resultMeta.fallback_date}` : null,
      ].filter((reason): reason is string => Boolean(reason))
    : [];
  const hasResultStatus = Boolean(
    resultMeta &&
      (resultMeta.quality_flag !== "ok" ||
        resultMeta.fallback_mode !== "none" ||
        Boolean(resultMeta.fallback_date) ||
        (Boolean(resultMeta.requested_report_date) &&
          Boolean(resultMeta.resolved_report_date) &&
          resultMeta.requested_report_date !== resultMeta.resolved_report_date)),
  );
  const balanceChangeTotal = summary?.balance_change_total;
  const hasBalanceChangeTotal =
    balanceChangeTotal !== null &&
    balanceChangeTotal !== undefined &&
    balanceChangeTotal !== "" &&
    Number.isFinite(Number(balanceChangeTotal));
  const accountingByReportDate = useMemo(() => {
    const map = new Map<string, BalanceMovementTrendMonth>();
    for (const month of accountingMatrixMonths) {
      map.set(month.report_date, month);
    }
    return map;
  }, [accountingMatrixMonths]);
  const businessMatrixAssetRows = useMemo(
    () =>
      businessMatrixRows.filter(
        (row) =>
          row.side === "asset" &&
          !row.key.startsWith("asset_zqtz_") &&
          row.key !== "asset_long_term_equity_investment",
      ),
    [businessMatrixRows],
  );
  const businessMatrixLiabilityRows = useMemo(
    () => businessMatrixRows.filter((row) => row.side === "liability"),
    [businessMatrixRows],
  );
  const businessProjectTableRows = useMemo((): BusinessMovementMatrixRow[] => {
    return [
      {
        key: "asset-total",
        label: "资产端合计",
        side: "total",
        sourceNote: "资产端合计 = AC + OCI + TPL + 同业资产；金融投资明细在上方单独页展示。",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => {
          const accountingTotal = basisThreeBucketSum(accountingByReportDate, month);
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          if (accountingTotal === undefined) {
            return interbankAssetTotal.value;
          }
          return interbankAssetTotal.value === null
            ? accountingTotal
            : accountingTotal + interbankAssetTotal.value;
        },
        getCellMeta: (month) => {
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          return interbankAssetTotal.hasMissingInputs ? { hasMissingInputs: true } : undefined;
        },
      },
      {
        key: "liability-total",
        label: "负债端合计",
        side: "total",
        sourceNote: "负债端同业业务行合计",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows).value,
        getCellMeta: (month) => {
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          return liabilityTotal.hasMissingInputs ? { hasMissingInputs: true } : undefined;
        },
      },
      {
        key: "net-total",
        label: "资产负债净额",
        side: "total",
        sourceNote: "资产端合计 + 负债端合计。",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => {
          const accountingTotal = basisThreeBucketSum(accountingByReportDate, month);
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          const assetTotal =
            accountingTotal === undefined
              ? interbankAssetTotal.value
              : interbankAssetTotal.value === null
                ? accountingTotal
                : accountingTotal + interbankAssetTotal.value;
          if (assetTotal === null || assetTotal === undefined) {
            return liabilityTotal.value;
          }
          return liabilityTotal.value === null ? assetTotal : assetTotal + liabilityTotal.value;
        },
        getCellMeta: (month) => {
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          return interbankAssetTotal.hasMissingInputs || liabilityTotal.hasMissingInputs
            ? { hasMissingInputs: true }
            : undefined;
        },
      },
    ];
  }, [accountingByReportDate, businessMatrixAssetRows, businessMatrixLiabilityRows]);
  const {
    structureShareTableRows,
    shareRowByReportMonth,
    chartRows: balanceStructureChartRows,
    balanceStructureInsight,
  } = useMemo(
    () => buildBalanceStructureEvolution(accountingMatrixMonths),
    [accountingMatrixMonths],
  );
  const currentTrendMonth = trendMonths[0];
  const previousTrendMonth = trendMonths[1];
  const rowByBucket = useMemo(
    () => new Map(rows.map((row) => [row.basis_bucket, row])),
    [rows],
  );
  const movementDrivers = useMemo(
    () =>
      rows
        .map(toMovementDriver)
        .sort((left, right) => Math.abs(right.balanceChange) - Math.abs(left.balanceChange)),
    [rows],
  );
  const movementDriverByBucket = useMemo(
    () => new Map(movementDrivers.map((driver) => [driver.bucket, driver])),
    [movementDrivers],
  );
  const topMovementDriver = movementDrivers[0];
  const maxShareShiftDriver = useMemo(
    () =>
      movementDrivers.filter(
        (
          driver,
        ): driver is BalanceMovementDriver & {
          shareDelta: number;
        } => driver.shareDelta !== null && Number.isFinite(driver.shareDelta),
      ).sort(
        (left, right) => Math.abs(right.shareDelta) - Math.abs(left.shareDelta),
      )[0],
    [movementDrivers],
  );

  const trendComparison = useMemo(() => {
    if (!currentTrendMonth || !previousTrendMonth) {
      return null;
    }
    if (
      !isPreviousCalendarMonth(
        currentTrendMonth.report_date,
        previousTrendMonth.report_date,
      )
    ) {
      return null;
    }
    const totalDelta = trendDelta(
      currentTrendMonth.current_balance_total,
      previousTrendMonth.current_balance_total,
    );
    if (totalDelta === null) {
      return null;
    }
    const drivers = balanceMovementBuckets
      .map((bucket) => {
        const delta = trendDelta(
          trendBucket(currentTrendMonth, bucket)?.current_balance,
          trendBucket(previousTrendMonth, bucket)?.current_balance,
        );
        return delta === null ? null : { bucket, delta };
      })
      .filter((driver): driver is { bucket: BalanceMovementRow["basis_bucket"]; delta: number } =>
        driver !== null,
      )
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
    return {
      drivers,
      previousReportDate: previousTrendMonth.report_date,
      totalDelta,
    };
  }, [currentTrendMonth, previousTrendMonth]);

  const reconAggregate = useMemo(() => aggregateBucketReconciliation(rows), [rows]);
  const summaryHasCompleteBuckets = summary?.bucket_count === balanceMovementBuckets.length;
  const summaryAllBucketsMatched =
    summary?.matched_bucket_count === balanceMovementBuckets.length;
  const reconciliationLabel =
    rows.length === 0
      ? "待数据"
      : !reconAggregate.hasExactBuckets || !summaryHasCompleteBuckets
        ? "分桶不完整"
        : reconAggregate.allMatched && summaryAllBucketsMatched
          ? "三桶一致"
          : reconciliationConcernLabel(reconAggregate.counts);
  const previousBalanceTotal = finiteMetric(summary?.previous_balance_total);
  const balanceChangeValue = finiteMetric(balanceChangeTotal);
  const balanceChangePct =
    previousBalanceTotal !== null && previousBalanceTotal !== 0 && balanceChangeValue !== null
      ? (balanceChangeValue / previousBalanceTotal) * 100
      : null;
  const compactMaturityGroups = useMemo<CompactMaturityGroup[]>(() => {
    type MaturityBucketKey = BalanceZqtzMaturityStructure["buckets"][number]["maturity_bucket"];
    const definitions: Array<{ key: string; label: string; buckets: MaturityBucketKey[] }> = [
      {
        key: "within-90d",
        label: "≤90天",
        buckets: ["overdue_or_matured", "<=30d", "31-90d"],
      },
      { key: "91d-1y", label: "91天–1年", buckets: ["91d-1y"] },
      { key: "1-3y", label: "1–3年", buckets: ["1-3y"] },
      { key: "over-3y", label: ">3年", buckets: ["3-5y", ">5y"] },
    ];
    return definitions.map((definition) => {
      const buckets = (zqtzMaturityStructure?.buckets ?? []).filter((bucket) =>
        definition.buckets.includes(bucket.maturity_bucket),
      );
      const currentValues = buckets.map((bucket) => finiteMetric(bucket.current_amount));
      const deltaValues = buckets.map((bucket) => finiteMetric(bucket.delta_amount));
      const shareValues = buckets.map((bucket) => finiteMetric(bucket.share_pct));
      return {
        key: definition.key,
        label: definition.label,
        currentAmount:
          buckets.length > 0 && currentValues.every((value): value is number => value !== null)
            ? currentValues.reduce((total, value) => total + value, 0)
            : null,
        deltaAmount:
          buckets.length > 0 && deltaValues.every((value): value is number => value !== null)
            ? deltaValues.reduce((total, value) => total + value, 0)
            : null,
        sharePct:
          buckets.length > 0 && shareValues.every((value): value is number => value !== null)
            ? shareValues.reduce((total, value) => total + value, 0)
            : null,
      };
    });
  }, [zqtzMaturityStructure]);
  const issuerConcentration = useMemo(
    () =>
      zqtzConcentrationAnalysis?.dimensions.find(
        (dimension) => dimension.dimension === "issuer_name",
      ) ?? null,
    [zqtzConcentrationAnalysis],
  );
  const businessTopMomMoves = useMemo(
    () => topBusinessLineMovesByMomAbs(businessMatrixMonths, businessMatrixRows, 5),
    [businessMatrixMonths, businessMatrixRows],
  );
  const businessTopSixMonthMoves = useMemo(
    () =>
      topBusinessLineMovesByWindowAbs(
        businessMatrixMonths,
        businessMatrixRows,
        5,
        Math.max(1, businessMatrixMonths.length - 1),
      ),
    [businessMatrixMonths, businessMatrixRows],
  );
  const historicalAnomalyDiagnostics = useMemo(
    () =>
      buildHistoricalAnomalyDiagnostics({
        trendMonths,
        businessTrendMonths,
        businessRows: businessMatrixRows,
      }),
    [businessMatrixRows, businessTrendMonths, trendMonths],
  );
  const zqtzAssetDetailRows = useMemo(
    () => buildZqtzAssetDetailRows(businessMatrixMonths),
    [businessMatrixMonths],
  );
  const zqtzAssetDetailSummaryRow = useMemo<ZqtzAssetDetailRow | null>(() => {
    if (zqtzAssetDetailRows.length === 0) {
      return null;
    }
    return {
      key: "zqtz-detail-summary",
      label: "汇总",
      sourceNote: "按本表非“其中”明细加总，避免重复计算下级项目。",
      isSubItem: false,
      valueKind: "amount",
      getValue: (month) => sumPrimaryZqtzAssetDetailRows(month, zqtzAssetDetailRows).value,
      getCellMeta: (month) => {
        const summary = sumPrimaryZqtzAssetDetailRows(month, zqtzAssetDetailRows);
        return summary.hasMissingInputs ? { hasMissingInputs: true } : undefined;
      },
    };
  }, [zqtzAssetDetailRows]);
  const trendMoMDriverBucket = trendComparison?.drivers[0]?.bucket;
  const structureShareDriverBucket = maxShareShiftDriver?.bucket;
  const structureDriverHint = useMemo(() => {
    if (!trendMoMDriverBucket || !structureShareDriverBucket) {
      return null;
    }
    if (trendMoMDriverBucket === structureShareDriverBucket) {
      return null;
    }
    return `「变动额」环比主导为 ${trendMoMDriverBucket}，「占比变化（pp）」主导为 ${structureShareDriverBucket}；二者可同时成立。`;
  }, [trendMoMDriverBucket, structureShareDriverBucket]);

  const unsupportedWaterfallComponents = useMemo(
    () =>
      differenceAttributionWaterfall?.components.filter(
        (component) => component.is_supported === false,
      ) ?? [],
    [differenceAttributionWaterfall],
  );
  const residualWaterfallComponent = useMemo(
    () => differenceAttributionWaterfall?.components.find((component) => component.is_residual),
    [differenceAttributionWaterfall],
  );
  const explanationClosure = useMemo(
    () =>
      buildExplanationClosure({
        waterfall: differenceAttributionWaterfall,
        summary: detailData?.result.summary ?? null,
      }),
    [differenceAttributionWaterfall, detailData?.result.summary],
  );
  const analysisDimensionCards = useMemo<AnalysisDimensionCard[]>(() => {
    const businessTopMove = businessTopMomMoves[0];
    const unsupportedLabels = unsupportedWaterfallComponents.map((component) => component.component_label);
    const maturityCoverage = zqtzMaturityStructure
      ? formatPct(zqtzMaturityStructure.meta.coverage_pct)
      : EM_DASH;
    const concentrationCoverage = zqtzConcentrationAnalysis
      ? formatPct(zqtzConcentrationAnalysis.meta.coverage_pct)
      : EM_DASH;
    return [
      {
        key: "business",
        title: "业务品类 Top 变动",
        metric: businessTopMove
          ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
          : "暂无连续业务行",
        detail: businessTopMove
          ? `${sourceKindLabel(businessTopMove.sourceKind)} · ${sourceNotePreview(businessTopMove.sourceNote)}`
          : "需要至少两个连续报告月。",
        href: "#balance-movement-analysis-business-summary-anchor",
        tags: businessTopMove
          ? [{ label: "主导变动", tone: "info" }]
          : [{ label: "样本不足", tone: "unknown" }],
        evidence: [
          {
            label: "维度字段",
            value: "业务趋势月 / 品类衍生行",
            note: "business_trend_months / product category derived rows",
          },
          {
            label: "Top 变动",
            value: businessTopMove
              ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
              : EM_DASH,
          },
          {
            label: "来源说明",
            value: businessTopMove ? sourceNotePreview(businessTopMove.sourceNote) : "样本不足",
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
        ],
      },
      {
        key: "basis",
        title: "AC / OCI / FVTPL",
        metric: topMovementDriver
          ? `${topMovementDriver.bucket} ${formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿`
          : "暂无分桶变动",
        detail: topMovementDriver
          ? `贡献 ${formatPct(topMovementDriver.contributionPct)} · 期末占比 ${formatPct(topMovementDriver.currentBalancePct)}`
          : "等待 AC/OCI/TPL 读模型返回。",
        href: "#balance-movement-analysis-basis-anchor",
        tags: [
          { label: "主导分桶", tone: "info" },
          ...(trendMoMDriverBucket && structureShareDriverBucket && trendMoMDriverBucket !== structureShareDriverBucket
            ? [{ label: "结构迁移", tone: "warn" as const }]
            : []),
        ],
        evidence: [
          {
            label: "维度字段",
            value: "分桶 / 余额变动 / 贡献占比",
            note: "rows[].basis_bucket / balance_change / contribution_pct",
          },
          { label: "主导分桶", value: topMovementDriver?.bucket ?? EM_DASH },
          { label: "规则版本", value: resultMeta?.rule_version ?? EM_DASH },
          { label: "源版本", value: resultMeta?.source_version ?? EM_DASH },
        ],
      },
      {
        key: "residual",
        title: "对账残差",
        metric: residualWaterfallComponent
          ? `${formatSignedYiCell(residualWaterfallComponent.amount)} 亿`
          : "暂无残差项",
        detail:
          unsupportedLabels.length > 0
            ? `${unsupportedLabels.join("、")} 未支持，不反推`
            : "当前瀑布未返回待补口径。",
        href: "#balance-movement-analysis-residual-anchor",
        tags: [
          {
            label: unsupportedLabels.length > 0 ? "口径待补" : "残差闭合",
            tone: residualTone(explanationClosure?.residualRatioPct ?? null, unsupportedLabels.length),
          },
        ],
        evidence: [
          {
            label: "维度字段",
            value: "差异归因瀑布组件",
            note: "difference_attribution_waterfall.components",
          },
          {
            label: "残差",
            value: residualWaterfallComponent
              ? `${formatSignedYiCell(residualWaterfallComponent.amount)} 亿`
              : EM_DASH,
          },
          {
            label: "未支持项",
            value: unsupportedLabels.join("、") || "无",
            note: "未支持，不反推",
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
          { label: "规则版本", value: resultMeta?.rule_version ?? EM_DASH },
          { label: "源版本", value: resultMeta?.source_version ?? EM_DASH },
          { label: "使用表", value: formatMetaList(resultMeta?.tables_used) },
          {
            label: "证据行数",
            value:
              resultMeta?.evidence_rows === null || resultMeta?.evidence_rows === undefined
                ? EM_DASH
                : String(resultMeta.evidence_rows),
          },
          { label: "限制", value: "估值差和外币折算差没有可闭合字段，不在前端反算。" },
        ],
      },
      {
        key: "coverage",
        title: "期限 / 集中度覆盖",
        metric: `期限 ${maturityCoverage} / 集中度 ${concentrationCoverage}`,
        detail: `期限 ${drilldownStatusLabel(zqtzMaturityStructure?.meta.status)} · 集中度 ${drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status)}`,
        href: "#balance-movement-analysis-coverage-anchor",
        tags: [
          {
            label: `期限覆盖`,
            tone: coverageTone(zqtzMaturityStructure?.meta.coverage_pct),
          },
          {
            label: `集中度覆盖`,
            tone: coverageTone(zqtzConcentrationAnalysis?.meta.coverage_pct),
          },
        ],
        evidence: [
          { label: "期限覆盖", value: maturityCoverage },
          { label: "集中度覆盖", value: concentrationCoverage },
          {
            label: "期限状态",
            value: drilldownStatusLabel(zqtzMaturityStructure?.meta.status),
          },
          {
            label: "集中度状态",
            value: drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status),
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
        ],
      },
    ];
  }, [
    businessTopMomMoves,
    explanationClosure,
    resultMeta,
    residualWaterfallComponent,
    structureShareDriverBucket,
    topMovementDriver,
    trendMoMDriverBucket,
    unsupportedWaterfallComponents,
    zqtzConcentrationAnalysis,
    zqtzMaturityStructure,
  ]);

  const governanceMeta = useMemo(() => {
    const reportDate = detailData?.result.report_date ?? "";
    const ruleVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.rule_version ?? "")));
    const sourceVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.source_version ?? "")));
    return { reportDate, ruleVersions, sourceVersions };
  }, [detailData?.result.report_date, rows]);

  return {
    businessTopMomMoves,
    topMovementDriver,
    residualWaterfallComponent,
    unsupportedWaterfallComponents,
    zqtzMaturityStructure,
    zqtzConcentrationAnalysis,
    analysisDimensionCards,
    hasResultStatus,
    resultMeta,
    resultStatusReasons,
    summary,
    balanceChangePct,
    movementDrivers,
    reconciliationLabel,
    hasBalanceChangeTotal,
    compactMaturityGroups,
    issuerConcentration,
    rows,
    balanceStructureChartRows,
    structureShareTableRows,
    balanceStructureInsight,
    structureMigrationAnalysis,
    differenceAttributionWaterfall,
    explanationClosure,
    basisMovementDecomposition,
    zqtzCalibrationAnalysis,
    businessMatrixMonths,
    balanceChangeTotal,
    structureDriverHint,
    rowByBucket,
    movementDriverByBucket,
    businessTopSixMonthMoves,
    zqtzAssetDetailRows,
    zqtzAssetDetailSummaryRow,
    businessTrendMonths,
    businessMatrixLiabilityRows,
    businessProjectTableRows,
    currentTrendMonth,
    previousTrendMonth,
    governanceMeta,
    businessMatrixAssetRows,
    shareRowByReportMonth,
    historicalAnomalyDiagnostics,
  };
}

export type BalanceMovementViewModel = ReturnType<typeof useBalanceMovementViewModel>;
