import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
} from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

const actionButtonStyle = {
  padding: "10px 14px",
  borderRadius: 12,
  border: "1px solid #cddcff",
  background: "#edf3ff",
  color: "#1f5eff",
  fontWeight: 600,
  cursor: "pointer",
} as const;

const PAGE_SIZE = 2;

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
} as const;

const resultMetaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: 16,
  marginTop: 20,
} as const;

const resultMetaCardStyle = {
  padding: 16,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#f7f9fc",
} as const;

const resultMetaListStyle = {
  margin: 0,
  display: "grid",
  gridTemplateColumns: "minmax(110px, 140px) minmax(0, 1fr)",
  gap: "8px 12px",
  fontSize: 13,
} as const;

const workbookPrimaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const workbookPanelStyle = {
  borderRadius: 20,
  border: "1px solid #dfe7f2",
  background: "linear-gradient(180deg, #ffffff 0%, #f6f9fc 100%)",
  padding: 18,
  boxShadow: "0 12px 28px rgba(19, 37, 70, 0.06)",
} as const;

const workbookPanelHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 12,
  marginBottom: 14,
} as const;

const workbookPanelBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 8px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
} as const;

const workbookSecondaryGridStyle = {
  display: "grid",
  gap: 18,
  marginTop: 18,
} as const;

const workbookSecondaryPanelGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const workbookCockpitLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 2fr) minmax(300px, 1fr)",
  gap: 18,
  marginTop: 18,
  alignItems: "start",
} as const;

const workbookMainRailStyle = {
  display: "grid",
  gap: 18,
} as const;

const workbookRightRailStyle = {
  display: "grid",
  gap: 18,
  alignContent: "start",
} as const;

const barTrackStyle = {
  width: "100%",
  height: 8,
  borderRadius: 999,
  background: "#e9eef6",
  overflow: "hidden",
} as const;

const primaryWorkbookTableKeys = [
  "bond_business_types",
  "rating_analysis",
  "maturity_gap",
  "issuance_business_types",
] as const;

const secondaryWorkbookPanelKeys = [
  "industry_distribution",
  "rate_distribution",
  "counterparty_types",
] as const;

const rightRailWorkbookKeys = [
  "decision_items",
  "event_calendar",
  "risk_alerts",
] as const;

const workbookPanelNotes: Record<(typeof primaryWorkbookTableKeys)[number], string> = {
  bond_business_types: "对应 Excel 的债券业务种类页，先看资产端主分布和规模占比。",
  rating_analysis: "按评级拆开当前债券资产的规模，保留驾驶舱式强弱对比。",
  maturity_gap: "用期限桶直接看资产负债缺口，不再只给纯表格。",
  issuance_business_types: "发行类单独成块，避免和资产端视图混在一起。",
};

const workbookSecondaryPanelNotes: Record<(typeof secondaryWorkbookPanelKeys)[number], string> = {
  industry_distribution: "把债券资产按行业集中度展开，先看规模最重的方向。",
  rate_distribution: "同一利率桶里并排看债券、同业资产和同业负债。",
  counterparty_types: "按对手方类型看资产、负债和净头寸。",
};

const workbookRightRailNotes: Record<(typeof rightRailWorkbookKeys)[number], string> = {
  decision_items: "规则驱动的运营建议项，保留原因、来源分区和规则版本。",
  event_calendar: "内部治理事件日历，只展示由现有 formal/workbook 输入派生的事件。",
  risk_alerts: "阈值型风险预警，不在前端补正式金融判断。",
};

const ratingBlockPalette = ["#2fbf93", "#5792ff", "#ff9c43", "#8f7cf7", "#ff6b6b", "#7cc4fa"];

function downloadCsvFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function parseWorkbookNumber(value: unknown) {
  const text = String(value ?? "").replaceAll(",", "").trim();
  const parsed = Number.parseFloat(text);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatWorkbookValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function renderWorkbookContractMismatch(table: BalanceAnalysisWorkbookTable, message: string) {
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        borderRadius: 16,
        border: "1px solid #ffd8bf",
        background: "#fff7f0",
        color: "#a14a14",
        padding: 14,
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      {message}
    </div>
  );
}

