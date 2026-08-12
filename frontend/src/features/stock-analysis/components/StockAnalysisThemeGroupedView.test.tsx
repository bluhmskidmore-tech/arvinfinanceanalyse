import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  StockThemeBreakoutCard,
  StockThemeBreakoutReviewItem,
  StockThemeEvidenceStateRow,
} from "../lib/stockAnalysisPageModel";
import {
  buildStockThemeGroups,
  StockAnalysisThemeGroupedView,
} from "./StockAnalysisThemeGroupedView";

const GROUP_TESTID_PATTERN = /^stock-analysis-theme-group-/;

function buildCard(
  themeKey: string,
  themeName: string,
  rank: number,
  overrides: Partial<StockThemeBreakoutCard> = {},
): StockThemeBreakoutCard {
  return {
    rank,
    themeKey,
    themeName,
    parentSectorLabel: "电子 #1",
    summary: "观察范围内",
    reason: "题材内强势股占比达到观察阈值。",
    boundaryLabel: "边界：概念成分为当前时点快照。",
    strongCountLabel: "强势 3 只",
    limitCountLabel: "涨停 1 只",
    advanceRatioLabel: "上涨占比 62%",
    avgPctChangeLabel: "平均涨幅 2.10%",
    movementLabel: "异动 2 条",
    latestEventLabel: "最新事件：暂无",
    sourceKindLabel: "时点概念成分",
    leaders: [],
    ...overrides,
  };
}

describe("buildStockThemeGroups", () => {
  it("按 theme_key 分组，有信号的按行数降序，行数相同按 policy 声明序", () => {
    const { active, idle } = buildStockThemeGroups([
      buildCard("broker_proxy", "券商", 2),
      buildCard("ai_computing_proxy", "算力AI", 1),
      buildCard("semiconductor_proxy", "半导体", 3),
      buildCard("ai_computing_proxy", "算力AI", 4),
    ]);

    expect(active.map((group) => group.key)).toEqual([
      "ai_computing_proxy",
      "semiconductor_proxy",
      "broker_proxy",
    ]);
    expect(active[0]?.rows.map((row) => row.rank)).toEqual([1, 4]);
    expect(idle.map((entry) => entry.key)).toEqual([
      "robotics_proxy",
      "defense_proxy",
      "new_energy_proxy",
      "pharma_proxy",
    ]);
  });

  it("未知 theme_key 排在已知题材之后并保留数据里的题材名", () => {
    const { active } = buildStockThemeGroups([
      buildCard("low_altitude_proxy", "低空经济", 2),
      buildCard("broker_proxy", "券商", 1),
    ]);

    expect(active.map((group) => group.key)).toEqual(["broker_proxy", "low_altitude_proxy"]);
    expect(active[1]?.name).toBe("低空经济");
    expect(active[1]?.proxyCode).toBeNull();
  });
});

