import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

type DashboardBondCounterpartySectionProps = {
  reportDate: string;
};

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
  if (isError) return { kind: "error", message: "债券对手方统计加载失败" };
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
  return Number.isFinite(parsed) ? parsed : null;
}

export function DashboardBondCounterpartySection({
  reportDate,
}: DashboardBondCounterpartySectionProps) {
  const client = useApiClient();
  const date = reportDate.trim();
  const enabled = Boolean(date);
  const query = useQuery({
    queryKey: ["dashboard", "bond-counterparty-top5", client.mode, date],
    queryFn: () =>
      client.getPositionsCounterpartyBonds({
        startDate: date,
        endDate: date,
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

  const totalSample = result?.total_amount
    ? formatNumeric(
        formatRawAsNumeric({
          raw: parseYuan(result.total_amount),
          unit: "yuan",
          sign_aware: false,
        }),
      )
    : null;

  return (
    <DashboardCockpitSection
      testId="dashboard-bond-counterparty-section"
      eyebrow="Counterparty Risk"
      title="债券资产对手方"
      state={state}
      onRetry={() => void query.refetch()}
      extra={
        totalSample ? (
          <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
            样本口径 {totalSample}
          </span>
        ) : null
      }
    >
      <div data-testid="dashboard-bond-counterparty-list" style={{ display: "grid", gap: 10 }}>
        {rows.map((row, index) => {
          const amount = parseYuan(row.total_amount);
          const rate = parseRateRatio(row.weighted_rate);
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
              <div style={{ display: "grid", gap: 4 }}>
                <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>
                  {row.customer_name}
                </span>
                <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                  敞口{" "}
                  {amount === null
                    ? "—"
                    : formatNumeric(
                        formatRawAsNumeric({
                          raw: amount,
                          unit: "yuan",
                          sign_aware: false,
                        }),
                      )}
                  {rate === null
                    ? ""
                    : ` / 加权收益率 ${formatNumeric(
                        formatRawAsNumeric({
                          raw: rate,
                          unit: "pct",
                          sign_aware: false,
                        }),
                      )}`}
                </span>
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
    </DashboardCockpitSection>
  );
}
