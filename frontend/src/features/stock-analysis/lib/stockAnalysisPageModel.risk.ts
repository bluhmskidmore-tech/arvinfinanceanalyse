// Risk-exit rows for the stock-analysis page model.
import type { LivermoreSignalConfluencePayload, LivermoreStrategyPayload } from "../../../api/contracts";
import type { StockRiskDistanceBucket, StockRiskExitRow } from "./stockAnalysisPageModel.types";
import { formatNumber } from "./stockAnalysisPageModel.format";
import { localizeStockBackendText } from "./stockAnalysisPageModel.localize";
import { normalizeEvidence } from "./stockAnalysisPageModel.shared";

function bucketExitDistance(params: {
  status: "triggered" | "watch";
  latest: number | null;
  exit: number | null;
}): { distanceToExitPct: string; exitDistanceBucket: StockRiskDistanceBucket } {
  const { status, latest, exit } = params;
  if (latest == null || exit == null || !Number.isFinite(latest) || !Number.isFinite(exit)) {
    return { distanceToExitPct: "待补", exitDistanceBucket: "待补" };
  }
  if (exit === 0) {
    return { distanceToExitPct: "待补", exitDistanceBucket: "待补" };
  }
  const pctRaw = ((latest - exit) / exit) * 100;
  const pctLabel = `${pctRaw >= 0 ? "+" : ""}${pctRaw.toFixed(2)}%`;
  if (status === "triggered") {
    return {
      distanceToExitPct: pctLabel,
      exitDistanceBucket: "triggered",
    };
  }
  const pct = pctRaw;
  const bucket: StockRiskDistanceBucket =
    pct <= 3 ? "0-3%" : pct <= 6 ? "3-6%" : ">6%";
  return { distanceToExitPct: pctLabel, exitDistanceBucket: bucket };
}

function localizeRiskExitReason(reason: string | null | undefined): string {
  const value = reason?.trim();
  if (!value) return "原因待补";
  const lower = value.toLowerCase();
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    lower.includes("external vendor") ||
    lower.includes("vendor ")
  ) {
    return "风险退出证据待确认";
  }
  const labels: Record<string, string> = {
    "2d_below_ema10": "连续 2 日收盘低于 10 日均线",
    "2d_below_ema10_with_volume": "连续 2 日收盘低于 10 日均线且放量",
  };
  return labels[normalized] ?? localizeStockBackendText(value, "risk_exit");
}

export function buildRiskExitRows(
  payload: LivermoreStrategyPayload,
  confluence?: LivermoreSignalConfluencePayload | null,
): StockRiskExitRow[] {
  const rows: StockRiskExitRow[] = [];
  const seen = new Set<string>();

  for (const item of payload.risk_exit?.items ?? []) {
    const key = `${item.stock_code}:triggered`;
    seen.add(key);
    const exit = item.latest_ema10;
    const latest = item.latest_close;
    const parsedExit = exit;
    const parsedLatest = latest;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status: "triggered",
      latest: parsedLatest,
      exit: parsedExit,
    });
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status: "triggered",
      latestClose: formatNumber(parsedLatest),
      exitWatchPrice: formatNumber(parsedExit),
      reason: `触发复核：${localizeRiskExitReason(item.reason)}`,
      distanceToExitPct,
      exitDistanceBucket,
      entryCostAvailable: item.entry_cost_available ?? item.entry_cost != null,
    });
  }

  for (const item of payload.risk_exit?.watch_items ?? []) {
    const status = item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const latest = item.latest_close;
    const exit =
      status === "triggered"
        ? (item.exit_watch_price ?? item.latest_ema10)
        : item.exit_watch_price;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status,
      latest,
      exit: exit ?? null,
    });
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status,
      latestClose: formatNumber(latest),
      exitWatchPrice: formatNumber(exit ?? undefined),
      reason: status === "triggered" ? "触发复核：跌破退出观察价" : "观察中：接近退出观察价",
      distanceToExitPct,
      exitDistanceBucket,
      entryCostAvailable: item.entry_cost_available ?? item.entry_cost != null,
    });
  }

  for (const item of confluence?.exit_observations ?? []) {
    if (!item.stock_code) {
      continue;
    }
    const status = item.action === "exit_triggered" || item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const latest = item.current_price;
    const exit = item.exit_watch_price ?? null;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status,
      latest: latest ?? null,
      exit,
    });
    const evidenceReason = normalizeEvidence(item.evidence)[0];
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name ?? item.stock_code,
      status,
      latestClose: formatNumber(latest),
      exitWatchPrice: formatNumber(exit ?? undefined),
      reason:
        (evidenceReason ? localizeRiskExitReason(evidenceReason) : null) ??
        (status === "triggered" ? "触发复核：联动观察命中" : "观察中：联动观察"),
      distanceToExitPct,
      exitDistanceBucket,
      // Signal-confluence exit observations carry no entry-cost field; there is
      // no basis to disclose it as missing, so the marker stays hidden.
      entryCostAvailable: true,
    });
  }

  return rows;
}
