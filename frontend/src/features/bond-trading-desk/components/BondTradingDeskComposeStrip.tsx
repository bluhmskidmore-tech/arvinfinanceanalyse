import { Tag } from "antd";

import { DataStatusStrip } from "../../../components/page/PagePrimitives";
import type { BondTradingDeskComposeSourceStatus } from "../lib/bondTradingDeskPageModel";
import styles from "../BondTradingDeskPage.module.css";

export function BondTradingDeskComposeStrip({
  statuses,
  partialFailure,
}: {
  statuses: BondTradingDeskComposeSourceStatus[];
  partialFailure: boolean;
}) {
  return (
    <DataStatusStrip testId="bond-trading-desk-compose-strip">
      <div className={styles.composeStrip}>
        <span className={styles.composeStripLabel}>
          拼装来源{partialFailure ? "（部分失败，已用可用读面）" : ""}
        </span>
        {statuses.map((item) => {
          const qualityWarning =
            item.status === "ready" &&
            ((item.qualityFlag && item.qualityFlag !== "ok") ||
              (item.fallbackMode && item.fallbackMode !== "none"));
          return (
            <Tag
              key={item.key}
              data-testid={`bond-trading-desk-compose-${item.key}`}
              color={item.status === "failed" ? "error" : qualityWarning ? "warning" : "success"}
              title={item.detail}
            >
              {item.label}：{item.status === "ready" ? item.detail : "失败"}
            </Tag>
          );
        })}
      </div>
    </DataStatusStrip>
  );
}
