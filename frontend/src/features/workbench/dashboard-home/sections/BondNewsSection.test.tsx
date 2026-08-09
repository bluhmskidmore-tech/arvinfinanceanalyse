import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HomeBondNewsModel } from "../adapters/buildHomeBondNewsModel";
import { BondNewsSection } from "./BondNewsSection";

const bondNews: HomeBondNewsModel = {
  holdingHits: [
    {
      id: "holding-name",
      title: "25山东债26 成交活跃",
      timeLabel: "06-01 09:30",
      sourceLabel: "市场快讯",
      topicLabel: "持仓命中",
      hitLabel: "命中持仓：25山东债26",
    },
  ],
  marketNews: [
    {
      id: "market",
      title: "国债收益率曲线延续下行，资金面保持宽松",
      timeLabel: "06-01 09:10",
      sourceLabel: "政策要闻",
      topicLabel: "债券市场",
      hitLabel: null,
    },
  ],
  creditAndIssuanceNews: [],
  holdingMessage: null,
  marketMessage: null,
  creditMessage: "发行/评级：暂无相关新闻",
  sourceLabel: "后端入库：Choice / Tushare 债券新闻",
  asOfLabel: "最新内容 04-21 15:06",
  statusLabel: "来源状态：正常",
  refreshLabel: "页面读取：每 5 分钟重新读取已落库数据",
};

function renderSection(
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false },
    },
  }),
) {
  const result = render(
    <QueryClientProvider client={queryClient}>
      <BondNewsSection bondNews={bondNews} actions={{ queryClient }} />
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
}

describe("BondNewsSection", () => {
  it("renders bond news groups with the read-only source boundary and compact empty states", () => {
    renderSection();

    expect(screen.getByTestId("dashboard-home-bond-news")).toBeInTheDocument();
    expect(screen.getByText("债券信息新闻")).toBeInTheDocument();
    expect(screen.getByText("后端入库：Choice / Tushare 债券新闻")).toBeInTheDocument();
    expect(screen.getByText("最新内容 04-21 15:06")).toBeInTheDocument();
    expect(screen.getByText("来源状态：正常")).toBeInTheDocument();
    expect(screen.getByText("页面读取：每 5 分钟重新读取已落库数据")).toBeInTheDocument();
    expect(screen.getByText("来源更新：后台受控")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "重新读取已落库新闻与研报" }),
    ).toHaveAttribute(
      "title",
      "重新读取已落库新闻与研报，不触发外部来源更新",
    );
    expect(
      screen.getByRole("button", { name: "来源更新由后台受控任务维护" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "来源更新由后台受控任务维护" }),
    ).toHaveAttribute(
      "title",
      "外部来源更新当前不对前端开放，由后台受控任务维护",
    );

    const holdingGroup = screen.getByTestId("dashboard-home-bond-news-holding");
    expect(within(holdingGroup).getAllByText("持仓命中")).toHaveLength(2);
    expect(within(holdingGroup).getByText("25山东债26 成交活跃")).toBeInTheDocument();
    expect(within(holdingGroup).getByText("命中持仓：25山东债26 · 06-01 09:30")).toBeInTheDocument();

    const marketGroup = screen.getByTestId("dashboard-home-bond-news-market");
    expect(within(marketGroup).getAllByText("债券市场")).toHaveLength(2);
    expect(within(marketGroup).getByText("国债收益率曲线延续下行，资金面保持宽松")).toBeInTheDocument();
    expect(within(marketGroup).getByText("政策要闻 · 06-01 09:10")).toBeInTheDocument();

    const creditGroup = screen.getByTestId("dashboard-home-bond-news-credit");
    expect(within(creditGroup).getByText("发行/评级")).toBeInTheDocument();
    expect(within(creditGroup).getByText("发行/评级：暂无相关新闻")).toBeInTheDocument();
  });

  it("invalidates and refetches every relevant stored-content query on reread", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueries = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    renderSection(queryClient);

    fireEvent.click(
      screen.getByRole("button", { name: "重新读取已落库新闻与研报" }),
    );

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        "已重新读取当前已落库新闻与研报",
      );
    });
    for (const queryKey of [
      ["dashboard", "macro-news"],
      ["dashboard", "macro-news-fallback"],
      ["dashboard", "bond-news"],
      ["dashboard", "choice-news-digest"],
      ["home", "research-reports"],
    ]) {
      expect(invalidateQueries).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey,
          exact: false,
          refetchType: "active",
        }),
      );
    }
  });

  it("does not expose the reserved source-update boundary as an action", () => {
    renderSection();

    const updateButton = screen.getByRole("button", {
      name: "来源更新由后台受控任务维护",
    });
    expect(updateButton).toBeDisabled();
    fireEvent.click(updateButton);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
