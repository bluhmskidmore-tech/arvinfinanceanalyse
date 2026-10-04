import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EM_DASH } from "../../../utils/format";

vi.mock("../../../components/charts/BaseChart", () => ({
  BaseChart: () => <div data-testid="base-chart-stub" />,
}));

import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import {
  buildStockAnalysisResearchDeskModel,
  type BuildStockAnalysisResearchDeskModelInput,
  type ResearchDeskEndpointItem,
} from "../lib/stockAnalysisResearchDeskModel";
import {
  StockAnalysisResearchDesk,
  type StockAnalysisResearchDeskProps,
} from "./StockAnalysisResearchDesk";

function buildCandidate(
  overrides: Partial<StockCandidateReviewQueueItem> = {},
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "示例科技",
    sectorCode: "801010",
    sectorName: "科技",
    headline: "观察候选 #1 · 示例科技",
    sourcePool: "stock_candidates",
    sourcePoolLabel: "趋势突破",
    walkForward: null,
    pattern: "突破观察",
    patternNote: "量价结构已经返回。",
    distanceToBreakoutPct: "+1.2%",
    reviewFocus: "核实公告催化后再确认候选状态。",
    primaryEvidence: [
      { key: "close_vs_break", label: "收盘 vs 观察位", value: "21.9 / 21.8" },
    ],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [
      { key: "fusion_score", label: "融合得分", value: "88" },
      { key: "pe_ttm", label: "市盈率", value: "18.2x" },
      { key: "pctchange", label: "个股涨幅", value: "1.20" },
    ],
    ...overrides,
  };
}

const DEFAULT_ENDPOINT_ITEMS: ResearchDeskEndpointItem[] = [
  {
    key: "strategy",
    label: "策略接口",
    statusLabel: "已就绪",
    businessDateLabel: "—",
    description: "候选快照已经返回。",
    tone: "positive",
  },
];

type ModelOverrides = Partial<
  Pick<
    BuildStockAnalysisResearchDeskModelInput,
    "decisionStatusLabel" | "decisionReason" | "candidateProgressionAllowed" | "endpointItems"
  >
>;

/** 用真实模型构造研究台展示数据，保证组件测试走的是生产路径而不是手写 props。 */
function buildModel(
  candidates: StockCandidateReviewQueueItem[],
  selectedCandidate: StockCandidateReviewQueueItem | null,
  overrides: ModelOverrides = {},
) {
  return buildStockAnalysisResearchDeskModel({
    decisionStatusLabel: "观察",
    decisionReason: "市场门控允许观察，仍需完成个股复核。",
    candidateProgressionAllowed: true,
    poolTab: "queue",
    selectedSectorLabel: "全部行业",
    selectedCandidate,
    poolCandidates: candidates,
    signalWindow: null,
    selectedRisk: null,
    detailQueryState: "idle",
    detailPayload: null,
    klineQueryState: "idle",
    klinePayload: null,
    newsQueryState: "idle",
    newsPayload: null,
    selectedHistoryRows: [],
    endpointItems: DEFAULT_ENDPOINT_ITEMS,
    noteDraft: "",
    savedNote: "",
    auditRows: [],
    analyticsAsOfDate: "2026-08-24",
    ...overrides,
  });
}

