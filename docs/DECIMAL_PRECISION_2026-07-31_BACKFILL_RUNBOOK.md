# 2026-07-31 Decimal 精度单日生产回填 Runbook

执行状态：**BLOCKED — 本文档不授权当前直接写生产**。

本文档记录 `2026-07-31` 的 Decimal 精度单日回填边界、停写、备份、执行门禁、验收和回滚要求。仓库现已提供固定单日 runner `scripts/run_decimal_precision_backfill.py` 和强只读 verifier `scripts/verify_decimal_precision_backfill.py`，并已在私有、静止的隔离 DuckDB 上完成全链演练。该结果只证明代码和数据链具备隔离执行能力；它不验证生产维护窗口、生产 writer quiescence、SQL authority/JSONL/DB/archive 协调备份与恢复，也不构成业务 owner 的生产批准。操作员在这些外部门禁闭合前仍不得执行生产物化。

## 1. 范围与非授权事项

本次只允许重算：

```text
zqtz/tyw standardized snapshot
→ formal balance
→ formal bond analytics
→ formal risk tensor
```

固定参数：

| 项目 | 固定值 |
| --- | --- |
| report date | `2026-07-31` |
| ingest batch | `ib_caddbbe10b2e` |
| ZQTZ source version | `sv_de5be20e6794` |
| TYW source version | `sv_7023ef05edc8` |
| snapshot rule | `rv_snapshot_zqtz_tyw_v1` |

以下不在本次范围内：

- 全历史回填；
- formal PnL、product-category PnL、accounting asset movement 或 source preview 重算；
- 新增或刷新 vendor FX、收益率曲线、宏观、新闻或股票数据；
- 手工 SQL 更新事实表；
- 修改 schema、规则版本或指标定义；
- 将本 runbook 或隔离演练视为业务 owner 对生产写入的批准。

## 2. 锁定来源与预期结果

必须使用下列两个已归档来源；文件名、长度、SHA256、source version 或 batch 任一不符即停止。

| family | archive | bytes | SHA256 |
| --- | --- | ---: | --- |
| ZQTZ | `ZQTZSHOW-20260731__96e96983b31f__ib_caddbbe10b2e.xls` | 1,396,224 | `DE5BE20E6794F50326E4171D2094F4F6AE62E75DA170F269013F05D2333FB132` |
| TYW | `TYWLSHOW-20260731__37b24b37611d__ib_caddbbe10b2e.xls` | 1,433,088 | `7023EF05EDC8E65D85B97981123896D36F71957F8EAAE13AF783DF999B57883B` |

隔离演练锁定的目标日预期：

| table | expected rows |
| --- | ---: |
| `zqtz_bond_daily_snapshot` | 1,872 |
| `tyw_interbank_daily_snapshot` | 3,128 |
| `fact_formal_zqtz_balance_daily` | 3,744 |
| `fact_formal_tyw_balance_daily` | 6,256 |
| `fact_formal_bond_analytics_daily` | 1,750 |
| `fact_formal_risk_tensor_daily` | 1 |

TYW 原始解析为 3,133 行；按 canonical grain `(report_date, position_id)` 合并后为 3,128 行。该 `-5` 是 3 个重复 grain 的受控合并，不是丢数。

已知源数据警告：证券 `XS3034102791` 和 `XS3047137040` 的 YTM 分别为 `878.3497`、`20720.9302`，正式债券计算会将其归一化为缺失值。该警告必须保留在执行记录中；不得在本次精度回填中顺手修正或静默填值。

冻结 FX 口径为 `AUD/CNY=4.74410000`、`CAD/CNY=4.82060000`、`EUR/CNY=7.78860000`、`HKD/CNY=0.86559000`、`USD/CNY=6.78940000`，共同 source version 为 `sv_fx_chinamoney_4d21e1e9a6c3`。

冻结曲线 fallback date 为 `2026-06-30`，rule version 均为 `rv_yield_curve_formal_materialize_v1`：

| curve | points | vendor | vendor/source version | canonical row SHA256 |
| --- | ---: | --- | --- | --- |
| `aaa_credit` | 9 | `choice` | `vv_choice_aaa_credit_20260630_8c11af661fd4` / `sv_yield_curve_aaa_credit_8c11af661fd4` | `6433D1B9E3A2373A25637470201CBC46947979A70D3A185FB680130502B0F8F9` |
| `cdb` | 8 | `choice` | `vv_choice_cdb_20260630_3a6861339722` / `sv_yield_curve_cdb_3a6861339722` | `7C85EDF86AE1D07C32FCCBC705C9193C12B46063E720E79A8405232CDDCCEB56` |
| `treasury` | 9 | `akshare` | `vv_akshare_treasury_20260630_f91623b0de5c` / `sv_yield_curve_treasury_f91623b0de5c` | `DBD41DF5E9EC93347610E394E58DBCF1A17C3027B7B0E0E24B4F5C35C5C602CD` |

任一 FX 或曲线值/版本在生产执行前发生变化，都必须重新做影响评估和隔离演练，不能沿用本 runbook 的既有结论。

### 2.1 已完成的隔离演练证据

受支持 runner 使用静态 baseline `SHA256=739DF1A9F3598463DB3FDAE2DEB2E689967ADBCFE1D4B07928B6515AC993A8C7`，在私有 DuckDB、私有治理副本和两份锁定 archive 上执行。最终机器回执为 `apply-receipt-v3.json`，长度 `1,017,168` 字节，`SHA256=D9E79DA3EA40F9BE9C21D58025E7EE4C12DA3D9E30D8646A201721E29021F1DA`。回执证明：

