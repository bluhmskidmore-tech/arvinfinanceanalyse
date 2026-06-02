import type { CSSProperties, ReactNode } from "react";

export type FilterBarProps = {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
};

/** Top-of-page filter row; pass controls as children. */
export function FilterBar({ children, className, style }: FilterBarProps) {
  return (
    <div
      className={className}
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 12,
        alignItems: "flex-end",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
