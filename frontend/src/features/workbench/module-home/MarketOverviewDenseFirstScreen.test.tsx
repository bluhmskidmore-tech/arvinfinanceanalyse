import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../../../api/client";
import { buildMockMarketOverviewSnapshot } from "../../../mocks/marketOverviewSnapshot";
import { MarketOverviewDenseFirstScreen } from "./MarketOverviewDenseFirstScreen";
import type { ModuleHomeSourceQueries, ModuleHomeView } from "./moduleHomeModel";
import {
  MARKET_OVERVIEW_SNAPSHOT_QUERY_VERSION,
  useMarketHomeQueries,
} from "./useMarketHomeQueries";

vi.mock("../../../components/charts/ChartCard", () => ({
  ChartCard: ({ title, ariaLabel }: { title?: string; ariaLabel?: string }) => <div data-testid="dense-chart" aria-label={ariaLabel}>{title}</div>,
}));

vi.mock("./MarketPortfolioScenarioPanel", () => ({
  MarketPortfolioScenarioPanel: ({ curveObservationDate }: { curveObservationDate: string | null }) => <div data-testid="scenario-curve-date">{curveObservationDate}</div>,
}));
vi.mock("./MarketRiskObservation", () => ({
  MarketRiskObservation: () => <section id="market-risk-observation" data-testid="risk-home-section">风险观察</section>,
}));

const view = {
  stateLabel: "已接入",
  marketDeskIntel: { curveShapeLabel: "牛平" },
} as ModuleHomeView;

function renderSnapshot(
  update?: (envelope: ReturnType<typeof buildMockMarketOverviewSnapshot>) => void,
  queryState?: { isError?: boolean },
) {
  const envelope = buildMockMarketOverviewSnapshot();
  update?.(envelope);
  const queries = {
    marketSnapshot: {
      data: envelope,
      isLoading: false,
      isError: queryState?.isError ?? false,
    },
  } as ModuleHomeSourceQueries;

  render(
    <MemoryRouter>
      <MarketOverviewDenseFirstScreen
        view={view}
        queries={queries}
        searchValue=""
      />
    </MemoryRouter>,
  );
  return envelope;
}

