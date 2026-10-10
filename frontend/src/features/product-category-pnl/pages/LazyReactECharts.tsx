import { useEffect, useState } from "react";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

import {
  ChartCard,
  type ChartCardProps,
} from "../../../components/charts/ChartCard";
import {
  getLoadedReactECharts,
  loadReactECharts,
  type ReactEChartsComponent,
} from "./lazyReactEChartsLoader";
import styles from "./LazyReactECharts.module.css";

type LazyChartCardProps = Omit<ChartCardProps, "chartRenderer"> & {
  canvasClassName?: string;
  onEvents?: EChartsReactProps["onEvents"];
};

export function LazyChartCard({
  canvasClassName,
  onEvents,
  ...chartCardProps
}: LazyChartCardProps) {
  const [EChartRenderer, setEChartRenderer] = useState<ReactEChartsComponent | null>(
    () => getLoadedReactECharts(),
  );

  useEffect(() => {
    if (EChartRenderer) {
      return undefined;
    }
    let active = true;
    void loadReactECharts().then((component) => {
      if (active) {
        setEChartRenderer(() => component);
      }
    });
    return () => {
      active = false;
    };
  }, [EChartRenderer]);

  return (
    <ChartCard
      {...chartCardProps}
      chartRenderer={({ option, height }) => {
        const className = [styles.canvas, styles[`height${height}`], canvasClassName]
          .filter(Boolean)
          .join(" ");
        if (!EChartRenderer) {
          return <div className={className} aria-hidden="true" />;
        }
        return (
          <EChartRenderer
            option={option}
            className={className}
            notMerge
            lazyUpdate
            onEvents={onEvents}
          />
        );
      }}
    />
  );
}
