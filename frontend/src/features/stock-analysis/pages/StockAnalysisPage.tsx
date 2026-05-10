import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Collapse, DatePicker, Drawer, Tabs, Typography } from "antd";
import dayjs from "dayjs";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreSectorRankSeriesPoint,
  LivermoreSignalConfluencePayload,
} from "../../../api/contracts";
import { AgentPanel } from "../../agent/AgentPanel";
import {
  buildCandidateEvidenceCards,
  buildDailyJudgmentStrip,
  buildInlineMetaSegments,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
  buildSectorTableSortComparator,
  buildSectorViewModel,
} from "../lib/stockAnalysisPageModel";
import type { StockSectorRow, StockSectorViewKind } from "../lib/stockAnalysisPageModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { StockDetailDrawer } from "../components/StockDetailDrawer";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import "./StockAnalysisPage.css";

const { Text } = Typography;

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    fail: "未通过",
    missing: "缺数据",
    stale: "已陈旧",
  };
  return labels[status] ?? status;
}

function riskStatusLabel(status: "triggered" | "watch") {
  return status === "triggered" ? "触发复核" : "观察中";
}

const sectorViewTabs: { key: StockSectorViewKind; label: string }[] = [
  { key: "score", label: "综合得分" },
  { key: "pctchange", label: "平均涨跌幅" },
  { key: "turnover", label: "换手活跃度" },
  { key: "amplitude", label: "波动振幅" },
];

const patternRank: Record<string, number> = {
  突破: 0,
  回踩: 1,
  缩量盘整: 2,
  待补: 3,
};

type SectorSortKey =
  | "rank"
  | "sectorCode"
  | "sectorName"
  | "score"
  | "pctChange"
  | "turnover"
  | "amplitude"
  | "constituentCount";

function sectorRankUnavailable(strategyPayload: { sector_rank?: { formula_version?: string; items?: unknown[] } } | null) {
  const items = strategyPayload?.sector_rank?.items ?? [];
  const fv = strategyPayload?.sector_rank?.formula_version;
  return items.length === 0 || fv == null || String(fv).trim() === "";
}

function latestSectorSeriesTableRows(series: LivermoreSectorRankSeriesPoint[]): LivermoreSectorRankSeriesPoint[] {
  const byCode = new Map<string, LivermoreSectorRankSeriesPoint>();
  for (const row of series) {
    const cur = byCode.get(row.sector_code);
    if (!cur || row.trade_date > cur.trade_date) {
      byCode.set(row.sector_code, row);
    }
  }
  return Array.from(byCode.values()).sort((a, b) => {
    const ra = a.rank ?? 9999;
    const rb = b.rank ?? 9999;
    return ra - rb;
  });
}

