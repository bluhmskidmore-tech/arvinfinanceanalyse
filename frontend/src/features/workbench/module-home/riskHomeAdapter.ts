import type {
  RiskTensorChangeMetric,
  RiskTensorPayload,
  RiskTensorScalar,
} from "../../../api/contracts";
import { bondNumericRawOrNull } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import type {
  ModuleHomeDetailChart,
  ModuleHomeDetailRow,
  ModuleHomeDetailSection,
} from "./moduleHomeModel";

const RISK_YUAN_PER_WAN = 10_000;

const RISK_KRD_FIELDS = [
  { key: "krd_1y", label: "KRD 1Y" },
  { key: "krd_3y", label: "KRD 3Y" },
  { key: "krd_5y", label: "KRD 5Y" },
  { key: "krd_7y", label: "KRD 7Y" },
  { key: "krd_10y", label: "KRD 10Y" },
  { key: "krd_30y", label: "KRD 30Y" },
] as const satisfies ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }>;

function riskTensorRaw(value: RiskTensorScalar | null | undefined): number | null {
  return bondNumericRawOrNull(value);
}

function priorMetricSparkline(
  metric: RiskTensorChangeMetric | undefined,
): readonly number[] | undefined {
  if (!metric) {
    return undefined;
  }
  const previous = bondNumericRawOrNull(metric.previous);
  const current = bondNumericRawOrNull(metric.current);
  if (previous === null || current === null) {
    return undefined;
  }
  return [previous, current];
}

export function enrichRiskSectionsWithSparklines(
  sections: ModuleHomeDetailSection[],
  tensor: RiskTensorPayload,
): ModuleHomeDetailSection[] {
  const metricByKey = new Map(
    (tensor.prior_period_change?.metrics ?? []).map((metric) => [metric.key, metric]),
  );
  return sections.map((section) => ({
    ...section,
    rows: section.rows.map((row): ModuleHomeDetailRow => {
      const metric = metricByKey.get(row.key);
      const sparkline = priorMetricSparkline(metric);
      if (!sparkline && !metric?.delta_display) {
        return row;
      }
      return {
        ...row,
        sparkline,
        detail: metric?.delta_display ?? row.detail,
      };
    }),
  }));
}

export function buildRiskKrdChart(tensor: RiskTensorPayload): ModuleHomeDetailChart | undefined {
  const categories: string[] = [];
  const values: number[] = [];

  for (const field of RISK_KRD_FIELDS) {
    const raw = riskTensorRaw(tensor[field.key] as RiskTensorScalar | null | undefined);
    if (raw === null) {
      continue;
    }
    categories.push(field.label);
    values.push(Math.abs(raw) / RISK_YUAN_PER_WAN);
  }

  if (categories.length < 2) {
    return undefined;
  }

  return {
    title: "KRD 分布",
    unit: "万元",
    orientation: "horizontal",
    categories,
    values,
  };
}

export function dv01LimitStatusLabel(status: string): string {
  if (status === "pending_configuration") return "限额待配置";
  if (status === "ok") return "限额内";
  if (status === "near") return "接近限额";
  if (status === "breach") return "已超限";
  return status;
}

export function riskKpiSparklineFromTensor(
  tensor: RiskTensorPayload,
  metricKey: string,
): readonly number[] | undefined {
  const metric = tensor.prior_period_change?.metrics?.find((item) => item.key === metricKey);
  return priorMetricSparkline(metric);
}
