import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type {
  KpiMetricWithValue,
  KpiOwnerListResponse,
  KpiValuesResponse,
} from "../api/contracts";
import { createApiClient, type ApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const kpiModalSourceFiles = [
  {
    name: "MetricEditModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/MetricEditModal.tsx"),
    rootClass: "kpi-modal-v2--edit",
  },
  {
    name: "BatchPasteModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/BatchPasteModal.tsx"),
    rootClass: "kpi-modal-v2--batch",
  },
  {
    name: "MetricManageModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/MetricManageModal.tsx"),
    rootClass: "kpi-modal-v2--manage",
  },
];

const kpiOwner = {
  owner_id: 1,
  owner_name: "固定收益部",
  org_unit: "金融市场部",
  person_name: null,
  year: 2026,
  scope_type: "department",
  scope_key: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

function kpiClientWithOwners(
  getKpiOwners: ApiClient["getKpiOwners"],
): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    getKpiOwners,
  };
}

function kpiMetricFixture(metricId: number, metricName: string, ownerId: number): KpiMetricWithValue {
  return {
    metric_id: metricId,
    metric_code: `M-${metricId}`,
    metric_name: metricName,
    major_category: "经营效益",
    owner_id: ownerId,
    year: 2026,
    target_value: "100",
    score_weight: "10",
    scoring_rule_type: "LINEAR_RATIO",
    data_source_type: "MANUAL",
    is_active: true,
  };
}

function kpiValuesResponse(ownerId: number, ownerName: string, metricName: string): KpiValuesResponse {
  return {
    owner_id: ownerId,
    owner_name: ownerName,
    as_of_date: "2026-08-14",
    metrics: [kpiMetricFixture(ownerId * 100 + 1, metricName, ownerId)],
    total: 1,
  };
}

