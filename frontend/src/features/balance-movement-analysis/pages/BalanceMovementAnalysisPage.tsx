import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { BalanceMovementRow, BalanceMovementTrendMonth } from "../../../api/contracts";
import { FilterBar } from "../../../components/FilterBar";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import "./BalanceMovementAnalysisPage.css";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: "1px solid #d7dfea",
  background: "#fbfcfe",
  marginBottom: 18,
} as const;

const badgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
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

  useEffect(() => {
    if (!selectedDate && datesQuery.data?.result.report_dates.length) {
      setSelectedDate(datesQuery.data.result.report_dates[0] ?? "");
    }
  }, [datesQuery.data, selectedDate]);

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
  const trendMonths = detailQuery.data?.result.trend_months ?? [];
  const currentTrendMonth = trendMonths[0];
  const previousTrendMonth = trendMonths[1];
  const rowByBucket = useMemo(
    () => new Map(rows.map((row) => [row.basis_bucket, row])),
    [rows],
  );
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
            style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}
          >
            AC / OCI / TPL 月末余额、月度变动与总账控制数对账。
          </p>
        </div>
        <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
          <span style={badgeStyle}>正式总账控制</span>
          <span style={badgeStyle}>{client.mode === "real" ? "正式接口" : "本地模拟"}</span>
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
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
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

      <AsyncSection
        title="AC / OCI / TPL 余额变动"
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

      {trendMonths.length > 0 ? (
        <AsyncSection
          title="最近6个可用月度趋势"
          isLoading={detailQuery.isLoading}
          isError={detailQuery.isError}
          isEmpty={trendMonths.length === 0}
          onRetry={() => void detailQuery.refetch()}
        >
          <div className="balance-movement-table-scroll">
            <table
              data-testid="balance-movement-analysis-trend-table"
              className="balance-movement-trend-table"
            >
              <thead>
                <tr>
                  <th>月份</th>
                  <th>总余额变动</th>
                  <th>AC余额</th>
                  <th>AC占比</th>
                  <th>OCI余额</th>
                  <th>OCI占比</th>
                  <th>TPL余额</th>
                  <th>TPL占比</th>
                </tr>
              </thead>
              <tbody>
                {trendMonths.map((month) => {
                  const ac = trendBucket(month, "AC");
                  const oci = trendBucket(month, "OCI");
                  const tpl = trendBucket(month, "TPL");
                  return (
                    <tr key={month.report_date}>
                      <td>{month.report_month}</td>
                      <td>{formatSignedYi(month.balance_change_total)}</td>
                      <td>{formatBalanceAmountToYiFromYuan(ac?.current_balance)}</td>
                      <td>{formatPct(ac?.current_balance_pct)}</td>
                      <td>{formatBalanceAmountToYiFromYuan(oci?.current_balance)}</td>
                      <td>{formatPct(oci?.current_balance_pct)}</td>
                      <td>{formatBalanceAmountToYiFromYuan(tpl?.current_balance)}</td>
                      <td>{formatPct(tpl?.current_balance_pct)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncSection>
      ) : null}

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
