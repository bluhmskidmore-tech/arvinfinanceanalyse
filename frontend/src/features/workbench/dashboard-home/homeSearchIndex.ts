import { visibleWorkbenchNavigation } from "../../../mocks/navigation";
import type {
  HomeDecisionAction,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";

/**
 * 首页搜索索引构建模块。
 *
 * 搜索对象仅来自现有可信来源，不新增虚假页面或后端接口：
 * - 页面：`mocks/navigation.ts` 的 visibleWorkbenchNavigation（真实路由 + 标签 + 描述）
 * - 指标：当前首屏 terminalKpis（真实展示的 KPI）
 * - 动作：当前决策栏 actions（真实可执行动作，带 to 链接）
 *
 * 指标 → 目标页面的映射复用首页既有导航语义（HOME_COMMANDS / 决策动作路由），
 * 不引入新的业务跳转定义。
 */

export type HomeSearchEntryType = "page" | "metric" | "action";

export type HomeSearchEntry = {
  id: string;
  name: string;
  type: HomeSearchEntryType;
  typeLabel: string;
  description: string;
  /** 跳转目标；为空表示本页内聚焦，不离开首页。 */
  to: string | null;
};

export type HomeSearchIndexInput = {
  terminalKpis: readonly HomeTerminalKpi[];
  decisionActions: readonly HomeDecisionAction[];
};

const METRIC_PAGE_MAP: ReadonlyArray<{ matchers: readonly string[]; to: string; label: string }> = [
  { matchers: ["aum", "资产规模", "组合市值"], to: "/balance-analysis", label: "资产负债分析" },
  { matchers: ["duration", "久期"], to: "/risk-overview", label: "风险工作台" },
  { matchers: ["pnl", "损益", "收益", "盈亏"], to: "/pnl-attribution", label: "收益归因" },
  { matchers: ["ytm", "yield", "收益率", "到期"], to: "/bond-analysis", label: "债券分析" },
  { matchers: ["dv01", "敏感度"], to: "/risk-tensor", label: "风险张量" },
  { matchers: ["credit", "信用"], to: "/concentration-monitor", label: "集中度监控" },
];

function metricTarget(kpi: HomeTerminalKpi): { to: string | null; label: string } {
  const haystack = `${kpi.id} ${kpi.label}`.toLowerCase();
  for (const rule of METRIC_PAGE_MAP) {
    if (rule.matchers.some((m) => haystack.includes(m.toLowerCase()))) {
      return { to: rule.to, label: rule.label };
    }
  }
  return { to: null, label: "本页指标" };
}

function buildPageEntries(): HomeSearchEntry[] {
  return visibleWorkbenchNavigation
    .filter((section) => section.readiness === "live" && section.path !== "/")
    .map((section) => ({
      id: `page:${section.key}`,
      name: section.label,
      type: "page" as const,
      typeLabel: "页面",
      description: section.description,
      to: section.path,
    }));
}

function buildMetricEntries(kpis: readonly HomeTerminalKpi[]): HomeSearchEntry[] {
  return kpis
    .filter((kpi) => metricTarget(kpi).to !== null)
    .map((kpi) => {
      const target = metricTarget(kpi);
      return {
        id: `metric:${kpi.id}`,
        name: kpi.label,
        type: "metric" as const,
        typeLabel: "指标",
        description: target.to ? `查看「${target.label}」` : "聚焦首页该指标",
        to: target.to,
      };
    });
}

function buildActionEntries(actions: readonly HomeDecisionAction[]): HomeSearchEntry[] {
  return actions
    .filter((action) => action.to)
    .map((action) => ({
      id: `action:${action.id}`,
      name: action.title,
      type: "action" as const,
      typeLabel: "动作",
      description: action.reason,
      to: action.to ?? null,
    }));
}

export function buildHomeSearchIndex(input: HomeSearchIndexInput): HomeSearchEntry[] {
  return [
    ...buildPageEntries(),
    ...buildMetricEntries(input.terminalKpis),
    ...buildActionEntries(input.decisionActions),
  ];
}

function normalize(text: string): string {
  return text.trim().toLowerCase();
}

/**
 * 按查询过滤搜索索引。匹配名称、描述与类型标签，大小写不敏感。
 * 空查询返回空结果（由调用方决定是否展示全部）。
 */
export function filterHomeSearchIndex(
  entries: readonly HomeSearchEntry[],
  query: string,
): HomeSearchEntry[] {
  const q = normalize(query);
  if (!q) {
    return [];
  }
  return entries.filter((entry) => {
    const haystack = `${entry.name} ${entry.description} ${entry.typeLabel}`;
    return normalize(haystack).includes(q);
  });
}
