import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

describe("CrossAssetPage route loading boundary", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("../features/cross-asset/pages/CrossAssetDriversPage");
  });

  it("shows a local route loading fallback until the heavy page module resolves", async () => {
    const pageModule = deferred<{
      default: () => JSX.Element;
    }>();

    vi.doMock("../features/cross-asset/pages/CrossAssetDriversPage", () => pageModule.promise);

    const { default: CrossAssetPage } = await import("../features/cross-asset/pages/CrossAssetPage");

    render(<CrossAssetPage />);

    const loadingBoundary = screen.getByTestId("cross-asset-route-loading");
    expect(loadingBoundary).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("页面加载中");

    pageModule.resolve({
      default: () => <div data-testid="cross-asset-drivers-page">cross asset drivers</div>,
    });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.queryByTestId("cross-asset-route-loading")).not.toBeInTheDocument();
  });
});
