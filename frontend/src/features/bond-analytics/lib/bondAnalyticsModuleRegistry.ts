export type BondAnalyticsModuleKey =
  | "return-decomposition"
  | "benchmark-excess"
  | "krd-curve-risk"
  | "credit-spread"
  | "action-attribution"
  | "accounting-audit";

export interface BondAnalyticsModuleDefinition {
  key: BondAnalyticsModuleKey;
  label: string;
  description: string;
  detailHint: string;
}

export interface BondAnalyticsFutureModuleDefinition {
  key: string;
  label: string;
  description: string;
}

export const BOND_ANALYTICS_CURRENT_MODULES: BondAnalyticsModuleDefinition[] = [
  {
    key: "return-decomposition",
    label: "收益拆解",
    description: "查看 carry、roll-down、利率和利差效应的拆解结果。",
    detailHint: "从明细区继续看收益效应和损益对账。",
  },
  {
    key: "benchmark-excess",
    label: "基准超额",
    description: "对比组合与基准的超额收益来源与久期偏离。",
    detailHint: "从明细区继续看超额来源和久期对比。",
  },
  {
    key: "krd-curve-risk",
    label: "曲线风险",
    description: "查看久期、DV01、KRD 和情景冲击。",
    detailHint: "从明细区继续看 KRD 分布和曲线情景。",
  },
  {
    key: "credit-spread",
    label: "信用利差",
    description: "查看信用债利差敏感度、情景冲击和集中度。",
    detailHint: "从明细区继续看利差冲击和信用暴露。",
  },
  {
    key: "action-attribution",
    label: "动作归因",
    description: "查看交易动作对损益、久期和 DV01 的影响。",
    detailHint: "从明细区继续看动作类型汇总和动作明细。",
  },
  {
    key: "accounting-audit",
    label: "会计分类审计",
    description: "查看推断分类、映射分类与分歧暴露。",
    detailHint: "从明细区继续看分歧资产类别和审计明细。",
  },
];

export const BOND_ANALYTICS_FUTURE_MODULES: BondAnalyticsFutureModuleDefinition[] = [
  {
    key: "portfolio-headlines",
    label: "组合 headline KPI",
    description: "规模、收益率、票息、久期和关键暴露的首屏指标组。",
  },
  {
    key: "structure-distribution",
    label: "结构分布图组",
    description: "资产结构、久期分布、信用等级和行业分布图。",
  },
  {
    key: "top-holdings",
    label: "持仓 TopN",
    description: "首屏持仓明细与重点债券观察入口。",
  },
  {
    key: "alerts-and-events",
    label: "异常与事件日历",
    description: "风险提示、事件追踪和近期待关注事项。",
  },
];

export function getBondAnalyticsModuleDefinition(
  key: BondAnalyticsModuleKey,
): BondAnalyticsModuleDefinition {
  return (
    BOND_ANALYTICS_CURRENT_MODULES.find((module) => module.key === key) ??
    BOND_ANALYTICS_CURRENT_MODULES[0]
  );
}
