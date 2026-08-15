import { useLayoutEffect, useState, type RefObject } from "react";

import { nocturneTokens } from "../../../theme/designSystem";

/**
 * ECharts 配色是 JS 静态常量，CSS 的 Nocturne scope 别名翻不动它。
 * 这里在页面挂载后从页根元素读取 `--dh-api-*` 的实际值构造调色板，
 * 传入 chart builder；jsdom/测试环境 getComputedStyle 返回空串时逐槽
 * 回退到 nocturneTokens 静态值（canonical Nocturne 镜像，DESIGN.md §2.2），
 * 保证测试与逻辑不变（参照 positions/CustomerDetailModal 的 readCssVar 模式）。
 */
export type MarketChartPalette = {
  accent: string;
  /** 次级强调线色：无独立 CSS 变量，按页面 CSS 惯例由 accent+ink color-mix 得出。 */
  accentDeep: string;
  green: string;
  red: string;
  amber: string;
  ink: string;
  inkSoft: string;
  inkMuted: string;
  lineSoft: string;
  panel2: string;
  canvas: string;
};

export const MARKET_CHART_STATIC_PALETTE: MarketChartPalette = {
  accent: nocturneTokens.color.blue,
  // Nocturne 无独立 active 蓝；accent400 与运行时 color-mix(accent 70%, ink 30%) 最接近。
  accentDeep: nocturneTokens.color.accent400,
  green: nocturneTokens.color.green,
  red: nocturneTokens.color.red,
  amber: nocturneTokens.color.amber,
  ink: nocturneTokens.color.ink,
  inkSoft: nocturneTokens.color.inkSoft,
  inkMuted: nocturneTokens.color.inkMuted,
  lineSoft: nocturneTokens.color.lineSoft,
  panel2: nocturneTokens.color.panel2,
  canvas: nocturneTokens.color.bg,
};

const CONCRETE_COLOR_PATTERN = /^(#|rgb|hsl)/i;

/**
 * color-mix() 等函数式取值 zrender 解析不了；借一次性探针让浏览器
 * 把它算成 rgb()。探针挂 body（取值串在自定义属性计算后已不含 var()）。
 */
function resolveColorExpression(expression: string): string {
  if (CONCRETE_COLOR_PATTERN.test(expression)) {
    return expression;
  }
  if (typeof document === "undefined" || !document.body) {
    return "";
  }
  const probe = document.createElement("span");
  probe.style.display = "none";
  probe.style.color = expression;
  document.body.appendChild(probe);
  const resolved = getComputedStyle(probe).color.trim();
  probe.remove();
  return CONCRETE_COLOR_PATTERN.test(resolved) ? resolved : "";
}

function readScopeColor(host: Element, name: string): string {
  const raw = getComputedStyle(host).getPropertyValue(name).trim();
  return raw ? resolveColorExpression(raw) : "";
}

export function resolveMarketChartPalette(
  host: Element | null,
): MarketChartPalette {
  if (!host || typeof getComputedStyle !== "function") {
    return MARKET_CHART_STATIC_PALETTE;
  }
  const fallback = MARKET_CHART_STATIC_PALETTE;
  const read = (name: string, fallbackValue: string) =>
    readScopeColor(host, name) || fallbackValue;
  const accent = read("--dh-api-blue", fallback.accent);
  const ink = read("--dh-api-ink", fallback.ink);
  const scopeActive = accent !== fallback.accent || ink !== fallback.ink;
  const palette: MarketChartPalette = {
    accent,
    accentDeep: scopeActive
      ? resolveColorExpression(
          `color-mix(in srgb, ${accent} 70%, ${ink} 30%)`,
        ) || fallback.accentDeep
      : fallback.accentDeep,
    green: read("--dh-api-green", fallback.green),
    red: read("--dh-api-red", fallback.red),
    amber: read("--dh-api-amber", fallback.amber),
    ink,
    inkSoft: read("--dh-api-ink-soft", fallback.inkSoft),
    inkMuted: read("--dh-api-ink-muted", fallback.inkMuted),
    lineSoft: read("--dh-api-line-soft", fallback.lineSoft),
    panel2: read("--dh-api-panel-2", fallback.panel2),
    canvas: read("--dh-api-bg", fallback.canvas),
  };
  const unchanged = (
    Object.keys(palette) as Array<keyof MarketChartPalette>
  ).every((key) => palette[key] === fallback[key]);
  // 全部回退时返回同一实例，方便 setState 直接跳过更新。
  return unchanged ? fallback : palette;
}

export function useMarketChartPalette(
  hostRef: RefObject<HTMLElement | null>,
): MarketChartPalette {
  const [palette, setPalette] = useState(MARKET_CHART_STATIC_PALETTE);
  useLayoutEffect(() => {
    setPalette(resolveMarketChartPalette(hostRef.current));
  }, [hostRef]);
  return palette;
}
