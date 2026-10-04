/**
 * 持仓（positions）前后端契约防漂移测试（Wave3 F08，仅新增测试）。
 *
 * 机制沿用 `AgentContractSync.test.ts`（Wave1 F04）；解析辅助来自本任务新增的
 * `./contractSyncUtils`（`AgentContractSync.test.ts` 自身不做修改）。
 *
 * 后端 schema 定位：`frontend/src/api/contracts/positions.ts` 中的持仓/统计类型对应
 * `backend/app/schemas/positions.py`（文件头注释即写明 "aligned with frontend
 * contracts"）。该文件同时还放了一批 KPI 绩效考核类型（`Kpi*`），但那批类型属于
 * 另一个领域，其后端模型在 `backend/app/models/kpi.py`（ORM 层，非本任务 grep 到
 * 的 Pydantic 请求/响应 schema），与"portfolio/positions"契约无直接对应关系，
 * 不在本次任务范围内。
 *
 * 本轮解析未发现真实字段级契约漂移（字段名、可空性均一致）。
 */
import { describe, expect, it } from "vitest";

import type {
  BondPositionItem,
  CounterpartyStatItem,
  CounterpartyStatsResponse,
  CustomerBalanceTrendResponse,
  CustomerBondDetailItem,
  CustomerBondDetailsResponse,
  IndustryStatItem,
  IndustryStatsResponse,
  InterbankCounterpartySplitResponse,
  InterbankPositionItem,
  PositionBalanceTrendItem,
  RateCoverage,
  RatingStatItem,
  RatingStatsResponse,
} from "../api/contracts/positions";
import {
  expectFieldParity,
  expectNullableFieldParity,
  readBackendFile,
} from "./contractSyncUtils";

const BACKEND_POSITIONS_SCHEMA = readBackendFile("backend/app/schemas/positions.py");

// —— 编译期绑定：清单键必须与契约类型的 keyof 完全一致（多、少、拼错均无法通过 tsc）。 ——

const BOND_POSITION_ITEM_FIELDS = {
  bond_code: true,
  credit_name: true,
  sub_type: true,
  asset_class: true,
  market_value: true,
  face_value: true,
  valuation_net_price: true,
  yield_rate: true,
} as const satisfies Record<keyof BondPositionItem, true>;

const INTERBANK_POSITION_ITEM_FIELDS = {
  deal_id: true,
  counterparty: true,
  product_type: true,
  direction: true,
  amount: true,
  interest_rate: true,
  maturity_date: true,
} as const satisfies Record<keyof InterbankPositionItem, true>;

const COUNTERPARTY_STAT_ITEM_FIELDS = {
  customer_name: true,
  total_amount: true,
  avg_daily_balance: true,
  weighted_rate: true,
  weighted_coupon_rate: true,
  transaction_count: true,
} as const satisfies Record<keyof CounterpartyStatItem, true>;

const RATE_COVERAGE_FIELDS = {
  policy: true,
  covered_amount: true,
  missing_amount: true,
  missing_count: true,
  coverage_ratio: true,
} as const satisfies Record<keyof RateCoverage, true>;

const COUNTERPARTY_STATS_RESPONSE_FIELDS = {
  start_date: true,
  end_date: true,
  num_days: true,
  items: true,
  total_amount: true,
  total_avg_daily: true,
  total_weighted_rate: true,
  total_weighted_coupon_rate: true,
  total_customers: true,
  ytm_rate_coverage: true,
  coupon_rate_coverage: true,
  cr10_ratio: true,
} as const satisfies Record<keyof CounterpartyStatsResponse, true>;

const RATING_STAT_ITEM_FIELDS = {
  rating: true,
  total_amount: true,
  avg_daily_balance: true,
  weighted_rate: true,
  bond_count: true,
  percentage: true,
} as const satisfies Record<keyof RatingStatItem, true>;

