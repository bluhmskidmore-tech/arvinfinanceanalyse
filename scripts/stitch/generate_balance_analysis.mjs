/**
 * Generate MOSS balance-analysis page mockup via Google Stitch SDK.
 *
 * Usage:
 *   node scripts/stitch/generate_balance_analysis.mjs
 */
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const outputDir = join(repoRoot, "artifacts", "stitch", "balance-analysis");

const PROMPT = `
Design a desktop web page for MOSS institutional asset-liability analysis (资产负债分析 /balance-analysis).
This is NOT a marketing site. It is a dense internal treasury analytics workbench page inside an existing app shell.
Do NOT draw a full left sidebar navigation — only the page content area.

Visual system (must follow):
- Background #f5f7f9, white primary cards, light gray secondary surfaces
- Primary blue #1850a1, asset green #2d8a5e, liability red #ef4444, warning amber #d97706
- Font: Plus Jakarta Sans for labels, IBM Plex Mono for amounts
- Compact institutional density, tabular numbers, soft borders, minimal shadow
- No purple gradients, no generic SaaS hero, no metric IDs visible to users

Page first-screen question (hero must answer this):
"On the selected report date, what is the formal asset/liability/net position gap and what governance actions are pending?"

Top toolbar row:
- Title: 资产负债分析
- Subtitle chip: 正式口径 · 缺口优先
- Filters inline: 报告日 date picker (2026-04-30), 头寸范围 select (全部/资产/负债), 币种口径 select (人民币/原币)
- Right actions: green status pill "数据已更新", buttons 刷新正式结果, 导出 CSV, 导出 Excel

Block order (locked, top to bottom):

1) HERO ROW — "本日缺口判断" (3 cards in one row):
   Left card (wide): headline "6-12个月负债期限缺口偏高，需复核配置"
   - 4 metric tiles in 2x2: 资产市值 3,708.10亿元, 负债市值 1,841.59亿元, 净头寸 2,900.26亿元, 发行类负债 1,176.48亿元
   - 3 action chips below: 最高风险(6-12月负债缺口), 待办决策(复核3-5年缺口), 最近事件(1980141到期 2026-05-06)
   Center card: none — keep left card wide
   Right card (narrow rail): "治理与下钻" list with report date, position scope, currency basis, 治理队列 3, 风险预警 3, workbook shortcuts

2) KPI STRIP — "核心指标速览" horizontal 6 tiles:
   总市值规模 5,549.68亿元 | 总摊余成本 5,477.42亿元 | 总应计利息 1.78亿元 | 明细行数 4857 | 汇总行数 4857 | 治理动作 3

3) COMPARISON ROW — "资产端 / 负债端并排判断":
   Two horizontal comparison bars: 市值规模 and 摊余成本, asset bar green vs liability bar red with yi yuan labels

4) THREE-COLUMN ROW:
   Left: "期限缺口 Top3" table/chart with buckets 0-3M, 3-6M, 6-12M, 1-3Y, 3-5Y, 5Y+ and signed gap bars (red negative, blue positive)
   Center: "Workbook 图谱" card grid showing 7 workbook panels as clickable tiles: 债券业务种类, 评级分析, 期限缺口, 发行类业务, 行业分布, 利率分布, 对手方类型 — show counts like 25 tables / 5 cards
   Right: "治理闭环" stacked list — 3 decision items, 3 risk alerts, mini event calendar with 2 upcoming items

5) WORKBOOK PRIMARY ROW (4 equal cards with mini bar charts):
   债券业务种类, 评级分析, 期限缺口分析, 发行类业务种类 — each with top 4 rows and 亿元 amounts

6) WORKBOOK SECONDARY ROW (3 cards):
   行业分布, 利率分布, 对手方类型

7) BOTTOM COLLAPSED STRIP (muted):
   Tabs: 汇总底稿 | 明细底稿 | 证据链路 | ADB预览(分析) | 高级归因(场景)
   Show as collapsed footer bar, not expanded tables

Use realistic Chinese financial copy. Show small state badges on panels: 已接入 / 部分接入 / 加载中.
Reference mood: MOSS portfolio workbench home + bank ALM terminal, not Figma marketing template.
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
  const project = await stitch.createProject("MOSS 资产负债分析");
  console.log("[stitch] Project:", project.projectId ?? project.id);

  console.log("[stitch] Generating balance-analysis desktop screen…");
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
        page: "/balance-analysis",
        contract: "PAGE-BALANCE-001",
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
