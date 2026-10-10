import type { ReactNode } from "react";

export function CrossAssetDecisionZone({
  id,
  testId,
  title,
  className,
  children,
}: {
  /** 跨页 hash 锚点（如 /cross-asset#cross-asset-zone-linkage）需要的 DOM id；默认不渲染。 */
  id?: string;
  testId: string;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  const zoneClassName = className ? `cross-asset-decision-zone ${className}` : "cross-asset-decision-zone";

  return (
    <section id={id} data-testid={testId} className={zoneClassName} aria-labelledby={`${testId}-title`}>
      <h2 id={`${testId}-title`} className="cross-asset-decision-zone__title">
        {title}
      </h2>
      <div className="cross-asset-decision-zone__body cross-asset-decision-zone__body--flat">{children}</div>
    </section>
  );
}
