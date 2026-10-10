import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { createApiClient } from "../../../api/client";
import { BalanceMovementBucketEvidence } from "./BalanceMovementBucketEvidence";

it.each(["CNX", "CNY", "unavailable"] as const)("discloses %s main-chain provenance separately from CNY detail provenance", async (sourceBasis) => {
  const { result } = await createApiClient({ mode: "mock" }).getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
  result.rows[0].position_source_basis = sourceBasis;
  result.rows[0].zqtz_amount = "0";
  result.zqtz_maturity_structure = { meta: { ...result.basis_movement_decomposition!.meta, zqtz_currency_basis: "CNY" }, buckets: [] };
  render(<BalanceMovementBucketEvidence result={result} bucket="AC" onReturn={vi.fn()} />);
  const panel = screen.getByTestId("balance-movement-bucket-evidence");
  expect(panel).toHaveTextContent(`独立头寸主链实际来源${sourceBasis}`);
  expect(panel).toHaveTextContent("明细头寸币种口径CNY");
  expect(panel).toHaveTextContent(sourceBasis === "unavailable" ? "独立头寸余额不适用" : "独立头寸余额0.00 亿");
});
