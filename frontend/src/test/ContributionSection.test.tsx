import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import type { ContributionPayload } from "../api/contracts";
import ContributionSection from "../features/executive-dashboard/components/ContributionSection";

function contributionFixture(): ContributionPayload {
  return {
    title: "贡献",
    rows: [
      {
        id: "r1",
        name: "固收一号",
        owner: "团队 A",
        contribution: "+3.2M",
        completion: 72,
        status: "进行中",
      },
      {
        id: "r2",
        name: "利率策略",
        owner: "账户 B",
        contribution: "+1.1M",
        completion: 100,
        status: "完成",
      },
    ],
  };
}

describe("ContributionSection", () => {
  it("renders table headers and row name, owner, contribution, status, and completion bar cell", () => {
    const data = contributionFixture();

    render(
      <ContributionSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("团队 / 账户 / 策略贡献")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "名称" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "维度" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "贡献" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "完成度" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "状态" })).toBeInTheDocument();

    const row1 = screen.getByRole("row", { name: /固收一号/ });
    expect(within(row1).getByText("固收一号")).toBeInTheDocument();
    expect(within(row1).getByText("团队 A")).toBeInTheDocument();
    expect(within(row1).getByText("+3.2M")).toBeInTheDocument();
    expect(within(row1).getByText("进行中")).toBeInTheDocument();

    const completionCell = within(row1).getAllByRole("cell")[3];
    const barHost = completionCell.querySelector(
      "div[style*='overflow']",
    ) as HTMLElement | null;
    expect(barHost).toBeTruthy();
    expect(barHost!.querySelector("div")).toBeTruthy();

    const row2 = screen.getByRole("row", { name: /利率策略/ });
    expect(within(row2).getByText("利率策略")).toBeInTheDocument();
    expect(within(row2).getByText("账户 B")).toBeInTheDocument();
    expect(within(row2).getByText("+1.1M")).toBeInTheDocument();
    expect(within(row2).getByText("完成")).toBeInTheDocument();
  });

  it("renders empty state when rows is empty", () => {
    const data: ContributionPayload = { title: "贡献", rows: [] };

    render(
      <ContributionSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
  });
});
