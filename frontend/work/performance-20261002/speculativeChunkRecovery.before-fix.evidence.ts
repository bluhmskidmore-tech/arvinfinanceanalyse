import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { installChunkLoadRecovery } from "../../src/app/chunkLoadRecovery";
import { lazyWorkbenchPage, preloadWorkbenchRoute } from "../../src/router/workbenchRouteModules";

type PageModule = { default: () => null };
type VitePreload = (loader: () => Promise<PageModule>, deps: string[]) => Promise<PageModule | undefined>;

const assets = resolve(process.cwd(), "dist/assets");
const helperFile = readdirSync(assets).find((file) => /^preload-helper-.*\.js$/.test(file));
if (!helperFile) throw new Error("The existing production Vite preload helper is required for this review.");
const { t: vitePreload } = await import(/* @vite-ignore */ resolve(assets, helperFile)) as { t: VitePreload };

let cleanup: (() => void) | undefined;
beforeEach(() => sessionStorage.clear());
afterEach(() => {
  cleanup?.();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

function setupRecovery() {
  const target = new EventTarget();
  const reload = vi.fn();
  vi.stubGlobal("window", Object.assign(target, { location: { reload } }));
  cleanup = installChunkLoadRecovery();
  return reload;
}

const moduleFailure = () => new TypeError("Failed to fetch dynamically imported module: /assets/review-unavailable.js");

describe("independent speculative chunk recovery counterexamples", () => {
  it("keeps the current document when only an unmounted navigation target fails to warm", async () => {
    const reload = setupRecovery();
    lazyWorkbenchPage("/review-unmounted-navigation-target", () =>
      vitePreload(() => Promise.reject(moduleFailure()), []) as Promise<PageModule>,
    );

    // WorkbenchShell uses precisely this catch for hover/focus/pointerdown.
    await preloadWorkbenchRoute("/review-unmounted-navigation-target").catch(() => undefined);
    expect(reload).not.toHaveBeenCalled();
  });

  it("retries a failed optional warm instead of caching an undefined module", async () => {
    setupRecovery();
    const loader = vi.fn(() => vitePreload(() => loader.mock.calls.length === 1
      ? Promise.reject(moduleFailure())
      : Promise.resolve({ default: () => null }), []) as Promise<PageModule>);
    lazyWorkbenchPage("/review-retry-optional-warm", loader);

    await preloadWorkbenchRoute("/review-retry-optional-warm").catch(() => undefined);
    await preloadWorkbenchRoute("/review-retry-optional-warm").catch(() => undefined);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("retains the existing automatic document recovery for a demanded module failure", async () => {
    const reload = setupRecovery();
    await vitePreload(() => Promise.reject(moduleFailure()), []);
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
