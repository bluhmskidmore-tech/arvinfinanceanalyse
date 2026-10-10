import type { Numeric } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
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

/** 2026-09-02 迁入 ChartCard：六张结构图统一 hero 档（原 300px），空态由铬件收缩。 */
const CHART_HEIGHT = CHART_CARD_HEIGHTS.hero;

function hasAnyValue(items: Array<{ amountYi: Numeric | null }>): boolean {
  return items.some((item) => numericRaw(item.amountYi) !== null);
}

/* 环形图图例走下方 PieLegend（带金额与缺数 EM_DASH），ECharts 自带图例由铬件 legend="none" 关闭。 */
function pieOption(items: NamedYi[]): EChartsOption {
  return nocturneChartTheme.createBaseChartOption({
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
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = params as { data?: { amountYi: Numeric | null }[]; name?: string }[];
        const first = list?.[0];
        const data = first?.data as { amountYi: Numeric | null } | undefined;
        return `${first?.name ?? ""}<br/>${numericOrDash(data?.amountYi)}`;
      },
    },
    grid: { left: 48, right: 16, top: 16 },
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
  /* 标题里的口径与单位拆到 question / unit / footnote，标题本身 ≤ 12 字（视觉方案 §5）。 */
  return (
    <>
      <div className="liability-analytics-page__grid liability-analytics-page__grid--structure liability-analytics-page__grid--matched-panels">
        <ChartCard
          title="负债结构总览"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(structure) ? pieOption(structure) : null}
          footnote={structurePieCaption}
        >
          <PieLegend items={structure} />
        </ChartCard>
        <ChartCard
          title="期限结构"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(term) ? barOption(term) : null}
          footnote="口径：发行债券（asset_class 含“发行类”）+ 同业负债（direction=Liability）。"
        />
      </div>

      <div className="liability-analytics-page__grid liability-analytics-page__grid--2 liability-analytics-page__grid--matched-panels">
        <ChartCard
          title="同业负债业务结构"
          question="按产品类型"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(interbankStructure) ? pieOption(interbankStructure) : null}
        >
          <PieLegend items={interbankStructure} />
        </ChartCard>
        <ChartCard
          title="同业负债期限结构"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(interbankTerm) ? barOption(interbankTerm) : null}
        />
      </div>

      <div className="liability-analytics-page__grid liability-analytics-page__grid--2 liability-analytics-page__grid--matched-panels">
        <ChartCard
          title="发行负债业务结构"
          question="按业务种类"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(issuedStructure) ? pieOption(issuedStructure) : null}
        >
          <PieLegend items={issuedStructure} />
        </ChartCard>
        <ChartCard
          title="发行负债期限结构"
          unit="亿元"
          height={CHART_HEIGHT}
          legend="none"
          option={hasAnyValue(issuedTerm) ? barOption(issuedTerm) : null}
        />
      </div>
    </>
  );
}
