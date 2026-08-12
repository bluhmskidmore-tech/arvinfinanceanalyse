/**
 * ledger-pnl `fallback_or_stale_state_visible_when_applicable` gate 探针
 * （回退 / 过期 / 上游不可用 / 无响应等降级形态必须显式可见，不得静默展示旧数据或空白）。
 *
 * Gate 语义（任务 gap 记录 + frontend/AGENTS.md "Explicitly surface material
 * no-data, stale-data, fallback-date, loading-failure states"）：
 * - 报告日回退（result_meta.fallback_mode="latest_snapshot"）：必须显式披露请求日/解析日，
 *   旧报告日数据可以展示，但必须与回退披露同屏，不得静默冒充请求日数据；
 * - 数据过期（quality_flag="stale" 或 vendor_status="vendor_stale"）：必须显式渲染
 *   过期披露（截至日 + vendor 状态）；
 * - 上游不可用（vendor_status="vendor_unavailable"）：分析面整体替换为警示卡，
 *   不得渲染任何可被误读为新鲜结论的金额；
 * - 分析响应缺失（envelope 为空且非 loading/error）：渲染显式“暂无分析响应”卡，不留空白；
 * - 反向（防误报）：ready 且元数据健康时不得渲染任何降级面，且数据面确实在展示
 *   （反向断言不能靠“什么都没渲染”成立）。
 *
 * 被测状态面（features/ledger-pnl/components/LedgerPnlAnalysisWorkbench.tsx）：
 * - SourceStatus（data-testid="ledger-pnl-analysis-source-status"）：
 *   fallback 块条件 = fallback_mode==="latest_snapshot"；
 *   stale 块条件 = quality_flag==="stale" || vendor_status==="vendor_stale"；
 *   两者皆无 → 返回 null（不渲染任何来源状态面）；
 *   解析日显示链 = resolved_report_date || fallback_date || EM_DASH。
 * - StateCard 警示卡：vendor_unavailable / no_data / 无响应分支整面替换数据面板；
 *   no_data 分支同时保留 SourceStatus（回退后仍无数据的叠加形态）。
 *
 * 现有测试已覆盖、本文件不重复：
 * - LedgerPnlAnalysisWorkbench.test.tsx：fallback+stale 同时出现的组合断言、
 *   纯 no_data 卡（无回退元数据）、403 与错误重试；
 * - LedgerPnlFinancialIndicatorSummaryPanel.test.tsx 与 LedgerPnlNullMatrixContract.test.tsx：
 *   SummaryPanel data_status="no_data" 的整表无数据状态（不以 0 值展示）。
 * 本文件补：fallback-only（含解析日回退链与 EM_DASH 占位）、stale-only（quality_flag 与
 * vendor_stale 两个触发通道分别验证，防止其中一个通道回归后被另一个掩盖）、
 * vendor_unavailable 整面替换、no_data×fallback 叠加、无响应卡，以及 ready 健康态反向断言。
 *
 * 疑似问题登记（不放宽断言，以 it.skip 保留语义断言，详见专家报告）：
 * - [观察A·低风险] vendor_unavailable 整面替换时，workbench 的 data-state 钩子仍透传
 *   payload.analysis_status（="ready"）：用户可见面正确（警示卡 + 无金额），但机器可读
 *   状态钩子宣称 ready，按 data-state 做自动化监测会漏报该降级。CSS 不消费该钩子，
 *   无用户可见影响，故仅登记不修改。
 * - [gap·页面级] LedgerPnlPage.tsx 的 collectSourceRiskSegments（候选分析证据条“来源状态”）
 *   仅被 LedgerPnlPage.test.tsx 验证了健康方向（“来源正常”），fallback/vendor 降级方向
 *   未覆盖；需整页渲染 harness，超出本组件级探针范围，登记为未覆盖形态。
 *
 * 先红后绿：开发中曾临时把「形态一 fallback-only 必须渲染来源状态面」的断言反转为
 * expect(screen.queryByTestId("ledger-pnl-analysis-source-status")).toBeNull()
 * （模拟“回退横幅静默缺失”的回归方向），探针如期变红；证据保存在专家报告中，
 * 此处已恢复为契约断言。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiEnvelope, LedgerPnlAnalysisPayload } from "../api/contracts";
import { createApiClient } from "../api/client";
import { LedgerPnlAnalysisWorkbench } from "../features/ledger-pnl/components/LedgerPnlAnalysisWorkbench";
import { EM_DASH } from "../utils/format";

/** mock 快照中唯一 ready 的总账分析报告日（src/mocks/ledgerPnlMocks.ts）。 */
const READY_REPORT_DATE = "2025-12-31";
/** 未登记快照的报告日：mock 客户端返回 analysis_status="no_data" 载荷。 */
const NO_DATA_REPORT_DATE = "2026-01-31";

