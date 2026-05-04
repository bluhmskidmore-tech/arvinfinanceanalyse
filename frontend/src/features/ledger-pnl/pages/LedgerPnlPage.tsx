import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { modeBadgeStyle, summaryGridStyle, tableStyle } from "../../../components/page/pageStyles";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { shellTokens } from "../../../theme/tokens";
import { FilterBar } from "../../../components/FilterBar";
import type { LedgerMoneyValue } from "../../../api/contracts";

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 10,
  marginBottom: 0,
  maxWidth: 860,
  color: designTokens.color.neutral[600],
  fontSize: 15,
  lineHeight: 1.75,
} as const;

const summaryGridStyleWithBottom = { ...summaryGridStyle, marginBottom: designTokens.space[5] } as const;

const summaryCardStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  padding: designTokens.space[4],
  background: shellTokens.colorBgSurface,
} as const;

const tableWrapStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  background: shellTokens.colorBgSurface,
  overflow: "auto",
} as const;

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  if (value?.yi) {
    return `${value.yi} 亿元`;
  }
  const yuan = Number(value?.yuan);
  return `${Number.isFinite(yuan) ? (yuan / 100_000_000).toFixed(2) : "0.00"} 亿元`;
}

export default function LedgerPnlPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const reportDateFromQuery = searchParams.get("report_date")?.trim() ?? "";
  const currencyFromQuery = searchParams.get("currency")?.trim() ?? "";
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [currency, setCurrency] = useState("ALL");

  const datesQuery = useQuery({
    queryKey: ["ledger-pnl", "dates", client.mode],
    queryFn: () => client.getLedgerPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(() => datesQuery.data?.result.dates ?? [], [datesQuery.data?.result.dates]);

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (reportDateFromQuery && reportDates.includes(reportDateFromQuery)) {
      setSelectedReportDate((current) => (current === reportDateFromQuery ? current : reportDateFromQuery));
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDateFromQuery, reportDates, selectedReportDate]);

  const effectiveCurrency = currency === "ALL" ? undefined : currency;

  const summaryQuery = useQuery({
    queryKey: ["ledger-pnl", "summary", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlSummary(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["ledger-pnl", "data", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlData(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const summary = summaryQuery.data?.result;
  const data = dataQuery.data?.result;

  const currencyOptions = useMemo(() => {
    const seen = new Set(["ALL"]);
    for (const item of summary?.by_currency ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    for (const item of data?.items ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    return Array.from(seen);
  }, [data?.items, summary?.by_currency]);

  useEffect(() => {
    if (!currencyFromQuery) {
      return;
    }
    if (!currencyOptions.includes(currencyFromQuery)) {
      return;
    }
    setCurrency((current) => (current === currencyFromQuery ? current : currencyFromQuery));
  }, [currencyFromQuery, currencyOptions]);

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    if (selectedReportDate) {
      nextParams.set("report_date", selectedReportDate);
    } else {
      nextParams.delete("report_date");
    }
    if (currency !== "ALL") {
      nextParams.set("currency", currency);
    } else {
      nextParams.delete("currency");
    }

    if (typeof window === "undefined") {
      return;
    }
    if (nextParams.toString() !== window.location.search.replace(/^\?/, "")) {
      const nextUrl = new URL(window.location.href);
      nextUrl.search = nextParams.toString();
      window.history.replaceState({}, "", nextUrl);
    }
  }, [currency, searchParams, selectedReportDate]);

  return (
    <section data-testid="ledger-pnl-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="ledger-pnl-page-title"
            style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: "-0.03em" }}
          >
            总账损益
          </h1>
          <p data-testid="ledger-pnl-page-subtitle" style={pageSubtitleStyle}>
            科目口径损益总览、币种汇总与账户明细。页面直接消费后端总账口径读模型，
            不在前端补算会计科目聚合。
          </p>
        </div>
        <span
          style={{
            ...modeBadgeStyle,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
          }}
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>报告日</span>
          <select
            aria-label="ledger-pnl-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            disabled={reportDates.length === 0}
            style={{
              minWidth: 180,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
          >
            {reportDates.length === 0 ? <option value="">暂无可选报告日</option> : null}
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>币种</span>
          <select
            aria-label="ledger-pnl-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            style={{
              minWidth: 140,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
          >
            {currencyOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <div data-testid="ledger-pnl-summary-cards" style={summaryGridStyleWithBottom}>
        {[
          ["核心损益", formatMoney(summary?.ledger_monthly_pnl_core)],
          ["全量损益", formatMoney(summary?.ledger_monthly_pnl_all)],
          ["总资产", formatMoney(summary?.ledger_total_assets)],
          ["总负债", formatMoney(summary?.ledger_total_liabilities)],
          ["净资产", formatMoney(summary?.ledger_net_assets)],
        ].map(([title, value]) => (
          <div key={title} style={summaryCardStyle}>
            <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[600] }}>{title}</div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: designTokens.color.neutral[900],
                marginTop: 10,
              }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            币种汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.by_currency ?? []).map((item) => (
                <tr key={item.currency} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                  <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            科目汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>笔数</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.by_account ?? []).map((item) => (
                <tr key={item.account_code} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                  <td style={{ padding: designTokens.space[3] }}>
                    <div>{item.account_code}</div>
                    <div style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[12] }}>
                      {item.account_name}
                    </div>
                  </td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div data-testid="ledger-pnl-detail-table" style={tableWrapStyle}>
        <div
          style={{
            padding: designTokens.space[4],
            fontWeight: 600,
            borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
          }}
        >
          科目明细
        </div>
        <table style={tableStyle}>
          <thead>
            <tr style={{ background: designTokens.color.neutral[50] }}>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目代码</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目名称</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期初</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期末</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月损益</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月日均</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>天数</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((item) => (
              <tr key={`${item.account_code}-${item.currency}`} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                <td style={{ padding: designTokens.space[3] }}>{item.account_code}</td>
                <td style={{ padding: designTokens.space[3] }}>{item.account_name}</td>
                <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.beginning_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.ending_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.monthly_pnl)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.daily_avg_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.days_in_period}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FormalResultMetaPanel
        testId="ledger-pnl-result-meta-panel"
        sections={[
          { key: "dates", title: "Ledger 报告日", meta: datesQuery.data?.result_meta },
          { key: "summary", title: "Ledger 汇总", meta: summaryQuery.data?.result_meta },
          { key: "data", title: "Ledger 明细", meta: dataQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
