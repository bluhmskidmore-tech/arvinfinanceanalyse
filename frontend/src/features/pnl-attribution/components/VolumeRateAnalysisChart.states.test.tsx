import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";
import type { DataSectionState } from "../../../components/DataSection.types";

function renderWith(state: DataSectionState, data = null as any) {
  render(
    <VolumeRateAnalysisChart data={data} state={state} onRetry={vi.fn()} />,
  );
}

describe("VolumeRateAnalysisChart · state=loading", () => {
  it("shows loading placeholder", () => {
    renderWith({ kind: "loading" });
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart · state=error", () => {
  it("shows error with retry", () => {
    renderWith({ kind: "error", message: "fetch failed" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart · state=empty", () => {
  it("shows empty placeholder when no data", () => {
    renderWith({ kind: "empty" });
    expect(screen.getByTestId("data-section-empty")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart · state=vendor_unavailable", () => {
  it("shows vendor unavailable placeholder", () => {
    renderWith({ kind: "vendor_unavailable", details: "pnl 未返回" });
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart · state=fallback", () => {
  it("renders fallback banner", () => {
    renderWith({ kind: "fallback", effective_date: "2026-03-31" }, null);
    expect(screen.getByTestId("data-section-fallback-banner")).toBeInTheDocument();
  });
});
