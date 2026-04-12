import { useState, type FormEvent } from "react";

import { shellTokens as t } from "../../theme/tokens";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

type AgentResultCard = {
  title: string;
  value: string;
  type: string;
};

type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  evidence_rows: number;
  quality_flag: string;
};

type AgentNextDrill = {
  dimension: string;
  label: string;
};

type AgentQueryResult = {
  answer: string;
  cards: AgentResultCard[];
  evidence: AgentEvidence;
  result_meta: Record<string, unknown>;
  next_drill: AgentNextDrill[];
};

type AgentQueryError =
  | {
      kind: "disabled";
      detail: string;
      phase: string;
    }
  | {
      kind: "request";
      message: string;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentQueryResult(value: unknown): value is AgentQueryResult {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.answer === "string" &&
    Array.isArray(value.cards) &&
    value.cards.every(isAgentResultCard) &&
    isAgentEvidence(value.evidence) &&
    Array.isArray(value.next_drill) &&
    value.next_drill.every(isAgentNextDrill) &&
    isRecord(value.result_meta)
  );
}

function isAgentResultCard(value: unknown): value is AgentResultCard {
  return (
    isRecord(value) &&
    typeof value.title === "string" &&
    typeof value.value === "string" &&
    typeof value.type === "string"
  );
}

function isAgentEvidence(value: unknown): value is AgentEvidence {
  return (
    isRecord(value) &&
    Array.isArray(value.tables_used) &&
    value.tables_used.every((item) => typeof item === "string") &&
    isRecord(value.filters_applied) &&
    typeof value.evidence_rows === "number" &&
    typeof value.quality_flag === "string"
  );
}

function isAgentNextDrill(value: unknown): value is AgentNextDrill {
  return (
    isRecord(value) &&
    typeof value.dimension === "string" &&
    typeof value.label === "string"
  );
}

function isDisabledPayload(value: unknown): value is {
  enabled: false;
  phase: string;
  detail: string;
} {
  return (
    isRecord(value) &&
    value.enabled === false &&
    typeof value.phase === "string" &&
    typeof value.detail === "string"
  );
}

function buildErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Agent 查询失败，请稍后重试。";
}

function hasEvidenceContent(evidence: AgentEvidence) {
  return (
    evidence.tables_used.length > 0 ||
    Object.keys(evidence.filters_applied).length > 0 ||
    evidence.evidence_rows > 0 ||
    evidence.quality_flag.trim().length > 0
  );
}

function hasRenderableResult(result: AgentQueryResult) {
  return (
    result.answer.trim().length > 0 ||
    result.cards.length > 0 ||
    hasEvidenceContent(result.evidence) ||
    result.next_drill.length > 0
  );
}

function buildResultMetaEntries(resultMeta: Record<string, unknown>) {
  const orderedKeys = ["trace_id", "basis", "generated_at"];
  const seen = new Set<string>();
  const entries: Array<[string, unknown]> = [];

  for (const key of orderedKeys) {
    if (key in resultMeta) {
      entries.push([key, resultMeta[key]]);
      seen.add(key);
    }
  }

  for (const [key, value] of Object.entries(resultMeta)) {
    if (seen.has(key)) {
      continue;
    }
    entries.push([key, value]);
  }

  return entries;
}

