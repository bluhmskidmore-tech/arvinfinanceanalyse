import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ApiEnvelope, ResultMeta } from "../api/contracts";
import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";
import { summarizeAdvancedAttributionQuality } from "../features/pnl-attribution/components/pnlAttributionViewModel";

vi.mock("../lib/echarts", () => ({ default: () => <div /> }));

function resultMeta(kind: string, patch: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: `tr_${kind}`,
    basis: "formal",
    result_kind: kind,
    formal_use_allowed: true,
    source_version: `sv_${kind}`,
    vendor_version: "vv_none",
    rule_version: `rv_${kind}`,
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-03-31",
    generated_at: "2026-04-01T10:30:00Z",
    ...patch,
  };
}

function withMeta<Args extends unknown[], Payload>(
  read: (...args: Args) => Promise<ApiEnvelope<Payload>>,
  meta: ResultMeta,
) {
  return vi.fn(async (...args: Args) => ({ ...(await read(...args)), result_meta: meta }));
}

function clientWithQuality(source: "four" | "decision", sourcePatch: Partial<ResultMeta>) {
  const client = createApiClient({ mode: "mock" });
  const summaryMeta = Object.freeze(resultMeta("advanced_summary", { quality_flag: "warning" }));
  const childMeta = Object.freeze(resultMeta("campisi_quality_source", sourcePatch));
  client.getFormalPnlDates = vi.fn(async () => ({
    result_meta: resultMeta("pnl.dates"),
    result: { report_dates: ["2026-03-31"], formal_fi_report_dates: ["2026-03-31"], nonstd_bridge_report_dates: [] },
  }));
  client.getProductCategoryDates = vi.fn(async () => ({
    result_meta: resultMeta("product_category_pnl.dates"),
    result: { report_dates: ["2026-03-31"] },
  }));
  client.getPnlAdvancedAttributionSummary = withMeta(client.getPnlAdvancedAttributionSummary, summaryMeta);
  client.getPnlCarryRollDown = withMeta(client.getPnlCarryRollDown, resultMeta("carry"));
  client.getPnlSpreadAttribution = withMeta(client.getPnlSpreadAttribution, resultMeta("spread"));
  client.getPnlKrdAttribution = withMeta(client.getPnlKrdAttribution, resultMeta("krd"));
  client.getPnlCampisiFourEffects = withMeta(client.getPnlCampisiFourEffects, source === "four" ? childMeta : resultMeta("four"));
  client.getPnlCampisiEnhanced = withMeta(client.getPnlCampisiEnhanced, resultMeta("enhanced"));
  client.getPnlCampisiMaturityBuckets = withMeta(client.getPnlCampisiMaturityBuckets, resultMeta("maturity"));
  client.getPnlCampisiDecisionGrade = withMeta(client.getPnlCampisiDecisionGrade, source === "decision" ? childMeta : resultMeta("decision"));
  return { client, summaryMeta, childMeta };
}

describe("advanced attribution quality summary", () => {
  it("keeps an unloaded view pending", () => {
    expect(summarizeAdvancedAttributionQuality([null, null])).toEqual({ qualityFlag: null, fallbackLabel: "待加载" });
  });

  it.each([
    [["ok", "warning", "stale", "error"], "error"],
    [["warning", "stale", "ok"], "stale"],
    [["ok", "warning"], "warning"],
    [["ok", "missing"], "missing"],
    [["ok", "ok"], "ok"],
  ] as const)("shows the worst loaded quality in %s", (flags, expected) => {
    const metas = flags.map((quality_flag) => resultMeta("test", { quality_flag }));
    expect(summarizeAdvancedAttributionQuality([null, ...metas]).qualityFlag).toBe(expected);
  });

  it("distinguishes no fallback, partial fallback, and all loaded results using fallback", () => {
    const healthy = Object.freeze(resultMeta("summary"));
    const fallback = Object.freeze(resultMeta("four", { fallback_mode: "latest_snapshot", fallback_date: null }));
    expect(summarizeAdvancedAttributionQuality([healthy, null]).fallbackLabel).toBe("未降级");
    expect(summarizeAdvancedAttributionQuality([healthy, fallback]).fallbackLabel).toBe("部分数据降级");
    expect(summarizeAdvancedAttributionQuality([fallback, null]).fallbackLabel).toBe("已加载数据均降级");
    expect(fallback.fallback_date).toBeNull();
    expect(healthy.formal_use_allowed).toBe(true);
  });
});

describe("advanced attribution decision strip wiring", () => {
  it.each(["four", "decision"] as const)("includes %s quality without replacing summary evidence", async (source) => {
    const user = userEvent.setup();
    const { client, summaryMeta, childMeta } = clientWithQuality(source, {
      quality_flag: "error", vendor_status: "vendor_stale", fallback_mode: "latest_snapshot",
      fallback_date: "2026-03-27", formal_use_allowed: false,
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter><PnlAttributionPage /></MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );
    await screen.findByTestId("pnl-attribution-current-view-meta");
    await user.click(screen.getByRole("button", { name: "高级归因 + Campisi" }));
    const strip = screen.getByTestId("pnl-attribution-decision-strip");
    await waitFor(() => expect(strip).toHaveTextContent("部分数据降级"));
    expect(within(strip).getByText("错误")).toHaveAttribute("data-quality", "error");
    expect(strip).not.toHaveTextContent("未降级");
    expect(strip).toHaveTextContent("未允许正式使用");

    const summaryEvidence = screen.getByTestId("pnl-attribution-current-view-meta");
    expect(summaryEvidence).toHaveTextContent("tr_advanced_summary");
    expect(summaryEvidence).not.toHaveTextContent("tr_campisi_quality_source");
    expect(screen.getByTestId("pnl-attribution-advanced-view-meta")).toHaveTextContent("tr_campisi_quality_source");
    expect(summaryMeta.quality_flag).toBe("warning");
    expect(summaryMeta.fallback_mode).toBe("none");
    expect(summaryMeta.as_of_date).toBe("2026-03-31");
    expect(childMeta.fallback_date).toBe("2026-03-27");
    expect(childMeta.formal_use_allowed).toBe(false);

    await user.click(screen.getByTestId("pnl-attribution-tab-product-category"));
    await waitFor(() => expect(strip).toHaveTextContent("未降级"));
    expect(strip).not.toHaveTextContent("部分数据降级");
  });
});