function buildProps(
  overrides: Partial<StockAnalysisResearchDeskProps> = {},
  modelOverrides: ModelOverrides = {},
): StockAnalysisResearchDeskProps {
  const candidates = overrides.poolCandidates ?? [
    buildCandidate(),
    buildCandidate({
      rank: 2,
      stockCode: "000002.SZ",
      stockName: "示例金融",
      sectorCode: "801020",
      sectorName: "金融",
      headline: "观察候选 #2 · 示例金融",
      distanceToBreakoutPct: "-0.8%",
    }),
  ];
  const selectedCandidate =
    overrides.selectedCandidate === undefined ? candidates[0] : overrides.selectedCandidate;

  return {
    model: buildModel(candidates, selectedCandidate, modelOverrides),
    queueSearchText: "",
    onQueueSearchTextChange: vi.fn(),
    sectorOptions: [
      ["801010", "科技"],
      ["801020", "金融"],
    ],
    selectedSectorCode: null,
    onSelectSector: vi.fn(),
    poolTab: "queue",
    onPoolTabChange: vi.fn(),
    dossierTab: "summary",
    onDossierTabChange: vi.fn(),
    poolCandidates: candidates,
    queueVisibleCount: candidates.length,
    queueTotalCount: candidates.length,
    reviewQueueUsesHybridFusion: false,
    selectedCandidate,
    selectedCandidateCode: selectedCandidate?.stockCode ?? null,
    onSelectCandidate: vi.fn(),
    watchlistCodes: [],
    onToggleWatchlist: vi.fn(),
    selectedRisk: null,
    noteDraft: "",
    onNoteDraftChange: vi.fn(),
    savedNote: "",
    onSaveNote: vi.fn(),
    onOpenDeepResearch: vi.fn(),
    onJumpToEvidence: vi.fn(),
    onOpenDetailDrawer: vi.fn(),
    onOpenHistory: vi.fn(),
    sectorLinkSummary: "科技与金融候选并列",
    sectorLinkFocus: "优先复核突破距离较近的标的",
    queueEmptyHeadline: "暂无候选",
    queueEmptyDetail: "等待候选接口返回。",
    historyLoading: false,
    historyLoaded: true,
    ...overrides,
  };
}

