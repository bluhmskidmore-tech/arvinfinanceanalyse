import { useEffect, useState } from "react";

import type { WorkbenchDataDigest, WorkbenchFact } from "../lib/stockAnalysisPageModel";

function StockWorkbenchFactCard({
  fact,
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  fact: WorkbenchFact;
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  const isInteractive = typeof onFactSelect === "function";
  const isActive = isInteractive && activeFactId === fact.id;

  const toneColors: Record<string, string> = {
    positive: "border-l-success",
    negative: "border-l-danger",
    warning: "border-l-warning",
    watch: "border-l-secondary",
    ok: "border-l-success",
    neutral: "border-l-default",
  };

  const toneClass = toneColors[fact.tone || "neutral"] || toneColors.neutral;
  const activeClass = isActive ? "ring-1 ring-primary" : "";
  const interactiveClass = isInteractive ? "cursor-pointer transition-colors" : "";

  const content = (
    <div className="flex flex-col overflow-hidden">
      <span className="truncate">{fact.label}</span>
      <strong className="truncate">{fact.value}</strong>
      {fact.subValue ? <small className="truncate">{fact.subValue}</small> : null}
      <em className="hidden" title={fact.sourcePath}>字段来源已记录</em>
    </div>
  );

  if (isInteractive) {
    return (
      <button
        type="button"
        className={`w-full border-l-2 text-left ${toneClass} ${activeClass} ${interactiveClass}`}
        data-testid={`stock-analysis-workbench-fact-${fact.id}`}
        data-tone={fact.tone}
        data-primary={fact.isPrimary ? "true" : "false"}
        data-active={isActive ? "true" : "false"}
        aria-current={isActive ? "true" : undefined}
        aria-controls={factControlsId}
        onClick={() => onFactSelect(fact)}
      >
        {content}
      </button>
    );
  }

  return (
    <article
      className={`w-full border-l-2 ${toneClass}`}
      data-testid={`stock-analysis-workbench-fact-${fact.id}`}
      data-tone={fact.tone}
      data-primary={fact.isPrimary ? "true" : "false"}
      data-active="false"
    >
      {content}
    </article>
  );
}

function StockWorkbenchFactGrid({
  title,
  eyebrow,
  facts,
  layout = "default",
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  title: string;
  eyebrow?: string;
  facts: WorkbenchFact[];
  layout?: "primary" | "secondary" | "slow" | "default";
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  if (facts.length === 0) return null;

  return (
    <section className="flex flex-col gap-2" data-layout={layout}>
      <div className="stock-analysis-page__evidence-section-head">
        <h3>{title}</h3>
        {eyebrow ? <p>{eyebrow}</p> : null}
      </div>
      <div className="stock-analysis-page__evidence-source-grid" data-layout={layout}>
        {facts.map((fact) => (
          <StockWorkbenchFactCard
            key={fact.id}
            fact={fact}
            onFactSelect={onFactSelect}
            activeFactId={activeFactId}
            factControlsId={factControlsId}
          />
        ))}
      </div>
    </section>
  );
}

/** Evidence-layer fact digest: primary facts always visible, audit facts behind a toggle. */
export function StockAnalysisWorkbenchDigest({
  digest,
  onFactSelect,
  activeFactId,
  factControlsId,
}: {
  digest: WorkbenchDataDigest;
  onFactSelect?: (fact: WorkbenchFact) => void;
  activeFactId?: string | null;
  factControlsId?: string;
}) {
  const auditFacts = [...digest.candidateFacts, ...digest.evidenceFacts];
  const hasAuditDetails = auditFacts.length > 0 || digest.slowFacts.length > 0;
  const hasSelectedAuditFact =
    activeFactId != null &&
    [...auditFacts, ...digest.slowFacts].some((fact) => fact.id === activeFactId);
  const [auditOpen, setAuditOpen] = useState(hasSelectedAuditFact);

  useEffect(() => {
    if (hasSelectedAuditFact) {
      setAuditOpen(true);
    }
  }, [hasSelectedAuditFact]);

  return (
    <section
      className="stock-analysis-page__fs-card"
      data-testid="stock-analysis-workbench-digest"
      aria-label="供数摘要"
    >
      <StockWorkbenchFactGrid
        title="核心口径"
        eyebrow="核心事实"
        facts={digest.primaryFacts}
        layout="primary"
        onFactSelect={onFactSelect}
        activeFactId={activeFactId}
        factControlsId={factControlsId}
      />
      {hasAuditDetails ? (
        <section className="flex flex-col gap-2" data-layout="audit">
          <button
            type="button"
            className="stock-analysis-page__fs-rail-card items-start text-left transition-colors"
            aria-expanded={auditOpen}
            aria-controls="stock-analysis-workbench-audit-details"
            onClick={() => setAuditOpen((current) => !current)}
          >
            <span className="stock-analysis-page__dh-section-eyebrow">完整证据账本 / 审计明细</span>
            <strong className="text-sm font-semibold text-foreground">{auditOpen ? "收起" : "展开"}</strong>
            <small className="stock-analysis-page__dh-section-desc">展开查看候选、接口与慢链路补证。</small>
          </button>
          {auditOpen ? (
            <div
              id="stock-analysis-workbench-audit-details"
              data-testid="stock-analysis-workbench-audit-details"
              className="flex flex-col gap-3 pt-1"
            >
              <StockWorkbenchFactGrid
                title="候选与证据"
                eyebrow="候选与接口证据"
                facts={auditFacts}
                layout="secondary"
                onFactSelect={onFactSelect}
                activeFactId={activeFactId}
                factControlsId={factControlsId}
              />
              <StockWorkbenchFactGrid
                title="慢接口补证"
                eyebrow="非阻塞补证"
                facts={digest.slowFacts}
                layout="slow"
                onFactSelect={onFactSelect}
                activeFactId={activeFactId}
                factControlsId={factControlsId}
              />
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
