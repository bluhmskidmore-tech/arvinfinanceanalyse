import type { CSSProperties } from "react";
import type { LedgerSectionState } from "../models/ledgerPnlDisplay";

/** 只拆分既有展示文案的单位，保留格式化结果、空值与精度。 */
export function LedgerMoneyDisplay({ text }: { text: string }) {
  if (!text.endsWith(" 亿元")) return <>{text}</>;
  return <>{text.slice(0, -3)} <span className="ledger-pnl-money-unit">亿元</span></>;
}

/** 编号分区头（首页 Nocturne 语言）：序号由 CSS counter 生成，避免手写编号漂移。 */
export function LedgerPnlSectionLead({
  title,
  state,
  note,
}: {
  title: string;
  state?: LedgerSectionState;
  note?: string;
}) {
  return (
    <header className="ledger-pnl-section__lead">
      <h2>{title}</h2>
      {state ? (
        <span className="ledger-pnl-section__state" data-state={state.tone} role="status">
          {state.label}
        </span>
      ) : note ? (
        <span className="ledger-pnl-section__note">{note}</span>
      ) : null}
    </header>
  );
}

/**
 * 视口门控区块的占位骨架（DESIGN.md §6：带背板与接近折叠头部的高度，防止内容到达时重排）。
 * 数据查询在区块进入视口后才发起，骨架期不出现"读取失败"之类的误导状态。
 */
export function LedgerSectionSkeleton(props: {
  testId: string;
  title: string;
  minHeight: number;
}) {
  const style = {
    "--ledger-pnl-skeleton-min-height": `${props.minHeight}px`,
  } as CSSProperties;
  return (
    <div
      data-testid={props.testId}
      className="ledger-pnl-section-skeleton"
      style={style}
      role="status"
      aria-label={`${props.title}待加载`}
    >
      <div className="ledger-pnl-section-skeleton__title">{props.title}</div>
      <div className="ledger-pnl-section-skeleton__note">该区块进入视口后自动加载数据。</div>
      <div className="ledger-pnl-section-skeleton__bars" aria-hidden>
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
