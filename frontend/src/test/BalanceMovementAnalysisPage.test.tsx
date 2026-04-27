import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { createApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("BalanceMovementAnalysisPage", () => {
  it("renders AC OCI TPL balance movement from the governed read model", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("balance-movement-analysis-title")).toHaveTextContent(
      "余额变动分析",
    );
    expect(await screen.findByTestId("balance-movement-analysis-summary")).toHaveTextContent(
      "3,358.73",
    );
    const conclusion = await screen.findByTestId("balance-movement-analysis-conclusion");
    expect(conclusion).toHaveTextContent("总账控制核对通过");
    expect(conclusion).toHaveTextContent("3,358.733093 亿");
    expect(conclusion).toHaveTextContent("AC 42.44%");
    expect(conclusion).toHaveTextContent("OCI 31.49%");
    expect(conclusion).toHaveTextContent("TPL 26.07%");
    expect(conclusion).toHaveTextContent("排除 144020 股权 OCI");
    expect(conclusion).toHaveTextContent("ZQTZ 诊断差异仅用于提示明细扫描差异");
    expect(await screen.findByTestId("balance-movement-analysis-trend-conclusion")).toHaveTextContent(
      "较 2026-01-31 +129.80 亿",
    );
    expect(screen.getByTestId("balance-movement-analysis-trend-conclusion")).toHaveTextContent(
      "TPL +51.63 亿、OCI +44.87 亿、AC +33.29 亿",
    );

    const table = screen.getByTestId("balance-movement-analysis-table");
    expect(within(table).getByText("AC")).toBeInTheDocument();
    expect(within(table).getByText("42.44%")).toBeInTheDocument();
    expect(within(table).getByText("OCI")).toBeInTheDocument();
    expect(within(table).getByText("TPL")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-controls")).toHaveTextContent(
      "1440101%",
    );
    expect(screen.getByTestId("balance-movement-analysis-controls")).toHaveTextContent(
      "144020%",
    );
    const trendTable = screen.getByTestId("balance-movement-analysis-trend-table");
    expect(within(trendTable).getByText("2026-02")).toBeInTheDocument();
    expect(within(trendTable).getByText("+129.80 亿")).toBeInTheDocument();
    expect(within(trendTable).getByText("2026-01")).toBeInTheDocument();
  });

  it("refreshes the selected report date through the formal materialize endpoint", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    await screen.findByTestId("balance-movement-analysis-table");
    await user.click(screen.getByTestId("balance-movement-analysis-refresh"));

    expect(await screen.findByTestId("balance-movement-analysis-refresh-message")).toHaveTextContent(
      "completed: 3 行",
    );
  });

  it("suppresses the month-over-month conclusion when available snapshots are not adjacent", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const sparseClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            trend_months: envelope.result.trend_months.map((month, index) =>
              index === 1
                ? {
                    ...month,
                    report_date: "2025-12-31",
                    report_month: "2025-12",
                  }
                : month,
            ),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: sparseClient,
    });

    expect(await screen.findByTestId("balance-movement-analysis-trend-table")).toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-analysis-trend-conclusion")).not.toBeInTheDocument();
  });
});
