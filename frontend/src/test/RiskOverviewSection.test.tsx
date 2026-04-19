import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Numeric, RiskOverviewPayload } from "../api/contracts";
import { RiskOverviewSection } from "../features/executive-dashboard/components/RiskOverviewSection";

function numeric(
  raw: number | null,
  display: string,
  unit: Numeric["unit"] = "ratio",
  signAware = false,
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

function riskFixture(): RiskOverviewPayload {
  return {
    title: "椋庨櫓",
    signals: [
      {
        id: "sig1",
        label: "DV01",
        value: numeric(12.4, "12.4", "dv01", false, 1),
        status: "stable",
        detail: "闄愰鍐?",
      },
      {
        id: "sig2",
        label: "闆嗕腑搴?",
        value: numeric(0.82, "鍋忛珮"),
        status: "watch",
        detail: "鎺ヨ繎棰勮绾?",
      },
      {
        id: "sig3",
        label: "娴佸姩鎬?",
        value: numeric(-1, "绱у紶"),
        status: "warning",
        detail: "闇€鍘嬮檷",
      },
    ],
  };
}

describe("RiskOverviewSection", () => {
  it("renders signal labels, Numeric value displays, statuses, and detail text", () => {
    const data = riskFixture();

    render(
      <RiskOverviewSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("风险全景")).toBeInTheDocument();

    expect(screen.getByText("DV01")).toBeInTheDocument();
    expect(screen.getByText("12.4")).toBeInTheDocument();
    expect(screen.getByText("稳定")).toBeInTheDocument();
    expect(screen.getByText("闄愰鍐?")).toBeInTheDocument();

    expect(screen.getByText("闆嗕腑搴?")).toBeInTheDocument();
    expect(screen.getByText("鍋忛珮")).toBeInTheDocument();
    expect(screen.getByText("关注")).toBeInTheDocument();
    expect(screen.getByText("鎺ヨ繎棰勮绾?")).toBeInTheDocument();

    expect(screen.getByText("娴佸姩鎬?")).toBeInTheDocument();
    expect(screen.getByText("绱у紶")).toBeInTheDocument();
    expect(screen.getByText("预警")).toBeInTheDocument();
    expect(screen.getByText("闇€鍘嬮檷")).toBeInTheDocument();
  });

  it("renders empty state when signals is empty", () => {
    const data: RiskOverviewPayload = { title: "椋庨櫓", signals: [] };

    render(
      <RiskOverviewSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
  });

  it("shows retry in error state and calls onRetry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(
      <RiskOverviewSection
        data={riskFixture()}
        isLoading={false}
        isError
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
