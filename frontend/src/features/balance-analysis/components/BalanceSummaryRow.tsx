import { SummaryBlock } from "../../../components/SummaryBlock";
import { BaseChart } from "../../../components/charts/BaseChart";
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

function buildAllocationChartOption(
  model: BalanceStageSummaryModel,
  includeTitle: boolean,
): EChartsOption {
  const nct = nocturneTokens.color;
  const items = model.allocationItems.length
    ? model.allocationItems
    : [{ label: "无真实数据", value: 0, color: nct.inkMuted }];
  return {
    title: includeTitle
      ? {
          text: "资产负债净头寸（真实数据）",
          left: 0,
          top: 0,
          /* canvas 读不到 CSS 变量，取 nocturneTokens 常量（数值源=tokens.css Nocturne scope）。 */
          textStyle: { fontSize: 14, fontWeight: 700, color: nct.ink },
        }
      : undefined,
    grid: { left: 8, right: 8, top: includeTitle ? 40 : 16, bottom: 24, containLabel: true },
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
      axisLabel: { width: 72, overflow: "truncate", fontSize: 10, color: nct.inkSoft },
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
  const allocationChartOption = buildAllocationChartOption(model, !isTerminal);

  const summaryBlock = (
    <SummaryBlock
      title={isTerminal ? "" : "本期资产负债摘要"}
      content={model.content}
      tags={model.tags}
    />
  );

  const chartBlock = (
    <>
      <div className={isTerminal ? rowStyles.chartPanelTerminal : rowStyles.chartPanel}>
        {/* opts.renderer=canvas 为 echarts 默认值，迁 BaseChart 后省略等价。 */}
        <BaseChart option={allocationChartOption} height={isTerminal ? 210 : 240} />
      </div>
      <div className={rowStyles.netPositionFoot}>净头寸: {model.allocationNetValue}</div>
    </>
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
