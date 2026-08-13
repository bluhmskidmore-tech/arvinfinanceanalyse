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

// default 面与文字/边框改走全局重映射变量（:root 浅色、深色边界翻深），
// 避免 shellTokens 浅色字面量灌进深色 scope 页面；语义 tone 底保持原值。
const surfaceToneBackground: Record<PlaceholderCardSurfaceTone, string> = {
  default: "var(--moss-color-card-bg)",
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
          color: "var(--moss-color-text-primary)",
          lineHeight: 1.5,
        }
      : {
          marginTop: 14,
          marginBottom: 10,
          fontSize: 28,
          fontWeight: 600,
          color: "var(--moss-color-text-primary)",
        };

  return (
    <div
      style={{
        minHeight: valueVariant === "text" ? 140 : 170,
        padding: 24,
        borderRadius: 18,
        background: surfaceToneBackground[surfaceTone],
        border: "1px solid var(--moss-color-border-default)",
        boxShadow: t.shadowPanel,
      }}
    >
      <div
        style={{
          color: "var(--moss-color-text-muted)",
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
          color: "var(--moss-color-text-secondary)",
          fontSize: 14,
        }}
      >
        {detail}
      </p>
    </div>
  );
}
