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
    {
      id: "market-file",
      title: "硕远咨询_2026年中国旅游产业链研究报告_20260715.pdf",
      timeLabel: "06-01 08:40",
      sourceLabel: "市场快讯",
      topicLabel: "资金面",
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

    const trustStrip = screen.getByLabelText("债券新闻数据状态");
    expect(within(trustStrip).getByText("最新内容 04-21 15:06")).toBeInTheDocument();
    expect(screen.queryByText("来源状态：正常")).not.toBeInTheDocument();
    expect(screen.queryByText("后端入库：Choice / Tushare 债券新闻")).not.toBeInTheDocument();
    expect(screen.queryByText("页面读取：每 5 分钟重新读取已落库数据")).not.toBeInTheDocument();
    expect(screen.queryByText("来源更新：后台受控")).not.toBeInTheDocument();
    expect(trustStrip).toHaveAttribute(
      "title",
      "后端入库：Choice / Tushare 债券新闻 · 来源更新：后台受控 · 来源状态：正常 · 页面读取：每 5 分钟重新读取已落库数据",
    );
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
    // 与分组标题重复的行内分类不再渲染：组内只剩分组标题一处。
    expect(within(holdingGroup).getAllByText("持仓命中")).toHaveLength(1);
    expect(within(holdingGroup).getByText("25山东债26 成交活跃")).toBeInTheDocument();
    expect(within(holdingGroup).getByText("命中持仓：25山东债26 · 06-01 09:30")).toBeInTheDocument();

    const marketGroup = screen.getByTestId("dashboard-home-bond-news-market");
    expect(within(marketGroup).getAllByText("债券市场")).toHaveLength(1);
    expect(within(marketGroup).getByText("国债收益率曲线延续下行，资金面保持宽松")).toBeInTheDocument();
    expect(within(marketGroup).getByText("政策要闻 · 06-01 09:10")).toBeInTheDocument();
    // 与分组标题不同的分类保留为轻量文本。
    expect(within(marketGroup).getByText("资金面")).toBeInTheDocument();
    // 文件名式标题清洗后展示，原文保留在 title。
    const cleanedTitle = within(marketGroup).getByText(
      "硕远咨询 2026年中国旅游产业链研究报告",
    );
    expect(cleanedTitle).toHaveAttribute(
      "title",
      "硕远咨询_2026年中国旅游产业链研究报告_20260715.pdf",
    );
    expect(
      within(marketGroup).queryByText(
        "硕远咨询_2026年中国旅游产业链研究报告_20260715.pdf",
      ),
    ).not.toBeInTheDocument();

    const creditGroup = screen.getByTestId("dashboard-home-bond-news-credit");
    expect(within(creditGroup).getByText("发行/评级")).toBeInTheDocument();
    expect(within(creditGroup).getByText("发行/评级：暂无相关新闻")).toBeInTheDocument();
  });

  it("keeps only the abnormal status badge visible and folds the page-level update time into the tooltip", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <BondNewsSection
          bondNews={{ ...bondNews, statusLabel: "来源状态：偏旧" }}
          actions={{ queryClient }}
          updatedAt="09:27"
        />
      </QueryClientProvider>,
    );

    expect(screen.queryByText("更新 09:27")).not.toBeInTheDocument();
    const trustStrip = screen.getByLabelText("债券新闻数据状态");
    expect(trustStrip).toHaveAttribute(
      "title",
      expect.stringContaining("更新 09:27"),
    );
    const staleBadge = within(trustStrip).getByText("来源状态：偏旧");
    expect(staleBadge).toHaveAttribute("data-tone", "warning");
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
