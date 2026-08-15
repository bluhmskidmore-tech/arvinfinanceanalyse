import { BaseChart } from "../../../components/charts/BaseChart";
import { CalendarList } from "../../../components/CalendarList";
import { type EChartsOption } from "../../../lib/echarts";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import { BalanceStageTerminalPanel } from "./BalanceStageTerminalPanel";
import rowStyles from "./balanceAnalysisStageRow.module.css";
import type { BalanceStageBottomModel } from "../pages/balanceAnalysisPageModel";

type BalanceBottomRowProps = {
  model: BalanceStageBottomModel;
  variant?: "default" | "terminal";
};

function buildMaturityOption(model: BalanceStageBottomModel, includeTitle: boolean): EChartsOption {
  const nct = nocturneTokens.color;
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
          /* canvas 读不到 CSS 变量，取 nocturneTokens 常量（数值源=tokens.css Nocturne scope）。 */
          textStyle: { fontSize: 14, fontWeight: 700, color: nct.ink },
        }
      : undefined,
    legend: {
      top: includeTitle ? 28 : 8,
      textStyle: { fontSize: 10, color: nct.inkSoft },
    },
    grid: { left: 48, right: 16, top: includeTitle ? 56 : 36, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { rotate: 28, fontSize: 10, color: nct.inkMuted },
      axisLine: { lineStyle: { color: nct.line } },
    },
    yAxis: {
      type: "value",
      name: "亿",
      nameTextStyle: { fontSize: 10, color: nct.inkMuted },
      axisLabel: { color: nct.inkMuted, fontSize: designTokens.fontSize[11] },
      splitLine: { lineStyle: { color: nct.lineSoft } },
    },
    series: [
      {
        name: "资产",
        type: "bar",
        data: assetSeries,
        itemStyle: { color: nct.blue },
      },
      {
        name: "负债",
        type: "bar",
        data: liabilitySeries,
        itemStyle: { color: nct.red },
      },
      {
        name: "净缺口",
        type: "bar",
        /* 2026-07-19 决议：ALM 正缺口≠经营利好，禁止映射 up 绿；正缺口走中性
           次级墨（系列级色 = 图例色，二者同源），负缺口以 down 红仅标方向。 */
        itemStyle: { color: nct.inkSoft },
        data: gapSeries.map((value) => ({
          value,
          itemStyle: value !== null && value < 0 ? { color: nct.red } : undefined,
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
    /* opts.renderer=canvas 为 echarts 默认值，迁 BaseChart 后省略等价。 */
    <BaseChart option={maturityOption} height={isTerminal ? 260 : 300} />
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
        <BalanceStageTerminalPanel title="关键日历（负债到期关注）" wide>
          <div className={rowStyles.calendarGrid}>
            <CalendarList items={model.calendarItems} />
          </div>
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
