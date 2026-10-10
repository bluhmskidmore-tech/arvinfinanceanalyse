/**
 * ADB 深度分析面板专用格式化辅助。
 *
 * 深度分析响应里的数值有两种既有 `src/utils/format.ts` 无法直接覆盖的约定：
 * - 「已是百分比数值」（如 `delta_pct=4.0` 表示 4%，非 0–1 比例）；
 * - 「百分点差值」（`delta_pp`，迁移分析的份额变动，单位 pp）。
 * 金额（元）与 bp 数值请直接复用 `formatYi`/`formatBp`；0–1 比例请复用 `formatPercent`。
 * 本文件不得重复 `formatYi`/`formatPercent`/`formatBp`/`EM_DASH` 已有能力。
 */
import { EM_DASH } from "../../../utils/format";

/** `value` 已是百分比数值（如 4.0 → "+4.00%"），非 0–1 比例。 */
export function formatAlreadyPercent(value: number | null | undefined, signed: boolean): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/** `value` 为百分点（pp）差值（如结构集中度迁移 `delta_pp`）。 */
export function formatPercentagePoints(value: number | null | undefined, signed = true): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}pp`;
}

/** HHI 为 0–1 的无量纲指数，按指标字典保留 4 位小数，不显示为百分比。 */
export function formatHhi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return value.toFixed(4);
}

/** 复用页面既有 `.adb-tone--up`/`.adb-tone--down`（Nocturne scope `--dh-api-*` 家族）。 */
export function toneClassForSign(value: number | null | undefined): string | undefined {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return undefined;
  return value > 0 ? "adb-tone--up" : "adb-tone--down";
}

/** `AdbKpiStripItem.tone` 仅接受 "down" | "up" | "ok"，与 CSS class 版本分开映射。 */
export function kpiToneForSign(value: number | null | undefined): "up" | "down" | undefined {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return undefined;
  return value > 0 ? "up" : "down";
}
