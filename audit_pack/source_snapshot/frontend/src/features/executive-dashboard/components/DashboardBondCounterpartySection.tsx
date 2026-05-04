import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import { DashboardCockpitSection } from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

type DashboardBondCounterpartySectionProps = {
  reportDate: string;
};

function buildYtdRange(reportDate: string) {
  const date = reportDate.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return null;
  }
  return {
    startDate: `${date.slice(0, 4)}-01-01`,
    endDate: date,
  };
}

function toState(
  enabled: boolean,
  isLoading: boolean,
  isError: boolean,
  rowCount: number,
): DataSectionState {
  if (!enabled) {
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载债券资产对手方。" };
  }
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "债券对手方统计加载失败。" };
  if (rowCount === 0) return { kind: "empty", hint: "该日暂无债券对手方样本。" };
  return { kind: "ok" };
}

function parseYuan(value: string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseRateRatio(value: string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return null;
  // Real payloads may emit percent-point strings like "2.0235" for 2.0235%.
  // Homepage cards must align with the repo-wide pct display contract.
  return Math.abs(parsed) > 1 ? parsed / 100 : parsed;
}

function formatAmount(raw: number | null) {
  if (raw === null) return "—";
  return formatNumeric(
    formatRawAsNumeric({
      raw,
      unit: "yuan",
      sign_aware: false,
    }),
  );
}

function formatPercent(raw: number | null) {
  if (raw === null) return "—";
  return formatNumeric(
    formatRawAsNumeric({
      raw,
      unit: "pct",
      sign_aware: false,
    }),
  );
}

function ratio(part: number | null, total: number | null) {
  if (part === null || total === null || total <= 0) return null;
  return part / total;
}

const summaryCardStyle = {
  ...cockpitInsetCardStyle,
  gap: 6,
  minHeight: 86,
} as const;

export function DashboardBondCounterpartySection({
  reportDate,
}: DashboardBondCounterpartySectionProps) {
  const client = useApiClient();
  const range = useMemo(() => buildYtdRange(reportDate), [reportDate]);
  const date = range?.endDate ?? "";
  const enabled = Boolean(range);
  const query = useQuery({
    queryKey: [
      "dashboard",
      "bond-counterparty-top5",
      client.mode,
      range?.startDate ?? "",
      range?.endDate ?? "",
    ],
    queryFn: () =>
      client.getPositionsCounterpartyBonds({
        startDate: range!.startDate,
        endDate: range!.endDate,
        topN: 5,
        page: 1,
        pageSize: 5,
      }),
    enabled,
    retry: false,
  });

  const result = query.data?.result;
  const rows = useMemo(
    () => (result?.items ?? []).slice(0, 5),
    [result?.items],
  );

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, rows.length),
    [enabled, query.isLoading, query.isError, rows.length],
  );

  const totalAmount = parseYuan(result?.total_amount);
  const totalAvgDaily = parseYuan(result?.total_avg_daily);
  const totalWeightedRate = parseRateRatio(result?.total_weighted_rate);
  const totalWeightedCouponRate = parseRateRatio(result?.total_weighted_coupon_rate);

  const summaryItems = [
    { label: "区间累计", value: formatAmount(totalAmount) },
    { label: "日均合计", value: formatAmount(totalAvgDaily) },
    { label: "加权收益率", value: formatPercent(totalWeightedRate) },
    { label: "加权付息率", value: formatPercent(totalWeightedCouponRate) },
  ];

  return (
    <DashboardCockpitSection
      testId="dashboard-bond-counterparty-section"
      eyebrow="对手方风险"
      title="债券资产对手方"
      state={state}
      onRetry={() => void query.refetch()}
      extra={
        date ? (
          <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
            报告日 {date}
          </span>
        ) : null
      }
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 10,
          }}
        >
          {summaryItems.map((item) => (
            <article key={item.label} style={summaryCardStyle}>
              <span
                style={{
                  color: shellTokens.colorTextMuted,
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                {item.label}
              </span>
              <strong
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: 20,
                  fontWeight: 800,
                }}
              >
                {item.value}
              </strong>
            </article>
          ))}
        </div>

        <div data-testid="dashboard-bond-counterparty-list" style={{ display: "grid", gap: 10 }}>
          {rows.map((row, index) => {
            const avgDaily = parseYuan(row.avg_daily_balance);
            const share = ratio(avgDaily, totalAvgDaily);
            const rate = parseRateRatio(row.weighted_rate);
            const couponRate = parseRateRatio(row.weighted_coupon_rate);
            return (
              <article
                key={row.customer_name}
                style={{
                  ...cockpitInsetCardStyle,
                  gridTemplateColumns: "40px minmax(0, 1fr) auto",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <span
                  style={{
                    display: "grid",
                    placeItems: "center",
                    width: 32,
                    height: 32,
                    borderRadius: 12,
                    background: shellTokens.colorAccentSoft,
                    color: shellTokens.colorAccent,
                    fontWeight: 800,
                  }}
                >
                  {index + 1}
                </span>
                <div style={{ display: "grid", gap: 8 }}>
                  <div style={{ display: "grid", gap: 4 }}>
                    <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>
                      {row.customer_name}
                    </span>
                    <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                      日均 {formatAmount(avgDaily)} / 占样本 {formatPercent(share)}
                      {rate === null ? "" : ` / 加权收益率 ${formatPercent(rate)}`}
                      {couponRate === null ? "" : ` / 加权付息率 ${formatPercent(couponRate)}`}
                    </span>
                  </div>
                  <div
                    aria-hidden="true"
                    style={{
                      width: "100%",
                      height: 6,
                      borderRadius: 999,
                      background: "#eef3f8",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max((share ?? 0) * 100, 4)}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: "linear-gradient(90deg, #9ec4f2 0%, #2b6ea6 100%)",
                      }}
                    />
                  </div>
                </div>
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: 11,
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  资产端
                </span>
              </article>
            );
          })}
        </div>
      </div>
    </DashboardCockpitSection>
  );
}