function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value.trim().length > 0 ? value : "—";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export default function AgentWorkbenchPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [error, setError] = useState<AgentQueryError | null>(null);

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();

    const question = query.trim();
    if (!question) {
      setResult(null);
      setError({
        kind: "request",
        message: "请输入查询问题。",
      });
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          basis: "formal",
          filters: {},
          position_scope: "all",
          currency_basis: "CNY",
          context: {
            user_id: "web-user",
          },
        }),
      });

      const payload = (await response.json()) as unknown;

      if (response.status === 503 && isDisabledPayload(payload)) {
        setError({
          kind: "disabled",
          detail: payload.detail,
          phase: payload.phase,
        });
        return;
      }

      if (!response.ok) {
        throw new Error(`Agent 查询失败（${response.status}）`);
      }

      if (!isAgentQueryResult(payload)) {
        throw new Error("Agent 返回结果格式无效。");
      }

      setResult(payload);
    } catch (requestError) {
      setError({
        kind: "request",
        message: buildErrorMessage(requestError),
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h1
        style={{
          margin: 0,
          fontSize: 32,
          fontWeight: 600,
          letterSpacing: "-0.03em",
          color: t.colorTextPrimary,
        }}
      >
        Agent 工作台
      </h1>
      <p
        style={{
          marginTop: 10,
          marginBottom: 0,
          maxWidth: 860,
          color: t.colorTextSecondary,
          fontSize: 15,
          lineHeight: 1.75,
        }}
      >
        输入自然语言问题，Agent 路由到已有分析服务返回结构化结果。
      </p>

      <form
        onSubmit={(event) => void handleSubmit(event)}
        style={{
          display: "flex",
          gap: 12,
          marginTop: 20,
          marginBottom: 24,
        }}
      >
        <input
          type="text"
          placeholder="例如：组合概览、损益汇总、久期风险、信用集中度、GitNexus 仓库图谱..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          style={{
            flex: 1,
            padding: "12px 16px",
            borderRadius: 14,
            border: `1px solid ${t.colorBorder}`,
            background: t.colorBgCanvas,
            color: t.colorTextPrimary,
            fontSize: 15,
            outline: "none",
            boxSizing: "border-box",
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "12px 24px",
            borderRadius: 14,
            border: "none",
            background: t.colorAccent,
            color: t.colorBgCanvas,
            fontSize: 15,
            fontWeight: 600,
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.72 : 1,
          }}
        >
          {loading ? "查询中..." : "查询"}
        </button>
      </form>

      {error?.kind === "disabled" ? (
        <div
          style={{
            padding: 24,
            borderRadius: 16,
            border: `1px solid ${t.colorBorderWarning}`,
            background: t.colorBgWarningSoft,
            color: t.colorTextWarning,
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          Agent 当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。
        </div>
      ) : null}

      {error?.kind === "request" ? (
        <div
          style={{
            padding: 16,
            borderRadius: 14,
            border: `1px solid ${t.colorDanger}`,
            background: t.colorBgDangerSoft,
            color: t.colorDanger,
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          {error.message}
        </div>
      ) : null}

      {result ? (
        <div
          style={{
            display: "grid",
            gap: 18,
          }}
        >
          {hasRenderableResult(result) ? (
            <>
              {result.answer.trim().length > 0 ? (
                <div
                  style={{
                    padding: 20,
                    borderRadius: 16,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgCanvas,
                    color: t.colorTextPrimary,
                    fontSize: 15,
                    lineHeight: 1.75,
                  }}
                >
                  {result.answer}
                </div>
              ) : null}

              {result.cards.length > 0 ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: 14,
                  }}
                >
                  {result.cards.map((card) => (
                    <PlaceholderCard
                      key={`${card.title}-${card.type}`}
                      title={card.title}
                      value={String(card.value)}
                      detail={card.type}
                    />
                  ))}
                </div>
              ) : null}

              {hasEvidenceContent(result.evidence) ? (
                <div
                  style={{
                    marginTop: 18,
                    padding: 16,
                    borderRadius: 14,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgSurface,
                  }}
                >
                  <div
                    style={{
                      color: t.colorTextMuted,
                      fontSize: 12,
                      marginBottom: 8,
                    }}
                  >
                    证据链
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: t.colorTextSecondary,
                      lineHeight: 1.7,
                    }}
                  >
                    tables: {result.evidence.tables_used.join(", ")}
                    <br />
                    filters: {JSON.stringify(result.evidence.filters_applied)}
                    <br />
                    rows: {result.evidence.evidence_rows}
                    <br />
                    quality: {result.evidence.quality_flag}
                  </div>
                </div>
              ) : null}

              {result.next_drill.length > 0 ? (
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    marginTop: 12,
                  }}
                >
                  {result.next_drill.map((drill) => (
                    <span
                      key={drill.dimension}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 999,
                        background: t.colorBgMuted,
                        color: t.colorTextSecondary,
                        fontSize: 12,
                        fontWeight: 500,
                      }}
                    >
                      {drill.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <div
              style={{
                padding: 20,
                borderRadius: 16,
                border: `1px solid ${t.colorBorderSoft}`,
                background: t.colorBgCanvas,
                color: t.colorTextSecondary,
                fontSize: 15,
                lineHeight: 1.75,
              }}
            >
              本次查询未返回可展示结果。请调整问题后重试。
            </div>
          )}

          <div
            style={{
              padding: 16,
              borderRadius: 14,
              border: `1px solid ${t.colorBorderSoft}`,
              background: t.colorBgSurface,
            }}
          >
            <div
              style={{
                color: t.colorTextMuted,
                fontSize: 12,
                marginBottom: 8,
              }}
            >
              结果元信息
            </div>
            <div
              style={{
                fontSize: 13,
                color: t.colorTextSecondary,
                lineHeight: 1.7,
              }}
            >
              {buildResultMetaEntries(result.result_meta).map(([key, value]) => (
                <div key={key}>
                  {key}: {formatMetaValue(value)}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
