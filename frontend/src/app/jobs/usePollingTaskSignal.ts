import { useCallback, useEffect, useRef } from "react";

/** A page lifetime signal only; never sends a backend cancellation request. */
export function usePollingTaskSignal() {
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    return () => controller.abort();
  }, []);
  return useCallback(() => controllerRef.current?.signal, []);
}