- snapshot → balance → bond → risk 四阶段依次 completed，`write_completed=true`；
- 目标日行数分别为 1,872 / 3,128 / 3,744 / 6,256 / 1,750 / 1；
- archive parser + merge 到 snapshot 的 canonical-grain/Decimal 对平无 missing、extra、mismatch 或 required-null；
- formal balance、bond 和 risk 的 trace、金额与聚合残差均为 0；
- strong verifier 为 `PASS`、errors 为空、baseline/current fingerprint 稳定、63 张 BASE TABLE inventory 一致，且所有非允许 delta 不变；
- verifier 外部排序采用固定宽度二进制 digest，并在每张表结束后立即清理 chunk；全量演练观察到的临时空间峰值约 128 MB；
- `production_gate` 仅在显式 library rehearsal 中关闭，回执中的 `production_approval_granted_by_script=false`。

前两次演练分别暴露并阻断了 verifier 临时文件跨表累积，以及 snapshot 中间态被 full-chain validator 误判的问题；两项均在定向回归后修复。失败回执不能被第三次成功回执覆盖或解释为成功。

## 3. 受支持入口与明确禁用入口

### `scripts/run_decimal_precision_backfill.py`

这是本次唯一受支持的工作流入口。它固定 date/batch/families/input hashes，提供 `--dry-run`、`--verify-only`、`--apply`，且没有默认写入模式或 CLI 生产门禁绕过。`--apply` 仍必须通过脚本内生产 gate，并同时满足本文档第 4、6、8、10 节的外部审批、停写、备份和恢复条件。`maintenance-window-ref` 与 `dba-backup-ref` 只是操作员提供的证据引用；脚本明确不独立验证这些外部事实，因此两个非空字符串不能解除本页顶部的 `BLOCKED`。

### `scripts/verify_decimal_precision_backfill.py`

这是本次唯一受支持的 baseline/current DuckDB 强只读 verifier。它本身不执行物化，也不能替代 runner 的 source、stage、governance 或生产授权检查。

### `scripts/run_global_data_refresh.py`

不得用于本次回填。它还会执行 formal PnL、product-category PnL、accounting asset movement 和 source preview，超出单日精度修复范围；其 `--dry-run` 只打印计划，不验证 manifest、batch、archive、FX 或曲线。

### `backend.app.tasks.formal_balance_pipeline`

不得直接用于本次回填。CLI 没有显式 `--ingest-batch-id`，并且会先执行 ingest 和 FX materialization，可能生成新 batch 或访问供应商。

### 默认 balance / bond actor

在当前代码下不得直接用于生产：

- balance actor 会先调用 formal FX materialization；
- bond actor 在精确 anchor curve 缺失时会尝试 vendor fetch，当前 `2026-07-01` 和 `2026-07-31` 依赖 `2026-06-30` 的受控历史 fallback；
- 只有受支持 runner 显式传入 `use_existing_fx_only=True` / `use_existing_curves_only=True` 并通过冻结输入验证时，才能进入本次四阶段链；不得绕开 runner 直接调用 actor。

### 直接仓储或 SQL 写入

禁止。所有生产 DuckDB 写入必须继续经过 `backend.app.tasks.*` 和现有治理 runtime。

## 4. 解除生产阻断的必要条件

代码侧确定性入口和定向测试已落地；在排期生产维护窗口前，该入口仍必须持续满足以下合同，且不得以隔离演练替代生产外部证据：

1. 强制传入 `report_date=2026-07-31`、`ingest_batch_id=ib_caddbbe10b2e`、`source_families=[zqtz, tyw]`。
2. 只接受上表两个 source version 和 archive SHA；不允许自动选择最新 batch。
3. 把 `source_manifest.jsonl` 和两个 archive 作为不可变输入；不得调用 ingest、追加 source manifest 或生成新归档。
4. balance 阶段使用已有受治理 FX 或 checksum-pinned 显式 FX 输入，且禁止网络请求。
5. bond 阶段只接受已存在、在允许回溯窗口内的曲线，且禁止 vendor fetch 或曲线写入。
6. 严格按 snapshot → balance → bond → risk 顺序执行，首错停止。
7. 每一阶段都通过现有 task actor / formal runtime 写入。snapshot 沿用当前合同，只追加 completed/failed terminal；balance/bond/risk formal runtime 生成 queued → running → completed/failed。外层 receipt 必须统一记录四阶段 start/terminal，不得伪造 snapshot 不存在的 queued/running 治理记录。
8. 输出机器可读 receipt，包含 run ID、输入哈希、每阶段行数、source/rule/cache lineage 和失败类别。
9. 支持 `--dry-run`/`--verify-only`；只读模式必须真实校验 manifest、archive、FX、曲线和目标 grain，而不只是打印步骤名。
10. 有定向测试证明：禁止网络、禁止跨日期写入、治理终态失败时整体报错、同一批次重跑幂等、失败后不会宣称成功。
11. 使用这个最终生产命令再完成一次隔离演练；不得把临时 monkeypatch 版本的成功替代为生产命令证据。
12. 在 SQL-authority 治理模式下，receipt 和验收必须同时核对权威 SQL 记录与 JSONL mirror；二者不一致即失败。
13. 第 8.3 节的强 SHA256 verifier 必须以受版本控制的脚本和定向测试落地，能够输出机器 evidence；算法说明本身不构成可执行验收工具。

上述十三项已由代码、定向测试和隔离演练覆盖其本地可验证部分；生产 SQL authority、真实服务/队列停写、协调备份与恢复等环境事实仍必须在生产工单中单独闭合。在所有外部门禁完成前，本 runbook 的后续“写入阶段”保持未授权。

## 5. 只读 preflight

从仓库根目录运行。所有目标路径必须由环境 owner 明确填写，再与 `get_settings()` 的运行时解析结果比对；不要把仓库默认路径当成生产路径，也不要依赖当前目录、`~` 或未展开环境变量。

