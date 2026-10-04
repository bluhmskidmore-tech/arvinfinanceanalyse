import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MarketFundingObservation, MarketObservationEvidence, MarketRatesObservation } from "../../../api/contracts/marketMacro";
import { MarketFundingRatesObservations } from "./MarketFundingRatesObservations";

vi.mock("../../../components/charts/ChartCard", () => ({
  ChartCard: ({ title, ariaLabel, option, footnote }: { title?: string; ariaLabel?: string; option: unknown; footnote?: string }) => <><div data-testid={title ?? ariaLabel}>{JSON.stringify(option)}</div><p>{footnote}</p></>,
}));

function row(key: string, value: number, previous: number, change: number): MarketObservationEvidence {
  return { key, label: key, series_id: key, value, previous_value: previous, change_bp: change, unit: "%", observation_date: "2026-09-04", previous_date: "2026-09-03", source: "合成验收来源", quality_flag: "ok", fallback_mode: "none", is_proxy: false, status: "ok", reason: null, recent_points: [{ trade_date: "2026-09-03", value_numeric: previous }, { trade_date: "2026-09-04", value_numeric: value }] };
}

function observations(): { funding: MarketFundingObservation; rates: MarketRatesObservation } {
  const dr = { ...row("dr007", 1.5, 1.49, 1), label: "DR007" };
  const common = { status: "ok" as const, judgment_allowed: true, observation_date: "2026-09-04", comparison_date: "2026-09-03", summary: "合成验收判断", interpretation: "若市场变化传导至实际融资成本，持券负担可能变化。", limitations: ["本页没有本行融资数据。"], reason: null, rule_version: "test-v1", verification_route: "/market-data", window_label: "近20期" };
  const rows = [{ ...row("2y", 1.25, 1.3, -5), label: "2年", tenor_years: 2 }, { ...row("10y", 1.68, 1.7, -2), label: "10年", tenor_years: 10 }];
  return {
    funding: { ...common, rows: [dr], evidence: [dr], policy_reference: { value: 1.4, unit: "%", effective_from: null, effective_to: null, validity_status: "unverified", source: "操作日记录", reason: "缺少政策生效区间。" }, policy_deviation_bp: null },
    rates: { ...common, rows, evidence: rows, curve_family: "gov", full_curve_comparison_allowed: false, summary: "2年降幅大于10年，期限利差扩大。", spreads: [{ key: "10y_2y", label: "10年减2年", value_bp: 43, previous_value_bp: 40, change_bp: 3, observation_date: "2026-09-04", comparison_date: "2026-09-03", status: "ok", reason: null, input_keys: ["2y", "10y"] }] },
  };
}

function show(props = observations()) { return render(<MemoryRouter><MarketFundingRatesObservations {...props} /></MemoryRouter>); }
function expandDetails(name: "资金明细与说明" | "曲线明细与说明") { fireEvent.click(screen.getByText(name)); }

