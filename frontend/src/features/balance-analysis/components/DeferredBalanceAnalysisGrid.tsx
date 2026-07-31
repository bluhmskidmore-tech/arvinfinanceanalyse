import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";

import type { MossAgGridProps } from "../../../components/grid";

type LazyMossAgGridComponent = <TData = unknown>(
  props: MossAgGridProps<TData>,
) => ReactElement;

const LazyMossAgGrid = lazy(async () => {
  const { MossAgGrid } = await import("../../../components/grid/MossAgGrid");
  return { default: MossAgGrid };
}) as unknown as LazyMossAgGridComponent;

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
          <LazyMossAgGrid<TData> {...props} />
        </Suspense>
      ) : null}
    </div>
  );
}
