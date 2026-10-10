import { act, render, screen } from "@testing-library/react";
import { Suspense, useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { lazyWorkbenchPage, preloadWorkbenchRouteElement } from "./workbenchRouteModules";

describe("workbench route module reuse", () => {
  it("starts only declared active modules and shares their pending load with React.lazy", async () => {
    const readPageData = vi.fn();
    const renderPage = vi.fn();
    function Page() {
      renderPage();
      useEffect(() => { readPageData(); }, []);
      return <div data-testid="active-page" />;
    }
    let finishLoading!: (module: { default: typeof Page }) => void;
    const modulePending = new Promise<{ default: typeof Page }>((resolve) => { finishLoading = resolve; });
    const loader = vi.fn(() => modulePending);
    const otherLoader = vi.fn(async () => ({ default: () => <div /> }));
    const LazyPage = lazyWorkbenchPage(loader);
    lazyWorkbenchPage(otherLoader);
    expect(loader).not.toHaveBeenCalled();
    expect(otherLoader).not.toHaveBeenCalled();

    preloadWorkbenchRouteElement(<section><LazyPage /></section>);
    preloadWorkbenchRouteElement(<LazyPage />);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(renderPage).not.toHaveBeenCalled();
    expect(readPageData).not.toHaveBeenCalled();

    render(<Suspense fallback={<div data-testid="module-pending" />}><LazyPage /></Suspense>);
    expect(screen.getByTestId("module-pending")).toBeInTheDocument();
    expect(loader).toHaveBeenCalledTimes(1);
    expect(readPageData).not.toHaveBeenCalled();

    await act(async () => {
      finishLoading({ default: Page });
      await modulePending;
    });
    expect(await screen.findByTestId("active-page")).toBeInTheDocument();
    expect(readPageData).toHaveBeenCalledTimes(1);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(otherLoader).not.toHaveBeenCalled();
    preloadWorkbenchRouteElement(<LazyPage />);
    expect(loader).toHaveBeenCalledTimes(1);
  });
});
