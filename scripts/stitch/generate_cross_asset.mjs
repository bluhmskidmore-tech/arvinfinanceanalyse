/**
 * Generate MOSS cross-asset drivers homepage via Google Stitch SDK.
 *
 * Usage:
 *   node scripts/stitch/generate_cross_asset.mjs
 */
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const outputDir = join(repoRoot, "artifacts", "stitch", "cross-asset");

const PROMPT = `
Design a desktop web page for MOSS institutional cross-asset market drivers (跨资产驱动 /cross-asset).
This is an internal analytics workbench page inside an existing app shell.
Do NOT draw a full left sidebar navigation — only the page content area.
Match the visual skeleton of the portfolio workbench home (组合工作台总览): layered white cards, soft shadows, blue institutional palette.

Visual system (must follow):
- Page background #f4f7fb, primary cards #ffffff, secondary surfaces #f7f9fc
- Borders #e4e9f0 / #eef2f7, primary blue #1850a1, success #1f7a55, warning #b76e00, danger #b94743
- Font: Plus Jakarta Sans for UI labels, IBM Plex Mono for numeric KPI values (tabular)
- Card radius 10px, compact density, 8/12/16/24px vertical rhythm
- No purple gradients, no marketing hero, no stock photos

Page first-screen question:
"How do external variables transmit into bonds today — what is the regime, headline risk, and candidate actions?"

Block order (locked, top to bottom):

1) DECISION HERO (full width):
   - Eyebrow: 市场工作台
   - Title: 跨资产驱动
   - Subtitle: 外部变量怎样传导到债券？只保留判断、告警和候选动作
   - Meta line: 数据日期 2026-04-30 · 完整序列请转到市场数据
   - Conclusion pill with left blue accent: "利率上行+信用走阔，债券久期风险需收敛"
   - Right chips: 真实分析口径, link 市场数据

2) DATA STATUS STRIP (compact, full width):
   - Left: status pills (宏观序列陈旧, 联动质量正常)
   - Right meta: 宏观最新质量 正常 · 联动质量 正常 · timestamps

3) FIRST SCREEN GRID (2 columns on desktop):
   LEFT column stacked:
   - Panel "市场判断": regime card (Risk-On / 温和 risk-on) with icon, 3 factor chips (主导/次要/风格), short prose
   - 2x2 mini KPI tiles (10Y国债收益率, 信用利差, 美元/人民币, VIX) with mono values and delta
   RIGHT column:
   - Panel "投资研究判断": 2x2 research view cards (利率观点, 信用观点, 外汇观点, 权益观点) each with stance pill
   - Below: table "宏观 — 债市相关性（前列）" with columns 指标, 3月相关, 6月相关, 方向

4) SECTION LEAD + KPI BAND:
   - Section title "完整指标带" with eyebrow 环境上下文
   - 4-column KPI cards with sparkline on right (same style as workbench home KPI tiles)

5) TRANSMISSION ROW:
   - Title 传导主线
   - 5 equal cards for transmission axes (利率, 信用, 外汇, 流动性, 权益) with pills and summary text

6) ASSET CLASS ANALYSIS:
   - Wide panel with judgment card on left and 2x2 class cards on right, pending items column

7) DRIVER WATERFALL + RISK SNAPSHOT:
   - Waterfall chart panel "驱动归因瀑布"
   - Side by side: volatility clustering alert + equity-bond ERP gauge

8) CANDIDATE ACTIONS list + trend chart area (collapsed hint)

Use realistic Chinese labels and placeholder numbers (%, bp). Show loading/empty chips where appropriate.
Must feel like the same product family as 组合工作台总览 — white cards on cool gray canvas, not a different design language.
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
  const project = await stitch.createProject("MOSS 跨资产驱动首页");
  console.log("[stitch] Project:", project.projectId ?? project.id);

  console.log("[stitch] Generating desktop cross-asset screen…");
  const screen = await project.generate(PROMPT, "DESKTOP");
  const screenId = screen.id ?? screen.screenId;
  console.log("[stitch] Screen:", screenId);

  const htmlUrl = await screen.getHtml();
  const imageUrl = await screen.getImage();
  console.log("[stitch] Fetching HTML + screenshot…");

  const html = await downloadText(htmlUrl);
  await mkdir(outputDir, { recursive: true });

  const htmlPath = join(outputDir, "design-draft.html");
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
      await writeFile(join(outputDir, "design-draft.png"), buffer);
    }
  }

  console.log("[stitch] Saved:", htmlPath);
}

main().catch((error) => {
  console.error("[stitch] Generation failed:", error);
  process.exit(1);
});
