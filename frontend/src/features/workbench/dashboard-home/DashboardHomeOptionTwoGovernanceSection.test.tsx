import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardHomeAvailability } from "./dashboardHomeAvailability";
import {
  mapToHomeBodyView,
  type DashboardHomeBodyView,
  type MapToHomeBodyViewInput,
} from "./dashboardHomeBodyView";
import { DashboardHomeOptionTwoGovernanceSection } from "./DashboardHomeOptionTwoGovernanceSection";

const readyState = { kind: "ready", label: "已接入" } as const;

function makeView(
  overrides: Partial<DashboardHomeBodyView> = {},
): DashboardHomeBodyView {
  return {
    ...mapToHomeBodyView({
      reportDate: "2026-07-26",
      useMockFallback: true,
    } as MapToHomeBodyViewInput),
    ...overrides,
  };
}

const staleAvailability: DashboardHomeAvailability = {
  kind: "stale",
  failureKind: null,
  label: "展示上一版本",
  title: "主快照刷新失败，当前展示上一版本",
  reason: "主快照刷新未完成",
  impact: "使用前需复核",
  technicalDetail: null,
  requestedReportDate: "2026-07-27",
  actualReportDate: "2026-07-26",
  generatedAt: "2026-07-26 09:30",
  hasResolvedReportDate: true,
};

const errorAvailability: DashboardHomeAvailability = {
  kind: "error",
  failureKind: "requestFailed",
  label: "首页快照读取失败",
  title: "首页快照读取失败，模块保持可见",
  reason: "主快照请求未完成",
  impact: "主快照未闭合",
  technicalDetail: "snapshot unavailable",
  requestedReportDate: "2026-07-27",
  actualReportDate: "",
  generatedAt: null,
  hasResolvedReportDate: false,
};

function populatedView(): DashboardHomeBodyView {
  const base = makeView();
  return makeView({
    holdingsState: readyState,
    positionChangesState: readyState,
    researchReportsState: readyState,
    incomeTrendState: { kind: "stale", label: "收益数据偏旧" },
    holdingRows: [
      {
        id: "h-1",
        code: "240001.IB",
        name: "测试债一",
        assetClass: "利率债",
        marketValue: "10.00 亿",
        weight: "1.00%",
        ytm: "2.10%",
        duration: "3.20",
        rating: "不适用",
      },
      {
        id: "h-2",
        code: "240002.IB",
        name: "测试债二",
        assetClass: "利率债",
        marketValue: "8.00 亿",
        weight: "0.80%",
        ytm: "2.20%",
        duration: "4.10",
        rating: "不适用",
      },
    ],
    positionChanges: [
      {
        id: "p-1",
        code: "240001.IB",
        name: "测试债一",
        reason: "增持",
        currentValue: "10.00 亿",
        changeValue: "+1.00 亿",
        weightDelta: "+0.10pp",
        direction: "increase",
        tone: "up",
        barPct: 100,
      },
    ],
    researchReports: [
      {
        id: "r-1",
        title: "利率周报",
        category: "固收",
        publishedAt: "2026-07-25",
        source: "research",
        institution: "研究机构",
        summary: "—",
        link: null,
        isNewsFallback: false,
      },
    ],
    incomeTrend: [
      {
        id: "i-1",
        date: "2026-06-30",
        portfolioPnl: "1.00 亿",
        benchmarkPnl: "0.80 亿",
        excessPnl: "0.20 亿",
        portfolioRaw: 100_000_000,
        benchmarkRaw: 80_000_000,
        excessRaw: 20_000_000,
        missingReason: null,
      },
      {
        id: "i-2",
        date: "2026-07-24",
        portfolioPnl: "1.20 亿",
        benchmarkPnl: "0.90 亿",
        excessPnl: "0.30 亿",
        portfolioRaw: 120_000_000,
        benchmarkRaw: 90_000_000,
        excessRaw: 30_000_000,
        missingReason: null,
      },
    ],
    bondNews: {
      ...base.bondNews,
      holdingHits: base.bondNews.holdingHits.slice(0, 1),
      marketNews: [],
      creditAndIssuanceNews: [],
    },
    macroBriefing: {
      ...base.macroBriefing,
      newsItems: base.macroBriefing.newsItems.slice(0, 1),
    },
  });
}

