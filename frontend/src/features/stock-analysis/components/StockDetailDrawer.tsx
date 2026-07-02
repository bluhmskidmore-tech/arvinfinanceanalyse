import { useQuery } from "@tanstack/react-query";
import { Button as AntButton, Drawer as AntDrawer, Segmented } from "antd";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import type {
  ChoiceNewsEvent,
  LivermoreStockDetailCandle,
} from "../../../api/contracts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { designTokens } from "../../../theme/designSystem";
import { localizeStrategyPanelErrorDetail } from "../lib/stockAnalysisPageModel";
import type { StockDetailReviewThesis } from "../lib/stockAnalysisDetailSelection";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import "./StockDetailDrawer.css";



const LOOKBACK_CHOICES = [30, 60, 120] as const;
const STOCK_DETAIL_CHART_HEIGHT = 300;

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function buildCandleVolumeOption(
  candles: LivermoreStockDetailCandle[],
): EChartsOption {
  const dates = candles.map((c) => c.trade_date);
  const ohlc: [number, number, number, number][] = candles.map((c) => {
    const o = c.open_value ?? 0;
    const cl = c.close_value ?? 0;
    const lo = c.low_value ?? 0;
    const hi = c.high_value ?? 0;
    return [o, cl, lo, hi];
  });
  const volumes = candles.map((c) => c.volume ?? 0);
  const up = designTokens.color.semantic.up;
  const down = designTokens.color.semantic.down;
  const muted = designTokens.color.neutral[600];
  const gridLine = designTokens.color.neutral[200];

  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: muted, fontSize: 11 },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 52, right: 16, top: 28, height: "56%" },
      { left: 52, right: 16, top: "72%", height: "20%" },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        boundaryGap: true,
      },
      { type: "category", data: dates, gridIndex: 1, boundaryGap: true },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        scale: true,
        splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
      },
      {
        type: "value",
        gridIndex: 1,
        scale: true,
        splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
      },
    ],
    series: [
      {
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ohlc,
        itemStyle: {
          color: down,
          color0: up,
          borderColor: down,
          borderColor0: up,
        },
      },
      {
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: designTokens.color.neutral[400] },
      },
    ],
  };
}

function formatPePb(value: number | null): string {
  if (!isFiniteNumber(value)) return "待补";
  return value.toFixed(2);
}

function formatRoe(value: number | null): string {
  if (!isFiniteNumber(value)) return "待补";
  return `${(value * 100).toFixed(2)}%`;
}

function formatDividendYield(value: number | null): string {
  if (!isFiniteNumber(value)) return "待补";
  return `${(value * 100).toFixed(2)}%`;
}

function formatStockDetailPrice(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return "待补";
  return value.toFixed(2);
}

function formatStockDetailSignedPercent(
  value: number | null | undefined,
): string {
  if (!isFiniteNumber(value)) return "待补";
  const percentage = value * 100;
  return `${percentage >= 0 ? "+" : ""}${percentage.toFixed(2)}%`;
}

function formatStockDetailVolumeRatio(
  value: number | null | undefined,
): string {
  if (!isFiniteNumber(value)) return "待补";
  return `${value.toFixed(1)}x`;
}

const stockDetailMetaPendingLabel = "待确认";
const stockDetailMetaQualityLabels: Record<string, string> = {
  ok: "正常",
  warning: "需复核",
  stale: "陈旧",
  missing: "缺失",
  error: "异常",
  pending: stockDetailMetaPendingLabel,
};
const stockDetailMetaVendorLabels: Record<string, string> = {
  ok: "正常",
  degraded: "降级",
  vendor_stale: "供数陈旧",
  vendor_unavailable: "通道不可用",
  error: "异常",
  pending: stockDetailMetaPendingLabel,
};

function stockDetailMetaLabel(
  value: string | null | undefined,
  labels: Record<string, string>,
) {
  const normalized = (value ?? "").trim().toLowerCase();
  return labels[normalized] ?? stockDetailMetaPendingLabel;
}

function rawStockDetailErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error == null) return "";
  return String(error);
}

function stockDetailSubqueryErrorDescription(
  error: unknown,
  fallbackDescription: string,
): string {
  const message = rawStockDetailErrorMessage(error);
  const normalized = message.trim().toLowerCase().replace(/\s+/g, " ");
  if (
    normalized.includes("source_table") ||
    normalized.includes("source table")
  ) {
    return `${fallbackDescription} ${localizeStrategyPanelErrorDetail(message)}`;
  }
  return fallbackDescription;
}

