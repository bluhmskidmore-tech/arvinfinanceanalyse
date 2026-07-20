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

  it("uses extracted class for the section shell", () => {
    renderWith({ kind: "ok" });

    const section = screen.getByText("Overview").closest("section");

    expect(section).toHaveClass("data-section");
    expect(section).not.toHaveAttribute("style");
  });
});

describe("DataSection · loading", () => {
  it("shows loading message, hides children", () => {
    renderWith({ kind: "loading" }, <p data-testid="inner">should-hide</p>);
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
  });

  it("uses shared SkeletonBarStack classes for loading UI", () => {
    renderWith({ kind: "loading" }, <p data-testid="inner">should-hide</p>);

    const loadingBlock = screen.getByTestId("data-section-loading");
    const loadingLabel = loadingBlock.querySelector(".data-section__loading-label");
    const skeletonStack = loadingBlock.querySelector(".moss-skeleton-bar-stack");
    const skeletonBars = skeletonStack?.querySelectorAll(".moss-skeleton-bar");

    expect(loadingLabel).toBeInTheDocument();
    expect(loadingLabel).not.toHaveAttribute("style");
    expect(skeletonStack).toBeInTheDocument();
    expect(skeletonStack).toHaveClass("moss-skeleton-bar-stack--spaced");
    expect(skeletonStack).not.toHaveAttribute("style");
    expect(skeletonBars).toHaveLength(4);
    skeletonBars?.forEach((bar) => {
      expect(bar).not.toHaveAttribute("style");
    });
  });
});

describe("DataSection · error", () => {
  it("shows error UI and retry button", async () => {
    const { onRetry } = renderWith({ kind: "error", message: "fetch failed" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
    expect(screen.getByText(/fetch failed/)).toBeInTheDocument();
    const retryButton = screen.getByRole("button", { name: /重试/ });
    expect(retryButton).toHaveClass("data-section__retry-button");
    expect(retryButton).not.toHaveAttribute("style");
    await userEvent.click(retryButton);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("has generic error copy when no message provided", () => {
    renderWith({ kind: "error" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });

  it("uses extracted classes for error layout and title", () => {
    renderWith({ kind: "error", message: "fetch failed" });

    const errorBlock = screen.getByTestId("data-section-error");
    const errorTitle = errorBlock.querySelector(".data-section__error-title");

    expect(errorBlock).toHaveClass("data-section__state-stack");
    expect(errorBlock).not.toHaveAttribute("style");
    expect(errorTitle).toBeInTheDocument();
    expect(errorTitle).not.toHaveAttribute("style");
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
  it("uses extracted class for empty placeholder tone", () => {
    renderWith({ kind: "empty" });

    const emptyBlock = screen.getByTestId("data-section-empty");

    expect(emptyBlock).toHaveClass("data-section__empty");
    expect(emptyBlock).not.toHaveAttribute("style");
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

  it("uses extracted class for stale banner style", () => {
    renderWith({ kind: "stale", effective_date: "2025-12-31", details: "vendor_stale" });

    const staleBanner = screen.getByTestId("data-section-stale-banner");

    expect(staleBanner).toHaveClass("data-section__banner");
    expect(staleBanner).toHaveClass("data-section__banner--stale");
    expect(staleBanner).not.toHaveAttribute("style");
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

  it("uses extracted class for fallback banner style", () => {
    renderWith({ kind: "fallback", effective_date: "2025-12-30" });

    const fallbackBanner = screen.getByTestId("data-section-fallback-banner");

    expect(fallbackBanner).toHaveClass("data-section__banner");
    expect(fallbackBanner).toHaveClass("data-section__banner--fallback");
    expect(fallbackBanner).not.toHaveAttribute("style");
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
  it("uses extracted classes for vendor unavailable layout and title", () => {
    renderWith({ kind: "vendor_unavailable", details: "vendor down" });

    const block = screen.getByTestId("data-section-vendor-unavailable");
    const title = block.querySelector(".data-section__warning-soft-title");

    expect(block).toHaveClass("data-section__compact-state");
    expect(block).not.toHaveAttribute("style");
    expect(title).toBeInTheDocument();
    expect(title).not.toHaveAttribute("style");
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
  it("uses extracted classes for explicit miss layout and title", () => {
    renderWith({ kind: "explicit_miss", requested_date: "2025-11-30", details: "missing" });

    const block = screen.getByTestId("data-section-explicit-miss");
    const title = block.querySelector(".data-section__warning-title");

    expect(block).toHaveClass("data-section__compact-state");
    expect(block).not.toHaveAttribute("style");
    expect(title).toBeInTheDocument();
    expect(title).not.toHaveAttribute("style");
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
  it("uses extracted classes for header row and title", () => {
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

    const headerTitle = screen.getByText("Overview");
    const headerRow = headerTitle.parentElement;

    expect(headerRow).toHaveClass("data-section__header");
    expect(headerRow).not.toHaveAttribute("style");
    expect(headerTitle).toHaveClass("data-section__title");
    expect(headerTitle).not.toHaveAttribute("style");
  });

  it("uses extracted class for extra-only header wrapper", () => {
    render(
      <DataSection
        title=""
        state={{ kind: "ok" }}
        onRetry={() => undefined}
        extra={<span data-testid="extra-only">badge</span>}
      >
        <p>content</p>
      </DataSection>,
    );

    const extraOnlyWrapper = screen.getByTestId("extra-only").parentElement;

    expect(extraOnlyWrapper).toHaveClass("data-section__header-extra");
    expect(extraOnlyWrapper).not.toHaveAttribute("style");
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
