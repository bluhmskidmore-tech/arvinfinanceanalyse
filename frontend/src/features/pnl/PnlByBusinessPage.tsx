import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type { PnlByBusinessYtdItem } from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { SectionLead } from "../../components/page/SectionLead";
import {
  summaryGridStyle,
  tableShellStyle,
  tableStyle,
  tdStyle,
  thStyle,
} from "../../components/page/pageStyles";
import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";

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

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "#ffffff",
  color: designTokens.color.neutral[900],
} as const;

function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function formatYuanAsYi(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${(value / 100_000_000).toFixed(2)} 亿元`;
}

function formatAmount(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatRatioPct(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function toneFromSigned(raw: string | number | null | undefined): "default" | "positive" | "negative" {
  const value = numeric(raw);
  if (value === null || value === 0) {
    return "default";
  }
  return value > 0 ? "positive" : "negative";
}

function BusinessRowsTable({ rows }: { rows: PnlByBusinessYtdItem[] }) {
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>利息收入</th>
            <th style={thStyle}>公允价值变动</th>
            <th style={thStyle}>资本利得</th>
            <th style={thStyle}>合计损益</th>
            <th style={thStyle}>占比</th>
            <th style={thStyle}>资产数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.business_type}>
              <td style={tdStyle}>{row.business_type}</td>
              <td style={tdStyle}>{formatAmount(row.interest_income)}</td>
              <td style={tdStyle}>{formatAmount(row.fair_value_change)}</td>
              <td style={tdStyle}>{formatAmount(row.capital_gain)}</td>
              <td style={tdStyle}>{formatAmount(row.total_pnl)}</td>
              <td style={tdStyle}>{formatRatioPct(row.proportion)}</td>
              <td style={tdStyle}>{row.assets_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PnlByBusinessPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates("formal"),
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.formal_fi_report_dates ?? datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.formal_fi_report_dates, datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDates, selectedReportDate]);

  const selectedYear = selectedReportDate ? Number(selectedReportDate.slice(0, 4)) : new Date().getFullYear();
  const businessQuery = useQuery({
    queryKey: ["pnl-by-business", "ytd", client.mode, selectedYear],
    enabled: Boolean(selectedReportDate && selectedYear),
    queryFn: () => client.getPnlByBusinessYtd(selectedYear),
    retry: false,
  });

  const result = businessQuery.data?.result;
  const rows = result?.items ?? [];
  const topRow = rows[0];
  const assetCount = rows.reduce((total, row) => total + row.assets_count, 0);

  const loading = datesQuery.isLoading || businessQuery.isLoading;
  const error = datesQuery.isError || businessQuery.isError;
  const empty = !loading && !error && (!selectedReportDate || rows.length === 0);

  return (
    <main data-testid="pnl-by-business-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1 style={{ margin: 0, color: designTokens.color.primary[900] }}>业务种类损益</h1>
          <p style={pageSubtitleStyle}>
            按年度累计口径汇总业务种类损益，拆分利息收入、公允价值变动和资本利得。
          </p>
        </div>
      </div>

      <FilterBar style={{ marginBottom: 18 }}>
        <label style={{ display: "grid", gap: 6, color: designTokens.color.neutral[700], fontSize: 13 }}>
          报表日
          <select
            aria-label="pnl-by-business-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
          >
            {reportDates.map((date) => (
              <option key={date} value={date}>
                {date}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <AsyncSection
        isLoading={loading}
        isError={error}
        isEmpty={empty}
        loadingTitle="正在加载业务种类损益"
        errorTitle="业务种类损益加载失败"
        emptyTitle="当前报表日没有可追溯的业务种类损益"
        minHeight={220}
      >
        <section style={{ display: "grid", gap: 18 }}>
          <div style={summaryGridStyle} data-testid="pnl-by-business-summary-cards">
            <KpiCard
              label="年度累计损益"
              value={formatYuanAsYi(result?.total_pnl)}
              detail={result?.period_label ?? `${selectedYear} 年累计`}
              tone={toneFromSigned(result?.total_pnl)}
            />
            <KpiCard
              label="业务种类"
              value={`${rows.length}`}
              detail={`${assetCount} 个资产代码`}
            />
            <KpiCard
              label="最大损益业务"
              value={topRow?.business_type ?? "-"}
              detail={topRow ? formatYuanAsYi(topRow.total_pnl) : "无明细"}
              valueVariant="text"
              tone={toneFromSigned(topRow?.total_pnl)}
            />
            <KpiCard
              label="最大占比"
              value={formatRatioPct(topRow?.proportion)}
              detail={topRow?.business_type ?? "无明细"}
            />
          </div>

          {businessQuery.data ? (
            <FormalResultMetaPanel
              testId="pnl-by-business-result-meta-panel"
              sections={[
                { key: "by-business-ytd", title: "业务种类损益", meta: businessQuery.data.result_meta },
              ]}
            />
          ) : null}

          <SectionLead
            eyebrow="Business Type"
            title={`${selectedYear} 年累计明细`}
            description="按业务种类汇总损益组成和占比。"
          />
          <BusinessRowsTable rows={rows} />
        </section>
      </AsyncSection>
    </main>
  );
}
