import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";

type DashboardBondCounterpartySectionProps = {
  reportDate: string;
};

function toState(enabled: boolean, isLoading: boolean, isError: boolean, rowCount: number): DataSectionState {
  if (!enabled) {
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载债券对手方 Top 列表。" };
  }
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "债券对手方统计加载失败" };
  if (rowCount === 0) return { kind: "empty", hint: "该日暂无债券对手方样本。" };
  return { kind: "ok" };
}

function parseYuan(s: string | null | undefined): number | null {
  if (s == null || s === "") return null;
  const n = Number.parseFloat(s);
  return Number.isFinite(n) ? n : null;
}

function parseRateRatio(s: string | null | undefined): number | null {
  if (s == null || s === "") return null;
  const n = Number.parseFloat(s);
  return Number.isFinite(n) ? n : null;
}

export function DashboardBondCounterpartySection({ reportDate }: DashboardBondCounterpartySectionProps) {
  const client = useApiClient();
  const d = reportDate.trim();
  const enabled = Boolean(d);
  const query = useQuery({
    queryKey: ["dashboard", "bond-counterparty-top5", client.mode, d],
    queryFn: () =>
      client.getPositionsCounterpartyBonds({
        startDate: d,
        endDate: d,
        topN: 5,
        page: 1,
        pageSize: 5,
      }),
    enabled,
    retry: false,
  });

  const result = query.data?.result;
  const rows = useMemo(() => (result?.items ?? []).slice(0, 5), [result?.items]);

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, rows.length),
    [enabled, query.isLoading, query.isError, rows.length],
  );

  return (
    <div data-testid="dashboard-bond-counterparty-section">
      <DataSection
        title="对手方风险（债券资产 Top5）"
        state={state}
        onRetry={() => void query.refetch()}
      >
        <div style={{ display: "grid", gap: 12 }}>
          {result?.total_amount ? (
            <div style={{ fontSize: 13, color: "#5c6b82" }}>
              样本总敞口（原币）：
              <span style={{ fontWeight: 600, color: "#162033" }}>
                {formatNumeric(
                  formatRawAsNumeric({
                    raw: parseYuan(result.total_amount),
                    unit: "yuan",
                    sign_aware: false,
                  }),
                )}
              </span>
            </div>
          ) : null}
          <ol style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 12, fontSize: 13 }}>
            {rows.map((row) => {
              const amt = parseYuan(row.total_amount);
              const rate = parseRateRatio(row.weighted_rate);
              return (
                <li key={row.customer_name}>
                  <div style={{ fontWeight: 600, color: "#162033" }}>{row.customer_name}</div>
                  <div style={{ color: "#5c6b82" }}>
                    敞口：
                    {amt === null
                      ? "—"
                      : formatNumeric(formatRawAsNumeric({ raw: amt, unit: "yuan", sign_aware: false }))}
                    {rate === null
                      ? ""
                      : ` · 加权收益率：${formatNumeric(formatRawAsNumeric({ raw: rate, unit: "pct", sign_aware: false }))}`}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </DataSection>
    </div>
  );
}
