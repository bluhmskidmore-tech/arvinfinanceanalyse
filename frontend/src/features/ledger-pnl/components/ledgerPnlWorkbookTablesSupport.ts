import type {
  LedgerPnlWorkbookGroup,
  LedgerPnlWorkbookTableSpec,
} from "./LedgerPnlWorkbookTables";

export const LEDGER_PNL_WORKBOOK_GROUP_DEFS = [
  {
    id: "overview",
    label: "总览与预警",
    titles: ["财务指标落地状态", "3位科目总览", "11位偏离TOP", "异动预警"],
  },
  {
    id: "structure",
    label: "资产负债结构",
    titles: ["资产结构", "负债结构", "贷款行业", "存款行业_活期", "存款行业_定期", "行业存贷差"],
  },
  {
    id: "segment",
    label: "分部与条线规模",
    titles: [
      "分部基础规模",
      "分部规模同比环比",
      "公司规模",
      "公司规模同比环比",
      "零售规模",
      "零售规模同比环比",
      "金融市场规模",
      "金融市场规模同比环比",
    ],
  },
  {
    id: "income",
    label: "收益与利息",
    titles: ["收益率分析（总账可复算）", "收益量价归因（年累计同比）", "存款利息拆分", "母公司营收分项", "外币分析"],
  },
] as const;

export function buildLedgerPnlWorkbookGroups(
  specsByTitle: Record<string, LedgerPnlWorkbookTableSpec>,
): LedgerPnlWorkbookGroup[] {
  return LEDGER_PNL_WORKBOOK_GROUP_DEFS.map((definition) => ({
    id: definition.id,
    label: definition.label,
    tables: definition.titles.flatMap((title) => {
      const spec = specsByTitle[title];
      return spec ? [spec] : [];
    }),
  }));
}
