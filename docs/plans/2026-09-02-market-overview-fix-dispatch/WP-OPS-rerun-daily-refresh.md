# WP-OPS · 重跑日更任务并核回执（唯一有写副作用的包）

- 泳道：独立，任何时候都能派；但**同一时刻仓库里不能有 pytest / release suite / 另一个刷新任务在跑**（DuckDB 写锁）
- 层：运维（PowerShell + 读文件）
- 难度：低
- 用户已明确授权：本包**允许**运行 `schtasks /run`。其它所有包仍然禁止。

## 目标

让 `macro_toolkit_freshness_refresh_receipt.json` 从 `failed` 变为 `success`（或 `degraded`），使 `/market-overview` 首屏离开「暂停形成今日判断」。

## 步骤

1. 前置检查（任何一项不满足就停下报告，不要硬跑）：

```powershell
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine } | Where-Object { $_ -match 'pytest|release_suite|daily_refresh|freshness_refresh|choice_stock' }
```

应为空。`data/logs/*_receipt.json` 里不应有 `"status": "running"`。

2. 触发并等待（整条链约 5–8 分钟）：

```powershell
schtasks /run /tn MOSS-DailyDataRefresh
```

轮询 `scripts/scheduling/logs/<今天yyyyMMdd>.log`，直到出现 `-- summary --` 与 `===== daily_data_refresh finished`（用 Node `fs` 读，不用 `Get-Content`）。

3. 核回执（用 Node 或 Python 读 JSON，不用 PowerShell 文本 cmdlet）：

| 文件 | 期望 |
| --- | --- |
| `data/logs/macro_toolkit_freshness_refresh_receipt.json` | `status ∈ {success, degraded}`，`exit_code = 0`，`result.steps[].status` 全 `success`（`cffex_member_rank` 可 `skipped`） |
| `data/logs/choice_stock_daily_refresh_receipt.json` | 看 `status` 与 `error`；若仍是 `ChoiceStockVendorEraViolationError`（08-27 出现过）或 `insufficient user access`，那是供应方/数据代际问题，原文抄进报告，不要试图修 |
| `data/logs/macro_toolkit_daily_chain_receipt.json` | `status ∈ {success, degraded}` |

4. 后端在线时验证 gate：

```powershell
Invoke-WebRequest "http://127.0.0.1:7888/ui/macro/toolkit/analysis?detail=core" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json | ForEach-Object { $_.result_meta.quality_flag; $_.result.conclusion.stance; $_.result.conclusion.basis.refresh_receipt.status }
```

期望 `quality_flag` 不再因回执而 `warning`，`refresh_receipt.status = ready`（或 `ready_with_warning`）。注意分析缓存按回执指纹分键，回执一变键就变，不需要手动失效；若仍显示旧状态，等 TTL（300 s）或调用刷新端点。

5. 浏览器复核：从 `frontend/` 复制 `.tmp-agent/market-overview-audit/hero-facts.mjs` 到 `frontend/.tmp-audit/` 执行，`title` 不再是「暂停形成今日判断」，`gate` 格不再是「数据质量预警」。

## 若 `choice_policy_rate_7d` 再次因文件锁失败

说明 WP-J 尚未合入或锁持有者仍在（API 进程每次请求短暂开只读连接也可能撞上）。报告里写明失败原文与当时的进程列表，不要反复重跑。

## 报告要求

前置检查结果、触发时间、summary 全文、三份回执的关键字段、gate 状态、hero 文案；对代码零改动，对 `core_finance/` 的影响：无。
