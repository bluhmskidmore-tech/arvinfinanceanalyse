import type { ReactNode } from "react";

export type WorkbenchTone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";
export type WorkbenchDataState = "ok" | "loading" | "error" | "empty" | "stale" | "fallback" | "vendor_unavailable" | "explicit_miss";

export interface WorkbenchAction {
  key: string;
  label: ReactNode;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  primary?: boolean;
  onClick?: () => void;
}

export interface WorkbenchBadge {
  key: string;
  label: ReactNode;
  tone?: WorkbenchTone;
}

export type ResultMetaLike = Record<string, unknown> | null | undefined;
