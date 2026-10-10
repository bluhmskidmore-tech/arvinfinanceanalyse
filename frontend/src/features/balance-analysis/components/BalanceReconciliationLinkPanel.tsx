import { EM_DASH } from "../../../utils/format";
import {
  buildBalanceReconciliationLinkModel,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
} from "../pages/balanceAnalysisPageModel";

function withYiUnit(value: string): string {
  return value === EM_DASH ? value : `${value} 亿`;
}

function formatSignedBalanceYuanToYi(value: number | null): string {
  if (value === null) {
    return EM_DASH;
  }
  const formatted = formatBalanceAmountToYiFromYuan(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function renderReconciliationMetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="balance-analysis-reconciliation__tile">
      <span className="balance-analysis-reconciliation__tile-label">{label}</span>
      <strong className="balance-analysis-reconciliation__tile-value">
        {value}
      </strong>
      <span className="balance-analysis-reconciliation__tile-detail">{detail}</span>
    </div>
  );
}

export function renderBalanceReconciliationLinkPanel(
  model: ReturnType<typeof buildBalanceReconciliationLinkModel>,
) {
  const failedInternalCheck = model.internalChecks.find((check) => !check.aligned);
  const bridgeDetail = model.bridgeComponents
    .map((component) => `${component.label} ${withYiUnit(formatBalanceAmountToYiFromYuan(component.amountYuan))}`)
    .join(" · ");

  return (
    <section data-testid="balance-analysis-reconciliation-link" className="balance-analysis-reconciliation">
      <div className="balance-analysis-reconciliation__header">
        <div>
          <h3 className="balance-analysis-reconciliation__title">口径联动核对</h3>
          <p className="balance-analysis-reconciliation__copy">
            从 workbook 原币面值出发，桥接到 Formal CNY 的 AC/OCI/TPL，再落到余额变动 CNX 控制数。
          </p>
        </div>
        <span className={`balance-analysis-reconciliation__status balance-analysis-reconciliation__status--${model.status}`}>
          {model.statusLabel}
        </span>
      </div>
      <div className="balance-analysis-reconciliation__grid">
        {renderReconciliationMetricTile({
          label: "工作簿自校验",
          value: model.allInternalChecksAligned ? "已对齐" : "待复核",
          detail: failedInternalCheck
            ? `${failedInternalCheck.label}：${failedInternalCheck.leftLabel} 与 ${failedInternalCheck.rightLabel} 不一致`
            : "债券业务、评级、期限债券和发行类切片已回到同一组卡片值。",
        })}
        {renderReconciliationMetricTile({
          label: "Workbook 原币资产",
          value: withYiUnit(formatBalanceAmountToYiFromWan(model.workbookAssetTotalWan)),
          detail: `债券资产 ${withYiUnit(formatBalanceAmountToYiFromWan(model.workbookBondWan))}，期限缺口 ${withYiUnit(formatBalanceAmountToYiFromWan(model.workbookGapWan))}`,
        })}
        {renderReconciliationMetricTile({
          label: "Formal CNY 桥",
          value: withYiUnit(formatBalanceAmountToYiFromYuan(model.formalBridgeYuan)),
          detail: bridgeDetail || "等待口径拆解返回 AC/OCI/TPL 分桶。",
        })}
        {renderReconciliationMetricTile({
          label: "余额变动 CNX",
          value: withYiUnit(formatBalanceAmountToYiFromYuan(model.movementControlYuan)),
          detail: `残差 ${withYiUnit(formatSignedBalanceYuanToYi(model.residualYuan))}；${model.statusDetail}`,
        })}
      </div>
      <div className="balance-analysis-reconciliation__footer">
        <a href={model.movementHref} className="balance-analysis-reconciliation__link">
          打开余额变动核对
        </a>
        <span className="balance-analysis-reconciliation__footnote">
          全口径缺口 {withYiUnit(formatBalanceAmountToYiFromWan(model.workbookFullScopeGapWan))}
        </span>
      </div>
    </section>
  );
}
