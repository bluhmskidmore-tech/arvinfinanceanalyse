import { Tag } from "antd";
import type { MouseEvent, ReactNode } from "react";

import type { ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitScriptRecord,
} from "../../../api/macroToolkitClient";

import { MacroStatusIcon } from "../lib/MacroToolkitStatusPrimitives";
import { compactText } from "../lib/macroToolkitPanelShared";
import type {
  MacroToolkitActionReceipt,
  MacroToolkitActionReceiptStatus,
  MacroToolkitCommitteeChecklistItem,
  MacroToolkitCommitteePackItem,
  MacroToolkitDeepEvidenceQueueItem,
  MacroToolkitGovernanceFocusItem,
  MacroToolkitGovernanceFocusKey,
} from "../lib/macroToolkitPageModel";
import { governanceFocusFromEvidenceHref } from "../lib/macroToolkitPageModel";
import { MacroToolkitContractBoundary } from "./MacroToolkitPrimitives";

export function GovernanceAuditMap({
  items,
  selectedKey,
  onSelect,
}: {
  items: MacroToolkitGovernanceFocusItem[];
  selectedKey: MacroToolkitGovernanceFocusKey;
  onSelect: (key: MacroToolkitGovernanceFocusKey) => void;
}) {
  const selectedItem = items.find((item) => item.key === selectedKey) ?? items[0]!;
  return (
    <div className="macro-toolkit-governance-audit">
      <div
        className={`macro-toolkit-governance-audit__focus macro-toolkit-governance-audit__focus--${selectedItem.tone}`}
        data-testid="macro-toolkit-governance-focus"
        aria-live="polite"
      >
        <span>审计焦点</span>
        <strong>{selectedItem.focusTitle}</strong>
        <small>{selectedItem.detail}</small>
      </div>
      <div className="macro-toolkit-governance-gate__metrics">
        {items.map((item) => (
          <a
            href={item.href}
            key={item.key}
            className={`macro-toolkit-governance-link macro-toolkit-governance-link--${item.tone}`}
            aria-current={item.key === selectedKey ? "true" : undefined}
            onClick={() => onSelect(item.key)}
            title={item.detail}
          >
            <span>
              <MacroStatusIcon tone={item.tone}>{item.icon}</MacroStatusIcon>
              {item.label}
            </span>
            <Tag color={governanceStatusColor(item.status)}>{governanceStatusLabel(item.status)}</Tag>
          </a>
        ))}
      </div>
    </div>
  );
}

function governanceStatusColor(status: string) {
  if (status === "available") return "green";
  if (status === "failed") return "red";
  if (status === "data-pending" || status === "core-not-full") return "gold";
  return "default";
}

function governanceStatusLabel(status: string) {
  const labels: Record<string, string> = {
    available: "已就绪",
    failed: "失败",
    "data-pending": "数据待处理",
    "core-not-full": "待完整分析",
    "non-formal": "非正式",
  };
  return labels[status] ?? status;
}

export function ActionReceiptPanel({ receipt }: { receipt: MacroToolkitActionReceipt }) {
  return (
    <div
      className={`macro-toolkit-action-receipt macro-toolkit-action-receipt--${receipt.status}`}
      data-testid="macro-toolkit-action-receipt"
      aria-label="宏观工具操作回执"
      aria-live="polite"
    >
      <div className="macro-toolkit-action-receipt__head">
        <span>最近回执</span>
        <strong>{receipt.action}</strong>
      </div>
      <div className="macro-toolkit-action-receipt__grid">
        <ReceiptField label="状态" value={actionReceiptStatusLabel(receipt.status)} />
        <ReceiptField label="时间" value={receipt.time} />
        <ReceiptField label="影响对象" value={receipt.target} />
        <ReceiptField label="输出产物" value={receipt.artifact} />
        <ReceiptField label="下一步" value={receipt.nextStep} />
      </div>
    </div>
  );
}

