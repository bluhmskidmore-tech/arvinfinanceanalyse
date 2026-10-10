import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";

import { BaseChart } from "../../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../../components/charts/chartTheme";
import { EM_DASH } from "../../../../utils/format";
import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "../../lib/stockAnalysisPageModel";
import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import { statusTone } from "./researchDeskFormatters";
import type {
  ResearchDeskEndpointItem,
  ResearchDeskEvidenceItem,
  ResearchDeskFactorCell,
  ResearchDeskKeyValue,
  ResearchDeskTimelineItem,
} from "./types";

type ResearchDeskSummaryProps = {
  selectedCandidate: StockCandidateReviewQueueItem;
  selectedRisk: StockRiskExitRow | null;
  decisionStatusLabel: string;
  decisionReason: string;
  compositeScore: string;
  compositeScoreNote: string | null;
  chartOption: EChartsOption | null;
  keyFactItems: ResearchDeskKeyValue[];
  evidenceItems: ResearchDeskEvidenceItem[];
  factorCells: ResearchDeskFactorCell[];
  timelineItems: ResearchDeskTimelineItem[];
  financeItems: ResearchDeskKeyValue[];
  evidencePreviewItems: ResearchDeskEndpointItem[];
  onJumpToEvidence: () => void;
  onOpenFundamentals: () => void;
};

const PRICE_RANGES = ["1D", "5D", "20D", "60D", "120D", "YTD", "1Y"] as const;
type PriceRange = (typeof PRICE_RANGES)[number];
const PRICE_RANGE_DAYS: Record<PriceRange, number | null> = {
  "1D": 1,
  "5D": 5,
  "20D": 20,
  "60D": 60,
  "120D": 120,
  YTD: null,
  "1Y": 250,
};

