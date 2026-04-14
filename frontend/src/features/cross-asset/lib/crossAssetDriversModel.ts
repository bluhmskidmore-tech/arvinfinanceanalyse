import type { MacroBondLinkageEnvironmentScore } from "../../../api/contracts";

export type DriverTone = "bull" | "bear" | "neutral";

export type DriverColumn = {
  title: string;
  stance: string;
  tone: DriverTone;
  bullets: string[];
};

const STANCE: Record<DriverTone, { bg: string; color: string }> = {
  bull: { bg: "rgba(82, 196, 26, 0.12)", color: "#52c41a" },
  bear: { bg: "rgba(245, 34, 45, 0.1)", color: "#f5222d" },
  neutral: { bg: "rgba(250, 140, 22, 0.12)", color: "#fa8c16" },
};

export function driverStanceStyle(tone: DriverTone) {
  return STANCE[tone];
}

function toneFromScore(score: number): DriverTone {
  if (score > 0.12) {
    return "bull";
  }
  if (score < -0.12) {
    return "bear";
  }
  return "neutral";
}

export function buildDriverColumns(env: Partial<MacroBondLinkageEnvironmentScore>): DriverColumn[] {
  const liq = env.liquidity_score ?? 0;
  const rate = env.rate_direction_score ?? 0;
  const growth = env.growth_score ?? 0;
  const infl = env.inflation_score ?? 0;

  return [
    {
      title: "流动性",
      stance: liq > 0.12 ? "偏多" : liq < -0.12 ? "偏空" : "中性",
      tone: toneFromScore(liq),
      bullets: [
        liq > 0 ? "DR007 与资金利率偏松，利于短端。" : "资金利率偏紧，关注杠杆成本。",
        "NCD 与存单定价对信用利差有传导。",
      ],
    },
    {
      title: "海外约束",
      stance: rate > 0.12 ? "偏空" : rate < -0.12 ? "偏多" : "中性",
      tone: toneFromScore(-rate),
      bullets: [
        "美债与全球利率路径影响利差与风险偏好。",
        "美元与跨境流动性对长端有溢出。",
      ],
    },
    {
      title: "增长预期",
      stance: growth > 0.12 ? "偏多" : growth < -0.12 ? "偏空" : "中性偏交投",
      tone: growth > 0.12 ? "bull" : growth < -0.12 ? "bear" : "neutral",
      bullets: [
        "权益与商品隐含增长预期与长端利率博弈。",
        "关注高频数据与政策预期差。",
      ],
    },
    {
      title: "通胀扰动",
      stance: infl > 0.12 ? "偏空" : infl < -0.12 ? "偏多" : "中性",
      tone: infl > 0.12 ? "bear" : infl < -0.12 ? "bull" : "neutral",
      bullets: [
        "油价与输入性价格扰动影响曲线形态。",
        "预期差可能放大波动而非单边趋势。",
      ],
    },
  ];
}

export type EnvironmentTags = {
  primary: string;
  secondary: string;
  style: string;
};

export function buildEnvironmentTags(env: Partial<MacroBondLinkageEnvironmentScore>): EnvironmentTags {
  const liq = env.liquidity_score ?? 0;
  const rate = env.rate_direction_score ?? 0;
  const growth = env.growth_score ?? 0;

  let primary = "流动性";
  if (Math.abs(rate) >= Math.abs(liq) && Math.abs(rate) >= Math.abs(growth)) {
    primary = "海外利率";
  } else if (Math.abs(growth) >= Math.abs(liq)) {
    primary = "增长预期";
  }

  const secondary = rate > 0.1 ? "海外约束" : "政策预期";

  const style =
    growth < -0.05 && liq > 0
      ? "中段优于长端"
      : growth > 0.05
        ? "权益敏感"
        : "均衡";

  return { primary, secondary, style };
}
