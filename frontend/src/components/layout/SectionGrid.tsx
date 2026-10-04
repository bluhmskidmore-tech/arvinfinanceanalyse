import type { CSSProperties, ReactNode } from "react";

import styles from "./SectionGrid.module.css";

/**
 * Layout primitive that fixes DESIGN.md §11.2 ("等高 stretch 造成的空卡大
 * 留白；左右栏裸空白断层"): a plain CSS Grid defaults to `align-items:
 * stretch`, which drags short cards up to the tallest row neighbour and
 * leaves a bare gap under their content. This component defaults to
 * `align-items: start` so pages lose the ability to regress into that
 * anti-pattern by omission; callers who genuinely want a matched-bottom row
 * must opt in with `align="stretch"` (DESIGN.md §5: 齐底靠卡片背景补齐).
 */
/**
 * 一档的列定义：数字 = 等分列数；权重数组 = 非等分轨道（`[1.45, 1.2, 0.95]`
 * 生成 `minmax(0, 1.45fr) minmax(0, 1.2fr) minmax(0, 0.95fr)`）。
 *
 * 权重是按需能力，不是默认：等分覆盖绝大多数场景。它存在的理由是宽表——含
 * 合计行的表格在等分三列里会把数值列挤出可视区，而 §5 禁止压缩字号保列数，
 * 所以只能给那一列更多权重。
 */
export type SectionGridColSpec = number | readonly number[];

export type SectionGridBreakpointCols = {
  base?: SectionGridColSpec;
  md?: SectionGridColSpec;
  lg?: SectionGridColSpec;
  xl?: SectionGridColSpec;
};

/** Spacing-basis discipline (DESIGN.md §5): only the 8/12/16/24 ladder. */
export type SectionGridGap = 8 | 12 | 16 | 24;

export type SectionGridAlign = "start" | "stretch";

export type SectionGridProps = {
  cols?: SectionGridBreakpointCols;
  gap?: SectionGridGap;
  /** Default "start" — §11.2 anti-pattern only fires when a caller opts into "stretch". */
  align?: SectionGridAlign;
  /** Opt-in auto-fill mode (`minmax(min(minColWidth, 100%), 1fr)`); overrides `cols`. */
  minColWidth?: number;
  children: ReactNode;
  testId?: string;
};

const ALLOWED_GAPS: readonly SectionGridGap[] = [8, 12, 16, 24];
const DEFAULT_GAP: SectionGridGap = 16;
const DEFAULT_BASE_COLS = 1;

function resolveGap(gap: SectionGridGap | undefined): SectionGridGap {
  if (gap === undefined) return DEFAULT_GAP;
  if (!ALLOWED_GAPS.includes(gap)) {
    if (import.meta.env.DEV) {
      console.warn(
        `[SectionGrid] gap=${gap} 不在允许档位 8/12/16/24 内（DESIGN.md §5 基数纪律），已回退为 ${DEFAULT_GAP}。`,
      );
    }
    return DEFAULT_GAP;
  }
  return gap;
}

function resolveColSpec(
  value: SectionGridColSpec | undefined,
  fallback: SectionGridColSpec,
): SectionGridColSpec {
  if (value === undefined) return fallback;
  // 先判数字：Array.isArray 的守卫签名是 `arg is any[]`，对 readonly number[] 不收窄。
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value < 1) return fallback;
    return Math.floor(value);
  }
  const weights = value.filter((weight) => Number.isFinite(weight) && weight > 0);
  if (weights.length > 0) return weights;
  if (import.meta.env.DEV) {
    console.warn("[SectionGrid] 权重数组里没有有效的正数权重，已回退为上一档定义。");
  }
  return fallback;
}

function colCountOf(spec: SectionGridColSpec): number {
  return typeof spec === "number" ? spec : spec.length;
}

/** 等分返回 null（让 CSS 走 --sg-cols-* 的 repeat 回退链），权重返回完整轨道串。 */
function trackOf(spec: SectionGridColSpec): string | null {
  if (typeof spec === "number") return null;
  return spec.map((weight) => `minmax(0, ${weight}fr)`).join(" ");
}

type SectionGridStyle = CSSProperties & Record<`--${string}`, string | number>;

