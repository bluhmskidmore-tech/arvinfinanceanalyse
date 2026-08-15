import type { Dispatch, SetStateAction } from "react";
import {
  BarChartOutlined,
  DatabaseOutlined,
  FireOutlined,
  StockOutlined,
} from "@ant-design/icons";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import { CompactStatusTile, StatusIcon } from "./StockAnalysisStatusPrimitives";
import { lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import {
  buildRankContextDetailSelection,
  type StockDetailSelection,
} from "../lib/stockAnalysisDetailSelection";
import type {
  StockSectorHeavyweightPreviewRow,
  StockSectorHeavyweightPreviewSummary,
  StockThemeLeaderPreviewItem,
} from "../lib/stockAnalysisPageModel";
import type { StockHeavyweightTrendIndex } from "../lib/stockHeavyweightTrendView";
import { StockAnalysisTrendSparkline } from "./StockAnalysisTrendSparkline";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";

export type StockAnalysisDeepSelectionOverviewProps = {
  themeBreakoutCount: number;
  themeLeaderPreviewItems: StockThemeLeaderPreviewItem[];
  themeBreakoutUnsupported: boolean;
  themeBreakoutBlockerLabel: string | null;
  themeBreakoutBlockerText: string | null;
  sectorHeavyweightPreview: StockSectorHeavyweightPreviewSummary | null;
  sectorHeavyweightRows: StockSectorHeavyweightPreviewRow[];
  heavyweightTrends?: StockHeavyweightTrendIndex | null;
  /** Ref for the deferred-visibility gate that enables the trend request. */
  heavyweightSectionRef?: (node: HTMLElement | null) => void;
  strategyPayload: LivermoreStrategyPayload | null;
  setDetailSelection: Dispatch<SetStateAction<StockDetailSelection | null>>;
};

const HEAVYWEIGHT_STOCKS_PER_CARD = 3;

export function StockAnalysisDeepSelectionOverview({
  themeBreakoutCount,
  themeLeaderPreviewItems,
  themeBreakoutUnsupported,
  themeBreakoutBlockerLabel,
  themeBreakoutBlockerText,
  sectorHeavyweightPreview,
  sectorHeavyweightRows,
  heavyweightTrends,
  heavyweightSectionRef,
  strategyPayload,
  setDetailSelection,
}: StockAnalysisDeepSelectionOverviewProps) {
  return (
    <>
                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-theme-leaders-first-screen"
                    data-testid="stock-analysis-theme-leaders-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="stock-analysis-page__min-w-0">
                        <p className={SA_SECTION_EYEBROW}>题材突变</p>
                        <h2 className={SA_CARD_TITLE}>题材突破领涨股</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="题材突破状态">
                          <span className="stock-analysis-page__signal-pill">
                            <FireOutlined aria-hidden="true" /> 题材 {themeBreakoutCount}
                          </span>
                          <span className="stock-analysis-page__signal-pill">
                            <StockOutlined aria-hidden="true" /> 领涨 {themeLeaderPreviewItems.length}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {themeBreakoutCount > 0
                          ? `${themeLeaderPreviewItems.length} 只 · ${themeBreakoutCount} 题材`
                          : "题材雷达待补"}
                      </span>
                    </div>

                    {themeLeaderPreviewItems.length === 0 ? (
                      <CompactStatusTile
                        icon={<FireOutlined />}
                        label="题材"
                        value={themeBreakoutUnsupported ? "待补" : "0 领涨"}
                        detail={themeBreakoutBlockerLabel ?? undefined}
                        tone={themeBreakoutUnsupported ? "warning" : "neutral"}
                        testId="stock-analysis-theme-leader-empty"
                        title={themeBreakoutBlockerText ?? "当前无题材突破领涨股"}
                      />
                    ) : (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense stock-analysis-page__theme-leaders-table">
                          <thead>
                            <tr>
                              <th scope="col">题材</th>
                              <th scope="col">领涨股</th>
                              <th scope="col">涨跌</th>
                              <th scope="col">换手</th>
                              <th scope="col">收盘强度</th>
                              <th scope="col">标签</th>
                            </tr>
                          </thead>
                          <tbody>
                            {themeLeaderPreviewItems.map((row) => (
                              <tr
                                key={`${row.themeName}:${row.stockCode}`}
                                className="stock-analysis-page__row--clickable"
                                data-testid={`theme-leader-first-row-${row.stockCode}`}
                                onClick={() => {
                                  const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                                  setDetailSelection(
                                    buildRankContextDetailSelection({
                                      stockCode: row.stockCode,
                                      stockName: row.stockName,
                                      ranks,
                                    }),
                                  );
                                }}
                              >
                                <td>
                                  #{row.themeRank} {row.themeName}
                                </td>
                                <td>
                                  {row.stockName}
                                  <small className="stock-analysis-page__tabular"> {row.stockCode}</small>
                                </td>
                                <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                <td className="stock-analysis-page__table-number">{row.turn}</td>
                                <td className="stock-analysis-page__table-number">{row.closeStrength}</td>
                                <td>{row.tags.join(" / ") || "复核"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>

                  <section
                    ref={heavyweightSectionRef}
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-sector-heavyweights-first-screen"
                    data-testid="stock-analysis-sector-heavyweights-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="stock-analysis-page__min-w-0">
                        <p className={SA_SECTION_EYEBROW}>板块结构</p>
                        <h2 className={SA_CARD_TITLE}>权重股摘要</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="权重股样本状态">
                          <span className="stock-analysis-page__signal-pill">
                            <BarChartOutlined aria-hidden="true" /> 前 {sectorHeavyweightPreview?.sectorLimit ?? 0}
                          </span>
                          <span className="stock-analysis-page__signal-pill">
                            <StockOutlined aria-hidden="true" /> 样本{" "}
                            {sectorHeavyweightPreview?.totalSampleCount ?? 0}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {sectorHeavyweightPreview
                          ? sectorHeavyweightPreview.sectorsWithSamples > 0
                            ? `${sectorHeavyweightPreview.sectorsWithSamples}/${sectorHeavyweightPreview.sectorLimit} 板块 · ${sectorHeavyweightPreview.totalSampleCount} 只样本`
                            : `前 ${sectorHeavyweightPreview.sectorLimit} 板块 · 观察池未覆盖`
                          : "板块待补"}
                      </span>
                    </div>

                    {!sectorHeavyweightPreview || sectorHeavyweightPreview.rows.length === 0 ? (
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块强弱"
                        value="未就绪"
                        tone="warning"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : sectorHeavyweightRows.length === 0 ? (
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label={`前 ${sectorHeavyweightPreview.sectorLimit}`}
                        value="0 命中"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : (
                      <>
                        {sectorHeavyweightPreview.uncoveredSectorCount > 0 ? (
                          <div
                            className="stock-analysis-page__signal-pill stock-analysis-page__signal-pill--warn stock-analysis-page__sector-heavyweight-coverage"
                            data-testid="stock-analysis-sector-heavyweight-coverage"
                            role="status"
                            aria-label={`权重股样本缺口 ${sectorHeavyweightPreview.uncoveredSectorCount}`}
                          >
                            <StatusIcon tone="warning">
                              <DatabaseOutlined />
                            </StatusIcon>
                            缺口 {sectorHeavyweightPreview.uncoveredSectorCount}
                          </div>
                        ) : null}
                        <div className="stock-analysis-page__sector-heavyweight-grid">
                          {sectorHeavyweightRows.map((sector) => (
                            <article
                              key={sector.sectorCode}
                              className="stock-analysis-page__sector-heavyweight-card"
                              data-testid={`sector-heavyweight-card-${sector.sectorCode}`}
                            >
                              <header className="stock-analysis-page__sector-heavyweight-head">
                                <strong>
                                  #{sector.sectorRank} {sector.sectorName}
                                </strong>
                                <span>
                                  板块 {sector.sectorPctChange} / 得分 {sector.sectorScore} / 样本 {sector.stocks.length}
                                </span>
                              </header>
                              <ul className="stock-analysis-page__sector-heavyweight-list">
                                {sector.stocks.slice(0, HEAVYWEIGHT_STOCKS_PER_CARD).map((stock) => {
                                  const trend = heavyweightTrends?.byStockCode.get(stock.stockCode);
                                  return (
                                  <li
                                      key={stock.stockCode}
                                      className="stock-analysis-page__sector-heavyweight-row stock-analysis-page__row--clickable"
                                      data-testid={`sector-heavyweight-row-${sector.sectorCode}-${stock.stockCode}`}
                                      title={trend?.title}
                                      onClick={() => {
                                        const ranks = lookupStockStrategyRanks(
                                          strategyPayload ?? null,
                                          stock.stockCode,
                                        );
                                        setDetailSelection(
                                          buildRankContextDetailSelection({
                                            stockCode: stock.stockCode,
                                            stockName: stock.stockName,
                                            sectorCode: sector.sectorCode,
                                            sectorName: sector.sectorName,
                                            ranks,
                                          }),
                                        );
                                      }}
                                      role="button"
                                      tabIndex={0}
                                      onKeyDown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          const ranks = lookupStockStrategyRanks(
                                            strategyPayload ?? null,
                                            stock.stockCode,
                                          );
                                          setDetailSelection(
                                            buildRankContextDetailSelection({
                                              stockCode: stock.stockCode,
                                              stockName: stock.stockName,
                                              sectorCode: sector.sectorCode,
                                              sectorName: sector.sectorName,
                                              ranks,
                                            }),
                                          );
                                        }
                                      }}
                                    >
                                      <span className="stock-analysis-page__sector-heavyweight-main">
                                        <strong>{stock.stockName}</strong>
                                        <small className="stock-analysis-page__tabular">{stock.stockCode}</small>
                                        {trend?.plottable ? (
                                          <span
                                            className="stock-analysis-page__sector-heavyweight-trend"
                                            data-tone={trend.tone}
                                          >
                                            <StockAnalysisTrendSparkline
                                              values={trend.values}
                                              tone={trend.tone}
                                              title={trend.title}
                                            />
                                            <small className="stock-analysis-page__tabular">
                                              {trend.returnLabel}
                                            </small>
                                          </span>
                                        ) : null}
                                      </span>
                                      <span className="stock-analysis-page__sector-heavyweight-metrics">
                                        <span>{stock.pctChange}</span>
                                        <span>换手 {stock.turn}</span>
                                        {stock.auxiliaryLabel ? (
                                          <span>{stock.auxiliaryLabel}</span>
                                        ) : (
                                          <span>收盘强度 {stock.closeStrength}</span>
                                        )}
                                        {stock.detailLabel ? <span>{stock.detailLabel}</span> : null}
                                      </span>
                                      <em>{stock.sourceLabel}</em>
                                    </li>
                                  );
                                })}
                              </ul>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                  </section>
    </>
  );
}
