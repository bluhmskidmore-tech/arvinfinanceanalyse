import type { ReactNode } from "react";

/**
 * 编号分区头状态位（DESIGN.md §6 五态）：ready 时为 null 不占版面，
 * 其余状态用一句中文露出。推导约定（各使用方私有实现，锁定同一文案）：
 * loading → 「读取中」、error → 「读取失败」、数据空 → 「暂无数据」。
 */
export type BondDashboardSectionState = {
  label: string;
  tone: "loading" | "error" | "empty";
} | null;

/** 编号分区头（首页 Nocturne 语言）：序号由 CSS counter 生成，禁止手写编号。 */
export default function BondDashboardSectionLead({
  title,
  state,
  note,
  actions,
}: {
  title: string;
  state?: BondDashboardSectionState;
  note?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="bond-dashboard-section__lead">
      <h2>{title}</h2>
      {state ? (
        <span className="bond-dashboard-section__state" data-state={state.tone} role="status">
          {state.label}
        </span>
      ) : note ? (
        <span className="bond-dashboard-section__note">{note}</span>
      ) : actions ? (
        <div className="bond-dashboard-section__actions">{actions}</div>
      ) : null}
    </header>
  );
}
