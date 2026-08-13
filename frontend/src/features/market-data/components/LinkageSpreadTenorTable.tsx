import { Spin } from "antd";

import type { MacroBondLinkageTopCorrelation } from "../../../api/contracts";

import { tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { correlationStrength, formatCorrelation } from "../lib/marketDataLinkageFormat";
import { LinkageDirectionPill } from "./LinkageDirectionPill";

export type SpreadTenorSlot = {
  tenor: string;
  point: MacroBondLinkageTopCorrelation | null;
};

type LinkageSpreadTenorCardsProps = {
  slots: SpreadTenorSlot[];
  loading?: boolean;
  testIdPrefix?: string;
  emptySeriesLabel?: string;
};

export function LinkageSpreadTenorCards({
  slots,
  loading = false,
  testIdPrefix = "market-data-macro-spread-slot",
  emptySeriesLabel = EM_DASH,
}: LinkageSpreadTenorCardsProps) {
  if (loading) {
    return (
      <div className="market-data-spread-tenor-loading">
        <Spin size="small" />
      </div>
    );
  }

  return (
    <div className="market-data-spread-tenor-grid">
      {slots.map((slot) => {
        const point = slot.point;
        const corrStrength = correlationStrength(point?.correlation_1y);
        return (
          <article
            key={slot.tenor}
            data-testid={`${testIdPrefix}-${slot.tenor}`}
            className="market-data-spread-tenor-card"
            data-has-data={point ? "true" : "false"}
          >
            <header className="market-data-spread-tenor-card__head">
              <span className="market-data-spread-tenor-card__tenor">{slot.tenor}</span>
              <span className="market-data-spread-tenor-card__family">credit_spread</span>
            </header>
            <p className="market-data-spread-tenor-card__series" title={point?.series_name ?? undefined}>
              {point?.series_name ?? emptySeriesLabel}
            </p>
            <dl className="market-data-spread-tenor-card__metrics">
              <div>
                <dt>corr 1Y</dt>
                <dd style={tabularNumsStyle} data-strength={corrStrength}>
                  {point ? formatCorrelation(point.correlation_1y) : EM_DASH}
                </dd>
              </div>
              <div>
                <dt>lead/lag</dt>
                <dd style={tabularNumsStyle}>{point ? `${point.lead_lag_days} 天` : EM_DASH}</dd>
              </div>
              <div>
                <dt>方向</dt>
                <dd className="market-data-spread-tenor-card__direction">
                  {point ? <LinkageDirectionPill direction={point.direction} /> : EM_DASH}
                </dd>
              </div>
            </dl>
          </article>
        );
      })}
    </div>
  );
}

export function LinkageSpreadTenorTable({
  slots,
  loading,
}: {
  slots: SpreadTenorSlot[];
  loading?: boolean;
}) {
  return (
    <section data-testid="market-data-linkage-spread-table" className="market-data-spread-tenor-panel">
      <div className="market-data-spread-tenor-head">
        <div>
          <h2 className="market-data-spread-tenor-title">信用利差</h2>
          <p className="market-data-spread-tenor-lede">
            按 3Y / 5Y / 10Y 期限槽位展示 credit_spread 联动；无数据时显示「—」。
          </p>
        </div>
        <span className="market-data-spread-tenor-badge">结构化维度</span>
      </div>
      <LinkageSpreadTenorCards slots={slots} loading={loading} />
    </section>
  );
}
