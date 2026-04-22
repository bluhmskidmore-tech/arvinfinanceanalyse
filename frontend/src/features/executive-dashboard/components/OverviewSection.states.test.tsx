import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { OverviewSection } from "./OverviewSection";
import type { DashboardAdapterOutput } from "../adapters/executiveDashboardAdapter";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Numeric } from "../../../api/contracts";

function makeNumeric(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 1,
    unit: "yuan",
    display: "+1.00 亿",
    precision: 2,
    sign_aware: true,
    ...partial,
  };
}

function makeOverviewVM(): NonNullable<DashboardAdapterOutput["overview"]["vm"]> {
  return {
    title: "经营总览",
    metrics: [
      {
        id: "aum",
        label: "资产规模",
        value: makeNumeric({ raw: 123_456_000_000, display: "1,234.56 亿", sign_aware: false }),
        delta: makeNumeric({ raw: 0.023, unit: "pct", display: "+2.30%" }),
        tone: "positive",
        detail: "来自 formal balance",
        history: null,
      },
    ],
  };
}

function renderWithState(state: DataSectionState) {
  const vm = state.kind === "ok" || state.kind === "stale" || state.kind === "fallback" ? makeOverviewVM() : null;
  const onRetry = vi.fn();
  render(
    <OverviewSection
      overview={{ vm, state, meta: null }}
      onRetry={onRetry}
    />,
  );
  return { onRetry };
}

describe("OverviewSection · state=loading", () => {
  it("shows loading indicator, hides metric cards", () => {
    renderWithState({ kind: "loading" });
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
    expect(screen.queryByText("资产规模")).not.toBeInTheDocument();
  });
});

describe("OverviewSection · state=error", () => {
  it("shows error UI with retry", () => {
    renderWithState({ kind: "error", message: "fetch failed" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
    expect(screen.queryByText("资产规模")).not.toBeInTheDocument();
  });
});

describe("OverviewSection · state=empty", () => {
  it("shows empty placeholder", () => {
    renderWithState({ kind: "empty" });
    expect(screen.getByTestId("data-section-empty")).toBeInTheDocument();
  });
});

describe("OverviewSection · state=stale", () => {
  it("shows stale banner AND renders metric cards", () => {
    renderWithState({ kind: "stale", effective_date: "2026-04-08" });
    expect(screen.getByTestId("data-section-stale-banner")).toBeInTheDocument();
    expect(screen.getByText("资产规模")).toBeInTheDocument();
    expect(screen.getByText("1,234.56 亿")).toBeInTheDocument();
  });
});

describe("OverviewSection · state=fallback", () => {
  it("shows fallback banner AND renders metric cards", () => {
    renderWithState({ kind: "fallback", effective_date: "2026-04-07" });
    expect(screen.getByTestId("data-section-fallback-banner")).toBeInTheDocument();
    expect(screen.getByText("资产规模")).toBeInTheDocument();
  });
});

describe("OverviewSection · state=vendor_unavailable", () => {
  it("shows vendor_unavailable placeholder, hides metric cards", () => {
    renderWithState({ kind: "vendor_unavailable", details: "balance 未返回" });
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
    expect(screen.queryByText("资产规模")).not.toBeInTheDocument();
  });
});

describe("OverviewSection · state=explicit_miss", () => {
  it("shows explicit_miss with requested date", () => {
    renderWithState({ kind: "explicit_miss", requested_date: "2025-11-30" });
    expect(screen.getByTestId("data-section-explicit-miss")).toBeInTheDocument();
    expect(screen.getByText(/2025-11-30/)).toBeInTheDocument();
  });
});

describe("OverviewSection · state=ok", () => {
  it("renders metric cards with display strings, no state testids present", () => {
    renderWithState({ kind: "ok" });
    expect(screen.queryByTestId("data-section-loading")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-section-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-section-empty")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-section-vendor-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-section-explicit-miss")).not.toBeInTheDocument();
    expect(screen.getByText("资产规模")).toBeInTheDocument();
    expect(screen.getByText("1,234.56 亿")).toBeInTheDocument();
    expect(screen.getByText("+2.30%")).toBeInTheDocument();
  });
});
