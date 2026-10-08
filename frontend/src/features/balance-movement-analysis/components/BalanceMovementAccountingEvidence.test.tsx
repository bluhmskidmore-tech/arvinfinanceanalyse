import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { createApiClient } from "../../../api/client";
import { LiveBasisDecompositionStage, StructureBridgeStage } from "./BalanceMovementAccountingEvidence";

it("discloses mechanical same-day closure separately from unexplained cross-period residual", async () => {
  const client = createApiClient({ mode: "mock" });
  const { result } = await client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
  const waterfall = { ...result.difference_attribution_waterfall!, closing_check: "0" };
  const decomposition = result.basis_movement_decomposition!;
  render(<><StructureBridgeStage analysis={null} waterfall={waterfall} closure={null} /><LiveBasisDecompositionStage decomposition={decomposition} hasCalibration={false} /></>);
  expect(screen.getByText(/同日报表桥的残差已计入分项，算术闭合不表示差异已被解释/)).toBeVisible();
  expect(screen.getByText(/跨期分类驱动的期末校验等于未解释残差/)).toBeVisible();
});
