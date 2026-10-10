import type { ReactNode } from "react";

import { StateSurface } from "../../../components/layout";
import type { BondSectionDataState } from "../sectionStatus";

/**
 * 非表格数据块（图表、评级色带、指标列表）的五态外壳。
 *
 * 这里没有任何视觉决定——高度、背板、空态收缩、状态色全部由 StateSurface 承担。
 * 它存在的理由只是把「分区状态 + 是否真空 → 渲染哪一态」这段映射写一次，而不是
 * 在五个组件里各写一遍三段 ternary（那正是重构前反复复发的形状）。三张表不经过
 * 这里：DataTable 自带同一套判定。
 *
 * 只处理 loading / error / empty / ready 四条分支，因为
 * `BondDashboardBundleSectionStatus` 目前只有 ok 与 error 两个取值，stale / partial
 * 在这条链路上不会产生；契约将来补上时，这里是唯一需要扩展的地方。
 */
export function BondSectionSurface({
  state,
  isEmpty = false,
  loadingMinHeight,
  children,
}: {
  state: BondSectionDataState;
  /** ready 且真空时收缩为「暂无数据」（DESIGN.md §5 空态收缩）。 */
  isEmpty?: boolean;
  /** 载入骨架的防重排下限，取该块内容的真实高度（DESIGN.md §11.10）。 */
  loadingMinHeight: number;
  children: ReactNode;
}) {
  if (state.status === "loading") {
    return <StateSurface status="loading" minHeight={loadingMinHeight} />;
  }
  if (state.status === "error") {
    return <StateSurface status="error" reason={state.message ?? undefined} />;
  }
  if (isEmpty) {
    return <StateSurface status="empty" />;
  }
  return <>{children}</>;
}
