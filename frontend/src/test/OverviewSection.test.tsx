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
    title: "鎬昏",
    metrics: [
      {
        id: "m1",
        caliberLabel: null,
        label: "璧勪骇瑙勬ā",
        value: numeric(12_000_000_000, "120.00 浜?", "yuan", false),
        delta: numeric(0.021, "+2.10%", "pct"),
        tone: "positive",
        detail: "杈冧笂鏈堟湯",
        history: null,
      },
      {
        id: "m2",
        caliberLabel: null,
        label: "娴佸姩鎬ц鐩?",
        value: numeric(1.18, "118.00%", "pct", false),
        delta: numeric(0, "鎸佸钩", "pct", false),
        tone: "neutral",
        detail: "鐩戠鍙ｅ緞",
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
    expect(screen.getByText("璧勪骇瑙勬ā")).toBeInTheDocument();
    expect(screen.getByText("120.00 浜?")).toBeInTheDocument();
    expect(screen.getByText("+2.10%")).toBeInTheDocument();
    expect(screen.getByText("杈冧笂鏈堟湯")).toBeInTheDocument();
    expect(screen.getByText("娴佸姩鎬ц鐩?")).toBeInTheDocument();
    expect(screen.getByText("118.00%")).toBeInTheDocument();
    expect(screen.getByText("鎸佸钩")).toBeInTheDocument();
    expect(screen.getByText("鐩戠鍙ｅ緞")).toBeInTheDocument();
  });

  it("renders empty state when overview state is empty", () => {
    renderOverview({ kind: "empty" });

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(screen.queryByText("璧勪骇瑙勬ā")).not.toBeInTheDocument();
  });

  it("shows retry in error state and calls onRetry", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderOverview({ kind: "error" });

    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
