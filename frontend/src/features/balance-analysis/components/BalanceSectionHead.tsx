import type { ReactNode } from "react";

type BalanceSectionHeadProps = {
  /** 分区标题；编号由 CSS counter 按已渲染分区自动生成，禁止手写。 */
  title: string;
  /** 右侧短元信息（口径/计数），单行省略，全文进 title。 */
  meta?: string;
  /** 标题行下的一句说明，弱化展示。 */
  hint?: string;
  actions?: ReactNode;
  /** 默认 h2；细分层级可降为 h3。 */
  as?: "h2" | "h3";
};

/**
 * 首页标准包编号分区头（bond-dashboard / positions / average-balance 同款）：
 * 编号（::before counter）+ 标题 + 右侧元信息 + 发丝底线。
 */
export function BalanceSectionHead({
  title,
  meta,
  hint,
  actions,
  as = "h2",
}: BalanceSectionHeadProps) {
  const Heading = as;
  return (
    <div className="balance-analysis-sec-head">
      <div className="balance-analysis-sec-head__row">
        <Heading className="balance-analysis-sec-head__title">{title}</Heading>
        {meta ? (
          <span className="balance-analysis-sec-head__meta" title={meta}>
            {meta}
          </span>
        ) : null}
        {actions ? <div className="balance-analysis-sec-head__actions">{actions}</div> : null}
      </div>
      {hint ? <p className="balance-analysis-sec-head__hint">{hint}</p> : null}
    </div>
  );
}
