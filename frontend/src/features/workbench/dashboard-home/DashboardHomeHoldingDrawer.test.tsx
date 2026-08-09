import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DashboardHomeHoldingDrawer } from "./DashboardHomeHoldingDrawer";
import type {
  HomeHoldingRow,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";

const row: HomeHoldingRow = {
  id: "holding-230210",
  code: "230210.IB",
  name: "2023 Policy Bank Bond",
  assetClass: "Policy Bank Bond",
  marketValue: "128.45 亿元",
  marketValueRaw: 128.45,
  weight: "3.46%",
  weightRaw: 3.46,
  ytm: "2.18%",
  duration: "4.72",
  rating: "AAA",
};

const holdingsState: HomeTerminalListState = {
  kind: "ready",
  label: "已校验",
};

function renderDrawer(overrides?: {
  onClose?: () => void;
  reportDate?: string;
  row?: HomeHoldingRow;
  holdingsState?: HomeTerminalListState;
  holdingCount?: number;
}) {
  return render(
    <MemoryRouter>
      <DashboardHomeHoldingDrawer
        holdingCount={overrides?.holdingCount ?? 10}
        holdingsState={overrides?.holdingsState ?? holdingsState}
        onClose={overrides?.onClose ?? vi.fn()}
        reportDate={overrides?.reportDate ?? "2026-06-30"}
        row={overrides?.row ?? row}
      />
    </MemoryRouter>,
  );
}

function DrawerHarness() {
  const [open, setOpen] = useState(false);

  return (
    <MemoryRouter>
      <button onClick={() => setOpen(true)} type="button">
        Open holding drawer
      </button>
      {open ? (
        <DashboardHomeHoldingDrawer
          holdingCount={10}
          holdingsState={holdingsState}
          onClose={() => setOpen(false)}
          reportDate="2026-06-30"
          row={row}
        />
      ) : null}
    </MemoryRouter>
  );
}

describe("DashboardHomeHoldingDrawer", () => {
  it("renders the drawer into the document body portal", () => {
    const { container } = renderDrawer();

    expect(
      screen.getByTestId("dashboard-home-holding-drawer"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-home-holding-drawer").parentElement,
    ).toBe(document.body);
    expect(
      container.querySelector('[data-testid="dashboard-home-holding-drawer"]'),
    ).toBeNull();
  });

  it("moves initial focus to the close button when the drawer opens", () => {
    renderDrawer();

    expect(screen.getByRole("button", { name: "关闭重点券详情" })).toHaveFocus();
  });

  it("distinguishes the landed source rows from the homepage ranking", () => {
    renderDrawer({ holdingCount: 14 });

    expect(
      screen.getByText("来自首页重点持仓 · 数据源已落地 14 条"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Top14/)).not.toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDrawer({ onClose });

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("wraps Tab from the last focusable element back to the first", async () => {
    const user = userEvent.setup();
    renderDrawer();

    const closeButton = screen.getByRole("button", { name: "关闭重点券详情" });
    const links = screen.getAllByRole("link");
    const lastLink = links[links.length - 1];

    lastLink.focus();
    expect(lastLink).toHaveFocus();

    await user.tab();

    expect(closeButton).toHaveFocus();
  });

  it("wraps Shift+Tab from the first focusable element back to the last", async () => {
    const user = userEvent.setup();
    renderDrawer();

    const closeButton = screen.getByRole("button", { name: "关闭重点券详情" });
    const links = screen.getAllByRole("link");
    const lastLink = links[links.length - 1];

    expect(closeButton).toHaveFocus();

    await user.tab({ shift: true });

    expect(lastLink).toHaveFocus();
  });

  it("restores focus to the opener after the drawer unmounts", async () => {
    const user = userEvent.setup();
    render(<DrawerHarness />);

    const opener = screen.getByRole("button", { name: "Open holding drawer" });
    opener.focus();
    expect(opener).toHaveFocus();

    await user.click(opener);
    expect(screen.getByRole("button", { name: "关闭重点券详情" })).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(opener).toHaveFocus();
    expect(
      screen.queryByTestId("dashboard-home-holding-drawer"),
    ).not.toBeInTheDocument();
  });
});
