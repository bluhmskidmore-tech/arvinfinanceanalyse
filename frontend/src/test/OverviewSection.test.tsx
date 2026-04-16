import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { OverviewPayload } from "../api/contracts";
import { OverviewSection } from "../features/executive-dashboard/components/OverviewSection";

function overviewFixture(): OverviewPayload {
  return {
    title: "总览",
    metrics: [
      {
        id: "m1",
        label: "资产规模",
        value: "¥120 亿",
        delta: "+2.1%",
        tone: "positive",
        detail: "较上月末",
      },
      {
        id: "m2",
        label: "流动性覆盖",
        value: "118%",
        delta: "持平",
        tone: "neutral",
        detail: "监管口径",
      },
    ],
  };
}

describe("OverviewSection", () => {
  it("renders title, metric count badge, labels, values, deltas, and detail text", () => {
    const data = overviewFixture();

    render(
      <OverviewSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("经营总览")).toBeInTheDocument();
    expect(screen.getByText("2 项")).toBeInTheDocument();
    expect(screen.getByText("资产规模")).toBeInTheDocument();
    expect(screen.getByText("¥120 亿")).toBeInTheDocument();
    expect(screen.getByText("+2.1%")).toBeInTheDocument();
    expect(screen.getByText("较上月末")).toBeInTheDocument();
    expect(screen.getByText("流动性覆盖")).toBeInTheDocument();
    expect(screen.getByText("118%")).toBeInTheDocument();
    expect(screen.getByText("持平")).toBeInTheDocument();
    expect(screen.getByText("监管口径")).toBeInTheDocument();
  });

  it("renders empty state when metrics is empty", () => {
    const data: OverviewPayload = { title: "总览", metrics: [] };

    render(
      <OverviewSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(screen.queryByText("资产规模")).not.toBeInTheDocument();
  });

  it("shows retry in error state and calls onRetry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(
      <OverviewSection
        data={overviewFixture()}
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
