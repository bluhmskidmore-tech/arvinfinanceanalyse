import type { ColDef, ITooltipParams, ValueFormatterParams } from "ag-grid-community";
import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import { buildWorkbookGridColumnDefs } from "./balanceAnalysisGridColumns";

function display(field: string, value: unknown): string {
  const column: ColDef = buildWorkbookGridColumnDefs([{ key: field, label: field }])[0];
  if (typeof column.valueFormatter !== "function") {
    throw new Error("Workbook column must have a cell formatter");
  }
  return column.valueFormatter({ value, colDef: column } as ValueFormatterParams);
}

describe("FIN002 workbook income and coverage columns", () => {
  it("keeps diagnostic columns available while disclosing their values in coverage tooltips", () => {
    const keys = ["known_coupon_income_amount", "coupon_coverage_ratio", "coupon_known_abs_face_amount", "coupon_total_abs_face_amount", "coupon_known_count", "coupon_required_count"];
    const columns = buildWorkbookGridColumnDefs(keys.map((key) => ({ key, label: key })));
    expect(columns.filter((column) => !column.hide).map((column) => column.field)).toEqual([
      "known_coupon_income_amount", "coupon_coverage_ratio",
    ]);
    expect(columns.map((column) => column.field)).toEqual(keys);
    const coverage = columns[1];
    expect(coverage.tooltipValueGetter?.({ colDef: coverage, data: {
      coupon_known_abs_face_amount: "10000", coupon_total_abs_face_amount: "20000",
      coupon_known_count: 1, coupon_required_count: 2, coupon_known_balance_amount: "10000",
    } } as ITooltipParams)).toBe("绝对面值覆盖：1.00 亿元 / 2.00 亿元；票息已知/非零面值笔数：1 / 2；已知净面值：1.00 亿元");
  });

  it("discloses the benchmark coverage and each share's actual income denominator", () => {
    const columns = buildWorkbookGridColumnDefs([
      { key: "benchmark_coupon_coverage_ratio", label: "基准绝对面值覆盖率" },
      { key: "share_of_income", label: "占完整组合票息收入比重" },
      { key: "known_share_of_income", label: "占已知组合票息收入比重" },
    ]);
    const data = {
      benchmark_known_abs_face_amount: "10000", benchmark_total_abs_face_amount: "20000",
      benchmark_coupon_known_count: 1, benchmark_coupon_required_count: 2, benchmark_balance_amount: "0",
      portfolio_coupon_coverage_status: "部分缺失", total_coupon_income_amount: null,
      known_total_coupon_income_amount: "700",
    };
    expect(columns[0].tooltipValueGetter?.({ colDef: columns[0], data } as ITooltipParams)).toBe(
      "绝对面值覆盖：1.00 亿元 / 2.00 亿元；票息已知/非零面值笔数：1 / 2；基准净面值：0.00 亿元",
    );
    expect(columns[1].tooltipValueGetter?.({ colDef: columns[1], data } as ITooltipParams)).toBe(
      `组合票息覆盖状态：部分缺失；完整组合票息收入：${EM_DASH}`,
    );
    expect(columns[2].tooltipValueGetter?.({ colDef: columns[2], data } as ITooltipParams)).toBe(
      "已知组合票息收入小计：0.07 亿元",
    );
  });

  it.each([
    "known_coupon_income_amount",
    "known_spread_income_amount",
    "known_total_coupon_income_amount",
    "total_coupon_income_amount",
    "coupon_known_balance_amount",
    "coupon_known_abs_face_amount",
    "coupon_total_abs_face_amount",
    "benchmark_balance_amount",
    "benchmark_known_abs_face_amount",
    "benchmark_total_abs_face_amount",
  ])("formats %s from the API wan-yuan basis", (field) => {
    expect(display(field, "10000")).toBe("1.00 亿元");
    expect(display(field, "-10000")).toBe("-1.00 亿元");
    expect(display(field, null)).toBe(EM_DASH);
  });

  it("renders the mixed-coupon known subtotal and spread without a unit error", () => {
    expect(display("coupon_income_amount", null)).toBe(EM_DASH);
    expect(display("spread_income_amount", null)).toBe(EM_DASH);
    expect(display("known_coupon_income_amount", "400")).toBe("0.04 亿元");
    expect(display("known_spread_income_amount", "100")).toBe("0.01 亿元");
    expect(display("coupon_coverage_ratio", "0.5")).toBe("50.00%");
    expect(display("known_share_of_income", "0.5714285714285714285714285714")).toBe("57.14%");
    expect(display("share_of_income", null)).toBe(EM_DASH);
    expect(display("coupon_coverage_status", "部分缺失")).toBe("部分缺失");
  });

  it.each([
    "coupon_coverage_ratio",
    "benchmark_coupon_coverage_ratio",
    "share_of_income",
    "known_share_of_income",
  ])("formats %s as a ratio and keeps missing distinct from real zero", (field) => {
    expect(display(field, null)).toBe(EM_DASH);
    expect(display(field, "")).toBe(EM_DASH);
    expect(display(field, "  ")).toBe(EM_DASH);
    expect(display(field, "NaN")).toBe(EM_DASH);
    expect(display(field, "0")).toBe("0.00%");
    expect(display(field, "1")).toBe("100.00%");
  });
});
