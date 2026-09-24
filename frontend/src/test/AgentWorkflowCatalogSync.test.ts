/**
 * Agent 工作流目录前后端防漂移测试。
 *
 * 机制（与 AgentContractSync.test.ts 同款）：直接读取后端两个 catalog Python 源码
 * （financial_workflow_catalog.py / research_workflow_catalog.py），解析工作流 id、
 * slash 命令与 mapped intents，与前端硬编码副本（agentWorkbenchModel.ts 的
 * FINANCIAL_WORKFLOWS / RESEARCH_SHORTCUTS）比对：
 * - 后端目录新增/删除/换序/改名条目 → 本测试失败；
 * - 前端副本单方面改 id、slash 命令或 mappedIntents → 本测试失败。
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  buildFinancialWorkflowRequestBody,
  FINANCIAL_WORKFLOWS,
  RESEARCH_SHORTCUTS,
} from "../features/agent/lib/agentWorkbenchModel";

function readBackendCatalog(fileName: string) {
  return readFileSync(
    resolve(process.cwd(), "../backend/app/agent/runtime", fileName),
    "utf8",
  );
}

const FINANCIAL_CATALOG_SOURCE = readBackendCatalog("financial_workflow_catalog.py");
const RESEARCH_CATALOG_SOURCE = readBackendCatalog("research_workflow_catalog.py");

/** 解析模块级 `_SLASH_COMMANDS = {...}` 的 "命令": "workflow_id" 映射。 */
function parseSlashCommands(source: string): Record<string, string> {
  const block = /_SLASH_COMMANDS\s*=\s*\{([\s\S]*?)\}/.exec(source)?.[1];
  if (!block) {
    throw new Error("backend catalog is missing _SLASH_COMMANDS");
  }
  const mapping: Record<string, string> = {};
  for (const [, command, workflowId] of block.matchAll(/"([^"]+)":\s*"([^"]+)"/g)) {
    mapping[command] = workflowId;
  }
  return mapping;
}

/** 按声明顺序解析金融目录条目的 workflow_id 与 mapped_intents。 */
function parseFinancialWorkflows(
  source: string,
): { workflowId: string; mappedIntents: string[] }[] {
  const entries: { workflowId: string; mappedIntents: string[] }[] = [];
  for (const match of source.matchAll(
    /FinancialWorkflow\(\s*workflow_id="([^"]+)"[\s\S]*?mapped_intents=\[([^\]]*)\]/g,
  )) {
    entries.push({
      workflowId: match[1],
      mappedIntents: [...match[2].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]),
    });
  }
  if (entries.length === 0) {
    throw new Error("backend financial catalog has no FinancialWorkflow entries");
  }
  return entries;
}

/** 按声明顺序解析研究目录条目的 workflow_id。 */
function parseResearchWorkflowIds(source: string): string[] {
  const ids = [...source.matchAll(/ResearchWorkflow\(\s*workflow_id="([^"]+)"/g)].map(
    (match) => match[1],
  );
  if (ids.length === 0) {
    throw new Error("backend research catalog has no ResearchWorkflow entries");
  }
  return ids;
}

/** 解析 `_QUESTION_KEYWORDS` 中每个 workflow_id 的触发关键词。 */
function parseResearchQuestionKeywords(source: string): Record<string, string[]> {
  const block = /_QUESTION_KEYWORDS[^=]*=\s*\{([\s\S]*?)\}/.exec(source)?.[1];
  if (!block) {
    throw new Error("backend research catalog is missing _QUESTION_KEYWORDS");
  }
  const mapping: Record<string, string[]> = {};
  for (const [, workflowId, keywordTuple] of block.matchAll(/"([^"]+)":\s*\(([^)]*)\)/g)) {
    mapping[workflowId] = [...keywordTuple.matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
  }
  return mapping;
}

describe("金融工作流目录前后端防漂移（financial_workflow_catalog.py ↔ FINANCIAL_WORKFLOWS）", () => {
  const backendWorkflows = parseFinancialWorkflows(FINANCIAL_CATALOG_SOURCE);
  const backendSlashCommands = parseSlashCommands(FINANCIAL_CATALOG_SOURCE);

  it("工作流 id 与声明顺序一致", () => {
    expect(FINANCIAL_WORKFLOWS.map((workflow) => workflow.id)).toEqual(
      backendWorkflows.map((workflow) => workflow.workflowId),
    );
  });

  it("slash 命令与 workflow id 的映射一致（双向）", () => {
    expect(
      Object.fromEntries(
        FINANCIAL_WORKFLOWS.map((workflow) => [workflow.slashCommand, workflow.id]),
      ),
    ).toEqual(backendSlashCommands);
  });

  it("每个工作流的 mappedIntents 与后端 mapped_intents 一致（含顺序）", () => {
    for (const backend of backendWorkflows) {
      const frontend = FINANCIAL_WORKFLOWS.find(
        (workflow) => workflow.id === backend.workflowId,
      );
      expect(frontend, `missing frontend shortcut for ${backend.workflowId}`).toBeDefined();
      expect(frontend?.mappedIntents, backend.workflowId).toEqual(backend.mappedIntents);
    }
  });

  it("执行请求使用后端可识别的参数名（question=slash 命令，context.workflow_mode=execute）", () => {
    for (const workflow of FINANCIAL_WORKFLOWS) {
      const body = buildFinancialWorkflowRequestBody(workflow);
      expect(body.question).toBe(workflow.slashCommand);
      expect(body.context).toMatchObject({ workflow_mode: "execute" });
    }
    // 后端目录以 context.workflow_id 解析显式工作流请求；参数名改动会破坏前端契约。
    expect(FINANCIAL_CATALOG_SOURCE).toContain('context.get("workflow_id")');
  });
});

describe("研究工作流目录前后端防漂移（research_workflow_catalog.py ↔ RESEARCH_SHORTCUTS）", () => {
  const backendResearchIds = parseResearchWorkflowIds(RESEARCH_CATALOG_SOURCE);
  const backendKeywords = parseResearchQuestionKeywords(RESEARCH_CATALOG_SOURCE);
  const backendSlashCommands = parseSlashCommands(RESEARCH_CATALOG_SOURCE);

  it("每个后端研究工作流都有对应前端快捷入口，且 context 参数名/取值一致", () => {
    for (const workflowId of backendResearchIds) {
      const shortcut = RESEARCH_SHORTCUTS.find(
        (entry) => entry.context?.workflow_id === workflowId,
      );
      expect(shortcut, `missing frontend shortcut for ${workflowId}`).toBeDefined();
      expect(shortcut?.context?.intent, workflowId).toBe(workflowId);
    }
  });

  it("前端快捷问题文案命中后端触发关键词（plan 路径兜底）", () => {
    for (const workflowId of backendResearchIds) {
      const shortcut = RESEARCH_SHORTCUTS.find(
        (entry) => entry.context?.workflow_id === workflowId,
      );
      const keywords = backendKeywords[workflowId] ?? [];
      expect(
        keywords.some((keyword) =>
          (shortcut?.question ?? "").toLowerCase().includes(keyword.toLowerCase()),
        ),
        `question for ${workflowId} does not match any backend keyword`,
      ).toBe(true);
    }
  });

  it("研究 slash 命令只指向已注册的研究工作流", () => {
    for (const workflowId of Object.values(backendSlashCommands)) {
      expect(backendResearchIds).toContain(workflowId);
    }
  });

  it("后端研究目录以 context.workflow_id 解析显式请求", () => {
    expect(RESEARCH_CATALOG_SOURCE).toContain('context.get("workflow_id")');
  });
});
