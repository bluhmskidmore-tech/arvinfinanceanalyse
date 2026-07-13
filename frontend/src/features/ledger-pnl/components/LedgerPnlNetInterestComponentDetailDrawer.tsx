import { useQuery } from "@tanstack/react-query";
import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { useApiClient } from "../../../api/client";
import type { LedgerPnlCandidateFinancialIndicatorComponentMetricId } from "../../../api/contracts";
import { buildCandidateNetInterestComponentDetailViewModel } from "../models/candidateNetInterestComponentDetailModel";
import "./LedgerPnlNetInterestComponentDetailDrawer.css";

export type LedgerPnlNetInterestComponentSelection = {
  reportMonth: string;
  parentIdempotencyKey: string;
  metricId: LedgerPnlCandidateFinancialIndicatorComponentMetricId;
  metricName: string;
};

type Props = {
  selection: LedgerPnlNetInterestComponentSelection | null;
  onClose: () => void;
  onAfterClose: () => void;
};

function closedStateMessage(state: "invalid_contract" | "stale_parent" | "not_evaluable" | "failed") {
  if (state === "stale_parent") {
    return ["父级跨期结果已变化", "当前穿透已失效，请关闭后从最新四项贡献重新进入。"];
  }
  if (state === "not_evaluable") {
    return ["贡献项暂不可评估", "后端未形成完整三期科目证据，不把缺失行或金额补成 0。"];
  }
  if (state === "failed") {
    return ["贡献项科目勾稽失败", "后端科目合计未勾稽到父级贡献，已隐藏明细行，不作为有效解释。"];
  }
  return ["贡献项穿透契约校验失败", "响应的月份、指标、来源或金额字段不符合固定契约，已拒绝展示。"];
}

function lockLabel(lockStatus: "locked_match" | "unlocked") {
  return lockStatus === "locked_match" ? "哈希已锁定" : "来源未锁定";
}

