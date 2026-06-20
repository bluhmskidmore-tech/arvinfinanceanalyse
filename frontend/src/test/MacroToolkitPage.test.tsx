import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { ApiClientProvider } from "../api/clientContext";
import type { ResultMeta } from "../api/contracts";
import MacroToolkitPage from "../features/macro-toolkit/pages/MacroToolkitPage";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const MACRO_TOOLKIT_CSS_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.css",
);
const MACRO_TOOLKIT_PAGE_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
);

beforeAll(async () => {
  await preloadWorkbenchRouteModules("macro-toolkit");
}, 20_000);

type MacroToolkitAnalysisEnvelope = Awaited<ReturnType<ApiClient["getMacroToolkitAnalysis"]>>;
type MacroToolkitCapabilityResultFixture =
  MacroToolkitAnalysisEnvelope["result"]["capability_results"][number];
type MacroToolkitModelReadinessFixture = NonNullable<MacroToolkitAnalysisEnvelope["result"]["model_readiness"]>[number];
type MacroToolkitInputEvidenceFixture = NonNullable<
  NonNullable<MacroToolkitCapabilityResultFixture["input_evidence"]>["inputs"]
>[number];

function requireInputEvidenceInputs(
  result: MacroToolkitCapabilityResultFixture,
): MacroToolkitInputEvidenceFixture[] {
  const inputs = result.input_evidence?.inputs;
  if (!inputs) {
    throw new Error(`Missing input evidence for ${result.key}`);
  }
  return inputs;
}

