import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import dayjs from "dayjs";

import type {
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  MacroVendorSeries,
} from "../../../api/contracts";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import { EM_DASH } from "../../../utils/format";
import { MarketDataFxThemeCard } from "../components/MarketDataFxThemeCard";
import { MarketDataSeriesCompactTable } from "../components/MarketDataSeriesCompactTable";
import { MarketDataSeriesTimeChart } from "../components/MarketDataSeriesTimeChart";
import { displayAxisUnit } from "../lib/charts/marketDataSeriesTimeChartOption";
import { seriesAgeTier, type SeriesAgeTier } from "../lib/marketDataCategoryStore";
import { seriesDisplayName } from "../lib/marketDataFormat";
import {
  classifyMacroThemeGroup,
  buildMacroCatalogById,
  groupMacroSeriesByTheme,
} from "../lib/marketDataMacroThemeGroups";
import "./MarketDataExplorerView.css";

type ExplorerDomain = "macro" | "fx";
type ExplorerTier = "all" | "stable" | "fallback";

/** 目录里"待补齐稳定链路"伪主题的 theme query 取值。 */
const MISSING_THEME_KEY = "missing";

const TIER_OPTIONS: ReadonlyArray<{ key: ExplorerTier; label: string }> = [
  { key: "all", label: "全部" },
  { key: "stable", label: "稳定" },
  { key: "fallback", label: "降级" },
];

/** 浏览器视图占用的 URL query 键；关闭视图时全部清除，不动 date 等页面级参数。 */
const EXPLORER_QUERY_KEYS = ["view", "domain", "theme", "tier", "q", "series"] as const;

const QUALITY_FLAG_LABELS: Record<string, string> = {
  ok: "数据正常",
  warning: "需复核",
  stale: "数据延迟",
  error: "不可用",
};

const SERIES_AGE_TIER_LABELS: Record<SeriesAgeTier, string> = {
  current: "近期更新",
  stale: "更新延迟（>90 天）",
  historical: "历史存量（>365 天）",
};

function fxAnalyticalGroupTitle(title: string) {
  const labels: Record<string, string> = {
    "Analytical FX: middle-rates": "外汇分析：中间价",
    "Analytical FX: indices": "外汇分析：指数",
    "Analytical FX: swap curves": "外汇分析：掉期曲线",
    "Analytical FX: event calendar": "外汇分析：事件日历",
  };
  return labels[title] ?? title;
}

function matchesSeriesQuery(
  point: { series_name: string; display_name?: string | null },
  needle: string,
): boolean {
  if (!needle) {
    return true;
  }
  return (
    (point.display_name ?? "").toLowerCase().includes(needle) ||
    point.series_name.toLowerCase().includes(needle)
  );
}

function ExplorerDirectoryEntry({
  testId,
  active,
  title,
  count,
  onSelect,
}: {
  testId: string;
  active: boolean;
  title: string;
  count: number;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className="market-data-explorer__entry"
      data-testid={testId}
      data-active={active ? "true" : "false"}
      aria-pressed={active}
      onClick={onSelect}
    >
      <span className="market-data-explorer__entry-title" title={title}>
        {title}
      </span>
      <span className="market-data-explorer__entry-count market-data-tabular">{count}</span>
    </button>
  );
}

type MarketDataExplorerViewProps = {
  stableSeries: readonly ChoiceMacroLatestPoint[];
  fallbackSeries: readonly ChoiceMacroLatestPoint[];
  missingStableSeries: readonly MacroVendorSeries[];
  catalog: readonly MacroVendorSeries[];
  fxGroups: readonly FxAnalyticalGroup[];
  /** 观察日（YYYY-MM-DD），用于行级/钻取时效分档；缺省回退当天。 */
  observationDate?: string;
  macroLoading: boolean;
  macroError: boolean;
  macroEmpty: boolean;
  onMacroRetry: () => void;
  fxLoading: boolean;
  fxError: boolean;
  onFxRetry: () => void;
};

