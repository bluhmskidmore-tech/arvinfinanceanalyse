import type { CSSProperties, ReactNode } from "react";

import { SkeletonBarStack } from "./SkeletonBars";
import "./SkeletonBars.css";

type SkeletonContainerProps = {
  children: ReactNode;
  className?: string;
  disableWrapperStyles?: boolean;
};

type SkeletonProps = Omit<SkeletonContainerProps, "children">;

/** IB light surface chrome (DESIGN.md §5): 2px radius, hairline border. */
const wrapperStyle: CSSProperties = {
  width: "100%",
  borderRadius: "var(--ib-radius)",
  border: "1px solid var(--ib-hairline)",
  background: "var(--ib-surface)",
  padding: 16,
};

function SkeletonContainer({
  children,
  className,
  disableWrapperStyles = false,
}: SkeletonContainerProps) {
  return (
    <div
      className={className}
      style={disableWrapperStyles ? undefined : wrapperStyle}
    >
      {children}
    </div>
  );
}

export function CardSkeleton(props: SkeletonProps) {
  return (
    <SkeletonContainer {...props}>
      <SkeletonBarStack bars={4} />
    </SkeletonContainer>
  );
}

export function TableSkeleton(props: SkeletonProps) {
  return (
    <SkeletonContainer {...props}>
      <div className="moss-skeleton-bar moss-skeleton-bar--title" />
      <SkeletonBarStack bars={5} />
    </SkeletonContainer>
  );
}

export function TextSkeleton({ className, disableWrapperStyles }: SkeletonProps) {
  return (
    <SkeletonContainer
      className={className}
      disableWrapperStyles={disableWrapperStyles ?? true}
    >
      <div className="moss-skeleton-bar moss-skeleton-bar--block" />
    </SkeletonContainer>
  );
}
