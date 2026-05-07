import type {
  PnlByBusinessYtdItem,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../api/contracts";

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;

export type AssessmentIndicator2025 = {
  centerId: string;
  centerName: string;
  indicatorCategory: string;
  metric: string;
  target: string;
  weight: number;
  scoringText: string;
  actual: string;
  progress: string;
  score: number | null;
  sourceRow: number;
  blockLabel?: string;
};

export type MappingEndpoint = "by-business-ytd" | "product-category-ytd";
export type MappingConfidence = "high" | "medium" | "linked";
export type ProductCategoryMetricField =
  | "business_net_income"
  | "cny_scale"
  | "foreign_scale"
  | "foreign_net";

export type CenterPnlMapping2025 = {
  centerId: string;
  endpoint: MappingEndpoint;
  rowId: string;
  pnlField?: ProductCategoryMetricField;
  scaleField?: ProductCategoryMetricField;
  confidence: MappingConfidence;
  note?: string;
  additive?: boolean;
};

export type EvidenceWarningInput = {
  title: string;
  meta: ResultMeta | null | undefined;
  isMissing?: boolean;
};

export type TeamPerformanceEvidenceRow = {
  endpoint: MappingEndpoint;
  rowId: string;
  rowName: string;
  amountYuan: number | null;
  scaleYuan: number | null;
  unitLabel: string;
  confidence: MappingConfidence;
  note?: string;
  sourceLabel: string;
};

export type TeamPerformanceCenterSummary = {
  centerId: string;
  centerName: string;
  weightTotal: number;
  workbookScore: number;
  hasPendingScore: boolean;
  scoreRate: number | null;
  mappingStatus: "已映射" | "部分映射" | "仅表内" | "挂钩引用";
  mappedPnlTotalYuan: number | null;
  mappedScaleTotalYuan: number | null;
  coverageWarnings: string[];
  indicators: AssessmentIndicator2025[];
  evidenceRows: TeamPerformanceEvidenceRow[];
};

export type TeamPerformanceViewModel = {
  centers: TeamPerformanceCenterSummary[];
  totalWorkbookScore: number;
  totalCenterCount: number;
  mappedCenterCount: number;
  visibleEvidenceStatus: string;
  warnings: string[];
};

type BuildViewModelArgs = {
  indicators?: AssessmentIndicator2025[];
  mappings?: CenterPnlMapping2025[];
  byBusinessItems?: PnlByBusinessYtdItem[];
  productCategoryRows?: ProductCategoryPnlRow[];
  byBusinessMeta?: ResultMeta | null;
  productCategoryMeta?: ResultMeta | null;
};

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value: number | null, maximumFractionDigits = 2): string {
  if (value === null) {
    return "-";
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits });
}

export function formatWanFromYuan(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${formatNumber(value / YUAN_PER_WAN)} 万元`;
}

export function formatYiFromYuan(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${formatNumber(value / YUAN_PER_YI)} 亿元`;
}

export function formatScore(value: number | null): string {
  if (value === null) {
    return "待补分";
  }
  return `${formatNumber(value)} 分`;
}

