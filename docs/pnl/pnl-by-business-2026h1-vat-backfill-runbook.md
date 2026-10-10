# `/pnl-by-business` FI 517、J1 换汇与分类历史重算手册

## 适用口径

- FI 514、非标 JM 514 的税务回溯期间：2026-01-01 至 2026-06-30。该窗口不限制 FI 517 认定和 J1 汇率转换。
- 正式 FI：仅现有 V1 规则明确认定的应税品种，其 514 源金额按含税额处理并除以 `1.06`；H/A/T 仅表示投资分类，不作为增值税应税判断，免税品种不处理。
保留 `realized_formal` 与 `realized_incremental` 的独立读数和期间边界；本地业务执行金额与差额不附入公开版本，公开文档不据此宣称回填验收完成。
- 非标 JM：同一期间内按含税额除以 `1.06`；其他非标代码不处理。
- 外币委外 J1：原始美元 514/516/517 按各月正式 USD/CNY 月末汇率折人民币，2025 年也适用，且没有 2026H1 截止日；JM 与 J4 不应用这一 J1 规则。重复执行必须重新读取原始凭证，不得对已换汇的桥接事实再次乘汇率。
- 未带 FI 源事件标识的其他来源，仍需各自的已实现和不重复语义；FI/JM 514 税务窗口与 FI 516/517 全日期规则分开。
- 所有查询期间的 FI 和非标事实均必须为 `rv_pnl_phase2_materialize_v7`。页面和预计算同时检查两类事实，不能保留旧版本或按历史日期跳过校验。
- G2 信托归入非底层投资资产和信托计划，历史来源别名“大额存单”归入同业存单。损益与日均余额共用分类，其中项不重复计入父级合计。
- 外国债券披露清单补入 `292680026`、`292680027` 两只印尼主权人民币债，依据正式余额中的发行人“印度尼西亚共和国”；同时从非金融企业债券中排除，避免 FI“企业债”标签重复匹配。不能据此扩展到其他 `29*` 代码。
- 月报和 YTD 占比统一采用含未分类项的来源总损益作为分母，零分母返回 null。业务预计算规则和缓存版本同步为 `rv_pnl_by_business_precompute_v11`。

## 执行前

1. 停止占用目标 DuckDB 的 API/worker 进程。
2. 同时备份 `MOSS_DUCKDB_PATH` 指向的数据库文件和 `MOSS_GOVERNANCE_PATH` 指向的治理目录。物化任务会追加 build-run、cache manifest 等治理记录，二者必须使用同一个备份时点。
3. 枚举 FI 与非标事实中的全部报告日期，不设置年份下限；确认各期原始来源仍可读取。
4. 只读回放来源并与当前事实逐笔比较，记录预期差额及汇率版本。本次 v6 到 v7 的现有 19 个月（2025 年 1 月至 2026 年 7 月）全部金额应保持一致；若存在更早日期或更旧规则事实，须单独核对其 FI 517 认定和其他历史修正差额。

## 回溯物化

对所有已加载月份按日期升序整包重放，包含 FI 和非标原始来源。临时 FI-only 参数已移除；只重建预计算或改版本标签都不能修正旧事实。用仓库解释器执行下面的 Python 代码：

```python
import duckdb
from backend.app.governance.settings import get_settings
from backend.app.services.pnl_source_service import load_latest_pnl_refresh_input
from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync

settings = get_settings()
with duckdb.connect(str(settings.duckdb_path), read_only=True) as conn:
    dates = [row[0] for row in conn.execute(
        "select report_date from fact_formal_pnl_fi union "
        "select report_date from fact_nonstd_pnl_bridge order by report_date"
    ).fetchall()]
for report_date in dates:
    bundle = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path, report_date=report_date,
    )
    result = run_pnl_materialize_sync(
        report_date=report_date, is_month_end=bundle.is_month_end, fi_rows=bundle.fi_rows,
        nonstd_rows_by_type=bundle.nonstd_rows_by_type,
        duckdb_path=str(settings.duckdb_path), governance_dir=str(settings.governance_path),
    )
    assert result["status"] == "completed", result
    print(report_date, result["rule_version"], flush=True)
```

每个月的 PnL 物化成功后会自动重建对应的 `/pnl-by-business` 预计算结果；任何一个月失败都应停止，不要跳过后继续。

## 验证

重启 API 后执行：

```powershell
$result = Invoke-RestMethod `
  "http://localhost:7888/api/pnl/by-business-ytd?year=2026&as_of_date=2026-07-31"

$result.result | Select-Object `
  year, as_of_date, total_pnl, classified_parent_total_pnl, `
  unallocated_pnl, reconciliation_delta
```

验收条件：

- 接口成功返回，未报告旧规则版本。
- `reconciliation_delta` 为 `0.00`。
- 所有已加载日期的 FI 与非标事实全部使用 `rv_pnl_phase2_materialize_v7`，相应业务预计算使用 v11；未重建的旧版快照不得继续命中，读取应使用当前规则实时计算。
- 2025 年国债资本利得不再为零，逐笔对应源文件 517 的符号反向和价税分离；2026 年金额与回溯前一致。
- 正式 FI 517 合计不再为零，且同业存单本期源文件 517 与既有历史手工补录分别保留、不得相互覆盖。
- 外币委外 J1 的 `source_version` 包含对应月份的正式汇率版本；JM 不包含汇率版本。
本地业务验收的期间金额与归因差额保留在私有执行回执，公开版本不附这些读数。
本地运行结果不构成公开的完成声明；公开候选须用人工合成数据验证口径和守卫。
- 月报与 YTD 占比分母一致，父级汇总排除其中项；同时复核分类后的日均、年化收益和 FTP 成本。`reconciliation_delta=0` 本身不能证明币种和分类正确。
- 4 月手工补录的非标 517 金额 `154258000.00` 只出现一次，6 月累计文件不重复覆盖或追加该笔 4 月数据。
- J4 页面名称为“结构化融资（券商）”。

## 回滚

若任一验收条件失败，停止 API/worker，同时恢复执行前同一时点的 DuckDB 与治理目录备份；不要只回滚数据库，也不要通过手工改事实表绕过版本门禁。
