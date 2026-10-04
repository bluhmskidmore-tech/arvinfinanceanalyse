import type {
  ModuleHomeSourceQueries,
  ModuleHomeDataState,
  ModuleHomeKpi,
  ModuleHomeDataNote,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { UseQueryResult } from "@tanstack/react-query";
import {
  queryIsInitialLoading,
  queryHasData,
  queryResultMeta,
  resultMetaIsStale,
  resultMetaIsPartial,
  baseDataNote,
  metaEvidenceLine,
  combinedQueryStatus,
  queryStatus,
  MODULE_HOME_STATE_LABEL,
} from "./moduleHomeSourceState";
import type { ResultMeta } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { buildMarketDataTerminalModel } from "../../market-data/lib/marketDataTerminalModel";
import {
  choiceSeriesById,
  enrichMarketHomeRows,
} from "./marketHomeRowEnrichment";
import {
  buildMarketKeyRateRows,
  buildDerivedSpreadRows,
  mergeDerivedSpreads,
  macroPointToDetailRow,
  buildPercentRateChart,
  buildLatestMacroSnapshotRows,
  buildYieldCurveQuoteRows,
  catalogTierCounts,
  buildNewsEventsSnapshotRows,
  findMacroPoint,
} from "./marketHomeDetailModel";
import {
  buildDetailPanel,
  envelopeMeta,
} from "./moduleHomePresentation";
import type {
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeDetailTypes";
import {
  mergeMacroToolkitAnalysis,
  buildMacroToolkitOverviewRows,
  buildMacroToolkitSignalRows,
  buildMacroToolkitCapabilityRows,
  buildMacroToolkitIndicatorRows,
  buildMacroToolkitStrategyRows,
  buildMacroToolkitAShareRiskRows,
  buildMacroToolkitHasonRows,
  buildMacroToolkitShadowRows,
  buildMacroToolkitRuntimeRows,
  formatAShareRiskStance,
  aShareRiskModuleTone,
} from "./marketMacroToolkitHomeModel";
import { formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  macroToolkitModuleTone,
  buildMarketCrisisExplain,
  buildMarketDeskIntel,
} from "./marketDeskIntelModel";

function marketHomeDataState(
  queries: ModuleHomeSourceQueries,
  hasContent: boolean,
): ModuleHomeDataState {
  const active = [
    queries.choiceLatest,
    queries.marketRates,
    queries.marketCatalog,
    queries.macroToolkitAnalysis,
    queries.macroToolkitStrategySummaries,
    queries.newsEvents,
  ].filter(Boolean) as Array<UseQueryResult<unknown>>;

  if (active.some((query) => queryIsInitialLoading(query))) {
    return "loading";
  }

  const withData = active.filter((query) => queryHasData(query));
  const withError = active.filter((query) => query.isError);
  if (withError.length > 0) {
    return withData.length > 0 ? "partial" : "error";
  }
  if (active.length === 0 || withData.length === 0 || !hasContent) {
    return "empty";
  }
  if (withData.length < active.length) {
    return "partial";
  }

  const metas = withData.map((query) => queryResultMeta(query));
  if (metas.some((meta) => resultMetaIsStale(meta))) {
    return "stale";
  }
  if (metas.some((meta) => !meta || resultMetaIsPartial(meta))) {
    return "partial";
  }
  return "ready";
}

function marketDataMeta(
  source: string,
  meta: ResultMeta | undefined,
  fallbackDate?: string,
) {
  const date =
    meta?.as_of_date ?? meta?.resolved_report_date ?? meta?.fallback_date ?? fallbackDate ?? EM_DASH;
  const dateIsFallback = Boolean(
    meta && !meta.as_of_date && !meta.resolved_report_date && meta.fallback_date,
  );
  const isFallback = Boolean(meta?.fallback_mode && meta.fallback_mode !== "none") || dateIsFallback;
  const isStale = meta?.quality_flag === "stale";
  const markers = [isStale ? "[stale]" : null, isFallback ? "[fallback]" : null].filter(
    (marker): marker is string => Boolean(marker),
  );
  return markers.length > 0 ? `来源 ${source} · ${date} ${markers.join(" ")}` : `来源 ${source} · ${date}`;
}

/**
 * 市场首页专用：query 已失败且无历史缓存数据时，KPI 需要显示EM_DASH+error，
 * 不能与"接口成功但真实返回 0 条"混淆展示为裸数字 "0"。
 */
function marketSeriesCountKpiFields(
  query: UseQueryResult<unknown> | undefined,
  count: number,
  detail: string,
  failedDetail: string,
): Pick<ModuleHomeKpi, "value" | "tone" | "detail"> {
  if (query?.isError && query.data === undefined) {
    return { value: EM_DASH, tone: "error", detail: failedDetail };
  }
  return { value: `${count}`, tone: count > 0 ? "ok" : "watch", detail };
}

function marketDataNote(queries: ModuleHomeSourceQueries): ModuleHomeDataNote {
  const base = baseDataNote("market", queries);
  const evidenceLines = [
    metaEvidenceLine("Choice最新", queries.choiceLatest?.data?.result_meta),
    metaEvidenceLine("市场利率", queries.marketRates?.data?.result_meta),
    metaEvidenceLine("数据目录", queries.marketCatalog?.data?.result_meta),
    metaEvidenceLine("宏观工具", queries.macroToolkitAnalysis?.data?.result_meta),
  ].filter((line): line is string => Boolean(line));

  return {
    ...base,
    lines: [...base.lines, ...evidenceLines],
  };
}

export function marketView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const latestSeries = queries.choiceLatest?.data?.result.series ?? [];
  const rateSeries = queries.marketRates?.data?.result.series ?? [];
  const catalogSeries = queries.marketCatalog?.data?.result.series ?? [];
  const ratesMeta = queries.marketRates?.data?.result_meta;
  const latestMeta = queries.choiceLatest?.data?.result_meta;
  const catalogMeta = queries.marketCatalog?.data?.result_meta;
  const terminalModel = buildMarketDataTerminalModel({
    ratesEnvelope: queries.marketRates?.data,
    latestEnvelope: queries.choiceLatest?.data,
  });
  const tenYear =
    latestSeries.find((item) => ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"].includes(item.series_id)) ??
    latestSeries.find((item) => item.series_name.includes("10年")) ??
    rateSeries.find((item) => ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"].includes(item.series_id)) ??
    rateSeries.find((item) => item.series_name.includes("10年"));

  const seriesById = choiceSeriesById(latestSeries, rateSeries);
  const baseKeyRateRows = buildMarketKeyRateRows(latestSeries, rateSeries, terminalModel);
  const spreadTradeDate =
    baseKeyRateRows[0]?.tradeDate ?? latestSeries[0]?.trade_date ?? rateSeries[0]?.trade_date ?? EM_DASH;
  const keyRateRows = enrichMarketHomeRows(
    [
      ...baseKeyRateRows,
      ...buildDerivedSpreadRows(
        mergeDerivedSpreads(
          queries.marketRates?.data?.result.derived_spreads,
          queries.choiceLatest?.data?.result.derived_spreads,
        ),
        spreadTradeDate,
      ),
    ],
    seriesById,
  );
  const keyRateStatus = combinedQueryStatus(
    "key-rates",
    "关键利率快照",
    [queries.choiceLatest, queries.marketRates],
    keyRateRows.length > 0
      ? `已匹配 ${keyRateRows.length} 条关键利率点。`
      : "未匹配到关键利率点，前端不补数。",
  );
  const keyRateSnapshotPanel = buildDetailPanel({
    key: "key-rate-snapshot",
    title: "关键利率快照",
    meta: marketDataMeta(
      "choice-latest / market-data",
      ratesMeta ?? latestMeta,
      keyRateRows[0]?.tradeDate,
    ),
    status: keyRateStatus,
    rows: keyRateRows,
  });

  const formalRateRows: ModuleHomeDetailRow[] = rateSeries.slice(0, 24).map((point) =>
    macroPointToDetailRow(point, point.series_name, point.series_id),
  );
  const formalRateStatus = queryStatus(
    "formal-rates",
    "正式利率序列",
    queries.marketRates,
    formalRateRows.length > 0
      ? `market-data rates 已返回 ${rateSeries.length} 条。`
      : "正式利率序列为空。",
  );
  const formalRatePanel = buildDetailPanel({
    key: "formal-rate-series",
    title: "正式利率序列",
    meta: marketDataMeta("market-data", ratesMeta),
    status: formalRateStatus,
    rows: formalRateRows,
    chart: buildPercentRateChart(formalRateRows, "正式利率对比"),
  });

  const keyRateSeriesIds = new Set(keyRateRows.map((row) => row.source).filter((source) => source !== EM_DASH));
  const macroSnapshotRows = enrichMarketHomeRows(
    buildLatestMacroSnapshotRows(latestSeries, keyRateSeriesIds),
    seriesById,
  );
  const macroSnapshotStatus = queryStatus(
    "macro-snapshot",
    "跨资产快讯",
    queries.choiceLatest,
    macroSnapshotRows.length > 0
      ? `Choice latest 已匹配 ${macroSnapshotRows.length} 条跨资产观察点。`
      : "未匹配到跨资产快讯，前端不补数。",
  );
  const macroSnapshotPanel = buildDetailPanel({
    key: "latest-macro-snapshot",
    title: "跨资产快讯",
    meta: marketDataMeta("choice-latest", latestMeta, macroSnapshotRows[0]?.tradeDate),
    status: macroSnapshotStatus,
    rows: macroSnapshotRows,
  });

  const curveQuoteRows = buildYieldCurveQuoteRows(terminalModel);
  const curveQuoteStatus = combinedQueryStatus(
    "yield-curve",
    "收益率曲线",
    [queries.choiceLatest, queries.marketRates],
    curveQuoteRows.length > 0
      ? `已匹配 ${curveQuoteRows.length} 条国债/国开曲线点。`
      : "曲线报价为空。",
  );
  const yieldCurvePanel = buildDetailPanel({
    key: "yield-curve-quotes",
    title: "国债与国开曲线",
    meta: marketDataMeta("market-data terminal", ratesMeta ?? latestMeta, curveQuoteRows[0]?.tradeDate),
    status: curveQuoteStatus,
    rows: curveQuoteRows,
    chart: buildPercentRateChart(curveQuoteRows, "收益率对比"),
  });

  const tierCounts = catalogTierCounts(catalogSeries);
  const catalogSummaryRows: ModuleHomeDetailRow[] = [
    {
      key: "catalog-total",
      label: "已注册序列",
      value: `${catalogSeries.length} 条`,
      tradeDate: EM_DASH,
      source: "catalog",
      tone: catalogSeries.length > 0 ? "ok" : "watch",
    },
    {
      key: "catalog-stable",
      label: "stable 序列",
      value: `${tierCounts.stable} 条`,
      tradeDate: EM_DASH,
      source: "refresh_tier",
      tone: tierCounts.stable > 0 ? "ok" : "muted",
    },
    {
      key: "catalog-fallback",
      label: "fallback 序列",
      value: `${tierCounts.fallback} 条`,
      tradeDate: EM_DASH,
      source: "refresh_tier",
      tone: tierCounts.fallback > 0 ? "watch" : "muted",
    },
    ...catalogSeries.slice(0, 8).map((item) => ({
      key: `catalog-${item.series_id}`,
      label: item.series_name,
      value: item.unit ? `${item.unit}` : EM_DASH,
      tradeDate: item.frequency ?? EM_DASH,
      source: item.series_id,
      tone: "muted" as ModuleHomeTone,
    })),
  ];
  const catalogStatus = queryStatus(
    "catalog-overview",
    "数据目录",
    queries.marketCatalog,
    catalogSeries.length > 0 ? `catalog 已注册 ${catalogSeries.length} 条序列。` : "目录为空。",
  );
  const catalogPanel = buildDetailPanel({
    key: "catalog-overview",
    title: "数据目录概览",
    meta: marketDataMeta("market-data catalog", catalogMeta),
    status: catalogStatus,
    rows: catalogSummaryRows,
  });

  const macroAnalysis = mergeMacroToolkitAnalysis(
    queries.macroToolkitAnalysis?.data?.result,
    queries.macroToolkitStrategySummaries?.data?.result,
  );
  const newsEventsPayload = queries.newsEvents?.data?.result;
  const newsEventsStatus = queryStatus(
    "news-events",
    "新闻事件",
    queries.newsEvents,
    newsEventsPayload
      ? `新闻事件流已返回 ${newsEventsPayload.total_rows} 条事件摘要。`
      : "新闻事件摘要待读取。",
  );
  const macroToolkitMeta = queries.macroToolkitAnalysis?.data?.result_meta;
  const macroToolkitStatus = queryStatus(
    "macro-toolkit",
    "宏观工具",
    queries.macroToolkitAnalysis,
    macroAnalysis
      ? `${macroAnalysis.conclusion.stance} · 命中 ${macroAnalysis.coverage.hit_count}/${macroAnalysis.coverage.indicator_count}`
      : "宏观工具分析待接入或读取失败。",
  );
  const macroOverviewPanel = buildDetailPanel({
    key: "macro-toolkit-overview",
    title: "宏观工具结论",
    meta: marketDataMeta("macro-toolkit / analysis", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitOverviewRows(macroAnalysis) : [],
  });
  const macroSignalPanel = buildDetailPanel({
    key: "macro-toolkit-signals",
    title: "宏观信号卡片",
    meta: marketDataMeta("macro-toolkit / signal_cards", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitSignalRows(macroAnalysis) : [],
  });
  const macroCapabilityPanel = buildDetailPanel({
    key: "macro-toolkit-capabilities",
    title: "能力模块",
    meta: marketDataMeta("macro-toolkit / capabilities", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitCapabilityRows(macroAnalysis) : [],
  });
  const macroIndicatorPanel = buildDetailPanel({
    key: "macro-toolkit-indicators",
    title: "工具指标",
    meta: marketDataMeta("macro-toolkit / indicators", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitIndicatorRows(macroAnalysis.indicators) : [],
  });
  const macroStrategyPanel = buildDetailPanel({
    key: "macro-toolkit-strategies",
    title: "策略摘要",
    meta: marketDataMeta("macro-toolkit / strategies", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitStrategyRows(macroAnalysis) : [],
  });
  const macroAShareRiskPanel = buildDetailPanel({
    key: "macro-toolkit-a-share-risk",
    title: "A股踩踏风险",
    meta: marketDataMeta("macro-toolkit / a_share_risk", macroToolkitMeta, macroAnalysis?.a_share_risk?.trade_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis?.a_share_risk ? buildMacroToolkitAShareRiskRows(macroAnalysis.a_share_risk) : [],
  });
  const macroHasonPanel = buildDetailPanel({
    key: "macro-toolkit-hason",
    title: "Hason 宏观策略",
    meta: marketDataMeta("macro-toolkit / hason_strategy", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis?.hason_strategy ? buildMacroToolkitHasonRows(macroAnalysis.hason_strategy) : [],
  });
  const macroShadowPanel = buildDetailPanel({
    key: "macro-toolkit-shadow",
    title: "影子组合报告",
    meta: marketDataMeta(
      "macro-toolkit / shadow_portfolio",
      macroToolkitMeta,
      macroAnalysis?.shadow_portfolio_report?.as_of_date ?? undefined,
    ),
    status: macroToolkitStatus,
    rows: macroAnalysis?.shadow_portfolio_report
      ? buildMacroToolkitShadowRows(macroAnalysis.shadow_portfolio_report)
      : [],
  });
  const macroRuntimePanel = buildDetailPanel({
    key: "macro-toolkit-runtime",
    title: "数据运行时",
    meta: marketDataMeta("macro-toolkit / runtime", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitRuntimeRows(macroAnalysis) : [],
  });
  const newsEventsSnapshotRows = buildNewsEventsSnapshotRows(newsEventsPayload);
  const newsEventsPanel = buildDetailPanel({
    key: "news-events-snapshot",
    title: "新闻事件",
    meta: marketDataMeta("Tushare 备份链路", queries.newsEvents?.data?.result_meta),
    status: newsEventsStatus,
    rows: newsEventsSnapshotRows,
  });

  const dataState = marketHomeDataState(
    queries,
    latestSeries.length > 0 ||
      rateSeries.length > 0 ||
      catalogSeries.length > 0 ||
      Boolean(macroAnalysis) ||
      Boolean(newsEventsPayload?.total_rows),
  );
  const stateDetail =
    dataState === "loading"
      ? "正在读取最新行情、正式利率、数据目录、宏观分析与新闻事件。"
      : dataState === "error"
        ? "市场读链路失败，不使用前端补数；请重试或进入数据核验区检查来源。"
        : dataState === "empty"
          ? "市场读链路已完成，但未返回可展示行情或分析结果；请刷新数据并核验来源。"
          : dataState === "partial"
            ? "部分市场来源暂不可用；已返回的数据继续展示，不使用前端补数。"
            : dataState === "stale"
              ? "市场数据已返回，但存在过期来源；形成判断前请先核验报告日与供应方状态。"
              : `最新行情 ${latestSeries.length} 条，正式利率序列 ${rateSeries.length} 条。`;

  return {
    dataState,
    stateLabel: MODULE_HOME_STATE_LABEL[dataState],
    stateDetail,
    kpis: [
      {
        key: "macro-series",
        label: "最新行情",
        ...marketSeriesCountKpiFields(
          queries.choiceLatest,
          latestSeries.length,
          "Choice latest series 数量。",
          "Choice latest 读取失败，不使用前端补数。",
        ),
      },
      {
        key: "ten-year-rate",
        label: "10年利率",
        value: tenYear ? formatChoiceMacroValue(tenYear, { spaceBeforeUnit: false }) : EM_DASH,
        detail: tenYear ? `${tenYear.series_name} / ${tenYear.trade_date}` : "未返回 10 年利率点。",
        tone: tenYear ? "ok" : "watch",
      },
      {
        key: "rate-series",
        label: "正式利率",
        ...marketSeriesCountKpiFields(
          queries.marketRates,
          rateSeries.length,
          `market-data rates，${envelopeMeta(queries.marketRates)}`,
          "market-data rates 读取失败，不使用前端补数。",
        ),
      },
      {
        key: "catalog-series",
        label: "目录序列",
        ...marketSeriesCountKpiFields(
          queries.marketCatalog,
          catalogSeries.length,
          "market data catalog 已注册序列数。",
          "market data catalog 读取失败，不使用前端补数。",
        ),
      },
      ...(macroAnalysis
        ? [
            {
              key: "macro-toolkit-hit",
              label: "工具命中率",
              value: `${(macroAnalysis.coverage.hit_rate * 100).toFixed(1)}%`,
              detail: `${macroAnalysis.coverage.hit_count}/${macroAnalysis.coverage.indicator_count} 指标 · ${macroAnalysis.coverage.script_count} 脚本`,
              tone: (macroAnalysis.coverage.hit_rate >= 0.7 ? "ok" : "watch") as ModuleHomeTone,
            },
          ]
        : []),
    ],
    statuses: [
      queryStatus("choice", "最新行情", queries.choiceLatest, "Choice latest 已返回。"),
      queryStatus("rates", "市场数据", queries.marketRates, "market-data rates 已返回。"),
      queryStatus("catalog", "数据目录", queries.marketCatalog, "catalog 已返回。"),
      macroToolkitStatus,
      newsEventsStatus,
      {
        key: "cross-asset",
        label: "跨资产",
        value: "下钻页",
        detail: "跨资产传导解释以 /cross-asset 为准。",
        tone: "muted" as ModuleHomeTone,
      },
      ...(macroAnalysis?.a_share_risk
        ? [
            {
              key: "a-share-risk",
              label: "A股踩踏风险",
              value: formatAShareRiskStance(macroAnalysis.a_share_risk.risk_name),
              detail: macroAnalysis.a_share_risk.summary,
              tone: aShareRiskModuleTone(macroAnalysis.a_share_risk),
            },
          ]
        : []),
    ],
    briefings: (() => {
      const csi300 = findMacroPoint(latestSeries, rateSeries, ["CA.CSI300"], ["沪深300"]);
      const csiChg = findMacroPoint(latestSeries, rateSeries, ["CA.CSI300_PCT_CHG"], ["沪深300", "涨跌幅"]);
      const brent = findMacroPoint(latestSeries, rateSeries, ["CA.BRENT"], ["Brent", "布伦特"]);
      const dr007 = keyRateRows.find((row) => row.key === "dr007");

      return [
        {
          title: "利率快照",
          conclusion: tenYear
            ? `${tenYear.series_name} 最新值 ${formatChoiceMacroValue(tenYear, { spaceBeforeUnit: false })}${
                dr007 ? `；${dr007.label} ${dr007.value}` : ""
              }。`
            : keyRateRows.length > 0
              ? `已返回 ${keyRateRows.length} 条关键利率点，10Y 国债待下钻页核验。`
              : "未返回可用 10 年利率点。",
          evidence: "稳定序列编码优先，名称匹配兜底；完整曲线见下方国债/国开区。",
          tone: tenYear || keyRateRows.length > 0 ? "ok" : "watch",
        },
        {
          title: "跨资产传导",
          conclusion:
            csi300 && csiChg
              ? `沪深300 ${formatChoiceMacroValue(csi300, { spaceBeforeUnit: false })}，日变动 ${formatChoiceMacroValue(
                  csiChg,
                  { spaceBeforeUnit: false },
                )}。`
              : csi300
                ? `沪深300 ${formatChoiceMacroValue(csi300, { spaceBeforeUnit: false })}，完整传导见跨资产页。`
                : brent
                  ? `${brent.series_name} ${formatChoiceMacroValue(brent, { spaceBeforeUnit: false })}，跨资产解释进入 /cross-asset。`
                  : macroSnapshotRows.length > 0
                    ? `已返回 ${macroSnapshotRows.length} 条跨资产观察点，完整传导见 /cross-asset。`
                    : "跨资产解释仍进入 /cross-asset 阅读。",
          evidence: "首页仅展示 Choice latest 已返回的观察点，不把观察口径提升为正式结论。",
          tone: csi300 || brent || macroSnapshotRows.length > 0 ? "ok" : "muted",
        },
        {
          title: "事件状态",
          conclusion: newsEventsPayload
            ? newsEventsSnapshotRows.length > 1
              ? `新闻事件（Tushare 备份链路）已返回 ${newsEventsPayload.total_rows} 条；最新 ${newsEventsSnapshotRows[1]?.value ?? "待解析"}。`
              : `新闻事件（Tushare 备份链路）已注册 ${newsEventsPayload.total_rows} 条事件摘要。`
            : "新闻事件摘要待读取。",
          evidence: newsEventsSnapshotRows.length > 1
            ? `最近收到 ${newsEventsSnapshotRows[1]?.tradeDate ?? EM_DASH} · 进入 /news-events 查看全文。`
            : "首页仅展示事件计数与最新标题，完整列表见新闻事件页。",
          tone: newsEventsPayload && newsEventsPayload.total_rows > 0 ? "ok" : "muted",
        },
        {
          title: "宏观工具",
          conclusion: macroAnalysis
            ? `${macroAnalysis.conclusion.stance}：${macroAnalysis.conclusion.summary}`
            : `正式利率序列 ${rateSeries.length} 条，目录序列 ${catalogSeries.length} 条；宏观工具分析待读取。`,
          evidence: macroAnalysis
            ? `${macroAnalysis.conclusion.recommended_action}（工具口径，非正式经营结论）。`
            : "脚本注册表、信号卡片与能力模块由 /macro-toolkit 呈现。",
          tone: macroAnalysis ? macroToolkitModuleTone(macroAnalysis.conclusion.tone) : "muted",
        },
      ];
    })(),
    detailPanels: [
      keyRateSnapshotPanel,
      formalRatePanel,
      catalogPanel,
      macroSnapshotPanel,
      yieldCurvePanel,
      macroOverviewPanel,
      macroSignalPanel,
      macroCapabilityPanel,
      macroIndicatorPanel,
      macroStrategyPanel,
      macroAShareRiskPanel,
      macroHasonPanel,
      macroShadowPanel,
      macroRuntimePanel,
      newsEventsPanel,
    ],
    marketCrisisExplain: buildMarketCrisisExplain(macroAnalysis),
    marketDeskIntel: buildMarketDeskIntel(macroAnalysis),
    dataNote: marketDataNote(queries),
  };
}
