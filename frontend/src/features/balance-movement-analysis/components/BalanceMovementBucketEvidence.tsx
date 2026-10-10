import { Button, Descriptions } from "antd";
import type { BalanceMovementBucket, BalanceMovementPayload } from "../../../api/contracts";
import { SectionHead } from "../../../components/layout";
import tableStyles from "../../../components/layout/DataTable.module.css";
import { PageV2SurfacePanel } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import { counterpartyAmountText } from "../lib/balanceMovementReconciliationModel";
import { formatSignedYiCell, formatYiCell } from "../lib/balanceMovementPresentation";
import { PERIOD_CLOSURE_NOTE } from "../lib/balanceMovementDiagnostics";

export function BalanceMovementBucketEvidence({ result, bucket, onReturn }: {
  result: BalanceMovementPayload;
  bucket: BalanceMovementBucket;
  onReturn: () => void;
}) {
  const row = result.rows.find((item) => item.basis_bucket === bucket);
  const decomposition = result.basis_movement_decomposition;
  const accounting = decomposition?.buckets.find((item) => item.basis_bucket === bucket);
  const detailPositionBasis = result.zqtz_maturity_structure?.meta.zqtz_currency_basis
    ?? result.zqtz_concentration_analysis?.meta.zqtz_currency_basis;
  return <PageV2SurfacePanel testId="balance-movement-bucket-evidence">
    <SectionHead
      title={`${bucket} 来源复核`}
      numbered={false}
      note={`报告日 ${result.report_date} · 控制币种 ${result.currency_basis} · 金额单位：亿元`}
      actions={<Button onClick={onReturn}>返回核心对账</Button>}
    />
    {!row ? <p className="balance-movement-derived-panel__summary">该分类桶没有已返回的对账行。</p> : <>
      <Descriptions
        size="small"
        column={{ xs: 1, sm: 1, md: 2 }}
        colon={false}
        items={[
          { key: "balances", label: "期初 / 期末 / 变动", children: `${formatYiCell(row.previous_balance)} / ${formatYiCell(row.current_balance)} / ${formatSignedYiCell(row.balance_change)} 亿` },
          { key: "position-source", label: "独立头寸主链实际来源", children: row.position_source_basis ?? "未记录" },
          { key: "position-balance", label: "独立头寸余额", children: counterpartyAmountText(row, `${formatYiCell(row.zqtz_amount)} 亿`) },
          { key: "accounting-balance", label: "会计控制余额", children: `${formatYiCell(row.gl_amount)} 亿` },
          { key: "difference", label: "两侧诊断差异", children: counterpartyAmountText(row, `${formatSignedYiCell(row.reconciliation_diff)} 亿`) },
          { key: "detail-currency", label: "明细头寸币种口径", children: detailPositionBasis ?? "未返回" },
          { key: "versions", label: "来源版本 / 规则", children: `${row.source_version || EM_DASH} / ${row.rule_version || EM_DASH}` },
        ]}
      />
      <p className="balance-movement-derived-panel__caveat">主链按 CNX 优先、CNY 别名候选读取，实际命中以上述来源为准。明细使用其独立返回的币种口径；口径差异需要核对，不能据此认定真实错账。</p>
      <SectionHead title="会计控制来源" numbered={false} contentGap="tight" />
      <p className="balance-movement-derived-panel__summary">{result.accounting_controls.join("、") || "控制科目未返回"}；排除 {result.excluded_controls.join("、") || EM_DASH}</p>
      <p className="balance-movement-derived-panel__summary">{decomposition?.meta.source_tables.join("、") || "来源表未返回"} · {decomposition?.meta.source_scope || "来源范围未返回"}</p>
      <p className="balance-movement-derived-panel__summary">组件报告日 {decomposition?.meta.report_date ?? EM_DASH} / 基期 {decomposition?.meta.prior_report_date ?? EM_DASH}</p>
      {accounting ? <>
        <div className={tableStyles.root}>
          <div className={tableStyles.scroll}>
            <table className={tableStyles.table}>
              <thead><tr>
                <th className={tableStyles.headCell}>科目组件</th><th className={tableStyles.headCell}>科目规则</th>
                <th className={tableStyles.headCell} data-align="numeric">期初</th><th className={tableStyles.headCell} data-align="numeric">期末</th>
                <th className={tableStyles.headCell} data-align="numeric">变动</th><th className={tableStyles.headCell}>来源说明</th>
              </tr></thead>
              <tbody>{accounting.rows.map((component) => <tr key={component.component_key} className={tableStyles.row}>
                <th scope="row" className={tableStyles.cell}>{component.component_label}</th><td className={tableStyles.cell}>{component.account_code_pattern}</td>
                <td className={tableStyles.cell} data-align="numeric">{formatYiCell(component.previous_balance)}</td><td className={tableStyles.cell} data-align="numeric">{formatYiCell(component.current_balance)}</td>
                <td className={tableStyles.cell} data-align="numeric">{formatSignedYiCell(component.balance_change)}</td><td className={tableStyles.cell}>{component.source_note}{component.is_supported ? "" : " · 未支持"}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>
        <p className="balance-movement-derived-panel__caveat">{PERIOD_CLOSURE_NOTE}。残差 {formatSignedYiCell(accounting.residual_amount)} 亿；期末校验 {formatSignedYiCell(accounting.closing_check)} 亿。</p>
      </> : <p className="balance-movement-derived-panel__summary">本期未返回该分类桶的会计组件，页面不反推科目明细。</p>}
    </>}
  </PageV2SurfacePanel>;
}
