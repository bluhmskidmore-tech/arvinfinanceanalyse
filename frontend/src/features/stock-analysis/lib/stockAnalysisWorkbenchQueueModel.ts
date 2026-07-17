import type { StockAnalysisWorkbenchPayload } from "../../../api/contracts";
import type { StockCandidateReviewQueueItem } from "./stockAnalysisPageModel";

type WorkbenchReviewCandidate = StockAnalysisWorkbenchPayload["first_screen"]["review_queue"][number];
type CandidateEvidence = StockCandidateReviewQueueItem["primaryEvidence"][number];

const sourceLabels: Record<string, string> = {
  stock_candidates: "趋势候选",
  factor_screen_candidates: "多因子候选",
  hybrid_fusion_candidates: "融合候选",
  uptrend_momentum_candidates: "动量候选",
  fresh_trend_watchlist: "新趋势观察",
  mean_reversion_candidates: "超跌观察",
  theme_breakout: "题材观察",
};

function textValue(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function rankValue(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function rawValue(value: unknown): string | null {
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : null;
  if (typeof value === "string") return value.trim() || null;
  return null;
}

function evidenceFields(row: WorkbenchReviewCandidate) {
  const definitions = [
    ["score", "观察分"],
    ["factor_score", "因子分"],
    ["fusion_score", "融合分"],
    ["pe", "PE 原值"],
    ["pb", "PB 原值"],
  ] as const;

  return definitions.flatMap(([key, label]) => {
    const value = rawValue(row[key]);
    return value == null ? [] : [{ key, label, value }];
  });
}

function themeSourceLabel(value: unknown): string | null {
  const sourceKind = textValue(value)?.toLowerCase();
  if (!sourceKind) return null;
  if (sourceKind === "tushare_current_overlay" || sourceKind === "tushare_ths_current_overlay") {
    return "当前概念覆盖";
  }
  if (sourceKind === "real_concept" || sourceKind === "choice_point_in_time") {
    return "时点概念成分";
  }
  if (sourceKind === "proxy") return "代理主题";
  return "来源待确认";
}

function themeMembershipEvidence(row: WorkbenchReviewCandidate) {
  if (!Array.isArray(row.theme_memberships)) return [];
  return row.theme_memberships.flatMap((value, index) => {
    if (value == null || typeof value !== "object") return [];
    const membership = value as Record<string, unknown>;
    const themeKey = textValue(membership.theme_key);
    const themeName = textValue(membership.theme_name) ?? themeKey;
    if (!themeName) return [];
    const themeRank = rawValue(membership.rank);
    const memberRank = rawValue(membership.member_rank);
    const sourceLabel = themeSourceLabel(membership.source_kind);
    const parts = [
      themeRank ? `${themeName} #${themeRank}` : themeName,
      sourceLabel,
      memberRank ? `成分 #${memberRank}` : null,
    ].filter((item): item is string => Boolean(item));
    return [
      {
        key: `theme_membership:${themeKey ?? themeName}:${index}`,
        label: "题材归属",
        value: parts.join(" · "),
      },
    ];
  });
}

function uniqueEvidence(items: CandidateEvidence[]): CandidateEvidence[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const identity = `${item.label}\u0000${item.value}`;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}

function uniqueText(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

function isThemeReviewCandidate(row: WorkbenchReviewCandidate): boolean {
  return textValue(row.source_module) === "theme_breakout" || themeMembershipEvidence(row).length > 0;
}

export function selectStockCandidateThemeEvidence(card: StockCandidateReviewQueueItem): CandidateEvidence[] {
  return uniqueEvidence(
    [...(card.primaryEvidence ?? []), ...(card.supportingEvidence ?? []), ...(card.rawFields ?? [])].filter(
      (item) => item.label === "题材归属" || item.key.startsWith("theme_membership:"),
    ),
  );
}

export function resolveStockAnalysisFormalUseAllowed(
  payloadFormalUseAllowed: boolean | null | undefined,
  resultMetaFormalUseAllowed: boolean | null | undefined,
): boolean {
  return payloadFormalUseAllowed === true && resultMetaFormalUseAllowed === true;
}

export function buildStockAnalysisWorkbenchReviewQueue(
  rows: StockAnalysisWorkbenchPayload["first_screen"]["review_queue"],
  excludedSourceModules: ReadonlySet<string> = new Set(),
): StockCandidateReviewQueueItem[] {
  return rows.flatMap((row, index) => {
    const sourceModuleKey = textValue(row.source_module);
    if (sourceModuleKey && excludedSourceModules.has(sourceModuleKey)) return [];
    const stockCode = textValue(row.stock_code);
    if (!stockCode) return [];

    const rank = rankValue(row.rank, index + 1);
    const stockName = textValue(row.stock_name) ?? stockCode;
    const sectorCode = textValue(row.sector_code) ?? "";
    const sectorName = textValue(row.sector_name) ?? textValue(row.industry) ?? "接口未提供";
    const sourceModule = textValue(row.source_module) ?? "workbench_review_queue";
    const sourceLabel = sourceLabels[sourceModule] ?? "后端观察队列";
    const observedFields = evidenceFields(row);
    const membershipEvidence = themeMembershipEvidence(row);
    const sourceEvidence = [
      { key: "source_module", label: "来源模块", value: sourceLabel },
      { key: "api_rank", label: "接口排序", value: `#${rank}` },
    ];
    const sourceIdentityEvidence = {
      key: "source_module_key",
      label: "来源模块标识",
      value: sourceModule,
    };
    const evidence = [...membershipEvidence, ...sourceEvidence, ...observedFields];
    const firstThemeName = Array.isArray(row.theme_memberships)
      ? row.theme_memberships
          .map((value) =>
            value != null && typeof value === "object"
              ? textValue((value as Record<string, unknown>).theme_name)
              : null,
          )
          .find((value): value is string => Boolean(value))
      : null;
    const usesCurrentOverlay = Array.isArray(row.theme_memberships)
      ? row.theme_memberships.some(
          (value) =>
            value != null &&
            typeof value === "object" &&
            themeSourceLabel((value as Record<string, unknown>).source_kind) === "当前概念覆盖",
        )
      : false;
    const boundaryEvidence = [
      "候选来自 workbench 首屏只读队列；门禁与正式用途边界以接口状态为准。",
      ...(usesCurrentOverlay ? ["当前覆盖 · 非时点 · 不可历史使用 · 仅观察"] : []),
    ];

    return [
      {
        rank,
        stockCode,
        stockName,
        sectorCode,
        sectorName,
        headline: `${sourceLabel} #${rank} · ${stockName}`,
        pattern: "接口未提供",
        patternNote: "首屏候选接口未提供形态标签，页面不补算。",
        distanceToBreakoutPct: "待复核",
        reviewFocus: [
          stockName,
          sectorName,
          sourceLabel,
          membershipEvidence.length > 0
            ? `题材归属：${membershipEvidence.map((item) => item.value).join(" / ")}`
            : firstThemeName,
        ]
          .filter(Boolean)
          .join(" · "),
        primaryEvidence: evidence.slice(0, 3),
        supportingEvidence: evidence.slice(3),
        boundaryEvidence,
        invalidationFocus: "价格形态与风险退出条件待在个股详情复核。",
        invalidationRules: ["接口未返回正式交易或退出指令。"],
        rawFields: uniqueEvidence([...evidence, sourceIdentityEvidence]),
      },
    ];
  });
}

export function enrichStockAnalysisWorkbenchReviewQueue(
  workbenchQueue: StockCandidateReviewQueueItem[],
  strategyQueue: StockCandidateReviewQueueItem[],
): StockCandidateReviewQueueItem[] {
  const strategyByStockCode = new Map(
    strategyQueue.map((candidate) => [candidate.stockCode.trim().toUpperCase(), candidate] as const),
  );

  return workbenchQueue.map((workbenchCandidate) => {
    const strategyCandidate = strategyByStockCode.get(workbenchCandidate.stockCode.trim().toUpperCase());
    if (!strategyCandidate) return workbenchCandidate;

    const workbenchThemeEvidence = selectStockCandidateThemeEvidence(workbenchCandidate);
    const visibleEvidence = uniqueEvidence([
      ...workbenchThemeEvidence,
      ...strategyCandidate.primaryEvidence,
      ...strategyCandidate.supportingEvidence,
    ]);
    const workbenchHasSectorCode = Boolean(workbenchCandidate.sectorCode.trim());
    const workbenchHasSectorName =
      Boolean(workbenchCandidate.sectorName.trim()) &&
      workbenchCandidate.sectorName !== "接口未提供";
    const strategySectorMatchesWorkbench =
      workbenchHasSectorCode &&
      strategyCandidate.sectorCode.trim().toUpperCase() ===
        workbenchCandidate.sectorCode.trim().toUpperCase();

    return {
      ...strategyCandidate,
      rank: workbenchCandidate.rank,
      stockCode: workbenchCandidate.stockCode,
      stockName:
        workbenchCandidate.stockName === workbenchCandidate.stockCode
          ? strategyCandidate.stockName
          : workbenchCandidate.stockName,
      sectorCode:
        workbenchHasSectorCode
          ? workbenchCandidate.sectorCode
          : workbenchHasSectorName
            ? ""
            : strategyCandidate.sectorCode,
      sectorName: workbenchHasSectorName
        ? workbenchCandidate.sectorName
        : strategySectorMatchesWorkbench || !workbenchHasSectorCode
          ? strategyCandidate.sectorName
          : "接口未提供",
      reviewFocus: uniqueText([strategyCandidate.reviewFocus, workbenchCandidate.reviewFocus]).join(" · "),
      primaryEvidence: visibleEvidence.slice(0, 3),
      supportingEvidence: visibleEvidence.slice(3),
      boundaryEvidence:
        workbenchThemeEvidence.length > 0
          ? uniqueText([
              ...strategyCandidate.boundaryEvidence,
              ...workbenchCandidate.boundaryEvidence,
            ])
          : strategyCandidate.boundaryEvidence,
      rawFields: uniqueEvidence([
        ...strategyCandidate.rawFields,
        ...workbenchCandidate.rawFields,
      ]),
    };
  });
}

function mergeThemeEvidenceIntoCandidate(
  candidate: StockCandidateReviewQueueItem,
  themeCandidate: StockCandidateReviewQueueItem,
): StockCandidateReviewQueueItem {
  const themeEvidence = uniqueEvidence([
    ...selectStockCandidateThemeEvidence(candidate),
    ...selectStockCandidateThemeEvidence(themeCandidate),
  ]);
  const nonThemeEvidence = [...candidate.primaryEvidence, ...candidate.supportingEvidence].filter(
    (item) => item.label !== "题材归属" && !item.key.startsWith("theme_membership:"),
  );
  const visibleEvidence = uniqueEvidence([...themeEvidence, ...nonThemeEvidence]);
  const themeFocus = themeEvidence.length > 0
    ? `题材归属：${themeEvidence.map((item) => item.value).join(" / ")}`
    : null;

  return {
    ...candidate,
    reviewFocus: uniqueText([candidate.reviewFocus, themeFocus ?? ""]).join(" · "),
    primaryEvidence: visibleEvidence.slice(0, 3),
    supportingEvidence: visibleEvidence.slice(3),
    boundaryEvidence: uniqueText([...candidate.boundaryEvidence, ...themeCandidate.boundaryEvidence]),
    rawFields: uniqueEvidence([...candidate.rawFields, ...themeCandidate.rawFields]),
  };
}

export function mergeStockAnalysisWorkbenchThemeEvidence(
  strategyQueue: StockCandidateReviewQueueItem[],
  rows: StockAnalysisWorkbenchPayload["first_screen"]["review_queue"],
): StockCandidateReviewQueueItem[] {
  const merged = [...strategyQueue];
  const indexByStockCode = new Map(
    merged.map((candidate, index) => [candidate.stockCode.trim().toUpperCase(), index] as const),
  );
  const themeCandidates = rows.flatMap((row) =>
    isThemeReviewCandidate(row) ? buildStockAnalysisWorkbenchReviewQueue([row]) : [],
  );

  for (const themeCandidate of themeCandidates) {
    const stockKey = themeCandidate.stockCode.trim().toUpperCase();
    const existingIndex = indexByStockCode.get(stockKey);
    if (existingIndex == null) {
      indexByStockCode.set(stockKey, merged.length);
      merged.push(themeCandidate);
      continue;
    }
    merged[existingIndex] = mergeThemeEvidenceIntoCandidate(merged[existingIndex], themeCandidate);
  }

  return merged;
}
