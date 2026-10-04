import type { ReactNode } from "react";

import { EM_DASH, type MetricTone } from "../../pageModel";
import styles from "./KpiStrip.module.css";

/**
 * KpiStrip 原语：单框多格 KPI 横带。
 *
 * 组件只渲染，不做格式化——`value`/`delta`/`note` 均为使用方已格式化好的展示串
 * （与 pageModel `LabeledValue` 的"value 已格式化"约定一致）。组件负责的是
 * *视觉保证*：标签换行不挤数值、数值等宽对齐、缺值统一 EM_DASH、长数值不被
 * 断点误砍、无历史序列不冒充有数据。
 */
/**
 * 单格数据状态。`deferred` 与 `loading` 分开：前者是"首屏已发、这格要等完整分析
 * 才确认"，是一种被治理承认的中间态；后者是"请求在飞"。两者呈现相同但语义不同，
 * 合并会让页面无法表达"我故意还没算它"。
 */
export type KpiCellStatus = "ready" | "loading" | "deferred" | "failed";

export type KpiCell = {
  key: string;
  label: string;
  value: string;
  unit?: string | null;
  /** 主值后的轻量图标或状态标记；不参与数值长度判定，并继承主值 tone。 */
  valueAdornment?: ReactNode;
  /** `metric` 保持等宽大数；`text` 用于状态/分类等非数值结论。 */
  valueVariant?: "metric" | "text";
  /**
   * 主值着色。金融页面的一眼扫读靠的是主值本身的颜色（"64 橙色风险"、"市场踩踏
   * 风险"这类结论直接由数值承载），不是靠下面那行 delta——把结论降级成中性墨色
   * 会丢掉页面最核心的视觉信号，这是 `macro-observation` 迁移时保留自写 KPI 带
   * 的原因。缺省不挂属性，主值维持 `--dh-api-ink`，存量调用点 DOM 逐字不变；
   * 显式传 `"neutral"` 与缺省同色（区别于 delta 的 neutral 是 muted——delta 是
   * 次要读数，主值是主要读数）。
   */
  valueTone?: MetricTone;
  /**
   * 单格自身的数据状态。整条横带的 `loading` 是"全部在等"，这里管的是"这一格
   * 在等 / 这一格失败了"——两个域都撞上过：`macro-observation` 六格里 deferred
   * 与 ready 混排，`positions` 迁移时因为原语没有这个维度而放弃了格级着色。
   *
   * 语义是**状态优先于语气**：非 ready 时状态色压过 `valueTone`，因为"还没拿到
   * 数"和"拿到了一个坏数"必须看得出区别。缺省不挂属性，`valueTone` 照常生效，
   * 存量调用点 DOM 逐字不变。
   */
  cellStatus?: KpiCellStatus;
  /** 环比/同比等变动读数，已格式化（如 "+0.32pct"）。 */
  delta?: string | null;
  deltaTone?: MetricTone;
  /** 小注，如分母说明、基准日。缺省不渲染，不占版面。 */
  note?: string | null;
  /** 小注的完整悬停说明；缺省回退为 `note`。 */
  noteTitle?: string | null;
  /**
   * 迷你走势点位。`undefined` = 该 KPI 不承载走势概念（不渲染走势区）；
   * `null` / 空数组 / 少于 2 个有效点 = 承载走势概念但当前无数据
   * （渲染"无历史序列"小注，禁止常数兜底序列）。
   */
  spark?: number[] | null;
};

export type KpiStripCols = {
  base?: number;
  md?: number;
  lg?: number;
  xl?: number;
};

export type KpiStripProps = {
  cells: KpiCell[];
  /** 各断点列数；缺省按 cells.length 展开单行（xl/lg），md 折 4 列，720 以下折 2 列。 */
  cols?: KpiStripCols;
  loading?: boolean;
  /**
   * 尺寸档位。`hero` 放宽格内留白，主值仍为 DESIGN §5.4 的 20px。
   * `compact` 用于短标签的查询工作区，减少留白并保留主值字号。
   * 首屏横带可显式选择 `hero`。
   */
  size?: "default" | "compact" | "hero";
  /** 横带（根节点）testid。 */
  testId?: string;
  /** 仅作为语义/定位钩子；视觉仍完全由 KpiStrip 原语控制。 */
  className?: string;
  /** 需要独立区段语义时提供；组件会同步补上 region role。 */
  ariaLabel?: string;
  /**
   * 格子 testid 前缀；缺省复用 `testId`（逐字兼容现状：`${testId}-${cell.key}`）。
   *
   * 存在的理由：格子契约与横带锚点并非总是前缀关系（例如既有页面横带锚点是
   * `bond-dashboard-headline-kpis`、格子是 `bond-dashboard-kpi-<key>`）。这类
   * testid 通常被跨页金样本、readiness 契约、Playwright spec 引用，不能因为
   * 迁移到这个原语就改名，此前只能在原语外面再套一层纯粹为了挂 testid 的裸
   * `<div>`。传入此 prop 后横带与格子可以各自独立命名，不再需要外层包装。
   */
  cellTestIdPrefix?: string;
};

const MIN_COLS = 1;
const MAX_COLS = 8;
/** 长读数布局判据：>=9 字符允许完整换行；字号维持 20px，不截断数字。 */
const COMPACT_VALUE_LENGTH = 9;
const SPARK_WIDTH = 56;
const SPARK_HEIGHT = 20;
const CELL_STATUS_LABEL: Record<Exclude<KpiCellStatus, "ready">, string> = {
  loading: "正在载入",
  deferred: "等待完整分析",
  failed: "读取失败",
};

type FiniteSparkPoint = { index: number; value: number };

