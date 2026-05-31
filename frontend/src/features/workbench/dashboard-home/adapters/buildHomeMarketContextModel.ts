import type {
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  CampisiFourEffectsPayload,
  CreditSpreadMigrationPayload,
  Numeric,
  ReturnDecompositionPayload,
  YieldCurveTermStructureCurvePayload,
  YieldCurveTermStructurePayload,
} from "../../../../api/contracts";
import type { HomeMarketTicker } from "../dashboardHomeMarket";

export type HomeMarketContextTone = "cool" | "neutral" | "hot";

export type HomeMarketContextBlock = {
  id: "pnl" | "curve" | "credit";
  label: string;
  title: string;
  detail: string;
  foot: string;
};

export type HomeMarketContextModel = {
  temperatureLabel: string;
  temperatureScore: number;
  temperatureTone: HomeMarketContextTone;
  drivers: readonly string[];
  contextBlocks: readonly HomeMarketContextBlock[];
  aiSummary: readonly string[];
  sourceLabel: string;
  asOfLabel: string;
  statusLabel: string;
  refreshLabel: string;
};

type AttributionHint = {
  maxDragLabel: string;
  maxContributionLabel: string;
};

type AttributionComponent = {
  label: string;
  value: Numeric | null | undefined;
};

type MoneyComponent = {
  label: string;
  raw: number;
};

const SOURCE_LABEL = "来源：收益归因 / yield_curve_term_structure / credit_spread_migration";
const REFRESH_LABEL = "刷新：随报告日查询自动更新";
const GAP = "—";
const KEY_TENORS = ["1Y", "3Y", "5Y", "10Y"] as const;

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function numericDisplay(value: Numeric | null | undefined): string {
  return value?.display?.trim() || GAP;
}

function numericRaw(value: Numeric | null | undefined): number | null {
  return typeof value?.raw === "number" && Number.isFinite(value.raw) ? value.raw : null;
}

function isDisplayableNumeric(value: Numeric | null | undefined): boolean {
  const display = value?.display?.trim();
  return numericRaw(value) !== null && Boolean(display) && display !== GAP && display !== "undefined";
}

function displayOrMissing(value: Numeric | null | undefined, missingLabel: string): string {
  return isDisplayableNumeric(value) ? numericDisplay(value) : missingLabel;
}

function ratioPercentOrMissing(value: Numeric | null | undefined, missingLabel: string): string {
  const raw = numericRaw(value);
  return raw === null ? missingLabel : `${(raw * 100).toFixed(2)}%`;
}

