import { useEffect, useRef, useState } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import type { BalanceZqtzMaturityStructure } from "../../../api/contracts";
import { nullableNumber } from "../lib/balanceMovementShareModel";

export function MaturityDistributionChart({ structure, onSelect }: {
  structure: BalanceZqtzMaturityStructure;
  onSelect: (key: string) => void;
}) {
  const [mounted, setMounted] = useState(() => typeof globalThis.IntersectionObserver !== "function");
  const placeholderRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (mounted || !placeholderRef.current) return undefined;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setMounted(true);
        observer.disconnect();
      }
    }, { rootMargin: "300px 0px" });
    observer.observe(placeholderRef.current);
    return () => observer.disconnect();
  }, [mounted]);
  if (!mounted) {
    return <div ref={placeholderRef} className="balance-movement-maturity-chart-placeholder"
      data-testid="balance-movement-maturity-chart-placeholder" aria-hidden="true" />;
  }
  return (
          <ReactECharts
            option={{
              animation: false,
              grid: { left: 60, right: 28, top: 40, bottom: 65 },
              tooltip: { trigger: "axis", renderMode: "richText", valueFormatter: (value) => `${value} 亿元` },
              xAxis: { type: "category", data: structure.buckets.map((bucket) => bucket.bucket_label),
                axisLabel: { color: nocturneTokens.color.inkSoft, interval: 0, rotate: 20 } },
              yAxis: { type: "value", name: "亿元", axisLabel: { color: nocturneTokens.color.inkMuted },
                splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft } } },
              series: [{ type: "bar", barMaxWidth: 44,
                label: { show: true, position: "top", color: nocturneTokens.color.inkSoft },
                data: structure.buckets.map((bucket) => ({
                  value: nullableNumber(bucket.current_amount) === null ? null : Number((Number(bucket.current_amount) / 1e8).toFixed(2)),
                  itemStyle: { color: bucket.maturity_bucket === "unknown" ? nocturneTokens.color.amber : nocturneTokens.color.blue },
                })),
              }],
            } satisfies EChartsOption}
            onEvents={{ click: (event: { dataIndex: number }) => {
              const bucket = structure.buckets[event.dataIndex];
              if (bucket) onSelect(bucket.maturity_bucket);
            } }}
          />
  );
}
