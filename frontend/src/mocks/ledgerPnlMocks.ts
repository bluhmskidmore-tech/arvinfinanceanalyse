/**
 * Mock payloads for the Ledger P&L domain.
 * Extracted from client.ts to reduce monolith size.
 */
import type {
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  LedgerPnlDataPayload,
} from "../api/contracts";

const mockLedgerMoney = (yuan: string) => ({
  yuan,
  yi: (Number(yuan) / 100_000_000).toFixed(2),
  wan: (Number(yuan) / 10_000).toFixed(2),
});

export const mockLedgerPnlDates: LedgerPnlDatesPayload = {
  dates: ["2025-12-31", "2025-11-30"],
};

export const mockLedgerPnlSummary: LedgerPnlSummaryPayload = {
  report_date: "2025-12-31",
  source_version: "sv_mock_ledger",
  ledger_total_assets: mockLedgerMoney("1250000000"),
  ledger_total_liabilities: mockLedgerMoney("980000000"),
  ledger_net_assets: mockLedgerMoney("270000000"),
  ledger_monthly_pnl_core: mockLedgerMoney("3520000"),
  ledger_monthly_pnl_all: mockLedgerMoney("4180000"),
  by_currency: [
    { currency: "CNX", total_pnl: mockLedgerMoney("3010000") },
    { currency: "CNY", total_pnl: mockLedgerMoney("510000") },
  ],
  by_account: [
    {
      account_code: "514100",
      account_name: "利息收入",
      total_pnl: mockLedgerMoney("2120000"),
      count: 18,
    },
    {
      account_code: "516100",
      account_name: "公允价值变动损益",
      total_pnl: mockLedgerMoney("880000"),
      count: 9,
    },
  ],
};

export const mockLedgerPnlData: LedgerPnlDataPayload = {
  report_date: "2025-12-31",
  items: [
    {
      account_code: "514100",
      account_name: "利息收入",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("101200000"),
      ending_balance: mockLedgerMoney("106500000"),
      monthly_pnl: mockLedgerMoney("880000"),
      daily_avg_balance: mockLedgerMoney("104100000"),
      days_in_period: 31,
    },
    {
      account_code: "516100",
      account_name: "公允价值变动损益",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("10000000"),
      ending_balance: mockLedgerMoney("11200000"),
      monthly_pnl: mockLedgerMoney("420000"),
      daily_avg_balance: mockLedgerMoney("10600000"),
      days_in_period: 31,
    },
  ],
  summary: {
    total_pnl_cnx: mockLedgerMoney("1300000"),
    total_pnl_cny: mockLedgerMoney("0"),
    total_pnl: mockLedgerMoney("1300000"),
    count: 2,
  },
};
