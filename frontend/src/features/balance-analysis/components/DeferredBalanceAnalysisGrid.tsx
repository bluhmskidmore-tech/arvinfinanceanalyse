import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";

import type { MossAgGridProps } from "../../../components/grid";

// React.lazy 无法保留泛型组件签名，模块级持有 unknown 实例化（泛型实例化赋值，非强转）。
type UntypedMossAgGrid = (props: MossAgGridProps<unknown>) => ReactElement;

const LazyMossAgGrid = lazy(async () => {
  const { MossAgGrid } = await import("../../../components/grid/MossAgGrid");
  const Component: UntypedMossAgGrid = MossAgGrid;
  return { default: Component };
});

function gridHeight(height: MossAgGridProps["height"]): string | undefined {
  if (height === undefined) {
    return undefined;
  }
  return typeof height === "number" ? `${height}px` : height;
}

export function DeferredBalanceAnalysisGrid<TData = unknown>(
  props: MossAgGridProps<TData>,
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    const details = hostRef.current?.closest("details");
    if (!details) {
      setShouldLoad(true);
      return;
    }

    const syncWithDetails = () => {
      if (details.open) {
        setShouldLoad(true);
      }
    };
    syncWithDetails();
    details.addEventListener("toggle", syncWithDetails);
    return () => details.removeEventListener("toggle", syncWithDetails);
  }, []);

  return (
    <div ref={hostRef} data-deferred-balance-grid>
      {shouldLoad ? (
        <Suspense
          fallback={
            <div
              aria-label="表格加载中"
              data-testid={
                props["data-testid"] ? `${props["data-testid"]}-loading` : "balance-grid-loading"
              }
              style={{ height: gridHeight(props.height) }}
            />
          }
        >
          <LazyMossAgGrid {...(props as MossAgGridProps<unknown>)} />
        </Suspense>
      ) : null}
    </div>
  );
}
