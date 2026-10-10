import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import type { ResultMeta } from "../../../api/contracts";
import { mockCampisiEnhanced, mockCampisiMaturityBuckets } from "../../../mocks/campisiMocks";
import { AdvancedAttributionTabPanels } from "./PnlAttributionAdvancedTab";

vi.mock("../../../lib/echarts", () => ({ default: () => <div /> }));

function sourceMeta(patch: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "campisi-quality-test",
    basis: "formal",
    result_kind: "campisi.enhanced",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "error",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-09-09T00:00:00Z",
    ...patch,
  };
}

function props(meta: ResultMeta): ComponentProps<typeof AdvancedAttributionTabPanels> {
  return {
    carryData: null, spreadData: null, krdData: null, summaryData: null, campisiData: null,
    campisiFourEffects: null, campisiDecisionGrade: null,
    campisiEnhanced: mockCampisiEnhanced,
    campisiMaturityBuckets: { ...mockCampisiMaturityBuckets, basis: "formal_report_pnl_bridge" },
    carryMeta: null, spreadMeta: null, krdMeta: null, summaryMeta: null, campisiFourMeta: null,
    campisiEnhancedMeta: meta, campisiMaturityMeta: meta, campisiDecisionGradeMeta: null,
    isLoading: false, errorMessage: null, decisionGradeErrorMessage: null, onRetry: () => {},
  };
}

describe("Campisi enhanced and maturity source quality wiring", () => {
  it("shows a quality-only error by both panels while keeping their amounts visible", () => {
    render(<AdvancedAttributionTabPanels {...props(sourceMeta())} />);

    expect(screen.getByTestId("campisi-enhanced-quality-warning")).toHaveTextContent("数据质量错误");
    expect(screen.getByTestId("campisi-maturity-quality-warning")).toHaveTextContent("数据质量错误");
    expect(screen.getByTestId("campisi-enhanced-amount-income_return")).toHaveTextContent("0.01 亿");
    expect(screen.getByRole("cell", { name: "0-1Y" })).toBeInTheDocument();
  });

  it("does not claim a fallback date when upstream supplies only the report date", () => {
    render(<AdvancedAttributionTabPanels {...props(sourceMeta({
      fallback_mode: "latest_snapshot", fallback_date: null, as_of_date: "2026-08-31",
    }))} />);

    for (const id of ["campisi-enhanced-quality-warning", "campisi-maturity-quality-warning"]) {
      expect(screen.getByTestId(id)).toHaveTextContent("来源日期未提供");
      expect(screen.getByTestId(id)).not.toHaveTextContent("2026-08-31");
    }
  });

  it("does not add source quality warnings for healthy bridge metadata", () => {
    render(<AdvancedAttributionTabPanels {...props(sourceMeta({ quality_flag: "ok" }))} />);
    expect(screen.queryByTestId("campisi-enhanced-quality-warning")).not.toBeInTheDocument();
    expect(screen.queryByTestId("campisi-maturity-quality-warning")).not.toBeInTheDocument();
  });
});
