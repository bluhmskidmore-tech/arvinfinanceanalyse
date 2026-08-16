import { useCallback, useEffect, useState } from "react";

const DEFAULT_DEFERRED_SECTION_FALLBACK_MS = 1_000;

/**
 * 区块级"进入视口即视为已见"门控：一旦 seen 变 true 就不再回退，
 * 适合作为 React Query `enabled` 的可见性条件（容器 DOM 常驻，仅门控数据）。
 *
 * - 有 IntersectionObserver 时按 240px rootMargin 预热；
 * - 无 IO 环境（jsdom / 极老内核）退化为 delayMs 定时兜底；
 * - `markSeen` 供"点击章节导航直达"这类主动唤醒场景使用。
 */
export function useDeferredSectionSeen<TElement extends HTMLElement>(
  enabled: boolean,
  delayMs = DEFAULT_DEFERRED_SECTION_FALLBACK_MS,
) {
  const [node, setNode] = useState<TElement | null>(null);
  const [seen, setSeen] = useState(false);
  const ref = useCallback((nextNode: TElement | null) => {
    setNode(nextNode);
  }, []);
  const markSeen = useCallback(() => {
    setSeen(true);
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

  return { ref, seen, markSeen };
}
