import { useCallback, useEffect, useRef, useState } from "react";
import type { EChartsInstance } from "echarts-for-react/lib/types";

/**
 * Defers mounting an ECharts instance until its container has a non-zero
 * layout size, and calls `resize()` on later size changes (tab switches,
 * collapsed sections, window resize). Avoids the ECharts
 * "Can't get DOM width or height" warning when the chart mounts inside a
 * container that has not been laid out yet (e.g. behind a lazy tab pane).
 *
 * Uses a callback ref so the observer attaches even when the container
 * element appears after the initial mount (e.g. an empty-state early return
 * that later switches to the chart branch).
 *
 * Falls back to rendering immediately when ResizeObserver is unavailable
 * (e.g. in the jsdom test environment).
 */
export function useDeferredChartMount<T extends HTMLElement = HTMLDivElement>() {
  const [container, setContainer] = useState<T | null>(null);
  const chartRef = useRef<EChartsInstance | null>(null);
  const [ready, setReady] = useState(false);

  const containerRef = useCallback((node: T | null) => {
    setContainer(node);
  }, []);

  useEffect(() => {
    if (!container) return;

    const RO = globalThis.ResizeObserver;
    if (!RO) {
      setReady(true);
      return;
    }

    const hasSize = (target: HTMLElement) => target.clientWidth > 0 && target.clientHeight > 0;

    if (hasSize(container)) {
      setReady(true);
    }

    const ro = new RO(() => {
      if (hasSize(container)) {
        setReady(true);
      }
      chartRef.current?.resize();
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [container]);

  function onChartReady(instance: EChartsInstance) {
    chartRef.current = instance;
  }

  return { containerRef, ready, onChartReady };
}
