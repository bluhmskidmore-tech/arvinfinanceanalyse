import { useMemo } from "react";

import type {
  ChoiceMacroLatestPayload,
  MacroBondLinkageEnvironmentScore,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import {
  buildDerivedSpreadsBarOption,
  buildLinkageEnvironmentBarOption,
} from "../lib/charts/linkageEnvironmentBarChartOption";
import { buildLinkageCorrelationBarOption } from "../lib/charts/linkageCorrelationBarChartOption";

type MarketDataLinkageChartsProps = {
  environmentScore?: Partial<MacroBondLinkageEnvironmentScore>;
  derivedSpreads?: ChoiceMacroLatestPayload["derived_spreads"];
  correlations?: readonly MacroBondLinkageTopCorrelation[];
};

export function MarketDataLinkageEnvironmentChart({
  environmentScore,
  derivedSpreads,
}: Pick<MarketDataLinkageChartsProps, "environmentScore" | "derivedSpreads">) {
  const envOption = useMemo(
    () => buildLinkageEnvironmentBarOption(environmentScore),
    [environmentScore],
  );
  const spreadOption = useMemo(() => buildDerivedSpreadsBarOption(derivedSpreads), [derivedSpreads]);

  return (
    <div className="market-data-linkage-chart-stack" data-testid="market-data-linkage-environment-charts">
      <ChartCard
        flat
        title="环境评分"
        option={envOption}
        height={220}
        legend="none"
        testId="market-data-linkage-environment-bar"
        emptyMessage="缺少 environment_score 分项，无法绘制环境柱图。"
      />
      <ChartCard
        flat
        title="期限利差"
        unit="bp"
        option={spreadOption}
        height={220}
        legend="none"
        testId="market-data-linkage-derived-spreads-bar"
        emptyMessage="缺少同日、可用的期限利差数据。"
      />
    </div>
  );
}

export function MarketDataLinkageCorrelationChart({
  correlations = [],
  note = "截面相关（3M/6M/1Y 窗口），非滚动相关曲线。",
}: Pick<MarketDataLinkageChartsProps, "correlations"> & { note?: string }) {
  const option = useMemo(() => buildLinkageCorrelationBarOption(correlations), [correlations]);

  return (
    <div
      id="market-data-linkage-correlation"
      className="market-data-linkage-chart-block market-data-spreads-chart-panel"
      data-testid="market-data-linkage-correlation-wrap"
    >
      <ChartCard
        flat
        title="相关强度"
        question={note}
        option={option}
        height={280}
        legendRows={2}
        testId="market-data-linkage-correlation-bar"
        emptyMessage="缺少 top_correlations，无法绘制相关强度图。"
      />
    </div>
  );
}
