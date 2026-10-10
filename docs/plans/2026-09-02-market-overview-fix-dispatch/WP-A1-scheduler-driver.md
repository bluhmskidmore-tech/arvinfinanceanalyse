# WP-A1 · 日更调度驱动脚本被子进程 stderr 杀死

- 泳道：L1 后端/运维，第 1 个
- 层：PowerShell（`scripts/scheduling/`）
- 难度：低（改动一处，但必须先复现再改）
- 前置：无
- 后续：WP-A2 独立；合入后需要**人**手动触发一次任务（README §4.1）

## 目标

让 `MOSS-DailyDataRefresh` 不再因为任一步骤的子进程向 stderr 写了一行文字就整体退出。修完后，步骤失败要在日志里留下 `ALERT FAILED exit=…`，全部步骤跑完要留下 `-- summary --`。

## 根因（已复现）

`scripts/scheduling/daily_data_refresh.ps1:67` 设 `$ErrorActionPreference = "Stop"`；`:317` 用

```powershell
$output = & $PythonExe @stepArgs 2>&1
```

运行每个步骤。Windows PowerShell 5.1 会把原生命令 stderr 的**每一行**包成 `NativeCommandError` 写入错误流，`Stop` 偏好下第一行就终止脚本、退出码 1，后面的日志与 summary 都不会写。复现脚本 `.tmp-agent/market-overview-audit/ps_stderr_probe.ps1`（本机 PS 5.1.26100）输出：

```
before-call
python.exe : stderr-line
    + FullyQualifiedErrorId : NativeCommandError
driver-exit=1
```

触发源：`scripts/choice_stock_daily_refresh.py:267-269` 在 DuckDB 写锁争用时向 stderr 打印 `DuckDB writer contention … retrying`。API 进程持有 DuckDB 时步骤 1 一启动就打这一行，驱动脚本随即死亡。

证据：`scripts/scheduling/logs/20260828.log` 至 `20260901.log` 每天都是 499 字节、4 行，截断在 `[choice_stock_daily_refresh] START`；`schtasks /query /tn MOSS-DailyDataRefresh` 上次结果 `1`；`data/logs/choice_stock_daily_refresh_receipt.json` 与 `macro_toolkit_freshness_refresh_receipt.json` 都停在 `status: "running"` 存根。

## 改动范围

只改 `scripts/scheduling/daily_data_refresh.ps1` 第 314–323 行附近的子进程调用。推荐最小改法：在原生调用前后临时切换偏好，并把 `ErrorRecord` 归一为文本再写日志：

```powershell
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $output = & $PythonExe @stepArgs 2>&1
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
foreach ($line in $output) {
    $text = if ($line -is [System.Management.Automation.ErrorRecord]) { $line.Exception.Message } else { [string]$line }
    Add-Content -Path $logPath -Value ("    " + $text) -Encoding UTF8
}
```

在改动处加一段注释说明 PS 5.1 的这个行为（一两句即可，写清"stderr 行会被包成 NativeCommandError，Stop 偏好下终止脚本"）。

备选：`Start-Process -RedirectStandardOutput/-RedirectStandardError -Wait -PassThru` 分流后合并进日志。改动更大，只有在推荐改法验证不通过时才用。

## 不得触碰

- 不改 `$steps` 清单、依赖关系、退出码语义（0/1/2）与 `Write-Log` 格式（`data_health_service.py` 的调度任务检查依赖 `schtasks` 的 LastResult，而 `LastResult` 就是这个脚本的退出码）。
- 不改任何 Python 步骤脚本；`choice_stock_daily_refresh.py:267` 往 stderr 写重试提示是合理行为，驱动脚本应当容忍它，而不是让它闭嘴。
- 不改 `register_scheduled_tasks.ps1`、不动计划任务注册。
- 不要自行运行 `schtasks /run` 或 `daily_data_refresh.ps1`（非 DryRun）——它会写 DuckDB，由人触发。
- **文件编码**：脚本含中文注释，必须用 Node `fs` 或编辑器写回，不能用 PowerShell 文本 cmdlet / 重定向（`AGENTS.md` 文件编码一节；已有过被写坏的先例）。

## 验收

1. 把 `.tmp-agent/market-overview-audit/ps_stderr_probe.ps1` 里的调用改成与你的实现相同的写法，运行后 `driver-exit=0`、`stderr-line` 出现在输出里、`reached-after-call exit=0`。
2. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\scheduling\daily_data_refresh.ps1 -DryRun` 正常打印执行计划并 `exit 0`（DryRun 不运行任何步骤，安全）。
3. 用 Node 校验文件无 U+FFFD：`node scripts/audit_encoding_integrity.mjs`（`debt:audit` 的一部分）通过。
4. `git diff` 只含 `daily_data_refresh.ps1` 一个文件。

## 报告要求

按 `AGENTS.md` 工作协议：根因（引用上面的复现）、改动文件、验证命令与结果、剩余风险（至少写这一条：修复后步骤 1 会真正跑起来并可能再次撞 DuckDB 写锁，Python 侧已有重试逻辑，但首次成功运行前 `macro_toolkit_freshness` 回执仍是 `running`，页面首屏要等回执落地才恢复）。对 `backend/app/core_finance/` 的影响：无。
