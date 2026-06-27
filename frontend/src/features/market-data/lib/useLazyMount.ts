import { useEffect, useRef, useState } from "react";
import type React from "react";

type UseLazyMountOptions = {
  rootMargin?: string;
  threshold?: number;
  fallbackDelayMs?: number;
};

type UseLazyMountResult = {
  ref: React.RefObject<HTMLDivElement>;
  shouldMount: boolean;
};

const DEFAULT_ROOT_MARGIN = "200px";
const DEFAULT_THRESHOLD = 0;
const DEFAULT_FALLBACK_DELAY_MS = 1200;

export function useLazyMount(options?: UseLazyMountOptions): UseLazyMountResult {
  const ref = useRef<HTMLDivElement>(null);
  const [shouldMount, setShouldMount] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const config = optionsRef.current;
    const rootMargin = config?.rootMargin ?? DEFAULT_ROOT_MARGIN;
    const threshold = config?.threshold ?? DEFAULT_THRESHOLD;
    const fallbackDelayMs = config?.fallbackDelayMs ?? DEFAULT_FALLBACK_DELAY_MS;

    const activate = (): void => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setShouldMount(true);
    };

    if (typeof IntersectionObserver === "undefined") {
      timeoutRef.current = window.setTimeout(activate, fallbackDelayMs);
      return () => {
        if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      };
    }

    const node = ref.current;
    if (!node) {
      timeoutRef.current = window.setTimeout(activate, fallbackDelayMs);
      return () => {
        if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      };
    }

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            activate();
            break;
          }
        }
      },
      { rootMargin, threshold },
    );
    observerRef.current.observe(node);

    timeoutRef.current = window.setTimeout(activate, fallbackDelayMs);

    return () => {
      if (observerRef.current) observerRef.current.disconnect();
      if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
      observerRef.current = null;
      timeoutRef.current = null;
    };
  }, []);

  return { ref, shouldMount };
}