describe("MarketOverviewDenseFirstScreen snapshot contract", () => {
  it("keeps receipt paths in evidence while showing the blocked business consequence and recovery route", () => {
    const reason = "必要输入尚未通过 receipt.result.steps.market_rates 的刷新回执核验。";
    renderSnapshot(envelope => {
      envelope.result.gate!.level = "blocked";
      envelope.result.gate!.human_reason = reason;
      for (const observation of [envelope.result.funding_observation!, envelope.result.rates_observation!]) {
        observation.judgment_allowed = false;
        observation.reason = reason;
        observation.summary = reason;
        observation.verification_route = "/macro-toolkit";
      }
    });

    const reading = screen.getByTestId("market-home-reading");
    const gate = within(reading).getByTestId("module-home-market-dense-observation-gate");
    expect(gate).toBeVisible();
    expect(gate).toHaveTextContent("必要输入尚未通过 相关数据 的更新结果核验。");
    expect(gate).not.toHaveTextContent("receipt.result.steps");
    expect(within(reading).getByText("资金观察待核验，暂不形成判断。")).toBeVisible();
    expect(within(reading).getAllByRole("link", { name: "恢复与核验" })).toHaveLength(2);
    const evidence = within(reading).getByText(reason);
    expect(evidence).not.toBeVisible();
    fireEvent.click(within(reading).getByTestId("module-home-market-dense-observation-summary"));
    expect(evidence).not.toBeVisible();
    fireEvent.click(within(reading).getByText("技术诊断"));
    expect(evidence).toBeVisible();
  });

  it("keeps shared restrictions concise without removing their evidence or creating impact conclusions", () => {
    const reason = "必要输入及相应刷新回执尚未全部核验，原值仅供核验。";
    renderSnapshot(envelope => {
      for (const observation of [envelope.result.funding_observation!, envelope.result.rates_observation!]) {
        observation.judgment_allowed = false;
        observation.reason = reason;
        observation.summary = reason;
        observation.interpretation = "不能发布的方向判断";
      }
    });
    const reading = screen.getByTestId("market-home-reading");
    expect(within(reading).getByText("资金观察待核验，暂不形成判断。")).toBeVisible();
    expect(within(reading).getByText("国债利率观察待核验，暂不形成判断。")).toBeVisible();
    expect(within(reading).getAllByText("必要输入及相应更新结果尚未全部核验，原值仅供核验。").find(element => element.closest("details") === null)).toBeVisible();
    expect(within(reading).getByText(reason)).not.toBeVisible();
    const impact = screen.getByLabelText("影响核对");
    expect(impact).not.toHaveTextContent(reason);
    expect(impact).not.toHaveTextContent("不能发布的方向判断");
    expect(impact).toHaveTextContent("暂不解释估值影响");
    expect(impact).toHaveTextContent("暂不解释融资影响");
  });

  it("preserves different observation reasons rather than treating them as the same restriction", () => {
    renderSnapshot(envelope => {
      envelope.result.funding_observation!.judgment_allowed = false;
      envelope.result.funding_observation!.reason = "资金序列缺少比较日";
      envelope.result.rates_observation!.judgment_allowed = false;
      envelope.result.rates_observation!.reason = "曲线缺少必需期限";
    });
    const reading = screen.getByTestId("market-home-reading");
    expect(within(reading).getByText("资金序列缺少比较日")).toBeVisible();
    expect(within(reading).getByText("曲线缺少必需期限")).toBeVisible();
  });

  it("keeps dates and usage limits in mixed technical reasons and retains the original diagnostic", () => {
    const reason = "数据截至 2026-09-01，receipt.result.steps.market_rates 尚未核验；仅供分析，不可用于业务决策。";
    renderSnapshot(envelope => {
      envelope.result.gate!.level = "blocked";
      envelope.result.gate!.human_reason = reason;
    });
    const reading = screen.getByTestId("market-home-reading");
    const gate = within(reading).getByTestId("module-home-market-dense-observation-gate");
    expect(gate).toHaveTextContent("2026-09-01");
    expect(gate).toHaveTextContent("仅供分析，不可用于业务决策");
    expect(gate).not.toHaveTextContent("receipt.result");
    fireEvent.click(within(reading).getByTestId("module-home-market-dense-observation-summary"));
    fireEvent.click(within(reading).getByText("技术诊断"));
    expect(within(reading).getByText(reason)).toBeVisible();
  });

  it.each([
    ["dr007", "down", -0.02, "muted"],
    ["gov_10y", "up", 0.01, "warn"],
    ["usd_cny_mid", "up", 0.01, "up"],
    ["usd_cny_mid", "down", -0.01, "down"],
  ] as const)("keeps %s %s movement in its established semantic color", (key, toneHint, change, expectedTone) => {
    let metricLabel = "";
    renderSnapshot(envelope => {
      const metric = envelope.result.tape!.slots.find(slot => slot.key === key)!;
      metricLabel = metric.label;
      Object.assign(metric, { change, tone_hint: toneHint, status: "ok" });
    });
    const card = within(screen.getByLabelText("市场行情带")).getByText(metricLabel).closest("article")!;
    expect(card).toHaveAttribute("data-tone", expectedTone);
    expect(card.querySelector("em")).toHaveTextContent(change > 0 ? "+0.01" : String(change));
  });

  it("retains precise FX amount, long change unit and complete observation date", () => {
    renderSnapshot(envelope => {
      Object.assign(envelope.result.tape!.slots.find(slot => slot.key === "usd_cny_mid")!, {
        value: 6.7804, unit: "CNY/USD", change: 0.0009, change_unit: "CNY/USD", trade_date: "2026-09-08", status: "ok",
      });
    });
    const card = within(screen.getByLabelText("市场行情带")).getByText("6.7804").closest("article")!;
    expect(within(card).getByText("6.7804").tagName).toBe("SPAN");
    expect(card).toHaveTextContent("+0.0009 CNY/USD");
    expect(card.querySelector("time")).toHaveTextContent("2026-09-08");
  });

  it("shows latest event summaries and opens the complete selected text without inferring importance", async () => {
    const fullText = "长新闻正文用于核验全文访问。".repeat(30) + "这是正文末尾。";
    renderSnapshot(envelope => {
      envelope.result.news!.latest[0]!.summary = fullText;
    });
    const events = screen.getByTestId("market-home-events-summary");
    expect(within(events).getByRole("heading", { name: "最新事件" })).toBeVisible();
    expect(within(events).queryByRole("heading", { name: fullText })).not.toBeInTheDocument();
    expect(within(events).getByText(fullText).tagName).toBe("P");
    fireEvent.click(within(events).getByRole("button", { name: "查看第1条事件全文" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(fullText)).toBeVisible();
    fireEvent.click(within(dialog).getByRole("button", { name: "返回事件概览" }));
    expect(within(dialog).getByRole("heading", { name: "事件流入密度" })).toBeVisible();
  });

  it("keeps the reading, risk, four macro slots and events visible without opening details", () => {
    renderSnapshot((envelope) => { envelope.result.pulse!.items = envelope.result.pulse!.items.slice(0, 1); });
    expect(screen.getByTestId("market-home-reading")).toBeVisible();
    expect(screen.getByTestId("risk-home-section")).toBeVisible();
    const macro = screen.getByTestId("market-home-macro-summary");
    expect(macro).toBeVisible();
    expect(macro.querySelectorAll('section')).toHaveLength(4);
    expect(within(macro).getByText('社融存量同比')).toBeVisible();
    expect(screen.getByTestId("market-home-events-summary")).toBeVisible();
    expect(screen.getByTestId("scenario-curve-date")).toBeVisible();
    expect(screen.getByTestId("risk-home-section").compareDocumentPosition(macro) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("keeps the complete blocked reason visible once while operational details remain collapsible", () => {
    const reason = "最近一次刷新未完成，方向性结论已关闭。";
    renderSnapshot((envelope) => {
      envelope.result.gate!.level = "blocked";
      envelope.result.gate!.human_reason = reason;
      envelope.result.gate!.conclusion.summary = reason;
    });
    const summary = screen.getByTestId("module-home-market-dense-observation-summary");
    expect(summary).toBeVisible();
    expect(within(summary.closest("details")!).getAllByText(reason)).toHaveLength(1);
    expect(summary.closest("details")).not.toHaveAttribute("open");
    expect(screen.getByTestId("module-home-market-dense-observation-context")).not.toBeVisible();
    fireEvent.click(summary);
    expect(screen.getByTestId("module-home-market-dense-observation-context")).toBeVisible();
    expect(screen.getByTestId("module-home-market-dense-observation-title")).toHaveTextContent("市场观察");
    const verification = screen.getByTestId("module-home-market-dense-verification");
    expect(verification).not.toHaveAttribute("open");
    expect(verification).toContainElement(document.getElementById("market-overview-actions"));
    const background = screen.getByTestId("module-home-market-background-details");
    expect(background).not.toBeVisible();
    fireEvent.click(screen.getByText("核验详情"));
    expect(screen.getByRole("table", { name: "宏观指标变动" })).toBeVisible();
  });

  it("does not reuse a v4 market snapshot cache entry for the v5 contract", async () => {
    const legacyEnvelope = buildMockMarketOverviewSnapshot();
    legacyEnvelope.result.tape!.slots.forEach((slot) => {
      slot.status = "unresolved";
      slot.reason = "no configured alias landed on the latest valid date";
      slot.value = null;
    });
    const currentEnvelope = buildMockMarketOverviewSnapshot();
    const base = createApiClient({ mode: "mock" });
    const getMarketOverviewSnapshot = vi.fn(async () => currentEnvelope);
    const client = { ...base, getMarketOverviewSnapshot };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(
      ["module-home", "market-snapshot", "v4", client.mode],
      legacyEnvelope,
    );
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </ApiClientProvider>
    );

    const { result } = renderHook(
      () => useMarketHomeQueries({ chartsVisible: false, backendActiveKey: "choice" }),
      { wrapper },
    );

    await waitFor(() => expect(getMarketOverviewSnapshot).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.marketSnapshot?.data).toBe(currentEnvelope));
    expect(
      queryClient.getQueryData([
        "module-home",
        "market-snapshot",
        MARKET_OVERVIEW_SNAPSHOT_QUERY_VERSION,
        client.mode,
      ]),
    ).toBe(currentEnvelope);
  });

  it.each(["ok", "review", "blocked"] as const)("renders %s gate without reviving legacy directional labels", (level) => {
    const envelope = renderSnapshot((envelope) => {
      envelope.result.gate!.level = level;
    });

    expect(
      screen.getByTestId("module-home-market-dense-observation-title"),
    ).toHaveTextContent("市场观察");
    expect(
      screen.getByTestId("module-home-market-dense-observation-action"),
    ).toHaveTextContent(envelope.result.gate!.recovery_action);
    expect(screen.getByTestId("module-home-market-dense-observation-summary")).toBeVisible();
  });

  it("renders an unresolved tape slot as an explicit unbound state", () => {
    renderSnapshot((envelope) => {
      const slot = envelope.result.tape!.slots[0]!;
      slot.status = "unresolved";
      slot.reason = "no configured alias landed on the latest valid date";
      slot.value = null;
    });

    expect(screen.getByText("未绑定")).toBeInTheDocument();
    expect(screen.getByText("未绑定").closest("article")).toHaveAttribute(
      "title",
      expect.stringContaining("no configured alias"),
    );
  });

  it("renders four primary tape slots on each slot's own trade date", () => {
    const slotDates = [
      "2026-09-03",
      "2026-09-03",
      "2026-09-01",
      "2026-09-03",
      "2026-09-03",
      "2026-09-01",
      "2026-09-04",
      "2026-09-03",
    ];
    const envelope = renderSnapshot((snapshot) => {
      snapshot.result.tape!.slots.forEach((slot, index) => {
        slot.status = "ok";
        slot.reason = null;
        slot.trade_date = slotDates[index]!;
      });
    });
    const tape = screen.getByLabelText("市场行情带");
    const cards = Array.from(tape.querySelectorAll("article"));

    expect(cards).toHaveLength(4);
    expect(within(tape).queryByText("未绑定")).not.toBeInTheDocument();
    envelope.result.tape!.slots.forEach((slot, index) => {
      const card = cards.find((item) => item.textContent?.includes(slot.label));
      if (card) expect(card).toHaveTextContent(slotDates[index]!);
    });
  });

  it("discloses fallback dates and explicit formal-use restrictions on the tape", () => {
    renderSnapshot((envelope) => {
      const slot = envelope.result.tape!.slots[0]!;
      slot.fallback_mode = "latest_snapshot";
      slot.fallback_date = "2026-08-28";
      slot.formal_use_allowed = false;
    });

    const tape = screen.getByLabelText("市场行情带");
    const fallback = within(tape).getByText(/回退至 2026-08-28/);
    expect(fallback).toBeVisible();
    expect(fallback).toHaveTextContent("正式使用受限");
  });

  it("does not claim formal use is restricted when the slot has no permission metadata", () => {
    renderSnapshot((envelope) => {
      envelope.result.tape!.slots.forEach((slot) => {
        slot.fallback_mode = null;
        slot.formal_use_allowed = null;
      });
    });

    expect(within(screen.getByLabelText("市场行情带")).queryByText("正式使用受限")).not.toBeInTheDocument();
  });

  it("keeps the gate reason visible while collapsing technical verification details", () => {
    const envelope = renderSnapshot();

    expect(screen.getByTestId("module-home-market-dense-observation-gate")).toBeVisible();
    expect(screen.getByTestId("module-home-market-dense-observation-gate")).toHaveTextContent(envelope.result.gate!.human_reason);
    expect(screen.getByTestId("module-home-market-dense-verification")).not.toHaveAttribute("open");
    expect(screen.getByTestId("module-home-market-dense-observation-quality")).not.toBeVisible();
  });

  it("shows missing directional coverage and expands bounded issue impacts with valid routes", () => {
    renderSnapshot((envelope) => {
      envelope.result.gate!.conclusion.stance = "暂不判断";
      envelope.result.gate!.conclusion.basis = {
        source: "core_signal_cards",
        signal_cards: [{ key: "liquidity", tone: "neutral" }],
        directional_coverage: {
          expected_count: 3,
          valid_count: 1,
          missing_keys: ["credit", "risk_appetite"],
          status: "insufficient",
        },
      };
      envelope.result.gate!.issues = [
        {
          key: "directional_coverage",
          label: "方向信号不完整",
          reason: "信用、风险偏好方向信号缺失或无效。",
          impact: "暂不形成完整的宏观方向判断；已取得的信号仍保留供核验。",
          route: "/macro-toolkit",
        },
      ];
      envelope.result.actions!.items.unshift({
        priority: "P1",
        key: "gate_review_directional_coverage",
        label: "方向信号不完整",
        route: "/macro-toolkit",
        basis: "analytical",
        evidence: {
          reason: "信用、风险偏好方向信号缺失或无效。",
          impact: "暂不形成完整的宏观方向判断；已取得的信号仍保留供核验。",
        },
      });
    });

    expect(screen.getByTestId("module-home-market-dense-observation-title")).toHaveTextContent("市场观察");
    expect(screen.queryByTestId("module-home-market-dense-directional-coverage")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("核验详情"));
    const issue = screen.getByTestId("module-home-market-dense-gate-issue-directional_coverage");
    expect(issue).toHaveTextContent("信用、风险偏好方向信号缺失或无效");
    expect(issue).toHaveTextContent("影响：暂不形成完整的宏观方向判断");
    expect(within(issue).getByRole("link", { name: "进入核验" })).toHaveAttribute(
      "href",
      "/macro-toolkit",
    );
    expect(document.getElementById("market-overview-actions")).not.toHaveTextContent("reason=");
  });

  it("keeps known action evidence as bounded business copy", () => {
    renderSnapshot((envelope) => {
      envelope.result.actions!.items = [
        {
          priority: "P1",
          key: "rate_move_dr007",
          label: "核验 DR007 的大幅变动",
          route: "/market-data",
          basis: "analytical",
          evidence: { change_bp: 12.4, threshold_bp: 10 },
        },
        {
          priority: "P2",
          key: "crisis_regime_review",
          label: "复核 Crisis Score 高风险状态",
          route: "/macro-toolkit",
          basis: "analytical",
          evidence: { eligible: true, triggered: true, score: 2.31, threshold: 2 },
        },
        {
          priority: "P2",
          key: "surface_stale_strategy",
          label: "核验策略数据时效",
          route: "/macro-toolkit",
          basis: "analytical",
          evidence: { surface: "strategy", age_days: 12 },
        },
      ];
    });

    const queue = document.getElementById("market-overview-actions")!;
    expect(queue).toHaveTextContent("变动 +12.4bp，复核阈值 ±10.0bp");
    expect(queue).toHaveTextContent("当前风险门已触发，分数 2.31，阈值 2.00");
    expect(queue).toHaveTextContent("距页面计算日 12 天");
    expect(queue).not.toHaveTextContent("change_bp=");
    expect(queue).not.toHaveTextContent("eligible=");
    expect(queue).not.toHaveTextContent("surface=");
  });

  it("labels an old strategy snapshot without treating monthly pulse dates as daily staleness", () => {
    renderSnapshot((envelope) => {
      const strategyDate = envelope.result.dates!.surfaces.find(
        (surface) => surface.key === "strategy",
      )!;
      strategyDate.latest = "2026-08-24";
      strategyDate.age_days = 12;
      envelope.result.pulse!.items.forEach((item) => {
        item.latest_date = "2026-07-01";
      });
    });

    expect(screen.getByTestId("module-home-market-dense-stale-dates")).toHaveTextContent(
      "策略观察截至 2026-08-24（距页面计算日 12 天）",
    );
    expect(screen.getByTestId("module-home-market-dense-stale-dates")).not.toHaveTextContent(
      "宏观指标",
    );
    expect(within(screen.getByTestId("module-home-market-dense-chart-macro-pulse")).getAllByText("2026-07-01")).toHaveLength(4);
  });

  it("replaces issue restrictions with the recovered conclusion when the snapshot changes", () => {
    const degradedEnvelope = buildMockMarketOverviewSnapshot();
    const makeQueries = (envelope: typeof degradedEnvelope) => ({
      marketSnapshot: { data: envelope, isLoading: false, isError: false },
    }) as ModuleHomeSourceQueries;
    const rendered = render(
      <MemoryRouter>
        <MarketOverviewDenseFirstScreen
          view={view}
          queries={makeQueries(degradedEnvelope)}
          searchValue=""
        />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("module-home-market-dense-directional-coverage")).not.toBeInTheDocument();
    const recoveredEnvelope = buildMockMarketOverviewSnapshot();
    recoveredEnvelope.result.gate!.level = "ok";
    recoveredEnvelope.result.gate!.human_reason = "刷新回执与核心组件均通过当前读取校验。";
    recoveredEnvelope.result.gate!.issues = [];
    recoveredEnvelope.result.gate!.conclusion.stance = "三项方向信号已齐备";
    recoveredEnvelope.result.gate!.conclusion.basis = {
      source: "core_signal_cards",
      signal_cards: [
        { key: "liquidity", tone: "neutral" },
        { key: "risk_appetite", tone: "positive" },
        { key: "credit", tone: "neutral" },
      ],
      directional_coverage: {
        expected_count: 3,
        valid_count: 3,
        missing_keys: [],
        status: "complete",
      },
    };
    rendered.rerender(
      <MemoryRouter>
        <MarketOverviewDenseFirstScreen
          view={view}
          queries={makeQueries(recoveredEnvelope)}
          searchValue=""
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("module-home-market-dense-observation-title")).toHaveTextContent(
      "市场观察",
    );
    expect(screen.queryByTestId("module-home-market-dense-directional-coverage")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("受限结论与复核入口")).not.toBeInTheDocument();
  });

  it("explicitly warns when a failed snapshot refresh leaves previous data on screen", () => {
    renderSnapshot(undefined, { isError: true });

    const notice = screen.getByText("最新数据读取失败，当前保留上次数据，请刷新后复核。");
    expect(notice).toHaveAttribute("role", "status");
    expect(notice).toBeVisible();
    expect(screen.getByTestId("module-home-market-dense-observation-summary").closest("details")).not.toHaveAttribute("open");
    expect(within(screen.getByLabelText("市场行情带")).getAllByRole("article")).toHaveLength(4);
  });

  it("does not turn unavailable news into a green zero-review result", () => {
    renderSnapshot((envelope) => {
      envelope.result.news!.status = "unavailable";
      envelope.result.news!.reason = "新闻来源暂不可用";
      envelope.result.news!.compare.review_needed = 0;
    });

    const newsFocus = screen.getByText("复核状态不可用").closest("article")!;
    expect(newsFocus).toHaveAttribute("data-tone", "watch");
    expect(newsFocus).toHaveTextContent("新闻来源暂不可用");
    expect(newsFocus).not.toHaveTextContent("0 项待复核");
  });

  it("renders backend value and change units separately without inferring missing units", () => {
    renderSnapshot((envelope) => {
      envelope.result.pulse!.items = [
        { ...envelope.result.pulse!.items[0]!, key: "cpi", label: "CPI同比", previous_value: 0.2, latest_value: 0.3, change: 0.1, unit: "%", change_unit: "百分点" },
        { ...envelope.result.pulse!.items[0]!, key: "pending", label: "待核指标", previous_value: 10, latest_value: 12, change: 2, unit: null, change_unit: null },
      ];
    });

    fireEvent.click(screen.getByText("核验详情"));
    const pulse = screen.getByTestId("module-home-market-dense-chart-macro-pulse");
    expect(within(pulse).getByText("0.3%")).toBeVisible();
    expect(within(pulse).getByText("0.1 百分点")).toBeVisible();
    expect(within(pulse).getAllByText("单位待确认")).toHaveLength(2);
    expect(within(pulse).getByLabelText(/CPI同比：前值 0.2%，最新值 0.3%，变化 0.1 百分点/)).toBeInTheDocument();
  });

  it("keeps each indicator observation date visible and distinct from the analysis snapshot date", () => {
    renderSnapshot((envelope) => {
      const macroDate = envelope.result.dates!.surfaces.find((surface) => surface.key === "macro_analysis")!;
      macroDate.latest = "2026-09-04";
      envelope.result.pulse!.items = [
        { ...envelope.result.pulse!.items[0]!, latest_date: "2026-07-01" },
        { ...envelope.result.pulse!.items[1]!, latest_date: null },
      ];
    });

    fireEvent.click(screen.getByText("核验详情"));
    const pulse = screen.getByTestId("module-home-market-dense-chart-macro-pulse");
    expect(within(pulse).getByText("2026-07-01")).toBeVisible();
    expect(within(pulse).getByLabelText("观测日期 —")).toBeVisible();
    expect(within(pulse).getByText("分析日期 2026-09-04")).toBeVisible();
    expect(within(pulse).getByText("分析日期不代表指标所属期")).toBeVisible();
  });

  it("does not reuse the legacy voting summary when new observations are missing", () => {
    renderSnapshot((envelope) => {
      delete envelope.result.funding_observation;
      delete envelope.result.rates_observation;
    });
    const summary = "资金观察尚未返回，暂不形成判断。 国债曲线观察尚未返回，暂不形成判断。";
    const context = screen.getByTestId("module-home-market-dense-observation-context");
    const focus = document.getElementById("market-overview-focus")!;

    expect(context).not.toBeVisible();
    fireEvent.click(screen.getByTestId("module-home-market-dense-observation-summary"));
    expect(context).toBeVisible();
    expect(context).toHaveTextContent(summary);
    expect(within(focus).getByText(summary)).toBeInTheDocument();
  });

  it("uses separately verified observations under a blocked global gate and passes only the curve date to scenarios", () => {
    const envelope = renderSnapshot((next) => {
      next.result.gate!.level = "blocked";
      next.result.funding_observation!.observation_date = "2026-09-07";
      next.result.funding_observation!.judgment_allowed = false;
      next.result.funding_observation!.summary = "资金来源待核验，暂不判断。";
      next.result.rates_observation!.observation_date = "2026-09-04";
      next.result.rates_observation!.judgment_allowed = true;
      next.result.rates_observation!.summary = "国债两期证据有效，10年收益率上行1 bp。";
    });
    const context = screen.getByTestId("module-home-market-dense-observation-context");
    fireEvent.click(screen.getByTestId("module-home-market-dense-observation-summary"));
    expect(context).toBeVisible();
    expect(context).toHaveTextContent(envelope.result.funding_observation!.summary);
    expect(context).toHaveTextContent(envelope.result.rates_observation!.summary);
    expect(screen.getByTestId("module-home-market-dense-observation-date")).toHaveTextContent("资金 2026-09-07；曲线 2026-09-04");
    expect(screen.getByTestId("scenario-curve-date")).toHaveTextContent("2026-09-04");
    expect(document.getElementById("market-overview-signals")).toBeNull();
  });

  it("discloses excluded date-only rows and the snapshot timezone", () => {
    renderSnapshot();

    expect(screen.getByText(/已排除仅日期记录 1 条/)).toBeInTheDocument();
    expect(screen.getByText(/Asia\/Shanghai 每 2 小时分桶/)).toBeInTheDocument();
  });

  it("shows both ends of the backend tape date span", () => {
    renderSnapshot();
    expect(document.getElementById("market-overview-focus")).toHaveTextContent("2026-09-01–2026-09-02");
  });

  it("builds first-screen charts from the snapshot without child queries", () => {
    renderSnapshot();

    expect(screen.getAllByTestId("dense-chart").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "关键利率" }));
    const trend = screen.getByTestId("module-home-market-dense-chart-key-rate-trend");
    expect(trend).toBeVisible();
    expect(document.getElementById("market-overview-judgment")).toContainElement(trend);
    expect(trend.compareDocumentPosition(screen.getByTestId("scenario-curve-date")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const grid = document.getElementById("market-overview-judgment")!;
    const crossAsset = screen.getByTestId("module-home-market-dense-chart-cross-asset-move");
    expect(grid).toContainElement(trend);
    expect(grid).toContainElement(crossAsset);
    expect(document.getElementById("market-overview-judgment")).toContainElement(crossAsset);
    expect(screen.getByLabelText("市场行情带").compareDocumentPosition(crossAsset) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(document.getElementById("market-overview-evidence")).toContainElement(screen.getByTestId("scenario-curve-date"));
    expect(screen.getByTestId("module-home-market-dense-chart-news-density")).not.toBeVisible();
    const crisisTrend = screen.getByTestId("module-home-market-dense-crisis-trend");
    expect(crisisTrend).toHaveTextContent("近20期回落0.04");
    expect(crisisTrend).toHaveTextContent("近60期上升0.18");
    expect(crisisTrend).toHaveTextContent("高风险门未触发 · 阈值 2.00");
    expect(crisisTrend).toHaveTextContent("截至 2026-09-02");
    expect(screen.queryByText(/复核 Crisis Score/)).not.toBeInTheDocument();
  });

  it("shows backend Crisis coverage and input evidence when the risk gate is ineligible", () => {
    renderSnapshot((envelope) => {
      const crisis = envelope.result.crisis!;
      crisis.status = "degraded";
      crisis.data_status = "degraded";
      crisis.available_component_count = 4;
      crisis.component_count = 5;
      crisis.warnings = ["CREDIT_SPREAD_UNAVAILABLE"];
      crisis.input_evidence.inputs[0]!.latest_date = "2026-08-25";
      crisis.input_evidence.inputs[0]!.stale = true;
      crisis.input_evidence.inputs[0]!.stale_days = 9;
      crisis.input_evidence.stale_inputs = ["aa_5y"];
      envelope.result.crisis!.risk_gate = {
        eligible: false,
        triggered: false,
        threshold: 2,
        reason_code: "crisis_score_data_not_complete",
      };
      envelope.result.actions!.items.push({
        priority: "P2",
        key: "crisis_regime_review",
        label: "复核 Crisis Score 数据完整性",
        route: "/macro-toolkit",
        basis: "analytical",
        evidence: {
          eligible: false,
          triggered: false,
          reason_code: "crisis_score_data_not_complete",
        },
      });
    });

    const crisisTrend = screen.getByTestId("module-home-market-dense-crisis-trend");
    expect(crisisTrend).toHaveTextContent("风险门不可用 · 数据不完整");
    expect(crisisTrend).toHaveTextContent("组件 4/5");
    expect(crisisTrend).toHaveTextContent("信用利差不可用");
    expect(crisisTrend).toHaveTextContent("AA 5Y 最新日期 2026-08-25");
    expect(screen.getByText("复核 Crisis Score 数据完整性")).toBeInTheDocument();
  });

  it("withholds the current Crisis regime when only historical trends are available", () => {
    renderSnapshot((envelope) => {
      const crisis = envelope.result.crisis!;
      crisis.current_available = false;
      crisis.history_only = true;
      crisis.score = null;
      crisis.regime = "宽松";
      crisis.report_date = "2026-09-04";
      crisis.dependency_gate = { status: "blocked", blocked_by: ["refresh"], reason_code: "required_refresh_step_not_ready" };
      crisis.score_trends.forEach((trend) => { trend.end_date = "2026-09-02"; });
    });

    expect(screen.getByTestId("module-home-market-dense-crisis-current")).toHaveTextContent("当前不可用");
    expect(screen.getByTestId("module-home-market-dense-crisis-current")).not.toHaveTextContent("宽松");
    fireEvent.click(screen.getByText("核验详情"));
    expect(screen.getByText("历史截至 2026-09-02")).toBeVisible();
    const trend = screen.getByTestId("module-home-market-dense-crisis-trend");
    expect(trend).toHaveTextContent("近20期回落0.04");
    expect(trend).toHaveTextContent("近60期上升0.18");
    expect(trend).toHaveTextContent("历史截至 2026-09-02");
    expect(trend).not.toHaveTextContent("2026-09-04");
  });

  it("shows the current Crisis report date independently from its history end date", () => {
    renderSnapshot((envelope) => {
      const crisis = envelope.result.crisis!;
      crisis.current_available = true;
      crisis.report_date = "2026-09-04";
      crisis.score_trends.forEach((trend) => { trend.end_date = "2026-09-02"; });
    });

    fireEvent.click(screen.getByText("核验详情"));
    expect(screen.getByText("当前截至 2026-09-04")).toBeVisible();
    expect(screen.getByText("趋势截至 2026-09-02")).toBeVisible();
  });

  it("shows the triggered gate and only renders the action returned by the backend", () => {
    renderSnapshot((envelope) => {
      envelope.result.crisis!.risk_gate = {
        eligible: true,
        triggered: true,
        threshold: 2,
        reason_code: "crisis_score_at_or_above_threshold",
      };
      envelope.result.actions!.items.push({
        priority: "P2",
        key: "crisis_regime_review",
        label: "复核 Crisis Score 高风险状态",
        route: "/macro-toolkit",
        basis: "analytical",
        evidence: {
          eligible: true,
          triggered: true,
          threshold: 2,
        },
      });
    });

    expect(screen.getByTestId("module-home-market-dense-crisis-trend")).toHaveTextContent(
      "高风险门已触发 · 阈值 2.00",
    );
    expect(screen.getByText("复核 Crisis Score 高风险状态")).toBeInTheDocument();
  });

  it("does not synthesize an action from a triggered gate when the backend returns none", () => {
    renderSnapshot((envelope) => {
      envelope.result.crisis!.risk_gate = {
        eligible: true,
        triggered: true,
        threshold: 2,
        reason_code: "crisis_score_at_or_above_threshold",
      };
    });

    expect(screen.getByTestId("module-home-market-dense-crisis-trend")).toHaveTextContent(
      "高风险门已触发 · 阈值 2.00",
    );
    expect(screen.queryByText("复核 Crisis Score 高风险状态")).not.toBeInTheDocument();
  });

  it("does not repeat the core Crisis placeholder after the full snapshot result", () => {
    renderSnapshot((envelope) => {
      envelope.result.signals!.cards.unshift({
        key: "crisis_score_cn",
        title: "Crisis Score",
        stance: "完整结果待加载",
        tone: "neutral",
        score: null,
        evidence: ["首屏未运行完整 Crisis Score"],
        kind: "market_signal",
      });
    });

    expect(document.getElementById("market-overview-signals")).toBeNull();
    expect(screen.queryByText("完整结果待加载")).not.toBeInTheDocument();
  });
});
