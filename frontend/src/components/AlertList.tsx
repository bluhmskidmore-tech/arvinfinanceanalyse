import { shellTokens } from "../theme/tokens";

export type AlertItem = {
  level: "danger" | "warning" | "caution" | "info";
  title: string;
  detail?: string;
  time?: string;
};

export type AlertListProps = {
  items: AlertItem[];
};

const DOT_COLORS: Record<AlertItem["level"], string> = {
  danger: "#f5222d",
  warning: "#fa8c16",
  caution: "#faad14",
  info: shellTokens.colorAccent,
};

export function AlertList({ items }: AlertListProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((it, idx) => (
        <div
          key={`${it.title}-${idx}`}
          style={{ display: "flex", gap: 10, alignItems: "flex-start" }}
        >
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              marginTop: 6,
              flexShrink: 0,
              background: DOT_COLORS[it.level],
            }}
          />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#162033", lineHeight: 1.5 }}>
              {it.title}
            </div>
            {it.detail ? (
              <div style={{ fontSize: 13, color: "#5c6b82", marginTop: 2, lineHeight: 1.55 }}>
                {it.detail}
              </div>
            ) : null}
            {it.time ? (
              <div
                style={{
                  fontSize: 12,
                  color: "#8090a8",
                  marginTop: 4,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {it.time}
              </div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
