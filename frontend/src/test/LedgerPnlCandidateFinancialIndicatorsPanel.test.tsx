import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createHash } from "node:crypto";
import { StrictMode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient, type ApiClient } from "../api/client";
import { LedgerPnlCandidateFinancialIndicatorsPanel } from "../features/ledger-pnl/components/LedgerPnlCandidateFinancialIndicatorsPanel";

function renderPanel(
  client: ApiClient,
  reportMonth = "202606",
  currency: "CNX" | "CNY" = "CNX",
  strictMode = false,
) {
  const panel = (
    <AppProviders client={client}>
      <LedgerPnlCandidateFinancialIndicatorsPanel
        reportMonth={reportMonth}
        currency={currency}
      />
    </AppProviders>
  );
  return render(strictMode ? <StrictMode>{panel}</StrictMode> : panel);
}

async function openAnalysisView() {
  fireEvent.click(await screen.findByRole("tab", { name: /^经营分析/ }));
}

function canonicalizeResolutionJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalizeResolutionJson);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
      .map(([key, item]) => [key, canonicalizeResolutionJson(item)]),
  );
}

async function buildDryRunReceipt(
  baseClient: ApiClient,
  options: { mismatchIds?: boolean; manualOverrideCount?: number } = {},
) {
  const base = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
  const requirements = base.result.promotion_readiness.evidence_pack.owner_requirements;
  const resultPackKey = "c".repeat(64);
  const receipt = {
    contract_version: "candidate-financial-indicator-revalidation-v1" as const,
    revalidation_effect: "none" as const,
    persisted: false as const,
    formal_use_allowed: false as const,
    base_candidate_idempotency_key: base.result.idempotency_key,
    base_evidence_pack_key: base.result.promotion_readiness.evidence_pack.evidence_pack_key,
    manual_override_count: options.manualOverrideCount ?? 0,
    requirement_resolution: {
      contract_version: "candidate-promotion-resolution-v1" as const,
      resolution_key: "d".repeat(64),
      base_evidence_pack_key: base.result.promotion_readiness.evidence_pack.evidence_pack_key,
      result_evidence_pack_key: resultPackKey,
      base_requirement_ids: options.mismatchIds
        ? requirements.slice(1).map((item) => item.requirement_id)
        : requirements.map((item) => item.requirement_id),
      requirements: requirements.map((item, index) => ({
        requirement_id: item.requirement_id,
        status: index === 1
          ? "evidence_received" as const
          : index === 2
            ? "validation_failed" as const
            : "awaiting_owner_input" as const,
        status_detail: index === 1 ? "已收到凭证，等待证据核验。" : "仍待补充或校验。",
        submitted_evidence_refs: index === 1 ? ["voucher://202606/r010"] : [],
        validation_evidence_refs: index === 2 ? ["validation://manual/r011"] : [],
      })),
    },
    result: {
      ...base,
      result: {
        ...base.result,
        promotion_readiness: {
          ...base.result.promotion_readiness,
          evidence_pack: {
            ...base.result.promotion_readiness.evidence_pack,
            evidence_pack_key: resultPackKey,
          },
        },
        metrics: base.result.metrics.map((metric, index) => (
          index === 0 ? { ...metric, value: "999.99" } : metric
        )),
      },
    },
  };
  const { resolution_key: _ignored, ...resolutionPayload } = receipt.requirement_resolution;
  receipt.requirement_resolution.resolution_key = createHash("sha256")
    .update(JSON.stringify(canonicalizeResolutionJson(resolutionPayload)), "utf8")
    .digest("hex");
  return receipt;
}

async function buildCurrentSourceImpactResponse(baseClient: ApiClient) {
  const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
  return {
    ...response,
    result: {
      ...response.result,
      rule_version: "qdb-finance-2026-v1.0.1",
      source_version_impact: {
        contract_version: "candidate-source-version-impact-v1",
        impact_asset_sha256: "b".repeat(64),
        status: "numerically_unchanged",
        comparison_basis: "canonical_decimal_value",
        report_month: "202606",
        reference_rule_version: "qdb-finance-2026-v1.0.0",
        current_rule_version: "qdb-finance-2026-v1.0.1",
        reference_result_sha256: "c".repeat(64),
        reference_ledger_sha256: "d".repeat(64),
        current_ledger_sha256: "e".repeat(64),
        daily_sha256: "f".repeat(64),
        metric_total: 186,
        compared_metric_count: 186,
        reference_numeric_digest: "1".repeat(64),
        current_numeric_digest: "1".repeat(64),
        numeric_changed_count: 0,
        serialization_only_count: 8,
        serialization_only_metric_ids: response.result.metrics
          .slice(0, 8)
          .map((item) => item.metric_id),
        formal_use_allowed: false,
        certification_effect: "none",
      },
      promotion_readiness: {
        ...response.result.promotion_readiness,
        evidence_pack: {
          ...response.result.promotion_readiness.evidence_pack,
          rule_version: "qdb-finance-2026-v1.0.1",
        },
      },
    },
  } as unknown as typeof response;
}

