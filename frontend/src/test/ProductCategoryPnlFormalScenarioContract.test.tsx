/**
 * product-category-pnl Formal/Scenario 状态区分可见性契约探针
 * （agent 评测 harness gate 探针：`formal_scenario_state_distinction_visible`、
 *   `fallback_or_stale_state_visible_when_applicable`，
 *   见 scripts/agent_eval/tasks/product_category_pnl_contract_001.json）。
 *
 * Gate 语义：
 * 1. formal_scenario_state_distinction_visible —— Formal/Scenario 分离是仓库口径红线
 *    （backend caliber 测试守护计算侧；前端义务是「展示不重算 + 状态区分可见」）：
 *    - scenario_flag=true、basis 非 formal、formal_use_allowed=false 的 result_meta
 *      必须在治理条渲染「正式判断阻断」（role=alert），不得当作正式基线放行经营判断；
 *    - 干净 formal 基线渲染「可用于经营判断」（role=status）；
 *    - formal 与 scenario 两路 result_meta 的口径标签与 trace_id 必须同屏可见、不混用；
 *    - FTP 情景载荷对表格行是整体替换 + 逐字透传，前端不重算任何合计。
 * 2. fallback_or_stale_state_visible_when_applicable —— result_meta 的
 *    fallback_mode / vendor_status / quality_flag 降级必须渲染为可见治理公告；
 *    干净 meta 不得渲染公告（不制造虚假降级噪音）。
 *
 * 契约依据：
 * - docs/page_contracts.md PAGE-PROD-CAT-PNL-001 §E（默认解释 formal；scenario 字段仅在
 *   显式场景载荷下成为主解释）、§G（quality_flag/fallback_mode/vendor_status 须可见）
 * - docs/pnl/product-category-page-truth-contract.md §6/§9/§10/§11
 * - docs/metric_dictionary.md MTR-PCP-001~012（金额与行字段均为后端所有，前端不得重算）
 *
 * 探针成本控制：只渲染治理条组件 ProductCategoryGovernanceStrip（页面的状态可见性
 * 承载面），输入全部经由真实页面模型函数构造，不整页挂载。
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../api/contracts";
import { ProductCategoryGovernanceStrip } from "../features/product-category-pnl/pages/ProductCategoryGovernanceStrip";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  buildProductCategoryDataHealth,
  collectProductCategoryGovernanceNotices,
  formatProductCategoryDualMetaDistinctLine,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
} from "../features/product-category-pnl/pages/productCategoryPnlPageModel";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";

const REPORT_DATE = "2026-02-28";

const envelope = buildMockProductCategoryPnlEnvelope({
  reportDate: REPORT_DATE,
  view: "monthly",
});

/**
 * 干净 formal 基线 meta。区分性字段（basis/scenario_flag/formal_use_allowed/
 * quality/vendor/fallback/trace_id）全部显式钉死后再接受覆盖，mock fixture 的
 * 漂移不会弱化本探针的断言。
 */
function meta(overrides: Partial<ResultMeta>): ResultMeta {
  return {
    ...envelope.result_meta,
    trace_id: "t_formal_base",
    basis: "formal",
    formal_use_allowed: true,
    scenario_flag: false,
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    ...overrides,
  };
}

/** 用真实页面模型输出渲染治理条：health 由 healthMeta 推导，公告由 noticeMeta 推导。 */
function renderStrip(input: {
  healthMeta: ResultMeta | undefined;
  noticeMeta?: ResultMeta;
  formalScenarioDistinct?: string | null;
}) {
  const dataHealth = buildProductCategoryDataHealth({
    datesLoading: false,
    datesError: false,
    reportDates: [envelope.result.report_date],
    selectedDate: envelope.result.report_date,
    baselineLoading: false,
    baselineError: false,
    baseline: envelope.result,
    meta: input.healthMeta,
  });
  return render(
    <ProductCategoryGovernanceStrip
      dataHealth={dataHealth}
      asOfDateGapText={PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY}
      notices={collectProductCategoryGovernanceNotices(input.noticeMeta)}
      formalScenarioDistinct={input.formalScenarioDistinct ?? null}
      onRetry={null}
      evidence={<span>治理证据占位</span>}
    />,
  );
}

