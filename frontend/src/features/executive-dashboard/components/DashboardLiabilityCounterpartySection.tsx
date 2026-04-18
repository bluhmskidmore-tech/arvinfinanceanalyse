import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { formatNumeric } from "../../../utils/format";

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
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载负债端对手方 Top 列表。" };
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

  const rows = useMemo(() => (query.data?.top_10 ?? []).slice(0, 5), [query.data?.top_10]);

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, rows.length),
    [enabled, query.isLoading, query.isError, rows.length],
  );

  return (
    <div data-testid="dashboard-liability-counterparty-section">
      <DataSection
        title="对手方风险（负债端 Top5）"
        state={state}
        onRetry={() => void query.refetch()}
      >
        <div style={{ display: "grid", gap: 12 }}>
          {query.data?.total_value ? (
            <div style={{ fontSize: 13, color: "#5c6b82" }}>
              样本合计：<span style={{ fontWeight: 600, color: "#162033" }}>{formatNumeric(query.data.total_value)}</span>
            </div>
          ) : null}
          <ol style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 10, fontSize: 13 }}>
            {rows.map((row) => (
              <li key={`${row.name}-${row.type}`}>
                <div style={{ fontWeight: 600, color: "#162033" }}>{row.name}</div>
                <div style={{ color: "#5c6b82" }}>
                  余额：{row.value ? formatNumeric(row.value) : "—"}
                  {row.weighted_cost ? ` · 加权成本：${formatNumeric(row.weighted_cost)}` : ""}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </DataSection>
    </div>
  );
}
