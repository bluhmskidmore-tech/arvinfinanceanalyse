import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Numeric } from "../api/contracts";
import { nocturneChartTheme } from "../components/charts/chartTheme";
import AdbComparisonChart from "../features/average-balance/components/AdbComparisonChart";
import AdbMonthlyHorizontalChart from "../features/average-balance/components/AdbMonthlyHorizontalChart";
import { adaptLiabilityCounterparty } from "../features/liability-analytics/adapters/liabilityAdapter";
import {
  LiabilityCounterpartyBlock,
  type LiabilityCpRow,
} from "../features/liability-analytics/components/LiabilityCounterpartyBlock";
import { nocturneTokens } from "../theme/designSystem";
import { EM_DASH, formatRawAsNumeric } from "../utils/format";

type CapturedOption = {
  tooltip: { formatter: (params: unknown) => string | HTMLElement; renderMode?: string };
  yAxis: { data: string[] };
  series: Array<{
    type: string;
    name?: string;
    data: unknown[];
    itemStyle?: { color?: string };
  }>;
};

const charts = vi.hoisted(() => ({ options: [] as CapturedOption[] }));
vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: CapturedOption }) => {
    charts.options.push(option);
    return null;
  },
}));

function barOption(): CapturedOption {
  const matches = charts.options.filter((option) => option.series.some((series) => series.type === "bar"));
  expect(matches).toHaveLength(1);
  return matches[0];
}

// Match ECharts' HTML content boundary: strings are parsed, DOM nodes are appended.
// jsdom establishes literal text and node structure, not browser hover/visual acceptance.
function tooltipHost(option: CapturedOption, params: unknown): HTMLElement {
  const content = option.tooltip.formatter(params);
  const host = document.createElement("div");
  if (typeof content === "string") host.innerHTML = content;
  else host.append(content);
  return host;
}

function expectLines(host: HTMLElement, lines: string[]): void {
  expect(host.textContent).toBe(lines.join(""));
  expect(host.querySelectorAll("br")).toHaveLength(lines.length - 1);
  expect(host.querySelector("b, img, svg, script, [onerror], [onload]")).toBeNull();
  const content = host.firstElementChild?.tagName === "DIV" ? host.firstElementChild : host;
  expect(Array.from(content.childNodes, (node) => node.nodeType === Node.TEXT_NODE ? node.textContent : "\n").join(""))
    .toBe(lines.join("\n"));
}

