import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildHomeMacroBriefingModel, type HomeMacroBriefingModel } from "../adapters/buildHomeMacroBriefingModel";
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
  diagnostics: {
    summary: "当前源 Tushare 兜底：原始 9 条，入选 8 条，去重后 7 条，展示 6 条。",
    sourceVerdict: "当前使用 Tushare 兜底：Choice 快讯偏旧，已切换到兜底源。",
    filterNarrative: "已展示 6 条；另有 3 条因非政策/资金面、重复标题、超过展示上限未展示。",
    actionHint: null,
    narrativeTone: "info" as const,
    emptyHint: null,
    metrics: [
      { id: "raw", label: "原始", value: "9 条", tone: "neutral" as const },
      { id: "eligible", label: "入选", value: "8 条", tone: "info" as const },
      { id: "unique", label: "去重后", value: "7 条", tone: "info" as const },
      { id: "displayed", label: "展示", value: "6 条", tone: "info" as const },
    ],
    reasons: [
      { id: "not-policy-funding", label: "非政策/资金面", countLabel: "1 条", tone: "warning" as const },
      { id: "duplicate-title", label: "重复标题", countLabel: "1 条", tone: "neutral" as const },
      { id: "over-limit", label: "超过展示上限", countLabel: "1 条", tone: "neutral" as const },
    ],
  },
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
          releaseHistoryItems: [],
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
          supplyItems: [{ id: "supply-empty", label: "供给/招标：已查询当前窗口，暂无事件" }],
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    expect(screen.getByText("宏观 / 日历上下文")).toBeInTheDocument();
    expect(screen.getByLabelText("宏观上下文摘要")).toBeInTheDocument();
    expect(screen.getByText("发布项")).toBeInTheDocument();
    expect(screen.getByText("重大信息发布日期前瞻")).toBeInTheDocument();
    expect(screen.getByText("未来 45 天 · 1 项")).toBeInTheDocument();
    expect(screen.getByText("主题 / 事件")).toBeInTheDocument();
    expect(screen.getByText("政策与资金面")).toBeInTheDocument();

    // 来源长说明只进 title，可见处保留短文案；正常态不渲染状态胶囊。
    const policyTrustStrip = screen.getByLabelText("政策与资金面数据状态");
    expect(
      within(policyTrustStrip).getByText("来源 Choice 宏观新闻"),
    ).toBeInTheDocument();
    expect(policyTrustStrip).toHaveAttribute(
      "title",
      "来源：Choice 宏观新闻 · 来源状态：正常 · 数据截至 04-21 15:06 · 刷新：随页面查询读取已落库数据",
    );
    expect(screen.queryByText("来源状态：正常")).not.toBeInTheDocument();
    expect(screen.queryByText("刷新：随页面查询读取已落库数据")).not.toBeInTheDocument();
    expect(screen.queryByText("正常")).not.toBeInTheDocument();
    expect(screen.queryByText("数据截至 04-21 15:06")).not.toBeInTheDocument();
    expect(screen.getByText("最近更新 04-21 15:06")).toBeInTheDocument();
    expect(screen.getByText("ISM 制造业 PMI")).toBeInTheDocument();
    expect(screen.getByText("明日")).toBeInTheDocument();
    expect(screen.getByText("高优先级")).toBeInTheDocument();
    expect(screen.getByText("央行开展逆回购操作，DR007 小幅下行")).toBeInTheDocument();
    expect(screen.getByText("供给/招标：已查询当前窗口，暂无事件")).toBeInTheDocument();
    expect(screen.queryByText("当前窗口暂无供给/招标事件。")).not.toBeInTheDocument();
  });

  it("renders the policy funding pane as a summary with grouped evidence", () => {
    render(
      <ResearchCalendarSection
        macroBriefing={{
          releaseItems: [],
          releaseHistoryItems: [],
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

    expect(screen.getByTestId("dashboard-home-policy-funding-pane")).toBeInTheDocument();
    expect(screen.getByText(policyFundingSummary.headline)).toBeInTheDocument();
    // 异常态（兜底）胶囊保留；来源长说明折叠为短文案，原文进 title。
    const fallbackChip = screen.getByText("Tushare 兜底");
    expect(fallbackChip).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("来源 Tushare · Choice 回退")).toBeInTheDocument();
    expect(
      screen.queryByText("来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）"),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("政策与资金面数据状态")).toHaveAttribute(
      "title",
      expect.stringContaining("来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）"),
    );
    // 未来事件空态收缩为一行说明，不渲染空表头。
    expect(
      screen.getByText("暂无已维护发布日期，请补充配置清单。"),
    ).toBeInTheDocument();
    expect(screen.queryByText("主题 / 事件")).not.toBeInTheDocument();
    expect(screen.getByText("央行/公开市场")).toBeInTheDocument();
    expect(screen.getByText("利率/债券")).toBeInTheDocument();
    expect(screen.getByText("本周中国央行公开市场将有9089亿元逆回购到期")).toBeInTheDocument();
    expect(screen.getByText("10年期美国国债收益率最新上涨2.8个基点，报4.483%。")).toBeInTheDocument();
    expect(screen.getByText("数据诊断")).toBeInTheDocument();
    expect(screen.getByText(policyFundingSummary.diagnostics.summary)).toBeInTheDocument();
    expect(screen.getByText(policyFundingSummary.diagnostics.sourceVerdict)).toBeInTheDocument();
    expect(screen.getByText(policyFundingSummary.diagnostics.filterNarrative)).toBeInTheDocument();
    expect(screen.queryByText("请复核")).not.toBeInTheDocument();
    expect(screen.getByText("原始")).toBeInTheDocument();
    expect(screen.getByText("展示")).toBeInTheDocument();
    expect(screen.getByText("非政策/资金面")).toBeInTheDocument();
    expect(screen.getByText("超过展示上限")).toBeInTheDocument();
  });

  it("surfaces maintained release history below the forward calendar", () => {
    const macroBriefing = {
      releaseItems: [
        {
          id: "nbs-pmi-2026-06",
          date: "2026-06-30",
          dateLabel: "06-30",
          daysUntilLabel: "2天后",
          region: "国内",
          title: "中国官方 PMI（2026年6月）",
          category: "PMI",
          importance: "high",
          importanceLabel: "高优先级",
          timeLabel: "09:30 CST",
          sourceName: "NBS",
          sourceUrl: "https://www.stats.gov.cn/",
          history: {
            latestLabel: "最近一期",
            latestValue: "5月 49.5",
            previousLabel: "前值",
            previousValue: "4月 49.0",
            changeLabel: "较前值",
            changeValue: "+0.5",
            changeTone: "up",
            note: "制造业景气回升但仍低于荣枯线。",
            sourceLabel: "NBS 发布稿",
          },
        },
      ],
      releaseWindowLabel: "未来 45 天 · 1 项",
      releaseMessage: null,
      newsItems: [],
      newsMessage: "政策与资金面：暂无债券相关更新",
      newsStale: false,
      newsFreshnessLabel: "暂无更新",
      newsSourceLabel: "来源：Choice 宏观新闻",
      newsAsOfLabel: "数据截至：暂无",
      newsStatusLabel: "来源状态：暂无数据",
      newsRefreshLabel: "刷新：随页面查询读取已落库数据",
      policyFundingSummary: {
        headline: "暂无可展示的政策与资金面快讯。",
        chips: [],
        groups: [],
      },
      supplyItems: [],
    } as unknown as HomeMacroBriefingModel;
    macroBriefing.releaseHistoryItems =
      macroBriefing.releaseItems as HomeMacroBriefingModel["releaseHistoryItems"];

    render(<ResearchCalendarSection macroBriefing={macroBriefing} />);

    const history = screen.getByLabelText("重大信息过往数据与变动");
    expect(within(history).getByText("过往数据与变动")).toBeInTheDocument();
    expect(within(history).getByText("中国官方 PMI（2026年6月）")).toBeInTheDocument();
    expect(within(history).getByText("5月 49.5")).toBeInTheDocument();
    expect(within(history).getByText("4月 49.0")).toBeInTheDocument();
    expect(within(history).getByText("+0.5")).toBeInTheDocument();
    expect(within(history).getByText("制造业景气回升但仍低于荣枯线。")).toBeInTheDocument();
  });

  it("shows maintained history when current forward releases have no history", () => {
    const macroBriefing = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-07-16",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-07-16 to 2026-08-30",
        message: null,
      },
    });

    render(<ResearchCalendarSection macroBriefing={macroBriefing} />);

    expect(screen.getByText("ISM Manufacturing PMI")).toBeInTheDocument();
    expect(screen.getByText("ISM May 2026 Manufacturing ROB")).toBeInTheDocument();
  });

  it("keeps maintained history visible when the forward calendar is empty", () => {
    const macroBriefing = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-08-01",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-08-01 to 2026-09-15",
        message: null,
      },
    });

    expect(macroBriefing.releaseItems).toHaveLength(0);
    expect(macroBriefing.releaseHistoryItems).toHaveLength(6);

    render(<ResearchCalendarSection macroBriefing={macroBriefing} />);

    expect(screen.getByText("ISM Manufacturing PMI")).toBeInTheDocument();
  });
});
