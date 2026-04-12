import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { HealthResponse, ResultMeta, SourcePreviewPayload } from "../api/contracts";
import PlatformConfigPage from "../features/platform-config/PlatformConfigPage";

function renderPlatformConfig(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <MemoryRouter>
      <Wrapper>
        <PlatformConfigPage />
      </Wrapper>
    </MemoryRouter>,
  );
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_platform_test",
    vendor_version: "vv_none",
    rule_version: "rv_platform_test",
    cache_version: "cv_platform_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

describe("PlatformConfigPage", () => {
  it("renders health cards and source table from getHealth / getSourceFoundation", async () => {
    const base = createApiClient({ mode: "mock" });

    const health: HealthResponse & { environment?: string } = {
      status: "degraded",
      environment: "test",
      checks: {
        duckdb: { ok: false, detail: "duck offline" },
        redis: { ok: true, detail: "pong" },
        postgresql: { ok: true, detail: "up" },
        object_store: { ok: false, detail: "bucket unreachable" },
      },
    };

    const sourcesPayload: SourcePreviewPayload = {
      sources: [
        {
          source_family: "zqtz",
          report_date: "2025-12-31",
          source_file: "Z.xlsx",
          total_rows: 1500,
          manual_review_count: 0,
          source_version: "sv_zqtz_test",
          rule_version: "rv_test",
          group_counts: {},
          ingest_batch_id: "batch-z",
          batch_created_at: "2026-04-10T01:00:00Z",
        },
        {
          source_family: "tyw",
          report_date: null,
          source_file: "T.xls",
          total_rows: 100,
          manual_review_count: 3,
          source_version: "sv_tyw",
          rule_version: "rv_t",
          group_counts: {},
          ingest_batch_id: "batch-t",
          batch_created_at: "2026-04-11T02:00:00Z",
        },
      ],
    };

    const getHealth = vi.fn(async () => health);
    const getSourceFoundation = vi.fn(async () => ({
      result_meta: buildMeta("preview.source-foundation", "tr_src_foundation"),
      result: sourcesPayload,
    }));

    renderPlatformConfig({
      ...base,
      getHealth,
      getSourceFoundation,
    });

    expect(await screen.findByRole("heading", { name: "中台配置" })).toBeInTheDocument();
    expect(screen.getByText("系统健康状态、数据源概览与治理信息。")).toBeInTheDocument();

    expect(await screen.findByText("DuckDB 状态")).toBeInTheDocument();
    expect(screen.getByText("Redis 状态")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL 状态")).toBeInTheDocument();
    expect(screen.getByText("系统环境")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();

    const sourcesTable = await screen.findByTestId("platform-config-sources-table");
    expect(sourcesTable).toHaveTextContent("ZQTZ");
    expect(sourcesTable).toHaveTextContent("batch-z");
    expect(sourcesTable).toHaveTextContent("1500");
    expect(sourcesTable).toHaveTextContent("2026-04-10T01:00:00Z");
    expect(sourcesTable).toHaveTextContent("TYW");
    expect(sourcesTable).toHaveTextContent("异常");

    await waitFor(() => {
      expect(getHealth).toHaveBeenCalled();
      expect(getSourceFoundation).toHaveBeenCalled();
    });
  });
});
