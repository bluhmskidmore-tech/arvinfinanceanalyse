import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
} from "../types";
import { designTokens } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import {
  bundleSectionQuery,
  useBondAnalyticsCockpitBundleQuery,
} from "../lib/bondAnalyticsCockpitBundleQuery";
import { buildReturnDecompositionWaterfallOption } from "../lib/returnDecompositionWaterfallOption";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { BondAnalyticsYieldCurveTermStructureChart } from "./BondAnalyticsYieldCurveTermStructureChart";
import {
  DetailChartSkeleton,
  DetailEmptyNote,
} from "./BondAnalyticsDetailPrimitives";
import { ReturnDecompositionWaterfallChart } from "./ReturnDecompositionWaterfallChart";

const dt = designTokens;

export type BondAnalyticsOverviewMidChartsProps = {
  reportDate: string;
  periodType: PeriodType;
  assetClass: BondAnalyticsAssetClassFilter;
  accountingClass: BondAnalyticsAccountingClassFilter;
};

export function BondAnalyticsOverviewMidCharts({
  reportDate,
  periodType,
  assetClass,
  accountingClass,
}: BondAnalyticsOverviewMidChartsProps) {
  const client = useApiClient();
  const cockpitBundleQ = useBondAnalyticsCockpitBundleQuery(reportDate);
  const yieldCurveQ = bundleSectionQuery(cockpitBundleQ, "yield-curve-term-structure");
  const returnDecompositionOptions = {
    detail: "summary" as const,
    ...(assetClass !== "all" ? { assetClass } : {}),
    ...(accountingClass !== "all" ? { accountingClass } : {}),
  };
  const rdQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "return-decomposition",
      "summary",
      client.mode,
      reportDate,
      periodType,
      assetClass,
      accountingClass,
    ],
    queryFn: () =>
      client.getBondAnalyticsReturnDecomposition(reportDate, periodType, returnDecompositionOptions),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });

  const waterfallOption = useMemo(() => {
    const result = rdQuery.data?.result;
    if (!result) return null;
    const hasSeries = [
      result.carry,
      result.roll_down,
      result.rate_effect,
      result.spread_effect,
      result.fx_effect,
      result.convexity_effect,
      result.trading,
    ].some((value) => bondNumericRaw(value) !== null);
    return hasSeries ? buildReturnDecompositionWaterfallOption(result) : null;
  }, [rdQuery.data?.result]);

  return (
    <div data-testid="bond-analytics-overview-mid-charts" style={{ display: "grid", gap: dt.space[2] }}>
      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} lg={12}>
          <BondAnalyticsYieldCurveTermStructureChart
            reportDate={reportDate}
            bundledYieldCurveQuery={yieldCurveQ}
          />
        </Col>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="收益分解（瀑布）"
            data-testid="bond-analytics-overview-waterfall"
            styles={{ body: { paddingBlock: dt.space[2] } }}
          >
            {rdQuery.isError ? (
              <Alert
                type="warning"
                showIcon
                message="收益分解未就绪"
                description={
                  rdQuery.error instanceof Error ? rdQuery.error.message : "加载失败"
                }
              />
            ) : rdQuery.isPending ? (
              <DetailChartSkeleton
                height={280}
                testId="bond-analytics-overview-waterfall-loading"
              />
            ) : waterfallOption ? (
              <ReturnDecompositionWaterfallChart option={waterfallOption} height={280} />
            ) : (
              <DetailEmptyNote testId="bond-analytics-overview-waterfall-empty">
                暂无收益分解数据
              </DetailEmptyNote>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
