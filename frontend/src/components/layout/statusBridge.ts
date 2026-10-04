import type { SectionState } from "./SectionHead";
import type { SurfaceStatus } from "./StateSurface";

/**
 * 五态默认中文词表——原语层的单一来源。
 *
 * 背景：`/bond-dashboard` 迁移时四个分区各自写了一遍「读取中 / 读取失败 /
 * 暂无数据」，最后被迫在 feature 内新建 `sectionStatus.ts` 收口成单一来源。
 * 37 个页面铺开时如果每页各建一份，这次消掉的重复会在下一页重新长出来，所以
 * 默认文案下沉到这里，而不是留给每个调用方各写一份。
 *
 * 单一来源约束：`StateSurface.tsx` 的默认文案直接从这里导入使用，不在那边另存
 * 一份字面量；`sectionStateFromStatus` 省略 `label` 时也读同一份。两处永远同源，
 * 不会出现「原语给的默认词表」与「组件实际渲染的默认文案」互相漂移的情况
 * （`statusBridge.test.ts` 用逐字断言锁住这一点）。
 *
 * `ready` 没有默认文案：ready 态从不展示状态文案（`StateSurface` 直接渲染
 * `children`，`sectionStateFromStatus` 把它映射成 `null`）。
 */
export const SURFACE_STATUS_LABEL: Record<SurfaceStatus, string | undefined> = {
  ready: undefined,
  loading: "正在载入",
  empty: "暂无数据",
  error: "数据加载失败",
  stale: "数据可能已过期",
  partial: "部分数据不可用",
};

/**
 * `SurfaceStatus` 是原语层的规范状态词表。`SectionHead` 的 `SectionState` 刻意不
 * 收 `"ready"`——它的 ready 就是不渲染，用 `null` 表达比多一个枚举值更严格（类型
 * 上排除了「ready 却带 label」）。这个 helper 让页面只维护一份 status，避免每处
 * 手写 `status === "ready" ? null : { ... }` 映射。
 *
 * `label` 可省略：省略时取 `SURFACE_STATUS_LABEL` 里的原语默认文案。业务上「暂无
 * 数据」有时要说成「本期未产生业务」这类更具体的措辞，仍然可以显式传 `label`
 * 覆盖——原语给的是默认值，不是强制值。省略 `label` 是向后兼容的新增能力：现有
 * 「必传 label」的调用方（如 `bond-dashboard`）逐字不受影响。
 */
export function sectionStateFromStatus(status: SurfaceStatus, label?: string): SectionState {
  if (status === "ready") return null;
  return { label: label ?? SURFACE_STATUS_LABEL[status] ?? "", tone: status };
}
