import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
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

function buildMaturityOption(model: BalanceStageBottomModel): EChartsOption {
  const nct = nocturneTokens.color;
  const hasCategories = model.maturityCategories.length > 0;
  const categories = hasCategories ? model.maturityCategories : ["无真实数据"];
  // Missing buckets stay null so ECharts leaves a gap instead of drawing a zero bar.
  const assetSeries = hasCategories ? model.assetSeries : [null];
  const liabilitySeries = hasCategories ? model.liabilitySeries : [null];
  const gapSeries = hasCategories ? model.gapSeries : [null];
  return {
    grid: { left: 48, right: 16, top: 36 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { rotate: 28, fontSize: designTokens.fontSize[11], color: nct.inkMuted },
      axisLine: { lineStyle: { color: nct.line } },
    },
    yAxis: {
      type: "value",
      name: "亿",
      nameTextStyle: { fontSize: designTokens.fontSize[11], color: nct.inkMuted },
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
  const maturityOption = buildMaturityOption(model);

  const maturityPanel = (
    <ChartCard
      flat
      title={isTerminal ? undefined : "期限结构"}
      ariaLabel="期限结构"
      question="资产、负债与净缺口"
      unit="亿元"
      height={CHART_CARD_HEIGHTS.hero}
      option={model.maturityCategories.length ? maturityOption : null}
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
