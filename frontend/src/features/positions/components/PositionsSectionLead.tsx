import type { ReactNode } from "react";

/**
 * 编号分区头状态位（DESIGN.md §6 五态）：ready 时返回 null 不占版面，
 * 其余状态用一句中文露出。照抄 ledger-pnl SectionLead 模式。
 */
export type PositionsSectionState = {
  label: string;
  tone: "loading" | "error" | "empty";
} | null;

/** 编号分区头（首页 Nocturne 语言）：序号由 CSS counter 生成，禁止手写编号。 */
export default function PositionsSectionLead({
  title,
  state,
  note,
  actions,
}: {
  title: string;
  state?: PositionsSectionState;
  note?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="positions-view__section-lead">
      <h2>{title}</h2>
      {state ? (
        <span className="positions-view__section-state" data-state={state.tone} role="status">
          {state.label}
        </span>
      ) : note ? (
        <span className="positions-view__section-note">{note}</span>
      ) : actions ? (
        <div className="positions-view__section-actions">{actions}</div>
      ) : null}
    </header>
  );
}