```powershell
$RepoRoot = (Resolve-Path '.').Path
$Python = 'REPLACE_WITH_OWNER_APPROVED_ABSOLUTE_PYTHON_PATH'
$ExpectedCommit = 'REPLACE_WITH_OWNER_APPROVED_GIT_COMMIT_SHA'
$ExpectedDb = 'REPLACE_WITH_OWNER_APPROVED_ABSOLUTE_DUCKDB_PATH'
$ExpectedGov = 'REPLACE_WITH_OWNER_APPROVED_ABSOLUTE_GOVERNANCE_PATH'
$ExpectedArchive = 'REPLACE_WITH_OWNER_APPROVED_ABSOLUTE_ARCHIVE_PATH'
$EvidenceRoot = 'REPLACE_WITH_OWNER_APPROVED_EVIDENCE_PATH'
$Date = '2026-07-31'
$Batch = 'ib_caddbbe10b2e'

foreach ($value in @($Python, $ExpectedDb, $ExpectedGov, $ExpectedArchive, $EvidenceRoot)) {
  if ($value.StartsWith('REPLACE_') -or -not [IO.Path]::IsPathRooted($value)) {
    throw "Owner-approved absolute path required: $value"
  }
}
if ($ExpectedCommit.StartsWith('REPLACE_') -or $ExpectedCommit -notmatch '^[0-9a-fA-F]{40}$') {
  throw 'Owner-approved full Git commit SHA is required.'
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Approved Python runtime is missing.' }
if (-not (Test-Path -LiteralPath $ExpectedDb -PathType Leaf)) { throw 'Approved DuckDB is missing.' }
if (-not (Test-Path -LiteralPath $ExpectedGov -PathType Container)) { throw 'Approved governance path is missing.' }
if (-not (Test-Path -LiteralPath $ExpectedArchive -PathType Container)) { throw 'Approved archive root is missing.' }

$RepoCommit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $RepoCommit) { throw 'Repository commit identity is unavailable.' }
if (-not $RepoCommit.Equals($ExpectedCommit, [StringComparison]::OrdinalIgnoreCase)) {
  throw "Runtime commit $RepoCommit does not match approved commit $ExpectedCommit"
}
$RepoStatus = @(& git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $RepoStatus.Count -ne 0) {
  throw 'Production preflight requires a clean, review-approved working tree.'
}

$env:MOSS_BACKFILL_EXPECTED_DB_PATH = [IO.Path]::GetFullPath($ExpectedDb)
$env:MOSS_BACKFILL_EXPECTED_GOV_PATH = [IO.Path]::GetFullPath($ExpectedGov)
$env:MOSS_BACKFILL_EXPECTED_ARCHIVE_PATH = [IO.Path]::GetFullPath($ExpectedArchive)

$RuntimeJson = @'
import json
import os
from pathlib import Path

from backend.app.governance.settings import get_settings

settings = get_settings()
resolved = {
    "duckdb_path": str(Path(settings.duckdb_path).resolve()),
    "governance_path": str(Path(settings.governance_path).resolve()),
    "archive_path": str(Path(settings.local_archive_path).resolve()),
    "environment": str(settings.environment),
    "governance_backend": str(settings.governance_backend),
    "source_preview_governance_backend": str(settings.source_preview_governance_backend),
    "object_store_mode": str(settings.object_store_mode),
    "governance_sql_configured": bool(str(settings.governance_sql_dsn or "").strip()),
    "job_state_sql_configured": bool(str(settings.job_state_dsn or "").strip()),
}
assert Path(resolved["duckdb_path"]) == Path(os.environ["MOSS_BACKFILL_EXPECTED_DB_PATH"])
assert Path(resolved["governance_path"]) == Path(os.environ["MOSS_BACKFILL_EXPECTED_GOV_PATH"])
assert Path(resolved["archive_path"]) == Path(os.environ["MOSS_BACKFILL_EXPECTED_ARCHIVE_PATH"])
print(json.dumps(resolved))
'@ | & $Python -
if ($LASTEXITCODE -ne 0) { throw 'Runtime settings/path resolution failed.' }

$Runtime = $RuntimeJson | ConvertFrom-Json
if ($Runtime.environment -ne 'production') {
  throw "Production runbook requires MOSS_ENVIRONMENT=production; got $($Runtime.environment)"
}
if (
  $Runtime.governance_backend -ne 'sql-authority' -or
  $Runtime.source_preview_governance_backend -ne 'sql-authority' -or
  -not $Runtime.governance_sql_configured
) {
  throw 'Production SQL-authority governance is not fully configured.'
}
$Db = $Runtime.duckdb_path
$Gov = $Runtime.governance_path
$Archive = $Runtime.archive_path
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$RepoPrefix = $RepoRoot.TrimEnd('\') + '\'
if (
  $EvidenceRoot.Equals($RepoRoot, [StringComparison]::OrdinalIgnoreCase) -or
  $EvidenceRoot.StartsWith($RepoPrefix, [StringComparison]::OrdinalIgnoreCase)
) {
  throw 'Evidence path must be outside the repository.'
}
New-Item -ItemType Directory -Path $EvidenceRoot -Force -ErrorAction Stop | Out-Null
```

另外记录但不要输出任何 DSN、密码或 access key：

- `MOSS_ENVIRONMENT`；
- `MOSS_GOVERNANCE_BACKEND` 与 `MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND`；
- `MOSS_OBJECT_STORE_MODE`；
- 是否配置 SQL-authority governance 或 SQL job state、其 DBA owner 和备份工单号。

生产执行必须解析为 SQL authority：cache build-run/cache manifest 写入权威 SQL，并同时保留 JSONL mirror；其他 snapshot/source 治理流仍位于其 JSONL 合同。不得仅根据本地 JSONL 判断生产治理完整性。

### 5.1 生产文件基线

