import type { LiabilityCounterpartyPayload, Numeric } from "../../../api/contracts";

import type { LiabilityCpRow, LiabilityTypeRow } from "../components/LiabilityCounterpartyBlock";
import { numericYuanRaw, shareOfTotalNumeric } from "../utils/money";

export type LiabilityCounterpartyState = { kind: "loading" } | { kind: "error" } | { kind: "empty" } | { kind: "ok" };

export type LiabilityCounterpartyVM = {
  totalValue: Numeric;
  rows: LiabilityCpRow[];
  byType: LiabilityTypeRow[];
};

export type AdaptLiabilityCounterpartyInput = {
  payload: LiabilityCounterpartyPayload | undefined;
  isLoading: boolean;
  isError: boolean;
};

export type AdaptLiabilityCounterpartyOutput = {
  vm: LiabilityCounterpartyVM | null;
  state: LiabilityCounterpartyState;
};

export function adaptLiabilityCounterparty(input: AdaptLiabilityCounterpartyInput): AdaptLiabilityCounterpartyOutput {
  if (input.isLoading) {
    return { vm: null, state: { kind: "loading" } };
  }
  if (input.isError) {
    return { vm: null, state: { kind: "error" } };
  }
  const p = input.payload;
  if (!p) {
    return { vm: null, state: { kind: "empty" } };
  }

  const rows: LiabilityCpRow[] = (p.top_10 ?? []).map((it) => ({
    name: it.name,
    value: it.value ?? null,
    share: shareOfTotalNumeric(it.value ?? null, p.total_value),
    type: it.type ?? "",
    weightedCost: it.weighted_cost ?? null,
  }));
  const byType: LiabilityTypeRow[] = (p.by_type ?? []).map((x) => ({
    name: x.name,
    value: x.value ?? null,
  }));
  const vm: LiabilityCounterpartyVM = { totalValue: p.total_value, rows, byType };
  const kind = numericYuanRaw(p.total_value) === 0 && rows.length === 0 ? "empty" : "ok";
  return { vm, state: { kind } };
}
