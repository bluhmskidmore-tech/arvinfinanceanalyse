# MOSS 每日数据调度就绪包（Runbook）

一页说明：安装、验证、日志、排查。目标是让收盘后数据链无人值守地每天跑起来。

## 重要背景（安装前必读）

本机**已经注册**了 5 个 MOSS 计划任务（`schtasks /Query | findstr MOSS` 可见）：

| 任务 | 时间 | 覆盖内容 |
| --- | --- | --- |
| MOSS-MacroToolkitFreshness | 每日 18:30 | 宏观供应商数据刷新 |
| MOSS-ChoiceStockDailyRefresh | 每日 18:45 | 日线摄入→物化→宽度→门控→持仓快照 |
| MOSS-MacroToolkitDailyChain | 每日 19:10 | 宏观十模型链 + 图文日报 |
| MOSS-BalanceMovementFreshness | 每日 06:45 | 余额变动新鲜度（不属于本链，勿动） |
| MOSS-SupplyFreshnessSentry | 每日 19:15 | 供给新鲜度哨兵（不属于本链，勿动） |

数据停更的直接原因不是"没装任务"，而是这些任务近期**持续以退出码 1 失败**（网络不通）。
本就绪包补上两块真正没有调度的内容：**候选/执行/outcome 链**与**月度 walk-forward**，
并提供把整条链收敛到单一任务的选项。

`daily_data_refresh.ps1` 会自动检测上面三个链内旧 timer：**处于启用状态则跳过对应步骤**（不重复摄入）。

## 安装（管理员 PowerShell，一条命令）

推荐——由新任务接管整条链（旧的三个链内 timer 会被禁用，可随时恢复）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File F:\MOSS-V3\scripts\scheduling\register_scheduled_tasks.ps1 -DisableLegacyTimers
```

保守——与旧 timer 共存（新每日任务只补跑候选/outcome 步骤；此时建议 `-DailyTime 19:30`，排在旧链之后）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File F:\MOSS-V3\scripts\scheduling\register_scheduled_tasks.ps1 -DailyTime 19:30
```

注册的任务：

- `MOSS-DailyDataRefresh`：每日 17:30（默认，可用 `-DailyTime` 改），串行执行
  日线摄入→物化→宽度→门控→持仓快照→候选/执行→outcome→宏观 freshness→宏观模型链。
- `MOSS-MonthlyWalkForward`：每月第一个周六 09:00，walk-forward 验证并归档报告到
  `docs/strategy-reports/walk-forward-YYYYMMDD.md`（+ 同名 `.json`）。

时间提示：旧链选 18:45 是因为 Choice 收盘数据大约 18:30 后才齐；默认 17:30 可能偏早，
若首步经常失败请改 `-DailyTime 18:45` 重新执行注册脚本（幂等，直接覆盖更新）。

反注册：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File F:\MOSS-V3\scripts\scheduling\register_scheduled_tasks.ps1 -Unregister
```

## 验证

```powershell
schtasks /Query /TN MOSS-DailyDataRefresh /V /FO LIST
schtasks /Query /TN MOSS-MonthlyWalkForward /V /FO LIST

# 只打印执行计划，不真跑（也会显示哪些步骤因旧 timer 被跳过）
powershell -File F:\MOSS-V3\scripts\scheduling\daily_data_refresh.ps1 -DryRun

# 手动立刻触发一次
schtasks /Run /TN MOSS-DailyDataRefresh
```

## 日志与回执

- 每日链日志：`scripts/scheduling/logs/YYYYMMDD.log`（每步命令、输出、退出码、末尾汇总）。
- 月度日志：`scripts/scheduling/logs/monthly-YYYYMMDD.log`。
- JSON 回执（沿用既有约定）：`data/logs/choice_stock_daily_refresh_receipt.json`、
  `data/logs/macro_toolkit_freshness_refresh_receipt.json`、`data/logs/macro_toolkit_daily_chain_receipt.json`。
- 退出码：`0` 全部成功/合理跳过（含周末）；`1` 非关键步骤失败但链已跑完；`2` 关键摄入步骤失败，依赖步骤中止。

## 失败排查

**网络不通（当前状态，首跑必然失败）**：日志中首步 `choice_stock_daily_refresh` 记
`ALERT FAILED exit=1`，输出含 vendor/连接错误；`livermore_pretrade_candidates` 记
`SKIP: upstream step ... failed`；宏观两步各自失败。任务在 Task Scheduler 中 LastResult
非零。网络恢复后无须操作，次日自动恢复；也可手动补当天：

```powershell
powershell -File F:\MOSS-V3\scripts\scheduling\daily_data_refresh.ps1 -AsOfDate 2026-08-12 -IgnoreExistingTimers
```

（补历史日期需逐日执行；`-AsOfDate` 会透传给摄入与候选两步。）

**DuckDB 库锁（`Conflicting lock` / `database is locked`）**：通常是 API/worker 或另一
写任务占用 `data/moss.duckdb`。链内单写串行 + 关键步骤自带重试；若仍失败，确认没有第二个
写进程后重跑该日。

**单步重跑**（用各 CLI 原生入口，venv python）：

```powershell
.\.venv\Scripts\python.exe scripts\choice_stock_daily_refresh.py --run-once --as-of-date 2026-08-12
.\.venv\Scripts\python.exe scripts\run_livermore_daily_pretrade_refresh.py --target-date 2026-08-12
.\.venv\Scripts\python.exe scripts\macro_toolkit_freshness_refresh.py --run-once
.\.venv\Scripts\python.exe scripts\macro_toolkit_daily_chain.py --run-once
.\.venv\Scripts\python.exe scripts\run_walk_forward_validation.py --db-path data\moss.duckdb --report-path docs\strategy-reports\walk-forward-manual.md
```

**恢复旧 timer**（如果之前用了 `-DisableLegacyTimers` 又想回退）：

```powershell
schtasks /Change /TN MOSS-ChoiceStockDailyRefresh /ENABLE
schtasks /Change /TN MOSS-MacroToolkitFreshness /ENABLE
schtasks /Change /TN MOSS-MacroToolkitDailyChain /ENABLE
```
