import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { BalanceMovementRow, BalanceMovementTrendMonth } from "../../../api/contracts";
import AccountingBasisStackedShareChart, {
  type AccountingBasisStackedSharePoint,
} from "../../../components/charts/AccountingBasisStackedShareChart";
import { FilterBar } from "../../../components/FilterBar";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import "./BalanceMovementAnalysisPage.css";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  marginBottom: 18,
} as const;

const chipTypography = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
} as const;

const cardGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
  marginBottom: 18,
} as const;

const cardStyle = {
  display: "grid",
  gap: 6,
  padding: 16,
  borderRadius: 16,
  border: "1px solid #d7dfea",
  background: "#ffffff",
} as const;

const tableCellStyle = {
  padding: "12px 8px",
  borderBottom: "1px solid #edf1f6",
  textAlign: "right",
} as const;

const bucketLabels: Record<string, string> = {
  AC: "AC",
  OCI: "OCI",
  TPL: "TPL",
};
const bucketColors: Record<BalanceMovementRow["basis_bucket"], string> = {
  AC: "#10284a",
  OCI: "#33689a",
  TPL: "#d2a03f",
};
const balanceMovementBuckets: BalanceMovementRow["basis_bucket"][] = ["AC", "OCI", "TPL"];

function formatPct(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return `${n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function formatYiFixed(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatSignedYi(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} 亿`;
}

function trendBucket(
  month: BalanceMovementTrendMonth | undefined,
  bucket: BalanceMovementRow["basis_bucket"],
) {
  return month?.rows.find((row) => row.basis_bucket === bucket);
}

function trendDelta(
  current: string | number | null | undefined,
  previous: string | number | null | undefined,
) {
  const currentValue = Number(current);
  const previousValue = Number(previous);
  if (!Number.isFinite(currentValue) || !Number.isFinite(previousValue)) {
    return null;
  }
  return currentValue - previousValue;
}

function formatTrendMonthLabel(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year}年${monthNumber}月`;
}

function formatYiCell(value: string | number | null | undefined) {
  return formatYiFixed(value, 2);
}

function formatSignedYiCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function sumTrendRowValues(
  month: BalanceMovementTrendMonth,
  getValue: (row: BalanceMovementRow) => string | number | null | undefined,
) {
  return month.rows.reduce((total, row) => {
    const value = Number(getValue(row));
    return Number.isFinite(value) ? total + value : total;
  }, 0);
}

type BalanceMovementMatrixValueKind = "amount" | "percent";

type BalanceMovementMatrixRow = {
  key: string;
  label: string;
  valueKind: BalanceMovementMatrixValueKind;
  getValue: (month: BalanceMovementTrendMonth) => string | number | null | undefined;
};

function formatMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
) {
  if (valueKind === "percent") {
    return formatPct(value);
  }
  const formatted = formatYiCell(value);
  return formatted === "-" ? formatted : `${formatted} 亿`;
}

function formatSignedPercentPoint(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}pp`;
}

function formatSignedMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
) {
  if (valueKind === "percent") {
    return formatSignedPercentPoint(value);
  }
  const formatted = formatSignedYiCell(value);
  return formatted === "-" ? formatted : `${formatted} 亿`;
}

function compareMatrixCell(
  months: BalanceMovementTrendMonth[],
  row: BalanceMovementMatrixRow,
  baselineOffset: number,
) {
  const currentMonth = months[months.length - 1];
  const baselineMonth = months[months.length - 1 - baselineOffset];
  if (!currentMonth || !baselineMonth) {
    return "-";
  }
  return formatSignedMatrixValue(
    trendDelta(row.getValue(currentMonth), row.getValue(baselineMonth)),
    row.valueKind,
  );
}

function compareMatrixCellToFirst(
  months: BalanceMovementTrendMonth[],
  row: BalanceMovementMatrixRow,
) {
  const currentMonth = months[months.length - 1];
  const firstMonth = months[0];
  if (!currentMonth || !firstMonth || currentMonth.report_date === firstMonth.report_date) {
    return "-";
  }
  return formatSignedMatrixValue(
    trendDelta(row.getValue(currentMonth), row.getValue(firstMonth)),
    row.valueKind,
  );
}