function requireClosestElement(element: Element | null, label: string): HTMLElement {
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing ${label}`);
  }
  return element;
}

function expectElementBefore(first: HTMLElement, second: HTMLElement) {
  expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
}

function macroModelReadinessFixture(
  item: Pick<
    MacroToolkitModelReadinessFixture,
    "id" | "label" | "script_name" | "expected_outputs" | "readiness" | "missing_outputs" | "stale_outputs"
  > &
    Partial<MacroToolkitModelReadinessFixture>,
): MacroToolkitModelReadinessFixture {
  return {
    script_available: true,
    degraded_reason: null,
    evidence_level: "fixture",
    date_basis: "fixture",
    observation_only: true,
    formal_use_allowed: false,
    latest_modified_at: null,
    latest_content_date: null,
    degraded_outputs: [],
    notes: [],
    ...item,
  };
}

function macroCoreModelReadinessFixtures(): MacroToolkitModelReadinessFixture[] {
  const specs = [
    ["merrill_clock", "Merrill Clock", "merrill_clock_cn", ["merrill_clock_latest.csv", "merrill_clock_history.csv"]],
    ["crisis_score", "Crisis Score", "crisis_score_cn", ["crisis_score_latest.csv", "crisis_score_history.csv"]],
    ["bond_futures_four_factor", "Bond Futures Four-Factor Trend", "bond_futures_signals", ["bond_signals_latest.csv"]],
    ["funding_conditions", "Funding Conditions / Flow", "merrill_clock_cn", ["merrill_clock_latest.csv"]],
    ["crowding", "Crowding", "crowding_cn", ["crowding_latest.csv", "crowding_history.csv"]],
    ["dcc_garch", "DCC-GARCH", "dcc_garch_cn", ["dcc_latest.csv", "dcc_results.csv"]],
    ["cta_trend", "CTA Trend", "cta_trend_cn", ["cta_results.csv"]],
    [
      "bond_futures_basis",
      "Bond Futures Basis / IRR / Safety Margin",
      "bond_futures_data",
      ["bond_futures_basis.csv", "bond_futures_irr.csv", "bond_futures_safety_margin.csv"],
    ],
    ["final_signal", "Final Signal Aggregator", "signal_aggregator", ["final_signal.csv"]],
    ["risk_monitor", "Risk Monitor", "risk_monitor", ["risk_state.csv", "risk_log.csv"]],
  ] as const;

  return specs.map(([id, label, script_name, expected_outputs], index) => {
    const readiness = index < 2 ? "artifact_backed" : "missing_output";
    const missing_outputs = readiness === "artifact_backed" ? [] : [...expected_outputs];
    const latest_content_date = readiness === "artifact_backed" ? "2026-04-30" : null;
    return macroModelReadinessFixture({
      id,
      label,
      script_name,
      expected_outputs: [...expected_outputs],
      readiness,
      evidence_level: readiness === "artifact_backed" ? "fresh_artifacts" : "registered_script_only",
      date_basis: readiness === "artifact_backed" ? "csv_content" : "missing",
      degraded_reason: readiness === "artifact_backed" ? null : "missing_expected_outputs",
      artifact_receipt: {
        status: readiness,
        model_id: id,
        script_name,
        artifact_paths: readiness === "artifact_backed" ? [...expected_outputs] : [],
        missing_artifacts: missing_outputs,
        degraded_reason: readiness === "artifact_backed" ? null : "missing_expected_outputs",
        data_asof: latest_content_date,
        generated_at: "2026-04-30T09:00:00+00:00",
        runtime_endpoint: "/ui/macro/toolkit/scripts/run-chain",
        page_surface: "/macro-toolkit#macro-toolkit-script-artifact-detail",
        formal_use_allowed: false,
        observation_only: true,
      },
      latest_modified_at: readiness === "artifact_backed" ? "2026-04-30T15:00:00+00:00" : null,
      latest_content_date,
      missing_outputs,
      stale_outputs: [],
      notes: [`${label} artifact acceptance fixture.`],
    });
  });
}

async function openModelSignalDetail(
  signalMatrix: HTMLElement,
  user: ReturnType<typeof userEvent.setup>,
  label: string,
) {
  const rowTitle = within(signalMatrix).getByText(label);
  const row = requireClosestElement(rowTitle.closest("article"), `${label} signal row`);
  await user.click(within(row).getByRole("button"));
  return screen.findByTestId("macro-toolkit-model-signal-detail");
}

function extractCssBlock(css: string, selector: string): string {
  const start = css.indexOf(selector);
  if (start === -1) {
    throw new Error(`Missing CSS selector: ${selector}`);
  }

  let depth = 0;
  for (let index = start; index < css.length; index += 1) {
    const char = css[index];
    if (char === "{") {
      depth += 1;
    }
    if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return css.slice(start, index + 1);
      }
    }
  }

  throw new Error(`Unclosed CSS block: ${selector}`);
}

function withCrisisScoreInputEvidence(
  envelope: MacroToolkitAnalysisEnvelope,
  inputs: MacroToolkitInputEvidenceFixture[],
  warnings: string[],
) {
  return {
    ...envelope,
    result: {
      ...envelope.result,
      capability_results: envelope.result.capability_results.map((result) => {
        if (result.key !== "crisis_score_cn") {
          return result;
        }
        const rawInputEvidence =
          result.result.input_evidence && typeof result.result.input_evidence === "object"
            ? result.result.input_evidence
            : {};
        return {
          ...result,
          status: warnings.length ? ("degraded" as const) : result.status,
          warnings,
          input_evidence: result.input_evidence
            ? {
                ...result.input_evidence,
                inputs,
                missing_inputs: warnings,
              }
            : result.input_evidence,
          result: {
            ...result.result,
            input_evidence: {
              ...rawInputEvidence,
              inputs,
              missing_inputs: warnings,
            },
          },
        };
      }),
    },
  };
}

describe("MacroToolkitPage", () => {
  it("keeps the macro toolkit page off the monolithic API client entrypoint", () => {
    const source = readFileSync(MACRO_TOOLKIT_PAGE_PATH, "utf8");

    expect(source).not.toContain('from "../../../api/client";');
    expect(source).toContain('from "../../../api/clientContext"');
  });

  it("loads first-screen analysis through the deferred core scope", () => {
    const source = readFileSync(MACRO_TOOLKIT_PAGE_PATH, "utf8");

    expect(source).toContain('client.getMacroToolkitAnalysis({ detail: "core" })');
    expect(source).toContain("MACRO_TOOLKIT_FULL_PREFETCH_DELAY_MS");
    expect(source).toContain("historyLimit: MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT");
    expect(source).toContain("formatCrisisTopContributorSummary");
    expect(source).toContain('data-testid="macro-toolkit-crisis-capability-component-summary"');
  });

  it("keeps page-local decorative colors on the IB light institutional token family", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).not.toMatch(/moss-color-warm-/);
    expect(css).not.toMatch(/rgba\((255, 253, 248|120, 99, 76|147, 111, 88|111, 139, 106|171, 95, 62|143, 63, 63|55, 42, 30)/);
    expect(css).not.toMatch(/#(fffdf8|fffaf4|456882|6f8b6a|8f3f3f|2b2520|f0e7dc)/i);
    expect(css).toContain("var(--ib-accent)");
    expect(css).toContain("var(--ib-up)");
    expect(css).toContain("var(--ib-down)");
    expect(css).toContain("var(--ib-warn)");
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact");
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact__metrics");
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact__grid");
    expect(css).toContain(".macro-toolkit-cockpit--toolkit .macro-toolkit-investment-brief");
    expect(css).toContain("order: -1");
    expect(css).toContain(".macro-toolkit-mobile-committee-strip");
    expect(css).toContain("display: none");
  });

  it("keeps the macro toolkit mobile first screen focused on decision and evidence signoff", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain(".macro-toolkit-mobile-committee-strip");
    expect(css).toContain(".macro-toolkit-committee-first-screen-pipeline");
    expect(css).toContain(".macro-toolkit-committee-decision-memo");
    expect(css).toContain(".macro-toolkit-current-repair-status__tape");
    expect(css).toContain(".macro-toolkit-current-repair-status__locator");
    expect(css).toContain(".macro-toolkit-committee-closure-rail__axis");
    expect(css).toMatch(/\.macro-toolkit-committee-first-screen-pipeline\s*\{[\s\S]*?order:\s*2/);
    expect(css).toMatch(/\.macro-toolkit-mobile-committee-strip\s*\{[\s\S]*?order:\s*3/);
    expect(css).toContain(".macro-toolkit-data-health-signoff-pack");
    expect(css).toContain(".macro-toolkit-investment-brief__grid");
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-current-repair-status__tape\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-committee-closure-rail__axis\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(/\.macro-toolkit-committee-closure-rail__step small\s*\{\s*display:\s*none/);
    expect(css).toMatch(/\.macro-toolkit-committee-pack,\s*[\r\n]+\s*\.macro-toolkit-committee-checklist,\s*[\r\n]+\s*\.macro-toolkit-committee-decision-language/);
  });

  it("compresses the macro toolkit mobile first screen before the investment brief", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Mobile first-screen compression pass");
    expect(css).toMatch(/\.macro-toolkit-page__header-summary\s*\{\s*display:\s*none/);
    expect(css).toMatch(/\.macro-toolkit-page__header\s*\{[\s\S]*?padding:\s*8px/);
    expect(css).toMatch(/\.macro-toolkit-mobile-committee-strip\s*\{[\s\S]*?display:\s*grid/);
    expect(css).toMatch(/\.macro-toolkit-committee-decision-memo__grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
  });

  it("compresses the mobile submission cockpit into an approval summary", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Mobile submission cockpit approval compression pass");
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit__metrics\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit__lanes\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit__verdict,\s*[\s\S]*?\.macro-toolkit-submission-cockpit__owner\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit__metrics > div\s*\{[\s\S]*?min-height:\s*34px/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-submission-cockpit__lane\s*\{[\s\S]*?min-height:\s*44px/,
    );
  });

  it("turns the mobile submission cockpit lanes into a horizontal evidence rail", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile submission cockpit evidence rail pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-submission-cockpit__lanes\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-submission-cockpit__lane\s*\{[\s\S]*?flex:\s*0\s*0\s*112px[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-submission-cockpit__lane small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("compresses the mobile house view into an auxiliary review strip", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile house view auxiliary review strip pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view\s*\{[\s\S]*?gap:\s*4px[\s\S]*?padding:\s*6px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view \.macro-toolkit-cockpit__conclusion p\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-house-view__decision-chain\s*\{[\s\S]*?gap:\s*3px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-house-view__dossier\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-house-view__dossier-item\s*\{[\s\S]*?flex:\s*0\s*0\s*128px[\s\S]*?min-height:\s*44px/,
    );
  });

  it("lets the mobile submission cockpit own the first-screen decision summary", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile submission cockpit owns first-screen summary");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-committee-decision-memo\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(/\.macro-toolkit-current-repair-status\s*\{[\s\S]*?order:\s*3/);
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline\s*\{[\s\S]*?order:\s*9[\s\S]*?grid-template-columns:\s*1fr/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline__head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline small\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(/\.macro-toolkit-mobile-committee-strip\s*\{[\s\S]*?display:\s*none/);
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-final-signoff\s*\{[\s\S]*?order:\s*10[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
  });

  it("compresses the mobile current repair status into a signoff strip", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile current repair status signoff strip pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-current-repair-status__head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-current-repair-status__tape-item,\s*[\s\S]*?\.macro-toolkit-current-repair-status__tape-action\s*\{[\s\S]*?min-height:\s*34px/,
    );
    expect(mobileCss).toMatch(
      /a\.macro-toolkit-current-repair-status__tape-action,\s*[\s\S]*?button\.macro-toolkit-current-repair-status__tape-action\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-current-repair-status__triage-item\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-current-repair-status__triage-item em,\s*[\s\S]*?\.macro-toolkit-current-repair-status__triage-item small,\s*[\s\S]*?\.macro-toolkit-current-repair-status__triage-item b\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("prioritizes the mobile Action Console execution controls", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile operations console execution priority pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__actions\s*\{[\s\S]*?order:\s*2[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__actions \.ant-btn\s*\{[\s\S]*?flex:\s*0\s*0\s*128px[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue\s*\{[\s\S]*?order:\s*3/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-receipt\s*\{[\s\S]*?order:\s*4/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue\s*\{[\s\S]*?order:\s*5/,
    );
  });

  it("compresses the mobile Action Console receipts into a scannable rail", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile operations receipt rail compression pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-receipt\s*\{[\s\S]*?order:\s*4[\s\S]*?gap:\s*4px[\s\S]*?padding:\s*6px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-receipt__head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-receipt__grid\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-receipt__field\s*\{[\s\S]*?min-height:\s*34px[\s\S]*?padding:\s*4px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue\s*\{[\s\S]*?order:\s*5[\s\S]*?gap:\s*4px[\s\S]*?padding:\s*6px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue__list\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue__item\s*\{[\s\S]*?flex:\s*0\s*0\s*160px[\s\S]*?grid-template-columns:\s*1fr[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue__item small\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-action-queue__item a\s*\{[\s\S]*?min-height:\s*44px/,
    );
  });

  it("compresses the mobile Action Console metrics into a horizontal evidence rail", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile operations metrics evidence rail pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__metrics\s*\{[\s\S]*?order:\s*6[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__metrics \.macro-toolkit-metric\s*\{[\s\S]*?flex:\s*0\s*0\s*118px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__metrics \.macro-toolkit-metric strong\s*\{[\s\S]*?font-size:\s*12px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-operations-console__metrics \.macro-toolkit-metric small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("places the mobile committee main workspace before the governance rail", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile committee workspace action-first pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-workspace__main\s*\{[\s\S]*?order:\s*2/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-workspace__rail\s*\{[\s\S]*?order:\s*3/,
    );
  });

  it("compresses the mobile committee work queue into scannable rails", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile committee work queue rail compression pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__matrix\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__matrix-row\s*\{[\s\S]*?flex:\s*0\s*0\s*136px[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__todos\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__todo\s*\{[\s\S]*?flex:\s*0\s*0\s*150px[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__execution\s*\{[\s\S]*?min-height:\s*44px/,
    );
  });

  it("compresses the mobile committee work queue signoff and desk into evidence rails", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile committee work queue signoff desk rail pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__desk\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__desk > div\s*\{[\s\S]*?flex:\s*0\s*0\s*112px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__desk span\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__signoff-grid\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__signoff-item\s*\{[\s\S]*?flex:\s*0\s*0\s*126px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-committee-work-queue__signoff-item small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps the desktop committee pack inside the first-screen investment brief stack", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Desktop investment brief first-screen pack pass");
    expect(css).toMatch(/\.macro-toolkit-submission-cockpit\s*\{[\s\S]*?order:\s*2/);
    expect(css).toMatch(/\.macro-toolkit-committee-final-signoff\s*\{[\s\S]*?order:\s*6/);
    expect(css).toMatch(/\.macro-toolkit-current-repair-status\s*\{[\s\S]*?order:\s*8/);
    expect(css).toMatch(/\.macro-toolkit-committee-pack\s*\{[\s\S]*?order:\s*10/);
    expect(css).toMatch(/\.macro-toolkit-data-health-signoff-pack\s*\{[\s\S]*?order:\s*11/);
    expect(css).toMatch(/\.macro-toolkit-committee-checklist\s*\{[\s\S]*?order:\s*12/);
    expect(css).toMatch(/\.macro-toolkit-committee-redline\s*\{[\s\S]*?order:\s*13/);
    expect(css).toMatch(/\.macro-toolkit-committee-pack__grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/);
  });

  it("lets the desktop submission cockpit own the primary decision while old rails compact", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const desktopCss = extractCssBlock(css, "@media (min-width: 1101px)");

    expect(desktopCss).toContain("Desktop submission cockpit dedupe pass");
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline\s*\{[\s\S]*?grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\)[\s\S]*?padding:\s*4px/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline__head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline__step,\s*[\s\S]*?\.macro-toolkit-committee-first-screen-pipeline__step--action \.macro-toolkit-committee-action\s*\{[\s\S]*?min-height:\s*34px/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-first-screen-pipeline small\s*\{[\s\S]*?display:\s*none/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-decision-memo\s*\{[\s\S]*?grid-template-columns:\s*1fr/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-decision-memo__verdict\s*\{[\s\S]*?display:\s*none/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-next-step-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)[\s\S]*?padding:\s*4px\s*6px/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-next-step-strip > div\s*\{[\s\S]*?min-height:\s*30px/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-decision-memo small,\s*[\s\S]*?\.macro-toolkit-committee-next-step-strip small\s*\{[\s\S]*?display:\s*none/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-final-signoff\s*\{[\s\S]*?display:\s*grid[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*4px\s*6px/,
    );
    expect(desktopCss).toMatch(
      /\.macro-toolkit-committee-final-signoff__decision strong\s*\{[\s\S]*?font-size:\s*12px/,
    );
  });

  it("balances the desktop house view against the investment brief cockpit", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Desktop house view cockpit balance pass");
    expect(css).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view\s*\{[\s\S]*?min-height:\s*560px/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view\s*\{[\s\S]*?grid-template-rows:\s*auto auto auto auto/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-house-view__decision-chain\s*\{[\s\S]*?display:\s*grid/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-house-view__decision-chain\s*\{[\s\S]*?align-self:\s*start/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view \.macro-toolkit-brief-metrics\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-cockpit--toolkit \.macro-toolkit-house-view \.macro-toolkit-cockpit__conclusion\s*\{[\s\S]*?align-content:\s*center/,
    );
  });

  it("surfaces a house view decision chain beside the investment brief", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const houseView = await screen.findByTestId("macro-toolkit-house-view");
    const decisionChain = within(houseView).getByLabelText("House View 投委会决策链");

    expect(decisionChain).toHaveTextContent("投委会提交判断");
    expect(decisionChain).toHaveTextContent("首要卡点");
    expect(decisionChain).toHaveTextContent("下一动作");
    expect(decisionChain).toHaveTextContent(/提交包\s*\d+\/\d+/);
    expect(decisionChain).toHaveTextContent(/签核\s*\d+\/\d+/);
    expect(decisionChain).toHaveTextContent("待复核回执");
  });

  it("turns the desktop house view into a reviewable evidence dossier", async () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(css).toContain("House view evidence dossier pass");
    expect(css).toMatch(
      /\.macro-toolkit-house-view__dossier\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );

    const houseView = await screen.findByTestId("macro-toolkit-house-view");
    const dossier = within(houseView).getByLabelText("House View 依据档案");

    expect(dossier).toHaveTextContent("观点依据");
    expect(dossier).toHaveTextContent("触发条件");
    expect(dossier).toHaveTextContent("风险反证");
    expect(dossier).toHaveTextContent("证据覆盖");
    expect(dossier).toHaveTextContent("责任人");
  });

  it("frames the second screen as an investment committee submission workspace", async () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(css).toContain("Second-screen committee submission workspace pass");
    expect(css).toMatch(
      /\.macro-toolkit-committee-workspace\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1\.34fr\) minmax\(320px,\s*0\.66fr\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-committee-workspace__rail\s*\{[\s\S]*?position:\s*sticky/,
    );

    const workspace = await screen.findByLabelText("投委会提交作业区");
    expect(workspace).toHaveTextContent("投委会提交作业区");
    expect(workspace).toHaveTextContent("主作业区");
    expect(workspace).toHaveTextContent("治理侧栏");

    const scorecard = within(workspace).getByLabelText("投委会提交作业区状态");
    expect(scorecard).toHaveTextContent("提交包");
    expect(scorecard).toHaveTextContent("签核");
    expect(scorecard).toHaveTextContent("硬阻断");
    expect(scorecard).toHaveTextContent("回执");

    const main = within(workspace).getByLabelText("投委会提交主作业区");
    expect(within(main).getByTestId("macro-toolkit-operations-console")).toBeInTheDocument();
    expect(within(main).getByTestId("macro-toolkit-detail-density")).toBeInTheDocument();

    const rail = within(workspace).getByLabelText("投委会治理侧栏");
    expect(within(rail).getByTestId("macro-toolkit-governance-gate")).toBeInTheDocument();
    expect(rail).toHaveTextContent("深度证据入口");
  });

  it("turns the third screen into a committee evidence packet review flow", async () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(css).toContain("Third-screen committee evidence packet review flow pass");
    expect(css).toMatch(
      /\.macro-toolkit-evidence-review-flow\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1\.08fr\) minmax\(320px,\s*0\.92fr\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-evidence-review-flow__rail\s*\{[\s\S]*?position:\s*sticky/,
    );

    const reviewFlow = await screen.findByLabelText("投委会证据包审阅流");
    expect(reviewFlow).toHaveTextContent("投委会证据包审阅流");
    expect(reviewFlow).toHaveTextContent("审阅摘要");
    expect(reviewFlow).toHaveTextContent("阻断");
    expect(reviewFlow).toHaveTextContent("责任人");
    expect(reviewFlow).toHaveTextContent("证据位置");
    expect(reviewFlow).toHaveTextContent("签核动作");

    const reviewRail = within(reviewFlow).getByLabelText("投委会证据包审阅摘要");
    expect(reviewRail).toHaveTextContent("当前阻断");
    expect(reviewRail).toHaveTextContent("数据运营负责人");
    expect(reviewRail).toHaveTextContent("数据健康");
    expect(reviewRail).toHaveTextContent("处理数据缺口");

    const detailLane = within(reviewFlow).getByLabelText("投委会证据包详情");
    expect(within(detailLane).getByTestId("macro-toolkit-evidence-book")).toBeInTheDocument();
    expect(within(detailLane).getByTestId("macro-toolkit-data-health-detail")).toBeInTheDocument();
  });

  it("frames execution evidence and artifacts as a receipt workspace", async () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(css).toContain("Fourth-screen execution evidence receipt workspace pass");
    expect(css).toMatch(
      /\.macro-toolkit-execution-receipt-workspace\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1\.18fr\) minmax\(340px,\s*0\.82fr\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-execution-receipt-workspace__receipt\s*\{[\s\S]*?position:\s*sticky/,
    );

    const workspace = await screen.findByLabelText("执行证据与产物回执区");
    expect(workspace).toHaveTextContent("执行证据与产物回执区");
    expect(workspace).toHaveTextContent("执行证据");
    expect(workspace).toHaveTextContent("产物回执");

    const status = within(workspace).getByLabelText("执行证据与产物状态");
    expect(status).toHaveTextContent("脚本就绪");
    expect(status).toHaveTextContent("输出文件");
    expect(status).toHaveTextContent("源别名");
    expect(status).toHaveTextContent("回执");

    const executionLane = within(workspace).getByLabelText("执行证据详情");
    expect(within(executionLane).getByTestId("macro-toolkit-tool-execution-detail")).toBeInTheDocument();
    expect(within(executionLane).getByTestId("macro-toolkit-cffex-detail")).toBeInTheDocument();
    expect(within(executionLane).getByTestId("macro-toolkit-commodity-detail")).toBeInTheDocument();

    const receiptLane = within(workspace).getByLabelText("产物回执详情");
    expect(within(receiptLane).getByTestId("macro-toolkit-script-artifact-detail")).toBeInTheDocument();
    expect(receiptLane).toHaveTextContent("脚本产物");
    expect(receiptLane).toHaveTextContent("系统数据源命中");
  });

  it("keeps execution evidence summaries in committee language", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const executionLane = await screen.findByLabelText("执行证据详情");
    const executionSummary = within(executionLane).getByTestId("macro-toolkit-tool-execution-detail");

    await waitFor(() => expect(executionSummary).toHaveTextContent("宏观数据源"));
    expect(executionSummary).toHaveTextContent("执行闭环总览");
    expect(executionSummary).toHaveTextContent("行情与因子快照");
    expect(executionSummary).toHaveTextContent("席位排名证据");
    expect(executionSummary).toHaveTextContent("产物回执");
    expect(executionSummary).not.toHaveTextContent("choice + tushare");
    expect(executionSummary).not.toHaveTextContent("fact_choice_macro_daily");
    expect(executionSummary).not.toHaveTextContent("choice_market_snapshot");
    expect(executionSummary).not.toHaveTextContent("choice_stock_daily_observation");

    const statusStrip = requireClosestElement(
      executionLane.querySelector(".macro-toolkit-status-strip"),
      "macro toolkit execution status strip",
    );
    expect(statusStrip).toHaveTextContent("证据口径");
    expect(statusStrip).toHaveTextContent("业务证据");
    expect(statusStrip).not.toHaveTextContent("表：");
    expect(statusStrip).not.toHaveTextContent("analytical");

    const commodityDetail = within(executionLane).getByTestId("macro-toolkit-commodity-detail");
    expect(commodityDetail).toHaveTextContent("商品期货证据");
    expect(commodityDetail).not.toHaveTextContent("目标表");
    expect(commodityDetail).not.toHaveTextContent("fact_commodity_futures_daily");
  });

  it("translates live execution evidence identifiers before they reach the summary", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const client = {
      ...baseClient,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result_meta: {
          ...scriptsEnvelope.result_meta,
          basis: "analytical",
          tables_used: [
            "fact_choice_macro_daily",
            "choice_market_snapshot",
            "fx_daily_mid",
            "fact_formal_yield_curve_daily",
            "std_external_macro_daily",
            "fact_cffex_member_rank_daily",
            "vw_cffex_member_rank_daily",
            "choice_stock_daily_observation",
            "fact_commodity_futures_daily",
          ],
        },
        result: {
          ...scriptsEnvelope.result,
          output_files: [
            {
              name: "bond_futures_history.csv",
              path: "data/macro_toolkit/output/bond_futures_history.csv",
              size_bytes: 1024,
              modified_at: "2026-06-01T09:30:00Z",
            },
          ],
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const executionLane = await screen.findByLabelText("执行证据详情");
    const executionSummary = within(executionLane).getByTestId("macro-toolkit-tool-execution-detail");

    await waitFor(() => expect(executionSummary).toHaveTextContent("曲线利率证据"));
    expect(executionSummary).toHaveTextContent("汇率中间价证据");
    expect(executionSummary).toHaveTextContent("外部宏观证据");
    expect(executionSummary).toHaveTextContent("席位排名证据");
    expect(executionSummary).toHaveTextContent("产物回执已归档");
    expect(executionSummary).not.toHaveTextContent("fx_daily_mid");
    expect(executionSummary).not.toHaveTextContent("fact_formal_yield_curve_daily");
    expect(executionSummary).not.toHaveTextContent("std_external_macro_daily");
    expect(executionSummary).not.toHaveTextContent("fact_cffex_member_rank_daily");
    expect(executionSummary).not.toHaveTextContent("vw_cffex_member_rank_daily");
    expect(executionSummary).not.toHaveTextContent("bond_futures_history.csv");
  });

  it("keeps macro toolkit status strips readable while preserving raw audit titles", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const basisAuditNode = await screen.findByTitle("读取口径：analytical");
    const statusStrip = requireClosestElement(
      basisAuditNode.closest(".macro-toolkit-status-strip"),
      "macro toolkit status strip",
    );

    expect(statusStrip).toHaveTextContent("分析口径");
    expect(statusStrip).toHaveTextContent("质量可用");
    expect(statusStrip).not.toHaveTextContent("analytical");
    expect(statusStrip).not.toHaveTextContent(" ok ");
    expect(within(statusStrip).getByTitle("读取口径：analytical")).toBeInTheDocument();
    expect(within(statusStrip).getByTitle("质量：ok")).toBeInTheDocument();
  });

  it("anchors the receipt lane with an investment committee delivery chain", async () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(css).toContain("Fifth-screen committee delivery chain pass");
    expect(css).toMatch(
      /\.macro-toolkit-committee-delivery-chain\s*\{[\s\S]*?grid-template-columns:\s*minmax\(120px,\s*0\.7fr\) minmax\(0,\s*1\.3fr\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-committee-delivery-chain__steps\s*\{[\s\S]*?grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\)/,
    );

    const receiptLane = await screen.findByLabelText("产物回执详情");
    const deliveryChain = within(receiptLane).getByLabelText("投委会交付链");
    expect(deliveryChain).toHaveTextContent("投委会交付链");
    expect(deliveryChain).toHaveTextContent("结论");
    expect(deliveryChain).toHaveTextContent("证据");
    expect(deliveryChain).toHaveTextContent("执行");
    expect(deliveryChain).toHaveTextContent("回执");
    expect(deliveryChain).toHaveTextContent("签核");
    expect(deliveryChain).toHaveTextContent(/下一步/);
    expect(deliveryChain).toHaveTextContent(/签核\s*\d+\/\d+/);

    const artifactDetail = within(receiptLane).getByTestId("macro-toolkit-script-artifact-detail");
    expectElementBefore(deliveryChain, artifactDetail);
  });

  it("keeps the final committee signoff gate visible before all receipts clear", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const finalSignoff = within(investmentBrief).getByLabelText("最终投委会签核态");

    expect(finalSignoff).toHaveTextContent("最终投委会签核态");
    expect(finalSignoff).toHaveTextContent("暂缓提交");
    expect(finalSignoff).toHaveTextContent("提交包");
    expect(finalSignoff).toHaveTextContent("签核");
    expect(finalSignoff).toHaveTextContent("剩余风险");
    expect(finalSignoff).toHaveTextContent("待复核回执");
    expect(finalSignoff).toHaveTextContent("数据运营负责人");
    expect(finalSignoff).toHaveTextContent("待确认");
    expect(finalSignoff).not.toHaveTextContent("提交包 0/0");
  });

  it("opens with a submission cockpit that owns the committee decision state", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const submissionCockpit = within(investmentBrief).getByLabelText("投委会提交总控台");
    const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");

    await waitFor(() => expect(submissionCockpit).toHaveTextContent("提交包 1/4"));

    expect(submissionCockpit).toHaveTextContent("提交结论");
    expect(submissionCockpit).toHaveTextContent("暂缓提交");
    expect(submissionCockpit).toHaveTextContent("责任人");
    expect(submissionCockpit).toHaveTextContent("数据运营负责人");
    expect(submissionCockpit).toHaveTextContent("提交包 1/4");
    expect(submissionCockpit).toHaveTextContent("签核 1/3");
    expect(submissionCockpit).toHaveTextContent("剩余风险 1");
    expect(submissionCockpit).toHaveTextContent("待复核回执 0");

    const laneOverview = within(submissionCockpit).getByLabelText("投委会提交链路总览");
    expect(laneOverview).toHaveTextContent("数据健康");
    expect(laneOverview).toHaveTextContent("策略供数");
    expect(laneOverview).toHaveTextContent("工具执行");
    expect(laneOverview).toHaveTextContent("提交门禁");
    expect(within(laneOverview).getByRole("link", { name: /数据健康.*处理数据缺口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expectElementBefore(submissionCockpit, pipeline);
  });

  it("turns the committee material pack into a review index", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const committeePack = within(investmentBrief).getByLabelText("投委会材料包");

    await waitFor(() => expect(committeePack).toHaveTextContent("结论底稿"));
    const reviewIndex = within(committeePack).getByLabelText("投委会材料包审阅索引");

    expect(reviewIndex).toHaveTextContent("审阅索引");
    expect(reviewIndex).toHaveTextContent("责任人");
    expect(reviewIndex).toHaveTextContent("证据入口");
    expect(reviewIndex).toHaveTextContent("提交影响");
    expect(reviewIndex).toHaveTextContent("结论底稿");
    expect(reviewIndex).toHaveTextContent("数据健康");
    expect(reviewIndex).toHaveTextContent("数据运营负责人");
    expect(within(reviewIndex).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
  });

  it("aligns the Evidence Book with committee material pack delivery status", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");

    expect(evidenceBook).toHaveTextContent("交付状态");
    expect(evidenceBook).toHaveTextContent("提交影响");
    expect(evidenceBook).toHaveTextContent("回执状态");
    expect(evidenceBook).toHaveTextContent("责任人");

    const dataHealthRow = within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s });
    expect(dataHealthRow).toHaveTextContent("阻断提交");
    expect(dataHealthRow).toHaveTextContent("阻断最终提交");
    expect(dataHealthRow).toHaveTextContent("等待回执");
    expect(dataHealthRow).toHaveTextContent("数据运营负责人");
    expect(dataHealthRow).toHaveAttribute("href", "#macro-toolkit-data-health-detail");
  });

  it("summarizes committee submission readiness inside the Evidence Book", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const submissionSummary = within(evidenceBook).getByLabelText("证据复核总账提交包总览");

    expect(submissionSummary).toHaveTextContent("提交包可审");
    expect(submissionSummary).toHaveTextContent("1/4");
    expect(submissionSummary).toHaveTextContent("签核");
    expect(submissionSummary).toHaveTextContent("1/3");
    expect(submissionSummary).toHaveTextContent("待复核回执");
    expect(submissionSummary).toHaveTextContent("0");
    expect(submissionSummary).toHaveTextContent("硬阻断");
    expect(submissionSummary).toHaveTextContent("1");
  });

  it("surfaces the final committee submission gate inside the Evidence Book", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const submissionGate = within(evidenceBook).getByLabelText("投委会最终提交门禁");

    expect(submissionGate).toHaveTextContent("Submission Gate");
    expect(submissionGate).toHaveTextContent("投委会最终提交门禁");
    expect(submissionGate).toHaveTextContent("当前结论");
    expect(submissionGate).toHaveTextContent("暂缓提交");
    expect(submissionGate).toHaveTextContent("首要阻断");
    expect(submissionGate).toHaveTextContent("数据缺口");
    expect(submissionGate).toHaveTextContent("责任人");
    expect(submissionGate).toHaveTextContent("数据运营负责人");
    expect(submissionGate).toHaveTextContent("下一动作");
    expect(submissionGate).toHaveTextContent("处理数据缺口");
    expect(submissionGate).toHaveTextContent("提交包 1/4");
    expect(submissionGate).toHaveTextContent("签核 1/3");
    expect(submissionGate).toHaveTextContent("剩余风险 1");
    expect(submissionGate).toHaveTextContent("待复核回执 0");
    expect(submissionGate).toHaveTextContent("未达提交标准");
  });

  it("surfaces a committee material pack receipt in the Evidence Book", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const packReceipt = within(evidenceBook).getByLabelText("投委会材料包封面回执");

    expect(packReceipt).toHaveTextContent("Pack Receipt");
    expect(packReceipt).toHaveTextContent("投委会材料包封面回执");
    expect(packReceipt).toHaveTextContent("提交结论");
    expect(packReceipt).toHaveTextContent("暂缓提交");
    expect(packReceipt).toHaveTextContent("首要卡点");
    expect(packReceipt).toHaveTextContent("数据缺口");
    expect(packReceipt).toHaveTextContent("责任人");
    expect(packReceipt).toHaveTextContent("数据运营负责人");
    expect(packReceipt).toHaveTextContent("下一动作");
    expect(packReceipt).toHaveTextContent("处理数据缺口");
    expect(packReceipt).toHaveTextContent("提交包 1/4");
    expect(packReceipt).toHaveTextContent("签核 1/3");
    expect(packReceipt).toHaveTextContent("剩余风险 1");
    expect(packReceipt).toHaveTextContent("待复核回执 0");
    expect(packReceipt).toHaveTextContent("证据留痕");
    expect(packReceipt).toHaveTextContent("Evidence Book 同步材料包、回执与签核状态");
  });

  it("copies the committee material pack receipt summary", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const originalWindowClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      renderWorkbenchApp(["/macro-toolkit"]);

      const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
      const packReceipt = within(evidenceBook).getByLabelText("投委会材料包封面回执");

      fireEvent.click(within(packReceipt).getByRole("button", { name: "复制材料包摘要" }));

      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("投委会材料包封面回执")),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("提交结论 暂缓提交"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("首要卡点 数据缺口"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("责任人 数据运营负责人"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("下一动作 处理数据缺口"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("提交包 1/4"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("签核 1/3"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("剩余风险 1"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("待复核回执 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("证据留痕 数据健康 · 数据运营负责人"));
      await waitFor(() => expect(packReceipt).toHaveTextContent("材料包摘要已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
      if (originalWindowClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalWindowClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });

  it("keeps the Evidence Book entry label in sync with receipt signoff", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshMacroSourceBackfill: async (options) => baseClient.refreshMacroSourceBackfill(options),
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    await waitFor(() => expect(currentRepairStatus).toHaveTextContent("M0041813"));

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    expect(within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveTextContent(
      "等待回执",
    );

    await user.click(within(investmentBrief).getByRole("link", { name: /流水线下一步.*处理数据缺口/s }));
    const actionLocator = within(currentRepairStatus).getByLabelText("投委会动作定位回执");
    await user.click(within(actionLocator).getByRole("button", { name: "执行来源补齐" }));

    const evidenceBookAfterReceipt = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataHealthReceiptRow = within(evidenceBookAfterReceipt).getByRole("link", {
      name: /数据健康.*回执入口/s,
    });
    expect(dataHealthReceiptRow).toHaveTextContent("回执待复核");
    expect(dataHealthReceiptRow).toHaveTextContent("回执待签核");

    const investmentBriefAfterReceipt = await screen.findByTestId("macro-toolkit-investment-brief");
    await user.click(
      within(investmentBriefAfterReceipt).getByRole("button", {
        name: "复核数据健康回执",
      }),
    );

    const evidenceBookAfterSignoff = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataHealthSignoffRow = within(evidenceBookAfterSignoff).getByRole("link", {
      name: /数据健康.*签核证据/s,
    });
    expect(dataHealthSignoffRow).toHaveTextContent("已签核");
    expect(dataHealthSignoffRow).toHaveTextContent("可提交复核");
  });

  it("lets the Evidence Book execute and sign off the active blocking evidence row", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataHealthRow = within(evidenceBook).getByRole("group", { name: "数据健康证据处理闭环" });

    expect(within(dataHealthRow).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    await user.click(within(dataHealthRow).getByRole("button", { name: "处理数据缺口" }));

    await waitFor(() => expect(sourceBackfillCalls).toEqual([expect.objectContaining({ alias: "M0041813" })]));
    const evidenceBookAfterReceipt = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataHealthReceiptRow = within(evidenceBookAfterReceipt).getByRole("group", {
      name: "数据健康证据处理闭环",
    });
    expect(dataHealthReceiptRow).toHaveTextContent("回执待复核");
    expect(dataHealthReceiptRow).toHaveTextContent("回执待签核");
    await user.click(within(dataHealthReceiptRow).getByRole("button", { name: "复核数据健康回执" }));

    const evidenceBookAfterSignoff = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataHealthSignoffRow = within(evidenceBookAfterSignoff).getByRole("group", {
      name: "数据健康证据处理闭环",
    });
    expect(dataHealthSignoffRow).toHaveTextContent("已签核");
    expect(dataHealthSignoffRow).toHaveTextContent("可提交复核");
    expect(within(dataHealthSignoffRow).getByRole("link", { name: "查看签核证据" })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
  });

  it("opens the receipt lane with an audit workpaper before technical details", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const receiptLane = await screen.findByLabelText("产物回执详情");
    const auditWorkpaper = within(receiptLane).getByLabelText("产物审计底稿");

    expect(auditWorkpaper).toHaveTextContent("产物审计底稿");
    expect(auditWorkpaper).toHaveTextContent("产物归档");
    expect(auditWorkpaper).toHaveTextContent("来源命中");
    expect(auditWorkpaper).toHaveTextContent("执行能力");
    expect(auditWorkpaper).toHaveTextContent("留痕状态");
    expect(auditWorkpaper).toHaveTextContent("明细在下方展开");
    expect(auditWorkpaper).not.toHaveTextContent("bond_futures_history.csv");
    expect(auditWorkpaper).not.toHaveTextContent("signal_aggregator");
    expect(auditWorkpaper).not.toHaveTextContent("macro_toolkit");

    const artifactDetail = within(receiptLane).getByTestId("macro-toolkit-script-artifact-detail");
    const registryHeading = await screen.findByRole("heading", { level: 2, name: "脚本注册表" });
    const registrySection = requireClosestElement(
      registryHeading.closest(".macro-toolkit-section"),
      "macro toolkit script registry section",
    );
    const runHeading = await screen.findByRole("heading", { level: 2, name: "运行结果" });
    const runSection = requireClosestElement(
      runHeading.closest(".macro-toolkit-section"),
      "macro toolkit run result section",
    );

    expectElementBefore(auditWorkpaper, artifactDetail);
    expectElementBefore(auditWorkpaper, registrySection);
    expectElementBefore(auditWorkpaper, runSection);
  });

  it("keeps receipt technical details collapsed behind the audit workpaper by default", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    const receiptLane = await screen.findByLabelText("产物回执详情");
    const auditWorkpaper = within(receiptLane).getByLabelText("产物审计底稿");
    const technicalDetails = within(receiptLane).getByLabelText("底稿技术明细");
    const artifactDetail = within(technicalDetails).getByTestId("macro-toolkit-script-artifact-detail");

    expect(technicalDetails).toHaveClass("macro-toolkit-receipt-technical-details--collapsed");
    expect(technicalDetails).toHaveTextContent("默认收起");
    expect(technicalDetails).toHaveTextContent("展开明细");
    expect(technicalDetails).toHaveTextContent("脚本产物");
    expect(technicalDetails).toHaveTextContent("系统数据源命中");
    expect(technicalDetails).toHaveTextContent("脚本注册表");
    expect(technicalDetails).toHaveTextContent("运行结果");
    expect(technicalDetails.contains(artifactDetail)).toBe(true);

    const receiptChildren = Array.from(receiptLane.children);
    const workpaperIndex = receiptChildren.indexOf(auditWorkpaper);
    const technicalIndex = receiptChildren.indexOf(technicalDetails);
    expect(workpaperIndex).toBeGreaterThan(-1);
    expect(workpaperIndex).toBeLessThan(technicalIndex);

    await user.click(within(technicalDetails).getByRole("button", { name: "展开明细" }));

    expect(technicalDetails).toHaveClass("macro-toolkit-receipt-technical-details--expanded");
    expect(within(technicalDetails).getByRole("button", { name: "收起明细" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("frames the first screen as a conclusion blocker next-step committee pipeline", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");
    const decisionMemo = within(investmentBrief).getByLabelText("投委会决策稿");
    const nextStepStrip = within(investmentBrief).getByLabelText("投委会下一步执行条");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");

    await waitFor(() => expect(pipeline).toHaveTextContent("处理数据缺口"));

    expect(pipeline).toHaveTextContent("投委会首屏流水线");
    expect(pipeline).toHaveTextContent("结论");
    expect(pipeline).toHaveTextContent("首要卡点");
    expect(pipeline).toHaveTextContent("下一步");
    expect(pipeline).toHaveTextContent("签核");
    expect(pipeline).toHaveTextContent("提交包");
    expect(pipeline).toHaveTextContent("数据运营负责人");
    const pipelineAction = within(pipeline).getByRole("link", { name: /流水线下一步.*处理数据缺口/s });
    expect(pipelineAction).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expectElementBefore(pipeline, decisionMemo);
    expectElementBefore(pipeline, nextStepStrip);
    expectElementBefore(pipeline, currentRepairStatus);

    await user.click(pipelineAction);

    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
  });

  it("keeps the committee next-step strip as auxiliary status below the pipeline", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const completeCapabilityResults = analysisEnvelope.result.capability_results.map((result) => ({
      ...result,
      status: "complete" as const,
      warnings: [],
    }));
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "full",
            deferred_sections: [],
          },
          capability_results: completeCapabilityResults,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "full",
            capability_results: {
              ...analysisEnvelope.result.data_health!.capability_results,
              complete: completeCapabilityResults.length,
              degraded: 0,
              unavailable: 0,
              total_count: completeCapabilityResults.length,
              deferred: false,
            },
            repair_items: [],
          },
        },
      }),
    } as ApiClient;
    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");
    const nextStepStrip = within(investmentBrief).getByLabelText("投委会下一步执行条");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");

    await waitFor(() => expect(nextStepStrip).toHaveTextContent("待确认闭环"));

    expect(within(pipeline).getByRole("button", { name: /流水线下一步.*复核工具执行结果/s })).toBeInTheDocument();
    expect(nextStepStrip).toHaveTextContent("投委会下一步执行条");
    expect(nextStepStrip).toHaveTextContent("主入口已上移");
    expect(nextStepStrip).toHaveTextContent("流水线下一步：复核工具执行结果");
    expect(nextStepStrip).toHaveTextContent("数据运营负责人");
    expect(nextStepStrip).toHaveTextContent("工具执行待确认");
    expect(nextStepStrip).toHaveTextContent("回执要求");
    expect(nextStepStrip).toHaveTextContent("工具执行回执");
    expect(within(nextStepStrip).queryByRole("button", { name: "复核工具执行结果" })).not.toBeInTheDocument();
    expect(within(nextStepStrip).queryByRole("link", { name: /复核工具执行结果/ })).not.toBeInTheDocument();
    expectElementBefore(nextStepStrip, currentRepairStatus);
  });

  it("keeps the committee delivery chain readable on mobile", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Mobile committee delivery chain readability pass");
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-committee-delivery-chain__steps\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-committee-delivery-chain__step\s*\{[\s\S]*?min-height:\s*58px/,
    );
  });

  it("keeps deep evidence entry links touchable on mobile", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).toContain("Mobile evidence entry touch target pass");
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-evidence-book__evidence-link\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-committee-pack__review-row a\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-data-health-signoff-pack > a\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-evidence-book__pack-receipt-actions \.ant-btn\s*\{[\s\S]*?min-height:\s*44px/,
    );
  });

  it("compresses the mobile Evidence Book into committee dossier rails", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile evidence book committee dossier rail pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__submission-summary\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__submission-summary > div\s*\{[\s\S]*?flex:\s*0\s*0\s*96px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__submission-gate-verdict,\s*[\s\S]*?\.macro-toolkit-evidence-book__pack-receipt-verdict\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__submission-gate-verdict > div,\s*[\s\S]*?\.macro-toolkit-evidence-book__pack-receipt-verdict > div\s*\{[\s\S]*?flex:\s*0\s*0\s*126px[\s\S]*?min-height:\s*44px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__grid\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__row\s*\{[\s\S]*?flex:\s*0\s*0\s*210px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*6px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__evidence-link > span:not\(\.macro-toolkit-evidence-book__delivery\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-evidence-book__delivery i,\s*[\s\S]*?\.macro-toolkit-evidence-book__action small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("compresses the mobile data health detail into committee review rails", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const mobileCss = extractCssBlock(css, "@media (max-width: 760px)");

    expect(mobileCss).toContain("Mobile data health detail committee rail pass");
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health-summary,\s*[\s\S]*?\.macro-toolkit-data-health\s*\{[\s\S]*?gap:\s*6px[\s\S]*?padding:\s*8px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health-summary__grid,\s*[\s\S]*?\.macro-toolkit-data-health__grid,\s*[\s\S]*?\.macro-toolkit-data-health__repair-ticket-grid,\s*[\s\S]*?\.macro-toolkit-data-health__repair-list\s*\{[\s\S]*?display:\s*flex[\s\S]*?overflow-x:\s*auto[\s\S]*?scrollbar-width:\s*thin/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health-summary__grid > div,\s*[\s\S]*?\.macro-toolkit-data-health__tile,\s*[\s\S]*?\.macro-toolkit-data-health__repair-ticket-grid > div\s*\{[\s\S]*?flex:\s*0\s*0\s*126px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*5px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health__repair\s*\{[\s\S]*?flex:\s*0\s*0\s*178px[\s\S]*?min-height:\s*44px[\s\S]*?padding:\s*6px/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health-summary__grid small,\s*[\s\S]*?\.macro-toolkit-data-health__tile small,\s*[\s\S]*?\.macro-toolkit-data-health__repair-main small,\s*[\s\S]*?\.macro-toolkit-data-health__repair-action small\s*\{[\s\S]*?display:\s*none/,
    );
    expect(mobileCss).toMatch(
      /\.macro-toolkit-data-health__repair-action \.ant-btn,\s*[\s\S]*?\.macro-toolkit-data-health__repair-ticket-evidence\s*\{[\s\S]*?min-height:\s*44px/,
    );
  });

  it("contains deep-page tables and committee work queue rows without clipping", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");
    const source = readFileSync(MACRO_TOOLKIT_PAGE_PATH, "utf8");

    expect(css).toContain("Deep-page table containment pass");
    expect(source).toContain('className="macro-toolkit-table--wide"');
    expect(source).toContain('className="macro-toolkit-table--receipt"');
    expect(css).toMatch(
      /\.macro-toolkit-page \.ant-table-wrapper\s*\{[\s\S]*?overflow-x:\s*auto/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-page \.ant-table-wrapper\s*\{[\s\S]*?max-width:\s*100%/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-table--wide \.ant-table\s*\{[\s\S]*?min-width:\s*min\(920px,\s*100%\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-table--receipt \.ant-table\s*\{[\s\S]*?min-width:\s*min\(640px,\s*100%\)/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-committee-work-queue__todo-columns\s*\{[\s\S]*?display:\s*none/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-committee-work-queue__todo\s*\{[\s\S]*?grid-template-columns:\s*1fr/,
    );
    expect(css).toMatch(
      /\.macro-toolkit-committee-work-queue__todo-main\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toContain("Mobile governance gate wraps without horizontal strips");
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-governance-gate__metrics\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)[\s\S]*?overflow:\s*visible/,
    );
    expect(css).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.macro-toolkit-governance-gate \.macro-toolkit-contract-boundary\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)[\s\S]*?overflow:\s*visible/,
    );
    expect(css).toMatch(
      /@media \(max-width: 1100px\)[\s\S]*?\.macro-toolkit-committee-work-queue__todo-main\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
  });

  it("surfaces a first-screen action locator when the current repair action is selected", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
    } as ApiClient;
    const user = userEvent.setup();

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 0,
          refetchOnWindowFocus: false,
        },
      },
    });

    render(<MacroToolkitPage />, {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </ApiClientProvider>
      ),
    });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    await waitFor(() => expect(currentRepairStatus).toHaveTextContent("M0041813"));

    expect(within(currentRepairStatus).queryByLabelText("投委会动作定位回执")).not.toBeInTheDocument();

    const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");
    await user.click(within(pipeline).getByRole("link", { name: /流水线下一步.*处理数据缺口/s }));

    const actionLocator = within(currentRepairStatus).getByLabelText("投委会动作定位回执");
    expect(actionLocator).toHaveTextContent("动作已定位");
    expect(actionLocator).toHaveTextContent("M0041813");
    expect(actionLocator).toHaveTextContent("数据运营负责人");
    expect(actionLocator).toHaveTextContent("来源补齐回执");
    expect(actionLocator).toHaveTextContent("打开处理单");
    expect(within(actionLocator).getByRole("link", { name: "打开处理单" })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );

    const dataHealthDetail = await screen.findByTestId("macro-toolkit-data-health-detail");
    expect(within(dataHealthDetail).getByLabelText("当前处理数据项-M0041813")).toHaveTextContent("3M NCD");
  });

  it("keeps the committee decision memo as read-only rationale while the pipeline owns the repair action", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
    } as ApiClient;
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView as unknown as HTMLElement["scrollIntoView"];

    try {
      renderWorkbenchApp(["/macro-toolkit"], { client });

      const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
      const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
      const decisionMemo = within(investmentBrief).getByLabelText("投委会决策稿");
      const committeeReadiness = await screen.findByTestId("macro-toolkit-committee-readiness");
      const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");
      await waitFor(() => expect(currentRepairStatus).toHaveTextContent("M0041813"));

      const pipelineAction = within(pipeline).getByRole("link", { name: /流水线下一步.*处理数据缺口/s });
      expect(decisionMemo).toHaveTextContent("判断口径");
      expect(decisionMemo).toHaveTextContent("主入口在首屏流水线");
      expect(committeeReadiness).toHaveTextContent("执行说明");
      expect(committeeReadiness).toHaveTextContent("首屏流水线承接");
      expect(within(decisionMemo).queryByRole("link", { name: /执行下一动作.*处理数据缺口/s })).not.toBeInTheDocument();
      expect(within(committeeReadiness).queryByRole("link", { name: "处理数据缺口" })).not.toBeInTheDocument();

      expect(fireEvent.click(pipelineAction)).toBe(false);

      const actionLocator = within(currentRepairStatus).getByLabelText("投委会动作定位回执");
      expect(actionLocator).toHaveTextContent("动作已定位");
      expect(actionLocator).toHaveTextContent("M0041813");
      expect(within(actionLocator).getByRole("link", { name: "打开处理单" })).toHaveAttribute(
        "href",
        "#macro-toolkit-data-health-detail",
      );
      await waitFor(() =>
        expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ block: "nearest", inline: "nearest" })),
      );
    } finally {
      if (originalScrollIntoView) {
        HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
      } else {
        delete (HTMLElement.prototype as Partial<Pick<HTMLElement, "scrollIntoView">>).scrollIntoView;
      }
    }
  });

  it("keeps the data-gap committee action unique when a capability repair is the current item", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const dataHealth = analysisEnvelope.result.data_health!;
    const repairItems = dataHealth.repair_items ?? [];
    const capabilityRepair = repairItems.find((item) => item.key === "capability:leading_indicator");
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          data_health: {
            ...dataHealth,
            repair_items: [capabilityRepair].filter(Boolean),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    const decisionMemo = within(investmentBrief).getByLabelText("投委会决策稿");
    const committeeReadiness = await screen.findByTestId("macro-toolkit-committee-readiness");
    const pipeline = within(investmentBrief).getByLabelText("投委会首屏流水线");

    await waitFor(() => expect(currentRepairStatus).toHaveTextContent("宏观领先指标"));
    expect(within(pipeline).getByRole("link", { name: /流水线下一步.*处理数据缺口/s })).toBeInTheDocument();
    expect(decisionMemo).toHaveTextContent("判断口径");
    expect(decisionMemo).toHaveTextContent("主入口在首屏流水线");
    expect(committeeReadiness).toHaveTextContent("执行说明");
    expect(committeeReadiness).toHaveTextContent("首屏流水线承接");
    expect(within(decisionMemo).queryByRole("link", { name: /处理数据缺口/s })).not.toBeInTheDocument();
    expect(within(committeeReadiness).queryByRole("link", { name: /处理数据缺口/s })).not.toBeInTheDocument();
  });

  it("centers the first-screen action locator on narrow viewports", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
    } as ApiClient;
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const originalInnerWidth = window.innerWidth;
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView as unknown as HTMLElement["scrollIntoView"];
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });

    try {
      renderWorkbenchApp(["/macro-toolkit"], { client });

      const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
      const currentRepairStatus = investmentBrief.querySelector(".macro-toolkit-current-repair-status");
      const pipeline = investmentBrief.querySelector(".macro-toolkit-committee-first-screen-pipeline");
      expect(currentRepairStatus).toBeTruthy();
      expect(pipeline).toBeTruthy();
      await waitFor(() => expect(currentRepairStatus).toHaveTextContent("M0041813"));

      const pipelineAction = within(pipeline as HTMLElement).getByRole("link", {
        name: /流水线下一步.*处理数据缺口/s,
      });
      expect(fireEvent.click(pipelineAction)).toBe(false);

      const actionLocator = currentRepairStatus?.querySelector(".macro-toolkit-current-repair-status__locator");
      expect(actionLocator).toHaveTextContent("M0041813");
      await waitFor(() =>
        expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ block: "center", inline: "nearest" })),
      );
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: originalInnerWidth });
      if (originalScrollIntoView) {
        HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
      } else {
        delete (HTMLElement.prototype as Partial<Pick<HTMLElement, "scrollIntoView">>).scrollIntoView;
      }
    }
  });

  it("executes the located first-screen repair action and leaves a review receipt", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const originalWindowClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const coreAnalysisEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        runtime_status: {
          analysis_scope: "core",
          deferred_sections: [
            {
              key: "strategy_summaries",
              label: "策略展示",
              status: "loading",
            },
            {
              key: "capability_results",
              label: "能力结果",
              status: "loading",
            },
          ],
        },
        data_health: analysisEnvelope.result.data_health
          ? {
              ...analysisEnvelope.result.data_health,
              analysis_scope: "core",
            }
          : analysisEnvelope.result.data_health,
      },
    };
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const choiceStockCalls: Array<Parameters<ApiClient["refreshChoiceStock"]>[0]> = [];
    const analysisCalls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const scriptCalls: Array<string> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        analysisCalls.push(options);
        return options?.detail === "full" ? analysisEnvelope : coreAnalysisEnvelope;
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
      refreshChoiceStock: async (options) => {
        choiceStockCalls.push(options);
        return baseClient.refreshChoiceStock(options);
      },
      runMacroToolkitScript: async (name, options) => {
        scriptCalls.push(name);
        return baseClient.runMacroToolkitScript(name, options);
      },
    } as ApiClient;
    try {
      renderWorkbenchApp(["/macro-toolkit"], { client });

      const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
      const currentRepairStatus = investmentBrief.querySelector(".macro-toolkit-current-repair-status");
      const pipeline = investmentBrief.querySelector(".macro-toolkit-committee-first-screen-pipeline");
      expect(currentRepairStatus).toBeTruthy();
      expect(pipeline).toBeTruthy();
      await waitFor(() => expect(currentRepairStatus).toHaveTextContent("M0041813"));

      const pipelineAction = within(pipeline as HTMLElement).getByRole("link", {
        name: /流水线下一步.*处理数据缺口/s,
      });
      expect(fireEvent.click(pipelineAction)).toBe(false);

      const actionLocator = currentRepairStatus?.querySelector(".macro-toolkit-current-repair-status__locator");
      expect(actionLocator).toHaveTextContent("M0041813");
      await user.click(within(actionLocator as HTMLElement).getByRole("button", { name: "执行来源补齐" }));

      await waitFor(() =>
        expect(sourceBackfillCalls).toEqual([expect.objectContaining({ alias: "M0041813" })]),
      );
      const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
      const sourceBackfillReceipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
      await waitFor(() => expect(sourceBackfillReceipt).toHaveTextContent("来源补齐"));
      expect(sourceBackfillReceipt).toHaveTextContent("已完成");

      const investmentBriefAfterExecution = await screen.findByTestId("macro-toolkit-investment-brief");
      const readinessSummary = within(investmentBriefAfterExecution).getByLabelText("投委会提交包就绪摘要");
      expect(readinessSummary).toHaveTextContent(/硬阻断\s*0/);
      expect(readinessSummary).toHaveTextContent(/待复核回执\s*1/);

      const currentRepairActionAfterExecution = within(investmentBriefAfterExecution).getByRole("button", {
        name: "复核数据健康回执",
      });
      await user.click(currentRepairActionAfterExecution);

      const investmentBriefAfterSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
      const summaryAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会提交包就绪摘要");
      expect(summaryAfterSignoff).toHaveTextContent(/硬阻断\s*0/);
      expect(summaryAfterSignoff).toHaveTextContent(/待复核回执\s*0/);
      const committeeReadinessAfterSignoff = within(investmentBriefAfterSignoff).getByTestId(
        "macro-toolkit-committee-readiness",
      );
      expect(committeeReadinessAfterSignoff).toHaveTextContent("待确认闭环");
      expect(committeeReadinessAfterSignoff).toHaveTextContent("策略供数待确认");
      expect(committeeReadinessAfterSignoff).toHaveTextContent("权益策略负责人");
      expect(
        within(committeeReadinessAfterSignoff).getByRole("button", { name: "执行策略供数刷新" }),
      ).toBeInTheDocument();
      expect(committeeReadinessAfterSignoff).not.toHaveTextContent("查看签核证据");
      expect(committeeReadinessAfterSignoff).not.toHaveTextContent("数据健康回执待复核");
      const decisionMemoAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会决策稿");
      expect(
        within(decisionMemoAfterSignoff).getByRole("button", { name: "执行策略供数刷新" }),
      ).toHaveTextContent("执行策略供数刷新");
      const currentRepairStatusAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会当前处理状态");
      expect(currentRepairStatusAfterSignoff).toHaveTextContent("M0041813");
      expect(currentRepairStatusAfterSignoff).toHaveTextContent("签核已确认");
      const committeePackAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会材料包");
      expect(within(committeePackAfterSignoff).getByLabelText("投委会材料包-数据健康")).toHaveTextContent("已签核");

      const firstScreenStrategyAction = within(committeeReadinessAfterSignoff).getByRole("button", {
        name: "执行策略供数刷新",
      });
      await user.click(firstScreenStrategyAction);

      await waitFor(() => expect(choiceStockCalls).toHaveLength(1));
      await waitFor(() => {
        const investmentBriefAfterRefresh = screen.getByTestId("macro-toolkit-investment-brief");
        const committeePackAfterRefresh = within(investmentBriefAfterRefresh).getByLabelText("投委会材料包");
        expect(within(committeePackAfterRefresh).getByLabelText("投委会材料包-策略供数")).toHaveTextContent(
          "回执待复核",
        );
      });
      await waitFor(() => {
        const investmentBriefAfterRefresh = screen.getByTestId("macro-toolkit-investment-brief");
        const committeeReadinessAfterRefresh = within(investmentBriefAfterRefresh).getByTestId(
          "macro-toolkit-committee-readiness",
        );
        expect(committeeReadinessAfterRefresh).toHaveTextContent("策略供数回执待复核");
      });
      const investmentBriefAfterStrategyReceipt = await screen.findByTestId("macro-toolkit-investment-brief");
      const committeeReadinessAfterStrategyReceipt = within(investmentBriefAfterStrategyReceipt).getByTestId(
        "macro-toolkit-committee-readiness",
      );
      expect(committeeReadinessAfterStrategyReceipt).toHaveTextContent("待复核回执");
      expect(committeeReadinessAfterStrategyReceipt).toHaveTextContent("策略供数回执待复核");
      expect(committeeReadinessAfterStrategyReceipt).toHaveTextContent("复核策略供数回执");
      expect(committeeReadinessAfterStrategyReceipt).not.toHaveTextContent("待补全证据");
      expect(analysisCalls.some((item) => item?.detail === "full")).toBe(true);
      const strategySignoffAction = within(committeeReadinessAfterStrategyReceipt).getByRole("button", {
        name: "复核策略供数回执",
      });
      const committeePackAfterStrategyReceipt = within(investmentBriefAfterStrategyReceipt).getByLabelText("投委会材料包");
      expect(within(committeePackAfterStrategyReceipt).getByLabelText("投委会材料包-策略供数")).toHaveTextContent(
        "回执待复核",
      );

      await user.click(strategySignoffAction);

      const investmentBriefAfterStrategySignoff = await screen.findByTestId("macro-toolkit-investment-brief");
      const committeeReadinessAfterStrategySignoff = within(investmentBriefAfterStrategySignoff).getByTestId(
        "macro-toolkit-committee-readiness",
      );
      expect(committeeReadinessAfterStrategySignoff).toHaveTextContent("待确认闭环");
      expect(committeeReadinessAfterStrategySignoff).toHaveTextContent("工具执行待确认");
      expect(committeeReadinessAfterStrategySignoff).toHaveTextContent("复核工具执行结果");
      expect(committeeReadinessAfterStrategySignoff).not.toHaveTextContent("策略供数待确认");
      const summaryAfterStrategySignoff = within(investmentBriefAfterStrategySignoff).getByLabelText(
        "投委会提交包就绪摘要",
      );
      expect(summaryAfterStrategySignoff).toHaveTextContent(/提交包就绪度\s*3\/4/);
      expect(summaryAfterStrategySignoff).toHaveTextContent(/待复核回执\s*0/);
      const committeePackAfterStrategySignoff = within(investmentBriefAfterStrategySignoff).getByLabelText("投委会材料包");
      expect(within(committeePackAfterStrategySignoff).getByLabelText("投委会材料包-策略供数")).toHaveTextContent("已签核");

      const firstScreenToolAction = within(committeeReadinessAfterStrategySignoff).getByRole("button", {
        name: "复核工具执行结果",
      });
      await user.click(firstScreenToolAction);

      await waitFor(() => expect(scriptCalls).toHaveLength(1));
      await waitFor(() => {
        const investmentBriefAfterToolReceipt = screen.getByTestId("macro-toolkit-investment-brief");
        const committeeReadinessAfterToolReceipt = within(investmentBriefAfterToolReceipt).getByTestId(
          "macro-toolkit-committee-readiness",
        );
        expect(committeeReadinessAfterToolReceipt).toHaveTextContent("工具执行回执待复核");
      });
      const investmentBriefAfterToolReceipt = await screen.findByTestId("macro-toolkit-investment-brief");
      const committeeReadinessAfterToolReceipt = within(investmentBriefAfterToolReceipt).getByTestId(
        "macro-toolkit-committee-readiness",
      );
      expect(committeeReadinessAfterToolReceipt).toHaveTextContent("待复核回执");
      expect(committeeReadinessAfterToolReceipt).toHaveTextContent("复核工具执行回执");
      const committeePackAfterToolReceipt = within(investmentBriefAfterToolReceipt).getByLabelText("投委会材料包");
      expect(within(committeePackAfterToolReceipt).getByLabelText("投委会材料包-工具执行")).toHaveTextContent(
        "回执待复核",
      );

      const toolSignoffAction = within(committeeReadinessAfterToolReceipt).getByRole("button", {
        name: "复核工具执行回执",
      });
      await user.click(toolSignoffAction);

      const investmentBriefAfterToolSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
      const finalReadinessSummary = within(investmentBriefAfterToolSignoff).getByLabelText("投委会提交包就绪摘要");
      expect(finalReadinessSummary).toHaveTextContent(/提交包就绪度\s*4\/4/);
      expect(finalReadinessSummary).toHaveTextContent(/待复核回执\s*0/);
      const committeeReadinessAfterToolSignoff = within(investmentBriefAfterToolSignoff).getByTestId(
        "macro-toolkit-committee-readiness",
      );
      expect(committeeReadinessAfterToolSignoff).toHaveTextContent("可进入复核");
      const finalSignoff = within(investmentBriefAfterToolSignoff).getByLabelText("最终投委会签核态");
      expect(finalSignoff).toHaveTextContent("最终投委会签核态");
      expect(finalSignoff).toHaveTextContent("可提交复核");
      expect(finalSignoff).toHaveTextContent("主席复核");
      expect(finalSignoff).toHaveTextContent("提交包 4/4");
      expect(finalSignoff).toHaveTextContent("签核 3/3");
      expect(finalSignoff).toHaveTextContent("剩余风险 0");
      expect(finalSignoff).toHaveTextContent("待复核回执 0");
      const committeePackAfterToolSignoff = within(investmentBriefAfterToolSignoff).getByLabelText("投委会材料包");
      expect(within(committeePackAfterToolSignoff).getByLabelText("投委会材料包-工具执行")).toHaveTextContent("已签核");

      const evidenceBookAfterToolSignoff = await screen.findByTestId("macro-toolkit-evidence-book");
      const finalSubmissionGate = within(evidenceBookAfterToolSignoff).getByLabelText("投委会最终提交门禁");
      expect(finalSubmissionGate).toHaveTextContent("准入提交");
      expect(finalSubmissionGate).toHaveTextContent("当前结论");
      expect(finalSubmissionGate).toHaveTextContent("可提交复核");
      expect(finalSubmissionGate).toHaveTextContent("责任人");
      expect(finalSubmissionGate).toHaveTextContent("主席复核");
      expect(finalSubmissionGate).toHaveTextContent("提交包 4/4");
      expect(finalSubmissionGate).toHaveTextContent("签核 3/3");
      expect(finalSubmissionGate).toHaveTextContent("剩余风险 0");
      expect(finalSubmissionGate).toHaveTextContent("待复核回执 0");

      const finalPackReceipt = within(evidenceBookAfterToolSignoff).getByLabelText("投委会材料包封面回执");
      expect(finalPackReceipt).toHaveTextContent("可提交复核");
      expect(finalPackReceipt).toHaveTextContent("主席复核");
      expect(finalPackReceipt).toHaveTextContent("提交包 4/4");
      fireEvent.click(within(finalPackReceipt).getByRole("button", { name: "复制材料包摘要" }));
      await waitFor(() => expect(writeText).toHaveBeenCalledWith(expect.stringContaining("提交结论 可提交复核")));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("责任人 主席复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("提交包 4/4"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("签核 3/3"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("剩余风险 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("待复核回执 0"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
      if (originalWindowClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalWindowClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });

  it("renders from the workbench route", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    expect(
      await screen.findByRole("heading", { level: 1, name: "宏观工具" }),
    ).toBeInTheDocument();
    const cockpit = await screen.findByTestId("macro-toolkit-tailwind-cockpit");
    expect(cockpit).toHaveClass("macro-toolkit-cockpit--toolkit");
    const houseView = await screen.findByLabelText("宏观工具 House View");
    expect(houseView).toHaveTextContent("House View");
    expect(houseView).toHaveTextContent("投研观点");
    const governanceGate = await screen.findByTestId("macro-toolkit-governance-gate");
    expect(governanceGate).toHaveTextContent("Governance Gate");
    expect(governanceGate).toHaveTextContent("口径与数据闸门");
    expect(governanceGate).toHaveTextContent("证据覆盖");
    expect(governanceGate).toHaveTextContent("待处理数据");
    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    expect(investmentBrief).toHaveTextContent("Investment Committee Brief");
    expect(investmentBrief).toHaveTextContent("投资结论");
    expect(investmentBrief).toHaveTextContent("关键证据");
    expect(investmentBrief).toHaveTextContent("待复核缺口");
    expect(investmentBrief).toHaveTextContent("下一步动作");
    expect(investmentBrief).toHaveTextContent("投委会材料包");
    expect(investmentBrief).toHaveTextContent("结论底稿");
    expect(investmentBrief).toHaveTextContent("数据健康");
    expect(investmentBrief).toHaveTextContent("策略供数");
    expect(investmentBrief).toHaveTextContent("工具执行");
    expect(investmentBrief).toHaveTextContent("阻止提交");
    expect(investmentBrief).toHaveTextContent("已归档");
    expect(investmentBrief).toHaveTextContent("提交红线");
    expect(investmentBrief).toHaveTextContent("数据缺口阻止提交");
    expect(investmentBrief).toHaveTextContent("提交前动作");
    expect(investmentBrief).toHaveTextContent("先补齐高优先级输入，再复核观察结论。");
    expect(investmentBrief).toHaveTextContent("证据入口");
    expect(investmentBrief).toHaveTextContent("提交条件摘要");
    expect(investmentBrief).toHaveTextContent("1/4");
    expect(investmentBrief).toHaveTextContent("数据健康");
    expect(investmentBrief).toHaveTextContent("未通过");
    expect(investmentBrief).toHaveTextContent("证据口径");
    expect(investmentBrief).toHaveTextContent("已通过");
    expect(investmentBrief).toHaveTextContent("策略供数");
    expect(investmentBrief).toHaveTextContent("待确认");
    expect(investmentBrief).toHaveTextContent("工具执行");
    expect(investmentBrief).toHaveTextContent("待确认");
    expect(investmentBrief).toHaveTextContent("查看证据覆盖");
    expect(investmentBrief).toHaveTextContent("处理数据缺口");
    const mobileCommitteeStrip = within(investmentBrief).getByLabelText("投委会移动首屏摘要");
    expect(mobileCommitteeStrip).toHaveTextContent("提交判断");
    expect(mobileCommitteeStrip).toHaveTextContent("暂缓提交");
    expect(mobileCommitteeStrip).toHaveTextContent("硬阻断");
    expect(mobileCommitteeStrip).toHaveTextContent("高优先级");
    expect(mobileCommitteeStrip).toHaveTextContent("提交包");
    expect(mobileCommitteeStrip).toHaveTextContent("1/4");
    expect(mobileCommitteeStrip).toHaveTextContent("签核");
    expect(mobileCommitteeStrip).toHaveTextContent("1/3");
    expect(within(mobileCommitteeStrip).getByRole("link", { name: /硬阻断.*处理数据缺口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    const committeeDecisionMemo = within(investmentBrief).getByLabelText("投委会决策稿");
    expect(committeeDecisionMemo).toHaveTextContent("投委会决策稿");
    expect(committeeDecisionMemo).toHaveTextContent("结论");
    expect(committeeDecisionMemo).toHaveTextContent("暂缓提交");
    expect(committeeDecisionMemo).toHaveTextContent("阻断");
    expect(committeeDecisionMemo).toHaveTextContent("高优先级");
    expect(committeeDecisionMemo).toHaveTextContent("判断口径");
    expect(committeeDecisionMemo).toHaveTextContent("处理数据缺口");
    expect(committeeDecisionMemo).toHaveTextContent("主入口在首屏流水线");
    expect(committeeDecisionMemo).toHaveTextContent("放行条件");
    expect(committeeDecisionMemo).toHaveTextContent("提交包 1/4");
    expect(committeeDecisionMemo).toHaveTextContent("签核 1/3");
    expect(committeeDecisionMemo).toHaveTextContent("硬阻断 1");
    expect(within(committeeDecisionMemo).queryByRole("link", { name: /执行下一动作.*处理数据缺口/s })).not.toBeInTheDocument();
    const committeeReadiness = await screen.findByTestId("macro-toolkit-committee-readiness");
    expect(committeeReadiness).toHaveTextContent("投委会复核状态");
    expect(committeeReadiness).toHaveTextContent("暂缓提交");
    expect(committeeReadiness).toHaveTextContent("主要卡点");
    expect(committeeReadiness).toHaveTextContent("高优先级");
    expect(committeeReadiness).toHaveTextContent("3M NCD");
    expect(committeeReadiness).toHaveTextContent("M0041813");
    expect(committeeReadiness).toHaveTextContent("共 2 项");
    expect(committeeReadiness).toHaveTextContent("责任人");
    expect(committeeReadiness).toHaveTextContent("数据运营负责人");
    expect(committeeReadiness).toHaveTextContent("执行说明");
    expect(committeeReadiness).toHaveTextContent("首屏流水线承接");
    expect(within(committeeReadiness).queryByRole("link", { name: "处理数据缺口" })).not.toBeInTheDocument();
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    const currentExecutionTape = within(currentRepairStatus).getByLabelText("当前处理执行带");
    expect(currentExecutionTape).toHaveTextContent("执行带");
    expect(currentExecutionTape).toHaveTextContent("当前处理单");
    expect(currentExecutionTape).toHaveTextContent("责任人/SLA");
    expect(currentExecutionTape).toHaveTextContent("预期回执");
    expect(currentExecutionTape).toHaveTextContent("回执证据/签核");
    expect(currentExecutionTape).toHaveTextContent("审计状态");
    expect(currentRepairStatus).toHaveTextContent("当前处理状态");
    expect(currentRepairStatus).toHaveTextContent("当前处理");
    expect(currentRepairStatus).toHaveTextContent("3M NCD");
    expect(currentRepairStatus).toHaveTextContent("M0041813");
    expect(currentRepairStatus).toHaveTextContent("责任人");
    expect(currentRepairStatus).toHaveTextContent("数据运营负责人");
    expect(currentRepairStatus).toHaveTextContent("SLA");
    expect(currentRepairStatus).toHaveTextContent("T+0 盘前");
    expect(currentRepairStatus).toHaveTextContent("预期回执");
    expect(currentRepairStatus).toHaveTextContent("来源补齐回执");
    expect(currentRepairStatus).toHaveTextContent("回执状态");
    expect(currentRepairStatus).toHaveTextContent("待执行留痕");
    const repairTriage = within(currentRepairStatus).getByLabelText("投委会阻断分层");
    expect(repairTriage).toHaveTextContent("自动补齐");
    expect(repairTriage).toHaveTextContent("1 项");
    expect(repairTriage).toHaveTextContent("数据运营负责人");
    expect(repairTriage).toHaveTextContent("M0041813");
    expect(repairTriage).toHaveTextContent("人工升级");
    expect(repairTriage).toHaveTextContent("0 项");
    expect(repairTriage).toHaveTextContent("无待处理项");
    expect(repairTriage).toHaveTextContent("能力复核");
    expect(repairTriage).toHaveTextContent("1 项");
    expect(repairTriage).toHaveTextContent("宏观策略负责人");
    expect(repairTriage).toHaveTextContent("宏观领先指标");
    expect(currentRepairStatus).toHaveTextContent("审计状态");
    expect(currentRepairStatus).toHaveTextContent("主入口在首屏流水线");
    expect(within(currentRepairStatus).queryByRole("link", { name: "处理数据缺口" })).not.toBeInTheDocument();
    const committeeClosureRail = within(investmentBrief).getByLabelText("投委会闭环流水线");
    const committeeClosureAxis = within(committeeClosureRail).getByLabelText("投委会闭环状态轴");
    expect(committeeClosureAxis).toHaveTextContent("状态轴");
    expect(committeeClosureAxis).toHaveTextContent("处理");
    expect(committeeClosureAxis).toHaveTextContent("回执");
    expect(committeeClosureAxis).toHaveTextContent("签核");
    expect(committeeClosureAxis).toHaveTextContent("放行");
    expect(committeeClosureRail).toHaveTextContent("状态轴 · 辅助留痕");
    expect(committeeClosureRail).toHaveTextContent("1");
    expect(committeeClosureRail).toHaveTextContent("处理");
    expect(committeeClosureRail).toHaveTextContent("当前卡点");
    expect(committeeClosureRail).toHaveTextContent("主入口在首屏流水线");
    expect(committeeClosureRail).toHaveTextContent("2");
    expect(committeeClosureRail).toHaveTextContent("回执");
    expect(committeeClosureRail).toHaveTextContent("等待执行");
    expect(committeeClosureRail).toHaveTextContent("3");
    expect(committeeClosureRail).toHaveTextContent("签核");
    expect(committeeClosureRail).toHaveTextContent("等待回执");
    expect(committeeClosureRail).toHaveTextContent("4");
    expect(committeeClosureRail).toHaveTextContent("放行");
    expect(committeeClosureRail).toHaveTextContent("暂缓提交");
    expect(within(committeeClosureRail).queryByRole("link", { name: /处理.*处理数据缺口/s })).not.toBeInTheDocument();
    const dataHealthSignoffPack = within(investmentBrief).getByLabelText("数据健康签核证据包");
    expect(dataHealthSignoffPack).toHaveTextContent("数据健康签核包");
    expect(dataHealthSignoffPack).toHaveTextContent("阻断签核前置");
    expect(dataHealthSignoffPack).toHaveTextContent("最高优先级");
    expect(dataHealthSignoffPack).toHaveTextContent("高优先级");
    expect(dataHealthSignoffPack).toHaveTextContent("3M NCD");
    expect(dataHealthSignoffPack).toHaveTextContent("M0041813");
    expect(dataHealthSignoffPack).toHaveTextContent("来源覆盖");
    expect(dataHealthSignoffPack).toHaveTextContent("7/9");
    expect(dataHealthSignoffPack).toHaveTextContent("责任/SLA");
    expect(dataHealthSignoffPack).toHaveTextContent("数据运营负责人");
    expect(dataHealthSignoffPack).toHaveTextContent("T+0 盘前");
    expect(dataHealthSignoffPack).toHaveTextContent("签核前置");
    expect(dataHealthSignoffPack).toHaveTextContent("完成数据缺口回执 + 重读完整分析");
    expect(dataHealthSignoffPack).toHaveTextContent("不得由 CFFEX/商品/工具回执替代");
    expect(within(dataHealthSignoffPack).getByRole("link", { name: "打开数据健康证据" })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    const committeeReadinessSummary = within(investmentBrief).getByLabelText("投委会提交包就绪摘要");
    expect(committeeReadinessSummary).toHaveTextContent("提交包就绪度");
    expect(committeeReadinessSummary).toHaveTextContent("1/4");
    expect(committeeReadinessSummary).toHaveTextContent("签核就绪");
    expect(committeeReadinessSummary).toHaveTextContent("1/3");
    expect(committeeReadinessSummary).toHaveTextContent("硬阻断");
    expect(committeeReadinessSummary).toHaveTextContent("1");
    expect(committeeReadinessSummary).toHaveTextContent("待复核回执");
    expect(committeeReadinessSummary).toHaveTextContent("0");
    const committeeDecisionLanguage = within(investmentBrief).getByLabelText("投委会提交判断口径");
    expect(committeeDecisionLanguage).toHaveTextContent("提交判断口径");
    expect(committeeDecisionLanguage).toHaveTextContent("同源于提交判断矩阵");
    expect(committeeDecisionLanguage).toHaveTextContent("证据口径");
    expect(committeeDecisionLanguage).toHaveTextContent("已通过");
    expect(committeeDecisionLanguage).toHaveTextContent("数据健康");
    expect(committeeDecisionLanguage).toHaveTextContent("未通过");
    expect(committeeDecisionLanguage).toHaveTextContent("策略供数");
    expect(committeeDecisionLanguage).toHaveTextContent("待确认");
    expect(committeeDecisionLanguage).toHaveTextContent("工具执行");
    expect(within(committeeDecisionLanguage).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    const committeeChecklist = within(investmentBrief).getByLabelText("投委会提交条件摘要");
    expect(committeeChecklist).toHaveTextContent("提交条件摘要");
    expect(committeeChecklist).toHaveTextContent(/已通过\s*1/);
    expect(committeeChecklist).toHaveTextContent(/阻断\s*1/);
    expect(committeeChecklist).toHaveTextContent(/待确认\s*2/);
    expect(committeeChecklist).toHaveTextContent("主卡点");
    expect(committeeChecklist).toHaveTextContent("数据健康");
    expect(within(committeeChecklist).getByRole("link", { name: /主卡点.*数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expect(within(committeeChecklist).queryByRole("link", { name: /策略供数.*证据入口/s })).not.toBeInTheDocument();
    expect(await screen.findByText("投研观点")).toBeInTheDocument();
    expect(houseView).toHaveTextContent("主信号");
    expect((await screen.findAllByText("87.5%")).length).toBeGreaterThan(0);
    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    expect(cockpit.contains(investmentBrief)).toBe(true);
    expect(cockpit.contains(operationsConsole)).toBe(false);
    expect(operationsConsole).toHaveTextContent("Action Console");
    const committeeWorkQueue = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const committeeControl = within(committeeWorkQueue).getByLabelText("投委会提交作业控制");
    expect(committeeControl).toHaveTextContent("提交作业控制");
    expect(committeeControl).toHaveTextContent("牵头责任人");
    expect(committeeControl).toHaveTextContent("数据运营负责人");
    expect(committeeControl).toHaveTextContent("SLA");
    expect(committeeControl).toHaveTextContent("T+0 盘前");
    expect(committeeControl).toHaveTextContent("回执要求");
    expect(committeeControl).toHaveTextContent("完成回执 + 证据留痕");
    expect(committeeControl).toHaveTextContent("优先处理");
    expect(committeeControl).toHaveTextContent("数据健康");
    const signoffLane = within(committeeWorkQueue).getByLabelText("投委会签核轨道");
    expect(signoffLane).toHaveTextContent("签核轨道");
    expect(signoffLane).toHaveTextContent("宏观策略负责人");
    expect(signoffLane).toHaveTextContent("可签核");
    expect(signoffLane).toHaveTextContent("数据运营负责人");
    expect(signoffLane).toHaveTextContent("阻断签核");
    expect(signoffLane).toHaveTextContent("数据健康");
    expect(signoffLane).toHaveTextContent("权益策略负责人");
    expect(signoffLane).toHaveTextContent("待补证据");
    expect(signoffLane).toHaveTextContent("策略供数");
    expect(committeeWorkQueue).toHaveTextContent("执行入口");
    const submissionMatrix = within(committeeWorkQueue).getByLabelText("投委会提交判断矩阵");
    expect(submissionMatrix).toHaveTextContent("提交判断矩阵");
    expect(submissionMatrix).toHaveTextContent("条件");
    expect(submissionMatrix).toHaveTextContent("判断");
    expect(submissionMatrix).toHaveTextContent("责任人");
    expect(submissionMatrix).toHaveTextContent("证据");
    expect(submissionMatrix).toHaveTextContent("动作");
    expect(submissionMatrix).toHaveTextContent("证据口径");
    expect(submissionMatrix).toHaveTextContent("已通过");
    expect(submissionMatrix).toHaveTextContent("数据健康");
    expect(submissionMatrix).toHaveTextContent("未通过");
    expect(submissionMatrix).toHaveTextContent("策略供数");
    expect(submissionMatrix).toHaveTextContent("待确认");
    expect(submissionMatrix).toHaveTextContent("工具执行");
    expect(within(submissionMatrix).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expect(within(submissionMatrix).getByRole("link", { name: /工具执行.*动作入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-operations-actions",
    );
    const closureDesk = within(committeeWorkQueue).getByLabelText("投委会闭环作业台");
    expect(closureDesk).toHaveTextContent("问题定位");
    expect(closureDesk).toHaveTextContent("责任归属");
    expect(closureDesk).toHaveTextContent("证据动作");
    expect(closureDesk).toHaveTextContent("回执复核");
    expect(closureDesk).toHaveTextContent("提交判断");
    const submissionLedger = within(committeeWorkQueue).getByLabelText("投委会提交链路");
    expect(submissionLedger).toHaveTextContent("问题/条件");
    expect(submissionLedger).toHaveTextContent("提交判断");
    expect(submissionLedger).toHaveTextContent("下一步动作");
    expect(submissionLedger).toHaveTextContent("责任人");
    expect(submissionLedger).toHaveTextContent("SLA");
    expect(submissionLedger).toHaveTextContent("回执状态");
    expect(submissionLedger).toHaveTextContent("签核动作");
    const dataHealthLedgerItem = within(submissionLedger).getByLabelText("投委会提交链路-数据健康");
    expect(dataHealthLedgerItem).toHaveTextContent("数据运营负责人");
    expect(dataHealthLedgerItem).toHaveTextContent("T+0 盘前");
    expect(dataHealthLedgerItem).toHaveTextContent("待执行留痕");
    expect(dataHealthLedgerItem).toHaveTextContent("先执行");
    expect(within(committeeWorkQueue).getByRole("link", { name: /数据健康.*执行入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expect(within(committeeWorkQueue).getByRole("link", { name: /策略供数.*执行入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-strategy-detail",
    );
    expect(within(committeeWorkQueue).getByRole("link", { name: /工具执行.*执行入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-operations-actions",
    );
    const actionQueue = within(operationsConsole).getByTestId("macro-toolkit-action-queue");
    expect(actionQueue).toHaveTextContent("操作审计队列");
    expect(actionQueue).toHaveTextContent("0 条");
    expect(actionQueue).toHaveTextContent("暂无操作记录");
    expect(operationsConsole).toHaveTextContent("业务证据");
    expect(operationsConsole).toHaveTextContent("席位日期");
    expect(operationsConsole).toHaveTextContent("商品期货");
    expect(operationsConsole).toHaveTextContent("输出文件");
    expect(within(operationsConsole).getByRole("button", { name: /运行选中脚本/ })).toBeInTheDocument();
    expect(within(operationsConsole).getByRole("button", { name: /刷新股票策略明细/ })).toBeInTheDocument();
    expect(within(operationsConsole).getByRole("button", { name: /刷新席位明细/ })).toBeInTheDocument();
    expect(within(operationsConsole).getByRole("button", { name: /预估明细刷新/ })).toBeInTheDocument();
    expect(within(operationsConsole).queryByRole("button", { name: /刷新股票数据/ })).not.toBeInTheDocument();
    expect(within(operationsConsole).queryByRole("button", { name: /^reload 刷新席位$/ })).not.toBeInTheDocument();
    expect(within(operationsConsole).queryByRole("button", { name: /预估商品期货/ })).not.toBeInTheDocument();
    const detailDensity = await screen.findByTestId("macro-toolkit-detail-density");
    const macroPage = await screen.findByTestId("macro-toolkit-page");
    expect(detailDensity).toHaveTextContent("详情默认精简");
    expect(detailDensity).toHaveTextContent("深度证据仍可展开");
    const detailQueue = within(detailDensity).getByLabelText("深度证据摘要队列");
    expect(detailQueue).toHaveTextContent("策略证据");
    expect(detailQueue).toHaveTextContent("Crisis Score");
    expect(detailQueue).toHaveTextContent("Hason");
    expect(detailQueue).toHaveTextContent("脚本与产物");
    expect(within(detailQueue).getByRole("link", { name: /策略证据.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-strategy-detail",
    );
    expect(within(detailQueue).getByRole("link", { name: /Crisis Score.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-analysis-detail",
    );
    expect(within(detailQueue).getByRole("link", { name: /脚本与产物.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-script-artifact-detail",
    );
    expect(macroPage).toHaveClass("macro-toolkit-page--details-compact");
    await user.click(within(detailDensity).getByRole("button", { name: "全部展开" }));
    expect(macroPage).toHaveClass("macro-toolkit-page--details-expanded");
    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    expect(evidenceBook).toHaveTextContent("Evidence Book");
    expect(evidenceBook).toHaveTextContent("结论支撑");
    expect(evidenceBook).toHaveTextContent("数据缺口");
    expect(evidenceBook).toHaveTextContent("复核角色");
    expect(evidenceBook).toHaveTextContent("证据入口");
    expect(evidenceBook).toHaveTextContent("主信号");
    expect(evidenceBook).toHaveTextContent("数据健康");
    expect(evidenceBook).toHaveTextContent("策略供数");
    expect(evidenceBook).toHaveTextContent("工具执行");
    expect(within(evidenceBook).getByRole("link", { name: /主信号.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-analysis-detail",
    );
    expect(within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expect(within(evidenceBook).getByRole("link", { name: /策略供数.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-strategy-detail",
    );
    expect(within(evidenceBook).getByRole("link", { name: /工具执行.*证据入口/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-tool-execution-detail",
    );
    const dataHealth = await screen.findByLabelText("数据健康总览");
    expectElementBefore(cockpit, investmentBrief);
    expectElementBefore(investmentBrief, governanceGate);
    expectElementBefore(governanceGate, operationsConsole);
    expectElementBefore(operationsConsole, evidenceBook);
    expectElementBefore(evidenceBook, dataHealth);
    expect(dataHealth).toHaveTextContent("指标覆盖");
    expect(dataHealth).toHaveTextContent("7/8");
    expect(dataHealth).toHaveTextContent("来源覆盖");
    expect(dataHealth).toHaveTextContent("7/9");
    expect(dataHealth).toHaveTextContent("最新来源日期");
    expect(dataHealth).toHaveTextContent("2026-04-30");
    expect(dataHealth).toHaveTextContent("能力降级");
    expect(dataHealth).toHaveTextContent("1");
    expect(dataHealth).toHaveTextContent("待处理数据项");
    expect(dataHealth).toHaveTextContent("M0041813");
    expect(dataHealth).toHaveTextContent("补齐 M0041813 后重新运行完整宏观分析");
    expect(dataHealth).toHaveTextContent("宏观领先指标");
    expect(dataHealth).toHaveTextContent("PMI_MISSING");
    expect(dataHealth).toHaveTextContent("重新完整分析");
    expect(dataHealth).toHaveTextContent("M0041813");
    const boundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    expect(boundary).toHaveTextContent("分析/工具口径");
    expect(boundary).toHaveTextContent("非正式口径");
    expect(boundary).toHaveTextContent("macro_toolkit.analysis");
    expect(boundary).toHaveTextContent("rv_macro_toolkit_ui_v1");
    const hasonStrategy = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategy).toHaveTextContent("Hason");
    expect(hasonStrategy).toHaveTextContent("analytical");
    expect(hasonStrategy).toHaveTextContent("observation-only");
    expect(hasonStrategy).toHaveTextContent("4/5");
    expect(hasonStrategy).toHaveTextContent("Module gaps");
    expect(hasonStrategy).toHaveTextContent("1 partial");
    expect(hasonStrategy).toHaveTextContent("1 missing script");
    expect(await screen.findByTestId("macro-toolkit-hason-module-market_state")).toHaveTextContent(
      "market_state",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-module-market_state")).toHaveTextContent(
      "script-chain complete",
    );
    const allocationModule = await screen.findByTestId("macro-toolkit-hason-module-allocation");
    expect(allocationModule).toHaveTextContent("script-chain partial");
    expect(allocationModule).toHaveTextContent("risk_parity_cn");
    expect(allocationModule).toHaveTextContent("rebalance_cn");
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "final_signal.csv",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "stale",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "CSV content date",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "content 2026-04-29",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).not.toHaveTextContent(
      "csv_content",
    );
    expect(
      await screen.findByLabelText("宏观工具投研总览"),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "核心信号" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" }),
    ).toBeInTheDocument();
    expect((await screen.findAllByText("橙色风险")).length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText("总仓位上限30%，高位主题只减不加，午后不做冲高追买。")).toBeInTheDocument();
    expect(await screen.findByText("上涨家数")).toBeInTheDocument();
    expect(await screen.findByText("跌停家数")).toBeInTheDocument();
    expect(await screen.findByText("触发规则")).toBeInTheDocument();
    expect(await screen.findByText("观察条件")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "指标矩阵" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "功能补齐方案" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "CFFEX席位状态" }),
    ).toBeInTheDocument();
    const cffexSection = requireClosestElement(
      screen.getByRole("heading", { level: 2, name: "CFFEX席位状态" }).closest(".macro-toolkit-section") as HTMLElement | null,
      "macro toolkit cffex section",
    );
    expect(within(cffexSection).getByRole("button", { name: /刷新席位明细/ })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "脚本产物" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "未纳入脚本" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "脚本注册表" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "功能结果" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "策略展示" }),
    ).toBeInTheDocument();
    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 0/4");
    expect(strategySupply).toHaveTextContent("部分链路 0");
    expect(strategySupply).toHaveTextContent("降级 0");
    expect(strategySupply).toHaveTextContent("样例 4");
    expect(strategySupply).toHaveTextContent("股票历史 2026-04-30");
    expect(strategySupply).toHaveTextContent("因子快照 2026-04-30");
    const movingAverageTitle = await screen.findByText("移动均线策略");
    const movingAverageCard = movingAverageTitle.closest(".macro-toolkit-strategy-card");
    expect(movingAverageCard).not.toBeNull();
    expect(movingAverageCard).toHaveTextContent("SYNTHETIC_SAMPLE_ONLY");
    expect(movingAverageCard).toHaveTextContent("sample_only");
    expect(movingAverageCard).toHaveTextContent("价格来源缺失");
    expect(movingAverageCard).toHaveTextContent("因子来源缺失");
    expect(await screen.findByText("多因子选股")).toBeInTheDocument();
    const strategySection = requireClosestElement(
      screen.getByRole("heading", { level: 2, name: "策略展示" }).closest(".macro-toolkit-section") as HTMLElement | null,
      "macro toolkit strategy section",
    );
    expect(within(strategySection).getByRole("button", { name: /刷新股票策略明细/ })).toBeInTheDocument();
    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已授权");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
    expect(await screen.findByText("低拥挤度择时多因子")).toBeInTheDocument();
    expect((await screen.findAllByText(/M7/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/M16/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("signal_aggregator")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("equity_strategies")).length).toBeGreaterThan(0);
  });

  it("renders macro observation as a read-only analysis route without operations controls", async () => {
    renderWorkbenchApp(["/macro-observation"]);

    const cockpit = await screen.findByTestId("macro-toolkit-tailwind-cockpit");
    expect(cockpit).toBeInTheDocument();
    const houseView = requireClosestElement(
      cockpit.querySelector("[data-testid='macro-toolkit-house-view']"),
      "macro observation house view",
    );
    const conclusion = requireClosestElement(
      cockpit.querySelector(".macro-toolkit-cockpit__conclusion"),
      "macro observation conclusion",
    );
    const observationLoop = requireClosestElement(
      cockpit.querySelector("[aria-label='宏观观察首屏闭环']"),
      "macro observation first-screen loop",
    );
    const contractBoundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    const readOnlyBoundary = await screen.findByTestId("macro-observation-readonly-boundary");
    expect(cockpit).toHaveClass("macro-toolkit-cockpit--observation");
    expect(houseView).toHaveTextContent("观察结论");
    expect(houseView).not.toHaveTextContent("House View");
    expect(houseView).toHaveTextContent("只读宏观判断");
    expect(conclusion).toHaveTextContent("投研观点");
    expect(houseView.contains(conclusion)).toBe(true);
    expect(houseView.contains(observationLoop)).toBe(true);
    expect(observationLoop).toHaveTextContent("观察闭环");
    expect(observationLoop).toHaveTextContent("当前判断");
    expect(observationLoop).toHaveTextContent("关键证据");
    expect(observationLoop).toHaveTextContent("使用边界");
    expect(observationLoop).toHaveTextContent("不作为正式投资信号");
    expect(houseView.querySelector(".macro-toolkit-observation-boundaries")).not.toBeInTheDocument();
    expect(houseView).toHaveTextContent("已接入");
    expect(houseView).not.toHaveTextContent("choice + tushare");
    expect(contractBoundary).toHaveTextContent("宏观分析结果");
    expect(contractBoundary).not.toHaveTextContent("macro_toolkit.analysis");
    expect(contractBoundary).not.toHaveTextContent("rv_macro_toolkit_ui_v1");
    const signalRiskComparison = await screen.findByLabelText("信号风险对照");
    expect(signalRiskComparison).toHaveTextContent("核心信号");
    expect(signalRiskComparison).toHaveTextContent("风险预警");
    expect(signalRiskComparison).not.toHaveTextContent("风险待确认风险待确认");
    expect(signalRiskComparison).not.toHaveTextContent("上涨家数待确认跌停家数待确认成交额/20日待确认");
    expect(signalRiskComparison).toHaveTextContent("观察判断");
    expect(signalRiskComparison).toHaveTextContent("不作为正式投资信号");
    expect(screen.queryByRole("heading", { level: 2, name: "核心信号" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "市场踩踏风险" })).not.toBeInTheDocument();
    expect(readOnlyBoundary).toHaveTextContent("只读宏观观察");
    expect(readOnlyBoundary).not.toHaveTextContent("read-only");
    expect(readOnlyBoundary).not.toHaveTextContent("/macro-toolkit");
    const evidencePanel = await screen.findByLabelText("宏观观察证据与限制");
    const runtimeStrip = await screen.findByLabelText("宏观工具运行状态");
    const dataHealthSummary = await screen.findByLabelText("数据健康摘要");
    const readiness = await screen.findByLabelText("宏观工具投研总览");
    const evidenceBoundaries = requireClosestElement(
      evidencePanel.querySelector(".macro-toolkit-observation-boundaries"),
      "macro observation evidence boundaries",
    );
    expect(evidenceBoundaries.contains(contractBoundary)).toBe(true);
    expect(evidenceBoundaries.contains(readOnlyBoundary)).toBe(true);
    expect(evidencePanel).toHaveTextContent("观察证据与限制");
    expect(evidencePanel).toHaveTextContent("运行状态");
    expect(evidencePanel).toHaveTextContent("数据健康");
    expect(evidencePanel).toHaveTextContent("投研总览");
    expect(runtimeStrip).toHaveTextContent("完整分析");
    expect(runtimeStrip).not.toHaveTextContent("M7-M16");
    expect(runtimeStrip).not.toHaveTextContent("capability_results");
    expect(runtimeStrip).not.toHaveTextContent("功能结果");
    expect(runtimeStrip).not.toHaveTextContent("功能补齐方案");
    expect(evidencePanel).not.toHaveTextContent("analytical");
    expect(evidencePanel).not.toHaveTextContent("final_signal.csv");
    expect(evidencePanel).not.toHaveTextContent("signal_aggre");
    expect(evidencePanel).not.toHaveTextContent("脚本产物");
    expect(evidencePanel).not.toHaveTextContent("a_share_risk");
    expect(dataHealthSummary).toHaveTextContent("数据健康摘要");
    expect(dataHealthSummary).toHaveTextContent("观察复核提示");
    expect(dataHealthSummary).not.toHaveTextContent("待处理数据项");
    expect(dataHealthSummary).not.toHaveTextContent("capabilities");
    expect(readiness).toHaveTextContent("主信号");
    expect(readiness).toHaveTextContent("证据边界");
    expect(readiness).not.toHaveTextContent("模型结果");
    expect(readiness).not.toHaveTextContent("功能输出");
    expect(readiness).not.toHaveTextContent("脚本产物");
    expect(houseView).not.toHaveTextContent("页面/API");
    expect(evidencePanel.contains(runtimeStrip)).toBe(true);
    expect(evidencePanel.contains(dataHealthSummary)).toBe(true);
    expect(evidencePanel.contains(readiness)).toBe(true);
    const investmentEvidenceSection = await screen.findByTestId("macro-toolkit-investment-evidence-detail");
    const sectionOrder = Array.from(document.querySelectorAll(".macro-toolkit-section"));
    const comparisonSection = requireClosestElement(
      signalRiskComparison.closest(".macro-toolkit-section"),
      "macro observation signal-risk comparison section",
    );
    expect(sectionOrder.indexOf(comparisonSection)).toBeLessThan(sectionOrder.indexOf(investmentEvidenceSection));
    expect(comparisonSection).not.toHaveTextContent("总览核心信号");
    expect(comparisonSection).not.toHaveTextContent("预警市场踩踏风险");
    expect(investmentEvidenceSection).not.toHaveTextContent("投研投研证据摘要");
    expect(
      within(investmentEvidenceSection).getAllByText("投研证据摘要", { selector: "span,h2" }),
    ).toHaveLength(1);
    expect(comparisonSection).not.toHaveTextContent("signals");
    expect(comparisonSection).not.toHaveTextContent("risk");
    expect(investmentEvidenceSection).not.toHaveTextContent("evidence");
    expect(comparisonSection).toHaveTextContent("把主信号和市场踩踏风险放在同一张观察卡里");
    expect(comparisonSection).not.toHaveTextContent("Choice/Tushare");
    expect(comparisonSection).not.toHaveTextContent("脚本产物");
    expect(comparisonSection.querySelector(".macro-toolkit-signal-grid")).not.toBeInTheDocument();
    expect(comparisonSection.querySelector(".macro-toolkit-a-share-risk")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "策略展示" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "指标矩阵" })).not.toBeInTheDocument();
    expect(investmentEvidenceSection).toHaveTextContent("证据支撑");
    expect(investmentEvidenceSection).toHaveTextContent("策略证据");
    expect(investmentEvidenceSection).toHaveTextContent("指标证据");
    expect(investmentEvidenceSection).toHaveTextContent("观察边界");
    expect(investmentEvidenceSection).toHaveTextContent("影子组合只读");
    expect(investmentEvidenceSection).toHaveTextContent("非正式投资信号");
    expect(investmentEvidenceSection).toHaveTextContent("数据源已确认");
    expect(investmentEvidenceSection).toHaveTextContent("完整审计留在工具页");
    expect(investmentEvidenceSection).not.toHaveTextContent("进入正式候选评审");
    expect(investmentEvidenceSection).not.toHaveTextContent("正式参照");
    expect(investmentEvidenceSection).not.toHaveTextContent("评审动作");
    expect(investmentEvidenceSection).not.toHaveTextContent("READ_ONLY_SHADOW_NOT_PRODUCTION");
    expect(investmentEvidenceSection).not.toHaveTextContent("rv_macro_toolkit_shadow_portfolio_v1");
    expect(investmentEvidenceSection).not.toHaveTextContent("choice_stock_daily_observation");
    expect(investmentEvidenceSection).not.toHaveTextContent("choice_stock_factor_snapshot");
    expect(investmentEvidenceSection).not.toHaveTextContent("sv_choice_stock");
    expect(investmentEvidenceSection).not.toHaveTextContent("vv_choice_tushare_stock");
    expect(investmentEvidenceSection.querySelector(".macro-toolkit-shadow-report")).not.toBeInTheDocument();
    expect(investmentEvidenceSection.querySelector(".macro-toolkit-strategy-card")).not.toBeInTheDocument();
    expect(investmentEvidenceSection.querySelector(".ant-table")).not.toBeInTheDocument();
    expect(investmentEvidenceSection).not.toHaveTextContent("rows");
    expect(investmentEvidenceSection).not.toHaveTextContent("tushare");
    expect(investmentEvidenceSection).not.toHaveTextContent("CA.CSI300");
    expect(investmentEvidenceSection).not.toHaveTextContent("CA.COPPER");
    const evidenceTrace = await screen.findByLabelText("宏观观察证据追踪");
    const evidenceTraceSummary = await screen.findByLabelText("证据追踪摘要");
    expect(evidenceTrace.contains(evidenceTraceSummary)).toBe(true);
    expect(evidenceTraceSummary).toHaveTextContent("数据健康");
    expect(evidenceTraceSummary).toHaveTextContent("指标覆盖");
    expect(evidenceTraceSummary).toHaveTextContent("能力证据");
    expect(evidenceTraceSummary).toHaveTextContent("6 项证据");
    expect(evidenceTraceSummary).toHaveTextContent("不是正式投资信号");
    expect(evidenceTraceSummary).toHaveTextContent("观察框架");
    expect(evidenceTraceSummary).toHaveTextContent("观察就绪");
    expect(evidenceTraceSummary).not.toHaveTextContent("0 / 0/0");
    expect(evidenceTraceSummary).not.toHaveTextContent("另 1 项");
    expect(evidenceTraceSummary).not.toHaveTextContent("延后证据 / 延后证据");
    expect(evidenceTraceSummary).not.toHaveTextContent("待处理数据项");
    expect(evidenceTraceSummary).not.toHaveTextContent("页面/API");
    expect((evidenceTraceSummary.textContent?.match(/完整分析后确认/g) ?? []).length).toBeLessThanOrEqual(1);
    expect(evidenceTraceSummary.querySelector(".macro-toolkit-data-health")).not.toBeInTheDocument();
    expect(evidenceTraceSummary.querySelector(".macro-toolkit-hason-strategy")).not.toBeInTheDocument();
    expect(evidenceTraceSummary.querySelector("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "功能结果" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "功能补齐方案" })).not.toBeInTheDocument();

    expect(screen.queryByTestId("macro-toolkit-governance-gate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("macro-toolkit-operations-console")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新席位/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新股票数据/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新席位明细/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新股票明细/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新股票策略明细/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "脚本注册表" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "运行结果" })).not.toBeInTheDocument();
  });

  it("keeps toolkit data-health deferred tickets in committee language", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              { key: "capabilities", label: "capabilities", status: "deferred" },
              { key: "capability_results", label: "capability_results", status: "deferred" },
              { key: "source_checks", label: "source_checks", status: "deferred" },
            ],
          },
          capability_results: [],
          capabilities: [],
          source_checks: [],
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "core",
            source_coverage: {
              hit_count: 0,
              total_count: 0,
              hit_rate: null,
              latest_date: null,
              deferred: true,
              missing_aliases: [],
            },
            capability_results: {
              complete: 0,
              degraded: 0,
              unavailable: 0,
              total_count: 0,
              deferred: true,
            },
            capability_plan: {
              ready_count: 0,
              wired_count: 0,
              total_count: 0,
              deferred: true,
            },
            deferred_sections: ["capabilities", "capability_results", "source_checks"],
            repair_items: [
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:capabilities",
                alias: null,
                label: "capabilities",
                suggested_action: "打开完整分析后确认 capabilities，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:capability_results",
                alias: null,
                label: "capability_results",
                suggested_action: "打开完整分析后确认 capability_results，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:source_checks",
                alias: null,
                label: "source_checks",
                suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const dataHealthDetail = await screen.findByTestId("macro-toolkit-data-health-detail");
    const repairList = within(dataHealthDetail).getByLabelText("待处理数据项");

    expect(repairList).toHaveTextContent("能力边界");
    expect(repairList).toHaveTextContent("能力结果");
    expect(repairList).toHaveTextContent("来源证据");
    expect(repairList).toHaveTextContent("打开完整分析后确认这部分证据，不把首屏延后加载当作缺失。");
    expect(repairList).not.toHaveTextContent("capabilities");
    expect(repairList).not.toHaveTextContent("capability_results");
    expect(repairList).not.toHaveTextContent("source_checks");
  });

  it("keeps deferred blockers out of first-screen committee summaries", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [{ key: "capabilities", label: "capabilities", status: "deferred" }],
          },
          capability_results: [],
          capabilities: [],
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "core",
            repair_items: [
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:capabilities",
                alias: null,
                label: "capabilities",
                suggested_action: "打开完整分析后确认 capabilities，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const houseView = await screen.findByTestId("macro-toolkit-house-view");
    const reviewFlow = await screen.findByLabelText("投委会证据包审阅流");
    const signoffPack = within(investmentBrief).getByLabelText("数据健康签核证据包");

    expect(houseView).toHaveTextContent("低优先级 · 能力边界 · 共 1 项");
    expect(reviewFlow).toHaveTextContent("低优先级 · 能力边界 · 共 1 项");
    expect(signoffPack).toHaveTextContent("低优先级");
    expect(signoffPack).toHaveTextContent("能力边界");
    expect(houseView).not.toHaveTextContent("capabilities");
    expect(reviewFlow).not.toHaveTextContent("capabilities");
    expect(signoffPack).not.toHaveTextContent("capabilities");
  });

  it("keeps missing macro observation risk evidence as one concise gap", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          a_share_risk: undefined,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const signalRiskComparison = await waitFor(() => {
      const comparisons = screen.getAllByLabelText("信号风险对照");
      const resolvedComparison = comparisons.find((item) => item.textContent?.includes("风险证据延后确认"));
      expect(resolvedComparison).toBeInstanceOf(HTMLElement);
      return resolvedComparison as HTMLElement;
    });
    expect(signalRiskComparison).toHaveTextContent("风险预警");
    expect(signalRiskComparison).toHaveTextContent("风险预警证据缺口完整分析后确认风险边界");
    expect(signalRiskComparison).toHaveTextContent("需合并 A股宽度、跌停和成交压力。");
    expect(signalRiskComparison).not.toHaveTextContent("风险预警证据缺口风险证据延后确认");
    expect(signalRiskComparison).not.toHaveTextContent("风险证据延后确认完整分析后合并");
    expect(signalRiskComparison).not.toHaveTextContent("风险预警延后确认风险证据延后确认");
    expect(signalRiskComparison).not.toHaveTextContent("风险预警延后确认完整分析后复核");
    expect(signalRiskComparison).not.toHaveTextContent("待确认待完整分析");
    expect(signalRiskComparison).not.toHaveTextContent("风险证据待完整分析确认");
    expect(signalRiskComparison).not.toHaveTextContent("A股宽度、跌停和成交压力完整分析后再合并判断。");
    expect(signalRiskComparison).not.toHaveTextContent("风险待确认风险待确认");
    expect(signalRiskComparison).not.toHaveTextContent("上涨家数待确认跌停家数待确认成交额/20日待确认");
    expect(signalRiskComparison).not.toHaveTextContent("上涨家数");
    expect(signalRiskComparison).not.toHaveTextContent("跌停家数");
    expect(signalRiskComparison).not.toHaveTextContent("成交额/20日");
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
  });

  it("lets the Governance Gate drill into audit evidence and highlights the selected detail", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    const governanceGate = await screen.findByTestId("macro-toolkit-governance-gate");
    const focus = await screen.findByTestId("macro-toolkit-governance-focus");
    expect(focus).toHaveTextContent("审计焦点");
    expect(focus).toHaveTextContent("证据覆盖");
    expect(governanceGate).toHaveTextContent("non-formal");
    expect(governanceGate).toHaveTextContent("data-pending");
    const evidenceGate = within(governanceGate).getByRole("link", { name: /证据覆盖/ });
    const dataGate = within(governanceGate).getByRole("link", { name: /待处理数据/ });
    const capabilityGate = within(governanceGate).getByRole("link", { name: /能力闭环/ });

    expect(evidenceGate).toHaveAttribute("href", "#macro-toolkit-analysis-detail");
    expect(dataGate).toHaveAttribute("href", "#macro-toolkit-data-health-detail");
    expect(capabilityGate).toHaveAttribute("href", "#macro-toolkit-tool-execution-detail");

    await user.click(dataGate);

    expect(await screen.findByTestId("macro-toolkit-governance-focus")).toHaveTextContent("数据健康");
    expect(dataGate).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(capabilityGate);

    expect(await screen.findByTestId("macro-toolkit-governance-focus")).toHaveTextContent("能力闭环");
    expect(capabilityGate).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-tool-execution-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );
  });

  it("keeps script artifacts out of the Evidence Book primary signal", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const scriptArtifactCard = {
      key: "outputs",
      title: "脚本产物",
      stance: "已生成",
      tone: "positive",
      score: 99,
      evidence: ["final_signal.csv"],
    } as const;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          signal_cards: [
            scriptArtifactCard,
            ...analysisEnvelope.result.signal_cards.filter((card) => card.key !== "outputs"),
          ],
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const primarySignalEntry = within(evidenceBook).getByRole("link", { name: /主信号.*证据入口/s });
    expect(primarySignalEntry).toHaveTextContent("流动性");
    expect(primarySignalEntry).toHaveTextContent("偏松");
    expect(primarySignalEntry).not.toHaveTextContent("脚本产物");
    expect(primarySignalEntry).not.toHaveTextContent("final_signal.csv");
  });

  it("lets the Evidence Book focus the linked evidence detail", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const primarySignalEntry = within(evidenceBook).getByRole("link", { name: /主信号.*证据入口/s });
    const dataHealthEntry = within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s });
    const toolExecutionEntry = within(evidenceBook).getByRole("link", { name: /工具执行.*证据入口/s });

    await user.click(primarySignalEntry);

    expect(primarySignalEntry).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-analysis-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(dataHealthEntry);

    expect(primarySignalEntry).not.toHaveAttribute("aria-current");
    expect(dataHealthEntry).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
    expect(screen.getByTestId("macro-toolkit-tool-execution-detail")).not.toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(toolExecutionEntry);

    expect(dataHealthEntry).not.toHaveAttribute("aria-current");
    expect(toolExecutionEntry).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-tool-execution-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).not.toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
  });

  it("lets the Investment Committee Brief focus its linked evidence detail", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"]);

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    const committeePack = within(investmentBrief).getByLabelText("投委会材料包");
    const committeeReadiness = await screen.findByTestId("macro-toolkit-committee-readiness");
    const committeeWorkQueue = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const dataGapAction = within(investmentBrief).getByRole("link", { name: /流水线下一步.*处理数据缺口/s });
    const redlineEvidenceAction = within(investmentBrief).getByRole("link", { name: "证据入口" });
    const evidenceAction = within(investmentBrief).getByRole("link", { name: "查看证据覆盖" });
    const decisionLanguage = within(investmentBrief).getByLabelText("投委会提交判断口径");
    const decisionStrategyAction = within(decisionLanguage).getByRole("link", { name: /策略供数/ });
    const decisionToolAction = within(decisionLanguage).getByRole("link", { name: /工具执行/ });
    const queueDataHealthAction = within(committeeWorkQueue).getByRole("link", { name: /数据健康.*先完成数据缺口复核/s });
    const queueStrategyAction = within(committeeWorkQueue).getByRole("link", { name: /策略供数.*确认策略供数链路/s });
    const queueToolAction = within(committeeWorkQueue).getByRole("link", { name: /工具执行.*复核工具执行结果/s });
    const queueDataHealthExecution = within(committeeWorkQueue).getByRole("link", { name: /数据健康.*执行入口/s });
    const queueStrategyExecution = within(committeeWorkQueue).getByRole("link", { name: /策略供数.*执行入口/s });
    const queueToolExecution = within(committeeWorkQueue).getByRole("link", { name: /工具执行.*执行入口/s });
    const packDataHealthAction = within(committeePack).getByLabelText("投委会材料包-数据健康");
    const packStrategyAction = within(committeePack).getByLabelText("投委会材料包-策略供数");
    const dataHealthEvidenceRow = within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s });
    const primaryEvidenceRow = within(evidenceBook).getByRole("link", { name: /主信号.*证据入口/s });
    const strategyEvidenceRow = within(evidenceBook).getByRole("link", { name: /策略供数.*证据入口/s });
    const toolExecutionEvidenceRow = within(evidenceBook).getByRole("link", { name: /工具执行.*证据入口/s });

    expect(committeeReadiness).toHaveTextContent("执行说明");
    expect(committeeReadiness).toHaveTextContent("首屏流水线承接");
    expect(within(committeeReadiness).queryByRole("link", { name: "处理数据缺口" })).not.toBeInTheDocument();
    expect(redlineEvidenceAction).toHaveAttribute("href", "#macro-toolkit-data-health-detail");

    await user.click(dataGapAction);

    expect(dataGapAction).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(primaryEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
    expect(screen.getByTestId("macro-toolkit-analysis-detail")).not.toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
    const focusedRepairItem = within(screen.getByTestId("macro-toolkit-data-health-detail")).getByLabelText(
      "当前处理数据项-M0041813",
    );
    expect(focusedRepairItem).toHaveAttribute("aria-current", "true");
    expect(focusedRepairItem).toHaveTextContent("3M NCD");
    expect(focusedRepairItem).toHaveTextContent("需要补齐来源数据");
    const focusedRepairTicket = within(screen.getByTestId("macro-toolkit-data-health-detail")).getByLabelText(
      "当前处理单-M0041813",
    );
    expect(focusedRepairTicket).toHaveTextContent("责任人");
    expect(focusedRepairTicket).toHaveTextContent("数据运营负责人");
    expect(focusedRepairTicket).toHaveTextContent("SLA");
    expect(focusedRepairTicket).toHaveTextContent("T+0 盘前");
    expect(focusedRepairTicket).toHaveTextContent("预期回执");
    expect(focusedRepairTicket).toHaveTextContent("来源补齐回执");
    expect(focusedRepairTicket).toHaveTextContent("提交影响");
    expect(focusedRepairTicket).toHaveTextContent("暂缓提交");

    await user.click(redlineEvidenceAction);

    expect(redlineEvidenceAction).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(primaryEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(decisionStrategyAction);

    expect(decisionStrategyAction).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-strategy-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(decisionToolAction);

    expect(decisionToolAction).toHaveAttribute("aria-current", "true");
    expect(toolExecutionEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-tool-execution-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(evidenceAction);

    expect(evidenceAction).toHaveAttribute("aria-current", "true");
    expect(dataGapAction).not.toHaveAttribute("aria-current");
    expect(primaryEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-analysis-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).not.toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(packDataHealthAction);

    expect(packDataHealthAction).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(primaryEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(packStrategyAction);

    expect(packStrategyAction).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-strategy-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(queueDataHealthAction);

    expect(queueDataHealthAction).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(queueStrategyAction);

    expect(queueStrategyAction).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(dataHealthEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-strategy-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(queueToolAction);

    expect(queueToolAction).toHaveAttribute("aria-current", "true");
    expect(toolExecutionEvidenceRow).toHaveAttribute("aria-current", "true");
    expect(strategyEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-tool-execution-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(queueDataHealthExecution);

    expect(queueDataHealthExecution).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).toHaveClass(
      "macro-toolkit-anchor-target--active",
    );

    await user.click(queueStrategyExecution);

    expect(queueStrategyExecution).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-strategy-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(queueToolExecution);

    expect(queueToolExecution).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-operations-actions")).toHaveClass(
      "macro-toolkit-operations-console__actions--active",
    );
  });

  it("keeps the no-gap committee action aligned with the tool execution desk", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const completeCapabilityResults = analysisEnvelope.result.capability_results.map((result) => ({
      ...result,
      status: "complete" as const,
      warnings: [],
    }));
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "full",
            deferred_sections: [],
          },
          capability_results: completeCapabilityResults,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "full",
            capability_results: {
              ...analysisEnvelope.result.data_health!.capability_results,
              complete: completeCapabilityResults.length,
              degraded: 0,
              unavailable: 0,
              total_count: completeCapabilityResults.length,
              deferred: false,
            },
            repair_items: [],
          },
        },
      }),
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const committeeReadiness = await screen.findByTestId("macro-toolkit-committee-readiness");
    const evidenceBook = await screen.findByTestId("macro-toolkit-evidence-book");
    const committeeAction = within(committeeReadiness).getByRole("button", { name: "复核工具执行结果" });
    const toolExecutionEvidenceRow = within(evidenceBook).getByRole("link", { name: /工具执行.*证据入口/s });
    const dataHealthEvidenceRow = within(evidenceBook).getByRole("link", { name: /数据健康.*证据入口/s });
    const primaryEvidenceRow = within(evidenceBook).getByRole("link", { name: /主信号.*证据入口/s });

    expect(committeeReadiness).toHaveTextContent("待确认闭环");
    expect(committeeReadiness).toHaveTextContent("工具执行待确认");
    expect(within(investmentBrief).getAllByRole("button", { name: "复核工具执行结果" })).not.toHaveLength(0);

    await user.click(committeeAction);

    expect(toolExecutionEvidenceRow).not.toHaveAttribute("aria-current");
    expect(dataHealthEvidenceRow).not.toHaveAttribute("aria-current");
    expect(primaryEvidenceRow).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-operations-actions")).toHaveClass(
      "macro-toolkit-operations-console__actions--active",
    );
    expect(screen.getByTestId("macro-toolkit-data-health-detail")).not.toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
    expect(screen.getByTestId("macro-toolkit-analysis-detail")).not.toHaveClass(
      "macro-toolkit-anchor-target--active",
    );
  });

  it("uses completion-supplement wording in the core committee redline", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const scriptEnvelope = await baseClient.getMacroToolkitScripts();
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "capability_results",
                label: "功能结果",
                status: "deferred",
              },
            ],
          },
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "core",
            repair_items: [],
            deferred_sections: ["capability_results"],
          },
        },
      }),
    } as ApiClient;
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 0,
          refetchOnWindowFocus: false,
        },
      },
    });
    queryClient.setQueryData(["macro-toolkit", "scripts"], scriptEnvelope);

    render(
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <MacroToolkitPage mode="toolkit" />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    const redline = await screen.findByLabelText("投委会提交红线");
    await waitFor(() => expect(redline).toHaveTextContent("完整证据未确认"));
    expect(redline).toHaveTextContent("打开完整分析后确认完整分析补充项，再复核投委会材料。");
    expect(redline).not.toHaveTextContent("延后证据");
  });

  it("shows an Action Console receipt and updates it after a CFFEX refresh", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const cffexCalls: Array<Parameters<ApiClient["refreshCffexMemberRank"]>[0]> = [];
    const scriptCalls: string[] = [];
    const choiceStockCalls: Array<Parameters<ApiClient["refreshChoiceStock"]>[0]> = [];
    const client = {
      ...baseClient,
      refreshCffexMemberRank: async (options) => {
        cffexCalls.push(options);
        return baseClient.refreshCffexMemberRank(options);
      },
      runMacroToolkitScript: async (name, options) => {
        scriptCalls.push(name);
        return baseClient.runMacroToolkitScript(name, options);
      },
      refreshChoiceStock: async (options) => {
        choiceStockCalls.push(options);
        return baseClient.refreshChoiceStock(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    const receipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
    expect(receipt).toHaveTextContent("最近回执");
    expect(receipt).toHaveTextContent("状态");
    expect(receipt).toHaveTextContent("时间");
    expect(receipt).toHaveTextContent("影响对象");
    expect(receipt).toHaveTextContent("输出产物");
    expect(receipt).toHaveTextContent("下一步");
    expect(receipt).toHaveTextContent("等待执行");

    await user.click(within(operationsConsole).getByRole("button", { name: /刷新席位明细/ }));

    await waitFor(() => expect(cffexCalls).toHaveLength(1));
    await waitFor(() => {
      expect(within(operationsConsole).getByTestId("macro-toolkit-action-receipt")).toHaveTextContent("已完成");
    });
    const updatedReceipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
    expect(updatedReceipt).toHaveTextContent("CFFEX 席位");
    expect(updatedReceipt).toHaveTextContent("中金所席位 80 行");
    expect(updatedReceipt).toHaveTextContent("核对 CFFEX席位状态");
    const committeeWorkQueueAfterCffex = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const signoffAfterCffex = within(committeeWorkQueueAfterCffex).getByLabelText("投委会签核轨道");
    expect(signoffAfterCffex).toHaveTextContent("数据运营负责人");
    expect(signoffAfterCffex).toHaveTextContent("阻断签核");
    expect(signoffAfterCffex).toHaveTextContent("数据健康");
    expect(committeeWorkQueueAfterCffex).toHaveTextContent("回执闭环");
    expect(committeeWorkQueueAfterCffex).toHaveTextContent("CFFEX席位状态");

    await user.click(within(operationsConsole).getByRole("button", { name: /运行选中脚本/ }));

    await waitFor(() => expect(scriptCalls).toHaveLength(1));
    await waitFor(() => {
      expect(within(operationsConsole).getByTestId("macro-toolkit-action-receipt")).toHaveTextContent("运行脚本");
    });
    const scriptReceipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
    expect(scriptReceipt).toHaveTextContent("已完成");
    expect(scriptReceipt).toHaveTextContent("输出文件 0 · 退出码 0");
    expect(scriptReceipt).toHaveTextContent("核对脚本产物与注册表状态");
    const committeeWorkQueueAfterScript = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const signoffAfterScript = within(committeeWorkQueueAfterScript).getByLabelText("投委会签核轨道");
    const toolExecutionLedgerAfterScript = within(committeeWorkQueueAfterScript).getByLabelText("投委会提交链路-工具执行");
    const investmentBriefAfterScript = await screen.findByTestId("macro-toolkit-investment-brief");
    const committeePackAfterScript = within(investmentBriefAfterScript).getByLabelText("投委会材料包");
    const primarySignalPackAfterScript = within(committeePackAfterScript).getByLabelText("投委会材料包-主信号");
    const toolPackAfterScript = within(committeePackAfterScript).getByLabelText("投委会材料包-工具执行");
    expect(signoffAfterScript).toHaveTextContent("宏观策略负责人");
    expect(signoffAfterScript).toHaveTextContent("已留痕复核");
    expect(committeeWorkQueueAfterScript).toHaveTextContent("脚本产物");
    expect(committeeWorkQueueAfterScript).toHaveTextContent("回执待复核");
    expect(toolExecutionLedgerAfterScript).toHaveTextContent("回执闭环 · 脚本产物");
    expect(toolExecutionLedgerAfterScript).toHaveTextContent("复核签核");
    const toolExecutionSignoff = within(toolExecutionLedgerAfterScript).getByRole("button", {
      name: /复核签核.*工具执行/s,
    });
    expect(primarySignalPackAfterScript).toHaveTextContent("已归档");
    expect(primarySignalPackAfterScript).not.toHaveTextContent("回执待复核");
    expect(toolPackAfterScript).toHaveTextContent("回执待复核");
    expect(toolPackAfterScript).toHaveTextContent("脚本产物");
    expect(signoffAfterScript).toHaveTextContent("1/3");
    const readinessSummaryAfterScript = within(investmentBriefAfterScript).getByLabelText("投委会提交包就绪摘要");
    expect(readinessSummaryAfterScript).toHaveTextContent(/提交包就绪度\s*2\/4/);
    expect(readinessSummaryAfterScript).toHaveTextContent(/待复核回执\s*1/);

    await user.click(toolExecutionSignoff);

    const committeeWorkQueueAfterToolSignoff = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const toolLedgerAfterSignoff = within(committeeWorkQueueAfterToolSignoff).getByLabelText("投委会提交链路-工具执行");
    const signoffAfterToolConfirmation = within(committeeWorkQueueAfterToolSignoff).getByLabelText("投委会签核轨道");
    const investmentBriefAfterToolSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
    const committeePackAfterToolSignoff = within(investmentBriefAfterToolSignoff).getByLabelText("投委会材料包");
    expect(toolLedgerAfterSignoff).toHaveTextContent("签核已确认 · 脚本产物");
    expect(toolLedgerAfterSignoff).toHaveTextContent("查看签核证据");
    expect(within(committeePackAfterToolSignoff).getByLabelText("投委会材料包-工具执行")).toHaveTextContent("已签核");
    expect(signoffAfterToolConfirmation).toHaveTextContent("宏观策略负责人");
    expect(signoffAfterToolConfirmation).toHaveTextContent("已签核确认");
    expect(signoffAfterToolConfirmation).toHaveTextContent("1/3");
    expect(signoffAfterToolConfirmation).toHaveTextContent("数据运营负责人");
    expect(signoffAfterToolConfirmation).toHaveTextContent("阻断签核");

    await user.click(within(operationsConsole).getByRole("button", { name: /刷新股票策略明细/ }));

    await waitFor(() => expect(choiceStockCalls).toHaveLength(1));
    await waitFor(() => {
      expect(within(operationsConsole).getByTestId("macro-toolkit-action-receipt")).toHaveTextContent("刷新股票策略");
    });
    const stockReceipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
    expect(stockReceipt).toHaveTextContent("已完成");
    expect(stockReceipt).toHaveTextContent("历史");
    expect(stockReceipt).toHaveTextContent("因子");
    const committeeWorkQueueAfterStock = within(operationsConsole).getByTestId("macro-toolkit-committee-work-queue");
    const signoffAfterStock = within(committeeWorkQueueAfterStock).getByLabelText("投委会签核轨道");
    const strategyLedgerAfterStock = within(committeeWorkQueueAfterStock).getByLabelText("投委会提交链路-策略供数");
    const investmentBriefAfterStock = await screen.findByTestId("macro-toolkit-investment-brief");
    const committeePackAfterStock = within(investmentBriefAfterStock).getByLabelText("投委会材料包");
    const strategyPackAfterStock = within(committeePackAfterStock).getByLabelText("投委会材料包-策略供数");
    expect(signoffAfterStock).toHaveTextContent("权益策略负责人");
    expect(signoffAfterStock).toHaveTextContent("已留痕复核");
    expect(committeeWorkQueueAfterStock).toHaveTextContent("策略展示");
    expect(committeeWorkQueueAfterStock).toHaveTextContent("回执待复核");
    expect(strategyLedgerAfterStock).toHaveTextContent("回执闭环 · 策略展示");
    expect(strategyLedgerAfterStock).toHaveTextContent("复核签核");
    expect(strategyPackAfterStock).toHaveTextContent("回执待复核");
    expect(strategyPackAfterStock).toHaveTextContent("策略展示");
    expect(signoffAfterStock).toHaveTextContent("2/3");
    expect(signoffAfterStock).toHaveTextContent("数据运营负责人");
    expect(signoffAfterStock).toHaveTextContent("阻断签核");
    const readinessSummaryAfterStock = within(investmentBriefAfterStock).getByLabelText("投委会提交包就绪摘要");
    expect(readinessSummaryAfterStock).toHaveTextContent(/提交包就绪度\s*3\/4/);
    expect(readinessSummaryAfterStock).toHaveTextContent(/待复核回执\s*1/);
    const queue = within(operationsConsole).getByTestId("macro-toolkit-action-queue");
    expect(queue).toHaveTextContent("操作审计队列");
    expect(queue).toHaveTextContent("3 条");
    expect(queue).toHaveTextContent("决策影响");
    expect(queue).toHaveTextContent("复核角色");
    expect(queue).toHaveTextContent("证据入口");
    expect(queue).toHaveTextContent("A股策略供数");
    expect(queue).toHaveTextContent("权益策略负责人");
    expect(queue).toHaveTextContent("策略展示");
    expect(queue).toHaveTextContent("脚本产物闭环");
    expect(queue).toHaveTextContent("宏观策略负责人");
    expect(queue).toHaveTextContent("脚本产物");
    expect(queue).toHaveTextContent("期指席位结构");
    expect(queue).toHaveTextContent("数据运营负责人");
    expect(queue).toHaveTextContent("CFFEX席位状态");
    const scriptEvidenceLink = within(queue).getByRole("link", { name: /脚本产物/ });
    const cffexEvidenceLink = within(queue).getByRole("link", { name: /CFFEX席位状态/ });
    const stockEvidenceLink = within(queue).getByRole("link", { name: /策略展示/ });
    expect(scriptEvidenceLink).toHaveAttribute("href", "#macro-toolkit-script-artifact-detail");
    expect(cffexEvidenceLink).toHaveAttribute("href", "#macro-toolkit-cffex-detail");
    expect(stockEvidenceLink).toHaveAttribute("href", "#macro-toolkit-strategy-detail");
    expect(within(queue).getAllByRole("listitem")).toHaveLength(3);

    await user.click(scriptEvidenceLink);

    expect(within(queue).getByRole("link", { name: /脚本产物/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("macro-toolkit-script-artifact-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );
    expect(screen.getByTestId("macro-toolkit-cffex-detail")).not.toHaveClass(
      "macro-toolkit-section--audit-focus",
    );

    await user.click(cffexEvidenceLink);

    expect(within(queue).getByRole("link", { name: /CFFEX席位状态/ })).toHaveAttribute("aria-current", "true");
    expect(within(queue).getByRole("link", { name: /脚本产物/ })).not.toHaveAttribute("aria-current");
    expect(screen.getByTestId("macro-toolkit-cffex-detail")).toHaveClass(
      "macro-toolkit-section--audit-focus",
    );
    expect(screen.getByTestId("macro-toolkit-script-artifact-detail")).not.toHaveClass(
      "macro-toolkit-section--audit-focus",
    );
  });

  it("renders degraded model-chain runs as warning instead of success", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      runMacroToolkitScriptChain: async (options) => {
        const response = await baseClient.runMacroToolkitScriptChain(options);
        return {
          ...response,
          result: {
            ...response.result,
            run: {
              ...response.result.run,
              status: "degraded",
              dry_run: false,
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    await user.click(within(operationsConsole).getByRole("button", { name: /运行模型链/ }));

    const chainRunStatus = await within(operationsConsole).findByText(/degraded/);
    const chainRunAlert = requireClosestElement(chainRunStatus.closest(".ant-alert"), "model chain alert");
    expect(chainRunAlert).toHaveClass("ant-alert-warning");
    expect(chainRunAlert).not.toHaveClass("ant-alert-success");
  });

  it("keeps mock execution receipts degraded when expected artifacts stay missing", async () => {
    const client = createApiClient({ mode: "mock" });

    const response = await client.runMacroToolkitScriptChain({ dryRun: false, timeoutSeconds: 30 });
    const receiptsByScript = new Map(response.result.run.receipts.map((receipt) => [receipt.script_name, receipt]));

    for (const [scriptName, missingOutputs] of [
      ["dcc_garch_cn", ["dcc_latest.csv", "dcc_results.csv"]],
      ["cta_trend_cn", ["cta_results.csv"]],
      ["risk_monitor", ["risk_log.csv", "risk_state.csv"]],
    ] as const) {
      const receipt = receiptsByScript.get(scriptName);
      expect(receipt?.status).toBe("completed");
      expect(receipt?.missing_outputs_after).toEqual(missingOutputs);
      expect(receipt?.produced_outputs).toEqual([]);
      expect(receipt?.degraded_reason).toBe("missing_expected_outputs_after_run");
      expect(receipt?.data_asof).toBeNull();
      expect(receipt?.formal_use_allowed).toBe(false);
      expect(receipt?.observation_only).toBe(true);
    }
  });

  it("prefers committee evidence scripts for the default run action", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const firstScript = scriptsEnvelope.result.scripts[0]!;
    const signalScript = scriptsEnvelope.result.scripts.find((script) => script.name === "signal_aggregator")!;
    const scriptCalls: string[] = [];
    const client = {
      ...baseClient,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          groups: ["news", ...scriptsEnvelope.result.groups],
          scripts: [
            {
              ...firstScript,
              name: "alphaear_news_fetch",
              filename: "alphaear_news_fetch.py",
              group: "news",
              optional_dependencies: ["openclaw alphaear-news"],
              available: true,
            },
            signalScript,
            ...scriptsEnvelope.result.scripts.filter(
              (script) => !["equity_strategies", "signal_aggregator"].includes(script.name),
            ),
          ],
        },
      }),
      runMacroToolkitScript: async (name, options) => {
        scriptCalls.push(name);
        return baseClient.runMacroToolkitScript(name, options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    await waitFor(() =>
      expect(within(operationsConsole).getByText("signal_aggregator")).toBeInTheDocument(),
    );
    await user.click(within(operationsConsole).getByRole("button", { name: /运行选中脚本/ }));

    await waitFor(() => expect(scriptCalls).toEqual(["signal_aggregator"]));
  });

  it("keeps other operation actions disabled while script evidence is still reloading", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const scriptCalls: string[] = [];
    const choiceStockCalls: Array<Parameters<ApiClient["refreshChoiceStock"]>[0]> = [];
    let releaseScriptReload: () => void = () => undefined;
    const scriptReloadGate = new Promise<void>((resolve) => {
      releaseScriptReload = resolve;
    });
    const client = {
      ...baseClient,
      getMacroToolkitScripts: async () => {
        const response = await baseClient.getMacroToolkitScripts();
        if (scriptCalls.length > 0) {
          await scriptReloadGate;
        }
        return response;
      },
      runMacroToolkitScript: async (name, options) => {
        scriptCalls.push(name);
        return baseClient.runMacroToolkitScript(name, options);
      },
      refreshChoiceStock: async (options) => {
        choiceStockCalls.push(options);
        return baseClient.refreshChoiceStock(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    await user.click(within(operationsConsole).getByRole("button", { name: /运行选中脚本/ }));

    await waitFor(() => expect(scriptCalls).toHaveLength(1));
    await waitFor(() => {
      expect(within(operationsConsole).getByTestId("macro-toolkit-action-receipt")).toHaveTextContent("已完成");
    });
    const investmentBriefAfterScript = await screen.findByTestId("macro-toolkit-investment-brief");
    expect(
      within(investmentBriefAfterScript).getByLabelText("投委会材料包-工具执行"),
    ).toHaveTextContent("回执待复核");
    expect(within(operationsConsole).getByRole("button", { name: /刷新股票策略明细/ })).toBeDisabled();

    releaseScriptReload?.();

    await waitFor(() =>
      expect(within(operationsConsole).getByRole("button", { name: /刷新股票策略明细/ })).toBeEnabled(),
    );
    await user.click(within(operationsConsole).getByRole("button", { name: /刷新股票策略明细/ }));
    await waitFor(() => expect(choiceStockCalls).toHaveLength(1));
  });

  it("ignores cached script registry payloads on the macro observation route", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const [scriptEnvelope, analysisEnvelope] = await Promise.all([
      baseClient.getMacroToolkitScripts(),
      baseClient.getMacroToolkitAnalysis(),
    ]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          source_checks: [
            {
              alias: "OBS_ONLY",
              row_count: 1,
              latest: {
                date: "2026-04-30",
                series_id: "OBS_ONLY",
                vendor_name: "choice",
                value: 1,
              },
            },
          ],
          capabilities: [],
        },
      }),
    } as ApiClient;
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 0,
          refetchOnWindowFocus: false,
        },
      },
    });
    queryClient.setQueryData(["macro-toolkit", "scripts"], scriptEnvelope);

    render(
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <MacroToolkitPage mode="observation" />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    const readiness = await screen.findByLabelText("宏观工具投研总览");
    expect(readiness).toHaveTextContent("来源覆盖 7/9");
    expect(readiness).not.toHaveTextContent("源命中");
    expect(readiness).toHaveTextContent("证据边界");
    expect(readiness).not.toHaveTextContent("模型结果");
    expect(readiness).not.toHaveTextContent("功能输出");
    expect(screen.queryByText(scriptEnvelope.result.scripts[0]?.name ?? "")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "脚本注册表" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
  });

  it("renders handwritten data-health repair items from the analysis contract", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const resultMeta: ResultMeta = {
      trace_id: "trace_macro_health_contract",
      basis: "analytical",
      result_kind: "macro_toolkit.analysis",
      formal_use_allowed: false,
      source_version: "sv_macro_health_contract",
      vendor_version: "vv_choice_tushare",
      rule_version: "rv_macro_health_contract",
      cache_version: "cv_macro_health_contract",
      quality_flag: "warning",
      vendor_status: "vendor_stale",
      fallback_mode: "none",
      scenario_flag: false,
      as_of_date: "2026-04-10",
      generated_at: "2026-04-10T10:00:00Z",
      tables_used: ["system_macro_sources"],
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        result_meta: resultMeta,
        result: {
          default_data_sources: ["choice", "tushare"],
          as_of_date: "2026-04-10",
          conclusion: {
            stance: "数据健康待处理",
            tone: "neutral",
            summary: "存在缺失、滞后、降级和延后加载项。",
            recommended_action: "先处理高优先级输入，再查看完整分析。",
          },
          coverage: {
            indicator_count: 1,
            hit_count: 0,
            hit_rate: 0,
            script_count: 0,
            output_file_count: 0,
          },
          indicators: [],
          signal_cards: [],
          capability_results: [],
          strategy_summaries: [],
          output_files: [],
          source_checks: [],
          capabilities: [],
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "source_checks",
                label: "来源检查",
                status: "deferred",
              },
            ],
          },
          data_health: {
            analysis_scope: "core",
            indicator_coverage: {
              hit_count: 0,
              total_count: 1,
              hit_rate: 0,
              missing_count: 1,
              missing: [{ key: "ncd_3m", alias: "M0041813", label: "3M NCD" }],
            },
            source_coverage: {
              hit_count: 0,
              total_count: 0,
              hit_rate: null,
              latest_date: null,
              deferred: true,
              missing_aliases: [],
            },
            capability_results: {
              complete: 0,
              degraded: 0,
              unavailable: 0,
              total_count: 0,
              deferred: true,
            },
            capability_plan: {
              ready_count: 0,
              wired_count: 0,
              total_count: 0,
              deferred: true,
            },
            deferred_sections: ["source_checks"],
            warnings: ["存在待处理数据项"],
            repair_items: [
              {
                type: "missing",
                scope: "core",
                priority: "high",
                key: "indicator:ncd_3m",
                alias: "M0041813",
                label: "3M NCD",
                suggested_action: "补齐 M0041813 后重新运行完整宏观分析；缺失项不能按 0 处理。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要补齐来源数据",
                  enabled: true,
                  reason: "可触发宏观来源补齐；完成后重新运行完整分析确认。",
                  analysis_detail: "full",
                },
              },
              {
                type: "stale",
                scope: "core",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                source_table: "system_macro_sources",
                latest_date: "2026-04-01",
                reference_date: "2026-04-10",
                stale_days: 9,
                suggested_action: "CU0 最新 2026-04-01，落后分析日 2026-04-10 9 天；刷新 Choice/Tushare 后再确认。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要刷新来源",
                  enabled: false,
                  reason: "当前没有已接入的一键宏观序列刷新接口。",
                  analysis_detail: "full",
                },
              },
              {
                type: "degraded",
                scope: "core",
                priority: "medium",
                key: "capability:leading_indicator",
                label: "宏观领先指标",
                suggested_action: "宏观领先指标 当前 degraded：PMI_MISSING；补齐输入证据后重新运行完整宏观分析。",
                action: {
                  kind: "load_full_analysis",
                  label: "重新完整分析",
                  enabled: true,
                  reason: "补齐输入证据后重新运行完整分析确认状态。",
                  analysis_detail: "full",
                },
              },
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:source_checks",
                label: "source_checks",
                suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
            ],
          },
          warnings: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        result_meta: { ...resultMeta, result_kind: "macro_toolkit.strategy_summaries" },
        result: { strategy_summaries: [] },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const evidenceTraceSummary = await screen.findByLabelText("证据追踪摘要");
    expect(evidenceTraceSummary).toHaveTextContent("数据健康");
    expect(evidenceTraceSummary).toHaveTextContent("指标覆盖 0/1");
    expect(evidenceTraceSummary).toHaveTextContent("3M NCD");
    expect(evidenceTraceSummary).toHaveTextContent("完整分析补充项待确认");
    expect(evidenceTraceSummary).not.toHaveTextContent("有延后证据待确认");
    expect(evidenceTraceSummary).toHaveTextContent("4 项复核提示");
    expect(evidenceTraceSummary).toHaveTextContent("CU0 落后 9 天");
    expect(evidenceTraceSummary).toHaveTextContent("宏观领先指标 PMI_MISSING");
    expect(evidenceTraceSummary).toHaveTextContent("先补齐高优先级输入，再复核观察结论。");
    expect(evidenceTraceSummary).not.toHaveTextContent("待处理数据项");
    expect(evidenceTraceSummary).not.toHaveTextContent("source_checks");
    expect(evidenceTraceSummary).not.toHaveTextContent("另 1 项");
    expect(evidenceTraceSummary).not.toHaveTextContent("可触发宏观来源补齐");
    expect(evidenceTraceSummary).not.toHaveTextContent("当前没有已接入的一键宏观序列刷新接口。");
    expect(within(evidenceTraceSummary).queryByRole("button", { name: "需要刷新来源" })).not.toBeInTheDocument();
    expect(within(evidenceTraceSummary).queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
    expect(within(evidenceTraceSummary).queryByRole("button", { name: "重新完整分析" })).not.toBeInTheDocument();
  });

  it("surfaces the hidden count when data-health repair items are truncated", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const repairItems = Array.from({ length: 8 }, (_, index) => {
      const itemNumber = index + 1;
      return {
        type: "missing",
        scope: "full",
        priority: "medium",
        key: `repair:${itemNumber}`,
        alias: `MISSING_${itemNumber}`,
        label: `缺口 ${itemNumber}`,
        source_table: "system_macro_sources",
        latest_date: null,
        reference_date: "2026-04-30",
        stale_days: null,
        suggested_action: `补齐缺口 ${itemNumber} 后重新运行完整宏观分析。`,
        action: null,
        tags: ["missing"],
      };
    });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            repair_items: repairItems,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const evidenceTraceSummary = await screen.findByLabelText("证据追踪摘要");
    expect(evidenceTraceSummary).toHaveTextContent("8 项复核提示");
    expect(evidenceTraceSummary).toHaveTextContent("缺口 1");
    expect(evidenceTraceSummary).toHaveTextContent("缺口 4");
    expect(evidenceTraceSummary).toHaveTextContent("另 4 项");
    expect(evidenceTraceSummary).not.toHaveTextContent("缺口 5");
    expect(screen.queryByLabelText("待处理数据项")).not.toBeInTheDocument();
  });

  it("shows M7/M10/M14 input evidence and missing-input warnings in capability results", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const m7Text = await screen.findByText((content) => content.includes("Policy rate 7D"));
    await waitFor(() => {
      const capabilityPmiTexts = screen
        .getAllByText((content) => content.includes("PMI_MISSING"))
        .filter((item) => item.closest(".macro-toolkit-capability-result"));
      expect(capabilityPmiTexts.length).toBeGreaterThanOrEqual(2);
    });
    const m10Texts = screen
      .getAllByText((content) => content.includes("PMI_MISSING"))
      .filter((item) => item.closest(".macro-toolkit-capability-result"));
    const m7Card = m7Text.closest(".macro-toolkit-capability-result");
    const m10Card = m10Texts[0]?.closest(".macro-toolkit-capability-result");
    const m14Card = m10Texts[1]?.closest(".macro-toolkit-capability-result");

    expect(m7Card).not.toBeNull();
    expect(m10Card).not.toBeNull();
    expect(m14Card).not.toBeNull();

    expect(m7Card).toHaveTextContent("Policy rate 7D: M001 2026-04-10");
    expect(m7Card).not.toHaveTextContent("POLICY_RATE_7D_MISSING");
    expect(m7Card).toHaveTextContent("choice");
    expect(m7Card).toHaveTextContent("2026-04-10");

    expect(m10Card).toHaveTextContent("PMI_MISSING");
    expect(m10Card).toHaveTextContent("M2_YOY_MISSING");
    expect(m10Card).toHaveTextContent("choice / fred / moss_derived");
    expect(m10Card).toHaveTextContent("2026-02-01");

    expect(m14Card).toHaveTextContent("PMI_MISSING");
    expect(m14Card).toHaveTextContent("PPI_YOY_MISSING");
    expect(m14Card).toHaveTextContent("M2_YOY_MISSING");
    expect(m14Card).toHaveTextContent("2026-03-01");
  });

  it("keeps core risk analysis visible while deferred strategy summaries are still loading", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "strategy_summaries",
                label: "策略展示",
                status: "loading",
              },
            ],
          },
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: () => new Promise(() => {}),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(
      await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("宏观工具运行状态")).toHaveTextContent("策略展示 · 加载中");
    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("策略供数 加载中");
    expect(strategySupply).not.toHaveTextContent("0/0");
    expect(strategySupply).not.toHaveTextContent("样例 0");
    expect(await screen.findByText("策略展示正在生成")).toBeInTheDocument();
    expect(
      screen.getByText("核心信号已先返回；市场踩踏风险需打开完整分析后显示。"),
    ).toBeInTheDocument();
  });

  it("loads the full macro analysis from the core first screen action", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const coreCrisisCard = {
      key: "crisis_score_cn",
      title: "Crisis Score",
      stance: "完整结果待加载",
      tone: "neutral",
      score: null,
      evidence: ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
    } as const;
    const coreSignalCards = analysisEnvelope.result.signal_cards.map((card) =>
      card.key === "crisis_score_cn" ? coreCrisisCard : card,
    );
    const coreSignalCardsWithCrisis = [
      coreCrisisCard,
      ...coreSignalCards.filter((card) => card.key !== "crisis_score_cn"),
    ];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        const coreDataHealth = {
          ...analysisEnvelope.result.data_health!,
          analysis_scope: "core",
          source_coverage: {
            hit_count: 0,
            total_count: 0,
            hit_rate: null,
            latest_date: null,
            deferred: true,
            missing_aliases: [],
          },
          capability_results: {
            complete: 0,
            degraded: 0,
            unavailable: 0,
            total_count: 0,
            deferred: true,
          },
          capability_plan: {
            ready_count: 0,
            wired_count: 0,
            total_count: 0,
            deferred: true,
          },
          deferred_sections: ["capability_results", "source_checks"],
          repair_items: [
            {
              type: "deferred",
              scope: "core",
              priority: "low",
              key: "deferred:source_checks",
              alias: null,
              label: "source_checks",
              source_table: null,
              latest_date: null,
              reference_date: "2026-04-30",
              stale_days: null,
              suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
              action: {
                kind: "load_full_analysis",
                label: "查看完整分析",
                enabled: true,
                reason: "首屏延后加载，完整分析可确认。",
                analysis_detail: "full",
              },
              tags: ["deferred"],
            },
          ],
        } as const;
        return {
          ...analysisEnvelope,
          result: {
            ...analysisEnvelope.result,
            runtime_status: {
              analysis_scope: options?.detail === "full" ? "full" : "core",
              deferred_sections:
                options?.detail === "full"
                  ? []
                  : [
                      {
                        key: "capability_results",
                        label: "功能结果",
                        status: "deferred",
                      },
                    ],
            },
            capability_results:
              options?.detail === "full" ? analysisEnvelope.result.capability_results : [],
            signal_cards:
              options?.detail === "full" ? analysisEnvelope.result.signal_cards : coreSignalCardsWithCrisis,
            data_health: options?.detail === "full" ? analysisEnvelope.result.data_health : coreDataHealth,
          },
        };
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.source_backfill_refresh",
          },
          result: {
            refresh: {
              status: "completed",
              alias: options.alias,
              series_ids: ["NCD.SHIBOR.3M"],
              total_added: 42,
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByText("完整结果待加载")).toBeInTheDocument();
    const coreDataHealth = await screen.findByLabelText("数据健康总览");
    expect(coreDataHealth).toHaveTextContent("待处理数据项");
    expect(coreDataHealth).toHaveTextContent("完整分析后确认");
    expect(coreDataHealth).not.toHaveTextContent("来源未命中");
    expect(screen.queryByLabelText("Crisis Score 数据来源")).not.toBeInTheDocument();
    await user.click(within(coreDataHealth).getByRole("button", { name: /查看完整分析/ }));
    expect(calls).toContainEqual({ detail: "full" });
    await screen.findByLabelText("Crisis Score 数据来源");

    expect(calls).toContainEqual({ detail: "full" });
    const fullDataHealth = await screen.findByLabelText("数据健康总览");
    expect(fullDataHealth).toHaveTextContent("待处理数据项");
    expect(fullDataHealth).toHaveTextContent("补齐 M0041813 后重新运行完整宏观分析");
    expect(fullDataHealth).toHaveTextContent("PMI_MISSING");
    await user.click(within(fullDataHealth).getByRole("button", { name: /需要补齐来源数据/ }));
    expect(sourceBackfillCalls).toEqual([
      {
        alias: "M0041813",
        startDate: undefined,
        endDate: "2026-04-30",
        sources: undefined,
      },
    ]);
    const operationsConsoleAfterBackfill = await screen.findByTestId("macro-toolkit-operations-console");
    const sourceBackfillReceipt = within(operationsConsoleAfterBackfill).getByTestId("macro-toolkit-action-receipt");
    await waitFor(() => expect(sourceBackfillReceipt).toHaveTextContent("来源补齐"));
    expect(sourceBackfillReceipt).toHaveTextContent("已完成");
    expect(sourceBackfillReceipt).toHaveTextContent("M0041813");
    const sourceBackfillQueue = within(operationsConsoleAfterBackfill).getByTestId("macro-toolkit-committee-work-queue");
    const investmentBriefAfterBackfill = await screen.findByTestId("macro-toolkit-investment-brief");
    const sourceBackfillSummary = within(investmentBriefAfterBackfill).getByLabelText(
      "投委会提交包就绪摘要",
    );
    expect(sourceBackfillSummary).toHaveTextContent(/提交包就绪度\s*2\/4/);
    expect(sourceBackfillSummary).toHaveTextContent(/硬阻断\s*0/);
    expect(sourceBackfillSummary).toHaveTextContent(/待复核回执\s*1/);
    expect(sourceBackfillSummary).toHaveTextContent("待复核回执");
    const currentRepairStatusAfterBackfill = within(investmentBriefAfterBackfill).getByLabelText("投委会当前处理状态");
    expect(currentRepairStatusAfterBackfill).toHaveTextContent("回执状态");
    expect(currentRepairStatusAfterBackfill).toHaveTextContent("回执待复核");
    expect(currentRepairStatusAfterBackfill).toHaveTextContent("回执证据");
    expect(currentRepairStatusAfterBackfill).toHaveTextContent("来源补齐");
    const closureRailAfterBackfill = within(investmentBriefAfterBackfill).getByLabelText("投委会闭环流水线");
    expect(closureRailAfterBackfill).toHaveTextContent("处理");
    expect(closureRailAfterBackfill).toHaveTextContent("回执已生成");
    expect(closureRailAfterBackfill).toHaveTextContent("来源补齐");
    expect(closureRailAfterBackfill).toHaveTextContent("签核");
    expect(closureRailAfterBackfill).toHaveTextContent("待复核签核");
    expect(closureRailAfterBackfill).toHaveTextContent("放行");
    expect(closureRailAfterBackfill).toHaveTextContent("等待签核");
    const firstScreenSignoffButton = within(closureRailAfterBackfill).getByRole("button", {
      name: /复核签核-数据健康/s,
    });
    expect(firstScreenSignoffButton).toHaveTextContent("复核数据健康回执");
    expect(
      within(closureRailAfterBackfill).queryByRole("link", { name: /签核.*复核数据健康回执/s }),
    ).not.toBeInTheDocument();
    await user.click(firstScreenSignoffButton);
    const investmentBriefAfterFirstScreenSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
    const closureRailAfterFirstScreenSignoff = within(investmentBriefAfterFirstScreenSignoff).getByLabelText(
      "投委会闭环流水线",
    );
    expect(closureRailAfterFirstScreenSignoff).toHaveTextContent("签核已确认");
    expect(closureRailAfterFirstScreenSignoff).toHaveTextContent("可放行");
    expect(within(closureRailAfterFirstScreenSignoff).getByRole("link", { name: /放行.*查看签核证据/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    expect(sourceBackfillQueue).toHaveTextContent("来源补齐");
    expect(sourceBackfillQueue).toHaveTextContent("签核已确认");
    const dataHealthLedgerAfterBackfill = within(sourceBackfillQueue).getByLabelText("投委会提交链路-数据健康");
    expect(dataHealthLedgerAfterBackfill).toHaveTextContent("签核已确认 · 来源补齐");
    expect(dataHealthLedgerAfterBackfill).toHaveTextContent("查看签核证据");
    const repairTicketAfterBackfill = within(screen.getByTestId("macro-toolkit-data-health-detail")).getByLabelText(
      "当前处理单-M0041813",
    );
    expect(repairTicketAfterBackfill).toHaveTextContent("回执状态");
    expect(repairTicketAfterBackfill).toHaveTextContent("签核已确认");
    expect(repairTicketAfterBackfill).toHaveTextContent("回执证据");
    expect(repairTicketAfterBackfill).toHaveTextContent("来源补齐");

    const sourceBackfillQueueAfterSignoff = within(operationsConsoleAfterBackfill).getByTestId("macro-toolkit-committee-work-queue");
    const dataHealthLedgerAfterSignoff = within(sourceBackfillQueueAfterSignoff).getByLabelText("投委会提交链路-数据健康");
    const dataHealthSignoffLaneAfterSignoff = within(sourceBackfillQueueAfterSignoff).getByLabelText("投委会签核轨道");
    const investmentBriefAfterDataHealthSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
    const summaryAfterDataHealthSignoff = within(investmentBriefAfterDataHealthSignoff).getByLabelText(
      "投委会提交包就绪摘要",
    );
    const committeePackAfterDataHealthSignoff = within(investmentBriefAfterDataHealthSignoff).getByLabelText("投委会材料包");
    expect(dataHealthLedgerAfterSignoff).toHaveTextContent("签核已确认 · 来源补齐");
    expect(dataHealthLedgerAfterSignoff).toHaveTextContent("查看签核证据");
    expect(dataHealthSignoffLaneAfterSignoff).toHaveTextContent("数据运营负责人");
    expect(dataHealthSignoffLaneAfterSignoff).toHaveTextContent("已签核确认");
    expect(within(committeePackAfterDataHealthSignoff).getByLabelText("投委会材料包-数据健康")).toHaveTextContent("已签核");
    expect(summaryAfterDataHealthSignoff).toHaveTextContent(/硬阻断\s*0/);
    expect(summaryAfterDataHealthSignoff).toHaveTextContent(/待复核回执\s*0/);
    const currentRepairStatusAfterSignoff = within(investmentBriefAfterDataHealthSignoff).getByLabelText("投委会当前处理状态");
    expect(currentRepairStatusAfterSignoff).toHaveTextContent("回执状态");
    expect(currentRepairStatusAfterSignoff).toHaveTextContent("签核已确认");
    expect(within(currentRepairStatusAfterSignoff).getByRole("link", { name: "查看签核证据" })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    const closureRailAfterSignoff = within(investmentBriefAfterDataHealthSignoff).getByLabelText("投委会闭环流水线");
    expect(closureRailAfterSignoff).toHaveTextContent("处理完成");
    expect(closureRailAfterSignoff).toHaveTextContent("回执已生成");
    expect(closureRailAfterSignoff).toHaveTextContent("签核已确认");
    expect(closureRailAfterSignoff).toHaveTextContent("可放行");
    expect(within(closureRailAfterSignoff).getByRole("link", { name: /放行.*查看签核证据/s })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );
    const repairTicketAfterSignoff = within(screen.getByTestId("macro-toolkit-data-health-detail")).getByLabelText(
      "当前处理单-M0041813",
    );
    expect(repairTicketAfterSignoff).toHaveTextContent("回执状态");
    expect(repairTicketAfterSignoff).toHaveTextContent("签核已确认");
    expect(repairTicketAfterSignoff).toHaveTextContent("查看签核证据");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(2);
    await user.click(within(fullDataHealth).getAllByRole("button", { name: /重新完整分析/ })[0]!);
    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(3));
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("分数组件覆盖");
    expect(crisisEvidence).toHaveTextContent("5/5");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
    expect(crisisEvidence).toHaveTextContent("commodity_vol");
    expect(crisisEvidence).toHaveTextContent("2026-04-10");
    expect(crisisEvidence).toHaveTextContent("120 rows");
    expect(crisisEvidence).toHaveTextContent("商品旁证覆盖");
    expect(crisisEvidence).toHaveTextContent("6/6");
    expect(crisisEvidence).toHaveTextContent("supplemental_observation");
    expect(crisisEvidence).toHaveTextContent("Crisis Score 公式仍仅使用 nanhua");
    expect(crisisEvidence).toHaveTextContent("候选商品仅做影子评估，当前未计入 Crisis Score 分数");
    expect(crisisEvidence).toHaveTextContent("Copper futures");
    expect(crisisEvidence).toHaveTextContent("CU0 / CU0.SHF");
    expect(crisisEvidence).toHaveTextContent("matched CU0");
    expect(crisisEvidence).toHaveTextContent("同日");
    expect(crisisEvidence).toHaveTextContent("Crude oil futures");
    expect(crisisEvidence).toHaveTextContent("Gold futures");
    expect(crisisEvidence).toHaveTextContent("未纳入公式");
    expect(crisisEvidence).toHaveTextContent("商品扩展候选");
    expect(crisisEvidence).toHaveTextContent("影子评估就绪");
    expect(crisisEvidence).toHaveTextContent("6 个就绪");
    expect(crisisEvidence).toHaveTextContent("公式变更需审批");
    expect(crisisEvidence).toHaveTextContent("历史回测、相关性检验、权重审批");
    expect(crisisEvidence).toHaveTextContent("影子评估结果");
    expect(crisisEvidence).toHaveTextContent("2 个可读");
    expect(crisisEvidence).toHaveTextContent("4 个样本不足");
    expect(crisisEvidence).toHaveTextContent("样本 41");
    expect(crisisEvidence).toHaveTextContent("同日相关 0.00");
    expect(crisisEvidence).toHaveTextContent("危机期命中率 55.0%");
    const commodityDecisionPanel = within(crisisEvidence).getByLabelText("候选商品影子评估决策面板");
    expect(commodityDecisionPanel).toHaveTextContent("当前未计入 Crisis Score");
    expect(commodityDecisionPanel).toHaveTextContent("转正前需审批");
    expect(commodityDecisionPanel).toHaveTextContent("可复核 2/6");
    expect(commodityDecisionPanel).toHaveTextContent("样本不足 4");
    const commodityActionQueue = within(commodityDecisionPanel).getByLabelText("商品候选下一动作队列");
    expect(commodityActionQueue).toHaveTextContent("人工复核队列");
    expect(commodityActionQueue).toHaveTextContent("Copper futures / Crude oil futures");
    expect(commodityActionQueue).toHaveTextContent("补历史样本队列");
    expect(commodityActionQueue).toHaveTextContent(
      "Rebar futures / Iron ore futures / Aluminum futures / Gold futures",
    );
    expect(commodityActionQueue).toHaveTextContent("当前未计入 Crisis Score");
    expect(commodityActionQueue).toHaveTextContent("下一步：先补齐样本不足品种，再复核铜、原油的相关性与命中率");
    const commodityReviewConclusion = within(commodityDecisionPanel).getByLabelText("商品候选复核结论");
    expect(commodityReviewConclusion).toHaveTextContent("商品候选准入评估");
    expect(commodityReviewConclusion).toHaveTextContent("建议纳入 0 · 继续观察 2 · 暂不纳入 4");
    expect(commodityReviewConclusion).toHaveTextContent("rv_macro_crisis_commodity_admission_v1");
    expect(commodityReviewConclusion).toHaveTextContent("CANDIDATE_ADMISSION_READ_ONLY");
    expect(commodityReviewConclusion).toHaveTextContent("Copper futures");
    expect(commodityReviewConclusion).toHaveTextContent("继续观察");
    expect(commodityReviewConclusion).toHaveTextContent("相关性偏弱，需人工复核。");
    expect(commodityReviewConclusion).toHaveTextContent("样本 41");
    expect(commodityReviewConclusion).toHaveTextContent("危机样本 11");
    expect(commodityReviewConclusion).toHaveTextContent("命中率 55.0%");
    expect(commodityReviewConclusion).toHaveTextContent("下一步：复核相关性与危机期命中率");
    expect(commodityReviewConclusion).toHaveTextContent("Rebar futures");
    expect(commodityReviewConclusion).toHaveTextContent("暂不纳入");
    expect(commodityReviewConclusion).toHaveTextContent("样本不足，先补齐历史数据。");
    expect(commodityReviewConclusion).toHaveTextContent("样本 17/20");
    expect(commodityReviewConclusion).toHaveTextContent("下一步：先补齐历史样本和危机期样本");
    expect(commodityReviewConclusion).toHaveTextContent("审批前不改变正式 Crisis Score");
    const approvalPack = within(commodityDecisionPanel).getByLabelText("商品候选审批材料");
    expect(approvalPack).toHaveTextContent("商品候选审批材料");
    expect(approvalPack).toHaveTextContent("rv_macro_crisis_commodity_approval_pack_v1");
    expect(approvalPack).toHaveTextContent("建议纳入 0");
    expect(approvalPack).toHaveTextContent("继续观察 2");
    expect(approvalPack).toHaveTextContent("暂不纳入 4");
    expect(approvalPack).toHaveTextContent("shadow delta +0.04");
    expect(approvalPack).toHaveTextContent("审批前不改变正式 Crisis Score");
    expect(within(approvalPack).getByRole("button", { name: "复制审批材料" })).toBeEnabled();
    const crisisShadowImpact = within(crisisEvidence).getByLabelText("Crisis Score v2 影子影响评估");
    expect(crisisShadowImpact).toHaveTextContent("Crisis Score v2 影子影响评估");
    expect(crisisShadowImpact).toHaveTextContent("正式 Crisis Score");
    expect(crisisShadowImpact).toHaveTextContent("-0.57");
    expect(crisisShadowImpact).toHaveTextContent("v2 shadow score");
    expect(crisisShadowImpact).toHaveTextContent("-0.53");
    expect(crisisShadowImpact).toHaveTextContent("delta +0.04");
    expect(crisisShadowImpact).toHaveTextContent("rv_macro_crisis_score_shadow_commodity_v1");
    expect(crisisShadowImpact).toHaveTextContent("影响方向");
    expect(crisisShadowImpact).toHaveTextContent("压力上行");
    expect(crisisShadowImpact).toHaveTextContent("候选驱动");
    expect(crisisShadowImpact).toHaveTextContent("2 个待复核");
    expect(crisisShadowImpact).toHaveTextContent("不改变正式 Crisis Score");
    expect(crisisShadowImpact).toHaveTextContent("Copper futures");
    expect(crisisShadowImpact).toHaveTextContent("daily_return_z +0.52");
    expect(crisisShadowImpact).toHaveTextContent("贡献 +0.0260");
    expect(crisisShadowImpact).toHaveTextContent("权重 5.0%");
    expect(crisisShadowImpact).toHaveTextContent("SHADOW_SCORE_READ_ONLY");
    expect(crisisShadowImpact).toHaveTextContent("审批前不改变正式 Crisis Score");
    expect(commodityDecisionPanel).toHaveTextContent("Copper futures");
    expect(commodityDecisionPanel).toHaveTextContent("影子评估可读");
    expect(commodityDecisionPanel).toHaveTextContent("样本 41");
    expect(commodityDecisionPanel).toHaveTextContent("窗口 2026-03-01 -> 2026-04-10");
    expect(commodityDecisionPanel).toHaveTextContent("领先相关 0.00");
    expect(commodityDecisionPanel).toHaveTextContent("滞后相关 0.00");
    expect(commodityDecisionPanel).toHaveTextContent("危机样本 11");
    expect(commodityDecisionPanel).toHaveTextContent("Crude oil futures");
    expect(commodityDecisionPanel).toHaveTextContent("Rebar futures");
    expect(commodityDecisionPanel).toHaveTextContent("影子评估样本不足");
    expect(commodityDecisionPanel).toHaveTextContent("最低样本 20");
    expect(commodityDecisionPanel).toHaveTextContent("还差 3");
    expect(commodityDecisionPanel).toHaveTextContent("进入公式前仍需历史回测、相关性检验、权重审批和版本记录");
    const promotionRulePack = within(crisisEvidence).getByLabelText("候选商品转正规则包");
    expect(promotionRulePack).toHaveTextContent("规则只用于审批前复核，不改变 Crisis Score 公式");
    expect(promotionRulePack).toHaveTextContent("待人工判断 2");
    expect(promotionRulePack).toHaveTextContent("不建议进入公式 4");
    expect(promotionRulePack).toHaveTextContent("准入检查：样本>=20 / 危机样本>=5 / 相关性可读 / 命中率可读");
    expect(promotionRulePack).toHaveTextContent("规则版本 shadow_rule_v1");
    expect(promotionRulePack).toHaveTextContent("样本阈值 >=20 个重叠样本");
    expect(promotionRulePack).toHaveTextContent("危机样本阈值 >=5 个高 Crisis Score 样本");
    expect(promotionRulePack).toHaveTextContent("相关性阈值 |corr|>=0.20 才可直接通过");
    const auditNote = within(promotionRulePack).getByLabelText("shadow_rule_v1 审计注记");
    expect(auditNote).toHaveTextContent("shadow_rule_v1 审计注记");
    expect(auditNote).toHaveTextContent("用途：商品候选进入公式前的影子复核");
    expect(auditNote).toHaveTextContent("边界：不写入 Crisis Score，不改变权重");
    expect(auditNote).toHaveTextContent("审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交");
    const formulaBoundary = within(promotionRulePack).getByLabelText("Crisis Score 商品公式输入边界");
    expect(formulaBoundary).toHaveTextContent("正式输入");
    expect(formulaBoundary).toHaveTextContent("Nanhua commodity index · NH0100.NHF / NHCI.NH");
    expect(formulaBoundary).toHaveTextContent("已纳入 Crisis Score 公式");
    expect(formulaBoundary).toHaveTextContent("影子候选");
    expect(formulaBoundary).toHaveTextContent("Copper futures / Crude oil futures");
    expect(formulaBoundary).toHaveTextContent("当前未计入 Crisis Score");
    expect(promotionRulePack).toHaveTextContent("Copper futures");
    expect(promotionRulePack).toHaveTextContent("待人工判断");
    expect(promotionRulePack).toHaveTextContent("相关性偏弱，需人工复核");
    expect(promotionRulePack).toHaveTextContent("Crude oil futures");
    expect(promotionRulePack).toHaveTextContent("Rebar futures");
    expect(promotionRulePack).toHaveTextContent("不建议进入公式");
    expect(promotionRulePack).toHaveTextContent("样本不足，先补齐历史数据");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 样本检查 通过 41/20");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 危机样本检查 通过 11/5");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 相关性检查 待人工判断 0.00");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 命中率检查 通过 55.0%");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 样本检查 未通过 17/20");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 危机样本检查 未通过 缺失/5");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 相关性检查 未通过 缺失");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 命中率检查 未通过 缺失");
    expect(crisisEvidence).toHaveTextContent("先补齐样本不足品种的历史数据");
    expect(crisisEvidence).toHaveTextContent("样本不足：Rebar futures 17/20，还差 3");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：RB / I / AL / AU");
    await user.click(within(crisisEvidence).getByRole("button", { name: "按建议选择" }));
    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("已按 Crisis Score 建议选择：RB / I / AL / AU");
    expect(commodityPanel).toHaveTextContent("下一步先预估商品期货");
    expect(commodityPanel).toHaveTextContent("4/7");
    expect(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铝/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /黄金/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铜/ })).not.toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /原油/ })).not.toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /南华指数/ })).not.toBeChecked();
    await user.click(within(commodityPanel).getByRole("button", { name: /预估明细刷新/ }));
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，88 行");
    expect(crisisEvidence).toHaveTextContent("最低样本 20");
    expect(screen.queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
  });

  it("copies the commodity promotion rule audit pack from the full evidence panel", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const originalWindowClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      renderWorkbenchApp(["/macro-toolkit"]);

      const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
      const promotionRulePack = within(crisisEvidence).getByLabelText("候选商品转正规则包");
      const copyButton = within(promotionRulePack).getByRole("button", { name: "复制审计包" });
      expect(copyButton).toBeEnabled();

      fireEvent.click(copyButton);

      expect(promotionRulePack).not.toHaveTextContent("复制失败");
      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Crisis Score 商品候选审计包")),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("分析日期 2026-04-30"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("source_version macro_toolkit_mock"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("vendor_version choice+tushare"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("rule_version rv_macro_toolkit_ui_v1"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version none"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("规则版本 shadow_rule_v1"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("用途：商品候选进入公式前的影子复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("边界：不写入 Crisis Score，不改变权重"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("人工复核队列 Copper futures / Crude oil futures"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("补历史样本队列 Rebar futures / Iron ore futures / Aluminum futures / Gold futures"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("处理顺序 下一步：先补齐样本不足品种，再复核铜、原油的相关性与命中率"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "正式商品输入 Nanhua commodity index · NH0100.NHF / NHCI.NH · source choice · latest 2026-04-10 · rows 120 · value 1075.20 · 已纳入 Crisis Score 公式",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "候选来源 Copper futures · CA.COPPER · aliases CU0 / CU0.SHF · matched CU0 · tushare · latest 2026-04-10 · report 2026-04-10 · 同日 · rows 120 · 当前未计入 Crisis Score",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "候选来源 Rebar futures · COMMODITY.RB · aliases RB0 / RB0.SHF · matched RB0 · tushare · latest 2026-04-10 · report 2026-04-10 · 同日 · rows 120 · 当前未计入 Crisis Score",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 待人工判断 · 相关性偏弱，需人工复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 样本检查 通过 41/20"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 相关性检查 待人工判断 0.00"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Rebar futures · 不建议进入公式 · 样本不足，先补齐历史数据"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Rebar futures · 危机样本检查 未通过 缺失/5"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不建议进入公式 4"));
      await waitFor(() => expect(promotionRulePack).toHaveTextContent("审计包已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
      if (originalWindowClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalWindowClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });

  it("copies the commodity admission approval pack from the full evidence panel", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const originalWindowClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      renderWorkbenchApp(["/macro-toolkit"]);

      const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
      const approvalPack = within(crisisEvidence).getByLabelText("商品候选审批材料");
      fireEvent.click(within(approvalPack).getByRole("button", { name: "复制审批材料" }));

      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Crisis Score 商品候选审批材料")),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("规则版本 rv_macro_crisis_commodity_admission_v1"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("影子公式 rv_macro_crisis_score_shadow_commodity_v1"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("shadow delta +0.04"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("Copper futures · 继续观察 · 相关性偏弱，需人工复核。"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("样本 41/20"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("危机样本 11/5"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("审批前不改变正式 Crisis Score"));
      await waitFor(() => expect(approvalPack).toHaveTextContent("审批材料已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
      if (originalWindowClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalWindowClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });

  it("loads full analysis in the background after the core screen", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const coreCrisisCard = {
      key: "crisis_score_cn",
      title: "Crisis Score",
      stance: "完整结果待加载",
      tone: "neutral",
      score: null,
      evidence: ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
    } as const;
    const coreSignalCards = [
      coreCrisisCard,
      ...analysisEnvelope.result.signal_cards.filter((card) => card.key !== "crisis_score_cn"),
    ];
    const coreEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        runtime_status: {
          analysis_scope: "core",
          deferred_sections: [
            {
              key: "capability_results",
              label: "功能结果",
              status: "deferred",
            },
          ],
        },
        capability_results: [],
        signal_cards: coreSignalCards,
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        return options?.detail === "full" ? analysisEnvelope : coreEnvelope;
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByText("完整结果待加载")).toBeInTheDocument();
    const crisisSignalCard = screen
      .getAllByText("Crisis Score")
      .map((node) => node.closest(".macro-toolkit-signal-card"))
      .find((node): node is HTMLElement => node instanceof HTMLElement);
    expect(crisisSignalCard).toBeTruthy();
    expect(crisisSignalCard).toHaveTextContent("待加载");
    expect(crisisSignalCard).not.toHaveTextContent("缺失");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(0);
    expect(screen.queryByLabelText("Crisis Score 数据来源")).not.toBeInTheDocument();
    expect(screen.queryByText("影子评估结果")).not.toBeInTheDocument();

    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(1), {
      timeout: 3_000,
    });
    expect(calls).toContainEqual({ detail: "full", historyLimit: 430 });
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("5/5");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(1);

    const fullDataHealth = await screen.findByLabelText("数据健康总览");
    await user.click(within(fullDataHealth).getByRole("button", { name: /需要补齐来源数据/ }));
    expect(sourceBackfillCalls).toEqual([
      {
        alias: "M0041813",
        startDate: undefined,
        endDate: "2026-04-30",
        sources: undefined,
      },
    ]);
    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(2));
  });

  it("shows the Nanhua business alias when the Crisis Score input uses the system series id", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const envelopeWithSystemNanhuaSeries = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const systemInputs = requireInputEvidenceInputs(result).map((input) =>
            input.field === "nanhua"
              ? {
                  ...input,
                  aliases: [],
                  series_id: "NHCI.NH",
                  source: "fact_commodity_futures_daily",
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: systemInputs,
                  sources: ["fact_commodity_futures_daily"],
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: systemInputs,
                sources: ["fact_commodity_futures_daily"],
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithSystemNanhuaSeries,
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const commodityInputTile = requireClosestElement(
      within(crisisEvidence).getAllByText("商品期货输入")[0]?.closest(".macro-toolkit-metric") ?? null,
      "commodity input tile",
    );
    expect(commodityInputTile).toHaveTextContent("Nanhua commodity index");
    expect(commodityInputTile).toHaveTextContent("NH0100.NHF");
    expect(commodityInputTile).toHaveTextContent("NHCI.NH");
    expect(commodityInputTile.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NH0100.NHF"));
    expect(commodityInputTile.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NHCI.NH"));
  });

  it("uses backend-provided commodity refresh suggestions before field-name fallbacks", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const envelopeWithBackendRefreshSuggestions = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            result: {
              ...result.result,
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  suggested_refresh_products: ["CU", "SC"],
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithBackendRefreshSuggestions,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：CU / SC");
    expect(crisisEvidence).not.toHaveTextContent("建议刷新品种：RB / I / AL / AU");
    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["CU", "SC"],
      dryRun: true,
    });
  });

  it("groups Crisis Score warning and missing inputs into actionable gaps", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const missingWarnings = ["HS300_MISSING", "DR007_MISSING", "NANHUA_MISSING", "AA_5Y_MISSING"];
    const missingFields = new Set(["hs300", "dr007", "nanhua", "aa_5y"]);
    const envelopeWithCrisisGaps = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const gapInputs = requireInputEvidenceInputs(result).map((input) =>
            missingFields.has(input.field)
              ? {
                  ...input,
                  available: false,
                  row_count: 0,
                  latest_date: null,
                  source: null,
                  value: null,
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            status: "degraded" as const,
            warnings: missingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: gapInputs,
                  missing_inputs: missingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: gapInputs,
                missing_inputs: missingWarnings,
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithCrisisGaps,
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    expect(gapList).toHaveTextContent("股票风险输入");
    expect(gapList).toHaveTextContent("HS300 close");
    expect(gapList).toHaveTextContent("HS300_MISSING");
    expect(gapList).toHaveTextContent("利率与流动性输入");
    expect(gapList).toHaveTextContent("DR007");
    expect(gapList).toHaveTextContent("DR007_MISSING");
    expect(gapList).toHaveTextContent("商品期货输入");
    expect(gapList).toHaveTextContent("Nanhua commodity index");
    expect(gapList).toHaveTextContent("NANHUA_MISSING");
    expect(gapList).toHaveTextContent("曲线与信用输入");
    expect(gapList).toHaveTextContent("AA credit yield 5Y");
    expect(gapList).toHaveTextContent("AA_5Y_MISSING");
    expect(gapList).toHaveTextContent("缺失不按 0 处理");
  });

  it("offers available refresh actions from the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const missingWarnings = ["NANHUA_MISSING", "NCD_3M_MISSING"];
    const envelopeWithActionableGaps = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        data_health: {
          ...analysisEnvelope.result.data_health!,
          repair_items: (analysisEnvelope.result.data_health?.repair_items ?? []).map((item) =>
            item.alias === "M0041813"
              ? {
                  ...item,
                  scope: "full",
                  reference_date: "2026-04-30",
                  action: {
                    kind: "source_backfill_required",
                    label: "需要补齐来源数据",
                    enabled: true,
                    reason: "可触发宏观来源补齐；完成后重新运行完整分析确认。",
                    analysis_detail: "full",
                  },
                }
              : item,
          ),
        },
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const baseInputs = requireInputEvidenceInputs(result);
          const gapInputs = [
            ...baseInputs.map((input) =>
              input.field === "nanhua"
                ? {
                    ...input,
                    available: false,
                    row_count: 0,
                    latest_date: null,
                    source: null,
                    value: null,
                }
                : input,
            ),
            {
              field: "ncd_3m",
              label: "3M NCD",
              aliases: ["M0041813"],
              warning: "NCD_3M_MISSING",
              required: true,
              available: false,
              row_count: 0,
              latest_date: null,
              series_id: "NCD.SHIBOR.3M",
              source: null,
              value: null,
            },
          ];
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            status: "degraded" as const,
            warnings: missingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: gapInputs,
                  missing_inputs: missingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: gapInputs,
                missing_inputs: missingWarnings,
              },
            },
          };
        }),
      },
    };
    const envelopeAfterSourceBackfill = {
      ...envelopeWithActionableGaps,
      result: {
        ...envelopeWithActionableGaps.result,
        capability_results: envelopeWithActionableGaps.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const nextMissingWarnings = ["NANHUA_MISSING"];
          const nextInputs = requireInputEvidenceInputs(result).filter((input) => input.field !== "ncd_3m");
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            warnings: nextMissingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: nextInputs,
                  missing_inputs: nextMissingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: nextInputs,
                missing_inputs: nextMissingWarnings,
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () =>
        sourceBackfillCalls.length ? envelopeAfterSourceBackfill : envelopeWithActionableGaps,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.source_backfill_refresh",
          },
          result: {
            refresh: {
              status: "completed",
              alias: options.alias,
              series_ids: ["NCD.SHIBOR.3M"],
              total_added: 42,
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);
    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: true,
    });
    await waitFor(() => expect(gapList).toHaveTextContent("商品期货预估完成"));
    expect(gapList).toHaveTextContent("预计可补齐最低样本");

    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));
    await waitFor(() =>
      expect(sourceBackfillCalls).toEqual([
        {
          alias: "M0041813",
          startDate: undefined,
          endDate: "2026-04-30",
          sources: undefined,
        },
      ]),
    );
    await waitFor(() => expect(gapList).not.toHaveTextContent("NCD_3M_MISSING"));
    expect(gapList).toHaveTextContent("NANHUA_MISSING");
    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("已补齐，完整分析已重读");
  });

  it("keeps source gap feedback partial when full analysis still reports same-group missing inputs", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const crisisResult = analysisEnvelope.result.capability_results.find((result) => result.key === "crisis_score_cn");
    if (!crisisResult) {
      throw new Error("Missing Crisis Score fixture");
    }
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const ncdInput: MacroToolkitInputEvidenceFixture = {
      field: "ncd_3m",
      label: "3M NCD",
      aliases: ["M0041813"],
      warning: "NCD_3M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "NCD.SHIBOR.3M",
      source: null,
      value: null,
    };
    const shiborInput: MacroToolkitInputEvidenceFixture = {
      field: "shibor_1m",
      label: "1M SHIBOR",
      aliases: ["M0041813"],
      warning: "SHIBOR_1M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "SHIBOR.1M",
      source: null,
      value: null,
    };
    const initialEnvelope = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      ncdInput,
      shiborInput,
    ], ["NCD_3M_MISSING", "SHIBOR_1M_MISSING"]);
    const partialEnvelope = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      shiborInput,
    ], ["SHIBOR_1M_MISSING"]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => (sourceBackfillCalls.length ? partialEnvelope : initialEnvelope),
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("完整分析已重读，仍有缺口");
    expect(repairFeedback).toHaveTextContent("SHIBOR_1M_MISSING");
    await waitFor(() => expect(gapList).not.toHaveTextContent("NCD_3M_MISSING"));
    expect(gapList).toHaveTextContent("SHIBOR_1M_MISSING");
  });

  it("keeps source gap failure feedback inside the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const crisisResult = analysisEnvelope.result.capability_results.find((result) => result.key === "crisis_score_cn");
    if (!crisisResult) {
      throw new Error("Missing Crisis Score fixture");
    }
    const ncdInput: MacroToolkitInputEvidenceFixture = {
      field: "ncd_3m",
      label: "3M NCD",
      aliases: ["M0041813"],
      warning: "NCD_3M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "NCD.SHIBOR.3M",
      source: null,
      value: null,
    };
    const envelopeWithSourceGap = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      ncdInput,
    ], ["NCD_3M_MISSING"]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithSourceGap,
      refreshMacroSourceBackfill: async () => {
        throw new Error("source backfill unavailable");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("补齐失败，缺口仍需处理");
    expect(repairFeedback).toHaveTextContent("source backfill unavailable");
    expect(gapList).toHaveTextContent("NCD_3M_MISSING");
  });

  it("labels commodity preview failures as estimates in the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async () => {
        throw new Error("commodity preview unavailable");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("预估失败，缺口仍需处理");
    expect(repairFeedback).toHaveTextContent("commodity preview unavailable");
  });

  it("previews Crisis Score suggested commodity futures and queues refresh from the evidence panel", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    let completedRefreshCount = 0;
    const refreshedAnalysisEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const updatedInputs = requireInputEvidenceInputs(result).map((input) =>
            input.field === "nanhua"
              ? {
                  ...input,
                  row_count: 22,
                  latest_date: "2026-06-01",
                  source: "tushare",
                  value: 3187.42,
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: updatedInputs,
                  latest_dates: ["2026-06-01"],
                  sources: ["tushare"],
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: updatedInputs,
                latest_dates: ["2026-06-01"],
                sources: ["tushare"],
              },
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  shadow_evaluation_short_count: 0,
                  shadow_evaluation_ready_count: 6,
                  shadow_evaluation_short_items: [],
                  shadow_evaluation_status_counts: { review_ready: 6 },
                  shadow_evaluation_next_step: "样本已补齐；进入人工复核和权重审批。",
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        if (options?.detail === "full" && completedRefreshCount > 0) {
          return refreshedAnalysisEnvelope;
        }
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        if (!options?.dryRun) {
          completedRefreshCount += 1;
        }
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：RB / I / AL / AU");

    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    expect(refreshCalls).toHaveLength(1);
    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: true,
    });
    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("已按 Crisis Score 建议选择：RB / I / AL / AU");
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，88 行");
    expect(commodityPanel).toHaveTextContent("Crisis Score 样本预估");
    expect(commodityPanel).toHaveTextContent("预计可补齐最低样本");
    expect(commodityPanel).toHaveTextContent("建议刷新商品期货");
    expect(commodityPanel).toHaveTextContent("Rebar futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Iron ore futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Aluminum futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Gold futures 17/20，预计 +22，可补齐至 20/20");
    expect(
      within(commodityPanel).getByRole("button", { name: "刷新商品期货：刷新并重算证据" }),
    ).toBeEnabled();
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    const gapRefreshButton = within(gapList).getByRole("button", { name: "按建议刷新并重读" });
    expect(gapRefreshButton).toBeEnabled();
    expect(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铝/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /黄金/ })).toBeChecked();

    await user.click(gapRefreshButton);

    expect(refreshCalls[1]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: false,
    });
    await waitFor(() =>
      expect(commodityPanel).toHaveTextContent("商品期货刷新已排队，4 个品种，等待后台任务完成"),
    );
    expect(commodityPanel).toHaveTextContent("商品期货刷新已排队，等待后台任务完成。");
    expect(commodityPanel).not.toHaveTextContent("完整分析证据已重新读取");
    expect(commodityPanel).not.toHaveTextContent("Crisis Score 样本缺口变化");
    const reloadedCrisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const operationsConsoleAfterCommodity = await screen.findByTestId("macro-toolkit-operations-console");
    const commodityWorkQueue = within(operationsConsoleAfterCommodity).getByTestId("macro-toolkit-committee-work-queue");
    const commoditySignoff = within(commodityWorkQueue).getByLabelText("投委会签核轨道");
    expect(commoditySignoff).toHaveTextContent("数据运营负责人");
    expect(commoditySignoff).toHaveTextContent("阻断签核");
    expect(commoditySignoff).toHaveTextContent("数据健康");
    expect(commodityWorkQueue).toHaveTextContent("商品期货刷新");
    expect(commodityWorkQueue).toHaveTextContent("回执待复核");
    expect(within(reloadedCrisisEvidence).queryByLabelText("Crisis Score 样本刷新闭环")).not.toBeInTheDocument();
  });

  it("shows remaining Crisis Score sample gaps when the commodity preview is still short", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async (options) => {
        const response = await baseClient.refreshCommodityFutures(options);
        if (!options?.dryRun) {
          return response;
        }
        return {
          ...response,
          result: {
            ...response.result,
            refresh: {
              ...response.result.refresh,
              estimated_total_rows: 4,
              estimated_trading_days: 1,
              products: response.result.refresh.products?.map((product) =>
                typeof product === "string"
                  ? product
                  : {
                      ...product,
                      estimated_rows: 1,
                    },
              ),
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapSummaryTile = requireClosestElement(
      within(crisisEvidence).getByText("缺口提示").closest(".macro-toolkit-metric"),
      "gap summary tile",
    );
    expect(gapSummaryTile).toHaveTextContent("4");
    expect(gapSummaryTile.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("COMMODITY_SAMPLE_SHORT"),
    );
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    expect(gapList).toHaveTextContent("COMMODITY_SAMPLE_SHORT");
    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，4 行");
    expect(commodityPanel).toHaveTextContent("Crisis Score 样本预估");
    expect(commodityPanel).toHaveTextContent("预计仍有样本缺口");
    expect(commodityPanel).toHaveTextContent("刷新后仍不会闭环");
    expect(gapList).not.toHaveTextContent("按建议刷新并重读");
    expect(commodityPanel).toHaveTextContent("Rebar futures 17/20，预计 +1，预计到 18/20，还差 2");
    expect(commodityPanel).toHaveTextContent("Iron ore futures 17/20，预计 +1，预计到 18/20，还差 2");
    expect(
      within(commodityPanel).getByRole("button", { name: "刷新商品期货：仍有缺口，谨慎刷新" }),
    ).toBeEnabled();
  });

  it("keeps Crisis Score sample gaps pending while queued commodity refresh waits for the worker", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    let completedRefreshCount = 0;
    const partiallyRefreshedEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            result: {
              ...result.result,
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  shadow_evaluation_short_count: 2,
                  shadow_evaluation_ready_count: 4,
                  shadow_evaluation_short_items: [
                    {
                      field: "rebar",
                      label: "Rebar futures",
                      sample_count: 19,
                      minimum_sample_count: 20,
                      sample_gap: 1,
                      latest_date: "2026-04-30",
                    },
                    {
                      field: "iron_ore",
                      label: "Iron ore futures",
                      sample_count: 19,
                      minimum_sample_count: 20,
                      sample_gap: 1,
                      latest_date: "2026-04-30",
                    },
                  ],
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        if (options?.detail === "full" && completedRefreshCount > 0) {
          return partiallyRefreshedEnvelope;
        }
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        if (!options?.dryRun) {
          completedRefreshCount += 1;
        }
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);
    await user.click(within(gapList).getByRole("button", { name: "按建议刷新并重读" }));

    expect(refreshCalls[1]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: false,
    });
    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    await waitFor(() =>
      expect(commodityPanel).toHaveTextContent("商品期货刷新已排队，4 个品种，等待后台任务完成"),
    );
    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("商品期货刷新已排队。");
    expect(repairFeedback).toHaveTextContent("等待后台任务完成");
    const reloadedCrisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(within(reloadedCrisisEvidence).queryByLabelText("Crisis Score 样本刷新闭环")).not.toBeInTheDocument();
    expect(reloadedCrisisEvidence).not.toHaveTextContent("完整分析已重读，仍有缺口");
    expect(reloadedCrisisEvidence).toHaveTextContent("COMMODITY_SAMPLE_SHORT");
  });

  it("previews selected commodity futures before refreshing full evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        const products = options?.products ?? ["RB", "I", "CU", "AL", "SC", "AU", "NHCI"];
        const isDryRun = options?.dryRun ?? false;
        const productNames: Record<string, string> = {
          CU: "铜",
          SC: "原油",
          AU: "黄金",
          NHCI: "南华指数",
        };
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.commodity_futures_refresh",
          },
          result: {
            refresh: {
              status: isDryRun ? "dry_run" : "completed",
              dry_run: isDryRun,
              start_date: "2026-04-01",
              end_date: "2026-04-30",
              product_count: products.length,
              row_count: isDryRun ? 0 : products.length * 22,
              estimated_total_rows: isDryRun ? products.length * 22 : undefined,
              estimated_trading_days: isDryRun ? 22 : undefined,
              before_status: isDryRun
                ? undefined
                : {
                    materialized: true,
                    status: "ok",
                    table: "fact_commodity_futures_daily",
                    row_count: 120,
                    latest_trade_date: "2026-05-20",
                    source_vendors: ["tushare"],
                    coverage: {
                      target_product_count: 7,
                      available_product_count: 5,
                      available_products: ["CU", "AL", "SC", "AU", "NHCI"],
                      missing_products: ["RB", "I"],
                    },
                    nanhua_input: {
                      status: "hit",
                      product_code: "NHCI",
                      series_id: "NH0100.NHF",
                      system_series_id: "NHCI.NH",
                      latest_trade_date: "2026-05-20",
                      latest_value: 3007.05,
                      row_count: 18,
                      source_version: "sv_tushare_index_daily_nhci_old",
                      vendor_version: "vv_tushare_index_daily_NHCI_20260520",
                      rule_version: "rv_commodity_daily_v1",
                    },
                  },
              after_status: isDryRun
                ? undefined
                : {
                    materialized: true,
                    status: "ok",
                    table: "fact_commodity_futures_daily",
                    row_count: 154,
                    latest_trade_date: "2026-06-01",
                    source_vendors: ["tushare"],
                    coverage: {
                      target_product_count: 7,
                      available_product_count: 7,
                      available_products: ["RB", "I", "CU", "AL", "SC", "AU", "NHCI"],
                      missing_products: [],
                    },
                    nanhua_input: {
                      status: "hit",
                      product_code: "NHCI",
                      series_id: "NH0100.NHF",
                      system_series_id: "NHCI.NH",
                      latest_trade_date: "2026-06-01",
                      latest_value: 3187.42,
                      row_count: 22,
                      source_version: "sv_tushare_index_daily_nhci_new",
                      vendor_version: "vv_tushare_index_daily_NHCI_20260601",
                      rule_version: "rv_commodity_daily_v1",
                    },
                  },
              summary: isDryRun
                ? {
                    table: "fact_commodity_futures_daily",
                    row_count_before: 120,
                    row_count_after: 120,
                    row_count_delta: 0,
                    latest_trade_date_before: "2026-05-20",
                    latest_trade_date_after: "2026-05-20",
                    available_product_count_before: 5,
                    available_product_count_after: 5,
                    target_product_count: 7,
                    newly_available_products: [],
                    missing_products_after: ["RB", "I"],
                    nanhua_status_before: "hit",
                    nanhua_status_after: "hit",
                    nanhua_latest_date_before: "2026-05-20",
                    nanhua_latest_date_after: "2026-05-20",
                    nanhua_latest_value_after: 3007.05,
                    source_vendors_after: ["tushare"],
                    dry_run: true,
                  }
                : {
                    table: "fact_commodity_futures_daily",
                    row_count_before: 120,
                    row_count_after: 154,
                    row_count_delta: 34,
                    latest_trade_date_before: "2026-05-20",
                    latest_trade_date_after: "2026-06-01",
                    available_product_count_before: 5,
                    available_product_count_after: 7,
                    target_product_count: 7,
                    newly_available_products: ["RB", "I"],
                    missing_products_after: [],
                    nanhua_status_before: "hit",
                    nanhua_status_after: "hit",
                    nanhua_latest_date_before: "2026-05-20",
                    nanhua_latest_date_after: "2026-06-01",
                    nanhua_latest_value_after: 3187.42,
                    source_vendors_after: ["tushare"],
                    dry_run: false,
                  },
              products: products.map((product) => {
                const productCode = product === "NHCI" ? "NH0100.NHF" : product;
                return {
                  product_code: productCode,
                  name_zh: productNames[product] ?? product,
                  row_count: isDryRun ? undefined : 22,
                  estimated_rows: isDryRun ? 22 : undefined,
                  latest_date: isDryRun ? undefined : "2026-04-30",
                  latest_value: product === "NHCI" && !isDryRun ? 3187.42 : undefined,
                  series_id:
                    product === "NHCI"
                      ? "NH0100.NHF"
                      : product === "CU"
                        ? "CA.COPPER"
                        : product === "AL"
                          ? "CA.ALUMINUM"
                          : `COMMODITY.${product}`,
                  vendor: isDryRun ? "estimate_only" : "tushare",
                };
              }),
              table: "fact_commodity_futures_daily",
              rule_version: "rv_commodity_daily_v1",
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("已授权");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(within(commodityPanel).getByRole("button", { name: /预估明细刷新/ })).toBeEnabled();
    expect(within(commodityPanel).getByRole("button", { name: /刷新商品期货/ })).toBeEnabled();
    expect(within(commodityPanel).getByRole("checkbox", { name: /南华指数/ })).toBeChecked();
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ }));
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ }));
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /铝/ }));

    await user.click(within(commodityPanel).getByRole("button", { name: /预估明细刷新/ }));

    expect(refreshCalls[0]).toEqual({
      endDate: "2026-04-30",
      products: ["CU", "SC", "AU", "NHCI"],
      dryRun: true,
    });
    const dryRunSummaries = await screen.findAllByText(/商品期货预估完成/);
    expect(dryRunSummaries[0]).toHaveTextContent("4 个品种，88 行");
    expect(dryRunSummaries[0]).toHaveTextContent("22 个交易日");
    const dryRunResult = await screen.findByLabelText("商品期货刷新结果");
    expect(dryRunResult).toHaveTextContent("预计可写");
    expect(dryRunResult).toHaveTextContent("预估基线");
    expect(dryRunResult).toHaveTextContent("120 → 120");
    expect(dryRunResult).toHaveTextContent("+0");
    expect(dryRunResult).toHaveTextContent("覆盖 5/7 → 5/7");
    expect(dryRunResult).toHaveTextContent("缺失 RB / I");
    expect(dryRunResult).toHaveTextContent("南华 2026-05-20 → 2026-05-20");
    expect(dryRunResult).toHaveTextContent("estimate_only");
    expect(dryRunResult).toHaveTextContent("CU / CA.COPPER");
    expect(dryRunResult).toHaveTextContent("NHCI / NH0100.NHF");
    expect(dryRunResult).toHaveTextContent("fact_commodity_futures_daily");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(0);
    expect(screen.queryByTestId("crisis-gap-repair-feedback")).not.toBeInTheDocument();

    await user.click(within(commodityPanel).getByRole("button", { name: /刷新商品期货/ }));

    expect(refreshCalls[1]).toEqual({
      endDate: "2026-04-30",
      products: ["CU", "SC", "AU", "NHCI"],
      dryRun: false,
    });
    const refreshSummaries = await screen.findAllByText(/商品期货刷新完成/);
    expect(refreshSummaries[0]).toHaveTextContent("4 个品种，88 行");
    const completedResult = await screen.findByLabelText("商品期货刷新结果");
    expect(completedResult).toHaveTextContent("Crisis Score 南华输入已更新");
    expect(completedResult).toHaveTextContent("刷新后闭环");
    expect(completedResult).toHaveTextContent("120 → 154");
    expect(completedResult).toHaveTextContent("+34");
    expect(completedResult).toHaveTextContent("2026-05-20 → 2026-06-01");
    expect(completedResult).toHaveTextContent("5/7 → 7/7");
    expect(completedResult).toHaveTextContent("新增 RB / I");
    expect(completedResult).toHaveTextContent("缺失 无");
    expect(completedResult).toHaveTextContent("tushare");
    expect(completedResult).toHaveTextContent("已写入");
    expect(completedResult).toHaveTextContent("2026-04-30");
    expect(completedResult).toHaveTextContent("3187.42");
    await waitFor(() => expect(calls).toContainEqual({ detail: "full" }));
    const repairFeedback = screen.queryByTestId("crisis-gap-repair-feedback");
    if (repairFeedback) {
      expect(repairFeedback).not.toHaveTextContent("正在刷新并重读完整分析");
    }
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
  });

  it("keeps commodity futures permission fallback tied to the commodity resource", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: undefined,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
    expect(permissionTile).toHaveTextContent("待确认");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
  });

  it("shows commodity futures data health before a refresh is clicked", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            ...scriptsEnvelope.result.commodity_futures_refresh!,
            status: {
              materialized: true,
              status: "ok",
              table: "fact_commodity_futures_daily",
              row_count: 154,
              latest_trade_date: "2026-04-30",
              source_vendors: ["tushare"],
              coverage: {
                target_product_count: 7,
                available_product_count: 5,
                available_products: ["CU", "AL", "SC", "AU", "NHCI"],
                missing_products: ["RB", "I"],
              },
              nanhua_input: {
                status: "hit",
                product_code: "NHCI",
                series_id: "NH0100.NHF",
                system_series_id: "NHCI.NH",
                latest_trade_date: "2026-04-30",
                latest_value: 3187.42,
                row_count: 22,
                source_version: "sv_tushare_index_daily_nhci",
                vendor_version: "vv_tushare_index_daily_NHCI_20260430",
                rule_version: "rv_commodity_daily_v1",
              },
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    await waitFor(() => expect(within(commodityPanel).getByText("南华输入")).toBeInTheDocument());
    const nanhuaTile = within(commodityPanel).getByText("南华输入").closest(".macro-toolkit-metric");
    expect(nanhuaTile?.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NH0100.NHF"));
    expect(commodityPanel).toHaveTextContent("NH0100.NHF");
    expect(commodityPanel).toHaveTextContent("2026-04-30");
    expect(commodityPanel).toHaveTextContent("3187.42");
    expect(commodityPanel).toHaveTextContent("覆盖品种");
    expect(commodityPanel).toHaveTextContent("5/7");
    expect(commodityPanel).toHaveTextContent("数据来源");
    expect(commodityPanel).toHaveTextContent("tushare");
  });

  it("shows commodity futures refresh permission and blocks unauthorized actions", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            permission: {
              mode: "scoped_refresh",
              allowed: false,
              user_id: "commodity-user",
              role: "viewer",
              identity_source: "header",
              resource: "macro_toolkit.commodity_futures",
              actions: ["dry_run", "refresh"],
            },
          },
        },
      }),
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("未授权");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("user commodity-user"),
    );
    expect(commodityPanel).toHaveTextContent("缺少商品期货刷新授权");
    expect(commodityPanel).toHaveTextContent("macro_toolkit.commodity_futures");
    expect(commodityPanel).toHaveTextContent("dry_run / refresh");
    expect(commodityPanel).toHaveTextContent("commodity-user");
    expect(commodityPanel).toHaveTextContent("viewer");

    const dryRunButton = within(commodityPanel).getByRole("button", { name: /预估明细刷新/ });
    const refreshButton = within(commodityPanel).getByRole("button", { name: /刷新商品期货/ });
    expect(dryRunButton).toBeDisabled();
    expect(refreshButton).toBeDisabled();
    await user.click(dryRunButton);
    expect(refreshCalls).toHaveLength(0);
  });

  it("shows pending commodity futures permission before scoped refresh is confirmed", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            ...scriptsEnvelope.result.commodity_futures_refresh!,
            permission: {
              mode: "scoped_refresh",
              user_id: "anonymous",
              role: "viewer",
              identity_source: "fallback",
              resource: "macro_toolkit.commodity_futures",
              actions: ["dry_run", "refresh"],
            },
          },
        },
      }),
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("待确认");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("user anonymous"),
    );
    expect(commodityPanel).toHaveTextContent("商品期货刷新授权待确认");
    expect(commodityPanel).toHaveTextContent("macro_toolkit.commodity_futures");
    expect(commodityPanel).toHaveTextContent("dry_run / refresh");
    expect(commodityPanel).toHaveTextContent("action refresh");
    expect(commodityPanel).toHaveTextContent("scope store");
    expect(commodityPanel).toHaveTextContent("anonymous");
    expect(commodityPanel).toHaveTextContent("viewer");

    const dryRunButton = within(commodityPanel).getByRole("button", { name: /预估明细刷新/ });
    const refreshButton = within(commodityPanel).getByRole("button", { name: /刷新商品期货/ });
    expect(dryRunButton).toBeDisabled();
    expect(refreshButton).toBeDisabled();
    await user.click(dryRunButton);
    expect(refreshCalls).toHaveLength(0);
  });

  it("shows a readable commodity futures permission error when the backend rejects refresh", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        throw new Error("User is not allowed to refresh macro_toolkit.commodity_futures.");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    await user.click(within(commodityPanel).getByRole("button", { name: /预估明细刷新/ }));

    expect(refreshCalls).toHaveLength(1);
    expect(
      (await within(commodityPanel).findAllByText(/当前账号没有商品期货刷新权限/, {}, { timeout: 5_000 })).length,
    ).toBeGreaterThan(0);
    expect(
      (await within(commodityPanel).findAllByText(/macro_toolkit\.commodity_futures:refresh/, {}, { timeout: 5_000 }))
        .length,
    ).toBeGreaterThan(0);
  });

  it("does not trigger source backfill for unsupported aliases even when action is enabled", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            repair_items: [
              {
                type: "stale",
                scope: "full",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                reference_date: "2026-04-30",
                suggested_action: "Refresh CU0 after source update.",
                action: {
                  kind: "source_backfill_required",
                  label: "Refresh CU0 source",
                  enabled: true,
                  reason: "Backend should not enable unsupported aliases.",
                  analysis_detail: "full",
                },
                tags: ["source"],
              },
            ],
          },
        },
      }),
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        throw new Error("Unsupported alias should not refresh");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const dataHealth = await screen.findByLabelText("数据健康总览");
    expect(dataHealth).toHaveTextContent("CU0");
    expect(dataHealth).toHaveTextContent("Backend should not enable unsupported aliases.");
    expect(within(dataHealth).queryByRole("button", { name: "Refresh CU0 source" })).not.toBeInTheDocument();
    expect(sourceBackfillCalls).toEqual([]);
  });

  it("turns non-auto-refreshable data blockers into a manual review escalation packet", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "full",
            deferred_sections: [],
          },
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "full",
            repair_items: [
              {
                type: "stale",
                scope: "full",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                reference_date: "2026-04-30",
                suggested_action: "Refresh CU0 after source update.",
                action: {
                  kind: "source_backfill_required",
                  label: "Refresh CU0 source",
                  enabled: true,
                  reason: "Backend should not enable unsupported aliases.",
                  analysis_detail: "full",
                },
                tags: ["source"],
              },
            ],
          },
        },
      }),
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        throw new Error("Unsupported alias should not refresh");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    await waitFor(() => expect(currentRepairStatus).toHaveTextContent("CU0"));
    expect(currentRepairStatus).toHaveTextContent("人工复核升级处理包");
    expect(currentRepairStatus).toHaveTextContent("不可自动补齐");
    expect(currentRepairStatus).toHaveTextContent("升级处理");
    expect(currentRepairStatus).toHaveTextContent("提交影响");
    expect(currentRepairStatus).toHaveTextContent("待复核后提交");
    expect(currentRepairStatus).toHaveTextContent("人工复核记录");
    expect(within(currentRepairStatus).getByRole("link", { name: "升级人工复核" })).toHaveAttribute(
      "href",
      "#macro-toolkit-data-health-detail",
    );

    await user.click(within(currentRepairStatus).getByRole("link", { name: "升级人工复核" }));

    const actionLocator = within(currentRepairStatus).getByLabelText("投委会动作定位回执");
    expect(actionLocator).toHaveTextContent("不可自动补齐");
    expect(actionLocator).toHaveTextContent("人工复核记录");
    expect(actionLocator).toHaveTextContent("提交影响");
    expect(actionLocator).toHaveTextContent("待复核后提交");
    expect(actionLocator).toHaveTextContent("升级处理");
    expect(within(actionLocator).queryByRole("button", { name: "执行来源补齐" })).not.toBeInTheDocument();
    expect(sourceBackfillCalls).toEqual([]);
  });

  it("splits full-analysis data blockers into auto, manual, and capability lanes", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "full",
            deferred_sections: [],
          },
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "full",
            repair_items: [
              {
                type: "missing",
                scope: "full",
                priority: "high",
                key: "indicator:ncd_3m",
                alias: "M0041813",
                label: "3M NCD",
                suggested_action: "补齐 M0041813 后重新运行完整宏观分析；缺失项不能按 0 处理。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要补齐来源数据",
                  enabled: true,
                  reason: "可触发宏观来源补齐；完成后重新运行完整分析确认。",
                  analysis_detail: "full",
                },
              },
              {
                type: "stale",
                scope: "full",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                suggested_action: "CU0 最新数据落后；刷新上游后再确认。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要刷新来源",
                  enabled: false,
                  reason: "当前没有已接入的一键宏观序列刷新接口。",
                  analysis_detail: "full",
                },
              },
              {
                type: "degraded",
                scope: "full",
                priority: "medium",
                key: "capability:leading_indicator",
                label: "宏观领先指标",
                suggested_action: "宏观领先指标 当前 degraded：PMI_MISSING；补齐输入证据后重新运行完整宏观分析。",
                action: {
                  kind: "load_full_analysis",
                  label: "重新完整分析",
                  enabled: true,
                  reason: "补齐输入证据后重新运行完整宏观分析确认状态。",
                  analysis_detail: "full",
                },
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    const repairTriage = await within(currentRepairStatus).findByLabelText("投委会阻断分层");
    expect(repairTriage).toHaveTextContent("自动补齐");
    expect(repairTriage).toHaveTextContent("3M NCD");
    expect(repairTriage).toHaveTextContent("执行来源补齐");
    expect(repairTriage).toHaveTextContent("人工升级");
    expect(repairTriage).toHaveTextContent("CU0");
    expect(repairTriage).toHaveTextContent("升级处理");
    expect(repairTriage).toHaveTextContent("能力复核");
    expect(repairTriage).toHaveTextContent("宏观领先指标");
    expect(repairTriage).toHaveTextContent("复核完整分析");
    expect(repairTriage).toHaveTextContent("宏观策略负责人");
  });

  it("shows the full analysis action in the runtime strip when core capability results are deferred", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "capability_results",
                label: "功能结果",
                status: "deferred",
              },
            ],
          },
          capability_results: [],
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeStrip = await screen.findByLabelText("宏观工具运行状态");
    expect(within(runtimeStrip).getByRole("button", { name: "查看完整分析" })).toBeInTheDocument();
  });

  it("lets the first-screen deferred evidence action create a reviewable full-analysis receipt", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const analysisCalls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const coreEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        runtime_status: {
          analysis_scope: "core",
          deferred_sections: [
            {
              key: "capabilities",
              label: "功能补齐方案",
              status: "deferred",
            },
          ],
        },
        capability_results: [],
        capabilities: [],
        data_health: {
          ...analysisEnvelope.result.data_health!,
          analysis_scope: "core",
          source_coverage: {
            hit_count: 0,
            total_count: 0,
            hit_rate: null,
            latest_date: null,
            deferred: true,
            missing_aliases: [],
          },
          capability_results: {
            complete: 0,
            degraded: 0,
            unavailable: 0,
            total_count: 0,
            deferred: true,
          },
          capability_plan: {
            ready_count: 0,
            wired_count: 0,
            total_count: 0,
            deferred: true,
          },
          deferred_sections: ["capabilities"],
          repair_items: [
            {
              type: "deferred",
              scope: "core",
              priority: "low",
              key: "deferred:capabilities",
              alias: null,
              label: "capabilities",
              source_table: null,
              latest_date: null,
              reference_date: "2026-06-01",
              stale_days: null,
              suggested_action: "打开完整分析后确认 capabilities，不把首屏延后加载当作缺失。",
              action: {
                kind: "load_full_analysis",
                label: "查看完整分析",
                enabled: true,
                reason: "首屏延后加载，完整分析可确认。",
                analysis_detail: "full",
              },
              tags: ["deferred"],
            },
          ],
        },
      },
    };
    const fullEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        runtime_status: {
          analysis_scope: "full",
          deferred_sections: [],
        },
        data_health: {
          ...analysisEnvelope.result.data_health!,
          analysis_scope: "full",
          repair_items: [],
          deferred_sections: [],
        },
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        analysisCalls.push(options);
        return options?.detail === "full" ? fullEnvelope : coreEnvelope;
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const investmentBrief = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatus = within(investmentBrief).getByLabelText("投委会当前处理状态");
    await waitFor(() => expect(currentRepairStatus).toHaveTextContent("能力边界"));
    expect(currentRepairStatus).toHaveTextContent("完整分析复核包");
    expect(within(currentRepairStatus).getByRole("button", { name: "复核完整分析" })).toBeInTheDocument();

    await user.click(within(currentRepairStatus).getByRole("button", { name: "复核完整分析" }));

    await waitFor(() => expect(analysisCalls.some((item) => item?.detail === "full")).toBe(true));
    const operationsConsole = await screen.findByTestId("macro-toolkit-operations-console");
    const receipt = within(operationsConsole).getByTestId("macro-toolkit-action-receipt");
    await waitFor(() => expect(receipt).toHaveTextContent("完整分析复核"));
    expect(receipt).toHaveTextContent("已完成");
    expect(receipt).toHaveTextContent("完整分析回执");

    const investmentBriefAfterReceipt = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatusAfterReceipt = within(investmentBriefAfterReceipt).getByLabelText("投委会当前处理状态");
    expect(currentRepairStatusAfterReceipt).toHaveTextContent("回执待复核");
    expect(currentRepairStatusAfterReceipt).toHaveTextContent("完整分析回执");
    expect(
      within(currentRepairStatusAfterReceipt).getByRole("button", { name: "复核数据健康回执" }),
    ).toBeInTheDocument();
    const committeePackAfterReceipt = within(investmentBriefAfterReceipt).getByLabelText("投委会材料包");
    expect(within(committeePackAfterReceipt).getByLabelText("投委会材料包-数据健康")).toHaveTextContent("回执待复核");

    await user.click(within(currentRepairStatusAfterReceipt).getByRole("button", { name: "复核数据健康回执" }));

    const investmentBriefAfterSignoff = await screen.findByTestId("macro-toolkit-investment-brief");
    const currentRepairStatusAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会当前处理状态");
    expect(currentRepairStatusAfterSignoff).toHaveTextContent("签核已确认");
    const committeePackAfterSignoff = within(investmentBriefAfterSignoff).getByLabelText("投委会材料包");
    expect(within(committeePackAfterSignoff).getByLabelText("投委会材料包-数据健康")).toHaveTextContent("已签核");
  });

  it("summarizes deferred runtime sections in observation language", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "capability_results",
                label: "功能结果",
                status: "deferred",
              },
              {
                key: "source_checks",
                label: "功能补齐方案",
                status: "deferred",
              },
            ],
          },
          capability_results: [],
          data_health: {
            ...analysisEnvelope.result.data_health!,
            analysis_scope: "core",
            source_coverage: {
              hit_count: 0,
              total_count: 0,
              hit_rate: null,
              latest_date: null,
              deferred: true,
              missing_aliases: [],
            },
            capability_results: {
              complete: 0,
              degraded: 0,
              unavailable: 0,
              total_count: 0,
              deferred: true,
            },
            deferred_sections: ["capability_results", "source_checks"],
            repair_items: [
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:source_checks",
                alias: null,
                label: "source_checks",
                source_table: null,
                latest_date: null,
                reference_date: "2026-04-30",
                stale_days: null,
                suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
                tags: ["deferred"],
              },
            ],
          },
        },
      }),
    } as ApiClient;
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 0,
          refetchOnWindowFocus: false,
        },
      },
    });

    render(<MacroToolkitPage mode="observation" />, {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </ApiClientProvider>
      ),
    });

    const runtimeStrip = await screen.findByLabelText("宏观工具运行状态");
    expect(runtimeStrip).toHaveTextContent("待完整分析");
    expect(runtimeStrip).toHaveTextContent("2 项证据延后确认");
    expect(runtimeStrip).toHaveTextContent("待完整分析 · 2 项证据延后确认");
    expect(runtimeStrip).toHaveTextContent("下一步：查看完整分析");
    expect(runtimeStrip).not.toHaveTextContent("证据延后确认查看完整分析");
    expect(runtimeStrip).not.toHaveTextContent("功能结果");
    expect(runtimeStrip).not.toHaveTextContent("功能补齐方案");
    expect(runtimeStrip).not.toHaveTextContent("capability_results");
    const evidenceTraceSummary = await screen.findByLabelText("证据追踪摘要");
    expect(evidenceTraceSummary).toHaveTextContent("完整分析补充项待确认");
    expect(evidenceTraceSummary).not.toHaveTextContent("有延后证据待确认");
    expect(evidenceTraceSummary).toHaveTextContent("1 项复核提示：完整分析补充项；完整分析后复核。");
    expect(evidenceTraceSummary).not.toHaveTextContent("1 项复核提示：延后证据；完整分析后复核。");
    expect(evidenceTraceSummary).not.toHaveTextContent("延后证据待完整分析确认。");
    expect(evidenceTraceSummary).not.toHaveTextContent("完整分析可确认延后证据，不把首屏延后加载当作缺失。");
    expect(evidenceTraceSummary).not.toHaveTextContent("延后证据 / 延后证据");
    expect(evidenceTraceSummary).toHaveTextContent("能力证据");
    expect(evidenceTraceSummary).toHaveTextContent("能力证据延后确认不按 0 处理。");
    expect(evidenceTraceSummary).not.toHaveTextContent("待完整分析确认延后确认");
    expect(evidenceTraceSummary).not.toHaveTextContent("能力证据完整分析后确认");
    expect(evidenceTraceSummary).not.toHaveTextContent("待完整分析确认能力证据完整分析后确认");
    expect(evidenceTraceSummary).not.toHaveTextContent("能力结果");
    expect(evidenceTraceSummary).not.toHaveTextContent("来源证据");
    expect(evidenceTraceSummary).not.toHaveTextContent("source_checks");
    expect(evidenceTraceSummary).not.toHaveTextContent("capability_results");
    expect(within(runtimeStrip).getByRole("button", { name: "查看完整分析" })).toBeInTheDocument();
  });

  it("does not mark Hason runtime outputs ready when freshness is unknown", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            missing_runtime_outputs: [],
            stale_runtime_outputs: [],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) => ({
              ...item,
              freshness_status: "unknown",
              freshness_basis: "file_modified_date",
              content_date: null,
              content_date_min: null,
              content_date_max: null,
              modified_date: null,
              reference_date: "2026-04-30",
            })),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("unknown");
    expect(runtimeGaps).toHaveTextContent("final_signal.csv");
    expect(runtimeGaps).toHaveTextContent("crowding_latest.csv");
    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategyPanel).toHaveTextContent("Runtime outputs");
    expect(hasonStrategyPanel).toHaveTextContent("unknown · 2");
    expect(runtimeGaps).not.toHaveTextContent("runtime outputs · current");
  });

  it("shows Hason mixed CSV content date ranges", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "mixed",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-29",
                    content_date_max: "2026-04-30",
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("mixed");
    expect(runtimeGaps).toHaveTextContent("content 2026-04-29..2026-04-30");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("shows Hason invalid CSV content date counts", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "invalid_date",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 1,
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 0,
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("invalid_date");
    expect(runtimeGaps).toHaveTextContent("1 invalid date");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("shows Hason unknown CSV content freshness without treating file time as proof", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "unknown",
                    freshness_basis: "csv_content",
                    content_date: null,
                    content_date_min: null,
                    content_date_max: null,
                    content_date_invalid_count: 0,
                    modified_date: "2026-04-30",
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    freshness_basis: "csv_content",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 0,
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("final_signal.csv: unknown CSV content date");
    expect(runtimeGaps).toHaveTextContent("file 2026-04-30");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("labels fully current Hason output as observation-ready, not formal use", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "observation_ready",
            readiness: {
              ...hasonStrategy.readiness,
              ready_modules: hasonStrategy.readiness.total_modules,
              partial_modules: 0,
              missing_modules: 0,
              missing_script_count: 0,
              ratio: 1,
            },
            modules: hasonStrategy.modules.map((module) => ({
              ...module,
              status: "integrated",
              available_scripts: module.scripts,
              missing_scripts: [],
            })),
            runtime_output_status: "current",
            runtime_output_gaps: [],
            missing_runtime_outputs: [],
            stale_runtime_outputs: [],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) => ({
              ...item,
              freshness_status: "current",
              freshness_basis: "csv_content",
              content_date: "2026-04-30",
              content_date_min: "2026-04-30",
              content_date_max: "2026-04-30",
              content_date_invalid_count: 0,
              modified_date: "2026-04-30",
            })),
            observation_only: true,
            formal_use_allowed: false,
            formal_metric_id: null,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategyPanel).toHaveTextContent("观察就绪");
    expect(hasonStrategyPanel).toHaveTextContent("observation-only");
    expect(hasonStrategyPanel).toHaveTextContent("no formal MTR");
    expect(hasonStrategyPanel).toHaveTextContent("Runtime outputs");
    expect(hasonStrategyPanel).toHaveTextContent("current");
    expect(hasonStrategyPanel).not.toHaveTextContent("Runtime outputsready");
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(1)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(2)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(4)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    const marketStateModule = await screen.findByTestId("macro-toolkit-hason-module-market_state");
    expect(marketStateModule).toHaveTextContent("script-chain complete");
    expect(marketStateModule).not.toHaveTextContent("integrated");
  });

  it("counts all available Hason source trace scripts while keeping the detail preview bounded", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const sourceTrace = Array.from({ length: 7 }, (_, index) => ({
      script: `trace_script_${index + 1}`,
      filename: `trace_script_${index + 1}.py`,
      group: "Hason",
      available: true,
      modules: index === 0 ? ["market_state", "risk_management"] : ["market_state"],
    }));
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: sourceTrace,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    const scriptTraceMetric = hasonStrategyPanel.querySelector("[data-testid='macro-toolkit-hason-script-trace']");
    expect(scriptTraceMetric).toHaveTextContent("Script trace");
    expect(scriptTraceMetric).toHaveTextContent("7");
    expect(scriptTraceMetric).toHaveTextContent("trace_script_1");
    const scriptTraceDetail = scriptTraceMetric?.querySelector("small");
    expect(scriptTraceDetail).toHaveAttribute(
      "title",
      expect.stringContaining("trace_script_1[market_state+risk_management]"),
    );
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("trace_script_5"));
    expect(scriptTraceDetail).not.toHaveAttribute("title", expect.stringContaining("trace_script_6"));
  });

  it("renders legacy Hason source trace entries without module context", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: [
              {
                script: "legacy_trace",
                filename: "legacy_trace.py",
                group: "legacy",
                available: true,
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const scriptTraceMetric = await screen.findByTestId("macro-toolkit-hason-script-trace");
    expect(scriptTraceMetric).toHaveTextContent("legacy_trace");
  });

  it("keeps missing Hason scripts in the trace preview with module context", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: [
              {
                script: "rebalance_cn",
                filename: null,
                group: null,
                available: false,
                modules: ["allocation"],
              },
              {
                script: "risk_parity_cn",
                filename: "risk_parity_cn.py",
                group: "allocation",
                available: true,
                modules: ["allocation"],
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const scriptTraceMetric = await screen.findByTestId("macro-toolkit-hason-script-trace");
    expect(scriptTraceMetric).toHaveTextContent("2");
    const scriptTraceDetail = scriptTraceMetric.querySelector("small");
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("rebalance_cn[allocation]:missing"));
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("risk_parity_cn[allocation]"));
  });

  it("surfaces model readiness blockers as observation-only instead of healthy", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const readinessDetail = await screen.findByTestId("macro-toolkit-model-readiness-detail");

    expect(readinessDetail).toHaveTextContent("model readiness");
    expect(readinessDetail).toHaveTextContent("observation-only");
    expect(readinessDetail).toHaveTextContent("DCC-GARCH missing output");
    expect(readinessDetail).toHaveTextContent("CTA Trend missing output");
    expect(readinessDetail).toHaveTextContent("Risk Monitor missing output");
    expect(readinessDetail).toHaveTextContent("dcc_latest.csv");
    expect(readinessDetail).toHaveTextContent("dcc_results.csv");
    expect(readinessDetail).toHaveTextContent("cta_results.csv");
    expect(readinessDetail).toHaveTextContent("risk_log.csv");
    expect(readinessDetail).toHaveTextContent("risk_state.csv");
    expect(readinessDetail).not.toHaveTextContent("DCC-GARCH artifact-backed");
    expect(readinessDetail).not.toHaveTextContent("CTA Trend artifact-backed");
    expect(readinessDetail).not.toHaveTextContent("Risk Monitor artifact-backed");
  });

  it("presents model readiness as a signal matrix before raw script artifacts", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const modelReadiness = macroCoreModelReadinessFixtures();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          model_readiness: modelReadiness,
          readiness_summary: {
            total_count: modelReadiness.length,
            artifact_backed_count: 2,
            degraded_count: 8,
            status_counts: { artifact_backed: 2, missing_output: 8 },
            observation_only: true,
            formal_use_allowed: false,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    const artifactDetail = await screen.findByTestId("macro-toolkit-script-artifact-detail");

    expectElementBefore(signalMatrix, artifactDetail);
    expect(signalMatrix).toHaveTextContent("model signals");
    expect(signalMatrix).toHaveTextContent("artifact-backed 2/10");
    expect(signalMatrix).toHaveTextContent("Merrill Clock");
    expect(signalMatrix).toHaveTextContent("Crisis Score");
    expect(signalMatrix).toHaveTextContent("Bond Futures Four-Factor Trend");
    expect(signalMatrix).toHaveTextContent("Funding Conditions / Flow");
    expect(signalMatrix).toHaveTextContent("Crowding");
    expect(signalMatrix).toHaveTextContent("DCC-GARCH");
    expect(signalMatrix).toHaveTextContent("CTA Trend");
    expect(signalMatrix).toHaveTextContent("missing output");
    expect(signalMatrix.querySelector("a")).toHaveAttribute("href", "#macro-toolkit-script-artifact-detail");
  });

  it("opens artifact-backed acceptance actions for each core model signal", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const modelReadiness = macroCoreModelReadinessFixtures();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          model_readiness: modelReadiness,
          readiness_summary: {
            total_count: modelReadiness.length,
            artifact_backed_count: 2,
            degraded_count: 8,
            status_counts: { artifact_backed: 2, missing_output: 8 },
            observation_only: true,
            formal_use_allowed: false,
          },
        },
      }),
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    const coreModelLabels = [
      "Merrill Clock",
      "Crisis Score",
      "Bond Futures Four-Factor Trend",
      "Funding Conditions / Flow",
      "Crowding",
      "DCC-GARCH",
      "CTA Trend",
      "Bond Futures Basis / IRR / Safety Margin",
      "Final Signal Aggregator",
      "Risk Monitor",
    ];

    for (const label of coreModelLabels) {
      const detail = await openModelSignalDetail(signalMatrix, user, label);

      expect(detail).toHaveTextContent(label);
      expect(detail).toHaveTextContent("Expected outputs");
      expect(detail).toHaveTextContent("/ui/macro/toolkit/scripts/run-chain");
      expect(detail).toHaveTextContent("Artifact-backed acceptance");
      expect(within(detail).getByTestId("macro-toolkit-model-signal-chain-preflight")).toBeEnabled();
      expect(within(detail).getByTestId("macro-toolkit-model-signal-chain-run")).toBeEnabled();
    }
  });

  it("runs the model chain from model evidence and surfaces the selected script receipt", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const chainCalls: Array<{ dryRun?: boolean; timeoutSeconds?: number }> = [];
    const client = {
      ...baseClient,
      runMacroToolkitScriptChain: async (options) => {
        chainCalls.push(options ?? {});
        return baseClient.runMacroToolkitScriptChain(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    let detail = await openModelSignalDetail(signalMatrix, user, "DCC-GARCH");
    await user.click(within(detail).getByTestId("macro-toolkit-model-signal-chain-preflight"));

    await waitFor(() => expect(chainCalls).toEqual([{ dryRun: true }]));
    detail = await screen.findByTestId("macro-toolkit-model-signal-detail");

    expect(detail).toHaveTextContent("Latest script run receipt");
    expect(detail).toHaveTextContent("dcc_garch_cn");
    expect(detail).toHaveTextContent("dry_run");
    expect(detail).toHaveTextContent("dcc_latest.csv");
    expect(detail).toHaveTextContent("dcc_results.csv");
    expect(detail).toHaveTextContent("dry_run_not_executed");

    detail = await openModelSignalDetail(signalMatrix, user, "CTA Trend");
    expect(detail).toHaveTextContent("CTA Trend");
    expect(detail).not.toHaveTextContent("Latest script run receipt");

    detail = await openModelSignalDetail(signalMatrix, user, "Risk Monitor");
    expect(detail).toHaveTextContent("Risk Monitor");
    expect(detail).not.toHaveTextContent("Latest script run receipt");
  });

  it("surfaces model-chain execution blockers inside the selected model evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      runMacroToolkitScriptChain: async () => {
        throw new Error("User is not allowed to execute macro_toolkit.script.");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    const detail = await openModelSignalDetail(signalMatrix, user, "DCC-GARCH");
    await user.click(within(detail).getByTestId("macro-toolkit-model-signal-chain-preflight"));

    await waitFor(() => {
      expect(screen.getByTestId("macro-toolkit-model-signal-detail")).toHaveTextContent("Latest run issue");
    });
    expect(screen.getByTestId("macro-toolkit-model-signal-detail")).toHaveTextContent(
      "User is not allowed to execute macro_toolkit.script.",
    );
  });

  it("keeps model-chain execution blockers scoped to the model that launched them", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      runMacroToolkitScriptChain: async () => {
        throw new Error("User is not allowed to execute macro_toolkit.script.");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    let detail = await openModelSignalDetail(signalMatrix, user, "DCC-GARCH");
    await user.click(within(detail).getByTestId("macro-toolkit-model-signal-chain-preflight"));

    await waitFor(() => {
      expect(screen.getByTestId("macro-toolkit-model-signal-detail")).toHaveTextContent("Latest run issue");
    });

    detail = await openModelSignalDetail(signalMatrix, user, "CTA Trend");

    expect(detail).toHaveTextContent("CTA Trend");
    expect(detail).not.toHaveTextContent("Latest run issue");
    expect(detail).not.toHaveTextContent("User is not allowed to execute macro_toolkit.script.");
  });

  it("labels shared-script receipts as script-level evidence instead of model-specific acceptance", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const modelReadiness = macroCoreModelReadinessFixtures();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          model_readiness: modelReadiness,
          readiness_summary: {
            total_count: modelReadiness.length,
            artifact_backed_count: 2,
            degraded_count: 8,
            status_counts: { artifact_backed: 2, missing_output: 8 },
            observation_only: true,
            formal_use_allowed: false,
          },
        },
      }),
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");
    let detail = await openModelSignalDetail(signalMatrix, user, "Funding Conditions / Flow");
    await user.click(within(detail).getByTestId("macro-toolkit-model-signal-chain-preflight"));

    await waitFor(() => {
      expect(screen.getByTestId("macro-toolkit-model-signal-detail")).toHaveTextContent("Latest script run receipt");
    });
    detail = screen.getByTestId("macro-toolkit-model-signal-detail");

    expect(detail).toHaveTextContent("Funding Conditions / Flow");
    expect(detail).toHaveTextContent("merrill_clock_cn");
    expect(detail).toHaveTextContent("shared script receipt");
    expect(detail).not.toHaveTextContent("Latest run receipt");
  });

  it("renders the model signal matrix from Hason fallback readiness when backend readiness is absent", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          model_readiness: undefined,
          readiness_summary: undefined,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const readinessDetail = await screen.findByTestId("macro-toolkit-model-readiness-detail");
    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");

    expect(readinessDetail).toHaveTextContent("signal_aggregator");
    expect(readinessDetail).toHaveTextContent("crisis_score_cn");
    expect(signalMatrix).toHaveTextContent("signal_aggregator");
    expect(signalMatrix).toHaveTextContent("crisis_score_cn");
    expect(signalMatrix).toHaveTextContent("boundary pending backend summary");
    expect(signalMatrix).toHaveTextContent("formal use blocked");
  });

  it("keeps the model signal matrix formal boundary conservative without a backend readiness summary", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const modelReadiness = [
      macroModelReadinessFixture({
        id: "crisis_score",
        label: "Crisis Score",
        script_name: "crisis_score_cn",
        expected_outputs: ["crisis_score_latest.csv"],
        readiness: "artifact_backed",
        evidence_level: "fresh_artifacts",
        date_basis: "csv_content",
        observation_only: false,
        formal_use_allowed: true,
        latest_modified_at: "2026-04-30T15:00:00+00:00",
        latest_content_date: "2026-04-30",
        missing_outputs: [],
        stale_outputs: [],
      }),
    ] satisfies NonNullable<MacroToolkitAnalysisEnvelope["result"]["model_readiness"]>;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          model_readiness: modelReadiness,
          readiness_summary: undefined,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const signalMatrix = await screen.findByTestId("macro-toolkit-model-signal-matrix");

    expect(signalMatrix).toHaveTextContent("boundary pending backend summary");
    expect(signalMatrix).toHaveTextContent("formal use blocked");
    expect(signalMatrix).not.toHaveTextContent("formal use allowed");
  });

  it("keeps the page frame and non-formal boundary visible while core analysis is still loading", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: () => new Promise(() => {}),
      getMacroToolkitScripts: () => new Promise(() => {}),
      getMacroToolkitStrategySummaries: () => new Promise(() => {}),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByTestId("macro-toolkit-tailwind-cockpit")).toBeInTheDocument();
    const boundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    expect(boundary).toHaveTextContent("非正式口径");
    expect(await screen.findByTestId("macro-toolkit-initial-analysis-loading")).toHaveTextContent(
      "核心分析加载中",
    );
    expect(await screen.findByRole("heading", { level: 2, name: "核心信号" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" })).toBeInTheDocument();
    expect(screen.queryByText("正在读取宏观工具")).not.toBeInTheDocument();
  });

  it("keeps macro observation loading copy read-only and free of tool controls", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: () => new Promise(() => {}),
      getMacroToolkitScripts: () => new Promise(() => {}),
      getMacroToolkitStrategySummaries: () => new Promise(() => {}),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const cockpit = await screen.findByTestId("macro-toolkit-tailwind-cockpit");
    const observationLoop = requireClosestElement(
      cockpit.querySelector("[aria-label='宏观观察首屏闭环']"),
      "macro observation loading loop",
    );
    expect(observationLoop).toHaveTextContent("来源待确认");
    expect(observationLoop).not.toHaveTextContent("已接入 2 类系统数据源");
    const loadingState = await screen.findByTestId("macro-toolkit-initial-analysis-loading");
    expect(loadingState).toHaveTextContent("观察结论和证据对照");
    expect(loadingState).not.toHaveTextContent("脚本注册表");
    expect(await screen.findByRole("heading", { level: 2, name: "信号风险对照" })).toBeInTheDocument();
    const loadingComparison = await screen.findByLabelText("信号风险对照");
    expect(loadingComparison).toHaveTextContent("观察证据加载中");
    expect(screen.queryByRole("heading", { level: 2, name: "核心信号" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "市场踩踏风险" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
  });

  it("shows strategy source versions when real factor snapshots are used", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const realStrategies = strategyEnvelope.result.strategy_summaries.map((strategy) =>
      strategy.key === "multi_factor_selection"
        ? {
            ...strategy,
            status: "complete" as const,
            warnings: [],
            primary_metric: { label: "真实入选数量", value: 1, unit: "" },
            result: {
              data_status: "complete",
              price_source: "choice_stock_daily_observation",
              factor_source: "choice_stock_factor_snapshot",
              as_of_date: "2026-05-06",
              factor_as_of_date: "2026-04-30",
              factor_date_status: "fallback",
              factor_source_versions: ["sv_factor"],
              factor_vendor_versions: ["vv_factor"],
              factor_rule_versions: ["rv_factor"],
              factor_run_ids: ["run-factor"],
            },
          }
        : strategy,
    );
    const choiceStockRefresh = strategyEnvelope.result.choice_stock_refresh!;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
            result: {
              ...strategyEnvelope.result,
              choice_stock_refresh: {
                ...choiceStockRefresh,
                daily_observation: {
                  ...choiceStockRefresh.daily_observation,
                  freshness_status: "current",
                  reference_date: "2026-05-06",
                  stale_days: 1,
                  fallback_mode: "none",
                  fallback_date: null,
                },
                factor_snapshot: {
                  ...choiceStockRefresh.factor_snapshot,
                  freshness_status: "stale",
                  reference_date: "2026-05-06",
                  stale_days: 9,
                  fallback_mode: "latest_available",
                  fallback_date: "2026-04-27",
                },
              },
              strategy_summaries: realStrategies,
            },
          }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 1/4");
    expect(strategySupply).toHaveTextContent("部分链路 0");
    expect(strategySupply).toHaveTextContent("股票历史 2026-04-30 · 已对齐");
    expect(strategySupply).toHaveTextContent("因子快照 2026-04-30 · 陈旧");
    expect(strategySupply).toHaveTextContent("fallback latest_available · 最近可用 2026-04-27");
    const multiFactorTitle = await screen.findByText("多因子选股");
    const multiFactorCard = multiFactorTitle.closest(".macro-toolkit-strategy-card");
    expect(multiFactorCard).not.toBeNull();
    expect(multiFactorCard).toHaveTextContent("choice_stock_factor_snapshot");
    expect(multiFactorCard).toHaveTextContent("2026-05-06");
    expect(multiFactorCard).toHaveTextContent("2026-04-30");
    expect(multiFactorCard).toHaveTextContent("最近快照");
    expect(multiFactorCard).toHaveTextContent("sv_factor");
    expect(multiFactorCard).toHaveTextContent("vv_factor");
    expect(multiFactorCard).toHaveTextContent("rv_factor");
    expect(multiFactorCard).toHaveTextContent("run-factor");
  });

  it("shows scoped Choice refresh permission as authorized with trace detail", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const choiceStockRefresh = strategyEnvelope.result.choice_stock_refresh!;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          choice_stock_refresh: {
            ...choiceStockRefresh,
            permission: {
              mode: "scoped_refresh",
              allowed: true,
              user_id: "stock-refresh-user",
              role: "viewer",
              identity_source: "header",
              resource: "macro_toolkit.choice_stock",
              actions: ["history", "factor_snapshot"],
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已授权");
    expect(permissionTile).not.toHaveTextContent("待确认");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user stock-refresh-user",
    );
  });

  it("shows latest Choice refresh run status beside authorization evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const choiceStockRefresh = strategyEnvelope.result.choice_stock_refresh!;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          choice_stock_refresh: {
            ...choiceStockRefresh,
            refresh: {
              status: "completed",
              run_id: "choice_stock_refresh:2026-04-30:done",
              report_date: "2026-04-30",
              trigger_mode: "terminal",
              history_row_count: 111,
              factor_row_count: 222,
              source_version: "sv_factor",
              vendor_version: "vv_factor",
              rule_version: "rv_choice_stock_refresh_v1",
              cache_version: "choice_stock_refresh_v1",
              permission: choiceStockRefresh.permission,
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已完成");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "run choice_stock_refresh:2026-04-30:done · report 2026-04-30 · trigger terminal · rows history 111 / factor 222 · source sv_factor · vendor vv_factor · rule rv_choice_stock_refresh_v1 · cache choice_stock_refresh_v1 · resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
  });

  it("shows Choice refresh failure category and reason in run evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const choiceStockRefresh = strategyEnvelope.result.choice_stock_refresh!;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          choice_stock_refresh: {
            ...choiceStockRefresh,
            refresh: {
              status: "failed",
              run_id: "choice_stock_refresh:2026-04-30:failed",
              report_date: "2026-04-30",
              trigger_mode: "terminal",
              history_row_count: 111,
              factor_row_count: null,
              failure_category: "ChoiceVendorError",
              failure_reason: "factor snapshot vendor unavailable",
              error_message: "ChoiceVendorError: factor snapshot vendor unavailable",
              permission: choiceStockRefresh.permission,
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("失败");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "run choice_stock_refresh:2026-04-30:failed · report 2026-04-30 · trigger terminal · rows history 111 / factor - · failure ChoiceVendorError: factor snapshot vendor unavailable · resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
  });

  it("shows price source versions when factor strategy is degraded", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const degradedStrategies = strategyEnvelope.result.strategy_summaries.map((strategy) =>
      strategy.key === "multi_factor_selection"
        ? {
            ...strategy,
            status: "degraded" as const,
            warnings: ["FUNDAMENTAL_FACTORS_NOT_MATERIALIZED"],
            primary_metric: null,
            result: {
              data_status: "degraded",
              price_source: "choice_stock_daily_observation",
              source_versions: ["sv_stock"],
              vendor_versions: ["vv_stock"],
              missing_factor_inputs: [
                "pe",
                "pb",
                "ps",
                "roe",
                "gross_margin",
                "three_month_return",
                "twelve_month_return",
                "volatility",
                "dividend_yield",
              ],
            },
          }
        : strategy,
    );
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          strategy_summaries: degradedStrategies,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 0/4");
    expect(strategySupply).toHaveTextContent("部分链路 1");
    expect(strategySupply).toHaveTextContent("降级 1");
    expect(strategySupply).toHaveTextContent("样例 3");
    const multiFactorTitle = await screen.findByText("多因子选股");
    const multiFactorCard = multiFactorTitle.closest(".macro-toolkit-strategy-card");
    expect(multiFactorCard).not.toBeNull();
    expect(multiFactorCard).toHaveTextContent("FUNDAMENTAL_FACTORS_NOT_MATERIALIZED");
    expect(multiFactorCard).toHaveTextContent("choice_stock_daily_observation");
    expect(multiFactorCard).toHaveTextContent("sv_stock");
    expect(multiFactorCard).toHaveTextContent("vv_stock");
    expect(multiFactorCard).toHaveTextContent("因子来源缺失");
    expect(multiFactorCard).toHaveTextContent("缺失输入");
    expect(multiFactorCard).toHaveTextContent(
      "pe / pb / ps / roe / gross_margin / three_month_return / twelve_month_return / volatility / dividend_yield",
    );
  });

  it("shows the read-only shadow portfolio report beside the current rule", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const shadowReport = {
      status: "complete",
      basis: "read_only_shadow",
      label: "影子组合报告",
      as_of_date: "2026-05-27",
      completed_periods: 13,
      factor_dates: [
        "2026-04-01",
        "2026-04-03",
        "2026-04-08",
        "2026-04-10",
        "2026-04-15",
        "2026-04-17",
        "2026-04-22",
        "2026-04-24",
        "2026-04-29",
        "2026-05-06",
        "2026-05-08",
        "2026-05-13",
        "2026-05-20",
        "2026-05-27",
      ],
      rule_version: "rv_macro_toolkit_shadow_portfolio_v1",
      tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
      warnings: ["READ_ONLY_SHADOW_NOT_PRODUCTION"],
      cost_model: {
        cost_bps: [0, 10, 20, 50],
        initial_build_included: true,
        final_liquidation_included: false,
      },
      benchmark: {
        key: "equal_weight_factor_universe",
        label: "因子池等权基准",
        total_return: -0.0211,
        max_drawdown: -0.0601,
      },
      portfolios: [
        {
          key: "current_baseline",
          label: "当前正式规则",
          role: "production_reference",
          total_return: -0.0448,
          excess_return: -0.0242,
          max_drawdown: -0.0558,
          win_rate: 0.25,
          average_turnover: 0.3247,
          average_count: 29.25,
          average_pe: 43.02,
          average_pb: 2.06,
          weights: { value: 0.3, quality: 0.25, momentum: 0.15, low_vol: 0.15, dividend: 0.15 },
          constraints: { pe_max: null, pb_max: null, turnover_cap: null },
          cost_results: [
            { cost_bps: 0, total_return: -0.0448, excess_return: -0.0242, max_drawdown: -0.0558 },
            { cost_bps: 20, total_return: -0.0505, excess_return: -0.0301, max_drawdown: -0.0578 },
            { cost_bps: 50, total_return: -0.058, excess_return: -0.038, max_drawdown: -0.061 },
          ],
          latest_holdings: [
            { rank: 1, stock_code: "600519.SH", industry: "食品饮料", score: 1.9, pe: 29.13, pb: 4.32, three_month_return: 0.0613 },
            { rank: 2, stock_code: "600001.SH", industry: "银行", score: 1.7, pe: 5.3, pb: 0.62, three_month_return: -0.011 },
          ],
        },
        {
          key: "deep_value_quality_pe80",
          label: "深度价值质量影子组合",
          role: "shadow_candidate",
          total_return: 0.3798,
          excess_return: 0.0674,
          max_drawdown: -0.0402,
          win_rate: 0.5,
          average_turnover: 0.3472,
          average_count: 26.92,
          average_pe: 31.08,
          average_pb: 2.42,
          weights: { value: 0.45, quality: 0.25, momentum: 0.05, low_vol: 0.1, dividend: 0.15 },
          constraints: { pe_max: 80, pb_max: null, turnover_cap: null },
          cost_results: [
            { cost_bps: 0, total_return: 0.3798, excess_return: 0.0674, max_drawdown: -0.0402 },
            { cost_bps: 20, total_return: 0.3593, excess_return: 0.0516, max_drawdown: -0.0447 },
            { cost_bps: 50, total_return: 0.3291, excess_return: 0.0282, max_drawdown: -0.0581 },
          ],
          latest_holdings: [
            { rank: 1, stock_code: "600519.SH", industry: "食品饮料", score: 2.0071, pe: 29.13, pb: 4.32, three_month_return: 0.0613 },
            { rank: 2, stock_code: "603008.SH", industry: "轻工制造", score: 1.9121, pe: 18.6, pb: 1.52, three_month_return: 0.0413 },
          ],
          admission: {
            status: "passed",
            label: "通过",
            summary: "可进入正式规则候选评审",
            criteria: [
              { key: "history_length", label: "历史周期", passed: true, actual: 13, threshold: ">=12" },
              {
                key: "cost_20bps_outperformance",
                label: "20bp 成本后胜出",
                passed: true,
                actual: { total_return: 0.3593, excess_return: 0.0516 },
                threshold: { total_return: ">-0.0505", excess_return: ">-0.0301" },
              },
              {
                key: "cost_50bps_outperformance",
                label: "50bp 成本后胜出",
                passed: true,
                actual: { total_return: 0.3291, excess_return: 0.0282 },
                threshold: { total_return: ">-0.058", excess_return: ">-0.038" },
              },
              { key: "drawdown", label: "最大回撤", passed: true, actual: -0.0402, threshold: ">=-0.0658" },
              { key: "diversification", label: "持仓分散度", passed: true, actual: 26.92, threshold: ">=15" },
              { key: "blocking_warnings", label: "阻断告警", passed: true, actual: [], threshold: "无" },
            ],
          },
        },
      ],
      period_returns: [
        {
          portfolio_key: "current_baseline",
          start_date: "2026-04-30",
          end_date: "2026-05-08",
          gross_return: -0.008,
          benchmark_return: -0.01,
          excess_return: 0.002,
          selected_count: 29,
          name_turnover: null,
          traded_notional: 1,
          cost_results: [{ cost_bps: 20, net_return: -0.01, cost: 0.002 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-04-30",
          end_date: "2026-05-08",
          gross_return: 0.031,
          benchmark_return: 0,
          excess_return: 0.031,
          selected_count: 27,
          name_turnover: null,
          traded_notional: 1,
          cost_results: [{ cost_bps: 20, net_return: 0.029, cost: 0.002 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-05-08",
          end_date: "2026-05-13",
          gross_return: -0.019,
          benchmark_return: -0.007,
          excess_return: -0.012,
          selected_count: 27,
          name_turnover: 0.2,
          traded_notional: 0.4,
          cost_results: [{ cost_bps: 20, net_return: -0.0198, cost: 0.0008 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-05-13",
          end_date: "2026-05-20",
          gross_return: 0.024,
          benchmark_return: 0.011,
          excess_return: 0.013,
          selected_count: 26,
          name_turnover: 0.3,
          traded_notional: 0.6,
          cost_results: [{ cost_bps: 20, net_return: 0.0228, cost: 0.0012 }],
        },
      ],
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          shadow_portfolio_report: shadowReport,
        } as never,
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const report = await screen.findByLabelText("影子组合报告");
    expect(report).toHaveTextContent("只读影子组合");
    expect(report).toHaveTextContent("当前正式规则");
    expect(report).toHaveTextContent("深度价值质量影子组合");
    expect(report).toHaveTextContent("+38.0%");
    expect(report).toHaveTextContent("+6.7%");
    expect(report).toHaveTextContent("20bp");
    expect(report).toHaveTextContent("+35.9%");
    expect(report).toHaveTextContent("PE≤80");
    expect(report).not.toHaveTextContent("PB≤");
    expect(report).not.toHaveTextContent("换手≤");
    expect(report).toHaveTextContent("600519.SH");
    const review = await screen.findByLabelText("影子组合稳健性审查");
    expect(review).toHaveTextContent("周期胜负");
    expect(review).toHaveTextContent("2赢 / 1输");
    expect(review).toHaveTextContent("最佳 +3.1% / 最差 -1.2%");
    expect(review).toHaveTextContent("20bp/50bp 均胜出");
    expect(review).toHaveTextContent("准入结论");
    expect(review).toHaveTextContent("通过");
    expect(review).toHaveTextContent("可进入正式规则候选评审");
    expect(review).toHaveTextContent("历史周期");
    expect(review).toHaveTextContent("持仓分散度");
    expect(review).toHaveTextContent("持仓重合 1/2");
    expect(review).toHaveTextContent("新增观察 603008.SH");
    expect(review).toHaveTextContent("正式独有 600001.SH");
    const evidencePack = await screen.findByLabelText("影子组合准入证据包");
    expect(evidencePack).toHaveTextContent("评审动作");
    expect(evidencePack).toHaveTextContent("进入正式候选评审");
    expect(evidencePack).toHaveTextContent("不自动替换正式规则");
    expect(evidencePack).toHaveTextContent("规则版本");
    expect(evidencePack).toHaveTextContent("rv_macro_toolkit_shadow_portfolio_v1");
    expect(evidencePack).toHaveTextContent("回测窗口");
    expect(evidencePack).toHaveTextContent("2026-04-01 → 2026-05-27 / 13周期");
    expect(evidencePack).toHaveTextContent("成本模型");
    expect(evidencePack).toHaveTextContent("0/10/20/50bp");
    expect(evidencePack).toHaveTextContent("choice_stock_daily_observation / choice_stock_factor_snapshot");
    expect(evidencePack).toHaveTextContent("只读影子评估，不能作为正式投研信号");
  });

  it("shows why the shadow portfolio report is temporarily unavailable", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          shadow_portfolio_report: {
            status: "unavailable",
            basis: "read_only_shadow",
            label: "影子组合报告",
            as_of_date: null,
            completed_periods: 0,
            factor_dates: [],
            rule_version: "rv_macro_toolkit_shadow_portfolio_v1",
            tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            warnings: ["READ_ONLY_SHADOW_NOT_PRODUCTION", "DUCKDB_BUSY", "DUCKDB_OPEN_FAILED: IOException"],
            cost_model: {
              cost_bps: [0, 10, 20, 50],
              initial_build_included: true,
              final_liquidation_included: false,
            },
            benchmark: null,
            portfolios: [],
            period_returns: [],
          },
        } as never,
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const report = await screen.findByLabelText("影子组合报告");
    expect(report).toHaveTextContent("影子组合报告暂不可用");
    expect(report).toHaveTextContent("本地股票历史库正在刷新或被落库任务占用");
    expect(report).toHaveTextContent("DUCKDB_BUSY");
  });

  it("keeps analytical boundary and failing sources visible when macro toolkit reads fail", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis?detail=core (502)");
      },
      getMacroToolkitScripts: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/scripts (502)");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis/strategy-summaries (502)");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const errorState = await screen.findByTestId("macro-toolkit-error-state");
    expect(errorState).toHaveTextContent("宏观工具暂不可用");
    expect(errorState).toHaveTextContent("分析/工具口径");
    expect(errorState).toHaveTextContent("非正式口径");
    expect(errorState).toHaveTextContent("macro_toolkit.analysis");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/analysis?detail=core");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/scripts");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/analysis/strategy-summaries");
    expect(await screen.findByRole("button", { name: /重试读取/ })).toBeInTheDocument();
  });

  it("keeps macro observation read failures readable without backend paths", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis?detail=core (502)");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis/strategy-summaries (502)");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const errorState = await screen.findByTestId("macro-toolkit-error-state");
    expect(errorState).toHaveTextContent("宏观观察暂不可用");
    expect(errorState).toHaveTextContent("只读宏观观察");
    expect(errorState).toHaveTextContent("读取核心分析失败");
    expect(errorState).toHaveTextContent("读取策略摘要失败");
    expect(errorState).toHaveTextContent("规则版本已记录");
    expect(errorState).not.toHaveTextContent("Request failed");
    expect(errorState).not.toHaveTextContent("/ui/macro/toolkit");
    expect(errorState).not.toHaveTextContent("rv_macro_toolkit_ui_v1");
    expect(errorState).not.toHaveTextContent("read-only macro observation");
    expect(await screen.findByRole("button", { name: /重试读取/ })).toBeInTheDocument();
  });

  it("surfaces a copyable macro toolkit read-scope request when reads are forbidden", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
      getMacroToolkitScripts: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
    } as ApiClient;

    try {
      renderWorkbenchApp(["/macro-toolkit"], { client });

      const errorState = await screen.findByTestId("macro-toolkit-error-state");
      expect(errorState).toHaveTextContent("缺少宏观工具读取权限");
      expect(errorState).toHaveTextContent("macro_toolkit/read");
      expect(errorState).toHaveTextContent("授权后点击重试读取");
      const permissionPanel = within(errorState).getByLabelText("宏观工具读取权限缺口");
      fireEvent.click(within(permissionPanel).getByRole("button", { name: "复制授权申请" }));

      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("申请授予 macro_toolkit/read")),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("resource=macro_toolkit"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("action=read"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("页面=/macro-toolkit"));
      await waitFor(() => expect(permissionPanel).toHaveTextContent("授权申请已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });
});