export function formatRatePct(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${formatNumber(value * 100)}%`;
}

export function formatConfidenceLabel(value: MappingConfidence): string {
  if (value === "high") {
    return "高";
  }
  if (value === "medium") {
    return "中";
  }
  return "挂钩";
}

function uniqueBy<T>(items: T[], keyFn: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    const key = keyFn(item);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(item);
  }
  return result;
}

function pickProductValue(
  row: ProductCategoryPnlRow,
  field: ProductCategoryMetricField | undefined,
): number | null {
  if (!field) {
    return toNumber(row.business_net_income);
  }
  return toNumber(row[field]);
}

function buildEvidenceWarnings(inputs: EvidenceWarningInput[]): string[] {
  const warnings: string[] = [];

  for (const input of inputs) {
    if (input.isMissing) {
      warnings.push(`${input.title} 缺少正式结果。`);
      continue;
    }
    if (!input.meta) {
      continue;
    }
    if (input.meta.quality_flag !== "ok") {
      warnings.push(`${input.title} quality_flag=${input.meta.quality_flag}`);
    }
    if (input.meta.fallback_mode !== "none") {
      warnings.push(`${input.title} fallback_mode=${input.meta.fallback_mode}`);
    }
    if (input.meta.vendor_status !== "ok") {
      warnings.push(`${input.title} vendor_status=${input.meta.vendor_status}`);
    }
  }

  return warnings;
}

function buildCoverageWarnings(
  indicators: AssessmentIndicator2025[],
  evidenceRows: TeamPerformanceEvidenceRow[],
  mappingStatus: TeamPerformanceCenterSummary["mappingStatus"],
): string[] {
  const warnings: string[] = [];
  const coveredLabels = evidenceRows.map((row) => row.rowName).join(" ");

  for (const indicator of indicators) {
    const metric = indicator.metric.trim();
    const likelyMapped = coveredLabels.includes(metric);
    if (!likelyMapped) {
      warnings.push(`${metric} 暂未形成正式中心归因，仅展示表内或映射分析。`);
    }
  }

  if (mappingStatus === "部分映射") {
    warnings.push("当前中心仅完成部分映射，结论需结合左侧考核底稿。");
  }
  if (mappingStatus === "挂钩引用") {
    warnings.push("当前中心展示的是挂钩部门证据，不并入中心损益加总。");
  }

  return uniqueBy(warnings, (item) => item);
}

function buildEvidenceRows(
  centerId: string,
  mappings: CenterPnlMapping2025[],
  byBusinessItems: PnlByBusinessYtdItem[],
  productCategoryRows: ProductCategoryPnlRow[],
): TeamPerformanceEvidenceRow[] {
  const centerMappings = uniqueBy(
    mappings.filter((item) => item.centerId === centerId),
    (item) => `${item.centerId}:${item.endpoint}:${item.rowId}:${item.pnlField ?? "business_net_income"}`,
  );

  return centerMappings
    .map((mapping): TeamPerformanceEvidenceRow | null => {
      if (mapping.endpoint === "by-business-ytd") {
        const row = byBusinessItems.find((item) => item.row_key === mapping.rowId);
        if (!row) {
          return null;
        }
        return {
          endpoint: mapping.endpoint,
          rowId: mapping.rowId,
          rowName: row.business_type,
          amountYuan: toNumber(row.total_pnl),
          scaleYuan: toNumber(row.current_balance),
          unitLabel: "损益按万元展示，规模按亿元展示",
          confidence: mapping.confidence,
          note: mapping.note,
          sourceLabel: "业务种类损益 YTD",
        } satisfies TeamPerformanceEvidenceRow;
      }

      const row = productCategoryRows.find((item) => item.category_id === mapping.rowId);
      if (!row) {
        return null;
      }
      return {
        endpoint: mapping.endpoint,
        rowId: mapping.rowId,
        rowName: row.category_name,
        amountYuan: pickProductValue(row, mapping.pnlField),
        scaleYuan: mapping.scaleField ? pickProductValue(row, mapping.scaleField) : null,
        unitLabel: "损益按万元展示，规模按亿元展示",
        confidence: mapping.confidence,
        note: mapping.note,
        sourceLabel: "产品分类损益 YTD",
      } satisfies TeamPerformanceEvidenceRow;
    })
    .filter((item): item is TeamPerformanceEvidenceRow => item !== null);
}

function buildCenterSummary(
  centerId: string,
  indicators: AssessmentIndicator2025[],
  mappings: CenterPnlMapping2025[],
  byBusinessItems: PnlByBusinessYtdItem[],
  productCategoryRows: ProductCategoryPnlRow[],
): TeamPerformanceCenterSummary {
  const centerIndicators = indicators.filter((item) => item.centerId === centerId);
  const centerName = centerIndicators[0]?.centerName ?? centerId;
  const weightTotal = centerIndicators.reduce((sum, item) => sum + item.weight, 0);
  const workbookScore = centerIndicators.reduce((sum, item) => sum + (item.score ?? 0), 0);
  const hasPendingScore = centerIndicators.some((item) => item.score === null);
  const evidenceRows = buildEvidenceRows(centerId, mappings, byBusinessItems, productCategoryRows);
  const provisionalStatus: TeamPerformanceCenterSummary["mappingStatus"] =
    centerId === "jinan-branch"
      ? "挂钩引用"
      : evidenceRows.length === 0
        ? "仅表内"
        : "已映射";
  const provisionalWarnings = buildCoverageWarnings(
    centerIndicators,
    evidenceRows,
    provisionalStatus,
  );
  const mappingStatus: TeamPerformanceCenterSummary["mappingStatus"] =
    provisionalStatus === "已映射" && provisionalWarnings.length > 0
      ? "部分映射"
      : provisionalStatus;
  const additiveRows = centerId === "jinan-branch" ? [] : evidenceRows;
  const mappedPnlTotalYuan =
    additiveRows.length > 0
      ? additiveRows.reduce((sum, item) => sum + (item.amountYuan ?? 0), 0)
      : null;
  const mappedScaleTotalYuan =
    additiveRows.some((item) => item.scaleYuan !== null)
      ? additiveRows.reduce((sum, item) => sum + (item.scaleYuan ?? 0), 0)
      : null;

  return {
    centerId,
    centerName,
    weightTotal,
    workbookScore,
    hasPendingScore,
    scoreRate: weightTotal > 0 ? workbookScore / weightTotal : null,
    mappingStatus,
    mappedPnlTotalYuan,
    mappedScaleTotalYuan,
    coverageWarnings: buildCoverageWarnings(centerIndicators, evidenceRows, mappingStatus),
    indicators: centerIndicators,
    evidenceRows,
  };
}

export function buildTeamPerformanceViewModel({
  indicators = ASSESSMENT_CENTERS_2025,
  mappings = CENTER_PNL_MAPPINGS_2025,
  byBusinessItems = [],
  productCategoryRows = [],
  byBusinessMeta = null,
  productCategoryMeta = null,
}: BuildViewModelArgs = {}): TeamPerformanceViewModel {
  const centerIds = uniqueBy(indicators, (item) => item.centerId).map((item) => item.centerId);
  const centers = centerIds.map((centerId) =>
    buildCenterSummary(centerId, indicators, mappings, byBusinessItems, productCategoryRows),
  );
  const totalWorkbookScore = centers.reduce((sum, item) => sum + item.workbookScore, 0);
  const mappedCenterCount = centers.filter((item) =>
    item.mappingStatus === "已映射" || item.mappingStatus === "部分映射",
  ).length;

  const warnings = [
    "映射分析不代表正式中心归属。",
    ...buildEvidenceWarnings([
      { title: "业务种类损益 YTD", meta: byBusinessMeta, isMissing: !byBusinessMeta },
      { title: "产品分类损益 YTD", meta: productCategoryMeta, isMissing: !productCategoryMeta },
    ]),
    ...centers.flatMap((center) => center.coverageWarnings),
  ];

  return {
    centers,
    totalWorkbookScore,
    totalCenterCount: centers.length,
    mappedCenterCount,
    visibleEvidenceStatus:
      mappedCenterCount === 0
        ? "暂无正式映射证据"
        : mappedCenterCount === centers.length
          ? "映射证据已覆盖全部中心"
          : "映射证据部分覆盖",
    warnings: uniqueBy(warnings, (item) => item),
  };
}

export const ASSESSMENT_CENTERS_2025: AssessmentIndicator2025[] = [
  {
    centerId: "product-market",
    centerName: "产品与市场室",
    indicatorCategory: "效益类",
    metric: "金融投资营业收入",
    target: "2025年结构化融资实现收入3500万元（ftp价格按照1.75%）",
    weight: 10,
    scoringText: "按照完成额进行线性打分，完成额/3500*10分，上限为12分",
    actual: "3861",
    progress: "110.31%",
    score: 11.0314285714,
    sourceRow: 3,
  },
  {
    centerId: "product-market",
    centerName: "产品与市场室",
    indicatorCategory: "效益类",
    metric: "产业基金投资收益",
    target: "推动产业基金收益调整，全年实现估值损益变动4.3亿",
    weight: 10,
    scoringText: "根据产业基金收益情况线性打分",
    actual: "5.3亿",
    progress: "100%",
    score: 10,
    sourceRow: 4,
  },
  {
    centerId: "product-market",
    centerName: "产品与市场室",
    indicatorCategory: "规模类",
    metric: "金融债发行规模",
    target: "根据全行资产负债规划，完成全年永续债及金融债发行计划",
    weight: 15,
    scoringText: "根据发行计划完成情况进行打分",
    actual: "完成",
    progress: "100%",
    score: 15,
    sourceRow: 5,
  },
  {
    centerId: "self-investment",
    centerName: "自营投资室",
    indicatorCategory: "效益类",
    metric: "营业净收入",
    target: "2025年营业净收入16.8亿元",
    weight: 30,
    scoringText: "按照完成额进行线性（其中利息收入及非息收入统一核算）打分，完成额/15.45*30分，上限33分",
    actual: "14.77",
    progress: "95.60%",
    score: 28.6796116505,
    sourceRow: 10,
  },
  {
    centerId: "self-investment",
    centerName: "自营投资室",
    indicatorCategory: "效益类",
    metric: "中间业务收入",
    target: "2025年托管业务联动实现中间业务收入1500万元，2025年利率债承销量不低于80亿元",
    weight: 5,
    scoringText: "按照完成额进行线性打分，(托管中收/1500+利率债承销/80)/2*5分，上限5.5分",
    actual: "托管3810/1500，利率债承分销7858万元",
    progress: "完成",
    score: 5.5,
    sourceRow: 11,
  },
  {
    centerId: "self-investment",
    centerName: "自营投资室",
    indicatorCategory: "规模类",
    metric: "同业活期存款及托管业务规模",
    target: "低息同业活期日均新增60亿元，托管业务规模400亿元",
    weight: 5,
    scoringText: "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限5.5分",
    actual: "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
    progress: "低息同业活期：155.5%；托管规模：120.15%",
    score: 5,
    sourceRow: 12,
  },
  {
    centerId: "self-investment",
    centerName: "自营投资室",
    indicatorCategory: "客群类",
    metric: "投资业务客群",
    target: "投资业务客群较去年增长5%",
    weight: 5,
    scoringText: "根据投资的企业及同业客群增长情况线性打分，上限5分",
    actual: "2025年较2024年增加67家，增幅34.36%",
    progress: "完成",
    score: 5,
    sourceRow: 13,
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    indicatorCategory: "效益类",
    metric: "营业净收入",
    target: "全年实现拆放同业营业净收入1.05亿元（ftp价格按照1.75%）",
    weight: 15,
    scoringText: "按照完成额进行线性打分，完成额/1.05*15，上限17分",
    actual: "1.24",
    progress: "118.10%",
    score: 17,
    sourceRow: 18,
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    indicatorCategory: "效益类",
    metric: "同业负债成本压降",
    target: "人民币同业负债成本不超过1.83%",
    weight: 10,
    scoringText: "按照完成情况进行打分，每超1BP，扣1分，上限10分",
    actual: "1.74%",
    progress: "完成",
    score: 10,
    sourceRow: 19,
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    indicatorCategory: "效益类",
    metric: "同业银团贷款中间业务收入",
    target: "全年同业银团贷款中间业务收入1200万元",
    weight: 10,
    scoringText: "按照完成额进行线性打分，上限10分",
    actual: "1222.58",
    progress: "101.88%",
    score: 10,
    sourceRow: 20,
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    indicatorCategory: "规模类",
    metric: "同业活期存款及托管业务规模",
    target: "低息同业活期日均新增60亿元，托管业务规模400亿元",
    weight: 5,
    scoringText: "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限10分",
    actual: "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
    progress: "低息同业活期：155.5%；托管规模：120.15%",
    score: 6.89125,
    sourceRow: 21,
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    indicatorCategory: "客群类",
    metric: "同业往来业务客群",
    target: "同业往来客群较去年增长10户",
    weight: 5,
    scoringText: "根据同业客群数量增长情况线性打分，上限10分",
    actual: "2025年较2024年增加67家，增幅34.36%",
    progress: "完成",
    score: 10,
    sourceRow: 22,
  },
  {
    centerId: "money-trading",
    centerName: "货币交易室",
    indicatorCategory: "效益类",
    metric: "经营效益",
    target: "全年正逆回购价差不低于6BP",
    weight: 15,
    scoringText: "根据完成情况进行打分，每低于1BP扣1分",
    actual: "差额0.1BP",
    progress: "待核准",
    score: 9,
    sourceRow: 27,
  },
  {
    centerId: "money-trading",
    centerName: "货币交易室",
    indicatorCategory: "效益类",
    metric: "人民币同业负债成本",
    target: "人民币同业负债成本不超过1.83%",
    weight: 15,
    scoringText: "根据完成情况进行打分，每超1BP扣1分",
    actual: "1.74%",
    progress: "完成",
    score: 15,
    sourceRow: 28,
  },
  {
    centerId: "money-trading",
    centerName: "货币交易室",
    indicatorCategory: "规模类",
    metric: "人民币超额准备金年日均余额",
    target: "年日均不超过40亿元",
    weight: 10,
    scoringText: "超过1亿元扣1分，每低5亿元，加1分，上限12分",
    actual: "36.35",
    progress: "100%",
    score: 10,
    sourceRow: 29,
  },
  {
    centerId: "money-trading",
    centerName: "货币交易室",
    indicatorCategory: "客群类",
    metric: "货币交易客群",
    target: "货币对话交易客群数量较去年同期增长10%",
    weight: 5,
    scoringText: "根据货币对话交易客群增长情况线性打分",
    actual: "2025年较2024年增加46家，增幅50%",
    progress: "完成",
    score: 5,
    sourceRow: 30,
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    indicatorCategory: "效益及客群类",
    metric: "营业净收入",
    target: "2025年营业收入12.05亿元",
    weight: 35,
    scoringText: "按照完成额进行线性打分，完成额/12.05*35分，上限39分",
    actual: "16.89",
    progress: "140.17%",
    score: 39,
    sourceRow: 35,
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    indicatorCategory: "效益及客群类",
    metric: "中间业务收入",
    target: "债券借贷净收入850万元，利率债承销收入8424万元",
    weight: 5,
    scoringText: "根据中收情况线性打分（借贷净收入完成额/850*50%+承销收入/6740*50%）*5分",
    actual: "完成",
    progress: "100%",
    score: 5,
    sourceRow: 36,
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    indicatorCategory: "效益及客群类",
    metric: "交易客群",
    target: "债券借贷类低风险业务授信客群较去年同期增长5%",
    weight: 5,
    scoringText: "根据客群增长情况线性打分",
    actual: "2025年较2024年增加11家，增幅5.58%",
    progress: "完成",
    score: 5,
    sourceRow: 37,
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇及衍生品交易室",
    indicatorCategory: "效益及客群类",
    metric: "营业净收入",
    target: "美元资产负债营业净收入1.2亿元",
    weight: 30,
    scoringText: "按照完成额进行线性打分，完成额/1.2*30分，上限33分",
    actual: "1.69",
    progress: "140.83%",
    score: 33,
    sourceRow: 42,
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇及衍生品交易室",
    indicatorCategory: "效益及客群类",
    metric: "外汇交易客群",
    target: "外汇交易客群数量较去年增长10%",
    weight: 10,
    scoringText: "根据外汇交易客群增长情况线性打分",
    actual: "2025年较2024年增加8家，增幅21.06%",
    progress: "完成",
    score: 10,
    sourceRow: 43,
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇及衍生品交易室",
    indicatorCategory: "效益及客群类",
    metric: "外汇市场影响力",
    target: "交易中心银行间外汇市场100强",
    weight: 5,
    scoringText: "未达目标不得分",
    actual: "完成",
    progress: "完成",
    score: 5,
    sourceRow: 44,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "效益类",
    metric: "营业净收入",
    target: "全年实现远期结售汇及外汇买卖营收1000万元人民币",
    weight: 10,
    scoringText: "根据代客衍生业务收入情况线性打分，完成额/1000*10，上限10分",
    actual: "1201",
    progress: "120.1%",
    score: 10,
    sourceRow: 49,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "效益类",
    metric: "代客外汇业务量",
    target: "代客外汇买卖交易量较上一年度增长100%；代客外汇远期业务量较上一年度增长100%",
    weight: 20,
    scoringText: "根据代客外汇买卖业务量情况线性打分，每一项各占10分，每项上限11分",
    actual: "买卖2.43亿美元；远期2.49亿美元",
    progress: "完成",
    score: 22,
    sourceRow: 50,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "产品类",
    metric: "代客业务产品",
    target: "代客业务新增研发3个产品",
    weight: 10,
    scoringText: "根据产品开发情况打分，少开发一款产品扣2分。",
    actual: "新增研发4个产品",
    progress: "完成",
    score: 10,
    sourceRow: 51,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "客群类",
    metric: "代客业务客群规模",
    target: "即期结售汇业务业务量在5万美元以上的客户数量达到2500户，远期结售汇业务业务量在100万美元以上的新增客户50%",
    weight: 5,
    scoringText: "根据上述代客业务客群增长情况线性打分，上限7分",
    actual: "即期2700户；远期新增客户82%",
    progress: "108% / 164%",
    score: 6.52,
    sourceRow: 52,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "市场风险指标控制",
    metric: "结构性存款低收益触发占比",
    target: "结构性存款全年到期产品中，触发低收益的业务占比小于5%",
    weight: 5,
    scoringText: "根据触发低收益占比打分，每超1%扣1分",
    actual: "3.88%",
    progress: "完成",
    score: 5,
    sourceRow: 53,
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "效益类",
    metric: "利率债承销手续费收入",
    target: "全年实现增值税后收入8424万元",
    weight: 20,
    scoringText: "按照完成额进行线性打分，完成额/6740*20分，上限23分",
    actual: "7858",
    progress: "93.28%",
    score: 18.6562203229,
    sourceRow: 57,
    blockLabel: "利率债承分销室",
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "规模类",
    metric: "信用债交易流转",
    target: "全年实现省内信用债卖出交易量35亿元",
    weight: 10,
    scoringText: "按照完成额进行线性打分",
    actual: "实际卖出66.58亿",
    progress: "完成",
    score: 10,
    sourceRow: 58,
    blockLabel: "利率债承分销室",
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "规模类",
    metric: "同业活期存款及托管业务规模",
    target: "低息同业活期日均新增60亿元，托管业务规模400亿元",
    weight: 5,
    scoringText: "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限5分",
    actual: "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
    progress: "完成",
    score: 5,
    sourceRow: 59,
    blockLabel: "利率债承分销室",
  },
  {
    centerId: "customer-business",
    centerName: "代客业务室",
    indicatorCategory: "客群类",
    metric: "信用债交易客群",
    target: "信用债二级市场交易对手客群新增10%",
    weight: 10,
    scoringText: "根据信用债交易对手客群增长情况线性打分",
    actual: "2025年较2024年增加11家，增幅38%",
    progress: "完成",
    score: 10,
    sourceRow: 60,
    blockLabel: "利率债承分销室",
  },
  {
    centerId: "jinan-branch",
    centerName: "济南分部",
    indicatorCategory: "效益类",
    metric: "经营效益",
    target: "挂钩金融同业部营业净收入及中间业务收入指标",
    weight: 20,
    scoringText: "按照完成额进行线性打分（金融同业部营业净收入得分60%+金融同业部中间业务收入得分*40%）",
    actual: "20",
    progress: "挂钩引用",
    score: 20,
    sourceRow: 65,
  },
  {
    centerId: "jinan-branch",
    centerName: "济南分部",
    indicatorCategory: "规模类",
    metric: "同业活期",
    target: "全年同业活期存款日均新增60亿元",
    weight: 10,
    scoringText: "挂钩部门同业活期存款完成情况",
    actual: "10",
    progress: "低息同业活期日均新增93.3亿元",
    score: 10,
    sourceRow: 66,
  },
  {
    centerId: "jinan-branch",
    centerName: "济南分部",
    indicatorCategory: "客群类",
    metric: "同业授信客户数",
    target: "同业授信客户数较去年增长5户",
    weight: 10,
    scoringText: "根据同业授信客户数量增长情况线性打分，新增同业授信客户数/5*10，上限12分",
    actual: "12",
    progress: "截至2025年末同业授信客户数251户，较2024年末增加12户",
    score: 12,
    sourceRow: 67,
  },
];

export const CENTER_PNL_MAPPINGS_2025: CenterPnlMapping2025[] = [
  {
    centerId: "product-market",
    endpoint: "product-category-ytd",
    rowId: "intermediate_business_income",
    pnlField: "business_net_income",
    confidence: "medium",
    note: "中间业务收入与产品与市场室协同收益相关，仍需与金融债发行指标区分。",
  },
  {
    centerId: "product-market",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_detail_structured_finance_broker",
    confidence: "high",
    note: "结构化融资（券商）作为金融投资营业收入证据。",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_public_fund",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_local_government_bond",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_commercial_financial_bond",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_nonfinancial_enterprise_bond",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_abs",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_non_bottom_investment",
    confidence: "medium",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_railway_bond",
    confidence: "high",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_other_debt_financing",
    confidence: "medium",
  },
  {
    centerId: "self-investment",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_central_bank_bill",
    confidence: "medium",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "interbank_lending_assets",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "high",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "interbank_deposits",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "medium",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "interbank_borrowings",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "medium",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "repo_liabilities",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "medium",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "interbank_cds",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "medium",
  },
  {
    centerId: "interbank-finance",
    endpoint: "product-category-ytd",
    rowId: "credit_linked_notes",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "medium",
  },
  {
    centerId: "money-trading",
    endpoint: "product-category-ytd",
    rowId: "repo_assets",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "high",
  },
  {
    centerId: "money-trading",
    endpoint: "product-category-ytd",
    rowId: "repo_liabilities",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "high",
  },
  {
    centerId: "bond-trading",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_policy_financial_bond",
    confidence: "high",
  },
  {
    centerId: "bond-trading",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_local_government_bond",
    confidence: "high",
  },
  {
    centerId: "bond-trading",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_interbank_cd",
    confidence: "high",
  },
  {
    centerId: "bond-trading",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_treasury_bond",
    confidence: "high",
  },
  {
    centerId: "fx-derivatives",
    endpoint: "product-category-ytd",
    rowId: "interbank_lending_assets",
    pnlField: "foreign_net",
    scaleField: "foreign_scale",
    confidence: "medium",
  },
  {
    centerId: "fx-derivatives",
    endpoint: "product-category-ytd",
    rowId: "bond_investment",
    pnlField: "foreign_net",
    scaleField: "foreign_scale",
    confidence: "medium",
  },
  {
    centerId: "fx-derivatives",
    endpoint: "product-category-ytd",
    rowId: "repo_liabilities",
    pnlField: "foreign_net",
    scaleField: "foreign_scale",
    confidence: "medium",
  },
  {
    centerId: "fx-derivatives",
    endpoint: "product-category-ytd",
    rowId: "derivatives",
    pnlField: "business_net_income",
    confidence: "high",
    note: "衍生品条目按业务净收入展示。",
  },
  {
    centerId: "customer-business",
    endpoint: "product-category-ytd",
    rowId: "intermediate_business_income",
    pnlField: "business_net_income",
    confidence: "high",
  },
  {
    centerId: "customer-business",
    endpoint: "by-business-ytd",
    rowId: "asset_zqtz_nonfinancial_enterprise_bond",
    confidence: "medium",
    note: "信用债交易流转以非金融企业债券 YTD 损益作辅助证据。",
  },
  {
    centerId: "jinan-branch",
    endpoint: "product-category-ytd",
    rowId: "interbank_lending_assets",
    pnlField: "business_net_income",
    scaleField: "cny_scale",
    confidence: "linked",
    note: "济南分部挂钩金融同业部证据，仅作引用不并入加总。",
  },
  {
    centerId: "jinan-branch",
    endpoint: "product-category-ytd",
    rowId: "intermediate_business_income",
    pnlField: "business_net_income",
    confidence: "linked",
    note: "济南分部挂钩金融同业部中间业务收入证据，仅作引用。",
  },
];
