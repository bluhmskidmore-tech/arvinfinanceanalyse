import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { BalanceMovementRow } from "../../../api/contracts";
import { FilterBar } from "../../../components/FilterBar";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";

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

const conclusionStyle = {
  display: "grid",
  gap: 12,
  padding: 16,
  borderRadius: 8,
  border: "1px solid #b7d8c5",
  background: "#f6fbf7",
  marginBottom: 18,
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

function formatYiFixed(value: string | number | null | undefined, digits = 6) {
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
  const rowByBucket = useMemo(
    () => new Map(rows.map((row) => [row.basis_bucket, row])),
    [rows],
  );

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
        <section data-testid="balance-movement-analysis-conclusion" style={conclusionStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={{ color: "#027a48", fontSize: 12, fontWeight: 700 }}>
                总账控制核对通过
              </div>
              <strong style={{ display: "block", marginTop: 4, fontSize: 24 }}>
                {selectedDate || detailQuery.data?.result.report_date} 合计{" "}
                {formatYiFixed(summary.current_balance_total)} 亿
              </strong>
            </div>
            <div style={{ color: "#5c6b82", fontSize: 13, textAlign: "right" }}>
              控制科目 141 / 142 / 143 / 1440101；排除 144020 股权 OCI
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", color: "#26364a", fontSize: 13 }}>
            <span>AC {formatPct(rowByBucket.get("AC")?.current_balance_pct)}</span>
            <span>OCI {formatPct(rowByBucket.get("OCI")?.current_balance_pct)}</span>
            <span>TPL {formatPct(rowByBucket.get("TPL")?.current_balance_pct)}</span>
          </div>
          <div style={{ color: "#5c6b82", fontSize: 12 }}>
            本页以总账控制数为正式口径；ZQTZ 诊断差异仅用于提示明细扫描差异，不影响本页核对结论。
          </div>
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
