import { Collapse } from "antd";
import type { ReactElement } from "react";

import type { ChoiceMacroLatestPoint, MacroVendorSeries } from "../../../api/contracts";
import { canRenderMacroThemeChart, groupMacroSeriesByTheme } from "../lib/marketDataMacroThemeGroups";
import { MarketDataMacroThemeCard } from "./MarketDataMacroThemeCard";

type MarketDataMacroSeriesDeckProps = {
  stableSeries: readonly ChoiceMacroLatestPoint[];
  fallbackSeries: readonly ChoiceMacroLatestPoint[];
  catalog?: readonly MacroVendorSeries[];
};

const MACRO_THEME_GRID_MAX_COLUMNS = 3;
const MACRO_THEME_CARD_HEADER_WEIGHT = 2;
const MACRO_THEME_CARD_CHART_WEIGHT = 5;
const MACRO_THEME_CARD_ROW_WEIGHT = 1;
const MACRO_THEME_CARD_ROW_WEIGHT_CAP = 12;

type MacroThemeGroup = ReturnType<typeof groupMacroSeriesByTheme>[number];

type MacroThemeCardRenderItem = {
  key: string;
  node: ReactElement;
  weight: number;
};

function estimateThemeCardWeight(group: MacroThemeGroup, showThemeChart: boolean): number {
  return (
    MACRO_THEME_CARD_HEADER_WEIGHT +
    (showThemeChart ? MACRO_THEME_CARD_CHART_WEIGHT : 0) +
    Math.min(group.series.length, MACRO_THEME_CARD_ROW_WEIGHT_CAP) * MACRO_THEME_CARD_ROW_WEIGHT
  );
}

function renderThemeCards(
  series: readonly ChoiceMacroLatestPoint[],
  tier: "stable" | "fallback",
  catalog: readonly MacroVendorSeries[] | undefined,
) {
  const groups = groupMacroSeriesByTheme(series, catalog);
  return groups.map((group) => {
    const showThemeChart = canRenderMacroThemeChart(group.series);
    const key = `${tier}-${group.key}`;
    return {
      key,
      node: (
        <MarketDataMacroThemeCard
          key={key}
          group={group}
          tier={tier}
          showThemeChart={showThemeChart}
        />
      ),
      weight: estimateThemeCardWeight(group, showThemeChart),
    };
  });
}

function splitThemeCardsIntoColumns(cards: readonly MacroThemeCardRenderItem[]): MacroThemeCardRenderItem[][] {
  const columnCount = Math.min(MACRO_THEME_GRID_MAX_COLUMNS, Math.max(1, cards.length));
  const columns = Array.from({ length: columnCount }, () => ({
    cards: [] as MacroThemeCardRenderItem[],
    weight: 0,
  }));

  for (const card of cards) {
    let targetIndex = 0;
    for (let index = 1; index < columns.length; index += 1) {
      if (columns[index].weight < columns[targetIndex].weight) {
        targetIndex = index;
      }
    }
    columns[targetIndex].cards.push(card);
    columns[targetIndex].weight += card.weight;
  }

  return columns.map((column) => column.cards);
}

function renderThemeGrid(cards: readonly MacroThemeCardRenderItem[], tier: "stable" | "fallback") {
  const columns = splitThemeCardsIntoColumns(cards);
  return (
    <div
      className={
        `market-data-supplementary-theme-grid market-data-macro-theme-grid ` +
        `market-data-macro-theme-grid--columns-${columns.length}`
      }
      data-testid={`market-data-macro-${tier}-theme-band`}
    >
      {columns.map((column, index) => (
        <div
          className="market-data-macro-theme-grid__column"
          data-testid={`market-data-macro-${tier}-theme-column-${index + 1}`}
          key={`${tier}-column-${index + 1}`}
        >
          {column.map((card) => card.node)}
        </div>
      ))}
    </div>
  );
}

export function MarketDataMacroSeriesDeck({
  stableSeries,
  fallbackSeries,
  catalog,
}: MarketDataMacroSeriesDeckProps) {
  const stableCards = renderThemeCards(stableSeries, "stable", catalog);
  const fallbackCards = renderThemeCards(fallbackSeries, "fallback", catalog);

  return (
    <div className="market-data-series-category-stack" data-testid="market-data-macro-series-deck">
      {stableCards.length > 0 ? (
        <>
          <div className="market-data-supplementary-tier-rail" data-testid="market-data-macro-stable-tier-rail">
            稳定链路 · {stableSeries.length} 条 · {stableCards.length} 组
          </div>
          {renderThemeGrid(stableCards, "stable")}
        </>
      ) : (
        <div className="market-data-series-compact-empty" data-testid="market-data-macro-stable-theme-empty">
          当前无稳定链路宏观序列。
        </div>
      )}

      {fallbackCards.length > 0 ? (
        <Collapse
          bordered={false}
          defaultActiveKey={["fallback"]}
          className="market-data-supplementary-tier-collapse"
          data-testid="market-data-macro-fallback-tier-collapse"
          items={[
            {
              key: "fallback",
              label: `降级链路 · ${fallbackSeries.length} 条 · ${fallbackCards.length} 组`,
              children: renderThemeGrid(fallbackCards, "fallback"),
            },
          ]}
        />
      ) : null}
    </div>
  );
}
