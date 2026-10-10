import { Tag, Tooltip } from "antd";

import type { BalancePageCalibration } from "../api/contracts";
import { EM_DASH } from "../utils/format";
import "./CalibrationBadge.css";

export type CalibrationBadgeProps = {
  calibration?: BalancePageCalibration | null;
};

export function CalibrationBadge({ calibration }: CalibrationBadgeProps) {
  if (!calibration?.calibration_note) return null;

  const families =
    calibration.source_families?.length ?
      calibration.source_families.join("+")
    : EM_DASH;
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
        className="calibration-badge"
        color="default"
      >
        {calibration.calibration_note}
      </Tag>
    </Tooltip>
  );
}
