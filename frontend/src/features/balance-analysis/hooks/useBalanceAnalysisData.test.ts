import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import { formatBalanceWorkbookWanAmountDisplay } from "../pages/balanceAnalysisPageModel";
import type { ResultMeta } from "../../../api/contracts";
import { buildBalanceDistributionEvidence, yuanAmountToWanString } from "./useBalanceAnalysisData";

describe("balance distribution evidence", () => {
  const meta: ResultMeta = {
    trace_id: "movement-evidence", basis: "analytical", result_kind: "movement",
    formal_use_allowed: false, source_version: "movement-source", vendor_version: "none",
    rule_version: "rule", cache_version: "cache", quality_flag: "ok", vendor_status: "ok",
    fallback_mode: "none", scenario_flag: false, generated_at: "2026-01-02T00:00:00Z",
  };
  const input = { linked: true, reportDate: "2025-12-31", requestedReportDate: "2025-12-31", meta, loading: false, failed: false };

  it("keeps the actual source metadata and date together when movement is healthy", () => {
    const evidence = buildBalanceDistributionEvidence(input);
    expect(evidence).toMatchObject({ source: "余额变动", reportDate: "2025-12-31", meta });
    expect(evidence.stateSurfaces).toEqual([]);
  });

  it.each([
    ["stale", "stale"], ["warning", "definition-pending"], ["error", "error"], ["missing", "error"],
  ] as const)("discloses movement %s as %s without changing its source", (quality_flag, variant) => {
    const evidence = buildBalanceDistributionEvidence({ ...input, meta: { ...meta, quality_flag } });
    expect(evidence.source).toBe("余额变动");
    expect(evidence.stateSurfaces).toEqual([expect.objectContaining({ variant })]);
  });

  it("uses the data's actual month when the response falls back", () => {
    const evidence = buildBalanceDistributionEvidence({ ...input, reportDate: "2025-11-30" });
    expect(evidence.reportDate).toBe("2025-11-30");
    expect(evidence.stateSurfaces).toEqual([expect.objectContaining({ variant: "fallback-date", description: expect.stringContaining("2025-11-30") })]);
  });

  it.each([[true, "error"], [false, "definition-pending"]] as const)("discloses failed=%s while preserving workbook fallback", (failed, variant) => {
    const workbookMeta = { ...meta, source_version: "workbook-source" };
    const evidence = buildBalanceDistributionEvidence({ ...input, linked: false, failed, meta: workbookMeta });
    expect(evidence.source).toBe("工作簿");
    expect(evidence.meta).toBe(workbookMeta);
    expect(evidence.stateSurfaces).toEqual([expect.objectContaining({ variant })]);
  });
});

describe("yuanAmountToWanString", () => {
  it("maps null, undefined, and empty string to missing (EM_DASH)", () => {
    expect(yuanAmountToWanString(null)).toBe(EM_DASH);
    expect(yuanAmountToWanString(undefined)).toBe(EM_DASH);
    expect(yuanAmountToWanString("")).toBe(EM_DASH);
    expect(yuanAmountToWanString("   ")).toBe(EM_DASH);
  });

  it("keeps a true zero as 0 instead of missing", () => {
    expect(yuanAmountToWanString(0)).toBe("0");
    expect(yuanAmountToWanString("0")).toBe("0");
    expect(yuanAmountToWanString("0.00")).toBe("0");
    expect(yuanAmountToWanString("-0")).toBe("0");
  });

  it("converts yuan to wan without floating-point regression", () => {
    expect(yuanAmountToWanString("199451000000.00")).toBe("19945100");
    expect(yuanAmountToWanString("12345.67")).toBe("1.234567");
    expect(yuanAmountToWanString("-20000")).toBe("-2");
    expect(yuanAmountToWanString("12,345,000")).toBe("1234.5");
  });

  it("renders downstream workbook amounts as EM_DASH, not 0 or NaN", () => {
    expect(formatBalanceWorkbookWanAmountDisplay(yuanAmountToWanString(null))).toBe(EM_DASH);
    expect(formatBalanceWorkbookWanAmountDisplay(yuanAmountToWanString(undefined))).toBe(EM_DASH);
    expect(formatBalanceWorkbookWanAmountDisplay(yuanAmountToWanString(""))).toBe(EM_DASH);
    expect(formatBalanceWorkbookWanAmountDisplay(yuanAmountToWanString("0"))).toBe("0.00 亿元");
    expect(formatBalanceWorkbookWanAmountDisplay(yuanAmountToWanString("199451000000.00"))).toBe(
      "1,994.51 亿元",
    );
  });
});
