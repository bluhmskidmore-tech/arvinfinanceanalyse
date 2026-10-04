import type {
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  CampisiFourEffectsPayload,
  CreditSpreadMigrationPayload,
  Numeric,
  ResultMeta,
  ReturnDecompositionPayload,
  YieldCurveTermStructureCurvePayload,
  YieldCurveTermStructurePayload,
} from "../../../../api/contracts";
import {
  formatYieldCurveDateSummary,
  summarizeYieldCurveDates,
  type YieldCurveDateSummary,
} from "../../../../lib/yieldCurveDateSummary";
import {
  mapMarketSeries,
  type HomeMarketTicker,
} from "../dashboardHomeMarket";
import {
  buildCampisiAvailabilityNotices,
  buildCampisiBridgeQualityNotice,
  buildCampisiResultQualityNotice,
  buildCampisiTreasuryCurveDateNotice,
} from "../../../pnl-attribution/components/campisiAttributionPanelSupport";
import { buildCurveAvailabilityNotices } from "../../../pnl/pnlBridgePageSupport";

import { EM_DASH, formatYi } from "../../../../utils/format";
export type HomeMarketContextTone = "cool" | "neutral" | "hot";

export type HomeMarketContextBlock = {
  id: "pnl" | "curve" | "credit";
  label: string;
  title: string;
  detail: string;
  foot: string;
};

export type HomeMarketCurveRow = {
  tenor: (typeof KEY_TENORS)[number];
  yieldLabel: string;
  deltaLabel: string;
  deltaTone: "up" | "down" | "flat" | "muted";
};

export type HomeMarketCurveTable = {
  title: string;
  asOfLabel: string;
  rows: readonly HomeMarketCurveRow[];
  emptyMessage: string | null;
};

export type HomeAttributionCoverage = {
  label: string;
  state: "idle" | "loading" | "error" | "unknown" | "date-mismatch" | "complete" | "partial" | "unavailable";
  periodLabel: string;
  basisLabel: string;
  summary: string;
  positionLabel: string | null;
  excludedValueLabel: string | null;
  effectNotices: readonly string[];
  detailPath: string | null;
};

export type HomeMarketContextModel = {
  temperatureLabel: string;
  temperatureScore: number;
  temperatureTone: HomeMarketContextTone;
  drivers: readonly string[];
  contextBlocks: readonly HomeMarketContextBlock[];
  curveTable: HomeMarketCurveTable;
  rateSeries: readonly HomeMarketTicker[];
  aiSummary: readonly string[];
  attributionCoverage: HomeAttributionCoverage;
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

const SOURCE_LABEL =
  "来源：收益归因 / yield_curve_term_structure / credit_spread_migration";
const REFRESH_LABEL = "刷新：随报告日查询自动更新";
const GAP = EM_DASH;
const KEY_TENORS = ["1Y", "3Y", "5Y", "10Y"] as const;

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function numericDisplay(value: Numeric | null | undefined): string {
  return value?.display?.trim() || GAP;
}

function numericRaw(value: Numeric | null | undefined): number | null {
  return typeof value?.raw === "number" && Number.isFinite(value.raw)
    ? value.raw
    : null;
}

function isDisplayableNumeric(value: Numeric | null | undefined): boolean {
  const display = value?.display?.trim();
  return (
    numericRaw(value) !== null &&
    Boolean(display) &&
    display !== GAP &&
    display !== "undefined"
  );
}

function displayOrMissing(
  value: Numeric | null | undefined,
  missingLabel: string,
): string {
  return isDisplayableNumeric(value) ? numericDisplay(value) : missingLabel;
}

function ratioPercentOrMissing(
  value: Numeric | null | undefined,
  missingLabel: string,
): string {
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
  return (
    values
      .map((value) => value?.slice(0, 10) ?? "")
      .filter(Boolean)
      .sort((left, right) => right.localeCompare(left))[0] ?? ""
  );
}

function buildTemperature(
  marketTape: readonly HomeMarketTicker[],
): Pick<
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
    temperatureScore >= 65
      ? "hot"
      : temperatureScore <= 40
        ? "cool"
        : "neutral";
  const label =
    temperatureTone === "hot"
      ? "偏热"
      : temperatureTone === "cool"
        ? "偏冷"
        : "中性";

  return {
    temperatureLabel: `市场温度：${label}`,
    temperatureScore,
    temperatureTone,
    drivers:
      drivers.length > 0 ? drivers.slice(0, 4) : ["外部市场暂无明显方向"],
  };
}