function clampCols(value: number): number {
  if (!Number.isFinite(value)) return MIN_COLS;
  return Math.min(MAX_COLS, Math.max(MIN_COLS, Math.round(value)));
}

function resolveCols(cellCount: number, cols?: KpiStripCols) {
  const xl = clampCols(cols?.xl ?? Math.max(cellCount, MIN_COLS));
  const lg = clampCols(cols?.lg ?? xl);
  const md = clampCols(cols?.md ?? Math.min(lg, 4));
  const base = clampCols(cols?.base ?? 2);
  return { xl, lg, md, base };
}

function finiteSparkPoints(spark: number[] | null | undefined): FiniteSparkPoint[] {
  if (!spark) return [];
  return spark.reduce<FiniteSparkPoint[]>((points, value, index) => {
    if (Number.isFinite(value)) points.push({ index, value });
    return points;
  }, []);
}

function buildSparkPoints(points: FiniteSparkPoint[], sourceLength: number): string {
  const values = points.map(({ value }) => value);
  const scale = values.reduce((largest, value) => Math.max(largest, Math.abs(value)), 0) || 1;
  const normalizedValues = values.map((value) => value / scale);
  const min = Math.min(...normalizedValues);
  const max = Math.max(...normalizedValues);
  const span = max - min || 1;
  return points
    .map(({ index }, pointIndex) => {
      const x = (index / Math.max(sourceLength - 1, 1)) * SPARK_WIDTH;
      const y =
        SPARK_HEIGHT - ((normalizedValues[pointIndex] - min) / span) * (SPARK_HEIGHT - 4) - 2;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function SkeletonCell({ testId }: { testId?: string }) {
  return (
    <div className={styles.cell} data-testid={testId} data-skeleton="true">
      <div className={styles.skeletonLabel} />
      <div className={styles.skeletonValue} />
      <div className={styles.skeletonDelta} />
    </div>
  );
}

export default function KpiStrip({
  cells,
  cols,
  loading = false,
  size = "default",
  testId,
  cellTestIdPrefix,
  className,
  ariaLabel,
}: KpiStripProps) {
  const resolved = resolveCols(cells.length, cols);
  const cellPrefix = cellTestIdPrefix ?? testId;
  const colAttrs = {
    "data-cols-xl": resolved.xl,
    "data-cols-lg": resolved.lg,
    "data-cols-md": resolved.md,
    "data-cols-base": resolved.base,
    "data-size": size,
  };

  if (loading) {
    const skeletonCount = Math.max(cells.length, resolved.xl, 1);
    return (
      <div
        className={`${styles.strip} ${className ?? ""}`.trim()}
        data-testid={testId}
        data-loading="true"
        role={ariaLabel ? "region" : undefined}
        aria-label={ariaLabel}
        {...colAttrs}
      >
        {Array.from({ length: skeletonCount }, (_, index) => (
          <SkeletonCell key={index} testId={cellPrefix ? `${cellPrefix}-skeleton-${index}` : undefined} />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`${styles.strip} ${className ?? ""}`.trim()}
      data-testid={testId}
      role={ariaLabel ? "region" : undefined}
      aria-label={ariaLabel}
      {...colAttrs}
    >
      {cells.map((cell) => {
        const isMissing = cell.value === undefined || cell.value === null || cell.value === "" || cell.value === EM_DASH;
        const displayValue = isMissing ? EM_DASH : cell.value;
        const showUnit = !isMissing && cell.unit !== undefined && cell.unit !== null && cell.unit !== "";
        const isCompact = displayValue.length >= COMPACT_VALUE_LENGTH;
        const sparkProvided = cell.spark !== undefined;
        const finiteSpark = finiteSparkPoints(cell.spark);
        const sparkValid = finiteSpark.length >= 2;
        const statusLabel =
          cell.cellStatus && cell.cellStatus !== "ready" ? CELL_STATUS_LABEL[cell.cellStatus] : undefined;

        return (
          <div
            key={cell.key}
            className={styles.cell}
            data-kpi-cell="true"
            data-status={cell.cellStatus}
            data-testid={cellPrefix ? `${cellPrefix}-${cell.key}` : undefined}
          >
            <span className={styles.label} title={cell.label}>
              {cell.label}
            </span>

            <div
              className={styles.valueRow}
              data-compact={isCompact ? "true" : undefined}
              data-value-variant={cell.valueVariant === "text" ? "text" : undefined}
            >
              <strong className={styles.value} data-tone={isMissing ? undefined : cell.valueTone}>
                {displayValue}
                {cell.valueAdornment ? (
                  <span className={styles.valueAdornment}>{cell.valueAdornment}</span>
                ) : null}
              </strong>
              {showUnit ? <span className={styles.unit}>{cell.unit}</span> : null}
            </div>

            {statusLabel ? <span className={styles.srOnly}>{statusLabel}</span> : null}

            {cell.delta ? (
              <span className={styles.delta} data-tone={cell.deltaTone ?? "neutral"}>
                {cell.delta}
              </span>
            ) : null}

            {sparkProvided ? (
              <div className={styles.sparkRow}>
                {sparkValid ? (
                  <svg
                    className={styles.spark}
                    width={SPARK_WIDTH}
                    height={SPARK_HEIGHT}
                    viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}
                    role="img"
                    aria-label={`${cell.label} 走势`}
                  >
                    <polyline
                      className={styles.sparkLine}
                      points={buildSparkPoints(finiteSpark, cell.spark?.length ?? 0)}
                    />
                  </svg>
                ) : (
                  <span className={styles.sparkNote}>无历史序列</span>
                )}
              </div>
            ) : null}

            {cell.note ? (
              <span className={styles.note} title={cell.noteTitle ?? cell.note}>
                {cell.note}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
