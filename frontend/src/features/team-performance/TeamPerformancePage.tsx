import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { FilterBar } from "../../components/FilterBar";
import type { DecimalLike, ProductCategoryPnlRow } from "../../api/contracts";
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: shellTokens.colorTextPrimary,
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: shellTokens.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const tableShellStyle = {
  overflowX: "auto" as const,
  borderRadius: 16,
  border: `1px solid ${shellTokens.colorBorder}`,
  background: shellTokens.colorBgSurface,
  marginTop: 18,
};

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse" as const,
  fontSize: 13,
};

const thStyle = {
  textAlign: "left" as const,
  padding: "10px 12px",
  borderBottom: `1px solid ${shellTokens.colorBorder}`,
  color: shellTokens.colorTextSecondary,
  fontSize: 13,
};

const thNumericStyle = {
  ...thStyle,
  textAlign: "right" as const,
};

const tdStyle = {
  padding: "12px",
  borderBottom: `1px solid ${shellTokens.colorBgMuted}`,
  color: shellTokens.colorTextPrimary,
};

const tdNumericStyle = {
  ...tdStyle,
  textAlign: "right" as const,
};

const selectStyle = {
  padding: "10px 14px",
  borderRadius: 12,
  border: `1px solid ${shellTokens.colorBorder}`,
  background: shellTokens.colorBgSurface,
  color: shellTokens.colorTextPrimary,
  fontSize: 14,
} as const;

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function cellText(value: DecimalLike | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

export default function TeamPerformancePage() {
  const client = useApiClient();
  const [selectedDate, setSelectedDate] = useState("");

  const datesQuery = useQuery({
    queryKey: ["team-performance", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    const first = datesQuery.data?.result.report_dates?.[0];
    if (!selectedDate && first) {
      setSelectedDate(first);
    }
  }, [datesQuery.data?.result.report_dates, selectedDate]);

  const detailQuery = useQuery({
    queryKey: ["team-performance", "detail", client.mode, selectedDate],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: "monthly",
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const result = detailQuery.data?.result;

  const datesReady = Boolean(datesQuery.data?.result.report_dates?.length);
  /** Avoid flashing KPI placeholders before selectedDate is synced from dates (detail query still disabled). */
  const isInitializingSelection = datesReady && !selectedDate;

  const { grandRow, assetRow, liabilityRow, teamRows } = useMemo(() => {
    const rows = result?.rows ?? [];
    const teams = rows.filter((r) => r.level === 1 && !r.is_total);
    return {
      grandRow: result?.grand_total,
      assetRow: result?.asset_total,
      liabilityRow: result?.liability_total,
      teamRows: teams,
    };
  }, [result]);

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            data-testid="team-performance-page-title"
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
              color: shellTokens.colorTextPrimary,
            }}
          >
            团队绩效
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 860,
              color: shellTokens.colorTextSecondary,
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            按产品类别维度展示各组贡献，数据来源为产品损益 read model。
          </p>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ marginBottom: 22 }}>
        <div>
          <label style={{ display: "block", marginBottom: 6, color: shellTokens.colorTextSecondary, fontSize: 14 }}>
            报表月份
          </label>
          <select
            aria-label="团队绩效-报表月份"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            style={selectStyle}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </div>
      </FilterBar>

      <SectionLead
        eyebrow="Overview"
        title="团队概览"
        description="先看资产端、负债端和综合净收入，再进入各组贡献表，保持团队绩效页的阅读顺序与标准壳层一致。"
      />

      <div data-testid="team-performance-kpi" style={summaryGridStyle}>
        <KpiCard
          title="资产端净收入"
          value={cellText(assetRow?.business_net_income)}
          detail="asset_total 行 business_net_income（后端返回值）。"
          tone={toneFromSignedDisplayString(cellText(assetRow?.business_net_income))}
        />
        <KpiCard
          title="负债端净收入"
          value={cellText(liabilityRow?.business_net_income)}
          detail="liability_total 行 business_net_income（后端返回值）。"
          tone={toneFromSignedDisplayString(cellText(liabilityRow?.business_net_income))}
        />
        <KpiCard
          title="综合净收入"
          value={cellText(grandRow?.business_net_income)}
          detail="grand_total 行 business_net_income（后端返回值）。"
          tone={toneFromSignedDisplayString(cellText(grandRow?.business_net_income))}
        />
        <KpiCard
          title="组数"
          value={String(teamRows.length)}
          detail="level=1 且非合计行的行数。"
          unit="组"
        />
      </div>

      <SectionLead
        eyebrow="Contribution"
        title="团队贡献"
        description="下方表格继续按产品类别 read model 展示各组贡献，不改变现有列与数值语义。"
      />
      <AsyncSection
        title="核心指标与团队贡献"
        isLoading={
          datesQuery.isLoading ||
          isInitializingSelection ||
          (Boolean(selectedDate) && detailQuery.isLoading)
        }
        isError={datesQuery.isError || detailQuery.isError}
        isEmpty={
          !datesQuery.isLoading &&
          !detailQuery.isLoading &&
          !datesQuery.isError &&
          !detailQuery.isError &&
          Boolean(selectedDate) &&
          !grandRow &&
          teamRows.length === 0
        }
        onRetry={() => {
          void Promise.all([datesQuery.refetch(), detailQuery.refetch()]);
        }}
      >
        <div style={{ display: "grid", gap: 20 }}>
          <div style={tableShellStyle}>
            <table data-testid="team-performance-table" style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>类别名称</th>
                  <th style={thNumericStyle}>日均规模</th>
                  <th style={thNumericStyle}>业务净收入</th>
                  <th style={thNumericStyle}>FTP 成本</th>
                  <th style={thNumericStyle}>净利差</th>
                  <th style={thNumericStyle}>完成进度</th>
                </tr>
              </thead>
              <tbody>
                {teamRows.map((row: ProductCategoryPnlRow) => (
                  <tr key={row.category_id}>
                    <td style={tdStyle}>{row.category_name}</td>
                    <td style={tdNumericStyle}>{cellText(row.cny_scale)}</td>
                    <td style={tdNumericStyle}>{cellText(row.business_net_income)}</td>
                    <td style={tdNumericStyle}>{cellText(row.cny_ftp)}</td>
                    <td style={tdNumericStyle}>{cellText(row.cny_net)}</td>
                    <td style={tdNumericStyle}>{cellText(row.weighted_yield)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </AsyncSection>
    </section>
  );
}
