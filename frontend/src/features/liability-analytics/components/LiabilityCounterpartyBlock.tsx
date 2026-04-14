import { Card, Col, Row, Spin, Typography } from "antd";
import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { concentrationMetrics } from "../utils/concentration";

const { Text } = Typography;

const LIAB_RED = "#cf1322";
const PIE_BANK = LIAB_RED;
const PIE_NONBANK = "#10239e";
const PIE_EXTRA = ["#13c2c2", "#fa8c16", "#52c41a", "#722ed1", "#eb2f96"];

export type LiabilityCpRow = {
  name: string;
  valueYuan: number;
  pct: number;
  type: string;
  weightedCost: number | null;
};

function truncateName(s: string, n = 10): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function bankNonBankFromByType(by: { name: string; value: number }[]): { name: string; value: number }[] {
  const bank = by.find((x) => x.name === "Bank")?.value || 0;
  const nonbank = by.reduce((sum, x) => (x.name === "Bank" ? sum : sum + (x.value || 0)), 0);
  return [
    { name: "银行", value: bank },
    { name: "非银行", value: nonbank },
  ];
}

export function LiabilityCounterpartyBlock({
  title = "资金来源依赖度（Top 10 对手方）",
  subtitle = "口径：TYWL 负债端（对手方名称 × 余额；剔除「青岛银行股份有限公司」）。",
  totalValueYuan,
  /** 全量对手方行（与明细表一致）；集中度 HHI / Top10 依赖度由此计算。 */
  counterpartyRows,
  byType,
  loading,
  errorText,
}: {
  title?: string;
  subtitle?: string;
  totalValueYuan: number;
  counterpartyRows: LiabilityCpRow[];
  byType: { name: string; value: number }[];
  loading: boolean;
  errorText: string | null;
}) {
  const ranked = useMemo(
    () => [...counterpartyRows].sort((a, b) => b.valueYuan - a.valueYuan),
    [counterpartyRows],
  );
  const cpTop10 = useMemo(() => ranked.slice(0, 10), [ranked]);

  const { top10Share, hhiTimes10000 } = useMemo(() => {
    const weights = counterpartyRows.map((r) => r.valueYuan);
    return concentrationMetrics(weights);
  }, [counterpartyRows]);

  const donut = useMemo(() => bankNonBankFromByType(byType), [byType]);

  const revTop10 = useMemo(() => [...cpTop10].reverse(), [cpTop10]);

  const barOption: EChartsOption = useMemo(
    () => ({
      grid: { left: 120, right: 24, top: 16, bottom: 16 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const arr = params as { data: { value: number; row: LiabilityCpRow } }[];
          if (!arr?.length) {
            return "";
          }
          const row = arr[0].data.row;
          const wc =
            row.weightedCost === null || row.weightedCost === undefined
              ? "—"
              : `${(Number(row.weightedCost) * 100).toFixed(2)}%`;
          return `${row.name}<br/>余额：${(row.valueYuan / 1e8).toFixed(2)} 亿<br/>占比：${row.pct.toFixed(2)}%<br/>加权负债成本：${wc}<br/>类型：${row.type || "—"}`;
        },
      },
      xAxis: { type: "value" },
      yAxis: {
        type: "category",
        data: revTop10.map((r) => truncateName(r.name)),
        axisLabel: { width: 110, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          data: revTop10.map((r) => ({
            value: r.valueYuan / 1e8,
            row: r,
          })),
          itemStyle: { color: LIAB_RED, borderRadius: [0, 4, 4, 0] },
        },
      ],
    }),
    [revTop10],
  );

  const pieOption: EChartsOption = useMemo(
    () => ({
      tooltip: {
        trigger: "item",
        formatter: (p: unknown) => {
          const x = p as { name: string; value: number };
          const tot = totalValueYuan;
          const pct = tot > 0 ? (x.value / tot) * 100 : 0;
          return `${x.name}<br/>余额：${(x.value / 1e8).toFixed(2)} 亿<br/>占比：${pct.toFixed(2)}%`;
        },
      },
      series: [
        {
          type: "pie",
          radius: ["40%", "65%"],
          data: donut.map((d, idx) => ({
            ...d,
            itemStyle: {
              color:
                donut.length <= 2 ? (idx === 0 ? PIE_BANK : PIE_NONBANK) : PIE_EXTRA[idx % PIE_EXTRA.length],
            },
          })),
        },
      ],
    }),
    [donut, totalValueYuan],
  );

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={16}>
        <Card
          size="small"
          title={title}
          extra={
            <Text type="secondary">
              总规模：{(totalValueYuan / 1e8).toFixed(0)} 亿 · Top10 占比：{(top10Share * 100).toFixed(2)}% · HHI：{" "}
              {hhiTimes10000.toFixed(0)}
            </Text>
          }
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            {subtitle}
          </Text>
          {errorText ? (
            <Text type="danger" style={{ display: "block", marginTop: 8 }}>
              {errorText}
            </Text>
          ) : null}
          <div style={{ height: 320, marginTop: 8 }}>
            {loading ? (
              <div style={{ padding: 48, textAlign: "center" }}>
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
          <Text type="secondary" style={{ fontSize: 12 }}>
            银行 vs 非银行（稳定性视角）。
          </Text>
          <div style={{ height: 280, marginTop: 8 }}>
            {loading ? (
              <div style={{ padding: 48, textAlign: "center" }}>
                <Spin />
              </div>
            ) : (
              <ReactECharts option={pieOption} style={{ height: 280 }} notMerge lazyUpdate />
            )}
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            银行占比越高，通常资金稳定性更强；非银行占比上升需关注期限错配与流动性压力。
          </Text>
        </Card>
      </Col>
    </Row>
  );
}