describe("StockAnalysisResearchDesk", () => {
  it("renders the default candidate pool and the selected security dossier", () => {
    render(<StockAnalysisResearchDesk {...buildProps()} />);

    expect(screen.getByTestId("stock-analysis-review-queue")).toHaveTextContent("精选池");
    expect(screen.getByTestId("stock-analysis-review-queue")).toHaveTextContent("涨跌");
    expect(screen.getByTestId("stock-analysis-review-queue")).toHaveTextContent("+1.20%");
    expect(screen.getByText("示例金融")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "示例科技 000001.SZ" }),
    ).toBeInTheDocument();
    expect(screen.getByText("价格序列待补")).toBeInTheDocument();
  });

  it("collapses the daily change column when every current candidate lacks a daily change", () => {
    const candidates = [
      buildCandidate({
        rawFields: [{ key: "fusion_score", label: "融合得分", value: "88" }],
      }),
      buildCandidate({
        rank: 2,
        stockCode: "000002.SZ",
        stockName: "示例金融",
        rawFields: [{ key: "fusion_score", label: "融合得分", value: "77" }],
      }),
    ];

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: candidates,
          selectedCandidate: candidates[0],
          selectedCandidateCode: candidates[0].stockCode,
        })}
      />,
    );

    const queue = screen.getByTestId("stock-analysis-review-queue");
    const table = queue.querySelector<HTMLElement>("[data-has-daily-change='false']");
    expect(table).not.toBeNull();
    expect(within(queue).queryByText("涨跌幅")).not.toBeInTheDocument();
    expect(within(queue).getAllByText("涨跌幅请查看个股详情")).toHaveLength(1);
    expect(table?.querySelector("[aria-hidden='true']")?.children).toHaveLength(4);
    expect(
      within(queue).getByRole("button", { name: /000001\.SZ.*示例科技/ }).parentElement
        ?.children,
    ).toHaveLength(4);
    expect(
      within(queue).getByRole("button", { name: /000002\.SZ.*示例金融/ }).parentElement,
    ).toHaveAttribute("data-active", "false");
  });

  it("keeps the daily change column when zero is the only legal value and leaves missing rows empty", () => {
    const candidates = [
      buildCandidate({
        rawFields: [{ key: "fusion_score", label: "融合得分", value: "88" }],
      }),
      buildCandidate({
        rank: 2,
        stockCode: "000002.SZ",
        stockName: "示例金融",
        rawFields: [
          { key: "fusion_score", label: "融合得分", value: "77" },
          { key: "pctchange", label: "个股涨幅", value: "0" },
        ],
      }),
    ];

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: candidates,
          selectedCandidate: candidates[0],
          selectedCandidateCode: candidates[0].stockCode,
        })}
      />,
    );

    const queue = screen.getByTestId("stock-analysis-review-queue");
    const table = queue.querySelector<HTMLElement>("[data-has-daily-change='true']");
    const missingRow = within(queue).getByRole("button", {
      name: /000001\.SZ.*示例科技/,
    }).parentElement;
    const zeroRow = within(queue).getByRole("button", {
      name: /000002\.SZ.*示例金融/,
    }).parentElement;

    expect(table).not.toBeNull();
    expect(within(queue).getByText("涨跌幅")).toBeInTheDocument();
    expect(within(queue).queryByText("涨跌幅请查看个股详情")).not.toBeInTheDocument();
    expect(within(missingRow as HTMLElement).getByText(EM_DASH)).toBeInTheDocument();
    expect(within(zeroRow as HTMLElement).getByText("0.00%")).toBeInTheDocument();
    expect(table?.querySelector("[aria-hidden='true']")?.children).toHaveLength(5);
    expect(missingRow?.children).toHaveLength(5);
    expect(zeroRow?.children).toHaveLength(5);
  });

  it("calls onSelectCandidate when a candidate row is activated", async () => {
    const user = userEvent.setup();
    const onSelectCandidate = vi.fn();
    render(
      <StockAnalysisResearchDesk {...buildProps({ onSelectCandidate })} />,
    );

    await user.click(
      screen.getByRole("button", { name: /000002\.SZ.*示例金融/ }),
    );

    expect(onSelectCandidate).toHaveBeenCalledWith("000002.SZ");
  });

  it("routes dossier changes while keeping evidence visible in the action rail", async () => {
    const user = userEvent.setup();
    const props = buildProps();
    const { rerender } = render(<StockAnalysisResearchDesk {...props} />);

    await user.click(screen.getByRole("button", { name: "基本面" }));
    expect(props.onDossierTabChange).toHaveBeenCalledWith("fundamentals");
    rerender(<StockAnalysisResearchDesk {...props} dossierTab="fundamentals" />);
    expect(screen.getByText("触发与失效")).toBeInTheDocument();

    expect(screen.getAllByText("策略接口").length).toBeGreaterThan(0);
    expect(screen.getAllByText("已就绪").length).toBeGreaterThan(0);
  });

  it("forwards note edits and the save action", async () => {
    const user = userEvent.setup();
    const props = buildProps();
    render(<StockAnalysisResearchDesk {...props} />);

    fireEvent.change(screen.getByRole("textbox", { name: /^研究备注$/ }), {
      target: { value: "关注业绩兑现" },
    });
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(props.onNoteDraftChange).toHaveBeenCalledWith("关注业绩兑现");
    expect(props.onSaveNote).toHaveBeenCalledOnce();
  });

  it("keeps the desk and evidence navigation usable while candidate actions are disabled without a selected row", async () => {
    const user = userEvent.setup();
    const props = buildProps(
      {
        poolCandidates: [],
        queueVisibleCount: 0,
        queueTotalCount: 0,
        selectedCandidate: null,
        selectedCandidateCode: null,
      },
      {
        decisionStatusLabel: "研究投影为空",
        decisionReason: "权威研究队列没有可选记录。",
        candidateProgressionAllowed: false,
      },
    );

    render(<StockAnalysisResearchDesk {...props} />);

    expect(screen.getByTestId("stock-analysis-research-desk")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-review-queue")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-research-dossier")).toHaveTextContent("暂无研究档案");
    expect(screen.getByTestId("stock-analysis-research-audit")).toBeInTheDocument();

    const actionRail = screen.getByTestId("stock-analysis-action-rail");
    for (const name of [
      "开始深度研究",
      "加入自选",
      "回溯该信号历史表现",
      "打开原始详情抽屉",
      "保存",
    ]) {
      expect(within(actionRail).getByRole("button", { name })).toBeDisabled();
    }

    const evidenceButton = within(actionRail).getByRole("button", { name: "查看全部" });
    expect(evidenceButton).toBeEnabled();
    await user.click(evidenceButton);
    expect(props.onJumpToEvidence).toHaveBeenCalledOnce();

    const fundamentalsTab = screen.getByRole("button", { name: "基本面" });
    expect(fundamentalsTab).toBeEnabled();
    await user.click(fundamentalsTab);
    expect(props.onDossierTabChange).toHaveBeenCalledWith("fundamentals");
  });

  it("keeps the institutional summary bands and real evidence counts visible", () => {
    const endpointItems: ResearchDeskEndpointItem[] = Array.from({ length: 6 }, (_, index) => ({
      key: `source-${index + 1}`,
      label: `来源 ${index + 1}`,
      statusLabel: index === 5 ? "待复核" : "已就绪",
      businessDateLabel: `2026-08-${String(index + 19).padStart(2, "0")}`,
      description: `来源说明 ${index + 1} · 日期：2026-08-${String(index + 19).padStart(2, "0")}`,
      tone: index === 5 ? "warning" : "positive",
    }));
    const selectedCandidate = buildCandidate({
      boundaryEvidence: ["门槛一", "门槛二", "门槛三"],
    });

    render(
      <StockAnalysisResearchDesk
        {...buildProps(
          {
            poolCandidates: [selectedCandidate, buildCandidate({ stockCode: "000002.SZ", stockName: "示例金融" })],
            selectedCandidate,
            selectedCandidateCode: selectedCandidate.stockCode,
          },
          { endpointItems },
        )}
      />,
    );

    expect(screen.getByLabelText("因子指标").querySelectorAll("[data-accent]")).toHaveLength(8);
    expect(screen.queryByText("结构")).not.toBeInTheDocument();
    // 主理由与三条边界共四条提示，不作为门禁完成度。
    expect(screen.getByText("复核边界（4 条）")).toBeInTheDocument();
    // 证据来源先列选中标的自己的三条溯源（详情 / K 线 / 事件），再补通用接口证据，最多 6 条。
    const rail = screen.getByTestId("stock-analysis-action-rail");
    expect(rail).toHaveTextContent("个股详情");
    expect(rail).toHaveTextContent("K线观察");
    expect(rail).toHaveTextContent("市场事件");
    expect(screen.getByTitle("来源说明 3 · 日期：2026-08-21")).toBeInTheDocument();
    expect(screen.queryByTitle("来源说明 4 · 日期：2026-08-22")).not.toBeInTheDocument();
    expect(screen.getAllByText("系统").length).toBeGreaterThan(0);
    expect(screen.getByText(/当前展示/)).toBeInTheDocument();
  });

  it.each(["未知边界未就绪，保留原始说明。", "constructor"])(
    "renders unknown boundary %s without guessing pass or block states",
    (unknownBoundary) => {
      const decisionReason =
        "研究候选可复核，仍有数据或边界事项待确认；当日研究数据可用；盘前资格尚未闭合（当前数据尚未绑定已发布版本），风险与执行结论保持关闭。";
      const queueBoundary =
        "候选来自 workbench 首屏只读队列；门禁与正式用途边界以接口状态为准。";
      const overlayBoundary = "当前覆盖 · 非时点 · 不可历史使用 · 仅观察";
      const selectedCandidate = buildCandidate({
        boundaryEvidence: [queueBoundary, overlayBoundary, unknownBoundary],
      });

      const props = buildProps(
        {
          poolCandidates: [selectedCandidate],
          queueVisibleCount: 1,
          queueTotalCount: 1,
          selectedCandidate,
          selectedCandidateCode: selectedCandidate.stockCode,
          restrictedActionsDisabled: true,
        },
        { decisionReason },
      );
      render(<StockAnalysisResearchDesk {...props} />);

      const boundarySection = screen.getByText("复核边界（4 条）").closest("section");
      expect(boundarySection).not.toBeNull();
      const boundaryView = within(boundarySection as HTMLElement);

      expect(boundaryView.getByText("研究数据可查看。盘前数据尚未绑定发布版本，暂不提供风险与执行结论。")).toHaveAttribute("title", decisionReason);
      expect(boundaryView.getByText("候选仅供研究参考，不代表交易建议。")).toHaveAttribute("title", queueBoundary);
      expect(boundaryView.getByText("题材归属采用当前成分，仅供观察；缺少历史时点记录，不能用于历史回测。")).toHaveAttribute("title", overlayBoundary);
      expect(boundaryView.getByText(unknownBoundary)).toHaveAttribute("title", unknownBoundary);
      expect(boundaryView.queryByText("通过")).not.toBeInTheDocument();
      expect(boundaryView.queryByText("阻断")).not.toBeInTheDocument();
      expect(boundarySection?.querySelector("em")).toBeNull();
      const deepResearchButton = screen.getByRole("button", { name: "开始深度研究" });
      expect(deepResearchButton).toBeEnabled();
      fireEvent.click(deepResearchButton);
      expect(props.onOpenDeepResearch).toHaveBeenCalledOnce();
      expect(screen.getByRole("button", { name: "查看全部" })).toBeEnabled();
      expect(screen.getByRole("button", { name: "回溯该信号历史表现" })).toBeEnabled();
      expect(screen.getByRole("button", { name: "加入自选" })).toBeEnabled();
    },
  );

  it("closes read-only research when the review qualification is unavailable", () => {
    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          interactionsDisabled: true,
          restrictedActionsDisabled: true,
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "开始深度研究" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "查看全部" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "回溯该信号历史表现" })).toBeDisabled();
  });

  it("reads factor cell values from candidate raw fields, not metric cards", () => {
    const selectedCandidate = buildCandidate({
      rawFields: [
        { key: "fusion_score", label: "融合得分", value: "88" },
        { key: "attention_score", label: "关注度", value: "65" },
        { key: "breakout_extension_norm", label: "突破延伸(归一)", value: "0.575" },
        { key: "daily_amount", label: "成交额(日)", value: "6.40亿" },
        { key: "amplitude", label: "振幅", value: "3.1%" },
      ],
    });

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: [selectedCandidate],
          queueVisibleCount: 1,
          queueTotalCount: 1,
          selectedCandidate,
          selectedCandidateCode: selectedCandidate.stockCode,
        })}
      />,
    );

    const factorTexts = Array.from(
      screen.getByLabelText("因子指标").querySelectorAll("[data-accent]"),
    ).map((element) => element.textContent);
    expect(factorTexts).toEqual([
      // 综合分与档案头、标的池列同为 3 位小数；其余非百分比因子格原样透传原始文本。
      "综合分88.000",
      "估值—",
      "质量—",
      "动量—",
      "情绪65",
      "拥挤度0.575",
      "流动性6.40亿",
      "波动率3.10%",
    ]);
  });

  it("renders ratio-valued quality fields as percentages regardless of the raw string form", () => {
    // Strategy-enriched rows carry "0.1430" (raw ratio string + numeric) while
    // workbench-only rows carry "14.30%"; both must render as 14.30%.
    const selectedCandidate = buildCandidate({
      rawFields: [
        { key: "roe", label: "ROE", value: "0.1430", numeric: 0.143 },
        { key: "gross_margin", label: "毛利率", value: "0.3200", numeric: 0.32 },
        { key: "pe", label: "PE", value: "12.4000", numeric: 12.4 },
      ],
    });

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: [selectedCandidate],
          queueVisibleCount: 1,
          queueTotalCount: 1,
          selectedCandidate,
          selectedCandidateCode: selectedCandidate.stockCode,
        })}
      />,
    );

    const factorBand = screen.getByLabelText("因子指标");
    expect(factorBand).toHaveTextContent("质量14.30%");
    expect(factorBand).not.toHaveTextContent("0.1430");
    expect(factorBand).not.toHaveTextContent("0.14%");
    const dossier = screen.getByTestId("stock-analysis-research-dossier");
    expect(dossier).toHaveTextContent("ROE14.30%");
    expect(dossier).toHaveTextContent("毛利率32.00%");
  });

  it("shows cross-section percentiles only when the pool has enough comparable samples", () => {
    const pool = Array.from({ length: 6 }, (_, index) =>
      buildCandidate({
        stockCode: `00000${index + 1}.SZ`,
        stockName: `样本${index + 1}`,
        rawFields: [{ key: "fusion_score", label: "融合得分", value: String(0.5 + index * 0.05) }],
      }),
    );
    const selectedCandidate = pool[5];

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: pool,
          queueVisibleCount: pool.length,
          queueTotalCount: pool.length,
          selectedCandidate,
          selectedCandidateCode: selectedCandidate.stockCode,
        })}
      />,
    );

    const factorBand = screen.getByLabelText("因子指标");
    expect(factorBand).toHaveTextContent("综合分0.750");
    expect(factorBand).toHaveTextContent("P100");
    // 只有一列有数值，其余因子格没有分位徽章。
    expect(factorBand.textContent?.match(/P\d+/g)).toHaveLength(1);
  });

  it("keeps point-based daily change out of ratio-based momentum and crowding", () => {
    const selectedCandidate = buildCandidate({
      rawFields: [
        { key: "fusion_score", label: "融合得分", value: "88" },
        { key: "pctchange", label: "个股涨幅", value: "20" },
        { key: "turn", label: "换手率", value: "45" },
      ],
    });

    render(
      <StockAnalysisResearchDesk
        {...buildProps({
          poolCandidates: [selectedCandidate],
          queueVisibleCount: 1,
          queueTotalCount: 1,
          selectedCandidate,
          selectedCandidateCode: selectedCandidate.stockCode,
        })}
      />,
    );

    const factorBand = screen.getByLabelText("因子指标");
    expect(factorBand.querySelectorAll("[data-accent]")).toHaveLength(8);
    expect(factorBand).toHaveTextContent("动量—");
    expect(factorBand).toHaveTextContent("拥挤度—");
    expect(factorBand).not.toHaveTextContent("+2000%");
    expect(screen.getAllByText("涨跌 +20.00%").length).toBeGreaterThan(0);
  });

  it("keeps the candidate row out of nested button markup", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { container } = render(<StockAnalysisResearchDesk {...buildProps()} />);
    const firstCandidateButton = screen.getByRole("button", {
      name: /000001\.SZ.*示例科技/,
    });
    const firstCandidateRow = firstCandidateButton.parentElement;

    expect(firstCandidateRow?.tagName).toBe("DIV");
    expect(firstCandidateButton.tagName).toBe("BUTTON");
    expect(firstCandidateButton.querySelector("button")).toBeNull();
    expect(firstCandidateRow?.querySelectorAll(":scope > button")).toHaveLength(1);
    expect(container.querySelector("button button")).toBeNull();
    expect(
      consoleError.mock.calls.some((call) =>
        call.some(
          (argument) =>
            typeof argument === "string" &&
            (argument.includes("cannot be a descendant") || argument.includes("validateDOMNesting")),
        ),
      ),
    ).toBe(false);
  });
});
