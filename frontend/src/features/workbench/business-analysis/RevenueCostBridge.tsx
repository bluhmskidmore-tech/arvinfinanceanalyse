import type { EChartsOption } from "echarts";

import { BaseChart } from "../../../components/charts/BaseChart";
import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { DataSourceBadge } from "../../../components/StatusPill";
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
  const { placeholder, positive, negative, total, categories } = buildWaterfallParts();
  return {
    color: ["rgba(0,0,0,0)", "#16a34a", "#dc2626"],
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
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: "#475569" },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      nameTextStyle: { color: "#64748b", fontSize: 11 },
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } },
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
    graphic: [
      {
        type: "text",
        left: "center",
        top: 8,
        style: {
          text: `示意瀑布（静态样例，累计 ${total.toFixed(2)} 为示意值）· 非正式口径，不作正式读数`,
          fill: "#64748b",
          fontSize: 11,
        },
      },
    ],
  };
}

export function RevenueCostBridge() {
  return (
    <EvidencePanel heading="收益成本桥（示意）">
      <div className={styles.body}>
        <div>
          <DataSourceBadge
            status="mock"
            label="示意数据·未接入正式口径"
            testId="revenue-cost-bridge-sample-badge"
            title="瀑布图为静态示意样例，未接入正式口径读链路，不作正式读数"
          />
        </div>
        <p className={styles.note} data-testid="revenue-cost-bridge-sample-note">
          正式口径读数：{EM_DASH}（未接入）。下方瀑布为静态示意样例，仅演示“资产收益抵减负债成本得到净贡献”的结构，数值不代表正式读数。
        </p>
        <BaseChart option={buildOption()} height={300} />
      </div>
    </EvidencePanel>
  );
}
