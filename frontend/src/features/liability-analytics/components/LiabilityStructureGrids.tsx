import { Card, Col, Row, Typography } from "antd";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

const { Text } = Typography;

const COLORS = ["#cf1322", "#1d39c4", "#08979c", "#389e0d", "#531dab"];

type NamedYi = { name: string; amountYi: number };
type BucketYi = { bucket: string; amountYi: number };

function pieOption(items: NamedYi[]): EChartsOption {
  return {
    color: COLORS,
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as { name: string; value: number; percent: number };
        return `${x.name}<br/>${x.percent.toFixed(2)}%<br/>${x.value.toFixed(2)} 亿元`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        data: items.map((s) => ({ name: s.name, value: s.amountYi })),
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
        const arr = params as { name: string; value: number }[];
        if (!arr?.length) {
          return "";
        }
        return `${arr[0].name}<br/>${arr[0].value.toFixed(2)} 亿元`;
      },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 32 },
    xAxis: { type: "category", data: items.map((x) => x.bucket), axisLabel: { fontSize: 11 } },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: items.map((x) => x.amountYi), barMaxWidth: 48 }],
  };
}

function PieLegend({ items }: { items: NamedYi[] }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
      {items.map((s, idx) => (
        <Text key={s.name} style={{ fontSize: 12 }} type="secondary">
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: 999,
              background: COLORS[idx % COLORS.length],
              marginRight: 6,
            }}
          />
          {s.name}: {s.amountYi.toFixed(2)} 亿
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
}: {
  structure: NamedYi[];
  term: BucketYi[];
  interbankStructure: NamedYi[];
  interbankTerm: BucketYi[];
  issuedStructure: NamedYi[];
  issuedTerm: BucketYi[];
}) {
  return (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="负债结构总览（单位：亿元）">
            <div style={{ height: 300 }}>
              <ReactECharts option={pieOption(structure)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
            <PieLegend items={structure} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card size="small" title="期限结构（单位：亿元）">
            <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
              口径：发行债券（asset_class 含「发行类」）+ 同业负债（direction=Liability）。
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
              <ReactECharts
                option={pieOption(interbankStructure)}
                style={{ height: 300 }}
                notMerge
                lazyUpdate
              />
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
