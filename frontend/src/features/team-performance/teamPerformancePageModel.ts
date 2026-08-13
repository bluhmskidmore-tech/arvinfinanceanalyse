import type {
  PnlByBusinessMonthlyPayload,
  PnlByBusinessYtdItem,
  ProductCategoryPnlRow,
  ResultMeta,
  TeamPerformanceAssessmentCenter,
  TeamPerformanceAssessmentIndicator,
  TeamPerformanceAssessmentWorkbookPayload,
  TeamPerformanceCenterPnlMapping,
} from "../../api/contracts";
import { EM_DASH } from "../../pageModel";

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
export type Q1CaliberSourceEndpoint = MappingEndpoint | "by-business-monthly";
export type MappingConfidence = "high" | "medium" | "linked";
export type ProductCategoryMetricField =
  | "business_net_income"
  | "cny_net"
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

export type Q1CaliberAmountField =
  | "total_pnl"
  | "ftp_net_pnl"
  | "business_net_income"
  | "cny_net"
  | "foreign_net";
export type Q1CaliberAllocation = "include" | "reference" | "subtract" | "pending";
export type Q1CaliberEvidenceStatus = "direct" | "aggregate" | "split-needed" | "excluded";

export type TeamPerformanceQ1CaliberRule = {
  centerId: string;
  centerName: string;
  businessLabel: string;
  sourceEndpoint?: Q1CaliberSourceEndpoint;
  rowId?: string;
  amountField?: Q1CaliberAmountField;
  allocation: Q1CaliberAllocation;
  evidenceStatus: Q1CaliberEvidenceStatus;
  note?: string;
};

export type TeamPerformanceQ1CaliberRuleResult = TeamPerformanceQ1CaliberRule & {
  rowName: string;
  amountYuan: number | null;
  contributionYuan: number | null;
  sourceLabel: string;
};

export type TeamPerformanceQ1CenterCaliber = {
  centerId: string;
  centerName: string;
  includedTotalYuan: number | null;
  includedRuleCount: number;
  pendingRuleCount: number;
  rules: TeamPerformanceQ1CaliberRuleResult[];
};

export type TeamPerformanceQ1CaliberModel = {
  periodLabel: string;
  sourceLabel: string;
  centers: TeamPerformanceQ1CenterCaliber[];
  warnings: string[];
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
  additive: boolean;
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
  /** 后端下发的 2025 考核底稿（含预汇总）；未加载时为 null，页面显示待加载态。 */
  workbook?: TeamPerformanceAssessmentWorkbookPayload | null;
  byBusinessItems?: PnlByBusinessYtdItem[];
  productCategoryRows?: ProductCategoryPnlRow[];
  byBusinessMeta?: ResultMeta | null;
  productCategoryMeta?: ResultMeta | null;
};

type BuildQ1CaliberModelArgs = {
  rules?: TeamPerformanceQ1CaliberRule[];
  byBusinessItems?: PnlByBusinessYtdItem[];
  byBusinessMonthly?: PnlByBusinessMonthlyPayload | null;
  productCategoryRows?: ProductCategoryPnlRow[];
};

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

// 本页金额/百分比展示为 zh-CN locale 语义（千分位分隔 + 去尾零，如 "12,345.68"、"60%"），
// 与 `src/pageModel` 的 `fixedOrDash`/`pctOrDash`（toFixed，恒定小数位）语义不同，
// 不能互换；缺失值语义（null → EM_DASH）由 teamPerformancePageModel.test.ts 锁定。
function formatNumber(value: number | null, maximumFractionDigits = 2): string {
  if (value === null) {
    return EM_DASH;
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits });
}

export function formatWanFromYuan(value: number | null): string {
  if (value === null) {
    return EM_DASH;
  }
  return `${formatNumber(value / YUAN_PER_WAN)} 万元`;
}

export function formatYiFromYuan(value: number | null): string {
  if (value === null) {
    return EM_DASH;
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
    return EM_DASH;
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

function isAdditiveMapping(mapping: CenterPnlMapping2025): boolean {
  return mapping.additive ?? mapping.confidence !== "linked";
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
          additive: isAdditiveMapping(mapping),
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
        additive: isAdditiveMapping(mapping),
        unitLabel: "损益按万元展示，规模按亿元展示",
        confidence: mapping.confidence,
        note: mapping.note,
        sourceLabel: "产品分类损益 YTD",
      } satisfies TeamPerformanceEvidenceRow;
    })
    .filter((item): item is TeamPerformanceEvidenceRow => item !== null);
}

