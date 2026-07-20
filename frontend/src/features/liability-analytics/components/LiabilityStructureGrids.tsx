import { Card, Col, Row, Typography } from "antd";

import type { Numeric } from "../../../api/contracts";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { numericOrDash } from "../utils/money";

const { Text } = Typography;

const COLORS = [
  mossChartCategoricalPalette[0],
  mossChartCategoricalPalette[1],
  mossChartCategoricalPalette[2],
  mossChartCategoricalPalette[3],
  mossChartCategoricalPalette[5],
] as const;

type NamedYi = { name: string; amountYi: Numeric | null };
type BucketYi = { bucket: string; amountYi: Numeric | null };

function pieOption(items: NamedYi[]): EChartsOption {
  return {
    color: [...COLORS],
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
    <div className="liability-legend">
      {items.map((item, index) => (
        <Text key={item.name} className="liability-legend__item" type="secondary">
          <span
            className="liability-legend__swatch"
            style={{ background: COLORS[index % COLORS.length] }}
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
              <Text type="secondary" className="liability-panel-caption--tight">
                {structurePieCaption}
              </Text>
            ) : null}
            <div className="liability-chart-frame liability-chart-frame--structure">
              <ReactECharts option={pieOption(structure)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
            <PieLegend items={structure} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card size="small" title="期限结构（单位：亿元）">
            <Text type="secondary" className="liability-panel-caption--tight">
              口径：发行债券（asset_class 含“发行类”）+ 同业负债（direction=Liability）。
            </Text>
            <div className="liability-chart-frame liability-chart-frame--structure">
              <ReactECharts option={barOption(term)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="同业负债业务结构（按产品类型，亿元）">
            <div className="liability-chart-frame liability-chart-frame--structure">
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
            <div className="liability-chart-frame liability-chart-frame--structure">
              <ReactECharts
                option={barOption(interbankTerm)}
                style={{ height: 300 }}
                notMerge
                lazyUpdate
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="发行负债业务结构（按业务种类，亿元）">
            <div className="liability-chart-frame liability-chart-frame--structure">
              <ReactECharts
                option={pieOption(issuedStructure)}
                style={{ height: 300 }}
                notMerge
                lazyUpdate
              />
            </div>
            <PieLegend items={issuedStructure} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="发行负债期限结构（亿元）">
            <div className="liability-chart-frame liability-chart-frame--structure">
              <ReactECharts option={barOption(issuedTerm)} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          </Card>
        </Col>
      </Row>
    </>
  );
}
