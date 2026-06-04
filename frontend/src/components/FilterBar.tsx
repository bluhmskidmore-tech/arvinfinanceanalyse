import type { CSSProperties, ReactNode } from "react";

import "./FilterBar.css";

export type FilterBarProps = {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
};

/** Top-of-page filter row; pass controls as children. */
export function FilterBar({ children, className, style }: FilterBarProps) {
  const classes = ["moss-filter-bar", className].filter(Boolean).join(" ");

  return (
    <div className={classes} style={style}>
      {children}
    </div>
  );
}