describe("KpiPerformancePage", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("kpi");
  }, 20_000);

  it("exposes stable local layout hooks for the /kpi governance surface", async () => {
    const mockClient = createApiClient({ mode: "mock" });

    renderWorkbenchApp(["/kpi"], { client: mockClient });

    const page = await screen.findByTestId("kpi-performance-page");

    expect(page).toHaveClass("kpi-performance-page");
    expect(page).toHaveClass("moss-page-v2-shell");
    expect(within(page).getByTestId("kpi-performance-header")).toHaveClass(
      "moss-page-v2-decision-hero",
    );
    expect(within(page).getByTestId("kpi-performance-data-status")).toHaveClass(
      "moss-page-v2-data-status",
    );
    const filters = within(page).getByTestId("kpi-performance-filters");
    expect(filters.querySelector(".ant-card")).toBeNull();
    expect(within(page).getByTestId("kpi-performance-filter-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-action-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-main-grid")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-owner-list-panel")).toHaveClass(
      "kpi-owner-list-card",
    );
    expect(within(page).getByTestId("kpi-performance-empty-state")).toHaveClass(
      "moss-page-v2-state-surface",
    );
    expect(within(page).getByRole("combobox", { name: "KPI assessment year" })).toBeInTheDocument();
    expect(within(page).getByRole("combobox", { name: "KPI period type" })).toBeInTheDocument();
    expect(within(page).getByLabelText("KPI as-of date")).toBeInTheDocument();
    expect(
      await within(page).findByRole("textbox", { name: "搜索考核部室" }),
    ).toBeInTheDocument();
  });

  it("keeps populated detail and fetch-result layout surfaces local to /kpi", async () => {
    const user = userEvent.setup();
    const mockClient = createApiClient({ mode: "mock" });

    renderWorkbenchApp(["/kpi"], { client: mockClient });

    const page = await screen.findByTestId("kpi-performance-page");
    const ownerButton = await screen.findByRole("button", { name: /固定收益部/ });
    expect(ownerButton).toHaveAttribute("aria-pressed", "false");
    await user.click(ownerButton);
    expect(ownerButton).toHaveAttribute("aria-pressed", "true");

    expect(within(page).getByTestId("kpi-performance-detail-header")).toHaveClass(
      "kpi-performance-page__detail-header",
    );
    expect(within(page).getByTestId("kpi-performance-detail-header").closest(".kpi-performance-page__detail-card")).not.toBeNull();
    expect(within(page).getByTestId("kpi-metric-table-panel")).toHaveClass(
      "kpi-metric-table-card",
    );

    await user.click(within(page).getByRole("button", { name: /抓取并重算/ }));

    const fetchResult = await within(page).findByText(/共 0 个指标/);
    expect(fetchResult.closest(".kpi-performance-page__fetch-result")).not.toBeNull();
    expect(within(page).getByTestId("kpi-performance-fetch-result")).toHaveClass(
      "moss-page-v2-data-status",
    );
  });

  it("fails closed with a visible 502 reason and retries the owners request", async () => {
    const user = userEvent.setup();
    const getKpiOwners = vi
      .fn<ApiClient["getKpiOwners"]>()
      .mockRejectedValueOnce(new Error("KPI API 502"))
      .mockResolvedValueOnce({ owners: [kpiOwner], total: 1 });
    const client = kpiClientWithOwners(getKpiOwners);

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    const errorState = await within(page).findByTestId("kpi-owner-list-error-state");

    expect(errorState).toHaveAttribute("data-state-variant", "error");
    expect(errorState).toHaveTextContent("考核对象加载失败");
    expect(errorState).toHaveTextContent("KPI 服务返回 502");
    expect(within(page).queryByText("无匹配结果")).not.toBeInTheDocument();
    expect(page).not.toHaveTextContent("共 0 个部室");

    expect(within(page).getByRole("button", { name: "新增指标" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "批量导入" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "抓取并重算" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "导出 CSV" })).toBeEnabled();
    expect(within(page).getByRole("combobox", { name: "KPI assessment year" })).toBeEnabled();
    expect(within(page).getByRole("combobox", { name: "KPI period type" })).toBeEnabled();
    expect(within(page).getByLabelText("KPI as-of date")).toBeEnabled();

    await user.click(
      within(errorState).getByRole("button", { name: "重试加载考核对象" }),
    );

    expect(await within(page).findByRole("button", { name: /固定收益部/ })).toBeEnabled();
    expect(getKpiOwners).toHaveBeenCalledTimes(2);
    expect(within(page).queryByTestId("kpi-owner-list-error-state")).not.toBeInTheDocument();
  });

  it("shows the underlying network failure without leaking an internal stack", async () => {
    const client = kpiClientWithOwners(
      vi.fn<ApiClient["getKpiOwners"]>().mockRejectedValue(
        new TypeError("Failed to fetch"),
      ),
    );

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    const errorState = await within(page).findByTestId("kpi-owner-list-error-state");

    expect(errorState).toHaveTextContent("网络请求失败");
    expect(errorState).toHaveTextContent("Failed to fetch");
    expect(errorState).not.toHaveTextContent("at KpiPerformancePage");
    expect(within(page).queryByText("无匹配结果")).not.toBeInTheDocument();
    expect(page).not.toHaveTextContent("共 0 个部室");
  });

  it("keeps owner-dependent actions unavailable while owners are loading", async () => {
    const ownersRequest = deferred<KpiOwnerListResponse>();
    const client = kpiClientWithOwners(vi.fn(() => ownersRequest.promise));

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    const ownerState = within(page).getByTestId("kpi-owner-list-panel");

    expect(ownerState).toHaveAttribute("data-state-variant", "loading");
    expect(ownerState).toHaveAttribute("role", "status");
    expect(within(page).getByRole("button", { name: "新增指标" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "批量导入" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "抓取并重算" })).toBeDisabled();
    expect(within(page).getByRole("button", { name: "导出 CSV" })).toBeEnabled();
    expect(within(page).getByRole("combobox", { name: "KPI assessment year" })).toBeEnabled();
    expect(within(page).getByRole("combobox", { name: "KPI period type" })).toBeEnabled();
    expect(within(page).getByLabelText("KPI as-of date")).toBeEnabled();

    ownersRequest.resolve({ owners: [kpiOwner], total: 1 });
    expect(await within(page).findByRole("button", { name: /固定收益部/ })).toBeEnabled();
  });

  it("preserves the blocked authority disclosure for a structured empty response", async () => {
    const client = kpiClientWithOwners(
      vi.fn(async () => ({
        owners: [],
        total: 0,
        meta: {
          authority_status: "blocked",
          reason: "no-active-owners",
          owner_count: 0,
          year: 2026,
        },
      })),
    );

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    const emptyState = await within(page).findByTestId("kpi-owner-list-empty-state");

    expect(emptyState).toHaveAttribute("data-state-variant", "definition-pending");
    expect(emptyState).toHaveTextContent("权威考核对象尚未就绪");
    expect(emptyState).toHaveTextContent("治理状态：blocked");
    expect(emptyState).toHaveTextContent("原因：no-active-owners");
    expect(within(page).queryByText("无匹配结果")).not.toBeInTheDocument();
    expect(within(page).queryByTestId("kpi-owner-list-error-state")).not.toBeInTheDocument();
  });

  it("renders a successful zero-owner response as empty data, not a search miss or request error", async () => {
    const client = kpiClientWithOwners(
      vi.fn(async () => ({ owners: [], total: 0 })),
    );

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    const emptyState = await within(page).findByTestId("kpi-owner-list-empty-state");

    expect(emptyState).toHaveAttribute("data-state-variant", "empty");
    expect(emptyState).toHaveTextContent("当前年度暂无考核部室");
    expect(emptyState).toHaveTextContent("接口已正常返回 0 个考核对象");
    expect(emptyState).not.toHaveTextContent("治理状态");
    expect(within(page).queryByText("无匹配结果")).not.toBeInTheDocument();
    expect(within(page).queryByTestId("kpi-owner-list-error-state")).not.toBeInTheDocument();
  });

  it("discards stale metric responses when switching owners quickly", async () => {
    const user = userEvent.setup();
    const ownerA = kpiOwner;
    const ownerB = { ...kpiOwner, owner_id: 2, owner_name: "金融同业部" };
    const staleRequest = deferred<KpiValuesResponse>();
    const freshRequest = deferred<KpiValuesResponse>();
    const getKpiValues = vi.fn(({ owner_id }: { owner_id: number }) =>
      owner_id === ownerA.owner_id ? staleRequest.promise : freshRequest.promise,
    ) as unknown as ApiClient["getKpiValues"];
    const client = {
      ...createApiClient({ mode: "mock" }),
      getKpiOwners: vi.fn(async () => ({ owners: [ownerA, ownerB], total: 2 })),
      getKpiValues,
    } as ApiClient;

    renderWorkbenchApp(["/kpi"], { client });

    const page = await screen.findByTestId("kpi-performance-page");
    await user.click(await screen.findByRole("button", { name: /固定收益部/ }));
    await waitFor(() =>
      expect(getKpiValues).toHaveBeenCalledWith(expect.objectContaining({ owner_id: 1 })),
    );

    await user.click(screen.getByRole("button", { name: /金融同业部/ }));
    await waitFor(() =>
      expect(getKpiValues).toHaveBeenCalledWith(expect.objectContaining({ owner_id: 2 })),
    );

    // 后发请求先返回：新部室数据展示。
    freshRequest.resolve(kpiValuesResponse(2, "金融同业部", "同业负债日均"));
    expect(await within(page).findByText("同业负债日均")).toBeInTheDocument();

    // 先发请求后返回：过期响应必须被丢弃，不得覆盖新部室数据。
    staleRequest.resolve(kpiValuesResponse(1, "固定收益部", "过期指标不应显示"));
    await waitFor(() => expect(within(page).getByText("同业负债日均")).toBeInTheDocument());
    expect(within(page).queryByText("过期指标不应显示")).not.toBeInTheDocument();
  });

  it("defaults the as-of date to the local calendar day, not the UTC day", async () => {
    // UTC 2026-08-13 22:00 = UTC+8 的 2026-08-14 06:00：任何东侧时区下
    // toISOString() 会把默认截止日期偏到前一天。
    vi.setSystemTime(new Date("2026-08-13T22:00:00Z"));
    try {
      renderWorkbenchApp(["/kpi"], { client: createApiClient({ mode: "mock" }) });

      const dateInput = await screen.findByLabelText("KPI as-of date");
      const now = new Date();
      const expected = [
        String(now.getFullYear()),
        String(now.getMonth() + 1).padStart(2, "0"),
        String(now.getDate()).padStart(2, "0"),
      ].join("-");
      expect(dateInput).toHaveValue(expected);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps KPI modal visual shells class-based and tokenized", () => {
    const inlineStyleMarker = ["style", "="].join("");
    const privateShadowPattern = new RegExp(
      [
        ["box", "Shadow"].join(""),
        ["box", "-", "shadow"].join(""),
        ["rgba", "\\("].join(""),
      ].join("|"),
    );

    for (const modalFile of kpiModalSourceFiles) {
      const source = readFileSync(modalFile.path, "utf8");

      expect(source, `${modalFile.name} should not add inline style debt`).not.toContain(inlineStyleMarker);
      expect(source, `${modalFile.name} should not hard-code hex colors`).not.toMatch(/#[0-9a-fA-F]{3,8}/);
      expect(source, `${modalFile.name} should not add private shadows`).not.toMatch(privateShadowPattern);
      expect(source).toContain('rootClassName="kpi-modal-v2');
      expect(source).toContain(modalFile.rootClass);
    }
  });
});
