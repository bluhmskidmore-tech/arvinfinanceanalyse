import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  buildLedgerKpiCards,
  directionLabel,
  formatLedgerYuanAmount,
  ledgerDataState,
  positionRowKey,
  resolvedLedgerDate,
  type LedgerDirectionFilter,
} from "./ledgerDashboardPageModel";
import "./LedgerDashboardPage.css";

function queryDirection(value: string | null): LedgerDirectionFilter {
  if (value === "ASSET" || value === "LIABILITY") {
    return value;
  }
  return "ALL";
}

function queryDate(value: string | null) {
  return value?.trim() ?? "";
}

export default function LedgerDashboardPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedDate, setSelectedDate] = useState(() => queryDate(searchParams.get("as_of_date")));
  const [direction, setDirection] = useState<LedgerDirectionFilter>(() =>
    queryDirection(searchParams.get("direction")),
  );

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
    setDirection((current) => {
      const next = queryDirection(searchParams.get("direction"));
      return current === next ? current : next;
    });
  }, [searchParams]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (selectedDate) {
      next.set("as_of_date", selectedDate);
    } else {
      next.delete("as_of_date");
    }
    if (direction === "ALL") {
      next.delete("direction");
    } else {
      next.set("direction", direction);
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [direction, searchParams, selectedDate, setSearchParams]);

  const dashboardQuery = useQuery({
    queryKey: ["bank-ledger", "dashboard", client.mode, selectedDate],
    enabled: Boolean(selectedDate),
    queryFn: () => client.getLedgerDashboard(selectedDate),
    retry: false,
  });

  const positionsQuery = useQuery({
    queryKey: ["bank-ledger", "positions", client.mode, selectedDate, direction],
    enabled: Boolean(selectedDate),
    queryFn: () =>
      client.getLedgerPositions({
        asOfDate: selectedDate,
        direction: direction === "ALL" ? undefined : direction,
        page: 1,
        pageSize: 20,
      }),
    retry: false,
  });

  const dashboard = dashboardQuery.data;
  const positions = positionsQuery.data;
  const cards = buildLedgerKpiCards(dashboard?.data);
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
        <div className="ledger-dashboard__mode">{client.mode === "real" ? "正式读链路" : "本地演示数据"}</div>
      </header>

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

        <div className="ledger-dashboard__segmented" role="group" aria-label="ledger-dashboard-direction">
          {(["ALL", "ASSET", "LIABILITY"] as LedgerDirectionFilter[]).map((item) => (
            <button
              key={item}
              type="button"
              className={direction === item ? "is-active" : ""}
              onClick={() => setDirection(item)}
            >
              {directionLabel(item)}
            </button>
          ))}
        </div>
      </div>

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
            <button type="button" onClick={() => setDirection(card.direction)}>
              明细
            </button>
          </article>
        ))}
      </div>

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
                <th>面值（元）</th>
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
                  <td className="ledger-dashboard__num">{formatLedgerYuanAmount(item.face_amount)}</td>
                  <td>{item.batch_id}</td>
                  <td>{item.row_no}</td>
                </tr>
              ))}
              {positions && positions.data.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="ledger-dashboard__empty">
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
            <dd>{direction === "ALL" ? "ALL" : direction}</dd>
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
