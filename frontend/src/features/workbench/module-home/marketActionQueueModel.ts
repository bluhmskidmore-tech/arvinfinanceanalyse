import { resolveMarketChangeDirection } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import { buildMarketCurveSpreadRows } from "./moduleHomeModel";

export type MarketActionQueueProps = {
  view: ModuleHomeView;
  keyRatePanel?: ModuleHomeDetailPanel;
  yieldCurvePanel?: ModuleHomeDetailPanel;
  macroPanel?: ModuleHomeDetailPanel;
};

export type MarketActionItem = {
  key: string;
  rank: string;
  title: string;
  evidence: string[];
  evidenceSparkline?: readonly number[];
  evidencePack: string[];
  task: {
    owner: string;
    sla: string;
    state: string;
  };
  gate: {
    trigger: string;
    check: string;
    next: string;
  };
  path: string;
  label: string;
  tone: ModuleHomeTone;
};

const ACTION_LIMIT = 3;

export function compactParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== "-"));
}

function firstRowEvidence(panel?: ModuleHomeDetailPanel) {
  const row = panel?.rows[0];
  if (!row) return compactParts([panel?.stateDetail]);
  return compactParts([row.label, row.value, row.detail, row.tradeDate]);
}

function firstRowEvidencePack(panel: ModuleHomeDetailPanel | undefined, fallbackLabel: string, sourceScope: string) {
  const row = panel?.rows[0];
  if (!row) return compactParts([fallbackLabel, panel?.stateDetail, sourceScope]);
  return compactParts([row.label, row.source, row.tradeDate, row.detail, sourceScope]);
}

function panelHasNoRows(panel?: ModuleHomeDetailPanel) {
  return Boolean(panel && panel.rows.length === 0 && (!panel.chart || panel.chart.categories.length === 0));
}

function rowIndicatesMovement(row?: ModuleHomeDetailRow): boolean {
  if (!row) {
    return false;
  }
  const direction = resolveMarketChangeDirection(row.detail, row.sparkline);
  return direction === "up" || direction === "down";
}

function findTenYearRow(panel?: ModuleHomeDetailPanel): ModuleHomeDetailRow | undefined {
  return panel?.rows.find((row) => /10Y|10年|十年|gov-10y/i.test(`${row.key} ${row.label}`));
}

function spreadOrTenYearMoved(keyRatePanel?: ModuleHomeDetailPanel): boolean {
  if (rowIndicatesMovement(findTenYearRow(keyRatePanel))) {
    return true;
  }
  const { termSpreadRows, creditSpreadRow } = buildMarketCurveSpreadRows(keyRatePanel);
  return [...termSpreadRows, creditSpreadRow].some((row) => rowIndicatesMovement(row));
}

