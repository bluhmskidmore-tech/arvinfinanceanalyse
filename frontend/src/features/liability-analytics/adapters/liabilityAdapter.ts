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

export type LiabilitySyntheticSectionKind = "reserved" | "unavailable" | "pending-definition";

export type LiabilitySyntheticSectionState = {
  kind: LiabilitySyntheticSectionKind;
  title: string;
  detail: string;
};

export type LiabilitySyntheticSectionStates = {
  watchItems: LiabilitySyntheticSectionState;
  alertEvents: LiabilitySyntheticSectionState;
  contributionRows: LiabilitySyntheticSectionState;
  riskIndicators: LiabilitySyntheticSectionState;
  calendarItems: LiabilitySyntheticSectionState;
};

export function getLiabilitySyntheticSectionStates(): LiabilitySyntheticSectionStates {
  return {
    watchItems: {
      kind: "pending-definition",
      title: "待关注事项",
      detail: "待统一预警/限额接口与严重度映射，当前不展示示意告警。",
    },
    alertEvents: {
      kind: "reserved",
      title: "预警与事件",
      detail: "保留时间轴卡位；待事件/日历接口接入。",
    },
    contributionRows: {
      kind: "unavailable",
      title: "资产 / 负债 / 缺口贡献",
      detail: "缺少真实分项拆解接口，当前不展示示意分项贡献。",
    },
    riskIndicators: {
      kind: "pending-definition",
      title: "风险指标",
      detail: "指标字典与口径尚未冻结，当前不展示混合示意指标。",
    },
    calendarItems: {
      kind: "reserved",
      title: "关键日历（负债到期关注）",
      detail: "保留关键日历卡位；待现金流/合约到期接口接入。",
    },
  };
}

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
