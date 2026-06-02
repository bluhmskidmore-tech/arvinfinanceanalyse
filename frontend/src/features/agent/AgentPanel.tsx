import { FormEvent, useMemo, useState } from "react";

import type { AgentPageContext } from "../../api/contracts";
import { useApiClient } from "../../api/client";
import { AgentDisabledError } from "../../api/agentClient";

import "./AgentPanel.css";

type AgentCard = {
  type: string;
  title: string;
  value?: string | null;
  data?: Record<string, unknown> | Array<Record<string, unknown>> | null;
};

export type AgentPanelProps = {
  pageId: string;
  reportDate?: string | null;
  currentFilters?: Record<string, unknown>;
  defaultFilters?: Record<string, unknown>;
  selectedRows?: Array<Record<string, unknown>>;
  contextNote?: string | null;
  defaultQuestion?: string;
};

export function AgentPanel({
  pageId,
  reportDate = null,
  currentFilters = {},
  defaultFilters = {},
  selectedRows,
  contextNote = null,
  defaultQuestion = "",
}: AgentPanelProps) {
  const client = useApiClient();
  const [question, setQuestion] = useState(defaultQuestion);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [qualityFlag, setQualityFlag] = useState<string | null>(null);
  const [tablesUsed, setTablesUsed] = useState<string[]>([]);
  const [cards, setCards] = useState<AgentCard[]>([]);
  const [chips, setChips] = useState<Array<{ type: string; label: string }>>([]);
  const [disabledBanner, setDisabledBanner] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const pageContextPayload = useMemo<AgentPageContext>(
    () => ({
      page_id: pageId,
      current_filters:
        reportDate != null ? { ...currentFilters, report_date: reportDate } : { ...currentFilters },
      selected_rows: selectedRows ?? [],
      context_note: contextNote ?? null,
    }),
    [pageId, reportDate, currentFilters, selectedRows, contextNote],
  );

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }
    setLoading(true);
    setDisabledBanner(null);
    setErrorMessage(null);
    setAnswer(null);
    setQualityFlag(null);
    setTablesUsed([]);
    setCards([]);
    setChips([]);
    try {
      const envelope = await client.queryAgent({
        question: trimmed,
        basis: "formal",
        filters: defaultFilters,
        page_context: pageContextPayload,
      });
      setAnswer(envelope.answer);
      setQualityFlag(envelope.evidence.quality_flag);
      setTablesUsed(envelope.evidence.tables_used ?? []);
      setCards(envelope.cards ?? []);
      setChips(
        (envelope.suggested_actions ?? []).map((action) => ({
          type: action.type,
          label: action.label,
        })),
      );
    } catch (err) {
      if (err instanceof AgentDisabledError) {
        setDisabledBanner(err.message);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("请求失败");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="dashboard-home-panel agent-panel" data-testid="agent-panel">
      <h2 className="agent-panel__title">只读 Agent</h2>
      <p className="agent-panel__muted">
        基于当前页面上下文提问；不会触发写入或刷新任务。
      </p>
      <form className="agent-panel__form" onSubmit={(e) => void handleSubmit(e)}>
        <textarea
          className="agent-panel__input"
          aria-label="Agent 问题"
          data-testid="agent-panel-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="输入业务问题…"
        />
        <div className="agent-panel__actions">
          <button
            type="submit"
            className="agent-panel__submit"
            data-testid="agent-panel-submit"
            disabled={loading || !question.trim()}
            aria-busy={loading}
          >
            {loading ? "处理中…" : "提交"}
          </button>
          {loading ? (
            <span className="agent-panel__muted" data-testid="agent-panel-loading">
              载入中
            </span>
          ) : null}
        </div>
      </form>

      {disabledBanner ? (
        <div className="agent-panel__banner" role="status" data-testid="agent-panel-disabled">
          {disabledBanner}
        </div>
      ) : null}

      {errorMessage ? (
        <div className="agent-panel__error" role="alert" data-testid="agent-panel-error">
          {errorMessage}
        </div>
      ) : null}

      {answer ? (
        <div className="agent-panel__answer" data-testid="agent-panel-answer">
          {answer}
        </div>
      ) : null}

      {cards.length > 0 ? (
        <div className="agent-panel__cards" data-testid="agent-panel-cards">
          {cards.map((card) => (
            <article key={`${card.type}:${card.title}`} className="agent-panel__card">
              <strong>{card.title}</strong>
              {card.value ? <p>{card.value}</p> : null}
              {Array.isArray(card.data) ? (
                <ul>
                  {card.data.map((row, index) => (
                    <li key={`${card.title}:${index}`}>{formatCardData(row)}</li>
                  ))}
                </ul>
              ) : card.data ? (
                <p>{formatCardData(card.data)}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {qualityFlag !== null ? (
        <div className="agent-panel__evidence" data-testid="agent-panel-evidence">
          <div data-testid="agent-panel-quality-flag">质量标记：{qualityFlag}</div>
          <div data-testid="agent-panel-tables-used">
            使用表：{tablesUsed.length ? tablesUsed.join(", ") : "—"}
          </div>
        </div>
      ) : null}

      {qualityFlag !== null && qualityFlag !== "ok" ? (
        <div data-testid="agent-panel-refresh-hint">
          数据不足或可能陈旧，请先使用页面刷新或 Choice/TuShare 手动刷新后再分析。
        </div>
      ) : null}

      {chips.length > 0 ? (
        <div className="agent-panel__chips" data-testid="agent-panel-chips">
          {chips.map((chip) => (
            <span key={`${chip.type}:${chip.label}`} className="agent-panel__chip">
              {chip.label}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function formatCardData(row: Record<string, unknown>) {
  if ("item" in row) {
    return String(row.item ?? "");
  }
  return Object.entries(row)
    .map(([key, value]) => `${key}: ${String(value ?? "")}`)
    .join(" / ");
}
