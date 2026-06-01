import { Tag, Tooltip } from "antd";

import type { BalancePageCalibration } from "../api/contracts";
import { designTokens } from "../theme/designSystem";

export type CalibrationBadgeProps = {
  calibration?: BalancePageCalibration | null;
};

export function CalibrationBadge({ calibration }: CalibrationBadgeProps) {
  if (!calibration?.calibration_note) return null;

  const families =
    calibration.source_families?.length ?
      calibration.source_families.join("+")
    : "—";
  const line1 =
    `范围: ${calibration.position_scope} | 币种: ${calibration.currency_basis} | ` +
    `数据源: ${families} | 基础: ${calibration.data_basis}`;
  const title = (
    <>
      {line1}
      {calibration.tyw_amount_semantics ?
        <>
          <br />
          注：同业以本金作为市值和摊余成本
        </>
      : null}
    </>
  );

  return (
    <Tooltip title={title}>
      <Tag
        color="default"
        style={{
          margin: 0,
          fontSize: 11,
          fontWeight: 500,
          borderColor: designTokens.color.neutral[200],
          color: designTokens.color.neutral[700],
          background: designTokens.color.neutral[50],
        }}
      >
        {calibration.calibration_note}
      </Tag>
    </Tooltip>
  );
}