const balanceCategoryMatrixRows: BalanceMovementMatrixRow[] = balanceMovementBuckets.flatMap(
  (bucket) => [
    {
      key: `${bucket}-current-balance`,
      label: `${bucket}期末余额`,
      valueKind: "amount" as const,
      getValue: (month: BalanceMovementTrendMonth) => trendBucket(month, bucket)?.current_balance,
    },
    {
      key: `${bucket}-current-share`,
      label: `${bucket}期末占比`,
      valueKind: "percent" as const,
      getValue: (month: BalanceMovementTrendMonth) =>
        trendBucket(month, bucket)?.current_balance_pct,
    },
    {
      key: `${bucket}-balance-change`,
      label: `${bucket}余额变动`,
      valueKind: "amount" as const,
      getValue: (month: BalanceMovementTrendMonth) => trendBucket(month, bucket)?.balance_change,
    },
    {
      key: `${bucket}-change-contribution`,
      label: `${bucket}变动贡献`,
      valueKind: "percent" as const,
      getValue: (month: BalanceMovementTrendMonth) =>
        trendBucket(month, bucket)?.contribution_pct,
    },
  ],
);

const balanceProjectMatrixRows: BalanceMovementMatrixRow[] = [
  {
    key: "current-balance-total",
    label: "期末余额合计",
    valueKind: "amount",
    getValue: (month) => month.current_balance_total,
  },
  {
    key: "balance-change-total",
    label: "余额变动合计",
    valueKind: "amount",
    getValue: (month) => month.balance_change_total,
  },
  {
    key: "gl-total",
    label: "总账控制余额",
    valueKind: "amount",
    getValue: (month) => sumTrendRowValues(month, (row) => row.gl_amount),
  },
  {
    key: "zqtz-total",
    label: "ZQTZ辅助余额",
    valueKind: "amount",
    getValue: (month) => sumTrendRowValues(month, (row) => row.zqtz_amount),
  },
  {
    key: "diagnostic-diff-total",
    label: "ZQTZ诊断差异",
    valueKind: "amount",
    getValue: (month) => sumTrendRowValues(month, (row) => row.reconciliation_diff),
  },
];

function formatTrendAxisMonth(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year.slice(2)}-${String(monthNumber).padStart(2, "0")}`;
}

function toSharePoint(month: BalanceMovementTrendMonth): AccountingBasisStackedSharePoint {
  const total = Number(month.current_balance_total);
  const point: AccountingBasisStackedSharePoint = {
    monthLabel: formatTrendAxisMonth(month.report_month),
    AC: 0,
    OCI: 0,
    TPL: 0,
    totalValueYi: Number.isFinite(total) ? total / 100000000 : undefined,
  };
  for (const bucket of balanceMovementBuckets) {
    const row = trendBucket(month, bucket);
    const value = Number(row?.current_balance);
    const share = total > 0 && Number.isFinite(value) ? (value / total) * 100 : Number(row?.current_balance_pct);
    point[bucket] = Number.isFinite(share) ? share : 0;
    if (bucket === "AC") point.acValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "OCI") point.ociValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "TPL") point.tplValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
  }
  return point;
}

function formatSignedPoint(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}pp`;
}

function numericValue(value: string | number | null | undefined) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function isPreviousCalendarMonth(currentReportDate: string, previousReportDate: string) {
  const currentParts = currentReportDate.split("-").map(Number);
  const previousParts = previousReportDate.split("-").map(Number);
  const [currentYear, currentMonth] = currentParts;
  const [previousYear, previousMonth] = previousParts;
  if (
    !Number.isInteger(currentYear) ||
    !Number.isInteger(currentMonth) ||
    !Number.isInteger(previousYear) ||
    !Number.isInteger(previousMonth)
  ) {
    return false;
  }
  return previousYear * 12 + previousMonth === currentYear * 12 + currentMonth - 1;
}

function statusTone(status: BalanceMovementRow["reconciliation_status"]) {
  return status === "matched" ? "#027a48" : "#b54708";
}

type BalanceMovementDriver = {
  bucket: BalanceMovementRow["basis_bucket"];
  balanceChange: number;
  balanceChangeYi: number;
  contributionPct: number;
  currentBalancePct: number;
  previousBalancePct: number;
  shareDelta: number;
};

