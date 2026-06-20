import { shellTokens as t } from "../../../theme/tokens";

type PlaceholderCardSurfaceTone = "default" | "ok" | "warning" | "error";

type PlaceholderCardProps = {
  title: string;
  value: string;
  detail: string;
  /** 列表型要点使用 text，大数字演示使用 metric（默认） */
  valueVariant?: "metric" | "text";
  surfaceTone?: PlaceholderCardSurfaceTone;
};

const surfaceToneBackground: Record<PlaceholderCardSurfaceTone, string> = {
  default: t.colorBgSurface,
  ok: t.colorBgSuccessSoft,
  warning: t.colorBgWarningSoft,
  error: t.colorBgDangerSoft,
};

export function PlaceholderCard({
  title,
  value,
  detail,
  valueVariant = "metric",
  surfaceTone = "default",
}: PlaceholderCardProps) {
  const valueStyle =
    valueVariant === "text"
      ? {
          marginTop: 10,
          marginBottom: 8,
          fontSize: 16,
          fontWeight: 600,
          color: t.colorTextPrimary,
          lineHeight: 1.5,
        }
      : {
          marginTop: 14,
          marginBottom: 10,
          fontSize: 28,
          fontWeight: 600,
          color: t.colorTextPrimary,
        };

  return (
    <div
      style={{
        minHeight: valueVariant === "text" ? 140 : 170,
        padding: 24,
        borderRadius: 18,
        background: surfaceToneBackground[surfaceTone],
        border: `1px solid ${t.colorBorderSoft}`,
        boxShadow: t.shadowPanel,
      }}
    >
      <div
        style={{
          color: t.colorTextMuted,
          fontSize: 13,
          letterSpacing: "0.02em",
        }}
      >
        {title}
      </div>
      <div style={valueStyle}>
        {value}
      </div>
      <p
        style={{
          marginBottom: 0,
          color: t.colorTextSecondary,
          fontSize: 14,
        }}
      >
        {detail}
      </p>
    </div>
  );
}
