import { act, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { Component, Suspense, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { installChunkLoadRecovery } from "../app/chunkLoadRecovery";
import { lazyWorkbenchPage, preloadWorkbenchRouteElement } from "./workbenchRouteModules";

type PageModule = { default: () => null };
let cleanupRecovery: (() => void) | undefined;
afterEach(() => {
  cleanupRecovery?.();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
  document.querySelectorAll("link[data-review-preload]").forEach((link) => link.remove());
});

function setupRecovery() {
  sessionStorage.clear();
  const reload = vi.fn();
  const realWindow = window;
  vi.stubGlobal("window", new Proxy(realWindow, {
    get(target, property) {
      if (property === "location") return { reload };
      if (property === "addEventListener" || property === "removeEventListener" || property === "dispatchEvent") {
        return target[property].bind(target);
      }
      return Reflect.get(target, property, target);
    },
  }));
  cleanupRecovery = installChunkLoadRecovery();
  return reload;
}

function productionVitePreload() {
  const require = createRequire(import.meta.url);
  const viteRoot = dirname(require.resolve("vite/package.json"));
  const source = readFileSync(resolve(viteRoot, "dist/node/chunks/node.js"), "utf8");
  const start = source.indexOf("function preload(baseModule, deps, importerUrl) {");
  const end = source.indexOf("\nfunction getPreloadCode(", start);
  if (start < 0 || end < 0) throw new Error("The installed Vite preload helper could not be inspected.");
  // Inject only import.meta's environment; execute Vite's actual seen-cache,
  // stylesheet, event and failure handling code unchanged.
  return new Function("__VITE_IS_MODERN__", "assetsURL", "seen", "scriptRel", "importMeta",
    source.slice(start, end).replaceAll("import.meta", "importMeta") + "\nreturn preload;",
  )(true, (dep: string) => dep, {}, "modulepreload", { url: "https://moss.test/assets/index.js" }) as
    (load: () => Promise<PageModule>, deps: string[]) => Promise<PageModule | undefined>;
}

class ErrorBoundary extends Component<{
  children: ReactNode;
  onError: (error: Error) => void;
}, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { this.props.onError(error); }
  render() { return this.state.failed ? <div data-testid="module-error" /> : this.props.children; }
}

async function renderFailure(page: ReactNode, error: Error) {
  const onError = vi.fn();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  const preventExpectedRenderError = (event: ErrorEvent) => {
    if (event.error === error) event.preventDefault();
  };
  window.addEventListener("error", preventExpectedRenderError);
  try {
    await act(async () => {
      render(<ErrorBoundary onError={onError}><Suspense fallback={null}>{page}</Suspense></ErrorBoundary>);
    });
    expect(screen.getByTestId("module-error")).toBeInTheDocument();
    expect(onError).toHaveBeenCalledWith(error);
  } finally {
    window.removeEventListener("error", preventExpectedRenderError);
  }
}

describe("active route resource failure", () => {
  it("recovers once while the actual Vite module failure stays rejected and reaches React.lazy", async () => {
    const reload = setupRecovery();
    const preload = productionVitePreload();
    const error = new TypeError("Failed to fetch dynamically imported module: /assets/current-page.js");
    const loader = vi.fn(() => preload(() => Promise.reject(error), []) as Promise<PageModule>);
    const LazyPage = lazyWorkbenchPage(loader);
    preloadWorkbenchRouteElement(<section><LazyPage /></section>);
    await expect(loader.mock.results[0].value).rejects.toBe(error);
    expect(reload).toHaveBeenCalledTimes(1);

    preloadWorkbenchRouteElement(<LazyPage />);
    await renderFailure(<LazyPage />, error);
    expect(loader).toHaveBeenCalledTimes(1);
    await expect(preload(() => Promise.reject(error), [])).rejects.toBe(error);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("keeps real Vite CSS failure visible instead of accepting its seen-cache false success", async () => {
    const reload = setupRecovery();
    const preload = productionVitePreload();
    const cssUrl = "https://moss.test/assets/review-preload.css";
    const pageModule = vi.fn(async () => ({ default: () => null }));
    const loader = vi.fn(() => preload(pageModule, [cssUrl]) as Promise<PageModule>);
    const LazyPage = lazyWorkbenchPage(loader);
    preloadWorkbenchRouteElement(<LazyPage />);
    const failure = (loader.mock.results[0].value as Promise<PageModule>).catch((error: unknown) => error);
    const failedLink = document.querySelector<HTMLLinkElement>(`link[href="${cssUrl}"]`)!;
    failedLink.dataset.reviewPreload = "true";
    failedLink.dispatchEvent(new Event("error"));
    const error = await failure;
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toContain("Unable to preload CSS");
    expect(reload).toHaveBeenCalledTimes(1);
    expect(pageModule).not.toHaveBeenCalled();

    // Retrying the dependency itself falsely succeeds without new CSS. The
    // active route must retain its original rejected Promise instead.
    const probeModule = vi.fn(async () => ({ default: () => null }));
    await expect(preload(probeModule, [cssUrl])).resolves.toMatchObject({ default: expect.any(Function) });
    expect(document.querySelectorAll(`link[href="${cssUrl}"]`)).toHaveLength(1);
    preloadWorkbenchRouteElement(<LazyPage />);
    await renderFailure(<LazyPage />, error as Error);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(pageModule).not.toHaveBeenCalled();
  });
});
