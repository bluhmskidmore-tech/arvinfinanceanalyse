import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PnlByBusinessYtdItem } from "../../api/contracts";
import {
  buildCapitalEfficiencyQuadrantModel,
  CapitalEfficiencyQuadrantPanel,
} from "./CapitalEfficiencyQuadrantPanel";

function buildItem(partial: Partial<PnlByBusinessYtdItem>): PnlByBusinessYtdItem {
  return {
    row_key: partial.row_key ?? "asset_zqtz_default",
    sort_order: partial.sort_order ?? 0,
    business_type: partial.business_type ?? "默认业务",
    interest_income: partial.interest_income ?? "0",
    fair_value_change: partial.fair_value_change ?? "0",
    capital_gain: partial.capital_gain ?? "0",
    manual_adjustment: partial.manual_adjustment ?? "0",
    total_pnl: partial.total_pnl ?? "0",
    avg_balance: partial.avg_balance ?? "0",
    current_balance: partial.current_balance ?? "0",
    balance_yield_pct: partial.balance_yield_pct ?? null,
    annualized_yield_pct: partial.annualized_yield_pct ?? null,
    ftp_rate_pct: partial.ftp_rate_pct ?? "1.60",
    ftp_cost: partial.ftp_cost ?? null,
    ftp_net_pnl: partial.ftp_net_pnl ?? null,
    ftp_net_annualized_yield_pct: partial.ftp_net_annualized_yield_pct ?? null,
    source_kind: partial.source_kind ?? "zqtz",
    source_note: partial.source_note ?? "父级",
    proportion: partial.proportion ?? null,
    assets_count: partial.assets_count ?? 1,
  };
}

describe("buildCapitalEfficiencyQuadrantModel", () => {
  it("splits parent rows into four quadrants using the median as the dividing line", () => {
    const items = [
      buildItem({ row_key: "a", business_type: "国债", proportion: "0.40", ftp_net_annualized_yield_pct: "5.00" }),
      buildItem({
        row_key: "b",
        business_type: "政策性金融债",
        proportion: "0.30",
        ftp_net_annualized_yield_pct: "1.00",
      }),
      buildItem({ row_key: "c", business_type: "同业存单", proportion: "0.20", ftp_net_annualized_yield_pct: "4.00" }),
      buildItem({ row_key: "d", business_type: "企业债", proportion: "0.10", ftp_net_annualized_yield_pct: "0.50" }),
    ];

    const model = buildCapitalEfficiencyQuadrantModel(items);

    expect(model.hasEnoughData).toBe(true);
    // proportion_pct values: 40, 30, 20, 10 -> median 25
    expect(model.proportionMedianPct).toBeCloseTo(25);
    // yield values: 5, 1, 4, 0.5 -> median 2.5
    expect(model.yieldMedianPct).toBeCloseTo(2.5);

    const byKey = new Map(model.buckets.map((bucket) => [bucket.key, bucket.rows.map((row) => row.row_key)]));
    expect(byKey.get("large_high")).toEqual(["a"]);
    expect(byKey.get("large_low")).toEqual(["b"]);
    expect(byKey.get("small_high")).toEqual(["c"]);
    expect(byKey.get("small_low")).toEqual(["d"]);
  });

  it("excludes rows with null proportion or null ftp_net_annualized_yield_pct from the median and classification", () => {
    const items = [
      buildItem({ row_key: "a", proportion: "0.50", ftp_net_annualized_yield_pct: "5.00" }),
      buildItem({ row_key: "b", proportion: null, ftp_net_annualized_yield_pct: "3.00" }),
      buildItem({ row_key: "c", proportion: "0.10", ftp_net_annualized_yield_pct: null }),
      buildItem({ row_key: "d", proportion: "0.20", ftp_net_annualized_yield_pct: "1.00" }),
    ];

    const model = buildCapitalEfficiencyQuadrantModel(items);

    const allRowKeys = model.buckets.flatMap((bucket) => bucket.rows.map((row) => row.row_key));
    expect(allRowKeys.sort()).toEqual(["a", "d"]);
    // only "a" (50) and "d" (20) contribute to proportion median -> 35
    expect(model.proportionMedianPct).toBeCloseTo(35);
    // only "a" (5) and "d" (1) contribute to yield median -> 3
    expect(model.yieldMedianPct).toBeCloseTo(3);
  });

  it("excludes non-parent (detail / 其中) rows from the median and classification", () => {
    const items = [
      buildItem({ row_key: "a", proportion: "0.50", ftp_net_annualized_yield_pct: "5.00", source_note: "父级" }),
      buildItem({
        row_key: "a_detail_1",
        proportion: "0.90",
        ftp_net_annualized_yield_pct: "9.00",
        source_note: "其中项",
        business_type: "其中：细分项",
      }),
    ];

    const model = buildCapitalEfficiencyQuadrantModel(items);
    const allRowKeys = model.buckets.flatMap((bucket) => bucket.rows.map((row) => row.row_key));
    expect(allRowKeys).toEqual(["a"]);
  });

  it("reports insufficient data when there are no parent rows or all eligible fields are null", () => {
    const emptyModel = buildCapitalEfficiencyQuadrantModel([]);
    expect(emptyModel.hasEnoughData).toBe(false);
    expect(emptyModel.proportionMedianPct).toBeNull();
    expect(emptyModel.yieldMedianPct).toBeNull();

    const allNullModel = buildCapitalEfficiencyQuadrantModel([
      buildItem({ row_key: "a", proportion: null, ftp_net_annualized_yield_pct: "5.00" }),
      buildItem({ row_key: "b", proportion: "0.50", ftp_net_annualized_yield_pct: null }),
    ]);
    expect(allNullModel.hasEnoughData).toBe(false);
  });

  it("marks a quadrant as empty when no rows fall into it", () => {
    // proportion median 50 / yield median 4.5: "a" lands in large_high, "b" lands in small_low,
    // leaving large_low and small_high empty.
    const items = [
      buildItem({ row_key: "a", proportion: "0.60", ftp_net_annualized_yield_pct: "5.00" }),
      buildItem({ row_key: "b", proportion: "0.40", ftp_net_annualized_yield_pct: "4.00" }),
    ];
    const model = buildCapitalEfficiencyQuadrantModel(items);
    const largeLow = model.buckets.find((bucket) => bucket.key === "large_low");
    const smallHigh = model.buckets.find((bucket) => bucket.key === "small_high");
    expect(largeLow?.rows).toEqual([]);
    expect(smallHigh?.rows).toEqual([]);
  });
});

