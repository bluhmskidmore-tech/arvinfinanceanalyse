import fs from "node:fs";
import path from "node:path";

import ts from "typescript";
import { describe, expect, it } from "vitest";

type GuardRule = "raw_text_number_cast" | "decimal_like" | "literal_div_1e8";

type GuardEntry = {
  path: string;
  page: string;
  rule: GuardRule;
  count: number;
  reason: string;
  owner?: string;
  expires_on?: string;
};

type PolicyRegistry = {
  schema_version: string;
  policy_version: string;
  release_eligible: boolean;
  controlled_pages: string[];
  controlled_paths: string[];
  active_exceptions: GuardEntry[];
  pending_migrations: GuardEntry[];
};

const REPO_ROOT = path.resolve(import.meta.dirname, "../../..");
const REGISTRY_PATH = path.join(REPO_ROOT, "config", "exact_numeric_compat_registry.v1.json");
const SOURCE_FILE_PATTERN = /\.(ts|tsx)$/;
const TEST_FILE_PATTERN = /\.test\.[jt]sx?$/;
const EXCLUDED_DIR_SEGMENTS = new Set(["test", "mocks"]);

function loadRegistry(): PolicyRegistry {
  return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf8")) as PolicyRegistry;
}

function collectProductionFiles(absPath: string, acc: string[]): string[] {
  const stats = fs.statSync(absPath);
  if (stats.isFile()) {
    if (SOURCE_FILE_PATTERN.test(absPath) && !TEST_FILE_PATTERN.test(absPath)) {
      acc.push(absPath);
    }
    return acc;
  }
  for (const entry of fs.readdirSync(absPath, { withFileTypes: true })) {
    if (entry.isDirectory() && EXCLUDED_DIR_SEGMENTS.has(entry.name)) continue;
    collectProductionFiles(path.join(absPath, entry.name), acc);
  }
  return acc;
}

function isRawTextReference(node: ts.Expression): boolean {
  if (ts.isIdentifier(node)) {
    return node.text === "raw_text" || node.text === "rawText";
  }
  if (ts.isPropertyAccessExpression(node)) {
    return node.name.text === "raw_text" || node.name.text === "rawText";
  }
  if (ts.isElementAccessExpression(node) && ts.isStringLiteral(node.argumentExpression)) {
    return node.argumentExpression.text === "raw_text" || node.argumentExpression.text === "rawText";
  }
  return false;
}

function scanFile(sourcePath: string): Record<GuardRule, number> {
  const source = fs.readFileSync(sourcePath, "utf8");
  const sourceFile = ts.createSourceFile(
    sourcePath,
    source,
    ts.ScriptTarget.Latest,
    true,
    sourcePath.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  const counts: Record<GuardRule, number> = {
    raw_text_number_cast: 0,
    decimal_like: 0,
    literal_div_1e8: 0,
  };

  const visit = (node: ts.Node) => {
    if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.PlusToken && isRawTextReference(node.operand)) {
      counts.raw_text_number_cast += 1;
    }

    if (ts.isCallExpression(node) && node.arguments.length === 1 && isRawTextReference(node.arguments[0])) {
      const callee = node.expression.getText(sourceFile);
      if (callee === "Number" || callee === "parseFloat" || callee === "Number.parseFloat") {
        counts.raw_text_number_cast += 1;
      }
    }

    if (ts.isIdentifier(node) && node.text === "DecimalLike") {
      counts.decimal_like += 1;
    }

    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.SlashToken) {
      const divisorText = node.right.getText(sourceFile).replaceAll("_", "");
      if (Number(divisorText) === 100_000_000) {
        counts.literal_div_1e8 += 1;
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
  return counts;
}

describe("exact numeric policy guard", () => {
  it("keeps controlled production sources within the explicit compat baseline", () => {
    const registry = loadRegistry();
    expect(registry.schema_version).toBe("exact-numeric-compat-registry/v1");
    expect(registry.policy_version).toBe("exact-numeric-v1");
    expect(registry.controlled_pages).toEqual([
      "cashflow-projection",
      "bond-dashboard",
      "risk-home",
      "pnl-attribution",
      "risk-tensor",
      "decision-items",
      "balance-analysis",
      "dashboard-home",
    ]);

    const controlledFiles = registry.controlled_paths
      .flatMap((relativePath) => collectProductionFiles(path.join(REPO_ROOT, relativePath), []))
      .map((absPath) => path.relative(REPO_ROOT, absPath).replaceAll("\\", "/"))
      .sort();

    expect(controlledFiles).toEqual([...new Set(registry.controlled_paths)].sort());

    const actual = new Map<string, number>();
    for (const relativePath of controlledFiles) {
      const counts = scanFile(path.join(REPO_ROOT, relativePath));
      (Object.entries(counts) as Array<[GuardRule, number]>).forEach(([rule, count]) => {
        if (count > 0) {
          actual.set(`${relativePath}::${rule}`, count);
        }
      });
    }

    const baseline = new Map<string, number>();
    for (const entry of [...registry.active_exceptions, ...registry.pending_migrations]) {
      baseline.set(`${entry.path}::${entry.rule}`, entry.count);
    }

    const violations: string[] = [];
    for (const [key, count] of [...actual.entries()].sort()) {
      const allowed = baseline.get(key) ?? 0;
      if (count !== allowed) {
        violations.push(`${key}: 实际 ${count} 处，登记允许 ${allowed} 处`);
      }
    }
    for (const [key, allowed] of [...baseline.entries()].sort()) {
      if (!actual.has(key)) {
        violations.push(`${key}: 登记 ${allowed} 处，但代码已无对应兼容项，请清理过期登记`);
      }
    }

    expect(
      violations,
      `exact-numeric 受控路径与兼容基线不一致：\n${violations.join("\n")}\n` +
        "请迁移现有兼容项，或先在 registry 中显式登记 owner/reason/page/expiry（active）或 pending_migrations（未闭合）。",
    ).toEqual([]);
  });
});
