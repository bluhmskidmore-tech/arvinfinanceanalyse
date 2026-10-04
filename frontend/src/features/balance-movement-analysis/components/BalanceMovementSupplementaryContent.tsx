import { EM_DASH } from "../../../utils/format";
import { StructureShareDetailTable } from "./BalanceStructureEvolution";
import type { BalanceMovementPayload } from "../../../api/contracts";
import type { HistoricalAnomalyDiagnostics } from "../lib/balanceMovementDiagnostics";
import {
  formatSignedYiCell,
  formatYiCell,
  formatYiFixed,
  formatSignedYiNumber,
} from "../lib/balanceMovementPresentation";
import { SupplementaryBusinessRowsTable } from "./BalanceMovementBusinessTables";
import type { BalanceMovementViewModel } from "../hooks/useBalanceMovementViewModel";
import type { ApiEnvelope } from "../../../api/contracts";

function HistoricalAnomalyPanel({
  diagnostics,
}: {
  diagnostics: HistoricalAnomalyDiagnostics;
}) {
  const sampleLabel =
    diagnostics.sampleCount > 0 ? `仅 ${diagnostics.sampleCount} 期样本` : "暂无历史样本";
  const hasBaseline = diagnostics.baselinePairCount > 0;
  return (
    <section
      className="balance-movement-anomaly-panel"
      data-testid="balance-movement-analysis-anomaly-diagnostics"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>历史异常定位</span>
          <h2>{diagnostics.headline}</h2>
        </div>
        <strong>{hasBaseline ? `近 ${diagnostics.baselinePairCount} 期常态` : sampleLabel}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">
        页面诊断提示，不是正式风险指标；只用现有趋势 payload 比较本期变动与最近历史变动，不反推交易动作。
      </p>
      <div className="balance-movement-anomaly-grid">
        <div className="balance-movement-anomaly-card">
          <span>AC / OCI / TPL 异常判断</span>
          {hasBaseline ? (
            diagnostics.accountingSignals.length > 0 ? (
              <ul className="balance-movement-anomaly-list">
                {diagnostics.accountingSignals.map((signal) => (
                  <li key={signal.bucket}>
                    <strong>{signal.bucket}</strong>
                    <span>{signal.headline}</span>
                    <p>
                      本期 {formatSignedYiCell(signal.currentDelta)} 亿；近 {signal.baselineCount} 期平均{" "}
                      {signal.baselineAverageAbs === null ? EM_DASH : `${formatYiCell(signal.baselineAverageAbs)} 亿`}
                      {signal.directionReversal ? "；方向反转" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p>未发现高于历史常态的 AC / OCI / TPL 单桶变动。</p>
            )
          ) : (
            <p>历史样本不足，{sampleLabel}，暂不判断异常。</p>
          )}
        </div>
        <div className="balance-movement-anomaly-card">
          <span>业务品类异常榜</span>
          {hasBaseline ? (
            diagnostics.businessSignals.length > 0 ? (
              <ul className="balance-movement-anomaly-list">
                {diagnostics.businessSignals.map((signal) => (
                  <li key={signal.label}>
                    <strong>{signal.label}</strong>
                    <span>{formatSignedYiCell(signal.currentDelta)} 亿</span>
                    <p>
                      高于近 {signal.baselineCount} 期常态；历史平均{" "}
                      {signal.baselineAverageAbs === null ? EM_DASH : `${formatYiCell(signal.baselineAverageAbs)} 亿`}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p>未发现高于历史常态的业务品类变动。</p>
            )
          ) : (
            <p>历史样本不足，{sampleLabel}，先看本期 Top 变动。</p>
          )}
        </div>
      </div>
    </section>
  );
}

type BalanceMovementSupplementaryContentProps = Pick<
  BalanceMovementViewModel,
    "governanceMeta"
  | "businessMatrixMonths"
  | "businessMatrixAssetRows"
  | "structureShareTableRows"
  | "shareRowByReportMonth"
  | "zqtzCalibrationAnalysis"
  | "historicalAnomalyDiagnostics"
> & { detailData: ApiEnvelope<BalanceMovementPayload> | undefined };

export function BalanceMovementSupplementaryContent({
  detailData,
  governanceMeta,
  businessMatrixMonths,
  businessMatrixAssetRows,
  structureShareTableRows,
  shareRowByReportMonth,
  zqtzCalibrationAnalysis,
  historicalAnomalyDiagnostics,
}: BalanceMovementSupplementaryContentProps) {
  return (
    <>
      {detailData?.result.accounting_controls ? (
        <div
          data-testid="balance-movement-analysis-controls"
          className="balance-movement-accounting-controls"
        >
          控制科目：{detailData.result.accounting_controls.join(", ")}；排除：
          {detailData.result.excluded_controls.join(", ")}
        </div>
      ) : null}
      {detailData?.result ? (
        <div
          data-testid="balance-movement-analysis-governance"
          className="balance-movement-governance-line"
        >
          读模型报告日：{governanceMeta.reportDate || EM_DASH}
          {" · "}规则版本：
          {governanceMeta.ruleVersions.length
            ? governanceMeta.ruleVersions.join("、")
            : EM_DASH}
          <br />
          源版本：
          {governanceMeta.sourceVersions.length
            ? governanceMeta.sourceVersions.join("、")
            : EM_DASH}
        </div>
      ) : null}
      <SupplementaryBusinessRowsTable
        months={businessMatrixMonths}
        rows={businessMatrixAssetRows}
      />
      <StructureShareDetailTable
        structureShareTableRows={structureShareTableRows}
        shareRowByReportMonth={shareRowByReportMonth}
      />
      {zqtzCalibrationAnalysis ? (
        <section
          data-testid="balance-movement-analysis-zqtz-calibration"
          className="balance-movement-zqtz-calibration"
        >
          <div className="balance-movement-zqtz-calibration__header">
            <div>
              <span>ZQTZ228 口径核对</span>
              <strong>{zqtzCalibrationAnalysis.source_file}</strong>
            </div>
            <p>{zqtzCalibrationAnalysis.conclusion}</p>
          </div>
          <div className="balance-movement-zqtz-calibration__diagnosis">
            <div>
              <span>差异定位</span>
              <p>{zqtzCalibrationAnalysis.root_cause}</p>
            </div>
            <div>
              <span>系统处理</span>
              <p>{zqtzCalibrationAnalysis.remediation}</p>
            </div>
          </div>
          <div className="balance-movement-zqtz-calibration__table-wrap">
            <table className="balance-movement-zqtz-calibration__table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>系统数（亿元）</th>
                  <th>核对表（亿元）</th>
                  <th>差异（亿元）</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {zqtzCalibrationAnalysis.items.map((item) => (
                  <tr key={item.row_key}>
                    <td>
                      <strong>{item.row_label}</strong>
                      <span>{item.note}</span>
                    </td>
                    <td>{formatYiFixed(item.system_amount)}</td>
                    <td>{formatYiFixed(item.reference_amount)}</td>
                    <td>{formatSignedYiNumber(Number(item.diff_amount) / 100000000)}</td>
                    <td>
                      <span
                        className={`balance-movement-zqtz-calibration__status balance-movement-zqtz-calibration__status--${item.status}`}
                      >
                        {item.status === "matched" ? "一致" : "观察"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="balance-movement-zqtz-calibration__risks">
            {zqtzCalibrationAnalysis.residual_risks.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {detailData ? (
        <HistoricalAnomalyPanel diagnostics={historicalAnomalyDiagnostics} />
      ) : null}
    </>
  );
}
