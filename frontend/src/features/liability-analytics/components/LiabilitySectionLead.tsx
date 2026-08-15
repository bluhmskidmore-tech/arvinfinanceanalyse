import type { ReactNode } from "react";

/**
 * 编号分区头状态位（DESIGN.md §6 五态）：ready 时为 null 不占版面，
 * 其余状态用一句中文露出。文案约定与 bond-dashboard 等首页标准页一致：
 * loading → 「读取中」、error → 「读取失败」、数据空 → 「暂无数据」。
 */
export type LiabilitySectionState = {
  label: string;
  tone: "loading" | "error" | "empty";
} | null;

/** 编号分区头（首页 Nocturne 语言）：序号由 CSS counter 生成，禁止手写编号。 */
export function LiabilitySectionLead({
  title,
  state,
  note,
  actions,
}: {
  title: string;
  state?: LiabilitySectionState;
  note?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="liability-section__lead">
      <h2>{title}</h2>
      {state ? (
        <span className="liability-section__state" data-state={state.tone} role="status">
          {state.label}
        </span>
      ) : note ? (
        <span className="liability-section__note">{note}</span>
      ) : actions ? (
        <div className="liability-section__actions">{actions}</div>
      ) : null}
    </header>
  );
}
