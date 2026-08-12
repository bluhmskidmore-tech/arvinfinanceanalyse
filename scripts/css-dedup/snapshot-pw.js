#!/usr/bin/env node
/* 用 Playwright(Chrome headless) 在全部断点区间采集几何+computed style+伪元素快照与 DOM 证据。
 * usage: node snapshot-pw.js <config.json> <outPrefix> [--shot <pngPath>]
 * 目标 URL 默认 config.mockUrl，可用环境变量 SNAP_URL 覆盖（如采真实态证据）。
 * 快照写入 config.workDir/<prefix>-<width>.json
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { loadConfig, REPO_ROOT } = require('./lib.js');
const { chromium } = require(path.join(REPO_ROOT, 'frontend', 'node_modules', 'playwright-core'));

const cfg = loadConfig(process.argv[2]);
const prefix = process.argv[3] || 'snap';
const shotIdx = process.argv.indexOf('--shot');
const shotPath = shotIdx > -1 ? process.argv[shotIdx + 1] : null;
const WIDTHS = [640, 720, 840, 900, 1000, 1200, 1300, 1920];
const URL = process.env.SNAP_URL || cfg.mockUrl;
const snapExpr = fs.readFileSync(path.join(__dirname, 'snap-expression.txt'), 'utf8');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    page.setDefaultTimeout(45000);
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForSelector('main [class]', { timeout: 30000 }).catch(() => {});
    if (cfg.waitSelector) {
      // 显式等待关键内容（如延迟挂载区块）进入 DOM，消除首个测量点与挂载的竞态。
      await page.waitForSelector(cfg.waitSelector, { timeout: 30000 });
      await page.waitForTimeout(500);
    }
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 1080 });
      await page.waitForTimeout(250);
      const json = await page.evaluate(snapExpr);
      const parsed = JSON.parse(json);
      fs.writeFileSync(path.join(cfg.workDir, `${prefix}-${w}.json`), json);
      console.log(`${w}px ok docH=${parsed.meta.docH} measured=${parsed.meta.measured} textLen=${parsed.meta.textLen}`);
    }
    if (shotPath) {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.waitForTimeout(250);
      await page.screenshot({ path: shotPath, fullPage: true });
      console.log('screenshot: ' + shotPath);
    }
  } finally {
    await browser.close();
  }
})().catch(e => { console.error('SNAPSHOT FAILED: ' + e.message); process.exit(1); });
