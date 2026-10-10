import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { AppProviders } from "../app/providers";
import { LedgerPnlAccountDetailDrawer } from "../features/ledger-pnl/components/LedgerPnlAccountDetailDrawer";
import type { LedgerPnlContributorSelection } from "../features/ledger-pnl/components/LedgerPnlAnalysisWorkbench";

const TAX_SELECTION: LedgerPnlContributorSelection = {
  account_code: "55000000001",
  account_name: "当期所得税",
  tone: "negative",
};

describe("LedgerPnlAccountDetailDrawer", () => {
  it("queries only while open and renders backend-owned comparison and canonical evidence", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailSpy = vi.spyOn(client, "getLedgerPnlAccountDetail");
    const onClose = vi.fn();
    const onLocate = vi.fn();
    const { rerender } = render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={null}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={onClose}
          onLocate={onLocate}
        />
      </AppProviders>,
    );

    expect(detailSpy).not.toHaveBeenCalled();

    rerender(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={onClose}
          onLocate={onLocate}
        />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(detailSpy).toHaveBeenCalledWith(
        "2026-06-30",
        "55000000001",
        "CNX",
      );
    });
    const drawer = await screen.findByTestId("ledger-pnl-account-detail-drawer");
    const period = await screen.findByTestId("ledger-pnl-account-detail-period");
    expect(drawer).toHaveTextContent("科目损益穿透");
    expect(drawer).toHaveTextContent("55000000001 当期所得税");
    expect(within(period).getByText("本期").closest("article")).toHaveTextContent("-5.67 亿元");
    expect(within(period).getByText("上期").closest("article")).toHaveTextContent("0.00 亿元");
    expect(within(period).getByText("变化").closest("article")).toHaveTextContent("-5.67 亿元");
    expect(within(drawer).getByTestId("ledger-pnl-account-detail-basis")).toHaveTextContent(
      "CNX - CNY",
    );
    expect(within(drawer).getByTestId("ledger-pnl-account-detail-evidence")).toHaveTextContent(
      "Canonical 规范化证据",
    );
    expect(period).toHaveTextContent("-566796492.18 元");
    const evidence = within(drawer).getByTestId("ledger-pnl-account-detail-evidence");
    expect(evidence).toHaveTextContent("-566796492.18 元");
    expect(evidence).toHaveTextContent("994043400.29 元");
    expect(drawer).toHaveTextContent("本期来源 sv_product_category_4490cb62d9f5");
    expect(drawer).toHaveTextContent("上期来源 sv_product_category_3353b116b9a6");
    expect(drawer).toHaveTextContent("精确科目匹配");
    expect(drawer).toHaveTextContent("上一期按最近可用总账报告日");
    expect(drawer).toHaveTextContent("Canonical 规范化证据，非源端物理凭证");
    expect(drawer).not.toHaveTextContent("原始凭证");
    expect(drawer).not.toHaveTextContent("月日均");
    expect(within(drawer).getAllByRole("button", { name: /关闭|Close/ })).toHaveLength(1);
  });

  it("renders DTO yi fields without deriving period or basis differences in the browser", async () => {
    const client = createApiClient({ mode: "mock" });
    const base = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    vi.spyOn(client, "getLedgerPnlAccountDetail").mockResolvedValue({
      ...base,
      result: {
        ...base.result,
        period_comparison: {
          ...base.result.period_comparison,
          current_monthly_pnl: { yuan: "1", yi: "9.91" },
          previous_monthly_pnl: { yuan: "2", yi: "8.82" },
          change: { yuan: "999", yi: "7.73" },
        },
        basis_comparison: {
          ...base.result.basis_comparison,
          current: {
            ...base.result.basis_comparison.current,
            cnx: { yuan: "3", yi: "5.55" },
            cny: { yuan: "4", yi: "4.44" },
            cnx_minus_cny: { yuan: "999", yi: "6.64" },
          },
        },
      },
    });

    render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    const period = await screen.findByTestId("ledger-pnl-account-detail-period");
    expect(period).toHaveTextContent("9.91 亿元");
    expect(period).toHaveTextContent("8.82 亿元");
    expect(period).toHaveTextContent("7.73 亿元");
    const basis = screen.getByTestId("ledger-pnl-account-detail-basis");
    expect(basis).toHaveTextContent("5.55 亿元");
    expect(basis).toHaveTextContent("4.44 亿元");
    expect(basis).toHaveTextContent("6.64 亿元");
  });

  it("isolates account and currency query keys without flashing the previous account response", async () => {
    const client = createApiClient({ mode: "mock" });
    const tax = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    const metal = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "51603030006",
      "CNY",
    );
    type DetailResponse = typeof tax;
    let resolveMetal: ((value: DetailResponse) => void) | undefined;
    const pendingMetal = new Promise<DetailResponse>((resolve) => {
      resolveMetal = resolve;
    });
    const detailSpy = vi
      .spyOn(client, "getLedgerPnlAccountDetail")
      .mockResolvedValueOnce(tax)
      .mockReturnValueOnce(pendingMetal);
    const { rerender } = render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    expect(await screen.findByTestId("ledger-pnl-account-detail-period")).toHaveTextContent("-5.67 亿元");

    rerender(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={{
            account_code: "51603030006",
            account_name: "选择行旧名称",
            tone: "positive",
          }}
          reportDate="2026-06-30"
          currency="CNY"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(detailSpy).toHaveBeenLastCalledWith(
        "2026-06-30",
        "51603030006",
        "CNY",
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent("科目穿透读取中");
    expect(screen.getByTestId("ledger-pnl-account-detail-drawer")).toHaveTextContent(
      "51603030006 选择行旧名称",
    );
    expect(screen.queryByTestId("ledger-pnl-account-detail-period")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-account-detail-evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("-566796492.18 元")).not.toBeInTheDocument();

    const resolvePendingMetal = resolveMetal;
    if (!resolvePendingMetal) {
      throw new Error("Expected pending metal response resolver");
    }
    await act(async () => {
      resolvePendingMetal(metal);
      await pendingMetal;
    });

    expect(await screen.findByTestId("ledger-pnl-account-detail-period")).toHaveTextContent("3.38 亿元");
    expect(screen.getByTestId("ledger-pnl-account-detail-drawer")).toHaveTextContent(
      "51603030006 贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    );
    expect(screen.getByTestId("ledger-pnl-account-detail-drawer")).not.toHaveTextContent(
      "选择行旧名称",
    );
    expect(screen.queryByText("-566796492.18 元")).not.toBeInTheDocument();
  });

  it("closes before locating so the drawer focus restoration cannot override the detail target", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const ready = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    vi.spyOn(client, "getLedgerPnlAccountDetail").mockResolvedValue({
      ...ready,
      result: {
        ...ready.result,
        account: {
          ...ready.result.account,
          account_name: "API 权威所得税科目",
        },
      },
    });
    const onClose = vi.fn();
    const onLocate = vi.fn();

    function Harness() {
      const [selection, setSelection] = useState<LedgerPnlContributorSelection | null>(TAX_SELECTION);
      return (
        <AppProviders client={client}>
          <LedgerPnlAccountDetailDrawer
            selection={selection}
            reportDate="2026-06-30"
            currency="CNX"
            onClose={() => {
              onClose();
              setSelection(null);
            }}
            onLocate={onLocate}
          />
        </AppProviders>
      );
    }

    render(<Harness />);
    const drawer = await screen.findByTestId("ledger-pnl-account-detail-drawer");
    await screen.findByTestId("ledger-pnl-account-detail-period");
    expect(drawer).toHaveTextContent("55000000001 API 权威所得税科目");
    expect(drawer).not.toHaveTextContent("55000000001 当期所得税");
    await user.click(within(drawer).getByRole("button", { name: "定位下方科目明细" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(onLocate).toHaveBeenCalledWith({
      ...TAX_SELECTION,
      account_name: "API 权威所得税科目",
    }));
    await waitFor(() => {
      expect(screen.queryByTestId("ledger-pnl-account-detail-drawer")).not.toBeInTheDocument();
    });
  });

  it("falls back to the selected account name when the loaded API payload omits it", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const ready = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    vi.spyOn(client, "getLedgerPnlAccountDetail").mockResolvedValue({
      ...ready,
      result: {
        ...ready.result,
        account: { ...ready.result.account, account_name: null },
      },
    });
    const onLocate = vi.fn();

    function Harness() {
      const [selection, setSelection] = useState<LedgerPnlContributorSelection | null>(TAX_SELECTION);
      return (
        <AppProviders client={client}>
          <LedgerPnlAccountDetailDrawer
            selection={selection}
            reportDate="2026-06-30"
            currency="CNX"
            onClose={() => setSelection(null)}
            onLocate={onLocate}
          />
        </AppProviders>
      );
    }

    render(<Harness />);
    const drawer = await screen.findByTestId("ledger-pnl-account-detail-drawer");
    await screen.findByTestId("ledger-pnl-account-detail-period");
    expect(drawer).toHaveTextContent("55000000001 当期所得税");
    await user.click(within(drawer).getByRole("button", { name: "定位下方科目明细" }));
    await waitFor(() => expect(onLocate).toHaveBeenCalledWith(TAX_SELECTION));
  });

  it("shows loading, distinguishes forbidden errors, and retries inside the open drawer", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const ready = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    const detailSpy = vi
      .spyOn(client, "getLedgerPnlAccountDetail")
      .mockRejectedValueOnce(new Error("Request failed (403): forbidden"))
      .mockResolvedValueOnce(ready);

    render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("科目穿透读取中");
    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent("无权限读取科目穿透");
    expect(error).not.toHaveTextContent("Request failed");
    await user.click(within(error).getByRole("button", { name: "重试科目穿透" }));
    expect(await screen.findByTestId("ledger-pnl-account-detail-period")).toBeVisible();
    expect(detailSpy).toHaveBeenCalledTimes(2);
  });

  it("surfaces explicit no_data without zero-filling or a misleading locate action", async () => {
    const client = createApiClient({ mode: "mock" });
    render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={{
            account_code: "59999999999",
            account_name: "待核科目",
            tone: "negative",
          }}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    const state = await screen.findByTestId("ledger-pnl-account-detail-no-data");
    expect(state).toHaveTextContent("当前报告日该科目暂无总账证据");
    expect(state).toHaveTextContent("无数据不等于 0");
    expect(state).toHaveTextContent("上一可用报告日 2026-05-31");
    expect(screen.queryByTestId("ledger-pnl-account-detail-period")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "定位下方科目明细" })).not.toBeInTheDocument();
  });

  it("keeps opposite-basis and previous evidence visible when the selected CNX basis has no data", async () => {
    const client = createApiClient({ mode: "mock" });
    const ready = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    const cnyCurrentEvidence = ready.result.canonical_evidence_rows.find(
      (row) => row.period === "current" && row.currency === "CNY",
    );
    const previousEvidence = ready.result.canonical_evidence_rows.find(
      (row) => row.period === "previous" && row.currency === "CNX",
    );
    if (!cnyCurrentEvidence || !previousEvidence) {
      throw new Error("Expected complete current CNY and previous mock evidence");
    }
    vi.spyOn(client, "getLedgerPnlAccountDetail").mockResolvedValue({
      ...ready,
      result: {
        ...ready.result,
        currency_basis: "CNX",
        analysis_status: "no_data",
        period_comparison: {
          ...ready.result.period_comparison,
          status: "current_account_no_data",
          current_monthly_pnl: null,
          change: null,
          current_evidence_rows: 0,
          previous_evidence_rows: 1,
        },
        basis_comparison: {
          ...ready.result.basis_comparison,
          current: {
            ...ready.result.basis_comparison.current,
            cnx: null,
            cnx_minus_cny: null,
            availability: { CNX: "no_data", CNY: "ready" },
            evidence_rows: { CNX: 0, CNY: 1 },
          },
        },
        canonical_evidence_rows: [cnyCurrentEvidence, previousEvidence],
      },
    });

    render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    const warning = await screen.findByTestId("ledger-pnl-account-detail-selected-basis-no-data");
    expect(warning).toHaveTextContent("当前选择口径 CNX 暂无总账证据");
    expect(warning).toHaveTextContent("无数据不等于 0");
    const period = screen.getByTestId("ledger-pnl-account-detail-period");
    expect(within(period).getByText("本期").closest("article")).toHaveTextContent("—");
    expect(within(period).getByText("本期").closest("article")).not.toHaveTextContent("0.00 亿元");
    expect(within(period).getByText("上期").closest("article")).toHaveTextContent("0.00 亿元");
    const basis = screen.getByTestId("ledger-pnl-account-detail-basis");
    expect(basis).toHaveTextContent("无数据");
    expect(basis).toHaveTextContent("-5.67 亿元");
    expect(screen.getByTestId("ledger-pnl-account-detail-evidence")).toHaveTextContent("2 行");
    expect(screen.queryByRole("button", { name: "定位下方科目明细" })).not.toBeInTheDocument();
  });

  it("surfaces stale fallback metadata, partial basis availability, and empty canonical evidence", async () => {
    const client = createApiClient({ mode: "mock" });
    const ready = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    vi.spyOn(client, "getLedgerPnlAccountDetail").mockResolvedValue({
      ...ready,
      result_meta: {
        ...ready.result_meta,
        quality_flag: "stale",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
        requested_report_date: "2026-06-30",
        resolved_report_date: "2026-05-31",
        fallback_date: "2026-05-31",
        as_of_date: "2026-05-31",
      },
      result: {
        ...ready.result,
        basis_comparison: {
          ...ready.result.basis_comparison,
          current: {
            ...ready.result.basis_comparison.current,
            cny: null,
            cnx_minus_cny: null,
            availability: { CNX: "ready", CNY: "no_data" },
            evidence_rows: { CNX: 1, CNY: 0 },
          },
        },
        canonical_evidence_rows: [],
      },
    });

    render(
      <AppProviders client={client}>
        <LedgerPnlAccountDetailDrawer
          selection={TAX_SELECTION}
          reportDate="2026-06-30"
          currency="CNX"
          onClose={vi.fn()}
          onLocate={vi.fn()}
        />
      </AppProviders>,
    );

    const sourceState = await screen.findByTestId("ledger-pnl-account-detail-source-status");
    expect(sourceState).toHaveTextContent("已回退至最近可用报告日");
    expect(sourceState).toHaveTextContent("请求日 2026-06-30");
    expect(sourceState).toHaveTextContent("解析日 2026-05-31");
    expect(sourceState).toHaveTextContent("数据可能已过期");
    const basis = screen.getByTestId("ledger-pnl-account-detail-basis");
    expect(basis).toHaveTextContent("无数据");
    expect(basis).toHaveTextContent("不可比");
    expect(screen.getByTestId("ledger-pnl-account-detail-evidence")).toHaveTextContent(
      "暂无 Canonical 规范化证据行，不以 0 补齐",
    );
  });

  it("closes on Escape and restores focus to the trigger", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });

    function Harness() {
      const [selection, setSelection] = useState<LedgerPnlContributorSelection | null>(null);
      return (
        <AppProviders client={client}>
          <button type="button" onClick={() => setSelection(TAX_SELECTION)}>
            打开科目穿透
          </button>
          <LedgerPnlAccountDetailDrawer
            selection={selection}
            reportDate="2026-06-30"
            currency="CNX"
            onClose={() => setSelection(null)}
            onLocate={vi.fn()}
          />
        </AppProviders>
      );
    }

    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "打开科目穿透" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "科目损益穿透" });
    expect(dialog).toBeVisible();
    const drawerRoot = dialog.closest(".ant-drawer");
    if (!drawerRoot) {
      throw new Error("Expected Ant Drawer root");
    }
    fireEvent.keyDown(drawerRoot, { key: "Escape", keyCode: 27, which: 27 });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "科目损益穿透" })).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});
