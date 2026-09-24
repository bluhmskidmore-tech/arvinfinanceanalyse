import type { ReactNode } from "react";

import type { MacroObservationSectionState } from "../model/macroObservationPageModel";

/**
 * 编号分区头（首页 Nocturne 语言，参照 /positions PositionsSectionLead）：
 * 序号由 CSS counter 生成，禁止手写编号。state 四态
 * （loading/empty/error/deferred）露出模型层给的一句 note，ready（null）
 * 不占版面；note / actions 仅在无 state 时按序补位。
 */
export default function MacroObservationSectionLead({
  title,
  state,
  note,
  actions,
}: {
  title: string;
  state?: MacroObservationSectionState;
  note?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="macro-observation-view__section-lead">
      <h2>{title}</h2>
      {state ? (
        <span
          className="macro-observation-view__section-state"
          data-state={state.state}
          role="status"
        >
          {state.note}
        </span>
      ) : note ? (
        <span className="macro-observation-view__section-note">{note}</span>
      ) : actions ? (
        <div className="macro-observation-view__section-actions">{actions}</div>
      ) : null}
    </header>
  );
}