export function ResearchDeskSummary({
  selectedCandidate,
  selectedRisk,
  decisionStatusLabel,
  decisionReason,
  compositeScore,
  compositeScoreNote,
  chartOption,
  keyFactItems,
  evidenceItems,
  factorCells,
  timelineItems,
  financeItems,
  evidencePreviewItems,
  onJumpToEvidence,
  onOpenFundamentals,
}: ResearchDeskSummaryProps) {
  const [activeRange, setActiveRange] = useState<PriceRange>("60D");
  const rangedChartOption = useMemo(() => {
    if (!chartOption) return null;
    const days = PRICE_RANGE_DAYS[activeRange];
    const rawAxis = Array.isArray(chartOption.xAxis) ? chartOption.xAxis[0] : chartOption.xAxis;
    const axisData =
      rawAxis && typeof rawAxis === "object" && "data" in rawAxis && Array.isArray(rawAxis.data)
        ? rawAxis.data
        : [];
    const pointCount = axisData.length;
    if (days == null || pointCount === 0 || days >= pointCount) {
      return { ...chartOption, dataZoom: [{ type: "inside", start: 0, end: 100 }] };
    }
    const start = Math.max(0, ((pointCount - days) / pointCount) * 100);
    return { ...chartOption, dataZoom: [{ type: "inside", start, end: 100 }] };
  }, [chartOption, activeRange]);

  const evidenceStatusSegments = [
    {
      key: "ready",
      label: "已就绪",
      tone: "positive",
      count: evidencePreviewItems.filter((item) => item.tone === "positive").length,
    },
    {
      key: "watch",
      label: "观察",
      tone: "warning",
      count: evidencePreviewItems.filter(
        (item) => item.tone === "warning" || item.tone === "neutral",
      ).length,
    },
    {
      key: "blocked",
      label: "阻断",
      tone: "negative",
      count: evidencePreviewItems.filter((item) => item.tone === "negative").length,
    },
  ].filter((item) => item.count > 0);
  const evidenceTotal = evidenceStatusSegments.reduce((total, item) => total + item.count, 0);
  const evidenceDistributionOption: EChartsOption = {
    color: [
      nocturneChartTheme.palette[1],
      nocturneChartTheme.palette[2],
      nocturneChartTheme.palette[3],
    ],
    tooltip: {
      trigger: "item",
      confine: true,
      formatter: "{b}<br/>{c} 项（{d}%）",
    },
    series: [
      {
        type: "pie",
        radius: ["58%", "78%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: nocturneChartTheme.emptyStateStyle.background as string,
          borderWidth: 2,
        },
        data: evidenceStatusSegments.map((item) => ({
          name: item.label,
          value: item.count,
        })),
      },
    ],
  };

  return (
    <div className={styles.summaryStack}>
      <div className={styles.summaryLayout}>
        <section className={styles.chartPanel}>
          <div className={styles.chartHeader}>
            <strong>价格表现</strong>
            <div className={styles.chartRanges} role="group" aria-label="价格区间">
              {PRICE_RANGES.map((range) => (
                <button
                  key={range}
                  type="button"
                  className={styles.rangeChip}
                  data-active={activeRange === range}
                  data-testid={`stock-analysis-price-chart-range-${range.toLowerCase()}`}
                  aria-pressed={activeRange === range}
                  onClick={() => setActiveRange(range)}
                >
                  {range}
                </button>
              ))}
            </div>
          </div>
          {rangedChartOption ? (
            <div className={styles.chart}>
              <BaseChart option={rangedChartOption} height={145} />
            </div>
          ) : (
            <div className={styles.chartFallback}>
              <strong>价格序列待补</strong>
              <span>当前个股详情未返回足够行情字段，保持显式空状态。</span>
            </div>
          )}
          <div className={styles.chartFooter}>
            <div className={styles.chartLegend} aria-label="价格图例">
              <span data-series="close">收盘</span>
              <span data-series="ma5">MA5</span>
              <span data-series="ma20">MA20</span>
            </div>
            <small className={styles.footnote}>来自个股详情日频收盘；无详情时保留空态。</small>
          </div>
        </section>

        <section className={styles.keyFacts}>
          <strong>关键数据</strong>
          {keyFactItems.map((item) => (
            <div key={item.key} className={styles.factRow}>
              <span>{item.label}</span>
              <p>{item.value}</p>
            </div>
          ))}
        </section>

        <section className={styles.conclusionCard}>
          <div className={styles.conclusionHeading}>
            <strong>综合结论</strong>
            <span data-tone={statusTone(selectedRisk?.status ?? decisionStatusLabel)} title={decisionReason}>
              {selectedRisk?.status === "triggered" ? "阻断" : decisionStatusLabel}
            </span>
          </div>
          <p className={styles.conclusionScore}>
            综合得分 <strong>{compositeScore}</strong> / 1.000
          </p>
          {compositeScoreNote ? (
            <small className={styles.conclusionScoreNote}>{compositeScoreNote}</small>
          ) : null}
          <p title={selectedCandidate.reviewFocus}>{selectedCandidate.reviewFocus}</p>
          <ul className={styles.conclusionList}>
            {selectedCandidate.invalidationRules.slice(0, 3).map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </section>
      </div>

      <div className={styles.researchBand}>
        <section className={styles.compactCard}>
          <strong>研究观点（简要）</strong>
          <p title={selectedCandidate.headline}>{selectedCandidate.headline}</p>
          <p title={selectedCandidate.patternNote}>{selectedCandidate.patternNote}</p>
          <button type="button" className={styles.railLink} onClick={onOpenFundamentals}>
            查看完整观点 &gt;
          </button>
        </section>
        <section className={styles.compactCard}>
          <strong>最新信号与关键证据</strong>
          {evidenceItems.slice(0, 4).map((item) => (
            <div key={item.key} className={styles.factRow} data-rail={item.rail}>
              <span>{item.label}</span>
              <p>{item.value}</p>
            </div>
          ))}
          <button type="button" className={styles.railLink} onClick={onJumpToEvidence}>
            查看证据包 &gt;
          </button>
        </section>
      </div>

      <section className={styles.factorSection} aria-label="因子指标">
        <div className={styles.factorSectionHead}>
          <strong>因子指标</strong>
          <small title="显示原始指标值；P 为当前候选池内分位，非全市场排名，也不代表投资优劣。">P：候选池内分位</small>
        </div>
        <div className={styles.factorBand}>
          {factorCells.map((item) => (
            <div
              key={item.key}
              className={styles.factorCell}
              data-accent={item.accent}
              data-empty={item.value === EM_DASH}
            >
              <span>{item.label}</span>
              <div className={styles.factorValueLine}>
                <strong>{item.value}</strong>
                {item.percentile ? <em>({item.percentile})</em> : null}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className={styles.lowerDeck}>
        <section className={styles.compactCard}>
          <strong>事件时间线</strong>
          {timelineItems.length > 0 ? (
            <ul className={`${styles.compactList} ${styles.timelineList}`}>
              {timelineItems.map((item) => (
                <li key={item.key}>
                  <time>{item.time}</time>
                  <span>{item.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <small>当前没有额外边界事件。</small>
          )}
        </section>
        <section className={styles.compactCard}>
          <strong>关键财务指标</strong>
          {financeItems.map((field) => (
            <div key={field.key} className={styles.factRow}>
              <span>{field.label}</span>
              <p>{field.value}</p>
            </div>
          ))}
        </section>
        <section className={`${styles.compactCard} ${styles.evidenceDistribution}`}>
          <div className={styles.evidenceDistributionHeading}>
            <strong>证据状态分布</strong>
            <small>证据来源与时点</small>
          </div>
          {evidenceTotal > 0 ? (
            <>
              <div className={styles.evidenceDistributionBody}>
                <div
                  className={styles.evidenceChart}
                  role="img"
                  aria-label={`当前页共 ${evidenceTotal} 项证据来源`}
                >
                  <BaseChart option={evidenceDistributionOption} height={96} />
                  <span className={styles.evidenceChartTotal}>
                    <strong>{evidenceTotal}</strong>
                    <small>项来源</small>
                  </span>
                </div>
                <div className={styles.evidenceLegend}>
                  {evidenceStatusSegments.map((item) => (
                    <div key={item.key} className={styles.evidenceLegendRow} data-tone={item.tone}>
                      <span>{item.label}</span>
                      <strong>{item.count}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <p className={styles.evidenceLatest} title={evidencePreviewItems[0]?.description}>
                {evidencePreviewItems[0]?.description}
              </p>
            </>
          ) : (
            <small>当前没有额外来源证据。</small>
          )}
        </section>
      </div>
    </div>
  );
}
