import type { ReactNode } from "react";

import styles from "./institutionalWorkbench.module.css";

export type InstitutionalKpiPriority = "primary" | "secondary" | "gap";
export type InstitutionalKpiTone = "default" | "positive" | "negative";
export type InstitutionalKpiState = "gap" | "pending" | "ready";

type InstitutionalKpiTileProps = {
  label: string;
  value: string;
  detail: string;
  unit?: string;
  status?: string;
  priority?: InstitutionalKpiPriority;
  tone?: InstitutionalKpiTone;
  /** When false, main value stays ink-colored; tone applies to detail only. */
  colorValue?: boolean;
  state?: InstitutionalKpiState;
  testId?: string;
  detailTestId?: string;
  sparkline?: ReactNode;
  className?: string;
};

export function InstitutionalKpiTile({
  label,
  value,
  detail,
  unit,
  status,
  priority = "secondary",
  tone = "default",
  colorValue = true,
  state,
  testId,
  detailTestId,
  sparkline,
  className,
}: InstitutionalKpiTileProps) {
  const resolvedState =
    state ??
    (status === "缺口"
      ? "gap"
      : status === "待读面"
        ? "pending"
        : status === "已读"
          ? "ready"
          : undefined);

  return (
    <article
      className={`${styles.referenceKpiTile} ${className ?? ""}`.trim()}
      data-priority={priority}
      data-state={resolvedState}
      data-testid={testId}
    >
      <div className={styles.referenceKpiHeader}>
        <div className={styles.referenceKpiLabel}>{label}</div>
        {status ? <span>{status}</span> : null}
      </div>
      <div className={styles.referenceKpiValue} data-tone={colorValue ? tone : "default"}>
        {value}
        {unit ? <small>{unit}</small> : null}
      </div>
      <div
        className={styles.referenceKpiDetail}
        data-tone={tone !== "default" ? tone : undefined}
        data-testid={detailTestId}
      >
        {detail}
      </div>
      {sparkline}
    </article>
  );
}

type InstitutionalKpiRailProps = {
  children: ReactNode;
  columns?: 5 | 7;
  layout?: "auto";
  testId?: string;
  flush?: boolean;
};

export function InstitutionalKpiRail({
  children,
  columns = 7,
  layout,
  testId,
  flush,
}: InstitutionalKpiRailProps) {
  const gridProps =
    layout === "auto"
      ? { "data-layout": "auto" as const }
      : { "data-columns": String(columns) };

  return (
    <div className={`${styles.holdingsKpiRail} ${flush ? styles.holdingsKpiRailFlush : ""}`.trim()}>
      <div data-testid={testId} className={styles.holdingsKpiGrid} {...gridProps}>
        {children}
      </div>
    </div>
  );
}
