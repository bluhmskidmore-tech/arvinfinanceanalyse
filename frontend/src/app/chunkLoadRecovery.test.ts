import { afterEach, describe, expect, it, vi } from "vitest";
import { installChunkLoadRecovery } from "./chunkLoadRecovery";

let cleanup: (() => void) | undefined;
afterEach(() => {
  cleanup?.();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

function setup() {
  const target = new EventTarget();
  const reload = vi.fn();
  vi.stubGlobal("window", Object.assign(target, { location: { reload } }));
  cleanup = installChunkLoadRecovery();
  return { target, reload };
}

function failedImport(message = "Failed to fetch dynamically imported module: /assets/MarketHomePage-old.js") {
  return Object.assign(new Event("vite:preloadError", { cancelable: true }), { payload: new TypeError(message) });
}

describe("chunk load recovery", () => {
  it("reloads the document once and keeps its guard after reinstalling without suppressing the failure", () => {
    const { target, reload } = setup();
    const event = failedImport();
    target.dispatchEvent(event);
    expect(reload).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(false);
    cleanup?.();
    cleanup = installChunkLoadRecovery();
    const retry = failedImport();
    target.dispatchEvent(retry);
    expect(reload).toHaveBeenCalledOnce();
    expect(retry.defaultPrevented).toBe(false);
  });

  it("does not reload for module evaluation or application errors", () => {
    const { target, reload } = setup();
    const event = failedImport("Cannot read properties of undefined");
    target.dispatchEvent(event);
    expect(reload).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("leaves errors visible when storage is unavailable", () => {
    const { target, reload } = setup();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    const event = failedImport();
    target.dispatchEvent(event);
    expect(reload).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("stops recovery when its listener is removed", () => {
    const { target, reload } = setup();
    cleanup?.();
    target.dispatchEvent(failedImport());
    expect(reload).not.toHaveBeenCalled();
  });
});
