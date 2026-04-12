import { useState, type ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import * as pollingModule from "../app/jobs/polling";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta, SourcePreviewColumn, SourcePreviewSummary } from "../api/contracts";
import SourcePreviewPage from "../features/source-preview/pages/SourcePreviewPage";

function renderPage(client: ApiClient) {
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
    <Wrapper>
      <SourcePreviewPage />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string, sourceVersion: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "analytical" as const,
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: sourceVersion,
    vendor_version: "vv_none",
    rule_version: "rv_preview",
    cache_version: "cv_preview",
    quality_flag: "ok" as const,
    vendor_status: "ok" as const,
    fallback_mode: "none" as const,
    scenario_flag: false,
    generated_at: "2026-04-10T09:00:00Z",
  };
}

function buildColumn(
  key: string,
  label: string,
  type: "string" | "number" | "boolean",
) {
  return { key, label, type };
}

describe("SourcePreviewPage", () => {
  it("paginates drilldown, resets offsets, and avoids stale family/batch requests", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const foundationSources: SourcePreviewSummary[] = [
      {
        ingest_batch_id: "z-batch-3",
        batch_created_at: "2026-04-10T09:00:00Z",
        source_family: "zqtz",
        report_date: "2025-12-31",
        source_file: "ZQTZSHOW-20251231.xls",
        total_rows: 55,
        manual_review_count: 0,
        source_version: "sv_z_3",
        rule_version: "rv_preview",
        group_counts: { bond: 55 },
        preview_mode: "tabular",
      },
      {
        ingest_batch_id: "t-batch-2",
        batch_created_at: "2026-04-10T08:00:00Z",
        source_family: "tyw",
        report_date: "2025-12-31",
        source_file: "TYWLSHOW-20251231.xls",
        total_rows: 14,
        manual_review_count: 1,
        source_version: "sv_t_2",
        rule_version: "rv_preview",
        group_counts: { repo: 14 },
        preview_mode: "tabular",
      },
    ];

    const historyCalls: Array<{ sourceFamily?: string; limit: number; offset: number }> = [];
    const rowCalls: Array<{ sourceFamily: string; ingestBatchId: string; limit: number; offset: number }> = [];
    const traceCalls: Array<{ sourceFamily: string; ingestBatchId: string; limit: number; offset: number }> = [];

    const historyPages: Record<string, SourcePreviewSummary[]> = {
      zqtz: [
        {
          ingest_batch_id: "z-batch-3",
          batch_created_at: "2026-04-10T09:00:00Z",
          source_family: "zqtz",
          report_date: "2025-12-31",
          source_file: "ZQTZSHOW-20251231.xls",
          total_rows: 55,
          manual_review_count: 0,
          source_version: "sv_z_3",
          rule_version: "rv_preview",
          group_counts: {},
          preview_mode: "tabular",
        },
        {
          ingest_batch_id: "z-batch-2",
          batch_created_at: "2026-04-09T09:00:00Z",
          source_family: "zqtz",
          report_date: "2025-12-30",
          source_file: "ZQTZSHOW-20251230.xls",
          total_rows: 22,
          manual_review_count: 1,
          source_version: "sv_z_2",
          rule_version: "rv_preview",
          group_counts: {},
          preview_mode: "tabular",
        },
        {
          ingest_batch_id: "z-batch-1",
          batch_created_at: "2026-04-08T09:00:00Z",
          source_family: "zqtz",
          report_date: "2025-12-29",
          source_file: "ZQTZSHOW-20251229.xls",
          total_rows: 5,
          manual_review_count: 0,
          source_version: "sv_z_1",
          rule_version: "rv_preview",
          group_counts: {},
          preview_mode: "tabular",
        },
      ],
      tyw: [
        {
          ingest_batch_id: "t-batch-2",
          batch_created_at: "2026-04-10T08:00:00Z",
          source_family: "tyw",
          report_date: "2025-12-31",
          source_file: "TYWLSHOW-20251231.xls",
          total_rows: 14,
          manual_review_count: 1,
          source_version: "sv_t_2",
          rule_version: "rv_preview",
          group_counts: {},
          preview_mode: "tabular",
        },
        {
          ingest_batch_id: "t-batch-1",
          batch_created_at: "2026-04-09T08:00:00Z",
          source_family: "tyw",
          report_date: "2025-12-30",
          source_file: "TYWLSHOW-20251230.xls",
          total_rows: 9,
          manual_review_count: 0,
          source_version: "sv_t_1",
          rule_version: "rv_preview",
          group_counts: {},
          preview_mode: "tabular",
        },
      ],
    };

    const client = {
      ...base,
      getSourceFoundation: async () => ({
        result_meta: buildMeta("preview.source-foundation", "sv_foundation"),
        result: { sources: foundationSources },
      }),
      getSourceFoundationHistory: async ({
        sourceFamily,
        limit,
        offset,
      }: {
        sourceFamily?: string;
        limit: number;
        offset: number;
      }) => {
        historyCalls.push({ sourceFamily, limit, offset });
        const rows = sourceFamily ? historyPages[sourceFamily] ?? [] : [];
        return {
          result_meta: buildMeta("preview.source-foundation.history", `sv_hist_${sourceFamily ?? "none"}`),
          result: {
            limit,
            offset,
            total_rows: rows.length,
            rows: rows.slice(offset, offset + limit),
          },
        };
      },
      getSourceFoundationRows: async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => {
        rowCalls.push({ sourceFamily, ingestBatchId, limit, offset });
        return {
          result_meta: buildMeta(`preview.${sourceFamily}.rows`, `sv_rows_${ingestBatchId}`),
          result: {
            source_family: sourceFamily,
            ingest_batch_id: ingestBatchId,
            limit,
            offset,
            total_rows: sourceFamily === "zqtz" ? 55 : 14,
            columns: [
              buildColumn("ingest_batch_id", "批次ID", "string"),
              buildColumn("row_locator", "行号", "number"),
              buildColumn("report_date", "报告日期", "string"),
              buildColumn("business_type_primary", "业务种类1", "string"),
              buildColumn("instrument_name", "债券名称", "string"),
              buildColumn("counterparty_name", "对手方名称", "string"),
            ],
            rows: [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: offset + 1,
                report_date: "2025-12-31",
                business_type_primary: `${sourceFamily}-primary`,
                business_type_final: "final",
                asset_group: "group",
                product_group: "group",
                instrument_code: `${sourceFamily}-${offset + 1}`,
                instrument_name: `${ingestBatchId}-row-${offset + 1}`,
                counterparty_name: `${ingestBatchId}-row-${offset + 1}`,
                account_category: "acct",
                investment_portfolio: "portfolio",
                manual_review_needed: false,
              },
            ],
          },
        };
      },
      getSourceFoundationTraces: async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => {
        traceCalls.push({ sourceFamily, ingestBatchId, limit, offset });
        return {
          result_meta: buildMeta(`preview.${sourceFamily}.traces`, `sv_traces_${ingestBatchId}`),
          result: {
            source_family: sourceFamily,
            ingest_batch_id: ingestBatchId,
            limit,
            offset,
            total_rows: sourceFamily === "zqtz" ? 44 : 8,
            rows: [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: offset + 1,
                trace_step: 1,
                field_name: `${sourceFamily}-field-${offset + 1}`,
                field_value: "value",
                derived_label: `${ingestBatchId}-trace-${offset + 1}`,
                manual_review_needed: false,
              },
            ],
          },
        };
      },
    } as unknown as ApiClient;

    renderPage(client);

    expect(await screen.findByRole("combobox", { name: "source-family" })).toBeInTheDocument();
    expect(await screen.findByRole("combobox", { name: "ingest-batch" })).toBeInTheDocument();

    await waitFor(() => {
      expect(historyCalls).toContainEqual({ sourceFamily: "zqtz", limit: 2, offset: 0 });
    });
    expect(screen.getByTestId("source-preview-history-page")).toHaveTextContent("1 / 2");
    await waitFor(() => {
      expect(rowCalls).toContainEqual({
        sourceFamily: "zqtz",
        ingestBatchId: "z-batch-3",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-rows-page")).toHaveTextContent("1 / 3");
    await waitFor(() => {
      expect(traceCalls).toContainEqual({
        sourceFamily: "zqtz",
        ingestBatchId: "z-batch-3",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-traces-page")).toHaveTextContent("1 / 3");

    await user.click(screen.getByTestId("source-preview-rows-next"));
    await user.click(screen.getByTestId("source-preview-traces-next"));
    await user.click(screen.getByTestId("source-preview-history-next"));

    await waitFor(() => {
      expect(historyCalls).toContainEqual({ sourceFamily: "zqtz", limit: 2, offset: 2 });
    });
    expect(screen.getByTestId("source-preview-history-page")).toHaveTextContent("2 / 2");
    await waitFor(() => {
      expect(rowCalls).toContainEqual({
        sourceFamily: "zqtz",
        ingestBatchId: "z-batch-1",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-rows-page")).toHaveTextContent("1 / 3");
    await waitFor(() => {
      expect(traceCalls).toContainEqual({
        sourceFamily: "zqtz",
        ingestBatchId: "z-batch-1",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-traces-page")).toHaveTextContent("1 / 3");

    await user.selectOptions(screen.getByRole("combobox", { name: "source-family" }), "tyw");

    await waitFor(() => {
      expect(historyCalls).toContainEqual({ sourceFamily: "tyw", limit: 2, offset: 0 });
    });
    expect(screen.getByTestId("source-preview-history-page")).toHaveTextContent("1 / 1");
    await waitFor(() => {
      expect(rowCalls).toContainEqual({
        sourceFamily: "tyw",
        ingestBatchId: "t-batch-2",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-rows-page")).toHaveTextContent("1 / 1");
    await waitFor(() => {
      expect(traceCalls).toContainEqual({
        sourceFamily: "tyw",
        ingestBatchId: "t-batch-2",
        limit: 20,
        offset: 0,
      });
    });
    expect(screen.getByTestId("source-preview-traces-page")).toHaveTextContent("1 / 1");
    expect(
      rowCalls.some(
        (call) =>
          call.sourceFamily === "tyw" &&
          (call.ingestBatchId === "z-batch-1" || call.offset !== 0),
      ),
    ).toBe(false);
    expect(
      traceCalls.some(
        (call) =>
          call.sourceFamily === "tyw" &&
          (call.ingestBatchId === "z-batch-1" || call.offset !== 0),
      ),
    ).toBe(false);
  });

  it("renders only the latest in-flight family selection result", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const foundationSources: SourcePreviewSummary[] = [
      {
        ingest_batch_id: "z-batch-1",
        batch_created_at: "2026-04-10T09:00:00Z",
        source_family: "zqtz",
        report_date: "2025-12-31",
        source_file: "ZQTZSHOW-20251231.xls",
        total_rows: 10,
        manual_review_count: 0,
        source_version: "sv_z_1",
        rule_version: "rv_preview",
        group_counts: { bond: 10 },
        preview_mode: "tabular",
      },
      {
        ingest_batch_id: "t-batch-1",
        batch_created_at: "2026-04-10T08:00:00Z",
        source_family: "tyw",
        report_date: "2025-12-31",
        source_file: "TYWLSHOW-20251231.xls",
        total_rows: 8,
        manual_review_count: 0,
        source_version: "sv_t_1",
        rule_version: "rv_preview",
        group_counts: { repo: 8 },
        preview_mode: "tabular",
      },
    ];

    type SourceRowsResponse = {
      result_meta: ReturnType<typeof buildMeta>;
      result: {
        source_family: string;
        ingest_batch_id: string;
        limit: number;
        offset: number;
        total_rows: number;
        columns: SourcePreviewColumn[];
        rows: Array<Record<string, unknown>>;
      };
    };

    let resolveZqtzRows: (value: SourceRowsResponse) => void = () => {
      throw new Error("resolveZqtzRows was not initialized");
    };

    const client = {
      ...base,
      getSourceFoundation: async () => ({
        result_meta: buildMeta("preview.source-foundation", "sv_foundation"),
        result: { sources: foundationSources },
      }),
      getSourceFoundationHistory: async ({
        sourceFamily,
        limit,
        offset,
      }: {
        sourceFamily?: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta("preview.source-foundation.history", `sv_hist_${sourceFamily ?? "none"}`),
        result: {
          limit,
          offset,
          total_rows: 1,
          rows:
            sourceFamily === "tyw"
              ? [foundationSources[1]]
              : [foundationSources[0]],
        },
      }),
      getSourceFoundationRows: ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => {
        if (sourceFamily === "zqtz") {
          return new Promise<SourceRowsResponse>((resolve) => {
            resolveZqtzRows = resolve;
          });
        }

        return Promise.resolve({
          result_meta: buildMeta("preview.tyw.rows", "sv_rows_t"),
          result: {
            source_family: sourceFamily,
            ingest_batch_id: ingestBatchId,
            limit,
            offset,
            total_rows: 1,
            columns: [
              buildColumn("ingest_batch_id", "批次ID", "string"),
              buildColumn("row_locator", "行号", "number"),
              buildColumn("report_date", "报告日期", "string"),
              buildColumn("business_type_primary", "业务种类1", "string"),
              buildColumn("counterparty_name", "对手方名称", "string"),
              buildColumn("manual_review_needed", "需人工复核", "boolean"),
            ],
            rows: [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "tyw-primary",
                product_group: "repo",
                counterparty_name: "TYW-LATEST",
                manual_review_needed: false,
              },
            ],
          },
        });
      },
      getSourceFoundationTraces: async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta(`preview.${sourceFamily}.traces`, `sv_traces_${ingestBatchId}`),
        result: {
          source_family: sourceFamily,
          ingest_batch_id: ingestBatchId,
          limit,
          offset,
          total_rows: 1,
          rows: [
            {
              ingest_batch_id: ingestBatchId,
              row_locator: 1,
              trace_step: 1,
              field_name: `${sourceFamily}-field`,
              field_value: "value",
              derived_label: `${ingestBatchId}-trace`,
              manual_review_needed: false,
            },
          ],
        },
      }),
    } as unknown as ApiClient;

    renderPage(client);

    expect(await screen.findByRole("combobox", { name: "source-family" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "source-family" })).toHaveTextContent("tyw");
    });
    await user.selectOptions(screen.getByRole("combobox", { name: "source-family" }), "tyw");

    expect(await screen.findByText("TYW-LATEST")).toBeInTheDocument();

    resolveZqtzRows({
      result_meta: buildMeta("preview.zqtz.rows", "sv_rows_z"),
      result: {
        source_family: "zqtz",
        ingest_batch_id: "z-batch-1",
        limit: 20,
        offset: 0,
        total_rows: 1,
        columns: [
          buildColumn("ingest_batch_id", "批次ID", "string"),
          buildColumn("row_locator", "行号", "number"),
          buildColumn("report_date", "报告日期", "string"),
          buildColumn("business_type_primary", "业务种类1", "string"),
          buildColumn("instrument_name", "债券名称", "string"),
          buildColumn("manual_review_needed", "需人工复核", "boolean"),
        ],
        rows: [
          {
            ingest_batch_id: "z-batch-1",
            row_locator: 1,
            report_date: "2025-12-31",
            business_type_primary: "zqtz-primary",
            instrument_name: "STALE-ZQTZ",
            manual_review_needed: false,
          },
        ],
      },
    });

    await waitFor(() => {
      expect(screen.getByText("TYW-LATEST")).toBeInTheDocument();
    });
    expect(screen.queryByText("STALE-ZQTZ")).not.toBeInTheDocument();
  });

  it("renders generic row-table headers from backend columns metadata", async () => {
    const base = createApiClient({ mode: "mock" });
    const client = {
      ...base,
      getSourceFoundation: async () => ({
        result_meta: buildMeta("preview.source-foundation", "sv_foundation"),
        result: {
          sources: [
            {
              ingest_batch_id: "z-batch-1",
              batch_created_at: "2026-04-10T09:00:00Z",
              source_family: "zqtz",
              report_date: "2025-12-31",
              source_file: "ZQTZSHOW-20251231.xls",
              total_rows: 1,
              manual_review_count: 0,
              source_version: "sv_z_1",
              rule_version: "rv_preview",
              group_counts: { bond: 1 },
              preview_mode: "tabular",
            },
          ],
        },
      }),
      getSourceFoundationHistory: async ({ limit, offset }: { limit: number; offset: number }) => ({
        result_meta: buildMeta("preview.source-foundation.history", "sv_hist"),
        result: {
          limit,
          offset,
          total_rows: 1,
          rows: [
            {
              ingest_batch_id: "z-batch-1",
              batch_created_at: "2026-04-10T09:00:00Z",
              source_family: "zqtz",
              report_date: "2025-12-31",
              source_file: "ZQTZSHOW-20251231.xls",
              total_rows: 1,
              manual_review_count: 0,
              source_version: "sv_z_1",
              rule_version: "rv_preview",
              group_counts: {},
              preview_mode: "tabular",
            },
          ],
        },
      }),
      getSourceFoundationRows: async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta(`preview.${sourceFamily}.rows`, "sv_rows"),
        result: {
          source_family: sourceFamily,
          ingest_batch_id: ingestBatchId,
          limit,
          offset,
          total_rows: 1,
          columns: [
            buildColumn("row_locator", "行号", "number"),
            buildColumn("instrument_name", "债券名称", "string"),
            buildColumn("business_type_primary", "业务种类1", "string"),
            buildColumn("manual_review_needed", "需人工复核", "boolean"),
          ],
          rows: [
            {
              row_locator: 1,
              instrument_name: "COLUMN-DRIVEN-ZQTZ",
              business_type_primary: "债券类",
              manual_review_needed: false,
            },
          ],
        },
      }),
      getSourceFoundationTraces: async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta(`preview.${sourceFamily}.traces`, "sv_traces"),
        result: {
          source_family: sourceFamily,
          ingest_batch_id: ingestBatchId,
          limit,
          offset,
          total_rows: 1,
          columns: [
            buildColumn("ingest_batch_id", "批次ID", "string"),
            buildColumn("row_locator", "行号", "number"),
            buildColumn("trace_step", "轨迹步骤", "number"),
            buildColumn("field_name", "字段名", "string"),
            buildColumn("field_value", "字段值", "string"),
            buildColumn("derived_label", "归类标签", "string"),
            buildColumn("manual_review_needed", "需人工复核", "boolean"),
          ],
          rows: [
            {
              ingest_batch_id: ingestBatchId,
              row_locator: 1,
              trace_step: 1,
              field_name: "业务种类1",
              field_value: "其他债券",
              derived_label: "债券类",
              manual_review_needed: false,
            },
          ],
        },
      }),
    } as unknown as ApiClient;

    renderPage(client);

    const rowsTable = await screen.findByTestId("source-preview-rows-table");
    expect(rowsTable).toBeInTheDocument();
    expect(within(rowsTable).getByRole("columnheader", { name: "行号" })).toBeInTheDocument();
    expect(within(rowsTable).getByRole("columnheader", { name: "债券名称" })).toBeInTheDocument();
    expect(within(rowsTable).getByRole("cell", { name: "COLUMN-DRIVEN-ZQTZ" })).toBeInTheDocument();
    expect(within(rowsTable).getByRole("cell", { name: "false" })).toBeInTheDocument();
    const tracesTable = screen.getByTestId("source-preview-traces-table");
    expect(tracesTable).toBeInTheDocument();
    expect(within(tracesTable).getByRole("columnheader", { name: "轨迹步骤" })).toBeInTheDocument();
    expect(within(tracesTable).getByRole("columnheader", { name: "字段名" })).toBeInTheDocument();
    expect(within(tracesTable).getByRole("cell", { name: "业务种类1" })).toBeInTheDocument();
  });

  it("polls source preview refresh status and shows the latest run id", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const sourceFoundationSpy = vi.fn(async () => ({
      result_meta: buildMeta("preview.source-foundation", "sv_foundation"),
      result: {
        sources: [
          {
            ingest_batch_id: "batch-1",
            batch_created_at: "2026-04-10T09:00:00Z",
            source_family: "zqtz",
            report_date: "2025-12-31",
            source_file: "ZQTZSHOW-20251231.xls",
            total_rows: 1,
            manual_review_count: 0,
            source_version: "sv_z_1",
            rule_version: "rv_preview",
            group_counts: { bond: 1 },
            preview_mode: "tabular",
          },
        ],
      },
    }));
    const historySpy = vi.fn(async ({ limit, offset }: { limit: number; offset: number }) => ({
      result_meta: buildMeta("preview.source-foundation.history", "sv_hist"),
      result: {
        limit,
        offset,
        total_rows: 1,
        rows: [
          {
            ingest_batch_id: "batch-1",
            batch_created_at: "2026-04-10T09:00:00Z",
            source_family: "zqtz",
            report_date: "2025-12-31",
            source_file: "ZQTZSHOW-20251231.xls",
            total_rows: 1,
            manual_review_count: 0,
            source_version: "sv_z_1",
            rule_version: "rv_preview",
            group_counts: {},
            preview_mode: "tabular",
          },
        ],
      },
    }));
    const rowsSpy = vi.fn(
      async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta(`preview.${sourceFamily}.rows`, "sv_rows"),
        result: {
          source_family: sourceFamily,
          ingest_batch_id: ingestBatchId,
          limit,
          offset,
          total_rows: 1,
          columns: [buildColumn("row_locator", "行号", "number")],
          rows: [{ row_locator: 1 }],
        },
      }),
    );
    const tracesSpy = vi.fn(
      async ({
        sourceFamily,
        ingestBatchId,
        limit,
        offset,
      }: {
        sourceFamily: string;
        ingestBatchId: string;
        limit: number;
        offset: number;
      }) => ({
        result_meta: buildMeta(`preview.${sourceFamily}.traces`, "sv_traces"),
        result: {
          source_family: sourceFamily,
          ingest_batch_id: ingestBatchId,
          limit,
          offset,
          total_rows: 1,
          columns: [buildColumn("trace_step", "轨迹步骤", "number")],
          rows: [{ trace_step: 1 }],
        },
      }),
    );
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "source_preview_refresh:test-run",
      job_name: "source_preview_refresh",
      trigger_mode: "async",
      cache_key: "source_preview.foundation",
      preview_sources: ["zqtz", "tyw"],
    }));
    const statusSpy = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "source_preview_refresh:test-run",
        job_name: "source_preview_refresh",
        trigger_mode: "async",
        cache_key: "source_preview.foundation",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "source_preview_refresh:test-run",
        job_name: "source_preview_refresh",
        trigger_mode: "terminal",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
        ingest_batch_id: "ib_preview_refresh",
        source_version: "sv_preview_refresh",
      });

    renderPage({
      ...base,
      getSourceFoundation: sourceFoundationSpy,
      getSourceFoundationHistory: historySpy,
      getSourceFoundationRows: rowsSpy,
      getSourceFoundationTraces: tracesSpy,
      refreshSourcePreview: refreshSpy,
      getSourcePreviewRefreshStatus: statusSpy,
    });

    await screen.findByTestId("source-preview-rows-table");
    await user.click(screen.getByTestId("source-preview-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(statusSpy).toHaveBeenCalledWith("source_preview_refresh:test-run");
      expect(sourceFoundationSpy).toHaveBeenCalledTimes(2);
      expect(historySpy).toHaveBeenCalledTimes(2);
      expect(rowsSpy).toHaveBeenCalledTimes(2);
      expect(tracesSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("source-preview-refresh-run-id")).toHaveTextContent(
        "source_preview_refresh:test-run",
      );
      expect(screen.getByTestId("source-preview-refresh-status")).toHaveTextContent(
        /最近结果：completed/,
      );
    });
  });

  it("shows backend failure detail and preserves the run id when source preview refresh fails", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "source_preview_refresh:failed-run",
      job_name: "source_preview_refresh",
      trigger_mode: "async",
      cache_key: "source_preview.foundation",
    }));
    const statusSpy = vi.fn(async () => ({
      status: "failed",
      run_id: "source_preview_refresh:failed-run",
      job_name: "source_preview_refresh",
      trigger_mode: "terminal",
      cache_key: "source_preview.foundation",
      error_message: "Source preview refresh queue dispatch failed.",
    }));

    renderPage({
      ...base,
      refreshSourcePreview: refreshSpy,
      getSourcePreviewRefreshStatus: statusSpy,
    });

    await screen.findByTestId("source-preview-refresh-button");
    await user.click(screen.getByTestId("source-preview-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("source-preview-refresh-run-id")).toHaveTextContent(
        "source_preview_refresh:failed-run",
      );
      expect(screen.getByTestId("source-preview-refresh-status")).toHaveTextContent(
        "最近结果：failed",
      );
      expect(
        screen.getByText(/Source preview refresh queue dispatch failed\./),
      ).toBeInTheDocument();
    });
  });

  it("preserves the last known refresh state when polling times out", async () => {
    const user = userEvent.setup();
    const pollingSpy = vi
      .spyOn(pollingModule, "runPollingTask")
      .mockImplementation(async (options) => {
        options.onUpdate?.({
          status: "running",
          run_id: "source_preview_refresh:timeout-run",
        } as never);
        throw new Error("任务轮询超时");
      });

    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByTestId("source-preview-refresh-button");
    await user.click(screen.getByTestId("source-preview-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("source-preview-refresh-run-id")).toHaveTextContent(
        "source_preview_refresh:timeout-run",
      );
      expect(screen.getByTestId("source-preview-refresh-status")).toHaveTextContent(
        "最近结果：running",
      );
      expect(screen.getByText(/任务轮询超时/)).toBeInTheDocument();
    });

    pollingSpy.mockRestore();
  });
});