function formatYiSigned(rawYuan: number): string {
  const yi = rawYuan / 100_000_000;
  const formatted = yi.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${yi >= 0 ? "+" : ""}${formatted} 亿`;
}

function latestIsoDate(values: readonly (string | null | undefined)[]): string {
  return values
    .map((value) => value?.slice(0, 10) ?? "")
    .filter(Boolean)
    .sort((left, right) => right.localeCompare(left))[0] ?? "";
}

function buildTemperature(marketTape: readonly HomeMarketTicker[]): Pick<
  HomeMarketContextModel,
  "temperatureLabel" | "temperatureScore" | "temperatureTone" | "drivers"
> {
  let score = 50;
  const drivers: string[] = [];

  for (const item of marketTape) {
    const label = item.label;
    if (/美国.*10|US.*10|US_GOV_10Y/i.test(label)) {
      if (item.deltaTone === "up") {
        score += 16;
        drivers.push("美债收益率上行");
      } else if (item.deltaTone === "down") {
        score -= 10;
        drivers.push("美债收益率下行");
      }
    } else if (/10年国债|国债.*10|CN.*10/i.test(label)) {
      if (item.deltaTone === "up") {
        score += 12;
        drivers.push("国内长端利率上行");
      } else if (item.deltaTone === "down") {
        score -= 8;
        drivers.push("国内长端利率下行");
      }
    } else if (/DR007|R007|Shibor/i.test(label)) {
      if (item.deltaTone === "up") {
        score += 10;
        drivers.push("资金利率上行");
      } else if (item.deltaTone === "down") {
        score -= 6;
        drivers.push("资金利率下行");
      }
    } else if (/人民币|USDCNY|汇率/i.test(label)) {
      if (item.deltaTone === "up") {
        score += 8;
        drivers.push("人民币走弱");
      } else if (item.deltaTone === "down") {
        score -= 4;
        drivers.push("人民币走强");
      }
    } else if (/原油|Brent|WTI/i.test(label)) {
      if (item.deltaTone === "up") {
        score += 6;
        drivers.push("油价上行");
      } else if (item.deltaTone === "down") {
        score -= 3;
        drivers.push("油价回落");
      }
    }
  }

  const temperatureScore = clampScore(score);
  const temperatureTone: HomeMarketContextTone =
    temperatureScore >= 65 ? "hot" : temperatureScore <= 40 ? "cool" : "neutral";
  const label =
    temperatureTone === "hot" ? "偏热" : temperatureTone === "cool" ? "偏冷" : "中性";

  return {
    temperatureLabel: `市场温度：${label}`,
    temperatureScore,
    temperatureTone,
    drivers: drivers.length > 0 ? drivers.slice(0, 4) : ["外部市场暂无明显方向"],
  };
}

function strongestPositive(components: readonly AttributionComponent[]): AttributionComponent | null {
  return components.reduce<AttributionComponent | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw <= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw > bestRaw ? item : best;
  }, null);
}

function strongestNegative(components: readonly AttributionComponent[]): AttributionComponent | null {
  return components.reduce<AttributionComponent | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw >= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw < bestRaw ? item : best;
  }, null);
}

function strongestPositiveMoney(components: readonly MoneyComponent[]): MoneyComponent | null {
  return components.reduce<MoneyComponent | null>((best, item) => {
    if (!Number.isFinite(item.raw) || item.raw <= 0) {
      return best;
    }
    return best == null || item.raw > best.raw ? item : best;
  }, null);
}

function strongestNegativeMoney(components: readonly MoneyComponent[]): MoneyComponent | null {
  return components.reduce<MoneyComponent | null>((best, item) => {
    if (!Number.isFinite(item.raw) || item.raw >= 0) {
      return best;
    }
    return best == null || item.raw < best.raw ? item : best;
  }, null);
}

function buildPnlBlock(
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined,
  returnDecomposition: ReturnDecompositionPayload | null | undefined,
  attribution: AttributionHint,
): HomeMarketContextBlock {
  if (campisiFourEffects) {
    const totals = campisiFourEffects.totals;
    const components: MoneyComponent[] = [
      { label: "Carry/Income", raw: totals.income_return },
      { label: "利率曲线", raw: totals.treasury_effect },
      { label: "信用利差", raw: totals.spread_effect },
      { label: "个券选择/残差", raw: totals.selection_effect },
    ];
    const contribution = strongestPositiveMoney(components);
    const drag = strongestNegativeMoney(components);
    const closure = campisiFourEffects.formal_closure?.status
      ? ` / 闭环 ${campisiFourEffects.formal_closure.status}`
      : "";
    return {
      id: "pnl",
      label: "PnL归因",
      title: contribution
        ? `最大贡献 ${contribution.label} ${formatYiSigned(contribution.raw)}`
        : "暂无正贡献项",
      detail: drag
        ? `最大拖累 ${drag.label} ${formatYiSigned(drag.raw)}`
        : "暂无负贡献项",
      foot: `Campisi 总收益 ${formatYiSigned(totals.total_return)}${closure}`,
    };
  }

  if (!returnDecomposition) {
    const fallback = [attribution.maxDragLabel, attribution.maxContributionLabel]
      .filter((item) => item && item !== GAP)
      .join(" / ");
    return {
      id: "pnl",
      label: "PnL归因",
      title: "等待正式归因数据",
      detail: fallback ? `已有瀑布图线索：${fallback}` : "未收到 return-decomposition 正式 payload",
      foot: "不从总 PnL 反推归因",
    };
  }

  const components: AttributionComponent[] = [
    { label: "Carry/Income", value: returnDecomposition.carry },
    { label: "利率曲线", value: returnDecomposition.rate_effect },
    { label: "信用利差", value: returnDecomposition.spread_effect },
    { label: "个券选择/残差", value: returnDecomposition.trading },
  ];
  const contribution = strongestPositive(components);
  const drag = strongestNegative(components);
  return {
    id: "pnl",
    label: "PnL归因",
    title: contribution
      ? `最大贡献 ${contribution.label} ${numericDisplay(contribution.value)}`
      : "暂无正贡献项",
    detail: drag
      ? `最大拖累 ${drag.label} ${numericDisplay(drag.value)}`
      : "暂无负贡献项",
    foot: `解释PnL ${numericDisplay(returnDecomposition.explained_pnl)} / 实际 ${numericDisplay(returnDecomposition.actual_pnl)}`,
  };
}

function curveLabel(curveType: string): string {
  const normalized = curveType.trim().toLowerCase();
  if (normalized === "cdb") return "CDB";
  if (normalized === "treasury") return "Treasury";
  if (normalized === "aaa_credit") return "AAA信用";
  return curveType.trim() || "曲线";
}

function findCurve(
  payload: YieldCurveTermStructurePayload | null | undefined,
): YieldCurveTermStructureCurvePayload | null {
  const curves = payload?.curves ?? [];
  return (
    curves.find((curve) => curve.curve_type === "cdb") ??
    curves.find((curve) => curve.curve_type === "treasury") ??
    curves[0] ??
    null
  );
}

function pointForTenor(curve: YieldCurveTermStructureCurvePayload, tenor: string) {
  return curve.points.find((point) => point.tenor.toUpperCase() === tenor.toUpperCase()) ?? null;
}

function formatTenorPoint(curve: YieldCurveTermStructureCurvePayload, tenor: string): string {
  const point = pointForTenor(curve, tenor);
  if (!point?.yield_pct) {
    return `${tenor} ${GAP}`;
  }
  const delta = numericDisplay(point.delta_bp_prev);
  return delta === GAP ? `${tenor} ${numericDisplay(point.yield_pct)}` : `${tenor} ${numericDisplay(point.yield_pct)}(${delta})`;
}

function buildCurveBlock(payload: YieldCurveTermStructurePayload | null | undefined): HomeMarketContextBlock {
  const curve = findCurve(payload);
  if (!curve) {
    return {
      id: "curve",
      label: "曲线/利率",
      title: "等待曲线期限结构",
      detail: "未收到 yield_curve_term_structure 正式 payload",
      foot: "默认曲线 treasury,cdb,aaa_credit",
    };
  }

  const tenYear = pointForTenor(curve, "10Y");
  const curveName = curveLabel(curve.curve_type);
  const title = tenYear?.yield_pct
    ? `${curveName} 10Y ${numericDisplay(tenYear.yield_pct)}`
    : `${curveName} 关键期限`;
  const delta = tenYear?.delta_bp_prev ? `，日变化 ${numericDisplay(tenYear.delta_bp_prev)}` : "";
  const detail = KEY_TENORS.map((tenor) => formatTenorPoint(curve, tenor)).join(" · ");
  const availableCurves = payload?.curves.map((item) => curveLabel(item.curve_type)).join(" / ") || curveName;
  return {
    id: "curve",
    label: "曲线/利率",
    title: `${title}${delta}`,
    detail,
    foot: `曲线日期 ${curve.trade_date_resolved ?? curve.trade_date_requested} · ${availableCurves}`,
  };
}

function findSpreadScenario25(payload: CreditSpreadMigrationPayload): Numeric | null | undefined {
  const scenario = payload.spread_scenarios.find((item) => {
    const shock = numericRaw(item.spread_change_bp);
    return shock === 25 || (shock === null && item.scenario_name.includes("25") && !item.scenario_name.includes("收窄"));
  });
  return scenario?.pnl_impact;
}

function hasSpreadLevelGap(payload: CreditSpreadMigrationPayload): boolean {
  return payload.warnings.some((warning) =>
    /Spread level input unavailable|weighted_avg_spread remains 0/i.test(warning),
  );
}

function buildCreditBlock(payload: CreditSpreadMigrationPayload | null | undefined): HomeMarketContextBlock {
  if (!payload) {
    return {
      id: "credit",
      label: "信用利差",
      title: "等待信用利差上下文",
      detail: "未收到 credit_spread_migration 正式 payload",
      foot: "只作解释变量，不改变 PnL 计算",
    };
  }
  const scenario25 = findSpreadScenario25(payload);
  const weightedAvgSpread = hasSpreadLevelGap(payload)
    ? "缺加权利差"
    : displayOrMissing(payload.weighted_avg_spread, "缺加权利差");
  return {
    id: "credit",
    label: "信用利差",
    title: `加权平均利差 ${weightedAvgSpread}`,
    detail: `spread DV01 ${displayOrMissing(payload.spread_dv01, "缺spread_dv01")} · AA及以下 ${ratioPercentOrMissing(payload.rating_aa_and_below_weight, "缺评级分布")} · 25bp ${displayOrMissing(scenario25, "缺25bp情景")}`,
    foot: `信用债 ${payload.credit_bond_count.toLocaleString("en-US")} 只 / 占比 ${ratioPercentOrMissing(payload.credit_weight, "缺信用债占比")}`,
  };
}

function buildSummary(blocks: readonly HomeMarketContextBlock[]): string[] {
  return blocks.map((block) => `${block.label}：${block.title}；${block.detail}。`);
}

function buildStatusLabel(input: {
  returnDecomposition: ReturnDecompositionPayload | null | undefined;
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  yieldCurveTermStructure: YieldCurveTermStructurePayload | null | undefined;
  creditSpreadMigration: CreditSpreadMigrationPayload | null | undefined;
}): string {
  const missing = [
    input.campisiFourEffects || input.returnDecomposition ? "" : "收益归因",
    input.yieldCurveTermStructure ? "" : "曲线",
    input.creditSpreadMigration ? "" : "信用利差",
  ].filter(Boolean);
  if (missing.length === 3) {
    return "来源状态：等待正式数据";
  }
  const warningCount =
    (input.campisiFourEffects?.warnings?.length ?? 0) +
    (input.returnDecomposition?.warnings.length ?? 0) +
    (input.yieldCurveTermStructure?.warnings.length ?? 0) +
    (input.creditSpreadMigration?.warnings.length ?? 0);
  if (warningCount > 0) {
    return "来源状态：正式链路有提示";
  }
  return missing.length > 0 ? `来源状态：部分缺 ${missing.join("/")}` : "来源状态：正式链路";
}

export function buildHomeMarketContextModel(input: {
  marketTape: readonly HomeMarketTicker[];
  marketPoints: readonly ChoiceMacroLatestPoint[] | null | undefined;
  macroNewsEvents: readonly ChoiceNewsEvent[] | null | undefined;
  todayIsoDate: string;
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  returnDecomposition: ReturnDecompositionPayload | null | undefined;
  yieldCurveTermStructure: YieldCurveTermStructurePayload | null | undefined;
  creditSpreadMigration: CreditSpreadMigrationPayload | null | undefined;
  attribution: AttributionHint;
}): HomeMarketContextModel {
  void input.macroNewsEvents;
  void input.todayIsoDate;
  const temperature = buildTemperature(input.marketTape);
  const contextBlocks = [
    buildPnlBlock(input.campisiFourEffects, input.returnDecomposition, input.attribution),
    buildCurveBlock(input.yieldCurveTermStructure),
    buildCreditBlock(input.creditSpreadMigration),
  ];
  const asOfDate = latestIsoDate([
    input.returnDecomposition?.report_date,
    input.campisiFourEffects?.report_date,
    input.yieldCurveTermStructure?.report_date,
    input.creditSpreadMigration?.report_date,
  ]);

  return {
    ...temperature,
    contextBlocks,
    aiSummary: buildSummary(contextBlocks),
    sourceLabel: SOURCE_LABEL,
    asOfLabel: asOfDate ? `数据截至 ${asOfDate}` : "数据截至：暂无",
    statusLabel: buildStatusLabel(input),
    refreshLabel: REFRESH_LABEL,
  };
}
