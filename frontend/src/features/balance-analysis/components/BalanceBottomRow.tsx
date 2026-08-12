import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { CalendarList } from "../../../components/CalendarList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import { BalanceStageTerminalPanel } from "./BalanceStageTerminalPanel";
import rowStyles from "./balanceAnalysisStageRow.module.css";
import type { BalanceStageBottomModel } from "../pages/balanceAnalysisPageModel";

type BalanceBottomRowProps = {
  model: BalanceStageBottomModel;
  variant?: "default" | "terminal";
};

function buildMaturityOption(model: BalanceStageBottomModel, includeTitle: boolean): EChartsOption {
  const hasCategories = model.maturityCategories.length > 0;
  const categories = hasCategories ? model.maturityCategories : ["无真实数据"];
  // Missing buckets stay null so ECharts leaves a gap instead of drawing a zero bar.
  const assetSeries = hasCategories ? model.assetSeries : [null];
  const liabilitySeries = hasCategories ? model.liabilitySeries : [null];
  const gapSeries = hasCategories ? model.gapSeries : [null];
  return {
    title: includeTitle
      ? {
          text: "期限结构（资产/负债/净缺口）",
          left: 0,
          top: 0,
          textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
        }
      : undefined,
    legend: { top: includeTitle ? 28 : 8, textStyle: { fontSize: 10 } },
    grid: { left: 48, right: 16, top: includeTitle ? 56 : 36, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: categories, axisLabel: { rotate: 28, fontSize: 10 } },
    yAxis: { type: "value", name: "亿", nameTextStyle: { fontSize: 10 } },
    series: [
      {
        name: "资产",
        type: "bar",
        data: assetSeries,
        itemStyle: { color: "#35679b" },
      },
      {
        name: "负债",
        type: "bar",
        data: liabilitySeries,
        itemStyle: { color: "#c76b66" },
      },
      {
        name: "净缺口",
        type: "bar",
        data: gapSeries.map((value) => ({
          value,
          itemStyle:
            value === null ? undefined : { color: value < 0 ? "#b76e00" : "#3f8a6a" },
        })),
      },
    ],
  };
}

export function BalanceBottomRow({ model, variant = "default" }: BalanceBottomRowProps) {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();
  const isTerminal = variant === "terminal";
  const maturityOption = buildMaturityOption(model, !isTerminal);

  const maturityPanel = (
    <ReactECharts
      option={maturityOption}
      style={{ height: isTerminal ? 260 : 300 }}
      opts={{ renderer: "canvas" }}
    />
  );

  const riskPanel = (
    <div className={rowStyles.riskMetricList}>
      {model.riskMetrics.map((m) => (
        <div key={m.label} className={rowStyles.riskMetricRow}>
          <span className={rowStyles.riskMetricLabel}>{m.label}</span>
          <span className={rowStyles.riskMetricValue}>{m.value}</span>
        </div>
      ))}
    </div>
  );

  return (
    <div
      data-testid="balance-analysis-bottom-row"
      className={
        isTerminal
          ? `${rowStyles.rowGrid} ${rowStyles.rowGridBottomTerminal}`
          : `${rowStyles.rowGrid} ${rowStyles.rowGridDefault}`
      }
      style={isTerminal ? undefined : gridStyle}
    >
      {isTerminal ? (
        <BalanceStageTerminalPanel title="期限结构">{maturityPanel}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefaultCompact} style={{ minHeight: 320 }}>
          {maturityPanel}
        </div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="风险指标">{riskPanel}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>
          <div className={rowStyles.panelTitle}>风险指标</div>
          {riskPanel}
        </div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="关键日历（负债到期关注）">
          <CalendarList items={model.calendarItems} />
        </BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>
          <div className={rowStyles.panelTitle}>关键日历（负债到期关注）</div>
          <CalendarList items={model.calendarItems} />
        </div>
      )}
    </div>
  );
}
