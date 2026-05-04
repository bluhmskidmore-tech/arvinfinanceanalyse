import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Spin } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
} from "../types";
import { designTokens } from "../../../theme/designSystem";
import { buildReturnDecompositionWaterfallOption } from "../lib/returnDecompositionWaterfallOption";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { BondAnalyticsYieldCurveTermStructureChart } from "./BondAnalyticsYieldCurveTermStructureChart";
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
  const rdQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "return-decomposition-overview",
      client.mode,
      reportDate,
      periodType,
      assetClass,
      accountingClass,
    ],
    queryFn: () =>
      assetClass === "all" && accountingClass === "all"
        ? client.getBondAnalyticsReturnDecomposition(reportDate, periodType)
        : client.getBondAnalyticsReturnDecomposition(reportDate, periodType, {
            ...(assetClass !== "all" ? { assetClass } : {}),
            ...(accountingClass !== "all" ? { accountingClass } : {}),
          }),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });

  const waterfallOption = useMemo(
    () => (rdQuery.data?.result ? buildReturnDecompositionWaterfallOption(rdQuery.data.result) : null),
    [rdQuery.data?.result],
  );

  return (
    <div data-testid="bond-analytics-overview-mid-charts" style={{ display: "grid", gap: dt.space[2] }}>
      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} lg={12}>
          <BondAnalyticsYieldCurveTermStructureChart reportDate={reportDate} />
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
              <div style={{ display: "flex", justifyContent: "center", padding: dt.space[6] }}>
                <Spin />
              </div>
            ) : waterfallOption ? (
              <ReturnDecompositionWaterfallChart option={waterfallOption} height={280} />
            ) : (
              <div
                style={{
                  border: `1px dashed ${dt.color.neutral[300]}`,
                  borderRadius: dt.radius.md,
                  padding: dt.space[4],
                  textAlign: "center",
                  color: dt.color.neutral[500],
                  fontSize: dt.fontSize[13],
                }}
              >
                暂无收益分解数据
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
