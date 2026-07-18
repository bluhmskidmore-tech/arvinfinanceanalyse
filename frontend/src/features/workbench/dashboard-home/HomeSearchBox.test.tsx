import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import { useState } from "react";

import { HomeSearchBox } from "./HomeSearchBox";
import type {
  HomeDecisionAction,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";

const kpis: readonly HomeTerminalKpi[] = [
  {
    id: "aum",
    label: "组合市值",
    value: "3,708.10",
    unit: "亿元",
    delta: "较前日 +1.2%",
    deltaTone: "up",
    sparkline: [1, 2],
    state: "ready",
  },
  {
    id: "duration",
    label: "加权久期",
    value: "4.23",
    delta: "较前日 持平",
    deltaTone: "flat",
    sparkline: [1, 2],
    state: "ready",
  },
];

const actions: readonly HomeDecisionAction[] = [
  {
    id: "risk-review",
    title: "复核风险总览",
    priority: "high",
    sourceLabel: "risk",
    reason: "3 项风险事项需要复核",
    to: "/risk-overview?report_date=2026-04-30",
    statusKind: "ready",
  },
];

/** 有状态包装：让受控 value 真正随输入变化，便于测试候选展开。 */
function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location-probe">
      {`${location.pathname}${location.search}${location.hash}`}
    </output>
  );
}

function StatefulBox({
  initial = "",
  reportDate = "2026-04-30",
  terminalKpis = kpis,
  decisionActions = actions,
}: {
  initial?: string;
  reportDate?: string;
  terminalKpis?: readonly HomeTerminalKpi[];
  decisionActions?: readonly HomeDecisionAction[];
}) {
  const [value, setValue] = useState(initial);
  return (
    <MemoryRouter initialEntries={["/"]}>
      <HomeSearchBox
        value={value}
        onValueChange={setValue}
        terminalKpis={terminalKpis}
        decisionActions={decisionActions}
        reportDate={reportDate}
      />
      <LocationProbe />
    </MemoryRouter>
  );
}

function typeQuery(initial: string) {
  render(<StatefulBox initial={initial} />);
  const input = screen.getByRole("combobox") as HTMLInputElement;
  fireEvent.focus(input);
  return input;
}