/**
 * 子项跨列（`SectionGridItem`）：跨列本质是子项的属性，但 `SectionGrid` 只接
 * `children: ReactNode`，没有 vnode 内省能力去分辨"这个孩子要不要跨列"——
 * 用 `cloneElement` 硬塞 prop 对任意 children（含字符串、Fragment、非
 * element 节点）不稳，也会让 `SectionGrid` 反过来依赖子项的实现细节，破坏
 * 封装。改用配套组件包一层：调用方显式用 `SectionGridItem` 包住需要跨列的
 * 那个子块，组件把跨列数落到 CSS 变量上，`SectionGrid` 完全不需要知道谁被
 * 包过。未被包的子项行为不变（不带 span 相关的 class/属性）。
 *
 * 断点解析沿用 `cols` 已经定下的规矩（见上方 `resolveColSpec` 注释）：JS 里
 * 按 base→md→lg→xl 前向继承出具体整数，每档变量各自独立赋值，不叠 CSS
 * `var()` 回退链，媒体查询直接读自己那档变量。
 */
export type SectionGridItemSpan =
  | number
  | {
      base?: number;
      md?: number;
      lg?: number;
      xl?: number;
    };

export type SectionGridItemProps = {
  /** 跨列数；数字 = 全断点同值，对象 = 按断点前向继承（未给的档沿用上一档）。 */
  span?: SectionGridItemSpan;
  children: ReactNode;
  testId?: string;
};

const DEFAULT_SPAN = 1;

function normalizeSpan(value: number | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  if (!Number.isFinite(value) || value < 1) {
    if (import.meta.env.DEV) {
      console.warn(`[SectionGridItem] span=${value} 不是有效跨列数（需要 >=1 的整数），已回退为 ${fallback}。`);
    }
    return fallback;
  }
  return Math.floor(value);
}

export function SectionGridItem({ span, children, testId }: SectionGridItemProps) {
  const spec = typeof span === "number" ? { base: span } : span;
  const base = normalizeSpan(spec?.base, DEFAULT_SPAN);
  const md = normalizeSpan(spec?.md, base);
  const lg = normalizeSpan(spec?.lg, md);
  const xl = normalizeSpan(spec?.xl, lg);

  const style: SectionGridStyle = {
    "--sgi-span-base": base,
    "--sgi-span-md": md,
    "--sgi-span-lg": lg,
    "--sgi-span-xl": xl,
  };

  return (
    <div className={styles.item} style={style} data-testid={testId}>
      {children}
    </div>
  );
}

export function SectionGrid({
  cols,
  gap,
  align = "start",
  minColWidth,
  children,
  testId,
}: SectionGridProps) {
  const resolvedGap = resolveGap(gap);
  // Each breakpoint resolves forward from the previous one in JS (not CSS
  // var() fallback chains), so every media query in the stylesheet can read
  // its own `--sg-cols-*` variable directly without nested var() plumbing.
  const base = resolveColSpec(cols?.base, DEFAULT_BASE_COLS);
  const md = resolveColSpec(cols?.md, base);
  const lg = resolveColSpec(cols?.lg, md);
  const xl = resolveColSpec(cols?.xl, lg);
  const isAutoFill = minColWidth !== undefined && minColWidth > 0;

  const style: SectionGridStyle = {
    "--sg-gap": `${resolvedGap}px`,
    "--sg-cols-base": colCountOf(base),
    "--sg-cols-md": colCountOf(md),
    "--sg-cols-lg": colCountOf(lg),
    "--sg-cols-xl": colCountOf(xl),
  };
  for (const [name, spec] of [
    ["base", base],
    ["md", md],
    ["lg", lg],
    ["xl", xl],
  ] as const) {
    const track = trackOf(spec);
    if (track) style[`--sg-track-${name}`] = track;
  }
  if (isAutoFill) {
    style["--sg-min-col-width"] = `${minColWidth}px`;
  }

  const rootClassName = [
    styles.grid,
    align === "stretch" ? styles.alignStretch : styles.alignStart,
    isAutoFill ? styles.autoFill : undefined,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={rootClassName}
      style={style}
      data-testid={testId}
      data-align={align}
      data-mode={isAutoFill ? "auto-fill" : "cols"}
    >
      {children}
    </div>
  );
}
