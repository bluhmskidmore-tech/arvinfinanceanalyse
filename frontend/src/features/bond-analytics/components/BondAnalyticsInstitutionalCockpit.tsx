import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Row, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type { ActionAttributionResponse } from "../types";
import { formatBp, formatPct, formatWan, formatYi, toneColor } from "../utils/formatters";
import { FIELD, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Text } = Typography;

const statusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: 12,
} as const;

const compactListStyle = {
  display: "grid",
  gap: 10,
} as const;

const dashboardCardStyle = panelStyle("#ffffff");

function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return Number.isFinite(n) ? n : Number.NaN;
}

function relRatioLine(
  label: string,
  prevRaw: Numeric | null | undefined,
  curRaw: Numeric | null | undefined,
): string | null {
  const p = numOr(prevRaw);
  const c = numOr(curRaw);
  if (!Number.isFinite(p) || p === 0 || !Number.isFinite(c)) return null;
  const pct = ((c - p) / p) * 100;
  return `${label} ${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatCompactValue(raw: Numeric | null | undefined, kind: "pct" | "bp" | "yi" | "wan") {
  if (!raw) return "—";
  if (kind === "pct") return formatPct(raw);
  if (kind === "bp") return formatBp(raw);
  if (kind === "yi") return formatYi(raw);
  return formatWan(raw);
}

function formatNumericString(raw: string | number | null | undefined) {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(raw);
  }
  return parsed.toLocaleString("zh-CN");
}

function buildCockpitConclusion(args: {
  duration: number;
  creditWeight: number;
  spreadMedian: number;
}) {
  const { duration, creditWeight, spreadMedian } = args;

  if (Number.isFinite(duration) && duration >= 3.8) {
    return {
      title: "当前结论",
      body: "久期敞口仍是首页第一观察位。",
      detail: `加权久期 ${duration.toFixed(2)} 年，先看期限结构和动作归因，再决定是否切到 KRD 下钻。`,
    };
  }

  if (Number.isFinite(creditWeight) && creditWeight >= 0.35) {
    return {
      title: "当前结论",
      body: "信用敞口偏重，需优先盯利差与集中度。",
      detail: `信用权重 ${(creditWeight * 100).toFixed(1)}%，建议先复核信用利差和行业集中暴露。`,
    };
  }

  const spreadBp = Number.isFinite(spreadMedian)
    ? (spreadMedian < 0.5 ? spreadMedian * 10000 : spreadMedian)
    : Number.NaN;

  return {
    title: "当前结论",
    body: "收益率和信用利差都处在可读但不宽松的区间。",
    detail: `加权久期 ${Number.isFinite(duration) ? `${duration.toFixed(2)} 年` : "—"}，信用利差中位数 ${
      Number.isFinite(spreadBp) ? `${spreadBp.toFixed(1)} bp` : "—"
    }。`,
  };
}

function DashboardMetric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px solid #dbe4f0",
        background: "#fbfcfe",
        padding: "12px 14px",
        display: "grid",
        gap: 5,
      }}
    >
      <div style={{ ...FIELD, marginBottom: 0 }}>{label}</div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: "-0.03em",
          color:
            tone === "positive"
              ? "#cf1322"
              : tone === "negative"
                ? "#3f8600"
                : "#18314d",
        }}
      >
        {value}
      </div>
      <div style={{ color: "#627791", fontSize: 12, lineHeight: 1.55 }}>{detail}</div>
    </div>
  );
}

function SignalCell({
  label,
  summary,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  summary: string;
  value: string;
  detail: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px solid #dde6f2",
        background: "#fbfcfe",
        padding: "14px 14px 12px",
        display: "grid",
        gap: 6,
      }}
    >
      <div style={{ ...FIELD, marginBottom: 0 }}>{label}</div>
      <div
        style={{
          color:
            tone === "positive" ? "#cf1322" : tone === "negative" ? "#3f8600" : "#1c3554",
          fontSize: 18,
          fontWeight: 800,
          lineHeight: 1.2,
          letterSpacing: "-0.03em",
        }}
      >
        {summary}
      </div>
      <div style={{ color: "#52657f", fontSize: 12, fontWeight: 700 }}>{value}</div>
      <div style={{ color: "#6a7d95", fontSize: 12, lineHeight: 1.55 }}>{detail}</div>
    </div>
  );
}

function scoreBarRows(
  items: Array<{ key: string; label: string; value: number; caption: string; color: string }>,
) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  return (
    <div style={compactListStyle}>
      {items.map((item) => (
        <div key={item.key} style={{ display: "grid", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: "#18314d", fontWeight: 700, fontSize: 13 }}>{item.label}</span>
            <span style={{ color: item.color, fontWeight: 700, fontSize: 12 }}>{item.caption}</span>
          </div>
          <div style={{ width: "100%", height: 7, borderRadius: 999, background: "#eaf0f6", overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.max(14, (Math.abs(item.value) / maxValue) * 100)}%`,
                height: "100%",
                borderRadius: 999,
                background: item.color,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  topAnomalies = [],
  actionAttribution = null,
  onOpenModuleDetail,
}: BondAnalyticsInstitutionalCockpitProps) {
  const client = useApiClient();

  const [headlineQ, spreadQ, maturityQ, holdingsQ, portfolioHlQ] = useQueries({
    queries: [
      {
        queryKey: ["bond-analytics-institutional", "headline", client.mode, reportDate],
        queryFn: () => client.getBondDashboardHeadlineKpis(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "spread", client.mode, reportDate],
        queryFn: () => client.getBondDashboardSpreadAnalysis(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "maturity", client.mode, reportDate],
        queryFn: () => client.getBondDashboardMaturityStructure(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "holdings", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsTopHoldings(reportDate, 5),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "portfolio-hl", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsPortfolioHeadlines(reportDate),
        enabled: Boolean(reportDate),
      },
    ],
  });

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;
  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;

  const dur = headline ? numOr(headline.kpis.weighted_duration) : Number.NaN;
  const creditWeight = portfolioHl ? numOr(portfolioHl.credit_weight) : Number.NaN;
  const spreadMedian = headline ? numOr(headline.kpis.credit_spread_median) : Number.NaN;
  const conclusion = buildCockpitConclusion({
    duration: dur,
    creditWeight,
    spreadMedian,
  });

  const k = headline?.kpis;
  const p = headline?.prev_kpis;

  const focusItems = useMemo(() => {
    const merged = [
      ...topAnomalies,
      ...(portfolioHl?.warnings ?? []),
      ...(actionAttribution?.warnings ?? []),
    ]
      .map((item) => item.trim())
      .filter(Boolean);

    const unique = Array.from(new Set(merged));
    if (unique.length > 0) {
      return unique.slice(0, 4);
    }

    const fallback = [
      k ? `组合规模 ${formatYi(k.total_market_value)}，浮盈 ${formatYi(k.unrealized_pnl)}。` : "",
      portfolioHl ? `信用权重 ${formatPct(portfolioHl.credit_weight)}，债券只数 ${portfolioHl.bond_count}。` : "",
      actionAttribution ? `本期动作 ${actionAttribution.total_actions} 笔，贡献 ${formatWan(actionAttribution.total_pnl_from_actions)}。` : "",
    ]
      .map((item) => item.trim())
      .filter(Boolean);

    return fallback.length > 0 ? fallback.slice(0, 3) : ["当前未返回额外异常或治理提示。"];
  }, [actionAttribution, k, portfolioHl, topAnomalies]);

  const maturityItems = useMemo(() => {
    return [...(maturityQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 4)
      .map((item) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: numOr(item.total_market_value),
        caption: formatYi(item.total_market_value),
        color: "#2f8f63",
      }));
  }, [maturityQ.data]);

  const spreadItems = useMemo(() => {
    return [...(spreadQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 4);
  }, [spreadQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const topHoldings = (holdingsQ.data?.result.items ?? []).slice(0, 3);
  const actionTypeRows = (actionAttribution?.by_action_type ?? []).slice(0, 4);
  const totalActionPnl = bondNumericRaw(actionAttribution?.total_pnl_from_actions ?? null);
  const ytmDeltaBp =
    k && p && Number.isFinite(numOr(k.weighted_ytm)) && Number.isFinite(numOr(p.weighted_ytm))
      ? (numOr(k.weighted_ytm) - numOr(p.weighted_ytm)) * 10000
      : Number.NaN;

  return (
    <section data-testid="bond-analysis-phase3-cockpit" style={{ display: "grid", gap: 12 }}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <Row gutter={[12, 12]}>
        <Col xs={24} xl={16}>
          <Card
            size="small"
            data-testid="bond-analysis-cockpit-conclusion"
            style={panelStyle("linear-gradient(135deg, #ffffff 0%, #f7fbff 55%, #eef4fb 100%)")}
          >
            <div style={{ display: "grid", gap: 14 }}>
              <div style={{ display: "grid", gap: 6 }}>
                <div style={FIELD}>市场状态（一句话）</div>
                <div style={{ fontSize: 28, fontWeight: 800, lineHeight: 1.18, letterSpacing: "-0.04em", color: "#18314d" }}>
                  {conclusion.body}
                </div>
                <Text type="secondary">{conclusion.detail}</Text>
              </div>

              <div style={statusGridStyle}>
                <SignalCell
                  label="利率"
                  summary={Number.isFinite(ytmDeltaBp) ? (ytmDeltaBp <= 0 ? "下行未尽" : "短端回弹") : "方向待确认"}
                  value={k ? `${formatPct(k.weighted_ytm)} · ${Number.isFinite(ytmDeltaBp) ? `${ytmDeltaBp >= 0 ? "+" : ""}${ytmDeltaBp.toFixed(1)}bp` : "—"}` : "—"}
                  detail={relRatioLine("较上期", p?.weighted_ytm, k?.weighted_ytm) ?? "关注收益率方向与波动。"}
                  tone={Number.isFinite(ytmDeltaBp) ? (ytmDeltaBp <= 0 ? "negative" : "positive") : "default"}
                />
                <SignalCell
                  label="曲线"
                  summary={leadMaturity ? `${leadMaturity.label} 最集中` : "期限待确认"}
                  value={leadMaturity ? leadMaturity.caption : Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"}
                  detail="先看最重期限桶，再决定是否切到 KRD 和收益率曲线下钻。"
                />
                <SignalCell
                  label="信用"
                  summary={Number.isFinite(creditWeight) && creditWeight >= 0.35 ? "压缩尾段" : "压缩可读"}
                  value={
                    Number.isFinite(spreadMedian)
                      ? `${(spreadMedian < 0.5 ? spreadMedian * 10000 : spreadMedian).toFixed(1)} bp · 权重 ${portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}`
                      : "—"
                  }
                  detail={portfolioHl ? `信用权重 ${formatPct(portfolioHl.credit_weight)}` : "关注信用权重与利差位置。"}
                />
                <SignalCell
                  label="资金"
                  summary={k && numOr(k.unrealized_pnl) >= 0 ? "收益垫仍在" : "收益垫转弱"}
                  value={k ? `${formatYi(k.total_market_value)} · 浮盈 ${formatYi(k.unrealized_pnl)}` : "—"}
                  detail="用组合规模和浮盈变化判断当前仓位的防守空间。"
                  tone={k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default"}
                />
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card size="small" title="今日关注" data-testid="bond-analysis-today-focus" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              {focusItems.map((item, index) => (
                <div
                  key={`${item}-${index}`}
                  style={{ display: "flex", gap: 10, alignItems: "flex-start", paddingBottom: 10, borderBottom: "1px solid #eef2f6" }}
                >
                  <span style={{ color: "#2f6fff", fontSize: 18, lineHeight: 1 }}>•</span>
                  <span style={{ color: "#314a66", fontSize: 13, lineHeight: 1.7 }}>{item}</span>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="利率驱动拆解" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>加权收益率</span>
                <span style={{ color: "#18314d", fontWeight: 700 }}>{k ? formatPct(k.weighted_ytm) : "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>加权久期</span>
                <span style={{ color: "#18314d", fontWeight: 700 }}>
                  {Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"}
                </span>
              </div>
              {maturityItems.length > 0 ? scoreBarRows(maturityItems) : <Text type="secondary">暂无期限结构</Text>}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="信用利差" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>信用权重</span>
                <span style={{ color: "#18314d", fontWeight: 700 }}>
                  {portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>利差中位数</span>
                <span style={{ color: "#18314d", fontWeight: 700 }}>
                  {k ? formatCompactValue(k.credit_spread_median, "bp") : "—"}
                </span>
              </div>
              {spreadItems.length > 0 ? (
                <div style={compactListStyle}>
                  {spreadItems.map((item) => (
                    <div
                      key={item.bond_type}
                      style={{ display: "grid", gap: 4, paddingBottom: 10, borderBottom: "1px solid #eef2f6" }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                        <span style={{ color: "#18314d", fontWeight: 700, fontSize: 13 }}>{item.bond_type}</span>
                        <span style={{ color: "#5c6b82", fontSize: 12 }}>{formatYi(item.total_market_value)}</span>
                      </div>
                      <div style={{ color: "#61758f", fontSize: 12 }}>
                        中位收益率 {item.median_yield ? formatPct(item.median_yield) : "—"} · 只数 {item.bond_count}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Text type="secondary">暂无利差分布</Text>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="组合收益概览" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>组合市值</span>
                <span style={{ color: "#18314d", fontWeight: 700 }}>{k ? formatYi(k.total_market_value) : "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>浮动盈亏</span>
                <span
                  style={{
                    color: k ? toneColor(numOr(k.unrealized_pnl)) : "#18314d",
                    fontWeight: 700,
                  }}
                >
                  {k ? formatYi(k.unrealized_pnl) : "—"}
                </span>
              </div>
              {topHoldings.length > 0 ? (
                <div style={compactListStyle}>
                  {topHoldings.map((item) => (
                    <div
                      key={item.instrument_code}
                      style={{ display: "grid", gap: 4, paddingBottom: 10, borderBottom: "1px solid #eef2f6" }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                        <span style={{ color: "#18314d", fontWeight: 700, fontSize: 13 }}>{item.instrument_name}</span>
                        <span style={{ color: "#5c6b82", fontSize: 12 }}>{formatWan(item.face_value)}</span>
                      </div>
                      <div style={{ color: "#61758f", fontSize: 12 }}>
                        收益率 {formatPct(item.ytm)} · 久期 {item.modified_duration.display} · {item.rating}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Text type="secondary">暂无重仓摘要</Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="组合暴露" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
                <DashboardMetric
                  label="组合规模"
                  value={portfolioHl ? formatYi(portfolioHl.total_market_value) : "—"}
                  detail="portfolio headlines"
                />
                <DashboardMetric
                  label="DV01"
                  value={portfolioHl ? formatWan(portfolioHl.total_dv01) : "—"}
                  detail="组合利率敏感度"
                />
                <DashboardMetric
                  label="Top5 集中度"
                  value={portfolioHl ? formatPct(portfolioHl.issuer_top5_weight) : "—"}
                  detail="发行人权重"
                />
                <DashboardMetric
                  label="债券只数"
                  value={portfolioHl ? formatNumericString(portfolioHl.bond_count) : "—"}
                  detail="持仓明细数量"
                />
              </div>
              {assetClassItems.length > 0 ? (
                <div style={compactListStyle}>
                  {assetClassItems.map((item) => (
                    <div key={item.asset_class} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <span style={{ color: "#61758f", fontSize: 12 }}>{item.asset_class}</span>
                      <span style={{ color: "#18314d", fontWeight: 700, fontSize: 12 }}>
                        {item.weight.display} · 久期 {item.duration.display}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="组合收益归因（本期）" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
                <DashboardMetric
                  label="动作数量"
                  value={actionAttribution ? formatNumericString(actionAttribution.total_actions) : "—"}
                  detail="action attribution"
                />
                <DashboardMetric
                  label="动作贡献"
                  value={actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : "—"}
                  detail="经济口径损益"
                  tone={Number.isFinite(totalActionPnl) && totalActionPnl !== 0 ? (totalActionPnl > 0 ? "positive" : "negative") : "default"}
                />
              </div>
              {actionTypeRows.length > 0 ? (
                <div style={compactListStyle}>
                  {actionTypeRows.map((item) => {
                    const pnl = bondNumericRaw(item.total_pnl_economic);
                    return (
                      <div
                        key={item.action_type}
                        style={{ display: "flex", justifyContent: "space-between", gap: 12, paddingBottom: 10, borderBottom: "1px solid #eef2f6" }}
                      >
                        <span style={{ color: "#18314d", fontWeight: 700, fontSize: 13 }}>{item.action_type_name}</span>
                        <span style={{ color: toneColor(pnl), fontWeight: 700, fontSize: 12 }}>
                          {formatWan(item.total_pnl_economic)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <Text type="secondary">当前没有可展示的动作类型汇总。</Text>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="交易建议" style={dashboardCardStyle}>
            <div style={compactListStyle}>
              <div style={{ color: "#52657f", fontSize: 13, lineHeight: 1.7 }}>
                首页只给动作方向，不在这里塞完整模块。需要证据时，直接进入对应 drill。
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: "#314a66", lineHeight: 1.8 }}>
                <li>{Number.isFinite(dur) && dur >= 3.8 ? "先看久期和期限结构，再决定是否做久期调整。" : "先看收益率分布和期限桶，确认久期是否仍在舒适区。"}</li>
                <li>{Number.isFinite(creditWeight) && creditWeight >= 0.35 ? "信用权重偏高，优先复核利差和行业集中度。" : "信用权重可控，但仍需关注利差收窄后的回撤风险。"}</li>
                <li>{actionAttribution ? `本期动作 ${actionAttribution.total_actions} 笔，可先看动作归因再下钻明细。` : "动作归因未返回时，不在首页补造操作建议。 "}</li>
              </ul>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <Button
                  size="small"
                  type="default"
                  data-testid="bond-analysis-home-open-action-attribution"
                  onClick={() => onOpenModuleDetail?.("action-attribution")}
                >
                  打开动作归因
                </Button>
                <Button
                  size="small"
                  type="default"
                  data-testid="bond-analysis-home-open-return-decomposition"
                  onClick={() => onOpenModuleDetail?.("return-decomposition")}
                >
                  打开收益拆解
                </Button>
                <Button
                  size="small"
                  type="default"
                  data-testid="bond-analysis-home-open-credit-spread"
                  onClick={() => onOpenModuleDetail?.("credit-spread")}
                >
                  打开信用利差
                </Button>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
