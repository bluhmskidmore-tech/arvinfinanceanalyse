import type { StockThemeBreakoutCard } from "./stockAnalysisPageModel";

/**
 * 7 题材目录，镜像后端 strategy_policy.POLICY.theme_proxies 的声明序
 * （FORMULA_VERSION=rv_livermore_theme_breakout_multi_proxy_v6）。
 * 仅用于：无信号题材的兜底名称/代理代码展示 + 无信号排序。
 * 后端题材池调整时需同步；后续建议改为由 payload 驱动。
 */
export const POLICY_THEME_ORDER: ReadonlyArray<{
  key: string;
  name: string;
  proxyCode: string;
}> = [
  { key: "semiconductor_proxy", name: "半导体", proxyCode: "S270000" },
  { key: "ai_computing_proxy", name: "算力AI", proxyCode: "S710000+S730000" },
  { key: "robotics_proxy", name: "机器人与智能装备", proxyCode: "S640000" },
  { key: "defense_proxy", name: "国防军工", proxyCode: "S650000" },
  { key: "new_energy_proxy", name: "新能源", proxyCode: "S630000" },
  { key: "pharma_proxy", name: "医药", proxyCode: "S370000" },
  { key: "broker_proxy", name: "券商", proxyCode: "S490000" },
];

const POLICY_INDEX = new Map(POLICY_THEME_ORDER.map((theme, index) => [theme.key, index]));
const POLICY_BY_KEY = new Map(POLICY_THEME_ORDER.map((theme) => [theme.key, theme]));

export type StockThemeGroup = {
  key: string;
  name: string;
  proxyCode: string | null;
  rows: StockThemeBreakoutCard[];
};

export type StockThemeIdleEntry = {
  key: string;
  name: string;
  proxyCode: string;
};

/**
 * 按 theme_key 分组并排序：有信号的组在前按行数降序（行数相同按 policy
 * 声明序，未知题材排在已知题材之后）；无信号题材按 policy 声明序返回。
 * 组内保持传入顺序（pageModel 已按 rank 排好）。
 */
export function buildStockThemeGroups(cards: StockThemeBreakoutCard[]): {
  active: StockThemeGroup[];
  idle: StockThemeIdleEntry[];
} {
  const byKey = new Map<string, StockThemeBreakoutCard[]>();
  for (const card of cards) {
    const rows = byKey.get(card.themeKey);
    if (rows) {
      rows.push(card);
    } else {
      byKey.set(card.themeKey, [card]);
    }
  }

  const active: StockThemeGroup[] = [...byKey.entries()].map(([key, rows]) => ({
    key,
    name: rows[0]?.themeName || POLICY_BY_KEY.get(key)?.name || key,
    proxyCode: POLICY_BY_KEY.get(key)?.proxyCode ?? null,
    rows,
  }));
  const policyRank = (key: string) => POLICY_INDEX.get(key) ?? POLICY_THEME_ORDER.length;
  active.sort(
    (left, right) =>
      right.rows.length - left.rows.length || policyRank(left.key) - policyRank(right.key),
  );

  const idle = POLICY_THEME_ORDER.filter((theme) => !byKey.has(theme.key));
  return { active, idle };
}