```powershell
$BaselineFiles = @((Get-Item -LiteralPath $Db)) + @(
  Get-ChildItem -LiteralPath $Gov -Recurse -File -ErrorAction Stop
)
$BaselineRecords = $BaselineFiles | ForEach-Object {
  $item = Get-Item -LiteralPath $_
  $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName
  [pscustomobject]@{
    path = $item.FullName
    bytes = $item.Length
    mtime_utc = $item.LastWriteTimeUtc.ToString('o')
    sha256 = $hash.Hash
  }
}
$BaselineReceipt = Join-Path $EvidenceRoot 'decimal-backfill-20260731-file-baseline.json'
$BaselineRecords | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $BaselineReceipt -Encoding UTF8
Get-FileHash -Algorithm SHA256 -LiteralPath $BaselineReceipt

$ArchiveBaselineRecords = Get-ChildItem -LiteralPath $Archive -Recurse -File -ErrorAction Stop |
  Sort-Object FullName |
  ForEach-Object {
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    [pscustomobject]@{
      relative_path = [IO.Path]::GetRelativePath($Archive, $_.FullName)
      bytes = $_.Length
      mtime_utc = $_.LastWriteTimeUtc.ToString('o')
      sha256 = $hash.Hash
    }
  }
$ArchiveBaselineReceipt = Join-Path $EvidenceRoot 'decimal-backfill-20260731-archive-baseline.json'
$ArchiveBaselineRecords | ConvertTo-Json -Depth 4 |
  Set-Content -LiteralPath $ArchiveBaselineReceipt -Encoding UTF8
Get-FileHash -Algorithm SHA256 -LiteralPath $ArchiveBaselineReceipt
```

`$RepoCommit`、`$BaselineReceipt`、`$ArchiveBaselineReceipt` 及其 SHA 必须保存进变更单/维护工单。SQL-authority 与 SQL job-state 的只读基线由 DBA 另行导出为 canonical sorted rows/hash；不得把 DSN 或凭据写入 evidence。仅在屏幕上查看不构成可回滚证据。

### 5.2 manifest、archive 与数据库只读门禁

下面命令只读 manifest、archive 和 DuckDB；任一断言失败即停止。

