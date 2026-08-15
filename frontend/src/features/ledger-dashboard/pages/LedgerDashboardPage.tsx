import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { workbenchNavigation } from "../../../app/navigation";
import { EM_DASH } from "../../../utils/format";
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

function ledgerBoolLabel(value: boolean | undefined): string {
  return value ? "是" : "否";
}

/** 「无数据 否」双重否定难读：无数据回退按事件表述（发生/未发生）。 */
function ledgerNoDataLabel(value: boolean | undefined): string {
  return value ? "发生" : "未发生";
}

/**
 * 英文治理记录原文（证据引用）：与外壳横幅共用 navigation 单一来源；
 * 横幅已收敛为中文摘要（governanceBanner），原文在页内默认折叠展示。
 */
const LEDGER_GOVERNANCE_NOTE_ORIGINAL =
  workbenchNavigation.find((section) => section.key === "bank-ledger-dashboard")?.readinessNote ?? "";

function ledgerMissingValue<T>(value: T | null | undefined): T | typeof EM_DASH {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  return value;
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
  const pageErrorMessage =
    pageError instanceof Error && pageError.message ? pageError.message : null;
  const positionsErrorMessage =
    positionsQuery.error instanceof Error && positionsQuery.error.message
      ? positionsQuery.error.message
      : null;
  const retryPageLoad = () => {
    if (datesQuery.isError) {
      void datesQuery.refetch();
    }
    if (selectedDate && dashboardQuery.isError) {
      void dashboardQuery.refetch();
    }
  };
  const positionsState = ledgerDataState(positions?.metadata, positionsQuery.error);
  const actualDate = resolvedLedgerDate(dashboard?.trace, dashboard?.data.as_of_date);
  const requestedDate = dashboard?.trace.requested_as_of_date ?? selectedDate;
  const positionsActualDate = resolvedLedgerDate(positions?.trace);
  const positionsRequestedDate = positions?.trace.requested_as_of_date ?? selectedDate;
  const importPresentation = ledgerImport.run
    ? ledgerImportPresentation(ledgerImport.run.status)
    : null;

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 独占，页根只声明 Nocturne scope 与
   * theme-dh-api：再写一次 data-moss-theme="dark" 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      className="ledger-dashboard theme-dh-api"
      data-testid="ledger-dashboard-page"
      data-moss-theme-scope="bank-ledger-dashboard"
    >
      <header className="ledger-dashboard__header">
        <div>
          <p className="ledger-dashboard__eyebrow">银行台账</p>
          <h1>银行台账驾驶舱</h1>
          <p className="ledger-dashboard__subtitle">
            {actualDate ? `数据日期 ${actualDate}` : "等待可用台账日期"}
          </p>
        </div>
        {/* 候选未获批准：徽标走琥珀而非绿色，避免与治理语义相悖（§4）。 */}
        <div className="ledger-dashboard__mode">
          {client.mode === "real" ? "候选读模型 · 真实链路" : "候选读模型 · 本地演示"}
        </div>
      </header>

      {/*
       * 候选口径/未批准/UNCLASSIFIED 已由外壳治理横幅（中文摘要）陈述，
       * 本卡只保留口径与回填进度事实，英文治理记录原文默认折叠（证据引用）。
       */}
      <section
        className="ledger-dashboard__governance-boundary"
        data-testid="ledger-dashboard-governance-boundary"
        aria-label="台账治理边界"
      >
        <strong>候选导入 position_snapshot（非正式口径）</strong>
        <span>
          各币种桶为独立原币金额（亿元），不做外汇折算。线上批次 1-8 历史回填已完成；golden sample 待审批，UNKNOWN 修复与授权真页 UAT 待完成。
        </span>
        {LEDGER_GOVERNANCE_NOTE_ORIGINAL ? (
          <details className="ledger-dashboard__governance-original">
            <summary>治理记录原文（英文）</summary>
            <p>{LEDGER_GOVERNANCE_NOTE_ORIGINAL}</p>
          </details>
        ) : null}
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
          <span>币种</span>
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
            {currencies.length === 0 ? <option value="">{EM_DASH}</option> : null}
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
          <p className="ledger-dashboard__eyebrow">导入流程</p>
          <h2 id="ledger-import-title">导入台账</h2>
          <p>候选台账导入证据，不构成正式余额或正式 PnL。支持 .csv、.xls、.xlsx，最大 16 MiB。</p>
        </div>
        <div className="ledger-dashboard__import-controls">
          {/* 原生 file input 控件文案随浏览器语言（Choose File 等）：视觉按钮改自绘中文，input 仅保留语义与焦点。 */}
          <label className="ledger-dashboard__file-field">
            <span>台账文件</span>
            <span className="ledger-dashboard__file-control">
              <input
                type="file"
                className="ledger-dashboard__file-input"
                aria-label="台账文件"
                accept=".csv,.xls,.xlsx"
                disabled={ledgerImport.isPending || ledgerImport.isSubmitting}
                onChange={(event) => ledgerImport.chooseFile(event.target.files?.[0] ?? null)}
              />
              <span className="ledger-dashboard__file-button" aria-hidden="true">
                {ledgerImport.file ? "重新选择文件" : "选择文件"}
              </span>
            </span>
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
          {state === "loading_failure" ? (
            <div className="ledger-dashboard__status-failure" role="alert">
              <strong>{pageErrorMessage ? `加载失败：${pageErrorMessage}` : "加载失败"}</strong>
              <span className="ledger-dashboard__status-scope">
                影响范围：KPI、分类质量与持仓明细暂不可用。
              </span>
              <button type="button" className="ledger-dashboard__status-retry" onClick={retryPageLoad}>
                重试
              </button>
            </div>
          ) : (
            <>
              {state === "no_data"
                ? "暂无数据"
                : state === "fallback"
                  ? `已回退到 ${actualDate ?? EM_DASH}`
                  : `数据截至 ${actualDate ?? EM_DASH}`}
              {requestedDate && actualDate && requestedDate !== actualDate ? (
                <span> 请求日期 {requestedDate}</span>
              ) : null}
            </>
          )}
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
              <p>旧规则批次不可评估；资产、负债和净敞口已 fail closed 显示为 {EM_DASH}。</p>
            ) : classificationStatus === "invalid_materialization" ? (
              <p>物化方向非法；资产、负债、净敞口和分类质量已 fail closed。</p>
            ) : (
              <p>
                覆盖率 {selectedBucket.classification_coverage_pct?.toFixed(2) ?? EM_DASH}%
                ，未分类 {selectedBucket.unclassified_row_count ?? EM_DASH} 行（
                {formatLedgerYiAmount(selectedBucket.unclassified_face_amount, selectedCurrency)}
                ）
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
                ? `明细加载失败${positionsErrorMessage ? `：${positionsErrorMessage}` : ""}`
                : positionsState === "no_data"
                  ? "明细暂无数据"
                  : positionsState === "fallback"
                    ? `明细已回退到 ${positionsActualDate ?? EM_DASH}`
                    : `明细数据截至 ${positionsActualDate ?? EM_DASH}`}
              {positionsRequestedDate && positionsActualDate && positionsRequestedDate !== positionsActualDate ? (
                <span> 请求日期 {positionsRequestedDate}</span>
              ) : null}
            </div>
          ) : null}
          <table data-testid="ledger-dashboard-positions-table">
            <thead>
              {/* 列名中文化；接口字段名收进 title 作证据引用（§7）。 */}
              <tr>
                <th title="position_key">持仓键</th>
                <th>方向</th>
                <th>债券代码</th>
                <th>组合</th>
                <th>币种</th>
                <th>账户类别</th>
                <th>资产分类</th>
                <th>面值（原币）</th>
                <th title="batch_id">批次号</th>
                <th title="row_no">行号</th>
              </tr>
            </thead>
            <tbody>
              {(positions?.data.items ?? []).map((item) => (
                <tr key={positionRowKey(item)}>
                  <td>{item.position_key}</td>
                  <td>{item.direction}</td>
                  <td>{item.bond_code}</td>
                  <td>{item.portfolio || EM_DASH}</td>
                  <td>{item.currency || EM_DASH}</td>
                  <td>{item.account_category_std || EM_DASH}</td>
                  <td>{item.asset_class_std || EM_DASH}</td>
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
          <h2>元数据</h2>
          <dl>
            <dt>source_version</dt>
            <dd>{ledgerMissingValue(dashboard?.metadata.source_version ?? datesQuery.data?.metadata.source_version)}</dd>
            <dt>rule_version</dt>
            <dd>{ledgerMissingValue(dashboard?.metadata.rule_version ?? datesQuery.data?.metadata.rule_version)}</dd>
            <dt>batch_id</dt>
            <dd>{ledgerMissingValue(dashboard?.metadata.batch_id ?? datesQuery.data?.metadata.batch_id)}</dd>
            <dt>数据延迟</dt>
            <dd>{ledgerBoolLabel(dashboard?.metadata.stale)}</dd>
            <dt>已回退</dt>
            <dd>{ledgerBoolLabel(dashboard?.metadata.fallback)}</dd>
            <dt title="no_data">无数据回退</dt>
            <dd>{ledgerNoDataLabel(dashboard?.metadata.no_data ?? datesQuery.data?.metadata.no_data)}</dd>
          </dl>
        </article>
        <article>
          <h2>溯源</h2>
          <dl>
            <dt>request_id</dt>
            <dd>{ledgerMissingValue(dashboard?.trace.request_id)}</dd>
            <dt>requested_as_of_date</dt>
            <dd>{ledgerMissingValue(requestedDate)}</dd>
            <dt>resolved_as_of_date</dt>
            <dd>{ledgerMissingValue(actualDate)}</dd>
            <dt>positions_filter</dt>
            <dd>{`${ledgerMissingValue(selectedCurrency)} / ${direction === "ALL" ? "ALL" : direction}`}</dd>
          </dl>
        </article>
        <article>
          <h2>持仓溯源</h2>
          <dl>
            <dt>request_id</dt>
            <dd>{ledgerMissingValue(positions?.trace.request_id)}</dd>
            <dt>requested_as_of_date</dt>
            <dd>{ledgerMissingValue(positionsRequestedDate)}</dd>
            <dt>resolved_as_of_date</dt>
            <dd>{ledgerMissingValue(positionsActualDate)}</dd>
            <dt>数据延迟</dt>
            <dd>{ledgerBoolLabel(positions?.metadata.stale)}</dd>
            <dt>已回退</dt>
            <dd>{ledgerBoolLabel(positions?.metadata.fallback)}</dd>
            <dt title="no_data">无数据回退</dt>
            <dd>{ledgerNoDataLabel(positions?.metadata.no_data)}</dd>
          </dl>
        </article>
      </section>
    </section>
  );
}