function renderWorkbookEmptyState(message: string) {
  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px dashed #d7dfea",
        background: "#f7f9fc",
        color: "#8090a8",
        padding: 14,
        fontSize: 13,
      }}
    >
      {message}
    </div>
  );
}

function hasWorkbookFields(rows: Array<Record<string, unknown>>, requiredKeys: string[]) {
  if (rows.length === 0) {
    return true;
  }
  return rows.every((row) => requiredKeys.every((key) => row[key] !== undefined && row[key] !== null));
}

function renderDistributionPanel(
  table: BalanceAnalysisWorkbookTable,
  {
    labelKey,
    valueKey,
    color,
  }: {
    labelKey: string;
    valueKey: string;
    color: string;
  },
) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, [labelKey, valueKey])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：缺少主分布图所需字段。");
  }
  const maxValue = Math.max(...rows.map((row) => parseWorkbookNumber(row[valueKey])), 1);
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row[valueKey]);
        const width = `${Math.max(14, (value / maxValue) * 100)}%`;
        return (
          <div key={`${table.key}-${index}`} style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span style={{ color: "#162033", fontWeight: 600 }}>
                {formatWorkbookValue(row[labelKey])}
              </span>
              <span style={{ color: "#5c6b82", fontVariantNumeric: "tabular-nums" }}>
                {formatWorkbookValue(row[valueKey])}
              </span>
            </div>
            <div style={barTrackStyle}>
              <div
                style={{
                  width,
                  height: "100%",
                  borderRadius: 999,
                  background: color,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function renderRatingPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["rating", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：评级分布字段不完整。");
  }
  const maxValue = Math.max(...rows.map((row) => parseWorkbookNumber(row.balance_amount)), 1);
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: 10,
      }}
    >
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row.balance_amount);
        const ratio = Math.max(0.35, value / maxValue);
        return (
          <article
            key={`${table.key}-${index}`}
            style={{
              borderRadius: 16,
              padding: 14,
              background: ratingBlockPalette[index % ratingBlockPalette.length],
              color: "#ffffff",
              minHeight: 88,
              opacity: 0.55 + ratio * 0.45,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 700 }}>{formatWorkbookValue(row.rating)}</div>
            <div style={{ fontSize: 13, opacity: 0.92 }}>{formatWorkbookValue(row.balance_amount)}</div>
          </article>
        );
      })}
    </div>
  );
}

function renderMaturityGapPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["bucket", "gap_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：期限缺口字段不完整。");
  }
  const maxValue = Math.max(...rows.map((row) => Math.abs(parseWorkbookNumber(row.gap_amount))), 1);
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${Math.max(rows.length, 1)}, minmax(0, 1fr))`,
        gap: 12,
        alignItems: "end",
        minHeight: 220,
      }}
    >
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row.gap_amount);
        const height = Math.max(18, (Math.abs(value) / maxValue) * 148);
        const positive = value >= 0;
        return (
          <div
            key={`${table.key}-${index}`}
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
              gap: 10,
              minHeight: 220,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                justifyContent: "center",
                minHeight: 160,
              }}
            >
              <div
                style={{
                  width: "100%",
                  maxWidth: 48,
                  height,
                  borderRadius: "14px 14px 6px 6px",
                  background: positive
                    ? "linear-gradient(180deg, #6aa8ff 0%, #1f5eff 100%)"
                    : "linear-gradient(180deg, #ffbe76 0%, #ff7a45 100%)",
                  boxShadow: positive
                    ? "0 12px 24px rgba(31, 94, 255, 0.18)"
                    : "0 12px 24px rgba(255, 122, 69, 0.18)",
                }}
              />
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ color: "#162033", fontWeight: 600, fontSize: 13 }}>
                {formatWorkbookValue(row.bucket)}
              </div>
              <div style={{ color: positive ? "#1f5eff" : "#d9622b", fontSize: 12, marginTop: 4 }}>
                {formatWorkbookValue(row.gap_amount)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function renderIssuancePanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, ["bond_type", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：发行类分析字段不完整。");
  }
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.bond_type)}</div>
            <div style={{ color: "#1f5eff", fontWeight: 700 }}>{formatWorkbookValue(row.balance_amount)}</div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, color: "#5c6b82", fontSize: 12 }}>
            <span>笔数 {formatWorkbookValue(row.count)}</span>
            <span>利率 {formatWorkbookValue(row.weighted_rate_pct)}</span>
            <span>期限 {formatWorkbookValue(row.weighted_term_years)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderWorkbookPrimaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "bond_business_types") {
    return renderDistributionPanel(table, {
      labelKey: "bond_type",
      valueKey: "balance_amount",
      color: "linear-gradient(90deg, #91c4ff 0%, #1f5eff 100%)",
    });
  }
  if (table.key === "rating_analysis") {
    return renderRatingPanel(table);
  }
  if (table.key === "maturity_gap") {
    return renderMaturityGapPanel(table);
  }
  if (table.key === "issuance_business_types") {
    return renderIssuancePanel(table);
  }
  return null;
}

function renderIndustryPanel(table: BalanceAnalysisWorkbookTable) {
  return renderDistributionPanel(table, {
    labelKey: "industry_name",
    valueKey: "balance_amount",
    color: "linear-gradient(90deg, #8ad7b0 0%, #2fbf93 100%)",
  });
}

function renderRateDistributionPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 5);
  if (!hasWorkbookFields(rows, [
    "bucket",
    "bond_amount",
    "interbank_asset_amount",
    "interbank_liability_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：利率分布字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.bucket)}</div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 10,
              fontSize: 12,
            }}
          >
            <div>
              <div style={{ color: "#8090a8" }}>债券</div>
              <div style={{ color: "#1f5eff", fontWeight: 700 }}>{formatWorkbookValue(row.bond_amount)}</div>
            </div>
            <div>
              <div style={{ color: "#8090a8" }}>同业资产</div>
              <div style={{ color: "#2fbf93", fontWeight: 700 }}>
                {formatWorkbookValue(row.interbank_asset_amount)}
              </div>
            </div>
            <div>
              <div style={{ color: "#8090a8" }}>同业负债</div>
              <div style={{ color: "#ff7a45", fontWeight: 700 }}>
                {formatWorkbookValue(row.interbank_liability_amount)}
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderCounterpartyPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, [
    "counterparty_type",
    "asset_amount",
    "liability_amount",
    "net_position_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：对手方类型字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.counterparty_type)}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12 }}>
            <span style={{ color: "#1f5eff" }}>资产 {formatWorkbookValue(row.asset_amount)}</span>
            <span style={{ color: "#ff7a45" }}>负债 {formatWorkbookValue(row.liability_amount)}</span>
            <span style={{ color: "#162033" }}>净头寸 {formatWorkbookValue(row.net_position_amount)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderDecisionItemsPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("No governed items.");
  }
  if (!hasWorkbookFields(table.rows, ["title", "action_label", "severity", "reason", "source_section"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：决策事项字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {table.rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
            <span style={workbookPanelBadgeStyle}>{formatWorkbookValue(row.severity)}</span>
          </div>
          <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
            {formatWorkbookValue(row.reason)}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
            <span>{formatWorkbookValue(row.action_label)}</span>
            <span>{formatWorkbookValue(row.source_section)}</span>
            <span>{formatWorkbookValue(row.rule_id)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderEventCalendarPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("No governed items.");
  }
  if (!hasWorkbookFields(table.rows, ["event_date", "event_type", "title", "source", "impact_hint"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：事件日历字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {table.rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
            <div style={{ color: "#1f5eff", fontSize: 12 }}>{formatWorkbookValue(row.event_date)}</div>
          </div>
          <div style={{ color: "#5c6b82", fontSize: 13 }}>{formatWorkbookValue(row.impact_hint)}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
            <span>{formatWorkbookValue(row.event_type)}</span>
            <span>{formatWorkbookValue(row.source)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderRiskAlertsPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("No governed items.");
  }
  if (!hasWorkbookFields(table.rows, ["title", "severity", "reason", "source_section"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：风险预警字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {table.rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #ffd8bf",
            background: "#fff7f0",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
            <span style={{ ...workbookPanelBadgeStyle, background: "#ffe7d6", color: "#d9622b" }}>
              {formatWorkbookValue(row.severity)}
            </span>
          </div>
          <div style={{ color: "#a14a14", fontSize: 13, lineHeight: 1.6 }}>
            {formatWorkbookValue(row.reason)}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#b46a3c" }}>
            <span>{formatWorkbookValue(row.source_section)}</span>
            <span>{formatWorkbookValue(row.rule_id)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderWorkbookSecondaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "industry_distribution") {
    return renderIndustryPanel(table);
  }
  if (table.key === "rate_distribution") {
    return renderRateDistributionPanel(table);
  }
  if (table.key === "counterparty_types") {
    return renderCounterpartyPanel(table);
  }
  return null;
}

function renderWorkbookRightRailPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "decision_items") {
    return renderDecisionItemsPanel(table);
  }
  if (table.key === "event_calendar") {
    return renderEventCalendarPanel(table);
  }
  if (table.key === "risk_alerts") {
    return renderRiskAlertsPanel(table);
  }
  return null;
}

export default function BalanceAnalysisPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [positionScope, setPositionScope] = useState<BalancePositionScope>("all");
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>("CNY");
  const [summaryOffset, setSummaryOffset] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    const firstDate = datesQuery.data?.result.report_dates?.[0];
    if (!selectedReportDate && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [datesQuery.data?.result.report_dates, selectedReportDate]);

  useEffect(() => {
    setSummaryOffset(0);
  }, [selectedReportDate, positionScope, currencyBasis]);

  const overviewQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "overview",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const detailQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "detail",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisDetail({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const workbookQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "workbook",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisWorkbook({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const summaryQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "summary-table",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
      summaryOffset,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisSummary({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
        limit: PAGE_SIZE,
        offset: summaryOffset,
      }),
    retry: false,
  });

  const overview = overviewQuery.data?.result;
  const overviewMeta = overviewQuery.data?.result_meta;
  const detailMeta = detailQuery.data?.result_meta;
  const workbookMeta = workbookQuery.data?.result_meta;
  const summaryMeta = summaryQuery.data?.result_meta;
  const workbook = workbookQuery.data?.result;
  const summaryTable = summaryQuery.data?.result;
  const workbookTables = workbook?.tables ?? [];
  const primaryWorkbookTables = primaryWorkbookTableKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);
  const secondaryWorkbookPanelTables = secondaryWorkbookPanelKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);
  const rightRailWorkbookTables = rightRailWorkbookKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);
  const secondaryWorkbookTables = workbookTables.filter(
    (table) =>
      !primaryWorkbookTableKeys.includes(table.key as (typeof primaryWorkbookTableKeys)[number]) &&
      !secondaryWorkbookPanelKeys.includes(table.key as (typeof secondaryWorkbookPanelKeys)[number]) &&
      !rightRailWorkbookKeys.includes(table.key as (typeof rightRailWorkbookKeys)[number]),
  );
  const resultMetaSections = [
    overviewMeta ? { key: "overview", title: "Overview Result Meta", meta: overviewMeta } : null,
    workbookMeta ? { key: "workbook", title: "Workbook Result Meta", meta: workbookMeta } : null,
    summaryMeta ? { key: "summary", title: "Summary Result Meta", meta: summaryMeta } : null,
    detailMeta ? { key: "detail", title: "Detail Result Meta", meta: detailMeta } : null,
  ].filter(
    (
      section,
    ): section is { key: string; title: string; meta: NonNullable<typeof overviewMeta> } =>
      section !== null,
  );

  async function handleRefresh() {
    if (!selectedReportDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshBalanceAnalysis(selectedReportDate),
        getStatus: (runId) => client.getBalanceAnalysisRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          setRefreshStatus(
            [nextPayload.status, nextPayload.run_id, nextPayload.source_version]
              .filter(Boolean)
              .join(" · "),
          );
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([
        datesQuery.refetch(),
        overviewQuery.refetch(),
        workbookQuery.refetch(),
        detailQuery.refetch(),
        summaryQuery.refetch(),
      ]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新资产负债分析失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExporting(true);
    setRefreshError(null);
    try {
      const payload = await client.exportBalanceAnalysisSummaryCsv({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      });
      downloadCsvFile(payload.filename, payload.content);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "导出资产负债分析失败");
    } finally {
      setIsExporting(false);
    }
  }

  const totalPages = Math.max(
    1,
    Math.ceil((summaryTable?.total_rows ?? 0) / (summaryTable?.limit ?? PAGE_SIZE)),
  );
  const currentPage = Math.floor(summaryOffset / (summaryTable?.limit ?? PAGE_SIZE)) + 1;

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          资产负债分析
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          第一张 governed balance-analysis consumer。页面只消费 formal facts，不读取 preview 或 snapshot。
        </p>
      </div>

      <div style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="balance-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>头寸范围</span>
          <select
            aria-label="balance-position-scope"
            value={positionScope}
            onChange={(event) => setPositionScope(event.target.value as BalancePositionScope)}
            style={controlStyle}
          >
            <option value="all">all</option>
            <option value="asset">asset</option>
            <option value="liability">liability</option>
          </select>
        </label>

        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>币种口径</span>
          <select
            aria-label="balance-currency-basis"
            value={currencyBasis}
            onChange={(event) => setCurrencyBasis(event.target.value as BalanceCurrencyBasis)}
            style={controlStyle}
          >
            <option value="CNY">CNY</option>
            <option value="native">native</option>
          </select>
        </label>

        <button
          data-testid="balance-analysis-refresh-button"
          type="button"
          onClick={() => void handleRefresh()}
          disabled={!selectedReportDate || isRefreshing}
          style={actionButtonStyle}
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
        <button
          data-testid="balance-analysis-export-button"
          type="button"
          onClick={() => void handleExport()}
          disabled={!selectedReportDate || isExporting}
          style={actionButtonStyle}
        >
          {isExporting ? "导出中..." : "导出 CSV"}
        </button>
      </div>

      <div data-testid="balance-analysis-overview-cards" style={summaryGridStyle}>
        <PlaceholderCard
          title="明细行数"
          value={String(overview?.detail_row_count ?? 0)}
          detail="当前筛选条件下的 formal detail 行数。"
        />
        <PlaceholderCard
          title="汇总分组"
          value={String(overview?.summary_row_count ?? 0)}
          detail="按 source_family / position_scope / currency_basis 聚合后的组数。"
        />
        <PlaceholderCard
          title="总规模"
          value={String(overview?.total_market_value_amount ?? "0.00")}
          detail="当前 summary.market_value_amount 求和。"
        />
        <PlaceholderCard
          title="摊余成本"
          value={String(overview?.total_amortized_cost_amount ?? "0.00")}
          detail="当前 formal 摊余成本总额。"
        />
        <PlaceholderCard
          title="应计利息"
          value={String(overview?.total_accrued_interest_amount ?? "0.00")}
          detail="当前 formal 应计利息总额。"
        />
      </div>

      <div data-testid="balance-analysis-summary" style={{ display: "none" }}>
        {String(overview?.detail_row_count ?? 0)} {String(overview?.summary_row_count ?? 0)}{" "}
        {String(overview?.total_market_value_amount ?? "0.00")}
      </div>

      {resultMetaSections.length > 0 && (
        <section data-testid="balance-analysis-result-meta" style={resultMetaGridStyle}>
          {resultMetaSections.map((section) => (
            <article
              key={section.key}
              data-testid={`balance-analysis-result-meta-${section.key}`}
              style={resultMetaCardStyle}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: 16,
                  fontWeight: 600,
                  color: "#162033",
                }}
              >
                {section.title}
              </h2>
              <p style={{ marginTop: 8, marginBottom: 14, color: "#5c6b82", fontSize: 13 }}>
                Inspect the governed formal provenance returned by the active query.
              </p>
              <dl style={resultMetaListStyle}>
                <dt style={{ color: "#5c6b82" }}>basis</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.basis}</dd>
                <dt style={{ color: "#5c6b82" }}>result_kind</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.result_kind}</dd>
                <dt style={{ color: "#5c6b82" }}>source_version</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.source_version}</dd>
                <dt style={{ color: "#5c6b82" }}>rule_version</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.rule_version}</dd>
                <dt style={{ color: "#5c6b82" }}>cache_version</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.cache_version}</dd>
                <dt style={{ color: "#5c6b82" }}>quality_flag</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.quality_flag}</dd>
                <dt style={{ color: "#5c6b82" }}>generated_at</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.generated_at}</dd>
                <dt style={{ color: "#5c6b82" }}>trace_id</dt>
                <dd style={{ margin: 0, color: "#162033" }}>{section.meta.trace_id}</dd>
              </dl>
            </article>
          ))}
        </section>
      )}

      {(refreshStatus || refreshError) && (
        <div
          style={{
            marginTop: 16,
            padding: 14,
            borderRadius: 14,
            border: "1px solid #e4ebf5",
            background: refreshError ? "#fff2f0" : "#f7f9fc",
            color: refreshError ? "#c83b3b" : "#5c6b82",
          }}
        >
          {refreshError ?? refreshStatus}
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="债券/组合汇总表现"
          isLoading={
            datesQuery.isLoading ||
            overviewQuery.isLoading ||
            summaryQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            overviewQuery.isError ||
            summaryQuery.isError
          }
          isEmpty={!summaryQuery.isLoading && (summaryTable?.rows.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([
              datesQuery.refetch(),
              overviewQuery.refetch(),
              workbookQuery.refetch(),
              detailQuery.refetch(),
              summaryQuery.refetch(),
            ]);
          }}
        >
          <div style={tableShellStyle}>
            <table data-testid="balance-analysis-summary-table" style={tableStyle}>
              <thead>
                <tr>
                  {[
                    "来源",
                    "组合名称",
                    "分类",
                    "规模(亿)",
                    "摊余成本",
                    "应计利息",
                    "明细行数",
                    "会计口径",
                  ].map((label) => (
                    <th
                      key={label}
                      style={{
                        textAlign: "left",
                        padding: "10px 12px",
                        borderBottom: "1px solid #e4ebf5",
                        color: "#5c6b82",
                        fontSize: 13,
                      }}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(summaryTable?.rows ?? []).map((row) => (
                  <tr key={row.row_key}>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.source_family.toUpperCase()}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.owner_name}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.category_name}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.market_value_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.amortized_cost_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.accrued_interest_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.detail_row_count}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.invest_type_std} / {row.accounting_basis}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 10,
              marginTop: 12,
            }}
          >
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => Math.max(0, current - PAGE_SIZE))}
              disabled={summaryOffset === 0}
              style={actionButtonStyle}
            >
              上一页
            </button>
            <span>{`第 ${currentPage} / ${totalPages} 页`}</span>
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => current + PAGE_SIZE)}
              disabled={summaryOffset + PAGE_SIZE >= (summaryTable?.total_rows ?? 0)}
              style={actionButtonStyle}
            >
              下一页
            </button>
          </div>
          <div style={{ marginTop: 18 }}>
            <div style={{ color: "#8090a8", fontSize: 12, marginBottom: 8 }}>明细下钻预留</div>
            {detailQuery.isError ? (
              <div
                style={{
                  borderRadius: 14,
                  border: "1px solid #ffd8bf",
                  background: "#fff7f0",
                  color: "#a14a14",
                  padding: 14,
                  fontSize: 13,
                }}
              >
                明细下钻暂时不可用，汇总驾驶舱仍可继续使用。
              </div>
            ) : detailQuery.isLoading ? (
              <div style={{ color: "#8090a8", fontSize: 13 }}>明细下钻加载中…</div>
            ) : (
              <table data-testid="balance-analysis-table" style={tableStyle}>
                <thead>
                  <tr>
                    {["来源", "标识", "范围", "会计口径", "规模", "应计利息"].map((label) => (
                      <th
                        key={label}
                        style={{
                          textAlign: "left",
                          padding: "10px 12px",
                          borderBottom: "1px solid #e4ebf5",
                          color: "#5c6b82",
                          fontSize: 13,
                        }}
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(detailQuery.data?.result.details ?? []).map((row) => (
                    <tr key={row.row_key}>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.source_family.toUpperCase()}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.display_name}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.position_scope}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.invest_type_std} / {row.accounting_basis}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.market_value_amount}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                        {row.accrued_interest_amount}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="Excel 参考模块"
          isLoading={
            datesQuery.isLoading ||
            workbookQuery.isLoading
          }
          isError={datesQuery.isError || workbookQuery.isError}
          isEmpty={!workbookQuery.isLoading && (workbook?.tables.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), workbookQuery.refetch()]);
          }}
        >
          <div data-testid="balance-analysis-workbook-cards" style={summaryGridStyle}>
            {(workbook?.cards ?? []).map((card) => (
              <PlaceholderCard
                key={card.key}
                title={card.label}
                value={String(card.value)}
                detail={card.note ?? ""}
              />
            ))}
          </div>

          <div style={workbookCockpitLayoutStyle}>
            <div style={workbookMainRailStyle}>
              <div data-testid="balance-analysis-workbook-primary-grid" style={workbookPrimaryGridStyle}>
                {primaryWorkbookTables.map((table) => (
                  <article
                    key={table.key}
                    data-testid={`balance-analysis-workbook-panel-${table.key}`}
                    style={workbookPanelStyle}
                  >
                    <div style={workbookPanelHeaderStyle}>
                      <div>
                        <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                        <p
                          style={{
                            marginTop: 6,
                            marginBottom: 0,
                            color: "#5c6b82",
                            fontSize: 13,
                            lineHeight: 1.6,
                          }}
                        >
                          {workbookPanelNotes[table.key as (typeof primaryWorkbookTableKeys)[number]]}
                        </p>
                      </div>
                      <span style={workbookPanelBadgeStyle}>Excel 映射</span>
                    </div>
                    {renderWorkbookPrimaryPanel(table)}
                  </article>
                ))}
              </div>

              <div
                data-testid="balance-analysis-workbook-secondary-panels"
                style={workbookSecondaryPanelGridStyle}
              >
                {secondaryWorkbookPanelTables.map((table) => (
                  <article
                    key={table.key}
                    data-testid={`balance-analysis-workbook-panel-${table.key}`}
                    style={workbookPanelStyle}
                  >
                    <div style={workbookPanelHeaderStyle}>
                      <div>
                        <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                        <p
                          style={{
                            marginTop: 6,
                            marginBottom: 0,
                            color: "#5c6b82",
                            fontSize: 13,
                            lineHeight: 1.6,
                          }}
                        >
                          {workbookSecondaryPanelNotes[table.key as (typeof secondaryWorkbookPanelKeys)[number]]}
                        </p>
                      </div>
                      <span style={workbookPanelBadgeStyle}>二级驾驶舱</span>
                    </div>
                    {renderWorkbookSecondaryPanel(table)}
                  </article>
                ))}
              </div>
            </div>

            <aside data-testid="balance-analysis-right-rail" style={workbookRightRailStyle}>
              {rightRailWorkbookTables.map((table) => (
                <article
                  key={table.key}
                  data-testid={`balance-analysis-right-rail-panel-${table.key}`}
                  style={workbookPanelStyle}
                >
                  <div style={workbookPanelHeaderStyle}>
                    <div>
                      <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                      <p
                        style={{
                          marginTop: 6,
                          marginBottom: 0,
                          color: "#5c6b82",
                          fontSize: 13,
                          lineHeight: 1.6,
                        }}
                      >
                        {workbookRightRailNotes[table.key as (typeof rightRailWorkbookKeys)[number]]}
                      </p>
                    </div>
                    <span style={workbookPanelBadgeStyle}>Governed rail</span>
                  </div>
                  {renderWorkbookRightRailPanel(table)}
                </article>
              ))}
            </aside>
          </div>

          <div data-testid="balance-analysis-workbook-secondary-grid" style={workbookSecondaryGridStyle}>
            {secondaryWorkbookTables.map((table) => (
              <div key={table.key} data-testid={`balance-analysis-workbook-table-${table.key}`}>
                <div style={{ marginBottom: 8, color: "#162033", fontWeight: 600 }}>{table.title}</div>
                <div style={tableShellStyle}>
                  <table style={tableStyle}>
                    <thead>
                      <tr>
                        {table.columns.map((column) => (
                          <th
                            key={column.key}
                            style={{
                              textAlign: "left",
                              padding: "10px 12px",
                              borderBottom: "1px solid #e4ebf5",
                              color: "#5c6b82",
                              fontSize: 13,
                            }}
                          >
                            {column.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, index) => (
                        <tr key={`${table.key}-${index}`}>
                          {table.columns.map((column) => (
                            <td
                              key={column.key}
                              style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}
                            >
                              {formatWorkbookValue(row[column.key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>
      </div>
    </section>
  );
}
