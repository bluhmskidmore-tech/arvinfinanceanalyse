import { positionsParams } from "../api/ledgerClient";
import type {
  LedgerClientMethods,
  LedgerPositionItem,
  LedgerPositionsOptions,
  LedgerResponseMetadata,
  LedgerResponseTrace,
} from "../api/ledgerClient";

const mockMetadata: LedgerResponseMetadata = {
  source_version: "sv_ledger_mock_20260317",
  rule_version: "rv_ledger_classification_v2",
  batch_id: 1,
  stale: false,
  fallback: false,
  no_data: false,
};

const mockTrace: LedgerResponseTrace = {
  request_id: "req_ledger_mock",
  requested_as_of_date: "2026-03-17",
  resolved_as_of_date: "2026-03-17",
  batch_id: 1,
  filters: null,
};

const mockPositions: LedgerPositionItem[] = [
  {
    position_key: "ledger:asset:20260317:0001",
    batch_id: 1,
    row_no: 1,
    as_of_date: "2026-03-17",
    bond_code: "ASSET-001",
    bond_name: "资产样例债券",
    portfolio: "银行账簿",
    direction: "ASSET",
    business_type: "投资",
    business_type_1: "债券",
    account_category_std: "银行账户",
    cost_center: "总行",
    asset_class_std: "持有至到期类资产",
    channel: "ZQTZSHOW",
    currency: "CNY",
    face_amount: 100_000_000,
    fair_value: 99_500_000,
    amortized_cost: 100_100_000,
    accrued_interest: 120_000,
    interest_receivable_payable: 50_000,
    quantity: 1_000_000,
    latest_face_value: 100,
    interest_method: "fixed",
    coupon_rate: 0.03,
    yield_to_maturity: 0.031,
    interest_start_date: "2025-03-17",
    maturity_date: "2028-03-17",
    counterparty_name_cn: "样例发行人A",
    legal_customer_name: "样例发行人A",
    group_customer_name: "样例集团A",
    trace: {
      position_key: "ledger:asset:20260317:0001",
      batch_id: 1,
      row_no: 1,
    },
  },
  {
    position_key: "ledger:liability:20260317:0002",
    batch_id: 1,
    row_no: 2,
    as_of_date: "2026-03-17",
    bond_code: "LIAB-001",
    bond_name: "发行负债样例债券",
    portfolio: "银行账簿",
    direction: "LIABILITY",
    business_type: "发行",
    business_type_1: "债券",
    account_category_std: "发行类债券",
    cost_center: "总行",
    asset_class_std: "发行类债券",
    channel: "ZQTZSHOW",
    currency: "CNY",
    face_amount: 50_000_000,
    fair_value: 49_800_000,
    amortized_cost: 50_020_000,
    accrued_interest: 60_000,
    interest_receivable_payable: 20_000,
    quantity: 500_000,
    latest_face_value: 100,
    interest_method: "fixed",
    coupon_rate: 0.025,
    yield_to_maturity: 0.026,
    interest_start_date: "2025-03-17",
    maturity_date: "2029-03-17",
    counterparty_name_cn: "本行发行",
    legal_customer_name: "本行发行",
    group_customer_name: "本行发行",
    trace: {
      position_key: "ledger:liability:20260317:0002",
      batch_id: 1,
      row_no: 2,
    },
  },
];

export function createMockLedgerClient(): LedgerClientMethods {
  return {
    async getLedgerDates() {
      return {
        data: { items: ["2026-03-17"] },
        metadata: mockMetadata,
        trace: { ...mockTrace, requested_as_of_date: null, resolved_as_of_date: null },
      };
    },
    async getLedgerDashboard(asOfDate: string) {
      const fallback = asOfDate !== "2026-03-17";
      return {
        data: {
          as_of_date: "2026-03-17",
          classification_status: "ready",
          classification_rule_version: "rv_ledger_classification_v2",
          currency_breakdown: [
            { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31, classification_total_row_count: 2, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
            { currency: "USD", asset_face_amount: 2, liability_face_amount: null, net_face_exposure: 2, classification_total_row_count: 1, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
          ],
        },
        metadata: {
          ...mockMetadata,
          stale: fallback,
          fallback,
        },
        trace: {
          ...mockTrace,
          request_id: "req_ledger_dashboard_mock",
          requested_as_of_date: asOfDate,
          resolved_as_of_date: "2026-03-17",
        },
      };
    },
    async getLedgerPositions(options: LedgerPositionsOptions) {
      const items = mockPositions.filter(
        (item) =>
          (!options.direction || item.direction === options.direction) &&
          (!options.currency || item.currency === options.currency.trim().toUpperCase()),
      );
      return {
        data: {
          items,
          page: options.page ?? 1,
          page_size: options.pageSize ?? 50,
          total: items.length,
        },
        metadata: {
          ...mockMetadata,
          no_data: items.length === 0,
          stale: options.asOfDate !== "2026-03-17",
          fallback: options.asOfDate !== "2026-03-17",
        },
        trace: {
          ...mockTrace,
          request_id: "req_ledger_positions_mock",
          requested_as_of_date: options.asOfDate,
          resolved_as_of_date: "2026-03-17",
          filters: positionsParams(options),
        },
      };
    },
    async exportLedgerPositions() {
      return new Blob(["mock ledger positions"], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
    },
    async importLedger(file: File) {
      const runId = `ledger_import:mock:${Date.now()}`;
      return {
        data: { run_id: runId, status: "queued", file_name: file.name },
        trace: { request_id: "req_ledger_import_mock", run_id: runId },
      };
    },
    async getLedgerImportStatus(runId: string) {
      return {
        data: {
          run_id: runId,
          status: "succeeded",
          file_name: "ledger_mock.xlsx",
          batch_id: 1,
          finished_at: new Date().toISOString(),
        },
        trace: { request_id: "req_ledger_import_status_mock", run_id: runId },
      };
    },
  };
}