function strongestPositive(
  components: readonly AttributionComponent[],
): AttributionComponent | null {
  return components.reduce<AttributionComponent | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw <= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw > bestRaw ? item : best;
  }, null);
}

function strongestNegative(
  components: readonly AttributionComponent[],
): AttributionComponent | null {
  return components.reduce<AttributionComponent | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw >= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw < bestRaw ? item : best;
  }, null);
}

function strongestPositiveMoney(
  components: readonly MoneyComponent[],
): MoneyComponent | null {
  return components.reduce<MoneyComponent | null>((best, item) => {
    if (!Number.isFinite(item.raw) || item.raw <= 0) {
      return best;
    }
    return best == null || item.raw > best.raw ? item : best;
  }, null);
}

function strongestNegativeMoney(
  components: readonly MoneyComponent[],
): MoneyComponent | null {
  return components.reduce<MoneyComponent | null>((best, item) => {
    if (!Number.isFinite(item.raw) || item.raw >= 0) {
      return best;
    }
    return best == null || item.raw < best.raw ? item : best;
  }, null);
}

function moneyComponentBreakdown(
  components: readonly MoneyComponent[],
): string {
  const prefix = components.length === 4 ? "四因子" : "分量";
  return `${prefix} ${components.map((item) => `${item.label} ${formatYiSigned(item.raw)}`).join(" · ")}`;
}

function pushOptionalMoneyComponent(
  components: MoneyComponent[],
  label: string,
  raw: number | undefined,
): void {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    components.push({ label, raw });
  }
}

