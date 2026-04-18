import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { nativeToNumber } from "../../bond-dashboard/utils/format";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";

type DashboardBondHeadlineSectionProps = {
  reportDate: string;
};

function toState(enabled: boolean, isLoading: boolean, isError: boolean, hasData: boolean): DataSectionState {
  if (!enabled) {
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载债券头条 KPI。" };
  }
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "债券头条 KPI 加载失败" };
  if (!hasData) return { kind: "empty", hint: "该日暂无债券头条 KPI。" };
  return { kind: "ok" };
}

const GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
} as const;

const CELL_STYLE = {
  display: "grid",
  gap: 6,
  padding: 14,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

export function DashboardBondHeadlineSection({ reportDate }: DashboardBondHeadlineSectionProps) {
  const client = useApiClient();
  const enabled = Boolean(reportDate.trim());
  const query = useQuery({
    queryKey: ["dashboard", "bond-headline-kpis", client.mode, reportDate],
    queryFn: () => client.getBondDashboardHeadlineKpis(reportDate.trim()),
    enabled,
    retry: false,
  });

  const payload = query.data?.result;
  const kpis = payload?.kpis;

  const cells = useMemo(() => {
    if (!kpis) return [];
    const mv = nativeToNumber(kpis.total_market_value);
    const pnl = nativeToNumber(kpis.unrealized_pnl);
    const ytm = nativeToNumber(kpis.weighted_ytm);
    const dur = nativeToNumber(kpis.weighted_duration);
    const cpn = nativeToNumber(kpis.weighted_coupon);
    const spr = nativeToNumber(kpis.credit_spread_median);
    const dv = nativeToNumber(kpis.total_dv01);
    const dvWan = dv / 10_000;
    return [
      { label: "债券持仓规模", value: formatNumeric(formatRawAsNumeric({ raw: mv, unit: "yuan", sign_aware: false })) },
      { label: "未实现损益", value: formatNumeric(formatRawAsNumeric({ raw: pnl, unit: "yuan", sign_aware: true })) },
      { label: "加权到期收益率", value: formatNumeric(formatRawAsNumeric({ raw: ytm, unit: "pct", sign_aware: false })) },
      { label: "加权久期", value: formatNumeric(formatRawAsNumeric({ raw: dur, unit: "ratio", sign_aware: false })) },
      { label: "加权票息率", value: formatNumeric(formatRawAsNumeric({ raw: cpn, unit: "pct", sign_aware: false })) },
      { label: "信用利差(中位数)", value: formatNumeric(formatRawAsNumeric({ raw: spr, unit: "pct", sign_aware: false })) },
      {
        label: "DV01 合计",
        value: `${formatNumeric(formatRawAsNumeric({ raw: dvWan, unit: "ratio", sign_aware: false, precision: 2 }))} 万元`,
      },
      {
        label: "债券只数",
        value: formatNumeric(
          formatRawAsNumeric({ raw: kpis.bond_count, unit: "count", sign_aware: false }),
        ),
      },
    ];
  }, [kpis]);

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, Boolean(kpis)),
    [enabled, query.isLoading, query.isError, kpis],
  );

  return (
    <div data-testid="dashboard-bond-headline-section">
      <DataSection
        title="债券组合头条"
        state={state}
        onRetry={() => void query.refetch()}
        extra={
          payload?.report_date ? (
            <span style={{ fontSize: 12, color: "#64748b" }}>报告日 {payload.report_date}</span>
          ) : null
        }
      >
        <div style={GRID_STYLE}>
          {cells.map((c) => (
            <div key={c.label} style={CELL_STYLE}>
              <div style={{ fontSize: 12, color: "#8090a8" }}>{c.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#162033", fontVariantNumeric: "tabular-nums" }}>
                {c.value}
              </div>
            </div>
          ))}
        </div>
      </DataSection>
    </div>
  );
}
