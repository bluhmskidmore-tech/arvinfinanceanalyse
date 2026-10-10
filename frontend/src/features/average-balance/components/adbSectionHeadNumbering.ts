import type { SectionHeadExternalCounter } from "../../../components/layout";

/**
 * average-balance 页面自己的编号域：`.adb-stack` 上的 `counter-reset: adb-sec`
 * （见 AverageBalanceView.css）先于本次迁移就存在，迁移前由页面私有的
 * `AdbSectionHead` 组件在自己身上 `counter-increment: adb-sec` 打印编号。
 *
 * 迁移到共享 `SectionHead` 后改用其外接编号域能力（`numbered={{ counter, increment }}`），
 * `increment: true` 是因为原实现的递增位同样落在头部自己身上（不是分区容器），
 * 与页面既有 CSS 的编号域完全对齐，序号逐字不变，只是渲染样式（原 12px/800/蓝色
 * 数字）改为 SectionHead 的原语默认样式（11px/500/muted）。
 */
export const ADB_SECTION_HEAD_NUMBERING: SectionHeadExternalCounter = {
  counter: "adb-sec",
  increment: true,
};
