import { useSyncExternalStore } from "react";

const NARROW_QUERY = "(max-width: 1366px)";

function getNarrowMediaQueryList() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return null;
  }
  return window.matchMedia(NARROW_QUERY);
}

function subscribeNarrow(callback: () => void) {
  const mq = getNarrowMediaQueryList();
  if (!mq) {
    return () => undefined;
  }
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getNarrowSnapshot() {
  return getNarrowMediaQueryList()?.matches ?? false;
}

function getNarrowServerSnapshot() {
  return false;
}

/** ≤1366px: single column; wider: three equal columns. */
export function useBalanceAnalysisThreeColumnGridStyle() {
  const narrow = useSyncExternalStore(subscribeNarrow, getNarrowSnapshot, getNarrowServerSnapshot);
  return {
    display: "grid" as const,
    gridTemplateColumns: narrow ? ("1fr" as const) : ("1fr 1fr 1fr" as const),
    gap: 16,
    marginTop: 20,
  };
}
