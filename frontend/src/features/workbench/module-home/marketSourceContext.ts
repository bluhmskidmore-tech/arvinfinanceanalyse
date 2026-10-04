export type MarketReturnSection = "market" | "risk" | "macro" | "events" | "scenario";
const sectionAnchors: Record<MarketReturnSection, string> = {
  market: "market-overview-judgment", risk: "market-risk-observation",
  macro: "market-overview-evidence", events: "market-overview-evidence", scenario: "market-home-scenario",
};

/** Only source context goes into URLs; portfolio values never belong here. */
export function buildMarketSourceLink(
  path: "/macro-observation" | "/news-events",
  section: MarketReturnSection,
  params: Record<string, string | undefined> = {},
): string {
  const search = new URLSearchParams({ origin: "market-overview", return_section: section });
  for (const key of ["indicator_id", "indicator_period", "published_at", "market_observation_date", "topic_code", "received_from", "received_to"]) {
    if (params[key]) search.set(key, params[key]);
  }
  return `${path}?${search.toString()}`;
}

export function readMarketSourceContext(search: string) {
  const params = new URLSearchParams(search);
  if (params.get("origin") !== "market-overview") return null;
  const requested = params.get("return_section");
  const section = requested && Object.hasOwn(sectionAnchors, requested) ? requested as MarketReturnSection : "market";
  return { params, returnTo: `/market-overview#${sectionAnchors[section]}` };
}
