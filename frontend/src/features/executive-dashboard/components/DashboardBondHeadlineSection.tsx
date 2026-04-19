import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import { formatNumeric, formatRawAsNumeric } from "../../../utils/format";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { nativeToNumber } from "../../bond-dashboard/utils/format";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
import {
  cockpitBodyStyle,
  cockpitInsetCardStyle,
} from "./DashboardCockpitSection.styles";

type DashboardBondHeadlineSectionProps = {
  reportDate: string;
};

type HeadlineCell = {
  label: string;
  value: string;
  detail: string;
  tone?: "positive" | "negative" | "neutral";
};

function toState(
  enabled: boolean,
  isLoading: boolean,
  isError: boolean,
  hasData: boolean,
): DataSectionState {
  if (!enabled) {
    return { kind: "empty", hint: "等待快照或手动选择报告日后加载债券头条。" };
  }
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "债券头条 KPI 加载失败" };
  if (!hasData) return { kind: "empty", hint: "该日暂无债券头条 KPI。" };
  return { kind: "ok" };
}

export function DashboardBondHeadlineSection({
  reportDate,
}: DashboardBondHeadlineSectionProps) {
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

  const { leadText, cells } = useMemo(() => {
    if (!kpis) {
      return { leadText: "", cells: [] as HeadlineCell[] };
    }

    const totalMarketValue = nativeToNumber(kpis.total_market_value);
    const unrealizedPnl = nativeToNumber(kpis.unrealized_pnl);
    const weightedYtm = nativeToNumber(kpis.weighted_ytm);
    const weightedDuration = nativeToNumber(kpis.weighted_duration);
    const weightedCoupon = nativeToNumber(kpis.weighted_coupon);
    const spreadMedian = nativeToNumber(kpis.credit_spread_median);
    const rateSensitivity = nativeToNumber(kpis.total_dv01) / 10_000;
    const bondCount = nativeToNumber(kpis.bond_count);

    const leadText = [
      `市场值 ${formatNumeric(formatRawAsNumeric({ raw: totalMarketValue, unit: "yuan", sign_aware: false }))}`,
      `久期 ${formatNumeric(formatRawAsNumeric({ raw: weightedDuration, unit: "ratio", sign_aware: false }))}`,
      `YTM ${formatNumeric(formatRawAsNumeric({ raw: weightedYtm, unit: "pct", sign_aware: false }))}`,
    ].join(" / ");

    const pnlTone = toneFromSignedNumber(unrealizedPnl) === "positive"
      ? "positive"
      : toneFromSignedNumber(unrealizedPnl) === "negative"
        ? "negative"
        : "neutral";

    return {
      leadText,
      cells: [
        {
          label: "债券持仓规模",
          value: formatNumeric(formatRawAsNumeric({ raw: totalMarketValue, unit: "yuan", sign_aware: false })),
          detail: "债券组合总市场值",
        },
        {
          label: "未实现损益",
          value: formatNumeric(formatRawAsNumeric({ raw: unrealizedPnl, unit: "yuan", sign_aware: true })),
          detail: "浮盈浮亏状态",
          tone: pnlTone,
        },
        {
          label: "加权到期收益率",
          value: formatNumeric(formatRawAsNumeric({ raw: weightedYtm, unit: "pct", sign_aware: false })),
          detail: "组合收益率中枢",
        },
        {
          label: "加权久期",
          value: formatNumeric(formatRawAsNumeric({ raw: weightedDuration, unit: "ratio", sign_aware: false })),
          detail: "利率暴露中枢",
        },
        {
          label: "加权票息率",
          value: formatNumeric(formatRawAsNumeric({ raw: weightedCoupon, unit: "pct", sign_aware: false })),
          detail: "票息收入水平",
        },
        {
          label: "信用利差中位数",
          value: formatNumeric(formatRawAsNumeric({ raw: spreadMedian, unit: "pct", sign_aware: false })),
          detail: "信用估值区间",
        },
        {
          label: "利率敏感度合计",
          value: `${formatNumeric(formatRawAsNumeric({ raw: rateSensitivity, unit: "ratio", sign_aware: false, precision: 2 }))} 万元`,
          detail: "基点价值口径",
        },
        {
          label: "债券只数",
          value: formatNumeric(formatRawAsNumeric({ raw: bondCount, unit: "count", sign_aware: false })),
          detail: "样本覆盖范围",
        },
      ],
    };
  }, [kpis]);

  const state = useMemo(
    () => toState(enabled, query.isLoading, query.isError, Boolean(kpis)),
    [enabled, query.isLoading, query.isError, kpis],
  );

  return (
    <DashboardCockpitSection
      testId="dashboard-bond-headline-section"
      eyebrow="Bond Headlines"
      title="债券组合头条"
      state={state}
      onRetry={() => void query.refetch()}
      extra={
        payload?.report_date ? (
          <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
            报告日 {payload.report_date}
          </span>
        ) : null
      }
    >
      <div style={{ display: "grid", gap: 14 }}>
        <div
          data-testid="dashboard-bond-headline-lead"
          style={{
            ...cockpitInsetCardStyle,
            gap: 6,
            background: "linear-gradient(135deg, rgba(240,246,255,0.88) 0%, rgba(255,255,255,0.96) 100%)",
          }}
        >
          <strong style={{ color: shellTokens.colorTextPrimary, fontSize: 16 }}>
            首页先看债券组合状态
          </strong>
          <p style={cockpitBodyStyle}>
            {leadText || "等待报告日后再生成债券组合的首屏状态判断。"}
          </p>
        </div>
        <div
          data-testid="dashboard-bond-headline-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
            gap: 12,
          }}
        >
          {cells.map((cell) => (
            <div key={cell.label} data-testid="dashboard-bond-headline-kpi" style={cockpitInsetCardStyle}>
              <span style={{ color: shellTokens.colorTextMuted, fontSize: 11, fontWeight: 700 }}>
                {cell.label}
              </span>
              <strong
                style={{
                  color:
                    cell.tone === "positive"
                      ? shellTokens.colorSuccess
                      : cell.tone === "negative"
                        ? shellTokens.colorDanger
                        : shellTokens.colorTextPrimary,
                  fontSize: 22,
                  lineHeight: 1.1,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.03em",
                }}
              >
                {cell.value}
              </strong>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                {cell.detail}
              </span>
            </div>
          ))}
        </div>
      </div>
    </DashboardCockpitSection>
  );
}
