import type {
  BalanceDifferenceAttributionWaterfall,
  BalanceMovementPayload,
  BalanceMovementRow,
  BalanceMovementTrendMonth,
  BalanceBusinessMovementTrendMonth,
} from "../../../api/contracts";
import {
  isPreviousCalendarMonth,
  trendDelta,
  type BusinessMovementMatrixRow,
  balanceMovementBuckets,
  trendBucket,
} from "./balanceMovementBusinessModel";

type BalanceDiagnosticTone = "ok" | "info" | "warn" | "critical" | "unknown";

type BalanceDiagnosticTag = {
  label: string;
  tone: BalanceDiagnosticTone;
};

type BalanceEvidenceItem = {
  label: string;
  value: string;
  note?: string;
};

export type BalanceExplanationClosure = {
  tone: BalanceDiagnosticTone;
  headline: string;
  supportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  unsupportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  residualComponent?: BalanceDifferenceAttributionWaterfall["components"][number];
  residualRatioPct: number | null;
  note: string;
};

export type AnalysisDimensionCard = {
  key: string;
  title: string;
  metric: string;
  detail: string;
  href: string;
  tags: BalanceDiagnosticTag[];
  evidence: BalanceEvidenceItem[];
};

function amountToNumber(value: string | number | null | undefined) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function buildExplanationClosure(options: {
  waterfall: BalanceDifferenceAttributionWaterfall | null;
  summary: BalanceMovementPayload["summary"] | null;
}): BalanceExplanationClosure | null {
  const { waterfall, summary } = options;
  if (!waterfall) {
    return null;
  }
  const supportedComponents = waterfall.components.filter(
    (component) => component.is_supported !== false && !component.is_residual,
  );
  const unsupportedComponents = waterfall.components.filter(
    (component) => component.is_supported === false,
  );
  const residualComponent = waterfall.components.find((component) => component.is_residual);
  const residualAmount = amountToNumber(residualComponent?.amount);
  const totalChange = amountToNumber(summary?.balance_change_total);
  const residualRatioPct =
    residualAmount !== null && totalChange !== null && Math.abs(totalChange) > 0
      ? (Math.abs(residualAmount) / Math.abs(totalChange)) * 100
      : null;

  if (unsupportedComponents.length > 0) {
    return {
      tone: residualRatioPct !== null && residualRatioPct > 2 ? "critical" : "warn",
      headline: "存在待补口径，不能反推为已解释",
      supportedComponents,
      unsupportedComponents,
      residualComponent,
      residualRatioPct,
      note: "估值差和外币折算差缺少可闭合字段；页面只展示后端已返回的证据项。",
    };
  }

  return {
    tone: residualRatioPct !== null && residualRatioPct > 2 ? "warn" : "ok",
    headline: "现有瀑布项可用于本页解释闭合",
    supportedComponents,
    unsupportedComponents,
    residualComponent,
    residualRatioPct,
    note: "该判断是页面诊断提示，不替代正式审计归因。",
  };
}

export function coverageTone(value: string | number | null | undefined): BalanceDiagnosticTone {
  const coverage = amountToNumber(value);
  if (coverage === null) {
    return "unknown";
  }
  if (coverage < 80) {
    return "critical";
  }
  if (coverage < 95) {
    return "warn";
  }
  return "ok";
}

export function residualTone(ratioPct: number | null, unsupportedCount: number): BalanceDiagnosticTone {
  if (unsupportedCount > 0) {
    return "warn";
  }
  if (ratioPct !== null && ratioPct > 2) {
    return "warn";
  }
  return "ok";
}

type HistoricalAccountingSignal = {
  bucket: BalanceMovementRow["basis_bucket"];
  headline: string;
  currentDelta: number;
  baselineAverageAbs: number | null;
  baselineCount: number;
  directionReversal: boolean;
};

type HistoricalBusinessSignal = {
  label: string;
  currentDelta: number;
  baselineAverageAbs: number | null;
  baselineCount: number;
};

export type HistoricalAnomalyDiagnostics = {
  sampleCount: number;
  baselinePairCount: number;
  headline: string;
  accountingSignals: HistoricalAccountingSignal[];
  businessSignals: HistoricalBusinessSignal[];
};

function averageAbs(values: number[]) {
  if (values.length === 0) {
    return null;
  }
  return values.reduce((total, value) => total + Math.abs(value), 0) / values.length;
}

