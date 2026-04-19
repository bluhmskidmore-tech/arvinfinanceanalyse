import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import type { ContributionPayload, Numeric } from "../api/contracts";
import ContributionSection from "../features/executive-dashboard/components/ContributionSection";

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

function contributionFixture(): ContributionPayload {
  return {
    title: "璐＄尞",
    rows: [
      {
        id: "r1",
        name: "鍥烘敹涓€鍙?",
        owner: "鍥㈤槦 A",
        contribution: numeric(3_200_000, "+0.03 浜?"),
        completion: 72,
        status: "杩涜涓?",
      },
      {
        id: "r2",
        name: "鍒╃巼绛栫暐",
        owner: "璐︽埛 B",
        contribution: numeric(1_100_000, "+0.01 浜?"),
        completion: 100,
        status: "瀹屾垚",
      },
    ],
  };
}

describe("ContributionSection", () => {
  it("renders table headers and row name, owner, Numeric contribution display, status, and completion bar cell", () => {
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

    const row1 = screen.getByRole("row", { name: /鍥烘敹涓€鍙?/ });
    expect(within(row1).getByText("鍥烘敹涓€鍙?")).toBeInTheDocument();
    expect(within(row1).getByText("鍥㈤槦 A")).toBeInTheDocument();
    expect(within(row1).getByText("+0.03 浜?")).toBeInTheDocument();
    expect(within(row1).getByText("杩涜涓?")).toBeInTheDocument();

    const completionCell = within(row1).getAllByRole("cell")[3];
    const barHost = completionCell.querySelector("div[style*='overflow']") as HTMLElement | null;
    expect(barHost).toBeTruthy();
    expect(barHost?.querySelector("div")).toBeTruthy();

    const row2 = screen.getByRole("row", { name: /鍒╃巼绛栫暐/ });
    expect(within(row2).getByText("鍒╃巼绛栫暐")).toBeInTheDocument();
    expect(within(row2).getByText("璐︽埛 B")).toBeInTheDocument();
    expect(within(row2).getByText("+0.01 浜?")).toBeInTheDocument();
    expect(within(row2).getByText("瀹屾垚")).toBeInTheDocument();
  });

  it("renders empty state when rows is empty", () => {
    const data: ContributionPayload = { title: "璐＄尞", rows: [] };

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
