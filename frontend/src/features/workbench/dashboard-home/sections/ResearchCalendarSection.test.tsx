import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResearchCalendarSection } from "./ResearchCalendarSection";

const singlePolicyFundingNewsItem = {
  id: "news-1",
  timeLabel: "04-21 15:06",
  topicLabel: "货币市场",
  title: "央行开展逆回购操作，DR007 小幅下行",
  freshnessLabel: "最近更新 04-21 15:06",
};

const singlePolicyFundingSummary = {
  headline: "1 条政策与资金面快讯，重点集中在央行/公开市场。",
  chips: [
    { id: "status", label: "正常", tone: "info" as const },
    { id: "as-of", label: "数据截至 04-21 15:06", tone: "neutral" as const },
  ],
  groups: [
    {
      id: "public-market",
      label: "央行/公开市场",
      countLabel: "1 条",
      items: [singlePolicyFundingNewsItem],
    },
  ],
};

const policyFundingSummary = {
  headline: "2 条政策与资金面快讯，重点集中在央行/公开市场、利率/债券。",
  chips: [
    { id: "source", label: "Tushare 兜底", tone: "warning" as const },
    { id: "as-of", label: "数据截至 06-03 20:17", tone: "neutral" as const },
  ],
  groups: [
    {
      id: "public-market",
      label: "央行/公开市场",
      countLabel: "1 条",
      items: [
        {
          id: "repo",
          timeLabel: "06-03 20:01",
          topicLabel: "市场快讯",
          title: "本周中国央行公开市场将有9089亿元逆回购到期",
          freshnessLabel: "最近更新 06-03 20:01",
        },
      ],
    },
    {
      id: "rates-bonds",
      label: "利率/债券",
      countLabel: "1 条",
      items: [
        {
          id: "us10y",
          timeLabel: "06-03 20:17",
          topicLabel: "市场快讯",
          title: "10年期美国国债收益率最新上涨2.8个基点，报4.483%。",
          freshnessLabel: "最近更新 06-03 20:17",
        },
      ],
    },
  ],
};

describe("ResearchCalendarSection", () => {
  it("renders macro release and news windows with supply calendar as a compact note", () => {
    render(
      <ResearchCalendarSection
        macroBriefing={{
          releaseItems: [
            {
              id: "ism-manufacturing-2026-06",
              date: "2026-06-01",
              dateLabel: "06-01",
              daysUntilLabel: "明日",
              region: "海外",
              title: "ISM 制造业 PMI",
              category: "PMI",
              importance: "high",
              importanceLabel: "高优先级",
              timeLabel: "10:00 ET",
              sourceName: "ISM",
              sourceUrl: "https://www.ismworld.org/",
            },
          ],
          releaseWindowLabel: "未来 45 天 · 1 项",
          releaseMessage: null,
          newsItems: [
            singlePolicyFundingNewsItem,
          ],
          newsMessage: null,
          newsStale: false,
          newsFreshnessLabel: "最近更新 04-21 15:06",
          newsSourceLabel: "来源：Choice 宏观新闻",
          newsAsOfLabel: "数据截至 04-21 15:06",
          newsStatusLabel: "来源状态：正常",
          newsRefreshLabel: "刷新：随页面查询读取已落库数据",
          policyFundingSummary: singlePolicyFundingSummary,
          supplyItems: [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }],
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    expect(screen.getByText("重大信息发布日期前瞻")).toBeInTheDocument();
    expect(screen.getByText("未来 45 天 · 1 项")).toBeInTheDocument();
    expect(screen.getByText("政策与资金面")).toBeInTheDocument();
    expect(screen.getByText("来源：Choice 宏观新闻")).toBeInTheDocument();
    expect(screen.getAllByText("数据截至 04-21 15:06").length).toBeGreaterThan(0);
    expect(screen.getByText("来源状态：正常")).toBeInTheDocument();
    expect(screen.getByText("刷新：随页面查询读取已落库数据")).toBeInTheDocument();
    expect(screen.getByText("ISM 制造业 PMI")).toBeInTheDocument();
    expect(screen.getByText("明日")).toBeInTheDocument();
    expect(screen.getByText("高优先级")).toBeInTheDocument();
    expect(screen.getByText("央行开展逆回购操作，DR007 小幅下行")).toBeInTheDocument();
    expect(screen.getByText("供给/招标：当前窗口无事件")).toBeInTheDocument();
    expect(screen.queryByText("当前窗口暂无供给/招标事件。")).not.toBeInTheDocument();
  });

  it("renders the policy funding pane as a focused summary with grouped evidence", () => {
    render(
      <ResearchCalendarSection
        focusPolicyFunding
        macroBriefing={{
          releaseItems: [],
          releaseWindowLabel: "未来 45 天",
          releaseMessage: "暂无已维护发布日期，请补充配置清单。",
          newsItems: policyFundingSummary.groups.flatMap((group) => group.items),
          newsMessage: null,
          newsStale: false,
          newsFreshnessLabel: "最近更新 06-03 20:17",
          newsSourceLabel: "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）",
          newsAsOfLabel: "数据截至 06-03 20:17",
          newsStatusLabel: "来源状态：Tushare 兜底",
          newsRefreshLabel: "刷新：随页面查询读取已落库数据",
          policyFundingSummary,
          supplyItems: [],
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-policy-funding-pane")).toHaveAttribute(
      "data-focused",
      "true",
    );
    expect(screen.getByText(policyFundingSummary.headline)).toBeInTheDocument();
    expect(screen.getByText("Tushare 兜底")).toBeInTheDocument();
    expect(screen.getByText("央行/公开市场")).toBeInTheDocument();
    expect(screen.getByText("利率/债券")).toBeInTheDocument();
    expect(screen.getByText("本周中国央行公开市场将有9089亿元逆回购到期")).toBeInTheDocument();
    expect(screen.getByText("10年期美国国债收益率最新上涨2.8个基点，报4.483%。")).toBeInTheDocument();
  });
});