export function LedgerPnlNetInterestComponentDetailDrawer({
  selection,
  onClose,
  onAfterClose,
}: Props) {
  const client = useApiClient();
  const open = Boolean(selection);
  const reportMonth = selection?.reportMonth ?? "";
  const parentKey = selection?.parentIdempotencyKey ?? "";
  const metricId = selection?.metricId ?? "income.interest.loan.total";
  const detailQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "candidate-financial-indicator-component-detail",
      client.mode,
      reportMonth || "__none",
      parentKey || "__none",
      metricId,
    ] as const,
    queryFn: ({ signal }) => client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      reportMonth,
      metricId,
      parentKey,
      { signal },
    ),
    enabled: open,
    retry: false,
  });
  const model = selection && detailQuery.data
    ? buildCandidateNetInterestComponentDetailViewModel(
      detailQuery.data,
      selection.reportMonth,
      selection.metricId,
      selection.parentIdempotencyKey,
    )
    : null;

  return (
    <AntDrawer
      placement="right"
      width="min(720px, 100vw)"
      open={open}
      onClose={onClose}
      afterOpenChange={(isOpen) => {
        if (!isOpen) onAfterClose();
      }}
      destroyOnHidden
      closable={false}
      rootClassName="ledger-net-interest-detail"
      data-testid="ledger-pnl-net-interest-component-detail-drawer"
      title="净息贡献项科目穿透"
      extra={(
        <AntButton type="text" onClick={onClose} aria-label="关闭净息贡献项科目穿透">
          关闭
        </AntButton>
      )}
    >
      {selection ? (
        <div className="ledger-net-interest-detail__body">
          <header className="ledger-net-interest-detail__header">
            <div>
              <span>候选净息构成 · {selection.reportMonth}</span>
              <h2>{selection.metricName}</h2>
              <code>{selection.metricId}</code>
            </div>
            <strong>亿元 · CNX</strong>
          </header>

          {detailQuery.isPending ? (
            <div className="ledger-net-interest-detail__state" role="status" aria-live="polite">
              正在读取贡献项科目穿透…
            </div>
          ) : detailQuery.isError ? (
            <div className="ledger-net-interest-detail__state ledger-net-interest-detail__state--error" role="alert">
              <strong>贡献项科目穿透读取失败</strong>
              <span>本次请求未返回可校验的后端证据，请重试。</span>
              <AntButton type="primary" onClick={() => void detailQuery.refetch()}>
                重试贡献项穿透
              </AntButton>
            </div>
          ) : model && model.state !== "available" ? (
            <div className="ledger-net-interest-detail__state ledger-net-interest-detail__state--warning" role="alert">
              <strong>{closedStateMessage(model.state)[0]}</strong>
              <span>{closedStateMessage(model.state)[1]}</span>
              <small>后端原因：{model.reason}</small>
            </div>
          ) : model?.state === "available" ? (
            <>
              <section className="ledger-net-interest-detail__summary" aria-label="贡献项后端摘要">
                <header>
                  <div>
                    <strong>{model.summary.metricName}</strong>
                    <code>{model.payload.metric_id}</code>
                  </div>
                  <div className="ledger-net-interest-detail__badges">
                    <span>{model.summary.qualityLabel}</span>
                    <span>{model.summary.footLabel}</span>
                  </div>
                </header>
                <div className="ledger-net-interest-detail__metric-grid">
                  <article><span>本月</span><strong>{model.summary.currentDisplay}</strong></article>
                  <article><span>上月</span><strong>{model.summary.previousDisplay}</strong></article>
                  <article><span>构成项变动</span><strong>{model.summary.componentDeltaDisplay}</strong></article>
                  <article><span>对净息贡献</span><strong>{model.summary.contributionDisplay}</strong></article>
                </div>
              </section>

              <section className="ledger-net-interest-detail__accounts" aria-label="贡献项科目明细">
                <div className="ledger-net-interest-detail__table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>科目代码 / 名称</th>
                        <th>本月</th>
                        <th>上月</th>
                        <th>变动</th>
                        <th>贡献</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {model.rows.map((row, index) => {
                        const rawRow = model.payload.rows[index];
                        return (
                          <tr key={row.accountCode} data-row-status={row.rowStatus}>
                            <th scope="row">
                              <code>{row.accountCode}</code>
                              <strong>{row.accountName}</strong>
                              <small>
                                规则项 {rawRow.matched_terms.map((term) => (
                                  `${term.level}:${term.code}(${term.weight})`
                                )).join(" + ")}；构成权重 {rawRow.effective_component_weight}；净息权重 {rawRow.effective_net_weight}
                              </small>
                              <details>
                                <summary>查看三期来源定位</summary>
                                <ul>
                                  {rawRow.source_evidence.map((evidence) => (
                                    <li key={evidence.month}>
                                      <strong>{evidence.month} · {evidence.ledger_file_name}</strong>
                                      <span>{evidence.sheet}!{evidence.ending_cell} · 行 {evidence.row} · 科目格 {evidence.account_code_cell}</span>
                                      <span>期末余额 {evidence.ending_yuan} 元 · {lockLabel(evidence.lock_status)}</span>
                                      <code>{evidence.ledger_sha256}</code>
                                    </li>
                                  ))}
                                </ul>
                              </details>
                            </th>
                            <td>{row.currentDisplay}</td>
                            <td>{row.previousDisplay}</td>
                            <td>{row.componentDeltaDisplay}</td>
                            <td>{row.contributionDisplay}</td>
                            <td>{row.rowStatus === "contributing" ? "计入勾稽" : "规则抵销，不计入勾稽"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              <footer className="ledger-net-interest-detail__boundary">
                <strong>期末余额恢复自然月、非贷方-借方。</strong>
                <span>本表是后端固定公式的算术贡献非规模、利率或原因归因；前端不做减法、乘法、合计、排序或勾稽复算。</span>
              </footer>
            </>
          ) : (
            <div className="ledger-net-interest-detail__state" role="status">
              未收到可展示的贡献项穿透响应。
            </div>
          )}
        </div>
      ) : null}
    </AntDrawer>
  );
}
