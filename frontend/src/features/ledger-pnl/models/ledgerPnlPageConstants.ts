export const LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID = "ledger-pnl-formal-indicator-source-contract-panel";
export const LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID =
  "ledger-pnl-formal-indicator-source-contract-release-gate";
export const LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID =
  "ledger-pnl-formal-indicator-source-contract-material-checklist";
export const LEDGER_PNL_REPORT_DATE_SELECT_ID = "ledger-pnl-report-date-select";
export const LEDGER_PNL_RULE_CHECKS_PANEL_ID = "ledger-pnl-formal-indicator-rule-checks-panel";
/** 章节锚点：整页高度远超一屏，导航条与各区块靠这组 id 对齐。 */
export const LEDGER_PNL_SECTION_IDS = {
  verdict: "ledger-pnl-section-verdict",
  summary: "ledger-pnl-section-summary",
  analysis: "ledger-pnl-section-analysis",
  indicators: "ledger-pnl-section-indicators",
  candidate: "ledger-pnl-section-candidate",
  reconciliation: "ledger-pnl-section-reconciliation",
  accounts: "ledger-pnl-section-accounts",
  detail: "ledger-pnl-section-detail",
  evidence: "ledger-pnl-section-evidence",
} as const;
export const LEDGER_PNL_CURRENCY_BASIS_OPTIONS = [
  { value: "CNX", label: "CNX（综本）" },
  { value: "CNY", label: "CNY（人民币账）" },
] as const;

export type LedgerPnlCurrencyBasis = (typeof LEDGER_PNL_CURRENCY_BASIS_OPTIONS)[number]["value"];

export function normalizeLedgerPnlCurrencyBasis(value: string | null | undefined): LedgerPnlCurrencyBasis {
  return value?.trim() === "CNY" ? "CNY" : "CNX";
}
