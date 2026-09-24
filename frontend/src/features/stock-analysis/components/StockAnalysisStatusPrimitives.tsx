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

export function StockAnalysisInlineChip({
  children,
  className = "",
  color = "default",
  size = "md",
  startContent,
  title,
  variant = "flat",
}: {
  children?: ReactNode;
  className?: string;
  color?: "default" | "primary" | "secondary" | "success" | "warning" | "danger" | string;
  size?: "sm" | "md" | "lg" | string;
  startContent?: ReactNode;
  title?: string;
  variant?: "flat" | "bordered" | "faded" | "solid" | "light" | string;
}) {
  const toneClass =
    color === "primary"
      ? "border-blue-200 bg-blue-50 text-blue-700"
      : color === "success"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : color === "warning"
          ? "border-amber-200 bg-amber-50 text-amber-700"
          : color === "danger"
            ? "border-rose-200 bg-rose-50 text-rose-700"
            : color === "secondary"
              ? "border-slate-200 bg-slate-50 text-slate-700"
              : "border-default-200 bg-default-50 text-default-700";
  const sizeClass = size === "sm" ? "min-h-5 px-2 py-0 text-xs" : "min-h-6 px-2.5 py-0.5 text-xs";
  const variantClass = variant === "bordered" ? "bg-transparent" : "";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border font-medium ${toneClass} ${sizeClass} ${variantClass} ${className}`.trim()}
      data-color={color}
      data-variant={variant}
      title={title}
    >
      {startContent ? <span aria-hidden="true" className="inline-flex items-center">{startContent}</span> : null}
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