function numeric(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function renderCounterparty(name: string, overrides: Partial<LiabilityCpRow> = {}): CapturedOption {
  const { vm } = adaptLiabilityCounterparty({
    payload: {
      report_date: "2026-08-31",
      total_value: numeric(1_000_000_000, "yuan"),
      top10_share: numeric(0.125, "pct"),
      hhi: numeric(0.25, "ratio"),
      population_count: 12,
      is_truncated: true,
      top_10: [{ name, value: numeric(125_000_000, "yuan"), type: "Bank", weighted_cost: numeric(0.025, "pct", true) }],
      by_type: [{ name: "Bank", value: numeric(1_000_000_000, "yuan") }],
    },
    isLoading: false,
    isError: false,
  });
  if (!vm) throw new Error("Synthetic liability payload must produce its real adapter view model");
  expect(vm.rows[0].name).toBe(name);
  render(<LiabilityCounterpartyBlock
    totalValue={vm.totalValue}
    authoritativeTop10Share={vm.top10Share}
    authoritativeHhi={vm.hhi}
    populationCount={vm.populationCount}
    isTruncated={vm.isTruncated}
    counterpartyRows={vm.rows.map((row) => ({ ...row, ...overrides }))}
    byType={vm.byType}
    loading={false}
    errorText={null}
  />);
  return barOption();
}

function counterpartyTooltip(option: CapturedOption): HTMLElement {
  return tooltipHost(option, [{ data: option.series[0].data[0] }]);
}

const importedNames = [
  ["harmless markup", '<b data-marker="synthetic">合成名称</b> & 企业'],
  ["inert event-handler text", '<img src=x onerror="void 0"><svg onload="void 0">合成名称</svg>'],
  ["special characters and quotes", `合成 < A > B & "双引号" '单引号'`],
  ["pre-encoded source text", "合成 &lt;b&gt;名称&lt;/b&gt; &amp; &quot;引号&quot; &#39;"],
  ["ordinary Chinese full name", "中国合成集团股份有限公司青岛分行"],
];

beforeEach(() => { charts.options = []; });

describe("imported ADB and liability tooltip names", () => {
  it.each(importedNames)("comparison keeps %s literal with unchanged metrics", (_case, name) => {
    render(<AdbComparisonChart title="合成对比" rows={[{ label: name, spot: 123_456_789, avg: 100_000_000, deviationPct: 23.456789 }]} />);
    const option = barOption();
    expect(option.yAxis.data).toEqual([name]);
    expect(option.series[0].data).toEqual([123_456_789]);
    expect(option.series[0].itemStyle?.color).toBe(nocturneChartTheme.palette[0]);
    expectLines(tooltipHost(option, [{ dataIndex: 0, data: option.series[0].data[0] }]), [
      name, "期末时点：1.23 亿元", "区间日均：1.00 亿元", "偏离度：+23.46%",
    ]);
  });

  it.each(importedNames)("monthly keeps %s literal with unchanged metrics", (_case, name) => {
    render(<AdbMonthlyHorizontalChart title="合成月度" variant="liability" rows={[{ category: name, avgYi: 1.23456, weightedRate: 2.34567 }]} />);
    const option = barOption();
    expect(option.yAxis.data).toEqual([name]);
    expect(option.series[0].data).toEqual([1.23456]);
    expect(option.series[0].itemStyle?.color).toBe(nocturneTokens.color.red);
    expectLines(tooltipHost(option, [{ dataIndex: 0, data: option.series[0].data[0] }]), [
      name, "日均：1.23 亿元", "加权利率：2.35%",
    ]);
  });

  it.each(importedNames)("counterparty keeps %s literal and full after adapter and truncated axis", (_case, name) => {
    const option = renderCounterparty(name);
    expect(option.yAxis.data).toEqual([`${name.slice(0, 5)}…${name.slice(-4)}`]);
    expect(option.yAxis.data[0]).not.toBe(name);
    expect(option.series[0].data[0]).toMatchObject({ value: 1.25, row: { name } });
    expect(option.series[0].itemStyle?.color).toBe(nocturneChartTheme.palette[0]);
    expectLines(counterpartyTooltip(option), [
      name, "余额：1.25 亿", "占比：12.50%", "加权负债成本：2.50%", "类型：银行",
    ]);
  });
});

describe("unchanged numeric and empty tooltip contracts", () => {
  it.each([
    { label: "zero", value: 0, amount: "0.00", pct: "0.00%" },
    { label: "missing", value: null, amount: EM_DASH, pct: EM_DASH },
    { label: "NaN", value: Number.NaN, amount: EM_DASH, pct: EM_DASH },
  ])("comparison retains $label values", ({ value, amount, pct }) => {
    render(<AdbComparisonChart title="合成对比" rows={[{ label: "普通中文类别", spot: value, avg: value, deviationPct: value }]} />);
    const option = barOption();
    expectLines(tooltipHost(option, [{ dataIndex: 0 }]), [
      "普通中文类别", `期末时点：${amount} 亿元`, `区间日均：${amount} 亿元`, `偏离度：${pct}`,
    ]);
    expect(option.tooltip.formatter([])).toBe("");
  });

  it.each([
    { label: "zero", value: 0, amount: "0.00", pct: "0.00%" },
    { label: "missing", value: null, amount: EM_DASH, pct: EM_DASH },
    { label: "NaN", value: Number.NaN, amount: EM_DASH, pct: EM_DASH },
  ])("monthly retains $label values", ({ value, amount, pct }) => {
    render(<AdbMonthlyHorizontalChart title="合成月度" rows={[{ category: "普通中文类别", avgYi: value, weightedRate: value }]} />);
    const option = barOption();
    expectLines(tooltipHost(option, [{ dataIndex: 0 }]), [
      "普通中文类别", `日均：${amount} 亿元`, `加权利率：${pct}`,
    ]);
    expect(option.tooltip.formatter([])).toBe("");
  });

  it.each([
    { label: "zero", value: numeric(0, "yuan"), share: numeric(0, "pct"), cost: numeric(0, "pct", true), amount: "0.00 亿", pct: "0.00%" },
    { label: "missing objects", value: null, share: null, cost: null, amount: EM_DASH, pct: EM_DASH },
    { label: "missing raw numbers", value: numeric(null, "yuan"), share: numeric(null, "pct"), cost: numeric(null, "pct"), amount: EM_DASH, pct: EM_DASH },
  ])("counterparty retains $label values", ({ value, share, cost, amount, pct }) => {
    const option = renderCounterparty("合成银行", { value, share, weightedCost: cost, type: "" });
    expectLines(counterpartyTooltip(option), [
      "合成银行", `余额：${amount}`, `占比：${pct}`, `加权负债成本：${pct}`, `类型：${EM_DASH}`,
    ]);
    expect(option.tooltip.formatter([])).toBe("");
    expect(option.tooltip.formatter([{ data: {} }])).toBe("");
  });

  it("keeps unrecognized counterparty type text literal and preserves negative cost", () => {
    const type = '<b data-marker="type">合成类型</b> & 企业';
    const option = renderCounterparty("合成银行", { type, weightedCost: numeric(-0.0125, "pct", true) });
    expectLines(counterpartyTooltip(option), [
      "合成银行", "余额：1.25 亿", "占比：12.50%", "加权负债成本：-1.25%", `类型：${type}`,
    ]);
  });

  it("leaves empty components without a chart or tooltip", () => {
    const { container } = render(<>
      <AdbComparisonChart title="空对比" rows={[]} />
      <AdbMonthlyHorizontalChart title="空月度" rows={[]} />
      <LiabilityCounterpartyBlock totalValue={null} authoritativeTop10Share={null} authoritativeHhi={null}
        counterpartyRows={[]} byType={[]} loading={false} errorText={null} />
    </>);
    expect(charts.options).toHaveLength(0);
    expect(container.querySelectorAll('figure[data-state="empty"]')).toHaveLength(4);
  });
});
