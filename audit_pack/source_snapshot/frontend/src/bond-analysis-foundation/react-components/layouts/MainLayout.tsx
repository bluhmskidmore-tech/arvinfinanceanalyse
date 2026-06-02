import type { CSSProperties, ReactNode } from "react";

export interface MainLayoutProps {
  header: ReactNode;
  sidebar?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  aside?: ReactNode;
}

const shellStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "280px minmax(0, 1fr) 320px",
  minHeight: "100vh",
  background:
    "linear-gradient(135deg, rgba(7, 18, 34, 0.04), rgba(15, 32, 60, 0.08)), #f5f7fb",
};

export function MainLayout({
  header,
  sidebar,
  footer,
  children,
  aside,
}: MainLayoutProps) {
  return (
    <div data-testid="bond-foundation-main-layout" style={shellStyle}>
      <aside
        style={{
          borderRight: "1px solid #d0d5dd",
          background: "rgba(7, 18, 34, 0.92)",
          color: "#f8fafc",
          padding: 24,
        }}
      >
        {sidebar}
      </aside>
      <div style={{ display: "grid", gridTemplateRows: "auto 1fr auto", minWidth: 0 }}>
        <header
          style={{
            borderBottom: "1px solid #d0d5dd",
            background: "rgba(255, 255, 255, 0.88)",
            backdropFilter: "blur(12px)",
            padding: "20px 24px",
          }}
        >
          {header}
        </header>
        <main style={{ padding: 24 }}>{children}</main>
        <footer style={{ borderTop: "1px solid #d0d5dd", padding: "16px 24px" }}>{footer}</footer>
      </div>
      <aside
        style={{
          borderLeft: "1px solid #d0d5dd",
          padding: 24,
          background: "rgba(248, 250, 252, 0.95)",
        }}
      >
        {aside}
      </aside>
    </div>
  );
}
