import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
} from "../api/client";
import type { ApiEnvelope, PlaceholderSnapshot, ResultMeta } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import WorkbenchPlaceholderPage from "../features/workbench/pages/WorkbenchPlaceholderPage";

const meta: ResultMeta = {
  trace_id: "test_trace",
  basis: "mock",
  result_kind: "workbench.test",
  formal_use_allowed: false,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-09T10:30:00Z",
};

function envelope(result: PlaceholderSnapshot): ApiEnvelope<PlaceholderSnapshot> {
  return { result_meta: meta, result };
}

function renderPage(
  path: string,
  client: ApiClient,
  queryClient?: QueryClient,
) {
  const qc =
    queryClient ??
    new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0 } },
    });

  const router = createMemoryRouter(
    [
      {
        path: "/risk-overview",
        element: <WorkbenchPlaceholderPage />,
      },
    ],
    { initialEntries: [path], future: routerFuture },
  );

  return render(
    <QueryClientProvider client={qc}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("WorkbenchPlaceholderPage", () => {
  it("shows loading then snapshot content", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getPlaceholderSnapshot: vi.fn(async () => {
        await new Promise((r) => setTimeout(r, 30));
        return envelope({
          title: "风险总览",
          summary: "摘要行",
          highlights: ["点一"],
        });
      }),
    };

    renderPage("/risk-overview", client);

    expect(await screen.findByText("正在载入模块说明")).toBeInTheDocument();
    expect(await screen.findByText("摘要行")).toBeInTheDocument();
    expect(screen.getByText("规划要点 1")).toBeInTheDocument();
  });

  it("shows error and retries", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getPlaceholderSnapshot: vi
        .fn()
        .mockRejectedValueOnce(new Error("boom"))
        .mockResolvedValueOnce(
          envelope({
            title: "风险总览",
            summary: "恢复后",
            highlights: [],
          }),
        ),
    };

    renderPage("/risk-overview", client);

    expect(await screen.findByText("数据载入失败。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("恢复后")).toBeInTheDocument();
  });

  it("shows empty state when snapshot has no usable fields", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getPlaceholderSnapshot: vi.fn(async () =>
        envelope({ title: "风险总览", summary: "", highlights: [] }),
      ),
    };

    renderPage("/risk-overview", client);

    expect(
      await screen.findByText("当前暂无可展示内容。"),
    ).toBeInTheDocument();
  });
});


