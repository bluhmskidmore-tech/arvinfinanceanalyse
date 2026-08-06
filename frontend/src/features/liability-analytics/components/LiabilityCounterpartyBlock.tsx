import { Card, Col, Row, Spin, Typography } from "antd";
import { useMemo } from "react";

import type { Numeric } from "../../../api/contracts";
import { ibChartTheme } from "../../../components/charts/chartTheme";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";
import { numericToYiNumeric, numericYuanRaw } from "../utils/money";

const { Text } = Typography;

const CHART_PALETTE = ibChartTheme.palette;
const CATEGORICAL = ibChartTheme.categoricalPalette;
const BAR_COLOR = CHART_PALETTE[0];
const PIE_BANK = CATEGORICAL[0];
const PIE_NONBANK = CATEGORICAL[1] ?? CHART_PALETTE[1];
const PIE_EXTRA = CATEGORICAL;

export type LiabilityCpRow = {
  name: string;
  value: Numeric | null;
  share: Numeric | null;
  type: string;
  weightedCost: Numeric | null;
};

export type LiabilityTypeRow = {
  name: string;
  value: Numeric | null;
};

function truncateName(value: string, max = 10): string {
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function rawYuanForChart(value: Numeric | null | undefined): number {
  return numericYuanRaw(value) ?? 0;
}

function populationSummary(populationCount: number | null | undefined, isTruncated: boolean): string {
  if (populationCount === null || populationCount === undefined || populationCount < 0) {
    return EM_DASH;
  }
  if (isTruncated && populationCount > 0) {
    return `${populationCount} names (Top10 shown)`;
  }
  return `${populationCount} names`;
}

function bankNonBankFromByType(rows: LiabilityTypeRow[]): { name: string; value: number }[] {
  const bankRow = rows.find((row) => row.name === "Bank");
  const bank = rawYuanForChart(bankRow?.value);
  const nonBank = rows.reduce(
    (sum, row) => (row.name === "Bank" ? sum : sum + rawYuanForChart(row.value)),
    0,
  );
  return [
    { name: "Bank", value: bank },
    { name: "NonBank", value: nonBank },
  ];
}

export function LiabilityCounterpartyBlock({
  title = "Funding source concentration (Top10 counterparties)",
  subtitle = "Scope: TYWL liability-side counterparties, excluding self-counterparty rows.",
  totalValue,
  authoritativeTop10Share,
  authoritativeHhi,
  populationCount = null,
  isTruncated = false,
  counterpartyRows,
  barRankingRows,
  byType,
  loading,
  errorText,
}: {
  title?: string;
  subtitle?: string;
  totalValue: Numeric | null;
  authoritativeTop10Share: Numeric | null;
  authoritativeHhi: Numeric | null;
  populationCount?: number | null;
  isTruncated?: boolean;
  counterpartyRows: LiabilityCpRow[];
  barRankingRows?: LiabilityCpRow[];
  byType: LiabilityTypeRow[];
  loading: boolean;
  errorText: string | null;
}) {
  const ranked = useMemo(
    () => [...counterpartyRows].sort((a, b) => rawYuanForChart(b.value) - rawYuanForChart(a.value)),
    [counterpartyRows],
  );

  const top10Rows = useMemo(() => {
    if (barRankingRows && barRankingRows.length > 0) {
      return barRankingRows.slice(0, 10);
    }
    return ranked.slice(0, 10);
  }, [barRankingRows, ranked]);

  const donut = useMemo(() => bankNonBankFromByType(byType), [byType]);
  const reversedTop10 = useMemo(() => [...top10Rows].reverse(), [top10Rows]);

  const barOption: EChartsOption = useMemo(
    () => ({
      grid: { left: 120, right: 24, top: 16, bottom: 16 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const rows = params as { data: { row: LiabilityCpRow } }[];
          const row = rows?.[0]?.data?.row;
          if (!row) return "";
          const balanceDisplay = numericToYiNumeric(row.value)?.display ?? EM_DASH;
          const shareDisplay = row.share?.display ?? EM_DASH;
          const weightedCostDisplay = row.weightedCost?.display ?? EM_DASH;
          return `${row.name}<br/>Balance: ${balanceDisplay}<br/>Share: ${shareDisplay}<br/>Weighted cost: ${weightedCostDisplay}<br/>Type: ${row.type || EM_DASH}`;
        },
      },
      xAxis: { type: "value" },
      yAxis: {
        type: "category",
        data: reversedTop10.map((row) => truncateName(row.name)),
        axisLabel: { width: 110, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          data: reversedTop10.map((row) => ({
            value: numericToYiNumeric(row.value)?.raw ?? 0,
            row,
          })),
          itemStyle: { color: BAR_COLOR, borderRadius: [0, 2, 2, 0] },
        },
      ],
    }),
    [reversedTop10],
  );

  const pieOption: EChartsOption = useMemo(
    () => ({
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const point = params as { name: string; value: number };
          const total = numericYuanRaw(totalValue);
          const pct =
            total !== null && Number.isFinite(total) && total > 0
              ? `${((point.value / total) * 100).toFixed(2)}%`
              : EM_DASH;
          return `${point.name}<br/>Balance: ${(point.value / 1e8).toFixed(2)} yi<br/>Share: ${pct}`;
        },
      },
      series: [
        {
          type: "pie",
          radius: ["40%", "65%"],
          data: donut.map((item, index) => ({
            ...item,
            itemStyle: {
              color:
                donut.length <= 2
                  ? index === 0
                    ? PIE_BANK
                    : PIE_NONBANK
                  : PIE_EXTRA[index % PIE_EXTRA.length],
            },
          })),
        },
      ],
    }),
    [donut, totalValue],
  );

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={16}>
        <Card
          size="small"
          title={title}
          extra={
            <div className="liability-cp-extra">
              <span className="liability-cp-extra__line">
                Total size: {numericToYiNumeric(totalValue)?.display ?? EM_DASH}
              </span>
              <span className="liability-cp-extra__line" data-testid="liability-cp-top10-share">
                Top10 share: {authoritativeTop10Share?.display ?? EM_DASH}
              </span>
              <span className="liability-cp-extra__line" data-testid="liability-cp-hhi">
                HHI: {authoritativeHhi?.display ?? EM_DASH}
              </span>
              <span className="liability-cp-extra__line" data-testid="liability-cp-population">
                Population: {populationSummary(populationCount, isTruncated)}
              </span>
            </div>
          }
        >
          <Text type="secondary" className="liability-panel-caption--tight">
            {subtitle}
          </Text>
          {errorText ? (
            <Text type="danger" style={{ display: "block", marginTop: 8 }}>
              {errorText}
            </Text>
          ) : null}
          <div className="liability-chart-frame liability-chart-frame--bar">
            {loading ? (
              <div className="liability-chart-loading">
                <Spin />
              </div>
            ) : (
              <ReactECharts option={barOption} style={{ height: 320 }} notMerge lazyUpdate />
            )}
          </div>
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Card size="small" title="Institution mix">
          <Text type="secondary" className="liability-panel-caption--tight">
            Bank vs non-bank composition.
          </Text>
          <div className="liability-chart-frame liability-chart-frame--pie">
            {loading ? (
              <div className="liability-chart-loading">
                <Spin />
              </div>
            ) : (
              <ReactECharts option={pieOption} style={{ height: 280 }} notMerge lazyUpdate />
            )}
          </div>
          <Text type="secondary" className="liability-panel-caption--tight">
            Higher bank share usually implies more stable funding; rising non-bank share deserves liquidity review.
          </Text>
        </Card>
      </Col>
    </Row>
  );
}
