import { Tag } from "antd";

import type { BondTradingDeskBondSnapshot } from "../lib/bondTradingDeskPageModel";
import { EM_DASH } from "../../../utils/format";
import styles from "../BondTradingDeskPage.module.css";

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
          {snapshot.rating ? <Tag>{snapshot.rating}</Tag> : null}
          {snapshot.assetClass ? (
            <Tag color="blue">{snapshot.assetClass}</Tag>
          ) : null}
          <Tag color="default">{snapshot.coverageSource}</Tag>
        </>
      ) : (
        <span className={styles.identityMeta}>尚未命中拼装范围</span>
      )}
    </div>
  );
}
