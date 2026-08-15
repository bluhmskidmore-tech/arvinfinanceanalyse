import type { EChartsOption } from "echarts";

import { BaseChart } from "../../../components/charts/BaseChart";
// canvas 不消费 CSS 变量：示意瀑布取色走 nocturneTokens 常量组
// （operations-analysis 页根已声明 Nocturne scope，risk-tensor 先例）。
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import styles from "./RevenueCostBridge.module.css";

const STEPS = [
  { name: "债券资产收益", value: 68.56 },
  { name: "同业资产收益", value: 4.31 },
  { name: "发行负债成本", value: -22.11 },
  { name: "同业负债成本", value: -9.11 },
] as const;

function buildWaterfallParts() {
  const placeholder: number[] = [];
  const positive: number[] = [];
  const negative: number[] = [];
  let acc = 0;
  for (const step of STEPS) {
    if (step.value >= 0) {
      placeholder.push(acc);
      positive.push(step.value);
      negative.push(0);
      acc += step.value;
    } else {
      const next = acc + step.value;
      placeholder.push(next);
      positive.push(0);
      negative.push(-step.value);
      acc = next;
    }
  }
  return { placeholder, positive, negative, total: acc, categories: STEPS.map((s) => s.name) };
}

function buildOption(): EChartsOption {
  const { placeholder, positive, negative, categories } = buildWaterfallParts();
  return {
    color: ["rgba(0,0,0,0)", nocturneTokens.color.green, nocturneTokens.color.red],
    grid: { left: 48, right: 24, top: 40, bottom: 72 },
    legend: { show: false },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const idx = Number((list[0] as { dataIndex?: number }).dataIndex ?? 0);
        const step = STEPS[idx];
        if (!step) {
          return "";
        }
        const sign = step.value >= 0 ? "+" : "";
        return `${step.name}<br/>${sign}${step.value.toFixed(2)} 亿`;
      },
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: nocturneTokens.color.inkSoft },
      axisLine: { lineStyle: { color: nocturneTokens.color.line } },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      nameTextStyle: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
      axisLabel: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
      splitLine: { lineStyle: { type: "dashed", color: nocturneTokens.color.lineSoft } },
    },
    series: [
      {
        name: "base",
        type: "bar",
        stack: "bridge",
        silent: true,
        itemStyle: { color: "rgba(0,0,0,0)", borderWidth: 0 },
        emphasis: { disabled: true },
        data: placeholder,
      },
      {
        name: "增收",
        type: "bar",
        stack: "bridge",
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        data: positive,
      },
      {
        name: "成本",
        type: "bar",
        stack: "bridge",
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        data: negative,
      },
    ],
  };
}

/**
 * 收益成本桥示意瀑布（静态样例）。
 * 「静态示例」红胶囊声明由页面折叠区 summary 承载（收敛为一处），
 * 组件内只保留一行正式口径缺口说明。
 */
export function RevenueCostBridge() {
  return (
    <div className={styles.body}>
      <p className={styles.note} data-testid="revenue-cost-bridge-sample-note">
        正式口径读数：{EM_DASH}（未接入）；瀑布为静态样例，数值不代表正式读数。
      </p>
      <BaseChart option={buildOption()} height={300} />
    </div>
  );
}