```powershell
$PreflightJson = @'
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import duckdb

db = Path(os.environ["MOSS_BACKFILL_EXPECTED_DB_PATH"]).resolve()
gov = Path(os.environ["MOSS_BACKFILL_EXPECTED_GOV_PATH"]).resolve()
archive_root = Path(os.environ["MOSS_BACKFILL_EXPECTED_ARCHIVE_PATH"]).resolve()
date = "2026-07-31"
batch = "ib_caddbbe10b2e"
expected = {
    "zqtz": {
        "source_version": "sv_de5be20e6794",
        "bytes": 1396224,
        "sha256": "DE5BE20E6794F50326E4171D2094F4F6AE62E75DA170F269013F05D2333FB132",
    },
    "tyw": {
        "source_version": "sv_7023ef05edc8",
        "bytes": 1433088,
        "sha256": "7023EF05EDC8E65D85B97981123896D36F71957F8EAAE13AF783DF999B57883B",
    },
}

selected = []
for line in (gov / "source_manifest.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if (
        row.get("report_date") == date
        and row.get("ingest_batch_id") == batch
        and row.get("source_family") in expected
        and row.get("status") in {"completed", "rerun"}
    ):
        selected.append(row)

assert len(selected) == 2, f"expected exactly two source manifests, got {len(selected)}"
assert {row["source_family"] for row in selected} == {"zqtz", "tyw"}
for row in selected:
    contract = expected[row["source_family"]]
    assert row.get("source_version") == contract["source_version"]
    path = Path(str(row.get("archived_path") or "")).resolve()
    assert path.is_file(), f"archive missing: {path}"
    assert path.is_relative_to(archive_root), f"archive escaped approved root: {path}"
    assert path.stat().st_size == contract["bytes"]
    assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == contract["sha256"]

con = duckdb.connect(str(db), read_only=True)
try:
    counts = {
        table: con.execute(
            f'SELECT count(*) FROM "{table}" WHERE cast("{column}" AS varchar) = ?',
            [date],
        ).fetchone()[0]
        for table, column in (
            ("zqtz_bond_daily_snapshot", "report_date"),
            ("tyw_interbank_daily_snapshot", "report_date"),
            ("fx_daily_mid", "trade_date"),
            ("fact_formal_zqtz_balance_daily", "report_date"),
            ("fact_formal_tyw_balance_daily", "report_date"),
            ("fact_formal_bond_analytics_daily", "report_date"),
            ("fact_formal_risk_tensor_daily", "report_date"),
        )
    }
    assert counts == {
        "zqtz_bond_daily_snapshot": 1872,
        "tyw_interbank_daily_snapshot": 3128,
        "fx_daily_mid": 5,
        "fact_formal_zqtz_balance_daily": 3744,
        "fact_formal_tyw_balance_daily": 6256,
        "fact_formal_bond_analytics_daily": 1750,
        "fact_formal_risk_tensor_daily": 1,
    }, counts

    fx = con.execute(
        """
        SELECT
          upper(base_currency),
          upper(quote_currency),
          mid_rate,
          source_name,
          source_version,
          vendor_name,
          vendor_version,
          vendor_series_code,
          cast(observed_trade_date AS varchar),
          is_business_day,
          is_carry_forward
        FROM fx_daily_mid
        WHERE cast(trade_date AS varchar) = ?
        ORDER BY 1, 2
        """,
        [date],
    ).fetchall()
    expected_fx = {
        ("AUD", "CNY"): Decimal("4.74410000"),
        ("CAD", "CNY"): Decimal("4.82060000"),
        ("EUR", "CNY"): Decimal("7.78860000"),
        ("HKD", "CNY"): Decimal("0.86559000"),
        ("USD", "CNY"): Decimal("6.78940000"),
    }
    assert len(fx) == 5
    assert len({(row[0], row[1]) for row in fx}) == 5
    assert {(row[0], row[1]): row[2] for row in fx} == expected_fx
    assert all(row[2] is not None and Decimal(str(row[2])).is_finite() and row[2] > 0 for row in fx)
    assert all(all(str(row[index] or "").strip() for index in (3, 4, 5, 6, 7, 8)) for row in fx)
    expected_fx_lineage = {
        "AUD": ("CFETS", "sv_fx_chinamoney_4d21e1e9a6c3", "chinamoney", "vv_chinamoney_fx_20260731_4d21e1e9a6c3", "EMM00058129"),
        "CAD": ("CFETS", "sv_fx_chinamoney_4d21e1e9a6c3", "chinamoney", "vv_chinamoney_fx_20260731_4d21e1e9a6c3", "EMM00058130"),
        "EUR": ("CFETS", "sv_fx_chinamoney_4d21e1e9a6c3", "chinamoney", "vv_chinamoney_fx_20260731_4d21e1e9a6c3", "EMM00058125"),
        "HKD": ("CFETS", "sv_fx_chinamoney_4d21e1e9a6c3", "chinamoney", "vv_chinamoney_fx_20260731_4d21e1e9a6c3", "EMM01588399"),
        "USD": ("CFETS", "sv_fx_chinamoney_4d21e1e9a6c3", "chinamoney", "vv_chinamoney_fx_20260731_4d21e1e9a6c3", "EMM00058124"),
    }
    assert {row[0]: tuple(row[3:8]) for row in fx} == expected_fx_lineage
    assert all(row[8] == date and bool(row[9]) and not bool(row[10]) for row in fx)

    curve_rows = con.execute(
        """
        WITH anchors(anchor_date) AS (
          VALUES (DATE '2026-06-30'), (DATE '2026-07-01'), (DATE '2026-07-31')
        ), curve_types(curve_type) AS (
          VALUES ('treasury'), ('cdb'), ('aaa_credit')
        )
        SELECT
          a.anchor_date,
          c.curve_type,
          max(cast(y.trade_date AS date)) FILTER (
            WHERE cast(y.trade_date AS date) <= a.anchor_date
              AND cast(y.trade_date AS date) >= a.anchor_date - INTERVAL 40 DAY
          ) AS resolved_trade_date
        FROM anchors a
        CROSS JOIN curve_types c
        LEFT JOIN fact_formal_yield_curve_daily y ON y.curve_type = c.curve_type
        GROUP BY a.anchor_date, c.curve_type
        ORDER BY a.anchor_date, c.curve_type
        """
    ).fetchall()
    assert len(curve_rows) == 9
    assert all(row[2] is not None for row in curve_rows), curve_rows
    assert {str(row[2]) for row in curve_rows} == {"2026-06-30"}, curve_rows

    curve_contract = con.execute(
        """
        SELECT
          curve_type,
          count(*) AS point_count,
          count(DISTINCT vendor_name) AS vendor_count,
          count(DISTINCT vendor_version) AS vendor_version_count,
          count(DISTINCT source_version) AS source_version_count,
          count(DISTINCT rule_version) AS rule_version_count,
          sum(CASE WHEN rate_pct IS NULL THEN 1 ELSE 0 END) AS null_rate_count,
          min(rule_version) AS rule_version,
          min(vendor_name) AS vendor_name,
          min(vendor_version) AS vendor_version,
          min(source_version) AS source_version
        FROM fact_formal_yield_curve_daily
        WHERE cast(trade_date AS varchar) = '2026-06-30'
          AND curve_type IN ('treasury', 'cdb', 'aaa_credit')
        GROUP BY curve_type
        ORDER BY curve_type
        """
    ).fetchall()
    assert [(row[0], row[1]) for row in curve_contract] == [
        ("aaa_credit", 9),
        ("cdb", 8),
        ("treasury", 9),
    ], curve_contract
    assert all(row[2:7] == (1, 1, 1, 1, 0) for row in curve_contract), curve_contract
    assert {row[7] for row in curve_contract} == {"rv_yield_curve_formal_materialize_v1"}
    assert [(row[0], row[8], row[9], row[10]) for row in curve_contract] == [
        (
            "aaa_credit",
            "choice",
            "vv_choice_aaa_credit_20260630_8c11af661fd4",
            "sv_yield_curve_aaa_credit_8c11af661fd4",
        ),
        (
            "cdb",
            "choice",
            "vv_choice_cdb_20260630_3a6861339722",
            "sv_yield_curve_cdb_3a6861339722",
        ),
        (
            "treasury",
            "akshare",
            "vv_akshare_treasury_20260630_f91623b0de5c",
            "sv_yield_curve_treasury_f91623b0de5c",
        ),
    ], curve_contract

    expected_curve_hashes = {
        "aaa_credit": "6433D1B9E3A2373A25637470201CBC46947979A70D3A185FB680130502B0F8F9",
        "cdb": "7C85EDF86AE1D07C32FCCBC705C9193C12B46063E720E79A8405232CDDCCEB56",
        "treasury": "DBD41DF5E9EC93347610E394E58DBCF1A17C3027B7B0E0E24B4F5C35C5C602CD",
    }
    curve_hashes = {}
    for curve_type in expected_curve_hashes:
        rows = con.execute(
            """
            SELECT tenor, cast(rate_pct AS varchar), vendor_name, vendor_version,
                   source_version, rule_version
            FROM fact_formal_yield_curve_daily
            WHERE cast(trade_date AS varchar) = '2026-06-30' AND curve_type = ?
            ORDER BY tenor
            """,
            [curve_type],
        ).fetchall()
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        curve_hashes[curve_type] = hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()
    assert curve_hashes == expected_curve_hashes, curve_hashes
finally:
    con.close()

print(json.dumps({
    "status": "preflight_pass",
    "archives": [
        str(Path(row["archived_path"]).resolve())
        for row in sorted(selected, key=lambda item: item["source_family"])
    ],
    "counts": counts,
    "fx": fx,
    "curve_anchors": curve_rows,
    "curve_contract": curve_contract,
    "curve_hashes": curve_hashes,
}, default=str))
'@ | & $Python -
if ($LASTEXITCODE -ne 0) { throw 'Read-only preflight failed.' }
$PreflightReceipt = Join-Path $EvidenceRoot 'decimal-backfill-20260731-preflight.json'
$PreflightJson | Set-Content -LiteralPath $PreflightReceipt -Encoding UTF8
$Preflight = $PreflightJson | ConvertFrom-Json
if (@($Preflight.archives).Count -ne 2) { throw 'Preflight archive contract is incomplete.' }
Get-FileHash -Algorithm SHA256 -LiteralPath $PreflightReceipt
```

