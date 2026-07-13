import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildCandidateNetInterestComponentDetailCsv,
  buildCandidateNetInterestComponentSourceLocator,
  downloadCandidateNetInterestComponentDetailCsv,
} from "../features/ledger-pnl/models/candidateNetInterestComponentDetailExport";
import { buildCandidateNetInterestComponentDetailViewModel } from "../features/ledger-pnl/models/candidateNetInterestComponentDetailModel";
import { buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail } from "../mocks/ledgerPnlMocks";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function buildAvailableModel() {
  const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
    "202606",
    "income.interest.investment",
    "b".repeat(64),
  );
  const secondRow = structuredClone(payload.rows[0]);
  secondRow.account_name = "=HYPERLINK(\"https://example.invalid\",\"收益, 测试\")";
  secondRow.current_value_yi = "-999999999999999999.000000001";
  payload.rows.push(secondRow);
  const model = buildCandidateNetInterestComponentDetailViewModel(
    payload,
    "202606",
    "income.interest.investment",
    "b".repeat(64),
  );
  if (model.state !== "available") throw new Error(`expected available, received ${model.state}`);
  return model;
}

describe("candidate net-interest component detail export", () => {
  it("exports the filtered backend-order view with raw Decimal, evidence, and governance fields", () => {
    const model = buildAvailableModel();
    const firstSource = model.rows[0].sourceEvidence[0];

    const artifact = buildCandidateNetInterestComponentDetailCsv(model, model.rows);

    expect(artifact.filename).toBe(
      "ledger-pnl-net-interest-component-202606-income.interest.investment.csv",
    );
    expect(artifact.content.startsWith("\uFEFF")).toBe(true);
    expect(artifact.content.replace(/\r\n/g, "")).not.toContain("\n");
    expect(artifact.content).toContain('"backend_position","row_status","account_code"');
    expect(artifact.content).toContain('"current_value_yi"');
    expect(artifact.content).toContain('"source_1_file","source_1_sheet","source_1_ending_cell"');
    expect(artifact.content).toContain('"source_3_ledger_sha256","source_3_locked_sha256","source_3_lock_status"');
    expect(artifact.content).toContain(
      '"contract_version","analysis_kind","status","quality_status","formal_use_allowed","certification_effect","driver_status"',
    );
    expect(artifact.content).toContain(
      '"candidate-financial-indicator-component-detail-v1","accounting_component_account_detail","available","degraded_candidate","false","none","unclear"',
    );
    expect(artifact.content).not.toContain('"metric_status"');
    expect(artifact.content).not.toContain('"candidate"');
    expect(artifact.content).toContain('"总账对账202606.xlsx","综本","Q12","12","A12"');
    expect(artifact.content).toContain(
      `"${firstSource.ledger_sha256}","${firstSource.locked_sha256}","locked_match"`,
    );
    expect(artifact.content).toContain('"-999999999999999999.000000001"');
    expect(artifact.content).not.toContain('"\'-999999999999999999.000000001"');
    expect(artifact.content).toContain(
      '"\'=HYPERLINK(""https://example.invalid"",""收益, 测试"")"',
    );
    const firstPosition = artifact.content.indexOf('"1","contributing"');
    const secondPosition = artifact.content.indexOf('"2","contributing"');
    expect(firstPosition).toBeGreaterThan(0);
    expect(secondPosition).toBeGreaterThan(firstPosition);
    expect(artifact.content.split("\r\n")).toHaveLength(4);
  });

  it("uses one shared, complete source locator for CSV and clipboard interactions", () => {
    const model = buildAvailableModel();
    const evidence = model.rows[0].sourceEvidence[0];

    const locator = buildCandidateNetInterestComponentSourceLocator(
      model,
      model.rows[0],
      evidence,
    );
    expect(locator).toBe(
      `报告月 202606 | 指标 income.interest.investment 金融投资利息收入 | 后端位置 #1 | 科目 51402010003 其他公允价值变动计入损益的金融资产利息收入 | 证据月 202606 | 总账对账202606.xlsx | 综本!Q12 | 行12 | 科目格A12 | SHA256 ${evidence.ledger_sha256} | 锁定哈希 ${evidence.locked_sha256} | locked_match`,
    );
    expect(buildCandidateNetInterestComponentDetailCsv(model, model.rows).content).toContain(locator);
  });

  it("downloads once and always revokes the object URL", () => {
    const model = buildAvailableModel();
    const artifact = buildCandidateNetInterestComponentDetailCsv(model, model.rows.slice(0, 1));
    const createObjectURL = vi.fn(() => "blob:component-detail");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadCandidateNetInterestComponentDetailCsv(artifact);

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:component-detail");
    expect(document.querySelector(`a[download="${artifact.filename}"]`)).not.toBeInTheDocument();
  });
});
