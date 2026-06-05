import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import PnlAttributionSection from "./PnlAttributionSection";
import type { DashboardAdapterOutput } from "../adapters/executiveDashboardAdapter";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Numeric } from "../../../api/contracts";

// ECharts is mocked globally if project has setup; otherwise render will include
// an <ReactECharts /> placeholder without crashing in jsdom. We don't assert on
// chart internals; we assert on DataSection state testids and list content.

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

function makeAttributionVM(): NonNullable<DashboardAdapterOutput["attribution"]["vm"]> {
  return {
    title: "经营贡献拆解",
    total: makeNumeric({ raw: 3_200_000_000, display: "+32.00 亿" }),
    segments: [
      {
        id: "carry",
        label: "Carry",
        amount: makeNumeric({ raw: 1_500_000_000, display: "+15.00 亿" }),
        tone: "positive",
      },
      {
        id: "roll",
        label: "Roll-down",
        amount: makeNumeric({ raw: -300_000_000, display: "-3.00 亿" }),
        tone: "negative",
      },
    ],
  };
}

function renderWithState(state: DataSectionState) {
  const vm = state.kind === "ok" || state.kind === "stale" || state.kind === "fallback" ? makeAttributionVM() : null;
  const onRetry = vi.fn();
  render(
    <PnlAttributionSection
      attribution={{ vm, state, meta: null }}
      onRetry={onRetry}
    />,
  );
  return { onRetry };
}

describe("PnlAttributionSection · state=loading", () => {
  it("shows loading indicator, hides segment list", () => {
    renderWithState({ kind: "loading" });
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
    expect(screen.queryByText("Carry")).not.toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=error", () => {
  it("shows error with retry", () => {
    renderWithState({ kind: "error" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=empty", () => {
  it("shows empty placeholder", () => {
    renderWithState({ kind: "empty" });
    expect(screen.getByTestId("data-section-empty")).toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=stale", () => {
  it("shows stale banner AND renders segments", () => {
    renderWithState({ kind: "stale", effective_date: "2026-04-08" });
    expect(screen.getByTestId("data-section-stale-banner")).toBeInTheDocument();
    expect(screen.getByText("Carry")).toBeInTheDocument();
    expect(screen.getByText("+15.00 亿")).toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=fallback", () => {
  it("shows fallback banner AND renders segments", () => {
    renderWithState({ kind: "fallback", effective_date: "2026-04-07" });
    expect(screen.getByTestId("data-section-fallback-banner")).toBeInTheDocument();
    expect(screen.getByText("Roll-down")).toBeInTheDocument();
    expect(screen.getByText("-3.00 亿")).toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=vendor_unavailable", () => {
  it("shows vendor_unavailable, hides segments", () => {
    renderWithState({ kind: "vendor_unavailable", details: "attribution 未返回" });
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Carry")).not.toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=explicit_miss", () => {
  it("shows explicit_miss with requested date", () => {
    renderWithState({ kind: "explicit_miss", requested_date: "2025-11-30" });
    expect(screen.getByTestId("data-section-explicit-miss")).toBeInTheDocument();
    expect(screen.getByText(/2025-11-30/)).toBeInTheDocument();
  });
});

describe("PnlAttributionSection · state=ok", () => {
  it("renders segment list with display strings and total", () => {
    renderWithState({ kind: "ok" });
    expect(screen.queryByTestId("data-section-loading")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-section-error")).not.toBeInTheDocument();
    expect(screen.getByText("Carry")).toBeInTheDocument();
    expect(screen.getByText("Roll-down")).toBeInTheDocument();
    expect(screen.getByText("+15.00 亿")).toBeInTheDocument();
    expect(screen.getByText("-3.00 亿")).toBeInTheDocument();
    // total appears in the extra slot (getAllByText since "+32.00 亿" may appear in chart title too)
    expect(screen.getAllByText("+32.00 亿").length).toBeGreaterThan(0);
  });

  it("does NOT use Math.abs: negative raw segment's display retains minus sign", () => {
    renderWithState({ kind: "ok" });
    expect(screen.getByText("-3.00 亿")).toBeInTheDocument();
  });
});
