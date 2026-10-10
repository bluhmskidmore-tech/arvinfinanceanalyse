import type { Numeric } from "../../../api/contracts";
import { EM_DASH, formatScaledAmount } from "../../../utils/format";
import { TONE_CSS_VAR } from "../../../utils/tone";

type FormatValue = Numeric | string | number | null | undefined;

function exactRaw(value: FormatValue): string | number | null | undefined {
  if (value === null || value === undefined || typeof value !== "object") return value;
  if (value.raw === null || !Number.isFinite(value.raw)) {
    return null;
  }
  return value.raw_text ?? value.raw;
}

function scaled(value: FormatValue, divisor: number, precision: number, suffix = "", grouped = true): string {
  const display = formatScaledAmount(exactRaw(value), divisor, precision, grouped);
  return display === EM_DASH ? display : `${display}${suffix}`;
}

/** Format yuan amount to 亿 with 2 decimal places */
export const formatYi = (value: FormatValue): string => scaled(value, 1e8, 2, " 亿");

/** Format yuan amount to 万 with no decimal places */
export const formatWan = (value: FormatValue): string => scaled(value, 1e4, 0, " 万");

/** Format DV01 raw yuan-per-bp exposure to 万元/bp display. */
export const formatDv01Wan = (value: FormatValue, digits = 2): string => scaled(value, 1e4, digits);

/** Format percentage: `pct` unit uses server display; `ratio` uses raw×100 (e.g. 0.25 → 25%). */
export const formatPct = (value: Numeric | string | null | undefined): string => {
  if (value != null && typeof value !== "string" && value.unit === "pct" && value.display) {
    return value.display;
  }
  return scaled(value, 0.01, 2, "%", false);
};

/** Format bp value */
export const formatBp = (value: Numeric | string | number | null | undefined): string => {
  if (
    value != null &&
    typeof value !== "string" &&
    typeof value !== "number" &&
    value.unit === "bp" &&
    value.display
  ) {
    return value.display;
  }
  return scaled(value, 1, 1, " bp", false);
};

/**
 * Color for positive/negative values（2026-08-11 全站决议：绿涨红跌，DESIGN §4）。
 * 主题感知入口：走 `TONE_CSS_VAR` CSS 变量（深色路由 `.theme-dh-api` 自动重映射），
 * 仅供 DOM style/CSS 消费；canvas/ECharts 场景请改用主题 TS 镜像 token。
 * 非负取绿（positive 通道）、负取红（negative 通道）。
 */
export const toneColor = (value: number): string =>
  value >= 0 ? TONE_CSS_VAR.positive : TONE_CSS_VAR.negative;
