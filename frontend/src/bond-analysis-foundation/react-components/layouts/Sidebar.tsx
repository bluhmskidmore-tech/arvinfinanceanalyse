export interface SidebarItem {
  key: string;
  label: string;
  badge?: string;
  active?: boolean;
  onClick?: () => void;
}

export interface SidebarProps {
  title?: string;
  items: SidebarItem[];
}

export function Sidebar({ title = "工作区", items }: SidebarProps) {
  return (
    <nav aria-label="债券分析导航">
      <div style={{ marginBottom: 18, opacity: 0.8 }}>{title}</div>
      <div style={{ display: "grid", gap: 10 }}>
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={item.onClick}
            style={{
              textAlign: "left",
              borderRadius: 14,
              border: item.active ? "1px solid rgba(125, 211, 252, 0.5)" : "1px solid transparent",
              background: item.active ? "rgba(15, 118, 110, 0.2)" : "transparent",
              color: "inherit",
              padding: "12px 14px",
            }}
          >
            <span>{item.label}</span>
            {item.badge ? (
              <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 12 }}>{item.badge}</span>
            ) : null}
          </button>
        ))}
      </div>
    </nav>
  );
}