function directionOf(value: number) {
  if (value > 0) return 1;
  if (value < 0) return -1;
  return 0;
}

function buildDeltaSeries<T>(
  months: T[],
  getReportDate: (month: T) => string,
  getValue: (month: T) => string | number | null | undefined,
) {
  const deltas: number[] = [];
  for (let index = 0; index < months.length - 1; index += 1) {
    const current = months[index];
    const previous = months[index + 1];
    if (!current || !previous || !isPreviousCalendarMonth(getReportDate(current), getReportDate(previous))) {
      continue;
    }
    const delta = trendDelta(getValue(current), getValue(previous));
    if (delta !== null) {
      deltas.push(delta);
    }
  }
  return deltas;
}

function anomalyHeadline(label: string, currentDelta: number, baselineAverageAbs: number | null, baselineCount: number) {
  if (baselineAverageAbs === null || baselineAverageAbs === 0) {
    return Math.abs(currentDelta) > 0 ? `${label} 新增跳变` : `${label} 未见异常`;
  }
  return Math.abs(currentDelta) >= baselineAverageAbs * 3
    ? `${label} 高于近 ${baselineCount} 期常态`
    : `${label} 接近近 ${baselineCount} 期常态`;
}

export function buildHistoricalAnomalyDiagnostics(options: {
  trendMonths: BalanceMovementTrendMonth[];
  businessTrendMonths: BalanceBusinessMovementTrendMonth[];
  businessRows: BusinessMovementMatrixRow[];
}): HistoricalAnomalyDiagnostics {
  const { trendMonths, businessTrendMonths, businessRows } = options;
  const sampleCount = Math.max(trendMonths.length, businessTrendMonths.length);
  const baselinePairCount = Math.max(0, sampleCount - 2);
  const accountingSignals =
    baselinePairCount > 0
      ? balanceMovementBuckets
          .map((bucket): HistoricalAccountingSignal | null => {
            const deltas = buildDeltaSeries(
              trendMonths,
              (month) => month.report_date,
              (month) => trendBucket(month, bucket)?.current_balance,
            );
            const [currentDelta, ...historyDeltas] = deltas;
            if (currentDelta === undefined || historyDeltas.length === 0) {
              return null;
            }
            const baselineAverageAbs = averageAbs(historyDeltas);
            const directionReversal =
              directionOf(currentDelta) !== 0 &&
              directionOf(historyDeltas[0]) !== 0 &&
              directionOf(currentDelta) !== directionOf(historyDeltas[0]);
            const headline = anomalyHeadline(bucket, currentDelta, baselineAverageAbs, historyDeltas.length);
            if (!directionReversal && !headline.includes("高于")) {
              return null;
            }
            return {
              bucket,
              headline,
              currentDelta,
              baselineAverageAbs,
              baselineCount: historyDeltas.length,
              directionReversal,
            };
          })
          .filter((signal): signal is HistoricalAccountingSignal => signal !== null)
          .sort((left, right) => Math.abs(right.currentDelta) - Math.abs(left.currentDelta))
      : [];

  const businessSignals =
    baselinePairCount > 0
      ? businessRows
          .filter((row) => row.side === "asset" || row.side === "liability")
          .map((row): HistoricalBusinessSignal | null => {
            const deltas = buildDeltaSeries(
              businessTrendMonths,
              (month) => month.report_date,
              (month) => row.getValue(month),
            );
            const [currentDelta, ...historyDeltas] = deltas;
            if (currentDelta === undefined || historyDeltas.length === 0) {
              return null;
            }
            const baselineAverageAbs = averageAbs(historyDeltas);
            const headline = anomalyHeadline(row.label, currentDelta, baselineAverageAbs, historyDeltas.length);
            if (!headline.includes("高于") && !headline.includes("新增")) {
              return null;
            }
            return {
              label: row.label,
              currentDelta,
              baselineAverageAbs,
              baselineCount: historyDeltas.length,
            };
          })
          .filter((signal): signal is HistoricalBusinessSignal => signal !== null)
          .sort((left, right) => Math.abs(right.currentDelta) - Math.abs(left.currentDelta))
          .slice(0, 5)
      : [];

  return {
    sampleCount,
    baselinePairCount,
    headline: baselinePairCount > 0 ? "本期相对历史常态的偏离" : "历史样本不足",
    accountingSignals,
    businessSignals,
  };
}
