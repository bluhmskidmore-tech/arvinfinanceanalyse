import { SummaryBlock } from "../../../components/SummaryBlock";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { type EChartsOption } from "../../../lib/echarts";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import type { BalanceStageSummaryModel } from "../pages/balanceAnalysisPageModel";
import { BalanceStageTerminalPanel } from "./BalanceStageTerminalPanel";
import rowStyles from "./balanceAnalysisStageRow.module.css";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";

type BalanceSummaryRowProps = {
  model: BalanceStageSummaryModel;
  variant?: "default" | "terminal";
};

function riskBadgeClass(level: "low" | "mid" | "high" | "neutral") {
  if (level === "low") {
    return rowStyles.riskBadgeLow;
  }
  if (level === "high") {
    return rowStyles.riskBadgeHigh;
  }
  if (level === "neutral") {
    return rowStyles.riskBadgeNeutral;
  }
  return rowStyles.riskBadgeMid;
}

function buildAllocationChartOption(model: BalanceStageSummaryModel): EChartsOption {
  const nct = nocturneTokens.color;
  const items = model.allocationItems.length
    ? model.allocationItems
    : [{ label: "无真实数据", value: 0, color: nct.inkMuted }];
  return {
    grid: { left: 8, right: 8, top: 16 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: {
      type: "value",
      axisLabel: {
        formatter: "{value}",
        color: nct.inkMuted,
        fontSize: designTokens.fontSize[11],
      },
      splitLine: { lineStyle: { color: nct.lineSoft } },
    },
    yAxis: {
      type: "category",
      data: items.map((item) => item.label),
      axisLabel: { width: 72, overflow: "truncate", fontSize: designTokens.fontSize[11], color: nct.inkSoft },
      axisLine: { lineStyle: { color: nct.line } },
    },
    series: [
      {
        type: "bar",
        data: items.map((item) => ({
          value: item.value,
          itemStyle: { color: item.color },
        })),
        barWidth: 16,
      },
    ],
  };
}

export function BalanceSummaryRow({ model, variant = "default" }: BalanceSummaryRowProps) {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();
  const isTerminal = variant === "terminal";
  const allocationChartOption = buildAllocationChartOption(model);

  const summaryBlock = (
    <SummaryBlock
      title={isTerminal ? "" : "本期资产负债摘要"}
      content={model.content}
      tags={model.tags}
    />
  );

  const chartBlock = (
    <ChartCard
      flat
      title={isTerminal ? undefined : "资产负债净头寸"}
      ariaLabel="资产负债净头寸"
      height={CHART_CARD_HEIGHTS.default}
      legend="none"
      option={model.allocationItems.length ? allocationChartOption : null}
      footnote={`净头寸: ${model.allocationNetValue}`}
    />
  );

  const riskBlock = (
    <table className="balance-analysis-table">
      <thead>
        <tr>
          <th>维度</th>
          <th>当前</th>
          <th>压力</th>
          <th>情景</th>
        </tr>
      </thead>
      <tbody>
        {model.riskRows.map((row) => (
          <tr key={row.dim}>
            <td>
              <b>{row.dim}</b>
            </td>
            <td>
              <span className={`${rowStyles.riskBadge} ${riskBadgeClass(row.level)}`}>
                {row.current}
              </span>
            </td>
            <td>
              <span className={`${rowStyles.riskBadge} ${rowStyles.riskBadgeMid}`}>{row.stress}</span>
            </td>
            <td>
              <span className={`${rowStyles.riskBadge} ${rowStyles.riskBadgeMid}`}>
                {row.scenario}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <div
      data-testid="balance-analysis-summary-row"
      className={
        isTerminal
          ? `${rowStyles.rowGrid} ${rowStyles.rowGridTerminal}`
          : `${rowStyles.rowGrid} ${rowStyles.rowGridDefault}`
      }
      style={isTerminal ? undefined : gridStyle}
    >
      {isTerminal ? (
        <BalanceStageTerminalPanel title="本期资产负债摘要">{summaryBlock}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>{summaryBlock}</div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="资产负债净头寸">{chartBlock}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefaultCompact}>{chartBlock}</div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="风险全景">{riskBlock}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>
          <div className={rowStyles.panelTitle}>风险全景</div>
          {riskBlock}
        </div>
      )}
    </div>
  );
}
