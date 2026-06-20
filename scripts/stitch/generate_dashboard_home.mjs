/**
 * Generate MOSS dashboard-home overview via Google Stitch SDK.
 * Requires STITCH_API_KEY in config/.env or environment.
 *
 * Usage:
 *   node scripts/stitch/generate_dashboard_home.mjs
 */
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const outputDir = join(repoRoot, "artifacts", "stitch", "dashboard-home");

const PROMPT = `
Design a desktop web dashboard for an institutional fixed-income portfolio workbench (组合工作台总览).

Visual style:
- Light institutional fintech UI, calm and audit-friendly
- Background #f5f7f9, white cards, subtle borders, soft shadows
- Primary blue #1850a1, success green #2d8a5e, warning amber #d97706, danger red #ef4444
- Typography: Plus Jakarta Sans for UI, IBM Plex Mono for numeric KPI values
- Compact density, tabular numbers aligned

Layout (top to bottom, locked order):
1) Top toolbar: page title "组合工作台 · 总览", report date picker, search box, refresh button, data status pill
2) Hero row (3 cards):
   - Left: "今日经营判断" AI summary card with health score bar /100 and short impact text
   - Center: 4-6 KPI tiles (组合规模, 久期, 到期收益率, 信用利差, DV01, 本月收入) each with value, unit, delta, mini sparkline
   - Right: "风险约束" mini metrics grid (集中度, 流动性, 评级分布预警)
3) Second row: horizontal market tape strip with key rates/spreads
4) Third row 3 columns:
   - Asset structure bars + pie
   - PnL attribution waterfall chart
   - Risk radar + watchlist
5) Fourth row 2 columns:
   - Research/event calendar
   - Top holdings table + position changes

Use realistic Chinese labels and placeholder numbers (亿元, bp, %). Show explicit empty/loading state chips on panels.
No purple gradients, no generic SaaS marketing look. Must feel like a bank treasury analytics terminal.
`.trim();

function readEnvValue(key, envPath) {
  if (!existsSync(envPath)) return "";
  const text = readFileSync(envPath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    if (trimmed.slice(0, eq).trim() !== key) continue;
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

async function downloadText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Download failed (${response.status}): ${url}`);
  }
  return response.text();
}

async function main() {
  const apiKey = process.env.STITCH_API_KEY?.trim()
    || readEnvValue("STITCH_API_KEY", join(repoRoot, "config", ".env"));

  if (!apiKey) {
    console.error("[stitch] Missing STITCH_API_KEY in config/.env or environment.");
    process.exit(1);
  }

  process.env.STITCH_API_KEY = apiKey;

  const sdkRoot = join(here, "node_modules", "@google", "stitch-sdk", "dist", "src", "index.js");
  if (!existsSync(sdkRoot)) {
    console.error("[stitch] Missing SDK. Run: npm install --prefix scripts/stitch");
    process.exit(1);
  }

  const { stitch } = await import(pathToFileURL(sdkRoot).href);

  console.log("[stitch] Creating project…");
  const project = await stitch.createProject("MOSS 组合工作台总览");
  console.log("[stitch] Project:", project.projectId ?? project.id);

  console.log("[stitch] Generating desktop overview screen…");
  const screen = await project.generate(PROMPT, "DESKTOP");
  const screenId = screen.id ?? screen.screenId;
  console.log("[stitch] Screen:", screenId);

  const htmlUrl = await screen.getHtml();
  const imageUrl = await screen.getImage();
  console.log("[stitch] Fetching HTML + screenshot…");

  const html = await downloadText(htmlUrl);
  await mkdir(outputDir, { recursive: true });

  const htmlPath = join(outputDir, "overview.html");
  const metaPath = join(outputDir, "meta.json");
  await writeFile(htmlPath, html, "utf8");
  await writeFile(
    metaPath,
    JSON.stringify(
      {
        projectId: project.projectId ?? project.id,
        screenId,
        htmlUrl,
        imageUrl,
        generatedAt: new Date().toISOString(),
        prompt: PROMPT,
      },
      null,
      2,
    ),
    "utf8",
  );

  if (imageUrl) {
    const imageResponse = await fetch(imageUrl);
    if (imageResponse.ok) {
      const buffer = Buffer.from(await imageResponse.arrayBuffer());
      await writeFile(join(outputDir, "overview.png"), buffer);
    }
  }

  console.log("[stitch] Saved:", htmlPath);
}

main().catch((error) => {
  console.error("[stitch] Generation failed:", error);
  process.exit(1);
});
