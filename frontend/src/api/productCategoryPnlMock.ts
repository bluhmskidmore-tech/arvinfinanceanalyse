import type { ProductCategoryPnlRow } from "./contracts";

const YUAN_PER_YI = 100_000_000;

function toYuan(value: string | number): string | number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return String(parsed * YUAN_PER_YI);
}

function withYuanValues(row: ProductCategoryPnlRow): ProductCategoryPnlRow {
  return {
    ...row,
    cnx_scale: toYuan(row.cnx_scale),
    cny_scale: toYuan(row.cny_scale),
    foreign_scale: toYuan(row.foreign_scale),
    cnx_cash: toYuan(row.cnx_cash),
    cny_cash: toYuan(row.cny_cash),
    foreign_cash: toYuan(row.foreign_cash),
    cny_ftp: toYuan(row.cny_ftp),
    foreign_ftp: toYuan(row.foreign_ftp),
    cny_net: toYuan(row.cny_net),
    foreign_net: toYuan(row.foreign_net),
    business_net_income: toYuan(row.business_net_income),
  };
}

export function buildProductCategoryMockYuanPayload(input: {
  rows: ProductCategoryPnlRow[];
  assetTotal: ProductCategoryPnlRow;
  liabilityTotal: ProductCategoryPnlRow;
  grandTotal: ProductCategoryPnlRow;
}) {
  const rows = input.rows.map(withYuanValues);
  const assetTotal = withYuanValues(input.assetTotal);
  const liabilityTotal = withYuanValues(input.liabilityTotal);
  const grandTotal = withYuanValues(input.grandTotal);
  const assetRows = rows.filter((row) => row.side === "asset");
  const liabilityRows = rows.filter((row) => row.side === "liability");

  return {
    rows: [...assetRows, assetTotal, ...liabilityRows, liabilityTotal, grandTotal],
    assetTotal,
    liabilityTotal,
    grandTotal,
  };
}
