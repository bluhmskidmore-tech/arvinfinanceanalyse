import { useState } from "react";
import { type PnlByBusinessYtdUnallocatedBreakdownRow, type PnlByBusinessYtdUnallocatedItem } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { numeric, formatPnlWan } from "./pnlByBusinessDisplay";

const UNALLOCATED_REASON_LABELS = {
  no_business_rule_match: "未命中业务分类规则",
  detail_only_business_rule_match: "仅命中其中项，未命中父级分类",
} as const;

export function UnallocatedPnlPanel({
  breakdown,
  items,
  totalPnl,
  totalAbsPnl,
  rowCount,
  testIdPrefix = "pnl-by-business-unallocated",
  evidenceComplete = true,
}: {
  breakdown: PnlByBusinessYtdUnallocatedBreakdownRow[] | undefined;
  items: PnlByBusinessYtdUnallocatedItem[] | undefined;
  totalPnl: string | undefined;
  totalAbsPnl: string | undefined;
  rowCount: number | undefined;
  testIdPrefix?: string;
  evidenceComplete?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const count = rowCount ?? items?.length ?? 0;
  const visibleItems = (items ?? []).slice(0, 100);
  const hasUnallocated = count > 0 || (numeric(totalPnl) ?? 0) !== 0 || (numeric(totalAbsPnl) ?? 0) !== 0;

  if (!hasUnallocated) {
    return null;
  }

  return (
    <section className="pnl-by-business-unallocated-panel" data-testid={`${testIdPrefix}-panel`}>
      <button
        type="button"
        className="pnl-by-business-unallocated-toggle"
        data-testid={`${testIdPrefix}-toggle`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>查看未分类明细</span>
        <span>
          {count} 条 · 净额 {formatPnlWan(totalPnl)} 万元 · 绝对金额 {formatPnlWan(totalAbsPnl)} 万元
        </span>
      </button>
      {open ? (
        <div className="pnl-by-business-unallocated-body">
          <p className="pnl-by-business-unallocated-note">
            以下展示原始来源字段与未命中原因，需结合产品类别和来源信息核对业务归属。
          </p>
          {(breakdown?.length ?? 0) > 0 ? (
            <div className="pnl-by-business-table-shell" data-testid={`${testIdPrefix}-breakdown-table`}>
              <table className="pnl-by-business-table">
                <thead>
                  <tr>
                    <th>未命中原因</th>
                    <th>来源</th>
                    <th>原始类型</th>
                    <th>会计分类</th>
                    <th>组合</th>
                    <th>成本中心</th>
                    <th>条数</th>
                    <th>净额（万元）</th>
                    <th>绝对金额（万元）</th>
                    <th>示例证券</th>
                  </tr>
                </thead>
                <tbody>
                  {(breakdown ?? []).map((row) => (
                    <tr
                      key={`${row.reason_code}:${row.source_kind}:${row.invest_type_std}:${row.accounting_basis}:${row.portfolio_name}:${row.cost_center}`}
                    >
                      <td>{UNALLOCATED_REASON_LABELS[row.reason_code]}</td>
                      <td>{row.source_kind || EM_DASH}</td>
                      <td>{row.invest_type_std || EM_DASH}</td>
                      <td>{row.accounting_basis || EM_DASH}</td>
                      <td>{row.portfolio_name || EM_DASH}</td>
                      <td>{row.cost_center || EM_DASH}</td>
                      <td>{row.pnl_row_count}</td>
                      <td>{formatPnlWan(row.total_pnl)}</td>
                      <td>{formatPnlWan(row.abs_pnl)}</td>
                      <td>{row.sample_instrument_codes.join("、") || EM_DASH}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="pnl-by-business-unallocated-note">汇总已返回，分组诊断明细待返回。</p>
          )}
          {(items?.length ?? 0) > 0 ? (
            <>
              <div className="pnl-by-business-unallocated-heading">
                <h3>逐笔证据</h3>
                <p>
                  {evidenceComplete && (items?.length ?? 0) === count
                    ? `页面显示前 ${visibleItems.length} 条；Excel 导出包含全部 ${count} 条。`
                    : `接口已返回 ${items?.length ?? 0}/${count} 条；Excel 导出包含已返回的全部 ${items?.length ?? 0} 条。`}
                </p>
              </div>
              <div className="pnl-by-business-table-shell" data-testid={`${testIdPrefix}-items-table`}>
                <table className="pnl-by-business-table">
                  <thead>
                    <tr>
                      <th>报表日</th>
                      <th>证券代码</th>
                      <th>原始类型</th>
                      <th>来源</th>
                      <th>组合</th>
                      <th>成本中心</th>
                      <th>会计分类</th>
                      <th>币种</th>
                      <th>损益（万元）</th>
                      <th>未命中原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.map((item, index) => (
                      <tr
                        key={`${item.report_date}:${item.source_kind}:${item.instrument_code}:${item.portfolio_name}:${item.cost_center}:${index}`}
                      >
                        <td>{item.report_date || EM_DASH}</td>
                        <td>{item.instrument_code || EM_DASH}</td>
                        <td>{item.invest_type_std || EM_DASH}</td>
                        <td>{item.source_kind || EM_DASH}</td>
                        <td>{item.portfolio_name || EM_DASH}</td>
                        <td>{item.cost_center || EM_DASH}</td>
                        <td>{item.accounting_basis || EM_DASH}</td>
                        <td>{item.currency_basis || EM_DASH}</td>
                        <td>{formatPnlWan(item.total_pnl)}</td>
                        <td>{UNALLOCATED_REASON_LABELS[item.reason_code]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="pnl-by-business-unallocated-note">未分类汇总已返回，逐笔明细待返回。</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