该检查只证明受治理输入存在；它不会阻止默认 actor 发起网络请求，因此不解除第 4 节的生产阻断。

## 6. 维护窗口与同点备份

只有第 4 节完成并再次获得明确生产批准后，才进入本节。

1. 暂停定时器、keepalive 和任何可能自动重启 API/worker 的外部 supervisor。
2. 停止所有会读取或写入目标 DuckDB 的 API/worker，并由队列 owner 确认没有已排队或正在执行的 materialize/refresh job。不得通过盲目清空队列来制造“空闲”状态。
3. 当前仓库只记录了 Windows native dev 和 Docker Compose dev，没有生产 service manager/scheduler 的权威停服命令。生产维护工单必须附上环境 owner 批准的实际停服/防自动拉起步骤。对于仓库内已验证的 Windows native dev 栈，使用：

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1
   ```

   对 Compose 使用环境 owner 审批的停服命令；最低限度必须停止 `api` 和 `worker`。不要把仓库 dev 命令冒充未记录的生产部署命令。
4. 用进程清单确认不存在 `uvicorn backend.app.main:app`、`backend.app.tasks.dev_worker_runner`、`dramatiq ... worker_bootstrap`、定时任务或其他目标 DB writer。文件锁没有替代停写：global refresh lock 与各 task writer lock 不是同一把锁。
5. 确认 `moss.duckdb.wal` 不存在，并重新获取 DB SHA/length/mtime；等待 30 秒后再次获取，必须完全相同。
6. 创建一个全新、明确、非仓库临时目录的备份位置。下面的占位路径故意 fail closed，操作员必须替换。除 DuckDB 和完整 JSONL 治理目录外，本地非版本化 archive 必须备份整个命名空间；若 archive 位于受版本化、不可变对象存储，可用完整 namespace inventory + 可恢复对象版本 ID 替代文件副本，但不能只写“已存在”：

   ```powershell
   $ApprovedBackupRoot = 'F:\approved-backup-root'
   if (
     $ApprovedBackupRoot -eq 'F:\approved-backup-root' -or
     -not [IO.Path]::IsPathRooted($ApprovedBackupRoot)
   ) {
     throw 'Replace ApprovedBackupRoot with the owner-approved backup volume.'
   }
   $ApprovedBackupRoot = [IO.Path]::GetFullPath($ApprovedBackupRoot)
   if (
     $ApprovedBackupRoot.Equals($RepoRoot, [StringComparison]::OrdinalIgnoreCase) -or
     $ApprovedBackupRoot.StartsWith($RepoPrefix, [StringComparison]::OrdinalIgnoreCase)
   ) {
     throw 'Backup root must be outside the repository.'
   }

   $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
   $Backup = Join-Path $ApprovedBackupRoot "moss-decimal-backfill-20260731-$Stamp"
   New-Item -ItemType Directory -Path $Backup -ErrorAction Stop | Out-Null
   Copy-Item -LiteralPath $Db -Destination (Join-Path $Backup 'moss.duckdb') -ErrorAction Stop
   Copy-Item -LiteralPath $Gov -Destination (Join-Path $Backup 'governance') -Recurse -ErrorAction Stop
   Copy-Item -LiteralPath $Archive -Destination (Join-Path $Backup 'archive') -Recurse -ErrorAction Stop

   $InputBackup = Join-Path $Backup 'inputs'
   New-Item -ItemType Directory -Path $InputBackup -ErrorAction Stop | Out-Null
   if (-not $Preflight) {
     $Preflight = Get-Content -LiteralPath $PreflightReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
   }
   $LockedArchives = @($Preflight.archives)
   if ($LockedArchives.Count -ne 2) { throw 'Exactly two locked archives are required.' }
   foreach ($LockedArchive in $LockedArchives) {
     if (-not (Test-Path -LiteralPath $LockedArchive -PathType Leaf)) {
       throw "Locked archive missing: $LockedArchive"
     }
     Copy-Item -LiteralPath $LockedArchive -Destination $InputBackup -ErrorAction Stop
   }
   ```

7. 校验备份 DB 与源 DB 的 SHA256 相同；校验治理目录和整个 archive namespace 的文件数、相对路径、总字节数和逐文件 SHA 与第 5.1 节 inventory 相同；另外校验两份锁定 archive 与第 2 节长度/SHA 合同相同。数据库、治理目录和输入证据必须来自同一个无 writer 的静止点。
8. 如果 `MOSS_GOVERNANCE_BACKEND` 解析为 SQL authority，必须由 DBA 使用该环境批准的原生备份方式备份治理 SQL 数据库；完整数据库备份优先，最低也要覆盖 `cache_build_run` 和 `cache_manifest`。记录备份 ID、LSN/等价恢复点、UTC 时间、artifact SHA256、DBA owner 和已经演练过的恢复命令。不要在本文档或工单输出 DSN/凭据。仅复制 JSONL mirror 不构成完整治理备份。
9. 如果配置了 `MOSS_JOB_STATE_DSN`，还必须备份其权威数据库（至少 `job_run_state`）并记录同等级恢复证据；它可能与 governance SQL DSN 不同，不能推定一次备份同时覆盖二者。
10. 在 SQL 权威库中以只读事务导出目标 cache key 的 canonical sorted 基线及 row count/hash，并与 JSONL mirror 对平。SQL/JSONL 不一致、DBA 备份没有可验证 artifact、或恢复步骤未演练，均不得继续。
11. 在维护工单中记录 DuckDB、JSONL governance、锁定 archive，以及（如适用）SQL governance/job-state 的备份位置或对象版本 ID及校验结果。缺少任一权威存储的同点备份不得继续。

## 7. 受支持入口的写入阶段

本节定义 `scripts/run_decimal_precision_backfill.py` 的阶段合同。由于当前状态仍为 `BLOCKED`，本文档不提供可直接复制执行的生产 `--apply` 命令；最终命令必须来自 owner 审批的维护工单，并使用与 `get_settings()` 解析完全一致的绝对路径和已审 commit。

每一步均须使用绝对生产路径、唯一 run ID，并在下一步前核对返回 `status=completed`：

1. **snapshot**：显式 date、batch 和两 family；预期 1,872 / 3,128；snapshot manifest 必须恰有两条 completed。
2. **balance**：使用冻结且通过 SHA/lineage 校验的现有 FX；预期 3,744 / 6,256；不得写入新的 FX 版本。
3. **bond**：只读已冻结曲线；预期 1,750；不得调用 vendor，不得改写 yield-curve facts。
4. **risk**：预期一行、`bond_count=1750`；上游 source/rule/cache 必须指向本次 bond completed run。

执行前后 `source_manifest.jsonl` 与两个 archive 的 SHA 必须相同；任何变化都表明入口越过了本次范围。

任一步失败、返回非 completed、治理终态缺失、网络访问被检测到、非目标日期发生写入或 receipt 不完整时：立即停止，不得跳过或继续后续阶段。

## 8. 写入后、重启前验收

### 8.1 来源解析与快照精确相等

用当前 `snapshot_row_parse` 重新解析锁定 archive，再调用 `merge_zqtz_rows_by_grain` / `merge_tyw_rows_by_grain`。以 canonical grain 比较生产快照：

- ZQTZ：1,872 → 1,872；missing/extra key = 0；所有 source-origin Decimal 字段 diff = 0；
- TYW：3,133 → 3,128；missing/extra key = 0；所有 source-origin Decimal 字段 diff = 0；
- 排除随机 `trace_id` 和 DB-only 派生 `market_value_cny` 后，其他解析字段必须一致。

### 8.2 正式链对平

- 每个 ZQTZ/TYW snapshot trace 必须各有 `native` 和 `CNY` 两条 formal balance；缺失、孤儿、重复均为 0。ZQTZ 的 `is_issuance_like=true` 行仍进入 formal balance，但其业务归类是负债而不是债券资产；不得因后续 bond 排除逻辑而从 balance 验收中漏掉。
- CNY 金额必须以 `Decimal` 计算并量化为 `DECIMAL(24,8)`，再与 `native × 正式 FX` 精确对平；不得先转 `float`。FX grain 唯一、汇率正数且有限，source/vendor/version/observed date lineage 均非空。
- bond rows 必须与非发行类 snapshot trace 一一对应；missing/extra/duplicate trace = 0。
- formal balance 和 bond 事实物理列中的 `source_version`、`rule_version`、`ingest_batch_id`、`trace_id` 必须非空；risk 事实中的 source/rule/cache/upstream/liability/trace 必填列必须非空。fact 表没有 `run_id` 时，不得假装从事实行直接读取：应按 stage cache key + report date + source/rule/cache 连接本次 `cache_manifest`/`cache_build_run`，证明唯一 completed run；旧 completed run 不得被复用。
- risk tensor 必须满足：

  ```text
  bond_count = count(bond rows) = 1750
  total_market_value = sum(bond.market_value)
  portfolio_dv01 = sum(bond.dv01)
  cs01 = sum(bond.spread_dv01)
  ```

  四项残差必须为 0。

### 8.3 非目标日期不变

不得使用 `bit_xor(hash(to_json(row)))` 作为验收依据：它既不能提供抗碰撞证明，也可能因行/类型序列化差异而不稳定。受支持入口必须同时提供一个经过测试的只读 verifier，使用以下固定算法生成 evidence：

1. 分别以 `read_only=True` 打开停写备份 DB 和回填后 DB；先比较完整 schema/table inventory、列名、列顺序和 DuckDB 类型。
2. 从 schema 取得并在 receipt 中固化每张表的显式列清单；按类型进行 canonical serialization：`NULL`、布尔、整数、`Decimal`（保留 scale）、ISO date/time、UTF-8 string 和 binary 必须有不同类型标签，禁止通过 `float` 或 locale 文本中转。
3. 每行计算 SHA256；将 row digest 按字节序排序后再计算 table SHA256，同时记录 row count。数据量较大时用受控临时目录做外部排序，不得只保留交换律弱校验和。
4. 对允许写入的六张表，目标日行可以变化，但 `date <> 2026-07-31` 的 row count/table SHA256 必须与备份一致：

   - `zqtz_bond_daily_snapshot`
   - `tyw_interbank_daily_snapshot`
   - `fact_formal_zqtz_balance_daily`
   - `fact_formal_tyw_balance_daily`
   - `fact_formal_bond_analytics_daily`
   - `fact_formal_risk_tensor_daily`

   这六张表的日期列均为 `report_date`；verifier 必须把该列解析为 ISO date 后过滤，不能依赖字符串排序。

5. `fx_daily_mid` 和 `fact_formal_yield_curve_daily` 本次为冻结只读输入，必须整表 row count/table SHA256 不变，包括目标日或 fallback date；两表的日期列均为 `trade_date`。
6. 对数据库中其余所有表做整表 row count/table SHA256 比较；尤其要覆盖 formal/non-standard PnL、product-category、accounting movement、source-preview/precompute 及其 read models。不得仅检查“预计会改”的表，因为本验收的目的也包括发现越界写入。
7. 对 archive root 重新生成与第 5.1 节相同的 relative-path/bytes/mtime/SHA256 inventory，并与基线逐项相等；本次入口禁止生成任何新 archive。对 `source_manifest.jsonl` 的文件 SHA 也必须与基线相等。
8. SQL authority 另做 schema/table inventory 与 canonical sorted row SHA256：`cache_build_run`/`cache_manifest` 只允许新增本次 balance/bond/risk 的 target cache key + report date + run ID 行，其余历史行必须不变。若配置 SQL job state，`job_run_state` 只允许本次明确 run ID 的合同内状态迁移，其他行必须不变。DBA evidence 必须同时给出 before/after 全表摘要、允许 delta 明细和 verdict；目标行 SQL↔JSONL parity 不能替代非目标行不变证明。

schema/table inventory 必须相同；任一不在上述明确允许 delta 内的 row count 或 table SHA256 变化都视为失败并进入回滚。verifier 源码版本、显式列清单、临时目录、两侧摘要和最终 verdict 必须保存在 evidence packet；仅保存屏幕输出不合格。

### 8.4 治理终态

- snapshot 只核对 JSONL `snapshot_build_run` 与 `snapshot_manifest`：当前 task 合同只追加一个 completed 或 failed terminal，不存在持久化 queued/running；本次必须恰有一个新 completed build-run、不得有同 run 的 failed terminal，并恰有 ZQTZ/TYW 两条 completed manifest。manifest 的 source linkage 必须唯一连接第 2 节锁定的两条 `source_manifest`，由该 source manifest + 目标事实 slice 证明 report date/batch；snapshot 记录本身没有 `report_date` 字段，不应虚构。snapshot 也不应被误判为必须存在 formal cache manifest。
- balance、bond、risk 分别核对正式 cache 流：

  | stage | cache key | rule/cache version |
  | --- | --- | --- |
  | balance | `balance_analysis:materialize:formal` | `rv_balance_analysis_formal_materialize_v1` / `cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1` |
  | bond | `bond_analytics:materialize:formal` | `rv_bond_analytics_formal_materialize_v1` / `cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1` |
  | risk | `risk_tensor:materialize:formal` | `rv_risk_tensor_formal_materialize_v5` / `cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v5` |

- 三个 stage 的 `cache_build_run` 状态都必须严格为 queued → running → completed，且各有一条与 run ID、report date、source/rule/cache、input sources、fact tables 一致的 `cache_manifest`；
- 不得有同 run ID 的后续 failed/running/queued；
- DuckDB 成功但 terminal governance write 失败属于整体失败，不得以事实表存在宣称成功。
- SQL-authority 模式下，仅 balance/bond/risk 的 cache streams 要求权威 SQL 与 JSONL mirror 逐字段、逐 run 对平；snapshot/source streams 继续按其 JSONL 权威合同单独核对。mirror 成功不能替代 SQL authority 成功，反之亦然。
- 受支持入口还必须输出独立的机器 receipt，汇总四阶段状态、输入 SHA、各表行数、治理 run ID 和 verifier digest。不同治理 stream 的字段集合不一致，不能拿一份通用 manifest 断言替代 stage-specific 检查。

## 9. 重启与正式读面冒烟

只有第 8 节全部通过后才重启 API/worker。重启会同时清除 API 与 worker 的进程内缓存，避免把本地 cache invalidation 当成跨进程协议。

用只读 GET 或服务调用核对：

1. balance overview：`basis=formal`、`formal_use_allowed=true`、日期和新 lineage 正确；
2. bond DV01 risk：1,750 positions，正式 source/rule/cache 与新 completed run 一致；
3. risk tensor：`basis=formal`、`evidence_rows=1`、市场价值/DV01/CS01 与 SQL 相等。

不得调用任何 refresh、backfill 或 mutation API 做冒烟。

## 10. 回滚

触发条件包括：阶段失败、治理终态失败、非目标日期变化、Decimal/FX/trace/risk 对平失败、读面 lineage 仍旧、异常网络写入或 owner 要求撤回。

1. 再次停止 API/worker 和 supervisor。
2. 将失败现场的 DB 与治理目录复制到独立 forensic 目录；不要覆盖原备份。
3. 校验第 6 节 DuckDB、JSONL governance 以及（如适用）SQL governance 备份 ID、哈希和文件清单。
4. 在同一停写窗口内按 owner/DBA 批准的协调顺序恢复：SQL governance 与 job-state（如适用）、整个 JSONL 治理目录、DuckDB，以及完整 archive namespace。对于本地 archive，按第 5.1 节 inventory 恢复全部原文件并通过批准的存储恢复流程清除/隔离新增孤儿文件；对于版本化对象存储，将整个 namespace 恢复到记录的对象版本集合。这里的“协调”不表示跨存储物理原子，而表示任何 reader/writer 重启前所有权威存储都恢复到第 6 节同一静止点。
5. 禁止只恢复数据库、只恢复 JSONL mirror、只恢复 SQL authority，或把失败执行生成的新 archive 留在可选输入范围内。
6. 恢复后重新校验备份 SHA、目标日期计数、全库 verifier digest、SQL↔JSONL parity 和治理 latest terminal。
7. 所有恢复验证通过后才重启服务，并执行第 9 节只读冒烟。
8. 在维护工单记录失败阶段、错误类别、是否发生 DuckDB commit、治理终态是否写入、回滚 artifact/LSN/hash 和后续 owner。

不得通过手工改事实表、删除单条治理 JSONL 或伪造 completed 终态来“修复”回填失败。

## 11. 成功判定

只有同时满足以下条件才可宣布生产单日回填成功：

- 第 4 节受支持入口与测试已完成；
- 有本次生产写入的明确 owner 批准和维护窗口；
- 同一静止点的 DuckDB、JSONL governance、锁定 archive，以及（如适用）SQL governance/job-state 备份已经完成恢复演练；
- 四阶段均 completed，输入哈希与锁定合同一致；
- parser、grain、FX、formal balance、bond、risk 全部对平；
- 非目标日期及所有范围外表的强 SHA256 digest 完全不变，FX/曲线整表不变；
- 正式读面使用新 lineage 且数值与 SQL 一致；
- 生产 evidence packet 保存了基线、receipt、验收输出、警告与备份路径。

当前状态只满足“隔离演练与只读口径已经验证”，**不满足生产执行授权**。
