import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondNewsSection } from "./BondNewsSection";

describe("BondNewsSection", () => {
  it("renders bond news groups with source status and compact empty states", () => {
    render(
      <BondNewsSection
        bondNews={{
          holdingHits: [
            {
              id: "holding-name",
              title: "25山东债06 成交活跃",
              timeLabel: "06-01 09:30",
              sourceLabel: "市场快讯",
              topicLabel: "持仓命中",
              hitLabel: "命中持仓：25山东债06",
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
          sourceLabel: "来源：Choice / Tushare 债券新闻",
          asOfLabel: "数据截至 04-21 15:06",
          statusLabel: "来源状态：正常",
          refreshLabel: "刷新：随页面查询自动更新",
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-bond-news")).toBeInTheDocument();
    expect(screen.getByText("债券信息新闻")).toBeInTheDocument();
    expect(screen.getByText("来源：Choice / Tushare 债券新闻")).toBeInTheDocument();
    expect(screen.getByText("数据截至 04-21 15:06")).toBeInTheDocument();
    expect(screen.getByText("来源状态：正常")).toBeInTheDocument();
    expect(screen.getByText("刷新：随页面查询自动更新")).toBeInTheDocument();

    const holdingGroup = screen.getByTestId("dashboard-home-bond-news-holding");
    expect(within(holdingGroup).getAllByText("持仓命中")).toHaveLength(2);
    expect(within(holdingGroup).getByText("25山东债06 成交活跃")).toBeInTheDocument();
    expect(within(holdingGroup).getByText("命中持仓：25山东债06 · 06-01 09:30")).toBeInTheDocument();

    const marketGroup = screen.getByTestId("dashboard-home-bond-news-market");
    expect(within(marketGroup).getAllByText("债券市场")).toHaveLength(2);
    expect(within(marketGroup).getByText("国债收益率曲线延续下行，资金面保持宽松")).toBeInTheDocument();
    expect(within(marketGroup).getByText("政策要闻 · 06-01 09:10")).toBeInTheDocument();

    const creditGroup = screen.getByTestId("dashboard-home-bond-news-credit");
    expect(within(creditGroup).getByText("发行/评级")).toBeInTheDocument();
    expect(within(creditGroup).getByText("发行/评级：暂无相关新闻")).toBeInTheDocument();
  });
});
