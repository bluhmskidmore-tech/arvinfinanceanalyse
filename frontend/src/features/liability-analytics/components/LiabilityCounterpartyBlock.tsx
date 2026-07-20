import { Card, Col, Row, Spin, Typography } from "antd";
import { useMemo } from "react";

import type { Numeric } from "../../../api/contracts";
import { ibChartTheme } from "../../../components/charts/chartTheme";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";
import { concentrationMetrics } from "../utils/concentration";
import { numericToYiNumeric, numericYuanRaw } from "../utils/money";

const { Text } = Typography;

const CHART_PALETTE = ibChartTheme.palette;
const CATEGORICAL = ibChartTheme.categoricalPalette;
const BAR_COLOR = CHART_PALETTE[0];
/** 银行扇区用分类色盘强调色，避免误用 palette 中的 --ib-down。 */
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

function bankNonBankFromByType(rows: LiabilityTypeRow[]): { name: string; value: number }[] {
  const bankRow = rows.find((row) => row.name === "Bank");
  const bank = rawYuanForChart(bankRow?.value);
  const nonBank = rows.reduce(
    (sum, row) => (row.name === "Bank" ? sum : sum + rawYuanForChart(row.value)),
    0,
  );
  return [
    { name: "银行", value: bank },
    { name: "非银行", value: nonBank },
  ];
}

export function LiabilityCounterpartyBlock({
  title = "资金来源依赖度（前十对手方）",
  subtitle = "口径：TYWL 负债端（对手方名称 × 余额；剔除“青岛银行股份有限公司”）。",
  totalValue,
  counterpartyRows,
  barRankingRows,
  byType,
  loading,
  errorText,
}: {
  title?: string;
  subtitle?: string;
  totalValue: Numeric | null;
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

  const { top10Share, hhiTimes10000 } = useMemo(() => {
    const weights = counterpartyRows
      .map((row) => numericYuanRaw(row.value))
      .filter((value): value is number => value !== null && Number.isFinite(value));
    return concentrationMetrics(weights);
  }, [counterpartyRows]);

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
          return `${row.name}<br/>余额：${balanceDisplay}<br/>占比：${shareDisplay}<br/>加权负债成本：${weightedCostDisplay}<br/>类型：${row.type || EM_DASH}`;
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
          return `${point.name}<br/>余额：${(point.value / 1e8).toFixed(2)} 亿<br/>占比：${pct}`;
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
                总规模：{numericToYiNumeric(totalValue)?.display ?? EM_DASH}
              </span>
              <span className="liability-cp-extra__line">
                Top10 占比：{(top10Share * 100).toFixed(2)}%
              </span>
              <span className="liability-cp-extra__line">HHI：{hhiTimes10000.toFixed(0)}</span>
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
        <Card size="small" title="机构类型结构">
          <Text type="secondary" className="liability-panel-caption--tight">
            银行 vs 非银行（稳定性视角）。
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
            银行占比越高，通常资金稳定性更强；非银行占比上升需关注期限错配与流动性压力。
          </Text>
        </Card>
      </Col>
    </Row>
  );
}
