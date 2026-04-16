import type { EChartsOption } from "../../../lib/echarts";
import ReactECharts from "../../../lib/echarts";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const MOCK_SLICES = [
  { name: "政策性金融债", value: 35.2 },
  { name: "地方政府债", value: 22.3 },
  { name: "同业存单", value: 17.9 },
  { name: "信用债-企业", value: 14.1 },
  { name: "金融债", value: 3.5 },
  { name: "其他", value: 7.0 },
];

const option: EChartsOption = {
  tooltip: { trigger: "item" },
  series: [
    {
      type: "pie",
      radius: ["42%", "70%"],
      data: MOCK_SLICES,
      label: { formatter: "{b}\n{d}%" },
    },
  ],
};

export function AssetStructurePie() {
  return (
    <SectionCard
      title="债券资产结构（示意）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <ReactECharts option={option} style={{ height: 300 }} opts={{ renderer: "canvas" }} />
    </SectionCard>
  );
}

export default AssetStructurePie;
