import { useEffect, useRef, useState, type ReactNode } from "react";

const DEFAULT_ROOT_MARGIN = "300px 0px";

function supportsIntersectionObserver() {
  return typeof globalThis.IntersectionObserver === "function";
}

type LazyChartMountProps = {
  placeholderClassName: string;
  placeholderTestId?: string;
  rootMargin?: string;
  children: ReactNode;
};

/**
 * 图表进入视口附近才挂载 ECharts，一旦挂载不再卸载。
 *
 * 未挂载时用 `placeholderClassName` 复用画布自身的样式类占位，
 * 高度与真实画布逐主题、逐断点一致，滚动时不会抖动。
 *
 * 无 IntersectionObserver 的环境（jsdom、极老内核）收不到视口回调，
 * 只能首帧直接挂载，否则图表永远不会出现。
 */
export function LazyChartMount({
  placeholderClassName,
  placeholderTestId,
  rootMargin = DEFAULT_ROOT_MARGIN,
  children,
}: LazyChartMountProps) {
  const [mounted, setMounted] = useState(() => !supportsIntersectionObserver());
  const placeholderRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (mounted) {
      return undefined;
    }
    const node = placeholderRef.current;
    if (!node) {
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setMounted(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [mounted, rootMargin]);

  if (mounted) {
    return <>{children}</>;
  }

  return (
    <div
      ref={placeholderRef}
      className={placeholderClassName}
      data-testid={placeholderTestId}
      aria-hidden="true"
    />
  );
}
