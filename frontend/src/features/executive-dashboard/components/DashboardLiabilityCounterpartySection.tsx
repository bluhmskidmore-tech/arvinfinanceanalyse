import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric } from "../../../utils/format";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
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
  if (isError) return { kind: "error", message: "负债对手方数据加载失败" };
  if (rowCount === 0) return { kind: "empty", hint: "该日暂无负债对手方 Top 数据。" };
  return { kind: "ok" };
}

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

  return (
    <DashboardCockpitSection
      testId="dashboard-liability-counterparty-section"
      eyebrow="Funding Dependence"
      title="负债端对手方"
      state={state}
      onRetry={() => void query.refetch()}
      extra={
        query.data?.total_value ? (
          <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
            样本合计 {formatNumeric(query.data.total_value)}
          </span>
        ) : null
      }
    >
      <div data-testid="dashboard-liability-counterparty-list" style={{ display: "grid", gap: 10 }}>
        {rows.map((row, index) => (
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
            <div style={{ display: "grid", gap: 4 }}>
              <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>
                {row.name}
              </span>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                余额 {row.value ? formatNumeric(row.value) : "—"}
                {row.weighted_cost ? ` / 加权成本 ${formatNumeric(row.weighted_cost)}` : ""}
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
              负债端
            </span>
          </article>
        ))}
      </div>
    </DashboardCockpitSection>
  );
}
