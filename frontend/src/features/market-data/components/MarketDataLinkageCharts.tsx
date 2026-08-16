import { useMemo } from "react";

import type {
  ChoiceMacroLatestPayload,
  MacroBondLinkageEnvironmentScore,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import {
  buildDerivedSpreadsBarOption,
  buildLinkageEnvironmentBarOption,
} from "../lib/charts/linkageEnvironmentBarChartOption";
import { buildLinkageCorrelationBarOption } from "../lib/charts/linkageCorrelationBarChartOption";
import { MarketDataChartShell } from "./MarketDataChartShell";

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
      <MarketDataChartShell
        option={envOption}
        height={220}
        testId="market-data-linkage-environment-bar"
        emptyMessage="缺少 environment_score 分项，无法绘制环境柱图。"
      />
      {spreadOption ? (
        <MarketDataChartShell
          option={spreadOption}
          height={Math.max(160, (Object.keys(derivedSpreads ?? {}).length || 1) * 28)}
          testId="market-data-linkage-derived-spreads-bar"
          emptyMessage="缺少 derived_spreads。"
        />
      ) : null}
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
      <p className="market-data-linkage-chart-note">{note}</p>
      <MarketDataChartShell
        option={option}
        height={260}
        testId="market-data-linkage-correlation-bar"
        emptyMessage="缺少 top_correlations，无法绘制相关强度图。"
      />
    </div>
  );
}
