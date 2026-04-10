/** Format yuan amount to 亿 with 2 decimal places */
export const formatYi = (value: string): string => {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return "-";
  return `${(num / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
};

/** Format yuan amount to 万 with no decimal places */
export const formatWan = (value: string): string => {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return "-";
  return `${(num / 1e4).toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 万`;
};

/** Format percentage from decimal (0.0255 -> "2.55%") */
export const formatPct = (value: string): string => {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return "-";
  return `${(num * 100).toFixed(2)}%`;
};

/** Format bp value */
export const formatBp = (value: string): string => {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return "-";
  return `${num.toFixed(1)} bp`;
};

/** Color for positive/negative values (China standard: red=up, green=down) */
export const toneColor = (value: number): string =>
  value >= 0 ? "#cf1322" : "#3f8600";
