const RECOVERY_KEY = "moss:chunk-load-recovery-at";
const RECOVERY_COOLDOWN_MS = 60_000;

export function isChunkLoadError(error: unknown): boolean {
  return error instanceof Error && /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS/i.test(error.message);
}

export function installChunkLoadRecovery() {
  const recover = (event: Event) => {
    if (!isChunkLoadError((event as Event & { payload?: unknown }).payload)) return;

    // Persist before reloading: a missing asset or offline server must not loop.
    try {
      const now = Date.now();
      const previous = Number(sessionStorage.getItem(RECOVERY_KEY));
      if (previous && now - previous < RECOVERY_COOLDOWN_MS) return;
      sessionStorage.setItem(RECOVERY_KEY, String(now));
    } catch {
      // Without a durable guard, leave recovery to the route's reload link.
      return;
    }
    window.location.reload();
    // Leave Vite's event unprevented: preventing it resolves the failed import
    // as undefined and hides the real error from React.lazy and route recovery.
  };
  window.addEventListener("vite:preloadError", recover);
  return () => window.removeEventListener("vite:preloadError", recover);
}
