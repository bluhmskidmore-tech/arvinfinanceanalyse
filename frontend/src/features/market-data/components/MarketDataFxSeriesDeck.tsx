import type { FxAnalyticalGroup } from "../../../api/contracts";
import { MarketDataFxThemeCard } from "./MarketDataFxThemeCard";

type MarketDataFxSeriesDeckProps = {
  groups: readonly FxAnalyticalGroup[];
  groupTitle: (title: string) => string;
};

export function MarketDataFxSeriesDeck({ groups, groupTitle }: MarketDataFxSeriesDeckProps) {
  if (groups.length === 0) {
    return null;
  }
  const fxEventCalendarEvents =
    groups.find((group) => group.group_key === "fx_event_calendar")?.events ?? [];

  return (
    <div className="market-data-series-category-stack" data-testid="market-data-fx-series-deck">
      <div
        className="market-data-supplementary-theme-grid market-data-fx-theme-grid"
        data-testid="market-data-fx-theme-band"
      >
        {groups.map((group) => (
          <MarketDataFxThemeCard
            key={group.group_key}
            group={group}
            title={groupTitle(group.title)}
            contextEvents={group.group_key === "fx_index" ? fxEventCalendarEvents : undefined}
          />
        ))}
      </div>
    </div>
  );
}