function buildPnlBlock(
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined,
  returnDecomposition: ReturnDecompositionPayload | null | undefined,
  attribution: AttributionHint,
): HomeMarketContextBlock {
  if (campisiFourEffects) {
    const positionChange = campisiFourEffects.basis === "formal_report_pnl_bridge"
      ? undefined
      : campisiFourEffects.effect_availability?.position_change;
    const coverage = campisiFourEffects.effect_availability;
    const coverageDetail = positionChange && coverage
      ? `排除 ${positionChange.unavailable_bonds}/${coverage.bonds} 项持仓` +
        (positionChange.covered_bonds == null
          ? ""
          : `，覆盖 ${positionChange.covered_bonds} 项持仓`) +
        `；排除期初市值 ${positionChange.unavailable_market_value_start} 元` +
        (positionChange.unavailable_market_value_end == null
          ? ""
          : `、期末市值 ${positionChange.unavailable_market_value_end} 元`)
      : "";
    if (positionChange?.status === "unavailable") {
      return {
        id: "pnl",
        label: "PnL归因",
        title: "持仓收益无法归因",
        detail: `${coverageDetail}；缺少本金变动现金流说明，全部持仓被排除。`,
        foot: "Campisi 收益及各效应暂无可归因数值",
      };
    }
    const totals = campisiFourEffects.totals;
    const components: MoneyComponent[] = [
      { label: "Carry/Income", raw: totals.income_return },
      { label: "利率曲线", raw: totals.treasury_effect },
      { label: "信用利差", raw: totals.spread_effect },
    ];
    pushOptionalMoneyComponent(components, "已实现交易", totals.realized_trading);
    pushOptionalMoneyComponent(components, "手工调整", totals.manual_adjustment);
    pushOptionalMoneyComponent(components, "汇兑", totals.fx_translation);
    components.push({ label: "个券选择/残差", raw: totals.selection_effect });
    const contribution = strongestPositiveMoney(components);
    const drag = strongestNegativeMoney(components);
    const closure = campisiFourEffects.formal_closure?.status
      ? ` / 闭环 ${campisiFourEffects.formal_closure.status}`
      : "";
    const partialCoverage = positionChange?.status === "partial";
    const detail = drag
      ? `最大拖累 ${drag.label} ${formatYiSigned(drag.raw)}；${moneyComponentBreakdown(components)}`
      : `无负贡献项；${moneyComponentBreakdown(components)}`;
    return {
      id: "pnl",
      label: "PnL归因",
      title: contribution
        ? `${partialCoverage ? "可归因持仓：" : ""}最大贡献 ${contribution.label} ${formatYiSigned(contribution.raw)}`
        : "无正贡献项",
      detail: `${detail}${partialCoverage ? `；${coverageDetail}，金额仅汇总可归因持仓，未外推全组合` : ""}`,
      foot: `Campisi ${partialCoverage ? "可归因持仓" : ""}总收益 ${formatYiSigned(totals.total_return)}${closure}`,
    };
  }

  if (!returnDecomposition) {
    const fallback = [
      attribution.maxDragLabel,
      attribution.maxContributionLabel,
    ]
      .filter((item) => item && item !== GAP)
      .join(" / ");
    return {
      id: "pnl",
      label: "PnL归因",
      title: "等待正式归因数据",
      detail: fallback
        ? `已有瀑布图线索：${fallback}`
        : "未收到 return-decomposition 正式 payload",
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
      : "无正贡献项",
    detail: drag
      ? `最大拖累 ${drag.label} ${numericDisplay(drag.value)}`
      : "无负贡献项",
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

/**
 * 面板标题只用业务名，vendor 源名（如 akshare）不进 h2（§7 语域），
 * 溯源信息由来源元数据行与治理台账承担；无曲线时与成功态保持同名，
 * 避免失败瞬间标题跳变。
 */
function curveTableTitle(
  curve: YieldCurveTermStructureCurvePayload | null,
): string {
  if (!curve) {
    return "国债收益率";
  }
  return curve.curve_type === "cdb"
    ? "国开债收益率"
    : curve.curve_type === "treasury"
      ? "国债收益率"
      : curve.curve_type === "aaa_credit"
        ? "AAA信用收益率"
        : `${curveLabel(curve.curve_type)}收益率`;
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

function findMarketTableCurve(
  payload: YieldCurveTermStructurePayload | null | undefined,
): YieldCurveTermStructureCurvePayload | null {
  const curves = payload?.curves ?? [];
  return (
    curves.find((curve) => curve.curve_type === "treasury") ??
    curves.find((curve) => curve.curve_type === "cdb") ??
    curves[0] ??
    null
  );
}

function pointForTenor(
  curve: YieldCurveTermStructureCurvePayload,
  tenor: string,
) {
  return (
    curve.points.find(
      (point) => point.tenor.toUpperCase() === tenor.toUpperCase(),
    ) ?? null
  );
}

function formatTenorPoint(
  curve: YieldCurveTermStructureCurvePayload,
  tenor: string,
): string {
  const point = pointForTenor(curve, tenor);
  if (!point?.yield_pct) {
    return `${tenor} ${GAP}`;
  }
  const delta = numericDisplay(point.delta_bp_prev);
  return delta === GAP
    ? `${tenor} ${numericDisplay(point.yield_pct)}`
    : `${tenor} ${numericDisplay(point.yield_pct)}(${delta})`;
}

function curveDeltaTone(
  value: Numeric | null | undefined,
): HomeMarketCurveRow["deltaTone"] {
  const raw = numericRaw(value);
  if (raw === null) return "muted";
  if (raw > 0) return "up";
  if (raw < 0) return "down";
  return "flat";
}

/** 收益率水平列是存量水平值而非变动，剥离后端 display 的「+」符号（变动列保留符号）。 */
function stripLevelPlusSign(label: string): string {
  return label.replace(/^\+\s*/, "");
}

function buildCurveTable(
  payload: YieldCurveTermStructurePayload | null | undefined,
): HomeMarketCurveTable {
  const curve = findMarketTableCurve(payload);
  const rows = KEY_TENORS.map((tenor): HomeMarketCurveRow => {
    const point = curve ? pointForTenor(curve, tenor) : null;
    return {
      tenor,
      yieldLabel: stripLevelPlusSign(displayOrMissing(point?.yield_pct, GAP)),
      deltaLabel: displayOrMissing(point?.delta_bp_prev, GAP),
      deltaTone: isDisplayableNumeric(point?.delta_bp_prev)
        ? curveDeltaTone(point?.delta_bp_prev)
        : "muted",
    };
  });
  const hasAnyValue = rows.some(
    (row) => row.yieldLabel !== GAP || row.deltaLabel !== GAP,
  );
  return {
    title: curveTableTitle(curve),
    asOfLabel: curve?.trade_date_resolved?.slice(0, 10) ?? "",
    rows,
    emptyMessage: hasAnyValue ? null : "关键期限数据暂不可用",
  };
}

function buildCurveBlock(
  payload: YieldCurveTermStructurePayload | null | undefined,
  dateSummary: YieldCurveDateSummary,
): HomeMarketContextBlock {
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
  const delta = tenYear?.delta_bp_prev
    ? `，日变化 ${numericDisplay(tenYear.delta_bp_prev)}`
    : "";
  const detail = KEY_TENORS.map((tenor) => formatTenorPoint(curve, tenor)).join(
    " · ",
  );
  const availableCurves =
    payload?.curves.map((item) => curveLabel(item.curve_type)).join(" / ") ||
    curveName;
  return {
    id: "curve",
    label: "曲线/利率",
    title: `${title}${delta}`,
    detail,
    foot: `${formatYieldCurveDateSummary(dateSummary)} · ${availableCurves}`,
  };
}

function findSpreadScenario25(
  payload: CreditSpreadMigrationPayload,
): Numeric | null | undefined {
  const scenario = payload.spread_scenarios.find((item) => {
    const shock = numericRaw(item.spread_change_bp);
    return (
      shock === 25 ||
      (shock === null &&
        item.scenario_name.includes("25") &&
        !item.scenario_name.includes("收窄"))
    );
  });
  return scenario?.pnl_impact;
}

function hasSpreadLevelGap(payload: CreditSpreadMigrationPayload): boolean {
  return payload.warnings.some((warning) =>
    /Spread level input unavailable|weighted_avg_spread remains 0/i.test(
      warning,
    ),
  );
}

function buildCreditBlock(
  payload: CreditSpreadMigrationPayload | null | undefined,
): HomeMarketContextBlock {
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
  return blocks.map(
    (block) => `${block.label}：${block.title}；${block.detail}。`,
  );
}

function isIsoDate(value: string | null | undefined): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function absoluteYi(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "未提供";
  if (value > 0 && value < 500_000) return "少于 0.01 亿";
  return formatYi(value, false);
}

function buildAttributionCoverage(input: {
  expectedReportDate?: string;
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  campisiRequested?: boolean;
  campisiLoading?: boolean;
  campisiError?: boolean;
  campisiFormalUseAllowed?: boolean | null;
  campisiResultMeta?: ResultMeta | null;
}): HomeAttributionCoverage {
  const payload = input.campisiFourEffects;
  const meta = input.campisiResultMeta;
  const isFormalBridge = payload?.basis === "formal_report_pnl_bridge";
  const qualityNotices = [...new Set([
    buildCampisiResultQualityNotice(meta ?? null),
    isFormalBridge ? buildCampisiBridgeQualityNotice(payload.formal_closure) : null,
  ].filter((notice): notice is string => Boolean(notice)))];
  const qualityError = meta?.quality_flag === "error" ||
    (isFormalBridge && payload.formal_closure?.bridge_quality_flag === "error");
  const formalUseAllowed = meta?.formal_use_allowed ?? input.campisiFormalUseAllowed;
  const base = {
    label: isFormalBridge ? "正式桥归因覆盖" : "持仓收益归因覆盖",
    periodLabel: "归因区间未提供",
    basisLabel: qualityError ? "归因来源存在质量错误；当前不可正式使用" : "归因口径未确认",
    positionLabel: null,
    excludedValueLabel: null,
    effectNotices: qualityNotices,
    detailPath: null,
  };
  if (input.campisiError) {
    return { ...base, state: "error", summary: "持仓归因覆盖读取失败" };
  }
  if (input.campisiLoading) {
    return { ...base, state: qualityError ? "error" : "loading", summary: qualityError ? "归因来源存在数据质量错误" : "持仓归因覆盖读取中" };
  }
  if (!payload) {
    return {
      ...base,
      state: qualityError ? "error" : input.campisiRequested ? "unknown" : "idle",
      summary: qualityError ? "归因来源存在数据质量错误" : input.campisiRequested ? "暂无可核对的覆盖数据" : "持仓归因覆盖待加载",
    };
  }

  const periodLabel = isIsoDate(payload.period_start) && isIsoDate(payload.period_end)
    ? `归因区间 ${payload.period_start} 至 ${payload.period_end}`
    : base.periodLabel;
  const dated = { ...base, periodLabel };
  if (
    !isIsoDate(input.expectedReportDate) ||
    !isIsoDate(payload.report_date) ||
    !isIsoDate(payload.period_start) ||
    !isIsoDate(payload.period_end) ||
    payload.period_start > payload.period_end
  ) {
    return { ...dated, state: qualityError ? "error" : "unknown", summary: "报告日或归因区间未确认，覆盖信息未提供" };
  }
  if (
    payload.report_date !== input.expectedReportDate ||
    payload.period_end !== input.expectedReportDate
  ) {
    return {
      ...dated,
      state: qualityError ? "error" : "date-mismatch",
      summary: `来源报告日与首页不一致：归因 ${payload.report_date}，首页 ${input.expectedReportDate}`,
    };
  }

  const availability = payload.effect_availability;
  const position = availability?.position_change;
  const params = new URLSearchParams({
    source: "dashboard-home",
    report_date: payload.period_end,
    campisi_start_date: payload.period_start,
    campisi_end_date: payload.period_end,
  });
  const detailPath = `/pnl-attribution?${params.toString()}`;
  if (isFormalBridge) {
    const coverage = payload.input_quality?.formal_bridge_coverage;
    if (!coverage || coverage.source !== "pnl.bridge.rows" || coverage.basis !== "formal_report_pnl_bridge") {
      return {
        ...dated,
        basisLabel: `正式损益桥归因${qualityError ? "；当前不可正式使用" : ""}`,
        state: qualityError ? "error" : "unknown",
        summary: "会计记录行覆盖信息未提供，不能推定完整覆盖",
      };
    }
    const total = coverage.bridge_rows;
    const covered = coverage.attributed_rows;
    const countsValid = Number.isInteger(total) && (total ?? -1) >= 0 &&
      Number.isInteger(covered) && covered >= 0;
    const coverageValid = countsValid && (
      (coverage.status === "ok" && (total ?? 0) > 0 && covered === total) ||
      (coverage.status === "partial" && covered > 0 && covered < (total ?? 0))
    );
    const positionLabel = countsValid ? `会计记录行纳入 ${covered}/${total} 行` : null;
    const blocks = [availability?.roll_down_availability, availability?.treasury_curve_availability, availability?.credit_spread_availability];
    const effectsValid = blocks.every((block) => block &&
      Number.isInteger(block.applicable_rows) && block.applicable_rows >= 0 &&
      Number.isInteger(block.unavailable_rows) && block.unavailable_rows >= 0 &&
      Array.isArray(block.reasons) && (
        (block.status === "ok" && block.applicable_rows > 0 && block.unavailable_rows === 0) ||
        (block.status === "not_applicable" && block.applicable_rows === 0 && block.unavailable_rows === 0) ||
        (block.status === "partial" && block.unavailable_rows > 0 && block.unavailable_rows < block.applicable_rows) ||
        (block.status === "unavailable" && block.applicable_rows > 0 && block.unavailable_rows === block.applicable_rows)
      ));
    const curveNotices = effectsValid ? buildCurveAvailabilityNotices(availability) : [];
    const hasEffectGap = blocks.some((block) => block?.status === "partial" || block?.status === "unavailable") ||
      [availability?.treasury_effect, availability?.spread_effect, availability?.accrued_interest]
        .some((entry) => entry && entry.status !== "ok");
    const closure = payload.formal_closure;
    const closureConfirmed = closure?.status === "closed" && closure.report_date === payload.report_date;
    const metadataConfirmed = meta &&
      ["ok", "warning", "error", "stale"].includes(meta.quality_flag) &&
      ["ok", "vendor_stale", "vendor_unavailable"].includes(meta.vendor_status) &&
      ["none", "latest_snapshot"].includes(meta.fallback_mode);
    const effectNotices = [
      ...qualityNotices,
      ...curveNotices.map((notice) => `${notice.label}${notice.statusText}：${notice.text}`),
      ...(!effectsValid ? ["市场效应覆盖诊断未提供或计数不一致，不能推定完整覆盖。"] : []),
      ...(hasEffectGap && curveNotices.every((notice) => notice.statusText === "不适用")
        ? ["正式桥归因效应存在输入缺口，详见同区间明细。"] : []),
      ...(!closureConfirmed ? ["归因合计与正式损益金额闭合未确认。"] : []),
      ...(!metadataConfirmed ? ["归因来源质量状态未确认。"] : []),
    ];
    const state = qualityError ? "error"
      : !coverageValid ? coverage.status === "unavailable" ? "unavailable" : "unknown"
        : closure?.status === "unavailable" ? "unavailable"
          : !effectsValid || !metadataConfirmed || !closure ? "unknown"
            : coverage.status === "partial" || hasEffectGap || !closureConfirmed ||
              qualityNotices.length > 0 || formalUseAllowed !== true ? "partial"
              : "complete";
    return {
      ...dated,
      state,
      basisLabel: `正式损益桥归因${state === "complete" ? "" : "；当前不可正式使用"}`,
      summary: state === "error" ? "归因来源存在数据质量错误，不能按完整口径使用"
        : state === "unavailable" ? countsValid && total === 0 && covered === 0
          ? "本期正式桥无会计记录行，暂无可核对的归因数据"
          : "会计记录行覆盖或正式损益金额闭合不可用"
          : state === "unknown" ? "会计记录行或市场效应覆盖尚未确认，不能推定完整覆盖"
            : state === "partial" ? coverage.status === "partial"
              ? "仅部分会计记录行纳入归因，不能按完整口径解读"
              : "会计记录行已纳入；市场效应输入、金额闭合或来源质量仍有缺口"
              : blocks.every((block) => block?.status === "not_applicable")
                ? "会计记录行已全部纳入；本期无适用市场效应"
                : "会计记录行已全部纳入，适用市场效应输入可用",
      positionLabel,
      effectNotices,
      detailPath: countsValid ? detailPath : null,
    };
  }
  const total = availability?.bonds;
  const excluded = position?.unavailable_bonds;
  const covered = position?.covered_bonds;
  const countsValid =
    Number.isInteger(total) && (total ?? 0) > 0 &&
    Number.isInteger(excluded) && (excluded ?? -1) >= 0 &&
    Number.isInteger(covered) && (covered ?? -1) >= 0 &&
    (covered ?? 0) + (excluded ?? 0) === total;
  if (
    !position || !countsValid ||
    !availability?.treasury_effect ||
    !availability.spread_effect ||
    !availability.accrued_interest ||
    !["ok", "partial", "unavailable"].includes(position.status) ||
    (position.status === "ok" && excluded !== 0) ||
    (position.status === "partial" && (excluded === 0 || covered === 0)) ||
    (position.status === "unavailable" && covered !== 0)
  ) {
    return {
      ...dated,
      state: qualityError ? "error" : "unknown",
      summary: "覆盖信息未提供或计数不一致，不能推定全覆盖",
    };
  }

  const availabilityNotices = buildCampisiAvailabilityNotices(availability)
    .filter((notice) => notice.key !== "position_change")
    // The detail page carries the full diagnostic; the narrow home card keeps its first sentence.
    .map((notice) => `${notice.text.split("。")[0].replace(/(影响 \d+\/\d+) 只债券$/, "$1 项持仓")}。`);
  const curveDateNotice = buildCampisiTreasuryCurveDateNotice(payload);
  const maturity = payload.input_quality?.included_maturity_unavailable;
  const maturityGap = position.status !== "unavailable" && maturity &&
    Number.isInteger(maturity.positions) && maturity.positions > 0 &&
    Number.isFinite(maturity.market_value_start_abs) && maturity.market_value_start_abs >= 0 &&
    Number.isFinite(maturity.model_residual)
    ? maturity
    : null;
  const maturityValueLabel = maturityGap &&
    maturityGap.market_value_start_abs > 0 && maturityGap.market_value_start_abs < 500_000
    ? `${maturityGap.market_value_start_abs.toLocaleString("en-US")} 元`
    : absoluteYi(maturityGap?.market_value_start_abs);
  const residualLabel = maturityGap
    ? maturityGap.model_residual !== 0 && Math.abs(maturityGap.model_residual) < 500_000
      ? `${maturityGap.model_residual > 0 ? "+" : ""}${maturityGap.model_residual.toLocaleString("en-US")} 元`
      : maturityGap.model_residual === 0
        ? formatYi(0, false)
        : formatYiSigned(maturityGap.model_residual)
    : null;
  const effectNotices = [
    ...qualityNotices,
    ...availabilityNotices,
    ...(curveDateNotice ? [curveDateNotice] : []),
    ...(maturityGap ? [
      `到期日不可用 ${maturityGap.positions} 项持仓（已纳入模型）；期初绝对市值 ${maturityValueLabel}；模型剩余项 ${residualLabel}。`,
      "国债曲线可用不代表逐项久期可用；上述剩余项不代表主动选券。",
    ] : []),
  ];
  const state = qualityError ? "error" : position.status === "unavailable"
    ? "unavailable"
    : position.status === "partial" || availabilityNotices.length > 0 || maturityGap || qualityNotices.length > 0
      ? "partial"
      : "complete";
  const basisLabel = qualityError || formalUseAllowed === false || position.status !== "ok"
    ? "Campisi 模型分析口径；当前不可正式使用"
    : "Campisi 模型归因；与正式损益桥口径不同";
  const positionLabel = position.status === "unavailable"
    ? `无可归因持仓；本金变化维度排除 ${excluded}/${total} 项持仓`
    : `本金变化维度覆盖 ${covered}/${total} 项持仓；排除 ${excluded}/${total} 项持仓`;
  const excludedValueLabel = (excluded ?? 0) > 0
    ? `排除绝对市值：期初 ${absoluteYi(position.unavailable_market_value_start)}；期末 ${absoluteYi(position.unavailable_market_value_end)}`
    : null;
  return {
    ...dated,
    state,
    basisLabel,
    summary: state === "error" ? "归因来源存在数据质量错误，当前不可正式使用" : state === "unavailable"
      ? "全部持仓被排除，暂无可归因收益"
      : state === "partial"
         ? qualityNotices.length > 0 && position.status === "ok" && availabilityNotices.length === 0 && !maturityGap
           ? "归因来源质量存在缺口，当前不能按完整口径使用"
           : maturityGap && position.status === "ok" && availabilityNotices.length === 0
          ? "已纳入持仓存在到期日缺口，模型剩余项不代表主动选券"
          : "归因输入部分缺失，金额未外推全组合"
        : "本金变化与逐效应输入均有覆盖诊断",
    positionLabel,
    excludedValueLabel,
    effectNotices,
    detailPath,
  };
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
  return missing.length > 0
    ? `来源状态：部分缺 ${missing.join("/")}`
    : "来源状态：正式链路";
}

export function buildHomeMarketContextModel(input: {
  marketTape: readonly HomeMarketTicker[];
  marketPoints: readonly ChoiceMacroLatestPoint[] | null | undefined;
  macroNewsEvents: readonly ChoiceNewsEvent[] | null | undefined;
  todayIsoDate: string;
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  expectedReportDate?: string;
  campisiRequested?: boolean;
  campisiLoading?: boolean;
  campisiError?: boolean;
  campisiFormalUseAllowed?: boolean | null;
  campisiResultMeta?: ResultMeta | null;
  returnDecomposition: ReturnDecompositionPayload | null | undefined;
  yieldCurveTermStructure: YieldCurveTermStructurePayload | null | undefined;
  creditSpreadMigration: CreditSpreadMigrationPayload | null | undefined;
  attribution: AttributionHint;
}): HomeMarketContextModel {
  void input.macroNewsEvents;
  void input.todayIsoDate;
  const temperature = buildTemperature(input.marketTape);
  const yieldCurveDateSummary = summarizeYieldCurveDates(
    input.yieldCurveTermStructure?.curves ?? [],
  );
  const contextBlocks = [
    buildPnlBlock(
      input.campisiFourEffects,
      input.returnDecomposition,
      input.attribution,
    ),
    buildCurveBlock(input.yieldCurveTermStructure, yieldCurveDateSummary),
    buildCreditBlock(input.creditSpreadMigration),
  ];
  const curveTable = buildCurveTable(input.yieldCurveTermStructure);
  const asOfDate = latestIsoDate([
    input.returnDecomposition?.report_date,
    input.campisiFourEffects?.report_date,
    yieldCurveDateSummary.sharedResolvedDate,
    input.creditSpreadMigration?.report_date,
  ]);

  return {
    ...temperature,
    contextBlocks,
    curveTable,
    rateSeries: mapMarketSeries(input.marketPoints),
    aiSummary: buildSummary(contextBlocks),
    attributionCoverage: buildAttributionCoverage(input),
    sourceLabel: SOURCE_LABEL,
    asOfLabel: asOfDate ? `数据截至 ${asOfDate}` : "数据截至：暂无",
    statusLabel: buildStatusLabel(input),
    refreshLabel: REFRESH_LABEL,
  };
}