describe("CapitalEfficiencyQuadrantPanel", () => {
  it("renders the explicit empty state when data is insufficient", () => {
    const { getByTestId, queryByTestId } = render(<CapitalEfficiencyQuadrantPanel items={[]} />);
    expect(getByTestId("capital-efficiency-quadrant-empty")).toHaveTextContent(
      "暂无足够的份额（proportion）与FTP后年化收益率（ftp_net_annualized_yield_pct）数据用于象限计算。",
    );
    expect(queryByTestId("capital-efficiency-quadrant-grid")).toBeNull();
  });

  it("renders four quadrant cards and the empty-quadrant message when a quadrant has no rows", () => {
    const items = [
      buildItem({ row_key: "a", business_type: "国债", proportion: "0.60", ftp_net_annualized_yield_pct: "5.00" }),
      buildItem({
        row_key: "b",
        business_type: "政策性金融债",
        proportion: "0.40",
        ftp_net_annualized_yield_pct: "4.00",
      }),
    ];
    const { getByTestId } = render(<CapitalEfficiencyQuadrantPanel items={items} />);

    expect(getByTestId("capital-efficiency-quadrant-grid")).not.toBeNull();
    expect(getByTestId("capital-efficiency-quadrant-large_high")).toHaveTextContent("国债");
    expect(getByTestId("capital-efficiency-quadrant-small_low")).toHaveTextContent("政策性金融债");
    expect(getByTestId("capital-efficiency-quadrant-large_low")).toHaveTextContent("暂无业务种类落入此象限");
    expect(getByTestId("capital-efficiency-quadrant-small_high")).toHaveTextContent("暂无业务种类落入此象限");

    expect(getByTestId("capital-efficiency-quadrant-note")).toHaveTextContent(
      "分割线为当期父级行的份额与FTP后年化收益率中位数，仅用于本页展示分类，不代表业务已确认的分类标准，不参与任何组合指标重算。",
    );
  });
});
