import { useEffect, useMemo, type ReactNode } from "react";

import type { EChartsOption } from "../../lib/echarts";
import { EM_DASH } from "../../utils/format";
import { StateSurface, type SurfaceStatus } from "../layout/StateSurface";
import { BaseChart } from "./BaseChart";
import {
  applyChartCardChrome,
  detectChartCardWarnings,
  isChartCardOptionEmpty,
  type ChartCardLegendMode,
} from "./chartCardChrome";
import { CHART_CARD_HEIGHTS, isChartCardHeight, type ChartCardHeight } from "./chartCardScale";
import styles from "./ChartCard.module.css";

export type ChartCardState = SurfaceStatus;

export type ChartCardRendererProps = {
  option: EChartsOption;
  height: ChartCardHeight;
};

export type ChartCardProps = {
  /** ≤ 12 字的区块标题；flat 模式可省略并沿用外层区块标题。 */
  title?: string;
  /** 一句业务问题（12px muted），回答"这张图为什么在这里"。 */
  question?: string;
  /** 亿元 / % / bp 等；与 asOf 一起构成标题行右侧唯一的 "·" 元信息。 */
  unit?: string;
  /** 数据日期：不传 = 该图无独立日期（不占位）；null = 应有但缺失，渲染 EM_DASH。stale / partial 时日期前加琥珀圆点。 */
  asOf?: string | null;
  /** 只允许 160 / 220 / 280 三档；非法值回落 220 并在开发态 warn。 */
  height?: ChartCardHeight;
  /** null 或 series 为空 → 空态收缩；铬件（图例 / tooltip / 网格 / 文字色）由组件统一覆盖。 */
  option: EChartsOption | null;
  /** 默认由 option 推导 ready / empty；loading / error / stale / partial 由调用方传入。 */
  state?: ChartCardState;
  errorMessage?: string;
  emptyMessage?: string;
  /** error 态的一次重试；不传则不渲染按钮（例如 403 重试无意义）。 */
  onRetry?: () => void;
  footnote?: string;
  /** 右上角动作，最多两个。 */
  actions?: ReactNode;
  legend?: ChartCardLegendMode;
  /** 图例预计行数（多系列时传 2–4），用于底部预留；默认 1。 */
  legendRows?: number;
  /** 嵌在已有面板里时去掉自己的边与底，只保留标题行与画布。 */
  flat?: boolean;
  /** 叠在画布上的 DOM 层（环形图中心读数等）；只在实际绘图时渲染，空态 / 错态不叠。 */
  canvasOverlay?: ReactNode;
  /** 需要 ECharts onEvents 等交互能力时使用；接收已应用统一铬件的 option。 */
  chartRenderer?: (props: ChartCardRendererProps) => ReactNode;
  /** 画布下方的补充区（自定义图例、紧凑数值列、行内提示）；五态下都渲染，由调用方决定内容。 */
  children?: ReactNode;
  testId?: string;
  ariaLabel?: string;
};

const DEFAULT_EMPTY_MESSAGE = "暂无数据";
const DEFAULT_ERROR_MESSAGE = "读取失败，不使用前端补数。";
const STATE_WORD: Record<Exclude<ChartCardState, "ready" | "loading" | "empty" | "error">, string> = {
  stale: "数据陈旧",
  partial: "部分可用",
};

function resolveHeight(height: ChartCardHeight | undefined): ChartCardHeight {
  if (height === undefined) return CHART_CARD_HEIGHTS.default;
  if (isChartCardHeight(height)) return height;
  if (import.meta.env.DEV) {
    console.warn(`[ChartCard] 非法高度 ${String(height)}，只允许 160 / 220 / 280，已回落 220。`);
  }
  return CHART_CARD_HEIGHTS.default;
}

function resolveState(state: ChartCardState | undefined, option: EChartsOption | null): ChartCardState {
  if (state && state !== "ready") return state;
  return isChartCardOptionEmpty(option) ? "empty" : "ready";
}

