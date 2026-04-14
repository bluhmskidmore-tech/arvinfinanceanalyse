import { useSyncExternalStore } from "react";

const NARROW_QUERY = "(max-width: 1366px)";

function subscribeNarrow(callback: () => void) {
  const mq = window.matchMedia(NARROW_QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getNarrowSnapshot() {
  return window.matchMedia(NARROW_QUERY).matches;
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
