# CI Push Preflight — monthly OA audit smoke vs state server（2026-07-20）

## 结论：**A. 推送就该冒烟项而言是安全的**

`frontend/tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs` 已改为硬失败（`expect(serverCheck.ok).toBe(true)`），但远程 CI 的 `Frontend accessibility smoke` 会通过 Playwright `webServer` **同时拉起** mock `:5888` 与 real/state `:5889`，与该冒烟的探测目标一致。

**对「现在能否 push `origin/codex/V1`」的建议：** 就本已知风险点，**可以 push**；不因 monthly OA 硬失败探测而单独阻塞。仍建议 push 后盯首轮 CI 全绿（其他并行改动另计）。

## 证据

### 1. 冒烟硬依赖 state URL

文件：`frontend/tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs`

- `REAL_STATE_BASE_URL` 在 `MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"` 时默认 `http://127.0.0.1:5889`（或 `MOSS_PLAYWRIGHT_STATE_PORT`）。
- 测试开头 `probeServer(REAL_STATE_BASE_URL)`，失败即 `expect(...).toBe(true)` 硬失败（不再 soft-skip）。

### 2. Playwright 配置在 USE_WEB_SERVER=1 时启动双服务

文件：`frontend/playwright.config.mjs`

- `MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"` 时 `webServer` 数组含：
  - mock Vite → `MOSS_PLAYWRIGHT_PORT` / `BASE_URL`（默认 5888）
  - real Vite → `MOSS_PLAYWRIGHT_STATE_PORT`（默认 5889），`VITE_DATA_SOURCE=real`

### 3. CI 入口

文件：`.github/workflows/ci.yml` → job 步骤 `Frontend accessibility smoke`

```yaml
env:
  MOSS_PLAYWRIGHT_USE_WEB_SERVER: "1"
  MOSS_PLAYWRIGHT_BASE_URL: "http://127.0.0.1:5888"
run: npm run test:a11y-smoke
```

`npm run test:a11y-smoke` → `playwright test -c playwright.config.mjs`，会跑 `tests/playwright/**`（含 monthly OA 冒烟）。

## 残余风险（不改变 A 结论）

- real-mode Vite（5889）若因环境/依赖无法启动，整段 a11y-smoke 会红——这是既有双 webServer 设计，不是「无 state server 却硬失败」的逻辑漏洞。
- 本文件只审计该已知风险点，不担保 `codex/V1` 相对 origin 的其他新增提交全部绿。

## 是否需要代码修复

- **不需要**为该风险点再加 skip/守卫；CI 路径已提供 state server。
- 若本地不设 `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1` 且无 5889，本地跑该文件会硬失败——属本地用法问题，与远程 CI 无关。
