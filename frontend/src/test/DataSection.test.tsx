import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DataSection } from "../components/DataSection";
import type { DataSectionState } from "../components/DataSection.types";

function renderWith(state: DataSectionState, children = <p>child content</p>) {
  const onRetry = vi.fn();
  render(
    <DataSection title="Overview" state={state} onRetry={onRetry}>
      {children}
    </DataSection>,
  );
  return { onRetry };
}

describe("DataSection · ok", () => {
  it("renders children when state.kind === 'ok'", () => {
    renderWith({ kind: "ok" }, <p data-testid="inner">alive</p>);
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("renders title as section header", () => {
    renderWith({ kind: "ok" });
    expect(screen.getByText("Overview")).toBeInTheDocument();
  });
});

describe("DataSection · loading", () => {
  it("shows loading message, hides children", () => {
    renderWith({ kind: "loading" }, <p data-testid="inner">should-hide</p>);
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
  });
});

describe("DataSection · error", () => {
  it("shows error UI and retry button", async () => {
    const { onRetry } = renderWith({ kind: "error", message: "fetch failed" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
    expect(screen.getByText(/fetch failed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /重试/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("has generic error copy when no message provided", () => {
    renderWith({ kind: "error" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });
});

describe("DataSection · empty", () => {
  it("shows empty placeholder", () => {
    renderWith({ kind: "empty" });
    expect(screen.getByTestId("data-section-empty")).toBeInTheDocument();
  });

  it("includes hint when provided", () => {
    renderWith({ kind: "empty", hint: "请先选择日期" });
    expect(screen.getByText("请先选择日期")).toBeInTheDocument();
  });
});

describe("DataSection · stale", () => {
  it("still renders children but overlays stale banner", () => {
    renderWith(
      { kind: "stale", effective_date: "2025-12-31", details: "vendor_stale" },
      <p data-testid="inner">partial-data</p>,
    );
    expect(screen.getByTestId("inner")).toBeInTheDocument();
    expect(screen.getByTestId("data-section-stale-banner")).toBeInTheDocument();
    expect(screen.getByText(/2025-12-31/)).toBeInTheDocument();
  });
});

describe("DataSection · fallback", () => {
  it("renders children and shows fallback banner with effective_date", () => {
    renderWith(
      { kind: "fallback", effective_date: "2025-12-30" },
      <p data-testid="inner">partial-data</p>,
    );
    expect(screen.getByTestId("inner")).toBeInTheDocument();
    expect(screen.getByTestId("data-section-fallback-banner")).toBeInTheDocument();
    expect(screen.getByText(/2025-12-30/)).toBeInTheDocument();
  });
});

describe("DataSection · vendor_unavailable", () => {
  it("shows vendor_unavailable placeholder, hides children", () => {
    renderWith(
      { kind: "vendor_unavailable", details: "bond analytics 未返回" },
      <p data-testid="inner">should-hide</p>,
    );
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
    expect(screen.getByText(/bond analytics 未返回/)).toBeInTheDocument();
  });
});

describe("DataSection · explicit_miss", () => {
  it("shows explicit_miss placeholder with requested date", () => {
    renderWith(
      { kind: "explicit_miss", requested_date: "2025-11-30", details: "该日无数据" },
      <p data-testid="inner">should-hide</p>,
    );
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
    expect(screen.getByTestId("data-section-explicit-miss")).toBeInTheDocument();
    expect(screen.getByText(/2025-11-30/)).toBeInTheDocument();
  });
});

describe("DataSection · header extra slot", () => {
  it("renders extra header content when provided", () => {
    render(
      <DataSection
        title="Overview"
        state={{ kind: "ok" }}
        onRetry={() => undefined}
        extra={<span data-testid="extra">badge</span>}
      >
        <p>content</p>
      </DataSection>,
    );
    expect(screen.getByTestId("extra")).toBeInTheDocument();
  });
});

describe("DataSection · state exhaustiveness", () => {
  it("exports DataSectionState from types module", async () => {
    const mod = await import("../components/DataSection.types");
    // compile-time type check — verify the union has all 8 kinds via a mapped
    // const to catch silent removal.
    const sample: DataSectionState[] = [
      { kind: "loading" },
      { kind: "error" },
      { kind: "empty" },
      { kind: "stale" },
      { kind: "fallback" },
      { kind: "vendor_unavailable" },
      { kind: "explicit_miss" },
      { kind: "ok" },
    ];
    expect(sample).toHaveLength(8);
    expect(typeof mod).toBe("object");
  });
});
