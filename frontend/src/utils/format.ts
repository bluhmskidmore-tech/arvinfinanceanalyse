const zhNumberFormat = new Intl.NumberFormat("zh-CN");

export function fmtYi(v: number): string {
  return `${zhNumberFormat.format(v)} 亿`;
}

export function fmtBp(v: number): string {
  return `${v.toFixed(1)} bp`;
}

export function fmtPct(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtChange(v: number): string {
  return v > 0 ? `+${zhNumberFormat.format(v)}` : zhNumberFormat.format(v);
}

export function fmtRate(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtCount(v: number, unit = "项"): string {
  return `${v} ${unit}`;
}
