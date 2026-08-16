import type { AdbMonthlyDataItem } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { LiabilitySectionLead } from "./LiabilitySectionLead";

export function LiabilityNimStressMonthlyPanel({
  adbMonth,
}: {
  adbMonth: AdbMonthlyDataItem | null;
}) {
  const nim = adbMonth?.net_interest_margin;
  const projectedRaw = adbMonth?.nim_stress?.nim_stressed;
  const projected =
    projectedRaw !== null && projectedRaw !== undefined && Number.isFinite(projectedRaw)
      ? projectedRaw
      : null;
  const deltaBpRaw = adbMonth?.nim_stress?.delta_bp;
  const deltaBp =
    deltaBpRaw !== null && deltaBpRaw !== undefined && Number.isFinite(deltaBpRaw)
      ? deltaBpRaw
      : null;
  const nimNegative = nim !== null && nim !== undefined && nim < 0;
  const projectedNegative = projected !== null && projected < 0;

  return (
    <section className="liability-section">
      <LiabilitySectionLead
        title="压力测试：NIM 敏感性（+50bps）"
        actions={<span className="liability-status-pill">候选情景</span>}
      />
      <p className="liability-caption">口径：月度日均（月度收益率/付息率；若缺失则仅展示结构）。</p>
      <p className="liability-caption" data-testid="liability-nim-monthly-analysis-note">
        压力口径：当前月度 NIM −50bp 平移（后端分析口径，候选指标，与日度面板采用同一冲击幅度）；缺 NIM 的月份不展示压力值。
      </p>
      <div className="liability-kpi-band" data-cols="4">
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">资产收益率（月日均）</span>
          <span className="liability-kpi-cell__value">
            {adbMonth?.asset_yield === null || adbMonth?.asset_yield === undefined
              ? EM_DASH
              : `${adbMonth.asset_yield.toFixed(2)}%`}
          </span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">负债付息率（月日均）</span>
          <span className="liability-kpi-cell__value">
            {adbMonth?.liability_cost === null || adbMonth?.liability_cost === undefined
              ? EM_DASH
              : `${adbMonth.liability_cost.toFixed(2)}%`}
          </span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">当前 NIM（月日均）</span>
          <span className="liability-kpi-cell__value" data-tone={nimNegative ? "down" : undefined}>
            {nim === null || nim === undefined ? EM_DASH : `${nim.toFixed(2)}%`}
          </span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">压力后 NIM（+50bps）</span>
          <span className="liability-kpi-cell__value" data-tone={projectedNegative ? "down" : undefined}>
            {projected === null ? EM_DASH : `${projected.toFixed(2)}%`}
          </span>
          {/* 有意对齐 DESIGN 语义色（涨绿跌红）：冲击下行固定 --dh-api-red，不再使用旧 A股红涨绿跌。 */}
          <span className="liability-kpi-cell__note" data-tone={deltaBp === null ? "muted" : "down"}>
            {deltaBp === null
              ? `Δ ${EM_DASH}`
              : `${deltaBp} bp（负债成本 +50bps，NIM 同幅下行）`}
          </span>
        </div>
      </div>
    </section>
  );
}
