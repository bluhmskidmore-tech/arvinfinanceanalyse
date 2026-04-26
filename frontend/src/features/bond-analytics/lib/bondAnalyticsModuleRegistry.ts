export type BondAnalyticsModuleKey =
  | "return-decomposition"
  | "benchmark-excess"
  | "krd-curve-risk"
  | "credit-spread"
  | "portfolio-headlines"
  | "top-holdings"
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
    description: "查看票息、骑乘、利率和利差效应的拆解结果。",
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
    key: "portfolio-headlines",
    label: "组合头条指标",
    description: "规模、收益率、久期、DV01、信用占比与发行人集中度等首屏指标。",
    detailHint: "从明细区继续看资产类别风险分布表。",
  },
  {
    key: "top-holdings",
    label: "重点持仓",
    description: "按市值排序的重点持仓与权重。",
    detailHint: "从明细区继续看持仓明细与合计权重。",
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
    key: "structure-distribution",
    label: "结构分布图组",
    description: "资产结构、久期分布、信用等级和行业分布图。",
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
