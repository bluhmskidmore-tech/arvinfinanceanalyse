# 股票行情 Tushare 受控缺口补录

当 Choice 历史行情权限不可用时，使用现有股票刷新命令的显式 Tushare 模式补齐已确认的日期缺口。行情保留实际 Tushare 来源以及千元、手的原始单位，消费端统一换算为元、股。默认刷新行为及代际保护保持有效；不要把跨代际放行用于默认 220 日历史窗口。

先备份目标 DuckDB，并核对缺口、目标交易日和可用供应商出口。本地开发运行环境须先执行 `. .\scripts\dev-env.ps1`，让 CLI 与 API、worker 使用同一治理库；仅工作目录一致并不能保证治理连接一致。下面以 2026-08-25 至 2026-09-04 为例；日期和 IP 是本次操作参数，不应固定用于未来补录。先执行 `--dry-run`，再对完整数据库副本运行真实供应商演练，核验窗口外行数及内容指纹、来源、交易日、单位与当日因子。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\choice_stock_daily_refresh.py --dry-run --as-of-date 2026-09-04 --tushare-gap-repair --history-start-date 2026-08-25
```

演练和代码审查通过后，以相同范围运行正式刷新。该入口继续生成标准治理记录与 JSON 回执；历史 CSD 在显式模式下直接使用 Tushare，股票范围和其他可用 Choice 字段仍沿用现有目录。市值来自目标交易日的 Tushare `daily_basic`，从万元换算为元，不沿用旧日因子冒充当前快照。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\choice_stock_daily_refresh.py --run-once --run-kind manual --as-of-date 2026-09-04 --tushare-gap-repair --history-start-date 2026-08-25 --vendor-source-ip 192.168.3.100 --receipt-path data\logs\choice_stock_daily_refresh_receipt.json
```

行情和因子快照更新并不代表复权因子已齐。对缺口内每个真实交易日，再使用 `scripts/stock_adjustment_factor_daily_refresh.py --run-once --as-of-date YYYY-MM-DD --vendor-source-ip <verified-ip>`，或调用其现有任务 `refresh_stock_adjustment_factors_for_trade_date`。该任务只要求并写入当天有有效正收盘价的股票，拒绝供应商错日、非法因子、覆盖不足或已有值冲突，不触发历史 outcome 重算。不要改用会触发额外成熟化任务的旧全量 backfill 脚本。缺少原始收盘价的观察行保持缺失语义，不造价格或因子。

正式验收应再次确认：窗口外历史指纹不变；行情及复权因子自然键无重复；窗口内有效价格对应的复权因子缺口为零；目标日市值及估值输入来自真实当日响应；页面显示实际行情和因子日期。页面的新鲜度状态不能替代上述数据核验，研究用途限制也不会因补录而解除。

日常调度复用 `MOSS-DailyDataRefresh`，启动动作先载入既有 `scripts/dev-env.ps1`，再执行 `scripts/scheduling/daily_data_refresh.ps1 -TushareStockGapRepair`。这个开关只给股票摄入步骤传入 `--tushare-gap-repair`，未提供起点时窗口限定为目标日；后续复权、涨跌停价和分析步骤保持现有顺序。保持旧独立股票定时任务停用，避免重复调度。未来若需恢复 Choice 原生模式，移除该显式调度开关后仍须验证原生接口权限与返回覆盖。
