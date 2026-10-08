import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createApiClient } from "../../../api/client";
import { BusinessBalanceMatrixSection } from "../components/BalanceMovementBusinessTables";
import { trendDelta } from "./balanceMovementBusinessModel";
import { buildExplanationClosure } from "./balanceMovementDiagnostics";
import { buildBalanceMovementCsv } from "./balanceMovementCsv";

describe("monthly read evidence contracts", () => {
  it.each([null, "", "   ", undefined])("keeps an absent comparison value missing: %s", (missing) => {
    expect(trendDelta("120", missing)).toBeNull();
    expect(trendDelta(missing, "100")).toBeNull();
    expect(trendDelta("0", "0")).toBe(0);
  });

  it("does not infer zero residual from a missing residual component amount", async () => {
    const { result } = await createApiClient({ mode: "mock" }).getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const waterfall = result.difference_attribution_waterfall!;
    waterfall.components = [{ ...waterfall.components[0], is_residual: true, amount: "" }];
    expect(buildExplanationClosure({ waterfall, summary: { ...result.summary, balance_change_total: "10" } })?.residualRatioPct).toBeNull();
  });

  it("labels the actual first observed month rather than a year opening", () => {
    const months = ["2026-03", "2026-06"].map((month) => ({ report_date: `${month}-30`, report_month: month, asset_balance_total: "0", liability_balance_total: "0", net_balance_total: "0", rows: [] }));
    render(<BusinessBalanceMatrixSection months={months} liabilityRows={[]} projectRows={[]} balanceRows={[]} accountingSnapshotsAreNonAdjacent />);
    expect(screen.getByRole("columnheader", { name: "较基期 2026年3月" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "较年初" })).not.toBeInTheDocument();
  });

  it("exports the selected bucket with requested/resolved dates, both currency sources and closure definitions", async () => {
    const { result, result_meta } = await createApiClient({ mode: "mock" }).getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    result.rows = result.rows.map((row) => ({ ...row, position_source_basis: "CNX" }));
    result.zqtz_maturity_structure = { meta: { ...result.basis_movement_decomposition!.meta, zqtz_currency_basis: "CNY" }, buckets: [] };
    const csv = buildBalanceMovementCsv({ result, resultMeta: result_meta, businessTopMove: undefined, accountingTopDriver: undefined, residualComponent: undefined, unsupportedComponents: [], maturityStructure: null, concentrationAnalysis: null, explanationClosure: null, dimensionCards: [], historicalAnomalyDiagnostics: { sampleCount: 0, baselinePairCount: 0, headline: "", accountingSignals: [], businessSignals: [] }, selectedBucket: "OCI", requestedReportDate: "2020-01-31" });
    expect(csv).toContain("meta,requested_report_date,2020-01-31");
    expect(csv).toContain("meta,selected_bucket,OCI");
    expect(csv).toContain("position_source_basis");
    expect(csv).toContain("detail_position_currency_basis,CNY");
    expect(csv).toContain("同日报表桥的残差已计入分项，算术闭合不表示差异已被解释");
    expect(csv).toContain("跨期分类驱动的期末校验等于未解释残差");
    expect(csv).not.toMatch(/\r\nAC,/);
    expect(csv).not.toMatch(/\r\nTPL,/);
    expect(csv).toMatch(/\r\nOCI,/);
  });
});
