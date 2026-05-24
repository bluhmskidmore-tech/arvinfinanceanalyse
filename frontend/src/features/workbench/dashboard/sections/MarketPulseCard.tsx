import { Link } from "react-router-dom";

import type { DashboardMarketPulseVM } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { buildSparkPath } from "../sparklinePath";

const SPARK_W = 88;
const SPARK_H = 28;
const SPARK_BASELINE_Y = SPARK_H - 2;

type MarketPulseCardProps = {
  item: DashboardMarketPulseVM;
};

function resolveDirectionLabel(item: DashboardMarketPulseVM): string {
  const isSpread =
    item.id.includes("spread") ||
    item.id.includes("slope") ||
    item.label.includes("利差");
  if (isSpread) {
    if (item.deltaTone === "up") return "走阔";
    if (item.deltaTone === "down") return "收窄";
    return "稳定";
  }
  if (item.deltaTone === "up") return "上行";
  if (item.deltaTone === "down") return "下行";
  if (item.deltaTone === "warn") return "波动";
  return "稳定";
}

function sparkEndPoint(values: readonly number[], width: number, height: number) {
  const margin = 2;
  const nums = values.filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
  if (nums.length === 0) {
    return { x: width - margin, y: height / 2 };
  }
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const innerW = Math.max(0, width - 2 * margin);
  const innerH = Math.max(0, height - 2 * margin);
  const last = nums[nums.length - 1]!;
  const t = nums.length === 1 ? 1 : 1;
  const x = margin + t * innerW;
  const y =
    min === max
      ? height / 2
      : margin + innerH * (1 - (last - min) / (max - min));
  return { x, y };
}

export function MarketPulseCard({ item }: MarketPulseCardProps) {
  const path = buildSparkPath(item.sparkline, SPARK_W, SPARK_H);
  const areaPath = `${path} L ${SPARK_W - 2} ${SPARK_BASELINE_Y} L 2 ${SPARK_BASELINE_Y} Z`;
  const endPoint = sparkEndPoint(item.sparkline, SPARK_W, SPARK_H);
  const directionLabel = resolveDirectionLabel(item);

  return (
    <Link
      to="/market-data"
      data-testid={`dashboard-market-pulse-${item.id}`}
      className="dashboard-cockpit-pulse"
      data-tone={item.deltaTone}
      aria-label={`${item.label} ${item.value}`}
    >
      <div className="dashboard-cockpit-pulse__head">
        <span className="dashboard-cockpit-pulse__label">
          {item.label}
          {item.isEstimated ? (
            <span className="dashboard-cockpit-pulse__estimate" aria-label="估算值">
              估算
            </span>
          ) : null}
        </span>
        <span className="dashboard-cockpit-pulse__status">{directionLabel}</span>
      </div>
      <span className="dashboard-cockpit-pulse__impact">{item.impactLabel}</span>
      <div className="dashboard-cockpit-pulse__body">
        <div className="dashboard-cockpit-pulse__values">
          <strong className="dashboard-cockpit-tabular">{item.value}</strong>
          <span className={`dashboard-cockpit-tabular ${resolveKpiDeltaClass(item.deltaTone)}`}>
            {item.delta}
          </span>
        </div>
        <svg
          className="dashboard-cockpit-pulse__spark"
          viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
          aria-hidden="true"
        >
          <path
            d={`M 2 ${SPARK_BASELINE_Y} L ${SPARK_W - 2} ${SPARK_BASELINE_Y}`}
            className="dashboard-cockpit-pulse__spark-baseline"
          />
          <path d={areaPath} className="dashboard-cockpit-pulse__spark-area" stroke="none" />
          <path
            d={path}
            className="dashboard-cockpit-pulse__spark-line"
            fill="none"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <circle
            cx={endPoint.x}
            cy={endPoint.y}
            r="2.2"
            className="dashboard-cockpit-pulse__spark-dot"
          />
        </svg>
      </div>
      <span className="dashboard-cockpit-pulse__hover-hint">查看曲线 →</span>
    </Link>
  );
}
