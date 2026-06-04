import type { ReactNode } from "react";

import "./FilterBar.css";

export type FilterBarProps = {
  children: ReactNode;
  className?: string;
};

/** Top-of-page filter row; pass controls as children. */
export function FilterBar({ children, className }: FilterBarProps) {
  const classes = ["moss-filter-bar", className].filter(Boolean).join(" ");

  return (
    <div className={classes}>
      {children}
    </div>
  );
}
