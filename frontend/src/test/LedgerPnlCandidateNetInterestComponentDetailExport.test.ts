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

    const artifact = buildCandidateNetInterestComponentDetailCsv(model, model.rows, {
      query: "   ",
      status: "all",
    });

    expect(artifact.filename).toBe(
      "ledger-pnl-net-interest-component-202606-income.interest.investment.csv",
    );
    expect(artifact.content.startsWith("\uFEFF")).toBe(true);
    expect(artifact.content.replace(/\r\n/g, "")).not.toContain("\n");
    expect(artifact.content).toContain('"backend_position","row_status","account_code"');
    expect(artifact.content).toContain(
      '"export_scope","export_query","export_status_filter","exported_row_count","backend_total_row_count","is_complete_view"',
    );
    expect(artifact.content).toContain(
      '"full_detail","","all","2","2","true","1","contributing"',
    );
    expect(artifact.content).toContain('"current_value_yi"');
    expect(artifact.content).toContain('"source_1_file","source_1_sheet","source_1_ending_cell"');
    expect(artifact.content).toContain('"source_3_ledger_sha256","source_3_locked_sha256","source_3_lock_status"');
    expect(artifact.content).toContain(
      '"contract_version","analysis_kind","payload_status","quality_status","formal_use_allowed","certification_effect","driver_status"',
    );
    expect(artifact.content).toContain(
      '"candidate-financial-indicator-component-detail-v1","accounting_component_account_detail","available","degraded_candidate","false","none","unclear"',
    );
    expect(artifact.content).not.toContain('"metric_status"');
    expect(artifact.content).toContain('"full_detail_foot_status"');
    expect(artifact.content).not.toContain('"foot_status"');
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

  it("marks a single-row filtered export with normalized scope metadata and filename", () => {
    const model = buildAvailableModel();

    const artifact = buildCandidateNetInterestComponentDetailCsv(model, model.rows.slice(0, 1), {
      query: "  ALPHA  ",
      status: "contributing",
    });

    expect(artifact.filename).toBe(
      "ledger-pnl-net-interest-component-202606-income.interest.investment-filtered.csv",
    );
    expect(artifact.content).toContain(
      '"current_filtered_view","alpha","contributing","1","2","false","1","contributing"',
    );
  });

  it("derives the backend total from the authoritative model instead of caller metadata", () => {
    const model = buildAvailableModel();
    const untrustedContext = {
      query: "",
      status: "all" as const,
      backendTotalCount: 1,
    };

    const artifact = buildCandidateNetInterestComponentDetailCsv(
      model,
      model.rows.slice(0, 1),
      untrustedContext,
    );

    expect(artifact.filename).toContain("-filtered.csv");
    expect(artifact.content).toContain(
      '"current_filtered_view","","all","1","2","false","1","contributing"',
    );
  });

  it("prefixes spreadsheet formulas after leading controls, spaces, NBSP, or BOM", () => {
    const model = buildAvailableModel();
    const dangerousNames = [
      "\u0001 =SUM(A1:A2)",
      "\u00A0+SUM(A1:A2)",
      "\uFEFF-SUM(A1:A2)",
      "\t@SUM(A1:A2)",
      "\u00A0＝SUM(A1:A2)",
      "\uFEFF＋SUM(A1:A2)",
      "\u0007－SUM(A1:A2)",
      " ＠SUM(A1:A2)",
    ];
    const rows = dangerousNames.map((accountName, index) => ({
      ...model.rows[0],
      backendPosition: index + 1,
      accountName,
    }));

    const artifact = buildCandidateNetInterestComponentDetailCsv(model, rows, {
      query: "",
      status: "all",
    });

    dangerousNames.forEach((accountName) => {
      expect(artifact.content).toContain(`"'${accountName}"`);
    });
  });

  it("normalizes lone CR and LF inside cells while preserving Decimal strings", () => {
    const model = buildAvailableModel();
    const row = {
      ...model.rows[0],
      accountName: "first\rsecond\nthird\r\nfourth",
      currentValueYi: "-999999999999999999.000000001",
    };

    const artifact = buildCandidateNetInterestComponentDetailCsv(model, [row], {
      query: "",
      status: "all",
    });

    expect(artifact.content).toContain('"first\r\nsecond\r\nthird\r\nfourth"');
    expect(artifact.content).toContain('"-999999999999999999.000000001"');
    expect(artifact.content).not.toContain('"\'-999999999999999999.000000001"');
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
    expect(buildCandidateNetInterestComponentDetailCsv(model, model.rows, {
      query: "",
      status: "all",
    }).content).toContain(locator);
  });

  it("downloads once and always revokes the object URL", () => {
    const model = buildAvailableModel();
    const artifact = buildCandidateNetInterestComponentDetailCsv(model, model.rows.slice(0, 1), {
      query: "",
      status: "all",
    });
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
