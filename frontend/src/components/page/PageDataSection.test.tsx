import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DataSectionState } from "../DataSection.types";
import { PageDataSection } from "./PageDataSection";

function renderSection(
  state: DataSectionState,
  children = <div data-testid="inner">loaded</div>,
) {
  const onRetry = vi.fn();
  const view = render(
    <PageDataSection
      title="经营总览"
      state={state}
      onRetry={onRetry}
      testId="page-data-section"
    >
      {children}
    </PageDataSection>,
  );

  return { onRetry, ...view };
}

function expectPageV2State(testId: string, variant: string) {
  const state = screen.getByTestId(testId);
  expect(state).toHaveClass("moss-page-v2-state-surface");
  expect(state).toHaveAttribute("data-state-variant", variant);
  return state;
}

describe("PageDataSection", () => {
  it("renders ok children inside the page-v2 evidence panel", () => {
    renderSection({ kind: "ok" });

    expect(screen.getByTestId("page-data-section")).toHaveClass(
      "moss-page-v2-evidence-panel",
    );
    expect(screen.getByText("经营总览")).toBeInTheDocument();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("renders loading state with the page-v2 state surface", () => {
    renderSection({ kind: "loading" });

    expectPageV2State("data-section-loading", "loading");
    expect(screen.getByText("正在载入")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });

  it("renders error state and retries", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderSection({ kind: "error" });

    expectPageV2State("data-section-error", "error");
    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();
    expect(
      screen.getByText("当前页面保留重试入口，不在浏览器端自行拼接正式口径。"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders empty state with the page-v2 state surface", () => {
    renderSection({ kind: "empty" });

    expectPageV2State("data-section-empty", "empty");
    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });

  it("renders stale banner date and details while preserving children", () => {
    renderSection({
      kind: "stale",
      effective_date: "2026-04-08",
      details: "vendor_stale",
    });

    expectPageV2State("data-section-stale-banner", "stale");
    expect(screen.getByText("数据可能已过期")).toBeInTheDocument();
    expect(screen.getByText("有效日 2026-04-08 · vendor_stale")).toBeInTheDocument();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("renders fallback banner date and details while preserving children", () => {
    renderSection({
      kind: "fallback",
      effective_date: "2026-04-07",
      details: "latest_available",
    });

    expectPageV2State("data-section-fallback-banner", "fallback-date");
    expect(screen.getByText("已回退至最近可用日")).toBeInTheDocument();
    expect(
      screen.getByText("回退日 2026-04-07 · latest_available"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("renders vendor unavailable copy and test id", () => {
    renderSection({
      kind: "vendor_unavailable",
      details: "balance 未返回",
    });

    expectPageV2State("data-section-vendor-unavailable", "empty");
    expect(screen.getByText("该业务域数据暂不可用。")).toBeInTheDocument();
    expect(screen.getByText("balance 未返回")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });

  it("renders explicit miss date, details, and test id", () => {
    renderSection({
      kind: "explicit_miss",
      requested_date: "2025-11-30",
      details: "该日无数据",
    });

    expectPageV2State("data-section-explicit-miss", "empty");
    expect(
      screen.getByText("指定报告日 2025-11-30 无数据。"),
    ).toBeInTheDocument();
    expect(screen.getByText("该日无数据")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });
});
