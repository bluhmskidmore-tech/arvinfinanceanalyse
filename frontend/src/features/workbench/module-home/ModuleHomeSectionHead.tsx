import type { ReactNode } from "react";

export function ModuleHomeSectionHead({
  label,
  title,
  trailing,
  className,
}: {
  label: string;
  title: string;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <span>{label}</span>
      <strong>{title}</strong>
      {trailing}
    </div>
  );
}
