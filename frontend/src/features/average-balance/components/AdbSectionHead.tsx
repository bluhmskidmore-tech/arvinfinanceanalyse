import type { ReactNode } from "react";

import "./AverageBalanceView.css";

type AdbSectionHeadProps = {
  title: string;
  /** 右侧单行口径说明（超长省略，完整文案入 title）。 */
  meta?: string;
  /** 右侧控件位（如月份选择），与 meta 互斥使用为宜。 */
  actions?: ReactNode;
};

/**
 * 编号节题（首页 01/02… 语言：mono 编号 + 标题 + 右侧 meta/控件 + 发丝底线）。
 * 编号由 CSS counter 按已渲染区块顺序生成（总账损益先例）：
 * 数据缺失整节隐藏时编号自动连续，不出现跳号。
 */
export default function AdbSectionHead({ title, meta, actions }: AdbSectionHeadProps) {
  return (
    <div className="adb-sec-head">
      <i aria-hidden="true" />
      <h3>{title}</h3>
      {meta ? (
        <span className="adb-sec-meta" title={meta}>
          {meta}
        </span>
      ) : null}
      {actions ? <div className="adb-sec-actions">{actions}</div> : null}
    </div>
  );
}
