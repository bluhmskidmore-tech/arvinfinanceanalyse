/**
 * MCP stdio launcher for Google Stitch (stitch-mcp-server).
 * Reads STITCH_API_KEY from environment or config/.env, then runs npx stitch-mcp-server.
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");

function readEnvValue(key, envPath) {
  if (!existsSync(envPath)) {
    return "";
  }

  const text = readFileSync(envPath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const eq = trimmed.indexOf("=");
    if (eq <= 0) {
      continue;
    }

    const envKey = trimmed.slice(0, eq).trim();
    if (envKey !== key) {
      continue;
    }

    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"'))
      || (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    return value.trim();
  }

  return "";
}

function loadStitchApiKey() {
  const fromProcess = process.env.STITCH_API_KEY?.trim();
  if (fromProcess) {
    return fromProcess;
  }

  return readEnvValue("STITCH_API_KEY", join(repoRoot, "config", ".env"));
}

const apiKey = loadStitchApiKey();
if (!apiKey) {
  console.error(
    "[stitch MCP] Missing STITCH_API_KEY. Add it to config/.env or your shell environment.",
  );
  console.error("[stitch MCP] Get a key at https://stitch.google.com/");
  process.exit(1);
}

const isWin = process.platform === "win32";
const command = isWin ? "cmd.exe" : "npx";
const args = isWin
  ? ["/d", "/s", "/c", "npx.cmd", "-y", "stitch-mcp-server@1.0.7"]
  : ["-y", "stitch-mcp-server@1.0.7"];
const child = spawn(command, args, {
  cwd: repoRoot,
  stdio: "inherit",
  windowsHide: true,
  env: {
    ...process.env,
    STITCH_API_KEY: apiKey,
  },
});

child.on("error", (err) => {
  console.error("[stitch MCP]", err);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code ?? 0);
});
