import type { CSSProperties, ReactNode } from "react";

export type FilterBarProps = {
  children: ReactNode;
  style?: CSSProperties;
};

/** Top-of-page filter row; pass controls as children. */
export function FilterBar({ children, style }: FilterBarProps) {
  return (
    <div
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
