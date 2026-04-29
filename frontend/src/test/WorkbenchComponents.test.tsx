import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ResultMeta } from "../api/contracts";
import { TraceMetaBar, WorkbenchCard } from "../components/workbench";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_workbench_test",
    basis: "formal",
    result_kind: "test.result",
    formal_use_allowed: true,
    source_version: "source_v1",
    vendor_version: "vendor_v1",
    rule_version: "rule_v1",
    cache_version: "cache_v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

describe("workbench components", () => {
  it("renders governed ResultMeta fallback and stale states", () => {
    render(
      <TraceMetaBar
        meta={createResultMeta({
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
        })}
      />,
    );

    expect(screen.getByText("Fallback")).toBeInTheDocument();
    expect(screen.getByText("Stale")).toBeInTheDocument();
    expect(screen.getByText("source_v1")).toBeInTheDocument();
    expect(screen.getByText("rule_v1")).toBeInTheDocument();
  });

  it("renders the stable WorkbenchCard surface with toned badges and actions", () => {
    const onAction = vi.fn();
    render(
      <WorkbenchCard
        title="Shared card"
        badges={[{ key: "ready", label: "Ready", tone: "success" }]}
        actions={[{ key: "refresh", label: "Refresh", onClick: onAction }]}
      >
        <div>Card body</div>
      </WorkbenchCard>,
    );

    expect(screen.getByText("Shared card")).toBeInTheDocument();
    expect(screen.getByText("Card body")).toBeInTheDocument();
    expect(screen.getByText("Ready").closest(".ant-tag")).toHaveClass("ant-tag-green");

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
