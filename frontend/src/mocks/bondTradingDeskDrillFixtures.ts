import type { BondPositionItem, BondTopHoldingItem } from "../api/contracts";
import { formatRawAsNumeric } from "../utils/format";

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const years = (raw: number) => formatRawAsNumeric({ raw, unit: "years", sign_aware: false });

/** Stable code used by bond-trading-desk layout/drill Playwright specs. */
export const MOCK_BOND_TRADING_DESK_INSTRUMENT_CODE = "230210.IB";

export const MOCK_POSITIONS_BOND_TRADING_DESK_CODE = "149001.SZ";

export function buildMockBondTradingDeskTopHoldings(topN: number): BondTopHoldingItem[] {
  const items: BondTopHoldingItem[] = [
    {
      instrument_code: MOCK_BOND_TRADING_DESK_INSTRUMENT_CODE,
      instrument_name: "23国开10",
      issuer_name: "国家开发银行",
      rating: "AAA",
      asset_class: "rate",
      market_value: yuan(1_200_000_000),
      face_value: yuan(1_000_000_000),
      ytm: pct(2.45),
      modified_duration: years(4.2),
      weight: pct(3.5),
    },
  ];
  return items.slice(0, Math.max(0, topN));
}

export function buildMockBondTradingDeskPositionsBonds(): BondPositionItem[] {
  return [
    {
      bond_code: MOCK_POSITIONS_BOND_TRADING_DESK_CODE,
      credit_name: "示例信用债",
      sub_type: "公司债",
      asset_class: "credit",
      market_value: "120000000",
      face_value: "100000000",
      valuation_net_price: "102.30",
      // 小数口径（0.0310 → 3.10%），与真实契约 _fmt_rate 一致；演示数据自洽口径见 D 节审计。
      yield_rate: "0.0310",
    },
  ];
}

export function sumMockTopHoldingsMarketValue(items: BondTopHoldingItem[]) {
  const total = items.reduce((sum, item) => sum + (item.market_value.raw ?? 0), 0);
  return yuan(total);
}
