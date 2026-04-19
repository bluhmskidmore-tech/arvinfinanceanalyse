import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "..");
const CONTRACTS_PATH = resolve(ROOT, "api/contracts.ts");
const FEATURE_TYPES_PATH = resolve(ROOT, "features/bond-analytics/types.ts");

describe("bond analytics payload contract location", () => {
  it("keeps major bond analytics API payloads in api/contracts.ts and only aliases them in feature types", () => {
    const contractsText = readFileSync(CONTRACTS_PATH, "utf8");
    const featureTypesText = readFileSync(FEATURE_TYPES_PATH, "utf8");

    for (const name of [
      "AssetClassBreakdown",
      "BondLevelDecomposition",
      "ReturnDecompositionPayload",
      "ExcessSourceBreakdown",
      "BenchmarkExcessPayload",
      "ActionTypeSummary",
      "ActionDetail",
      "ActionAttributionPayload",
      "AccountingClassAuditItem",
      "AccountingClassAuditPayload",
    ]) {
      expect(contractsText).toContain(`export type ${name}`);
    }

    expect(featureTypesText).not.toContain("export interface AssetClassBreakdown");
    expect(featureTypesText).not.toContain("export interface BondLevelDecomposition");
    expect(featureTypesText).not.toContain("export interface ReturnDecompositionResponse");
    expect(featureTypesText).not.toContain("export interface ExcessSourceBreakdown");
    expect(featureTypesText).not.toContain("export interface BenchmarkExcessResponse");
    expect(featureTypesText).not.toContain("export interface ActionTypeSummary");
    expect(featureTypesText).not.toContain("export interface ActionDetail");
    expect(featureTypesText).not.toContain("export interface ActionAttributionResponse");
    expect(featureTypesText).not.toContain("export interface AccountingClassAuditItem");
    expect(featureTypesText).not.toContain("export interface AccountingClassAuditResponse");

    expect(featureTypesText).toContain("export type ReturnDecompositionResponse = ApiReturnDecompositionPayload;");
    expect(featureTypesText).toContain("export type BenchmarkExcessResponse = ApiBenchmarkExcessPayload;");
    expect(featureTypesText).toContain("export type ActionAttributionResponse = ApiActionAttributionPayload;");
    expect(featureTypesText).toContain("export type AccountingClassAuditResponse = ApiAccountingClassAuditPayload;");

    expect(contractsText).toContain("bond_name: string | null;");
    expect(contractsText).toContain("convexity_effect: Numeric;");
    expect(contractsText).toContain("tracking_error: Numeric | null;");
    expect(contractsText).toContain("information_ratio: Numeric | null;");
  });
});
