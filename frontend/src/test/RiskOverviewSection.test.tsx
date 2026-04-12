import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { RiskOverviewPayload } from "../api/contracts";
import { RiskOverviewSection } from "../features/executive-dashboard/components/RiskOverviewSection";

function riskFixture(): RiskOverviewPayload {
  return {
    title: "风险",
    signals: [
      {
        id: "sig1",
        label: "DV01",
        value: "12.4",
        status: "stable",
        detail: "限额内",
      },
      {
        id: "sig2",
        label: "集中度",
        value: "偏高",
        status: "watch",
        detail: "接近预警线",
      },
      {
        id: "sig3",
        label: "流动性",
        value: "紧张",
        status: "warning",
        detail: "需压降",
      },
    ],
  };
}

describe("RiskOverviewSection", () => {
  it("renders signal labels, values, statuses, and detail text", () => {
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
    expect(screen.getByText("stable")).toBeInTheDocument();
    expect(screen.getByText("限额内")).toBeInTheDocument();

    expect(screen.getByText("集中度")).toBeInTheDocument();
    expect(screen.getByText("偏高")).toBeInTheDocument();
    expect(screen.getByText("watch")).toBeInTheDocument();
    expect(screen.getByText("接近预警线")).toBeInTheDocument();

    expect(screen.getByText("流动性")).toBeInTheDocument();
    expect(screen.getByText("紧张")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("需压降")).toBeInTheDocument();
  });

  it("renders empty state when signals is empty", () => {
    const data: RiskOverviewPayload = { title: "风险", signals: [] };

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
    await user.click(screen.getByRole("button", { name: /重\s*试/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