describe("product-category-pnl Formal/Scenario 状态区分可见（治理条渲染）", () => {
  it("FTP 情景 meta（scenario_flag=true）渲染「正式判断阻断」，不得当作正式基线放行", () => {
    renderStrip({
      healthMeta: meta({
        basis: "scenario",
        scenario_flag: true,
        trace_id: "t_scen",
      }),
    });

    const health = screen.getByTestId("product-category-data-health");
    const judgement = screen.getByTestId(
      "product-category-formal-judgement-status",
    );
    // 情景被当作正式基线放行（ready/allowed）是本探针要捕获的违规态；
    // 契约要求情景 meta 一律阻断正式判断并以 alert 呈现。
    expect(health).toHaveAttribute("data-health-state", "degraded");
    expect(health).toHaveAttribute("role", "alert");
    expect(judgement).toHaveAttribute("data-judgement-state", "blocked");
    expect(judgement).toHaveTextContent("正式判断阻断");
  });

  it.each([
    ["basis 非 formal（analytical）", { basis: "analytical" }],
    ["formal_use_allowed=false", { formal_use_allowed: false }],
  ] satisfies Array<[string, Partial<ResultMeta>]>)(
    "非正式基线 meta（%s）同样渲染阻断态",
    (_reason, overrides) => {
      renderStrip({ healthMeta: meta(overrides) });

      expect(
        screen.getByTestId("product-category-data-health"),
      ).toHaveAttribute("data-health-state", "degraded");
      expect(
        screen.getByTestId("product-category-formal-judgement-status"),
      ).toHaveTextContent("正式判断阻断");
    },
  );

  it("缺失 result_meta 时 fail-closed 渲染阻断态", () => {
    renderStrip({ healthMeta: undefined });

    expect(
      screen.getByTestId("product-category-formal-judgement-status"),
    ).toHaveAttribute("data-judgement-state", "blocked");
  });

  it("干净 formal 基线渲染「可用于经营判断」（role=status）", () => {
    renderStrip({ healthMeta: meta({}) });

    const health = screen.getByTestId("product-category-data-health");
    const judgement = screen.getByTestId(
      "product-category-formal-judgement-status",
    );
    expect(health).toHaveAttribute("data-health-state", "ready");
    expect(health).toHaveAttribute("role", "status");
    expect(judgement).toHaveAttribute("data-judgement-state", "allowed");
    expect(judgement).toHaveTextContent("可用于经营判断");
  });

  it("formal 与 scenario 双 meta 行同屏保留两路口径标签与 trace_id；无情景时不渲染该行", () => {
    const line = formatProductCategoryDualMetaDistinctLine(
      meta({ trace_id: "t_formal" }),
      meta({ basis: "scenario", scenario_flag: true, trace_id: "t_scen" }),
    );
    renderStrip({ healthMeta: meta({}), formalScenarioDistinct: line });

    const distinct = screen.getByTestId(
      "product-category-formal-scenario-meta-distinct",
    );
    expect(distinct).toHaveTextContent("t_formal");
    expect(distinct).toHaveTextContent("t_scen");
    expect(distinct).toHaveTextContent("正式口径=正式口径");
    expect(distinct).toHaveTextContent("情景口径=情景口径");

    renderStrip({ healthMeta: meta({}), formalScenarioDistinct: null });
    expect(
      screen.queryAllByTestId("product-category-formal-scenario-meta-distinct"),
    ).toHaveLength(1);
  });
});

describe("product-category-pnl 情景切换展示不重算（模型契约）", () => {
  it("scenario 载荷整体替换基线行并逐字透传，前端不合并、不重算", () => {
    const baselineRows = envelope.result.rows;
    expect(baselineRows.length).toBeGreaterThan(1);

    const scenarioRows = [
      { ...baselineRows[0]!, business_net_income: "123.456789" },
    ];
    const displayed = selectProductCategoryDetailRows(
      baselineRows,
      scenarioRows,
    );
    expect(displayed).toHaveLength(1);
    expect(displayed[0]!.business_net_income).toBe("123.456789");

    const baselineDisplayed = selectProductCategoryDetailRows(
      baselineRows,
      undefined,
    );
    for (const row of baselineDisplayed) {
      const source = baselineRows.find(
        (candidate) => candidate.category_id === row.category_id,
      );
      expect(row.business_net_income).toBe(source?.business_net_income);
    }
  });

  it("表体剔除 grand_total；总计取后端行（scenario 优先、baseline 兜底），不由前端求和", () => {
    const baselineRows = envelope.result.rows;
    const withTotal = [
      { ...baselineRows[0]!, category_id: "grand_total", is_total: true },
      baselineRows[1]!,
    ];
    const displayed = selectProductCategoryDetailRows(withTotal, undefined);
    expect(
      displayed.some((row) => row.category_id === "grand_total"),
    ).toBe(false);

    expect(
      selectDisplayedProductCategoryGrandTotal(
        { business_net_income: "2.22" },
        { business_net_income: "1.11" },
      )?.business_net_income,
    ).toBe("2.22");
    expect(
      selectDisplayedProductCategoryGrandTotal(undefined, {
        business_net_income: "1.11",
      })?.business_net_income,
    ).toBe("1.11");
    expect(
      selectDisplayedProductCategoryGrandTotal(undefined, undefined),
    ).toBeUndefined();
  });
});

describe("product-category-pnl 降级状态可见（fallback/vendor/quality）", () => {
  it("三类降级 meta 渲染为可见治理公告（role=status）", () => {
    renderStrip({
      healthMeta: meta({}),
      noticeMeta: meta({
        fallback_mode: "latest_snapshot",
        vendor_status: "vendor_stale",
        quality_flag: "stale",
      }),
    });

    const fallback = screen.getByTestId(
      "product-category-governance-notice-fallback_mode",
    );
    const vendor = screen.getByTestId(
      "product-category-governance-notice-vendor_status",
    );
    const quality = screen.getByTestId(
      "product-category-governance-notice-quality_flag",
    );
    expect(fallback).toHaveTextContent("降级模式");
    expect(vendor).toHaveTextContent("供应商状态");
    expect(quality).toHaveTextContent("质量标记");
    for (const notice of [fallback, vendor, quality]) {
      expect(notice).toHaveAttribute("role", "status");
    }
  });

  it("干净 meta 不渲染任何治理公告", () => {
    renderStrip({ healthMeta: meta({}), noticeMeta: meta({}) });

    expect(
      screen.queryByTestId("product-category-governance-notice-fallback_mode"),
    ).toBeNull();
    expect(
      screen.queryByTestId("product-category-governance-notice-vendor_status"),
    ).toBeNull();
    expect(
      screen.queryByTestId("product-category-governance-notice-quality_flag"),
    ).toBeNull();
  });
});
