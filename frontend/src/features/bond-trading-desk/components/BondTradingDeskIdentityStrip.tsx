import type { BondTradingDeskBondSnapshot } from "../lib/bondTradingDeskPageModel";
import { EM_DASH } from "../../../utils/format";
import styles from "../BondTradingDeskPage.module.css";

/** 资产类别后端枚举 → 中文展示；未登记枚举原样透出（原文进 title）。 */
const ASSET_CLASS_LABELS: Record<string, string> = {
  rate: "利率债",
  credit: "信用债",
};

/** 拼装来源 token → 中文展示。 */
const COVERAGE_SOURCE_LABELS: Record<string, string> = {
  top_holdings: "重仓来源",
  positions: "持仓来源",
  credit_spread: "利差来源",
  none: "未命中",
};

function IdentityTag({
  raw,
  display,
  accent = false,
}: {
  raw: string;
  display: string;
  accent?: boolean;
}) {
  return (
    <span
      className={accent ? `${styles.identityTag} ${styles.identityTagAccent}` : styles.identityTag}
      title={display !== raw ? raw : undefined}
    >
      {display}
    </span>
  );
}

export function BondTradingDeskIdentityStrip({
  bondCode,
  snapshot,
}: {
  bondCode: string;
  snapshot: BondTradingDeskBondSnapshot | null;
}) {
  return (
    <div data-testid="bond-trading-desk-identity" className={styles.identityStrip}>
      <span className={styles.identityCode}>{bondCode || EM_DASH}</span>
      {snapshot ? (
        <>
          <span className={styles.identityMeta}>{snapshot.bondName ?? "名称待返回"}</span>
          {snapshot.issuerName ? (
            <span className={styles.identityMeta}>发行人：{snapshot.issuerName}</span>
          ) : null}
          {snapshot.rating ? (
            <IdentityTag raw={snapshot.rating} display={snapshot.rating} />
          ) : null}
          {snapshot.assetClass ? (
            <IdentityTag
              raw={snapshot.assetClass}
              display={ASSET_CLASS_LABELS[snapshot.assetClass] ?? snapshot.assetClass}
              accent
            />
          ) : null}
          <IdentityTag
            raw={snapshot.coverageSource}
            display={COVERAGE_SOURCE_LABELS[snapshot.coverageSource] ?? snapshot.coverageSource}
          />
        </>
      ) : (
        <span className={styles.identityMeta}>尚未命中拼装范围</span>
      )}
    </div>
  );
}
