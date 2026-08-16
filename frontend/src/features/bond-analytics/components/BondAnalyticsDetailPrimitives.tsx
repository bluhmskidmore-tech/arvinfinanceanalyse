import type { CSSProperties, Key, ReactNode } from "react";
import { Alert } from "antd";

import { tabularNumsStyle } from "../../../theme/designSystem";
import styles from "./BondAnalyticsDetailPrimitives.module.css";

type DetailChartSkeletonProps = {
  height?: number;
  testId?: string;
};

/** 图表位 loading 占位：锁到接近真实图高，避免数据到达时整卡重排。 */
export function DetailChartSkeleton({ height = 240, testId }: DetailChartSkeletonProps) {
  return (
    <div className={styles.chartSkeleton} style={{ minHeight: height }} data-testid={testId}>
      <span />
      <span />
      <span />
      <span />
    </div>
  );
}

type DetailPanelSkeletonProps = {
  testId?: string;
};

/** 整个明细面板 loading 占位：卡头 + KPI 带 + 主体块，替代裸 Spin。 */
export function DetailPanelSkeleton({ testId }: DetailPanelSkeletonProps) {
  return (
    <div className={styles.panelSkeleton} data-testid={testId}>
      <div className={styles.panelSkeletonHead} />
      <div className={styles.panelSkeletonBand}>
        <span />
        <span />
        <span />
        <span />
      </div>
      <div className={styles.panelSkeletonRow} />
    </div>
  );
}

type DetailEmptyNoteProps = {
  children: ReactNode;
  testId?: string;
};

/** 空态：收缩到消息框自身高度，不画空图也不画虚线框。 */
export function DetailEmptyNote({ children, testId }: DetailEmptyNoteProps) {
  return (
    <div className={styles.emptyNote} data-testid={testId}>
      {children}
    </div>
  );
}

/**
 * 明细请求失败文案：中文原因句进正文，裸端点/原始报错属证据层收进 title（DESIGN §6 溯源分层）。
 * 状态码从 `Request failed: /api/...(502)` 形态中提取；无法识别时给通用原因句，原文保留在 title。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function describeDetailLoadError(raw: string): { text: string; title: string } {
  const statusMatch = /\((\d{3})\)\s*$/.exec(raw.trim());
  const status = statusMatch ? Number(statusMatch[1]) : null;
  const text =
    status === null
      ? "数据请求失败，请稍后重试。"
      : status >= 500
        ? `后端服务暂不可用（${status}），请稍后重试。`
        : status === 404
          ? "请求的读面不存在（404），请核对报告日与参数。"
          : status === 401 || status === 403
            ? `没有访问该读面的权限（${status}）。`
            : `数据请求失败（${status}），请稍后重试。`;
  return { text, title: raw };
}

/** 明细区统一错误横幅：正文中文原因句，title 保留原始报错供复核。 */
export function DetailLoadErrorAlert({ error, testId }: { error: string; testId?: string }) {
  const { text, title } = describeDetailLoadError(error);
  return (
    <Alert
      type="error"
      showIcon
      message={<span title={title}>{text}</span>}
      data-testid={testId}
    />
  );
}

/**
 * 明细区「计算时间」展示：截到分钟，UTC 口径与总览真值条的
 * `bondAnalyticsOverviewModel.formatIsoMoment` 保持同形（同页同一时间戳只允许一种写法）。
 * UTC 口径是登记过的决策（不转本地时区），但必须显式标注 "UTC"，
 * 避免 UTC+8 用户把它误读成本地时间。无法解析的输入原样透出，不隐藏证据。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function formatDetailComputedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

/**
 * 期间 token 的业务标签；文案与驾驶舱期间筛选（bondAnalyticsCockpitTokens.PERIOD_OPTIONS）
 * 逐字一致。未登记枚举原样透出（ledger-pnl 先例）。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function periodTypeLabel(value: string): string {
  if (value === "MoM") return "月度环比";
  if (value === "YTD") return "年初至今";
  if (value === "TTM") return "近12个月";
  return value;
}

type NumericAlignableColumn = {
  key?: Key;
  align?: unknown;
  onCell?: unknown;
};

type TableCellProps = {
  style?: CSSProperties;
  [key: string]: unknown;
};

/**
 * 明细区数值列统一右对齐并挂等宽数字栈。
 * 既有列已用 `onCell` 标记数值单元格，这里沿用该标记；未标记的列用 `numericKeys` 声明。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function withNumericColumns<C>(
  columns: readonly C[],
  numericKeys: readonly string[] = [],
): C[] {
  const declared = new Set(numericKeys);
  return columns.map((column) => {
    const alignableColumn = column as C & NumericAlignableColumn;
    const key = typeof alignableColumn.key === "string" ? alignableColumn.key : "";
    const originalOnCell =
      typeof alignableColumn.onCell === "function"
        ? (alignableColumn.onCell as (...args: unknown[]) => TableCellProps)
        : undefined;
    const marked = Boolean(originalOnCell);
    if (!marked && !declared.has(key)) {
      return column;
    }
    return {
      ...column,
      align: "right",
      onCell: (...args: unknown[]) => {
        const originalCell = originalOnCell?.(...args) ?? {};
        return {
          ...originalCell,
          style: {
            ...(originalCell.style ?? {}),
            ...tabularNumsStyle,
          },
        };
      },
    } as C;
  });
}
