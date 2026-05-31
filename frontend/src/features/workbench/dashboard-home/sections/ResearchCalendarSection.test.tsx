import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResearchCalendarSection } from "./ResearchCalendarSection";

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
            {
              id: "news-1",
              timeLabel: "04-21 15:06",
              topicLabel: "国际资讯",
              title: "国际油价直线拉升",
              freshnessLabel: "最近更新 04-21 15:06",
            },
          ],
          newsMessage: null,
          newsStale: false,
          newsFreshnessLabel: "最近更新 04-21 15:06",
          newsSourceLabel: "来源：Choice 宏观新闻",
          newsAsOfLabel: "数据截至 04-21 15:06",
          newsStatusLabel: "来源状态：正常",
          newsRefreshLabel: "刷新：随页面查询自动更新",
          supplyItems: [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }],
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    expect(screen.getByText("重大信息发布日期前瞻")).toBeInTheDocument();
    expect(screen.getByText("未来 45 天 · 1 项")).toBeInTheDocument();
    expect(screen.getByText("国内外宏观新闻")).toBeInTheDocument();
    expect(screen.getByText("来源：Choice 宏观新闻")).toBeInTheDocument();
    expect(screen.getByText("数据截至 04-21 15:06")).toBeInTheDocument();
    expect(screen.getByText("来源状态：正常")).toBeInTheDocument();
    expect(screen.getByText("刷新：随页面查询自动更新")).toBeInTheDocument();
    expect(screen.getByText("ISM 制造业 PMI")).toBeInTheDocument();
    expect(screen.getByText("明日")).toBeInTheDocument();
    expect(screen.getByText("高优先级")).toBeInTheDocument();
    expect(screen.getByText("国际油价直线拉升")).toBeInTheDocument();
    expect(screen.getByText("供给/招标：当前窗口无事件")).toBeInTheDocument();
    expect(screen.queryByText("当前窗口暂无供给/招标事件。")).not.toBeInTheDocument();
  });
});
