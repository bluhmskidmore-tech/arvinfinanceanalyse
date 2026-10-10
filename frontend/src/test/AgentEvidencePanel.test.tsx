import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentEvidencePanel } from "../features/agent/components/AgentEvidencePanel";

describe("AgentEvidencePanel", () => {
  it("labels provider runtime evidence separately from governed MOSS evidence", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["dexter_sidecar"]}
        filtersApplied={{ provider: "dexter" }}
        evidenceStrength="provider_runtime"
        evidenceRows={0}
        qualityFlag="warning"
      />,
    );

    expect(screen.getByText("证据级别")).toBeInTheDocument();
    expect(screen.getByText("外部模型运行证据")).toBeInTheDocument();
  });

  it("labels provider answers backed by governed context as mixed evidence", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["choice_stock_daily_observation"]}
        filtersApplied={{ provider: "dexter" }}
        evidenceStrength="mixed"
        evidenceRows={1}
        qualityFlag="warning"
      />,
    );

    expect(screen.getByText("外部模型 + MOSS 上下文")).toBeInTheDocument();
  });

  it("shows governed metric identity, actual date, and formal-use state", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["fact_formal_pnl_overview"]}
        filtersApplied={{ report_date: "2026-03-31" }}
        evidenceRows={1}
        qualityFlag="warning"
        semanticContext={{
          status: "resolved",
          result_check: "matched",
          references: [
            {
              entity_id: "MTR-PNL-005",
              name: "正式总损益",
              status: "approved",
              business_definition: "按正式损益口径确认的总损益。",
              unit: "yuan",
              basis: "formal",
              time_semantics: "单一报告日",
              authority: ["docs/metric_dictionary.md", "docs/calc_rules.md"],
            },
          ],
          ontology_revision: "ontology-sha256-demo",
          binding_revision: "pnl-binding-v1",
          upstream_result_kind: "pnl.overview",
          upstream_trace_id: "trace-upstream-001",
        }}
        resultMeta={{
          requested_report_date: "2026-04-30",
          resolved_report_date: "2026-03-31",
          formal_use_allowed: false,
        }}
      />,
    );

    expect(screen.getByText("指标口径")).toBeInTheDocument();
    expect(screen.getAllByText("正式总损益")).toHaveLength(2);
    expect(screen.getByText("元")).toBeInTheDocument();
    expect(screen.getByText("2026-03-31")).toBeInTheDocument();
    expect(screen.getByText("不可正式使用")).toBeInTheDocument();
    expect(screen.queryByText("2026-04-30")).not.toBeInTheDocument();

    const details = screen.getByTestId("agent-evidence-semantic-context");
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("MTR-PNL-005");
    expect(details).toHaveTextContent("已批准");
    expect(details).toHaveTextContent("yuan");
    expect(details).toHaveTextContent("按正式损益口径确认的总损益。");
    expect(details).toHaveTextContent("docs/metric_dictionary.md、docs/calc_rules.md");
    expect(details).toHaveTextContent("ontology-sha256-demo");
    expect(details).toHaveTextContent("pnl-binding-v1");
    expect(details).toHaveTextContent("pnl.overview");
    expect(details).toHaveTextContent("trace-upstream-001");
  });

  it("falls back to the as-of date and blocks formal use when result checking is blocked", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={[]}
        filtersApplied={{}}
        evidenceRows={0}
        qualityFlag="warning"
        semanticContext={{
          status: "clarification_required",
          result_check: "blocked",
          references: [],
          reason_code: "ambiguous_metric",
        }}
        resultMeta={{ as_of_date: "2026-03-30", formal_use_allowed: true }}
      />,
    );

    expect(screen.getByText("2026-03-30")).toBeInTheDocument();
    expect(screen.getByText("不可正式使用（结果未通过核对）")).toBeInTheDocument();
    expect(screen.queryByText("允许正式使用")).not.toBeInTheDocument();
    const details = screen.getByTestId("agent-evidence-semantic-context");
    expect(details).toHaveTextContent("需要澄清");
    expect(details).toHaveTextContent("结果未通过核对");
    expect(details).toHaveTextContent("ambiguous_metric");
  });

  it("shows the fallback data date before resolved and as-of dates", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["fact_formal_pnl_overview"]}
        filtersApplied={{ report_date: "2026-04-30" }}
        evidenceRows={1}
        qualityFlag="warning"
        semanticContext={{
          status: "resolved",
          result_check: "blocked",
          references: [],
          reason_code: "upstream_fallback_not_allowed",
        }}
        resultMeta={{
          fallback_date: "2026-03-31",
          resolved_report_date: "2026-04-30",
          as_of_date: "2026-04-30",
          fallback_mode: "latest_snapshot",
          formal_use_allowed: true,
        }}
      />,
    );

    expect(screen.getByText("2026-03-31")).toBeInTheDocument();
    expect(screen.queryByText("2026-04-30")).not.toBeInTheDocument();
    expect(screen.getByText("不可正式使用（结果未通过核对）")).toBeInTheDocument();
    expect(screen.queryByText("允许正式使用")).not.toBeInTheDocument();
  });

  it("does not present unavailable semantic context as formally usable", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={[]}
        filtersApplied={{}}
        evidenceRows={0}
        qualityFlag="warning"
        semanticContext={{
          status: "unavailable",
          result_check: "matched",
          references: [],
        }}
        resultMeta={{ formal_use_allowed: true }}
      />,
    );

    expect(screen.getByText("不可正式使用（语义信息不可用）")).toBeInTheDocument();
    expect(screen.queryByText("允许正式使用")).not.toBeInTheDocument();
  });

  it("allows formal-use wording only for a resolved and matched result", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={[]}
        filtersApplied={{}}
        evidenceRows={0}
        qualityFlag="ok"
        semanticContext={{
          status: "resolved",
          result_check: "matched",
          references: [],
        }}
        resultMeta={{ formal_use_allowed: true }}
      />,
    );

    expect(screen.getByText("允许正式使用")).toBeInTheDocument();
  });

  it("lists read-only SQL disclosures in a collapsed section when provided", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["fact_formal_zqtz_balance_daily"]}
        filtersApplied={{ report_date: "2026-03-31" }}
        sqlExecuted={[
          "SELECT report_date, market_value FROM fact_formal_zqtz_balance_daily WHERE report_date = '2026-03-31'",
          "SELECT count(*) FROM fact_formal_tyw_balance_daily",
        ]}
        evidenceRows={3}
        qualityFlag="ok"
      />,
    );

    const disclosure = screen.getByTestId("agent-evidence-sql");
    expect(disclosure).not.toHaveAttribute("open");
    expect(disclosure).toHaveTextContent("查看只读 SQL 披露 · 2 条");
    expect(disclosure).toHaveTextContent(
      "SELECT report_date, market_value FROM fact_formal_zqtz_balance_daily WHERE report_date = '2026-03-31'",
    );
    expect(disclosure).toHaveTextContent("SELECT count(*) FROM fact_formal_tyw_balance_daily");
    expect(disclosure.querySelector("textarea, input, button")).toBeNull();
  });

  it("keeps the SQL disclosure hidden for an empty sql_executed array", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={["fact_formal_zqtz_balance_daily"]}
        filtersApplied={{}}
        sqlExecuted={[]}
        evidenceRows={1}
        qualityFlag="ok"
      />,
    );

    expect(screen.queryByTestId("agent-evidence-sql")).not.toBeInTheDocument();
    expect(screen.queryByText(/查看只读 SQL 披露/)).not.toBeInTheDocument();
  });

  it("keeps the SQL disclosure hidden when the field is absent", () => {
    render(
      <AgentEvidencePanel
        tablesUsed={[]}
        filtersApplied={{}}
        evidenceRows={0}
        qualityFlag="warning"
      />,
    );

    expect(screen.queryByTestId("agent-evidence-sql")).not.toBeInTheDocument();
    expect(screen.queryByText("指标口径")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-evidence-semantic-context")).not.toBeInTheDocument();
  });
});