export function ChartCard({
  title,
  question,
  unit,
  asOf,
  height,
  option,
  state,
  errorMessage,
  emptyMessage,
  onRetry,
  footnote,
  actions,
  legend = "bottom-left",
  legendRows,
  flat = false,
  canvasOverlay,
  chartRenderer,
  children,
  testId,
  ariaLabel,
}: ChartCardProps) {
  const resolvedHeight = resolveHeight(height);
  const resolvedState = resolveState(state, option);
  const drawsChart = resolvedState === "ready" || resolvedState === "stale" || resolvedState === "partial";

  const chromedOption = useMemo(
    () => (option && drawsChart ? applyChartCardChrome(option, { legend, legendRows }) : null),
    [option, drawsChart, legend, legendRows],
  );

  useEffect(() => {
    if (!import.meta.env.DEV || !option) return;
    const warnings = detectChartCardWarnings(option);
    if (warnings.length > 0) {
      console.warn(`[ChartCard] ${title ?? ariaLabel ?? "图表"}: ${warnings.join(" ")}`);
    }
  }, [ariaLabel, option, title]);

  // asOf 三态：undefined = 该图没有独立数据日期（不占位）；null = 应有但缺失（EM_DASH）；string = 显示。
  const metaParts = [unit, asOf === undefined ? undefined : asOf ?? EM_DASH].filter(
    (part): part is string => Boolean(part),
  );
  const flagged = resolvedState === "stale" || resolvedState === "partial";
  const hasTitles = Boolean(title || question);
  const hasActions = metaParts.length > 0 || Boolean(actions);
  const hasCaption = hasTitles || hasActions;

  return (
    <figure
      className={styles.card}
      data-testid={testId}
      data-state={resolvedState}
      data-flat={flat ? "true" : undefined}
      aria-label={ariaLabel ?? title ?? "图表"}
    >
      {hasCaption ? (
        <figcaption className={styles.head}>
          {hasTitles ? (
            <div className={styles.titles}>
              {title ? (
                <span className={styles.title} title={title}>
                  {title}
                </span>
              ) : null}
              {question ? (
                <span className={styles.question} title={question}>
                  {question}
                </span>
              ) : null}
            </div>
          ) : null}
          {hasActions ? (
            <div className={styles.actions}>
              <span
                className={styles.meta}
                title={flagged ? `${STATE_WORD[resolvedState]}：${metaParts.join(" · ")}` : undefined}
              >
                {flagged ? <i className={styles.metaDot} aria-hidden="true" /> : null}
                {metaParts.join(" · ")}
              </span>
              {actions}
            </div>
          ) : null}
        </figcaption>
      ) : null}

      <div className={styles.canvas}>
        {drawsChart && chromedOption ? (
          <>
            {chartRenderer ? (
              chartRenderer({ option: chromedOption, height: resolvedHeight })
            ) : (
              <BaseChart option={chromedOption} height={resolvedHeight} />
            )}
            {canvasOverlay ? (
              <div className={styles.canvasOverlay} aria-hidden="true">
                {canvasOverlay}
              </div>
            ) : null}
          </>
        ) : (
          <StateSurface
            status={resolvedState}
            message={
              resolvedState === "empty"
                ? emptyMessage ?? DEFAULT_EMPTY_MESSAGE
                : resolvedState === "error"
                  ? errorMessage ?? DEFAULT_ERROR_MESSAGE
                  : undefined
            }
            minHeight={resolvedHeight}
            actions={
              resolvedState === "error" && onRetry ? (
                <button type="button" onClick={onRetry}>
                  重试
                </button>
              ) : undefined
            }
            testId={testId ? `${testId}-state` : undefined}
          />
        )}
      </div>

      {children ? <div className={styles.below}>{children}</div> : null}

      {footnote ? (
        <p className={styles.footnote} title={footnote}>
          {footnote}
        </p>
      ) : null}
    </figure>
  );
}

export default ChartCard;
