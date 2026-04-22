import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { Bond } from "../bond-analysis-foundation/data-structures/BondModel";
import type { Portfolio } from "../bond-analysis-foundation/data-structures/PortfolioModel";
import { Dashboard } from "../bond-analysis-foundation/react-components/dashboard/Dashboard";
import { MainLayout } from "../bond-analysis-foundation/react-components/layouts/MainLayout";
import { BondTable } from "../bond-analysis-foundation/react-components/bonds/BondTable";
import { OrderForm } from "../bond-analysis-foundation/react-components/trading/OrderForm";

const sampleBond: Bond = {
  bondId: "BOND-240210",
  bondCode: "240210",
  isin: "CND100240210",
  market: "CIBM",
  shortName: "24国开10",
  fullName: "2024年国家开发银行金融债券",
  issuerId: "ISSUER-CDB",
  issuerName: "国家开发银行",
  issuerType: "policy_bank",
  currency: "CNY",
  couponType: "fixed",
  couponRate: 2.45,
  issueDate: "2024-02-10",
  maturityDate: "2034-02-10",
  paymentFrequency: "ANNUAL",
  marketData: {
    cleanPrice: 101.24,
    dirtyPrice: 101.56,
    yieldToMaturity: 2.12,
    yieldChangeBp: -3,
    priceChangePct: 0.35,
    tradeVolume: 85000000,
    tradeAmount: 86000000,
    bidPrice: 101.2,
    askPrice: 101.28,
    midPrice: 101.24,
    quoteTime: "2026-04-21T09:31:00Z",
    dataQuality: {
      asOfDate: "2026-04-21",
      source: "mock",
      freshness: "live",
      isStale: false,
      lastUpdatedAt: "2026-04-21T09:31:00Z",
    },
  },
  riskMetrics: {
    rating: "AAA",
    modifiedDuration: 6.4,
    macaulayDuration: 6.7,
    convexity: 0.88,
    creditSpreadBp: 32,
    optionAdjustedSpreadBp: 28,
    liquidityRating: "L1",
    riskScore: 24,
  },
  history: {
    priceHistory: [
      { date: "2026-04-19", value: 100.82 },
      { date: "2026-04-20", value: 101.01 },
      { date: "2026-04-21", value: 101.24 },
    ],
    yieldHistory: [
      { date: "2026-04-19", value: 2.18 },
      { date: "2026-04-20", value: 2.15 },
      { date: "2026-04-21", value: 2.12 },
    ],
    ratingHistory: [
      {
        effectiveDate: "2026-04-01",
        agency: "中债资信",
        newRating: "AAA",
      },
    ],
  },
};

const samplePortfolio: Portfolio = {
  portfolioId: "PF-001",
  portfolioName: "核心利率组合",
  createdAt: "2026-01-02T09:00:00Z",
  managerName: "交易台一组",
  benchmark: "中债-国债及政策性金融债指数",
  totalMarketValue: 1280000000,
  cashBalance: 12000000,
  statistics: {
    averageYield: 2.38,
    weightedDuration: 5.8,
    concentrationRatio: 0.34,
    riskScore: 21,
    dailyPnl: 3200000,
    monthlyPnl: 12400000,
  },
  holdings: [
    {
      positionId: "POS-1",
      bond: sampleBond,
      weight: 0.18,
      faceValue: 230000000,
      holdingCost: 100.21,
      marketValue: 231400000,
      unrealizedPnl: 1450000,
      contributionYield: 0.39,
    },
  ],
  analytics: {
    asOfDate: "2026-04-21",
    curveExposure: [
      { tenor: "5Y", weight: 0.24 },
      { tenor: "10Y", weight: 0.42 },
    ],
    ratingExposure: [
      { bucket: "AAA", weight: 0.76 },
      { bucket: "AA+", weight: 0.18 },
    ],
    issuerExposure: [
      { issuerName: "国家开发银行", weight: 0.18 },
    ],
    stressTests: [
      {
        scenarioId: "SCN-UP50",
        scenarioName: "收益率平行上行 50bp",
        estimatedPnl: -28400000,
      },
    ],
  },
};

describe("bond-analysis foundation scaffold", () => {
  it("renders dashboard first-screen conclusions and stale-state messaging", () => {
    render(
      <Dashboard
        title="债券交易仪表板"
        primaryConclusion="久期风险可控，但信用利差收敛带来交易窗口。"
        marketSummary="10Y 国债收益率回落 3bp，组合久期略高于基准。"
        status={{
          freshness: "fallback",
          asOfDate: "2026-04-21",
          isStale: true,
          fallbackDate: "2026-04-20",
        }}
        metrics={[
          { label: "组合久期", value: "5.8", helperText: "高于基准 0.4" },
          { label: "平均到期收益率", value: "2.38%", trend: { direction: "up", value: "+4bp" } },
        ]}
        portfolio={samplePortfolio}
        watchlist={[sampleBond]}
      />,
    );

    expect(screen.getByText("债券交易仪表板")).toBeInTheDocument();
    expect(screen.getByText("久期风险可控，但信用利差收敛带来交易窗口。")).toBeInTheDocument();
    expect(screen.getByText(/回退日期/)).toHaveTextContent("2026-04-20");
    expect(screen.getByText("核心利率组合")).toBeInTheDocument();
    expect(screen.getAllByText("24国开10").length).toBeGreaterThan(0);
  });

  it("renders the layout shell and bond table selection flow", async () => {
    const user = userEvent.setup();
    const onSelectBond = vi.fn();

    render(
      <MainLayout
        header={<div>header</div>}
        sidebar={<div>sidebar</div>}
        footer={<div>footer</div>}
      >
        <BondTable bonds={[sampleBond]} onSelectBond={onSelectBond} />
      </MainLayout>,
    );

    expect(screen.getByText("header")).toBeInTheDocument();
    expect(screen.getByText("sidebar")).toBeInTheDocument();
    expect(screen.getByText("footer")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看 24国开10" }));

    expect(onSelectBond).toHaveBeenCalledWith(sampleBond);
  });

  it("submits order form payloads with numeric fields coerced to numbers", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <OrderForm
        initialBondCode="240210"
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText("数量"), "1000000");
    await user.type(screen.getByLabelText("价格"), "101.25");
    await user.type(screen.getByLabelText("手续费"), "500");
    await user.click(screen.getByRole("button", { name: "提交订单" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        bondCode: "240210",
        quantity: 1000000,
        price: 101.25,
        feeAmount: 500,
      }),
    );
  });
});
