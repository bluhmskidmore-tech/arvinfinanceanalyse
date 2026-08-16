import type { Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { TONE_CSS_VAR } from "../../../utils/tone";

type FormatValue = Numeric | string | number | null | undefined;

function coerceRaw(value: FormatValue): number {
  if (value == null) {
    return Number.NaN;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : Number.NaN;
  }
  if (typeof value === "string") {
    return Number.parseFloat(value);
  }
  if (value.raw === null || !Number.isFinite(value.raw)) {
    return Number.NaN;
  }
  return value.raw;
}

/** Format yuan amount to 亿 with 2 decimal places */
export const formatYi = (value: FormatValue): string => {
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return EM_DASH;
  return `${(num / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
};

/** Format yuan amount to 万 with no decimal places */
export const formatWan = (value: FormatValue): string => {
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return EM_DASH;
  return `${(num / 1e4).toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 万`;
};

/** Format DV01 raw yuan-per-bp exposure to 万元/bp display. */
export const formatDv01Wan = (value: FormatValue, digits = 2): string => {
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return EM_DASH;
  return (num / 1e4).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

/** Format percentage: `pct` unit uses server display; `ratio` uses raw×100 (e.g. 0.25 → 25%). */
export const formatPct = (value: Numeric | string | null | undefined): string => {
  if (value != null && typeof value !== "string") {
    if (value.unit === "pct" && value.display) {
      return value.display;
    }
    if (value.unit === "ratio" && value.raw !== null && Number.isFinite(value.raw)) {
      return `${(value.raw * 100).toFixed(2)}%`;
    }
  }
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return EM_DASH;
  return `${(num * 100).toFixed(2)}%`;
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
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return EM_DASH;
  return `${num.toFixed(1)} bp`;
};

/**
 * Color for positive/negative values（2026-08-11 全站决议：绿涨红跌，DESIGN §4）。
 * 主题感知入口：走 `TONE_CSS_VAR` CSS 变量（深色路由 `.theme-dh-api` 自动重映射），
 * 仅供 DOM style/CSS 消费；canvas/ECharts 场景请改用主题 TS 镜像 token。
 * 非负取绿（positive 通道）、负取红（negative 通道）。
 */
export const toneColor = (value: number): string =>
  value >= 0 ? TONE_CSS_VAR.positive : TONE_CSS_VAR.negative;