describe("StockAnalysisThemeGroupedView", () => {
  it("按题材分组渲染：标题、信号行数徽章与组内行归属正确", () => {
    const cards = [
      buildCard("ai_computing_proxy", "算力AI", 1, {
        leaders: [
          {
            stockCode: "300308.SZ",
            stockName: "中际旭创",
            pctChange: "+6.2%",
            turn: "8.1%",
            closeStrength: "0.94",
            tags: ["强势"],
          },
        ],
      }),
      buildCard("semiconductor_proxy", "半导体", 2),
      buildCard("ai_computing_proxy", "算力AI", 3),
    ];

    render(<StockAnalysisThemeGroupedView cards={cards} emptyMessage="暂无样本" />);

    const groups = screen.getAllByTestId(GROUP_TESTID_PATTERN);
    expect(groups.map((node) => node.getAttribute("data-testid"))).toEqual([
      "stock-analysis-theme-group-ai_computing_proxy",
      "stock-analysis-theme-group-semiconductor_proxy",
    ]);

    const aiGroup = screen.getByTestId("stock-analysis-theme-group-ai_computing_proxy");
    expect(within(aiGroup).getByRole("heading", { name: "算力AI" })).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-theme-count-ai_computing_proxy")).toHaveTextContent(
      "信号 2 行",
    );
    expect(
      within(aiGroup).getByTestId("stock-analysis-theme-grouped-row-ai_computing_proxy-1"),
    ).toBeInTheDocument();
    expect(
      within(aiGroup).getByTestId("stock-analysis-theme-grouped-row-ai_computing_proxy-3"),
    ).toBeInTheDocument();
    expect(within(aiGroup).getByText("中际旭创")).toBeInTheDocument();
    expect(within(aiGroup).getByText("强势")).toBeInTheDocument();

    const semiGroup = screen.getByTestId("stock-analysis-theme-group-semiconductor_proxy");
    expect(within(semiGroup).getByText("信号 1 行")).toBeInTheDocument();
    expect(within(semiGroup).getByText("S270000")).toBeInTheDocument();
  });

  it("行数相同的题材按 policy 声明序渲染", () => {
    render(
      <StockAnalysisThemeGroupedView
        cards={[
          buildCard("broker_proxy", "券商", 1),
          buildCard("semiconductor_proxy", "半导体", 2),
        ]}
        emptyMessage="暂无样本"
      />,
    );

    const groups = screen.getAllByTestId(GROUP_TESTID_PATTERN);
    expect(groups.map((node) => node.getAttribute("data-testid"))).toEqual([
      "stock-analysis-theme-group-semiconductor_proxy",
      "stock-analysis-theme-group-broker_proxy",
    ]);
  });

  it("题材筛选 chips：点选只显示该组，再点或点全部恢复；无信号题材 chip 禁用", () => {
    render(
      <StockAnalysisThemeGroupedView
        cards={[
          buildCard("ai_computing_proxy", "算力AI", 1),
          buildCard("ai_computing_proxy", "算力AI", 2),
          buildCard("broker_proxy", "券商", 3),
        ]}
        emptyMessage="暂无样本"
      />,
    );

    const allChip = screen.getByTestId("stock-analysis-theme-chip-all");
    const brokerChip = screen.getByTestId("stock-analysis-theme-chip-broker_proxy");
    expect(allChip).toHaveAttribute("aria-pressed", "true");
    expect(allChip).toHaveTextContent("3");

    fireEvent.click(brokerChip);
    expect(brokerChip).toHaveAttribute("aria-pressed", "true");
    expect(allChip).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("stock-analysis-theme-group-broker_proxy")).toBeInTheDocument();
    expect(
      screen.queryByTestId("stock-analysis-theme-group-ai_computing_proxy"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-theme-grouped-idle")).not.toBeInTheDocument();

    fireEvent.click(brokerChip);
    expect(screen.getAllByTestId(GROUP_TESTID_PATTERN)).toHaveLength(2);

    fireEvent.click(screen.getByTestId("stock-analysis-theme-chip-ai_computing_proxy"));
    fireEvent.click(allChip);
    expect(screen.getAllByTestId(GROUP_TESTID_PATTERN)).toHaveLength(2);

    const pharmaChip = screen.getByTestId("stock-analysis-theme-chip-pharma_proxy");
    expect(pharmaChip).toBeDisabled();
    expect(pharmaChip).toHaveTextContent("0");
  });

  it("7 题材全空时渲染空态，不渲染 chips 与无信号汇总条", () => {
    render(
      <StockAnalysisThemeGroupedView cards={[]} emptyMessage="当前没有题材观察样本。" />,
    );

    expect(screen.getByTestId("stock-analysis-theme-grouped-empty")).toHaveTextContent(
      "当前没有题材观察样本。",
    );
    expect(screen.queryByTestId("stock-analysis-theme-grouped-chips")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-theme-grouped-idle")).not.toBeInTheDocument();
  });

  it("单题材有数据时只渲染该组，其余题材进可折叠的无信号汇总条", () => {
    render(
      <StockAnalysisThemeGroupedView
        cards={[buildCard("semiconductor_proxy", "半导体", 1)]}
        emptyMessage="暂无样本"
      />,
    );

    expect(screen.getAllByTestId(GROUP_TESTID_PATTERN)).toHaveLength(1);

    const idleBar = screen.getByTestId("stock-analysis-theme-grouped-idle");
    const toggle = within(idleBar).getByRole("button", { name: /无信号题材 6 个/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(idleBar).queryByText("医药")).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const idleItems = within(idleBar).getAllByRole("listitem");
    expect(idleItems.map((item) => item.textContent)).toEqual([
      "算力AIS710000+S730000",
      "机器人与智能装备S640000",
      "国防军工S650000",
      "新能源S630000",
      "医药S370000",
      "券商S490000",
    ]);

    fireEvent.click(toggle);
    expect(within(idleBar).queryByText("医药")).not.toBeInTheDocument();
  });

  it("证据与复核区块随同形态 props 渲染", () => {
    const evidenceRows: StockThemeEvidenceStateRow[] = [
      {
        key: "concept_membership",
        label: "概念成分",
        status: "current_overlay",
        statusLabel: "当前时点覆盖",
        detail: "概念成分为当前快照，回看日期存在幸存者偏差。",
        rowCountLabel: "1200 行",
      },
    ];
    const reviewItems: StockThemeBreakoutReviewItem[] = [
      {
        rank: 8,
        themeKey: "pharma_proxy",
        themeName: "医药",
        sourceKindLabel: "行业代理篮子",
        parentSectorLabel: "医药生物 #9",
        summary: "强度不足",
        failedGateLabel: "未过门槛：强势股数量",
        reason: "题材内强势股数量未达门槛。",
        leaders: [],
      },
    ];

    render(
      <StockAnalysisThemeGroupedView
        cards={[buildCard("semiconductor_proxy", "半导体", 1)]}
        emptyMessage="暂无样本"
        evidenceRows={evidenceRows}
        reviewItems={reviewItems}
      />,
    );

    const evidence = screen.getByTestId("stock-analysis-theme-grouped-evidence");
    expect(within(evidence).getByText("题材证据受限")).toBeInTheDocument();
    expect(within(evidence).getByText("1 项证据")).toBeInTheDocument();
    expect(within(evidence).getByText("概念成分")).toBeInTheDocument();

    const review = screen.getByTestId("stock-analysis-theme-grouped-review");
    expect(within(review).getByText("题材未入选复核")).toBeInTheDocument();
    expect(within(review).getByText("待排查 1 项")).toBeInTheDocument();
    expect(within(review).getByText(/复核 #8 医药/)).toBeInTheDocument();
    expect(within(review).getByText("未过门槛：强势股数量")).toBeInTheDocument();
  });
});
