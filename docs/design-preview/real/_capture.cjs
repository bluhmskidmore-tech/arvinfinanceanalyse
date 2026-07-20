/* 真实环境采集脚本（只读）：截图 + innerText + 计算样式 + 网络请求记录 */
const { chromium } = require("F:/MOSS-V3/frontend/node_modules/playwright");
const fs = require("fs");
const path = require("path");

const BASE = "http://127.0.0.1:5888";
const OUT = __dirname;

const PAGES = [
  { route: "/", name: "home", wait: 18000, label: "经营日报首页" },
  { route: "/portfolio", name: "portfolio", wait: 15000, label: "组合首页" },
  { route: "/market-overview", name: "market", wait: 15000, label: "市场首页" },
  { route: "/bond-analysis", name: "bond-analysis", wait: 15000, label: "债券分析" },
  { route: "/market-data", name: "market-data", wait: 15000, label: "市场数据" },
  { route: "/operations-analysis", name: "operations", wait: 12000, label: "经营分析" },
  { route: "/reports", name: "reports", wait: 12000, label: "报表中心" },
];

(async () => {
  const browser = await chromium.launch();
  const manifest = [];

  for (const p of PAGES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    const apiCalls = [];
    const consoleErrors = [];

    page.on("response", (res) => {
      const url = res.url();
      if (url.includes("/ui/") || url.includes("/api/")) {
        apiCalls.push({ status: res.status(), url: url.replace(BASE, "") });
      }
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 300));
    });
    page.on("pageerror", (err) => consoleErrors.push("PAGEERROR: " + String(err).slice(0, 300)));

    let navError = null;
    try {
      await page.goto(BASE + p.route, { waitUntil: "domcontentloaded", timeout: 60000 });
    } catch (e) {
      navError = String(e).slice(0, 300);
    }
    await page.waitForTimeout(p.wait);

    const shotPath = path.join(OUT, `${p.name}.png`);
    try {
      await page.screenshot({ path: shotPath });
    } catch (e) {
      navError = (navError || "") + " SHOT_FAIL:" + String(e).slice(0, 200);
    }

    let extracted = { innerText: "", styles: {}, finalUrl: "", title: "" };
    try {
      extracted = await page.evaluate(() => {
        const root = document.documentElement;
        const body = document.body;
        const cs = getComputedStyle(body);
        const rootCs = getComputedStyle(root);
        const cssVarNames = [
          "--background", "--foreground", "--card", "--primary", "--border",
          "--font-sans", "--radius", "--moss-bg", "--bg", "--text",
        ];
        const vars = {};
        for (const n of cssVarNames) {
          const v = rootCs.getPropertyValue(n).trim();
          if (v) vars[n] = v;
        }
        // 收集 html/body 上实际出现的前 20 个自定义属性
        const all = [];
        for (const sheet of document.styleSheets) {
          try {
            for (const rule of sheet.cssRules) {
              if (rule.style) {
                for (const prop of rule.style) {
                  if (prop.startsWith("--") && !all.includes(prop)) all.push(prop);
                  if (all.length >= 60) break;
                }
              }
              if (all.length >= 60) break;
            }
          } catch (_) { /* cross-origin sheet */ }
          if (all.length >= 60) break;
        }
        for (const n of all.slice(0, 40)) {
          if (!(n in vars)) {
            const v = rootCs.getPropertyValue(n).trim();
            if (v) vars[n] = v;
          }
        }
        const firstMain = document.querySelector("main") || body.firstElementChild;
        const mainCs = firstMain ? getComputedStyle(firstMain) : null;
        return {
          finalUrl: location.href,
          title: document.title,
          innerText: (body.innerText || "").slice(0, 3000),
          styles: {
            body_backgroundColor: cs.backgroundColor,
            body_color: cs.color,
            body_fontFamily: cs.fontFamily,
            body_fontSize: cs.fontSize,
            root_backgroundColor: rootCs.backgroundColor,
            main_backgroundColor: mainCs ? mainCs.backgroundColor : null,
            body_borderRadius_first: cs.borderRadius,
            css_vars: vars,
          },
        };
      });
    } catch (e) {
      navError = (navError || "") + " EVAL_FAIL:" + String(e).slice(0, 200);
    }

    const txt = [
      `# ${p.label}  ${p.route}`,
      `final_url: ${extracted.finalUrl}`,
      `title: ${extracted.title}`,
      ``,
      `## innerText (first ~3000 chars)`,
      extracted.innerText,
      ``,
      `## computed styles`,
      JSON.stringify(extracted.styles, null, 2),
      ``,
      `## api calls (${apiCalls.length})`,
      ...apiCalls.map((c) => `${c.status}  ${c.url}`),
      ``,
      `## console errors (${consoleErrors.length})`,
      ...consoleErrors.slice(0, 10),
    ].join("\n");
    fs.writeFileSync(path.join(OUT, `${p.name}.txt`), txt, "utf8");

    manifest.push({
      name: p.name,
      route: p.route,
      label: p.label,
      navError,
      finalUrl: extracted.finalUrl,
      apiCalls,
      consoleErrorCount: consoleErrors.length,
      consoleErrors: consoleErrors.slice(0, 5),
      innerTextHead: extracted.innerText.slice(0, 400),
    });

    console.log(`DONE ${p.name}: api=${apiCalls.length} err=${consoleErrors.length} nav=${navError || "ok"}`);
    await ctx.close();
  }

  fs.writeFileSync(path.join(OUT, "_capture.json"), JSON.stringify(manifest, null, 2), "utf8");
  await browser.close();
  console.log("ALL_DONE");
})();
