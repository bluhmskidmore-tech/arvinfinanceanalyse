# `/pnl-by-business` 2026 年上半年 514 增值税回溯操作手册

## 适用口径

- 期间：2026-01-01 至 2026-06-30。
- 正式 FI：现有 V1 应税品种的 514 源金额按含税额处理，除以 `1.06`；免税品种不处理。
- 非标 JM：同一期间内按含税额除以 `1.06`；其他非标代码不处理。
- 2025 年及 2026-07-01 之后不应用本次回溯规则。
- 正式事实规则版本必须为 `rv_pnl_phase2_materialize_v2`。页面和预计算在发现旧版本事实时会拒绝继续读取。

## 执行前

1. 停止占用目标 DuckDB 的 API/worker 进程。
2. 同时备份 `MOSS_DUCKDB_PATH` 指向的数据库文件和 `MOSS_GOVERNANCE_PATH` 指向的治理目录。物化任务会追加 build-run、cache manifest 等治理记录，二者必须使用同一个备份时点。
3. 确认 1—6 月源文件仍在当前 PnL 数据根目录中。

## 回溯物化

在仓库根目录的 PowerShell 中执行：

```powershell
$dates = @(
  "2026-01-31",
  "2026-02-28",
  "2026-03-31",
  "2026-04-30",
  "2026-05-31",
  "2026-06-30"
)

foreach ($date in $dates) {
  python scripts/run_materialize_pipeline_sync.py `
    --skip source balance bond product_category `
    --pnl-report-date $date
  if ($LASTEXITCODE -ne 0) { throw "PnL materialize failed for $date" }
}
```

每个月的 PnL 物化成功后会自动重建对应的 `/pnl-by-business` 预计算结果；任何一个月失败都应停止，不要跳过后继续。

## 验证

重启 API 后执行：

```powershell
$result = Invoke-RestMethod `
  "http://localhost:7888/api/pnl/by-business-ytd?year=2026&as_of_date=2026-06-30"

$result.result | Select-Object `
  year, as_of_date, total_pnl, classified_parent_total_pnl, `
  unallocated_pnl, reconciliation_delta
```

验收条件：

- 接口成功返回，未报告旧规则版本。
- `reconciliation_delta` 为 `0.00`。
- 1—6 月正式事实的 `rule_version` 均为 `rv_pnl_phase2_materialize_v2`。
- 4 月手工补录的非标 517 金额 `154258000.00` 只出现一次，6 月累计文件不重复覆盖或追加该笔 4 月数据。
- J4 页面名称为“其中：结构化产业基金（产业基金部分）”。

## 回滚

若任一验收条件失败，停止 API/worker，同时恢复执行前同一时点的 DuckDB 与治理目录备份；不要只回滚数据库，也不要通过手工改事实表绕过版本门禁。