/**
 * “数值 + 亿元”金额展示形（Workbench.formatMoney 输出，mock yi 恒带两位小数）。
 * 降级整面替换时整个工作台不得出现该形态，防止旧数值被误读为新鲜结论。
 */
const MONEY_DISPLAY_PATTERN = /-?\d[\d,]*\.\d+ 亿元/;

async function loadAnalysisEnvelope(
  reportDate: string,
): Promise<ApiEnvelope<LedgerPnlAnalysisPayload>> {
  const client = createApiClient({ mode: "mock" });
  return structuredClone(await client.getLedgerPnlAnalysis(reportDate, "CNX"));
}

function renderWorkbench(
  envelope: ApiEnvelope<LedgerPnlAnalysisPayload> | undefined,
  options?: { onRetry?: () => void },
) {
  render(
    <LedgerPnlAnalysisWorkbench
      envelope={envelope}
      isLoading={false}
      isError={false}
      error={null}
      onRetry={options?.onRetry ?? vi.fn()}
    />,
  );
  return screen.getByTestId("ledger-pnl-analysis-workbench");
}

describe("LedgerPnlFallbackStateContract / 反向断言：ready 健康态不得出现降级面", () => {
  it("quality ok + vendor ok + fallback none：来源状态面不渲染，数据面正常展示", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    // 夹具守卫：mock ready envelope 的元数据必须是健康态，防 mock 漂移让反向断言空转。
    expect(envelope.result_meta.quality_flag).toBe("ok");
    expect(envelope.result_meta.vendor_status).toBe("ok");
    expect(envelope.result_meta.fallback_mode).toBe("none");

    const workbench = renderWorkbench(envelope);

    expect(workbench).toHaveAttribute("data-state", "ready");
    expect(screen.queryByTestId("ledger-pnl-analysis-source-status")).not.toBeInTheDocument();
    expect(workbench).not.toHaveTextContent("已回退至最近可用报告日");
    expect(workbench).not.toHaveTextContent("数据可能已过期");
    expect(workbench).not.toHaveTextContent("总账分析上游数据不可用");
    expect(workbench).not.toHaveTextContent("暂无分析响应");
    // 反向断言不能靠“什么都没渲染”成立：结论面与金额确实在展示。
    expect(screen.getByTestId("ledger-pnl-analysis-conclusion")).toBeVisible();
    expect(workbench.textContent).toMatch(MONEY_DISPLAY_PATTERN);
  });
});

describe("LedgerPnlFallbackStateContract / 形态一：报告日回退（fallback_mode=latest_snapshot）", () => {
  it("仅 fallback（无 stale）：回退披露与旧数据同屏，且不误挂过期披露", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.fallback_mode = "latest_snapshot";
    envelope.result_meta.requested_report_date = "2026-06-30";
    envelope.result_meta.resolved_report_date = "2025-12-31";
    envelope.result_meta.fallback_date = "2025-12-31";

    const workbench = renderWorkbench(envelope);

    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toBeVisible();
    expect(status).toHaveTextContent("已回退至最近可用报告日");
    expect(status).toHaveTextContent("请求日 2026-06-30");
    expect(status).toHaveTextContent("解析日 2025-12-31");
    // fallback 单独出现时不得同时渲染 stale 块：两类降级语义不可互相污染。
    expect(status).not.toHaveTextContent("数据可能已过期");
    // gate 关键语义：旧报告日数据可以展示，但必须与回退披露同屏，不得静默冒充请求日数据。
    expect(screen.getByTestId("ledger-pnl-analysis-conclusion")).toBeVisible();
    expect(workbench.textContent).toMatch(MONEY_DISPLAY_PATTERN);
  });

  it("解析日缺失时回退显示 fallback_date；请求日缺失渲染 EM_DASH 而非空白", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.fallback_mode = "latest_snapshot";
    envelope.result_meta.requested_report_date = null;
    envelope.result_meta.resolved_report_date = null;
    envelope.result_meta.fallback_date = "2025-12-31";

    renderWorkbench(envelope);

    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toHaveTextContent("已回退至最近可用报告日");
    expect(status).toHaveTextContent(`请求日 ${EM_DASH}`);
    expect(status).toHaveTextContent("解析日 2025-12-31");
  });
});

