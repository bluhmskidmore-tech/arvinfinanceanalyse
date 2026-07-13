import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  buildLedgerKpiCards,
  directionLabel,
  formatLedgerYiAmount,
  formatLedgerYuanAmount,
  ledgerDataState,
  ledgerImportPresentation,
  positionRowKey,
  resolvedLedgerDate,
  selectLedgerCurrency,
  type LedgerDirectionFilter,
} from "./ledgerDashboardPageModel";
import { useLedgerImportWorkflow } from "./useLedgerImportWorkflow";
import "./LedgerDashboardPage.css";

function queryDirection(value: string | null): LedgerDirectionFilter {
  if (value === "ASSET" || value === "LIABILITY" || value === "UNCLASSIFIED") {
    return value;
  }
  return "ALL";
}

function queryDate(value: string | null) {
  return value?.trim() ?? "";
}

function queryCurrency(value: string | null) {
  return value?.trim().toUpperCase() ?? "";
}

export default function LedgerDashboardPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedDate, setSelectedDate] = useState(() => queryDate(searchParams.get("as_of_date")));
  const direction = queryDirection(searchParams.get("direction"));
  const ledgerImport = useLedgerImportWorkflow(client);

  function updateDirection(nextDirection: LedgerDirectionFilter, replace = false) {
    const next = new URLSearchParams(searchParams);
    if (nextDirection === "ALL") {
      next.delete("direction");
    } else {
      next.set("direction", nextDirection);
    }
    setSearchParams(next, { replace });
  }

  const datesQuery = useQuery({
    queryKey: ["bank-ledger", "dates", client.mode],
    queryFn: () => client.getLedgerDates(),
    retry: false,
  });

  const dates = useMemo(() => datesQuery.data?.data.items ?? [], [datesQuery.data?.data.items]);

  useEffect(() => {
    const fromQuery = queryDate(searchParams.get("as_of_date"));
    if (fromQuery) {
      setSelectedDate((current) => (current === fromQuery ? current : fromQuery));
      return;
    }
    const latest = dates[0];
    if (latest && !selectedDate) {
      setSelectedDate(latest);
    }
  }, [dates, searchParams, selectedDate]);


  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (selectedDate) {
      next.set("as_of_date", selectedDate);
    } else {
      next.delete("as_of_date");
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, selectedDate, setSearchParams]);

  const dashboardQuery = useQuery({
    queryKey: ["bank-ledger", "dashboard", client.mode, selectedDate],
    enabled: Boolean(selectedDate),
    queryFn: () => client.getLedgerDashboard(selectedDate),
    retry: false,
  });

  const dashboard = dashboardQuery.data;
  const currencies = useMemo(
    () => dashboard?.data.currency_breakdown.map((item) => item.currency).sort() ?? [],
    [dashboard?.data.currency_breakdown],
  );
  const requestedCurrency = queryCurrency(searchParams.get("currency"));
  const selectedCurrency = selectLedgerCurrency(
    dashboard?.data.currency_breakdown ?? [],
    requestedCurrency,
  );

  useEffect(() => {
    if (currencies.length === 0 || !selectedCurrency || requestedCurrency === selectedCurrency) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("currency", selectedCurrency);
    setSearchParams(next, { replace: true });
  }, [currencies.length, requestedCurrency, searchParams, selectedCurrency, setSearchParams]);

  const classificationStatus = dashboard?.data.classification_status;
  const classificationReady = classificationStatus === "ready";
  const unclassifiedDirectionBlocked = direction === "UNCLASSIFIED" && !classificationReady;
  const normalizeUnclassifiedDirection =
    direction === "UNCLASSIFIED" && classificationStatus != null && !classificationReady;

  useEffect(() => {
    if (!normalizeUnclassifiedDirection) return;
    const next = new URLSearchParams(searchParams);
    next.delete("direction");
    setSearchParams(next, { replace: true });
  }, [normalizeUnclassifiedDirection, searchParams, setSearchParams]);

  const positionsQuery = useQuery({
    queryKey: ["bank-ledger", "positions", client.mode, selectedDate, selectedCurrency, direction],
    enabled: Boolean(selectedDate && selectedCurrency && !unclassifiedDirectionBlocked),
    queryFn: () =>
      client.getLedgerPositions({
        asOfDate: selectedDate,
        currency: selectedCurrency,
        direction: direction === "ALL" ? undefined : direction,
        page: 1,
        pageSize: 20,
      }),
    retry: false,
  });

  const positions = unclassifiedDirectionBlocked ? undefined : positionsQuery.data;
  const cards = buildLedgerKpiCards(dashboard?.data, selectedCurrency);
  const selectedBucket = dashboard?.data.currency_breakdown.find(
    (item) => item.currency === selectedCurrency,
  );
  const pageError = dashboardQuery.error ?? (!selectedDate ? datesQuery.error : null);
  const state = ledgerDataState(
    dashboard?.metadata ?? datesQuery.data?.metadata,
    pageError,
  );
  const positionsState = ledgerDataState(positions?.metadata, positionsQuery.error);
  const actualDate = resolvedLedgerDate(dashboard?.trace, dashboard?.data.as_of_date);
  const requestedDate = dashboard?.trace.requested_as_of_date ?? selectedDate;
  const positionsActualDate = resolvedLedgerDate(positions?.trace);
  const positionsRequestedDate = positions?.trace.requested_as_of_date ?? selectedDate;
  const importPresentation = ledgerImport.run
    ? ledgerImportPresentation(ledgerImport.run.status)
    : null;

  return (
    <section className="ledger-dashboard" data-testid="ledger-dashboard-page">
      <header className="ledger-dashboard__header">
        <div>
          <p className="ledger-dashboard__eyebrow">Bank Ledger</p>
          <h1>银行台账驾驶舱</h1>
          <p className="ledger-dashboard__subtitle">
            {actualDate ? `数据日期 ${actualDate}` : "等待可用台账日期"}
          </p>
        </div>
        <div className="ledger-dashboard__mode">
          {client.mode === "real" ? "真实传输 · 候选读模型" : "本地演示 · 候选读模型"}
        </div>
      </header>

      <section
        className="ledger-dashboard__governance-boundary"
        data-testid="ledger-dashboard-governance-boundary"
        aria-label="Ledger governance boundary"
      >
        <strong>{"candidate · imported position_snapshot · not for formal use"}</strong>
        <span>{"Currency buckets are independent native amounts / 100m with no FX conversion. Classification v2 is import-time only; unmatched pairs are UNCLASSIFIED and legacy batches fail closed. Historical backfill completed for live batches 1-8; golden sample captured-awaiting-approval. UNKNOWN remediation, owner approval, and authorized real-page UAT remain pending."}</span>
      </section>
      <div className="ledger-dashboard__toolbar">
        <label className="ledger-dashboard__field">
          <span>日期</span>
          <select
            aria-label="ledger-dashboard-as-of-date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            disabled={dates.length === 0 && !selectedDate}
          >
            {selectedDate && !dates.includes(selectedDate) ? (
              <option value={selectedDate}>{selectedDate}</option>
            ) : null}
            {dates.length === 0 ? <option value="">暂无可选日期</option> : null}
            {dates.map((date) => (
              <option key={date} value={date}>
                {date}
              </option>
            ))}
          </select>
        </label>

        <label className="ledger-dashboard__field">
          <span>Currency</span>
          <select
            aria-label="ledger-dashboard-currency"
            value={selectedCurrency}
            onChange={(event) => {
              const next = new URLSearchParams(searchParams);
              next.set("currency", event.target.value);
              setSearchParams(next);
            }}
            disabled={currencies.length === 0}
          >
            {currencies.length === 0 ? <option value="">--</option> : null}
            {currencies.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
          </select>
        </label>
        <div className="ledger-dashboard__segmented" role="group" aria-label="ledger-dashboard-direction">
          {(["ALL", "ASSET", "LIABILITY", "UNCLASSIFIED"] as LedgerDirectionFilter[]).map((item) => (
            <button
              key={item}
              type="button"
              className={direction === item ? "is-active" : ""}
              onClick={() => updateDirection(item)}
              disabled={!classificationReady && item === "UNCLASSIFIED"}
            >
              {directionLabel(item)}
            </button>
          ))}
        </div>
      </div>

      <section className="ledger-dashboard__import" aria-labelledby="ledger-import-title">
        <div className="ledger-dashboard__import-copy">
          <p className="ledger-dashboard__eyebrow">Operational workflow</p>
          <h2 id="ledger-import-title">导入台账</h2>
          <p>候选台账导入证据，不构成正式余额或正式 PnL。支持 .csv、.xls、.xlsx，最大 16 MiB。</p>
        </div>
        <div className="ledger-dashboard__import-controls">
          <label className="ledger-dashboard__file-field">
            <span>台账文件</span>
            <input
              type="file"
              accept=".csv,.xls,.xlsx"
              disabled={ledgerImport.isPending || ledgerImport.isSubmitting}
              onChange={(event) => ledgerImport.chooseFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="button"
            className="ledger-dashboard__import-submit"
            disabled={
              ledgerImport.isPending ||
              ledgerImport.isSubmitting ||
              !ledgerImport.file ||
              Boolean(ledgerImport.submissionError)
            }
            onClick={() => void ledgerImport.submit()}
          >
            {ledgerImport.isPending || ledgerImport.isSubmitting ? "正在导入" : "开始导入"}
          </button>
        </div>
        {ledgerImport.file ? (
          <p className="ledger-dashboard__selected-file">已选择：{ledgerImport.file.name}</p>
        ) : null}
        {ledgerImport.submissionError ? (
          <div className="ledger-dashboard__import-error" role="alert">
            {ledgerImport.submissionError}
          </div>
        ) : null}
        {ledgerImport.run && importPresentation ? (
          <div
            className={`ledger-dashboard__import-status ledger-dashboard__import-status--${importPresentation.tone}`}
            data-testid="ledger-import-status"
            role={ledgerImport.run.status === "failed" ? "alert" : "status"}
            aria-live="polite"
          >
            <strong>{importPresentation.label}</strong>
            <span>文件 {ledgerImport.run.file_name}</span>
            <span>run_id {ledgerImport.run.run_id}</span>
            {ledgerImport.run.batch_id != null ? <span>batch_id {ledgerImport.run.batch_id}</span> : null}
            {ledgerImport.run.duplicate_of_batch_id != null ? (
              <span>duplicate_of_batch_id {ledgerImport.run.duplicate_of_batch_id}</span>
            ) : null}
            {ledgerImport.run.queued_at ? <span>queued_at {ledgerImport.run.queued_at}</span> : null}
            {ledgerImport.run.started_at ? <span>started_at {ledgerImport.run.started_at}</span> : null}
            {ledgerImport.run.finished_at ? <span>finished_at {ledgerImport.run.finished_at}</span> : null}
            {ledgerImport.run.error_category ? (
              <span>error_category {ledgerImport.run.error_category}</span>
            ) : null}
            {ledgerImport.run.error_message ? <span>{ledgerImport.run.error_message}</span> : null}
          </div>
        ) : null}
        {ledgerImport.pollingError ? (
          <div className="ledger-dashboard__import-confirmation-error" role="alert">
            <span>{ledgerImport.pollingError}</span>
            {ledgerImport.run ? (
              <button type="button" onClick={ledgerImport.retryStatus}>
                继续查询
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      {datesQuery.isLoading || dashboardQuery.isLoading ? (
        <div className="ledger-dashboard__status" data-testid="ledger-dashboard-loading">
          加载中
        </div>
      ) : null}

      {state !== "ready" ? (
        <div
          className={`ledger-dashboard__status ledger-dashboard__status--${state}`}
          data-testid="ledger-dashboard-status"
        >
          {state === "loading_failure"
            ? "加载失败"
            : state === "no_data"
              ? "暂无数据"
              : state === "fallback"
                ? `已回退到 ${actualDate ?? "--"}`
                : `数据截至 ${actualDate ?? "--"}`}
          {requestedDate && actualDate && requestedDate !== actualDate ? (
            <span> 请求日期 {requestedDate}</span>
          ) : null}
        </div>
      ) : null}

      <div className="ledger-dashboard__kpis" data-testid="ledger-dashboard-kpis">
        {cards.map((card) => (
          <article
            key={card.key}
            className="ledger-dashboard__kpi"
            data-testid={`ledger-dashboard-kpi-${card.key}`}
          >
            <div>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.detail}</small>
            </div>
            <button type="button" onClick={() => updateDirection(card.direction)}>
              明细
            </button>
          </article>
        ))}
      </div>

      <section className="ledger-dashboard__panel" data-testid="ledger-dashboard-classification-quality">
        <div className="ledger-dashboard__panel-head">
          <div>
            <h2>分类质量</h2>
            {!selectedBucket ? (
              <p>暂无可评估分类质量。</p>
            ) : classificationStatus === "legacy_unassessed" ? (
              <p>旧规则批次不可评估；资产、负债和净敞口已 fail closed 显示为 --。</p>
            ) : classificationStatus === "invalid_materialization" ? (
              <p>物化方向非法；资产、负债、净敞口和分类质量已 fail closed。</p>
            ) : (
              <p>
                覆盖率 {selectedBucket.classification_coverage_pct?.toFixed(2) ?? "--"}% ·
                未分类 {selectedBucket.unclassified_row_count ?? "--"} 行 ·
                {formatLedgerYiAmount(selectedBucket.unclassified_face_amount, selectedCurrency)}
              </p>
            )}
          </div>
          {classificationReady && selectedBucket ? (
            <button type="button" onClick={() => updateDirection("UNCLASSIFIED")}>
              查看未分类明细
            </button>
          ) : null}
        </div>
      </section>
      <section className="ledger-dashboard__panel" data-testid="ledger-dashboard-positions-panel">
        <div className="ledger-dashboard__panel-head">
          <div>
            <h2>持仓明细</h2>
            <p>
              {directionLabel(direction)} · {positions?.data.total ?? 0} 条
            </p>
          </div>
        </div>

        <div className="ledger-dashboard__table-wrap">
          {positionsQuery.isLoading ? (
            <div className="ledger-dashboard__panel-status">明细加载中</div>
          ) : null}
          {!positionsQuery.isLoading && positionsState !== "ready" ? (
            <div
              className={`ledger-dashboard__panel-status ledger-dashboard__panel-status--${positionsState}`}
              data-testid="ledger-dashboard-positions-status"
            >
              {positionsState === "loading_failure"
                ? "明细加载失败"
                : positionsState === "no_data"
                  ? "明细暂无数据"
                  : positionsState === "fallback"
                    ? `明细已回退到 ${positionsActualDate ?? "--"}`
                    : `明细数据截至 ${positionsActualDate ?? "--"}`}
              {positionsRequestedDate && positionsActualDate && positionsRequestedDate !== positionsActualDate ? (
                <span> 请求日期 {positionsRequestedDate}</span>
              ) : null}
            </div>
          ) : null}
          <table data-testid="ledger-dashboard-positions-table">
            <thead>
              <tr>
                <th>position_key</th>
                <th>方向</th>
                <th>债券代码</th>
                <th>组合</th>
                <th>币种</th>
                <th>账户类别</th>
                <th>资产分类</th>
                <th>面值（原币）</th>
                <th>batch_id</th>
                <th>row_no</th>
              </tr>
            </thead>
            <tbody>
              {(positions?.data.items ?? []).map((item) => (
                <tr key={positionRowKey(item)}>
                  <td>{item.position_key}</td>
                  <td>{item.direction}</td>
                  <td>{item.bond_code}</td>
                  <td>{item.portfolio || "--"}</td>
                  <td>{item.currency || "--"}</td>
                  <td>{item.account_category_std || "--"}</td>
                  <td>{item.asset_class_std || "--"}</td>
                  <td className="ledger-dashboard__num">{formatLedgerYuanAmount(item.face_amount)}</td>
                  <td>{item.batch_id}</td>
                  <td>{item.row_no}</td>
                </tr>
              ))}
              {positions && positions.data.items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="ledger-dashboard__empty">
                    暂无匹配明细
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="ledger-dashboard__evidence" data-testid="ledger-dashboard-evidence">
        <article>
          <h2>metadata</h2>
          <dl>
            <dt>source_version</dt>
            <dd>{dashboard?.metadata.source_version ?? datesQuery.data?.metadata.source_version ?? "--"}</dd>
            <dt>rule_version</dt>
            <dd>{dashboard?.metadata.rule_version ?? datesQuery.data?.metadata.rule_version ?? "--"}</dd>
            <dt>batch_id</dt>
            <dd>{dashboard?.metadata.batch_id ?? datesQuery.data?.metadata.batch_id ?? "--"}</dd>
            <dt>stale</dt>
            <dd>{String(dashboard?.metadata.stale ?? false)}</dd>
            <dt>fallback</dt>
            <dd>{String(dashboard?.metadata.fallback ?? false)}</dd>
            <dt>no_data</dt>
            <dd>{String(dashboard?.metadata.no_data ?? datesQuery.data?.metadata.no_data ?? false)}</dd>
          </dl>
        </article>
        <article>
          <h2>trace</h2>
          <dl>
            <dt>request_id</dt>
            <dd>{dashboard?.trace.request_id ?? "--"}</dd>
            <dt>requested_as_of_date</dt>
            <dd>{requestedDate || "--"}</dd>
            <dt>resolved_as_of_date</dt>
            <dd>{actualDate ?? "--"}</dd>
            <dt>positions_filter</dt>
            <dd>{`${selectedCurrency || "--"} / ${direction === "ALL" ? "ALL" : direction}`}</dd>
          </dl>
        </article>
        <article>
          <h2>positions trace</h2>
          <dl>
            <dt>request_id</dt>
            <dd>{positions?.trace.request_id ?? "--"}</dd>
            <dt>requested_as_of_date</dt>
            <dd>{positionsRequestedDate || "--"}</dd>
            <dt>resolved_as_of_date</dt>
            <dd>{positionsActualDate ?? "--"}</dd>
            <dt>stale</dt>
            <dd>{String(positions?.metadata.stale ?? false)}</dd>
            <dt>fallback</dt>
            <dd>{String(positions?.metadata.fallback ?? false)}</dd>
            <dt>no_data</dt>
            <dd>{String(positions?.metadata.no_data ?? false)}</dd>
          </dl>
        </article>
      </section>
    </section>
  );
}
