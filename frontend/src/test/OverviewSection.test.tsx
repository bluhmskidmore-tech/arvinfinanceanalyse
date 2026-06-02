import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Numeric } from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import type { DashboardAdapterOutput } from "../features/executive-dashboard/adapters/executiveDashboardAdapter";
import { OverviewSection } from "../features/executive-dashboard/components/OverviewSection";

function numeric(
  raw: number | null,
  display: string,
  unit: Numeric["unit"] = "yuan",
  signAware = true,
  precision = 2,
): Numeric {
  return {
    raw,
    unit,
    display,
    precision,
    sign_aware: signAware,
  };
}

function overviewVm(): NonNullable<DashboardAdapterOutput["overview"]["vm"]> {
  return {
    title: "总览",
    metrics: [
      {
        id: "m1",
        caliberLabel: null,
        label: "资产规模",
        value: numeric(12_000_000_000, "120.00 亿", "yuan", false),
        delta: numeric(0.021, "+2.10%", "pct"),
        tone: "positive",
        detail: "较上月末",
        history: null,
      },
      {
        id: "m2",
        caliberLabel: null,
        label: "流动性覆盖",
        value: numeric(1.18, "118.00%", "pct", false),
        delta: numeric(0, "持平", "pct", false),
        tone: "neutral",
        detail: "监管口径",
        history: null,
      },
    ],
  };
}

function renderOverview(state: DataSectionState) {
  const onRetry = vi.fn();
  render(
    <OverviewSection
      overview={{
        vm: state.kind === "ok" ? overviewVm() : null,
        state,
        meta: null,
      }}
      onRetry={onRetry}
    />,
  );
  return { onRetry };
}

describe("OverviewSection", () => {
  it("renders current overview VM cards with Numeric display strings", () => {
    renderOverview({ kind: "ok" });

    expect(screen.getByText("经营总览")).toBeInTheDocument();
    expect(screen.getByText("2 项")).toBeInTheDocument();
    expect(screen.getByText("资产规模")).toBeInTheDocument();
    expect(screen.getByText("120.00 亿")).toBeInTheDocument();
    expect(screen.getByText("+2.10%")).toBeInTheDocument();
    expect(screen.getByText("较上月末")).toBeInTheDocument();
    expect(screen.getByText("流动性覆盖")).toBeInTheDocument();
    expect(screen.getByText("118.00%")).toBeInTheDocument();
    expect(screen.getByText("持平")).toBeInTheDocument();
    expect(screen.getByText("监管口径")).toBeInTheDocument();
  });

  it("renders empty state when overview state is empty", () => {
    renderOverview({ kind: "empty" });

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(screen.queryByText("资产规模")).not.toBeInTheDocument();
  });

  it("shows retry in error state and calls onRetry", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderOverview({ kind: "error" });

    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
