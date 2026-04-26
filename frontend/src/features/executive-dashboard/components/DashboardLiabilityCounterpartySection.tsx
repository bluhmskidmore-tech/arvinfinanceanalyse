import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import { DashboardCockpitSection } from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

type DashboardLiabilityCounterpartySectionProps = {
  reportDate: string;
};

function toState(
  enabled: boolean,
  isLoading: boolean,
  isError: boolean,
  rowCount: number,
): DataSectionState {
  if (!enabled) {
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载负债端对手方。" };
  }
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "负债对手方数据加载失败。" };
  if (rowCount === 0) return { kind: "empty", hint: "该日暂无负债对手方 Top 数据。" };
  return { kind: "ok" };
}

function numericRaw(value: Numeric | null | undefined) {
  return value?.raw ?? null;
}

function formatValue(value: Numeric | null | undefined) {
  if (!value) return "—";
  if (value.raw === null || value.raw === undefined) return "—";
  if (value.unit === "yuan" || value.unit === "yi") {
    return formatNumeric(
      formatRawAsNumeric({
        raw: value.unit === "yuan" ? value.raw : value.raw * 100_000_000,
        unit: "yuan",
        sign_aware: value.sign_aware,
        precision: 2,
      }),
    );
  }
  if (value.unit === "pct") {
    return formatNumeric(
      formatRawAsNumeric({
        raw: value.raw,
        unit: "pct",
        sign_aware: value.sign_aware,
        precision: value.precision,
      }),
    );
  }
  return formatNumeric(value);
}

function ratio(part: Numeric | null | undefined, total: Numeric | null | undefined) {
  const partRaw = numericRaw(part);
  const totalRaw = numericRaw(total);
  if (partRaw === null || totalRaw === null || totalRaw <= 0) return null;
  return {
    raw: partRaw / totalRaw,
    unit: "pct" as const,
    precision: 2,
    sign_aware: false,
    display: "",
  };
}

function bankShareValue(
  rows: Array<{ name: string; value?: Numeric | null }>,
  totalValue: Numeric | null | undefined,
) {
  const bank = rows.find((row) => row.name === "Bank");
  return ratio(bank?.value, totalValue);
}

const summaryCardStyle = {
  ...cockpitInsetCardStyle,
  gap: 6,
  minHeight: 86,
} as const;

export function DashboardLiabilityCounterpartySection({
  reportDate,
}: DashboardLiabilityCounterpartySectionProps) {
  const client = useApiClient();
  const enabled = Boolean(reportDate.trim());
  const query = useQuery({
    queryKey: ["dashboard", "liability-cp-top5", client.mode, reportDate],
    queryFn: () =>
      client.getLiabilityCounterparty({
        reportDate: reportDate.trim(),
        topN: 5,
      }),
    enabled,
    retry: false,
  });

  const rows = useMemo(
    () => (query.data?.top_10 ?? []).slice(0, 5),
    [query.data?.top_10],
  );

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, rows.length),
    [enabled, query.isLoading, query.isError, rows.length],
  );

  const topShare = ratio(rows[0]?.value, query.data?.total_value);
  const bankShare = bankShareValue(query.data?.by_type ?? [], query.data?.total_value);

  const summaryItems = [
    { label: "样本合计", value: formatValue(query.data?.total_value) },
    { label: "Top1 占比", value: formatValue(topShare) },
    { label: "银行占比", value: formatValue(bankShare) },
    {
      label: "机构类型",
      value:
        query.data?.by_type && query.data.by_type.length > 0
          ? `${query.data.by_type.length} 类`
          : "—",
    },
  ];

  return (
    <DashboardCockpitSection
      testId="dashboard-liability-counterparty-section"
      eyebrow="资金依赖"
      title="负债端对手方"
      state={state}
      onRetry={() => void query.refetch()}
      extra={
        reportDate.trim() ? (
          <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
            报告日 {reportDate.trim()}
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

        <div data-testid="dashboard-liability-counterparty-list" style={{ display: "grid", gap: 10 }}>
          {rows.map((row, index) => {
            const share = ratio(row.value, query.data?.total_value);
            return (
              <article
                key={`${row.name}-${row.type}`}
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
                    background: "#fff4e4",
                    color: shellTokens.colorWarning,
                    fontWeight: 800,
                  }}
                >
                  {index + 1}
                </span>
                <div style={{ display: "grid", gap: 8 }}>
                  <div style={{ display: "grid", gap: 4 }}>
                    <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>
                      {row.name}
                    </span>
                    <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                      余额 {formatValue(row.value)} / 占样本 {formatValue(share)}
                      {row.weighted_cost ? ` / 加权成本 ${formatValue(row.weighted_cost)}` : ""}
                    </span>
                  </div>
                  <div
                    aria-hidden="true"
                    style={{
                      width: "100%",
                      height: 6,
                      borderRadius: 999,
                      background: "#f5ede0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max((numericRaw(share) ?? 0) * 100, 4)}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: "linear-gradient(90deg, #f0c388 0%, #c97a1f 100%)",
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
                  负债端
                </span>
              </article>
            );
          })}
        </div>
      </div>
    </DashboardCockpitSection>
  );
}
