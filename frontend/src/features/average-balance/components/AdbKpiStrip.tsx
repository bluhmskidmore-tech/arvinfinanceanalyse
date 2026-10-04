import { WarningFilled } from "@ant-design/icons";

import KpiStrip, { type KpiCell, type KpiStripCols } from "../../../components/layout/KpiStrip";

export type AdbKpiStripItem = {
  key: string;
  label: string;
  /** 已格式化读数（缺值由调用方以 EM_DASH 格式化后传入）。 */
  value: string;
  /** 可选副行（如「TYW 正式余额（区间日均）」）。 */
  detail?: string;
  /** 语义 tone：偏离超限/利差为负走 down（红）。 */
  tone?: "down" | "up" | "ok";
  /** 超限警示图标（偏离度 > 5% 时保留 WarningFilled）。 */
  warn?: boolean;
};

type AdbKpiStripProps = {
  items: AdbKpiStripItem[];
  /** 桌面列数；断点折行由 CSS 统一处理（1200/900/680）。 */
  columns: 2 | 5 | 6;
};

/** KPI 单框横带（首页 kpiStrip 语言：单框 + 发丝竖缝 + 等高分格 + 等宽数字）。 */
export default function AdbKpiStrip({ items, columns }: AdbKpiStripProps) {
  const cols: KpiStripCols = {
    base: 1,
    md: 2,
    lg: columns === 2 ? 2 : 3,
    xl: columns,
  };
  const cells: KpiCell[] = items.map((item) => ({
    key: item.key,
    label: item.label,
    value: item.value,
    valueTone: item.tone === "down" ? "negative" : item.tone ? "positive" : undefined,
    valueAdornment: item.warn ? (
      <WarningFilled className="adb-kpi-warn-icon" aria-hidden="true" />
    ) : undefined,
    note: item.detail,
    noteTitle: item.detail,
  }));

  return <KpiStrip cells={cells} cols={cols} />;
}
