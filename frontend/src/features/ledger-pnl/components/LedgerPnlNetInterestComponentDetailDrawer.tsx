import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { useApiClient } from "../../../api/client";
import type { LedgerPnlCandidateFinancialIndicatorComponentMetricId } from "../../../api/contracts";
import {
  buildCandidateNetInterestComponentDetailCsv,
  buildCandidateNetInterestComponentSourceLocator,
  downloadCandidateNetInterestComponentDetailCsv,
} from "../models/candidateNetInterestComponentDetailExport";
import {
  buildCandidateNetInterestComponentDetailViewModel,
  filterCandidateNetInterestComponentDetailRows,
  type CandidateNetInterestComponentDetailRowStatusFilter,
  type CandidateNetInterestComponentDetailViewModel,
} from "../models/candidateNetInterestComponentDetailModel";
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

type AvailableComponentDetailModel = Extract<
  CandidateNetInterestComponentDetailViewModel,
  { state: "available" }
>;

const CLIPBOARD_FEEDBACK_TIMEOUT_MS = 1_500;

type CopyFeedback = {
  state: "success" | "failure" | "unconfirmed";
  backendPosition: number;
  accountCode: string;
  month: string;
  locator: string;
} | null;

function AvailableComponentDetailContent({
  model,
  copyFeedback,
  copyPending,
  onCopySourceLocator,
}: {
  model: AvailableComponentDetailModel;
  copyFeedback: CopyFeedback;
  copyPending: boolean;
  onCopySourceLocator: (
    row: AvailableComponentDetailModel["rows"][number],
    evidence: AvailableComponentDetailModel["rows"][number]["sourceEvidence"][number],
  ) => void;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<CandidateNetInterestComponentDetailRowStatusFilter>(
    "all",
  );
  const filteredRows = filterCandidateNetInterestComponentDetailRows(model.rows, {
    query: searchQuery,
    status: statusFilter,
  });
  const filtersActive = searchQuery.length > 0 || statusFilter !== "all";

  const resetFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
  };

  const exportCurrentView = () => {
    downloadCandidateNetInterestComponentDetailCsv(
      buildCandidateNetInterestComponentDetailCsv(model, filteredRows, {
        query: searchQuery,
        status: statusFilter,
      }),
    );
  };

  return (
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

      <section className="ledger-net-interest-detail__analysis" aria-labelledby="ledger-net-interest-business-question">
        <div className="ledger-net-interest-detail__analysis-heading">
          <div>
            <h3 id="ledger-net-interest-business-question">
              哪些科目按后端贡献影响顺序影响该净息构成项？
            </h3>
            <p>后端已完成贡献影响排序：计入勾稽优先，再按贡献绝对值降序和科目代码排列；前端仅保序筛选。</p>
          </div>
          <strong className="ledger-net-interest-detail__candidate-warning">
            候选分析，不可用于正式使用
          </strong>
        </div>
        <div className="ledger-net-interest-detail__toolbar">
          <label>
            <span>搜索科目代码或名称</span>
            <input
              type="search"
              aria-label="搜索科目代码或名称"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.currentTarget.value)}
              placeholder="输入代码或名称"
            />
          </label>
          <label>
            <span>科目状态</span>
            <select
              aria-label="科目状态"
              value={statusFilter}
              onChange={(event) => setStatusFilter(
                event.currentTarget.value as CandidateNetInterestComponentDetailRowStatusFilter,
              )}
            >
              <option value="all">全部</option>
              <option value="contributing">计入勾稽</option>
              <option value="excluded_offset">规则抵销</option>
            </select>
          </label>
          <span className="ledger-net-interest-detail__count" aria-live="polite">
            当前 {filteredRows.length} / 共 {model.rows.length} 条
          </span>
          <AntButton onClick={resetFilters} disabled={!filtersActive}>重置条件</AntButton>
          <AntButton
            type="primary"
            onClick={exportCurrentView}
            disabled={filteredRows.length === 0}
          >
            导出当前视图
          </AntButton>
        </div>
        <small className="ledger-net-interest-detail__narrow-hint">
          窄屏可横向滚动查看完整金额、状态和来源字段。
        </small>
      </section>

      <section className="ledger-net-interest-detail__accounts" aria-label="贡献项科目明细">
        {filteredRows.length === 0 ? (
          <div className="ledger-net-interest-detail__empty" role="status">
            <strong>当前筛选没有匹配科目</strong>
            <span>当前视图未将缺失科目补成 0，也不会回退展示未筛选行。</span>
            <AntButton onClick={resetFilters}>重置筛选</AntButton>
          </div>
        ) : (
          <div className="ledger-net-interest-detail__table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">科目代码 / 名称</th>
                  <th scope="col">本月</th>
                  <th scope="col">上月</th>
                  <th scope="col">变动</th>
                  <th scope="col">贡献</th>
                  <th scope="col">状态</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr
                    key={`${row.backendPosition}-${row.accountCode}`}
                    data-row-status={row.rowStatus}
                  >
                    <th scope="row">
                      <span className="ledger-net-interest-detail__position">
                        {row.rowStatus === "contributing" ? "后端贡献序位" : "后端原始位置"} #{row.backendPosition}
                      </span>
                      <code>{row.accountCode}</code>
                      <strong>{row.accountName}</strong>
                      <small>
                        规则项 {row.matchedTerms.map((term) => (
                          `${term.level}:${term.code}(${term.weight})`
                        )).join(" + ")}；构成权重 {row.effectiveComponentWeight}；净息权重 {row.effectiveNetWeight}
                      </small>
                      <details>
                        <summary>查看三期来源定位</summary>
                        <ul>
                          {row.sourceEvidence.map((evidence) => (
                            <li key={`${evidence.month}-${evidence.row}-${evidence.ending_cell}`}>
                              <strong>{evidence.month} · {evidence.ledger_file_name}</strong>
                              <span>{evidence.sheet}!{evidence.ending_cell} · 行 {evidence.row} · 科目格 {evidence.account_code_cell}</span>
                              <span>期末余额 {evidence.ending_yuan} 元 · {lockLabel(evidence.lock_status)}</span>
                              <code>{evidence.ledger_sha256}</code>
                              <AntButton
                                size="small"
                                type="link"
                                aria-label={`复制定位 后端位置 #${row.backendPosition} ${row.accountCode} ${evidence.month}`}
                                disabled={copyPending}
                                onClick={() => onCopySourceLocator(row, evidence)}
                              >
                                复制定位
                              </AntButton>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </th>
                    <td className="ledger-net-interest-detail__numeric">{row.currentDisplay}</td>
                    <td className="ledger-net-interest-detail__numeric">{row.previousDisplay}</td>
                    <td className="ledger-net-interest-detail__numeric">{row.componentDeltaDisplay}</td>
                    <td className="ledger-net-interest-detail__numeric">{row.contributionDisplay}</td>
                    <td>{row.rowStatus === "contributing" ? "计入勾稽" : "规则抵销，不计入勾稽"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div
        className="ledger-net-interest-detail__copy-feedback"
        role="status"
        aria-label="来源定位复制反馈"
        aria-live="polite"
      >
        {copyFeedback?.state === "success"
          ? `已复制 后端位置 #${copyFeedback.backendPosition} · ${copyFeedback.accountCode} · ${copyFeedback.month} 来源定位`
          : copyFeedback?.state === "failure"
            ? `复制失败，请手工复制 后端位置 #${copyFeedback.backendPosition} · ${copyFeedback.accountCode} · ${copyFeedback.month} 来源定位`
            : copyFeedback?.state === "unconfirmed"
              ? `复制结果未确认，请手工复制 后端位置 #${copyFeedback.backendPosition} · ${copyFeedback.accountCode} · ${copyFeedback.month} 来源定位`
            : null}
      </div>
      {copyFeedback?.state === "failure" || copyFeedback?.state === "unconfirmed" ? (
        <label className="ledger-net-interest-detail__manual-copy">
          <span>后端位置 #{copyFeedback.backendPosition} · {copyFeedback.accountCode} · {copyFeedback.month} 来源定位文本</span>
          <textarea
            aria-label={`后端位置 ${copyFeedback.backendPosition} ${copyFeedback.accountCode} ${copyFeedback.month} 来源定位文本`}
            readOnly
            value={copyFeedback.locator}
            onFocus={(event) => event.currentTarget.select()}
          />
        </label>
      ) : null}

      <footer className="ledger-net-interest-detail__boundary">
        <strong>期末余额恢复自然月、非贷方-借方。</strong>
        <span>本表是后端固定公式的算术贡献非规模、利率或原因归因；前端不做减法、乘法、合计、排序或勾稽复算。</span>
      </footer>
    </>
  );
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
  const selectionIdentity = selection
    ? `${selection.reportMonth}-${selection.metricId}-${selection.parentIdempotencyKey}`
    : "__none";
  const [copyFeedback, setCopyFeedback] = useState<CopyFeedback>(null);
  const [copyPending, setCopyPending] = useState(false);
  const copyPendingRef = useRef(false);
  const mountedRef = useRef(true);
  const activeSelectionIdentityRef = useRef(selectionIdentity);
  activeSelectionIdentityRef.current = selectionIdentity;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setCopyFeedback(null);
  }, [selectionIdentity]);

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

  const copySourceLocator = async (
    copyModel: AvailableComponentDetailModel,
    row: AvailableComponentDetailModel["rows"][number],
    evidence: AvailableComponentDetailModel["rows"][number]["sourceEvidence"][number],
  ) => {
    if (copyPendingRef.current) return;
    copyPendingRef.current = true;
    setCopyPending(true);
    setCopyFeedback(null);
    const requestSelectionIdentity = selectionIdentity;
    const locator = buildCandidateNetInterestComponentSourceLocator(copyModel, row, evidence);
    const feedbackFor = (state: NonNullable<CopyFeedback>["state"]): CopyFeedback => ({
      state,
      backendPosition: row.backendPosition,
      accountCode: row.accountCode,
      month: evidence.month,
      locator,
    });
    const requestIsCurrent = () => (
      mountedRef.current
      && activeSelectionIdentityRef.current === requestSelectionIdentity
    );
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    try {
      const clipboard = globalThis.navigator?.clipboard;
      if (!clipboard?.writeText) throw new Error("clipboard unavailable");
      const write = clipboard.writeText(locator);
      timeoutId = setTimeout(() => {
        if (requestIsCurrent()) setCopyFeedback(feedbackFor("unconfirmed"));
      }, CLIPBOARD_FEEDBACK_TIMEOUT_MS);
      await write;
      if (requestIsCurrent()) setCopyFeedback(feedbackFor("success"));
    } catch {
      if (requestIsCurrent()) setCopyFeedback(feedbackFor("failure"));
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
      copyPendingRef.current = false;
      if (mountedRef.current) setCopyPending(false);
    }
  };

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
      data-moss-theme-scope="ledger-pnl"
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
            <AvailableComponentDetailContent
              key={`${selection.reportMonth}-${selection.metricId}-${selection.parentIdempotencyKey}`}
              model={model}
              copyFeedback={copyFeedback}
              copyPending={copyPending}
              onCopySourceLocator={(row, evidence) => {
                void copySourceLocator(model, row, evidence);
              }}
            />
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
