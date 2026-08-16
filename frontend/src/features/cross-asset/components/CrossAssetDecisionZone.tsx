import type { ReactNode } from "react";

export function CrossAssetDecisionZone({
  testId,
  title,
  className,
  children,
}: {
  testId: string;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  const zoneClassName = className ? `cross-asset-decision-zone ${className}` : "cross-asset-decision-zone";

  return (
    <section data-testid={testId} className={zoneClassName} aria-labelledby={`${testId}-title`}>
      <h2 id={`${testId}-title`} className="cross-asset-decision-zone__title">
        {title}
      </h2>
      <div className="cross-asset-decision-zone__body cross-asset-decision-zone__body--flat">{children}</div>
    </section>
  );
}
