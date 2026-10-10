/**
 * 表格区五态的共享几何常量。
 *
 * 迁移前这两档高度写在 `PositionsView.css` 的 `.positions-view__table-state`
 * （96px 收缩档）与 `--loading`（240px 防重排档）上，六个组件靠 className 共享。
 * 状态渲染搬到 `StateSurface` 后，收缩档由原语自己保证（§5 空态收缩），只有
 * 「骨架要撑到接近真实表高」这一档是页面语域的事实（本页明细表 20 行/页），
 * 收在这里做单一来源，避免六处各写一个数字。
 */
export const TABLE_SKELETON_MIN_HEIGHT = 240;

/**
 * 分布卡（评级 / 行业）的骨架高度：卡内是「图 + 表」两段，实测总高比明细表矮，
 * 用 240px 会在数据到达时反向塌陷，取图表高度（190/220）与表头的合值一档。
 */
export const DISTRIBUTION_SKELETON_MIN_HEIGHT = 200;
