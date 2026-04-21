/**
 * 把一组数值映射成 SVG path d 字符串。
 * - values 为空或全相同 → 返回中线水平线
 * - 自动忽略 NaN / null / undefined
 * - viewBox 固定为 [0, 0, width, height]，边距 2px
 */
export function buildSparkPath(
  values: readonly (number | null | undefined)[],
  width: number,
  height: number,
): string {
  const margin = 2;
  const nums: number[] = [];
  for (const v of values) {
    if (v == null || typeof v !== "number" || Number.isNaN(v)) {
      continue;
    }
    nums.push(v);
  }

  const innerW = Math.max(0, width - 2 * margin);
  const midY = height / 2;
  const x0 = margin;
  const x1 = Math.max(margin, width - margin);

  if (nums.length === 0 || nums.length === 1) {
    return `M ${x0} ${midY} L ${x1} ${midY}`;
  }

  const min = Math.min(...nums);
  const max = Math.max(...nums);
  if (min === max) {
    return `M ${x0} ${midY} L ${x1} ${midY}`;
  }

  const innerH = Math.max(0, height - 2 * margin);
  const points = nums.map((v, i) => {
    const t = nums.length === 1 ? 0 : i / (nums.length - 1);
    const x = margin + t * innerW;
    const yn = (v - min) / (max - min);
    const y = margin + innerH * (1 - yn);
    return { x, y };
  });

  const first = points[0]!;
  return `M ${first.x} ${first.y}${points
    .slice(1)
    .map((p) => ` L ${p.x} ${p.y}`)
    .join("")}`;
}
