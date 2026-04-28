import type { ReactNode } from "react";

import { displayTokens } from "../theme/displayTokens";

export type KpiCardProps = {
  /** @deprecated Prefer `label`; kept for existing call sites. */
  title?: string;
  label?: string;
  value: string;
  detail?: string;
  unit?: string;
  tone?: "default" | "positive" | "negative" | "warning" | "error";
  icon?: ReactNode;
  /** metric：大号居中数值；text：信息密度更高的小号数值 */
  valueVariant?: "metric" | "text";
  change?: number;
  changeLabel?: string;
  trend?: "up" | "down" | "flat";
  sparklineData?: number[];
  status?: "normal" | "warning" | "danger";
  onClick?: () => void;
};

type ToneKey = NonNullable<KpiCardProps["tone"]>;

const TITLE_COLOR = displayTokens.kpi.label;
const UNIT_COLOR = displayTokens.kpi.unit;
const DETAIL_COLOR = displayTokens.kpi.detail;

const VALUE_COLORS: Record<ToneKey, string> = {
  default: displayTokens.kpi.valueDefault,
  positive: displayTokens.kpi.valuePositive,
  negative: displayTokens.kpi.valueNegative,
  warning: displayTokens.kpi.valueWarning,
  error: displayTokens.kpi.valueNegative,
};

const CARD_SHADOW = displayTokens.kpi.cardShadow;

function resolveToneFromHints(props: Pick<KpiCardProps, "status" | "trend">): ToneKey {
  if (props.status === "warning") {
    return "warning";
  }
  if (props.status === "danger") {
    return "error";
  }
  if (props.trend === "up") {
    return "positive";
  }
  if (props.trend === "down") {
    return "negative";
  }
  return "default";
}

function MiniSparkline({ data }: { data: number[] }) {
  if (data.length === 0) {
    return null;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const w = 56;
  const h = 20;
  const pts = data
    .map((v, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * w;
      const y = h - ((v - min) / span) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} aria-hidden style={{ flexShrink: 0 }}>
      <polyline
        fill="none"
        stroke={displayTokens.kpi.sparklineStroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
    </svg>
  );
}

export function KpiCard({
  title,
  label,
  value,
  detail,
  unit,
  tone: toneProp = "default",
  icon,
  valueVariant = "metric",
  change,
  changeLabel,
  trend,
  sparklineData,
  status: _status,
  onClick,
}: KpiCardProps) {
  const heading = title ?? label ?? "";
  const tone = toneProp !== "default" ? toneProp : resolveToneFromHints({ status: _status, trend });
  const valueColor = VALUE_COLORS[tone];
  const isMetric = valueVariant === "metric";

  const trendGlyph =
    trend === "up" ? "↑" : trend === "down" ? "↓" : trend === "flat" ? "→" : null;

  const changeText =
    change !== undefined && Number.isFinite(change)
      ? `${change > 0 ? "+" : ""}${change.toLocaleString("zh-CN")}`
      : null;

  const outer = (
    <div
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      style={{
        minHeight: isMetric ? 152 : 132,
        minWidth: 0,
        padding: "18px 18px 16px",
        borderRadius: 12,
        background: displayTokens.kpi.cardBg,
        border: displayTokens.kpi.cardBorder,
        boxShadow: CARD_SHADOW,
        display: "flex",
        flexDirection: "column",
        cursor: onClick ? "pointer" : undefined,
        overflow: "visible",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          marginBottom: isMetric ? 12 : 8,
        }}
      >
        {icon ? (
          <div
            aria-hidden
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              borderRadius: 8,
              background: displayTokens.kpi.iconBg,
              color: displayTokens.kpi.iconFg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
            }}
          >
            {icon}
          </div>
        ) : null}
        <div
          style={{
            color: TITLE_COLOR,
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 1.35,
            flex: 1,
            minWidth: 0,
            paddingTop: icon ? 2 : 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
          }}
        >
          <span
            style={{
              flex: "1 1 auto",
              minWidth: 0,
              overflowWrap: "break-word",
              wordBreak: "break-word",
            }}
          >
            {heading}
          </span>
          {sparklineData && sparklineData.length > 0 ? (
            <MiniSparkline data={sparklineData} />
          ) : null}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: isMetric ? "center" : "stretch",
          textAlign: isMetric ? "center" : "left",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "baseline",
            justifyContent: isMetric ? "center" : "flex-start",
            gap: "4px 8px",
            width: "100%",
          }}
        >
          <span
            style={{
              fontSize: isMetric ? 24 : 16,
              fontWeight: 700,
              color: valueColor,
              letterSpacing: isMetric ? "-0.02em" : "normal",
              lineHeight: isMetric ? 1.15 : 1.5,
            }}
          >
            {value}
          </span>
          {unit ? (
            <span
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: UNIT_COLOR,
              }}
            >
              {unit}
            </span>
          ) : null}
          {trendGlyph ? (
            <span style={{ fontSize: 14, color: valueColor }} aria-hidden>
              {trendGlyph}
            </span>
          ) : null}
        </div>

        {changeText || changeLabel ? (
          <p
            style={{
              margin: 0,
              marginTop: 6,
              color: DETAIL_COLOR,
              fontSize: 12,
              lineHeight: 1.45,
              textAlign: isMetric ? "center" : "left",
              width: "100%",
              overflowWrap: "anywhere",
              wordBreak: "break-word",
            }}
          >
            {changeLabel ? `${changeLabel} ` : null}
            {changeText}
          </p>
        ) : null}

        {detail ? (
          <p
            style={{
              margin: 0,
              marginTop: "auto",
              paddingTop: isMetric ? 10 : 8,
              color: DETAIL_COLOR,
              fontSize: 12,
              lineHeight: 1.45,
              textAlign: isMetric ? "center" : "left",
              width: "100%",
              overflowWrap: "anywhere",
              wordBreak: "break-word",
            }}
          >
            {detail}
          </p>
        ) : null}
      </div>
    </div>
  );

  return outer;
}
