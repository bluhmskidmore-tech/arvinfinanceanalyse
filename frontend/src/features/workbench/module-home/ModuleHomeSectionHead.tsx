import type { ReactNode } from "react";

export function ModuleHomeSectionHead({
  label,
  title,
  trailing,
  className,
  index,
}: {
  label: string;
  title: string;
  trailing?: ReactNode;
  className?: string;
  index?: string;
}) {
  const showLabel = Boolean(label) || Boolean(index);
  return (
    <div className={className}>
      {showLabel ? (
        <span>
          {index ? (
            <i data-section-index aria-hidden="true">
              {index}
            </i>
          ) : null}
          {label}
        </span>
      ) : null}
      <strong>{title}</strong>
      {trailing}
    </div>
  );
}
