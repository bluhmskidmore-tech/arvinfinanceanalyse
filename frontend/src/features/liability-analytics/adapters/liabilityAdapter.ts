import type { LiabilityCounterpartyPayload, Numeric } from "../../../api/contracts";

import type { LiabilityCpRow } from "../components/LiabilityCounterpartyBlock";
import { numericPctRaw, numericYuanRaw } from "../utils/money";

export type LiabilityCounterpartyState = { kind: "loading" } | { kind: "error" } | { kind: "empty" } | { kind: "ok" };

export type LiabilityCounterpartyVM = {
  totalValueYuan: number;
  rows: LiabilityCpRow[];
  byType: { name: string; value: number }[];
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
  const total = numericYuanRaw(p.total_value);
  const rows: LiabilityCpRow[] = (p.top_10 ?? []).map((it) => {
    const valueYuan = numericYuanRaw(it.value ?? null);
    return {
      name: it.name,
      valueYuan,
      pct: total > 0 ? (valueYuan / total) * 100 : 0,
      type: it.type ?? "",
      weightedCost: numericPctRaw(it.weighted_cost ?? null),
    };
  });
  const byType = (p.by_type ?? []).map((x) => ({
    name: x.name,
    value: numericYuanRaw(x.value ?? null),
  }));
  const vm: LiabilityCounterpartyVM = { totalValueYuan: total, rows, byType };
  const kind = total === 0 && rows.length === 0 ? "empty" : "ok";
  return { vm, state: { kind } };
}
