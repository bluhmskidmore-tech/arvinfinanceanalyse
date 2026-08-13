/**
 * PnlAttributionView 与其 tab 容器共享的展示基元。
 *
 * SectionLead 承担首页 Nocturne 编号分区头语言（2026-08-13 重构）：
 * - 默认 `section` 变体：页根 counter-reset，分区头 ::before 输出 01/02…，
 *   标题 14px/700，右侧留状态位，底部发丝线（样式见 PnlAttributionView.css）。
 * - `card` 变体：卡片级小节头（眉标 + 13px 标题），不参与页级编号，
 *   供口径卡与页签内面板沿用，调用方接口保持兼容。
 */

export function SectionLead(props: {
  eyebrow?: string;
  title: string;
  description: string;
  testId?: string;
  variant?: "section" | "card";
}) {
  if (props.variant === "card") {
    return (
      <div
        data-testid={props.testId}
        className="pnl-attribution-section-lead pnl-attribution-section-lead--card"
      >
        {props.eyebrow ? (
          <span className="pnl-attribution-section-lead__eyebrow">
            {props.eyebrow}
          </span>
        ) : null}
        <h2 className="pnl-attribution-section-lead__title">{props.title}</h2>
        {props.description ? (
          <p className="pnl-attribution-section-lead__description">
            {props.description}
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <div
      data-testid={props.testId}
      className="pnl-attribution-section-lead pnl-attribution-section-head"
    >
      <h2 className="pnl-attribution-section-head__title">{props.title}</h2>
      {props.description ? (
        <p className="pnl-attribution-section-lead__description">
          {props.description}
        </p>
      ) : null}
    </div>
  );
}