describe("HomeSearchBox", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("输入后展示候选结果，包含名称与类型", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "风险" } });
    expect(screen.getByText("复核风险总览")).toBeInTheDocument();
    expect(screen.getAllByText("风险工作台").length).toBeGreaterThan(0);
  });

  it("输入无匹配时显示未找到提示并允许清空", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "zzz不存在的查询zzz" } });
    expect(screen.getByText("未找到相关指标、报告或动作")).toBeInTheDocument();
    expect(screen.getByText("清空")).toBeInTheDocument();
  });

  it("空查询不展示候选列表", () => {
    typeQuery("");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("↓ 选择候选后 Enter 触发跳转，列表收起", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "风险工作台" } });
    expect(screen.queryByRole("listbox")).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("Esc 关闭候选列表", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "组合" } });
    expect(screen.queryByRole("listbox")).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("Esc 在候选已关闭时清空输入", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "组合" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    // 再次 Esc 清空输入
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveValue("");
  });

  it("清空按钮清空输入", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "组合市值" } });
    const clearBtn = screen.getByLabelText("清空搜索");
    fireEvent.click(clearBtn);
    expect(input).toHaveValue("");
  });

  it("搜索输入变化更新值", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "久期" } });
    expect(input).toHaveValue("久期");
  });

  it("指标候选可命中并带类型标签", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "久期" } });
    expect(screen.getByText("加权久期")).toBeInTheDocument();
    const option = screen.getByTestId("dashboard-home-search-option-metric:duration");
    expect(option).toHaveTextContent("指标");
  });

  it("routes the all-asset AUM metric to balance analysis", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "组合市值" } });

    const option = screen.getByTestId("dashboard-home-search-option-metric:aum");
    fireEvent.click(option);

    expect(screen.getByTestId("location-probe")).toHaveTextContent(
      "/balance-analysis?report_date=2026-04-30",
    );
  });

  it("Ctrl+K 聚焦搜索框", () => {
    render(<StatefulBox />);
    const input = screen.getByRole("combobox") as HTMLInputElement;
    expect(document.activeElement).not.toBe(input);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(document.activeElement).toBe(input);
  });

  it("preserves the actual report date plus an existing query and hash when navigating", () => {
    const decisionActions: readonly HomeDecisionAction[] = [
      {
        ...actions[0],
        title: "Open breach queue",
        to: "/risk-overview?tab=limits&report_date=2026-01-01#breaches",
      },
    ];
    render(
      <StatefulBox
        reportDate="2026-04-18"
        decisionActions={decisionActions}
      />,
    );
    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "Open breach queue" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("location-probe")).toHaveTextContent(
      "/risk-overview?tab=limits&report_date=2026-04-18#breaches",
    );
  });

  it("keeps the active option in range when live results shrink", () => {
    const shrinkingKpis: readonly HomeTerminalKpi[] = [
      { ...kpis[1], id: "duration-shrink-a", label: "Shrink check A" },
      { ...kpis[1], id: "duration-shrink-b", label: "Shrink check B" },
    ];
    const renderSearch = (terminalKpis: readonly HomeTerminalKpi[]) => (
      <MemoryRouter>
        <HomeSearchBox
          value="Shrink check"
          onValueChange={vi.fn()}
          terminalKpis={terminalKpis}
          decisionActions={[]}
          reportDate="2026-04-18"
        />
      </MemoryRouter>
    );
    const { rerender } = render(renderSearch(shrinkingKpis));
    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")).toHaveLength(2);

    expect(() => rerender(renderSearch(shrinkingKpis.slice(0, 1)))).not.toThrow();
    const activeOptionId = input.getAttribute("aria-activedescendant");
    expect(activeOptionId).toBeTruthy();
    expect(document.getElementById(activeOptionId ?? "")).toBeInTheDocument();
  });

  it("commits an option from an assistive-technology click event", () => {
    const input = typeQuery("");
    fireEvent.change(input, { target: { value: "加权久期" } });

    fireEvent.click(screen.getByTestId("dashboard-home-search-option-metric:duration"));

    expect(screen.getByTestId("location-probe")).toHaveTextContent(
      "/risk-overview?report_date=2026-04-30",
    );
  });

  it("supports Enter and Space on the clear button", async () => {
    const user = userEvent.setup();
    render(<StatefulBox initial="duration" />);
    const input = screen.getByRole("combobox");

    let clearButton = screen.getByLabelText("\u6e05\u7a7a\u641c\u7d22");
    clearButton.focus();
    await user.keyboard("{Enter}");
    expect(input).toHaveValue("");

    await user.click(input);
    await user.type(input, "duration");
    clearButton = screen.getByLabelText("\u6e05\u7a7a\u641c\u7d22");
    clearButton.focus();
    await user.keyboard(" ");
    expect(input).toHaveValue("");
  });

  it("does not expose an unmapped KPI as a no-op option", () => {
    const unmappedKpis: readonly HomeTerminalKpi[] = [
      { ...kpis[0], id: "unmapped-kpi", label: "Unmapped local KPI" },
    ];
    render(
      <StatefulBox
        initial="Unmapped local KPI"
        terminalKpis={unmappedKpis}
        decisionActions={[]}
      />,
    );
    fireEvent.focus(screen.getByRole("combobox"));

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    const status = screen.getByText("未找到相关指标、报告或动作");
    expect(status).toHaveTextContent("未找到相关指标、报告或动作");
    expect(status.closest('[role="listbox"]')).toBeNull();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("runs the pointer clear action once", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <MemoryRouter>
        <HomeSearchBox
          value="duration"
          onValueChange={onValueChange}
          terminalKpis={kpis}
          decisionActions={actions}
          reportDate="2026-04-30"
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByLabelText("清空搜索"));

    expect(onValueChange).toHaveBeenCalledTimes(1);
    expect(onValueChange).toHaveBeenCalledWith("");
  });
});
