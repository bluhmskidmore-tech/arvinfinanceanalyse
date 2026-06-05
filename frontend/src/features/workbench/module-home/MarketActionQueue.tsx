import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDetailPanel, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketActionQueueProps = {
  view: ModuleHomeView;
  keyRatePanel?: ModuleHomeDetailPanel;
  yieldCurvePanel?: ModuleHomeDetailPanel;
  macroPanel?: ModuleHomeDetailPanel;
};

type MarketActionItem = {
  key: string;
  rank: string;
  title: string;
  evidence: string[];
  path: string;
  label: string;
  tone: ModuleHomeTone;
};

const ACTION_LIMIT = 3;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function compactParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== "-"));
}

function renderFieldSegments(parts: string[]) {
  return parts.flatMap((part, index) =>
    index > 0
      ? [
          <span className={marketStyles.fieldSeparator} key={`${part}-${index}-separator`}>
            {" / "}
          </span>,
          <span key={`${part}-${index}`}>{part}</span>,
        ]
      : [<span key={`${part}-${index}`}>{part}</span>],
  );
}

function firstRowEvidence(panel?: ModuleHomeDetailPanel) {
  const row = panel?.rows[0];
  if (!row) return compactParts([panel?.stateDetail]);
  return compactParts([row.label, row.value, row.detail, row.tradeDate, row.source]);
}

function panelHasNoRows(panel?: ModuleHomeDetailPanel) {
  return Boolean(panel && panel.rows.length === 0 && (!panel.chart || panel.chart.categories.length === 0));
}

function buildActionQueue({
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
  const crossAssetEvidence = firstRowEvidence(macroPanel);

  if (failedStatus) {
    queue.push({
      key: "failed-read",
      rank: "P0",
      title: `${failedStatus.label}读链路复核`,
      evidence: compactParts([failedStatus.detail]),
      path: "/market-data",
      label: "查看读链路",
      tone: "error",
    });
  }

  if (aShareRisk) {
    queue.push({
      key: "a-share-risk",
      rank: aShareRisk.tone === "error" ? "P0" : "P1",
      title: `复核${aShareRisk.label}`,
      evidence: compactParts([aShareRisk.value, aShareRisk.detail]),
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
      path: "/market-data",
      label: "市场数据",
      tone: "watch",
    });
  } else if (hasKeyRates) {
    queue.push({
      key: "key-rate-check",
      rank: "P2",
      title: "确认关键利率变动",
      evidence: firstRowEvidence(keyRatePanel),
      path: "/market-data",
      label: "利率序列",
      tone: keyRatePanel?.tone ?? "ok",
    });
  }

  queue.push({
    key: "cross-asset-path",
    rank: "P3",
    title: "跟踪跨资产传导",
    evidence: crossAssetEvidence.length > 0 ? crossAssetEvidence : compactParts([crossAssetStatus?.detail, "跨资产传导解释以 /cross-asset 为准。"]),
    path: "/cross-asset",
    label: "跨资产",
    tone: macroPanel?.tone ?? crossAssetStatus?.tone ?? "muted",
  });

  return queue.slice(0, ACTION_LIMIT);
}

export function MarketActionQueue(props: MarketActionQueueProps) {
  const items = buildActionQueue(props);
  const { view } = props;

  if (items.length === 0) {
    return null;
  }

  return (
    <section className={marketStyles.actionQueue} data-testid="module-home-market-actions">
      <div className={marketStyles.actionQueueHeader}>
        <span>Action Queue</span>
        <strong>异常 / 机会闭环</strong>
        <em>只保留风险、曲线和跨资产三条处置线。</em>
      </div>
      <div className={marketStyles.actionQueueList}>
        {items.map((item) => (
          <Link
            className={marketStyles.actionQueueItem}
            data-testid={`module-home-market-action-${item.key}`}
            data-tone={item.tone}
            key={item.key}
            to={item.path}
          >
            <span className={`${marketStyles.actionQueueRank} ${toneClass(item.tone)}`}>{item.rank}</span>
            <div className={marketStyles.actionQueueMain}>
              <strong>{item.title}</strong>
              <em
                aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
                data-testid={`module-home-market-action-${item.key}-evidence`}
              >
                {item.evidence.length > 0 ? renderFieldSegments(item.evidence) : <span>待返回</span>}
              </em>
            </div>
            <b data-testid={`module-home-market-action-${item.key}-target`}>{item.label}</b>
          </Link>
        ))}
      </div>
      <div className={marketStyles.actionQueueSourceGate} data-testid="module-home-status-strip">
        <span>Source Gate</span>
        <strong>{view.stateLabel}</strong>
        <em>{view.sourceScope}</em>
      </div>
    </section>
  );
}
