import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
import { EM_DASH } from "../../../utils/format";
import { dailyNimStressFromKpi } from "../utils/nimStress";
import { LiabilitySectionLead } from "./LiabilitySectionLead";

/** 有意对齐 DESIGN 语义色（涨绿跌红），不再使用旧 A股红涨绿跌。 */
function deltaTone(deltaBp: number | null): "up" | "down" | "muted" | "ink" {
  if (deltaBp === null || !Number.isFinite(deltaBp)) {
    return "muted";
  }
  if (deltaBp > 0) {
    return "up";
  }
  if (deltaBp < 0) {
    return "down";
  }
  return "ink";
}

export function LiabilityNimStressPanel({
  yieldKpi,
  gapNote,
}: {
  yieldKpi: LiabilityYieldKpi | null;
  /** 负债收益读面整组缺失时的区头一次性披露（§6），由页面统一判定后传入。 */
  gapNote?: string | null;
}) {
  const stress = dailyNimStressFromKpi(yieldKpi);
  const deltaBpRaw = stress.deltaBp?.raw ?? null;
  const bpText = stress.deltaBp?.display ?? EM_DASH;
  const nimNegative =
    stress.nim?.raw !== null && stress.nim?.raw !== undefined && stress.nim.raw < 0;
  const projectedNegative =
    stress.projected?.raw !== null &&
    stress.projected?.raw !== undefined &&
    stress.projected.raw < 0;

  return (
    <section className="liability-section">
      <LiabilitySectionLead
        title="压力测试：NIM 敏感性（+50bps）"
        actions={<span className="liability-status-pill">候选情景</span>}
      />
      {gapNote ? <p className="liability-caption liability-caption--gap">{gapNote}</p> : null}
      <p className="liability-caption">
        口径：资产收益率减金融市场同业负债成本（全口径同业往来 + 发行同业存单）；冲击为负债成本 +50bps。
      </p>
      <div className="liability-kpi-band" data-cols="4">
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">资产收益率</span>
          <span className="liability-kpi-cell__value">{stress.ay?.display ?? EM_DASH}</span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">金融市场同业负债成本</span>
          <span className="liability-kpi-cell__value">{stress.mlc?.display ?? EM_DASH}</span>
          <span className="liability-kpi-cell__note">（增值税前）</span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">当前 NIM</span>
          <span className="liability-kpi-cell__value" data-tone={nimNegative ? "down" : undefined}>
            {stress.nim?.display ?? EM_DASH}
          </span>
        </div>
        <div className="liability-kpi-cell">
          <span className="liability-kpi-cell__label">压力后 NIM（+50bps）</span>
          <span className="liability-kpi-cell__value" data-tone={projectedNegative ? "down" : undefined}>
            {stress.projected?.display ?? EM_DASH}
          </span>
          <span className="liability-kpi-cell__note" data-tone={deltaTone(deltaBpRaw)}>
            变化 {bpText}
          </span>
        </div>
      </div>
    </section>
  );
}
