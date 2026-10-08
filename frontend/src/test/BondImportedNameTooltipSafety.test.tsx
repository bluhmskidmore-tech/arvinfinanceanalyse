import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { normalizeCreditSpreadMigrationEnvelope } from "../api/bondAnalyticsNormalization";
import type { ApiEnvelope, CreditSpreadMigrationPayload, Numeric, ResultMeta } from "../api/contracts";
import { CreditSpreadView } from "../features/bond-analytics/components/CreditSpreadView";
import {
  buildIssuerConcentrationPieOption,
  concentrationBarOption,
} from "../features/bond-analytics/components/creditSpreadViewSupport";
import { designTokens, nocturneTokens } from "../theme/designSystem";
import { EM_DASH, formatRawAsNumeric } from "../utils/format";

// Capture actual component options, leaving their formatters and chart chrome intact.
const charts = vi.hoisted(() => ({ options: [] as unknown[] }));
vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => { charts.options.push(option); return null; },
}));

type Datum = { name: string; value?: number; weight?: Numeric; marketValueRaw?: Numeric };
type TestOption = {
  tooltip: {
    formatter: (params: unknown) => string | HTMLElement;
    backgroundColor?: string;
    borderColor?: string;
    textStyle?: { color?: string; fontSize?: number };
    renderMode?: string;
  };
  xAxis?: { data: string[] };
  series: Array<{ type: string; data: Array<Datum | number | null>; radius?: string | string[] }>;
};

const numeric = (raw: number | null, unit: Numeric["unit"]) =>
  formatRawAsNumeric({ raw, unit, sign_aware: false });

const resultMeta: ResultMeta = {
  trace_id: "synthetic-tooltip-only",
  basis: "mock",
  result_kind: "bond_analytics.credit_spread_migration",
  formal_use_allowed: false,
  source_version: "synthetic",
  vendor_version: "synthetic",
  rule_version: "synthetic",
  cache_version: "synthetic",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-10-06T00:00:00Z",
};

function syntheticEnvelope(name: string, amount: number | null = 100_000_000, weight: number | null = 0.125) {
  const concentration = (dimension: string) => ({
    dimension,
    hhi: numeric(0.1, "ratio"),
    top5_concentration: numeric(0.5, "ratio"),
    top_items: [{
      name: `${dimension} ${name}`,
      market_value: numeric(amount, "yuan"),
      // Deliberately distinguish authoritative display precision from chart percent.
      weight: { ...numeric(weight, "ratio"), display: weight === null ? EM_DASH : `${weight * 100}%`, precision: 3 },
    }],
  });
  const envelope: ApiEnvelope<CreditSpreadMigrationPayload> = {
    result_meta: resultMeta,
    result: {
      report_date: "2026-10-06",
      credit_bond_count: 1,
      credit_market_value: numeric(amount, "yuan"),
      credit_weight: numeric(weight, "ratio"),
      spread_dv01: numeric(null, "dv01"),
      weighted_avg_spread: numeric(null, "bp"),
      weighted_avg_spread_duration: numeric(null, "ratio"),
      spread_scenarios: [],
      migration_scenarios: [],
      oci_credit_exposure: numeric(null, "yuan"),
      oci_spread_dv01: numeric(null, "dv01"),
      oci_sensitivity_25bp: numeric(null, "yuan"),
      concentration_by_industry: concentration("行业"),
      concentration_by_rating: concentration("评级"),
      concentration_by_tenor: concentration("期限"),
      concentration_by_issuer: concentration("发行人"),
      warnings: [],
      computed_at: "2026-10-06T00:00:00Z",
    },
  };
  return normalizeCreditSpreadMigrationEnvelope(envelope);
}