export type StockDetailDrawerProps = {
  stockCode: string | null;
  stockName?: string;
  asOfDate?: string;
  reviewContext?: {
    sourceLabel: string;
    sectorName?: string;
    reviewRank?: number;
    distanceToBreakoutPct?: string;
    livermoreRank?: number | null;
    meanReversionRank?: number | null;
    factorScreenRank?: number | null;
    hybridFusionRank?: number | null;
    reviewThesis?: StockDetailReviewThesis;
  } | null;
  onClose: () => void;
};

function formatChoiceNewsReceivedAt(iso: string): string {
  const t = iso.trim();
  if (t.length >= 16) return t.slice(0, 16).replace("T", " ");
  return t || "—";
}

function truncateChoiceNewsText(text: string | null, maxLen: number): string {
  if (text == null || text === "") return "—";
  const s = text.trim();
  if (s.length <= maxLen) return s;
  return `${s.slice(0, maxLen)}…`;
}

const choiceNewsContentTypeLabels: Record<string, string> = {
  announcement: "公告",
  research: "研报",
  research_report: "研报",
  sectornews: "行业新闻",
  stocknews: "个股新闻",
};

function choiceNewsTopicLabel(
  topicCode: string | null | undefined,
  contentType: string | null | undefined,
): string {
  const normalizedContentType = contentType?.trim().toLowerCase();
  if (
    normalizedContentType &&
    choiceNewsContentTypeLabels[normalizedContentType]
  ) {
    return choiceNewsContentTypeLabels[normalizedContentType];
  }

  const value = topicCode?.trim();
  if (!value) return "事件分类待确认";
  if (
    isTechnicalChoiceNewsCode(contentType) ||
    isTechnicalChoiceNewsCode(value)
  )
    return "事件分类待确认";
  if (/^[A-Z0-9_]+$/.test(value) || value.includes("_"))
    return "事件分类待确认";
  return value;
}

function isTechnicalChoiceNewsCode(value: string | null | undefined): boolean {
  const normalized = value
    ?.trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, "");
  if (!normalized) return false;
  return (
    normalized.includes("externalvendor") ||
    normalized.includes("vendorstatus") ||
    normalized.includes("sourcetable") ||
    normalized.includes("choicestock")
  );
}

function formatCandidateHistoryReturn(
  value: number | null | undefined,
): string {
  if (!isFiniteNumber(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function candidateHistoryRowClass(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "pending")
    return "stock-detail-drawer__history-row--pending";
  if (normalized === "partial_halt")
    return "stock-detail-drawer__history-row--halt";
  return "";
}

function candidateHistoryDataStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    complete: "已成熟",
    partial_halt: "部分停牌",
    pending: "待成熟",
  };
  const normalized = status.trim().toLowerCase();
  return labels[normalized] ?? "状态待确认";
}

const candidateHistorySignalLabels: Record<string, string> = {
  livermore: "趋势突破",
  hybrid_fusion: "融合策略",
  stock_candidate: "趋势突破",
  factor_screen: "多因子",
  theme_breakout: "题材突变",
  mean_reversion: "超跌反弹",
};

function candidateHistorySignalLabel(value: string | null | undefined): string {
  const key = value?.trim() || "stock_candidate";
  const normalized = key.toLowerCase().replace(/[\s-]+/g, "_");
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "策略待确认";
  }
  return candidateHistorySignalLabels[normalized] ?? "策略待确认";
}

function hasReviewThesis(
  thesis: StockDetailReviewThesis | null | undefined,
): thesis is StockDetailReviewThesis {
  if (!thesis) return false;
  return (
    thesis.whySelected.length > 0 ||
    thesis.boundaries.length > 0 ||
    thesis.invalidation.length > 0 ||
    thesis.nextActions.length > 0
  );
}

