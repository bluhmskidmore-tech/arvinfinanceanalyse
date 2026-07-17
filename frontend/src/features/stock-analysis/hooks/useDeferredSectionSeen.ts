import { useCallback, useEffect, useState } from "react";

const DEFAULT_DEFERRED_SECTION_FALLBACK_MS = 1_000;

export function useDeferredSectionSeen<TElement extends HTMLElement>(
  enabled: boolean,
  delayMs = DEFAULT_DEFERRED_SECTION_FALLBACK_MS,
) {
  const [node, setNode] = useState<TElement | null>(null);
  const [seen, setSeen] = useState(false);
  const ref = useCallback((nextNode: TElement | null) => {
    setNode(nextNode);
  }, []);

  useEffect(() => {
    if (seen || !enabled) return undefined;

    if (typeof IntersectionObserver === "undefined") {
      const timer = window.setTimeout(() => setSeen(true), delayMs);
      return () => window.clearTimeout(timer);
    }

    if (!node) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [delayMs, enabled, node, seen]);

  return { ref, seen };
}
