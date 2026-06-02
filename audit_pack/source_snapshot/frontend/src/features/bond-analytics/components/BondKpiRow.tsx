import { Card, Col, Row, Spin } from "antd";

import type { BondDashboardHeadlinePayload, BondPortfolioHeadlinesPayload, Numeric } from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import { formatPct, formatYi, toneColor } from "../utils/formatters";

function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return Number.isFinite(n) ? n : Number.NaN;
}

function relRatioLine(label: string, prevRaw: Numeric | null | undefined, curRaw: Numeric | null | undefined): string | null {
  const p = numOr(prevRaw);
  const c = numOr(curRaw);
  if (!Number.isFinite(p) || p === 0 || !Number.isFinite(c)) return null;
  const pct = ((c - p) / p) * 100;
  return `${label} ${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function spreadBpFoot(curRaw: Numeric | null | undefined, prevRaw: Numeric | null | undefined): string | null {
  const c = numOr(curRaw);
  if (!Number.isFinite(c)) return null;
  const curBp = c < 0.5 ? c * 10000 : c;
  if (prevRaw == null) {
    return `最新 ${curBp.toFixed(1)} bp`;
  }
  const p = numOr(prevRaw);
  if (!Number.isFinite(p)) return `最新 ${curBp.toFixed(1)} bp`;
  const prevBp = p < 0.5 ? p * 10000 : p;
  const d = curBp - prevBp;
  return `较上期 ${d >= 0 ? "+" : ""}${d.toFixed(1)} bp · 最新 ${curBp.toFixed(1)} bp`;
}

function Tile({
  label,
  value,
  foot,
  valueColor,
}: {
  label: string;
  value: string;
  foot?: string | null;
  valueColor?: string;
}) {
  return (
    <Card
      size="small"
      style={{
        borderRadius: designTokens.radius.lg,
        borderColor: designTokens.color.neutral[200],
        height: "100%",
      }}
    >
      <div
        style={{
          fontSize: designTokens.fontSize[11],
          color: designTokens.color.neutral[600],
          fontWeight: 700,
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: designTokens.fontSize[20],
          fontWeight: 700,
          marginTop: designTokens.space[2],
          color: valueColor ?? designTokens.color.neutral[900],
          ...tabularNumsStyle,
        }}
      >
        {value}
      </div>
      {foot ? (
        <div
          style={{
            fontSize: designTokens.fontSize[12],
            color: designTokens.color.neutral[700],
            marginTop: designTokens.space[2],
            lineHeight: designTokens.lineHeight.snug,
          }}
        >
          {foot}
        </div>
      ) : null}
    </Card>
  );
}

export interface BondKpiRowProps {
  headline: BondDashboardHeadlinePayload | undefined;
  portfolioHeadlines: BondPortfolioHeadlinesPayload | undefined;
  loading: boolean;
}

export function BondKpiRow({ headline, portfolioHeadlines, loading }: BondKpiRowProps) {
  if (loading) {
    return <Spin style={{ display: "block", margin: `${designTokens.space[6]}px auto` }} />;
  }
  if (!headline) return null;

  const k = headline.kpis;
  const p = headline.prev_kpis;
  const warnCount = portfolioHeadlines?.warnings?.length ?? 0;

  const mvFoot = p ? relRatioLine("较上期", p.total_market_value, k.total_market_value) : null;
  const pnlFoot = p ? relRatioLine("较上期", p.unrealized_pnl, k.unrealized_pnl) : null;
  const ytmFoot =
    p && Number.isFinite(numOr(k.weighted_ytm)) && Number.isFinite(numOr(p.weighted_ytm))
      ? `较上期 ${((numOr(k.weighted_ytm) - numOr(p.weighted_ytm)) * 10000).toFixed(2)} bp`
      : null;
  const dur = numOr(k.weighted_duration);
  const durFoot =
    p && Number.isFinite(dur) && Number.isFinite(numOr(p.weighted_duration))
      ? `较上期 ${(dur - numOr(p.weighted_duration)).toFixed(2)} 年`
      : null;
  const cpnFoot =
    p && Number.isFinite(numOr(k.weighted_coupon)) && Number.isFinite(numOr(p.weighted_coupon))
      ? `较上期 ${((numOr(k.weighted_coupon) - numOr(p.weighted_coupon)) * 100).toFixed(2)} 百分点`
      : null;

  const sprFoot = spreadBpFoot(k.credit_spread_median, p?.credit_spread_median);

  const pnlNum = numOr(k.unrealized_pnl);
  const pnlColor = Number.isFinite(pnlNum) ? toneColor(pnlNum) : undefined;

  const spreadMedian = numOr(k.credit_spread_median);
  const spreadLabel = Number.isFinite(spreadMedian)
    ? `${(spreadMedian < 0.5 ? spreadMedian * 10000 : spreadMedian).toFixed(1)} bp`
    : "—";

  return (
    <Row gutter={[designTokens.space[3], designTokens.space[3]]}>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="债券持仓规模" value={formatYi(k.total_market_value)} foot={mvFoot} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="浮动盈亏" value={formatYi(k.unrealized_pnl)} foot={pnlFoot} valueColor={pnlColor} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="加权到期收益率" value={formatPct(k.weighted_ytm)} foot={ytmFoot} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="加权久期" value={Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"} foot={durFoot} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="平均票息" value={formatPct(k.weighted_coupon)} foot={cpnFoot} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="信用利差中位数" value={spreadLabel} foot={sprFoot} />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="逾期余额" value="—" foot="待接入报送口径字段" />
      </Col>
      <Col xs={24} sm={12} md={12} lg={6}>
        <Tile label="异常预警" value={`${warnCount} 个`} foot="较上期 —（无历史序列）" />
      </Col>
    </Row>
  );
}
