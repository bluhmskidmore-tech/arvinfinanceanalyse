import type { ReactNode } from "react";

import { displayTokens } from "../theme/displayTokens";
import "./KpiCard.css";

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
  /** For tests / QA; forwarded as `data-testid` on the card root. */
  testId?: string;
};

type ToneKey = NonNullable<KpiCardProps["tone"]>;

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
    <svg width={w} height={h} aria-hidden className="kpi-card__sparkline">
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

function cx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
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
  testId,
}: KpiCardProps) {
  const heading = title ?? label ?? "";
  const tone = toneProp !== "default" ? toneProp : resolveToneFromHints({ status: _status, trend });
  const isMetric = valueVariant === "metric";

  const trendGlyph =
    trend === "up" ? "↑" : trend === "down" ? "↓" : trend === "flat" ? "→" : null;

  const changeText =
    change !== undefined && Number.isFinite(change)
      ? `${change > 0 ? "+" : ""}${change.toLocaleString("zh-CN")}`
      : null;

  return (
    <div
      data-testid={testId}
      data-tone={tone}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={cx(
        "kpi-card",
        !isMetric && "kpi-card--text",
        Boolean(onClick) && "kpi-card--clickable",
      )}
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
    >
      <div className="kpi-card__header">
        {icon ? (
          <div aria-hidden className="kpi-card__icon">
            {icon}
          </div>
        ) : null}
        <div className={cx("kpi-card__title", Boolean(icon) && "kpi-card__title--with-icon")}>
          <span className="kpi-card__title-text">{heading}</span>
          {sparklineData && sparklineData.length > 0 ? (
            <MiniSparkline data={sparklineData} />
          ) : null}
        </div>
      </div>

      <div className="kpi-card__body">
        <div className="kpi-card__value-row">
          <span className="kpi-card__value">{value}</span>
          {unit ? <span className="kpi-card__unit">{unit}</span> : null}
          {trendGlyph ? (
            <span className="kpi-card__trend" aria-hidden>
              {trendGlyph}
            </span>
          ) : null}
        </div>

        {changeText || changeLabel ? (
          <p className="kpi-card__secondary kpi-card__change">
            {changeLabel ? `${changeLabel} ` : null}
            {changeText}
          </p>
        ) : null}

        {detail ? <p className="kpi-card__secondary kpi-card__detail">{detail}</p> : null}
      </div>
    </div>
  );
}
