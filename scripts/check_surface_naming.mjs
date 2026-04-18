#!/usr/bin/env node
// Surface naming lint — enforces §7.3 of the numeric-correctness design doc.
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const EXTS = new Set([".ts", ".tsx", ".js", ".jsx"]);

const RULES = [
  {
    id: "executive-no-gui-yin",
    includeGlobs: [
      "frontend/src/features/executive-dashboard/**/*.{ts,tsx,js,jsx}",
      "frontend/src/features/workbench/pages/DashboardPage.tsx",
    ],
    forbidden: ["归因"],
    allowedContains: [],
    description: "executive 表层禁止出现'归因'（应使用'贡献拆解'）",
  },
  {
    id: "pnl-attribution-no-jing-ying-gong-xian",
    includeGlobs: ["frontend/src/features/pnl-attribution/**/*.{ts,tsx,js,jsx}"],
    forbidden: ["经营贡献"],
    allowedContains: [],
    description: "pnl-attribution 表层禁止出现'经营贡献'（应使用'归因'/'PnL 贡献'）",
  },
];

function listFilesRecursive(dir) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, ent.name);
    if (ent.isDirectory()) out.push(...listFilesRecursive(p));
    else out.push(p);
  }
  return out;
}

function collectTargets(rule) {
  const hits = new Set();
  for (const pattern of rule.includeGlobs) {
    if (
      pattern.endsWith(".tsx") ||
      pattern.endsWith(".ts") ||
      pattern.endsWith(".js") ||
      pattern.endsWith(".jsx")
    ) {
      const abs = join(ROOT, pattern);
      if (existsSync(abs)) hits.add(abs);
      continue;
    }
    const baseDir = pattern.replace(/\/\*\*\/\*\.\{[^}]+\}$/, "");
    const absBase = join(ROOT, baseDir);
    for (const p of listFilesRecursive(absBase)) {
      const dot = p.lastIndexOf(".");
      if (dot === -1) continue;
      if (EXTS.has(p.slice(dot))) hits.add(p);
    }
  }
  return [...hits];
}

let violations = 0;

for (const rule of RULES) {
  const files = collectTargets(rule);
  for (const abs of files) {
    const text = readFileSync(abs, "utf8");
    const lines = text.split(/\r?\n/);
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      for (const tok of rule.forbidden) {
        let searchFrom = 0;
        let idx = line.indexOf(tok, searchFrom);
        while (idx !== -1) {
          let exempt = false;
          for (const allow of rule.allowedContains) {
            if (allow && line.includes(allow)) {
              exempt = true;
              break;
            }
          }
          if (!exempt) {
            const rel = relative(ROOT, abs).split(sep).join("/");
            const ctxStart = Math.max(0, idx - 30);
            const ctx = line.slice(ctxStart, ctxStart + 60);
            process.stderr.write(
              `${rel}:${i + 1}: forbidden token '${tok}' found: "${ctx}" [rule=${rule.id}]\n`,
            );
            violations += 1;
          }
          searchFrom = idx + tok.length;
          idx = line.indexOf(tok, searchFrom);
        }
      }
    }
  }
}

if (violations > 0) {
  process.stdout.write(`${violations} surface-naming violation(s).\n`);
  process.stderr.write(`\nRule descriptions:\n`);
  for (const r of RULES) process.stderr.write(`  - ${r.id}: ${r.description}\n`);
  process.exit(1);
} else {
  process.stdout.write("surface-naming lint: OK\n");
}
