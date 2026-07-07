import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { ModuleHomeTone } from "./moduleHomeModel";
import { buildActionQueue, compactParts, type MarketActionItem, type MarketActionQueueProps } from "./marketActionQueueModel";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
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

export function MarketActionQueue(props: MarketActionQueueProps) {
  const items = buildActionQueue(props);
  const { view } = props;

  if (items.length === 0) {
    return null;
  }

  return (
    <section
      className={`${dhStyles.dhCard} ${marketStyles.actionQueue} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-actions"
    >
      <div className={marketStyles.actionQueueHeader}>
        <span>下一步动作</span>
        <em>只保留今天需要看的事</em>
        <em data-testid="module-home-market-actions-audit-label" hidden>
          Action Queue · Owner / SLA / Gate / Evidence Pack
        </em>
      </div>
      <div className={marketStyles.actionQueueTape} role="table" aria-label="行动队列">
        <div className={marketStyles.actionQueueTableHead} role="row">
          <span role="columnheader">优先级</span>
          <span role="columnheader">事项</span>
          <span role="columnheader">证据</span>
          <span role="columnheader">入口</span>
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
              role="row"
              to={item.path}
            >
              <span className={`${marketStyles.actionQueueRank} ${toneClass(item.tone)}`} role="cell">{item.rank}</span>
              <strong className={marketStyles.actionQueueTableTitle} role="cell">{item.title}</strong>
              <em
                aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
                className={marketStyles.actionQueueTableEvidence}
                data-testid={`module-home-market-action-${item.key}-evidence`}
                role="cell"
              >
                {item.evidence.length > 0
                  ? renderColoredFieldSegments(item.evidence, item.evidenceSparkline)
                  : <span>待返回</span>}
              </em>
              <b className={marketStyles.actionQueueTableTarget} data-testid={`module-home-market-action-${item.key}-target`} role="cell">
                {item.label}
              </b>
              <div
                aria-label={[...taskParts, ...gateParts, ...packParts].join(" / ")}
                className={`${marketStyles.actionQueueMetaGrid} ${marketStyles.marketAuditOnly}`}
                hidden
              >
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
