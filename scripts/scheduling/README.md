# MOSS 每日数据调度就绪包（Runbook）

一页说明：安装、验证、日志、排查。目标是让收盘后数据链无人值守地每天跑起来。

## 重要背景（安装前必读）

旧部署通常已经注册下列 5 个 MOSS 计划任务（`schtasks /Query | findstr MOSS` 可核对）：

| 任务 | 时间 | 覆盖内容 |
| --- | --- | --- |
| MOSS-MacroToolkitFreshness | 每日 18:30 | 宏观供应商数据刷新 |
| MOSS-ChoiceStockDailyRefresh | 每日 18:45 | 日线摄入→物化→宽度→门控→持仓快照 |
| MOSS-MacroToolkitDailyChain | 每日 19:10 | 宏观十模型链 + 图文日报 |
| MOSS-BalanceMovementFreshness | 每日 06:45 | 余额变动新鲜度（不属于本链，勿动） |
| MOSS-SupplyFreshnessSentry | 每日 19:15 | 供给新鲜度哨兵（不属于本链，勿动） |

历史停更的直接原因不是“没装任务”，而是旧任务的固定源 IP 已失效，任务在供应商请求前即退出。
本就绪包补上三块真正缺失的内容：**复权因子日增量**、**候选/执行/outcome 链**与**月度 walk-forward**，
并提供把整条链收敛到单一任务的选项。

`daily_data_refresh.ps1` 会自动检测上面三个链内旧 timer：处于启用状态会跳过对应步骤；
如果被跳过的是本链后续步骤的上游（目前是 Choice），本链会阻断 factor/pretrade 并返回非零，
不会假设另一个 timer 已经跑完。要取得可验收的完整闭环，应由一个总调度独占编排。

## 安装（管理员 PowerShell，一条命令）

推荐——由新任务接管整条链（旧的三个链内 timer 会被禁用，可随时恢复）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File F:\MOSS-V3\scripts\scheduling\register_scheduled_tasks.ps1 -DisableLegacyTimers -VendorSourceIp <物理网卡IPv4>
```

不建议让链内旧 timer 与新总调度共存。若只想先观察计划，可安装后保持旧任务启用并执行
`-DryRun`；真正切换闭环时请使用上面的 `-DisableLegacyTimers`。如确需人工强制全链，先确认
没有旧任务正在执行，再使用 `-IgnoreExistingTimers`：

```powershell
powershell -File F:\MOSS-V3\scripts\scheduling\daily_data_refresh.ps1 -AsOfDate 2026-08-12 -VendorSourceIp <物理网卡IPv4> -IgnoreExistingTimers
```

注册的任务：

- `MOSS-DailyDataRefresh`：每日 18:45（默认，可用 `-DailyTime` 改），串行执行
  日线摄入→物化→宽度→门控→持仓快照→复权因子全覆盖校验/增量写入→
  候选/执行→outcome→宏观 freshness→宏观模型链。
- `MOSS-MonthlyWalkForward`：每月第一个周六 09:00，walk-forward 验证并归档报告到
  `docs/strategy-reports/walk-forward-YYYYMMDD.md`（+ 同名 `.json`）。

时间提示：默认 18:45 是因为 Choice 收盘数据大约 18:30 后才齐；如需换更早或更晚的时间，
可直接改 `-DailyTime` 并幂等重注册（直接覆盖更新）。

编排边界：Choice 主任务只负责行情、基本面快照及其直接派生输入；不会在复权因子落地前
提前执行 Livermore 盘前闭环。盘前闭环由每日总调度在复权因子步骤成功后统一触发，避免
形成“Choice 等复权、复权又等 Choice”的循环依赖。

`-VendorSourceIp` 需要填本机物理网卡 IPv4，而不是 VPN/默认路由地址；换网卡、换 Wi-Fi、
换 VPN 后请用新的物理网卡 IPv4 幂等重注册一次，旧任务配置不会自动跟着变。

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
  `data/logs/stock_adjustment_factor_daily_refresh_receipt.json`、
  `data/logs/macro_toolkit_freshness_refresh_receipt.json`、`data/logs/macro_toolkit_daily_chain_receipt.json`。
- 退出码：`0` 全部成功/独立步骤合理跳过（含周末）；`1` 非关键步骤失败但链已跑完；
  `2` 关键摄入失败，或关键上游由外部 timer 承担而本次无法验证其完成，依赖步骤中止。

## 失败排查

**网络或源 IP 不通**：日志中首步 `choice_stock_daily_refresh` 记
`ALERT FAILED exit=1`，输出含 vendor/连接错误；`livermore_pretrade_candidates` 记
`SKIP: upstream step ... failed`；宏观两步各自失败。任务在 Task Scheduler 中 LastResult
非零。若物理网卡 IP 已变化，先用新 IP 幂等重注册；网络恢复后也可手动补当天：

```powershell
powershell -File F:\MOSS-V3\scripts\scheduling\daily_data_refresh.ps1 -AsOfDate 2026-08-12 -VendorSourceIp <物理网卡IPv4> -IgnoreExistingTimers
```

（补历史日期需逐日执行；`-AsOfDate` 会透传给行情摄入、复权因子和候选链。）

**DuckDB 库锁（`Conflicting lock` / `database is locked`）**：通常是 API/worker 或另一
写任务占用已配置的 DuckDB（默认 `data/moss.duckdb`）。链内单写串行 + 关键步骤自带重试；若仍失败，确认没有第二个
写进程后重跑该日。

**单步重跑**（用各 CLI 原生入口，venv python）：每日和月度入口沿用各 Python CLI 的 Settings 路径解析，遵循环境变量和 `.env` 的外置配置；只有明确检查另一份库时才传入 `--db-path`。

```powershell
.\backend\.venv\Scripts\python.exe scripts\choice_stock_daily_refresh.py --run-once --as-of-date 2026-08-12 --vendor-source-ip <物理网卡IPv4>
.\backend\.venv\Scripts\python.exe scripts\stock_adjustment_factor_daily_refresh.py --run-once --as-of-date 2026-08-12 --vendor-source-ip <物理网卡IPv4>
.\backend\.venv\Scripts\python.exe scripts\run_livermore_daily_pretrade_refresh.py --target-date 2026-08-12
.\backend\.venv\Scripts\python.exe scripts\macro_toolkit_freshness_refresh.py --run-once
.\backend\.venv\Scripts\python.exe scripts\macro_toolkit_daily_chain.py --run-once
.\backend\.venv\Scripts\python.exe scripts\run_walk_forward_validation.py --report-path docs\strategy-reports\walk-forward-manual.md
```

**恢复旧 timer**（如果之前用了 `-DisableLegacyTimers` 又想回退）：

```powershell
schtasks /Change /TN MOSS-ChoiceStockDailyRefresh /ENABLE
schtasks /Change /TN MOSS-MacroToolkitFreshness /ENABLE
schtasks /Change /TN MOSS-MacroToolkitDailyChain /ENABLE
```
