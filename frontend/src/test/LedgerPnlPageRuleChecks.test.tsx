import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";
import { mockLedgerPnlFormalIndicatorRuleChecks202603 } from "../mocks/ledgerPnlMocks";

/**
 * Focused tests for the "规则符合性检查" (formal indicator rule checks) panel.
 * Kept in a separate file rather than growing the already large LedgerPnlPage.test.tsx.
 */
function renderLedgerPnlPage(client: ApiClient, initialEntry: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <LedgerPnlPage />
    </Wrapper>,
  );
}

function getFrozenAdditivityCheck(checkKey: string) {
  const check = mockLedgerPnlFormalIndicatorRuleChecks202603.additivity_checks.find(
    (item) => item.check_key === checkKey,
  );
  expect(check).toBeDefined();
  return check;
}

describe("LedgerPnlPage formal indicator rule checks panel", () => {
  it("renders 202603 ratio matched rows, additivity residuals, and npl target pass", async () => {
    const client = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(client, "/ledger-pnl?report_date=2026-03-31");

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-rule-checks-panel");
    const costIncomeRow = await within(panel).findByTestId(
      "ledger-pnl-rule-checks-ratio-row-group.cost_income_ratio",
    );
    expect(panel).toHaveTextContent("report_month 202603");
    expect(panel).toHaveTextContent("formal_use_allowed=false");
    expect(panel).toHaveTextContent("sample_status contract_fixture");

    expect(getFrozenAdditivityCheck("group.operating_revenue")).toMatchObject({
      total_value: "43.4194731314",
      components: [
        { metric_key: "parent.operating_revenue.consolidated_basis", value: "40.5057623568" },
        { metric_key: "subsidiary.jinzu.operating_revenue", value: "1.7633073047" },
        { metric_key: "subsidiary.licai.operating_revenue", value: "1.1233358159" },
        { metric_key: "subsidiary.village_bank.operating_revenue", value: "0.0321492748" },
      ],
      components_sum: "43.4245547522",
      residual: "-0.0050816208",
    });
    expect(getFrozenAdditivityCheck("group.business_admin_expense")).toMatchObject({
      total_value: "9.7335327322",
      components: [
        { metric_key: "parent.business_admin_expense", value: "9.2856413190" },
        { metric_key: "subsidiary.jinzu.business_admin_expense", value: "0.1529288536" },
        { metric_key: "subsidiary.licai.business_admin_expense", value: "0.2508577245" },
        { metric_key: "subsidiary.village_bank.business_admin_expense", value: "0.0470170997" },
      ],
      components_sum: "9.7364449968",
      residual: "-0.0029122646",
    });
    expect(getFrozenAdditivityCheck("group.impairment_loss")).toMatchObject({
      total_value: "13.8794270584",
      components: [
        { metric_key: "parent.impairment_loss", value: "13.8357855232" },
        { metric_key: "subsidiary.impairment_loss", value: "0.0378967223" },
      ],
      components_sum: "13.8736822455",
      residual: "0.0057448129",
    });
    expect(getFrozenAdditivityCheck("group.net_profit")).toMatchObject({
      total_value: "15.7131099579",
      components: [
        { metric_key: "parent.net_profit", value: "13.9118472050" },
        { metric_key: "subsidiary.jinzu.net_profit", value: "1.1775187483" },
        { metric_key: "subsidiary.licai.net_profit", value: "0.6390026754" },
        { metric_key: "subsidiary.village_bank.net_profit", value: "-0.0149530904" },
      ],
      components_sum: "15.7134155383",
      residual: "-0.0003055804",
    });
    expect(getFrozenAdditivityCheck("asset_quality.writeoff_total")).toMatchObject({
      total_value: "3.0847286675",
      components: [
        { metric_key: "asset_quality.loan_writeoff", value: "3.0497046763" },
        { metric_key: "asset_quality.other_asset_writeoff", value: "0.0350239912" },
      ],
      components_sum: "3.0847286675",
      residual: "0.0000000000",
    });
    expect(getFrozenAdditivityCheck("asset_quality.recovery_after_writeoff_total")).toMatchObject({
      total_value: "0.5154111414",
      components: [
        { metric_key: "asset_quality.loan_recovery_after_writeoff", value: "0.5143695576" },
        { metric_key: "asset_quality.other_asset_recovery_after_writeoff", value: "0.0010415838" },
      ],
      components_sum: "0.5154111414",
      residual: "0.0000000000",
    });
    expect(getFrozenAdditivityCheck("asset_quality.provision_balance_total")).toMatchObject({
      total_value: "192.4598240500",
      components: [
        { metric_key: "asset_quality.loan_loss_provision_balance", value: "122.7295998170" },
        { metric_key: "asset_quality.other_asset_provision_balance", value: "69.7302242330" },
      ],
      components_sum: "192.4598240500",
      residual: "0.0000000000",
    });

    expect(costIncomeRow).toHaveTextContent("matched");
    expect(costIncomeRow).toHaveTextContent("22.4174363027");

    const roaRow = within(panel).getByTestId("ledger-pnl-rule-checks-ratio-row-group.roa");
    expect(roaRow).toHaveTextContent("insufficient_inputs");
    expect(roaRow).toHaveTextContent("缺失输入");

    const operatingRevenueRow = within(panel).getByTestId(
      "ledger-pnl-rule-checks-additivity-row-group.operating_revenue",
    );
    expect(operatingRevenueRow).toHaveTextContent("residual_present");
    expect(operatingRevenueRow).toHaveTextContent("-0.0050816208");

    const netProfitRow = within(panel).getByTestId(
      "ledger-pnl-rule-checks-additivity-row-group.net_profit",
    );
    expect(netProfitRow).toHaveTextContent("-0.0003055804");

    const writeoffRow = within(panel).getByTestId(
      "ledger-pnl-rule-checks-additivity-row-asset_quality.writeoff_total",
    );
    expect(writeoffRow).toHaveTextContent("exact");

    const nplRuleRow = within(panel).getByTestId(
      "ledger-pnl-rule-checks-arrangement-row-rule_npl_ratio_target",
    );
    expect(nplRuleRow).toHaveTextContent("pass");
    expect(nplRuleRow).toHaveTextContent("0.9575326965");
    expect(nplRuleRow).toHaveTextContent("1.21");

    expect(panel).toHaveTextContent("比率复算 4/6 matched");
    expect(panel).toHaveTextContent("勾稽 3/7 exact");
    expect(panel).toHaveTextContent("安排规则 1/5 pass");

    expect(screen.queryByTestId("ledger-pnl-rule-checks-missing-contract")).not.toBeInTheDocument();
  });

  it("shows an explicit missing-contract state for a month without a frozen contract", async () => {
    const client = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(client, "/ledger-pnl?report_date=2026-06-30");

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-rule-checks-panel");
    const missingState = await within(panel).findByTestId("ledger-pnl-rule-checks-missing-contract");
    expect(panel).toHaveTextContent("report_month 202606");
    expect(panel).toHaveTextContent("sample_status missing_contract");

    expect(missingState).toHaveTextContent("202606 正式契约缺失，无法执行规则检查");
    expect(missingState).toHaveTextContent("规则符合性检查无法执行");

    expect(
      screen.queryByTestId("ledger-pnl-rule-checks-ratio-row-group.cost_income_ratio"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("ledger-pnl-rule-checks-additivity-row-group.operating_revenue"),
    ).not.toBeInTheDocument();
  });
});

describe("LedgerPnlPage candidate analysis authority", () => {
  it("uses the backend analysis envelope for the functional audit and removes the legacy explainability panel", async () => {
    const client = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(client, "/ledger-pnl?report_date=2025-12-31&currency=CNX");

    await screen.findByTestId("ledger-pnl-analysis-conclusion");
    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");

    expect(strip).toHaveTextContent("候选分析状态");
    expect(strip).toHaveTextContent("ready · candidate");
    expect(strip).toHaveTextContent("ledger_pnl.analysis · evidence 37");
    expect(screen.queryByTestId("ledger-pnl-explainability-panel")).not.toBeInTheDocument();
  });

  it("keeps an analysis failure visible in both the workbench and the functional audit", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getLedgerPnlAnalysis: async () => {
        throw new Error("Request failed: /api/ledger-pnl/analysis (500)");
      },
    };

    renderLedgerPnlPage(client, "/ledger-pnl?report_date=2025-12-31&currency=CNX");

    expect(await screen.findByText("总账损益分析读取失败")).toBeVisible();
    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    expect(strip).toHaveTextContent("候选分析读取失败");
    expect(strip).toHaveTextContent("/api/ledger-pnl/analysis (500)");
  });
});