export function buildActionQueue({
  view,
  keyRatePanel,
  yieldCurvePanel,
  macroPanel,
}: MarketActionQueueProps): MarketActionItem[] {
  const queue: MarketActionItem[] = [];
  const failedStatus = view.statuses.find((status) => status.tone === "error" && status.key !== "a-share-risk");
  const aShareRisk = view.statuses.find((status) => status.key === "a-share-risk");
  const crossAssetStatus = view.statuses.find((status) => status.key === "cross-asset");
  const curveNeedsCheck = panelHasNoRows(yieldCurvePanel);
  const hasKeyRates = (keyRatePanel?.rows.length ?? 0) > 0;
  const keyRateLabel = keyRatePanel?.rows[0]?.label ?? "关键利率";
  const crossAssetEvidence = firstRowEvidence(macroPanel);
  const ratesMoved = spreadOrTenYearMoved(keyRatePanel);
  const blockingAShare = aShareRisk?.tone === "error";

  if (failedStatus) {
    queue.push({
      key: "failed-read",
      rank: "P0",
      title: "市场数据读链路复核",
      evidence: compactParts([failedStatus.detail]),
      evidencePack: compactParts([failedStatus.label, failedStatus.detail, "market-data"]),
      task: {
        owner: "平台值班岗",
        sla: "T+0 30m",
        state: "阻塞",
      },
      gate: {
        trigger: "读链路异常",
        check: failedStatus.label,
        next: "查看读链路",
      },
      path: "/market-data",
      label: "查看读链路",
      tone: "error",
    });
  }

  if (aShareRisk && blockingAShare) {
    queue.push({
      key: "a-share-risk",
      rank: "P0",
      title: `复核${aShareRisk.label}`,
      evidence: compactParts([aShareRisk.value, aShareRisk.detail]),
      evidencePack: compactParts([aShareRisk.label, aShareRisk.value, aShareRisk.detail, "macro-toolkit"]),
      task: {
        owner: "宏观策略岗",
        sla: "T+0 午盘前",
        state: "阻塞",
      },
      gate: {
        trigger: "A股风险",
        check: "跨资产传导",
        next: "宏观工具",
      },
      path: "/macro-toolkit",
      label: "宏观工具",
      tone: aShareRisk.tone,
    });
  }

  if (curveNeedsCheck) {
    queue.push({
      key: "curve-check",
      rank: "P1",
      title: "补齐国债/国开曲线核验",
      evidence: compactParts([yieldCurvePanel?.stateDetail ?? "曲线报价为空。"]),
      evidencePack: compactParts(["曲线报价缺口", yieldCurvePanel?.stateDetail ?? "曲线报价为空。", "market-data"]),
      task: {
        owner: "市场数据岗",
        sla: "T+0 收盘前",
        state: "待核验",
      },
      gate: {
        trigger: "曲线缺口",
        check: "国债/国开曲线",
        next: "市场数据",
      },
      path: "/market-data",
      label: "市场数据",
      tone: "watch",
    });
  } else if (hasKeyRates) {
    queue.push({
      key: "key-rate-check",
      rank: ratesMoved ? "P1" : "P2",
      title: ratesMoved ? "确认关键利率与利差变动" : "确认关键利率变动",
      evidence: firstRowEvidence(keyRatePanel),
      evidenceSparkline: keyRatePanel?.rows[0]?.sparkline,
      evidencePack: firstRowEvidencePack(keyRatePanel, keyRateLabel, "market-data"),
      task: {
        owner: "市场数据岗",
        sla: ratesMoved ? "T+0 收盘前" : "T+1 早盘",
        state: ratesMoved ? "待复核" : "监控",
      },
      gate: {
        trigger: ratesMoved ? "利率/利差变动" : "利率变动",
        check: keyRateLabel,
        next: "利率序列",
      },
      path: "/market-data",
      label: "利率序列",
      tone: keyRatePanel?.tone ?? "ok",
    });
  }

  if (aShareRisk && !blockingAShare) {
    queue.push({
      key: "a-share-risk",
      rank: "P2",
      title: `复核${aShareRisk.label}`,
      evidence: compactParts([aShareRisk.value, aShareRisk.detail]),
      evidencePack: compactParts([aShareRisk.label, aShareRisk.value, aShareRisk.detail, "macro-toolkit"]),
      task: {
        owner: "宏观策略岗",
        sla: "T+0 收盘前",
        state: "待复核",
      },
      gate: {
        trigger: "A股风险",
        check: "跨资产传导",
        next: "宏观工具",
      },
      path: "/macro-toolkit",
      label: "宏观工具",
      tone: aShareRisk.tone,
    });
  }

  queue.push({
    key: "cross-asset-path",
    rank: "P2",
    title: "跟踪跨资产传导",
    evidence: crossAssetEvidence.length > 0 ? crossAssetEvidence : compactParts([crossAssetStatus?.detail, "跨资产传导解释以 /cross-asset 为准。"]),
    evidenceSparkline: macroPanel?.rows[0]?.sparkline,
    evidencePack:
      crossAssetEvidence.length > 0
        ? firstRowEvidencePack(macroPanel, "跨资产传导", "cross-asset")
        : compactParts(["跨资产传导", crossAssetStatus?.detail, "cross-asset"]),
    task: {
      owner: "跨资产研究岗",
      sla: "T+1 早会",
      state: "观察",
    },
    gate: {
      trigger: "跨资产传导",
      check: "宏观快讯",
      next: "跨资产",
    },
    path: "/cross-asset",
    label: "跨资产",
    tone: macroPanel?.tone ?? crossAssetStatus?.tone ?? "muted",
  });

  return queue.slice(0, ACTION_LIMIT);
}
