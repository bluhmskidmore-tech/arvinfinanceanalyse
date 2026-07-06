import { Skeleton } from "antd";
import type { ReactNode } from "react";

type SkeletonContainerProps = {
  children: ReactNode;
  className?: string;
  disableWrapperStyles?: boolean;
};

type SkeletonProps = Omit<SkeletonContainerProps, "children">;

function SkeletonContainer({
  children,
  className,
  disableWrapperStyles = false,
}: SkeletonContainerProps) {
  const classes = disableWrapperStyles
    ? className
    : ["w-full rounded-lg border border-default-200/60 bg-white/80 p-4", className]
        .filter(Boolean)
        .join(" ");

  return <div className={classes}>{children}</div>;
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