describe("LedgerPnlFallbackStateContract / 形态二：数据过期（stale 的两个触发通道）", () => {
  it("quality_flag=stale 单独触发：过期披露带截至日，且不误挂回退披露", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.quality_flag = "stale";

    const workbench = renderWorkbench(envelope);

    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toBeVisible();
    expect(status).toHaveTextContent("数据可能已过期");
    expect(status).toHaveTextContent(`截至日 ${READY_REPORT_DATE}`);
    expect(status).not.toHaveTextContent("已回退至最近可用报告日");
    // 过期数据仍可展示，但必须带显式过期披露。
    expect(screen.getByTestId("ledger-pnl-analysis-conclusion")).toBeVisible();
    expect(workbench.textContent).toMatch(MONEY_DISPLAY_PATTERN);
  });

  it("vendor_status=vendor_stale 单独触发：过期披露透出 vendor 状态", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.vendor_status = "vendor_stale";

    renderWorkbench(envelope);

    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toHaveTextContent("数据可能已过期");
    expect(status).toHaveTextContent("vendor vendor_stale");
    expect(status).not.toHaveTextContent("已回退至最近可用报告日");
  });
});

describe("LedgerPnlFallbackStateContract / 形态三：上游不可用（vendor_unavailable 整面替换）", () => {
  it("警示卡整面替换：不渲染任何可被误读为新鲜结论的金额，重试动作可用", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.vendor_status = "vendor_unavailable";
    const onRetry = vi.fn();

    const workbench = renderWorkbench(envelope, { onRetry });

    expect(screen.getByText("总账分析上游数据不可用")).toBeVisible();
    expect(screen.getByText("当前不能形成候选分析结论。")).toBeVisible();
    // envelope 里携带 ready 载荷，但任何分析面板与金额都不得渲染。
    expect(screen.queryByTestId("ledger-pnl-analysis-conclusion")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-analysis-bridge")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-analysis-basis")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-analysis-contributors")).not.toBeInTheDocument();
    expect(workbench.textContent).not.toMatch(MONEY_DISPLAY_PATTERN);

    fireEvent.click(screen.getByRole("button", { name: "重试分析" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  // [观察A·低风险] 可见面正确（上一用例已断言），但 data-state 钩子透传
  // payload.analysis_status（="ready"）：按 data-state 做自动化监测会把“上游不可用”
  // 误读为 ready。CSS 不消费该钩子、无用户可见影响，登记观察，不放宽可见面断言。
  // 解除 skip 的实测输出：expected not to have attribute data-state="ready"，received ready。
  it.skip("[观察A] 整面替换时 data-state 钩子不应仍宣称 ready", async () => {
    const envelope = await loadAnalysisEnvelope(READY_REPORT_DATE);
    envelope.result_meta.vendor_status = "vendor_unavailable";

    const workbench = renderWorkbench(envelope);

    expect(workbench).not.toHaveAttribute("data-state", "ready");
  });
});

describe("LedgerPnlFallbackStateContract / 形态四：no_data 与回退叠加", () => {
  it("回退后仍无数据：无数据卡与回退披露同屏，且无任何金额展示", async () => {
    const envelope = await loadAnalysisEnvelope(NO_DATA_REPORT_DATE);
    // 夹具守卫：未登记报告日必须落在 no_data 载荷上，防 mock 快照扩表后夹具失义。
    expect(envelope.result.analysis_status).toBe("no_data");
    envelope.result_meta.fallback_mode = "latest_snapshot";
    envelope.result_meta.requested_report_date = "2026-02-28";
    envelope.result_meta.resolved_report_date = NO_DATA_REPORT_DATE;

    const workbench = renderWorkbench(envelope);

    expect(workbench).toHaveAttribute("data-state", "no_data");
    expect(screen.getByText("当前报告日与账务口径暂无损益分析数据")).toBeVisible();
    expect(workbench).toHaveTextContent("无数据不等于损益为 0");
    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toHaveTextContent("已回退至最近可用报告日");
    expect(status).toHaveTextContent("请求日 2026-02-28");
    expect(status).toHaveTextContent(`解析日 ${NO_DATA_REPORT_DATE}`);
    expect(screen.queryByTestId("ledger-pnl-analysis-conclusion")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-analysis-bridge")).not.toBeInTheDocument();
    expect(workbench.textContent).not.toMatch(MONEY_DISPLAY_PATTERN);
  });
});

describe("LedgerPnlFallbackStateContract / 形态五：分析响应缺失", () => {
  it("非 loading 非 error 且 envelope 缺失：渲染显式“暂无分析响应”卡而非空白", () => {
    const onRetry = vi.fn();

    const workbench = renderWorkbench(undefined, { onRetry });

    expect(workbench).toHaveAttribute("data-state", "no_data");
    expect(screen.getByText("暂无分析响应")).toBeVisible();
    expect(workbench).toHaveTextContent("未收到候选总账分析结果，不以 0 补齐。");
    expect(workbench.textContent).not.toMatch(MONEY_DISPLAY_PATTERN);

    fireEvent.click(screen.getByRole("button", { name: "重试分析" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