function buildCenterSummary(
  center: TeamPerformanceAssessmentCenter,
  mappings: CenterPnlMapping2025[],
  byBusinessItems: PnlByBusinessYtdItem[],
  productCategoryRows: ProductCategoryPnlRow[],
): TeamPerformanceCenterSummary {
  const centerId = center.center_id;
  // 底稿指标与汇总分（weightTotal / workbookScore / scoreRate）都由后端算好下发，
  // 前端不再本地 reduce；本函数只负责映射证据的展示组装。
  const centerIndicators = center.indicators.map(adaptAssessmentIndicator);
  const centerMappings = mappings.filter((item) => item.centerId === centerId);
  const hasOnlyLinkedMappings =
    centerMappings.length > 0 && centerMappings.every((mapping) => !isAdditiveMapping(mapping));
  const evidenceRows = buildEvidenceRows(centerId, mappings, byBusinessItems, productCategoryRows);
  const additiveRows = evidenceRows.filter((row) => row.additive);
  const provisionalStatus: TeamPerformanceCenterSummary["mappingStatus"] =
    hasOnlyLinkedMappings || (evidenceRows.length > 0 && additiveRows.length === 0)
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
    centerName: center.center_name,
    weightTotal: center.weight_total,
    workbookScore: center.workbook_score,
    hasPendingScore: center.has_pending_score,
    scoreRate: center.score_rate,
    mappingStatus,
    mappedPnlTotalYuan,
    mappedScaleTotalYuan,
    coverageWarnings: buildCoverageWarnings(centerIndicators, evidenceRows, mappingStatus),
    indicators: centerIndicators,
    evidenceRows,
  };
}

export function adaptAssessmentIndicator(
  item: TeamPerformanceAssessmentIndicator,
): AssessmentIndicator2025 {
  return {
    centerId: item.center_id,
    centerName: item.center_name,
    indicatorCategory: item.indicator_category,
    metric: item.metric,
    target: item.target,
    weight: item.weight,
    scoringText: item.scoring_text,
    actual: item.actual,
    progress: item.progress,
    score: item.score,
    sourceRow: item.source_row,
    blockLabel: item.block_label ?? undefined,
  };
}

export function adaptCenterPnlMapping(
  item: TeamPerformanceCenterPnlMapping,
): CenterPnlMapping2025 {
  return {
    centerId: item.center_id,
    endpoint: item.endpoint,
    rowId: item.row_id,
    pnlField: item.pnl_field ?? undefined,
    scaleField: item.scale_field ?? undefined,
    confidence: item.confidence,
    note: item.note ?? undefined,
    additive: item.additive ?? undefined,
  };
}

