import { SummaryBlock } from "../../../components/SummaryBlock";
import { BaseChart } from "../../../components/charts/BaseChart";
import { type EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import dhStyles from "../../workbench/dashboard-home/dashboardHome.module.css";
import type { BalanceStageSummaryModel } from "../pages/balanceAnalysisPageModel";
import { BalanceStageTerminalPanel } from "./BalanceStageTerminalPanel";
import rowStyles from "./balanceAnalysisStageRow.module.css";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";

type BalanceSummaryRowProps = {
  model: BalanceStageSummaryModel;
  variant?: "default" | "terminal";
};

function riskBadgeClass(level: "low" | "mid" | "high") {
  if (level === "low") {
    return rowStyles.riskBadgeLow;
  }
  if (level === "high") {
    return rowStyles.riskBadgeHigh;
  }
  return rowStyles.riskBadgeMid;
}

function buildAllocationChartOption(
  model: BalanceStageSummaryModel,
  includeTitle: boolean,
): EChartsOption {
  const items = model.allocationItems.length
    ? model.allocationItems
    : [{ label: "无真实数据", value: 0, color: designTokens.color.cockpit.ink450 }];
  return {
    title: includeTitle
      ? {
          text: "资产负债净头寸（真实数据）",
          left: 0,
          top: 0,
          /* 图表标题墨色无同值 token，保留字面量（echarts 读不到 CSS 变量）。 */
          textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
        }
      : undefined,
    grid: { left: 8, right: 8, top: includeTitle ? 40 : 16, bottom: 24 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "value", axisLabel: { formatter: "{value}" } },
    yAxis: {
      type: "category",
      data: items.map((item) => item.label),
      axisLabel: { width: 72, overflow: "truncate", fontSize: 10 },
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
    <table className={dhStyles.dhTerminalTable}>
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
