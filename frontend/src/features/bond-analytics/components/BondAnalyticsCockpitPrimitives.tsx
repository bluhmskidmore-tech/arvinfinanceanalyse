import { useMemo, type CSSProperties, type ReactNode } from "react";

import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { DONUT_CHART_COLORS } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

/** 分布/结构图元共用行模型：value 为原始金额或面值，caption/detail 已在页面模型侧格式化。 */
export type DistributionItem = {
  key: string;
  label: string;
  value: number;
  caption: string;
  detail?: string;
  color?: string;
};

const DONUT_HEIGHT = 150;
const MATURITY_CHART_HEIGHT = 168;
const MATURITY_BAR_LIMIT = 7;
const DONUT_SLICE_LIMIT = 5;

/**
 * 金额轴刻度缩写（图表语法基线 §4）：亿 / 万 两档，禁止直出 700,000,000 级原始数字。
 * 只服务于坐标轴刻度，正文金额仍走 `utils/formatters` 的 formatYi / formatWan。
 */
function formatAmountAxisTick(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return "0";
  }
  const abs = Math.abs(value);
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(abs >= 1e9 ? 0 : 1)} 亿`;
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(0)} 万`;
  }
  return `${value}`;
}

export function SectionCardTitle({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className={styles.sectionCardTitle}>
      <div className={styles.sectionCardTitleEyebrow}>{eyebrow}</div>
      <div className={styles.sectionCardTitleText}>{title}</div>
    </div>
  );
}

export function MobileReadoutField({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: ReactNode;
}) {
  return (
    <div className={styles.mobileReadoutField}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function EmptyEvidencePanel({ text }: { text: string }) {
  return <div className={styles.emptyEvidencePanel}>{text}</div>;
}

export function PendingReadModelPanel({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className={styles.pendingReadModelPanel}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

/**
 * 分布行条（首页 distributionRow 语言）：行底 2px 微条兼作发丝分隔线，
 * 数值 12px 等宽右对齐。合并了旧 ProgressStack 与 RegionDistributionPanel
 * 两套同构实现（同为「标签 + 4px 轨道条 + 数值」）。
 */
export function DistributionRows({
  items,
  emptyText,
}: {
  items: DistributionItem[];
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.distributionRows}>
      {items.map((item) => (
        <div key={item.key} className={styles.distributionRow}>
          <span>{item.label}</span>
          <strong>{item.caption}</strong>
          {item.detail ? <em>{item.detail}</em> : null}
          <i
            className={styles.distributionRowBar}
            style={{ width: `${Math.max(2, (Math.abs(item.value) / maxValue) * 100)}%` }}
            aria-hidden="true"
          />
        </div>
      ))}
    </div>
  );
}

/* 单序列柱体统一强调单色（基线 §5）：不按期限桶轮播分类色。 */
function buildMaturityBarOption(items: DistributionItem[]): EChartsOption {
  const visible = items.slice(0, MATURITY_BAR_LIMIT);
  const captionByLabel = new Map(visible.map((item) => [item.label, item.caption]));

  return nocturneChartTheme.createBarChartOption({
    legend: { show: false },
    grid: { left: 4, right: 8, top: 14, bottom: 0, containLabel: true },
    tooltip: {
      formatter: (params: unknown) => {
        const list = (Array.isArray(params) ? params : [params]) as Array<{
          name?: string;
          marker?: string;
        }>;
        const head = list[0];
        if (!head?.name) {
          return "";
        }
        return `${head.marker ?? ""}${head.name}&nbsp;&nbsp;<strong>${captionByLabel.get(head.name) ?? ""}</strong>`;
      },
    },
    xAxis: {
      data: visible.map((item) => item.label),
      axisTick: { show: false },
      axisLabel: { interval: 0, hideOverlap: true },
    },
    yAxis: {
      axisLine: { show: false },
      axisLabel: { formatter: formatAmountAxisTick },
    },
    series: [
      {
        type: "bar",
        name: "期限桶市值",
        barMaxWidth: 34,
        itemStyle: { color: nocturneTokens.color.blue, borderRadius: [3, 3, 0, 0] },
        data: visible.map((item) => item.value),
      },
    ],
  } as EChartsOption);
}

export function MaturityColumnChart({
  items,
  emptyText,
}: {
  items: DistributionItem[];
  emptyText: string;
}) {
  const option = useMemo(() => buildMaturityBarOption(items), [items]);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.maturityChart} aria-label="期限桶市值柱状图">
      <BaseChart option={option} height={MATURITY_CHART_HEIGHT} />
    </div>
  );
}

function buildDistributionDonutOption(items: DistributionItem[]): EChartsOption {
  const slices = items.slice(0, DONUT_SLICE_LIMIT);

  return nocturneChartTheme.createBaseChartOption({
    /* 图例只留左侧 DOM 行（信息量更高：标签 + 规模），不与 echarts legend 双份。 */
    legend: { show: false },
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const point = params as {
          marker?: string;
          name?: string;
          data?: { caption?: string; detail?: string };
        };
        const caption = point.data?.caption ?? "";
        const detail = point.data?.detail ? ` · ${point.data.detail}` : "";
        return `${point.marker ?? ""}${point.name ?? ""}<br/><strong>${caption}</strong>${detail}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["58%", "82%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderWidth: 1, borderColor: nocturneTokens.color.panel },
        data: slices.map((item, index) => ({
          name: item.label,
          value: Math.max(item.value, 0),
          caption: item.caption,
          detail: item.detail,
          itemStyle: {
            color: item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length],
          },
        })),
      },
    ],
  } as EChartsOption);
}

export function DistributionDonut({
  items,
  center,
  emptyText,
}: {
  items: DistributionItem[];
  center: string;
  emptyText: string;
}) {
  const option = useMemo(() => buildDistributionDonutOption(items), [items]);
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);

  if (items.length === 0 || total <= 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.referenceDonutPanel}>
      <div className={styles.referenceDonutLegend}>
        {items.slice(0, DONUT_SLICE_LIMIT).map((item, index) => (
          <div key={item.key} className={styles.referenceDonutLegendRow}>
            <span
              style={
                {
                  background: item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length],
                } as CSSProperties
              }
            />
            <strong>{item.label}</strong>
            <em>{item.caption}</em>
          </div>
        ))}
      </div>
      <div className={styles.referenceDonut} aria-label="资产结构环形图">
        <BaseChart option={option} height={DONUT_HEIGHT} />
        <span className={styles.referenceDonutCenter}>{center}</span>
      </div>
    </div>
  );
}
