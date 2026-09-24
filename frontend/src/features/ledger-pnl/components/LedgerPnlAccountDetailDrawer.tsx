import { useQuery } from "@tanstack/react-query";
import { Button as AntButton, Drawer as AntDrawer } from "antd";
import { useRef } from "react";

import { useApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  LedgerMoneyValue,
  LedgerPnlAccountDetailBasisSnapshot,
  LedgerPnlAccountDetailPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type { LedgerPnlContributorSelection } from "./LedgerPnlAnalysisWorkbench";
import "./LedgerPnlAccountDetailDrawer.css";

type Props = {
  selection: LedgerPnlContributorSelection | null;
  reportDate: string;
  currency: "CNX" | "CNY";
  onClose: () => void;
  onLocate: (selection: LedgerPnlContributorSelection) => void;
};

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  const yi = String(value?.yi ?? "").trim();
  // 契约外防御：非有限数值串（如 "NaN"）按缺失占位，不把 NaN 字样透传到展示层。
  return yi && Number.isFinite(Number(yi)) ? `${yi} 亿元` : EM_DASH;
}

function formatYuan(value: LedgerMoneyValue | null | undefined) {
  const yuan = String(value?.yuan ?? "").trim();
  return yuan ? `${yuan} 元` : EM_DASH;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function isForbidden(error: unknown) {
  return /(^|\D)403(\D|$)|forbidden|无权限/i.test(errorMessage(error));
}

function formatBasisMoney(
  snapshot: LedgerPnlAccountDetailBasisSnapshot,
  basis: "CNX" | "CNY",
) {
  if (snapshot.availability[basis] !== "ready") {
    return "无数据";
  }
  return formatMoney(basis === "CNX" ? snapshot.cnx : snapshot.cny);
}

function formatBasisDifference(snapshot: LedgerPnlAccountDetailBasisSnapshot) {
  if (
    snapshot.availability.CNX !== "ready"
    || snapshot.availability.CNY !== "ready"
  ) {
    return "不可比";
  }
  return formatMoney(snapshot.cnx_minus_cny);
}

function PeriodComparison({ payload }: { payload: LedgerPnlAccountDetailPayload }) {
  const comparison = payload.period_comparison;
  return (
    <section
      className="ledger-account-detail__section"
      data-testid="ledger-pnl-account-detail-period"
    >
      <div className="ledger-account-detail__section-head">
        <div>
          <span>期间变化</span>
          <h3>本期与上一可用报告期</h3>
        </div>
        <small>{comparison.previous_report_date ?? "无上一期"}</small>
      </div>
      <div className="ledger-account-detail__metric-grid">
        <article>
          <span>本期</span>
          <strong>{formatMoney(comparison.current_monthly_pnl)}</strong>
          <small>{formatYuan(comparison.current_monthly_pnl)} · {comparison.current_evidence_rows} 行证据</small>
        </article>
        <article>
          <span>上期</span>
          <strong>{formatMoney(comparison.previous_monthly_pnl)}</strong>
          <small>{formatYuan(comparison.previous_monthly_pnl)} · {comparison.previous_evidence_rows} 行证据</small>
        </article>
        <article>
          <span>变化</span>
          <strong>{formatMoney(comparison.change)}</strong>
          <small>{formatYuan(comparison.change)} · 后端返回，前端不复算</small>
        </article>
      </div>
      <div className="ledger-account-detail__source-grid">
        <span>本期来源 {payload.source_version}</span>
        <span>上期来源 {comparison.previous_source_version ?? "无上一期来源"}</span>
      </div>
    </section>
  );
}

function BasisComparison({ payload }: { payload: LedgerPnlAccountDetailPayload }) {
  const snapshots = [
    { label: "本期", snapshot: payload.basis_comparison.current },
    { label: "上期", snapshot: payload.basis_comparison.previous },
  ];
  return (
    <section
      className="ledger-account-detail__section"
      data-testid="ledger-pnl-account-detail-basis"
    >
      <div className="ledger-account-detail__section-head">
        <div>
          <span>账务口径</span>
          <h3>CNX / CNY / CNX - CNY</h3>
        </div>
        <small>重叠口径，不可相加，差额非 FX PnL</small>
      </div>
      <div className="ledger-account-detail__table-wrap">
        <table>
          <thead>
            <tr>
              <th>期间</th>
              <th>报告日</th>
              <th>CNX</th>
              <th>CNY</th>
              <th>CNX - CNY</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map(({ label, snapshot }) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{snapshot?.report_date ?? EM_DASH}</td>
                <td>{snapshot ? formatBasisMoney(snapshot, "CNX") : "无数据"}</td>
                <td>{snapshot ? formatBasisMoney(snapshot, "CNY") : "无数据"}</td>
                <td>{snapshot ? formatBasisDifference(snapshot) : "不可比"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CanonicalEvidence({ payload }: { payload: LedgerPnlAccountDetailPayload }) {
  return (
    <section
      className="ledger-account-detail__section"
      data-testid="ledger-pnl-account-detail-evidence"
    >
      <div className="ledger-account-detail__section-head">
        <div>
          <span>总账证据</span>
          <h3>Canonical 规范化证据</h3>
        </div>
        <small>{payload.canonical_evidence_rows.length} 行</small>
      </div>
      {payload.canonical_evidence_rows.length > 0 ? (
        <div className="ledger-account-detail__table-wrap">
          <table>
            <thead>
              <tr>
                <th>期间</th>
                <th>报告日</th>
                <th>口径</th>
                <th>期初</th>
                <th>期末</th>
                <th>月损益</th>
                <th>天数</th>
              </tr>
            </thead>
            <tbody>
              {payload.canonical_evidence_rows.map((row) => (
                <tr key={`${row.period}-${row.report_date}-${row.currency}-${row.account_code}`}>
                  <td>{row.period === "current" ? "本期" : "上期"}</td>
                  <td>{row.report_date}</td>
                  <td>{row.currency}</td>
                  <td><span className="ledger-account-detail__exact-money">{formatMoney(row.beginning_balance)}<small>{formatYuan(row.beginning_balance)}</small></span></td>
                  <td><span className="ledger-account-detail__exact-money">{formatMoney(row.ending_balance)}<small>{formatYuan(row.ending_balance)}</small></span></td>
                  <td><span className="ledger-account-detail__exact-money">{formatMoney(row.monthly_pnl)}<small>{formatYuan(row.monthly_pnl)}</small></span></td>
                  <td>{row.days_in_period}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="ledger-account-detail__empty">暂无 Canonical 规范化证据行，不以 0 补齐</p>
      )}
    </section>
  );
}

function SourceStatus({ envelope }: {
  envelope: ApiEnvelope<LedgerPnlAccountDetailPayload>;
}) {
  const meta = envelope.result_meta;
  const fallback = meta.fallback_mode === "latest_snapshot";
  const stale = meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale";
  if (!fallback && !stale) {
    return null;
  }
  return (
    <div
      className="ledger-account-detail__source-status"
      data-testid="ledger-pnl-account-detail-source-status"
    >
      {fallback ? (
        <div>
          <strong>已回退至最近可用报告日</strong>
          <span>
            请求日 {meta.requested_report_date || EM_DASH} · 解析日 {meta.resolved_report_date || meta.fallback_date || EM_DASH}
          </span>
        </div>
      ) : null}
      {stale ? (
        <div>
          <strong>数据可能已过期</strong>
          <span>截至日 {meta.as_of_date || EM_DASH} · vendor {meta.vendor_status || EM_DASH}</span>
        </div>
      ) : null}
    </div>
  );
}

function hasAccountEvidence(payload: LedgerPnlAccountDetailPayload) {
  const currentBasisRows = payload.basis_comparison.current.evidence_rows;
  const previousBasisRows = payload.basis_comparison.previous?.evidence_rows;
  return payload.canonical_evidence_rows.length > 0
    || payload.period_comparison.current_evidence_rows > 0
    || payload.period_comparison.previous_evidence_rows > 0
    || currentBasisRows.CNX > 0
    || currentBasisRows.CNY > 0
    || Boolean(previousBasisRows && (previousBasisRows.CNX > 0 || previousBasisRows.CNY > 0));
}

function AccountEvidenceSections({ payload }: { payload: LedgerPnlAccountDetailPayload }) {
  return (
    <>
      <PeriodComparison payload={payload} />
      <BasisComparison payload={payload} />
      <CanonicalEvidence payload={payload} />
      <footer className="ledger-account-detail__footer">
        <span>本期来源 {payload.source_version}</span>
        <span>上期来源 {payload.period_comparison.previous_source_version ?? "无上一期来源"}</span>
        <span title={payload.calculation_basis.account_match}>精确科目匹配</span>
        <span title={payload.calculation_basis.previous_period_rule}>上一期按最近可用总账报告日</span>
        <span title={payload.calculation_basis.evidence_boundary}>Canonical 规范化证据，非源端物理凭证</span>
        <span title={payload.calculation_basis.metric_boundary}>候选非正式</span>
      </footer>
    </>
  );
}

export function LedgerPnlAccountDetailDrawer(props: Props) {
  const client = useApiClient();
  const pendingLocateRef = useRef<LedgerPnlContributorSelection | null>(null);
  const accountCode = props.selection?.account_code ?? "";
  const open = Boolean(props.selection && props.reportDate && accountCode);
  const detailQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "account-detail",
      client.mode,
      props.reportDate,
      props.currency,
      accountCode || "__none",
    ] as const,
    queryFn: () => client.getLedgerPnlAccountDetail(
      props.reportDate,
      accountCode,
      props.currency,
    ),
    enabled: open,
    retry: false,
  });
  const payload = detailQuery.data?.result;
  const accountName = payload?.account.account_name ?? props.selection?.account_name;
  const hasEvidence = payload ? hasAccountEvidence(payload) : false;
  const handleClose = () => {
    pendingLocateRef.current = null;
    props.onClose();
  };
  const handleLocate = () => {
    if (!props.selection) {
      return;
    }
    pendingLocateRef.current = {
      ...props.selection,
      account_name: payload?.account.account_name ?? props.selection.account_name,
    };
    props.onClose();
  };
  const handleOpenChange = (isOpen: boolean) => {
    if (isOpen || !pendingLocateRef.current) {
      return;
    }
    const selection = pendingLocateRef.current;
    pendingLocateRef.current = null;
    queueMicrotask(() => props.onLocate(selection));
  };

  return (
    <AntDrawer
      placement="right"
      width="min(720px, 100vw)"
      open={open}
      onClose={handleClose}
      afterOpenChange={handleOpenChange}
      destroyOnHidden
      closable={false}
      className="ledger-account-detail"
      data-testid="ledger-pnl-account-detail-drawer"
      data-moss-theme-scope="ledger-pnl"
      title="科目损益穿透"
      extra={(
        <AntButton type="text" onClick={handleClose} aria-label="关闭科目损益穿透">
          关闭
        </AntButton>
      )}
    >
      {props.selection ? (
        <div className="ledger-account-detail__body">
          <header className="ledger-account-detail__header">
            <div>
              <span>候选总账科目</span>
              <h2>{props.selection.account_code}{accountName ? ` ${accountName}` : ""}</h2>
              <p>{props.reportDate} · {props.currency}</p>
            </div>
            <span className="ledger-account-detail__badge">候选分析</span>
          </header>

          {detailQuery.data ? <SourceStatus envelope={detailQuery.data} /> : null}

          {detailQuery.isLoading ? (
            <div className="ledger-account-detail__state" role="status" aria-live="polite">
              科目穿透读取中
            </div>
          ) : detailQuery.isError ? (
            <div className="ledger-account-detail__state ledger-account-detail__state--error" role="alert">
              <strong>{isForbidden(detailQuery.error) ? "无权限读取科目穿透" : "科目穿透读取失败"}</strong>
              <span>{isForbidden(detailQuery.error) ? "当前用户缺少 ledger_pnl 读取权限。" : "本次无法读取科目穿透，请重试。"}</span>
              <AntButton type="primary" onClick={() => void detailQuery.refetch()}>
                重试科目穿透
              </AntButton>
            </div>
          ) : payload?.analysis_status === "no_data" && !hasEvidence ? (
            <div
              className="ledger-account-detail__state ledger-account-detail__state--warning"
              data-testid="ledger-pnl-account-detail-no-data"
            >
              <strong>当前报告日该科目暂无总账证据</strong>
              <span>无数据不等于 0，不形成科目变化结论。</span>
              <small>上一可用报告日 {payload.period_comparison.previous_report_date ?? "无"}</small>
            </div>
          ) : payload?.analysis_status === "no_data" ? (
            <>
              <div
                className="ledger-account-detail__state ledger-account-detail__state--warning"
                data-testid="ledger-pnl-account-detail-selected-basis-no-data"
              >
                <strong>当前选择口径 {props.currency} 暂无总账证据</strong>
                <span>无数据不等于 0；以下保留其他口径及历史期间的可用证据。</span>
              </div>
              <AccountEvidenceSections payload={payload} />
            </>
          ) : payload?.analysis_status === "ready" ? (
            <AccountEvidenceSections payload={payload} />
          ) : (
            <div className="ledger-account-detail__state ledger-account-detail__state--warning">
              未收到完整科目穿透响应，不以 0 补齐。
            </div>
          )}

          {payload?.analysis_status === "ready" ? (
            <div className="ledger-account-detail__actions">
              <AntButton type="primary" onClick={handleLocate}>
                定位下方科目明细
              </AntButton>
            </div>
          ) : null}
        </div>
      ) : null}
    </AntDrawer>
  );
}
