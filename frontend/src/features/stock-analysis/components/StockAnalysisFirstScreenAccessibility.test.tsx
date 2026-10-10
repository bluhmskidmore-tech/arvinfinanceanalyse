import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FactorScreenCandidateItem } from "../../../api/contracts";
import { StockAnalysisFactorCandidatesCard } from "./StockAnalysisFactorCandidatesCard";

const factorCandidate: FactorScreenCandidateItem = {
  rank: 1,
  stock_code: "600000.SH",
  stock_name: "因子甲",
  sector_code: "801730",
  sector_name: "电力设备",
  industry: "电力设备",
  score: 0.8123,
  pe: 12.4,
  pb: 1.6,
  roe: 0.143,
  gross_margin: 0.32,
  three_month_return: 0.056,
  twelve_month_return: 0.184,
  dividend_yield: 0.021,
};

describe("stock-analysis first-screen accessibility contracts", () => {
  it("uses the visible stock name and code as the factor-row button name", async () => {
    const onOpenDetail = vi.fn();
    render(
      <StockAnalysisFactorCandidatesCard
        model={{
          candidateCount: 1,
          countLabel: "1 只",
          asOfLabel: "2026-08-24",
          degraded: false,
          degradedTitle: null,
          observationOnly: true,
          coverageLabel: "覆盖 1 只",
        }}
        items={[factorCandidate]}
        onOpenDetail={onOpenDetail}
      />,
    );

    const button = screen.getByRole("button", { name: "因子甲 600000.SH" });
    expect(button).toHaveAccessibleName("因子甲 600000.SH");
    expect(button).toHaveAttribute("title", "查看因子甲（600000.SH）详情");
    expect(button).toHaveAttribute("data-testid", "stock-analysis-factor-open-600000.SH");
  });

  it("keeps mobile row actions at least 24 by 24 pixels without changing desktop density", () => {
    const editorialCss = readFileSync(
      resolve(process.cwd(), "src/features/stock-analysis/pages/StockAnalysisEditorialLedger.css"),
      "utf8",
    );

    expect(editorialCss).toMatch(
      /@media \(max-width: 719px\)[\s\S]*?\.stock-analysis-page__fs-factor-stock\s*\{[^}]*min-width:\s*24px;[^}]*min-height:\s*24px;/,
    );
  });
});
