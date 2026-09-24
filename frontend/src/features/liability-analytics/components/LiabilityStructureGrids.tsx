import type { Numeric } from "../../../api/contracts";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { BaseChart } from "../../../components/charts/BaseChart";
import { type EChartsOption } from "../../../lib/echarts";
import { termBucketLabel } from "../utils/labels";
import { numericOrDash, numericRaw } from "../utils/money";

/** 结构饼图分类色：取 Nocturne 分类盘前五档（无语义红，避免结构图带告警暗示）。 */
const COLORS = [
  nocturneChartTheme.categoricalPalette[0],
  nocturneChartTheme.categoricalPalette[1],
  nocturneChartTheme.categoricalPalette[2],
  nocturneChartTheme.categoricalPalette[3],
  nocturneChartTheme.categoricalPalette[4],
] as const;

type NamedYi = { name: string; amountYi: Numeric | null };
type BucketYi = { bucket: string; amountYi: Numeric | null };

function pieOption(items: NamedYi[]): EChartsOption {
  return nocturneChartTheme.createBaseChartOption({
    color: [...COLORS],
    legend: { show: false },
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
        // 缺数（null）不入饼图系列，避免画出假 0 扇区；图例仍以 EM_DASH 展示缺数项。
        data: items
          .filter((item) => numericRaw(item.amountYi) !== null)
          .map((item) => ({
            name: item.name,
            value: numericRaw(item.amountYi) as number,
            amountYi: item.amountYi,
          })),
        label: { show: false },
      },
    ],
  });
}

function barOption(items: BucketYi[]): EChartsOption {
  return nocturneChartTheme.createBarChartOption({
    color: [COLORS[0]],
    legend: { show: false },
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
    xAxis: {
      type: "category",
      // 桶名中文化（显示层）；interval: 0 禁止轴标签抽稀，8 桶全量可见。
      data: items.map((item) => termBucketLabel(item.bucket)),
      axisLabel: { fontSize: 11, interval: 0 },
    },
    yAxis: { type: "value" },
    series: [
      {
        type: "bar",
        // 缺数（null）保留类目但不画柱；tooltip 经 numericOrDash 显示 EM_DASH。
        data: items.map((item) => ({
          value: numericRaw(item.amountYi),
          amountYi: item.amountYi,
        })),
        barMaxWidth: 48,
      },
    ],
  });
}

function PieLegend({ items }: { items: NamedYi[] }) {
  return (
    <div className="liability-legend">
      {items.map((item, index) => (
        <span key={item.name} className="liability-legend__item">
          <span
            className="liability-legend__swatch"
            style={{ background: COLORS[index % COLORS.length] }}
          />
          {item.name}: {numericOrDash(item.amountYi)}
        </span>
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
      <div className="liability-analytics-page__grid liability-analytics-page__grid--structure">
        <div className="liability-panel">
          <h3 className="liability-panel__title">负债结构总览（单位：亿元）</h3>
          {structurePieCaption ? <p className="liability-caption">{structurePieCaption}</p> : null}
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={pieOption(structure)} height={300} />
          </div>
          <PieLegend items={structure} />
        </div>
        <div className="liability-panel">
          <h3 className="liability-panel__title">期限结构（单位：亿元）</h3>
          <p className="liability-caption">
            口径：发行债券（asset_class 含“发行类”）+ 同业负债（direction=Liability）。
          </p>
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={barOption(term)} height={300} />
          </div>
        </div>
      </div>

      <div className="liability-analytics-page__grid liability-analytics-page__grid--2">
        <div className="liability-panel">
          <h3 className="liability-panel__title">同业负债业务结构（按产品类型，亿元）</h3>
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={pieOption(interbankStructure)} height={300} />
          </div>
          <PieLegend items={interbankStructure} />
        </div>
        <div className="liability-panel">
          <h3 className="liability-panel__title">同业负债期限结构（亿元）</h3>
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={barOption(interbankTerm)} height={300} />
          </div>
        </div>
      </div>

      <div className="liability-analytics-page__grid liability-analytics-page__grid--2">
        <div className="liability-panel">
          <h3 className="liability-panel__title">发行负债业务结构（按业务种类，亿元）</h3>
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={pieOption(issuedStructure)} height={300} />
          </div>
          <PieLegend items={issuedStructure} />
        </div>
        <div className="liability-panel">
          <h3 className="liability-panel__title">发行负债期限结构（亿元）</h3>
          <div className="liability-chart-frame liability-chart-frame--structure">
            <BaseChart option={barOption(issuedTerm)} height={300} />
          </div>
        </div>
      </div>
    </>
  );
}
