import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { NcdFundingProxyPayload } from "../../../api/contracts";
import type { MarketDataMoneyMarketSection } from "../lib/marketDataTerminalModel";
import { MoneyMarketTable } from "./MoneyMarketTable";
import { NcdMatrix } from "./NcdMatrix";
import type { MarketDataRateQuoteSection } from "../lib/marketDataTerminalModel";
import { RateQuoteTable } from "./RateQuoteTable";

const longSourceVersion =
  "backfill_macro_v1__sv_choice_macro_a01365356ebe__sv_crisis_score_aa_5y__sv_research_observation_20260612";

const model: MarketDataRateQuoteSection = {
  status: "ready",
  emptyReason: "",
  source: {
    basis: "formal",
    qualityFlag: "ok",
    fallbackMode: "none",
    sourceVersion: longSourceVersion,
    vendorVersion: "vv_choice_macro",
    traceId: "tr_rate_quote_table",
  },
  rows: [
    {
      key: "cgb-10y",
      variety: "国债",
      tenor: "10Y",
      seriesId: "EMM00166466",
      seriesName: "ChinaBond CGB yield 10Y",
      rateText: "1.75%",
      deltaText: "-1bp",
      tradeDate: "2026-06-12",
      sourceVersion: longSourceVersion,
      vendorVersion: "vv_choice_macro",
      qualityFlag: "ok",
      sourceMode: "formal",
      sparklineValues: [1.76, 1.75],
    },
  ],
};

describe("RateQuoteTable", () => {
  it("keeps full source lineage available without letting long versions dominate the table", async () => {
    render(<RateQuoteTable model={model} curveFilter="treasury" sourceFilter="all" embedded />);

    const table = screen.getByTestId("market-data-rate-quote-table");
    const sourceChip = await within(table).findByTestId("market-data-rate-source-chip-cgb-10y");
    const seriesChip = within(table).getByTestId("market-data-rate-series-chip-cgb-10y");

    expect(sourceChip).toHaveAttribute("title", longSourceVersion);
    expect(sourceChip).not.toHaveTextContent(longSourceVersion);
    expect(sourceChip.textContent?.length ?? 0).toBeLessThan(40);
    expect(seriesChip).toHaveTextContent("EMM00166466");
  });

  it("colors rate deltas with theme-aware CSS variables instead of light semantic hex", () => {
    render(<RateQuoteTable model={model} curveFilter="treasury" sourceFilter="all" embedded />);

    // 页面处于 ThemedRouteBoundary 暗色边界内：着色必须走 --ib-* CSS 变量，
    // 由 tokens.css 在 theme-dh-api 下重映射，禁止浅色 semantic.profit/loss 直灌。
    const delta = screen.getByText("-1bp");
    expect(delta.style.color).toBe("var(--ib-up)");
    expect(delta.style.color).not.toMatch(/#[0-9a-fA-F]{3,8}/);
  });
});

const moneyModel: MarketDataMoneyMarketSection = {
  status: "ready",
  emptyReason: "",
  source: {
    basis: "analytical",
    qualityFlag: "warning",
    fallbackMode: "latest_snapshot",
    sourceVersion: longSourceVersion,
    vendorVersion: "vv_choice_macro",
    traceId: "tr_money_market_table",
  },
  rows: [
    {
      key: "dr007",
      name: "DR007",
      seriesId: "CA.DR007",
      seriesName: "Depository repo fixing DR007",
      rateText: "1.82%",
      deltaText: "-0.6bp",
      tradeDate: "2026-06-12",
      sourceVersion: longSourceVersion,
      vendorVersion: "vv_choice_macro",
      qualityFlag: "warning",
      sourceMode: "latest_snapshot",
      sparklineValues: [1.83, 1.82],
    },
  ],
};

describe("MoneyMarketTable", () => {
  it("keeps source mode and series chips visible without letting long labels dominate", async () => {
    render(<MoneyMarketTable model={moneyModel} sourceFilter="all" embedded />);

    const table = screen.getByTestId("market-data-money-market-table");
    const sourceModeChip = await within(table).findByTestId(
      "market-data-money-source-mode-chip-dr007",
    );
    const seriesChip = within(table).getByTestId("market-data-money-series-chip-dr007");

    expect(sourceModeChip).toHaveAttribute("title", "latest_snapshot");
    expect(sourceModeChip).toHaveTextContent("latest");
    expect(sourceModeChip).not.toHaveTextContent("latest_snapshot");
    expect(seriesChip).toHaveAttribute("title", "Depository repo fixing DR007 · CA.DR007");
    expect(seriesChip).toHaveTextContent("CA.DR007");
  });

  it("shows a filter empty state after source filtering removes all money-market rows", () => {
    render(<MoneyMarketTable model={moneyModel} sourceFilter="internal" embedded />);

    expect(screen.getByTestId("market-data-money-market-filter-empty")).toHaveTextContent(
      "当前来源筛选下无资金利率序列。",
    );
    expect(screen.queryByText("CA.DR007")).not.toBeInTheDocument();
  });

  it("colors money-market deltas with theme-aware CSS variables instead of light semantic hex", () => {
    render(<MoneyMarketTable model={moneyModel} sourceFilter="all" embedded />);

    const delta = screen.getByText("-0.6bp");
    expect(delta.style.color).toBe("var(--ib-up)");
    expect(delta.style.color).not.toMatch(/#[0-9a-fA-F]{3,8}/);
  });
});

const ncdProxyPayload: NcdFundingProxyPayload = {
  as_of_date: "2026-06-09",
  proxy_label: "Choice/Tushare Shibor funding proxy",
  is_actual_ncd_matrix: false,
  formal_ncd_matrix_status: {
    status: "blocked",
    required_shape: "tenor_rating_matrix",
    current_proxy_basis: "shibor_funding_proxy",
    choice_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
    tushare_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
    missing_requirements: ["governed NCD tenor-rating source contract"],
  },
  rows: [
    {
      row_key: "shibor_fixing",
      label: "Shibor fixing",
      "1M": 1.427,
      "3M": 1.4144,
      "6M": 1.4299,
      "9M": 1.45,
      "1Y": 1.43,
      quote_count: null,
    },
  ],
  warnings: ["Proxy only; not actual NCD issuance matrix."],
};

describe("NcdMatrix", () => {
  it("keeps proxy status explicit and does not present the table as a formal NCD matrix", async () => {
    render(<NcdMatrix payload={ncdProxyPayload} showResultMeta={false} embedded />);

    const panel = await screen.findByTestId("market-data-ncd-matrix");
    expect(within(panel).getByText(/Choice\/Tushare Shibor funding proxy/)).toBeInTheDocument();
    expect(within(panel).getByText(/proxy 非正式发行矩阵/)).toBeInTheDocument();
    expect(within(panel).getByTestId("market-data-ncd-view-toggle")).toBeInTheDocument();
    expect(within(panel).getByText("Shibor fixing")).toBeInTheDocument();
    expect(within(panel).getByText("1.427")).toBeInTheDocument();
    expect(panel).not.toHaveTextContent("formal NCD matrix");
  });
});