describe("DashboardHomeOptionTwoGovernanceSection", () => {
  it("defaults to the six-row source gate and keeps every tab panel mounted", () => {
    render(<DashboardHomeOptionTwoGovernanceSection view={populatedView()} />);

    const ledger = screen.getByTestId("dashboard-home-governance-ledger");
    expect(within(ledger).getByRole("heading", { name: "数据治理台账" })).toBeInTheDocument();
    expect(within(ledger).getByRole("tab", { name: "来源核验" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getAllByTestId("dashboard-home-source-gate-row")).toHaveLength(6);
    expect(screen.getByTestId("dashboard-home-evidence-chain")).toHaveAttribute("hidden");
    expect(screen.getByTestId("dashboard-home-api-row-reserved")).toBeInTheDocument();
    expect(screen.getAllByTestId("dashboard-home-data-task-row")).toHaveLength(4);
    expect(ledger).toHaveTextContent("页面读链 · 非审计结论");
    expect(ledger).not.toHaveTextContent("审计已闭合");
  });

  it("keeps ready rows quiet: no completion badge word, label only in title and screen-reader text", () => {
    render(<DashboardHomeOptionTwoGovernanceSection view={populatedView()} />);

    const source = screen.getByTestId("dashboard-home-source-gate");
    // 上游 ready 文案「已接入」不进台账（§12 结论 17 常态收声）。
    expect(source).not.toHaveTextContent("已接入");
    expect(source).not.toHaveTextContent("已就绪");
    const holdingsRow = source.querySelector('[data-source-id="holdings"]');
    const status = holdingsRow?.querySelector('[data-tone="ok"]');
    expect(status).toHaveAttribute("title", "正常");
    expect(status?.textContent).toBe("正常");
    // 异常态仍可见发声：stale 行保留原文与琥珀 tone。
    const incomeRow = source.querySelector('[data-source-id="income"]');
    expect(incomeRow?.querySelector('[data-tone="warn"]')).toHaveTextContent("收益数据偏旧");
  });

  it("maps news source status by meaning: 正常 is a quiet ok dot, 兜底/偏旧 stay amber", () => {
    const base = populatedView();
    render(
      <DashboardHomeOptionTwoGovernanceSection
        view={makeView({
          ...base,
          bondNews: {
            ...base.bondNews,
            marketNews: [
              {
                id: "bn-1",
                title: "利率债一级招标结果",
                timeLabel: "09-02 10:00",
                sourceLabel: "Choice",
                topicLabel: "债券市场",
                hitLabel: null,
              },
            ],
            statusLabel: "来源状态：正常",
          },
          macroBriefing: {
            ...base.macroBriefing,
            newsItems: [
              {
                id: "mn-1",
                timeLabel: "09-02 13:36",
                topicLabel: "央行/公开市场",
                title: "央行开展逆回购操作",
                freshnessLabel: "今日更新",
              },
            ],
            newsStale: false,
            newsStatusLabel: "来源状态：Tushare 兜底",
          },
        })}
      />,
    );

    const source = screen.getByTestId("dashboard-home-source-gate");
    const bondRow = source.querySelector('[data-source-id="bond-news"]');
    const bondStatus = bondRow?.querySelector('[data-tone="ok"]');
    expect(bondStatus).toHaveAttribute("title", "正常");
    expect(bondRow).not.toHaveTextContent("来源状态");
    const macroRow = source.querySelector('[data-source-id="macro-news"]');
    expect(macroRow?.querySelector('[data-tone="warn"]')).toHaveTextContent("Tushare 兜底");
    expect(macroRow).not.toHaveTextContent("来源状态：");
  });

  it("shows empty, error and stale states without inventing dates", () => {
    const base = makeView();
    render(
      <DashboardHomeOptionTwoGovernanceSection
        view={makeView({
          holdingsState: { kind: "empty", label: "持仓暂无数据" },
          positionChangesState: { kind: "error", label: "变动读取失败" },
          incomeTrendState: { kind: "stale", label: "收益数据偏旧" },
          researchReportsState: { kind: "empty", label: "研报暂无数据" },
          holdingRows: [],
          positionChanges: [],
          incomeTrend: [],
          researchReports: [],
          bondNews: {
            ...base.bondNews,
            holdingHits: [],
            marketNews: [],
            creditAndIssuanceNews: [],
          },
          macroBriefing: { ...base.macroBriefing, newsItems: [] },
        })}
        availability={errorAvailability}
      />,
    );

    const source = screen.getByTestId("dashboard-home-source-gate");
    expect(source).toHaveTextContent("持仓暂无数据");
    expect(source).toHaveTextContent("变动读取失败");
    expect(source).toHaveTextContent("收益数据偏旧");
    expect(source).toHaveTextContent("暂无数据");
    expect(
      source.querySelector('[data-source-id="holdings"]'),
    ).toHaveTextContent("—");

    fireEvent.click(screen.getByRole("tab", { name: "接口台账" }));
    expect(screen.getByTestId("dashboard-home-api-row-snapshot")).toHaveTextContent(
      "首页快照读取失败",
    );
    expect(screen.getByTestId("dashboard-home-api-row-supplemental")).toHaveTextContent(
      "未请求",
    );
    expect(screen.getByTestId("dashboard-home-api-row-holdings")).toHaveTextContent(
      "未请求",
    );
    expect(screen.getByTestId("dashboard-home-api-row-reserved")).toHaveTextContent(
      "保留",
    );
  });

  it("reports evidence dates and landed counts from the visible view", () => {
    render(
      <DashboardHomeOptionTwoGovernanceSection
        view={populatedView()}
        availability={staleAvailability}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "证据覆盖" }));
    expect(screen.getByTestId("dashboard-home-evidence-chain")).not.toHaveAttribute("hidden");
    expect(screen.getByTestId("dashboard-home-evidence-row-snapshot")).toHaveTextContent(
      "2026-07-26 09:30",
    );
    expect(screen.getByTestId("dashboard-home-evidence-row-snapshot")).toHaveTextContent(
      "展示上一版本",
    );
    expect(screen.getByTestId("dashboard-home-evidence-row-formal")).toHaveTextContent(
      "2026-07-26",
    );
    expect(screen.getByTestId("dashboard-home-evidence-row-formal")).toHaveTextContent("3");
    expect(screen.getByTestId("dashboard-home-evidence-row-analytical")).toHaveTextContent(
      "2026-07-25",
    );
    expect(screen.getByTestId("dashboard-home-evidence-row-analytical")).toHaveTextContent("3");
    expect(screen.getByTestId("dashboard-home-evidence-row-reserved")).toHaveTextContent(
      "保留",
    );
  });

  it("renders the supplemental label and supports wrapped arrow-key tab navigation", () => {
    render(
      <DashboardHomeOptionTwoGovernanceSection
        view={populatedView()}
        availability={staleAvailability}
        supplementalStateLabel="补充接口读取中"
      />,
    );

    const sourceTab = screen.getByRole("tab", { name: "来源核验" });
    sourceTab.focus();
    fireEvent.keyDown(sourceTab, { key: "ArrowLeft" });
    const lineageTab = screen.getByRole("tab", { name: "数据链路" });
    expect(lineageTab).toHaveFocus();
    expect(lineageTab).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(lineageTab, { key: "ArrowRight" });
    expect(sourceTab).toHaveFocus();
    expect(sourceTab).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "接口台账" }));
    expect(screen.getByTestId("dashboard-home-api-row-supplemental")).toHaveTextContent(
      "补充接口读取中",
    );
    expect(
      screen.getAllByTestId(/^dashboard-home-api-row-/),
    ).toHaveLength(8);
  });
});
