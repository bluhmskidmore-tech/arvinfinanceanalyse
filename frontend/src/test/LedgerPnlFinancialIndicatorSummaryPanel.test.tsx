import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient, type ApiClient } from "../api/client";
import { LedgerPnlFinancialIndicatorSummaryPanel } from "../features/ledger-pnl/components/LedgerPnlFinancialIndicatorSummaryPanel";

function renderPanel(
  client: ApiClient,
  reportMonth = "202603",
  currency: "CNX" | "CNY" = "CNX",
) {
  return render(
    <AppProviders client={client}>
      <LedgerPnlFinancialIndicatorSummaryPanel
        reportMonth={reportMonth}
        currency={currency}
      />
    </AppProviders>,
  );
}

describe("LedgerPnlFinancialIndicatorSummaryPanel", () => {
  it("renders the three workbook sections with ledger-computed values for 202603", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    expect(
      await screen.findByRole("heading", { name: "2026年经营指标情况表（总账口径）" }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("ledger-indicator-summary-section-financial"),
    ).toHaveTextContent("财务指标");
    expect(
      screen.getByTestId("ledger-indicator-summary-section-business"),
    ).toHaveTextContent("业务指标");
    expect(
      screen.getByTestId("ledger-indicator-summary-section-asset_quality"),
    ).toHaveTextContent("资产质量指标");

    const revenueRow = screen.getByTestId(
      "ledger-indicator-summary-row-fin.mother_revenue",
    );
    expect(revenueRow).toHaveTextContent("（一）母公司营收（并表口径）");
    // 202603 本期 40.5057623569 亿元 → 2 位小数显示；同比 37.9361212775。
    expect(revenueRow).toHaveTextContent("40.51");
    expect(revenueRow).toHaveTextContent("37.94");
    expect(revenueRow).toHaveTextContent("+2.57");

    const loansRow = screen.getByTestId("ledger-indicator-summary-row-biz.mother_loans");
    expect(loansRow).toHaveTextContent("4,189.47");
    expect(loansRow).toHaveTextContent("3,964.69");

    const ratioRow = screen.getByTestId(
      "ledger-indicator-summary-row-fin.mother_cost_income_ratio",
    );
    expect(ratioRow).toHaveTextContent("22.92%");
    expect(ratioRow).toHaveTextContent("24.20%");
  });

  it("keeps no-source rows as em-dash with an explicit reason instead of zeros", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const groupRevenueRow = await screen.findByTestId(
      "ledger-indicator-summary-row-fin.group_revenue",
    );
    expect(groupRevenueRow).toHaveAttribute("data-availability", "no_system_source");
    expect(within(groupRevenueRow).getAllByText("—").length).toBeGreaterThanOrEqual(4);
    expect(groupRevenueRow).toHaveTextContent("无系统来源");
    expect(groupRevenueRow).not.toHaveTextContent("0.00");

    // 原因不再逐行铺陈整句文案，改为安静标记 + title/aria-label 悬停展示
    // （DESIGN.md §6：同一缺失原因不得每行重复）。
    const nplRow = screen.getByTestId("ledger-indicator-summary-row-aq.npl_amount");
    const reasonMarker = within(nplRow).getByTitle(/五级分类（不良）数据不在总账科目中/);
    expect(reasonMarker).toHaveTextContent("无系统来源");
    expect(reasonMarker).toHaveAttribute(
      "aria-label",
      expect.stringContaining("五级分类（不良）数据不在总账科目中"),
    );
  });

  it("shows a quiet caliber-note and account-evidence marker instead of inline paragraphs", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const loansRow = await screen.findByTestId("ledger-indicator-summary-row-biz.mother_loans");
    const caliberMarker = within(loansRow).getByTitle(/工作簿贷款余额核对一致/);
    expect(caliberMarker).toHaveTextContent("口径差异");

    const evidenceMarker = within(loansRow).getByTitle(/122\+123\+129\+130\+132\+136/);
    expect(evidenceMarker).toHaveTextContent("科目取数");

    // 正文不再平铺完整口径说明句子。
    expect(loansRow).not.toHaveTextContent("已与财务指标工作簿贷款余额核对一致");
  });

  it("labels flow columns as 上年同期 and point columns as 上年末", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const financialSection = await screen.findByTestId(
      "ledger-indicator-summary-section-financial",
    );
    expect(within(financialSection).getAllByText("上年同期").length).toBeGreaterThan(0);
    expect(within(financialSection).queryByText("上年末")).not.toBeInTheDocument();
    expect(within(financialSection).getAllByText("2026年1-3月").length).toBeGreaterThan(0);

    const businessSection = screen.getByTestId(
      "ledger-indicator-summary-section-business",
    );
    expect(within(businessSection).getAllByText("上年末").length).toBeGreaterThan(0);
    expect(within(businessSection).getAllByText("2026年3月末").length).toBeGreaterThan(0);

    // 资产质量板块混合口径：核销段为累计期间，余额段为月末时点。
    const assetQualitySection = screen.getByTestId(
      "ledger-indicator-summary-section-asset_quality",
    );
    expect(within(assetQualitySection).getAllByText("上年同期").length).toBeGreaterThan(0);
    expect(within(assetQualitySection).getAllByText("上年末").length).toBeGreaterThan(0);
  });

  it("shows the quality strip with identity checks and computed coverage", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const quality = await screen.findByTestId("ledger-indicator-summary-quality");
    expect(quality).toHaveAttribute("data-state", "ok");
    expect(quality).toHaveTextContent("恒等校验 14 / 14 通过");
    // 覆盖度状态条：可计算 / 无系统来源 / 共计行数三段式，配语义色圆点。
    expect(quality).toHaveTextContent("可计算 13 / 无系统来源 37 / 共 50 行");
    expect(quality.querySelectorAll('[data-tone="ok"]').length).toBeGreaterThanOrEqual(2);
  });

  it("surfaces a failing quality check with its message and gap in yuan", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlFinancialIndicatorSummary: async (reportMonth, currency) => {
        const envelope = await baseClient.getLedgerPnlFinancialIndicatorSummary(
          reportMonth,
          currency,
        );
        return {
          ...envelope,
          result: {
            ...envelope.result,
            quality_checks: envelope.result.quality_checks.map((check, index) =>
              index === 0 ? { ...check, passed: false, gap_yuan: "1234.56" } : check,
            ),
          },
        };
      },
    };
    renderPanel(client);

    const quality = await screen.findByTestId("ledger-indicator-summary-quality");
    expect(quality).toHaveAttribute("data-state", "warning");
    expect(quality).toHaveTextContent("净利润(利润总额-所得税)与 -(全部损益科目余额合计) 恒等未闭合");
    // gap_yuan 单位是元，与表体亿元单位不同，展示时必须显式标注、不可直接混用。
    expect(quality).toHaveTextContent("1,234.56 元");
    expect(quality).toHaveTextContent("与表体亿元单位不同");
  });

  it("collapses business and asset_quality sections by default while keeping financial expanded", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const financialSection = (await screen.findByTestId(
      "ledger-indicator-summary-section-financial",
    )) as HTMLDetailsElement;
    const businessSection = screen.getByTestId(
      "ledger-indicator-summary-section-business",
    ) as HTMLDetailsElement;
    const assetQualitySection = screen.getByTestId(
      "ledger-indicator-summary-section-asset_quality",
    ) as HTMLDetailsElement;

    expect(financialSection.open).toBe(true);
    expect(businessSection.open).toBe(false);
    expect(assetQualitySection.open).toBe(false);

    // 折叠头部即便未展开也要能看到该分区的可计算/无系统来源行数。
    expect(businessSection).toHaveTextContent("可计算 3 / 无系统来源 3 / 共 6 行");
    expect(assetQualitySection).toHaveTextContent("可计算 2 / 无系统来源 12 / 共 14 行");

    const businessSummary = businessSection.querySelector("summary");
    expect(businessSummary).not.toBeNull();
    fireEvent.click(businessSummary as HTMLElement);
    expect(businessSection.open).toBe(true);
  });

  it("shows the no-data state for a month without ledger sources", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client, "202605");

    const state = await screen.findByTestId("ledger-indicator-summary-no-data");
    expect(state).toHaveTextContent("202605 无可计算的总账来源");
    expect(state).toHaveTextContent("不以 0 值展示");
  });

  it("surfaces backend failures with a retry action", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlFinancialIndicatorSummary: vi.fn(async () => {
        throw new Error("Request failed: financial indicator summary (503)");
      }),
    };
    renderPanel(client);

    const state = await screen.findByTestId("ledger-indicator-summary-error");
    expect(state).toHaveTextContent("经营指标情况表读取失败");
    expect(state).toHaveTextContent("Request failed: financial indicator summary (503)");
    expect(within(state).getByRole("button", { name: "重新读取" })).toBeInTheDocument();
  });
});
