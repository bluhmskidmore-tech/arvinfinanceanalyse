import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MarketDataMoneyMarketSection } from "../lib/marketDataTerminalModel";
import { MoneyMarketTable } from "./MoneyMarketTable";

const longSourceVersion =
  "backfill_macro_v1__sv_choice_macro_a01365356ebe__sv_crisis_score_aa_5y__sv_research_observation_20260612";

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

  it("colors money-market deltas with the Nocturne theme chain instead of boundary steel-blue vars", () => {
    render(<MoneyMarketTable model={moneyModel} sourceFilter="all" embedded />);

    // --ib-* 在 market-data scope 内解析为边界钢蓝值，着色必须走 --dh-api-* 语义链。
    const delta = screen.getByText("-0.6bp");
    expect(delta.style.color).toBe("var(--dh-api-green)");
    expect(delta.style.color).not.toMatch(/#[0-9a-fA-F]{3,8}/);
  });
});
