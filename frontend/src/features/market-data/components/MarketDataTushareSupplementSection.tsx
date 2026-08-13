import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Spin } from "antd";

import { useApiClient } from "../../../api/client";
import { externalDataQueryOptions } from "../../../app/externalDataRefreshPolicy";
import type { TushareEcoCalEventRow, TushareMoneySupplyRow } from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { LiveResultMetaStrip } from "./LiveResultMetaStrip";

type MoneySummaryItem = {
  label: string;
  value: string;
  caption: string;
  tone?: "up" | "down" | "neutral";
};

type MoneyTrendRow = {
  month: string;
  m1Yoy: string;
  m2Yoy: string;
  spread: string;
  widthPct: number;
};

type EcoCalendarSummary = {
  total: number;
  published: number;
  pending: number;
  currencies: Array<{ currency: string; count: number }>;
};

function formatPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(2)}%`;
}

function formatMonth(month: string) {
  return month.length >= 7 ? month.slice(0, 7) : month;
}

function formatEcoDate(eventDate: string) {
  if (eventDate.length === 8 && /^\d+$/.test(eventDate)) {
    return `${eventDate.slice(0, 4)}-${eventDate.slice(4, 6)}-${eventDate.slice(6, 8)}`;
  }
  return eventDate;
}

function formatEcoGroupLabel(eventDate: string, anchorDate?: string | null) {
  const formatted = formatEcoDate(eventDate);
  const anchorCompact = anchorDate?.replace(/-/g, "").slice(0, 8);
  if (anchorCompact && eventDate === anchorCompact) {
    return `${formatted} · 参考日`;
  }
  return formatted;
}

function buildEcoCalGroups(rows: readonly TushareEcoCalEventRow[], anchorDate?: string | null) {
  const groups = new Map<string, TushareEcoCalEventRow[]>();
  rows.forEach((row) => {
    const bucket = groups.get(row.event_date) ?? [];
    bucket.push(row);
    groups.set(row.event_date, bucket);
  });
  return [...groups.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([dateKey, groupRows]) => ({
      dateKey,
      label: formatEcoGroupLabel(dateKey, anchorDate),
      rows: groupRows,
    }));
}

function toFiniteNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatSpread(row: TushareMoneySupplyRow | undefined) {
  const m1Yoy = toFiniteNumber(row?.m1_yoy);
  const m2Yoy = toFiniteNumber(row?.m2_yoy);
  if (m1Yoy == null || m2Yoy == null) {
    return null;
  }
  return m2Yoy - m1Yoy;
}

function classifyDirection(latest: number | null, oldest: number | null) {
  if (latest == null || oldest == null) {
    return "缺口";
  }
  const delta = latest - oldest;
  if (delta > 0.05) {
    return "上行";
  }
  if (delta < -0.05) {
    return "下行";
  }
  return "震荡";
}

function buildMoneySummary(rows: readonly TushareMoneySupplyRow[]): MoneySummaryItem[] {
  const latest = rows[0];
  const latestM2Yoy = toFiniteNumber(latest?.m2_yoy);
  const latestM1Yoy = toFiniteNumber(latest?.m1_yoy);
  const spread = formatSpread(latest);
  const trendRows = rows.slice(0, 3);
  const oldestTrendRow = trendRows[trendRows.length - 1];
  const hasEnoughTrendRows = trendRows.length >= 3;
  const m2Direction = hasEnoughTrendRows ? classifyDirection(latestM2Yoy, toFiniteNumber(oldestTrendRow?.m2_yoy)) : "缺口";

  return [
    {
      label: "最新月份",
      value: latest ? formatMonth(latest.month) : "—",
      caption: "cn_m 可见最近月",
    },
    {
      label: "M2同比",
      value: formatPct(latestM2Yoy),
      caption: "宽货币增速",
      tone: "neutral",
    },
    {
      label: "M1同比",
      value: formatPct(latestM1Yoy),
      caption: "活化资金增速",
      tone: "neutral",
    },
    {
      label: "M2-M1 剪刀差",
      value: spread == null ? "—" : formatPct(spread),
      caption: "仅作分析读面",
      tone: spread == null ? "neutral" : spread >= 0 ? "up" : "down",
    },
    {
      label: "M1/M2 环比",
      value: `${formatPct(latest?.m1_mom)} / ${formatPct(latest?.m2_mom)}`,
      caption: "月内动能对照",
      tone: "neutral",
    },
    {
      label: "近3月 M2 同比",
      value: m2Direction,
      caption: hasEnoughTrendRows ? "按最新与最早月比较" : "样本不足，暂不判向",
      tone: m2Direction === "上行" ? "up" : m2Direction === "下行" ? "down" : "neutral",
    },
  ];
}

function buildMoneyTrendRows(rows: readonly TushareMoneySupplyRow[]): MoneyTrendRow[] {
  const latestRows = rows.slice(0, 6);
  const maxAbsSpread = Math.max(
    1,
    ...latestRows.map((row) => Math.abs(formatSpread(row) ?? 0)),
  );

  return latestRows.map((row) => {
    const spread = formatSpread(row);
    return {
      month: formatMonth(row.month),
      m1Yoy: formatPct(row.m1_yoy),
      m2Yoy: formatPct(row.m2_yoy),
      spread: spread == null ? "—" : formatPct(spread),
      widthPct: spread == null ? 4 : Math.max(8, Math.min(100, Math.abs(spread) / maxAbsSpread * 100)),
    };
  });
}

function buildEcoCalendarSummary(rows: readonly TushareEcoCalEventRow[]): EcoCalendarSummary {
  const currencies = new Map<string, number>();
  let published = 0;

  rows.forEach((row) => {
    if (row.value != null && String(row.value).trim() !== "") {
      published += 1;
    }
    const currency = row.currency?.trim();
    if (currency) {
      currencies.set(currency, (currencies.get(currency) ?? 0) + 1);
    }
  });

  return {
    total: rows.length,
    published,
    pending: rows.length - published,
    currencies: [...currencies.entries()]
      .map(([currency, count]) => ({ currency, count }))
      .sort((a, b) => b.count - a.count || a.currency.localeCompare(b.currency))
      .slice(0, 6),
  };
}

type QueryFailureKind = "forbidden" | "api" | "unknown";

function classifyQueryFailure(error: unknown): { kind: QueryFailureKind; message: string } {
  const text = error instanceof Error ? error.message : String(error ?? "未知错误");
  if (/\(403\)/.test(text) || /403/.test(text) && /forbidden|权限|scope|denied/i.test(text)) {
    return {
      kind: "forbidden",
      message: "无读取权限（403）：请确认账号已授予 market_data.tushare_supplement 读权限。",
    };
  }
  if (text.trim()) {
    return { kind: "api", message: `接口请求失败：${text}` };
  }
  return { kind: "unknown", message: "Tushare 补充数据加载失败，请稍后重试。" };
}

function momTone(value: number | null | undefined): "up" | "down" | undefined {
  const finite = toFiniteNumber(value);
  if (finite == null || finite === 0) {
    return undefined;
  }
  return finite > 0 ? "up" : "down";
}

function MoneySupplyTable({ rows }: { rows: readonly TushareMoneySupplyRow[] }) {
  return (
    <div className="market-data-tushare-table-wrap">
      <table data-testid="market-data-tushare-money-supply-table" className="market-data-tushare-table">
        <thead>
          <tr>
            <th>月份</th>
            <th>M0同比</th>
            <th>M1同比</th>
            <th>M2同比</th>
            <th>M1环比</th>
            <th>M2环比</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.month}>
              <td style={tabularNumsStyle}>{formatMonth(row.month)}</td>
              <td style={tabularNumsStyle}>{formatPct(row.m0_yoy)}</td>
              <td style={tabularNumsStyle}>{formatPct(row.m1_yoy)}</td>
              <td style={tabularNumsStyle}>{formatPct(row.m2_yoy)}</td>
              <td style={tabularNumsStyle} data-tone={momTone(row.m1_mom)}>
                {formatPct(row.m1_mom)}
              </td>
              <td style={tabularNumsStyle} data-tone={momTone(row.m2_mom)}>
                {formatPct(row.m2_mom)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MoneySupplySummary({ rows }: { rows: readonly TushareMoneySupplyRow[] }) {
  const summaryItems = buildMoneySummary(rows);
  const primaryItems = summaryItems.slice(0, 4);
  const secondaryItems = summaryItems.slice(4);

  const renderSummaryCard = (item: MoneySummaryItem) => (
    <div key={item.label} className="market-data-tushare-summary-card" data-tone={item.tone ?? "neutral"}>
      <span className="market-data-tushare-summary-card__label">{item.label}</span>
      <strong className="market-data-tushare-summary-card__value" style={tabularNumsStyle}>
        {item.value}
      </strong>
      <span className="market-data-tushare-summary-card__caption">{item.caption}</span>
    </div>
  );

  return (
    <div data-testid="market-data-tushare-money-summary" className="market-data-tushare-money-summary">
      <div className="market-data-tushare-money-summary__primary">{primaryItems.map(renderSummaryCard)}</div>
      {secondaryItems.length > 0 ? (
        <details className="market-data-tushare-details market-data-tushare-money-summary__more">
          <summary>更多货币指标</summary>
          <div className="market-data-tushare-money-summary__secondary">
            {secondaryItems.map(renderSummaryCard)}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function MoneySupplyTrend({ rows }: { rows: readonly TushareMoneySupplyRow[] }) {
  const trendRows = buildMoneyTrendRows(rows);
  return (
    <div data-testid="market-data-tushare-money-trend" className="market-data-tushare-money-trend">
      <div className="market-data-tushare-money-trend__head">
        <span>月份</span>
        <span>M1同比</span>
        <span>M2同比</span>
        <span>剪刀差</span>
      </div>
      {trendRows.map((row) => (
        <div key={row.month} className="market-data-tushare-money-trend__row">
          <span style={tabularNumsStyle}>{row.month}</span>
          <span style={tabularNumsStyle}>{row.m1Yoy}</span>
          <span style={tabularNumsStyle}>{row.m2Yoy}</span>
          <span className="market-data-tushare-money-trend__spread" style={tabularNumsStyle}>
            <i style={{ width: `${row.widthPct}%` }} aria-hidden />
            {row.spread}
          </span>
        </div>
      ))}
    </div>
  );
}

function EcoCalList({
  rows,
  anchorDate,
}: {
  rows: readonly TushareEcoCalEventRow[];
  anchorDate?: string | null;
}) {
  const groups = buildEcoCalGroups(rows, anchorDate);
  return (
    <div data-testid="market-data-tushare-eco-cal-list" className="market-data-tushare-eco-cal-list">
      {groups.map((group) => (
        <section key={group.dateKey} className="market-data-tushare-eco-cal-group">
          <h4 className="market-data-tushare-eco-cal-group__title">{group.label}</h4>
          <ul className="market-data-tushare-eco-cal-group__items">
            {group.rows.map((row) => {
              const published = row.value != null && String(row.value).trim() !== "";
              return (
                <li
                  key={row.event_id}
                  className="market-data-tushare-eco-cal-item"
                  data-published={published ? "true" : "false"}
                >
                  <div className="market-data-tushare-eco-cal-item__meta" style={tabularNumsStyle}>
                    {row.event_time ? <span>{row.event_time}</span> : null}
                    {row.currency ? (
                      <span className="market-data-tushare-eco-cal-item__currency">{row.currency}</span>
                    ) : null}
                  </div>
                  <div className="market-data-tushare-eco-cal-item__title">{row.event}</div>
                  <div className="market-data-tushare-eco-cal-item__values">
                    <span data-state={published ? "published" : "pending"}>
                      {published ? `公布 ${row.value}` : "待公布"}
                    </span>
                    {row.pre_value ? <span>前值 {row.pre_value}</span> : null}
                    {row.fore_value ? <span>预测 {row.fore_value}</span> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

function EcoCurrencyFilter({
  rows,
  value,
  onChange,
}: {
  rows: readonly TushareEcoCalEventRow[];
  value: string | null;
  onChange: (currency: string | null) => void;
}) {
  const currencies = buildEcoCalendarSummary(rows).currencies;
  if (currencies.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="market-data-tushare-eco-currency-filter"
      className="market-data-tushare-eco-currency-filter"
      role="group"
      aria-label="经济日历币种筛选"
    >
      <button
        type="button"
        className="market-data-tushare-eco-currency-filter__chip"
        data-active={value == null ? "true" : "false"}
        onClick={() => onChange(null)}
      >
        全部
      </button>
      {currencies.map((item) => (
        <button
          key={item.currency}
          type="button"
          className="market-data-tushare-eco-currency-filter__chip"
          data-active={value === item.currency ? "true" : "false"}
          onClick={() => onChange(item.currency)}
        >
          {item.currency} {item.count}
        </button>
      ))}
    </div>
  );
}

function EcoCalendarPanel({
  rows,
  anchorDate,
}: {
  rows: readonly TushareEcoCalEventRow[];
  anchorDate?: string | null;
}) {
  const [currencyFilter, setCurrencyFilter] = useState<string | null>(null);
  const filteredRows = useMemo(() => {
    if (!currencyFilter) {
      return rows;
    }
    return rows.filter((row) => row.currency === currencyFilter);
  }, [rows, currencyFilter]);

  return (
    <div className="market-data-tushare-supplement-stack">
      <EcoCalendarSummary rows={filteredRows} />
      <EcoCurrencyFilter rows={rows} value={currencyFilter} onChange={setCurrencyFilter} />
      {filteredRows.length === 0 ? (
        <p data-testid="market-data-tushare-eco-cal-filter-empty" className="market-data-tushare-empty-hint">
          当前币种筛选下无事件，请切换「全部」或其他币种。
        </p>
      ) : (
        <EcoCalList rows={filteredRows} anchorDate={anchorDate} />
      )}
    </div>
  );
}
function EcoCalendarSummary({ rows }: { rows: readonly TushareEcoCalEventRow[] }) {
  const summary = buildEcoCalendarSummary(rows);
  return (
    <div data-testid="market-data-tushare-eco-summary" className="market-data-tushare-eco-summary">
      <span className="market-data-tushare-eco-summary__metric" style={tabularNumsStyle}>
        事件 {summary.total}
      </span>
      <span className="market-data-tushare-eco-summary__metric" style={tabularNumsStyle}>
        已公布 {summary.published}
      </span>
      <span className="market-data-tushare-eco-summary__metric" style={tabularNumsStyle}>
        待公布 {summary.pending}
      </span>
    </div>
  );
}


export function MarketDataTushareSupplementSection() {
  const client = useApiClient();
  const query = useQuery({
    queryKey: ["market-data", "tushare-supplement", client.mode],
    queryFn: () => client.getTushareSupplement({ moneySupplyLimit: 12, ecoCalLimit: 30 }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });

  const resultMeta = query.data?.result_meta;
  const moneyRows = useMemo(
    () => [...(query.data?.result.money_supply_rows ?? [])].sort((a, b) => b.month.localeCompare(a.month)),
    [query.data?.result.money_supply_rows],
  );
  const ecoRows = useMemo(() => query.data?.result.eco_cal_rows ?? [], [query.data?.result.eco_cal_rows]);
  const warnings = query.data?.result.warnings ?? [];
  const failure = query.isError ? classifyQueryFailure(query.error) : null;
  const hasRows = moneyRows.length > 0 || ecoRows.length > 0;
  const vendorUnavailable = resultMeta?.vendor_status === "vendor_unavailable";

  const moneyEmptyHint =
    vendorUnavailable && !hasRows
      ? "暂无货币供应数据：供应商不可用或未回填，请运行 refresh_tushare_supplement。"
      : "暂无货币供应数据，请运行 refresh_tushare_supplement。";
  const ecoEmptyHint =
    vendorUnavailable && !hasRows
      ? "暂无经济日历事件：供应商不可用或未回填，请运行 refresh_tushare_supplement。"
      : "暂无经济日历事件。";

  return (
    <section data-testid="market-data-tushare-supplement-section" className="market-data-tushare-supplement-section">
      <header className="market-data-tushare-supplement-head">
        <div>
          <span className="market-data-supplementary-kicker">宏观补充</span>
          <h2 className="market-data-supplementary-title">Tushare 宏观补充</h2>
          <p className="market-data-supplementary-summary">
            货币供应（cn_m）与经济日历（eco_cal）；分析口径，非正式金融指标。
          </p>
        </div>
      </header>
      {!query.isLoading && !query.isError ? (
        <LiveResultMetaStrip
          meta={resultMeta}
          testId="market-data-tushare-supplement-meta"
          lead="Tushare 补充读面"
        />
      ) : null}
      {query.isLoading ? (
        <div className="market-data-tushare-supplement-loading">
          <Spin />
        </div>
      ) : query.isError ? (
        <Alert
          data-testid="market-data-tushare-supplement-error"
          type="error"
          showIcon
          message={failure?.message ?? "Tushare 补充数据加载失败。"}
          description={
            failure?.kind === "forbidden"
              ? "这是权限问题，不是数据为空。请联系管理员分配读权限后刷新页面。"
              : "若持续失败，请确认 dev-api 可用且 DuckDB 已回填。"
          }
        />
      ) : (
        <div className="market-data-tushare-supplement-grid">
          <div
            data-testid="market-data-tushare-money-supply-panel"
            className="market-data-tushare-panel market-data-tushare-panel--money"
          >
            <h3 className="market-data-tushare-supplement-subtitle">货币供应 M0/M1/M2</h3>
            {moneyRows.length === 0 ? (
              <p data-testid="market-data-tushare-money-supply-empty" className="market-data-tushare-empty-hint">
                {moneyEmptyHint}
              </p>
            ) : (
              <div className="market-data-tushare-supplement-stack">
                <MoneySupplySummary rows={moneyRows} />
                <MoneySupplyTrend rows={moneyRows} />
                <details className="market-data-tushare-details">
                  <summary>查看完整 M0/M1/M2 明细表</summary>
                  <MoneySupplyTable rows={moneyRows} />
                </details>
              </div>
            )}
          </div>
          <div
            data-testid="market-data-tushare-eco-cal-panel"
            className="market-data-tushare-panel market-data-tushare-panel--eco"
          >
            <h3 className="market-data-tushare-supplement-subtitle">经济日历</h3>
            {ecoRows.length === 0 ? (
              <p data-testid="market-data-tushare-eco-cal-empty" className="market-data-tushare-empty-hint">
                {ecoEmptyHint}
              </p>
            ) : (
              <EcoCalendarPanel rows={ecoRows} anchorDate={resultMeta?.as_of_date} />
            )}
          </div>
        </div>
      )}
      {warnings.length > 0 ? (
        <p data-testid="market-data-tushare-supplement-warnings" className="market-data-tushare-warning-hint">
          {warnings.join(" ")}
        </p>
      ) : null}
      {!query.isLoading && !query.isError && resultMeta ? (
        <p
          data-testid="market-data-tushare-supplement-freshness"
          className="market-data-tushare-freshness-hint"
          data-tone={
            resultMeta.quality_flag === "stale" ||
            resultMeta.vendor_status === "vendor_unavailable" ||
            resultMeta.vendor_status === "vendor_stale"
              ? "warn"
              : "ok"
          }
        >
          数据截至 {resultMeta.as_of_date ?? "—"}
          {resultMeta.generated_at ? ` · 生成 ${resultMeta.generated_at}` : ""}
          {resultMeta.quality_flag === "stale" ||
          resultMeta.vendor_status === "vendor_unavailable" ||
          resultMeta.vendor_status === "vendor_stale"
            ? " · 若读面陈旧请运行 scripts/refresh_tushare_supplement.py（见 docs/tushare_supplement_refresh_runbook.md）。"
            : " · 运维刷新见 docs/tushare_supplement_refresh_runbook.md。"}
        </p>
      ) : null}
    </section>
  );
}