function toMovementDriver(row: BalanceMovementRow): BalanceMovementDriver {
  const balanceChange = numericValue(row.balance_change);
  const currentBalancePct = numericValue(row.current_balance_pct);
  const previousBalancePct = numericValue(row.previous_balance_pct);
  return {
    bucket: row.basis_bucket,
    balanceChange,
    balanceChangeYi: balanceChange / 100000000,
    contributionPct: numericValue(row.contribution_pct),
    currentBalancePct,
    previousBalancePct,
    shareDelta: currentBalancePct - previousBalancePct,
  };
}

function formatSignedYiNumber(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function movementDirection(value: string | number | null | undefined) {
  const n = numericValue(value);
  if (n > 0) return "增加";
  if (n < 0) return "减少";
  return "持平";
}

function dataIndexFromTooltip(params: unknown) {
  const first = Array.isArray(params) ? params[0] : params;
  if (!first || typeof first !== "object" || !("dataIndex" in first)) {
    return 0;
  }
  const dataIndex = Number((first as { dataIndex?: unknown }).dataIndex);
  return Number.isFinite(dataIndex) ? dataIndex : 0;
}

function buildDriverChartOption(drivers: BalanceMovementDriver[]): EChartsOption {
  return {
    grid: { left: 44, right: 72, top: 20, bottom: 34 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const driver = drivers[dataIndexFromTooltip(params)];
        if (!driver) return "";
        return [
          driver.bucket,
          `变动：${formatSignedYiNumber(driver.balanceChangeYi)} 亿`,
          `贡献：${formatPct(driver.contributionPct)}`,
          `占比变化：${formatSignedPoint(driver.shareDelta)}`,
        ].join("<br/>");
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` },
      splitLine: { lineStyle: { color: "#edf1f6" } },
    },
    yAxis: {
      type: "category",
      data: drivers.map((driver) => driver.bucket),
      axisTick: { show: false },
      axisLabel: { color: "#26364a", fontWeight: 700 },
    },
    series: [
      {
        name: "余额变动",
        type: "bar",
        barWidth: 28,
        data: drivers.map((driver) => driver.balanceChangeYi),
        itemStyle: {
          color: (params: { dataIndex: number }) =>
            bucketColors[drivers[params.dataIndex]?.bucket ?? "AC"],
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          position: "right",
          color: "#26364a",
          fontWeight: 700,
          formatter: (params: { dataIndex: number }) => {
            const driver = drivers[params.dataIndex];
            return driver ? `${formatSignedYiNumber(driver.balanceChangeYi)} 亿` : "";
          },
        },
      },
    ],
  };
}

export default function BalanceMovementAnalysisPage() {
  const client = useApiClient();
  const [selectedDate, setSelectedDate] = useState("");
  const [currencyBasis, setCurrencyBasis] = useState("CNX");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-movement-analysis", "dates", client.mode, currencyBasis],
    queryFn: () => client.getBalanceMovementDates(currencyBasis),
    retry: false,
  });
  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );
  const dateStatus = datesQuery.isError
    ? {
        tone: "error" as const,
        title: "报告日期加载失败",
        detail: "请确认后端 7888 服务与余额变动读模型可用。",
      }
    : !datesQuery.isLoading && reportDates.length === 0
      ? {
          tone: "empty" as const,
          title: "暂无已物化报告日期",
          detail: `${currencyBasis} 口径下没有可选日期；请先物化余额变动读模型。`,
        }
      : null;

  useEffect(() => {
    if (!selectedDate && reportDates.length) {
      setSelectedDate(reportDates[0] ?? "");
    }
  }, [reportDates, selectedDate]);

  const detailQuery = useQuery({
    queryKey: ["balance-movement-analysis", "detail", client.mode, selectedDate, currencyBasis],
    queryFn: () =>
      client.getBalanceMovementAnalysis({
        reportDate: selectedDate,
        currencyBasis,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const rows = useMemo(
    () => detailQuery.data?.result.rows ?? [],
    [detailQuery.data?.result.rows],
  );
  const summary = detailQuery.data?.result.summary;
  const trendMonths = useMemo(
    () => detailQuery.data?.result.trend_months ?? [],
    [detailQuery.data?.result.trend_months],
  );
  const reportMatrixMonths = useMemo(() => [...trendMonths].reverse(), [trendMonths]);
  const balanceStructureTrend = useMemo(
    () => reportMatrixMonths.map(toSharePoint),
    [reportMatrixMonths],
  );
  const balanceStructureInsight = useMemo(() => {
    const first = balanceStructureTrend[0];
    const latest = balanceStructureTrend[balanceStructureTrend.length - 1];
    if (!first || !latest || first.monthLabel === latest.monthLabel) {
      return null;
    }
    return `AC占比较首月 ${formatSignedPoint(latest.AC - first.AC)}，OCI ${formatSignedPoint(
      latest.OCI - first.OCI,
    )}，TPL ${formatSignedPoint(latest.TPL - first.TPL)}。`;
  }, [balanceStructureTrend]);
  const currentTrendMonth = trendMonths[0];
  const previousTrendMonth = trendMonths[1];
  const rowByBucket = useMemo(
    () => new Map(rows.map((row) => [row.basis_bucket, row])),
    [rows],
  );
  const movementDrivers = useMemo(
    () =>
      rows
        .map(toMovementDriver)
        .sort((left, right) => Math.abs(right.balanceChange) - Math.abs(left.balanceChange)),
    [rows],
  );
  const movementDriverByBucket = useMemo(
    () => new Map(movementDrivers.map((driver) => [driver.bucket, driver])),
    [movementDrivers],
  );
  const topMovementDriver = movementDrivers[0];
  const maxShareShiftDriver = useMemo(
    () =>
      [...movementDrivers].sort(
        (left, right) => Math.abs(right.shareDelta) - Math.abs(left.shareDelta),
      )[0],
    [movementDrivers],
  );
  const driverChartOption = useMemo(
    () => buildDriverChartOption(movementDrivers),
    [movementDrivers],
  );
  const structureStatus =
    maxShareShiftDriver && Math.abs(maxShareShiftDriver.shareDelta) <= 1
      ? "结构整体稳定"
      : "结构变化明显";
  const trendComparison = useMemo(() => {
    if (!currentTrendMonth || !previousTrendMonth) {
      return null;
    }
    if (
      !isPreviousCalendarMonth(
        currentTrendMonth.report_date,
        previousTrendMonth.report_date,
      )
    ) {
      return null;
    }
    const totalDelta = trendDelta(
      currentTrendMonth.current_balance_total,
      previousTrendMonth.current_balance_total,
    );
    if (totalDelta === null) {
      return null;
    }
    const drivers = balanceMovementBuckets
      .map((bucket) => {
        const delta = trendDelta(
          trendBucket(currentTrendMonth, bucket)?.current_balance,
          trendBucket(previousTrendMonth, bucket)?.current_balance,
        );
        return delta === null ? null : { bucket, delta };
      })
      .filter((driver): driver is { bucket: BalanceMovementRow["basis_bucket"]; delta: number } =>
        driver !== null,
      )
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
    return {
      drivers,
      previousReportDate: previousTrendMonth.report_date,
      totalDelta,
    };
  }, [currentTrendMonth, previousTrendMonth]);

  async function handleRefresh() {
    if (!selectedDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      const payload = await client.refreshBalanceMovementAnalysis({
        reportDate: selectedDate,
        currencyBasis,
      });
      setRefreshMessage(`${payload.status}: ${payload.row_count} 行`);
      await detailQuery.refetch();
      await datesQuery.refetch();
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section data-testid="balance-movement-analysis-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="balance-movement-analysis-title"
            style={{ margin: 0, fontSize: 28, fontWeight: 700 }}
          >
            余额变动分析
          </h1>
          <p
            data-testid="balance-movement-analysis-subtitle"
            style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 14 }}
          >
            AC / OCI / TPL 月末余额、月度变动与总账控制数对账。
          </p>
        </div>
        <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
          <span
            style={{
              ...chipTypography,
              background: designTokens.color.primary[50],
              color: designTokens.color.primary[600],
            }}
          >
            正式总账控制
          </span>
          <span
            style={{
              ...chipTypography,
              background:
                client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
              color:
                client.mode === "real"
                  ? displayTokens.apiMode.realForeground
                  : displayTokens.apiMode.mockForeground,
            }}
          >
            {client.mode === "real" ? "正式接口" : "本地模拟"}
          </span>
        </div>
      </div>

      <FilterBar style={{ marginBottom: 16 }}>
        <label style={{ display: "grid", gap: 6 }}>
          报告日期
          <select
            aria-label="余额变动分析-报告日期"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          >
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          控制币种
          <select
            aria-label="余额变动分析-控制币种"
            value={currencyBasis}
            onChange={(event) => {
              setCurrencyBasis(event.target.value);
              setSelectedDate("");
            }}
          >
            <option value="CNX">CNX</option>
            <option value="CNY">CNY</option>
          </select>
        </label>
        <button
          type="button"
          data-testid="balance-movement-analysis-refresh"
          onClick={() => void handleRefresh()}
          disabled={!selectedDate || isRefreshing}
        >
          {isRefreshing ? "刷新中..." : "刷新余额变动"}
        </button>
        {refreshMessage ? (
          <span data-testid="balance-movement-analysis-refresh-message">{refreshMessage}</span>
        ) : null}
      </FilterBar>
      {dateStatus ? (
        <div
          data-testid="balance-movement-analysis-date-status"
          className={`balance-movement-date-status balance-movement-date-status--${dateStatus.tone}`}
          role={dateStatus.tone === "error" ? "alert" : "status"}
        >
          <strong>{dateStatus.title}</strong>
          <span>{dateStatus.detail}</span>
        </div>
      ) : null}

      {summary ? (
        <section
          data-testid="balance-movement-analysis-conclusion"
          className="balance-movement-conclusion"
        >
          <div className="balance-movement-conclusion__top">
            <div>
              <div className="balance-movement-conclusion__status">
                总账控制核对通过
              </div>
              <strong className="balance-movement-conclusion__headline">
                {selectedDate || detailQuery.data?.result.report_date} 合计{" "}
                {formatYiFixed(summary.current_balance_total)} 亿
              </strong>
            </div>
            <div className="balance-movement-conclusion__controls">
              控制科目 141 / 142 / 143 / 1440101；排除 144020 股权 OCI
            </div>
          </div>
          <div className="balance-movement-conclusion__shares">
            <span>AC {formatPct(rowByBucket.get("AC")?.current_balance_pct)}</span>
            <span>OCI {formatPct(rowByBucket.get("OCI")?.current_balance_pct)}</span>
            <span>TPL {formatPct(rowByBucket.get("TPL")?.current_balance_pct)}</span>
          </div>
          <div className="balance-movement-conclusion__note">
            本页以 CNX 总账控制数为正式口径；ZQTZ 诊断同步读取 CNX 余额表，不再回退到 CNY 辅助口径。
          </div>
          <div
            data-testid="balance-movement-analysis-diagnostic-reason"
            className="balance-movement-conclusion__note"
          >
            口径差异原因：昨晚定位的是 ZQTZ 诊断应使用 CNX 表；若误读 CNY
            辅助口径，会把综合本位币核对数和人民币辅助数相减，形成 AC / OCI / TPL 的假差异。
          </div>
          {trendComparison ? (
            <div
              data-testid="balance-movement-analysis-trend-conclusion"
              className="balance-movement-conclusion__trend"
            >
              较 {trendComparison.previousReportDate} {formatSignedYi(trendComparison.totalDelta)}
              ，主要来自{" "}
              {trendComparison.drivers
                .map((driver) => `${driver.bucket} ${formatSignedYi(driver.delta)}`)
                .join("、")}。
            </div>
          ) : null}
        </section>
      ) : null}

      {summary ? (
        <div data-testid="balance-movement-analysis-summary" style={cardGridStyle}>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>期末余额</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.current_balance_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>期初余额</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.previous_balance_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>余额变动</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.balance_change_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>ZQTZ诊断差异</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.reconciliation_diff_total)} 亿</strong>
          </div>
        </div>
      ) : null}

      {summary && topMovementDriver && maxShareShiftDriver ? (
        <section
          data-testid="balance-movement-analysis-business-summary"
          className="balance-movement-business-summary"
        >
          <div className="balance-movement-business-summary__headline">
            <span>分析结论</span>
            <strong>
              本月余额{movementDirection(summary.balance_change_total)}{" "}
              {formatYiFixed(Math.abs(numericValue(summary.balance_change_total)))} 亿，最大驱动是{" "}
              {topMovementDriver.bucket}
            </strong>
            <p>
              {structureStatus}，最大占比变化为 {maxShareShiftDriver.bucket}{" "}
              {formatSignedPoint(maxShareShiftDriver.shareDelta)}
            </p>
          </div>

          <div className="balance-movement-business-summary__facts">
            <div>
              <span>最大驱动</span>
              <p>
                {topMovementDriver.bucket} 增量最大：
                {formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿，贡献{" "}
                {formatPct(topMovementDriver.contributionPct)}
              </p>
            </div>
            <div>
              <span>压舱石</span>
              <p>
                AC 压舱石占比{" "}
                {formatPct(rowByBucket.get("AC")?.current_balance_pct)}，较期初{" "}
                {formatSignedPoint(movementDriverByBucket.get("AC")?.shareDelta ?? 0)}
              </p>
            </div>
            <div>
              <span>配置变化</span>
              <p>
                OCI 配置占比{" "}
                {formatPct(rowByBucket.get("OCI")?.current_balance_pct)}，较期初{" "}
                {formatSignedPoint(movementDriverByBucket.get("OCI")?.shareDelta ?? 0)}
              </p>
            </div>
          </div>

          <div className="balance-movement-business-summary__body">
            <div
              data-testid="balance-movement-analysis-driver-chart"
              className="balance-movement-driver-chart"
            >
              <h2>余额变动驱动</h2>
              <ReactECharts
                option={driverChartOption}
                style={{ height: 240, width: "100%" }}
                notMerge
                lazyUpdate
              />
            </div>

            <div
              data-testid="balance-movement-analysis-driver-ranking"
              className="balance-movement-driver-ranking"
            >
              <h2>贡献排序</h2>
              {movementDrivers.map((driver, index) => (
                <div key={driver.bucket} className="balance-movement-driver-ranking__row">
                  <span>{index + 1}</span>
                  <strong>
                    {driver.bucket} {formatSignedYiNumber(driver.balanceChangeYi)} 亿{" "}
                    {formatPct(driver.contributionPct)}
                  </strong>
                </div>
              ))}
            </div>

            <div
              data-testid="balance-movement-analysis-structure-shift"
              className="balance-movement-structure-shift"
            >
              <h2>期初到期末结构变化</h2>
              {balanceMovementBuckets.map((bucket) => {
                const driver = movementDrivers.find((item) => item.bucket === bucket);
                if (!driver) return null;
                return (
                  <div key={bucket} className="balance-movement-structure-shift__row">
                    <div>
                      <strong>{bucket}</strong>
                      <span>
                        期初 {formatPct(driver.previousBalancePct)} 期末{" "}
                        {formatPct(driver.currentBalancePct)}
                      </span>
                    </div>
                    <div className="balance-movement-structure-shift__track">
                      <span
                        className="balance-movement-structure-shift__previous"
                        style={{
                          width: `${Math.min(Math.max(driver.previousBalancePct, 1), 100)}%`,
                        }}
                      />
                      <span
                        className="balance-movement-structure-shift__current"
                        style={{
                          width: `${Math.min(Math.max(driver.currentBalancePct, 1), 100)}%`,
                        }}
                      />
                    </div>
                    <em>{formatSignedPoint(driver.shareDelta)}</em>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      {trendMonths.length > 0 ? (
        <AsyncSection
          title="月度余额分析矩阵"
          isLoading={detailQuery.isLoading}
          isError={detailQuery.isError}
          isEmpty={trendMonths.length === 0}
          onRetry={() => void detailQuery.refetch()}
        >
          <div className="balance-movement-matrix-scroll">
            <table
              data-testid="balance-movement-analysis-trend-table"
              className="balance-movement-report-matrix balance-movement-report-matrix--workbook"
            >
              <thead>
                <tr>
                  <th>分类</th>
                  {reportMatrixMonths.map((month) => (
                    <th key={month.report_date}>{formatTrendMonthLabel(month.report_month)}</th>
                  ))}
                  <th>比上月</th>
                  <th>比年初</th>
                </tr>
              </thead>
              <tbody>
                {balanceCategoryMatrixRows.map((row) => (
                  <tr key={row.key}>
                    <td>{row.label}</td>
                    {reportMatrixMonths.map((month) => (
                      <td key={`${row.key}-${month.report_date}`}>
                        {formatMatrixValue(row.getValue(month), row.valueKind)}
                      </td>
                    ))}
                    <td>{compareMatrixCell(reportMatrixMonths, row, 1)}</td>
                    <td>{compareMatrixCellToFirst(reportMatrixMonths, row)}</td>
                  </tr>
                ))}
                <tr className="balance-movement-report-matrix__gap">
                  <td colSpan={reportMatrixMonths.length + 3} />
                </tr>
                <tr className="balance-movement-report-matrix__section">
                  <th>项目</th>
                  {reportMatrixMonths.map((month) => (
                    <th key={`project-${month.report_date}`}>
                      {formatTrendMonthLabel(month.report_month)}
                    </th>
                  ))}
                  <th>比上月</th>
                  <th>比年初</th>
                </tr>
                {balanceProjectMatrixRows.map((row) => {
                  return (
                    <tr key={row.key}>
                      <td>{row.label}</td>
                      {reportMatrixMonths.map((month) => (
                        <td key={`${row.key}-${month.report_date}`}>
                          {formatMatrixValue(row.getValue(month), row.valueKind)}
                        </td>
                      ))}
                      <td>{compareMatrixCell(reportMatrixMonths, row, 1)}</td>
                      <td>{compareMatrixCellToFirst(reportMatrixMonths, row)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div
            className="balance-movement-structure-chart"
            data-testid="balance-movement-analysis-structure-chart"
          >
            <AccountingBasisStackedShareChart
              rows={balanceStructureTrend}
              title="金融投资账户结构演变：余额口径"
            />
            {balanceStructureInsight ? (
              <div
                className="balance-movement-structure-chart__insight"
                data-testid="balance-movement-analysis-structure-insight"
              >
                {balanceStructureInsight}
              </div>
            ) : null}
          </div>
        </AsyncSection>
      ) : null}

      <AsyncSection
        title="明细 / 对账：AC / OCI / TPL 余额变动"
        isLoading={detailQuery.isLoading}
        isError={detailQuery.isError}
        isEmpty={!detailQuery.isLoading && !detailQuery.isError && rows.length === 0}
        onRetry={() => void detailQuery.refetch()}
      >
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="balance-movement-analysis-table"
            style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
          >
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea" }}>
                <th style={{ padding: "12px 8px" }}>分类</th>
                <th style={tableCellStyle}>期初余额(亿)</th>
                <th style={tableCellStyle}>期初占比</th>
                <th style={tableCellStyle}>期末余额(亿)</th>
                <th style={tableCellStyle}>期末占比</th>
                <th style={tableCellStyle}>变动(亿)</th>
                <th style={tableCellStyle}>变动率</th>
                <th style={tableCellStyle}>变动贡献</th>
                <th style={tableCellStyle}>ZQTZ辅助(亿)</th>
                <th style={tableCellStyle}>ZQTZ诊断差异(亿)</th>
                <th style={tableCellStyle}>状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.basis_bucket}>
                  <td style={{ ...tableCellStyle, textAlign: "left", fontWeight: 700 }}>
                    {bucketLabels[row.basis_bucket] ?? row.basis_bucket}
                  </td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.previous_balance)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.previous_balance_pct)}</td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.current_balance)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.current_balance_pct)}</td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.balance_change)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.change_pct)}</td>
                  <td style={tableCellStyle}>{formatPct(row.contribution_pct)}</td>
                  <td style={tableCellStyle}>{formatBalanceAmountToYiFromYuan(row.zqtz_amount)}</td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.reconciliation_diff)}
                  </td>
                  <td style={{ ...tableCellStyle, color: statusTone(row.reconciliation_status) }}>
                    {row.reconciliation_status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncSection>

      {detailQuery.data?.result.accounting_controls ? (
        <div
          data-testid="balance-movement-analysis-controls"
          style={{ marginTop: 14, color: "#5c6b82", fontSize: 12 }}
        >
          控制科目：{detailQuery.data.result.accounting_controls.join(", ")}；排除：
          {detailQuery.data.result.excluded_controls.join(", ")}
        </div>
      ) : null}
    </section>
  );
}
