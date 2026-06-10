import { Alert, Button } from "antd";
import type { UseQueryResult } from "@tanstack/react-query";

import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { LinkageSpreadTenorTable } from "../components/LinkageSpreadTenorTable";
import { LiveResultMetaStrip } from "../components/LiveResultMetaStrip";
import { KpiCard } from "../../../components/KpiCard";
import { toneFromSignedDisplayString, toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { formatSignedNumber } from "../lib/marketDataFormat";
import { RATE_TREND_DEFINITIONS } from "./marketDataMacroConstants";
import "./MarketDataPage.css";

type MacroDepthTabKey = "curve" | "spreads" | "linkage";

type SpreadTenorSlot = { tenor: "3Y" | "5Y" | "10Y"; point: MacroBondLinkageTopCorrelation | null };

type MacroBondLinkagePartial = Partial<MacroBondLinkagePayload>;

export type MarketDataMacroDepthTabsProps = {
  macroDepthTab: MacroDepthTabKey;
  onMacroDepthTabChange: (key: MacroDepthTabKey) => void;
  latestQuery: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>, Error>;
  rateTrendChartOption: EChartsOption | null;
  macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, Error>;
  spreadSlots: SpreadTenorSlot[];
  macroBondLinkage: MacroBondLinkagePartial;
};

const macroDepthTabLabels: Array<{ key: MacroDepthTabKey; label: string }> = [
  { key: "curve", label: "曲线（M8）" },
  { key: "spreads", label: "信用利差" },
  { key: "linkage", label: "压力与情景（M11/M15）" },
];

export function MarketDataMacroDepthTabs({
  macroDepthTab,
  onMacroDepthTabChange,
  latestQuery,
  rateTrendChartOption,
  macroBondLinkageQuery,
  spreadSlots,
  macroBondLinkage,
}: MarketDataMacroDepthTabsProps) {
  return (
    <div
      data-testid="market-data-macro-depth-wrap"
      className="market-data-detail-panel market-data-macro-chart-shell--flush-top"
    >
      <div
        data-testid="market-data-macro-depth-tabs"
        className="market-data-macro-depth-tabs"
        role="tablist"
        aria-label="宏观深度视图"
      >
        {macroDepthTabLabels.map((tab) => {
          const active = macroDepthTab === tab.key;
          return (
            <button
              key={tab.key}
              id={`market-data-macro-tab-trigger-${tab.key}`}
              className={`market-data-macro-depth-tab${active ? " market-data-macro-depth-tab--active" : ""}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`market-data-macro-tab-${tab.key}`}
              onClick={() => onMacroDepthTabChange(tab.key)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {macroDepthTab === "curve" ? (
        <div
          data-testid="market-data-macro-tab-curve"
          id="market-data-macro-tab-curve"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-curve"
        >
          <h2 className="market-data-block-title market-data-block-title--flush">收益率曲线</h2>
          <p className="market-data-curve-intro">
            国债 10Y（{RATE_TREND_DEFINITIONS[0].series_id}）、国开 5Y（{RATE_TREND_DEFINITIONS[1].series_id}）、
            SHIBOR 隔夜（{RATE_TREND_DEFINITIONS[2].series_id}），数据来自各序列的 recent_points。
          </p>
          <LiveResultMetaStrip
            lead="收益率曲线·宏观最新"
            meta={latestQuery.data?.result_meta}
            testId="market-data-curve-live-meta"
          />
          {latestQuery.isLoading ? (
            <div className="market-data-curve-loading">加载宏观序列中…</div>
          ) : latestQuery.isError ? (
            <Alert
              action={
                <Button danger size="small" onClick={() => void latestQuery.refetch()}>
                  重试宏观序列
                </Button>
              }
              data-testid="market-data-rate-trend-error"
              description="无法确认收益率曲线输入，不按空数据处理；请重试或查看下方宏观序列失败态。"
              message="宏观最新载入失败"
              showIcon
              type="error"
            />
          ) : rateTrendChartOption ? (
            <div data-testid="market-data-rate-trend-chart" className="market-data-rate-chart-wrap">
              <ReactECharts option={rateTrendChartOption} style={{ height: 260, width: "100%" }} />
            </div>
          ) : (
            <div data-testid="market-data-rate-trend-empty" className="market-data-rate-trend-empty">
              当前响应中缺少上述利率序列的近期点位，无法绘制走势图。
            </div>
          )}
        </div>
      ) : null}

      {macroDepthTab === "spreads" ? (
        <div
          data-testid="market-data-macro-tab-spreads"
          id="market-data-macro-tab-spreads"
          className="market-data-macro-tab-panel"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-spreads"
        >
          <LiveResultMetaStrip
            lead="信用利差表格·联动读面"
            meta={macroBondLinkageQuery.data?.result_meta}
            testId="market-data-spreads-live-meta"
          />
          <LinkageSpreadTenorTable slots={spreadSlots} loading={macroBondLinkageQuery.isLoading} />
        </div>
      ) : null}

      {macroDepthTab === "linkage" ? (
        <div
          data-testid="market-data-macro-tab-linkage"
          id="market-data-macro-tab-linkage"
          className="market-data-macro-tab-panel"
          role="tabpanel"
          aria-labelledby="market-data-macro-tab-trigger-linkage"
        >
          <p className="market-data-linkage-tab-intro">
            摘要来自 <code>getMacroBondLinkageAnalysis</code> 的 <code>environment_score</code> 与{" "}
            <code>portfolio_impact</code>；完整相关性矩阵仍在下文「宏观-债市联动」折叠区。
          </p>
          <div className="market-data-summary-grid">
            <KpiCard
              title="环境综合分"
              value={
                macroBondLinkage.environment_score?.composite_score != null
                  ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                  : "—"
              }
              detail={macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分。"}
              tone={
                macroBondLinkage.environment_score?.composite_score != null
                  ? toneFromSignedNumber(macroBondLinkage.environment_score.composite_score)
                  : "default"
              }
            />
            <KpiCard
              title="流动性分项"
              value={
                macroBondLinkage.environment_score?.liquidity_score != null
                  ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                  : "—"
              }
              detail="对应联动载荷的流动性评分（非 V1 压力测试原样复刻）。"
              tone={
                macroBondLinkage.environment_score?.liquidity_score != null
                  ? toneFromSignedNumber(macroBondLinkage.environment_score.liquidity_score)
                  : "default"
              }
            />
            <KpiCard
              title="利率方向"
              value={macroBondLinkage.environment_score?.rate_direction ?? "—"}
              detail={
                macroBondLinkage.environment_score?.rate_direction_score != null
                  ? `方向评分 ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                  : "缺少方向评分。"
              }
              valueVariant="text"
            />
            <KpiCard
              title="组合影响合计"
              value={formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}
              detail="结构化情景下的总影响估计（展示字段，不在前端重算）。"
              tone={toneFromSignedDisplayString(
                formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact),
              )}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
