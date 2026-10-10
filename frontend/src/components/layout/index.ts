/**
 * 视觉原语层（Nocturne 深色终端）。
 *
 * 存在的理由：这些版式保证过去写在各页面的 CSS 里，于是「编号分区头」「KPI 单框
 * 横带」「表格密度」在 20 多个页面各自实现了一遍，同类版式问题（标签换行致数值
 * 错位、等高 stretch 空卡留白、懒加载占位重排、状态文案重复）在六个页面反复返工
 * 两三轮。原语把保证收进组件自带的 CSS module，页面因此失去写歪的能力。
 *
 * 使用纪律：
 * - 组件自包含，不依赖页面 CSS 才能正确显示；页面不要再去覆盖它们的密度与色板。
 * - 颜色一律走 `--dh-api-*` 语义链（scope 内解析为 Nocturne `--nct-*`）。
 * - 编号分区头需要把同一串分区包在 `SECTION_HEAD_STACK_CLASSNAME` 容器里，
 *   一个容器 = 一个独立编号域（tab 各自从 01 开始时要各套一层）。
 *
 * 各原语的边界见其源文件头注释；DataTable 不适用的场景（排序/固定列/虚拟滚动/
 * 行选择等）回退 AG Grid，非行列结构的可视化不要塞进 `<table>`。
 */

export { default as KpiStrip } from "./KpiStrip";
export type { KpiCell, KpiCellStatus, KpiStripCols, KpiStripProps } from "./KpiStrip";

export {
  default as SectionHead,
  SECTION_HEAD_COUNTER_CSS_VAR,
  SECTION_HEAD_STACK_CLASSNAME,
} from "./SectionHead";
export type {
  SectionHeadContentGap,
  SectionHeadExternalCounter,
  SectionHeadNumbering,
  SectionHeadProps,
  SectionMetaField,
  SectionState,
  SectionStateTone,
} from "./SectionHead";

export { SectionGrid, SectionGridItem } from "./SectionGrid";
export type {
  SectionGridAlign,
  SectionGridBreakpointCols,
  SectionGridColSpec,
  SectionGridGap,
  SectionGridItemProps,
  SectionGridItemSpan,
  SectionGridProps,
} from "./SectionGrid";

export { StateSurface, StateSurfaceQuotaProvider } from "./StateSurface";
export type { StateSurfaceDensity, StateSurfaceProps, SurfaceStatus } from "./StateSurface";

export { STATE_SURFACE_DEDUPE_LIMIT, useStateSurfaceQuota } from "./stateSurfaceQuota";
export type { StateSurfaceQuotaContextValue } from "./stateSurfaceQuota";

export { DataTable } from "./DataTable";
export type {
  ColumnAlign,
  DataTableColumn,
  DataTableColumnNotice,
  DataTableDensity,
  DataTableEmptyPolicy,
  DataTableProps,
  DataTableStatus,
  DataTableSummaryRow,
} from "./DataTable";

export { SURFACE_STATUS_LABEL, sectionStateFromStatus } from "./statusBridge";