export default function StockAnalysisPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [asOfOverride, setAsOfOverride] = useState<string | null>(null);
  const [sectorFilterSectorCode, setSectorFilterSectorCode] = useState<string | null>(null);
  const [sectorView, setSectorView] = useState<StockSectorViewKind>("score");
  const [sectorSort, setSectorSort] = useState<{
    key: SectorSortKey;
    order: "ascend" | "descend";
  }>({ key: "rank", order: "ascend" });
  const [boundaryDrawerOpen, setBoundaryDrawerOpen] = useState(false);
  const [detailSelection, setDetailSelection] = useState<{ code: string; name?: string } | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [sectorSeriesCollapseKeys, setSectorSeriesCollapseKeys] = useState<string[]>([]);
  const [sectorSeriesWindow, setSectorSeriesWindow] = useState<5 | 20>(5);

  const strategyQueryKey = ["stock-analysis", "livermore-strategy", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      asOfOverride
        ? client.getLivermoreStrategy({ asOfDate: asOfOverride })
        : client.getLivermoreStrategy(),
  });

  const strategyPayload = strategyQuery.data?.result ?? null;

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: Boolean(strategyPayload?.as_of_date),
  });

  const confluencePayload: LivermoreSignalConfluencePayload | null =
    confluenceQuery.data?.result ?? null;

  const judgment = useMemo(
    () => (strategyPayload ? buildDailyJudgmentStrip(strategyPayload) : null),
    [strategyPayload],
  );

  const marketState = useMemo(
    () => (strategyPayload ? buildMarketStateCard(strategyPayload) : null),
    [strategyPayload],
  );

  const sectorRowsFull = useMemo(
    () => (strategyPayload ? buildSectorRows(strategyPayload) : []),
    [strategyPayload],
  );

  const sectorViewRows = useMemo(
    () => (strategyPayload ? buildSectorViewModel(strategyPayload, sectorView) : []),
    [strategyPayload, sectorView],
  );

  const sortedDetailRows = useMemo(() => {
    const cmp = buildSectorTableSortComparator(sectorSort.key, sectorSort.order);
    return [...sectorRowsFull].sort(cmp);
  }, [sectorRowsFull, sectorSort]);

  const candidateCards = useMemo(() => {
    const cards = strategyPayload ? buildCandidateEvidenceCards(strategyPayload) : [];
    return [...cards].sort((a, b) => (patternRank[a.pattern] ?? 99) - (patternRank[b.pattern] ?? 99));
  }, [strategyPayload]);

  const sectorOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const card of candidateCards) {
      map.set(card.sectorCode, card.sectorName || card.sectorCode);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b, "zh-Hans-CN"));
  }, [candidateCards]);

  const filteredCandidates = useMemo(() => {
    if (!sectorFilterSectorCode) return candidateCards;
    return candidateCards.filter((c) => c.sectorCode === sectorFilterSectorCode);
  }, [candidateCards, sectorFilterSectorCode]);

  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );

  const riskExitUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "risk_exit");

  const metaSegments = strategyPayload
    ? buildInlineMetaSegments(strategyPayload, {
        quality_flag: strategyQuery.data?.result_meta?.quality_flag,
        vendor_status: strategyQuery.data?.result_meta?.vendor_status,
        source_version: strategyQuery.data?.result_meta?.source_version,
        rule_version: strategyQuery.data?.result_meta?.rule_version,
      })
    : [];

  const showStaleBanner = Boolean(
    strategyQuery.data?.result_meta &&
      (strategyQuery.data.result_meta.quality_flag !== "ok" ||
        strategyQuery.data.result_meta.vendor_status !== "ok"),
  );

  const topBars = sectorViewRows.slice(0, 5);
  const bottomBars = sectorViewRows.slice(Math.max(sectorViewRows.length - 5, 0));

  const invalidateStockAnalysis = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-analysis"] }).catch(() => undefined);
  };

  const toggleSectorFilter = (code: string | null) => {
    setSectorFilterSectorCode((prev) => (prev === code ? null : code));
  };

  const toggleSort = (key: SectorSortKey) => {
    setSectorSort((prev) =>
      prev.key === key ? { key, order: prev.order === "ascend" ? "descend" : "ascend" } : { key, order: "ascend" },
    );
  };

  function renderSortSuffix(key: SectorSortKey) {
    if (sectorSort.key !== key) return "";
    return sectorSort.order === "ascend" ? " ▲" : " ▼";
  }

  const headerDateValue =
    strategyPayload?.as_of_date != null ? dayjs(strategyPayload.as_of_date) : null;

  const pickerDisplay =
    asOfOverride != null && asOfOverride.trim() !== "" ? dayjs(asOfOverride) : headerDateValue;

  const stockDetailAsOfDate = asOfOverride ?? strategyPayload?.as_of_date ?? undefined;

  const effectiveAsOf = asOfOverride ?? strategyPayload?.as_of_date ?? null;

  const sectorSeriesExpanded = sectorSeriesCollapseKeys.includes("sector-rank-series-multi");

  const sectorRankSeriesQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-sector-rank-series", effectiveAsOf ?? "__none", sectorSeriesWindow] as const,
    queryFn: () =>
      client.getLivermoreSectorRankSeries({
        asOfDate: effectiveAsOf ?? undefined,
        windowDays: sectorSeriesWindow,
        topK: 10,
      }),
    enabled: Boolean(
      sectorSeriesExpanded &&
        effectiveAsOf &&
        strategyPayload &&
        !sectorRankUnavailable(strategyPayload),
    ),
  });

  const sectorSeriesTableRows = useMemo(() => {
    const envelope = sectorRankSeriesQuery.data?.result;
    const series = envelope?.series;
    if (!series || envelope?.state !== "ok") {
      return [];
    }
    return latestSectorSeriesTableRows(series);
  }, [sectorRankSeriesQuery.data?.result]);

  const stockAnalysisAgentPageContext = useMemo(
    () =>
      buildStockAnalysisAgentPageContext({
        asOfDate: effectiveAsOf,
        sectorFilterSectorCode,
        sectorView,
        detailSelection,
      }),
    [detailSelection, effectiveAsOf, sectorFilterSectorCode, sectorView],
  );

  return (
    <main
      className="stock-analysis-page"
      style={stockAnalysisPageCssVars}
      data-testid="stock-analysis-page"
    >
      <header className="stock-analysis-page__header">
        <p className="stock-analysis-page__eyebrow">A股观察 / Evidence first</p>
        <div className="stock-analysis-page__header-main">
          <div>
            <h1>股票分析</h1>
            <p>
              复用 Livermore 与 Choice 股票只读链路，展示市场状态、板块强弱与候选证据；
              仅供研究复核，不构成交易指令。
            </p>
          </div>
          <div className="stock-analysis-page__header-controls">
            <span className="stock-analysis-page__badge">仅观察 / 复核 / 研究</span>
            <Button
              type="default"
              className="stock-analysis-page__agent-entry"
              data-testid="stock-analysis-agent-open"
              onClick={() => setAgentDrawerOpen(true)}
              aria-expanded={agentDrawerOpen}
            >
              召唤 Agent 复核
            </Button>
            <DatePicker
              allowClear
              aria-label="as-of-date-picker"
              data-testid="stock-analysis-as-of-picker"
              value={pickerDisplay}
              onChange={(_, iso) => {
                setAsOfOverride(Array.isArray(iso) ? (iso[0] ?? null) : iso || null);
              }}
            />
            <Button data-testid="stock-analysis-refresh" onClick={invalidateStockAnalysis}>
              刷新
            </Button>
            {strategyQuery.data?.result_meta?.generated_at ? (
              <Text type="secondary" className="stock-analysis-page__tabular">
                最后更新 {strategyQuery.data.result_meta.generated_at}
              </Text>
            ) : null}
          </div>
        </div>
      </header>

      {strategyQuery.isLoading ? (
        <section className="stock-analysis-page__panel">
          <p className="stock-analysis-page__state">正在加载股票分析结果。</p>
        </section>
      ) : null}

      {strategyQuery.isError ? (
        <section className="stock-analysis-page__panel stock-analysis-page__panel--error">
          <h2>股票分析结果加载失败。</h2>
          <p>{errorMessage(strategyQuery.error)}</p>
        </section>
      ) : null}

      {marketState ? (
        <>
          {judgment ? (
            <section
              className="stock-analysis-page__panel"
              aria-label="本日判断"
              data-testid="stock-analysis-judgment-strip"
            >
              <div className="stock-analysis-page__judgment-strip">
                <main>
                  <p className="stock-analysis-page__judgment-lead">{judgment.headline}</p>
                  <span className="stock-analysis-page__pattern-tag">
                    {marketState.state} · 观察暴露 {marketState.exposureLabel}
                  </span>
                </main>
                <aside>
                  <span className="stock-analysis-page__judgment-chip">{judgment.gateChip}</span>
                  <span className="stock-analysis-page__judgment-chip">{judgment.exposureChip}</span>
                  <span className="stock-analysis-page__judgment-chip">{judgment.strongestSectorChip}</span>
                  <span className="stock-analysis-page__judgment-chip">{judgment.weakestSectorChip}</span>
                </aside>
              </div>
            </section>
          ) : null}

          {showStaleBanner ? (
            <div className="stock-analysis-page__stale-banner" data-testid="stock-analysis-stale-banner" role="status">
              数据陈旧或通道异常（quality_flag / vendor_status）。下方结论仅供复核参考。
            </div>
          ) : null}

          <section className="stock-analysis-page__panel stock-analysis-page__overview-panel">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>{marketState.title}</h2>
                <p>先看市场门控，再看板块与个股证据。</p>
              </div>
              <span className="stock-analysis-page__pill">{marketState.basisLabel}</span>
            </div>
            <div className="stock-analysis-page__kpis">
              <div className="stock-analysis-page__kpi">
                <span>状态</span>
                <strong>{marketState.state}</strong>
              </div>
              <div className="stock-analysis-page__kpi">
                <span>观察暴露</span>
                <strong>{marketState.exposureLabel}</strong>
              </div>
              <div className="stock-analysis-page__kpi">
                <span>门控确认</span>
                <strong>{marketState.passedLabel}</strong>
              </div>
            </div>
            <div className="stock-analysis-page__split">
              <div>
                <h3>门控条件</h3>
                <ul className="stock-analysis-page__list">
                  {marketState.conditions.map((condition) => (
                    <li key={condition.key}>
                      <span>
                        <strong>{condition.label}</strong>
                        <small>{condition.evidence}</small>
                      </span>
                      <em>{statusLabel(condition.status)}</em>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>需要关注边界</h3>
                {marketState.warnings.length > 0 ? (
                  <ul className="stock-analysis-page__notes">
                    {marketState.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="stock-analysis-page__empty">当前无诊断预警。</p>
                )}
              </div>
            </div>
          </section>

          <div className="stock-analysis-page__workspace">
            <div className="stock-analysis-page__primary">
              <section className="stock-analysis-page__panel stock-analysis-page__panel--compact">
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>板块强弱</h2>
                    <p>Livermore sector_rank，仅用后端字段做排序视图；图示为横向对比入口。</p>
                  </div>
                  <span className="stock-analysis-page__pill">
                    {(strategyPayload?.sector_rank?.formula_version ?? "").trim() || "formula 待补"}
                  </span>
                </div>

                {!sectorRankUnavailable(strategyPayload) ? (
                  <>
                    <Tabs
                      className="stock-analysis-page__sector-tabs"
                      size="small"
                      activeKey={sectorView}
                      onChange={(key) => setSectorView(key as StockSectorViewKind)}
                      items={sectorViewTabs.map((tab) => ({ key: tab.key, label: tab.label }))}
                    />

                    <div className="stock-analysis-page__sector-bisect" data-testid="stock-analysis-sector-bars">
                      <div>
                        <h3 className="stock-analysis-page__sector-col-title">强势 Top 5</h3>
                        <div className="stock-analysis-page__bar-list">
                          {topBars.map((row) => (
                            <button
                              type="button"
                              key={`top-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__bar-row${sectorFilterSectorCode === row.sectorCode ? " stock-analysis-page__bar-row--active" : ""}`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__bar-meta stock-analysis-page__table-number">
                                <span>
                                  {row.rank}. {row.sectorName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.sectorCode}</small>
                                </span>
                                <span>{row.score}</span>
                              </div>
                              <div className="stock-analysis-page__bar-track">
                                <div
                                  className="stock-analysis-page__bar-fill"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div className="stock-analysis-page__bar-label-overlay stock-analysis-page__table-number">
                                  <span>{row.pctChange}</span>
                                  <small>成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="stock-analysis-page__sector-col--bottom">
                        <h3 className="stock-analysis-page__sector-col-title">弱势 Bottom 5</h3>
                        <div className="stock-analysis-page__bar-list">
                          {bottomBars.map((row) => (
                            <button
                              type="button"
                              key={`bottom-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__bar-row${sectorFilterSectorCode === row.sectorCode ? " stock-analysis-page__bar-row--active" : ""}`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-bottom-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__bar-meta stock-analysis-page__table-number">
                                <span>
                                  {row.rank}. {row.sectorName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.sectorCode}</small>
                                </span>
                                <span>{row.pctChange}</span>
                              </div>
                              <div className="stock-analysis-page__bar-track">
                                <div
                                  className="stock-analysis-page__bar-fill"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div className="stock-analysis-page__bar-label-overlay stock-analysis-page__table-number">
                                  <span>{row.pctChange}</span>
                                  <small>成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <p className="stock-analysis-page__footnote">
                      视图切换不重拉接口；条形图为单日截面，多日窗口聚合见下方折叠（运行时聚合，sum 累加未复利）。
                    </p>

                    <Collapse
                      bordered={false}
                      style={{ marginTop: 12 }}
                      items={[
                        {
                          key: "sector-detail-table",
                          label: "展开看明细表格",
                          children: (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table">
                                <thead>
                                  <tr>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("rank")}
                                      onKeyDown={(e) => e.key === "Enter" && toggleSort("rank")}
                                      role="columnheader"
                                    >
                                      排名
                                      {renderSortSuffix("rank")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("sectorName")}
                                    >
                                      行业
                                      {renderSortSuffix("sectorName")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("score")}
                                    >
                                      分数
                                      {renderSortSuffix("score")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("pctChange")}
                                    >
                                      涨跌幅
                                      {renderSortSuffix("pctChange")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("turnover")}
                                    >
                                      换手
                                      {renderSortSuffix("turnover")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("amplitude")}
                                    >
                                      振幅
                                      {renderSortSuffix("amplitude")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("constituentCount")}
                                    >
                                      成分数
                                      {renderSortSuffix("constituentCount")}
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      涨跌条
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sortedDetailRows.map((row: StockSectorRow) => (
                                    <tr key={row.sectorCode}>
                                      <td className="stock-analysis-page__table-number">#{row.rank}</td>
                                      <td>
                                        {row.sectorName}
                                        <small>{row.sectorCode}</small>
                                      </td>
                                      <td className="stock-analysis-page__table-number">{row.score}</td>
                                      <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                      <td className="stock-analysis-page__table-number">{row.turnover}</td>
                                      <td className="stock-analysis-page__table-number">{row.amplitude}</td>
                                      <td className="stock-analysis-page__table-number">{row.constituentCount}</td>
                                      <td className="stock-analysis-page__pct-bar-cell">
                                        <div className="stock-analysis-page__pct-bar-visual">
                                          <div
                                            className="stock-analysis-page__pct-bar-fill"
                                            style={{ width: `${row.pctChangeBar}%` }}
                                          />
                                        </div>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ),
                        },
                      ]}
                    />

                    <Collapse
                      bordered={false}
                      style={{ marginTop: 12 }}
                      activeKey={sectorSeriesCollapseKeys}
                      onChange={(keys) =>
                        setSectorSeriesCollapseKeys(Array.isArray(keys) ? keys : [keys])
                      }
                      items={[
                        {
                          key: "sector-rank-series-multi",
                          label: "多日累计强度（窗口聚合）",
                          children: (
                            <div
                              className="stock-analysis-page__sector-series-wrap"
                              data-testid="stock-analysis-sector-series-panel"
                            >
                              <p className="stock-analysis-page__sector-series-note">
                                窗口内对每日 avg_pctchange 做 sum 累加（未做复利）；动量持续度与资金流向暂不可用（见接口
                                unsupported_notes）。
                              </p>
                              <Tabs
                                size="small"
                                activeKey={String(sectorSeriesWindow)}
                                onChange={(key) => setSectorSeriesWindow(key === "20" ? 20 : 5)}
                                className="stock-analysis-page__sector-series-tabs"
                                items={[
                                  { key: "5", label: "5 交易日" },
                                  { key: "20", label: "20 交易日" },
                                ]}
                              />
                              {sectorRankSeriesQuery.isFetching ? (
                                <Text type="secondary">加载多日板块序列…</Text>
                              ) : null}
                              {sectorRankSeriesQuery.isError ? (
                                <Alert
                                  type="warning"
                                  showIcon
                                  message="多日板块序列加载失败"
                                  description={errorMessage(sectorRankSeriesQuery.error)}
                                />
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "missing" ? (
                                <Text type="secondary">暂无多日窗口可用数据。</Text>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length === 0 ? (
                                <Text type="secondary">窗口内无表格行可展示。</Text>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length > 0 ? (
                                <div className="stock-analysis-page__table-wrap">
                                  <table className="stock-analysis-page__table">
                                    <thead>
                                      <tr>
                                        <th scope="col">行业</th>
                                        <th scope="col">代码</th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          score（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          rank（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          cum_pctchange_window
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          成分数
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {sectorSeriesTableRows.map((row) => (
                                        <tr
                                          key={`${row.sector_code}-${row.trade_date}`}
                                          data-testid={`sector-series-row-${row.sector_code}`}
                                        >
                                          <td>{row.sector_name}</td>
                                          <td className="stock-analysis-page__tabular">{row.sector_code}</td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.score ?? "—"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.rank ?? "—"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.cum_pctchange_window ?? "—"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.constituent_count ?? "—"}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ) : null}
                            </div>
                          ),
                        },
                      ]}
                    />
                  </>
                ) : (
                  <p className="stock-analysis-page__empty">
                    当前行业强弱不可用，请检查 Choice 股票目录与当日落地覆盖。
                  </p>
                )}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--evidence"
                data-testid="stock-analysis-candidates-section"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>候选股证据卡</h2>
                    <p>说明为什么进入观察、反证与待补证据，以及失效条件。</p>
                  </div>
                  <span className="stock-analysis-page__pill">候选 / 复核</span>
                </div>

                {candidateCards.length > 0 ? (
                  <div className="stock-analysis-page__chip-row" data-testid="stock-sector-filter-chips">
                    <button
                      type="button"
                      className={`stock-analysis-page__pill stock-analysis-page__filter-chip${sectorFilterSectorCode === null ? " stock-analysis-page__filter-chip--active" : ""}`}
                      onClick={() => setSectorFilterSectorCode(null)}
                      aria-pressed={sectorFilterSectorCode === null}
                    >
                      全部行业
                    </button>
                    {sectorOptions.map(([code, label]) => (
                      <button
                        key={code}
                        type="button"
                        data-testid={`sector-filter-chip-${code}`}
                        className={`stock-analysis-page__pill stock-analysis-page__filter-chip${sectorFilterSectorCode === code ? " stock-analysis-page__filter-chip--active" : ""}`}
                        onClick={() => toggleSectorFilter(code)}
                        aria-pressed={sectorFilterSectorCode === code}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : null}

                {candidateCards.length > 0 ? (
                  <div className="stock-analysis-page__candidate-grid">
                    {filteredCandidates.map((card) => (
                      <article
                        className="stock-analysis-page__candidate"
                        data-testid={`stock-candidate-${card.stockCode}`}
                        key={card.stockCode}
                      >
                        <div className="stock-analysis-page__candidate-head">
                          <div>
                            <h3>{card.headline}</h3>
                            <p>
                              {card.stockCode} · {card.stockName} · {card.sectorName}
                            </p>
                            <div className="stock-analysis-page__pattern-tag" title={card.patternNote}>
                              形态(UI)：{card.pattern} · 距观察位 {card.distanceToBreakoutPct}
                            </div>
                          </div>
                          <div className="stock-analysis-page__candidate-actions">
                            <Button
                              type="link"
                              size="small"
                              data-testid={`stock-candidate-review-chart-${card.stockCode}`}
                              onClick={() => setDetailSelection({ code: card.stockCode, name: card.stockName })}
                            >
                              复核 K 线
                            </Button>
                            <span>观察</span>
                          </div>
                        </div>
                        <div className="stock-analysis-page__evidence-columns">
                          <div>
                            <h4>入选证据</h4>
                            <ul>
                              {card.evidenceBullets.map((item) => (
                                <li key={item.key}>
                                  <strong>{item.label}</strong>：{item.value}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4>反证 / 待补证据</h4>
                            <ul>
                              {card.counterEvidence.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4>失效条件</h4>
                            <ul>
                              {card.invalidationRules.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        <Collapse
                          ghost
                          bordered={false}
                          items={[
                            {
                              key: "raw",
                              label: "展开原始字段",
                              children: (
                                <dl className="stock-analysis-page__raw-grid">
                                  {card.rawFields.map((field) => (
                                    <div key={field.key}>
                                      <dt>{field.label}</dt>
                                      <dd>{field.value}</dd>
                                    </div>
                                  ))}
                                </dl>
                              ),
                            },
                          ]}
                        />
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">当前无候选股证据卡。</p>
                )}
                {candidateCards.length > 0 &&
                sectorFilterSectorCode &&
                filteredCandidates.length === 0 ? (
                  <p className="stock-analysis-page__empty">
                    该行业暂无候选卡片，可切换到其他行业复核。
                  </p>
                ) : null}
              </section>
            </div>

            <aside className="stock-analysis-page__rail" aria-label="股票分析辅助信息">
              <section className="stock-analysis-page__panel stock-analysis-page__panel--rail" data-testid="stock-analysis-risk-section">
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>风险退出观察</h2>
                    <p>展示风险退出项、观察项与可用的联动观察，不使用交易动作标签。</p>
                  </div>
                  <span className="stock-analysis-page__pill">退出观察价</span>
                </div>
                {confluenceQuery.isError ? (
                  <p className="stock-analysis-page__notice">联动观察暂不可用。</p>
                ) : null}
                {riskExitUnsupported ? (
                  <div className="stock-analysis-page__notice-block">
                    <strong>风险退出观察暂不可用。</strong>
                    <p>{riskExitUnsupported.reason}</p>
                  </div>
                ) : null}
                {riskRows.length > 0 ? (
                  <div className="stock-analysis-page__rail-list">
                    {riskRows.map((row) => (
                      <div
                        className="stock-analysis-page__rail-row stock-analysis-page__rail-row--interactive"
                        data-testid={`stock-risk-row-${row.stockCode}`}
                        key={`${row.stockCode}:${row.status}:${row.reason}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => setDetailSelection({ code: row.stockCode, name: row.stockName })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setDetailSelection({ code: row.stockCode, name: row.stockName });
                          }
                        }}
                      >
                        <div>
                          <strong>{row.stockName}</strong>
                          <small>{row.stockCode}</small>
                        </div>
                        <span>{riskStatusLabel(row.status)}</span>
                        <p className="stock-analysis-page__tabular">
                          最新收盘 {row.latestClose} · 退出观察价 {row.exitWatchPrice} · 距价 {row.distanceToExitPct}{" "}
                          <small>({row.exitDistanceBucket})</small>
                        </p>
                        <p>{row.reason}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">
                    {riskExitUnsupported
                      ? "等待持仓快照接入后生成风险退出观察项。"
                      : "当前无风险退出观察项。"}
                  </p>
                )}
              </section>

              <section className="stock-analysis-page__panel stock-analysis-page__panel--rail">
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>数据口径与边界</h2>
                    <p>只读链路的可追溯标签；完整诊断请看抽屉分组。</p>
                  </div>
                  <span className="stock-analysis-page__pill">只读链路</span>
                </div>
                <div className="stock-analysis-page__toolbar-meta">
                  {metaSegments.map((seg, index) => (
                    <span key={seg.key} className="stock-analysis-page__toolbar-meta-code">
                      {index > 0 ? " · " : null}
                      {`${seg.key}=${seg.text}`}
                    </span>
                  ))}
                </div>
                <Button type="link" aria-expanded={boundaryDrawerOpen} onClick={() => setBoundaryDrawerOpen(true)}>
                  查看完整诊断
                </Button>
                <Drawer
                  title="数据口径诊断"
                  open={boundaryDrawerOpen}
                  onClose={() => setBoundaryDrawerOpen(false)}
                  destroyOnClose
                  width={480}
                >
                  {strategyPayload ? (
                    <>
                      <Text strong type="danger">
                        严重 / Error
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "error")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                        {strategyPayload.diagnostics.filter((d) => d.severity === "error").length === 0 ? (
                          <li>暂无</li>
                        ) : null}
                      </ul>
                      <Text strong type="warning">
                        警告 / Warning
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "warning")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                        {strategyPayload.diagnostics.filter((d) => d.severity === "warning").length === 0 ? (
                          <li>暂无</li>
                        ) : null}
                      </ul>
                      <Text strong type="secondary">
                        信息 / Info
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "info")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                      </ul>
                      <Typography.Title level={5}>data_gaps</Typography.Title>
                      <ul>
                        {strategyPayload.data_gaps.map((g) => (
                          <li key={`${g.input_family}-${g.status}`}>
                            <strong>{g.input_family}</strong> {g.status}: {g.evidence}
                          </li>
                        ))}
                      </ul>
                      <Typography.Title level={5}>supported_outputs</Typography.Title>
                      <p>{strategyPayload.supported_outputs.join(", ") || "无"}</p>
                      <Typography.Title level={5}>unsupported_outputs</Typography.Title>
                      <ul>
                        {strategyPayload.unsupported_outputs.map((u) => (
                          <li key={u.key}>
                            <strong>{u.key}</strong>: {u.reason}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </Drawer>
              </section>
            </aside>
          </div>
        </>
      ) : null}
      <StockDetailDrawer
        stockCode={detailSelection?.code ?? null}
        stockName={detailSelection?.name}
        asOfDate={stockDetailAsOfDate}
        onClose={() => setDetailSelection(null)}
      />
      <Drawer
        title="Agent 复核当前观察"
        placement="left"
        width={480}
        open={agentDrawerOpen}
        onClose={() => setAgentDrawerOpen(false)}
        destroyOnClose
        className="stock-analysis-page__agent-drawer"
        data-testid="stock-analysis-agent-drawer"
        maskClosable
      >
        <div style={stockAnalysisPageCssVars} className="stock-analysis-page__agent-drawer-body">
          <AgentPanel
            pageId="stock-analysis"
            currentFilters={stockAnalysisAgentPageContext.current_filters}
            defaultFilters={{ research_domain: "stock" }}
            selectedRows={stockAnalysisAgentPageContext.selected_rows}
            contextNote={stockAnalysisAgentPageContext.context_note ?? null}
          />
        </div>
      </Drawer>
    </main>
  );
}