async function renderConcentrations(name: string, amount?: number | null, weight?: number | null) {
  const envelope = syntheticEnvelope(name, amount, weight);
  const client = createApiClient({ mode: "mock" });
  vi.spyOn(client, "getBondAnalyticsCreditSpreadMigration").mockResolvedValue(envelope);
  vi.spyOn(client, "getCreditSpreadAnalysisDetail").mockResolvedValue({
    result_meta: { ...resultMeta, result_kind: "credit_spread_analysis.detail" },
    result: {
      report_date: "2026-10-06", credit_bond_count: 0, total_credit_market_value: "0",
      weighted_avg_spread_bps: null, spread_term_structure: [], top_spread_bonds: [],
      bottom_spread_bonds: [], historical_context: null, warnings: [], computed_at: "2026-10-06T00:00:00Z",
    },
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ApiClientProvider client={client}><CreditSpreadView reportDate="2026-10-06" /></ApiClientProvider>
  </QueryClientProvider>);
  await waitFor(() => expect(findOption("pie", `行业 ${name}`)).toBeDefined());
  return envelope.result;
}

function findOption(type: "pie" | "bar", name: string): TestOption | undefined {
  return (charts.options as TestOption[]).find((option) => option.series[0].type === type && (
    type === "bar" ? option.xAxis?.data[0] === name : (option.series[0].data[0] as Datum)?.name === name
  ));
}

function getOption(type: "pie" | "bar", name: string): TestOption {
  const option = findOption(type, name);
  expect(option, `${type} chart for ${name}`).toBeDefined();
  return option!;
}

function tooltipHost(option: TestOption, params: unknown): HTMLElement {
  const content = option.tooltip.formatter(params);
  const host = document.createElement("div");
  // Match ECharts' string HTML sink versus its DOM-node append contract.
  if (typeof content === "string") host.innerHTML = content;
  else host.append(content);
  return host;
}

function expectLiteralTooltip(host: HTMLElement, text: string, breaks: number) {
  expect.soft(host.querySelector("b,img,svg,script,[onerror]"), "source names must not become elements").toBeNull();
  expect.soft(host.textContent).toBe(text);
  expect.soft(host.querySelectorAll("br")).toHaveLength(breaks);
}

beforeEach(() => { charts.options = []; });

describe("bond concentration imported names at the actual tooltip boundary", () => {
  it.each([
    ["benign markup", '<b data-marker="synthetic">合成企业</b>'],
    ["inert image probe", '<img src="synthetic-no-request" onerror="void 0">'],
    ["metacharacters", '合成 & < > "双引号" \'单引号\''],
    ["pre-encoded text", "&lt;b&gt;合成&lt;/b&gt; &amp; &quot;"],
    ["ordinary Chinese", "合成制造集团（华东）"],
  ])("keeps %s literal through the real normalizer and component", async (_label, name) => {
    const result = await renderConcentrations(name);
    expect(result.concentration_by_industry?.top_items[0].name).toBe(`行业 ${name}`);
    for (const dimension of ["行业", "评级", "期限"]) {
      const option = getOption("pie", `${dimension} ${name}`);
      const datum = option.series[0].data[0] as Datum;
      expectLiteralTooltip(tooltipHost(option, { ...datum, data: datum, percent: 37 }), `${dimension} ${name}: 1.00 亿 (37%)`, 0);
    }
    for (const dimension of ["评级", "期限"]) {
      const option = getOption("bar", `${dimension} ${name}`);
      expectLiteralTooltip(tooltipHost(option, [{ name: option.xAxis!.data[0], value: option.series[0].data[0] }]), `${dimension} ${name}市值占比：12.5%`, 1);
    }
    const option = getOption("pie", `发行人 ${name}`);
    const datum = option.series[0].data[0] as Datum;
    expectLiteralTooltip(tooltipHost(option, { ...datum, data: datum, percent: 99 }), `发行人 ${name}市值：1.00 亿权重：12.5%`, 2);
  });

  it.each([
    ["zero", 0, "0.00 亿", "0%"],
    ["missing", null, EM_DASH, EM_DASH],
  ] as const)("preserves %s amounts, weights, order and punctuation", async (_label, raw, amountText, weightText) => {
    await renderConcentrations("合成企业", raw, raw);
    const pie = getOption("pie", "行业 合成企业");
    const datum = pie.series[0].data[0] as Datum;
    expectLiteralTooltip(tooltipHost(pie, { ...datum, data: datum }), `行业 合成企业: ${amountText} (0%)`, 0);
    const bar = getOption("bar", "评级 合成企业");
    expectLiteralTooltip(tooltipHost(bar, { name: bar.xAxis!.data[0], value: bar.series[0].data[0] }), `评级 合成企业市值占比：${weightText}`, 1);
    const issuer = getOption("pie", "发行人 合成企业");
    expectLiteralTooltip(tooltipHost(issuer, { data: issuer.series[0].data[0], percent: 99 }), `发行人 合成企业市值：${amountText}权重：${weightText}`, 2);
  });

  it("retains a backend issuer display even when the chart percentage differs", () => {
    const metrics = syntheticEnvelope("合成发行人").result.concentration_by_issuer!;
    metrics.top_items[0].weight = { ...metrics.top_items[0].weight, display: "12.500%" };
    const option = buildIssuerConcentrationPieOption(metrics) as TestOption;
    expectLiteralTooltip(tooltipHost(option, { data: option.series[0].data[0], percent: 100 }), "发行人 合成发行人市值：1.00 亿权重：12.500%", 2);
  });

  it("retains existing empty-name and missing-data fallbacks", async () => {
    await renderConcentrations("合成企业");
    expectLiteralTooltip(tooltipHost(getOption("pie", "行业 合成企业"), {}), `: ${EM_DASH} (0%)`, 0);
    expectLiteralTooltip(tooltipHost(getOption("bar", "评级 合成企业"), [{}]), `市值占比：${EM_DASH}`, 1);
    const issuer = getOption("pie", "发行人 合成企业");
    expect(issuer.tooltip.formatter({})).toBe("");
    expect(issuer.tooltip.formatter({ data: null })).toBe("");
  });

  it("retains absent and empty concentration bar behavior", () => {
    expect(concentrationBarOption(undefined, nocturneTokens.color.blue, "市值占比")).toBeNull();
    const metrics = syntheticEnvelope("合成企业").result.concentration_by_rating!;
    expect(concentrationBarOption({ ...metrics, top_items: [] }, nocturneTokens.color.blue, "市值占比")).toBeNull();
  });

  it("preserves chart chrome and leaves the existing rendering mode unchanged", async () => {
    await renderConcentrations("合成企业");
    for (const option of [getOption("pie", "行业 合成企业"), getOption("bar", "评级 合成企业"), getOption("pie", "发行人 合成企业")]) {
      expect(option.tooltip.backgroundColor).toBe(nocturneTokens.color.panel2);
      expect(option.tooltip.borderColor).toBe(nocturneTokens.color.line);
      expect(option.tooltip.textStyle).toMatchObject({ color: nocturneTokens.color.ink, fontSize: designTokens.fontSize[12] });
      expect(option.tooltip.renderMode).toBeUndefined();
    }
  });
});
