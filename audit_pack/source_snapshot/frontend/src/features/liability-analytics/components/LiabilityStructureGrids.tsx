import { Card, Col, Row, Typography } from "antd";

import type { Numeric } from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { numericOrDash } from "../utils/money";

const { Text } = Typography;

const COLORS = ["#cf1322", "#1d39c4", "#08979c", "#389e0d", "#531dab"];

type NamedYi = { name: string; amountYi: Numeric | null };
type BucketYi = { bucket: string; amountYi: Numeric | null };

function pieOption(items: NamedYi[]): EChartsOption {
  return {
    color: COLORS,
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const point = params as { data?: { name: string; amountYi: Numeric | null }; percent?: number };
        const item = point.data;
        return `${item?.name ?? ""}<br/>${(point.percent ?? 0).toFixed(2)}%<br/>${numericOrDash(item?.amountYi)}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        data: items.map((item) => ({
          name: item.name,
          value: item.amountYi?.raw ?? 0,
          amountYi: item.amountYi,
        })),
        label: { show: false },
      },
    ],
  };
}

function barOption(items: BucketYi[]): EChartsOption {
  return {
    color: [COLORS[0]],
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = params as { data?: { amountYi: Numeric | null }[]; name?: string }[];
        const first = list?.[0];
        const data = first?.data as { amountYi: Numeric | null } | undefined;
        return `${first?.name ?? ""}<br/>${numericOrDash(data?.amountYi)}`;
      },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 32 },
    xAxis: { type: "category", data: items.map((item) => item.bucket), axisLabel: { fontSize: 11 } },
    yAxis: { type: "value" },
    series: [
      {
        type: "bar",
        data: items.map((item) => ({
          value: item.amountYi?.raw ?? 0,
          amountYi: item.amountYi,
        })),
        barMaxWidth: 48,
      },
    ],
  };
}

function PieLegend({ items }: { items: NamedYi[] }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
      {items.map((item, index) => (
        <Text key={item.name} style={{ fontSize: 12 }} type="secondary">
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: 999,
              background: COLORS[index % COLORS.length],
              marginRight: 6,
            }}
          />
          {item.name}: {numericOrDash(item.amountYi)}
        </Text>
      ))}
    </div>
  );
}

export function LiabilityStructureGrids({
  structure,
  term,
  interbankStructure,
  interbankTerm,
  issuedStructure,
  issuedTerm,
  structurePieCaption,
}: {
  structure: NamedYi[];
  term: BucketYi[];
  interbankStructure: NamedYi[];
  interbankTerm: BucketYi[];
  issuedStructure: NamedYi[];
  issuedTerm: BucketYi[];
  structurePieCaption?: string;
}) {
  return (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="负债结构总览（单位：亿元）">
            {structurePieCaption ? (
              <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
                {structurePieCaption}
              </Text>
            ) : null}
            <div style={{ height: 300 }}>
              <ReactECharts option={pieOption(structure)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
            <PieLegend items={structure} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card size="small" title="期限结构（单位：亿元）">
            <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
              口径：发行债券（asset_class 含“发行类”）+ 同业负债（direction=Liability）。
            </Text>
            <div style={{ height: 300 }}>
              <ReactECharts option={barOption(term)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 0 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title="同业负债业务结构（按产品类型，亿元）">
            <div style={{ height: 300 }}>
              <ReactECharts option={pieOption(interbankStructure)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
            <PieLegend items={interbankStructure} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="同业负债期限结构（亿元）">
            <div style={{ height: 300 }}>
              <ReactECharts option={barOption(interbankTerm)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="发行负债业务结构（按业务种类，亿元）">
            <div style={{ height: 300 }}>
              <ReactECharts option={pieOption(issuedStructure)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
            <PieLegend items={issuedStructure} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="发行负债期限结构（亿元）">
            <div style={{ height: 300 }}>
              <ReactECharts option={barOption(issuedTerm)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          </Card>
        </Col>
      </Row>
    </>
  );
}