const RATING_STATS_RESPONSE_FIELDS = {
  start_date: true,
  end_date: true,
  num_days: true,
  items: true,
  total_amount: true,
  total_avg_daily: true,
  ytm_rate_coverage: true,
} as const satisfies Record<keyof RatingStatsResponse, true>;

const INDUSTRY_STAT_ITEM_FIELDS = {
  industry: true,
  total_amount: true,
  avg_daily_balance: true,
  weighted_rate: true,
  bond_count: true,
  percentage: true,
} as const satisfies Record<keyof IndustryStatItem, true>;

const INDUSTRY_STATS_RESPONSE_FIELDS = {
  start_date: true,
  end_date: true,
  num_days: true,
  items: true,
  total_amount: true,
  total_avg_daily: true,
  ytm_rate_coverage: true,
} as const satisfies Record<keyof IndustryStatsResponse, true>;

const CUSTOMER_BOND_DETAIL_ITEM_FIELDS = {
  bond_code: true,
  sub_type: true,
  asset_class: true,
  market_value: true,
  yield_rate: true,
  maturity_date: true,
  rating: true,
  industry: true,
} as const satisfies Record<keyof CustomerBondDetailItem, true>;

const CUSTOMER_BOND_DETAILS_RESPONSE_FIELDS = {
  customer_name: true,
  report_date: true,
  total_market_value: true,
  bond_count: true,
  items: true,
} as const satisfies Record<keyof CustomerBondDetailsResponse, true>;

const POSITION_BALANCE_TREND_ITEM_FIELDS = {
  date: true,
  balance: true,
} as const satisfies Record<keyof PositionBalanceTrendItem, true>;

const CUSTOMER_BALANCE_TREND_RESPONSE_FIELDS = {
  customer_name: true,
  start_date: true,
  end_date: true,
  days: true,
  items: true,
} as const satisfies Record<keyof CustomerBalanceTrendResponse, true>;

const INTERBANK_COUNTERPARTY_SPLIT_RESPONSE_FIELDS = {
  start_date: true,
  end_date: true,
  num_days: true,
  asset_total_amount: true,
  asset_total_avg_daily: true,
  asset_total_weighted_rate: true,
  asset_customer_count: true,
  liability_total_amount: true,
  liability_total_avg_daily: true,
  liability_total_weighted_rate: true,
  liability_customer_count: true,
  asset_items: true,
  liability_items: true,
} as const satisfies Record<keyof InterbankCounterpartySplitResponse, true>;

describe("positions.py ↔ contracts/positions.ts（债券/同业持仓明细）", () => {
  const source = BACKEND_POSITIONS_SCHEMA;

  it("BondPositionItem / InterbankPositionItem 字段与前端契约一致", () => {
    expectFieldParity(source, "BondPositionItem", BOND_POSITION_ITEM_FIELDS);
    expectFieldParity(source, "InterbankPositionItem", INTERBANK_POSITION_ITEM_FIELDS);
  });

  it("BondPositionItem 除 bond_code 外全部可空", () => {
    expectNullableFieldParity(source, "BondPositionItem", [
      "credit_name",
      "sub_type",
      "asset_class",
      "market_value",
      "face_value",
      "valuation_net_price",
      "yield_rate",
    ]);
  });

  it("InterbankPositionItem 除 deal_id/amount 外全部可空", () => {
    expectNullableFieldParity(source, "InterbankPositionItem", [
      "counterparty",
      "product_type",
      "direction",
      "interest_rate",
      "maturity_date",
    ]);
  });
});

