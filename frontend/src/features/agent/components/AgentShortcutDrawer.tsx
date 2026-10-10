import {
  FINANCIAL_WORKFLOWS,
  RESEARCH_SHORTCUTS,
} from "../lib/agentWorkbenchModel";
import type {
  FinancialWorkflowShortcut,
  ResearchShortcut,
} from "../lib/agentWorkbenchModel";

type AgentShortcutDrawerProps = {
  loading: boolean;
  onExecuteWorkflow: (workflow: FinancialWorkflowShortcut) => void;
  onExecuteResearchShortcut: (shortcut: ResearchShortcut) => void;
};

function FinancialWorkflowPanel({
  loading,
  onExecuteWorkflow,
}: Pick<AgentShortcutDrawerProps, "loading" | "onExecuteWorkflow">) {
  return (
    <section className="agent-financial-workflows" aria-label="金融工作流">
      <div className="agent-financial-workflows__header">
        <div>
          <div className="agent-financial-workflows__eyebrow">金融工作流</div>
          <h2>本地分析模板</h2>
        </div>
        <span>不接外部数据</span>
      </div>
      <div className="agent-financial-workflows__grid">
        {FINANCIAL_WORKFLOWS.map((workflow) => (
          <button
            key={workflow.id}
            type="button"
            className="agent-financial-workflows__button"
            onClick={() => onExecuteWorkflow(workflow)}
            disabled={loading}
          >
            <span className="agent-financial-workflows__title">{workflow.title}</span>
            <span className="agent-financial-workflows__command">{workflow.slashCommand}</span>
            <span className="agent-financial-workflows__description">{workflow.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function ResearchShortcutPanel({
  loading,
  onExecuteResearchShortcut,
}: Pick<AgentShortcutDrawerProps, "loading" | "onExecuteResearchShortcut">) {
  return (
    <section className="agent-financial-workflows" aria-label="研究快捷入口">
      <div className="agent-financial-workflows__header">
        <div>
          <div className="agent-financial-workflows__eyebrow">数据研究入口</div>
          <h2>已刷新数据复核</h2>
        </div>
        <span>先刷新数据</span>
      </div>
      <div className="agent-financial-workflows__grid">
        {RESEARCH_SHORTCUTS.map((shortcut) => (
          <button
            key={shortcut.id}
            type="button"
            className="agent-financial-workflows__button"
            onClick={() => onExecuteResearchShortcut(shortcut)}
            disabled={loading}
          >
            <span className="agent-financial-workflows__title">{shortcut.title}</span>
            <span className="agent-financial-workflows__command">{shortcut.commandLabel ?? shortcut.domain ?? "research"}</span>
            <span className="agent-financial-workflows__description">{shortcut.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function AgentShortcutDrawer({
  loading,
  onExecuteWorkflow,
  onExecuteResearchShortcut,
}: AgentShortcutDrawerProps) {
  const shortcutCount = RESEARCH_SHORTCUTS.length + FINANCIAL_WORKFLOWS.length;
  return (
    <details className="agent-quick-entry">
      <summary>
        <span className="agent-quick-entry__title">常用入口</span>
        <span className="agent-quick-entry__meta">{shortcutCount} 个模板</span>
      </summary>
      <div className="agent-quick-entry__content">
        <FinancialWorkflowPanel loading={loading} onExecuteWorkflow={onExecuteWorkflow} />
        <ResearchShortcutPanel
          loading={loading}
          onExecuteResearchShortcut={onExecuteResearchShortcut}
        />
      </div>
    </details>
  );
}