describe("LedgerPnlCandidateFinancialIndicatorsPanel", () => {
  it("disables dry-run revalidation for demo data with a direct Chinese explanation", async () => {
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    expect(within(section).getByText("演示数据不支持本次核验，请切换真实 API")).toBeInTheDocument();
    expect(within(section).getByRole("textbox", { name: "手工覆盖 JSON" })).toBeDisabled();
    expect(within(section).getByRole("button", { name: "运行本次核验（不保存）" })).toBeDisabled();
  });

  it("runs a non-persisted revalidation with base keys bound from the current payload", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient, { manualOverrideCount: 1 });
    const revalidate = vi.fn(async () => receipt);
    const client = { ...baseClient, mode: "real" as const, revalidateLedgerPnlCandidateFinancialIndicators: revalidate };

    renderPanel(client);

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    expect(within(section).getByText(/刷新页面后丢失/)).toBeInTheDocument();
    expect(within(section).queryByRole("textbox", { name: /候选幂等键|证据包键/ })).not.toBeInTheDocument();
    fireEvent.change(within(section).getByRole("textbox", { name: "手工覆盖 JSON" }), {
      target: { value: JSON.stringify({
        "input.adjustment.noninterest.r010": {
          value_yi: "0",
          submitted_evidence_refs: ["voucher://202606/r010"],
        },
      }) },
    });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(revalidate).toHaveBeenCalledWith("202606", {
      base_candidate_idempotency_key: receipt.base_candidate_idempotency_key,
      base_evidence_pack_key: receipt.base_evidence_pack_key,
      manual_overrides: {
        "input.adjustment.noninterest.r010": {
          value_yi: "0",
          submitted_evidence_refs: ["voucher://202606/r010"],
        },
      },
    });
    expect(await within(section).findByText("本次结果 · 未保存")).toBeInTheDocument();
    expect(screen.getByText(/已补·待证据核验 1/)).toBeInTheDocument();
    expect(screen.getByText(/校验失败 1/)).toBeInTheDocument();
    expect(screen.getAllByText("999.99").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /批准|上传|提交审批|确认审批/ })).not.toBeInTheDocument();
  });

  it("keeps invalid JSON recoverable without calling the backend", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const revalidate = vi.fn();
    renderPanel({ ...baseClient, mode: "real" as const, revalidateLedgerPnlCandidateFinancialIndicators: revalidate });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.clear(within(section).getByRole("textbox", { name: "手工覆盖 JSON" }));
    await user.type(within(section).getByRole("textbox", { name: "手工覆盖 JSON" }), "not json");
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(await within(section).findByRole("alert")).toHaveTextContent("JSON");
    expect(revalidate).not.toHaveBeenCalled();
  });

  it("clears a successful in-memory result as soon as the JSON input changes", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    renderPanel({
      ...baseClient,
      mode: "real" as const,
      revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
    });
    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));
    expect(await within(section).findByText("本次结果 · 未保存")).toBeInTheDocument();

    fireEvent.change(within(section).getByRole("textbox", { name: "手工覆盖 JSON" }), {
      target: { value: '{"input.adjustment.noninterest.r010":{"value_yi":"1","submitted_evidence_refs":["voucher://changed"]}}' },
    });

    expect(within(section).queryByText("本次结果 · 未保存")).not.toBeInTheDocument();
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("clears the prior successful result before a later request fails", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    const revalidate = vi.fn()
      .mockResolvedValueOnce(receipt)
      .mockRejectedValueOnce(new Error("Request failed: candidate revalidation (422)"));
    renderPanel({ ...baseClient, mode: "real" as const, revalidateLedgerPnlCandidateFinancialIndicators: revalidate });
    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    const run = within(section).getByRole("button", { name: "运行本次核验（不保存）" });
    await user.click(run);
    expect(await within(section).findByText("本次结果 · 未保存")).toBeInTheDocument();

    await user.click(run);
    expect(await within(section).findByRole("alert")).toHaveTextContent("422");
    expect(within(section).queryByText("本次结果 · 未保存")).not.toBeInTheDocument();
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("disables the dry-run controls while revalidation is pending", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderPanel({
      ...baseClient,
      mode: "real" as const,
      revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(
        () => new Promise<never>(() => undefined),
      ),
    });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(within(section).getByRole("button", { name: "正在核验…" })).toBeDisabled();
    expect(within(section).getByRole("textbox", { name: "手工覆盖 JSON" })).toBeDisabled();
  });

  it("ignores an in-flight receipt after the report month and base binding change", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const oldReceipt = await buildDryRunReceipt(baseClient);
    let resolveOldReceipt!: (value: typeof oldReceipt) => void;
    const revalidate = vi.fn(() => new Promise<typeof oldReceipt>((resolve) => {
      resolveOldReceipt = resolve;
    }));
    const client = { ...baseClient, mode: "real" as const, revalidateLedgerPnlCandidateFinancialIndicators: revalidate };
    const view = renderPanel(client, "202606");

    const dryRun = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(dryRun).getByRole("button", { name: "运行本次核验（不保存）" }));
    expect(within(dryRun).getByRole("button", { name: "正在核验…" })).toBeDisabled();

    view.rerender(
      <AppProviders client={client}>
        <LedgerPnlCandidateFinancialIndicatorsPanel reportMonth="202605" currency="CNX" />
      </AppProviders>,
    );
    expect(await screen.findByTestId("candidate-financial-indicators-no-data")).toHaveTextContent(
      "202605 暂无可计算的候选财务指标",
    );

    await act(async () => resolveOldReceipt(oldReceipt));
    await waitFor(() => {
      expect(screen.queryByText("本次结果 · 未保存")).not.toBeInTheDocument();
      expect(screen.queryByText("999.99")).not.toBeInTheDocument();
      expect(screen.getByTestId("candidate-financial-indicators-no-data")).toHaveTextContent("202605");
    });
  });

  it("shows request conflicts and can clear a successful in-memory result", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    const revalidate = vi.fn()
      .mockRejectedValueOnce(new Error("Request failed: candidate revalidation (409): base evidence expired"))
      .mockResolvedValueOnce(receipt);
    renderPanel({ ...baseClient, mode: "real" as const, revalidateLedgerPnlCandidateFinancialIndicators: revalidate });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    const run = within(section).getByRole("button", { name: "运行本次核验（不保存）" });
    await user.click(run);
    expect(await within(section).findByRole("alert")).toHaveTextContent("409");
    await user.click(run);
    await user.click(await within(section).findByRole("button", { name: "清除本次结果" }));
    expect(within(section).queryByText("本次结果 · 未保存")).not.toBeInTheDocument();
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("fails closed when resolution IDs do not bind the complete base worklist", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient, { mismatchIds: true });
    renderPanel({
      ...baseClient,
      mode: "real" as const,
      revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
    });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(await within(section).findByRole("alert")).toHaveTextContent("核验回执契约错误");
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("fails closed when resolution content is tampered without recomputing its key", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    receipt.requirement_resolution.requirements[0].status_detail = "篡改后的核验说明";
    receipt.requirement_resolution.requirements[0].submitted_evidence_refs = [
      "voucher://tampered",
    ];
    renderPanel({
      ...baseClient,
      mode: "real" as const,
      revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
    });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(await within(section).findByRole("alert")).toHaveTextContent("核验回执契约错误");
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("fails closed when receipt manual override count differs from the submitted request", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    receipt.manual_override_count = 7;
    renderPanel({
      ...baseClient,
      mode: "real" as const,
      revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
    });

    const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
    await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

    expect(await within(section).findByRole("alert")).toHaveTextContent("核验回执契约错误");
    expect(screen.queryByText("999.99")).not.toBeInTheDocument();
  });

  it("fails closed when Web Crypto SHA-256 is unavailable", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const baseResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const receipt = await buildDryRunReceipt(baseClient);
    vi.stubGlobal("crypto", {});
    try {
      renderPanel({
        ...baseClient,
        mode: "real" as const,
        getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => baseResponse),
        revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
      });
      const section = await screen.findByRole("region", { name: "本次核验（不保存）" });
      await user.click(within(section).getByRole("button", { name: "运行本次核验（不保存）" }));

      expect(await within(section).findByRole("alert")).toHaveTextContent("核验回执契约错误");
      expect(screen.queryByText("999.99")).not.toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("copies resolved evidence states and references without candidate or submitted values", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const receipt = await buildDryRunReceipt(baseClient);
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      renderPanel({
        ...baseClient,
        mode: "real" as const,
        revalidateLedgerPnlCandidateFinancialIndicators: vi.fn(async () => receipt),
      });
      const dryRun = await screen.findByRole("region", { name: "本次核验（不保存）" });
      await user.click(within(dryRun).getByRole("button", { name: "运行本次核验（不保存）" }));
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));

      const copied = String(writeText.mock.calls[0][0]);
      expect(copied).toContain("状态：已补·待证据核验");
      expect(copied).toContain("提交证据：voucher://202606/r010");
      expect(copied).toContain("校验证据：validation://manual/r011");
      expect(copied).not.toContain("999.99");
      expect(copied).not.toContain("value_yi");
      expect(copied).not.toContain("submitted_value");
      expect(copied).not.toContain('"metrics"');
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });
  it("shows the auditable candidate result and loads one metric lineage only after selection", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const candidateRead = vi.fn(baseClient.getLedgerPnlCandidateFinancialIndicators);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: candidateRead,
    };

    renderPanel(client, "202606", "CNY");

    expect(await screen.findByRole("heading", { name: "候选财务指标" })).toBeInTheDocument();
    expect(screen.getByText("财务指标引擎")).toBeInTheDocument();
    expect(await screen.findByText("审计待办")).toBeInTheDocument();
    expect(screen.getByText("指标目录")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正式化就绪清单" })).toBeInTheDocument();
    expect(screen.getByText("正式化未就绪 · 3 项阻断")).toBeInTheDocument();
    expect(screen.getByText("就绪证据键")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "下载阻断证据 JSON" })).toBeInTheDocument();
    expect(screen.getByText("规则资产与候选计算")).toBeInTheDocument();
    expect(screen.getByText("正式契约登记")).toBeInTheDocument();
    expect(await screen.findByText("仅支持 CNX 综合本口径")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-financial-indicators-panel")).toHaveAttribute(
      "data-calculation-state",
      "partial",
    );
    expect(screen.queryByTestId("candidate-financial-indicators-stale-warning")).not.toBeInTheDocument();
    expect(screen.getAllByText("未配置锁定样本")).toHaveLength(2);
    for (const value of ["184.6771", "10.0333"]) {
      expect(screen.getAllByText(value).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("已计算 186 / 186")).toBeInTheDocument();
    expect(candidateRead).toHaveBeenCalledTimes(1);
    expect(candidateRead).toHaveBeenNthCalledWith(1, "202606", { includeLineage: false });

    await openAnalysisView();
    const search = screen.getByRole("searchbox", { name: "搜索全部财务指标" });
    await user.type(search, "input.adjustment.noninterest.r019");
    expect(screen.getByText("显示 1 / 186")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /结果调整.*查看追溯/ })).toBeInTheDocument();

    await user.clear(search);
    await user.click(screen.getByRole("button", { name: /利息净收入.*查看追溯/ }));

    const detail = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect(within(detail).getByText("追溯详情")).toBeInTheDocument();
    expect(within(detail).getByText("income.interest.net")).toBeInTheDocument();
    expect(await within(detail).findByText("income.interest.loan.total")).toBeInTheDocument();
    expect(candidateRead).toHaveBeenNthCalledWith(2, "202606", {
      includeLineage: true,
      metricId: "income.interest.net",
    });
  });

  it("accepts the active v1.0.1 evidence pack without weakening the candidate gate", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const activeResponse = await buildCurrentSourceImpactResponse(baseClient);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => activeResponse),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("candidate-financial-indicators-contract-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("candidate-analysis-view")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-source-version-impact")).toHaveTextContent("186 / 186");
    expect(screen.getByTestId("candidate-source-version-impact")).toHaveTextContent("8");
  });

  it("opens on analysis and keeps the governance worklist behind an explicit view switch", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const activeResponse = await buildCurrentSourceImpactResponse(baseClient);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => activeResponse),
    };

    renderPanel(client);

    const switcher = await screen.findByRole("tablist", { name: "候选财务指标视图" });
    expect(within(switcher).getByRole("tab", { name: "经营分析 结论、规模、收入与指标目录" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("candidate-analysis-view")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-analysis-view")).not.toHaveAttribute("hidden");
    expect(screen.getByTestId("candidate-governance-view")).toHaveAttribute("hidden");

    await user.click(within(switcher).getByRole("tab", { name: "治理与补证 3 项门禁仍阻断" }));

    expect(screen.getByTestId("candidate-governance-view")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-governance-view")).not.toHaveAttribute("hidden");
    expect(screen.getByTestId("candidate-analysis-view")).toHaveAttribute("hidden");
    expect(screen.getByTestId("candidate-financial-indicators-promotion-readiness")).toHaveAttribute(
      "data-status",
      "blocked",
    );
  });

  it("opens on governance when the source-version numeric digest does not match", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const activeResponse = await buildCurrentSourceImpactResponse(baseClient);
    activeResponse.result.source_version_impact = {
      ...activeResponse.result.source_version_impact!,
      status: "numeric_digest_mismatch",
      current_numeric_digest: "2".repeat(64),
      numeric_changed_count: null,
      serialization_only_count: 0,
      serialization_only_metric_ids: [],
    };
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => activeResponse),
    };

    renderPanel(client);

    const switcher = await screen.findByRole("tablist", { name: "候选财务指标视图" });
    expect(within(switcher).getByRole("tab", { name: /^治理与补证/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("candidate-governance-view")).not.toHaveAttribute("hidden");
    expect(screen.getByTestId("candidate-analysis-view")).toHaveAttribute("hidden");
  });

  it("fails closed when an unchanged source-impact claim has inconsistent digests", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const activeResponse = await buildCurrentSourceImpactResponse(baseClient);
    activeResponse.result.source_version_impact = {
      ...activeResponse.result.source_version_impact!,
      current_numeric_digest: "2".repeat(64),
    };
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => activeResponse),
    };

    renderPanel(client);

    const switcher = await screen.findByRole("tablist", { name: "候选财务指标视图" });
    expect(within(switcher).getByRole("tab", { name: /^治理与补证/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(within(switcher).getByRole("tab", { name: /^经营分析/ }));
    expect(screen.getByTestId("candidate-source-version-impact-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("candidate-source-version-impact")).not.toBeInTheDocument();
  });

  it("downloads the exact backend-authored evidence pack without candidate values", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const originalBlob = Blob;
    const blobConstructor = vi.fn(function MockBlob(
      parts: BlobPart[],
      options?: BlobPropertyBag,
    ) {
      return new originalBlob(parts, options);
    });
    const createObjectURL = vi.fn(() => "blob:candidate-promotion-evidence");
    const revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal("Blob", blobConstructor);
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    try {
      renderPanel(baseClient);
      await user.click(await screen.findByRole("button", { name: "下载阻断证据 JSON" }));

      const expected = JSON.stringify(response.result.promotion_readiness.evidence_pack, null, 2);
      expect(blobConstructor).toHaveBeenCalledWith([expected], {
        type: "application/json;charset=utf-8",
      });
      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:candidate-promotion-evidence");
      expect(click).toHaveBeenCalledTimes(1);
      expect(expected).not.toContain('"metrics"');
      expect(expected).not.toContain('"values"');
      expect(expected).not.toContain('"formal_value"');
    } finally {
      click.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it("groups every owner requirement into a six-category evidence worklist", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPanel(client);

    const worklist = await screen.findByRole("region", { name: "待补证据清单" });
    const filterGroup = within(worklist).getByRole("group", { name: "筛选待补证据类别" });
    expect(within(filterGroup).getAllByRole("button").map((button) => (
      button.textContent?.replace(/\s+/g, " ").trim()
    ))).toEqual([
      "全部 22",
      "来源证据 1",
      "控制校验 0",
      "手工输入 19",
      "科目覆盖 0",
      "正式契约 1",
      "负责人复核 1",
    ]);
    expect(within(worklist).getByRole("button", { name: "全部 22" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    for (const label of [
      "来源证据 1",
      "控制校验 0",
      "手工输入 19",
      "科目覆盖 0",
      "正式契约 1",
      "负责人复核 1",
    ]) {
      expect(within(worklist).getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(within(worklist).getByRole("heading", { name: "来源证据" })).toBeInTheDocument();
    expect(within(worklist).getByRole("heading", { name: "手工输入" })).toBeInTheDocument();
    expect(within(worklist).getByRole("heading", { name: "正式契约" })).toBeInTheDocument();
    expect(within(worklist).getByRole("heading", { name: "负责人复核" })).toBeInTheDocument();
    expect(within(worklist).queryByRole("button", {
      name: /批准|通过|拒绝|提交|保存|上传|登记|确认审批/,
    })).not.toBeInTheDocument();
    expect(worklist.querySelector("form, textarea, input[type='file']")).toBeNull();
  });

  it("filters the evidence worklist without changing backend requirement state", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });

    renderPanel(client);

    const worklist = await screen.findByRole("region", { name: "待补证据清单" });
    await user.click(within(worklist).getByRole("button", { name: "手工输入 19" }));

    expect(within(worklist).getByRole("button", { name: "手工输入 19" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(worklist).getByRole("heading", { name: "手工输入" })).toBeInTheDocument();
    expect(within(worklist).queryByRole("heading", { name: "来源证据" })).not.toBeInTheDocument();
    expect(within(worklist).getAllByText("待负责人补充")).toHaveLength(19);
  });

  it("copies the filtered backend worklist as value-free evidence requests", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      renderPanel(client);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "手工输入 19" }));
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));

      expect(writeText).toHaveBeenCalledTimes(1);
      const copied = String(writeText.mock.calls[0][0]);
      expect(copied).toContain("报告期：202606 / 2026-06-30");
      expect(copied).toContain("要求编号：manual_input.1");
      expect(copied).toContain("要求编号：manual_input.19");
      expect(copied).toContain("证据引用：input.adjustment.noninterest.r010");
      expect(copied).toContain("需补材料：Approved period-matched manual input");
      expect(copied).not.toContain("要求编号：source_evidence.1");
      expect(copied).not.toContain("submitted_value");
      expect(copied).not.toContain('"metrics"');
      expect(await within(worklist).findByRole("status", { name: "复制状态" })).toHaveTextContent(
        "已复制 19 项待补要求",
      );
      await user.click(within(worklist).getByRole("button", { name: "来源证据 1" }));
      expect(within(worklist).queryByRole("status", { name: "复制状态" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("reports a successful copy when mounted through React StrictMode", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    try {
      renderPanel(client, "202606", "CNX", true);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));

      expect(await within(worklist).findByRole("status", { name: "复制状态" })).toHaveTextContent(
        "已复制 22 项待补要求",
      );
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows a recoverable message when the worklist cannot be copied", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });

    try {
      renderPanel(client);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));

      expect(await within(worklist).findByRole("status", { name: "复制状态" })).toHaveTextContent(
        "复制失败，请下载阻断证据 JSON",
      );
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("falls back when the clipboard request never settles", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(() => new Promise<void>(() => undefined)) },
    });

    try {
      renderPanel(client);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));

      expect(await within(worklist).findByRole(
        "status",
        { name: "复制状态" },
        { timeout: 2500 },
      )).toHaveTextContent("复制失败，请下载阻断证据 JSON");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores a clipboard result after the user changes the filter", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    let resolveWrite: (() => void) | undefined;
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn(() => new Promise<void>((resolve) => {
          resolveWrite = resolve;
        })),
      },
    });

    try {
      renderPanel(client);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      await user.click(within(worklist).getByRole("button", { name: "复制当前清单" }));
      await user.click(within(worklist).getByRole("button", { name: "手工输入 19" }));
      await act(async () => resolveWrite?.());

      expect(within(worklist).queryByRole("status", { name: "复制状态" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("prevents an older clipboard write from racing a copy for a new filter", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    let resolveFirstWrite: (() => void) | undefined;
    const writeText = vi.fn()
      .mockImplementationOnce(() => new Promise<void>((resolve) => {
        resolveFirstWrite = resolve;
      }))
      .mockResolvedValue(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      renderPanel(client);
      const worklist = await screen.findByRole("region", { name: "待补证据清单" });
      const copyButton = within(worklist).getByRole("button", { name: "复制当前清单" });
      await user.click(copyButton);
      await user.click(within(worklist).getByRole("button", { name: "手工输入 19" }));

      expect(copyButton).toBeDisabled();
      await user.click(copyButton);
      expect(writeText).toHaveBeenCalledTimes(1);

      await act(async () => resolveFirstWrite?.());
      await waitFor(() => expect(copyButton).toBeEnabled());
      await user.click(copyButton);
      expect(writeText).toHaveBeenCalledTimes(2);
      expect(String(writeText.mock.calls[1][0])).toContain("要求编号：manual_input.19");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("renders an explicit loading state", () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(() => new Promise<never>(() => undefined)),
    };

    renderPanel(client);

    expect(screen.getByTestId("candidate-financial-indicators-loading")).toHaveAttribute(
      "data-state",
      "loading",
    );
    expect(screen.getByText("正在读取候选财务指标…")).toBeInTheDocument();
  });

  it("renders no_data without treating missing metrics as zero", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPanel(client, "202607");

    expect(await screen.findByTestId("candidate-financial-indicators-no-data")).toHaveAttribute(
      "data-state",
      "no_data",
    );
    expect(screen.getByText("202607 暂无可计算的候选财务指标")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正式化就绪清单" })).toBeInTheDocument();
    expect(screen.getByText("正式化未就绪 · 5 项阻断")).toBeInTheDocument();
    expect(screen.queryByText("0.0000")).not.toBeInTheDocument();
  });

  it("keeps the registered 202603 formal contract passed when candidate sources are absent", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPanel(client, "202603");

    expect(await screen.findByTestId("candidate-financial-indicators-no-data")).toBeInTheDocument();
    expect(screen.getByText("正式化未就绪 · 4 项阻断")).toBeInTheDocument();
    const readiness = screen.getByTestId("candidate-financial-indicators-promotion-readiness");
    const formalContract = within(readiness).getByText("正式契约登记").closest("article");
    expect(formalContract).toHaveAttribute("data-status", "passed");
    expect(within(formalContract as HTMLElement).getByText("通过")).toBeInTheDocument();
  });

  it("renders a recoverable error and retries the base request", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const noDataResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202607");
    const candidateRead = vi.fn()
      .mockRejectedValueOnce(new Error("503 candidate engine unavailable"))
      .mockResolvedValue(noDataResponse);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: candidateRead,
    };

    renderPanel(client);

    const error = await screen.findByTestId("candidate-financial-indicators-error");
    expect(error).toHaveAttribute("data-state", "error");
    expect(within(error).getByText("503 candidate engine unavailable")).toBeInTheDocument();
    await user.click(within(error).getByRole("button", { name: "重新读取" }));

    expect(await screen.findByTestId("candidate-financial-indicators-no-data")).toBeInTheDocument();
    expect(candidateRead).toHaveBeenCalledTimes(2);
  });

  it("keeps source, validation, and gap evidence visible for partial results", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPanel(client);

    expect(await screen.findByText("证据与待办")).toBeInTheDocument();
    expect(screen.getByText("规则验证 12 / 12 通过")).toBeInTheDocument();
    expect(screen.getByText("Synthetic demo sources are not governed evidence")).toBeInTheDocument();
    expect(screen.getByText("Synthetic manual inputs use demo defaults")).toBeInTheDocument();
    expect(screen.getByText("synthetic-ledger-202606.xlsx")).toBeInTheDocument();
    expect(screen.getByText("synthetic-daily-202606.xlsx")).toBeInTheDocument();
    expect(screen.getByText("候选口径 · 禁止正式使用")).toBeInTheDocument();
    expect(screen.getAllByText(/input\.adjustment\.noninterest\.r120/).length).toBeGreaterThan(0);
  });

  it("blocks headline values when the backend reports a business calculation error", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: { ...response.result, calculation_status: "error" as const },
      })),
    };

    renderPanel(client);

    const blocked = await screen.findByTestId("candidate-financial-indicators-blocked");
    expect(blocked).toHaveAttribute("data-state", "blocked");
    expect(blocked).toHaveTextContent("候选指标计算被阻断");
    expect(blocked).toHaveTextContent("synthetic-ledger-202606.xlsx");
    expect(blocked).toHaveTextContent("Synthetic demo sources are not governed evidence");
    expect(screen.getByTestId("candidate-financial-indicators-panel")).toHaveAttribute(
      "data-calculation-state",
      "blocked",
    );
    expect(screen.queryByText("184.6771")).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox", { name: "搜索全部财务指标" })).not.toBeInTheDocument();
  });

  it("distinguishes an unconfigured lock and labels warning headline values", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          sources: response.result.sources.map((source) => source.source_kind === "daily"
            ? { ...source, locked_sha256: null, locked_hash_match: null }
            : source),
          metrics: response.result.metrics.map((metric) => metric.metric_id === "income.interest.net"
            ? { ...metric, status: "warning" as const, reasons: ["source_account_missing"] }
            : metric),
        },
      })),
    };

    renderPanel(client);

    expect(await screen.findAllByText("未配置锁定样本")).toHaveLength(2);
    const headline = screen.getByTestId("candidate-headline-income.interest.net");
    expect(headline).toHaveTextContent("警告");
    const scale = screen.getByTestId("candidate-scale-balance.deposit.corporate.total::point");
    expect(scale).toHaveTextContent("通过");
  });

  it("shows unobserved account evidence, raw yuan, and metric reasons in trace detail", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const baseResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const detailResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606", {
      includeLineage: true,
      metricId: "balance.deposit.corporate.total::point",
    });
    const candidateRead = vi.fn(async (_reportMonth: string, options?: { includeLineage?: boolean }) => {
      if (!options?.includeLineage) return baseResponse;
      return {
        ...detailResponse,
        result: {
          ...detailResponse.result,
          metrics: detailResponse.result.metrics.map((metric) => ({
            ...metric,
            status: "warning" as const,
            reasons: ["source_account_missing"],
            lineage: metric.lineage.map((lineage) => lineage.lineage_type === "account"
              ? {
                  ...lineage,
                  observed: false,
                  raw_yuan: "0",
                  contribution_yi: "0",
                }
              : lineage),
          })),
        },
      };
    });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: candidateRead,
    };

    renderPanel(client);
    await openAnalysisView();
    const scaleHeadline = await screen.findByTestId(
      "candidate-scale-balance.deposit.corporate.total::point",
    );
    await user.click(within(scaleHeadline).getByRole("button", { name: /查看追溯/ }));

    const detail = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect((await within(detail).findAllByText("源表未观测 / 候选按 0 代入")).length).toBeGreaterThan(0);
    expect(within(detail).getAllByText("原始金额（元）").length).toBeGreaterThan(0);
    expect(within(detail).getByText("source_account_missing")).toBeInTheDocument();
  });

  it("renders a blank report month as no_data without issuing a request", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const candidateRead = vi.fn(baseClient.getLedgerPnlCandidateFinancialIndicators);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: candidateRead,
    };

    renderPanel(client, "   ");

    expect(await screen.findByTestId("candidate-financial-indicators-no-data")).toHaveTextContent(
      "未选择报告月份",
    );
    expect(candidateRead).not.toHaveBeenCalled();
    expect(screen.queryByTestId("candidate-financial-indicators-loading")).not.toBeInTheDocument();
  });

  it("keeps every source mismatch and its cell, validation, and metric evidence visible", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          source_alignment: "mismatch" as const,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            evidence_pack: {
              ...response.result.promotion_readiness.evidence_pack,
              source_alignment: "mismatch" as const,
            },
          },
          sources: response.result.sources.map((source) => ({
            ...source,
            sha256: source.source_kind === "ledger" ? "a".repeat(64) : "c".repeat(64),
            locked_sha256: source.source_kind === "ledger" ? "b".repeat(64) : "d".repeat(64),
            locked_hash_match: false,
            periods: source.periods.map((period, index) => ({
              ...period,
              source_cell: source.source_kind === "ledger" ? "综本!A5" : `日均!A${index + 5}`,
            })),
          })),
          validations: response.result.validations.map((validation) => (
            validation.validation_id === "recon.company_deposit"
              ? { ...validation, passed: false, delta_yi: "0.125", sample: ["company.deposit.sample"] }
              : validation
          )),
          gaps: [
            {
              gap_id: "source_hash.ledger",
              severity: "warning" as const,
              kind: "source_hash" as const,
              title: "总账来源与锁定样本不一致",
              detail: "总账哈希不一致。",
              metric_ids: ["income.interest.net"],
            },
            {
              gap_id: "source_hash.daily",
              severity: "warning" as const,
              kind: "source_hash" as const,
              title: "日均来源与锁定样本不一致",
              detail: "日均哈希不一致。",
              metric_ids: ["income.interest.net"],
            },
          ],
        },
      })),
    };

    renderPanel(client);

    expect(await screen.findAllByText("总账来源与锁定样本不一致")).toHaveLength(2);
    expect(screen.getAllByText("日均来源与锁定样本不一致")).toHaveLength(2);
    expect(screen.getByText(/综本!A5/)).toBeInTheDocument();
    expect(screen.getByText(/差额 0.125 亿元/)).toBeInTheDocument();
    expect(screen.getByText(/company.deposit.sample/)).toBeInTheDocument();
    expect(screen.getAllByText(/影响指标 income.interest.net/)).toHaveLength(2);
  });

  it("shows the concrete missing files and gaps for a no-data domain response", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPanel(client, "202607");

    const noData = await screen.findByTestId("candidate-financial-indicators-no-data");
    expect(noData).toHaveTextContent("总账对账202607.xlsx");
    expect(noData).toHaveTextContent("日均202607.xlsx");
    expect(noData).toHaveTextContent("缺少总账源文件");
    expect(noData).toHaveTextContent("缺少日均源文件");
  });

  it("treats a missing result payload as a contract error instead of no data", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: undefined,
      }) as never),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-contract-error")).toHaveTextContent(
      "响应缺少 result",
    );
    expect(screen.queryByTestId("candidate-financial-indicators-no-data")).not.toBeInTheDocument();
  });

  it("fails closed when promotion readiness is missing from the candidate contract", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: undefined,
        },
      }) as never),
    };

    renderPanel(client);

    const error = await screen.findByTestId("candidate-financial-indicators-contract-error");
    expect(error).toHaveTextContent("响应缺少 promotion_readiness");
    expect(screen.queryByTestId("candidate-financial-indicators-promotion-readiness")).not.toBeInTheDocument();
  });

  it("fails closed when promotion readiness is only partially deployed", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            checks: undefined,
          },
        },
      }) as never),
    };

    renderPanel(client);

    const error = await screen.findByTestId("candidate-financial-indicators-contract-error");
    expect(error).toHaveTextContent("响应缺少 promotion_readiness");
    expect(screen.queryByTestId("candidate-financial-indicators-promotion-readiness")).not.toBeInTheDocument();
  });

  it("fails closed when the backend evidence pack is absent", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            evidence_pack: undefined,
          },
        },
      }) as never),
    };

    renderPanel(client);

    const error = await screen.findByTestId("candidate-financial-indicators-contract-error");
    expect(error).toHaveTextContent("响应缺少 promotion_readiness");
    expect(screen.queryByRole("button", { name: "下载阻断证据 JSON" })).not.toBeInTheDocument();
  });

  it("fails closed when the evidence pack belongs to another report period", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            evidence_pack: {
              ...response.result.promotion_readiness.evidence_pack,
              report_month: "202605",
              report_date: "2026-05-31",
            },
          },
        },
      }) as never),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-contract-error")).toHaveTextContent(
      "响应缺少 promotion_readiness",
    );
  });

  it("fails closed when readiness belongs to another candidate run", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const otherCandidateKey = "9".repeat(64);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            candidate_idempotency_key: otherCandidateKey,
            evidence_pack: {
              ...response.result.promotion_readiness.evidence_pack,
              candidate_idempotency_key: otherCandidateKey,
            },
          },
        },
      }) as never),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-contract-error")).toHaveTextContent(
      "响应缺少 promotion_readiness",
    );
  });

  it("fails closed when an owner requirement category is unknown", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const pack = response.result.promotion_readiness.evidence_pack;
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            evidence_pack: {
              ...pack,
              owner_requirements: [
                { ...pack.owner_requirements[0], category: "unknown" },
                ...pack.owner_requirements.slice(1),
              ],
            },
          },
        },
      }) as never),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-contract-error")).toHaveTextContent(
      "响应缺少 promotion_readiness",
    );
  });

  it("fails closed when promotion readiness has an unknown status", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...response,
        result: {
          ...response.result,
          promotion_readiness: {
            ...response.result.promotion_readiness,
            status: "unexpected",
          },
        },
      }) as never),
    };

    renderPanel(client);

    expect(await screen.findByTestId("candidate-financial-indicators-contract-error")).toHaveTextContent(
      "响应缺少 promotion_readiness",
    );
    expect(screen.queryByText("技术门槛已通过 · 待业务复核")).not.toBeInTheDocument();
  });

  it("shows a terminal detail state when lineage returns no data", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const baseResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    const noDataResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202607");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async (_month, options) => (
        options?.includeLineage ? noDataResponse : baseResponse
      )),
    };

    renderPanel(client);
    await openAnalysisView();
    await user.click(await screen.findByRole("button", { name: /利息净收入.*查看追溯/ }));

    const dialog = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect(within(dialog).getByRole("heading", { name: "指标追溯不可用" })).toBeInTheDocument();
    expect(within(dialog).queryByText("正在读取指标追溯")).not.toBeInTheDocument();
  });

  it("reports truncated broad-search results honestly", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);
    await openAnalysisView();

    const search = await screen.findByRole("searchbox", { name: "搜索全部财务指标" });
    await user.type(search, "income");

    expect(screen.getByText("匹配 107，当前展示 50 / 186")).toBeInTheDocument();
  });

  it("searches the displayed Chinese basis label", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);
    await openAnalysisView();

    const search = await screen.findByRole("searchbox", { name: "搜索全部财务指标" });
    await user.type(search, "时点余额");

    expect(screen.getByText("显示 19 / 186")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /公司存款活期.*查看追溯/ })).toBeInTheDocument();
  });

  it("labels account lineage for business users and includes units for metric lineage", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const interestDetail = await client.getLedgerPnlCandidateFinancialIndicators("202606", {
      includeLineage: true,
      metricId: "income.interest.net",
    });
    const metricLineageValues = interestDetail.result.metrics[0]?.lineage
      .filter((lineage) => lineage.lineage_type === "metric")
      .map((lineage) => lineage.metric_value_yi);
    if (!metricLineageValues || metricLineageValues.length < 2) {
      throw new Error("synthetic interest lineage fixture is incomplete");
    }
    renderPanel(client);
    await openAnalysisView();

    const companyDeposit = await screen.findByTestId(
      "candidate-scale-balance.deposit.corporate.total::point",
    );
    await user.click(within(companyDeposit).getByRole("button", { name: /查看追溯/ }));
    let dialog = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect(
      (await within(dialog).findAllByText("主表 · 时点余额 · 一级科目")).length,
    ).toBeGreaterThan(0);
    await user.keyboard("{Escape}");

    await user.click(await screen.findByRole("button", { name: /利息净收入.*查看追溯/ }));
    dialog = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect(
      (await within(dialog).findAllByText(`${metricLineageValues[0]} 亿元`)).length,
    ).toBeGreaterThan(0);
    expect(within(dialog).getAllByText(`${metricLineageValues[1]} 亿元`).length).toBeGreaterThan(0);
  });

  it("uses modal dialog keyboard behavior and restores focus to the opener", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    renderPanel(client);
    await openAnalysisView();
    const opener = await screen.findByRole("button", { name: /利息净收入.*查看追溯/ });

    await user.click(opener);

    const dialog = await screen.findByRole("dialog", { name: "指标追溯详情" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByRole("button", { name: "关闭指标追溯详情" })).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog", { name: "指标追溯详情" })).not.toBeInTheDocument();
    await waitFor(() => expect(opener).toHaveFocus());
  });
});
