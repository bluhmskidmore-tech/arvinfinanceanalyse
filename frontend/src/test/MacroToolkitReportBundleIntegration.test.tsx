import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { ApiClientProvider } from "../api/clientContext";
import MacroToolkitPage from "../features/macro-toolkit/pages/MacroToolkitPage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="macro-toolkit-echarts-stub" />,
}));

describe("macro report bundle page integration", () => {
  it("shows the read-only report asset on the toolkit surface", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const envelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...envelope,
        result: {
          ...envelope.result,
          report_bundle: {
            status: "ready" as const,
            reason: null,
            schema_version: "macro-report-bundle-v1",
            bundle_id: "china-macro-rates-2026-07-20",
            title: "2026 中国宏观与利率策略",
            basis: "analytical" as const,
            as_of_date: "2026-07-20",
            curve_date: "2026-07-17",
            account_report_date: "2026-06-30",
            observation_only: true as const,
            formal_use_allowed: false as const,
            validation: {
              passed: 93,
              failed: 0,
              scope: "交付物一致性校验，不构成外部市场真值复核",
            },
            warnings: ["研究材料，只读观察，不构成正式指标或交易信号。"],
            artifacts: [
              {
                id: "full-report",
                filename: "report.pdf",
                label: "完整报告",
                kind: "report",
                media_type: "application/pdf",
                size_bytes: 3_182_018,
                sha256: "a".repeat(64),
              },
            ],
          },
        },
      }),
    } as ApiClient;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(<MacroToolkitPage />, {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </ApiClientProvider>
      ),
    });

    const panel = await screen.findByLabelText("宏观策略报告资产");
    expect(panel).toHaveTextContent("研究级只读");
    expect(panel).toHaveTextContent("非正式口径");
    expect(panel).toHaveTextContent("2026 中国宏观与利率策略");
  });
});
