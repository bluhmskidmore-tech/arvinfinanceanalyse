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

  return (
    <div
      className={`inline-flex min-h-12 items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2.5 py-2 ${className}`}
      role="status"
      aria-label={ariaLabel}
      data-testid={testId}
      title={title}
    >
      <StatusIcon tone={tone}>{icon}</StatusIcon>
      <span className="min-w-0">
        <span className={`block text-[10px] font-semibold ${toneTextClass(tone)}`}>{label}</span>
        <strong className="block truncate text-sm font-semibold text-neutral-900">{value}</strong>
        {detail ? <span className="block text-xs font-medium leading-snug text-neutral-600">{detail}</span> : null}
      </span>
    </div>
  );
}