describe("MarketFundingRatesObservations", () => {
  beforeEach(() => { sessionStorage.removeItem("moss:market-home:funding-controls"); window.history.replaceState(null, "", window.location.pathname); });
  it("reveals and focuses the original chart for a repeated same-hash reference", async () => {
    const props = observations();
    render(<MemoryRouter><a href="#market-overview-chart-key-rate-trend">查看原图</a><MarketFundingRatesObservations {...props} display="funding" keyRatesContent={<section id="market-overview-chart-key-rate-trend">关键利率原图</section>} /></MemoryRouter>);
    expect(screen.getByText("关键利率原图")).not.toBeVisible();
    fireEvent.click(screen.getByRole("link", { name: "查看原图" }));
    await waitFor(() => expect(screen.getByText("关键利率原图")).toHaveFocus());
    fireEvent.click(screen.getByRole("button", { name: "资金价格" }));
    expect(screen.getByText("关键利率原图")).not.toBeVisible();
    fireEvent.click(screen.getByRole("link", { name: "查看原图" }));
    await waitFor(() => expect(screen.getByText("关键利率原图")).toBeVisible());
    expect(screen.getByRole("button", { name: "关键利率" })).toHaveAttribute("aria-pressed", "true");
  });

  it("restores only chart controls on return without storing observations", () => {
    sessionStorage.setItem("moss:market-home:funding-controls", JSON.stringify({ view: "key-rates", series: "shibor_3m" }));
    const props = observations();
    props.funding.rows.push({ ...row("shibor_3m", 1.43, 1.42, 1), label: "SHIBOR 3M" });
    render(<MemoryRouter><MarketFundingRatesObservations {...props} display="funding" keyRatesContent={<p>关键利率图内容</p>} /></MemoryRouter>);
    expect(screen.getByText("关键利率图内容")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "资金价格" }));
    expect(screen.getByRole("combobox", { name: "走势指标" })).toHaveValue("shibor_3m");
    expect(JSON.parse(sessionStorage.getItem("moss:market-home:funding-controls")!)).toEqual({ view: "funding", series: "shibor_3m" });
  });
  it("renders the split chart slots and switches funding without dropping its selected series", () => {
    const props = observations();
    props.funding.rows.push({ ...row("shibor_3m", 1.43, 1.42, 1), label: "SHIBOR 3M" });
    render(<MemoryRouter><MarketFundingRatesObservations {...props} display="funding" keyRatesContent={<p>关键利率图内容</p>} /></MemoryRouter>);
    expect(screen.queryByText("国债收益率曲线")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "走势指标" }), { target: { value: "shibor_3m" } });
    fireEvent.click(screen.getByRole("button", { name: "关键利率" }));
    expect(screen.getByText("关键利率图内容")).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "走势指标" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "资金价格" }));
    expect(screen.getByRole("combobox", { name: "走势指标" })).toHaveValue("shibor_3m");
  });

  it("displays backend changes and spreads without recomputing or implying complete curve coverage", () => {
    show();
    expandDetails("曲线明细与说明");
    const curves = screen.getByRole("table", { name: "国债分期限变化" });
    expect(curves).toHaveTextContent("-5 bp");
    expect(curves).toHaveTextContent("-2 bp");
    const spreads = screen.getByRole("table", { name: "国债期限利差变化" });
    expect(spreads).toHaveTextContent("40 bp");
    expect(spreads).toHaveTextContent("43 bp");
    expect(spreads).toHaveTextContent("+3 bp");
    expect(within(screen.getByText("曲线明细与说明").closest("details")!).getByText("2年降幅大于10年，期限利差扩大。")).toBeVisible();
    const series = JSON.parse(screen.getByTestId("两期国债曲线").textContent!).series;
    expect(series[0].data).toEqual([1.25, 1.68]);
    expect(series[1].data).toEqual([1.3, 1.7]);
  });

  it("never extends an unverified operation rate into a policy line", () => {
    const props = observations();
    show(props);
    expect(screen.getByText("政策基准待核验")).toBeVisible();
    expect(screen.getByText("缺少政策生效区间。")).not.toBeVisible();
    expect(screen.getByTestId("资金价格近20期")).not.toHaveTextContent("有效政策基准");
    expandDetails("资金明细与说明");
    expect(screen.getByText("缺少政策生效区间。")).toBeVisible();
    expect(screen.getByRole("table", { name: "资金价格与比较日期" })).toHaveTextContent("1.5 %");
  });

  it("displays a verified deviation and only the proven interval in the policy chart", () => {
    const props = observations();
    props.funding.policy_reference.validity_status = "verified";
    props.funding.policy_reference.effective_from = "2026-09-04";
    props.funding.policy_deviation_bp = 10;
    show(props);
    expandDetails("资金明细与说明");
    expect(screen.getByText("+10")).toHaveTextContent("+10 bp");
    const series = JSON.parse(screen.getByTestId("资金价格近20期").textContent!).series;
    expect(series[1].data).toEqual([null, 1.4]);
  });

  it("keeps different observation dates and excludes mismatched nodes from a same-date curve", () => {
    const props = observations();
    props.funding.observation_date = "2026-09-07";
    props.rates.rows[0]!.observation_date = "2026-09-02";
    show(props);
    expect(screen.getByText(/资金观察日 2026-09-07；比较日 2026-09-03 · %/)).toBeVisible();
    expect(screen.getByText(/曲线观察日 2026-09-04；比较日 2026-09-03 · %/)).toBeVisible();
    const series = JSON.parse(screen.getByTestId("两期国债曲线").textContent!).series;
    expect(series[0].data).toEqual([null, 1.68]);
  });

  it("keeps zero, missing and tiny nonzero backend changes distinct and raw evidence accessible", () => {
    const props = observations();
    props.rates.rows[0]!.change_bp = 0.00000006;
    props.rates.rows[1]!.change_bp = 0;
    props.rates.spreads[0]!.change_bp = null;
    show(props);
    expandDetails("曲线明细与说明");
    expect(screen.getByRole("table", { name: "国债分期限变化" })).toHaveTextContent("+0.00000006 bp");
    expect(screen.getByRole("table", { name: "国债分期限变化" })).toHaveTextContent("0 bp");
    expect(screen.getByRole("table", { name: "国债期限利差变化" })).toHaveTextContent("—");
    fireEvent.click(screen.getByRole("button", { name: "查看曲线依据" }));
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText("test-v1", { exact: false })).toBeVisible();
    expect(within(drawer).getAllByText("合成验收来源")).toHaveLength(2);
    expect(within(drawer).getByText("6e-8")).toBeVisible();
    fireEvent.click(within(drawer).getByRole("button", { name: /close/i }));
  });

  it("preserves independent curve facts when funding is blocked and accurately names proxy inputs", () => {
    const props = observations();
    props.funding.judgment_allowed = false;
    props.funding.summary = "DR007来源待核验。";
    props.funding.rows[0]!.label = "FDR007（定盘代理）";
    props.funding.rows[0]!.is_proxy = true;
    show(props);
    expect(screen.getByText("判断受限")).toBeVisible();
    expect(screen.getByText("代理参考")).toBeVisible();
    expect(screen.getByText("DR007来源待核验。")).not.toBeVisible();
    const visibleCurveSummary = screen.getAllByText("2年降幅大于10年，期限利差扩大。").find((element) => !element.closest("details"));
    expect(visibleCurveSummary).toBeVisible();
    expandDetails("资金明细与说明");
    expect(screen.getByText("DR007来源待核验。")).toBeVisible();
    expect(screen.getByRole("table", { name: "资金价格与比较日期" })).toHaveTextContent("FDR007（定盘代理）");
  });

  it("shows the precise restriction once per panel without mislabeling an unverified comparison as missing coverage", () => {
    const props = observations();
    props.rates.judgment_allowed = false;
    props.rates.reason = "曲线刷新回执尚未核验，原值仅供核验。";
    show(props);
    expect(screen.getAllByText(props.rates.reason)).toHaveLength(1);
    expect(screen.queryByText("判断受限；以下保留带日期的原始观测。")).not.toBeInTheDocument();
    expect(screen.getByText("跨期比较待核验")).toBeVisible();
    expandDetails("曲线明细与说明");
    expect(screen.getByText("跨期比较条件未全部核验，请按各项日期与使用限制核对。")).toBeVisible();
    expect(screen.queryByText(/曲线覆盖不完整/)).not.toBeInTheDocument();
  });

  it("shows allowed conclusions and both main charts before collapsed tables, with explanations available on demand", () => {
    const props = observations();
    show(props);
    const fundingDetails = screen.getByText("资金明细与说明").closest("details")!;
    const ratesDetails = screen.getByText("曲线明细与说明").closest("details")!;
    expect(fundingDetails.open).toBe(false);
    expect(ratesDetails.open).toBe(false);
    for (const [summary, details] of [[props.funding.summary, fundingDetails], [props.rates.summary, ratesDetails]] as const) {
      const mainSummary = screen.getAllByText(summary).filter((element) => !element.closest("details"));
      expect(mainSummary).toHaveLength(1);
      expect(mainSummary[0]).toBeVisible();
      expect(within(details).getByText(summary)).not.toBeVisible();
    }
    expect(screen.getByTestId("资金价格近20期")).toBeVisible();
    expect(screen.getByTestId("两期国债曲线")).toBeVisible();
    expect(screen.getByTestId("资金价格近20期").compareDocumentPosition(fundingDetails) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId("两期国债曲线").compareDocumentPosition(ratesDetails) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("table", { name: "资金价格与比较日期" })).not.toBeVisible();
    expect(screen.getByRole("table", { name: "国债分期限变化" })).not.toBeVisible();
    for (const explanation of screen.getAllByText("若市场变化传导至实际融资成本，持券负担可能变化。")) expect(explanation).not.toBeVisible();
    expandDetails("资金明细与说明");
    expect(screen.getByRole("table", { name: "资金价格与比较日期" })).toBeVisible();
    expect(within(fundingDetails).getByText("若市场变化传导至实际融资成本，持券负担可能变化。")).toBeVisible();
    expandDetails("曲线明细与说明");
    expect(screen.getByRole("table", { name: "国债分期限变化" })).toBeVisible();
    expect(screen.getByRole("table", { name: "国债期限利差变化" })).toBeVisible();
  });

  it("keeps concise restrictions visible and preserves their full reasons in the collapsed details", () => {
    const props = observations();
    props.funding.judgment_allowed = false;
    props.funding.reason = "资金刷新回执未通过核验，原值仅供核验。";
    props.funding.rows[0]!.is_proxy = true;
    props.funding.rows[0]!.reason = "来源为代理，不能替代目标指标判断。";
    props.funding.policy_reference.reason = "政策基准待核验：没有生效区间。";
    props.funding.limitations = [...props.funding.limitations, props.funding.policy_reference.reason];
    props.rates.judgment_allowed = false;
    props.rates.reason = "曲线刷新回执未通过核验，原值仅供核验。";
    props.rates.limitations = [...props.rates.limitations, "必要期限节点缺少有效比较，不能形成整体判断。"];
    show(props);
    for (const message of [props.funding.reason, props.funding.rows[0]!.reason, props.funding.policy_reference.reason, props.rates.reason, props.rates.limitations[1]!]) {
      expect(screen.getByText(message)).not.toBeVisible();
    }
    expect(screen.getAllByText("判断受限")).toHaveLength(2);
    for (const status of screen.getAllByText("判断受限")) expect(status).toBeVisible();
    expect(screen.getByText("政策基准待核验")).toBeVisible();
    expect(screen.getByText("跨期比较待核验")).toBeVisible();
    expect(screen.getAllByText(props.funding.policy_reference.reason)).toHaveLength(1);
    expect(screen.getByText("代理参考")).toBeVisible();
    expect(screen.getByText("资金明细与说明").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText("曲线明细与说明").closest("details")).not.toHaveAttribute("open");
    expandDetails("资金明细与说明");
    expandDetails("曲线明细与说明");
    for (const message of [props.funding.reason, props.funding.rows[0]!.reason, props.funding.policy_reference.reason, props.rates.reason, props.rates.limitations[1]!]) {
      expect(screen.getByText(message)).toBeVisible();
    }
  });

  it("keeps the funding selector usable while the data table is folded", () => {
    const props = observations();
    props.funding.rows.push({ ...row("shibor_3m", 1.43, 1.42, 1), label: "SHIBOR 3M" });
    show(props);
    fireEvent.change(screen.getByRole("combobox", { name: "走势指标" }), { target: { value: "shibor_3m" } });
    const series = JSON.parse(screen.getByTestId("资金价格近20期").textContent!).series;
    expect(series[0].name).toBe("SHIBOR 3M");
    expect(series[0].data).toEqual([1.42, 1.43]);
    expect(screen.getByText("资金明细与说明").closest("details")).not.toHaveAttribute("open");
  });
});
