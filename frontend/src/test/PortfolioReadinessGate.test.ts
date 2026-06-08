import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../api/contracts";
import {
  buildPortfolioReadinessGate,
  type PortfolioEvidenceSource,
} from "../features/workbench/module-home/portfolioReadinessGate";

function meta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "portfolio_gate_trace",
    basis: "formal",
    result_kind: "portfolio.gate.test",
    formal_use_allowed: true,
    source_version: "sv_portfolio_gate",
    vendor_version: "vv_portfolio_gate",
    rule_version: "rv_portfolio_gate",
    cache_version: "cv_portfolio_gate",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    requested_report_date: "2026-05-31",
    resolved_report_date: "2026-05-31",
    as_of_date: "2026-05-31",
    generated_at: "2026-06-01T00:00:00Z",
    tables_used: ["fact_formal_portfolio_gate"],
    evidence_rows: 1710,
    ...overrides,
  };
}

function source(label: string, reportDate = "2026-05-31", overrides: Partial<ResultMeta> = {}): PortfolioEvidenceSource {
  return {
    label,
    hasData: true,
    reportDate,
    meta: meta(overrides),
  };
}

function buildGate(overrides: {
  sources?: PortfolioEvidenceSource[];
  riskDates?: string[];
  riskMeta?: Partial<ResultMeta>;
} = {}) {
  return buildPortfolioReadinessGate({
    decisionAnchorDate: "2026-05-31",
    readPathTone: "ok",
    hasCoreReads: true,
    evidenceSources:
      overrides.sources ??
      [
        source("债券总览"),
        source("风险指标"),
        source("资产负债"),
        source("损益归因"),
      ],
    riskDatesEvidence: {
      hasData: true,
      dates: overrides.riskDates ?? ["2026-05-31"],
      meta: meta({
        result_kind: "risk.tensor.dates",
        ...overrides.riskMeta,
      }),
    },
  });
}

describe("portfolio readiness gate", () => {
  it("allows decision and risk closure only when every page source has same-day payload and metadata", () => {
    const gate = buildGate();

    expect(gate.decisionReady).toBe(true);
    expect(gate.riskClosureReady).toBe(true);
    expect(gate.riskClosureFact).toBe("同日闭合 2026-05-31");
    expect(gate.blockingReasons).toEqual([]);
    expect(gate.sourceDates).toContain("债券总览=2026-05-31");
    expect(gate.sourceDates).toContain("资产负债=2026-05-31");
    expect(gate.sourceDates).toContain("损益归因=2026-05-31");
  });

  it("blocks decision-grade evidence when a cross-page source has a different metadata date", () => {
    const gate = buildGate({
      sources: [
        source("债券总览"),
        source("风险指标"),
        source("资产负债", "2026-05-31", {
          resolved_report_date: "2026-05-30",
          as_of_date: "2026-05-30",
        }),
        source("损益归因"),
      ],
    });

    expect(gate.decisionReady).toBe(false);
    expect(gate.riskClosureReady).toBe(true);
    expect(gate.blockingReasons).toContain("资产负债 meta_date=2026-05-30");
    expect(gate.riskClosureFact).toBe("同日闭合 2026-05-31");
  });

  it("blocks decision-grade evidence when any metadata date field differs", () => {
    const gate = buildGate({
      sources: [
        source("bond"),
        source("risk"),
        source("balance", "2026-05-31", {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: "2026-05-30",
        }),
        source("pnl"),
      ],
    });

    expect(gate.decisionReady).toBe(false);
    expect(gate.blockingReasons).toContain("balance meta_date=2026-05-30");
  });

  it("blocks decision-grade evidence when any metadata date field is missing", () => {
    const gate = buildGate({
      sources: [
        source("bond"),
        source("risk"),
        source("balance", "2026-05-31", {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: null,
        }),
        source("pnl"),
      ],
    });

    expect(gate.decisionReady).toBe(false);
    expect(gate.blockingReasons).toContain("balance report_date 缺失");
  });

  it("blocks same-day risk closure when risk dates include the anchor but metadata is not same-day", () => {
    const gate = buildGate({
      riskDates: ["2026-05-31"],
      riskMeta: {
        resolved_report_date: "2026-05-30",
        as_of_date: "2026-05-30",
      },
    });

    expect(gate.decisionReady).toBe(true);
    expect(gate.riskClosureReady).toBe(false);
    expect(gate.riskClosureFact).toContain("风险闭合证据 meta_date=2026-05-30");
    expect(gate.riskClosureFact).not.toContain("同日闭合");
  });

  it("blocks same-day risk closure when any risk metadata date field differs", () => {
    const gate = buildGate({
      riskDates: ["2026-05-31"],
      riskMeta: {
        resolved_report_date: "2026-05-31",
        requested_report_date: "2026-05-31",
        as_of_date: "2026-05-30",
      },
    });

    expect(gate.riskClosureReady).toBe(false);
    expect(gate.riskClosureFact).toContain("风险闭合证据 meta_date=2026-05-30");
    expect(gate.riskClosureFact).not.toContain("同日闭合");
  });

  it("blocks same-day risk closure when any risk metadata date field is missing", () => {
    const gate = buildGate({
      riskDates: ["2026-05-31"],
      riskMeta: {
        resolved_report_date: "2026-05-31",
        requested_report_date: "2026-05-31",
        as_of_date: null,
      },
    });

    expect(gate.riskClosureReady).toBe(false);
    expect(gate.riskClosureFact).toContain("风险闭合证据 report_date 缺失");
    expect(gate.riskClosureFact).not.toContain("同日闭合");
  });
});