export function ActionReceiptQueue({
  receipts,
  selectedEvidenceHref,
  onSelectEvidence,
}: {
  receipts: MacroToolkitActionReceipt[];
  selectedEvidenceHref: string | null;
  onSelectEvidence: (href: string) => void;
}) {
  return (
    <div
      className="macro-toolkit-action-queue"
      data-testid="macro-toolkit-action-queue"
      aria-label="宏观工具操作审计队列"
    >
      <div className="macro-toolkit-action-queue__head">
        <span>操作审计队列</span>
        <strong>{receipts.length} 条</strong>
      </div>
      {receipts.length ? (
        <>
          <div className="macro-toolkit-action-queue__columns" aria-hidden="true">
            <span>动作</span>
            <span>决策影响</span>
            <span>复核角色</span>
            <span>证据入口</span>
          </div>
          <ul className="macro-toolkit-action-queue__list">
            {receipts.map((receipt) => (
              <li
                key={receipt.id}
                className={`macro-toolkit-action-queue__item macro-toolkit-action-queue__item--${receipt.status}`}
              >
                <div>
                  <strong>{receipt.action}</strong>
                  <span>{actionReceiptStatusLabel(receipt.status)}</span>
                </div>
                <small title={`${receipt.decisionImpact} · ${receipt.target}`}>
                  {compactText(`${receipt.decisionImpact} · ${receipt.target}`, 32)}
                </small>
                <small title={receipt.reviewOwner}>{compactText(receipt.reviewOwner, 24)}</small>
                <a
                  href={receipt.evidenceHref}
                  title={`${receipt.evidenceEntry} · ${receipt.nextStep}`}
                  aria-current={receipt.evidenceHref === selectedEvidenceHref ? "true" : undefined}
                  onClick={() => onSelectEvidence(receipt.evidenceHref)}
                >
                  {compactText(`${receipt.evidenceEntry} · ${receipt.nextStep}`, 34)}
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="macro-toolkit-action-queue__empty">暂无操作记录</div>
      )}
    </div>
  );
}

export function ReceiptField({ label, value }: { label: string; value: string }) {
  return (
    <div className="macro-toolkit-action-receipt__field">
      <span>{label}</span>
      <strong title={value}>{compactText(value, 40)}</strong>
    </div>
  );
}

function actionReceiptStatusLabel(status: MacroToolkitActionReceiptStatus) {
  const labels: Record<MacroToolkitActionReceiptStatus, string> = {
    idle: "等待执行",
    running: "进行中",
    completed: "已完成",
    warning: "需复核",
    failed: "失败",
  };
  return labels[status];
}

export function MacroToolkitInvestmentBriefPanel({
  committeeFinalSignoffStatus,
  committeeFinalGateOutcome,
  committeeFinalSignoffOwner,
  committeeDecisionBlocker,
  committeeFinalPackValue,
  committeeFinalSignoffValue,
  committeeFinalResidualRiskValue,
  committeeFinalReceiptReviewValue,
  committeeChecklistItems,
  committeePackItemByKey,
  selectedEvidenceHref,
  focusDataHealthRepair,
  setSelectedEvidenceHref,
  setSelectedGovernanceFocus,
  committeeDecisionActionControl,
}: {
  analysis: MacroToolkitAnalysisPayload | undefined;
  committeeFinalSignoffStatus: string;
  committeeFinalGateOutcome: string;
  committeeFinalSignoffOwner: string;
  committeeDecisionBlocker: string;
  committeeFinalPackValue: string;
  committeeFinalSignoffValue: string;
  committeeFinalResidualRiskValue: string;
  committeeFinalReceiptReviewValue: string;
  committeeChecklistItems: MacroToolkitCommitteeChecklistItem[];
  committeePackItemByKey: Map<string, MacroToolkitCommitteePackItem>;
  selectedEvidenceHref: string | null;
  focusDataHealthRepair: () => void;
  setSelectedEvidenceHref: (href: string) => void;
  setSelectedGovernanceFocus: (key: MacroToolkitGovernanceFocusKey) => void;
  committeeDecisionActionControl: ReactNode;
}) {
  return (
    <div
      className="macro-toolkit-investment-brief"
      data-testid="macro-toolkit-investment-brief"
      aria-label="宏观工具投委会摘要"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>投委会门禁</span>
        <strong>{committeeFinalGateOutcome}</strong>
      </div>
      <section className="macro-toolkit-submission-cockpit" aria-label="投委会提交门禁">
        <div className="macro-toolkit-submission-cockpit__metrics">
          <div className="macro-toolkit-submission-cockpit__verdict">
            <span>提交判断</span>
            <strong>{committeeFinalSignoffStatus}</strong>
          </div>
          <div className="macro-toolkit-submission-cockpit__owner">
            <span>责任人</span>
            <strong>{committeeFinalSignoffOwner}</strong>
            <small>{committeeDecisionBlocker}</small>
          </div>
          <div>
            <span>提交包</span>
            <strong>{committeeFinalPackValue}</strong>
          </div>
          <div>
            <span>签核</span>
            <strong>{committeeFinalSignoffValue}</strong>
          </div>
          <div>
            <span>剩余风险</span>
            <strong>{committeeFinalResidualRiskValue}</strong>
          </div>
          <div>
            <span>待复核回执</span>
            <strong>{committeeFinalReceiptReviewValue}</strong>
          </div>
        </div>
        <div className="macro-toolkit-submission-cockpit__lanes" aria-label="投委会提交链路总览">
          {committeeChecklistItems.map((item) => {
            const href = committeePackItemByKey.get(item.key)?.receipt?.evidenceHref ?? item.href;
            const actionLabel = item.key === "data-health" && item.status === "block" ? "处理数据缺口" : item.action;
            return (
              <a
                key={item.key}
                className={`macro-toolkit-submission-cockpit__lane macro-toolkit-submission-cockpit__lane--${item.status}`}
                href={href}
                aria-current={selectedEvidenceHref === href ? "true" : undefined}
                onClick={() => {
                  if (href === "#macro-toolkit-data-health-detail") {
                    focusDataHealthRepair();
                    return;
                  }
                  setSelectedEvidenceHref(href);
                  setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
                }}
              >
                <span>{item.condition}</span>
                <strong>{item.statusLabel}</strong>
                <small>{item.owner}</small>
                <em>{actionLabel}</em>
              </a>
            );
          })}
        </div>
        <div className="macro-toolkit-submission-cockpit__action">
          {committeeDecisionActionControl}
        </div>
      </section>
    </div>
  );
}

export function MacroToolkitGovernanceGatePanel({
  analysisMeta,
  governanceFocusItems,
  selectedGovernanceFocusItem,
  setSelectedGovernanceFocus,
}: {
  analysisMeta: ResultMeta | undefined;
  governanceFocusItems: MacroToolkitGovernanceFocusItem[];
  selectedGovernanceFocusItem: MacroToolkitGovernanceFocusItem;
  setSelectedGovernanceFocus: (key: MacroToolkitGovernanceFocusKey) => void;
}) {
  return (
    <div
      className="macro-toolkit-governance-gate"
      data-testid="macro-toolkit-governance-gate"
      aria-label="宏观工具口径与数据闸门"
    >
      <div className="macro-toolkit-panel-kicker">
        <span>治理闸门</span>
        <strong>口径与数据闸门</strong>
      </div>
      <MacroToolkitContractBoundary
        formalUseAllowed={analysisMeta?.formal_use_allowed}
        resultKind={analysisMeta?.result_kind}
        ruleVersion={analysisMeta?.rule_version}
      />
      <GovernanceAuditMap
        items={governanceFocusItems}
        selectedKey={selectedGovernanceFocusItem.key}
        onSelect={setSelectedGovernanceFocus}
      />
    </div>
  );
}

export function MacroToolkitCommitteeDecisionAction({
  variant,
  hasDataHealthRepairReceiptPending,
  completedDataHealthReceipt,
  focusDataHealthRepair,
  confirmActionReceipt,
  hasCommitteeOpenSubmissionLane,
  committeeLeadChecklistItem,
  committeeLeadReceipt,
  setSelectedEvidenceHref,
  setSelectedGovernanceFocus,
  setSelectedExecutionHref,
  refreshChoiceStock,
  isRefreshingChoiceStock,
  runSelectedScript,
  isRunning,
  selectedScript,
  committeeDecisionAction,
  committeeDecisionActionCurrent,
  committeeDecisionHref,
  handleCommitteeDecisionActionClick,
}: {
  variant: "tile";
  hasDataHealthRepairReceiptPending: boolean;
  completedDataHealthReceipt: MacroToolkitActionReceipt | null;
  focusDataHealthRepair: () => void;
  confirmActionReceipt: (receiptId: string) => void;
  hasCommitteeOpenSubmissionLane: boolean;
  committeeLeadChecklistItem: MacroToolkitCommitteeChecklistItem | null;
  committeeLeadReceipt: MacroToolkitActionReceipt | null;
  setSelectedEvidenceHref: (href: string) => void;
  setSelectedGovernanceFocus: (key: MacroToolkitGovernanceFocusKey) => void;
  setSelectedExecutionHref: (href: string) => void;
  refreshChoiceStock: () => Promise<void>;
  isRefreshingChoiceStock: boolean;
  runSelectedScript: () => Promise<void>;
  isRunning: boolean;
  selectedScript: MacroToolkitScriptRecord | null;
  committeeDecisionAction: string;
  committeeDecisionActionCurrent: boolean;
  committeeDecisionHref: string;
  handleCommitteeDecisionActionClick: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const committeeDecisionButtonAction = hasDataHealthRepairReceiptPending && completedDataHealthReceipt
    ? {
        label: "复核数据健康回执",
        onClick: () => {
          focusDataHealthRepair();
          confirmActionReceipt(completedDataHealthReceipt.id);
        },
        busy: false,
        status: "确认签核",
      }
    : hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem?.key === "strategy-supply"
      ? committeeLeadReceipt
        ? {
            label: "复核策略供数回执",
            onClick: () => {
              confirmActionReceipt(committeeLeadReceipt.id);
              setSelectedEvidenceHref("#macro-toolkit-strategy-detail");
              setSelectedGovernanceFocus("execution");
            },
            busy: false,
            status: "确认签核",
          }
        : {
            label: "执行策略供数刷新",
            onClick: () => {
              setSelectedExecutionHref("#macro-toolkit-operations-actions");
              setSelectedGovernanceFocus("execution");
              void refreshChoiceStock();
            },
            busy: isRefreshingChoiceStock,
            status: "生成回执",
          }
      : hasCommitteeOpenSubmissionLane && committeeLeadChecklistItem?.key === "tool-execution"
        ? committeeLeadReceipt
          ? {
              label: "复核工具执行回执",
              onClick: () => {
                confirmActionReceipt(committeeLeadReceipt.id);
                setSelectedEvidenceHref(committeeLeadReceipt.evidenceHref);
                setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(committeeLeadReceipt.evidenceHref));
              },
              busy: false,
              status: "确认签核",
            }
          : {
              label: "复核工具执行结果",
              onClick: () => {
                setSelectedExecutionHref("#macro-toolkit-operations-actions");
                setSelectedGovernanceFocus("execution");
                void runSelectedScript();
              },
              busy: isRunning || !selectedScript,
              status: selectedScript ? "生成回执" : "等待脚本",
          }
      : null;
    const actionInner = committeeDecisionButtonAction?.label ?? committeeDecisionAction;

    if (committeeDecisionButtonAction) {
      return (
        <button
          type="button"
          className={`macro-toolkit-committee-action macro-toolkit-committee-action--${variant}`}
          disabled={committeeDecisionButtonAction.busy}
          aria-current={committeeDecisionActionCurrent ? "true" : undefined}
          aria-label={committeeDecisionButtonAction.label}
          onClick={committeeDecisionButtonAction.onClick}
        >
          {actionInner}
          <small>{committeeDecisionButtonAction.status}</small>
        </button>
      );
    }

    return (
      <a
        className={`macro-toolkit-committee-action macro-toolkit-committee-action--${variant}`}
        href={committeeDecisionHref}
        aria-current={committeeDecisionActionCurrent ? "true" : undefined}
        onClick={handleCommitteeDecisionActionClick}
      >
        {actionInner}
      </a>
    );
}

export function MacroToolkitDeepEvidenceRailCard({
  deepEvidenceQueueItems,
}: {
  deepEvidenceQueueItems: MacroToolkitDeepEvidenceQueueItem[];
}) {
  return (
    <div className="macro-toolkit-committee-workspace__evidence-links">
      <div className="macro-toolkit-committee-workspace__evidence-head">
        <span>深度证据入口</span>
        <strong>{deepEvidenceQueueItems.length} 个追踪面</strong>
      </div>
      <div className="macro-toolkit-committee-workspace__evidence-grid" aria-label="深度证据入口">
        {deepEvidenceQueueItems.map((item) => (
          <a key={item.key} href={item.href}>
            <span>{item.label}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

export function MacroToolkitOperationsBand({
  governanceGatePanel,
  deepEvidenceQueueItems,
  operationsConsolePanel,
}: {
  governanceGatePanel?: ReactNode;
  deepEvidenceQueueItems?: MacroToolkitDeepEvidenceQueueItem[];
  operationsConsolePanel: ReactNode;
}) {
  // 过渡兜底：E6 在主文件挂载 MacroToolkitDeepEvidenceRailCard 并停传该 prop 前，入口仍由本带渲染。
  const deepEvidenceCard = deepEvidenceQueueItems?.length ? (
    <MacroToolkitDeepEvidenceRailCard deepEvidenceQueueItems={deepEvidenceQueueItems} />
  ) : null;
  const hasRail = Boolean(governanceGatePanel) || Boolean(deepEvidenceCard);
  return (
    <section className="macro-toolkit-operations-band" aria-label="宏观工具操作与治理区">
      <div
        className={`macro-toolkit-committee-workspace${
          hasRail ? "" : " macro-toolkit-committee-workspace--console-only"
        }`}
      >
        {hasRail ? (
          <aside className="macro-toolkit-committee-workspace__rail" aria-label="治理侧栏">
            {governanceGatePanel}
            {deepEvidenceCard}
          </aside>
        ) : null}
        <div className="macro-toolkit-committee-workspace__main" aria-label="操作台">
          {operationsConsolePanel}
        </div>
      </div>
    </section>
  );
}
