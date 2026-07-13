import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient, type ApiClient } from "../api/client";
import type { LedgerPnlCandidateFinancialIndicatorComponentDetail } from "../api/contracts";
import {
  LedgerPnlNetInterestComponentDetailDrawer,
  type LedgerPnlNetInterestComponentSelection,
} from "../features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer";

const INVESTMENT_SELECTION: LedgerPnlNetInterestComponentSelection = {
  reportMonth: "202606",
  parentIdempotencyKey: "d".repeat(64),
  metricId: "income.interest.investment",
  metricName: "金融投资利息收入",
};

function renderDrawer(
  client: ApiClient,
  selection: LedgerPnlNetInterestComponentSelection | null = INVESTMENT_SELECTION,
) {
  return render(
    <AppProviders client={client}>
      <LedgerPnlNetInterestComponentDetailDrawer
        selection={selection}
        onClose={vi.fn()}
        onAfterClose={vi.fn()}
      />
    </AppProviders>,
  );
}

describe("LedgerPnlNetInterestComponentDetailDrawer", () => {
  it.each([
    ["stale_parent", "父级跨期结果已变化"],
    ["not_evaluable", "贡献项暂不可评估"],
    ["failed", "贡献项科目勾稽失败"],
    ["invalid_contract", "贡献项穿透契约校验失败"],
  ] as const)("fails closed for %s without exposing account rows", async (state, message) => {
    const baseClient = createApiClient({ mode: "mock" });
    const payload = await baseClient.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "d".repeat(64),
    );
    if (state === "stale_parent") {
      Object.assign(payload, {
        status: "stale_parent",
        quality_status: "not_evaluable",
        foot_status: "not_evaluable",
        parent_idempotency_key: "c".repeat(64),
        reasons: ["parent_idempotency_key_mismatch"],
        rows: [],
      });
      for (const key of [
        "parent_current_value_yi", "parent_previous_value_yi",
        "parent_component_delta_yi", "parent_contribution_to_net_delta_yi",
        "account_current_total_yi", "account_previous_total_yi",
        "account_component_delta_total_yi", "account_contribution_total_yi",
        "current_reconciliation_yi", "previous_reconciliation_yi",
        "component_delta_reconciliation_yi", "contribution_reconciliation_yi",
      ] as const) payload[key] = null;
    } else if (state === "not_evaluable") {
      Object.assign(payload, {
        status: "not_evaluable",
        quality_status: "not_evaluable",
        foot_status: "not_evaluable",
        reasons: ["account_set_mismatch"],
        rows: [],
      });
      for (const key of [
        "parent_current_value_yi", "parent_previous_value_yi",
        "parent_component_delta_yi", "parent_contribution_to_net_delta_yi",
        "account_current_total_yi", "account_previous_total_yi",
        "account_component_delta_total_yi", "account_contribution_total_yi",
        "current_reconciliation_yi", "previous_reconciliation_yi",
        "component_delta_reconciliation_yi", "contribution_reconciliation_yi",
      ] as const) payload[key] = null;
    } else if (state === "failed") {
      Object.assign(payload, {
        status: "not_evaluable",
        quality_status: "not_evaluable",
        foot_status: "failed",
        account_current_total_yi: null,
        account_previous_total_yi: null,
        account_component_delta_total_yi: null,
        account_contribution_total_yi: null,
        current_reconciliation_yi: "1",
        previous_reconciliation_yi: "0",
        component_delta_reconciliation_yi: "0",
        contribution_reconciliation_yi: "0",
        reasons: ["component_account_reconciliation_failed"],
        rows: [],
      });
    } else {
      payload.unit = "万元" as never;
    }
    renderDrawer({
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorComponentDetail: vi.fn(async () => payload),
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(screen.queryByText("51402010003")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("queries with AbortSignal and renders only backend/model strings for available detail", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailRead = vi.spyOn(client, "getLedgerPnlCandidateFinancialIndicatorComponentDetail");
    renderDrawer(client);

    const drawer = await screen.findByRole("dialog", { name: "净息贡献项科目穿透" });
    await waitFor(() => expect(detailRead).toHaveBeenCalledWith(
      "202606",
      "income.interest.investment",
      "d".repeat(64),
      { signal: expect.any(AbortSignal) },
    ));
    expect(within(drawer).getAllByText("金融投资利息收入").length).toBeGreaterThan(0);
    expect(await within(drawer).findByText("51402010003")).toBeInTheDocument();
    expect(within(drawer).getAllByText("−1.3160").length).toBeGreaterThan(0);
    expect(within(drawer).getByText(/期末余额恢复自然月、非贷方-借方/)).toBeInTheDocument();
    expect(within(drawer).getByText(/算术贡献非规模、利率或原因/)).toBeInTheDocument();
  });

  it("shows loading, hides the previous component while switching, and aborts the old read", async () => {
    const client = createApiClient({ mode: "mock" });
    const investment = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "d".repeat(64),
    );
    let investmentSignal: AbortSignal | undefined;
    let resolveInvestment: ((value: LedgerPnlCandidateFinancialIndicatorComponentDetail) => void) | undefined;
    const pendingInvestment = new Promise<LedgerPnlCandidateFinancialIndicatorComponentDetail>((resolve) => {
      resolveInvestment = resolve;
    });
    vi.spyOn(client, "getLedgerPnlCandidateFinancialIndicatorComponentDetail")
      .mockImplementationOnce((_month, _metric, _parent, options) => {
        investmentSignal = options?.signal;
        return pendingInvestment;
      })
      .mockImplementation((month, metric, parent) => (
        createApiClient({ mode: "mock" })
          .getLedgerPnlCandidateFinancialIndicatorComponentDetail(month, metric, parent)
      ));
    const view = renderDrawer(client);

    expect(await screen.findByRole("status")).toHaveTextContent("正在读取贡献项科目穿透");
    view.rerender(
      <AppProviders client={client}>
        <LedgerPnlNetInterestComponentDetailDrawer
          selection={{
            ...INVESTMENT_SELECTION,
            metricId: "income.interest.loan.total",
            metricName: "贷款利息收入",
          }}
          onClose={vi.fn()}
          onAfterClose={vi.fn()}
        />
      </AppProviders>,
    );
    await waitFor(() => expect(investmentSignal?.aborted).toBe(true));
    expect(screen.queryByText("51402010003")).not.toBeInTheDocument();
    expect(await screen.findByText("50101010001")).toBeInTheDocument();

    const resolveOld = resolveInvestment;
    if (!resolveOld) throw new Error("missing old resolver");
    await act(async () => resolveOld(investment));
    expect(screen.queryByText("51402010003")).not.toBeInTheDocument();
  });

  it("shows an alert and retries a failed detail read", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "d".repeat(64),
    );
    const detailRead = vi.fn()
      .mockRejectedValueOnce(new Error("503 detail unavailable"))
      .mockResolvedValue(response);
    renderDrawer({
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorComponentDetail: detailRead,
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("贡献项科目穿透读取失败");
    await user.click(within(alert).getByRole("button", { name: "重试贡献项穿透" }));
    expect(await screen.findByText("51402010003")).toBeInTheDocument();
    expect(detailRead).toHaveBeenCalledTimes(2);
  });

  it("explains a 50206 excluded offset and preserves backend summary strings", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const payload = await baseClient.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.interbank_net",
      "d".repeat(64),
    );
    Object.assign(payload, {
      parent_current_value_yi: "999",
      parent_previous_value_yi: "1",
      parent_component_delta_yi: "7.77777",
      parent_contribution_to_net_delta_yi: "7.77777",
      account_current_total_yi: "999",
      account_previous_total_yi: "1",
      account_component_delta_total_yi: "7.77777",
      account_contribution_total_yi: "7.77777",
    });
    const sourceRow = payload.rows[0];
    payload.rows.push({
      ...structuredClone(sourceRow),
      row_status: "excluded_offset",
      account_code: "50206000001",
      account_name: "贷款规则抵销科目",
      effective_component_weight: "0",
      effective_net_weight: "0",
      matched_terms: [
        { source: "ledger", level: "l1", code: "502", weight: "-1" },
        { source: "ledger", level: "l2", code: "50206", weight: "1" },
      ],
      current_value_yi: "0",
      previous_value_yi: "0",
      component_delta_yi: "0",
      contribution_to_net_delta_yi: "0",
    });
    renderDrawer({
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorComponentDetail: vi.fn(async () => payload),
    }, {
      ...INVESTMENT_SELECTION,
      metricId: "income.interest.interbank_net",
      metricName: "同业资产负债利息净收入",
    });

    const summary = await screen.findByRole("region", { name: "贡献项后端摘要" });
    expect(within(summary).getAllByText("7.7778")).toHaveLength(2);
    expect(within(summary).queryByText("998.0000")).not.toBeInTheDocument();
    const offsetRow = screen.getByRole("row", { name: /50206000001/ });
    expect(offsetRow).toHaveTextContent("l1:502(-1) + l2:50206(1)");
    expect(offsetRow).toHaveTextContent("规则抵销，不计入勾稽");
  });
});
