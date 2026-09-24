/**
 * KPI 数字滚动的解析与格式化：只接受纯数值展示串（可带符号与千分位），
 * 其余（em dash、含单位残留等）返回 null 表示不可动画。
 */
export type ParsedKpiNumeric = {
  sign: string;
  abs: number;
  decimals: number;
};

export function parseKpiNumeric(value: string): ParsedKpiNumeric | null {
  const match = /^([+-]?)([\d,]+(?:\.\d+)?)$/.exec(value.trim());
  if (!match) return null;
  const amountToken = match[2];
  if (!amountToken) return null;
  const abs = Number(amountToken.replaceAll(",", ""));
  if (!Number.isFinite(abs) || abs <= 0) return null;
  const decimals = amountToken.includes(".")
    ? (amountToken.split(".")[1]?.length ?? 0)
    : 0;
  return { sign: match[1] ?? "", abs, decimals };
}

export function formatKpiNumeric(
  parsed: Pick<ParsedKpiNumeric, "sign" | "decimals">,
  amount: number,
): string {
  return `${parsed.sign}${amount.toLocaleString("zh-CN", {
    minimumFractionDigits: parsed.decimals,
    maximumFractionDigits: parsed.decimals,
  })}`;
}