export function buildTeamPerformanceViewModel({
  workbook = null,
  byBusinessItems = [],
  productCategoryRows = [],
  byBusinessMeta = null,
  productCategoryMeta = null,
}: BuildViewModelArgs = {}): TeamPerformanceViewModel {
  const mappings = (workbook?.mappings ?? []).map(adaptCenterPnlMapping);
  const centers = (workbook?.centers ?? []).map((center) =>
    buildCenterSummary(center, mappings, byBusinessItems, productCategoryRows),
  );
  const mappedCenterCount = centers.filter((item) =>
    item.mappingStatus === "已映射" || item.mappingStatus === "部分映射",
  ).length;

  const warnings = [
    "映射分析不代表正式中心归属。",
    ...(workbook ? [] : ["考核底稿尚未从后端加载，暂不显示部室矩阵。"]),
    ...buildEvidenceWarnings([
      { title: "业务种类损益 YTD", meta: byBusinessMeta, isMissing: !byBusinessMeta },
      { title: "产品分类损益 YTD", meta: productCategoryMeta, isMissing: !productCategoryMeta },
    ]),
    ...centers.flatMap((center) => center.coverageWarnings),
  ];

  return {
    centers,
    // 工作簿总分与部室数为后端预汇总字段，前端不再本地加总。
    totalWorkbookScore: workbook?.total_workbook_score ?? 0,
    totalCenterCount: workbook?.total_center_count ?? 0,
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

const Q1_PERIOD_LABEL = "2026 Q1（2026-01-01 至 2026-03-31）";
const Q1_SOURCE_LABEL = "Q1损益.xlsx 规则拆解 + 两条现有页面数据源";

export const Q1_CENTER_CALIBER_RULES: TeamPerformanceQ1CaliberRule[] = [
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "公募基金",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_public_fund",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "企业债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_nonfinancial_enterprise_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "企业债、中期票据、短期融资券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "中期票据",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_nonfinancial_enterprise_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "企业债、中期票据、短期融资券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "商业银行债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_commercial_financial_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "商业银行债、非银行金融债、次级债券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "资产支持证券",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_abs",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "人民币资管产品",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_detail_securities_asset_management_plan",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "先取证券业资管计划，再扣除已归产品与市场室的结构化融资。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "非银行金融债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_commercial_financial_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "商业银行债、非银行金融债、次级债券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "次级债券",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_commercial_financial_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "商业银行债、非银行金融债、次级债券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "债权投资",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_other_debt_financing",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "当前接口以其他债权融资类产品承接，保留聚合标识。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "短期融资券",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_nonfinancial_enterprise_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "企业债、中期票据、短期融资券在现有接口为同一聚合行，金额只计一次。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "产业基金（J4资产）扣除",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_detail_structured_finance_broker",
    amountField: "total_pnl",
    allocation: "subtract",
    evidenceStatus: "direct",
    note: "J4开头资产归产品与市场室，自营中心人民币资管产品中扣除，避免重复；来源页面仍使用现有行名。",
  },
  {
    centerId: "self-investment",
    centerName: "自营中心",
    businessLabel: "非底层投资资产父级",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_non_bottom_investment",
    amountField: "total_pnl",
    allocation: "reference",
    evidenceStatus: "excluded",
    note: "父级行与明细行重叠，不参与自营中心 Q1 实际汇总。",
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    businessLabel: "政策性金融债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_policy_financial_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    businessLabel: "同业存单",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_interbank_cd",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    businessLabel: "地方政府债券",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_local_government_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    businessLabel: "国债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_treasury_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "bond-trading",
    centerName: "债券交易室",
    businessLabel: "铁道债",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_railway_bond",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币拆放同业",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_lending_assets",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币同业存放",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_deposits",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币同业拆入",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_borrowings",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币卖出回购",
    sourceEndpoint: "product-category-ytd",
    rowId: "repo_liabilities",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币同业存单负债",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_cds",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "人民币信用联结票据",
    sourceEndpoint: "product-category-ytd",
    rowId: "credit_linked_notes",
    amountField: "cny_net",
    allocation: "include",
    evidenceStatus: "aggregate",
    note: "沿用现有产品分类负债证据，后续如有同业专属明细再细化。",
  },
  {
    centerId: "interbank-finance",
    centerName: "金融同业部",
    businessLabel: "中间业务净收入",
    sourceEndpoint: "product-category-ytd",
    rowId: "intermediate_business_income",
    amountField: "business_net_income",
    allocation: "pending",
    evidenceStatus: "split-needed",
    note: "现有页面只有总行级聚合行，不能强行分摊到金融同业部。",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币债券收入",
    sourceEndpoint: "product-category-ytd",
    rowId: "bond_investment",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币拆放同业",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_lending_assets",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币同业存放",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_deposits",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币同业拆入",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_borrowings",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币卖出回购",
    sourceEndpoint: "product-category-ytd",
    rowId: "repo_liabilities",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币同业存单负债",
    sourceEndpoint: "product-category-ytd",
    rowId: "interbank_cds",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "fx-derivatives",
    centerName: "外汇与衍生品室",
    businessLabel: "外币信用联结票据",
    sourceEndpoint: "product-category-ytd",
    rowId: "credit_linked_notes",
    amountField: "foreign_net",
    allocation: "include",
    evidenceStatus: "direct",
  },
  {
    centerId: "customer-business",
    centerName: "代客室 / 代客交易室",
    businessLabel: "外汇远期/掉期归代客交易",
    sourceEndpoint: "product-category-ytd",
    rowId: "derivatives",
    amountField: "business_net_income",
    allocation: "reference",
    evidenceStatus: "split-needed",
    note: "当前产品分类页只有汇兑损益及衍生聚合行，需要账户或产品明细拆出外汇远期、外汇掉期；不强行归属。",
  },
  {
    centerId: "product-market",
    centerName: "产品与市场室",
    businessLabel: "产业基金",
    sourceEndpoint: "by-business-ytd",
    rowId: "asset_zqtz_detail_structured_finance_broker",
    amountField: "total_pnl",
    allocation: "include",
    evidenceStatus: "direct",
    note: "映射规则：产业基金为J4开头资产；来源页面不改名，仍引用现有业务种类行。",
  },
];

export function formatQ1AllocationLabel(value: Q1CaliberAllocation): string {
  if (value === "include") {
    return "纳入";
  }
  if (value === "subtract") {
    return "扣除";
  }
  if (value === "pending") {
    return "待拆";
  }
  return "参考";
}

export function formatQ1EvidenceStatusLabel(value: Q1CaliberEvidenceStatus): string {
  if (value === "direct") {
    return "直接可取";
  }
  if (value === "aggregate") {
    return "聚合行参考";
  }
  if (value === "split-needed") {
    return "需拆分";
  }
  return "已排除";
}

function q1SourceLabel(endpoint: Q1CaliberSourceEndpoint | undefined): string {
  if (endpoint === "by-business-monthly") {
    return "/pnl-by-business（月度FTP后）";
  }
  if (endpoint === "by-business-ytd") {
    return "/pnl-by-business";
  }
  if (endpoint === "product-category-ytd") {
    return "/product-category-pnl";
  }
  return "现有数据源暂无独立行";
}

type Q1MonthlyFtpNetEvidence = {
  rowName: string;
  amountYuan: number | null;
};

function buildQ1MonthlyFtpNetEvidence(
  monthlyPayload: PnlByBusinessMonthlyPayload | null | undefined,
): Map<string, Q1MonthlyFtpNetEvidence> {
  const evidence = new Map<string, Q1MonthlyFtpNetEvidence>();
  for (const month of monthlyPayload?.months ?? []) {
    for (const item of month.items) {
      const current = evidence.get(item.row_key) ?? {
        rowName: item.business_type,
        amountYuan: null,
      };
      const ftpNetPnl = toNumber(item.ftp_net_pnl);
      evidence.set(item.row_key, {
        rowName: item.business_type,
        amountYuan:
          ftpNetPnl === null
            ? current.amountYuan
            : (current.amountYuan ?? 0) + ftpNetPnl,
      });
    }
  }
  return evidence;
}

function pickQ1Amount(
  rule: TeamPerformanceQ1CaliberRule,
  byBusinessItems: PnlByBusinessYtdItem[],
  byBusinessMonthlyFtpNet: Map<string, Q1MonthlyFtpNetEvidence>,
  productCategoryRows: ProductCategoryPnlRow[],
): {
  rowName: string;
  amountYuan: number | null;
  sourceEndpoint?: Q1CaliberSourceEndpoint;
  amountField?: Q1CaliberAmountField;
} {
  if (!rule.sourceEndpoint || !rule.rowId || !rule.amountField) {
    return { rowName: "待补充独立数据行", amountYuan: null };
  }

  if (rule.sourceEndpoint === "by-business-ytd" || rule.sourceEndpoint === "by-business-monthly") {
    const monthlyEvidence = byBusinessMonthlyFtpNet.get(rule.rowId);
    if (monthlyEvidence) {
      return {
        rowName: monthlyEvidence.rowName,
        amountYuan: monthlyEvidence.amountYuan,
        sourceEndpoint: "by-business-monthly",
        amountField: "ftp_net_pnl",
      };
    }
    const row = byBusinessItems.find((item) => item.row_key === rule.rowId);
    return {
      rowName: row?.business_type ?? "未命中业务种类月度FTP后行",
      amountYuan: null,
      sourceEndpoint: "by-business-monthly",
      amountField: "ftp_net_pnl",
    };
  }

  const row = productCategoryRows.find((item) => item.category_id === rule.rowId);
  if (!row) {
    return { rowName: "未命中产品分类行", amountYuan: null };
  }
  if (rule.amountField === "total_pnl" || rule.amountField === "ftp_net_pnl") {
    return { rowName: row.category_name, amountYuan: null };
  }
  const productAmountField = rule.amountField;
  return {
    rowName: row.category_name,
    amountYuan: toNumber(row[productAmountField]),
  };
}

function buildQ1RuleResult(
  rule: TeamPerformanceQ1CaliberRule,
  byBusinessItems: PnlByBusinessYtdItem[],
  byBusinessMonthlyFtpNet: Map<string, Q1MonthlyFtpNetEvidence>,
  productCategoryRows: ProductCategoryPnlRow[],
): TeamPerformanceQ1CaliberRuleResult {
  const amount = pickQ1Amount(rule, byBusinessItems, byBusinessMonthlyFtpNet, productCategoryRows);
  const amountYuan = amount.amountYuan;
  const canContribute =
    rule.evidenceStatus !== "excluded" &&
    (rule.allocation === "include" || rule.allocation === "subtract") &&
    amountYuan !== null;
  const sign = rule.allocation === "subtract" ? -1 : 1;

  return {
    ...rule,
    sourceEndpoint: amount.sourceEndpoint ?? rule.sourceEndpoint,
    amountField: amount.amountField ?? rule.amountField,
    rowName: amount.rowName,
    amountYuan,
    contributionYuan: canContribute ? amountYuan * sign : null,
    sourceLabel: q1SourceLabel(amount.sourceEndpoint ?? rule.sourceEndpoint),
  };
}

function contributionKey(rule: TeamPerformanceQ1CaliberRuleResult): string {
  return [
    rule.centerId,
    rule.sourceEndpoint ?? "none",
    rule.rowId ?? rule.businessLabel,
    rule.amountField ?? "none",
    rule.allocation,
  ].join(":");
}

function buildQ1CenterCaliber(
  centerId: string,
  rules: TeamPerformanceQ1CaliberRule[],
  byBusinessItems: PnlByBusinessYtdItem[],
  byBusinessMonthlyFtpNet: Map<string, Q1MonthlyFtpNetEvidence>,
  productCategoryRows: ProductCategoryPnlRow[],
): TeamPerformanceQ1CenterCaliber {
  const centerRules = rules.filter((rule) => rule.centerId === centerId);
  const seenContributionKeys = new Set<string>();
  const resolvedRules = centerRules.map((rule) => {
    const resolvedRule = buildQ1RuleResult(
      rule,
      byBusinessItems,
      byBusinessMonthlyFtpNet,
      productCategoryRows,
    );
    if (resolvedRule.contributionYuan === null) {
      return resolvedRule;
    }
    const key = contributionKey(resolvedRule);
    if (seenContributionKeys.has(key)) {
      return {
        ...resolvedRule,
        contributionYuan: null,
        note: resolvedRule.note
          ? `${resolvedRule.note} 同一聚合行已在本中心前序子项计入汇总。`
          : "同一聚合行已在本中心前序子项计入汇总。",
      };
    }
    seenContributionKeys.add(key);
    return resolvedRule;
  });
  const contributionRows = resolvedRules.filter((rule) => rule.contributionYuan !== null);
  const includedTotalYuan =
    contributionRows.length > 0
      ? contributionRows.reduce((sum, rule) => sum + (rule.contributionYuan ?? 0), 0)
      : null;

  return {
    centerId,
    centerName: centerRules[0]?.centerName ?? centerId,
    includedTotalYuan,
    includedRuleCount: centerRules.filter((rule) => rule.allocation === "include").length,
    pendingRuleCount: centerRules.filter((rule) => rule.evidenceStatus === "split-needed").length,
    rules: resolvedRules,
  };
}

export function buildTeamPerformanceQ1CaliberModel({
  rules = Q1_CENTER_CALIBER_RULES,
  byBusinessItems = [],
  byBusinessMonthly = null,
  productCategoryRows = [],
}: BuildQ1CaliberModelArgs = {}): TeamPerformanceQ1CaliberModel {
  const centerIds = uniqueBy(rules, (rule) => rule.centerId).map((rule) => rule.centerId);
  const byBusinessMonthlyFtpNet = buildQ1MonthlyFtpNetEvidence(byBusinessMonthly);

  return {
    periodLabel: Q1_PERIOD_LABEL,
    sourceLabel: Q1_SOURCE_LABEL,
    centers: centerIds.map((centerId) =>
      buildQ1CenterCaliber(
        centerId,
        rules,
        byBusinessItems,
        byBusinessMonthlyFtpNet,
        productCategoryRows,
      ),
    ),
    warnings: [
      "2026年计划尚未发布，本区只展示Q1实际证据和口径拆解。",
      "Excel中的外推值、全年预测和手工汇总不参与本区实际汇总。",
      "/pnl-by-business 的业务种类行采用月度 ftp_net_pnl 汇总；不再把未扣FTP的 total_pnl 直接归中心。",
      "接口粒度较粗的行只展示聚合证据，不强行分摊到子项。",
    ],
  };
}