function renderThesisList(items: string[]) {
  const displayItems = items.length > 0 ? items : ["待补"];
  return (
    <ul>
      {displayItems.map((item, index) => (
        <li key={`${item}:${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function latestCandleWithClose(
  candles: LivermoreStockDetailCandle[],
): LivermoreStockDetailCandle | null {
  for (let index = candles.length - 1; index >= 0; index -= 1) {
    if (isFiniteNumber(candles[index]?.close_value)) return candles[index];
  }
  return null;
}

function previousClose(
  candles: LivermoreStockDetailCandle[],
  latest: LivermoreStockDetailCandle | null,
): number | null {
  if (!latest) return null;
  const latestIndex = candles.lastIndexOf(latest);
  for (let index = latestIndex - 1; index >= 0; index -= 1) {
    const close = candles[index]?.close_value;
    if (isFiniteNumber(close)) return close;
  }
  return null;
}

function latestVolumeRatio(
  candles: LivermoreStockDetailCandle[],
  latest: LivermoreStockDetailCandle | null,
): number | null {
  if (!latest || !isFiniteNumber(latest.volume)) return null;
  const latestIndex = candles.lastIndexOf(latest);
  const previousVolumes = candles
    .slice(Math.max(0, latestIndex - 20), latestIndex)
    .map((candle) => candle.volume)
    .filter((value): value is number => isFiniteNumber(value) && value > 0);
  if (previousVolumes.length === 0) return null;
  const average =
    previousVolumes.reduce((sum, value) => sum + value, 0) /
    previousVolumes.length;
  if (!isFiniteNumber(average) || average <= 0) return null;
  return latest.volume / average;
}

function firstReviewText(
  items: string[] | undefined,
  fallback: string,
): string {
  const value = items?.find((item) => item.trim() !== "")?.trim();
  return value || fallback;
}

function eventBoundaryTimelineLabel(event: ChoiceNewsEvent): string {
  const label = choiceNewsTopicLabel(event.topic_code, event.content_type);
  if (label === "事件分类待确认") return "事件待确认";
  return `${label}事件`;
}

export function StockDetailDrawer({
  stockCode,
  stockName,
  asOfDate,
  reviewContext,
  onClose,
}: StockDetailDrawerProps) {
  const client = useApiClient();
  const [lookback, setLookback] = useState<number>(60);
  const [drawerLayoutReady, setDrawerLayoutReady] = useState(false);

  const open = stockCode != null && stockCode.trim() !== "";
  const stockCodeForQuery = stockCode?.trim() || undefined;

  const detailQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-stock-detail",
      stockCode,
      asOfDate ?? null,
      lookback,
    ] as const,
    queryFn: () =>
      client.getLivermoreStockDetail({
        stockCode: stockCode ?? "",
        asOfDate,
        lookback,
      }),
    enabled: open,
  });

  const choiceNewsQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "choice-news-latest",
      stockCodeForQuery ?? "__none",
      open ? 10 : 0,
    ] as const,
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: 10,
        offset: 0,
        stockCode: stockCodeForQuery,
      }),
    enabled: open,
  });

  const candidateHistoryAsOfDate = detailQuery.data?.result?.as_of_date ?? null;
  const candidateHistoryQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history",
      stockCode,
      candidateHistoryAsOfDate,
      10,
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        stockCode: stockCodeForQuery,
        snapshotTo: candidateHistoryAsOfDate ?? undefined,
        limit: 10,
      }),
    enabled: open && candidateHistoryAsOfDate != null,
  });

  const chartOption = useMemo(() => {
    const candles = detailQuery.data?.result?.candles ?? [];
    if (!candles.length) return { series: [] } as EChartsOption;
    return buildCandleVolumeOption(candles);
  }, [detailQuery.data?.result?.candles]);

  const factor = detailQuery.data?.result?.factor;
  const candles = detailQuery.data?.result?.candles ?? [];
  const latestCandle = latestCandleWithClose(candles);
  const previousCloseValue = previousClose(candles, latestCandle);
  const latestCloseValue = latestCandle?.close_value ?? null;
  const priceChange =
    isFiniteNumber(latestCloseValue) &&
    isFiniteNumber(previousCloseValue) &&
    previousCloseValue !== 0
      ? latestCloseValue / previousCloseValue - 1
      : null;
  const volumeRatio = latestVolumeRatio(candles, latestCandle);
  const observationLine = reviewContext?.distanceToBreakoutPct ?? "待补";
  const invalidationLine = firstReviewText(
    reviewContext?.reviewThesis?.invalidation,
    "失效条件待补",
  );
  const boundaryLine = firstReviewText(
    reviewContext?.reviewThesis?.boundaries,
    "公告/新闻/财报边界待确认。",
  );
  const whySelectedLine = firstReviewText(
    reviewContext?.reviewThesis?.whySelected,
    reviewContext?.distanceToBreakoutPct
      ? `距观察位 ${reviewContext.distanceToBreakoutPct}`
      : "入选理由待补",
  );
  const nextActionLine = firstReviewText(
    reviewContext?.reviewThesis?.nextActions,
    "先看 K 线，再核公告/新闻边界",
  );
  const eventBoundaryEvents = choiceNewsQuery.data?.result?.events ?? [];
  const meta =
    detailQuery.data?.result == null
      ? null
      : (detailQuery.data.result_meta ?? {
          source_version: stockDetailMetaPendingLabel,
          rule_version: stockDetailMetaPendingLabel,
          quality_flag: "pending",
          vendor_status: "pending",
        });
  const sourceVersionLabel =
    meta?.source_version ?? stockDetailMetaPendingLabel;
  const ruleVersionLabel = meta?.rule_version ?? stockDetailMetaPendingLabel;
  const qualityStatusLabel = stockDetailMetaLabel(
    meta?.quality_flag,
    stockDetailMetaQualityLabels,
  );
  const vendorStatusLabel = stockDetailMetaLabel(
    meta?.vendor_status,
    stockDetailMetaVendorLabels,
  );
  const dataLineageStatusLabel =
    sourceVersionLabel === stockDetailMetaPendingLabel ||
    ruleVersionLabel === stockDetailMetaPendingLabel
      ? stockDetailMetaPendingLabel
      : "已确认";
  const resolvedAsOfDate = detailQuery.data?.result?.as_of_date ?? "日期待补";
  const requestedAsOfDate =
    detailQuery.data?.result?.requested_as_of_date ?? asOfDate ?? null;
  const showRequestedAsOfDate =
    requestedAsOfDate != null && requestedAsOfDate !== resolvedAsOfDate;
  const handleDrawerClose = () => {
    setDrawerLayoutReady(false);
    onClose();
  };

  return (
    <AntDrawer
      placement="right"
      width={960}
      open={open}
      onClose={handleDrawerClose}
      afterOpenChange={(isOpen) => setDrawerLayoutReady(isOpen)}
      className="stock-detail-drawer"
      data-testid="stock-detail-drawer"
      title="个股复核"
      extra={
        <AntButton type="text" onClick={handleDrawerClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      {open ? (
        <div
          className="stock-detail-drawer__body"
          style={stockAnalysisPageCssVars}
        >
          <header className="stock-detail-drawer__header">
            <div>
              <span className="font-semibold stock-detail-drawer__tabular">
                {stockCode}
              </span>
              {stockName ? (
                <span className="text-default-500 stock-detail-drawer__name">
                  {" "}
                  {stockName}
                </span>
              ) : null}
              <div className="stock-detail-drawer__meta-line">
                <span className="text-default-500">截至日 {resolvedAsOfDate}</span>
                {showRequestedAsOfDate ? (
                  <span className="text-default-500">请求日期 {requestedAsOfDate}</span>
                ) : null}
              </div>
              {reviewContext ? (
                <div
                  className="stock-detail-drawer__review-context"
                  data-testid="stock-detail-review-context"
                >
                  <span>{reviewContext.sourceLabel}</span>
                  {reviewContext.reviewRank != null ? (
                    <span>#{reviewContext.reviewRank}</span>
                  ) : null}
                  {reviewContext.sectorName ? (
                    <span>{reviewContext.sectorName}</span>
                  ) : null}
                  {reviewContext.distanceToBreakoutPct ? (
                    <span>距观察位 {reviewContext.distanceToBreakoutPct}</span>
                  ) : null}
                </div>
              ) : null}
              {reviewContext &&
              (reviewContext.livermoreRank != null ||
                reviewContext.meanReversionRank != null ||
                reviewContext.factorScreenRank != null ||
                reviewContext.hybridFusionRank != null) ? (
                <div
                  className="stock-detail-drawer__strategy-ranks"
                  data-testid="stock-detail-strategy-ranks"
                  aria-label="多策略命中"
                >
                  <span className="stock-detail-drawer__strategy-ranks-label">
                    策略命中
                  </span>
                  {reviewContext.livermoreRank != null ? (
                    <span className="stock-detail-drawer__strategy-ranks-badge">
                      趋势 #{reviewContext.livermoreRank}
                    </span>
                  ) : null}
                  {reviewContext.hybridFusionRank != null ? (
                    <span className="stock-detail-drawer__strategy-ranks-badge">
                      融合策略 #{reviewContext.hybridFusionRank}
                    </span>
                  ) : null}
                  {reviewContext.meanReversionRank != null ? (
                    <span className="stock-detail-drawer__strategy-ranks-badge">
                      超跌反弹 #{reviewContext.meanReversionRank}
                    </span>
                  ) : null}
                  {reviewContext.factorScreenRank != null ? (
                    <span className="stock-detail-drawer__strategy-ranks-badge">
                      多因子 #{reviewContext.factorScreenRank}
                    </span>
                  ) : null}
                  {[
                    reviewContext.livermoreRank,
                    reviewContext.hybridFusionRank,
                    reviewContext.meanReversionRank,
                    reviewContext.factorScreenRank,
                  ].filter((v) => v != null).length >= 2 ? (
                    <span className="stock-detail-drawer__strategy-ranks-badge stock-detail-drawer__strategy-ranks-badge--consensus">
                      共振
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="stock-detail-drawer__lookback">
              <span className="text-default-500">回看交易日</span>
              <Segmented
                size="small"
                value={lookback}
                options={LOOKBACK_CHOICES.map((n) => ({ label: String(n), value: n }))}
                onChange={(value) => setLookback(Number(value))}
              />
            </div>
          </header>

          {hasReviewThesis(reviewContext?.reviewThesis) ? (
            <section
              className="stock-detail-drawer__review-thesis stock-detail-drawer__decision-summary"
              data-testid="stock-detail-decision-summary"
              aria-label="候选复核详情"
            >
              <div className="stock-detail-drawer__decision-summary-head">
                <span className="font-semibold">候选复核</span>
                <span>先看取舍，再看完整依据</span>
              </div>
              <div
                className="stock-detail-drawer__decision-brief"
                data-testid="stock-detail-decision-brief"
              >
                <div>
                  <span>为什么看</span>
                  <strong>{whySelectedLine}</strong>
                </div>
                <div data-tone="warning">
                  <span>失效线</span>
                  <strong>{invalidationLine}</strong>
                </div>
                <div data-tone="warning">
                  <span>边界</span>
                  <strong>{boundaryLine}</strong>
                </div>
                <div data-tone="positive">
                  <span>下一步</span>
                  <strong>{nextActionLine}</strong>
                </div>
              </div>
              <details
                className="stock-detail-drawer__thesis-details"
                data-testid="stock-detail-thesis-details"
              >
                <summary>
                  <span>完整依据</span>
                  <small>入选 / 边界 / 失效 / 动作</small>
                </summary>
                <div
                  data-testid="stock-detail-review-thesis"
                  className="stock-detail-drawer__review-thesis-grid"
                >
                  <div>
                    <span>为什么入选</span>
                    {renderThesisList(reviewContext.reviewThesis.whySelected)}
                  </div>
                  <div>
                    <span>主要边界</span>
                    {renderThesisList(reviewContext.reviewThesis.boundaries)}
                  </div>
                  <div>
                    <span>失效条件</span>
                    {renderThesisList(reviewContext.reviewThesis.invalidation)}
                  </div>
                  <div>
                    <span>下一步动作</span>
                    {renderThesisList(reviewContext.reviewThesis.nextActions)}
                  </div>
                </div>
              </details>
            </section>
          ) : null}

          {!detailQuery.isError ? (
            <section
              className="stock-detail-drawer__review-checklist"
              data-testid="stock-detail-review-checklist"
              aria-label="复核核验"
            >
              <div className="stock-detail-drawer__section-title-row">
                <span className="font-semibold">复核核验</span>
                <span>
                  {choiceNewsQuery.isLoading
                    ? "事件加载中"
                    : choiceNewsQuery.isError
                      ? "事件暂不可用"
                      : eventBoundaryEvents.length > 0
                        ? `事件 ${eventBoundaryEvents.length} 条`
                        : "事件待人工确认"}
                </span>
              </div>
              <div className="stock-detail-drawer__confirmation-grid stock-detail-drawer__review-check-grid">
                <div>
                  <span>价格</span>
                  <strong className="stock-detail-drawer__tabular">
                    {formatStockDetailPrice(latestCloseValue)}
                  </strong>
                  <small>
                    较前日 {formatStockDetailSignedPercent(priceChange)} · 量能{" "}
                    {formatStockDetailVolumeRatio(volumeRatio)}
                  </small>
                </div>
                <div>
                  <span>观察位</span>
                  <strong>{observationLine}</strong>
                  <small>{latestCandle?.trade_date ?? "日期待补"}</small>
                </div>
              </div>
              <details
                className="stock-detail-drawer__review-check-more"
                data-testid="stock-detail-review-check-more"
              >
                <summary>
                  <span>失效 / 边界 / 事件</span>
                  <small>展开完整核验</small>
                </summary>
                <div className="stock-detail-drawer__confirmation-grid stock-detail-drawer__review-check-more-grid">
                  <div data-tone="warning">
                    <span>失效</span>
                    <strong>{invalidationLine}</strong>
                    <small>触发后降级观察</small>
                  </div>
                  <div data-tone="warning">
                    <span>边界</span>
                    <strong>{boundaryLine}</strong>
                    <small>公告/新闻仍需核验</small>
                  </div>
                </div>
                <div
                  className="stock-detail-drawer__event-boundary-compact"
                  data-testid="stock-detail-event-boundary-timeline"
                >
                  {choiceNewsQuery.isLoading ? (
                    <p className="stock-detail-drawer__boundary-line">
                      事件边界加载中…
                    </p>
                  ) : null}
                  {choiceNewsQuery.isError ? (
                    <p className="stock-detail-drawer__boundary-line">
                      {stockDetailSubqueryErrorDescription(
                        choiceNewsQuery.error,
                        "事件边界暂不可用。",
                      )}
                    </p>
                  ) : null}
                  {!choiceNewsQuery.isError &&
                  eventBoundaryEvents.length === 0 &&
                  !choiceNewsQuery.isLoading ? (
                    <p className="stock-detail-drawer__boundary-line">
                      暂无公告/新闻事件匹配，仍需人工确认。
                    </p>
                  ) : null}
                  {eventBoundaryEvents.length > 0 ? (
                    <ol className="stock-detail-drawer__event-boundary-list">
                      {eventBoundaryEvents.slice(0, 3).map((event) => (
                        <li key={event.event_key}>
                          <time className="stock-detail-drawer__tabular">
                            {formatChoiceNewsReceivedAt(event.received_at)}
                          </time>
                          <span>{eventBoundaryTimelineLabel(event)}</span>
                          <p>
                            {truncateChoiceNewsText(event.payload_text, 72)}
                          </p>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>
              </details>
            </section>
          ) : null}

          {detailQuery.isError ? (
            <div
              className="p-4 mb-4 text-sm text-danger-800 rounded-lg bg-danger-50 flex items-start gap-3 border border-danger-200"
              role="alert"
              data-testid="stock-detail-error"
            >
              <div className="flex flex-col gap-1">
                <span className="font-semibold text-danger-900">个股复核数据暂不可用</span>
                <span>请稍后重试，或切换到其他标的复核。</span>
              </div>
            </div>
          ) : null}

          {detailQuery.isLoading && !detailQuery.isError ? (
            <p className="stock-detail-drawer__loading">加载中…</p>
          ) : null}

          {!detailQuery.isError ? (
            <section
              className="stock-detail-drawer__chart"
              aria-label="K 线与成交量"
              data-testid="stock-detail-chart"
            >
              <span className="font-semibold">价格与成交量（复核）</span>
              {drawerLayoutReady ? (
                <BaseChart
                  option={chartOption}
                  height={STOCK_DETAIL_CHART_HEIGHT}
                  loading={detailQuery.isLoading}
                />
              ) : (
                <p className="stock-detail-drawer__loading">图表布局准备中…</p>
              )}
            </section>
          ) : null}

          {!detailQuery.isError ? (
            <details
              className="stock-detail-drawer__audit-details"
              data-testid="stock-detail-audit-details"
            >
              <summary>
                <span>审计明细</span>
                <small>因子 / 历史 / 事件 / 版本</small>
              </summary>
              <div className="stock-detail-drawer__audit-details-body">
                {meta ? (
                  <section
                    className="stock-detail-drawer__lineage-detail"
                    data-testid="stock-detail-lineage-detail"
                    aria-label="数据版本明细"
                  >
                    <span className="font-semibold">数据版本</span>
                    <dl className="stock-detail-drawer__lineage-grid">
                      <div>
                        <dt>来源版本</dt>
                        <dd>{sourceVersionLabel}</dd>
                      </div>
                      <div>
                        <dt>规则版本</dt>
                        <dd>{ruleVersionLabel}</dd>
                      </div>
                      <div>
                        <dt>质量</dt>
                        <dd>{qualityStatusLabel}</dd>
                      </div>
                      <div>
                        <dt>供数状态</dt>
                        <dd>{vendorStatusLabel}</dd>
                      </div>
                    </dl>
                  </section>
                ) : null}
                <section
                  className="stock-detail-drawer__factors"
                  data-testid="stock-detail-factors"
                >
                  <span className="font-semibold">因子快照</span>
                  <div className="stock-detail-drawer__factor-grid">
                    <div data-testid="stock-detail-factor-pe">
                      <div className="stock-detail-drawer__factor-label">
                        PE
                      </div>
                      <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                        {formatPePb(factor?.pe ?? null)}
                      </div>
                    </div>
                    <div data-testid="stock-detail-factor-pb">
                      <div className="stock-detail-drawer__factor-label">
                        PB
                      </div>
                      <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                        {formatPePb(factor?.pb ?? null)}
                      </div>
                    </div>
                    <div data-testid="stock-detail-factor-roe">
                      <div className="stock-detail-drawer__factor-label">
                        ROE
                      </div>
                      <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                        {formatRoe(factor?.roe ?? null)}
                      </div>
                    </div>
                    <div data-testid="stock-detail-factor-dividend">
                      <div className="stock-detail-drawer__factor-label">
                        股息率
                      </div>
                      <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                        {formatDividendYield(factor?.dividend_yield ?? null)}
                      </div>
                    </div>
                  </div>
                </section>

                <section
                  className="stock-detail-drawer__candidate-history"
                  data-testid="stock-detail-candidate-history"
                  aria-label="入选历史"
                >
                  <span className="font-semibold">入选历史</span>
                  <p className="stock-detail-drawer__candidate-history-note">
                    价格回报 · 快照累计
                  </p>
                  {candidateHistoryQuery.isLoading ? (
                    <p
                      className="stock-detail-drawer__candidate-history-loading"
                      data-testid="stock-detail-candidate-history-loading"
                    >
                      入选历史加载中…
                    </p>
                  ) : null}
                  {candidateHistoryQuery.isError ? (
                    <div
                      className="p-4 mb-4 text-sm text-warning-800 rounded-lg bg-warning-50 flex items-start gap-3 border border-warning-200"
                      role="alert"
                      data-testid="stock-detail-candidate-history-error"
                    >
                      <div className="flex flex-col gap-1">
                        <span className="font-semibold text-warning-900">入选历史暂不可用</span>
                        <span>{stockDetailSubqueryErrorDescription(
                          candidateHistoryQuery.error,
                          "图表与因子仍可继续查看。",
                        )}</span>
                      </div>
                    </div>
                  ) : null}
                  {candidateHistoryQuery.isSuccess &&
                  (candidateHistoryQuery.data?.result?.items?.length ?? 0) ===
                    0 ? (
                    <p
                      className="stock-detail-drawer__candidate-history-empty"
                      data-testid="stock-detail-candidate-history-empty"
                    >
                      暂无入选快照记录（服务端尚未累积或未跑任务）
                    </p>
                  ) : null}
                  {candidateHistoryQuery.isSuccess &&
                  (candidateHistoryQuery.data?.result?.items?.length ?? 0) >
                    0 ? (
                    <div className="stock-detail-drawer__history-table-wrap">
                      <table className="stock-detail-drawer__history-table">
                        <thead>
                          <tr>
                            <th scope="col">入选日</th>
                            <th scope="col">策略</th>
                            <th scope="col">排名</th>
                            <th scope="col">入选收盘</th>
                            <th scope="col">T+1</th>
                            <th scope="col">T+5</th>
                            <th scope="col">T+20</th>
                            <th scope="col">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            candidateHistoryQuery.data?.result?.items ?? []
                          ).map((row) => (
                            <tr
                              key={`${row.snapshot_as_of_date}-${row.candidate_rank}-${row.stock_code}`}
                              className={candidateHistoryRowClass(
                                row.data_status,
                              )}
                              data-testid={`stock-detail-candidate-history-row-${row.snapshot_as_of_date}-${row.candidate_rank}`}
                            >
                              <td className="stock-detail-drawer__tabular">
                                {row.snapshot_as_of_date}
                              </td>
                              <td>
                                {candidateHistorySignalLabel(row.signal_kind)}
                              </td>
                              <td className="stock-detail-drawer__tabular">
                                {row.candidate_rank}
                              </td>
                              <td className="stock-detail-drawer__tabular">
                                {row.selection_close ?? "—"}
                              </td>
                              <td className="stock-detail-drawer__tabular">
                                {formatCandidateHistoryReturn(
                                  row.return_1d ?? null,
                                )}
                              </td>
                              <td className="stock-detail-drawer__tabular">
                                {formatCandidateHistoryReturn(
                                  row.return_5d ?? null,
                                )}
                              </td>
                              <td className="stock-detail-drawer__tabular">
                                {formatCandidateHistoryReturn(
                                  row.return_20d ?? null,
                                )}
                              </td>
                              <td>
                                {candidateHistoryDataStatusLabel(
                                  row.data_status,
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </section>

                {!detailQuery.isError ? (
                  <section
                    className="stock-detail-drawer__market-events"
                    aria-label="市场最近事件"
                    data-testid="stock-detail-market-events"
                  >
                    <span className="font-semibold">市场最近事件</span>
                    <div
                      className="stock-detail-drawer__market-events-banner"
                      role="note"
                      data-testid="stock-detail-market-events-banner"
                    >
                      市场事件 · 公告财报待补
                    </div>
                    {choiceNewsQuery.isLoading ? (
                      <p
                        className="stock-detail-drawer__market-events-loading"
                        data-testid="stock-detail-market-events-loading"
                      >
                        市场事件加载中…
                      </p>
                    ) : null}
                    {choiceNewsQuery.isError ? (
                      <div
                        className="p-4 mb-4 text-sm text-warning-800 rounded-lg bg-warning-50 flex items-start gap-3 border border-warning-200"
                        role="alert"
                        data-testid="stock-detail-market-events-error"
                      >
                        <div className="flex flex-col gap-1">
                          <span className="font-semibold text-warning-900">市场事件暂不可用</span>
                          <span>{stockDetailSubqueryErrorDescription(
                            choiceNewsQuery.error,
                            "个股复核数据不受影响，可稍后刷新市场事件。",
                          )}</span>
                        </div>
                      </div>
                    ) : null}
                    {choiceNewsQuery.isSuccess &&
                    !choiceNewsQuery.data?.result?.events?.length ? (
                      <p
                        className="stock-detail-drawer__market-events-empty"
                        data-testid="stock-detail-market-events-empty"
                      >
                        暂无与该股票代码匹配的市场事件，公告财报仍待补。
                      </p>
                    ) : null}
                    {choiceNewsQuery.isSuccess &&
                    (choiceNewsQuery.data?.result?.events?.length ?? 0) > 0 ? (
                      <ul
                        className="stock-detail-drawer__market-events-list"
                        data-testid="stock-detail-market-events-list"
                      >
                        {(choiceNewsQuery.data?.result?.events ?? []).map(
                          (ev) => (
                            <li
                              key={ev.event_key}
                              className="stock-detail-drawer__market-events-item"
                            >
                              <span className="stock-detail-drawer__market-events-time stock-detail-drawer__tabular">
                                {formatChoiceNewsReceivedAt(ev.received_at)}
                              </span>
                              <span className="stock-detail-drawer__market-events-topic">
                                {choiceNewsTopicLabel(
                                  ev.topic_code,
                                  ev.content_type,
                                )}
                              </span>
                              <span className="stock-detail-drawer__market-events-text">
                                {truncateChoiceNewsText(ev.payload_text, 100)}
                              </span>
                            </li>
                          ),
                        )}
                      </ul>
                    ) : null}
                  </section>
                ) : null}
              </div>
            </details>
          ) : null}

          {!detailQuery.isError && meta ? (
            <footer
              className="stock-detail-drawer__footer-meta"
              data-testid="stock-detail-footer-meta"
            >
              <span className="text-default-500">
                数据口径 {dataLineageStatusLabel} · 质量 {qualityStatusLabel} ·
                供数状态 {vendorStatusLabel}
              </span>
            </footer>
          ) : null}
        </div>
      ) : null}
    </AntDrawer>
  );
}
