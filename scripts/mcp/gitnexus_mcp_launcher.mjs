/**
 * MCP stdio proxy for GitNexus: resolves repo root from this file's location
 * so startup works even when Cursor reports no workspace cwd.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const cliJs = join(
  repoRoot,
  ".tmp-gitnexus-v13",
  "node_modules",
  "gitnexus",
  "dist",
  "cli",
  "index.js",
);

if (!existsSync(cliJs)) {
  console.error(`[gitnexus MCP] Missing CLI at ${cliJs}`);
  process.exit(1);
}

const child = spawn(process.execPath, [cliJs, "mcp"], {
  cwd: repoRoot,
  stdio: "inherit",
  windowsHide: true,
});

child.on("error", (err) => {
  console.error("[gitnexus MCP]", err);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) process.exit(1);
  process.exit(code ?? 0);
});