describe("positions.py ↔ contracts/positions.ts（对手方/评级/行业统计）", () => {
  const source = BACKEND_POSITIONS_SCHEMA;

  it("CounterpartyStatItem / RateCoverage / CounterpartyStatsResponse 字段与前端契约一致", () => {
    expectFieldParity(source, "CounterpartyStatItem", COUNTERPARTY_STAT_ITEM_FIELDS);
    expectFieldParity(source, "RateCoverage", RATE_COVERAGE_FIELDS);
    expectFieldParity(source, "CounterpartyStatsResponse", COUNTERPARTY_STATS_RESPONSE_FIELDS);
  });

  it("RatingStatItem / RatingStatsResponse 字段与前端契约一致", () => {
    expectFieldParity(source, "RatingStatItem", RATING_STAT_ITEM_FIELDS);
    expectFieldParity(source, "RatingStatsResponse", RATING_STATS_RESPONSE_FIELDS);
  });

  it("IndustryStatItem / IndustryStatsResponse 字段与前端契约一致", () => {
    expectFieldParity(source, "IndustryStatItem", INDUSTRY_STAT_ITEM_FIELDS);
    expectFieldParity(source, "IndustryStatsResponse", INDUSTRY_STATS_RESPONSE_FIELDS);
  });

  it("RateCoverage 全部字段非空（覆盖率诊断恒有值）", () => {
    expectNullableFieldParity(source, "RateCoverage", []);
  });

  it("CounterpartyStatsResponse 可空字段（weighted 系列/覆盖率诊断/CR10）与前端一致", () => {
    expectNullableFieldParity(source, "CounterpartyStatsResponse", [
      "total_weighted_rate",
      "total_weighted_coupon_rate",
      "ytm_rate_coverage",
      "coupon_rate_coverage",
      "cr10_ratio",
    ]);
  });
});

describe("positions.py ↔ contracts/positions.ts（客户明细/余额趋势/同业资产负债拆分）", () => {
  const source = BACKEND_POSITIONS_SCHEMA;

  it("CustomerBondDetailItem / CustomerBondDetailsResponse 字段与前端契约一致", () => {
    expectFieldParity(source, "CustomerBondDetailItem", CUSTOMER_BOND_DETAIL_ITEM_FIELDS);
    expectFieldParity(source, "CustomerBondDetailsResponse", CUSTOMER_BOND_DETAILS_RESPONSE_FIELDS);
  });

  it("PositionBalanceTrendItem / CustomerBalanceTrendResponse 字段与前端契约一致", () => {
    expectFieldParity(source, "PositionBalanceTrendItem", POSITION_BALANCE_TREND_ITEM_FIELDS);
    expectFieldParity(
      source,
      "CustomerBalanceTrendResponse",
      CUSTOMER_BALANCE_TREND_RESPONSE_FIELDS,
    );
  });

  it("InterbankCounterpartySplitResponse 字段与前端契约一致", () => {
    expectFieldParity(
      source,
      "InterbankCounterpartySplitResponse",
      INTERBANK_COUNTERPARTY_SPLIT_RESPONSE_FIELDS,
    );
  });

  it("CustomerBondDetailItem 可空字段一致（rating/industry 后端有非空默认值，非可空）", () => {
    expectNullableFieldParity(source, "CustomerBondDetailItem", [
      "sub_type",
      "asset_class",
      "yield_rate",
      "maturity_date",
    ]);
  });

  it("InterbankCounterpartySplitResponse 可空字段（asset/liability weighted_rate）与前端一致", () => {
    expectNullableFieldParity(source, "InterbankCounterpartySplitResponse", [
      "asset_total_weighted_rate",
      "liability_total_weighted_rate",
    ]);
  });
});

describe("KPI 契约的领域边界说明", () => {
  it("KpiOwner/KpiMetric 等类型属于 KPI 绩效考核领域，其后端模型在 app/models/kpi.py（非本任务范围）", () => {
    // 本用例不断言字段 parity，只固定"边界认定"本身：若未来把 KPI 迁到独立
    // contracts 文件（如 contracts/kpi.ts），应同时新增对应的 KPI 契约同步测试，
    // 而不是混进 positions 契约同步测试里一起断言。
    expect(BACKEND_POSITIONS_SCHEMA).not.toContain("class KpiOwner(");
    expect(BACKEND_POSITIONS_SCHEMA).not.toContain("class KpiMetric(");
  });
});
