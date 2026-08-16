import { useEffect, useState } from "react";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

import {
  getLoadedReactECharts,
  loadReactECharts,
  type ReactEChartsComponent,
} from "./lazyReactEChartsLoader";

export function LazyReactECharts(props: EChartsReactProps) {
  const [ReactECharts, setReactECharts] = useState<ReactEChartsComponent | null>(
    () => getLoadedReactECharts(),
  );

  useEffect(() => {
    if (ReactECharts) {
      return undefined;
    }
    let active = true;
    void loadReactECharts().then((component) => {
      if (active) {
        setReactECharts(() => component);
      }
    });
    return () => {
      active = false;
    };
  }, [ReactECharts]);

  if (!ReactECharts) {
    // 复用画布自身的类名占位：高度逐主题、逐断点与真实画布一致，出图时不抖动。
    return <div className={props.className} aria-hidden="true" />;
  }

  return <ReactECharts {...props} />;
}
