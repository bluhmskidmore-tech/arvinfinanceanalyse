import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

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

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function compactParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== "-"));
}

function isChangeEvidencePart(part: string) {
  return /bp|%|日变动|[+-]\d/.test(part);
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

function renderColoredFieldSegments(parts: string[], sparkline?: readonly number[]) {
  return parts.flatMap((part, index) => {
    const change = marketChangePresentation(
      isChangeEvidencePart(part) ? part : undefined,
      isChangeEvidencePart(part) ? sparkline : undefined,
      MARKET_CHANGE_CLASSES,
    );
    const segment = (
      <span
        className={change.direction ? change.className : undefined}
        data-change={change.direction}
        key={`${part}-${index}`}
      >
        {part}
      </span>
    );
    return index > 0
      ? [
          <span className={marketStyles.fieldSeparator} key={`${part}-${index}-separator`}>
            {" / "}
          </span>,
          segment,
        ]
      : [segment];
  });
}

function taskMetaParts(item: MarketActionItem) {
  return [`Owner ${item.task.owner}`, `SLA ${item.task.sla}`, `状态 ${item.task.state}`];
}

function gateMetaParts(item: MarketActionItem) {
  return [`触发 ${item.gate.trigger}`, `核验 ${item.gate.check}`, `下一步 ${item.gate.next}`];
}

function evidencePackParts(item: MarketActionItem) {
  const [lead, ...rest] = item.evidencePack;
  return compactParts([lead ? `Evidence Pack ${lead}` : "Evidence Pack 待返回", ...rest]);
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
  const keyRateLabel = keyRatePanel?.rows[0]?.label ?? "关键利率";
  const crossAssetEvidence = firstRowEvidence(macroPanel);

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

  if (aShareRisk) {
    queue.push({
      key: "a-share-risk",
      rank: aShareRisk.tone === "error" ? "P0" : "P1",
      title: `复核${aShareRisk.label}`,
      evidence: compactParts([aShareRisk.value, aShareRisk.detail]),
      evidencePack: compactParts([aShareRisk.label, aShareRisk.value, aShareRisk.detail, "macro-toolkit"]),
      task: {
        owner: "宏观策略岗",
        sla: aShareRisk.tone === "error" ? "T+0 午盘前" : "T+0 收盘前",
        state: aShareRisk.tone === "error" ? "阻塞" : "待复核",
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
      rank: "P2",
      title: "确认关键利率变动",
      evidence: firstRowEvidence(keyRatePanel),
      evidenceSparkline: keyRatePanel?.rows[0]?.sparkline,
      evidencePack: firstRowEvidencePack(keyRatePanel, keyRateLabel, "market-data"),
      task: {
        owner: "市场数据岗",
        sla: "T+1 早盘",
        state: "监控",
      },
      gate: {
        trigger: "利率变动",
        check: keyRateLabel,
        next: "利率序列",
      },
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

export function MarketActionQueue(props: MarketActionQueueProps) {
  const items = buildActionQueue(props);
  const { view } = props;

  if (items.length === 0) {
    return null;
  }

  return (
    <section
      className={`${marketStyles.actionQueue} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-actions"
    >
      <div className={marketStyles.actionQueueHeader}>
        <span>下一步动作</span>
        <em>只保留今天需要看的事</em>
        <em data-testid="module-home-market-actions-audit-label" hidden>
          Action Queue · Owner / SLA / Gate / Evidence Pack
        </em>
      </div>
      <div className={marketStyles.actionQueueTape}>
        <div aria-hidden="true" className={marketStyles.actionQueueTableHead}>
          <span>优先级</span>
          <span>事项</span>
          <span>证据</span>
          <span>入口</span>
        </div>
        {items.map((item) => {
          const taskParts = taskMetaParts(item);
          const gateParts = gateMetaParts(item);
          const packParts = evidencePackParts(item);
          return (
            <Link
              className={marketStyles.actionQueueTableRow}
              data-testid={`module-home-market-action-${item.key}`}
              data-tone={item.tone}
              key={item.key}
              to={item.path}
            >
              <span className={`${marketStyles.actionQueueRank} ${toneClass(item.tone)}`}>{item.rank}</span>
              <strong className={marketStyles.actionQueueTableTitle}>{item.title}</strong>
              <em
                aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
                className={marketStyles.actionQueueTableEvidence}
                data-testid={`module-home-market-action-${item.key}-evidence`}
              >
                {item.evidence.length > 0
                  ? renderColoredFieldSegments(item.evidence, item.evidenceSparkline)
                  : <span>待返回</span>}
              </em>
              <b className={marketStyles.actionQueueTableTarget} data-testid={`module-home-market-action-${item.key}-target`}>
                {item.label}
              </b>
              <div className={marketStyles.actionQueueMetaGrid}>
                <span
                  aria-label={taskParts.join(" / ")}
                  className={marketStyles.actionQueueTaskMeta}
                  data-testid={`module-home-market-action-${item.key}-task-meta`}
                >
                  {renderFieldSegments(taskParts)}
                </span>
                <span
                  aria-label={gateParts.join(" / ")}
                  className={marketStyles.actionQueueGate}
                  data-testid={`module-home-market-action-${item.key}-gate`}
                >
                  {renderFieldSegments(gateParts)}
                </span>
                <span
                  aria-label={packParts.join(" / ")}
                  className={marketStyles.actionQueueEvidencePack}
                  data-testid={`module-home-market-action-${item.key}-evidence-pack`}
                >
                  {renderFieldSegments(packParts)}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
      <div
        className={marketStyles.actionQueueSourceGate}
        data-testid="module-home-status-strip"
        hidden
      >
        <span>来源闸门</span>
        <strong>{view.stateLabel}</strong>
        <em>{view.sourceScope}</em>
      </div>
    </section>
  );
}
