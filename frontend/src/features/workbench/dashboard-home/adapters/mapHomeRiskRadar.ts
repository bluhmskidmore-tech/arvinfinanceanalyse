import type { BondPortfolioHeadlinesPayload } from "../../../../api/contracts";
import { buildRiskItems } from "../../dashboard/dashboardCockpitModel";
import { buildRiskRadarFromRiskItems } from "./riskRadarFromRiskItems";
import type { HomeRiskRadar } from "../dashboardHomeView";

/** Portfolio 衍生维度；缺失轴（如杠杆）不展示。口径待产品确认。 */
export function mapHomeRiskRadar(
  portfolio: BondPortfolioHeadlinesPayload | null | undefined,
  reportDate: string,
): HomeRiskRadar {
  const riskItems = buildRiskItems(portfolio, reportDate);
  const { radar } = buildRiskRadarFromRiskItems(riskItems, false);

  if (radar.pending || radar.dimensions.length === 0) {
    return { dimensions: [], values: [], placeholder: true };
  }

  return {
    dimensions: radar.dimensions,
    values: radar.values,
    placeholder: false,
  };
}
