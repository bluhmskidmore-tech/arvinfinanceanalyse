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
  });
});