export default function MarketDataExplorerView({
  stableSeries,
  fallbackSeries,
  missingStableSeries,
  catalog,
  fxGroups,
  observationDate,
  macroLoading,
  macroError,
  macroEmpty,
  onMacroRetry,
  fxLoading,
  fxError,
  onFxRetry,
}: MarketDataExplorerViewProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  // 来源筛选为目录辅助过滤，不进 URL 契约（URL 状态只承诺 view/domain/theme/tier/q/series）。
  const [sourceFilter, setSourceFilter] = useState("all");

  const domain: ExplorerDomain = searchParams.get("domain") === "fx" ? "fx" : "macro";
  const tierParam = searchParams.get("tier");
  const tier: ExplorerTier =
    tierParam === "stable" || tierParam === "fallback" ? tierParam : "all";
  const themeParam = searchParams.get("theme");
  const q = searchParams.get("q") ?? "";
  const selectedSeriesId = searchParams.get("series");
  const needle = q.trim().toLowerCase();

  const updateParams = useCallback(
    (mutate: (params: URLSearchParams) => void, options?: { replace?: boolean }) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          mutate(next);
          return next;
        },
        options,
      );
    },
    [setSearchParams],
  );

  const closeExplorer = () =>
    updateParams((params) => {
      for (const key of EXPLORER_QUERY_KEYS) {
        params.delete(key);
      }
    });
  const switchDomain = (next: ExplorerDomain) => {
    if (next === domain) {
      return;
    }
    updateParams((params) => {
      if (next === "fx") {
        params.set("domain", "fx");
      } else {
        params.delete("domain");
      }
      params.delete("theme");
      params.delete("tier");
      params.delete("series");
    });
  };
  const selectTheme = (key: string) =>
    updateParams((params) => {
      params.set("theme", key);
      params.delete("series");
    });
  const selectTier = (next: ExplorerTier) =>
    updateParams((params) => {
      if (next === "all") {
        params.delete("tier");
      } else {
        params.set("tier", next);
      }
    });
  // 搜索输入逐键更新，用 replace 语义避免每个字符占一条历史记录。
  const changeSearch = (value: string) =>
    updateParams(
      (params) => {
        if (value) {
          params.set("q", value);
        } else {
          params.delete("q");
        }
      },
      { replace: true },
    );
  const changeSelectedSeries = useCallback(
    (seriesId: string | null) =>
      updateParams((params) => {
        if (seriesId) {
          params.set("series", seriesId);
        } else {
          params.delete("series");
        }
      }),
    [updateParams],
  );

  const catalogById = useMemo(() => buildMacroCatalogById(catalog), [catalog]);
  const vendorOptions = useMemo(() => {
    const vendors = new Set<string>();
    for (const entry of catalog) {
      if (entry.vendor_name) {
        vendors.add(entry.vendor_name);
      }
    }
    for (const point of stableSeries) {
      if (point.vendor_name) {
        vendors.add(point.vendor_name);
      }
    }
    for (const point of fallbackSeries) {
      if (point.vendor_name) {
        vendors.add(point.vendor_name);
      }
    }
    return [...vendors].sort();
  }, [catalog, stableSeries, fallbackSeries]);

  const matchesFilters = useCallback(
    (point: ChoiceMacroLatestPoint) => {
      if (!matchesSeriesQuery(point, needle)) {
        return false;
      }
      if (sourceFilter === "all") {
        return true;
      }
      const vendor =
        catalogById.get(point.series_id)?.vendor_name ?? point.vendor_name ?? "";
      return vendor === sourceFilter;
    },
    [needle, sourceFilter, catalogById],
  );

  const filteredStable = useMemo(
    () => stableSeries.filter(matchesFilters),
    [stableSeries, matchesFilters],
  );
  const filteredFallback = useMemo(
    () => fallbackSeries.filter(matchesFilters),
    [fallbackSeries, matchesFilters],
  );
  const filteredMissing = useMemo(
    () => missingStableSeries.filter((series) => matchesSeriesQuery(series, needle)),
    [missingStableSeries, needle],
  );
  const stableGroups = useMemo(
    () => groupMacroSeriesByTheme(filteredStable, catalog),
    [filteredStable, catalog],
  );
  const fallbackGroups = useMemo(
    () => groupMacroSeriesByTheme(filteredFallback, catalog),
    [filteredFallback, catalog],
  );

  const stableVisible = tier !== "fallback";
  const fallbackVisible = tier !== "stable";

  const selectedPoint = useMemo(() => {
    if (!selectedSeriesId || domain !== "macro") {
      return null;
    }
    return (
      stableSeries.find((point) => point.series_id === selectedSeriesId) ??
      fallbackSeries.find((point) => point.series_id === selectedSeriesId) ??
      null
    );
  }, [selectedSeriesId, domain, stableSeries, fallbackSeries]);

  const resolvedTheme = useMemo(() => {
    if (domain !== "macro") {
      return null;
    }
    if (themeParam === MISSING_THEME_KEY && filteredMissing.length > 0) {
      return MISSING_THEME_KEY;
    }
    const visibleKeys = new Set<string>();
    if (stableVisible) {
      for (const group of stableGroups) {
        visibleKeys.add(group.key);
      }
    }
    if (fallbackVisible) {
      for (const group of fallbackGroups) {
        visibleKeys.add(group.key);
      }
    }
    if (themeParam && visibleKeys.has(themeParam)) {
      return themeParam;
    }
    // series 深链但 theme 缺省时，落到该序列所属主题，保证下方表格是它的同组上下文。
    if (selectedPoint) {
      const key = classifyMacroThemeGroup(selectedPoint, catalogById);
      if (visibleKeys.has(key)) {
        return key;
      }
    }
    if (stableVisible && stableGroups[0]) {
      return stableGroups[0].key;
    }
    if (fallbackVisible && fallbackGroups[0]) {
      return fallbackGroups[0].key;
    }
    return filteredMissing.length > 0 ? MISSING_THEME_KEY : null;
  }, [
    domain,
    themeParam,
    filteredMissing.length,
    stableVisible,
    fallbackVisible,
    stableGroups,
    fallbackGroups,
    selectedPoint,
    catalogById,
  ]);

  const panelGroup = useMemo(() => {
    if (domain !== "macro" || !resolvedTheme || resolvedTheme === MISSING_THEME_KEY) {
      return null;
    }
    const stableBucket = stableVisible
      ? stableGroups.find((group) => group.key === resolvedTheme)
      : undefined;
    const fallbackBucket = fallbackVisible
      ? fallbackGroups.find((group) => group.key === resolvedTheme)
      : undefined;
    const def = stableBucket ?? fallbackBucket;
    if (!def) {
      return null;
    }
    return {
      key: resolvedTheme,
      title: def.title,
      caption: def.caption,
      stableCount: stableBucket?.series.length ?? 0,
      fallbackCount: fallbackBucket?.series.length ?? 0,
      rows: [...(stableBucket?.series ?? []), ...(fallbackBucket?.series ?? [])],
    };
  }, [domain, resolvedTheme, stableVisible, fallbackVisible, stableGroups, fallbackGroups]);

  const resolvedObservationDate = observationDate ?? dayjs().format("YYYY-MM-DD");
  const selectedDetail = useMemo(() => {
    if (!selectedPoint) {
      return null;
    }
    const age = seriesAgeTier(selectedPoint.trade_date, resolvedObservationDate);
    const unit = displayAxisUnit(selectedPoint.unit);
    const quality = selectedPoint.quality_flag;
    return {
      point: selectedPoint,
      metaItems: [
        { label: "展示名", value: seriesDisplayName(selectedPoint) },
        { label: "原始名", value: selectedPoint.series_name },
        { label: "序列编号", value: selectedPoint.series_id },
        { label: "单位", value: unit || EM_DASH },
        { label: "最新日期", value: selectedPoint.trade_date || EM_DASH },
        {
          label: "质量",
          value: quality ? (QUALITY_FLAG_LABELS[quality] ?? quality) : EM_DASH,
        },
        { label: "时效档", value: SERIES_AGE_TIER_LABELS[age] },
      ],
    };
  }, [selectedPoint, resolvedObservationDate]);

  const fxCalendarEvents = useMemo(
    () => fxGroups.find((group) => group.group_key === "fx_event_calendar")?.events ?? [],
    [fxGroups],
  );
  const resolvedFxKey = useMemo(() => {
    if (domain !== "fx") {
      return null;
    }
    if (themeParam && fxGroups.some((group) => group.group_key === themeParam)) {
      return themeParam;
    }
    return fxGroups[0]?.group_key ?? null;
  }, [domain, themeParam, fxGroups]);
  const fxSelectedGroup = useMemo(() => {
    if (!resolvedFxKey) {
      return null;
    }
    const group = fxGroups.find((entry) => entry.group_key === resolvedFxKey);
    if (!group) {
      return null;
    }
    if (!needle) {
      return group;
    }
    return { ...group, series: group.series.filter((point) => matchesSeriesQuery(point, needle)) };
  }, [resolvedFxKey, fxGroups, needle]);
  const fxEmpty = !fxLoading && !fxError && fxGroups.length === 0;

  const searchInput = (
    <input
      type="search"
      className="market-data-explorer__search"
      data-testid="market-data-explorer-search"
      placeholder="搜索序列名称"
      aria-label="按名称搜索序列（同时匹配清洗名与原始名）"
      value={q}
      onChange={(event) => changeSearch(event.target.value)}
    />
  );

  const macroDirectory = (
    <nav
      className="market-data-explorer__directory"
      data-testid="market-data-explorer-directory"
      aria-label="宏观序列目录"
    >
      {searchInput}
      <div
        className="market-data-explorer__tier-filter"
        data-testid="market-data-explorer-tier-filter"
        role="group"
        aria-label="链路等级筛选"
      >
        {TIER_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            data-testid={`market-data-explorer-tier-${option.key}`}
            aria-pressed={tier === option.key}
            data-active={tier === option.key ? "true" : "false"}
            onClick={() => selectTier(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <select
        className="market-data-explorer__source-filter"
        data-testid="market-data-explorer-source-filter"
        aria-label="来源筛选"
        value={sourceFilter}
        onChange={(event) => setSourceFilter(event.target.value)}
      >
        <option value="all">全部来源</option>
        {vendorOptions.map((vendor) => (
          <option key={vendor} value={vendor}>
            {vendor}
          </option>
        ))}
      </select>

      {stableVisible ? (
        <details
          open
          className="market-data-explorer__tier-section"
          data-testid="market-data-macro-stable-theme-band"
        >
          <summary data-testid="market-data-macro-stable-tier-rail">
            稳定链路 {filteredStable.length} 条 · {stableGroups.length} 组
          </summary>
          {stableGroups.length > 0 ? (
            <div className="market-data-explorer__entry-list">
              {stableGroups.map((group) => (
                <ExplorerDirectoryEntry
                  key={`stable-${group.key}`}
                  testId={`market-data-macro-stable-theme-${group.key}`}
                  active={resolvedTheme === group.key}
                  title={group.title}
                  count={group.series.length}
                  onSelect={() => selectTheme(group.key)}
                />
              ))}
            </div>
          ) : (
            <div
              className="market-data-explorer__tier-empty"
              data-testid="market-data-macro-stable-theme-empty"
            >
              当前无稳定链路宏观序列。
            </div>
          )}
        </details>
      ) : null}

      {fallbackVisible ? (
        <details
          open
          className="market-data-explorer__tier-section"
          data-testid="market-data-macro-fallback-directory"
        >
          <summary data-testid="market-data-macro-fallback-tier-rail">
            降级链路 {filteredFallback.length} 条 · {fallbackGroups.length} 组
          </summary>
          {fallbackGroups.length > 0 ? (
            <div className="market-data-explorer__entry-list">
              {fallbackGroups.map((group) => (
                <ExplorerDirectoryEntry
                  key={`fallback-${group.key}`}
                  testId={`market-data-macro-fallback-group-${group.key}`}
                  active={resolvedTheme === group.key}
                  title={group.title}
                  count={group.series.length}
                  onSelect={() => selectTheme(group.key)}
                />
              ))}
            </div>
          ) : (
            <div
              className="market-data-explorer__tier-empty"
              data-testid="market-data-macro-fallback-theme-empty"
            >
              当前无降级链路宏观序列。
            </div>
          )}
        </details>
      ) : null}

      {filteredMissing.length > 0 ? (
        <ExplorerDirectoryEntry
          testId="market-data-macro-missing-stable-entry"
          active={resolvedTheme === MISSING_THEME_KEY}
          title="待补齐稳定链路"
          count={filteredMissing.length}
          onSelect={() => selectTheme(MISSING_THEME_KEY)}
        />
      ) : null}
    </nav>
  );

  const macroPanel = (
    <div className="market-data-explorer__panel" data-testid="market-data-explorer-panel">
      {resolvedTheme === MISSING_THEME_KEY ? (
        <section
          className="market-data-explorer__table-card"
          data-testid="market-data-missing-stable-section"
        >
          <header className="market-data-explorer__panel-head">
            <div>
              <h3 className="market-data-explorer__panel-title">待补齐稳定链路</h3>
              <p className="market-data-explorer__panel-caption">
                目录声明为稳定链路、当前观察日尚未回收到最新值的序列。
              </p>
            </div>
            <span className="market-data-explorer__panel-count market-data-tabular">
              {filteredMissing.length} 条
            </span>
          </header>
          <div className="market-data-stack-gap-3">
            {filteredMissing.map((series) => (
              <div key={series.series_id} className="market-data-catalog-row">
                <strong title={series.series_name}>{seriesDisplayName(series)}</strong>
                <div className="market-data-catalog-meta">
                  {series.frequency} · {displayAxisUnit(series.unit) || EM_DASH} ·{" "}
                  {series.series_id}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : panelGroup ? (
        <>
          {selectedDetail ? (
            <section
              className="market-data-explorer__detail"
              data-testid="market-data-explorer-series-detail"
            >
              <header className="market-data-explorer__panel-head">
                <div>
                  <h3 className="market-data-explorer__panel-title">
                    {seriesDisplayName(selectedDetail.point)}
                  </h3>
                  <p className="market-data-explorer__panel-caption">
                    单序列走势与元数据（分析口径观察）。
                  </p>
                </div>
                <button
                  type="button"
                  className="market-data-explorer__detail-close"
                  data-testid="market-data-explorer-series-detail-close"
                  onClick={() => changeSelectedSeries(null)}
                >
                  收起走势
                </button>
              </header>
              <MarketDataSeriesTimeChart
                series={selectedDetail.point}
                height={220}
                testId="market-data-explorer-series-detail-chart"
              />
              <dl
                className="market-data-explorer__detail-meta"
                data-testid="market-data-explorer-series-detail-meta"
              >
                {selectedDetail.metaItems.map((item) => (
                  <div key={item.label}>
                    <dt>{item.label}</dt>
                    <dd className="market-data-tabular" title={item.value}>
                      {item.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
          <section className="market-data-explorer__table-card">
            <header className="market-data-explorer__panel-head">
              <div>
                <h3 className="market-data-explorer__panel-title">{panelGroup.title}</h3>
                <p className="market-data-explorer__panel-caption">{panelGroup.caption}</p>
              </div>
              <span className="market-data-explorer__panel-count market-data-tabular">
                {tier === "all"
                  ? `稳定 ${panelGroup.stableCount} · 降级 ${panelGroup.fallbackCount}`
                  : `${panelGroup.rows.length} 条`}
              </span>
            </header>
            <MarketDataSeriesCompactTable
              series={panelGroup.rows}
              testIdPrefix="market-data-explorer-series"
              showTier={tier === "all"}
              compactSparseColumns
              observationDate={observationDate}
              selectedSeriesId={selectedSeriesId}
              onSelectedSeriesChange={changeSelectedSeries}
            />
          </section>
        </>
      ) : (
        <div
          className="market-data-explorer__tier-empty"
          data-testid="market-data-explorer-panel-empty"
        >
          当前筛选下无可展示主题。
        </div>
      )}
    </div>
  );

  const fxDirectory = (
    <nav
      className="market-data-explorer__directory"
      data-testid="market-data-explorer-fx-directory"
      aria-label="外汇分组目录"
    >
      {searchInput}
      <details
        open
        className="market-data-explorer__tier-section"
        data-testid="market-data-fx-theme-band"
      >
        <summary data-testid="market-data-fx-tier-rail">外汇分析 · {fxGroups.length} 组</summary>
        <div className="market-data-explorer__entry-list">
          {fxGroups.map((group) => (
            <ExplorerDirectoryEntry
              key={group.group_key}
              testId={`market-data-fx-explorer-group-${group.group_key}`}
              active={resolvedFxKey === group.group_key}
              title={fxAnalyticalGroupTitle(group.title)}
              count={group.series.length + (group.events?.length ?? 0)}
              onSelect={() => selectTheme(group.group_key)}
            />
          ))}
        </div>
      </details>
    </nav>
  );

  const fxPanel = (
    <div className="market-data-explorer__panel" data-testid="market-data-explorer-panel">
      {fxSelectedGroup ? (
        <MarketDataFxThemeCard
          group={fxSelectedGroup}
          title={fxAnalyticalGroupTitle(fxSelectedGroup.title)}
          contextEvents={
            fxSelectedGroup.group_key === "fx_index" ? fxCalendarEvents : undefined
          }
        />
      ) : (
        <div
          className="market-data-explorer__tier-empty"
          data-testid="market-data-explorer-panel-empty"
        >
          当前无可展示外汇分组。
        </div>
      )}
    </div>
  );

  return (
    <section className="market-data-explorer" data-testid="market-data-explorer-view">
      <header className="market-data-explorer__head">
        <div className="market-data-explorer__titles">
          <span className="market-data-explorer__kicker">序列浏览器</span>
          <h2 className="market-data-explorer__title">宏观与外汇序列</h2>
          <p className="market-data-explorer__summary market-data-tabular">
            稳定 {stableSeries.length} · 降级 {fallbackSeries.length} · 外汇 {fxGroups.length} 组
            {missingStableSeries.length > 0 ? ` · 待补齐 ${missingStableSeries.length}` : ""}
          </p>
        </div>
        <div className="market-data-explorer__head-actions">
          <div
            className="market-data-explorer__domain-switch"
            role="group"
            aria-label="序列域切换"
          >
            <button
              type="button"
              data-testid="market-data-explorer-domain-macro"
              aria-pressed={domain === "macro"}
              data-active={domain === "macro" ? "true" : "false"}
              onClick={() => switchDomain("macro")}
            >
              宏观序列
            </button>
            <button
              type="button"
              data-testid="market-data-explorer-domain-fx"
              aria-pressed={domain === "fx"}
              data-active={domain === "fx" ? "true" : "false"}
              onClick={() => switchDomain("fx")}
            >
              外汇分析
            </button>
          </div>
          <button
            type="button"
            className="market-data-explorer__close"
            data-testid="market-data-explorer-close"
            onClick={closeExplorer}
          >
            返回驾驶舱
          </button>
        </div>
      </header>

      {domain === "macro" ? (
        <PageAsyncSection
          title="宏观序列"
          hideHeading
          isLoading={macroLoading}
          isError={macroError}
          isEmpty={macroEmpty && missingStableSeries.length === 0}
          fillHeight={false}
          onRetry={onMacroRetry}
        >
          <div
            className="market-data-explorer__layout"
            data-testid="market-data-macro-series-deck"
          >
            {macroDirectory}
            {macroPanel}
          </div>
        </PageAsyncSection>
      ) : (
        <PageAsyncSection
          title="外汇分析"
          hideHeading
          isLoading={fxLoading}
          isError={fxError}
          isEmpty={fxEmpty}
          fillHeight={false}
          onRetry={onFxRetry}
        >
          <div
            className="market-data-explorer__layout"
            data-testid="market-data-fx-series-deck"
          >
            {fxDirectory}
            {fxPanel}
          </div>
        </PageAsyncSection>
      )}
    </section>
  );
}
