import type { ReactNode } from "react";

export interface HeaderAction {
  key: string;
  label: string;
  onClick?: () => void;
}

export interface HeaderProps {
  title: string;
  subtitle?: string;
  marketStatus?: string;
  refreshLabel?: string;
  actions?: HeaderAction[];
  searchSlot?: ReactNode;
}

export function Header({
  title,
  subtitle,
  marketStatus,
  refreshLabel,
  actions = [],
  searchSlot,
}: HeaderProps) {
  return (
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr auto" }}>
      <div>
        <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase" }}>
          Bond Analysis Platform
        </div>
        <h1 style={{ margin: "6px 0", fontSize: 28 }}>{title}</h1>
        {subtitle ? <p style={{ margin: 0, color: "#475467" }}>{subtitle}</p> : null}
      </div>
      <div style={{ display: "grid", gap: 12, justifyItems: "end" }}>
        {searchSlot}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {marketStatus ? (
            <span style={{ padding: "6px 10px", borderRadius: 999, background: "#e6f4ff" }}>
              {marketStatus}
            </span>
          ) : null}
          {refreshLabel ? (
            <span style={{ padding: "6px 10px", borderRadius: 999, background: "#ecfdf3" }}>
              {refreshLabel}
            </span>
          ) : null}
          {actions.map((action) => (
            <button key={action.key} type="button" onClick={action.onClick}>
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
