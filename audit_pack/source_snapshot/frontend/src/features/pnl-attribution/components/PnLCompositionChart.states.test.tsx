import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { PnLCompositionChart } from "./PnLCompositionChart";
import type { DataSectionState } from "../../../components/DataSection.types";

function renderWith(state: DataSectionState) {
  render(<PnLCompositionChart data={null} state={state} onRetry={vi.fn()} />);
}

describe("PnLCompositionChart · state=loading", () => {
  it("shows loading placeholder", () => {
    renderWith({ kind: "loading" });
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
  });
});

describe("PnLCompositionChart · state=error", () => {
  it("shows error with retry", () => {
    renderWith({ kind: "error" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });
});

describe("PnLCompositionChart · state=vendor_unavailable", () => {
  it("shows vendor unavailable", () => {
    renderWith({ kind: "vendor_unavailable" });
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
  });
});

describe("PnLCompositionChart · state=explicit_miss", () => {
  it("shows explicit miss", () => {
    renderWith({ kind: "explicit_miss", requested_date: "2025-12-30" });
    expect(screen.getByTestId("data-section-explicit-miss")).toBeInTheDocument();
    expect(screen.getByText(/2025-12-30/)).toBeInTheDocument();
  });
});
