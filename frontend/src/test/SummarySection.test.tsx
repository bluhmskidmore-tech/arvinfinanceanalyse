import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { SummaryPayload } from "../api/contracts";
import { SummarySection } from "../features/executive-dashboard/components/SummarySection";

function summaryFixture(): SummaryPayload {
  return {
    title: "摘要",
    narrative: "本周组合收益稳定，信用利差收窄。",
    points: [
      {
        id: "p1",
        label: "收益",
        tone: "positive",
        text: "固收贡献为正。",
      },
      {
        id: "p2",
        label: "风险",
        tone: "warning",
        text: "关注久期集中度。",
      },
    ],
  };
}

describe("SummarySection", () => {
  it("renders narrative and point labels and texts", () => {
    const data = summaryFixture();

    render(
      <SummarySection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("本周管理摘要")).toBeInTheDocument();
    expect(
      screen.getByText("本周组合收益稳定，信用利差收窄。"),
    ).toBeInTheDocument();
    expect(screen.getByText("收益")).toBeInTheDocument();
    expect(screen.getByText("固收贡献为正。")).toBeInTheDocument();
    expect(screen.getByText("风险")).toBeInTheDocument();
    expect(screen.getByText("关注久期集中度。")).toBeInTheDocument();
  });

  it("renders empty state when points is empty", () => {
    const data: SummaryPayload = {
      title: "摘要",
      narrative: "无叙事",
      points: [],
    };

    render(
      <SummarySection
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
      <SummarySection
        data={summaryFixture()}
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
