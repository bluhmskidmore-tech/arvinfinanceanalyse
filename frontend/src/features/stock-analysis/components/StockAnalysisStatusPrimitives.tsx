import type { ReactNode } from "react";

import {
  iconTone,
  statusIconClass,
  toneTextClass,
} from "../lib/stockAnalysisPageCopy";

export function StatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: string;
  children: ReactNode;
}) {
  return (
    <span aria-hidden="true" className={statusIconClass(iconTone(tone))}>
      {children}
    </span>
  );
}

export function CompactStatusTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
  testId,
  title,
  className = "",
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: string;
  testId?: string;
  title?: string;
  className?: string;
}) {
  const valueLabel = typeof value === "string" || typeof value === "number" ? String(value) : null;
  const detailLabel = typeof detail === "string" || typeof detail === "number" ? String(detail) : null;
  const ariaLabel = [label, valueLabel, detailLabel].filter(Boolean).join(" ") || undefined;
  const surfaceClass = className.includes("stock-analysis-page__compact-status-tile--accent")
    ? " stock-analysis-page__compact-status-tile--accent"
    : className.includes("stock-analysis-page__compact-status-tile--surface")
      ? " stock-analysis-page__compact-status-tile--surface"
      : "";
  const extraClass = className
    .replace("stock-analysis-page__compact-status-tile--accent", "")
    .replace("stock-analysis-page__compact-status-tile--surface", "")
    .trim();

  return (
    <div
      className={`stock-analysis-page__compact-status-tile${surfaceClass}${extraClass ? ` ${extraClass}` : ""}`}
      role="status"
      aria-label={ariaLabel}
      data-testid={testId}
      title={title}
    >
      <StatusIcon tone={tone}>{icon}</StatusIcon>
      <span className="stock-analysis-page__min-w-0">
        <span className={`stock-analysis-page__compact-status-tile__label ${toneTextClass(tone)}`}>{label}</span>
        <strong className="stock-analysis-page__compact-status-tile__value">{value}</strong>
        {detail ? (
          <span className="stock-analysis-page__compact-status-tile__detail">{detail}</span>
        ) : null}
      </span>
    </div>
  );
}
