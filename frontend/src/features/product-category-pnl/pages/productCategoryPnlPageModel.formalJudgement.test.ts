import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";

import { buildProductCategoryDataHealth } from "./productCategoryPnlPageModel";

const envelope = buildMockProductCategoryPnlEnvelope({
  reportDate: "2026-02-28",
  view: "monthly",
});

const formalMeta: ResultMeta = {
  ...envelope.result_meta,
  basis: "formal",
  formal_use_allowed: true,
  scenario_flag: false,
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
};

function buildHealth(meta: ResultMeta | null | undefined) {
  return buildProductCategoryDataHealth({
    datesLoading: false,
    datesError: false,
    reportDates: [envelope.result.report_date],
    selectedDate: envelope.result.report_date,
    baselineLoading: false,
    baselineError: false,
    baseline: envelope.result,
    meta,
  });
}

describe("buildProductCategoryDataHealth formal judgement gate", () => {
  it.each([
    ["basis is not formal", { basis: "analytical" }],
    ["formal use is not allowed", { formal_use_allowed: false }],
    ["the payload is a scenario", { scenario_flag: true }],
  ] satisfies Array<[string, Partial<ResultMeta>]>)(
    "blocks operating judgement when %s",
    (_reason, metaOverrides) => {
      expect(
        buildHealth({ ...formalMeta, ...metaOverrides }),
      ).toMatchObject({
        state: "degraded",
        judgementState: "blocked",
        judgementLabel: "正式判断阻断",
      });
    },
  );

  it("fails closed when result metadata is absent", () => {
    expect(buildHealth(undefined)).toMatchObject({
      state: "degraded",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
    });
  });

  it("allows operating judgement only for a clean formal baseline", () => {
    expect(buildHealth(formalMeta)).toMatchObject({
      state: "ready",
      judgementState: "allowed",
      judgementLabel: "可用于经营判断",
    });
  });
});
