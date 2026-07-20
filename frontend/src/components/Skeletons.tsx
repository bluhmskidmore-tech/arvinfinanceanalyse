import { Skeleton } from "antd";
import type { CSSProperties, ReactNode } from "react";

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
      <Skeleton active paragraph={{ rows: 3 }} title={{ width: "40%" }} />
    </SkeletonContainer>
  );
}

export function TableSkeleton(props: SkeletonProps) {
  return (
    <SkeletonContainer {...props}>
      <Skeleton active paragraph={{ rows: 1, width: ["72%"] }} title={{ width: "28%" }} />
      <Skeleton active paragraph={{ rows: 5 }} title={false} />
    </SkeletonContainer>
  );
}

export function TextSkeleton({ className, disableWrapperStyles }: SkeletonProps) {
  return (
    <SkeletonContainer
      className={className}
      disableWrapperStyles={disableWrapperStyles ?? true}
    >
      <Skeleton active paragraph={{ rows: 1, width: ["100%"] }} title={false} />
    </SkeletonContainer>
  );
}
